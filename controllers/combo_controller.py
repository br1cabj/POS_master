import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import sessionmaker

from database.models import Article, ArticleVariant, Branch, ComboItem, Warehouse
from utils.config import make_engine
from utils.shared import get_or_create_default_warehouse

_default_engine = make_engine()

logger = logging.getLogger(__name__)


class ComboController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def create_combo(self, tenant_id, name, price, btn_color, ingredients_list):
		"""
		Crea una promoción con su artículo contenedor, variante y receta de ingredientes.
		ingredients_list: [{'variant_id': int, 'qty': float}, ...]
		"""
		if not name or not str(name).strip():
			return False, 'El nombre del combo es obligatorio.'
		if not ingredients_list:
			return False, 'El combo debe tener al menos un ingrediente.'

		try:
			price = Decimal(str(price))
		except (ValueError, InvalidOperation):
			return False, 'Precio inválido.'

		if price < Decimal('0.0'):
			return False, 'El precio no puede ser negativo.'

		with self.SessionLocal() as session:
			try:
				article = Article(
					name=str(name).strip(), tenant_id=tenant_id, has_variants=False
				)
				session.add(article)
				session.flush()

				# Calcular el costo real del combo sumando ingredientes antes de crear la variante
				combo_cost = Decimal('0.0')
				validated_items = []
				for item in ingredients_list:
					try:
						qty = Decimal(str(item['qty']))
					except (ValueError, InvalidOperation, KeyError):
						session.rollback()
						return False, 'Cantidad de ingrediente inválida.'

					if qty <= 0:
						session.rollback()
						return (
							False,
							'La cantidad de cada ingrediente debe ser mayor a cero.',
						)

					ing_variant = session.get(ArticleVariant, item['variant_id'])
					if ing_variant:
						combo_cost += ing_variant.cost_price * qty
					validated_items.append((item['variant_id'], qty))

				combo_variant = ArticleVariant(
					article_id=article.id,
					barcode=None,
					cost_price=combo_cost,
					selling_price=price,
					is_combo=True,
					show_on_touch=True,
					btn_color=btn_color,
				)
				session.add(combo_variant)
				session.flush()

				for variant_id, qty in validated_items:
					session.add(
						ComboItem(
							combo_id=combo_variant.id,
							ingredient_id=variant_id,
							quantity_required=qty,
						)
					)

				session.commit()
				return True, f"Promo '{name}' creada y lista en la botonera."
			except Exception as e:
				session.rollback()
				logger.error(f'Error creando combo: {e}', exc_info=True)
				return False, 'Error interno al guardar la Promo.'

	def toggle_touch_status(self, tenant_id, variant_id, show_on_touch, btn_color):
		"""Activa o desactiva la visibilidad de un producto en la botonera táctil."""
		with self.SessionLocal() as session:
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
				logger.error(f'Error actualizando botonera: {e}', exc_info=True)
				return False, 'Error al actualizar la configuración.'
