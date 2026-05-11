import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
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
	User,
)
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)


class SalesController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _parse_decimal(self, value):
		return parse_decimal(value, default=Decimal('0.0'))

	def get_articles_for_sale(self, tenant_id):
		"""
		Retorna el catálogo activo con stock calculado.
		Para combos, el stock virtual es el mínimo de unidades armables según ingredientes.
		"""
		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article).joinedload(Article.supplier),
						joinedload(ArticleVariant.stocks),
						joinedload(ArticleVariant.ingredients)
						.joinedload(ComboItem.ingredient)
						.joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)  # noqa: E712
					.all()
				)

				variants_by_id = {v.id: v for v in variants}
				result = []
				for v in variants:
					if v.is_combo:
						if not v.ingredients:
							total_stock = 0
						else:
							virtual = float('inf')
							for ci in v.ingredients:
								ing = ci.ingredient
								ing_stock = (
									sum(s.quantity for s in ing.stocks)
									if ing and ing.stocks
									else 0
								)
								if ci.quantity_required > 0:
									possible = int(
										Decimal(str(ing_stock)) / ci.quantity_required
									)
								else:
									possible = 0
								if possible < virtual:
									virtual = possible
							total_stock = 0 if virtual == float('inf') else virtual
					else:
						total_stock = (
							sum(s.quantity for s in v.stocks) if v.stocks else 0
						)

					# Stock visible: para presentaciones mostrar en unidades del paquete
					units = getattr(v, 'units_per_pack', 1) or 1
					base_vid = getattr(v, 'base_variant_id', None)
					if base_vid and units > 1:
						# Stock de la variante base dividido por factor de empaque
						base_v = variants_by_id.get(base_vid)
						if base_v:
							base_stock = (
								sum(s.quantity for s in base_v.stocks)
								if base_v.stocks
								else 0
							)
							total_stock = int(base_stock // units)
						else:
							total_stock = 0

					result.append(
						{
							'variant_id': v.id,
							'name': v.article.name,
							'barcode': v.barcode,
							'selling_price': v.selling_price,
							'selling_price_b': float(v.selling_price_b)
							if v.selling_price_b
							else None,
							'total_stock': total_stock,
							'is_combo': v.is_combo,
							'show_on_touch': v.show_on_touch,
							'btn_color': v.btn_color,
							# Empaque
							'units_per_pack': units,
							'pack_label': getattr(v, 'pack_label', None),
							'base_variant_id': base_vid,
							# Descuento por producto
							'discount_pct': float(v.discount_pct)
							if v.discount_pct
							else 0.0,
							'discount_until': v.discount_until,
							# Descuento del distribuidor/proveedor
							'supplier_discount_pct': float(
								v.article.supplier.discount_pct
							)
							if v.article.supplier and v.article.supplier.discount_pct
							else 0.0,
							'supplier_discount_until': v.article.supplier.discount_until
							if v.article.supplier
							else None,
						}
					)
				return result
			except Exception as e:
				logger.error(
					f'Error al obtener artículos para venta: {e}', exc_info=True
				)
				return []

	def get_customers(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{
						'id': c.id,
						'name': c.name,
						'current_balance': c.current_balance,
						'price_list': c.price_list or 'A',
					}
					for c in session.query(Customer)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.order_by(Customer.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener clientes: {e}', exc_info=True)
				return []

	def get_history(self, tenant_id, limit=200, before_date=None):
		"""
		Retorna (rows, has_more).
		before_date: cursor para paginación — trae solo ventas anteriores a esa fecha.
		Carga limit+1 filas para detectar si hay más sin un COUNT extra.
		"""
		with self._Session() as session:
			try:
				query = (
					session.query(Sale)
					.options(joinedload(Sale.customer), joinedload(Sale.user))
					.filter_by(tenant_id=tenant_id)
					.order_by(Sale.date.desc())
				)
				if before_date is not None:
					query = query.filter(Sale.date < before_date)
				rows = query.limit(limit + 1).all()
				has_more = len(rows) > limit
				return [
					{
						'id': s.id,
						'date': s.date,
						'total_amount': float(s.total_amount or 0),
						'discount_amount': float(s.discount_amount or 0),
						'profit': float(s.profit or 0),
						'payment_method': s.payment_method,
						'payment_method_2': s.payment_method_2 or '',
						'amount_method_2': float(s.amount_method_2 or 0),
						'status': s.status,
						'quotation_number': s.quotation_number or '',
						'customer_name': s.customer.name
						if s.customer
						else 'Consumidor Final',
						'user_name': get_display_name(s.user) if s.user else '—',
					}
					for s in rows[:limit]
				], has_more
			except Exception as e:
				logger.error(f'Error al leer historial: {e}', exc_info=True)
				return [], False

	def get_sale_details(self, tenant_id, sale_id):
		with self._Session() as session:
			try:
				sale = (
					session.query(Sale)
					.filter_by(id=sale_id, tenant_id=tenant_id)
					.first()
				)
				discount = float(sale.discount_amount or 0) if sale else 0.0
				details = [
					{
						'description': d.description,
						'quantity': d.quantity,
						'unit_price': d.unit_price,
						'subtotal': d.subtotal,
					}
					for d in session.query(SaleDetail)
					.join(Sale)
					.filter(SaleDetail.sale_id == sale_id, Sale.tenant_id == tenant_id)
					.all()
				]
				return {
					'items': details,
					'discount_amount': discount,
					'payment_method': sale.payment_method or '',
					'payment_method_2': sale.payment_method_2 or '',
					'amount_method_2': float(sale.amount_method_2 or 0),
					'total_amount': float(sale.total_amount or 0),
				}
			except Exception as e:
				logger.error(
					f'Error al leer detalle de venta {sale_id}: {e}', exc_info=True
				)
				return {
					'items': [],
					'discount_amount': 0.0,
					'payment_method': '',
					'payment_method_2': '',
					'amount_method_2': 0.0,
					'total_amount': 0.0,
				}

	def process_sale(
		self,
		tenant_id,
		user_id,
		cart_items,
		customer_id=None,
		is_fiado=False,
		payment_method='efectivo',
		discount_amount=None,
		payment_method_2=None,
		amount_method_2=None,
		paid_amount=None,
	):
		"""
		Procesa una venta de forma atómica. Verifica caja, resuelve cliente, descuenta stock
		(descomponiendo combos en ingredientes), calcula totales en el backend y registra
		el movimiento financiero. La generación del ticket PDF es no-fatal post-commit.
		"""
		if not cart_items:
			return False, 'El carrito está vacío.'

		discount_amount = (
			self._parse_decimal(discount_amount)
			if discount_amount is not None
			else Decimal('0.0')
		)
		if discount_amount < Decimal('0.0'):
			discount_amount = Decimal('0.0')

		# Normalizar pago mixto
		amount_m2 = Decimal('0')
		payment_method_2_lower = None
		if payment_method_2 and not is_fiado:
			payment_method_2_lower = payment_method_2.lower()
			try:
				amount_m2 = self._parse_decimal(amount_method_2)
				if amount_m2 < Decimal('0'):
					amount_m2 = Decimal('0')
			except Exception:
				amount_m2 = Decimal('0')

		with self._Session() as session:
			try:
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active_cash:
					return False, '⚠️ ¡Debes ABRIR LA CAJA en el menú antes de vender!'

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
					# Verificar fiado ANTES de asignar Consumidor Final,
					# para evitar que un fiado quede registrado en nombre del cliente anónimo.
					if is_fiado:
						return False, 'Debes seleccionar un cliente válido para fiar.'
					customer_obj = (
						session.query(Customer)
						.filter_by(name='Consumidor Final', tenant_id=tenant_id)
						.first()
					)
					customer_id = customer_obj.id if customer_obj else None

				metodo_final = 'fiado' if is_fiado else payment_method.lower()
				new_sale = Sale(
					tenant_id=tenant_id,
					user_id=user_id,
					customer_id=customer_id,
					payment_method=metodo_final,
					status='pendiente' if is_fiado else 'completada',
					date=datetime.now(),
					total_amount=Decimal('0.0'),
					profit=Decimal('0.0'),
				)
				session.add(new_sale)
				session.flush()

				variant_ids_in_cart = [
					item['variant_id']
					for item in cart_items
					if item.get('variant_id') is not None
				]
				variants_db = {}
				variants_to_deduct = set()

				if variant_ids_in_cart:
					variants_db = {
						v.id: v
						for v in session.query(ArticleVariant)
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
					}
					for item in cart_items:
						v_id = item.get('variant_id')
						if v_id and v_id in variants_db:
							v = variants_db[v_id]
							if v.is_combo:
								for ci in v.ingredients:
									variants_to_deduct.add(ci.ingredient_id)
							elif getattr(v, 'base_variant_id', None):
								# Presentacion: stock se descuenta de la variante base
								variants_to_deduct.add(v.base_variant_id)
							else:
								variants_to_deduct.add(v_id)

				stocks_db = {}
				if variants_to_deduct:
					stocks_db = {
						s.variant_id: s
						for s in session.query(Stock)
						.filter(Stock.variant_id.in_(variants_to_deduct))
						.with_for_update()
						.all()
					}

				total_sale = Decimal('0.0')
				total_cost = Decimal('0.0')

				for item in cart_items:
					qty = self._parse_decimal(item.get('qty', 1))
					if qty <= 0:
						raise ValueError(
							f'Cantidad inválida para: {item.get("desc", "Desconocido")}'
						)

					v_id = item.get('variant_id')
					cost_price = Decimal('0.0')

					# Inicializamos el precio desde el item de forma segura
					price = self._parse_decimal(item.get('price', 0))

					if v_id is not None:
						variant = variants_db.get(v_id)
						if not variant:
							raise ValueError(
								f'Producto no encontrado o no autorizado: {item.get("desc")}'
							)

						price = self._parse_decimal(
							item.get('price', variant.selling_price)
						)
						if price < Decimal('0'):
							raise ValueError(
								f'El precio no puede ser negativo: {variant.article.name}'
							)

						if variant.is_combo:
							for ci in variant.ingredients:
								req_qty = ci.quantity_required * qty
								stock = stocks_db.get(ci.ingredient_id)
								if not stock or stock.quantity < req_qty:
									raise ValueError(
										f'Falta ingrediente para preparar: {variant.article.name}'
									)
								stock.quantity -= req_qty
								# ci.ingredient puede ser None si el producto fue eliminado del catálogo
								if ci.ingredient is None:
									logger.warning(
										'Ingrediente %s del combo %s no encontrado; costo omitido.',
										ci.ingredient_id,
										variant.id,
									)
								cost_price += (
									(
										ci.ingredient.cost_price
										if ci.ingredient
										else Decimal('0')
									)
									or Decimal('0')
								) * ci.quantity_required
								session.add(
									StockMovement(
										movement_type='out',
										quantity=req_qty,
										reference=f'Venta Promo #{new_sale.id}',
										source_warehouse_id=stock.warehouse_id,
										variant_id=ci.ingredient_id,
										user_id=user_id,
									)
								)
						else:
							# Determinar de donde descontar stock
							base_vid = getattr(variant, 'base_variant_id', None)
							units = getattr(variant, 'units_per_pack', 1) or 1
							if base_vid and units > 1:
								# Presentacion: descontar qty*units de la variante base
								deduct_vid = base_vid
								deduct_qty = qty * Decimal(str(units))
							else:
								deduct_vid = v_id
								deduct_qty = qty

							stock = stocks_db.get(deduct_vid)
							if not stock or stock.quantity < deduct_qty:
								raise ValueError(
									f'Stock insuficiente para {variant.article.name}'
								)
							stock.quantity -= deduct_qty
							cost_price = variant.cost_price
							session.add(
								StockMovement(
									movement_type='out',
									quantity=deduct_qty,
									reference=f'Venta Ticket #{new_sale.id}',
									source_warehouse_id=stock.warehouse_id,
									variant_id=deduct_vid,
									user_id=user_id,
								)
							)
					else:
						if price < 0:
							raise ValueError(
								f'El precio no puede ser negativo: {item.get("desc", "Desconocido")}'
							)

					subtotal = price * qty
					total_sale += subtotal
					total_cost += cost_price * qty
					new_sale.items.append(
						SaleDetail(
							variant_id=v_id,
							description=item.get('desc', 'Artículo'),
							quantity=qty,
							unit_cost=cost_price,
							unit_price=price,
							subtotal=subtotal,
						)
					)

				# Aplicar descuento al total final
				final_total = total_sale - discount_amount
				if final_total < Decimal('0.0'):
					final_total = Decimal('0.0')

				new_sale.total_amount = final_total
				new_sale.discount_amount = discount_amount
				new_sale.profit = final_total - total_cost

				if is_fiado and customer_obj:
					customer_obj.current_balance += final_total
				else:
					disc_str = (
						f' (Desc: ${discount_amount:.2f})'
						if discount_amount > 0
						else ''
					)
					if payment_method_2_lower and amount_m2 > 0:
						# Pago mixto: dos movimientos de caja
						amount_m1 = final_total - amount_m2

						if amount_m1 <= Decimal('0.0') or amount_m2 <= Decimal('0.0'):
							raise ValueError(
								'Error de consistencia: Ambos montos del pago mixto deben ser mayores a cero.'
							)

						new_sale.payment_method_2 = payment_method_2_lower
						new_sale.amount_method_2 = amount_m2
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type='venta',
								amount=amount_m1,  # Fallback de 0.01 removido
								description=f'Ticket #{new_sale.id} - {payment_method.capitalize()} (Mixto){disc_str}',
							)
						)
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type='venta',
								amount=amount_m2,
								description=f'Ticket #{new_sale.id} - {payment_method_2_lower.capitalize()} (Mixto)',
							)
						)
					else:
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type='venta',
								amount=final_total,  # Fallback de 0.01 removido
								description=f'Ticket #{new_sale.id} - Pago: {payment_method.capitalize()}{disc_str}',
							)
						)

				# Capturar antes del commit para evitar lazy loads post-commit
				_sale_id = new_sale.id
				_sale_date = new_sale.date
				try:
					_user_obj = session.query(User).filter_by(id=user_id).first()
					cashier_label = get_display_name(_user_obj)
				except Exception:
					cashier_label = 'Operador'

				session.commit()

				try:
					from controllers.receipt_controller import ReceiptController

					# Calcular vuelto si el pago fue en efectivo simple
					change_amt = None
					paid_dec = None
					pm_lower = payment_method.lower() if payment_method else ''
					if (
						paid_amount is not None
						and not is_fiado
						and not payment_method_2
					):
						try:
							paid_dec = Decimal(str(paid_amount))
							change_amt = max(paid_dec - final_total, Decimal('0'))
						except (ValueError, TypeError, Exception) as _e:
							logger.debug('No se pudo calcular el vuelto: %s', _e)
							change_amt = Decimal('0')

					ReceiptController().generate_pdf(
						tenant_id=tenant_id,
						sale_id=_sale_id,
						date_str=_sale_date.strftime('%d/%m/%Y  %H:%M'),
						items_list=cart_items,
						total=final_total,
						customer_name=customer_str,
						discount_amount=float(discount_amount),
						payment_method=None if is_fiado else pm_lower,
						payment_method_2=payment_method_2_lower
						if payment_method_2_lower
						else None,
						amount_method_2=float(amount_m2) if amount_m2 > 0 else None,
						paid_amount=float(paid_dec) if paid_dec is not None else None,
						change_amount=float(change_amt)
						if change_amt is not None
						else None,
						cashier_name=cashier_label,
					)
				except Exception as pdf_err:
					logger.warning(
						f'Venta guardada, pero falló la generación del ticket: {pdf_err}'
					)

				disc_msg = (
					f' · Descuento: ${discount_amount:.2f}'
					if discount_amount > 0
					else ''
				)
				if payment_method_2_lower and amount_m2 > 0:
					amt_m1 = final_total - amount_m2
					return (
						True,
						(
							f'Venta registrada (Mixto: {payment_method.capitalize()} ${amt_m1:.2f} + '
							f'{payment_method_2_lower.capitalize()} ${amount_m2:.2f}).'
							f' Total: ${final_total:.2f}{disc_msg}'
						),
					)
				return (
					True,
					f'Venta registrada ({metodo_final.capitalize()}). Total: ${final_total:.2f}{disc_msg}',
				)

			except ValueError as ve:
				session.rollback()
				return False, str(ve)
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error inesperado al procesar la venta: {e}', exc_info=True
				)
				return (
					False,
					'Ocurrió un error interno al procesar la venta. Revisa los logs.',
				)
