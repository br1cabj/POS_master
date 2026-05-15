"""
controllers/dollar_price_controller.py
=======================================
Manejo de precios atados al dólar y actualización masiva.
"""

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import Article, ArticleHistory, ArticleVariant

logger = logging.getLogger(__name__)


class DollarPriceController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def fetch_current_dollar_rate(self, dollar_type: str = 'blue') -> float | None:
		"""Obtiene la cotización actual (venta) según el tipo seleccionado.
		Retorna None si la API no está disponible; el caller debe verificar antes de usar.
		"""
		_endpoints = {'blue': 'blue', 'oficial': 'oficial', 'mep': 'bolsa'}
		endpoint = _endpoints.get(dollar_type.lower(), 'blue')
		try:
			response = requests.get(
				f'https://dolarapi.com/v1/dolares/{endpoint}', timeout=5
			)
			response.raise_for_status()
			return float(response.json().get('venta', 0))
		except requests.RequestException as e:
			logger.error(f'Error de red al consultar API de dólar ({dollar_type}): {e}')
			return None

	def get_last_update_info(self, tenant_id: int) -> dict | None:
		"""Recupera la fecha y detalles de la última actualización de precios en dólares."""
		with self._Session() as session:
			last_record = (
				session.query(ArticleHistory)
				.filter(
					ArticleHistory.tenant_id == tenant_id,
					ArticleHistory.action_type == 'ACTUALIZACIÓN DÓLAR',
				)
				.order_by(ArticleHistory.id.desc())
				.first()
			)
			if not last_record:
				return None

			return {
				'date': getattr(last_record, 'date', datetime.now()),
				'details': 'Cotización y márgenes aplicados previamente',
			}

	def get_variants(self, tenant_id: int) -> list[dict]:
		"""Obtiene las variantes activas con sus respectivos precios en USD y márgenes."""
		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.options(joinedload(ArticleVariant.article))
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						ArticleVariant.is_active == True,
						ArticleVariant.is_combo == False,
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
						'cost_price_usd': float(v.cost_price_usd)
						if v.cost_price_usd is not None
						else None,
						'margin_pct': float(v.margin_pct)
						if getattr(v, 'margin_pct', None) is not None
						else None,
					}
					for v in variants
				]
			except Exception as e:
				logger.error(
					f'Error al obtener variantes para dólar: {e}', exc_info=True
				)
				return []

	def save_usd_prices_bulk(
		self,
		tenant_id: int,
		variant_ids: list[int],
		usd_price_str: str,
		margin_str: str = '',
	) -> tuple[bool, str]:
		"""Asigna masivamente el precio en dólares y margen individual a una lista de variantes."""
		if not variant_ids:
			return False, 'No hay productos seleccionados.'

		usd_str = str(usd_price_str).strip().replace(',', '.')
		margin_str = str(margin_str).strip().replace(',', '.')

		try:
			usd_val = (
				None
				if not usd_str or Decimal(usd_str) == Decimal('0')
				else Decimal(usd_str)
			)
			if usd_val is not None and usd_val < 0:
				return False, 'El precio USD no puede ser negativo.'
		except InvalidOperation:
			return False, 'Precio USD inválido.'

		margin_val = None
		update_margin = False
		if margin_str:
			try:
				margin_val = Decimal(margin_str)
				if margin_val < 0:
					return False, 'El margen no puede ser negativo.'
				update_margin = True
			except InvalidOperation:
				return False, 'Margen individual inválido.'

		with self._Session() as session:
			try:
				variants = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(
						ArticleVariant.id.in_(variant_ids),
						Article.tenant_id == tenant_id,
					)
					.all()
				)

				if not variants:
					return False, 'Productos no encontrados.'

				for variant in variants:
					variant.cost_price_usd = usd_val
					if update_margin and hasattr(variant, 'margin_pct'):
						variant.margin_pct = margin_val

				session.commit()
				action = (
					'quitado'
					if usd_val is None
					else f'asignado (US${float(usd_val):.2f})'
				)
				return True, f'Precio USD {action} a {len(variants)} producto(s).'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al guardar precios USD masivos: {e}', exc_info=True
				)
				return False, 'Error al procesar la solicitud.'

	def preview_recalculate_prices(
		self, tenant_id: int, rate: float, global_margin_pct: float
	) -> dict:
		"""Genera un reporte de impacto (preview) de la actualización de precios sin persistir en BD."""
		if rate <= 0:
			return {'error': 'Cotización inválida.'}

		rate_d = Decimal(str(rate))

		with self._Session() as session:
			variants = (
				session.query(ArticleVariant)
				.join(Article)
				.filter(
					Article.tenant_id == tenant_id,
					ArticleVariant.is_active == True,
					ArticleVariant.is_combo == False,
					ArticleVariant.cost_price_usd.isnot(None),
					ArticleVariant.cost_price_usd > 0,
				)
				.all()
			)

			if not variants:
				return {'error': 'No hay productos con precio USD.'}

			old_prices, new_prices = [], []

			for v in variants:
				v_margin = (
					float(v.margin_pct)
					if getattr(v, 'margin_pct', None) is not None
					else global_margin_pct
				)
				factor_d = Decimal('1') + Decimal(str(v_margin)) / Decimal('100')
				new_price = (v.cost_price_usd * rate_d * factor_d).quantize(
					Decimal('0.01'), rounding=ROUND_HALF_UP
				)

				old_prices.append(float(v.selling_price))
				new_prices.append(float(new_price))

			total_old, total_new = sum(old_prices), sum(new_prices)
			avg_increase_pct = (
				((total_new - total_old) / total_old * 100) if total_old > 0 else 0
			)

			return {
				'affected_count': len(variants),
				'avg_increase_pct': round(avg_increase_pct, 2),
				'min_ars': round(min(new_prices), 2),
				'max_ars': round(max(new_prices), 2),
			}

	def recalculate_prices(
		self,
		tenant_id: int,
		user_id: int,
		rate: float,
		global_margin_pct: float,
	) -> tuple[bool, str]:
		"""Ejecuta la actualización de precios en ARS basándose en la cotización USD y márgenes."""
		if rate <= 0:
			return False, 'La cotización debe ser mayor a cero.'
		if global_margin_pct < 0:
			return False, 'El margen no puede ser negativo.'

		try:
			rate_d = Decimal(str(rate))
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
						ArticleVariant.is_active == True,
						ArticleVariant.is_combo == False,
						ArticleVariant.cost_price_usd.isnot(None),
						ArticleVariant.cost_price_usd > 0,
					)
					.all()
				)

				if not variants:
					return False, 'Ningún producto tiene precio en USD asignado.'

				updated = 0
				for v in variants:
					old_cost, old_price = v.cost_price, v.selling_price
					v_margin = (
						float(v.margin_pct)
						if getattr(v, 'margin_pct', None) is not None
						else global_margin_pct
					)
					factor_d = Decimal('1') + Decimal(str(v_margin)) / Decimal('100')

					new_cost = (v.cost_price_usd * rate_d).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)
					new_price = (v.cost_price_usd * rate_d * factor_d).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)

					if v.selling_price_b is not None and old_price and old_price > 0:
						scale = new_price / old_price
						v.selling_price_b = (v.selling_price_b * scale).quantize(
							Decimal('0.01'), rounding=ROUND_HALF_UP
						)

					v.cost_price, v.selling_price = new_cost, new_price

					child_packs = (
						session.query(ArticleVariant)
						.filter(
							ArticleVariant.base_variant_id == v.id,
							ArticleVariant.is_active == True,
						)
						.all()
					)

					for child in child_packs:
						units = Decimal(str(child.units_per_pack or 1))
						child_new_price = (new_price * units).quantize(
							Decimal('0.01'), rounding=ROUND_HALF_UP
						)
						child_old_price = child.selling_price
						child.cost_price = new_cost * units
						child.selling_price = child_new_price
						if (
							child.selling_price_b is not None
							and child_old_price
							and child_old_price > 0
						):
							child_scale = child_new_price / Decimal(str(child_old_price))
							child.selling_price_b = (
								child.selling_price_b * child_scale
							).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

					if new_price != old_price:
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
				return (
					True,
					f'✅ {updated} producto(s) actualizado(s).\nCotización: ${rate:,.2f}',
				)
			except Exception as e:
				session.rollback()
				logger.error(f'Error en recalculate_prices: {e}', exc_info=True)
				return False, 'Error interno al actualizar los precios.'
