from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	Stock,
	StockMovement,
	Warehouse,
)


class ArticleController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
		"""
		Función auxiliar: Si el usuario aún no ha configurado sucursales,
		le creamos una por defecto para no bloquear la creación de artículos.
		"""
		# 1. Buscamos o creamos la Sucursal
		branch = (
			session.query(Branch)
			.filter_by(tenant_id=tenant_id, name='Sede Principal')
			.first()
		)
		if not branch:
			branch = Branch(name='Sede Principal', tenant_id=tenant_id)
			session.add(branch)
			session.flush()  # Guardamos temporalmente para obtener el ID

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

	def get_all_variants(self, tenant_id):
		"""
		En el nuevo sistema, vendemos 'Variantes', no 'Artículos' genéricos.
		Esta función trae todas las variantes activas unidas a su artículo padre.
		"""
		session = self.Session()
		try:
			return (
				session.query(ArticleVariant)
				.options(
					joinedload(ArticleVariant.article),
					joinedload(ArticleVariant.stocks),
				)
				.join(Article)
				.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
				.all()
			)
		finally:
			session.close()

	# --- NUEVO: Agregamos user_id como parámetro ---
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
		session = self.Session()
		try:
			# 1. Aseguramos que exista un lugar físico donde guardar el stock
			warehouse_id = self._get_or_create_default_warehouse(session, tenant_id)

			# 2. Creamos la "Idea" del producto (El Artículo Padre)
			new_article = Article(
				name=name,
				tenant_id=tenant_id,
				has_variants=False,  # Falso porque es un artículo simple
			)
			session.add(new_article)
			session.flush()

			# 3. Creamos el "Producto Físico" (La Variante Única)
			new_variant = ArticleVariant(
				barcode=barcode,
				cost_price=cost_price,
				selling_price=selling_price,
				article_id=new_article.id,
			)
			session.add(new_variant)
			session.flush()

			# 4. Registramos la cantidad en el Almacén correspondiente
			new_stock = Stock(
				quantity=initial_stock,
				warehouse_id=warehouse_id,
				variant_id=new_variant.id,
			)
			session.add(new_stock)

			# --- NUEVO: REGISTRO HISTÓRICO DE ENTRADA (KARDEX) ---
			# Solo registramos el movimiento si se ingresó un stock mayor a cero
			if initial_stock > 0:
				movimiento_entrada = StockMovement(
					movement_type='in',
					quantity=initial_stock,
					reference='Inventario Inicial',
					dest_warehouse_id=warehouse_id,
					variant_id=new_variant.id,
					user_id=user_id,  # Guardamos quién creó el producto
				)
				session.add(movimiento_entrada)
			# -----------------------------------------------------

			# Guardamos todos los cambios juntos
			session.commit()
			return True, f"Artículo '{name}' creado correctamente en inventario."

		except Exception as e:
			session.rollback()  # Si algo falla, deshacemos todo para no dejar datos a medias
			return False, f'Error al crear artículo: {e}'
		finally:
			session.close()

	def delete_variant(self, variant_id):
		"""Realiza un borrado lógico de la variante para no romper el historial de ventas"""
		session = self.Session()
		try:
			variant = session.query(ArticleVariant).filter_by(id=variant_id).first()
			if not variant:
				return False, 'Variante no encontrada.'

			variant.is_active = False
			session.commit()
			return True, 'Artículo eliminado (Borrado lógico).'
		except Exception as e:
			session.rollback()
			return False, f'Error al eliminar: {e}'
		finally:
			session.close()
