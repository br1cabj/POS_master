import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import (
	Article,
	ArticleVariant,
	Branch,
	CashMovement,
	CashSession,
	Purchase,
	PurchaseDetail,
	Stock,
	StockMovement,
	Supplier,
	Warehouse,
)
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)


class PurchasesController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _parse_decimal(self, value):
		return parse_decimal(value, default=Decimal('0.0'))

	def get_suppliers(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{'id': s.id, 'name': s.name, 'phone': s.phone, 'email': s.email}
					for s in session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener proveedores: {e}', exc_info=True)
				return []

	def get_variants(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{
						'variant_id': v.id,
						'name': v.article.name,
						'barcode': v.barcode,
						'cost_price': v.cost_price,
						'selling_price': v.selling_price,
					}
					for v in (
						session.query(ArticleVariant)
						.options(joinedload(ArticleVariant.article))
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.all()
					)
				]
			except Exception as e:
				logger.error(
					f'Error al obtener variantes para compra: {e}', exc_info=True
				)
				return []

	def process_purchase(self, tenant_id, user_id, supplier_id, cart_items):
		"""
		Procesa una compra a proveedor de forma atómica: actualiza stock y costos,
		registra en el kardex y descuenta el total de la caja activa.
		El total se calcula en el backend; nunca se confía en valores de la UI.
		"""
		if not cart_items:
			return False, 'El carrito de compras está vacío.'

		with self._Session() as session:
			try:
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					return (
						False,
						'⚠️ Debes ABRIR LA CAJA para registrar pagos a proveedores.',
					)

				supplier = (
					session.query(Supplier)
					.filter_by(id=supplier_id, tenant_id=tenant_id)
					.first()
				)
				if not supplier:
					return False, 'Proveedor no encontrado o no autorizado.'

				branch = (
					session.query(Branch)
					.filter_by(tenant_id=tenant_id, name='Sede Principal')
					.first()
				)
				default_warehouse = (
					session.query(Warehouse)
					.filter_by(branch_id=branch.id, name='Depósito General')
					.first()
					if branch
					else None
				)

				variant_ids = [
					item['variant_id'] for item in cart_items if item.get('variant_id')
				]
				variants_db = {
					v.id: v
					for v in session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id.in_(variant_ids),
						Article.tenant_id == tenant_id,
					)
					.all()
				}
				stocks_db = {
					s.variant_id: s
					for s in session.query(Stock)
					.filter(Stock.variant_id.in_(variant_ids))
					.with_for_update()
					.all()
				}

				total = Decimal('0.0')
				kardex_entries = []
				detail_items = []

				for item in cart_items:
					variant_id = item.get('variant_id')
					qty = self._parse_decimal(item.get('qty', 0))
					new_cost = self._parse_decimal(item.get('cost', 0))

					if qty <= 0:
						raise ValueError('La cantidad no puede ser nula o negativa.')
					if new_cost <= 0:
						raise ValueError('El costo debe ser mayor a cero.')

					variant = variants_db.get(variant_id)
					if not variant:
						raise ValueError(
							f'La variante ID {variant_id} no existe o no te pertenece.'
						)

					subtotal = qty * new_cost
					total += subtotal
					desc = item.get(
						'desc',
						variant.article.name if variant.article else str(variant_id),
					)
					detail_items.append(
						{
							'variant_id': variant_id,
							'qty': qty,
							'cost': new_cost,
							'subtotal': subtotal,
							'desc': desc,
						}
					)

					# Stock primero: si falla (ej. no hay depósito), el costo NO se modifica
					stock = stocks_db.get(variant_id)
					if stock:
						stock.quantity += qty
						warehouse_id = stock.warehouse_id
					else:
						if not default_warehouse:
							raise ValueError(
								f"No se encontró el 'Depósito General' para ingresar '{desc}'. "
								"Cree el almacén predeterminado antes de registrar compras."
							)
						session.add(
							Stock(
								quantity=qty,
								warehouse_id=default_warehouse.id,
								variant_id=variant_id,
							)
						)
						warehouse_id = default_warehouse.id

					# Actualizar costo solo para variantes base; las presentaciones
					# derivan su costo de la base mediante cascada
					if not variant.base_variant_id:
						variant.cost_price = new_cost

						child_packs = (
							session.query(ArticleVariant)
							.filter(
								ArticleVariant.base_variant_id == variant_id,
								ArticleVariant.is_active == True,  # noqa: E712
							)
							.all()
						)
						for child in child_packs:
							child.cost_price = new_cost * (child.units_per_pack or 1)

					mov = StockMovement(
						movement_type='in',
						quantity=qty,
						reference='PENDING',
						dest_warehouse_id=warehouse_id,
						variant_id=variant_id,
						user_id=user_id,
					)
					session.add(mov)
					kardex_entries.append(mov)

				purchase = Purchase(
					tenant_id=tenant_id,
					user_id=user_id,
					supplier_id=supplier.id,
					total_amount=total,
					date=datetime.now(),
				)
				session.add(purchase)
				session.flush()

				for mov in kardex_entries:
					mov.reference = f'Compra Proveedor #{purchase.id}'

				for d in detail_items:
					session.add(
						PurchaseDetail(
							purchase_id=purchase.id,
							variant_id=d['variant_id'],
							description=d['desc'],
							quantity=d['qty'],
							unit_cost=d['cost'],
							subtotal=d['subtotal'],
						)
					)

				session.add(
					CashMovement(
						session_id=active_cash.id,
						movement_type='gasto',
						amount=total,
						description=f'Pago a proveedor {supplier.name} (Compra #{purchase.id})',
					)
				)

				session.commit()
				return (
					True,
					f'Compra registrada exitosamente. Total pagado: ${total:.2f}',
				)

			except ValueError as ve:
				session.rollback()
				return False, str(ve)
			except Exception as e:
				session.rollback()
				logger.error(f'Error al procesar compra: {e}', exc_info=True)
				return False, 'Error interno al registrar la compra. Intente de nuevo.'
