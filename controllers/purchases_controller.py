import logging
from datetime import datetime

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

	def _parse_float(self, value):
		"""Convierte valores de la UI a float de forma segura, soportando comas."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return float(value)
		except (ValueError, TypeError):
			return 0.0

	def get_suppliers(self, tenant_id):
		"""Obtiene la lista de proveedores activos como diccionarios."""
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
		"""Obtiene el catálogo de variantes físicas para comprar."""
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
		"""Registra la compra optimizando las consultas a la base de datos."""
		if not cart_items:
			return False, 'El carrito de compras está vacío.'

		with self.Session() as session:
			try:
				# 1. Verificar si la caja está abierta
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

				# Parseo seguro de los subtotales
				total_purchase = sum(
					self._parse_float(item.get('subtotal', 0)) for item in cart_items
				)

				# 2. Registrar la cabecera de la compra
				new_purchase = Purchase(
					tenant_id=tenant_id,
					user_id=user_id,
					supplier_id=supplier_id,
					total_amount=total_purchase,
					date=datetime.utcnow(),
				)
				session.add(new_purchase)
				session.flush()

				# Buscamos el almacén por defecto
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

				variant_ids = [item['variant_id'] for item in cart_items]

				# Diccionario {id_variante: objeto_variante}
				variants_db = {
					v.id: v
					for v in session.query(ArticleVariant)
					.filter(ArticleVariant.id.in_(variant_ids))
					.all()
				}

				# Diccionario {id_variante: objeto_stock}
				stocks_db = {
					s.variant_id: s
					for s in session.query(Stock)
					.filter(Stock.variant_id.in_(variant_ids))
					.all()
				}
				# ---------------------------------------------------------------

				# 3. Procesar el detalle del carrito
				for item in cart_items:
					variant_id = item['variant_id']
					qty = self._parse_float(item.get('qty', 0))
					new_cost = self._parse_float(item.get('cost', 0))

					if qty <= 0:
						continue

					variant = variants_db.get(variant_id)
					if not variant:
						raise Exception(
							f'La variante ID {variant_id} ya no existe en la base de datos.'
						)

					variant.cost_price = new_cost

					stock_record = stocks_db.get(variant_id)

					if stock_record:
						stock_record.quantity += qty
						warehouse_id = stock_record.warehouse_id
					else:
						if not default_warehouse:
							raise Exception(
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
						reference=f'Compra Proveedor #{new_purchase.id}',
						dest_warehouse_id=warehouse_id,
						variant_id=variant_id,
						user_id=user_id,
					)
					session.add(movimiento_entrada)

				# 4. Descontar el dinero de la caja
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='gasto',
					amount=total_purchase,
					description=f'Pago a proveedor (Compra #{new_purchase.id})',
				)
				session.add(movement)

				session.commit()
				return (
					True,
					f'Compra registrada exitosamente. Total pagado: ${total_purchase:.2f}',
				)

			except Exception as e:
				session.rollback()
				logger.error(f'Error al procesar compra: {e}', exc_info=True)
				return False, 'Error interno al registrar la compra. Revise los logs.'
