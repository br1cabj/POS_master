import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import sessionmaker

from database.models import Article, ArticleVariant, Branch, ComboItem, Warehouse

logger = logging.getLogger(__name__)


class ComboController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _get_or_create_default_warehouse(self, session, tenant_id):
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

	def create_combo(self, tenant_id, name, price, btn_color, ingredients_list):
		"""
		Crea un Combo.
		ingredients_list = [{'variant_id': 1, 'qty': 2}, ...]
		"""
		if not name or not ingredients_list:
			return False, 'El combo debe tener un nombre y al menos un ingrediente.'

		try:
			price = Decimal(str(price))
		except (ValueError, InvalidOperation):
			return False, 'Precio inválido.'

		with self.Session() as session:
			try:
				# 1. Creamos el Artículo "Contenedor"
				new_article = Article(
					name=str(name).strip(), tenant_id=tenant_id, has_variants=False
				)
				session.add(new_article)
				session.flush()

				# 2. Creamos la Variante que representa al Combo (Sin código de barras)
				new_combo_variant = ArticleVariant(
					article_id=new_article.id,
					barcode=None,
					cost_price=Decimal('0.0'),  # El costo se calcula dinámicamente
					selling_price=price,
					is_combo=True,  # 🛡️ Marcamos como Combo
					show_on_touch=True,  # 🛡️ Lo mostramos en la botonera
					btn_color=btn_color,
				)
				session.add(new_combo_variant)
				session.flush()

				# 3. Guardamos los ingredientes (La Receta)
				for item in ingredients_list:
					combo_item = ComboItem(
						combo_id=new_combo_variant.id,
						ingredient_id=item['variant_id'],
						quantity_required=Decimal(str(item['qty'])),
					)
					session.add(combo_item)

				session.commit()
				return True, f"Promo '{name}' creada y lista en la botonera."
			except Exception as e:
				session.rollback()
				logger.error(f'Error creando combo: {e}', exc_info=True)
				return False, 'Error interno al guardar la Promo.'

	def toggle_touch_status(self, tenant_id, variant_id, show_on_touch, btn_color):
		"""Activa o desactiva un producto normal para que aparezca en la botonera"""
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
					return False, 'Producto no encontrado.'

				variant.show_on_touch = show_on_touch
				variant.btn_color = btn_color
				session.commit()

				estado = 'agregado a' if show_on_touch else 'quitado de'
				return True, f'Producto {estado} la botonera rápida.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error actualizando touch: {e}', exc_info=True)
				return False, 'Error al actualizar la configuración.'
