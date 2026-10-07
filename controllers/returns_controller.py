"""
controllers/returns_controller.py
==================================
Gestión de anulaciones y devoluciones de ventas.

Operaciones soportadas:
  - cancel_sale     → Anulación total: restaura TODO el stock y descuenta de caja.
  - return_items    → Devolución parcial: restaura solo los ítems seleccionados.
  - get_sale_with_details → Datos completos de un ticket para mostrar en la vista.
  - get_sales_for_returns → Lista de ventas (con filtros) para el panel izquierdo.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
from database.models import (
	ArticleVariant,
	CashMovement,
	CashSession,
	ComboItem,
	Customer,
	Sale,
	Stock,
	StockMovement,
)

logger = logging.getLogger(__name__)

_OPERABLE = {'completada', 'pendiente', 'parcial'}


class ReturnsController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def get_sales_for_returns(self, tenant_id, filter_key='all', limit=300):
		with self._Session() as session:
			try:
				q = (
					session.query(Sale)
					.options(
						joinedload(Sale.customer),
						joinedload(Sale.user),
					)
					.filter(Sale.tenant_id == tenant_id)
					.order_by(Sale.date.desc())
				)

				today = datetime.now().date()
				if filter_key == 'today':
					q = q.filter(
						Sale.date >= datetime.combine(today, datetime.min.time())
					)
				elif filter_key == 'week':
					week_start = today - timedelta(days=today.weekday())
					q = q.filter(
						Sale.date >= datetime.combine(week_start, datetime.min.time())
					)
				elif filter_key == 'fiado':
					q = q.filter(Sale.payment_method == 'fiado')
				elif filter_key == 'anuladas':
					q = q.filter(Sale.status == 'anulada')

				sales = q.limit(limit).all()

				return [
					{
						'id': s.id,
						'date': s.date,
						'total_amount': float(s.total_amount or 0),
						'discount_amount': float(s.discount_amount or 0),
						'payment_method': s.payment_method or '',
						'payment_method_2': s.payment_method_2 or '',
						'amount_method_2': float(s.amount_method_2 or 0),
						'status': s.status or 'completada',
						'customer_name': s.customer.name
						if s.customer
						else 'Consumidor Final',
						'user_name': get_display_name(s.user) if s.user else '—',
						'quotation_number': s.quotation_number or '',
					}
					for s in sales
				]
			except Exception as e:
				logger.error(
					f'Error al obtener ventas para devoluciones: {e}', exc_info=True
				)
				return []

	def get_sale_with_details(self, tenant_id, sale_id):
		with self._Session() as session:
			try:
				sale = (
					session.query(Sale)
					.options(
						joinedload(Sale.items),
						joinedload(Sale.customer),
						joinedload(Sale.user),
					)
					.filter_by(id=sale_id, tenant_id=tenant_id)
					.first()
				)
				if not sale:
					return None

				return {
					'id': sale.id,
					'date': sale.date,
					'total_amount': float(sale.total_amount or 0),
					'discount_amount': float(sale.discount_amount or 0),
					'profit': float(sale.profit or 0),
					'payment_method': sale.payment_method or '',
					'payment_method_2': sale.payment_method_2 or '',
					'amount_method_2': float(sale.amount_method_2 or 0),
					'status': sale.status or 'completada',
					'customer_name': sale.customer.name
					if sale.customer
					else 'Consumidor Final',
					'customer_id': sale.customer_id,
					'user_name': get_display_name(sale.user) if sale.user else '—',
					'quotation_number': sale.quotation_number or '',
					'items': [
						{
							'detail_id': d.id,
							'variant_id': d.variant_id,
							'description': d.description,
							'quantity': float(d.quantity),
							'returned_quantity': float(d.returned_quantity or 0),
							'unit_price': float(d.unit_price),
							'unit_cost': float(d.unit_cost),
							'subtotal': float(d.subtotal),
						}
						for d in sale.items
					],
				}
			except Exception as e:
				logger.error(
					f'Error al obtener detalle de venta {sale_id}: {e}', exc_info=True
				)
				return None

	def cancel_sale(self, tenant_id, sale_id, user_id):
		with self._Session() as session:
			try:
				sale = (
					session.query(Sale)
					.options(joinedload(Sale.items), joinedload(Sale.customer))
					.filter_by(id=sale_id, tenant_id=tenant_id)
					.with_for_update()
					.first()
				)
				if not sale:
					return False, 'Ticket no encontrado.'
				if sale.status not in _OPERABLE:
					estado = sale.status or 'desconocido'
					return (
						False,
						f'Este ticket ya fue marcado como "{estado}". No se puede anular.',
					)

				# Verificar caja ANTES de modificar stock para evitar estado inconsistente
				pm1 = (sale.payment_method or '').lower()
				pm2 = (sale.payment_method_2 or '').lower()
				if pm1 not in ('', 'fiado') or (pm2 and pm2 != 'fiado'):
					active_cash_pre = (
						session.query(CashSession)
						.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
						.first()
					)
					if not active_cash_pre:
						metodo = pm1 or pm2
						return False, (
							f'No hay caja abierta. Abrí la caja antes de '
							f'anular un pago en {metodo}.'
						)

				# BUG 17: en ventas parcialmente devueltas, solo restaurar el stock
				# restante (original - ya devuelto) para no sobre-reponer inventario
				qty_override_cancel = {
					d.id: Decimal(str(d.quantity))
					- Decimal(str(d.returned_quantity or 0))
					for d in sale.items
				}
				details_to_restore = [
					d
					for d in sale.items
					if qty_override_cancel.get(d.id, Decimal('0')) > 0
				]
				warnings = self._restore_stock_for_items(
					session,
					details_to_restore,
					sale_id,
					user_id,
					label='Anulación',
					qty_override=qty_override_cancel,
					tenant_id=tenant_id,
				)

				total = Decimal(str(sale.total_amount or 0))
				# BUG 16: subtract already-returned amount to avoid double refund
				# when cancelling a sale that was fully (or partially) returned.
				already_returned = Decimal(str(sale.total_returned or 0))
				refund_amount = max(total - already_returned, Decimal('0'))
				self._register_financial_reversal(
					session,
					tenant_id,
					user_id,
					sale,
					refund_amount,
					description=f'Anulación Ticket #{sale_id}',
				)

				sale.status = 'anulada'
				sale.profit = Decimal('0')
				_customer_name = (
					sale.customer.name if sale.customer else 'Consumidor Final'
				)
				session.commit()

				try:
					from controllers.receipt_controller import ReceiptController

					date_str = datetime.now().strftime('%d/%m/%Y  %H:%M')
					ReceiptController().generate_credit_note(
						tenant_id=tenant_id,
						sale_id=sale_id,
						date_str=date_str,
						items_returned=[],
						refund_total=float(refund_amount),
						customer_name=_customer_name,
						note_type='Anulación',
					)
				except Exception as nc_err:
					logger.warning(
						f'Venta anulada, pero falló la nota de crédito: {nc_err}'
					)

				msg = f'Ticket #{sale_id} anulado correctamente. Total reembolsado: ${refund_amount:.2f}'
				if warnings:
					msg += '\n\nAvisos:\n' + '\n'.join(f'• {w}' for w in warnings)
				return True, msg

			except Exception as e:
				session.rollback()
				logger.error(f'Error al anular venta {sale_id}: {e}', exc_info=True)
				return False, f'Error interno al anular el ticket: {e}'

	def return_items(self, tenant_id, sale_id, user_id, items_to_return):
		if not items_to_return:
			return False, 'No seleccionaste ningún ítem para devolver.'

		with self._Session() as session:
			try:
				sale = (
					session.query(Sale)
					.options(joinedload(Sale.items), joinedload(Sale.customer))
					.filter_by(id=sale_id, tenant_id=tenant_id)
					.with_for_update()
					.first()
				)
				if not sale:
					return False, 'Ticket no encontrado.'
				if sale.status not in _OPERABLE:
					return (
						False,
						f'El ticket ya fue marcado como "{sale.status}". No se puede devolver.',
					)

				# Verificar caja ANTES de modificar stock para evitar estado inconsistente
				pm1_ret = (sale.payment_method or '').lower()
				pm2_ret = (sale.payment_method_2 or '').lower()
				if pm1_ret not in ('', 'fiado') or (pm2_ret and pm2_ret != 'fiado'):
					active_cash_pre = (
						session.query(CashSession)
						.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
						.first()
					)
					if not active_cash_pre:
						metodo = pm1_ret or pm2_ret
						return False, (
							f'No hay caja abierta. Abrí la caja antes de '
							f'devolver un pago en {metodo}.'
						)

				detail_map = {d.id: d for d in sale.items}

				# CORRECCIÓN: Factor de descuento para calcular reembolsos exactos
				sale_total_gross = sum(Decimal(str(d.subtotal)) for d in sale.items)
				discount_amount = Decimal(str(sale.discount_amount or 0))
				if sale_total_gross > 0:
					raw_factor = (sale_total_gross - discount_amount) / sale_total_gross
					if raw_factor < 0:
						# BUG 14: discount_amount supera el bruto — datos inconsistentes
						logger.warning(
							'discount_amount (%s) supera sale_total_gross (%s) en ticket %s',
							discount_amount,
							sale_total_gross,
							sale_id,
						)
						# Si el descuento supera el bruto, el cliente no pagó nada (o recibió dinero).
						# El reembolso debe ser $0, no el precio completo.
						discount_factor = Decimal('0')
					else:
						discount_factor = max(
							Decimal('0.0001'), min(raw_factor, Decimal('1'))
						)
				else:
					discount_factor = Decimal('1')

				# Consolidar antes de validar. Sin esto una petición que repite el
				# mismo detail_id valida cada fila contra el saldo anterior y puede
				# reembolsar más unidades que las vendidas.
				return_map = {}
				for r in items_to_return:
					did = str(r['detail_id'])
					qty = Decimal(str(r['qty_to_return']))
					if did not in detail_map:
						return False, f'Ítem #{did} no pertenece a este ticket.'
					if qty <= 0:
						return False, (
							f'Cantidad inválida para "{detail_map[did].description}": debe ser mayor a cero.'
						)
					return_map[did] = return_map.get(did, Decimal('0')) + qty

				refund_total = Decimal('0')
				profit_reduction = Decimal('0')

				for did, qty in return_map.items():
					original_qty = Decimal(str(detail_map[did].quantity))
					already_ret = Decimal(str(detail_map[did].returned_quantity or 0))
					available = original_qty - already_ret
					if qty > available:
						return (
							False,
							f'Cantidad inválida para "{detail_map[did].description}": máximo disponible {available:.2f}.',
						)

					# CORRECCIÓN: Cálculos ajustados por descuentos y costos
					unit_price = Decimal(str(detail_map[did].unit_price))
					unit_cost = Decimal(str(detail_map[did].unit_cost))

					effective_price = unit_price * discount_factor
					refund_total += effective_price * qty
					profit_reduction += (effective_price - unit_cost) * qty

				selected_details = [detail_map[did] for did in return_map]
				warnings = self._restore_stock_for_items(
					session,
					selected_details,
					sale_id,
					user_id,
					label='Devolución',
					qty_override=return_map,
					tenant_id=tenant_id,
				)

				self._register_financial_reversal(
					session,
					tenant_id,
					user_id,
					sale,
					refund_total,
					description=f'Devolución parcial Ticket #{sale_id}',
				)

				# Registrar las cantidades devueltas por ítem para evitar dobles devoluciones
				for did, qty in return_map.items():
					detail_map[did].returned_quantity = (
						Decimal(str(detail_map[did].returned_quantity or 0)) + qty
					)

				new_total_returned = (
					Decimal(str(sale.total_returned or 0)) + refund_total
				)
				# BUG 4: capping evita violar el CHECK constraint total_returned <= total_amount
				# ante errores de redondeo acumulados en devoluciones parciales sucesivas
				total_sale = Decimal(str(sale.total_amount or 0))
				sale.total_returned = min(new_total_returned, total_sale)
				if total_sale > 0:
					net_remaining = total_sale - new_total_returned
					sale.status = (
						'devuelta' if net_remaining <= Decimal('0') else 'parcial'
					)
				else:
					# Venta sin valor monetario: estado basado en cantidades devueltas
					all_qty_returned = all(
						Decimal(str(d.returned_quantity or 0))
						>= Decimal(str(d.quantity))
						for d in sale.items
					)
					sale.status = 'devuelta' if all_qty_returned else 'parcial'
				new_profit = Decimal(str(sale.profit or 0)) - profit_reduction
				sale.profit = new_profit
				_new_status = sale.status
				_customer_name = (
					sale.customer.name if sale.customer else 'Consumidor Final'
				)
				_nc_items = [
					{
						'desc': detail_map[did].description,
						'qty': float(qty),
						'price': float(detail_map[did].unit_price * discount_factor),
						'subtotal': float(
							(detail_map[did].unit_price * discount_factor) * qty
						),
					}
					for did, qty in return_map.items()
				]

				session.commit()

				try:
					from controllers.receipt_controller import ReceiptController

					date_str = datetime.now().strftime('%d/%m/%Y  %H:%M')
					ReceiptController().generate_credit_note(
						tenant_id=tenant_id,
						sale_id=sale_id,
						date_str=date_str,
						items_returned=_nc_items,
						refund_total=float(refund_total),
						customer_name=_customer_name,
						note_type='Devolución',
					)
				except Exception as nc_err:
					logger.warning(
						f'Devolución registrada, pero falló la nota de crédito: {nc_err}'
					)

				msg = f'Devolución registrada. Reembolso: ${refund_total:.2f}\nEstado del ticket: {_new_status.upper()}'
				if warnings:
					msg += '\n\nAvisos:\n' + '\n'.join(f'• {w}' for w in warnings)
				return True, msg

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error en devolución parcial {sale_id}: {e}', exc_info=True
				)
				return False, f'Error interno al procesar la devolución: {e}'

	def _restore_stock_for_items(
		self,
		session,
		details,
		sale_id,
		user_id,
		label='Devolución',
		qty_override=None,
		tenant_id=None,
	):
		warnings = []
		variant_ids = [d.variant_id for d in details if d.variant_id]
		variants_db = {}
		if variant_ids:
			variants_db = {
				v.id: v
				for v in session.query(ArticleVariant)
				.options(
					joinedload(ArticleVariant.ingredients).joinedload(
						ComboItem.ingredient
					)
				)
				.filter(ArticleVariant.id.in_(variant_ids))
				.all()
			}

		# Pre-cargar todos los stocks necesarios en una sola consulta
		_stock_ids = set()
		for _detail in details:
			if not _detail.variant_id:
				continue
			_v = variants_db.get(_detail.variant_id)
			if not _v:
				continue
			if _v.is_combo:
				for _ci in _v.ingredients:
					_stock_ids.add(_ci.ingredient_id)
			else:
				_stock_ids.add(_v.base_variant_id or _detail.variant_id)
		stocks_map = defaultdict(list)
		if _stock_ids:
			for stock_row in (
				session.query(Stock)
				.filter(Stock.variant_id.in_(_stock_ids))
				.with_for_update()
				.all()
			):
				stocks_map[stock_row.variant_id].append(stock_row)

		def restore_target(variant_id):
			"""Choose a stable destination row instead of an arbitrary dict overwrite."""
			rows = stocks_map.get(variant_id, [])
			if not rows:
				return None
			return min(
				rows,
				key=lambda s: (
					s.expiration_date is None,
					s.expiration_date or date.max,
					s.warehouse_id,
					s.id,
				),
			)

		for detail in details:
			if not detail.variant_id:
				continue

			qty = (
				qty_override.get(detail.id, Decimal(str(detail.quantity)))
				if qty_override
				else Decimal(str(detail.quantity))
			)
			variant = variants_db.get(detail.variant_id)

			if not variant:
				warnings.append(
					f'No se encontró el producto "{detail.description}" en el sistema.'
				)
				continue

			if variant.is_combo:
				for ci in variant.ingredients:
					req_qty = Decimal(str(ci.quantity_required)) * qty
					stock = restore_target(ci.ingredient_id)
					if stock:
						stock.quantity += req_qty
						session.add(
							StockMovement(
								movement_type='in',
								quantity=req_qty,
								reference=f'{label} Ticket #{sale_id}',
								dest_warehouse_id=stock.warehouse_id,
								variant_id=ci.ingredient_id,
								user_id=user_id,
								tenant_id=tenant_id,
							)
						)
					else:
						warnings.append(
							f'Sin registro de stock para ingrediente de "{detail.description}".'
						)
			else:
				target_vid = variant.base_variant_id or detail.variant_id
				restore_qty = (
					qty * Decimal(str(variant.units_per_pack or 1))
					if variant.base_variant_id
					else qty
				)
				stock = restore_target(target_vid)
				if stock:
					stock.quantity += restore_qty
					session.add(
						StockMovement(
							movement_type='in',
							quantity=restore_qty,
							reference=f'{label} Ticket #{sale_id}',
							dest_warehouse_id=stock.warehouse_id,
							variant_id=target_vid,
							user_id=user_id,
							tenant_id=tenant_id,
						)
					)
				else:
					warnings.append(
						f'Sin registro de stock para "{detail.description}".'
					)

		return warnings

	def _register_financial_reversal(
		self, session, tenant_id, user_id, sale, amount, description
	):
		if amount <= 0:
			return

		def process_method(method, split_amount):
			if not method or split_amount <= 0:
				return

			# CORRECCIÓN: Lógica encapsulada para procesar correctamente métodos combinados
			if method == 'fiado' and sale.customer_id:
				customer = (
					session.query(Customer)
					.filter_by(id=sale.customer_id)
					.with_for_update()
					.first()
				)
				if customer:
					customer.current_balance = (
						customer.current_balance or Decimal('0.0')
					) - split_amount
			else:
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					raise RuntimeError(
						f'No hay caja abierta. Abrí la caja antes de registrar una devolución en {method}.'
					)
				session.add(
					CashMovement(
						tenant_id=tenant_id,
						session_id=active_cash.id,
						# Un reintegro digital no extrae efectivo del cajón. El
						# resumen de caja sólo descuenta ``gasto`` físico.
						movement_type=(
							'gasto' if method == 'efectivo' else 'gasto_digital'
						),
						amount=split_amount,
						description=f'{description} ({method.capitalize()})',
					)
				)

		pm1 = (sale.payment_method or '').lower()
		pm2 = (sale.payment_method_2 or '').lower()

		if pm2 and sale.amount_method_2:
			amt_m2 = Decimal(str(sale.amount_method_2))
			# Usar amount_method_1 y amount_method_2 almacenados en la venta original.
			# Esto es determinista y no depende de búsquedas de texto en descripciones.
			amt_m1_stored = (
				Decimal(str(sale.amount_method_1)) if sale.amount_method_1 else None
			)
			if amt_m1_stored and amt_m1_stored > 0:
				original_total = amt_m1_stored + amt_m2
			else:
				# Fallback para ventas antiguas sin amount_method_1
				original_total = amount

			if original_total <= 0:
				original_total = amount

			ratio_m2 = min(amt_m2 / original_total, Decimal('1'))
			refund_m2 = (amount * ratio_m2).quantize(Decimal('0.01'))
			refund_m1 = amount - refund_m2

			process_method(pm1, refund_m1)
			process_method(pm2, refund_m2)
		else:
			process_method(pm1, amount)
