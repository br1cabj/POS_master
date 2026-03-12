import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	Stock,
	StockMovement,
	Warehouse,
)

logger = logging.getLogger(__name__)


class ArticleController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
		"""
		Función auxiliar: Busca o crea almacén por defecto.
		"""
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

	def get_all_variants(self, tenant_id):
		with self.Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(
						joinedload(ArticleVariant.article),
						joinedload(ArticleVariant.stocks),
					)
					.join(Article)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
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
						}
					)
				return result

			except Exception as e:
				logger.error(
					f'Error al obtener variantes para tenant {tenant_id}: {e}',
					exc_info=True,
				)
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
	):
		"""Crea un artículo simple y registra automáticamente su entrada."""
		# 1. 🛡️ ESCUDO: Validaciones estrictas de entrada
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

		if initial_stock < 0:
			return False, 'El stock inicial no puede ser negativo.'
		if cost_price < 0 or selling_price < 0:
			return False, 'Los precios no pueden ser negativos.'

		with self.Session() as session:
			try:
				existing_variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.barcode == str(barcode).strip(),
						ArticleVariant.is_active,
					)
					.first()
				)
				if existing_variant:
					return (
						False,
						f'El código de barras "{barcode}" ya está en uso por otro artículo.',
					)

				warehouse_id = self._get_or_create_default_warehouse(session, tenant_id)

				new_article = Article(
					name=str(name).strip(),
					tenant_id=tenant_id,
					has_variants=False,
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
					movimiento_entrada = StockMovement(
						movement_type='in',
						quantity=initial_stock,
						reference='Inventario Inicial',
						dest_warehouse_id=warehouse_id,
						variant_id=new_variant.id,
						user_id=user_id,
					)
					session.add(movimiento_entrada)

				session.commit()
				return True, f"Artículo '{name}' creado correctamente."

			except IntegrityError:
				session.rollback()
				logger.error(
					'Error de integridad de BD al crear artículo.', exc_info=True
				)
				return (
					False,
					'Error: Ya existe un registro conflictivo en la base de datos.',
				)
			except Exception as e:
				session.rollback()
				logger.error(f"Error al crear artículo '{name}': {e}", exc_info=True)
				return False, 'Error interno al crear el artículo. Intente de nuevo.'

	def delete_variant(self, tenant_id, variant_id):
		"""Realiza un borrado lógico de la variante."""
		with self.Session() as session:
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
					return (
						False,
						'Artículo no encontrado o no tienes permiso para eliminarlo.',
					)

				variant.is_active = False
				session.commit()
				return True, 'Artículo eliminado correctamente.'

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al eliminar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar eliminar. Intente de nuevo.'
