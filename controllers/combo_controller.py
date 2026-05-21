"""
controllers/combo_controller.py
===============================
Controlador de dominio para la estructuración de productos compuestos (Combos)
y gestión de la capa visual de atajos en el Punto de Venta (Touch POS).
"""

import logging
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from controllers.base import BaseController
from database.models import Article, ArticleVariant, ComboItem

logger = logging.getLogger(__name__)


class ComboController(BaseController):
	"""
	Controlador responsable de la integridad referencial y proyección de costos
	en la creación de promociones y botones rápidos.
	"""

	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def create_combo(self, tenant_id, name, price, btn_color, ingredients_list):
		"""
		Ensambla un artículo de tipo promoción.
		Aplica consolidación de duplicados, validación de aislamiento tenant,
		y previene topologías circulares (anidamiento de combos).
		"""
		if not name or not str(name).strip():
			return False, 'El nombre de la promoción es obligatorio.'
		if not ingredients_list:
			return False, 'La promoción debe contener al menos un ingrediente válido.'

		try:
			price = Decimal(str(price))
		except (ValueError, InvalidOperation):
			return False, 'El formato numérico del precio es inválido.'

		if price < Decimal('0.0'):
			return False, 'El precio de venta no puede poseer valor negativo.'
		if price == Decimal('0.0'):
			logger.warning('Combo creado con precio $0. Verificar si es intencional.')

		# Consolidación O(N) para unificar ingredientes repetidos enviados por la capa vista
		aggregated_ingredients = defaultdict(Decimal)
		for item in ingredients_list:
			try:
				qty = Decimal(str(item.get('qty', 0)))
				if qty <= 0:
					return (
						False,
						'Las proporciones en la receta deben ser mayores a cero.',
					)
				aggregated_ingredients[item['variant_id']] += qty
			except (ValueError, InvalidOperation, KeyError):
				return False, 'Estructura de payload de ingrediente inválida.'

		with self._Session() as session:
			try:
				combo_cost = Decimal('0.0')
				validated_items = []

				# Validación de ingredientes contra la Base de Datos
				for variant_id, qty in aggregated_ingredients.items():
					ing_variant = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							ArticleVariant.id == variant_id,
							Article.tenant_id == tenant_id,
						)
						.first()
					)

					if not ing_variant:
						return (
							False,
							f'Inconsistencia: El artículo (ID: {variant_id}) no pertenece a su base de datos.',
						)

					if getattr(ing_variant, 'is_combo', False):
						return (
							False,
							'Restricción arquitectónica: No se permite anidar combos.',
						)

					combo_cost += ing_variant.cost_price * qty
					validated_items.append((variant_id, qty))

				# Persistencia del Contenedor Base
				article = Article(
					name=str(name).strip(), tenant_id=tenant_id, has_variants=False
				)
				session.add(article)
				session.flush()

				# Persistencia de la Variante de tipo Venta
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

				# Vinculación Relacional de la Receta
				for variant_id, qty in validated_items:
					session.add(
						ComboItem(
							combo_id=combo_variant.id,
							ingredient_id=variant_id,
							quantity_required=qty,
						)
					)

				session.commit()
				return (
					True,
					f"Promoción '{name}' generada y habilitada en el panel POS.",
				)
			except Exception as e:
				session.rollback()
				logger.error(f'Error en persistencia de combo: {e}', exc_info=True)
				return (
					False,
					'Excepción interna al almacenar la estructura de la promoción.',
				)

	def get_combo_ingredients(self, tenant_id, combo_variant_id):
		"""Retorna la receta de un combo como lista de {variant_id, quantity}."""
		with self._Session() as session:
			try:
				items = (
					session.query(ComboItem)
					.join(ArticleVariant, ComboItem.combo_id == ArticleVariant.id)
					.join(Article, ArticleVariant.article_id == Article.id)
					.filter(
						ComboItem.combo_id == combo_variant_id,
						Article.tenant_id == tenant_id,
					)
					.all()
				)
				return [
					{
						'variant_id': item.ingredient_id,
						'quantity': item.quantity_required,
					}
					for item in items
				]
			except Exception as e:
				logger.error(
					f'Error cargando ingredientes del combo {combo_variant_id}: {e}',
					exc_info=True,
				)
				return []

	def update_combo(self, tenant_id, combo_variant_id, name, price, btn_color, ingredients_list):
		"""Actualiza nombre, precio, color y receta de un combo existente."""
		if not name or not str(name).strip():
			return False, 'El nombre de la promoción es obligatorio.'
		if not ingredients_list:
			return False, 'La promoción debe contener al menos un ingrediente válido.'

		try:
			price = Decimal(str(price))
		except (ValueError, InvalidOperation):
			return False, 'El formato numérico del precio es inválido.'

		if price < Decimal('0.0'):
			return False, 'El precio de venta no puede poseer valor negativo.'

		aggregated_ingredients = defaultdict(Decimal)
		for item in ingredients_list:
			try:
				qty = Decimal(str(item.get('qty', 0)))
				if qty <= 0:
					return False, 'Las proporciones en la receta deben ser mayores a cero.'
				aggregated_ingredients[item['variant_id']] += qty
			except (ValueError, InvalidOperation, KeyError):
				return False, 'Estructura de payload de ingrediente inválida.'

		with self._Session() as session:
			try:
				combo_variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id == combo_variant_id,
						Article.tenant_id == tenant_id,
						ArticleVariant.is_combo == True,  # noqa: E712
					)
					.first()
				)
				if not combo_variant:
					return False, 'Combo no encontrado o sin permisos.'

				combo_cost = Decimal('0.0')
				validated_items = []
				for variant_id, qty in aggregated_ingredients.items():
					ing_variant = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							ArticleVariant.id == variant_id,
							Article.tenant_id == tenant_id,
						)
						.first()
					)
					if not ing_variant:
						return False, f'Ingrediente (ID: {variant_id}) no encontrado.'
					if getattr(ing_variant, 'is_combo', False):
						return False, 'No se permite anidar combos.'
					combo_cost += ing_variant.cost_price * qty
					validated_items.append((variant_id, qty))

				combo_variant.article.name = str(name).strip()
				combo_variant.cost_price = combo_cost
				combo_variant.selling_price = price
				combo_variant.btn_color = btn_color

				session.query(ComboItem).filter_by(combo_id=combo_variant_id).delete()
				for variant_id, qty in validated_items:
					session.add(
						ComboItem(
							combo_id=combo_variant_id,
							ingredient_id=variant_id,
							quantity_required=qty,
						)
					)

				session.commit()
				return True, f"Promoción '{name}' actualizada correctamente."
			except Exception as e:
				session.rollback()
				logger.error(f'Error actualizando combo: {e}', exc_info=True)
				return False, 'Error interno al actualizar la promoción.'

	def toggle_touch_status(self, tenant_id, variant_id, show_on_touch, btn_color):
		"""
		Modifica los metadatos de renderizado POS para artículos individuales.
		"""
		with self._Session() as session:
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
					return (
						False,
						'Producto inhallable o violación de aislamiento de tenant.',
					)

				variant.show_on_touch = show_on_touch
				variant.btn_color = btn_color
				session.commit()

				estado = 'asignado al' if show_on_touch else 'retirado del'
				return True, f'Atajo {estado} panel de acceso rápido exitosamente.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error mutando estado touch: {e}', exc_info=True)
				return (
					False,
					'Fallo de concurrencia al actualizar preferencias visuales.',
				)
