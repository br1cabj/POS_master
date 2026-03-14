import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	CashMovement,
	CashSession,
	ComboItem,
	Customer,
	Sale,
	SaleDetail,
	Stock,
	StockMovement,
)

logger = logging.getLogger(__name__)


class SalesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_float(self, value):
		"""Convierte valores de la UI a float de forma segura."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return Decimal(str(value))
		except (ValueError, TypeError, InvalidOperation):
			return Decimal('0.0')

	def get_articles_for_sale(self, tenant_id):
		"""Obtiene el catálogo calculando el stock real y el stock virtual de los combos"""
		with self.Session() as session:
			try:
				# 🛡️ MEJORA: Cargamos también los ingredientes por si es un Combo
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article),
						joinedload(ArticleVariant.stocks),
						joinedload(ArticleVariant.ingredients)
						.joinedload(ComboItem.ingredient)
						.joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
					.all()
				)

				result = []
				for v in variants:
					# CÁLCULO DE STOCK VIRTUAL PARA COMBOS
					if v.is_combo:
						virtual_stock = float('inf')
						if not v.ingredients:
							virtual_stock = 0
						else:
							for ci in v.ingredients:
								ing = ci.ingredient
								ing_stock = (
									sum(s.quantity for s in ing.stocks)
									if ing.stocks
									else 0
								)

								possible = (
									int(Decimal(ing_stock) / ci.quantity_required)
									if ci.quantity_required > 0
									else 0
								)
								if possible < virtual_stock:
									virtual_stock = possible
						total_stock = (
							0 if virtual_stock == float('inf') else virtual_stock
						)
					else:
						# Cálculo normal
						total_stock = (
							sum(s.quantity for s in v.stocks) if v.stocks else 0
						)

					result.append(
						{
							'variant_id': v.id,
							'name': v.article.name,
							'barcode': v.barcode,
							'selling_price': v.selling_price,
							'total_stock': total_stock,
							'is_combo': v.is_combo,
							'show_on_touch': v.show_on_touch,
							'btn_color': v.btn_color,
						}
					)
				return result
			except Exception as e:
				logger.error(
					f'Error al obtener artículos para venta: {e}', exc_info=True
				)
				return []

	def get_customers(self, tenant_id):
		with self.Session() as session:
			try:
				customers = (
					session.query(Customer)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.order_by(Customer.name)
					.all()
				)
				return [
					{'id': c.id, 'name': c.name, 'current_balance': c.current_balance}
					for c in customers
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def get_history(self, tenant_id, limit=500):
		with self.Session() as session:
			try:
				sales = (
					session.query(Sale)
					.options(joinedload(Sale.customer), joinedload(Sale.user))
					.filter_by(tenant_id=tenant_id)
					.order_by(Sale.date.desc())
					.limit(limit)
					.all()
				)
				return [
					{
						'id': s.id,
						'date': s.date,
						'total_amount': s.total_amount,
						'profit': s.profit,
						'payment_method': s.payment_method,
						'status': s.status,
						'customer_name': s.customer.name
						if s.customer
						else 'Consumidor Final',
						'user_name': s.user.username if s.user else 'Desconocido',
					}
					for s in sales
				]
			except Exception as e:
				logger.error(f'Error al leer historial: {e}', exc_info=True)
				return []

	def get_sale_details(self, tenant_id, sale_id):
		with self.Session() as session:
			try:
				details = (
					session.query(SaleDetail)
					.join(Sale)
					.filter(SaleDetail.sale_id == sale_id, Sale.tenant_id == tenant_id)
					.all()
				)
				return [
					{
						'description': d.description,
						'quantity': d.quantity,
						'unit_price': d.unit_price,
						'subtotal': d.subtotal,
					}
					for d in details
				]
			except Exception as e:
				logger.error(
					f'Error al leer detalle de venta {sale_id}: {e}', exc_info=True
				)
				return []

	def process_sale(
		self,
		tenant_id,
		user_id,
		cart_items,
		customer_id=None,
		is_fiado=False,
		payment_method='efectivo',
	):
		if not cart_items:
			return False, 'El carrito está vacío.'

		with self.Session() as session:
			try:
				# 1. Verificación de Caja
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					return False, '⚠️ ¡Debes ABRIR LA CAJA en el menú antes de vender!'

				# 2. Gestión de Cliente
				customer_str = 'Consumidor Final'
				customer_obj = None

				if customer_id:
					customer_obj = (
						session.query(Customer)
						.filter_by(id=customer_id, tenant_id=tenant_id)
						.first()
					)
					if not customer_obj:
						return False, 'Cliente inválido o no autorizado.'
					customer_str = customer_obj.name
				else:
					customer_obj = (
						session.query(Customer)
						.filter_by(name='Consumidor Final', tenant_id=tenant_id)
						.first()
					)
					customer_id = customer_obj.id if customer_obj else None

				if is_fiado and not customer_id:
					return False, 'Debes seleccionar un cliente válido para fiar.'

				# 3. Preparación de la Venta Maestra
				metodo_final = 'fiado' if is_fiado else payment_method.lower()
				estado_final = 'pendiente' if is_fiado else 'completada'

				new_sale = Sale(
					tenant_id=tenant_id,
					user_id=user_id,
					customer_id=customer_id,
					payment_method=metodo_final,
					status=estado_final,
					date=datetime.now(),
					total_amount=0.0,
					profit=0.0,
				)
				session.add(new_sale)
				session.flush()

				variant_ids_in_cart = [
					item['variant_id']
					for item in cart_items
					if item.get('variant_id') is not None
				]
				variants_db = {}
				variants_to_deduct_ids = set()

				if variant_ids_in_cart:
					variants_list = (
						session.query(ArticleVariant)
						.join(Article)
						.options(
							joinedload(ArticleVariant.article),
							joinedload(ArticleVariant.ingredients).joinedload(
								ComboItem.ingredient
							),
						)
						.filter(
							ArticleVariant.id.in_(variant_ids_in_cart),
							Article.tenant_id == tenant_id,
						)
						.all()
					)

					variants_db = {v.id: v for v in variants_list}

					# Identificamos a quiénes hay que descontarle stock
					for item in cart_items:
						v_id = item.get('variant_id')
						if v_id and v_id in variants_db:
							variant = variants_db[v_id]
							if variant.is_combo:
								for c_item in variant.ingredients:
									variants_to_deduct_ids.add(c_item.ingredient_id)
							else:
								variants_to_deduct_ids.add(v_id)

				# Bloqueo estricto de concurrencia
				stocks_db = {}
				if variants_to_deduct_ids:
					stocks_list = (
						session.query(Stock)
						.filter(Stock.variant_id.in_(variants_to_deduct_ids))
						.with_for_update()
						.all()
					)
					stocks_db = {s.variant_id: s for s in stocks_list}

				total_sale = Decimal('0.0')
				total_cost = Decimal('0.0')

				# 4. Procesamiento del Carrito y Deducción (El Desarmador de Combos)
				for item in cart_items:
					qty = self._parse_float(item.get('qty', 1))

					if qty <= 0:
						raise ValueError(
							f'Cantidad inválida para el producto: {item.get("desc", "Desconocido")}'
						)

					v_id = item.get('variant_id')
					cost_price = Decimal('0.0')
					price = self._parse_float(item.get('price', 0))

					if v_id is not None:
						variant = variants_db.get(v_id)
						if not variant:
							raise ValueError(
								f'Producto no encontrado o no autorizado: {item.get("desc")}'
							)

						price = variant.selling_price

						# 🍔 SI ES COMBO: Desarmar y cobrar ingredientes
						if variant.is_combo:
							for c_item in variant.ingredients:
								ing_id = c_item.ingredient_id
								req_qty = c_item.quantity_required * qty

								stock_record = stocks_db.get(ing_id)
								if not stock_record or stock_record.quantity < req_qty:
									raise ValueError(
										f'Falta ingrediente para preparar Promo: {variant.article.name}'
									)

								stock_record.quantity -= req_qty
								cost_price += (
									c_item.ingredient.cost_price
									* c_item.quantity_required
								)

								movimiento_salida = StockMovement(
									movement_type='out',
									quantity=req_qty,
									reference=f'Venta Promo #{new_sale.id}',
									source_warehouse_id=stock_record.warehouse_id,
									variant_id=ing_id,
									user_id=user_id,
								)
								session.add(movimiento_salida)

						# 📦 SI ES NORMAL: Descontar stock directamente
						else:
							stock_record = stocks_db.get(v_id)
							if not stock_record or stock_record.quantity < qty:
								raise ValueError(
									f'Stock insuficiente para {variant.article.name}'
								)

							stock_record.quantity -= qty
							cost_price = variant.cost_price

							movimiento_salida = StockMovement(
								movement_type='out',
								quantity=qty,
								reference=f'Venta Ticket #{new_sale.id}',
								source_warehouse_id=stock_record.warehouse_id,
								variant_id=v_id,
								user_id=user_id,
							)
							session.add(movimiento_salida)
					else:
						if price < 0:
							raise ValueError(
								f'El precio no puede ser negativo: {item.get("desc", "Desconocido")}'
							)

					subtotal = price * qty
					cost_subtotal = cost_price * qty

					total_sale += subtotal
					total_cost += cost_subtotal

					detail = SaleDetail(
						variant_id=v_id,
						description=item.get('desc', 'Artículo'),
						quantity=qty,
						unit_cost=cost_price,
						unit_price=price,
						subtotal=subtotal,
					)
					new_sale.items.append(detail)

				# 5. Totales
				new_sale.total_amount = total_sale
				new_sale.profit = total_sale - total_cost

				# 6. Movimiento Financiero
				if is_fiado and customer_obj:
					customer_obj.current_balance += total_sale
				else:
					movement = CashMovement(
						session_id=active_cash.id,
						movement_type='venta',
						amount=total_sale,
						description=f'Ticket #{new_sale.id} - Pago: {payment_method.capitalize()}',
					)
					session.add(movement)

				session.commit()

				# 7. Generación del Ticket
				try:
					from controllers.receipt_controller import ReceiptController

					pdf_maker = ReceiptController()
					date_str = new_sale.date.strftime('%Y-%m-%d %H:%M')
					pdf_maker.generate_pdf(
						tenant_id=tenant_id,
						sale_id=new_sale.id,
						date_str=date_str,
						items_list=cart_items,
						total=total_sale,
						customer_name=customer_str,
					)
				except Exception as pdf_err:
					logger.warning(
						f'La venta se guardó, pero falló el ticket: {pdf_err}'
					)

				return (
					True,
					f'Venta registrada ({metodo_final.capitalize()}). Total: ${total_sale:.2f}',
				)

			except ValueError as ve:
				session.rollback()
				return False, str(ve)
			except Exception as e:
				session.rollback()
				logger.error(f'Error grave al procesar venta: {e}', exc_info=True)
				return (
					False,
					'Ocurrió un error interno al procesar la venta. Intente de nuevo.',
				)
