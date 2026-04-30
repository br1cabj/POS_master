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
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
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
from utils.config import make_engine

logger = logging.getLogger(__name__)

_default_engine = make_engine()

_OPERABLE = {'completada', 'pendiente'}


class ReturnsController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		super().__init__(engine)

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
						'user_name': s.user.username if s.user else 'Desconocido',
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
					'user_name': sale.user.username if sale.user else 'Desconocido',
					'quotation_number': sale.quotation_number or '',
					'items': [
						{
							'detail_id': d.id,
							'variant_id': d.variant_id,
							'description': d.description,
							'quantity': float(d.quantity),
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
					return False, f'Este ticket ya fue {estado}. No se puede anular.'

				warnings = self._restore_stock_for_items(
					session, sale.items, sale_id, user_id, label='Anulación'
				)

				total = Decimal(str(sale.total_amount or 0))
				self._register_financial_reversal(
					session,
					tenant_id,
					user_id,
					sale,
					total,
					description=f'Anulación Ticket #{sale_id}',
				)

				sale.status = 'anulada'
				sale.profit = 0  # CORRECCIÓN: La ganancia se anula también
				session.commit()

				try:
					from controllers.receipt_controller import ReceiptController

					date_str = datetime.now().strftime('%d/%m/%Y  %H:%M')
					ReceiptController().generate_credit_note(
						tenant_id=tenant_id,
						sale_id=sale_id,
						date_str=date_str,
						items_returned=[],
						refund_total=float(total),
						customer_name=sale.customer.name
						if sale.customer
						else 'Consumidor Final',
						note_type='Anulación',
					)
				except Exception as nc_err:
					logger.warning(
						f'Venta anulada, pero falló la nota de crédito: {nc_err}'
					)

				msg = f'Ticket #{sale_id} anulado correctamente. Total reembolsado: ${total:.2f}'
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
						f'El ticket ya fue {sale.status}. No se puede devolver.',
					)

				detail_map = {d.id: d for d in sale.items}

				# CORRECCIÓN: Factor de descuento para calcular reembolsos exactos
				sale_total_gross = sum(Decimal(str(d.subtotal)) for d in sale.items)
				discount_amount = Decimal(str(sale.discount_amount or 0))
				discount_factor = (
					(sale_total_gross - discount_amount) / sale_total_gross
					if sale_total_gross > 0
					else Decimal('1')
				)

				return_map = {}
				refund_total = Decimal('0')
				profit_reduction = Decimal('0')

				for r in items_to_return:
					did = int(r['detail_id'])
					qty = Decimal(str(r['qty_to_return']))

					if did not in detail_map:
						return False, f'Ítem #{did} no pertenece a este ticket.'

					original_qty = Decimal(str(detail_map[did].quantity))
					if qty <= 0 or qty > original_qty:
						return (
							False,
							f'Cantidad inválida para "{detail_map[did].description}": máximo {original_qty:.2f}.',
						)

					return_map[did] = qty

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
				)

				self._register_financial_reversal(
					session,
					tenant_id,
					user_id,
					sale,
					refund_total,
					description=f'Devolución parcial Ticket #{sale_id}',
				)

				all_returned = all(
					return_map.get(d.id, Decimal('0')) >= Decimal(str(d.quantity))
					for d in sale.items
				)
				sale.status = 'devuelta' if all_returned else 'parcial'

				sale.total_amount = Decimal(str(sale.total_amount or 0)) - refund_total
				sale.profit = (
					Decimal(str(sale.profit or 0)) - profit_reduction
				)  # CORRECCIÓN: Ajuste contable de ganancia

				session.commit()

				try:
					from controllers.receipt_controller import ReceiptController

					date_str = datetime.now().strftime('%d/%m/%Y  %H:%M')
					nc_items = [
						{
							'desc': detail_map[did].description,
							'qty': float(qty),
							'price': float(
								detail_map[did].unit_price * discount_factor
							),
							'subtotal': float(
								(detail_map[did].unit_price * discount_factor) * qty
							),
						}
						for did, qty in return_map.items()
					]
					ReceiptController().generate_credit_note(
						tenant_id=tenant_id,
						sale_id=sale_id,
						date_str=date_str,
						items_returned=nc_items,
						refund_total=float(refund_total),
						customer_name=sale.customer.name
						if sale.customer
						else 'Consumidor Final',
						note_type='Devolución',
					)
				except Exception as nc_err:
					logger.warning(
						f'Devolución registrada, pero falló la nota de crédito: {nc_err}'
					)

				msg = f'Devolución registrada. Reembolso: ${refund_total:.2f}\nEstado del ticket: {sale.status.upper()}'
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
		self, session, details, sale_id, user_id, label='Devolución', qty_override=None
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
					stock = (
						session.query(Stock)
						.filter_by(variant_id=ci.ingredient_id)
						.first()
					)
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
							)
						)
					else:
						warnings.append(
							f'Sin registro de stock para ingrediente de "{detail.description}".'
						)
			else:
				stock = (
					session.query(Stock).filter_by(variant_id=detail.variant_id).first()
				)
				if stock:
					stock.quantity += qty
					session.add(
						StockMovement(
							movement_type='in',
							quantity=qty,
							reference=f'{label} Ticket #{sale_id}',
							dest_warehouse_id=stock.warehouse_id,
							variant_id=detail.variant_id,
							user_id=user_id,
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
					session.query(Customer).filter_by(id=sale.customer_id).first()
				)
				if customer:
					customer.current_balance -= split_amount
			else:
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					logger.warning(
						f'No hay caja abierta para registrar el reembolso de {split_amount} en {method}.'
					)
					return
				session.add(
					CashMovement(
						session_id=active_cash.id,
						movement_type='gasto',
						amount=split_amount,
						description=f'{description} ({method.capitalize()})',
					)
				)

		pm1 = (sale.payment_method or '').lower()
		pm2 = (sale.payment_method_2 or '').lower()

		if pm2 and sale.amount_method_2:
			amt_m2 = Decimal(str(sale.amount_method_2))
			sale_total_approx = Decimal(str(sale.total_amount or 0))
			if sale_total_approx <= 0:
				sale_total_approx = amount

			ratio_m2 = min(amt_m2 / sale_total_approx, Decimal('1'))
			refund_m2 = (amount * ratio_m2).quantize(Decimal('0.01'))
			refund_m1 = amount - refund_m2

			process_method(pm1, refund_m1)
			process_method(pm2, refund_m2)
		else:
			process_method(pm1, amount)
