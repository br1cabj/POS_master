import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import (
	Article,
	ArticleHistory,
	ArticleVariant,
	Stock,
	StockMovement,
	Supplier,
)
from utils.config import make_engine
from utils.shared import get_or_create_default_warehouse

logger = logging.getLogger(__name__)

_default_engine = make_engine()


class ArticleController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		super().__init__(engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
		try:
			return get_or_create_default_warehouse(session, tenant_id)
		except Exception as e:
			logger.error(
				f'Error al obtener/crear almacén por defecto: {e}', exc_info=True
			)
			raise

	def get_suppliers_for_combo(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{'id': s.id, 'name': s.name}
					for s in session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				]
			except Exception as e:
				logger.error(f'Error obteniendo proveedores: {e}', exc_info=True)
				return []

	def get_all_variants(self, tenant_id):
		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article).joinedload(Article.supplier),
						joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.is_active == True,  # noqa: E712
					)
					.order_by(Article.name)
					.all()
				)

				return [
					{
						'variant_id': v.id,
						'article_id': v.article_id,
						'name': v.article.name,
						'barcode': v.barcode,
						'cost_price': v.cost_price,
						'selling_price': v.selling_price,
						'total_stock': sum(s.quantity for s in v.stocks)
						if v.stocks
						else 0,
						'supplier_id': v.article.supplier_id,
						'supplier_name': v.article.supplier.name
						if v.article.supplier
						else 'Sin Proveedor',
					}
					for v in variants
				]
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
	):
		if not name or not str(name).strip():
			return False, 'El nombre es obligatorio.'
		if not barcode or not str(barcode).strip():
			return False, 'El código de barras es obligatorio.'

		try:
			cost_price = Decimal(str(cost_price))
			selling_price = Decimal(str(selling_price))
			initial_stock = Decimal(str(initial_stock))
		except (InvalidOperation, ValueError):
			return False, 'Valores numéricos inválidos.'

		if initial_stock < 0 or cost_price < 0 or selling_price < 0:
			return False, 'Los precios y el stock no pueden ser negativos.'

		with self._Session() as session:
			try:
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
				)
				session.add(article)
				session.flush()

				variant = ArticleVariant(
					barcode=str(barcode).strip(),
					cost_price=cost_price,
					selling_price=selling_price,
					article_id=article.id,
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
						)
					)

				session.commit()
				return True, f"Artículo '{name}' creado."
			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear artículo: {e}', exc_info=True)
				return False, 'Error interno al crear el artículo.'

	def update_article(
		self,
		tenant_id,
		user_id,  # ── NUEVO: Requerido para la auditoría ──
		variant_id,
		name,
		barcode,
		cost_price,
		selling_price,
		supplier_id=None,
	):
		if not name or not str(name).strip():
			return False, 'El nombre es obligatorio.'
		if not barcode or not str(barcode).strip():
			return False, 'El código de barras es obligatorio.'

		try:
			cost_price = Decimal(str(cost_price))
			selling_price = Decimal(str(selling_price))
		except (InvalidOperation, ValueError):
			return False, 'Valores numéricos inválidos.'

		if cost_price < 0 or selling_price < 0:
			return False, 'Los precios no pueden ser negativos.'

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

				if old_cost != cost_price or old_price != selling_price:
					if selling_price > old_price or cost_price > old_cost:
						action_type = 'AUMENTO MANUAL'
					elif selling_price < old_price or cost_price < old_cost:
						action_type = 'REDUCCIÓN MANUAL'
					else:
						action_type = 'MODIFICACIÓN MANUAL'

					session.add(
						ArticleHistory(
							tenant_id=tenant_id,
							user_id=user_id,
							action_type=action_type,
							article_name=variant.article.name,
							variant_id=variant.id,
							old_cost=old_cost,
							new_cost=cost_price,
							old_price=old_price,
							new_price=selling_price,
						)
					)

				session.commit()
				return True, f"Artículo '{name}' actualizado correctamente."
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
						Article.tenant_id == tenant_id,
					)
					.first()
				)
				if not variant:
					return False, 'Artículo no encontrado.'

				total_stock = (
					sum(s.quantity for s in variant.stocks) if variant.stocks else 0
				)
				if total_stock > 0:
					logger.warning(
						f'Variante {variant_id} desactivada con stock positivo ({total_stock}).'
					)

				variant.is_active = False
				session.commit()
				return True, 'Artículo eliminado correctamente.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al eliminar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar eliminar.'

	def apply_bulk_price_changes(self, tenant_id, user_id, changes_list):
		if not changes_list:
			return False, 'No hay cambios para aplicar.'

		with self._Session() as session:
			try:
				updated = 0
				for item in changes_list:
					variant = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							ArticleVariant.id == item['variant_id'],
							Article.tenant_id == tenant_id,
						)
						.first()
					)
					if not variant:
						continue

					old_cost = variant.cost_price
					old_price = variant.selling_price
					new_cost = (
						Decimal(str(item['new_cost']))
						if 'new_cost' in item
						else old_cost
					)
					new_price = (
						Decimal(str(item['new_selling']))
						if 'new_selling' in item
						else old_price
					)

					variant.cost_price = new_cost
					variant.selling_price = new_price

					if new_price > old_price or new_cost > old_cost:
						action_type = 'AUMENTO MASIVO'
					elif new_price < old_price or new_cost < old_cost:
						action_type = 'REDUCCIÓN MASIVA'
					else:
						action_type = 'SIN CAMBIO'

					session.add(
						ArticleHistory(
							tenant_id=tenant_id,
							user_id=user_id,
							action_type=action_type,
							article_name=variant.article.name,
							variant_id=variant.id,
							old_cost=old_cost,
							new_cost=new_cost,
							old_price=old_price,
							new_price=new_price,
						)
					)
					updated += 1

				session.commit()
				return True, f'¡Se actualizaron {updated} artículos correctamente!'
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
						'user_name': h.user.username if h.user else 'Sistema',
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
