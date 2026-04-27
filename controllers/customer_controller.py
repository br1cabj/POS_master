import logging
import re
from decimal import Decimal, InvalidOperation

from controllers.base import BaseController
from database.models import CashMovement, CashSession, Customer
from utils.config import make_engine
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)

_default_engine = make_engine()


class CustomerController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		super().__init__(engine)

	def _parse_decimal(self, value):
		return parse_decimal(value, default=None)

	@staticmethod
	def _validate_phone(phone):
		"""Valida que el teléfono solo contenga caracteres permitidos. Retorna None si está vacío."""
		if not phone:
			return None
		phone_clean = str(phone).strip()
		if phone_clean and not re.match(r'^[0-9\s\-\+\(\)]{6,}$', phone_clean):
			return False
		return phone_clean

	def get_customers(self, tenant_id):
		"""Retorna clientes activos del tenant ordenados por nombre."""
		with self._Session() as session:
			try:
				return [
					{
						'id': c.id,
						'name': c.name,
						'phone': c.phone,
						'current_balance': c.current_balance,
					}
					for c in session.query(Customer)
					.filter(Customer.tenant_id == tenant_id, Customer.is_active == True)  # noqa: E712
					.order_by(Customer.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def add_customer(self, tenant_id, name, phone):
		"""Crea un cliente nuevo o reactiva uno dado de baja lógicamente."""
		if not name or not str(name).strip():
			return False, 'El nombre del cliente es obligatorio.'

		name_clean = str(name).strip()
		phone_clean = self._validate_phone(phone)
		if phone and phone_clean is False:
			return False, 'Número de teléfono con formato inválido.'

		with self._Session() as session:
			try:
				exist = (
					session.query(Customer)
					.filter_by(name=name_clean, tenant_id=tenant_id)
					.first()
				)
				if exist:
					if exist.is_active:
						return False, 'Ese cliente ya existe en el sistema.'
					exist.is_active = True
					exist.phone = phone_clean
					session.commit()
					return True, 'Cliente reactivado con éxito.'

				session.add(
					Customer(
						tenant_id=tenant_id,
						name=name_clean,
						phone=phone_clean,
						current_balance=Decimal('0.0'),
					)
				)
				session.commit()
				return True, 'Cliente registrado con éxito.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear cliente: {e}', exc_info=True)
				return False, 'Error interno al intentar crear el cliente.'

	def pay_debt(self, tenant_id, user_id, customer_id, amount):
		"""
		Registra el pago de cuenta corriente de forma atómica.
		Requiere caja abierta. Bloquea el registro del cliente con FOR UPDATE.
		"""
		amount_dec = self._parse_decimal(amount)
		if amount_dec is None or amount_dec <= Decimal('0.0'):
			return False, 'El monto a abonar debe ser un número válido mayor a cero.'

		with self._Session() as session:
			try:
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					return False, '⚠️ Abre la caja para registrar el pago.'

				customer = (
					session.query(Customer)
					.filter_by(id=customer_id, tenant_id=tenant_id)
					.with_for_update()
					.first()
				)
				if not customer:
					return False, 'Cliente no encontrado o no autorizado.'

				if customer.current_balance < amount_dec:
					return (
						False,
						f'Saldo insuficiente. Saldo actual: ${customer.current_balance:.2f}',
					)
				customer.current_balance -= amount_dec
				session.add(
					CashMovement(
						session_id=active_cash.id,
						movement_type='ingreso',
						amount=amount_dec,
						description=f'Abono de Cuenta Corriente: {customer.name}',
					)
				)
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
