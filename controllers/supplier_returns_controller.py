import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import (
	CashMovement,
	CashSession,
	Purchase,
	PurchaseReturn,
	PurchaseReturnItem,
	Stock,
	StockMovement,
	Supplier,
)

logger = logging.getLogger(__name__)

REASONS = [
	'Producto defectuoso',
	'Excedente de stock',
	'Error de precio',
	'Producto vencido',
	'Otro',
]

REFUND_TYPES = ['efectivo', 'credito']


class SupplierReturnsController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _get_already_returned(self, session, purchase_id: str) -> dict:
		"""Devuelve {detail_id: Decimal(cantidad_devuelta)} para una compra."""
		already_returned: dict[str, Decimal] = {}
		for ret in (
			session.query(PurchaseReturn)
			.filter_by(purchase_id=purchase_id)
			.options(joinedload(PurchaseReturn.items))
			.all()
		):
			for ri in ret.items:
				if ri.purchase_detail_id:
					already_returned[ri.purchase_detail_id] = (
						already_returned.get(ri.purchase_detail_id, Decimal('0'))
						+ Decimal(str(ri.quantity_returned))
					)
		return already_returned

	def get_purchases(self, tenant_id, limit=300):
		"""Lista compras con detalle de proveedor para mostrar en el panel izquierdo."""
		with self._Session() as session:
			try:
				purchases = (
					session.query(Purchase)
					.options(joinedload(Purchase.supplier), joinedload(Purchase.items))
					.filter(Purchase.tenant_id == tenant_id)
					.order_by(Purchase.date.desc())
					.limit(limit)
					.all()
				)
				result = []
				for p in purchases:
					items_count = len(p.items)
					result.append(
						{
							'id': p.id,
							'date': p.date,
							'total_amount': float(p.total_amount or 0),
							'status': p.status or 'pagada',
							'invoice_number': p.invoice_number or '',
							'supplier_name': p.supplier.name
							if p.supplier
							else 'Sin proveedor',
							'supplier_id': p.supplier_id,
							'items_count': items_count,
							'has_details': items_count > 0,
						}
					)
				return result
			except Exception as e:
				logger.error(f'Error al obtener compras: {e}', exc_info=True)
				return []

	def get_purchase_with_details(self, tenant_id, purchase_id):
		"""Devuelve la compra con sus ítems y cuánto ya fue devuelto por ítem."""
		with self._Session() as session:
			try:
				purchase = (
					session.query(Purchase)
					.options(
						joinedload(Purchase.supplier),
						joinedload(Purchase.items),
					)
					.filter_by(id=purchase_id, tenant_id=tenant_id)
					.first()
				)
				if not purchase:
					return None

				already_returned = self._get_already_returned(session, purchase_id)

				items = []
				for d in purchase.items:
					qty = Decimal(str(d.quantity))
					returned = already_returned.get(d.id, Decimal('0'))
					available = qty - returned
					items.append(
						{
							'detail_id': d.id,
							'variant_id': d.variant_id,
							'description': d.description,
							'quantity': float(qty),
							'unit_cost': float(d.unit_cost),
							'subtotal': float(d.subtotal),
							'already_returned': float(returned),
							'available': float(available),
						}
					)

				return {
					'id': purchase.id,
					'date': purchase.date,
					'total_amount': float(purchase.total_amount or 0),
					'status': purchase.status or 'pagada',
					'invoice_number': purchase.invoice_number or '',
					'supplier_name': purchase.supplier.name
					if purchase.supplier
					else 'Sin proveedor',
					'supplier_id': purchase.supplier_id,
					'items': items,
				}
			except Exception as e:
				logger.error(
					f'Error al obtener detalle de compra {purchase_id}: {e}',
					exc_info=True,
				)
				return None

	def process_return(
		self,
		tenant_id,
		user_id,
		purchase_id,
		items_to_return,
		reason,
		refund_type,
		notes='',
	):
		"""
		Procesa una devolución a proveedor de forma atómica.

		items_to_return: lista de dicts con:
			- detail_id: str
			- qty_to_return: float
			- unit_cost: float
			- description: str
			- variant_id: str (opcional)

		refund_type: 'efectivo' | 'credito'
		"""
		if not items_to_return:
			return False, 'No seleccionaste ningún ítem para devolver.'
		if reason not in REASONS:
			return False, f'Motivo inválido. Opciones: {REASONS}.'
		if refund_type not in REFUND_TYPES:
			return False, f'Tipo de reembolso inválido. Opciones: {REFUND_TYPES}.'

		with self._Session() as session:
			try:
				purchase = (
					session.query(Purchase)
					.options(joinedload(Purchase.supplier), joinedload(Purchase.items))
					.filter_by(id=purchase_id, tenant_id=tenant_id)
					.with_for_update()
					.first()
				)
				if not purchase:
					return False, 'Compra no encontrada.'
				if purchase.status == 'anulada':
					return False, 'Esta compra ya fue anulada. No se puede devolver.'

				# Mapa de detalles de la compra
				detail_map = {d.id: d for d in purchase.items}

				already_returned = self._get_already_returned(session, purchase_id)

				# Validar y preparar ítems
				validated = []
				total_refund = Decimal('0')

				for item in items_to_return:
					did = str(item['detail_id'])
					qty = Decimal(str(item['qty_to_return']))
					unit_cost = Decimal(str(item['unit_cost']))
					description = str(item.get('description', ''))
					variant_id = item.get('variant_id')

					if did not in detail_map:
						return (
							False,
							f'El ítem "{description}" no pertenece a esta compra.',
						)

					original_qty = Decimal(str(detail_map[did].quantity))
					returned_so_far = already_returned.get(did, Decimal('0'))
					available = original_qty - returned_so_far

					if qty <= 0 or qty > available:
						return False, (
							f'Cantidad inválida para "{description}": '
							f'disponible para devolver: {available:.2f}.'
						)

					subtotal = qty * unit_cost
					total_refund += subtotal
					validated.append(
						{
							'detail_id': did,
							'qty': qty,
							'unit_cost': unit_cost,
							'subtotal': subtotal,
							'description': description,
							'variant_id': variant_id or detail_map[did].variant_id,
						}
					)

				if total_refund <= 0:
					return False, 'El total a recuperar debe ser mayor a cero.'

				# Crear registro de devolución
				purchase_return = PurchaseReturn(
					purchase_id=purchase_id,
					user_id=user_id,
					tenant_id=tenant_id,
					reason=reason,
					refund_type=refund_type,
					total_refund=total_refund,
					notes=notes,
					date=datetime.now(),
				)
				session.add(purchase_return)
				session.flush()

				# Ítems de la devolución + movimientos de stock
				# BUG 10: en multi-almacén puede haber varios Stock por variant_id.
				# Seleccionar el depósito con mayor cantidad (el más probable receptor original).
				_sids = [v['variant_id'] for v in validated if v['variant_id']]
				stocks_map: dict[str, Stock] = {}
				if _sids:
					for stock_row in (
						session.query(Stock)
						.filter(Stock.variant_id.in_(_sids))
						.with_for_update()
						.all()
					):
						vid = stock_row.variant_id
						if vid not in stocks_map or stock_row.quantity > stocks_map[vid].quantity:
							stocks_map[vid] = stock_row
				for v in validated:
					session.add(
						PurchaseReturnItem(
							purchase_return_id=purchase_return.id,
							purchase_detail_id=v['detail_id'],
							variant_id=v['variant_id'],
							description=v['description'],
							quantity_returned=v['qty'],
							unit_cost=v['unit_cost'],
							subtotal=v['subtotal'],
						)
					)

					# Reducir stock (sale del depósito hacia el proveedor)
					if v['variant_id']:
						stock = stocks_map.get(v['variant_id'])
						if stock:
							if stock.quantity < v['qty']:
								raise ValueError(
									f'Stock insuficiente para devolver "{v["description"]}": '
									f'en depósito {stock.quantity}, se intenta devolver {v["qty"]}.'
								)
							stock.quantity -= v['qty']
							session.add(
								StockMovement(
									movement_type='out',
									quantity=v['qty'],
									reference=f'Devolución a Proveedor #{purchase_return.id}',
									source_warehouse_id=stock.warehouse_id,
									variant_id=v['variant_id'],
									user_id=user_id,
								)
							)

				# Efecto financiero
				if refund_type == 'efectivo':
					active_cash = (
						session.query(CashSession)
						.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
						.first()
					)
					if not active_cash:
						return (
							False,
							'⚠️ Debes ABRIR LA CAJA para registrar reembolsos en efectivo.',
						)
					session.add(
						CashMovement(
							session_id=active_cash.id,
							movement_type='ingreso',
							amount=total_refund,
							description=(
								f'Reembolso proveedor {purchase.supplier.name if purchase.supplier else ""} '
								f'(Dev. #{purchase_return.id})'
							),
						)
					)
				else:
					# Crédito: suma al balance del proveedor (with_for_update evita race condition)
					supplier = (
						session.query(Supplier)
						.filter_by(id=purchase.supplier_id)
						.with_for_update()
						.first()
					)
					if supplier:
						supplier.credit_balance = (
							Decimal(str(supplier.credit_balance or 0)) + total_refund
						)

				# Actualizar estado de la compra
				updated_returned: dict[str, Decimal] = dict(already_returned)
				for v in validated:
					updated_returned[v['detail_id']] = (
						updated_returned.get(v['detail_id'], Decimal('0')) + v['qty']
					)

				all_fully_returned = all(
					updated_returned.get(d.id, Decimal('0')) >= Decimal(str(d.quantity))
					for d in purchase.items
				)
				purchase.status = (
					'devuelta_total' if all_fully_returned else 'devuelta_parcial'
				)
				purchase_status = purchase.status

				# Capturar datos de relaciones antes del commit (se expiran tras commit)
				_return_id = purchase_return.id
				_supplier_name = purchase.supplier.name if purchase.supplier else 'Proveedor'
				_pdf_items = [
					{
						'description': v['description'],
						'quantity_returned': float(v['qty']),
						'unit_cost': float(v['unit_cost']),
						'subtotal': float(v['subtotal']),
					}
					for v in validated
				]

				session.commit()

				# Generar PDF después del commit para evitar archivos huérfanos en disco
				try:
					from sqlalchemy import update as sa_update

					from controllers.receipt_controller import ReceiptController

					ok, filepath = ReceiptController().generate_supplier_return_note(
						return_id=_return_id,
						purchase_id=purchase_id,
						date_str=datetime.now().strftime('%d/%m/%Y %H:%M'),
						supplier_name=_supplier_name,
						items_returned=_pdf_items,
						total_refund=float(total_refund),
						reason=reason,
						refund_type=refund_type,
						notes=notes,
					)
					if ok:
						# UPDATE directo para evitar acceder al objeto ORM expirado post-commit
						session.execute(
							sa_update(PurchaseReturn)
							.where(PurchaseReturn.id == _return_id)
							.values(file_path=filepath)
						)
						session.commit()
				except Exception as pdf_err:
					logger.warning(
						f'Devolución registrada, pero falló el PDF: {pdf_err}'
					)

				refund_label = (
					'efectivo ingresado a caja'
					if refund_type == 'efectivo'
					else 'crédito acreditado al proveedor'
				)
				return (
					True,
					f'Devolución registrada. Total a recuperar: ${total_refund:.2f} ({refund_label}).\n'
					f'Estado de la compra: {purchase_status.upper()}.',
				)

			except ValueError as ve:
				session.rollback()
				return False, str(ve)
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al procesar devolución a proveedor: {e}', exc_info=True
				)
				return False, f'Error interno al procesar la devolución: {e}'

	def get_returns_for_purchase(self, tenant_id, purchase_id):
		"""Lista el historial de devoluciones de una compra."""
		with self._Session() as session:
			try:
				returns = (
					session.query(PurchaseReturn)
					.options(joinedload(PurchaseReturn.items))
					.filter_by(purchase_id=purchase_id, tenant_id=tenant_id)
					.order_by(PurchaseReturn.date.desc())
					.all()
				)
				return [
					{
						'id': r.id,
						'date': r.date,
						'reason': r.reason,
						'refund_type': r.refund_type,
						'total_refund': float(r.total_refund),
						'notes': r.notes or '',
						'file_path': r.file_path or '',
						'items': [
							{
								'description': i.description,
								'quantity_returned': float(i.quantity_returned),
								'unit_cost': float(i.unit_cost),
								'subtotal': float(i.subtotal),
							}
							for i in r.items
						],
					}
					for r in returns
				]
			except Exception as e:
				logger.error(
					f'Error al obtener devoluciones de compra: {e}', exc_info=True
				)
				return []
