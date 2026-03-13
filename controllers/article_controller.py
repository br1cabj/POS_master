import logging
from decimal import Decimal

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	Stock,
	StockMovement,
	Supplier,
	Warehouse,
)

logger = logging.getLogger(__name__)


class ArticleController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
		try:
			branch = (
				session.query(Branch)
				.filter_by(tenant_id=tenant_id, name='Sede Principal')
				.first()
			)
			if not branch:
				branch = Branch(name='Sede Principal', tenant_id=tenant_id)
				session.add(branch)
				session.flush()

			warehouse = (
				session.query(Warehouse)
				.filter_by(branch_id=branch.id, name='Depósito General')
				.first()
			)
			if not warehouse:
				warehouse = Warehouse(name='Depósito General', branch_id=branch.id)
				session.add(warehouse)
				session.flush()

			return warehouse.id
		except Exception as e:
			logger.error(
				f'Error al obtener/crear almacén por defecto: {e}', exc_info=True
			)
			raise

	def get_suppliers_for_combo(self, tenant_id):
		with self.Session() as session:
			try:
				suppliers = (
					session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				)
				return [{'id': s.id, 'name': s.name} for s in suppliers]
			except Exception as e:
				logger.error(f'Error obteniendo proveedores: {e}', exc_info=True)
				return []

	def get_all_variants(self, tenant_id):
		with self.Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article).joinedload(Article.supplier),
						joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
					.order_by(Article.name)
					.all()
				)

				result = []
				for v in variants:
					total_stock = sum(s.quantity for s in v.stocks) if v.stocks else 0
					result.append(
						{
							'variant_id': v.id,
							'article_id': v.article_id,
							'name': v.article.name,
							'barcode': v.barcode,
							'cost_price': v.cost_price,
							'selling_price': v.selling_price,
							'total_stock': total_stock,
							'supplier_id': v.article.supplier_id,
							'supplier_name': v.article.supplier.name
							if v.article.supplier
							else 'Sin Proveedor',
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
	):
		if not name or not str(name).strip():
			return False, 'El nombre es obligatorio.'
		if not barcode or not str(barcode).strip():
			return False, 'El código de barras es obligatorio.'

		try:
			cost_price = Decimal(str(cost_price))
			selling_price = Decimal(str(selling_price))
			initial_stock = Decimal(str(initial_stock))
		except Exception:
			return False, 'Valores numéricos inválidos.'

		if (
			initial_stock < Decimal('0.0')
			or cost_price < Decimal('0.0')
			or selling_price < Decimal('0.0')
		):
			return False, 'Los precios y el stock no pueden ser negativos.'

		with self.Session() as session:
			try:
				existing = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.barcode == str(barcode).strip(),
						ArticleVariant.is_active,
					)
					.first()
				)

				if existing:
					return False, f'El código "{barcode}" ya está en uso.'

				warehouse_id = self._get_or_create_default_warehouse(session, tenant_id)

				new_article = Article(
					name=str(name).strip(),
					tenant_id=tenant_id,
					has_variants=False,
					supplier_id=supplier_id,  # Asociamos al proveedor
				)
				session.add(new_article)
				session.flush()

				new_variant = ArticleVariant(
					barcode=str(barcode).strip(),
					cost_price=cost_price,
					selling_price=selling_price,
					article_id=new_article.id,
				)
				session.add(new_variant)
				session.flush()

				new_stock = Stock(
					quantity=initial_stock,
					warehouse_id=warehouse_id,
					variant_id=new_variant.id,
				)
				session.add(new_stock)

				if initial_stock > 0:
					mov = StockMovement(
						movement_type='in',
						quantity=initial_stock,
						reference='Inventario Inicial',
						dest_warehouse_id=warehouse_id,
						variant_id=new_variant.id,
						user_id=user_id,
					)
					session.add(mov)

				session.commit()
				return True, f"Artículo '{name}' creado."
			except Exception as e:
				session.rollback()
				logger.error(f'Error al crear: {e}', exc_info=True)
				return False, 'Error interno al crear el artículo.'

	# --- NUEVO: Función para Editar un Artículo ---
	def update_article(
		self,
		tenant_id,
		variant_id,
		name,
		barcode,
		cost_price,
		selling_price,
		supplier_id=None,
	):
		"""Actualiza la información de un producto existente. (Nota: No actualiza stock directo por seguridad de auditoría)"""
		try:
			cost_price = Decimal(str(cost_price))
			selling_price = Decimal(str(selling_price))
		except Exception:
			return False, 'Valores numéricos inválidos.'

		with self.Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id, Article.tenant_id == tenant_id
					)
					.first()
				)

				if not variant:
					return False, 'Artículo no encontrado.'

				# Verificamos que no le asigne un código de barras que ya tiene OTRO producto
				if variant.barcode != str(barcode).strip():
					exist = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == str(barcode).strip(),
							ArticleVariant.is_active,
						)
						.first()
					)
					if exist:
						return (
							False,
							'Ese código de barras ya pertenece a otro producto.',
						)

				variant.barcode = str(barcode).strip()
				variant.cost_price = cost_price
				variant.selling_price = selling_price

				variant.article.name = str(name).strip()
				variant.article.supplier_id = supplier_id

				session.commit()
				return True, f"Artículo '{name}' actualizado correctamente."
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al actualizar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al actualizar.'

	def delete_variant(self, tenant_id, variant_id):
		with self.Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id, Article.tenant_id == tenant_id
					)
					.first()
				)

				if not variant:
					return False, 'Artículo no encontrado.'

				variant.is_active = False
				session.commit()
				return True, 'Artículo eliminado correctamente.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error eliminar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar eliminar.'
