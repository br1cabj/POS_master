"""
controllers/dollar_price_controller.py
=======================================
Manejo de precios atados al dólar.

Flujo de uso:
  1. El usuario asigna un precio en USD (cost_price_usd) a cada producto.
  2. Cuando la cotización cambia, llama a recalculate_prices(rate, margin_pct).
  3. El sistema actualiza cost_price  = usd * rate
                          selling_price = usd * rate * (1 + margin_pct/100)
     y registra el cambio en ArticleHistory con action_type = 'ACTUALIZACIÓN DÓLAR'.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import Article, ArticleHistory, ArticleVariant
from utils.config import make_engine

logger = logging.getLogger(__name__)

_default_engine = make_engine()


class DollarPriceController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		super().__init__(engine)

	# ──────────────────────────────────────────────
	# LECTURA
	# ──────────────────────────────────────────────
	def get_variants(self, tenant_id: int) -> list[dict]:
		"""
		Retorna todas las variantes activas con su precio en USD (puede ser None).
		Ordena: primero las que tienen USD asignado, luego el resto.
		"""
		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.is_active == True,  # noqa: E712
						ArticleVariant.is_combo == False,  # noqa: E712
					)
					.order_by(Article.name)
					.all()
				)
				return [
					{
						'variant_id': v.id,
						'name': v.article.name,
						'barcode': v.barcode or '',
						'cost_price': float(v.cost_price),
						'selling_price': float(v.selling_price),
						'cost_price_usd': (
							float(v.cost_price_usd)
							if v.cost_price_usd is not None
							else None
						),
					}
					for v in variants
				]
			except Exception as e:
				logger.error(
					f'Error al obtener variantes para dólar: {e}', exc_info=True
				)
				return []

	# ──────────────────────────────────────────────
	# ASIGNAR PRECIO USD A UN PRODUCTO
	# ──────────────────────────────────────────────
	def save_usd_price(
		self, tenant_id: int, variant_id: int, usd_price_str: str
	) -> tuple[bool, str]:
		"""
		Guarda el precio en dólares de una variante.
		Pasar usd_price_str = '' o '0' para quitar el precio USD.
		"""
		usd_str = str(usd_price_str).strip().replace(',', '.')
		if not usd_str:
			usd_val = None
		else:
			try:
				usd_val = Decimal(usd_str)
			except InvalidOperation:
				return False, 'Ingresá un número válido (ej: 2.50).'
			if usd_val < 0:
				return False, 'El precio en USD no puede ser negativo.'
			if usd_val == Decimal('0'):
				usd_val = None

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
					return False, 'Producto no encontrado.'

				variant.cost_price_usd = usd_val
				session.commit()

				name = variant.article.name
				if usd_val is None:
					return True, f'Precio USD quitado de "{name}".'
				return True, f'Precio USD de "{name}" guardado: US${float(usd_val):.2f}'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al guardar precio USD: {e}', exc_info=True)
				return False, 'Error al guardar el precio.'

	# ──────────────────────────────────────────────
	# RECALCULAR TODOS LOS PRECIOS — EL UN CLICK
	# ──────────────────────────────────────────────
	def recalculate_prices(
		self,
		tenant_id: int,
		user_id: int,
		rate: float,
		margin_pct: float,
	) -> tuple[bool, str]:
		"""
		Actualiza cost_price y selling_price de todas las variantes que
		tienen cost_price_usd asignado.

		Fórmula:
		    cost_price    = cost_price_usd × rate
		    selling_price = cost_price_usd × rate × (1 + margin_pct / 100)

		Registra cada cambio en ArticleHistory con action_type = 'ACTUALIZACIÓN DÓLAR'.
		"""
		if rate <= 0:
			return False, 'La cotización debe ser mayor a cero.'
		if margin_pct < 0:
			return False, 'El margen no puede ser negativo.'

		try:
			rate_d = Decimal(str(rate))
			# Evitar división float antes de Decimal: mantiene precisión total
			factor_d = Decimal('1') + Decimal(str(margin_pct)) / Decimal('100')
		except InvalidOperation:
			return False, 'Valores inválidos.'

		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.is_active == True,  # noqa: E712
						ArticleVariant.is_combo == False,  # noqa: E712
						ArticleVariant.cost_price_usd.isnot(None),
						ArticleVariant.cost_price_usd > 0,
					)
					.all()
				)

				if not variants:
					return (
						False,
						'Ningún producto tiene precio en USD asignado.\nAsigná precios USD primero.',
					)

				updated = 0
				for v in variants:
					old_cost = v.cost_price
					old_price = v.selling_price

					new_cost = (v.cost_price_usd * rate_d).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)
					new_price = (v.cost_price_usd * rate_d * factor_d).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)

					v.cost_price = new_cost
					v.selling_price = new_price

					# Cascade cost to packaging child variants
					child_packs = (
						session.query(ArticleVariant)
						.filter(
							ArticleVariant.base_variant_id == v.id,
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.all()
					)
					for child in child_packs:
						child.cost_price = new_cost * (child.units_per_pack or 1)

					session.add(
						ArticleHistory(
							tenant_id=tenant_id,
							user_id=user_id,
							action_type='ACTUALIZACIÓN DÓLAR',
							article_name=v.article.name,
							variant_id=v.id,
							old_cost=old_cost,
							new_cost=new_cost,
							old_price=old_price,
							new_price=new_price,
						)
					)
					updated += 1

				session.commit()
				return True, (
					f'✅ {updated} producto{"s" if updated != 1 else ""} actualizado{"s" if updated != 1 else ""}.\n'
					f'Cotización: ${rate:,.2f}  ·  Margen: {margin_pct:.1f}%'
				)
			except Exception as e:
				session.rollback()
				logger.error(f'Error en recalculate_prices: {e}', exc_info=True)
				return False, 'Error interno al actualizar los precios.'
