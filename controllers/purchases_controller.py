import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	CashMovement,
	CashSession,
	Purchase,
	Stock,
	StockMovement,
	Supplier,
	Warehouse,
)

logger = logging.getLogger(__name__)


class PurchasesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_decimal(self, value):
		"""Usamos Decimal para manejar dinero y stock sin perder precisión."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return Decimal(str(value))
		except (ValueError, TypeError, InvalidOperation):
			return Decimal('0.0')

	def get_suppliers(self, tenant_id):
		with self.Session() as session:
			try:
				suppliers = (
					session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				)
				return [
					{'id': s.id, 'name': s.name, 'phone': s.phone, 'email': s.email}
					for s in suppliers
				]
			except Exception as e:
				logger.error(f'Error al obtener proveedores: {e}', exc_info=True)
				return []

	def get_variants(self, tenant_id):
		with self.Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
					.all()
				)
				return [
					{
						'variant_id': v.id,
						'name': v.article.name,
						'barcode': v.barcode,
						'cost_price': v.cost_price,
						'selling_price': v.selling_price,
					}
					for v in variants
				]
			except Exception as e:
				logger.error(
					f'Error al obtener variantes para compra: {e}', exc_info=True
				)
				return []

	def process_purchase(self, tenant_id, user_id, supplier_id, cart_items):
		if not cart_items:
			return False, 'El carrito de compras está vacío.'

		with self.Session() as session:
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

				# Buscamos el almacén por defecto del tenant
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

				variants_list = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id.in_(variant_ids),
						Article.tenant_id == tenant_id,
					)
					.all()
				)
				variants_db = {v.id: v for v in variants_list}

				stocks_list = (
					session.query(Stock)
					.filter(Stock.variant_id.in_(variant_ids))
					.with_for_update()
					.all()
				)
				stocks_db = {s.variant_id: s for s in stocks_list}

				# 4. Procesar el detalle del carrito y CALCULAR el total nosotros mismos
				total_purchase = Decimal('0.0')

				for item in cart_items:
					variant_id = item.get('variant_id')
					qty = self._parse_decimal(item.get('qty', 0))
					new_cost = self._parse_decimal(item.get('cost', 0))

					if qty <= 0:
						raise ValueError('La cantidad no puede ser nula o negativa.')
					if new_cost < 0:
						raise ValueError(
							'El costo de un producto no puede ser negativo.'
						)

					variant = variants_db.get(variant_id)
					if not variant:
						raise ValueError(
							f'La variante ID {variant_id} no existe o no te pertenece.'
						)

					# Calculamos el subtotal REAL en el backend
					subtotal_real = qty * new_cost
					total_purchase += subtotal_real

					# Actualizamos el costo
					variant.cost_price = new_cost

					# Gestionamos el stock
					stock_record = stocks_db.get(variant_id)
					if stock_record:
						stock_record.quantity += qty
						warehouse_id = stock_record.warehouse_id
					else:
						if not default_warehouse:
							raise ValueError(
								"No se encontró el 'Depósito General' para ingresar la mercadería."
							)

						stock_record = Stock(
							quantity=qty,
							warehouse_id=default_warehouse.id,
							variant_id=variant_id,
						)
						session.add(stock_record)
						warehouse_id = default_warehouse.id

					# Registro en Kardex
					movimiento_entrada = StockMovement(
						movement_type='in',
						quantity=qty,
						reference='Compra Proveedor (Pendiente ID)',  # Actualizaremos esto abajo
						dest_warehouse_id=warehouse_id,
						variant_id=variant_id,
						user_id=user_id,
					)
					session.add(movimiento_entrada)

					# Truco de SQLAlchemy: asociaremos el objeto directamente en vez de IDs si fuera necesario,
					# pero lo dejaremos así por ahora.

				# 5. Crear la cabecera de la compra ahora que tenemos el TOTAL REAL
				new_purchase = Purchase(
					tenant_id=tenant_id,
					user_id=user_id,
					supplier_id=supplier.id,
					total_amount=total_purchase,
					date=datetime.utcnow(),
				)
				session.add(new_purchase)
				session.flush()  # Genera el ID de compra

				# Actualizamos las referencias del Kardex con el ID real
				for obj in session.new:
					if isinstance(obj, StockMovement) and 'Pendiente' in obj.reference:
						obj.reference = f'Compra Proveedor #{new_purchase.id}'

				# 6. Descontar el dinero de la caja
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='gasto',
					amount=total_purchase,
					description=f'Pago a proveedor {supplier.name} (Compra #{new_purchase.id})',
				)
				session.add(movement)

				session.commit()
				return (
					True,
					f'Compra registrada exitosamente. Total pagado: ${total_purchase:.2f}',
				)

			except ValueError as ve:
				session.rollback()
				return False, str(ve)
			except Exception as e:
				session.rollback()
				logger.error(f'Error al procesar compra: {e}', exc_info=True)
				return False, 'Error interno al registrar la compra. Intente de nuevo.'
