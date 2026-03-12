import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession, Customer

logger = logging.getLogger(__name__)


class CustomerController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_decimal(self, value):
		"""Convertimos a Decimal para evitar pérdida de centavos."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return Decimal(str(value))
		except (ValueError, TypeError, InvalidOperation):
			return None

	def get_customers(self, tenant_id):
		"""Obtiene la lista de clientes activos ordenados por nombre."""
		with self.Session() as session:
			try:
				customers = (
					session.query(Customer)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.order_by(Customer.name)
					.all()
				)

				return [
					{
						'id': c.id,
						'name': c.name,
						'phone': c.phone,
						'current_balance': c.current_balance,
					}
					for c in customers
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def add_customer(self, tenant_id, name, phone):
		"""Da de alta a un nuevo cliente o reactiva a uno borrado"""
		if not name or not str(name).strip():
			return False, 'El nombre del cliente es obligatorio.'

		name_clean = str(name).strip()
		phone_clean = str(phone).strip() if phone else None

		with self.Session() as session:
			try:
				exist = (
					session.query(Customer)
					.filter_by(name=name_clean, tenant_id=tenant_id)
					.first()
				)

				if exist:
					if exist.is_active:
						return False, 'Ese cliente ya existe en el sistema.'
					else:
						exist.is_active = True
						exist.phone = phone_clean
						session.commit()
						return True, 'Cliente reactivado con éxito.'

				new_customer = Customer(
					tenant_id=tenant_id,
					name=name_clean,
					phone=phone_clean,
					current_balance=Decimal('0.0'),
				)
				session.add(new_customer)
				session.commit()
				return True, 'Cliente registrado con éxito.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear cliente: {e}', exc_info=True)
				return False, 'Error interno al intentar crear el cliente.'

	def pay_debt(self, tenant_id, user_id, customer_id, amount):
		"""Registra el pago de una deuda de forma transaccional y segura."""
		amount_dec = self._parse_decimal(amount)

		if amount_dec is None or amount_dec <= Decimal('0.0'):
			return False, 'El monto a abonar debe ser un número válido mayor a cero.'

		with self.Session() as session:
			try:
				# 1. Verificar que la caja esté abierta
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					return False, '⚠️ Abre la caja para registrar el pago.'

				# 2. Buscar al cliente
				customer = (
					session.query(Customer)
					.filter_by(id=customer_id, tenant_id=tenant_id)
					.with_for_update()
					.first()
				)

				if not customer:
					return False, 'Cliente no encontrado o no autorizado.'

				# Opcional: Si NO quieres permitir que paguen de más (saldo a favor), descomenta esto:
				# if amount_dec > customer.current_balance:
				#     return False, f'El pago supera la deuda actual (${customer.current_balance:.2f}).'

				customer.current_balance -= amount_dec

				# 3. Registrar el ingreso en la caja
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='ingreso',
					amount=amount_dec,
					description=f'Abono de Cuenta Corriente: {customer.name}',
				)
				session.add(movement)

				session.commit()
				return (
					True,
					f'Pago de ${amount_dec:.2f} registrado. Nuevo saldo: ${customer.current_balance:.2f}',
				)

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al procesar pago del cliente {customer_id}: {e}',
					exc_info=True,
				)
				return False, 'Error interno al procesar el pago. Intente de nuevo.'
