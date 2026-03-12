import logging

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
		Función auxiliar: Si el usuario aún no ha configurado sucursales,
		le creamos una por defecto para no bloquear la creación de artículos.
		NOTA: Idealmente, esto debería ocurrir al crear el Tenant, no aquí.
		"""
		try:
			# 1. Buscamos o creamos la Sucursal
			branch = (
				session.query(Branch)
				.filter_by(tenant_id=tenant_id, name='Sede Principal')
				.first()
			)
			if not branch:
				branch = Branch(name='Sede Principal', tenant_id=tenant_id)
				session.add(branch)
				session.flush()

			# 2. Buscamos o creamos el Almacén dentro de esa sucursal
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
			raise  # Relanzamos porque si esto falla, no podemos crear el artículo

	def get_all_variants(self, tenant_id):
		"""
		Trae todas las variantes activas unidas a su artículo padre.
		Devuelve una lista de diccionarios para evitar DetachedInstanceError en la UI.
		"""
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

				# Convertimos a diccionarios planos para la interfaz gráfica
				result = []
				for v in variants:
					# Calculamos el stock total aquí mismo para facilidad de la UI
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
		"""
		Crea un artículo simple y registra automáticamente su entrada en el Kardex.
		"""
		# Validaciones básicas antes de tocar la base de datos
		if not name or not barcode:
			return False, 'El nombre y el código de barras son obligatorios.'
		if initial_stock < 0:
			return False, 'El stock inicial no puede ser negativo.'

		with self.Session() as session:
			try:
				warehouse_id = self._get_or_create_default_warehouse(session, tenant_id)

				new_article = Article(
					name=name,
					tenant_id=tenant_id,
					has_variants=False,
				)
				session.add(new_article)
				session.flush()

				new_variant = ArticleVariant(
					barcode=barcode,
					cost_price=cost_price,
					selling_price=selling_price,
					article_id=new_article.id,
				)
				session.add(new_variant)
				session.flush()

				# Solo creamos el registro en Stock si hay cantidad,
				# o lo creamos en 0 para tener la referencia (depende de tu lógica de negocio)
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

			except Exception as e:
				session.rollback()
				logger.error(f"Error al crear artículo '{name}': {e}", exc_info=True)
				return False, 'Error interno al crear el artículo. Revise los logs.'

	def delete_variant(self, variant_id):
		"""Realiza un borrado lógico de la variante."""
		with self.Session() as session:
			try:
				variant = session.query(ArticleVariant).filter_by(id=variant_id).first()
				if not variant:
					return False, 'Variante no encontrada.'

				variant.is_active = False
				session.commit()
				return True, 'Artículo eliminado (Borrado lógico).'

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al eliminar variante {variant_id}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar eliminar. Revise los logs.'
