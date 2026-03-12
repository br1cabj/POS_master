import logging

from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession, Customer

logger = logging.getLogger(__name__)


class CustomerController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_float(self, value):
		"""Convierte valores de la UI a float de forma segura, soportando comas."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return float(value)
		except (ValueError, TypeError):
			return None

	def get_customers(self, tenant_id):
		"""Obtiene la lista de clientes activos ordenados por nombre y los devuelve como diccionarios"""
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
						# Reactivamos al cliente borrado
						exist.is_active = True
						exist.phone = phone
						session.commit()
						return True, 'Cliente reactivado con éxito.'

				new_customer = Customer(
					tenant_id=tenant_id,
					name=name_clean,
					phone=phone,
					current_balance=0.0,
				)
				session.add(new_customer)
				session.commit()
				return True, 'Cliente registrado con éxito.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear cliente: {e}', exc_info=True)
				return False, 'Error interno al intentar crear el cliente.'

	def pay_debt(self, tenant_id, user_id, customer_id, amount):
		"""Registra el pago de una deuda: descuenta el saldo del cliente y mete dinero a la caja"""
		amount_float = self._parse_float(amount)

		# Validación temprana y segura
		if amount_float is None or amount_float <= 0:
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

				# 2. Buscar al cliente y actualizar su saldo
				customer = session.query(Customer).filter_by(id=customer_id).first()
				if not customer:
					return False, 'Cliente no encontrado.'

				customer.current_balance -= amount_float

				# 3. Registrar el ingreso en la caja
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='ingreso',
					amount=amount_float,
					description=f'Abono de Cuenta Corriente: {customer.name}',
				)
				session.add(movement)

				session.commit()
				return (
					True,
					f'Pago de ${amount_float:.2f} registrado. Nueva deuda: ${customer.current_balance:.2f}',
				)

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al procesar pago del cliente {customer_id}: {e}',
					exc_info=True,
				)
				return False, 'Error interno al procesar el pago. Revisa los logs.'
