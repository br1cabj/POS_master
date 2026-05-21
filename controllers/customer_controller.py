import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import func, or_

from controllers.base import BaseController
from database.models import CashMovement, CashSession, Customer, Sale
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)


class CustomerController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

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
		"""Retorna clientes activos del tenant ordenados por nombre, con fecha del último fiado."""
		with self._Session() as session:
			try:
				last_sale_sq = (
					session.query(
						Sale.customer_id,
						func.max(Sale.date).label('last_date'),
					)
					.filter(
						Sale.tenant_id == tenant_id,
						Sale.payment_method == 'fiado',
						Sale.status != 'anulada',
					)
					.group_by(Sale.customer_id)
					.subquery()
				)
				rows = (
					session.query(Customer, last_sale_sq.c.last_date)
					.outerjoin(last_sale_sq, Customer.id == last_sale_sq.c.customer_id)
					.filter(Customer.tenant_id == tenant_id, Customer.is_active.is_(True))
					.order_by(Customer.name)
					.all()
				)
				return [
					{
						'id': c.id,
						'name': c.name,
						'phone': c.phone,
						'current_balance': c.current_balance,
						'price_list': c.price_list or 'A',
						'last_movement': last_date,
					}
					for c, last_date in rows
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def add_customer(
		self, tenant_id: str, name: str, phone: Optional[str], price_list: str = 'A'
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
					exist.price_list = price_list if price_list in ('A', 'B') else 'A'
					session.commit()
					return True, 'Cliente reactivado con éxito.'

				# Creación nueva
				session.add(
					Customer(
						tenant_id=tenant_id,
						name=name_clean,
						phone=phone_clean,
						current_balance=Decimal('0.0'),
						price_list=price_list if price_list in ('A', 'B') else 'A',
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
		price_list: str = 'A',
	) -> Tuple[bool, str]:
		"""Actualiza nombre, teléfono y lista de precios de un cliente existente."""
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
				customer.price_list = price_list if price_list in ('A', 'B') else 'A'
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

				# Permite saldo a favor (ej: debe $100, paga $150 → queda en -$50)
				customer.current_balance = (
					customer.current_balance or Decimal('0.0')
				) - amount_dec

				session.add(
					CashMovement(
						session_id=active_cash.id,
						movement_type='ingreso',
						amount=amount_dec,
						description=f'Abono de Cuenta Corriente: {customer.name} [cid:{customer_id}]',
						customer_id=customer_id,
					)
				)

				balance_after = customer.current_balance  # capturar antes del commit (post-commit los atributos expiran)
				session.commit()

				# Mensaje dinámico según si quedó con saldo a favor o deuda
				if balance_after < 0:
					msg = f'Pago registrado. El cliente tiene un saldo A FAVOR de ${abs(balance_after):.2f}'
				else:
					msg = f'Pago registrado. Deuda restante: ${balance_after:.2f}'

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

				# 2. Buscar abonos/pagos: FK directa (registros nuevos) + ILIKE (registros
				# anteriores a v26 que no tienen customer_id).
				id_filter = f'%[cid:{customer_id}]%'
				# BUG 13: SQLite ilike is only ASCII-case-insensitive; use lower() on both
				# sides so names with accented chars (é, ñ) still match correctly.
				name_filter_lower = f'%abono de cuenta corriente: {customer.name.lower()}%'
				payments = (
					session.query(CashMovement)
					.join(CashSession, CashMovement.session_id == CashSession.id)
					.filter(
						CashSession.tenant_id == tenant_id,
						or_(
							CashMovement.customer_id == customer_id,
							CashMovement.description.ilike(id_filter),
							func.lower(CashMovement.description).like(name_filter_lower),
						),
					)
					.distinct()
					.all()
				)

				# 3. Unificar y estructurar datos
				ledger = []
				for s in sales:
					items_detail = [
						{
							'description': item.description,
							'quantity': float(item.quantity),
							'unit_price': float(item.unit_price),
							'subtotal': float(item.subtotal),
						}
						for item in s.items
					]
					ledger.append(
						{
							'date': getattr(s, 'date', None) or datetime.now(),
							'type': 'cargo',  # Aumenta la deuda
							'concept': f'Compra a crédito - Ticket #{s.id[:8]}',
							'amount': (s.total_amount or 0) - (s.total_returned or 0),
							'items': items_detail,
						}
					)

				for p in payments:
					p_date = p.time if p.time is not None else datetime.now()
					ledger.append(
						{
							'date': p_date,
							'type': 'abono',  # Reduce la deuda
							'concept': 'Abono / Pago en Caja',
							'amount': p.amount,
							'items': [],
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
