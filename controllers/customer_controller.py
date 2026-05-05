import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from controllers.base import BaseController

# Asegúrate de importar 'Sale' para poder buscar las compras a crédito
from database.models import CashMovement, CashSession, Customer, Sale
from utils.config import make_engine
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)

_default_engine = None


def _get_default_engine():
	global _default_engine
	if _default_engine is None:
		_default_engine = make_engine()
	return _default_engine


class CustomerController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _get_default_engine()
		super().__init__(engine)

	def _parse_decimal(self, value: Any) -> Optional[Decimal]:
		return parse_decimal(value, default=None)

	@staticmethod
	def _validate_phone(phone: Any) -> Tuple[bool, Optional[str]]:
		"""
		Valida que el teléfono solo contenga caracteres permitidos.
		Retorna (es_valido, telefono_limpio).
		"""
		if not phone:
			return True, None

		phone_clean = str(phone).strip()
		if phone_clean and not re.match(r'^[0-9\s\-\+\(\)]{6,}$', phone_clean):
			return False, phone_clean

		return True, phone_clean

	def get_customers(self, tenant_id: str) -> List[Dict[str, Any]]:
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
					.filter(
						Customer.tenant_id == tenant_id, Customer.is_active.is_(True)
					)
					.order_by(Customer.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def add_customer(
		self, tenant_id: str, name: str, phone: Optional[str]
	) -> Tuple[bool, str]:
		"""Crea un cliente nuevo o reactiva uno dado de baja lógicamente."""
		if not name or not str(name).strip():
			return False, 'El nombre del cliente es obligatorio.'

		name_clean = str(name).strip()
		is_valid_phone, phone_clean = self._validate_phone(phone)

		if not is_valid_phone:
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

					# Reactivación
					exist.is_active = True
					exist.phone = phone_clean
					session.commit()
					return True, 'Cliente reactivado con éxito.'

				# Creación nueva
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

	def update_customer(
		self,
		tenant_id: str,
		customer_id: str,
		name: str,
		phone: Optional[str],
	) -> Tuple[bool, str]:
		"""Actualiza nombre, teléfono y tipo de un cliente existente."""
		if not name or not str(name).strip():
			return False, 'El nombre del cliente es obligatorio.'

		name_clean = str(name).strip()
		is_valid_phone, phone_clean = self._validate_phone(phone)
		if not is_valid_phone:
			return False, 'Número de teléfono con formato inválido.'

		with self._Session() as session:
			try:
				customer = (
					session.query(Customer)
					.filter_by(id=customer_id, tenant_id=tenant_id, is_active=True)
					.first()
				)
				if not customer:
					return False, 'Cliente no encontrado.'

				# Verificar duplicado de nombre (excluyendo el mismo cliente)
				conflict = (
					session.query(Customer)
					.filter(
						Customer.tenant_id == tenant_id,
						Customer.name == name_clean,
						Customer.is_active.is_(True),
						Customer.id != customer_id,
					)
					.first()
				)
				if conflict:
					return False, 'Ya existe otro cliente con ese nombre.'

				customer.name = name_clean
				customer.phone = phone_clean
				session.commit()
				return True, f"Cliente '{name_clean}' actualizado con éxito."
			except Exception as e:
				session.rollback()
				logger.error(f'Error al actualizar cliente {customer_id}: {e}', exc_info=True)
				return False, 'Error interno al actualizar el cliente.'

	def pay_debt(
		self,
		tenant_id: str,
		user_id: str,
		customer_id: str,
		amount: Union[str, float, Decimal],
	) -> Tuple[bool, str]:
		"""
		Registra el pago de cuenta corriente de forma atómica.
		Permite saldos a favor (montos mayores a la deuda).
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
				if not customer or not customer.is_active:
					return False, 'Cliente no encontrado o inactivo.'

				# SOLUCIÓN APLICADA: Se remueve la restricción de 'customer.current_balance < amount_dec'
				# Esto permite que si debe $100 y paga $150, la cuenta quede en -$50 (Saldo a favor)
				customer.current_balance -= amount_dec

				session.add(
					CashMovement(
						session_id=active_cash.id,
						movement_type='ingreso',
						amount=amount_dec,
						description=f'Abono de Cuenta Corriente: {customer.name} [cid:{customer_id}]',
					)
				)

				session.commit()

				# Mensaje dinámico según si quedó con saldo a favor o deuda
				if customer.current_balance < 0:
					msg = f'Pago registrado. El cliente tiene un saldo A FAVOR de ${abs(customer.current_balance):.2f}'
				else:
					msg = f'Pago registrado. Deuda restante: ${customer.current_balance:.2f}'

				return True, msg
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al procesar pago del cliente {customer_id}: {e}',
					exc_info=True,
				)
				return False, 'Error interno al procesar el pago. Intente de nuevo.'

	def get_customer_ledger(
		self, tenant_id: str, customer_id: str
	) -> List[Dict[str, Any]]:
		"""
		Retorna el historial cronológico de un cliente: Compras a crédito (fiado) y Pagos.
		Ideal para el modal de 'Estado de Cuenta'.
		"""
		with self._Session() as session:
			try:
				# 1. Buscar las compras a crédito (fiado) del cliente (excluyendo anuladas)
				sales = (
					session.query(Sale)
					.filter_by(
						tenant_id=tenant_id,
						customer_id=customer_id,
						payment_method='fiado',
					)
					.filter(Sale.status != 'anulada')
					.all()
				)

				# Obtenemos los datos del cliente para buscar sus abonos en los movimientos de caja
				customer = (
					session.query(Customer)
					.filter_by(id=customer_id, tenant_id=tenant_id)
					.first()
				)
				if not customer:
					return []

				# 2. Buscar los abonos/pagos. Se busca por ID de cliente (nuevo formato)
				# y por nombre (compatibilidad con registros anteriores al fix).
				id_filter = f'%[cid:{customer_id}]%'
				name_filter = f'%Abono de Cuenta Corriente: {customer.name}%'
				payments = (
					session.query(CashMovement)
					.join(CashSession, CashMovement.session_id == CashSession.id)
					.filter(
						CashSession.tenant_id == tenant_id,
						(
							CashMovement.description.ilike(id_filter)
							| CashMovement.description.ilike(name_filter)
						),
					)
					.all()
				)

				# 3. Unificar y estructurar datos
				ledger = []
				for s in sales:
					ledger.append(
						{
							'date': getattr(s, 'date', None) or datetime.now(),
							'type': 'cargo',  # Aumenta la deuda
							'concept': f'Compra a crédito - Ticket #{s.id}',
							'amount': s.total_amount,
						}
					)

				for p in payments:
					# Diferentes ORMs usan date o created_at. Nos aseguramos de obtener la fecha.
					p_date = getattr(
						p, 'created_at', getattr(p, 'date', datetime.now())
					)
					ledger.append(
						{
							'date': p_date,
							'type': 'abono',  # Reduce la deuda
							'concept': 'Abono / Pago en Caja',
							'amount': p.amount,
						}
					)

				# 4. Ordenar del más reciente al más antiguo (para que lo último aparezca arriba en la tabla)
				ledger.sort(key=lambda x: x['date'], reverse=True)
				return ledger

			except Exception as e:
				logger.error(
					f'Error al obtener historial del cliente {customer_id}: {e}',
					exc_info=True,
				)
				return []
