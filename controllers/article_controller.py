import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
from database.models import (
	Article,
	ArticleHistory,
	ArticleVariant,
	Category,
	Stock,
	StockMovement,
	Supplier,
)
from utils.shared import get_or_create_default_warehouse

logger = logging.getLogger(__name__)


def _to_decimal_or_none(val):
	if val is None or val == '':
		return None
	try:
		d = Decimal(str(val))
		return d if d.is_finite() and d > 0 else None
	except (InvalidOperation, ValueError, TypeError) as e:
		logger.warning('_to_decimal_or_none falló para %r: %s', val, e)
		return None


def _parse_nonnegative_decimal(value, label):
	try:
		parsed = Decimal(str(value))
	except (InvalidOperation, ValueError, TypeError):
		return None, f'{label} es inválido.'
	if not parsed.is_finite() or parsed < 0:
		return None, f'{label} no puede ser negativo ni no numérico.'
	return parsed, None


def _parse_nonnegative_int(value, label):
	try:
		parsed = int(str(value))
		exact = Decimal(str(value))
	except (InvalidOperation, ValueError, TypeError):
		return None, f'{label} es inválido.'
	if parsed < 0 or exact != parsed:
		return None, f'{label} debe ser un entero no negativo.'
	return parsed, None


class ArticleController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
		try:
			return get_or_create_default_warehouse(session, tenant_id)
		except Exception as e:
			logger.error(
				f'Error al obtener/crear almacén por defecto: {e}', exc_info=True
			)
			raise

	@staticmethod
	def _add_price_history(
		session, tenant_id, user_id, variant, old_cost, old_price, new_cost, new_price, action
	):
		if old_cost == new_cost and old_price == new_price:
			return
		session.add(ArticleHistory(
			tenant_id=tenant_id, user_id=user_id, action_type=action,
			article_name=variant.article.name, variant_id=variant.id,
			old_cost=old_cost, new_cost=new_cost, old_price=old_price, new_price=new_price,
		))

	@staticmethod
	def _reference_belongs_to_tenant(session, model, record_id, tenant_id):
		if not record_id:
			return True
		query = session.query(model).filter(model.id == record_id)
		if model is Category:
			query = query.filter(
				(Category.tenant_id == tenant_id) | (Category.tenant_id.is_(None))
			)
		else:
			query = query.filter_by(tenant_id=tenant_id, is_active=True)
		return query.first() is not None

	def get_suppliers_for_combo(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{'id': s.id, 'name': s.name}
					for s in session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.filter(Supplier.deleted_at.is_(None))
					.order_by(Supplier.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error obteniendo proveedores: {e}', exc_info=True)
				return []

	def get_all_variants(
		self, tenant_id, include_inactive: bool = False, include_packaging: bool = True
	):
		with self._Session() as session:
			try:
				q = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article).joinedload(Article.supplier),
						joinedload(ArticleVariant.article).joinedload(Article.category),
						joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						Article.deleted_at.is_(None),
					)
					.order_by(Article.name)
				)
				if not include_inactive:
					q = q.filter(
						Article.is_active.is_(True),
						ArticleVariant.is_active == True,  # noqa: E712
						ArticleVariant.deleted_at.is_(None),
					)
				if not include_packaging:
					q = q.filter(ArticleVariant.base_variant_id.is_(None))

				variants = q.all()
				variants_by_id = {v.id: v for v in variants}
				result = []
				for v in variants:
					total_stock = sum(s.quantity for s in v.stocks) if v.stocks else 0
					base_variant = variants_by_id.get(v.base_variant_id)
					if base_variant:
						base_stock = sum(s.quantity for s in base_variant.stocks)
						total_stock = base_stock / (v.units_per_pack or 1)
					result.append(
						{
						'variant_id': v.id,
						'article_id': v.article_id,
						'name': v.article.name,
						'barcode': v.barcode,
						'cost_price': v.cost_price,
						'selling_price': v.selling_price,
						'selling_price_b': float(v.selling_price_b)
						if v.selling_price_b
						else None,
						'total_stock': total_stock,
						'min_stock': v.article.min_stock or 0,
						'supplier_id': v.article.supplier_id,
						'supplier_name': v.article.supplier.name
						if v.article.supplier
						else 'Sin Proveedor',
						'category_id': v.article.category_id,
						'category_name': v.article.category.name
						if v.article.category
						else 'Sin Categoría',
						'units_per_pack': v.units_per_pack or 1,
						'pack_label': v.pack_label,
						'base_variant_id': v.base_variant_id,
						'discount_pct': float(v.discount_pct)
						if v.discount_pct
						else 0.0,
						'discount_until': v.discount_until,
						'is_combo': v.is_combo or False,
						'btn_color': v.btn_color,
						'show_on_touch': v.show_on_touch or False,
						'is_active': v.is_active,
						}
					)
				return result
			except Exception as e:
				logger.error(f'Error al obtener variantes: {e}', exc_info=True)
				return []

	def add_simple_article(
		self,
		tenant_id,
		user_id,
		name,
		barcode,
		cost_price,
		selling_price,
		initial_stock,
		supplier_id=None,
		discount_pct=None,
		discount_until=None,
		selling_price_b=None,
		category_id=None,
		margin_pct=None,
		min_stock=0,
	):
		if not name or not str(name).strip():
			return False, 'El nombre es obligatorio.'
		if not barcode or not str(barcode).strip():
			return False, 'El código de barras es obligatorio.'

		cost_price, error = _parse_nonnegative_decimal(cost_price, 'El precio de costo')
		if error:
			return False, error
		selling_price, error = _parse_nonnegative_decimal(selling_price, 'El precio de venta')
		if error:
			return False, error
		initial_stock, error = _parse_nonnegative_decimal(initial_stock, 'El stock inicial')
		if error:
			return False, error
		min_stock, error = _parse_nonnegative_int(min_stock, 'El stock mínimo')
		if error:
			return False, error

		with self._Session() as session:
			try:
				if not self._reference_belongs_to_tenant(
					session, Supplier, supplier_id, tenant_id
				):
					return False, 'Proveedor inválido o inactivo.'
				if not self._reference_belongs_to_tenant(
					session, Category, category_id, tenant_id
				):
					return False, 'Categoría inválida.'
				exists = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.barcode == str(barcode).strip(),
						ArticleVariant.is_active == True,  # noqa: E712
					)
					.first()
				)
				if exists:
					return False, f'El código "{barcode}" ya está en uso.'

				warehouse_id = self._get_or_create_default_warehouse(session, tenant_id)

				article = Article(
					name=str(name).strip(),
					tenant_id=tenant_id,
					has_variants=False,
					supplier_id=supplier_id,
					category_id=category_id,
					min_stock=min_stock,
				)
				session.add(article)
				session.flush()

				spb = None
				if selling_price_b is not None:
					try:
						spb = Decimal(str(selling_price_b))
						if not spb.is_finite() or spb <= 0:
							spb = None
					except (InvalidOperation, ValueError, TypeError) as e:
						logger.warning('selling_price_b inválido %r en add_simple_article: %s', selling_price_b, e)
						spb = None

				variant = ArticleVariant(
					barcode=str(barcode).strip(),
					cost_price=cost_price,
					selling_price=selling_price,
					selling_price_b=spb,
					article_id=article.id,
					discount_pct=_to_decimal_or_none(discount_pct),
					discount_until=discount_until,
					margin_pct=_to_decimal_or_none(margin_pct),
				)
				session.add(variant)
				session.flush()

				session.add(
					Stock(
						quantity=initial_stock,
						warehouse_id=warehouse_id,
						variant_id=variant.id,
					)
				)

				if initial_stock > 0:
					session.add(
						StockMovement(
							movement_type='in',
							quantity=initial_stock,
							reference='Inventario Inicial',
							dest_warehouse_id=warehouse_id,
							variant_id=variant.id,
							user_id=user_id,
							tenant_id=tenant_id,
						)
					)

				session.commit()
				return True, f"Artículo '{name}' creado."
			except IntegrityError:
				session.rollback()
				return False, 'El código de barras ya está asignado a otro producto activo.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear artículo: {e}', exc_info=True)
				return False, 'Error interno al crear el artículo.'

	def update_article(
		self,
		tenant_id,
		user_id,
		variant_id,
		name,
		barcode,
		cost_price,
		selling_price,
		supplier_id=None,
		discount_pct=None,
		discount_until=None,
		selling_price_b=None,
		category_id=None,
		margin_pct=None,
		min_stock=0,
	):
		if not name or not str(name).strip():
			return False, 'El nombre es obligatorio.'
		if not barcode or not str(barcode).strip():
			return False, 'El código de barras es obligatorio.'

		cost_price, error = _parse_nonnegative_decimal(cost_price, 'El precio de costo')
		if error:
			return False, error
		selling_price, error = _parse_nonnegative_decimal(selling_price, 'El precio de venta')
		if error:
			return False, error
		min_stock, error = _parse_nonnegative_int(min_stock, 'El stock mínimo')
		if error:
			return False, error

		with self._Session() as session:
			try:
				if not self._reference_belongs_to_tenant(
					session, Supplier, supplier_id, tenant_id
				):
					return False, 'Proveedor inválido o inactivo.'
				if not self._reference_belongs_to_tenant(
					session, Category, category_id, tenant_id
				):
					return False, 'Categoría inválida.'
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						ArticleVariant.base_variant_id.is_(None),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Producto base no encontrado.'

				if variant.barcode != str(barcode).strip():
					conflict = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == str(barcode).strip(),
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.first()
					)
					if conflict:
						return (
							False,
							'Ese código de barras ya pertenece a otro producto.',
						)

				old_cost = variant.cost_price
				old_price = variant.selling_price

				# Actualizamos
				variant.barcode = str(barcode).strip()
				variant.cost_price = cost_price
				variant.selling_price = selling_price
				variant.article.name = str(name).strip()
				variant.article.supplier_id = supplier_id
				variant.article.category_id = category_id
				variant.article.min_stock = min_stock
				variant.margin_pct = _to_decimal_or_none(margin_pct)

				spb = None
				if selling_price_b is not None:
					try:
						spb = Decimal(str(selling_price_b))
						if not spb.is_finite() or spb <= 0:
							spb = None
					except (InvalidOperation, ValueError, TypeError) as e:
						logger.warning('selling_price_b inválido %r en update_article: %s', selling_price_b, e)
						spb = None
				variant.selling_price_b = spb

				# Descuento por producto
				variant.discount_pct = _to_decimal_or_none(discount_pct)
				variant.discount_until = discount_until

				if old_cost != cost_price:
					child_variants = (
						session.query(ArticleVariant)
						.filter(
							ArticleVariant.base_variant_id == variant.id,
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.all()
					)
					for child in child_variants:
						old_child_cost = child.cost_price
						child.cost_price = cost_price * (child.units_per_pack or 1)
						self._add_price_history(
							session, tenant_id, user_id, child, old_child_cost,
							child.selling_price, child.cost_price, child.selling_price,
							'MODIFICACIÓN MANUAL',
						)

				if old_cost != cost_price or old_price != selling_price:
					cost_up = cost_price > old_cost
					price_up = selling_price > old_price
					cost_down = cost_price < old_cost
					price_down = selling_price < old_price

					if (cost_up or price_up) and not (cost_down or price_down):
						action_type = 'AUMENTO MANUAL'
					elif (cost_down or price_down) and not (cost_up or price_up):
						action_type = 'REDUCCIÓN MANUAL'
					else:
						action_type = 'MODIFICACIÓN MANUAL'

					self._add_price_history(
						session, tenant_id, user_id, variant, old_cost, old_price,
						cost_price, selling_price, action_type,
					)

				session.commit()
				return True, f"Artículo '{name}' actualizado correctamente."
			except IntegrityError:
				session.rollback()
				return False, 'El código de barras ya está asignado a otro producto activo.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al actualizar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al actualizar.'

	def delete_variant(self, tenant_id, variant_id):
		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						ArticleVariant.base_variant_id.is_(None),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Producto base no encontrado.'

				active_packs = (
					session.query(ArticleVariant.id)
					.filter(
						ArticleVariant.base_variant_id == variant.id,
						ArticleVariant.is_active.is_(True),
					)
					.count()
				)
				if active_packs:
					return (
						False,
						'No se puede desactivar un producto con presentaciones activas. '
						'Desactívalas primero desde “Presentaciones”.',
					)

				total_stock = (
					sum(s.quantity for s in variant.stocks) if variant.stocks else 0
				)
				if total_stock > 0:
					return (
						False,
						f'No se puede eliminar un artículo con stock positivo ({total_stock} unidades). '
						'Ajuste el stock primero o realice una salida manual.',
					)

				variant.is_active = False
				all_variants = (
					session.query(ArticleVariant)
					.filter_by(article_id=variant.article_id)
					.all()
				)
				if all(not v.is_active for v in all_variants):
					variant.article.is_active = False
				session.commit()
				return True, 'Producto desactivado correctamente.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al eliminar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar eliminar.'

	def reactivate_variant(self, tenant_id, variant_id):
		"""Restores a base product without silently reactivating its packages."""
		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						ArticleVariant.base_variant_id.is_(None),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Producto base no encontrado.'
				variant.article.is_active = True
				variant.is_active = True
				session.commit()
				return True, 'Producto reactivado. Las presentaciones permanecen inactivas hasta que las reactives.'
			except Exception as e:
				session.rollback()
				logger.error('Error al reactivar variante %s: %s', variant_id, e, exc_info=True)
				return False, 'Error interno al reactivar el producto.'

	def get_categories_for_combo(self, tenant_id):
		with self._Session() as session:
			try:
				# Devuelve categorías del tenant + categorías globales (tenant_id=None)
				# para que el usuario pueda reclasificar.
				return [
					{'id': c.id, 'name': c.name}
					for c in session.query(Category)
					.filter(
						(Category.tenant_id == tenant_id) | (Category.tenant_id.is_(None))
					)
					.order_by(Category.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error obteniendo categorías: {e}', exc_info=True)
				return []

	def bulk_update_variants(self, tenant_id, user_id, variant_ids, updates):
		"""
		Aplica cambios masivos a una lista de variantes y sus artículos relacionados.
		updates: dict con campos (category_id, supplier_id, is_active, show_on_touch, discount_pct)
		"""
		if not variant_ids:
			return False, 'No se seleccionaron artículos.'

		for key, label in (('selling_price', 'El precio de venta'), ('cost_price', 'El precio de costo')):
			if key in updates:
				value, error = _parse_nonnegative_decimal(updates[key], label)
				if error:
					return False, error
				updates[key] = value

		with self._Session() as session:
			try:
				if 'supplier_id' in updates and not self._reference_belongs_to_tenant(
					session, Supplier, updates['supplier_id'], tenant_id
				):
					return False, 'Proveedor inválido o inactivo.'
				if 'category_id' in updates and not self._reference_belongs_to_tenant(
					session, Category, updates['category_id'], tenant_id
				):
					return False, 'Categoría inválida.'
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(ArticleVariant.id.in_(variant_ids), Article.tenant_id == tenant_id)
					.all()
				)
				if not variants:
					return False, 'No se encontraron los artículos seleccionados.'
				if 'cost_price' in updates and any(v.base_variant_id for v in variants):
					return False, 'El costo de una presentación se calcula desde su producto base.'
				if updates.get('is_active') is False:
					base_ids = [v.id for v in variants if not v.base_variant_id]
					if base_ids and session.query(ArticleVariant.id).filter(
						ArticleVariant.base_variant_id.in_(base_ids), ArticleVariant.is_active.is_(True)
					).first():
						return False, 'No podés desactivar un producto base con presentaciones activas.'
				if updates.get('is_active') is True:
					for pack in (v for v in variants if v.base_variant_id):
						base = session.get(ArticleVariant, pack.base_variant_id)
						if not base or not base.is_active or not base.article.is_active:
							return False, 'Reactivá primero el producto base antes de activar una presentación.'

				price_before = {}
				updated_articles = set()
				for v in variants:
					price_before[v.id] = (v, v.cost_price, v.selling_price)
					if 'show_on_touch' in updates:
						v.show_on_touch = updates['show_on_touch']
					if 'discount_pct' in updates:
						v.discount_pct = _to_decimal_or_none(updates['discount_pct'])
					if 'selling_price' in updates:
						v.selling_price = updates['selling_price']
					if 'cost_price' in updates:
						v.cost_price = updates['cost_price']
					if 'is_active' in updates:
						v.is_active = updates['is_active']
					art = v.article
					if art.id not in updated_articles:
						if 'category_id' in updates:
							art.category_id = updates['category_id']
						if 'supplier_id' in updates:
							art.supplier_id = updates['supplier_id']
						if 'is_active' in updates and not v.base_variant_id:
							art.is_active = updates['is_active']
						updated_articles.add(art.id)

				# Package costs are derived data. Recalculate and audit them whenever
				# their base cost changes, even if the packages were not selected.
				if 'cost_price' in updates:
					for base in variants:
						if base.base_variant_id:
							continue
						for child in session.query(ArticleVariant).filter(
							ArticleVariant.base_variant_id == base.id
						).all():
							if child.id not in price_before:
								price_before[child.id] = (child, child.cost_price, child.selling_price)
							child.cost_price = base.cost_price * (child.units_per_pack or 1)

				for variant, old_cost, old_price in price_before.values():
					self._add_price_history(
						session, tenant_id, user_id, variant, old_cost, old_price,
						variant.cost_price, variant.selling_price, 'MODIFICACIÓN MASIVA',
					)
				session.commit()
				return True, f'Se actualizaron {len(variants)} ítems correctamente.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error en actualización masiva: {e}', exc_info=True)
				return False, 'Error interno al procesar los cambios.'

	def apply_bulk_price_changes(self, tenant_id, user_id, changes_list):
		if not changes_list:
			return False, 'No hay cambios para aplicar.'
		for item in changes_list:
			for key, label in (('new_cost', 'El precio de costo'), ('new_selling', 'El precio de venta')):
				if key not in item:
					continue
				value, error = _parse_nonnegative_decimal(item[key], label)
				if error:
					return False, error
				item[key] = value

		variant_ids = [item['variant_id'] for item in changes_list]
		changes_by_id = {item['variant_id']: item for item in changes_list}

		with self._Session() as session:
			try:
				# Single query with IN + eager load article (evita N+1 y lazy loads)
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(
						ArticleVariant.id.in_(variant_ids),
						Article.tenant_id == tenant_id,
					)
					.all()
				)

				updated = 0
				not_found = len(variant_ids) - len(variants)

				for variant in variants:
					item = changes_by_id[variant.id]
					old_cost = variant.cost_price
					old_price = variant.selling_price
					new_cost = item.get('new_cost', old_cost)
					new_price = item.get('new_selling', old_price)

					if new_price == old_price and new_cost == old_cost:
						not_found += 1
						continue

					variant.cost_price = new_cost
					variant.selling_price = new_price

					price_up = new_price > old_price
					price_down = new_price < old_price
					cost_up = new_cost > old_cost
					cost_down = new_cost < old_cost

					if (price_up or cost_up) and not (price_down or cost_down):
						action_type = 'AUMENTO MASIVO'
					elif (price_down or cost_down) and not (price_up or cost_up):
						action_type = 'REDUCCIÓN MASIVA'
					else:
						action_type = 'MODIFICACIÓN MASIVA'

					self._add_price_history(
						session, tenant_id, user_id, variant, old_cost, old_price,
						new_cost, new_price, action_type,
					)
					updated += 1

				session.commit()
				msg = f'¡Se actualizaron {updated} artículos correctamente!'
				if not_found:
					msg += f' ({not_found} sin cambios o no encontrados)'
				return True, msg
			except Exception as e:
				session.rollback()
				logger.error(f'Error en actualización masiva: {e}', exc_info=True)
				return False, 'Error interno al guardar los nuevos precios.'

	def get_price_history(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{
						'date': h.date,
						'action': h.action_type,
						'article_name': h.article_name,
						'user_name': get_display_name(h.user) if h.user else 'Sistema',
						'old_cost': h.old_cost,
						'new_cost': h.new_cost,
						'old_price': h.old_price,
						'new_price': h.new_price,
					}
					for h in (
						session.query(ArticleHistory)
						.options(joinedload(ArticleHistory.user))
						.filter_by(tenant_id=tenant_id)
						.order_by(ArticleHistory.date.desc())
						.limit(100)
						.all()
					)
				]
			except Exception as e:
				logger.error(
					f'Error al obtener historial de precios: {e}', exc_info=True
				)
				return []

	def get_packaging_variants(self, tenant_id, base_variant_id, include_inactive=False):
		"""Retorna las presentaciones (cajon, pallet, etc.) de una variante base."""
		with self._Session() as session:
			try:
				query = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.base_variant_id == base_variant_id,
						Article.tenant_id == tenant_id,
					)
				)
				if not include_inactive:
					query = query.filter(ArticleVariant.is_active.is_(True))
				variants = (
					query
					.order_by(ArticleVariant.units_per_pack)
					.all()
				)
				return [
					{
						'variant_id': v.id,
						'barcode': v.barcode or '',
						'pack_label': v.pack_label or '',
						'units_per_pack': v.units_per_pack or 1,
						'selling_price': float(v.selling_price),
					}
					for v in variants
				]
			except Exception as e:
				logger.error(f'Error al obtener presentaciones: {e}', exc_info=True)
				return []

	def add_packaging_variant(
		self,
		tenant_id,
		base_variant_id,
		pack_label,
		units_per_pack,
		selling_price,
		barcode=None,
	):
		"""
		Agrega una presentacion (ej: Cajon 12u) vinculada a una variante base.
		El stock se descuenta de la variante base al vender.
		"""
		try:
			units_per_pack = int(units_per_pack)
		except (ValueError, TypeError):
			return False, 'Datos numericos invalidos.'
		selling_price, error = _parse_nonnegative_decimal(selling_price, 'El precio de venta')
		if error:
			return False, error

		if units_per_pack < 2:
			return False, 'La presentacion debe tener al menos 2 unidades por paquete.'
		if selling_price <= 0:
			return False, 'El precio de venta debe ser mayor a cero.'
		if not pack_label or not str(pack_label).strip():
			return False, 'El nombre de la presentacion es obligatorio.'

		with self._Session() as session:
			try:
				# Verificar que la variante base pertenece al tenant
				base = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == base_variant_id,
						ArticleVariant.base_variant_id.is_(None),
						ArticleVariant.is_active.is_(True),
						Article.is_active.is_(True),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not base:
					return False, 'Variante base no encontrada.'

				# Verificar barcode unico si se proporciona
				bc = str(barcode).strip() if barcode and str(barcode).strip() else None
				if bc:
					conflict = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == bc,
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.first()
					)
					if conflict:
						return False, f'El codigo "{bc}" ya esta en uso.'

				variant = ArticleVariant(
					article_id=base.article_id,
					barcode=bc,
					cost_price=base.cost_price * units_per_pack,
					selling_price=selling_price,
					units_per_pack=units_per_pack,
					pack_label=str(pack_label).strip(),
					base_variant_id=base_variant_id,
				)
				session.add(variant)
				session.commit()
				return True, f'Presentacion "{pack_label}" agregada.'
			except IntegrityError:
				session.rollback()
				return False, 'El código de barras ya está asignado a otro producto activo.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al agregar presentacion: {e}', exc_info=True)
				return False, 'Error interno al agregar la presentacion.'

	def update_packaging_variant(
		self,
		tenant_id,
		variant_id,
		pack_label,
		units_per_pack,
		selling_price,
		barcode=None,
	):
		"""Edita los datos de una variante de presentacion existente."""
		try:
			units_per_pack = int(units_per_pack)
		except (ValueError, TypeError):
			return False, 'Datos numericos invalidos.'
		selling_price, error = _parse_nonnegative_decimal(selling_price, 'El precio de venta')
		if error:
			return False, error

		if units_per_pack < 2:
			return False, 'La presentacion debe tener al menos 2 unidades por paquete.'
		if selling_price <= 0:
			return False, 'El precio de venta debe ser mayor a cero.'
		if not pack_label or not str(pack_label).strip():
			return False, 'El nombre de la presentacion es obligatorio.'

		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						ArticleVariant.base_variant_id.isnot(None),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Presentacion no encontrada.'

				# Verificar barcode unico si cambio
				bc = str(barcode).strip() if barcode and str(barcode).strip() else None
				if bc and bc != (variant.barcode or ''):
					conflict = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == bc,
							ArticleVariant.is_active == True,  # noqa: E712
							ArticleVariant.id != variant_id,
						)
						.first()
					)
					if conflict:
						return False, f'El codigo "{bc}" ya esta en uso.'

				# Recalcular costo proporcional desde la variante base
				base = session.get(ArticleVariant, variant.base_variant_id)
				variant.pack_label = str(pack_label).strip()
				variant.units_per_pack = units_per_pack
				variant.selling_price = selling_price
				variant.barcode = bc
				if base:
					variant.cost_price = base.cost_price * units_per_pack

				session.commit()
				return True, f'Presentacion "{pack_label}" actualizada.'
			except IntegrityError:
				session.rollback()
				return False, 'El código de barras ya está asignado a otro producto activo.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al editar presentacion: {e}', exc_info=True)
				return False, 'Error interno al editar la presentacion.'

	def delete_packaging_variant(self, tenant_id, variant_id):
		"""Elimina (desactiva) una variante de presentacion."""
		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						ArticleVariant.base_variant_id.isnot(None),
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Presentacion no encontrada.'
				variant.is_active = False
				session.commit()
				return True, 'Presentacion eliminada.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al eliminar presentacion: {e}', exc_info=True)
				return False, 'Error interno.'

	def set_discount(self, tenant_id, variant_id, discount_pct, discount_until):
		"""Actualiza o elimina el descuento de una variante."""
		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Artículo no encontrado.'
				variant.discount_pct = _to_decimal_or_none(discount_pct)
				variant.discount_until = discount_until
				session.commit()
				return True, 'Descuento actualizado.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al actualizar descuento: {e}', exc_info=True)
				return False, 'Error interno al actualizar el descuento.'

	def set_supplier_discount(
		self, tenant_id, supplier_id, discount_pct, discount_until
	):
		"""Configura o elimina el descuento de un distribuidor/proveedor completo."""
		with self._Session() as session:
			try:
				supplier = (
					session.query(Supplier)
					.filter_by(id=supplier_id, tenant_id=tenant_id, is_active=True)
					.first()
				)
				if not supplier:
					return False, 'Proveedor no encontrado.'
				supplier.discount_pct = _to_decimal_or_none(discount_pct)
				supplier.discount_until = discount_until
				session.commit()
				return True, f"Descuento de distribuidor '{supplier.name}' actualizado."
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al actualizar descuento de proveedor: {e}', exc_info=True
				)
				return (
					False,
					'Error interno al actualizar el descuento del distribuidor.',
				)

	def get_supplier_discount(self, tenant_id, supplier_id):
		"""Retorna el descuento activo de un proveedor, o (0, None) si no tiene."""
		with self._Session() as session:
			try:
				s = (
					session.query(Supplier)
					.filter_by(id=supplier_id, tenant_id=tenant_id)
					.first()
				)
				if not s:
					return 0.0, None
				return float(s.discount_pct or 0), s.discount_until
			except Exception as e:
				logger.warning('Error obteniendo descuento proveedor %s: %s', supplier_id, e)
				return 0.0, None
