import logging
from collections import defaultdict
from datetime import date, datetime
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
	Promotion,
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

	@staticmethod
	def _promotion_is_active_now(promo, now: datetime) -> bool:
		"""Valida vigencia completa de una promoción dentro de la transacción."""
		if not promo.is_active or now < promo.date_from or now > promo.date_to:
			return False
		if promo.days_of_week:
			try:
				if now.weekday() not in {
					int(day) for day in promo.days_of_week.split(',') if day.strip()
				}:
					return False
			except ValueError:
				return False
		if promo.time_from and promo.time_to:
			try:
				start = datetime.strptime(promo.time_from, '%H:%M').time()
				end = datetime.strptime(promo.time_to, '%H:%M').time()
				if not start <= now.time().replace(second=0, microsecond=0) <= end:
					return False
			except ValueError:
				return False
		return True

	def _resolve_promotion(self, session, tenant_id, variant, now: datetime):
		"""Prioriza una promo directa; para empates, la última actualización gana."""
		category_id = getattr(variant.article, 'category_id', None)
		candidates = (
			session.query(Promotion)
			.filter(
				Promotion.tenant_id == tenant_id,
				Promotion.is_active.is_(True),
				Promotion.date_from <= now,
				Promotion.date_to >= now,
				(
					(Promotion.variant_id == variant.id)
					| ((Promotion.variant_id.is_(None)) & (Promotion.category_id == category_id))
				),
			)
			.all()
		)
		active = [p for p in candidates if self._promotion_is_active_now(p, now)]
		return max(
			active,
			key=lambda p: (
				p.variant_id == variant.id,
				p.updated_at or p.date_from,
				p.id,
			),
			default=None,
		)

	@staticmethod
	def _discount_is_active(pct, until, now: datetime) -> bool:
		return bool(pct and Decimal(str(pct)) > 0 and (until is None or until >= now))

	def _resolve_variant_price(self, session, tenant_id, variant, total_qty, price_list, now):
		"""Calcula precio y descripción canónicos; nunca confía en el carrito recibido."""
		base_price = Decimal(str(variant.selling_price or 0))
		if price_list == 'B' and variant.selling_price_b is not None:
			base_price = Decimal(str(variant.selling_price_b))

		promo = self._resolve_promotion(session, tenant_id, variant, now)
		if promo:
			if promo.promo_type == 'pct':
				pct = Decimal(str(promo.discount_value or 0))
				price = (base_price * (Decimal(1) - pct / Decimal(100))).quantize(
					Decimal('0.01')
				)
			elif promo.promo_type == 'nxm':
				buy, pay = Decimal(str(promo.buy_qty)), Decimal(str(promo.pay_qty))
				sets, remainder = int(total_qty // buy), total_qty % buy
				price = ((sets * pay * base_price + remainder * base_price) / total_qty).quantize(
					Decimal('0.01')
				)
			elif promo.promo_type == 'fixed':
				price = Decimal(str(promo.discount_value or 0)).quantize(Decimal('0.01'))
			else:
				price = base_price
			return price, f'🎯 {promo.name}'

		product_pct = getattr(variant, 'discount_pct', None)
		supplier = getattr(variant.article, 'supplier', None)
		supplier_pct = getattr(supplier, 'discount_pct', None) if supplier else None
		if self._discount_is_active(
			product_pct, getattr(variant, 'discount_until', None), now
		):
			pct = Decimal(str(product_pct))
			return (base_price * (Decimal(1) - pct / Decimal(100))).quantize(
				Decimal('0.01')
			), f'🏷️ -{pct:.4g}% {variant.article.name}'
		if self._discount_is_active(
			supplier_pct, getattr(supplier, 'discount_until', None), now
		):
			pct = Decimal(str(supplier_pct))
			return (base_price * (Decimal(1) - pct / Decimal(100))).quantize(
				Decimal('0.01')
			), f'🏷️ -{pct:.4g}% {variant.article.name}'
		prefix = '💼 ' if price_list == 'B' and variant.selling_price_b is not None else ''
		return base_price, f'{prefix}{variant.article.name}'

	@staticmethod
	def _take_from_stock_rows(stock_rows, requested_qty):
		"""Deduct stock using FEFO, returning ``(row, deducted_qty)`` pairs.

		A variant may legitimately have one row per warehouse and batch.  Selecting
		a single row by ``variant_id`` silently loses the rest of its inventory.
		"""
		requested_qty = Decimal(str(requested_qty))
		available = sum((Decimal(str(s.quantity)) for s in stock_rows), Decimal('0'))
		if available < requested_qty:
			raise ValueError(
				f'Stock insuficiente: disponible {available:.4f}, requerido {requested_qty:.4f}.'
			)

		remaining = requested_qty
		allocations = []
		for stock in sorted(
			stock_rows,
			key=lambda s: (
				s.expiration_date is None,
				s.expiration_date or date.max,
				s.warehouse_id,
				s.id,
			),
		):
			if remaining <= 0:
				break
			on_row = min(Decimal(str(stock.quantity)), remaining)
			if on_row <= 0:
				continue
			stock.quantity -= on_row
			remaining -= on_row
			allocations.append((stock, on_row))
		return allocations

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
					.filter(
						Article.tenant_id == tenant_id,
						Article.is_active.is_(True),
						Article.deleted_at.is_(None),
						ArticleVariant.is_active.is_(True),
						ArticleVariant.deleted_at.is_(None),
					)
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
								if ci.quantity_required <= 0:
									continue  # ingrediente con cantidad inválida; se ignora
								ing = ci.ingredient
								ing_stock = (
									sum(s.quantity for s in ing.stocks)
									if ing and ing.stocks
									else 0
								)
								possible = int(
									Decimal(str(ing_stock)) / ci.quantity_required
								)
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
							'category_id': v.article.category_id,
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

	def search_articles(self, tenant_id, query: str, limit: int = 50):
		"""
		Búsqueda paginada por nombre o código de barras — no carga el catálogo completo.
		Usado por el dropdown de búsqueda en tiempo real.
		"""
		from sqlalchemy import or_

		with self._Session() as session:
			try:
				q_like = f'%{query}%'
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article).joinedload(Article.supplier),
						joinedload(ArticleVariant.stocks),
						joinedload(ArticleVariant.ingredients)
						.joinedload(ComboItem.ingredient)
						.joinedload(ArticleVariant.stocks),
						joinedload(ArticleVariant.base_variant).joinedload(
							ArticleVariant.stocks
						),
					)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						Article.is_active.is_(True),
						Article.deleted_at.is_(None),
						ArticleVariant.is_active,  # noqa: E712
						ArticleVariant.deleted_at.is_(None),
						or_(
							Article.name.ilike(q_like),
							ArticleVariant.barcode.ilike(q_like),
						),
					)
					.limit(limit)
					.all()
				)
				result = []
				for v in variants:
					if v.is_combo:
						virtual_stock = float('inf')
						for component in v.ingredients:
							if component.quantity_required > 0 and component.ingredient:
								available = sum(
									stock.quantity for stock in component.ingredient.stocks
								)
								virtual_stock = min(
									virtual_stock,
									int(Decimal(str(available)) / component.quantity_required),
								)
						total_stock = 0 if virtual_stock == float('inf') else virtual_stock
					else:
						total_stock = sum(s.quantity for s in v.stocks) if v.stocks else 0
					units = getattr(v, 'units_per_pack', 1) or 1
					base_vid = getattr(v, 'base_variant_id', None)
					if base_vid and units > 1:
						base = v.base_variant
						base_stock = (
							sum(s.quantity for s in base.stocks)
							if base and base.stocks
							else 0
						)
						total_stock = int(Decimal(str(base_stock)) // Decimal(str(units)))
					result.append(
						{
							'variant_id': v.id,
							'category_id': v.article.category_id,
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
							'units_per_pack': units,
							'pack_label': getattr(v, 'pack_label', None),
							'base_variant_id': base_vid,
							'discount_pct': float(v.discount_pct)
							if v.discount_pct
							else 0.0,
							'discount_until': v.discount_until,
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
				logger.error(f'Error en búsqueda de artículos: {e}', exc_info=True)
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
					for c in session.query(Customer.id, Customer.name, Customer.current_balance, Customer.price_list)
					.filter(
						Customer.tenant_id == tenant_id,
						Customer.is_active.is_(True),
						Customer.deleted_at.is_(None),
					)
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
				if not sale:
					return {
						'items': [],
						'discount_amount': 0.0,
						'payment_method': '',
						'payment_method_2': '',
						'amount_method_1': 0.0,
						'amount_method_2': 0.0,
						'total_amount': 0.0,
					}
				discount = float(sale.discount_amount or 0)
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
					'amount_method_1': float(sale.amount_method_1 or 0),
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
					'amount_method_1': 0.0,
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
		discount_pct=None,
		price_list='A',
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

		discount_pct = (
			self._parse_decimal(discount_pct)
			if discount_pct is not None
			else Decimal('0.0')
		)
		if not Decimal('0') <= discount_pct <= Decimal('100'):
			return False, 'El descuento debe estar entre 0% y 100%.'
		price_list = 'B' if str(price_list).upper() == 'B' else 'A'
		payment_method = str(payment_method or '').strip().lower()
		allowed_methods = {'efectivo', 'tarjeta', 'transferencia', 'qr', 'qr billetera'}
		if not is_fiado and payment_method not in allowed_methods:
			return False, 'Método de pago inválido.'

		# Normalizar pago mixto
		amount_m2 = Decimal('0')
		payment_method_2_lower = None
		if payment_method_2 and not is_fiado:
			payment_method_2_lower = str(payment_method_2).strip().lower()
			if payment_method_2_lower not in allowed_methods:
				return False, 'Segundo método de pago inválido.'
			if payment_method_2_lower == payment_method:
				return False, 'Los métodos de pago mixto deben ser distintos.'
			try:
				amount_m2 = self._parse_decimal(amount_method_2)
				if amount_m2 < Decimal('0'):
					amount_m2 = Decimal('0')
			except Exception as e:
				logger.warning('Error parseando monto método 2 (%r): %s — se usa 0', amount_method_2, e)
				amount_m2 = Decimal('0')

		with self._Session() as session:
			try:
				user = (
					session.query(User)
					.filter(
						User.id == user_id,
						User.tenant_id == tenant_id,
						User.is_active.is_(True),
						User.deleted_at.is_(None),
					)
					.first()
				)
				if not user:
					return False, 'Usuario inválido o inactivo.'
				user_role = str(user.role or '').strip().lower()
				max_discount = Decimal('100') if user_role in ('admin', 'gerente') else Decimal('20')
				if discount_pct > max_discount:
					return False, f'Tu perfil permite hasta {max_discount:.0f}% de descuento global.'
				if any(item.get('variant_id') is None for item in cart_items) and user_role not in (
					'admin',
					'gerente',
				):
					return False, 'La venta libre requiere una cuenta administradora.'
				active_cash = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.with_for_update()
					.first()
				)
				if not active_cash:
					return False, '⚠️ ¡Debes ABRIR LA CAJA en el menú antes de vender!'

				customer_str = 'Consumidor Final'
				customer_obj = None

				if customer_id:
					customer_obj = (
						session.query(Customer)
						.filter(
							Customer.id == customer_id,
							Customer.tenant_id == tenant_id,
							Customer.is_active.is_(True),
							Customer.deleted_at.is_(None),
						)
						.with_for_update()
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
						.filter(
							Customer.name == 'Consumidor Final',
							Customer.tenant_id == tenant_id,
							Customer.is_active.is_(True),
							Customer.deleted_at.is_(None),
						)
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
							joinedload(ArticleVariant.article).joinedload(Article.supplier),
							joinedload(ArticleVariant.ingredients).joinedload(
								ComboItem.ingredient
							),
						)
						.filter(
							ArticleVariant.id.in_(variant_ids_in_cart),
							Article.tenant_id == tenant_id,
							Article.is_active.is_(True),
							Article.deleted_at.is_(None),
							ArticleVariant.is_active.is_(True),
							ArticleVariant.deleted_at.is_(None),
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
					stocks_db = defaultdict(list)
					for stock_row in (
						session.query(Stock)
						.filter(Stock.variant_id.in_(variants_to_deduct))
						.with_for_update()
						.all()
					):
						stocks_db[stock_row.variant_id].append(stock_row)

				total_sale = Decimal('0.0')
				total_cost = Decimal('0.0')
				qty_by_variant = defaultdict(lambda: Decimal('0.0'))
				for item in cart_items:
					if item.get('variant_id') is not None:
						qty_by_variant[item['variant_id']] += self._parse_decimal(
							item.get('qty', 1)
						)
				sale_now = datetime.now()
				receipt_items = []

				for item in cart_items:
					qty = self._parse_decimal(item.get('qty', 1))
					if qty <= 0:
						raise ValueError(
							f'Cantidad inválida para: {item.get("desc", "Desconocido")}'
						)

					v_id = item.get('variant_id')
					cost_price = Decimal('0.0')
					description = str(item.get('desc', 'Artículo')).strip() or 'Artículo'
					# El precio libre se valida de forma explícita; los productos de catálogo
					# se recalculan exclusivamente desde la base local.
					price = self._parse_decimal(item.get('price', 0))

					if v_id is not None:
						variant = variants_db.get(v_id)
						if not variant:
							raise ValueError(
								f'Producto no encontrado o no autorizado: {item.get("desc")}'
							)

						price, description = self._resolve_variant_price(
							session,
							tenant_id,
							variant,
							qty_by_variant[v_id],
							price_list,
							sale_now,
						)

						if variant.is_combo:
							for ci in variant.ingredients:
								if ci.ingredient is None:
									raise ValueError(
										f'El combo "{variant.article.name}" contiene un ingrediente '
										'que fue eliminado del sistema. Actualiza el combo antes de vender.'
									)
								req_qty = ci.quantity_required * qty
								stock_rows = stocks_db.get(ci.ingredient_id, [])
								if not stock_rows:
									raise ValueError(
										f'Falta ingrediente para preparar: {variant.article.name}'
									)
								allocations = self._take_from_stock_rows(stock_rows, req_qty)
								cost_price += (
									ci.ingredient.cost_price or Decimal('0')
								) * ci.quantity_required
								for stock, allocated_qty in allocations:
									session.add(
										StockMovement(
											movement_type='out',
											quantity=allocated_qty,
											reference=f'Venta Promo #{new_sale.id}',
											source_warehouse_id=stock.warehouse_id,
											variant_id=ci.ingredient_id,
											user_id=user_id,
											tenant_id=tenant_id,
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

							stock_rows = stocks_db.get(deduct_vid, [])
							if not stock_rows:
								raise ValueError(
									f'Stock insuficiente para {variant.article.name}'
								)
							allocations = self._take_from_stock_rows(stock_rows, deduct_qty)
							cost_price = variant.cost_price or Decimal('0.0')
							for stock, allocated_qty in allocations:
								session.add(
									StockMovement(
										movement_type='out',
										quantity=allocated_qty,
										reference=f'Venta Ticket #{new_sale.id}',
										source_warehouse_id=stock.warehouse_id,
										variant_id=deduct_vid,
										user_id=user_id,
										tenant_id=tenant_id,
									)
								)
					else:
						if price <= 0:
							raise ValueError(
								'La venta libre debe tener un precio mayor a cero.'
							)
						if len(description) > 500:
							raise ValueError('La descripción de la venta libre es demasiado extensa.')

					subtotal = price * qty
					total_sale += subtotal
					total_cost += cost_price * qty
					new_sale.items.append(
						SaleDetail(
							variant_id=v_id,
							description=description,
							quantity=qty,
							unit_cost=cost_price,
							unit_price=price,
							subtotal=subtotal,
						)
					)
					receipt_items.append(
						{
							'desc': description,
							'price': price,
							'qty': qty,
							'subtotal': subtotal,
						}
					)

				# El descuento también se calcula desde el porcentaje validado, no desde la UI.
				discount_amount = (total_sale * discount_pct / Decimal(100)).quantize(
					Decimal('0.01')
				)
				final_total = total_sale - discount_amount
				if final_total < Decimal('0.0'):
					final_total = Decimal('0.0')
				if not is_fiado and not payment_method_2_lower and payment_method == 'efectivo':
					paid = self._parse_decimal(paid_amount) if paid_amount is not None else final_total
					if paid < final_total:
						raise ValueError('El pago en efectivo es menor al total de la venta.')

				new_sale.total_amount = final_total
				new_sale.discount_amount = discount_amount
				new_sale.profit = final_total - total_cost

				if is_fiado and customer_obj:
					customer_obj.current_balance = (
						customer_obj.current_balance or Decimal('0.0')
					) + final_total
				else:
					disc_str = (
						f' (Desc: ${discount_amount:.2f})'
						if discount_amount > 0
						else ''
					)
					_CASH_METHODS = {'efectivo'}
					if payment_method_2_lower and amount_m2 > 0:
						# Pago mixto: dos movimientos de caja
						if amount_m2 > final_total:
							raise ValueError(
								f'El monto del segundo método (${amount_m2:.2f}) supera el total (${final_total:.2f}).'
							)
						if amount_m2 <= Decimal('0.0'):
							raise ValueError(
								'El monto del segundo método de pago debe ser mayor a cero.'
							)
						amount_m1 = final_total - amount_m2

						if abs((amount_m1 + amount_m2) - final_total) > Decimal('0.01'):
							raise ValueError(
								f'Los montos del pago mixto (${amount_m1:.2f} + ${amount_m2:.2f}) '
								f'no coinciden con el total (${final_total:.2f}).'
							)

						new_sale.payment_method_2 = payment_method_2_lower
						new_sale.amount_method_2 = amount_m2
						new_sale.amount_method_1 = amount_m1
						# Solo el método en efectivo afecta el saldo físico de caja
						mov_type_1 = (
							'venta'
							if payment_method.lower() in _CASH_METHODS
							else 'venta_digital'
						)
						mov_type_2 = (
							'venta'
							if payment_method_2_lower in _CASH_METHODS
							else 'venta_digital'
						)
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type=mov_type_1,
								amount=amount_m1,
								description=f'Ticket #{new_sale.id} - {payment_method.capitalize()} (Mixto){disc_str}',
							)
						)
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type=mov_type_2,
								amount=amount_m2,
								description=f'Ticket #{new_sale.id} - {payment_method_2_lower.capitalize()} (Mixto)',
							)
						)
					else:
						mov_type = (
							'venta'
							if payment_method.lower() in _CASH_METHODS
							else 'venta_digital'
						)
						session.add(
							CashMovement(
								session_id=active_cash.id,
								movement_type=mov_type,
								amount=final_total,
								description=f'Ticket #{new_sale.id} - Pago: {payment_method.capitalize()}{disc_str}',
							)
						)

				# Capturar antes del commit para evitar lazy loads post-commit
				_sale_id = new_sale.id
				_sale_date = new_sale.date
				try:
					cashier_label = get_display_name(user)
				except Exception as e:
					logger.warning('Error obteniendo nombre del cajero %s: %s', user_id, e)
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
						except Exception as _e:
							logger.warning('Error calculando vuelto (paid=%r total=%s): %s', paid_amount, final_total, _e)
							change_amt = Decimal('0')

					import threading
					def _run_pdf():
						try:
							ReceiptController().generate_pdf(
								tenant_id=tenant_id,
								sale_id=_sale_id,
								date_str=_sale_date.strftime('%d/%m/%Y  %H:%M'),
								items_list=receipt_items,
								total=final_total,
								customer_name=customer_str,
								discount_amount=discount_amount,
								payment_method=None if is_fiado else pm_lower,
								payment_method_2=payment_method_2_lower if payment_method_2_lower else None,
								amount_method_2=amount_m2 if amount_m2 > 0 else None,
								paid_amount=paid_dec,
								change_amount=change_amt,
								cashier_name=cashier_label,
							)
						except Exception as pdf_err:
							logger.warning(f'Fallo la generacion del ticket en hilo: {pdf_err}')
					
					threading.Thread(target=_run_pdf, daemon=True).start()
				except Exception as thread_err:
					logger.warning(
						f'Venta guardada, pero falló el inicio del hilo de ticket: {thread_err}'
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
