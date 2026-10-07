"""
controllers/promo_controller.py
================================
Controlador para el sistema de Promociones con Vigencia.
Soporta tres tipos: % descuento, N×M (lleva N paga M) y precio fijo.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_

from controllers.base import BaseController
from database.models import Article, ArticleVariant, Promotion

logger = logging.getLogger(__name__)


class PromoController(BaseController):
	def _promo_to_dict(self, promo, variant_name=None):
		return {
			'id': promo.id,
			'name': promo.name,
			'is_active': promo.is_active,
			'promo_type': promo.promo_type,
			'discount_value': float(promo.discount_value)
			if promo.discount_value is not None
			else None,
			'buy_qty': promo.buy_qty,
			'pay_qty': promo.pay_qty,
			'variant_id': promo.variant_id,
			'category_id': promo.category_id,
			'variant_name': variant_name,
			'date_from': promo.date_from,
			'date_to': promo.date_to,
			'days_of_week': promo.days_of_week,
			'time_from': promo.time_from,
			'time_to': promo.time_to,
			'updated_at': promo.updated_at,
		}

	def _is_active_now(self, promo_dict) -> bool:
		"""Verifica si una promo aplica en este instante exacto."""
		if not promo_dict.get('is_active'):
			return False
		now = datetime.now()
		date_from = promo_dict.get('date_from')
		date_to = promo_dict.get('date_to')
		if date_from and now < date_from:
			return False
		if date_to and now > date_to:
			return False
		days_str = promo_dict.get('days_of_week')
		if days_str:
			try:
				allowed = {int(d) for d in days_str.split(',') if d.strip()}
				if now.weekday() not in allowed:
					return False
			except ValueError:
				pass
		time_from = promo_dict.get('time_from')
		time_to = promo_dict.get('time_to')
		if time_from and time_to:
			try:
				tf = datetime.strptime(time_from, '%H:%M').time()
				tt = datetime.strptime(time_to, '%H:%M').time()
				now_time = now.time().replace(second=0, microsecond=0)
				if not (tf <= now_time <= tt):
					return False
			except ValueError:
				pass
		return True

	def _status_label(self, promo_dict) -> str:
		"""
		Devuelve 'activa', 'pausada', 'vencida' o 'programada'.
		Considera fecha, día de semana y horario para reflejar el estado real ahora.
		"""
		if not promo_dict.get('is_active'):
			return 'pausada'
		now = datetime.now()
		date_to = promo_dict.get('date_to')
		if date_to and now > date_to:
			return 'vencida'
		date_from = promo_dict.get('date_from')
		if date_from and now < date_from:
			return 'programada'
		# Dentro del rango de fechas — verificar día y horario
		days_str = promo_dict.get('days_of_week')
		if days_str:
			try:
				allowed = {int(d) for d in days_str.split(',') if d.strip()}
				if now.weekday() not in allowed:
					return 'fuera-horario'
			except ValueError:
				pass
		time_from = promo_dict.get('time_from')
		time_to = promo_dict.get('time_to')
		if time_from and time_to:
			try:
				tf = datetime.strptime(time_from, '%H:%M').time()
				tt = datetime.strptime(time_to, '%H:%M').time()
				now_time = now.time().replace(second=0, microsecond=0)
				if not (tf <= now_time <= tt):
					return 'fuera-horario'
			except ValueError:
				pass
		return 'activa'

	def _build_variant_name_map(self, session, variant_ids: list) -> dict:
		"""Retorna {variant_id: article_name} en una sola query."""
		if not variant_ids:
			return {}
		rows = (
			session.query(ArticleVariant.id, Article.name)
			.join(Article)
			.filter(ArticleVariant.id.in_(variant_ids))
			.all()
		)
		return {vid: name for vid, name in rows}

	def get_all_promos(self, tenant_id) -> list:
		with self._Session() as session:
			try:
				promos = (
					session.query(Promotion)
					.filter_by(tenant_id=tenant_id)
					.order_by(Promotion.date_from.desc())
					.all()
				)
				variant_ids = [p.variant_id for p in promos if p.variant_id]
				name_map = self._build_variant_name_map(session, variant_ids)
				result = []
				for p in promos:
					d = self._promo_to_dict(p, name_map.get(p.variant_id))
					d['status'] = self._status_label(d)
					result.append(d)
				return result
			except Exception as e:
				logger.error('get_all_promos: %s', e, exc_info=True)
				return []

	def get_active_promos_now(self, tenant_id) -> list:
		"""Retorna solo las promos válidas en este momento (para aplicar en ventas)."""
		with self._Session() as session:
			try:
				now = datetime.now()
				promos = (
					session.query(Promotion)
					.filter(
						Promotion.tenant_id == tenant_id,
						Promotion.is_active == True,  # noqa: E712
						or_(Promotion.date_from.is_(None), Promotion.date_from <= now),
						or_(Promotion.date_to.is_(None), Promotion.date_to >= now),
					)
					.all()
				)
				variant_ids = [p.variant_id for p in promos if p.variant_id]
				name_map = self._build_variant_name_map(session, variant_ids)
				result = []
				for p in promos:
					d = self._promo_to_dict(p, name_map.get(p.variant_id))
					if self._is_active_now(d):
						result.append(d)
				return result
			except Exception as e:
				logger.error('get_active_promos_now: %s', e, exc_info=True)
				return []

	def create_promo(self, tenant_id, data: dict):
		try:
			validated, err = self._validate_data(data)
			if err:
				return False, err
		except Exception as e:
			return False, str(e)

		with self._Session() as session:
			try:
				promo = Promotion(tenant_id=tenant_id, **validated)
				session.add(promo)
				session.commit()
				return True, f"Promoción '{data['name']}' creada correctamente."
			except Exception as e:
				session.rollback()
				logger.error('create_promo: %s', e, exc_info=True)
				return False, 'Error interno al guardar la promoción.'

	def update_promo(self, tenant_id, promo_id, data: dict):
		try:
			validated, err = self._validate_data(data)
			if err:
				return False, err
		except Exception as e:
			return False, str(e)

		with self._Session() as session:
			try:
				promo = (
					session.query(Promotion)
					.filter_by(id=promo_id, tenant_id=tenant_id)
					.first()
				)
				if not promo:
					return False, 'Promoción no encontrada.'
				for key, val in validated.items():
					setattr(promo, key, val)
				promo.updated_at = datetime.now()
				session.commit()
				return True, f"Promoción '{data['name']}' actualizada."
			except Exception as e:
				session.rollback()
				logger.error('update_promo: %s', e, exc_info=True)
				return False, 'Error interno al actualizar la promoción.'

	def delete_promo(self, tenant_id, promo_id):
		with self._Session() as session:
			try:
				promo = (
					session.query(Promotion)
					.filter_by(id=promo_id, tenant_id=tenant_id)
					.first()
				)
				if not promo:
					return False, 'Promoción no encontrada.'
				session.delete(promo)
				session.commit()
				return True, 'Promoción eliminada.'
			except Exception as e:
				session.rollback()
				logger.error('delete_promo: %s', e, exc_info=True)
				return False, 'Error interno al eliminar la promoción.'

	def toggle_active(self, tenant_id, promo_id):
		with self._Session() as session:
			try:
				promo = (
					session.query(Promotion)
					.filter_by(id=promo_id, tenant_id=tenant_id)
					.first()
				)
				if not promo:
					return False, 'Promoción no encontrada.'
				promo.is_active = not promo.is_active
				promo.updated_at = datetime.now()
				session.commit()
				estado = 'activada' if promo.is_active else 'pausada'
				return True, f'Promoción {estado}.'
			except Exception as e:
				session.rollback()
				logger.error('toggle_active: %s', e, exc_info=True)
				return False, 'Error al cambiar estado.'

	def calc_nxm_price(
		self, base_price: Decimal, buy_qty: int, pay_qty: int, total_qty: Decimal
	) -> Decimal:
		"""Calcula el precio efectivo por unidad para una promo NxM según la cantidad en carrito."""
		if total_qty <= 0:  # BUG 3: evitar ZeroDivisionError
			return base_price
		buy = Decimal(str(buy_qty))
		pay = Decimal(str(pay_qty))
		sets = int(total_qty // buy)
		remainder = total_qty % buy
		total_cost = sets * pay * base_price + remainder * base_price
		return (total_cost / total_qty).quantize(Decimal('0.01'))

	def _validate_data(self, data: dict):
		name = str(data.get('name', '')).strip()
		if not name:
			return None, 'El nombre de la promoción es obligatorio.'

		promo_type = data.get('promo_type', '')
		if promo_type not in ('pct', 'nxm', 'fixed'):
			return None, 'Tipo de promoción inválido.'

		discount_value = None
		buy_qty = None
		pay_qty = None

		if promo_type == 'pct':
			try:
				discount_value = Decimal(str(data.get('discount_value', '')))
				if not (Decimal('0') < discount_value <= Decimal('100')):
					return None, 'El descuento debe estar entre 0.01% y 100%.'
			except (InvalidOperation, ValueError):
				return None, 'Porcentaje de descuento inválido.'

		elif promo_type == 'nxm':
			try:
				buy_qty = int(data.get('buy_qty', 0))
				pay_qty = int(data.get('pay_qty', 0))
				if buy_qty <= 1:
					return None, '"Lleva" debe ser mayor a 1.'
				if pay_qty <= 0:
					return None, '"Paga" debe ser mayor a 0.'
				if pay_qty >= buy_qty:
					return (
						None,
						'"Paga" debe ser menor que "Lleva" para que haya descuento.',
					)
			except (ValueError, TypeError):
				return None, 'Cantidades NxM inválidas.'

		elif promo_type == 'fixed':
			try:
				discount_value = Decimal(str(data.get('discount_value', '')))
				if discount_value < Decimal('0'):
					return None, 'El precio fijo no puede ser negativo.'
			except (InvalidOperation, ValueError):
				return None, 'Precio fijo inválido.'

		variant_id = data.get('variant_id') or None
		category_id = data.get('category_id') or None
		if not variant_id and not category_id:
			return None, 'Debés seleccionar un producto al que aplica la promoción.'

		try:
			date_from = datetime.strptime(data['date_from'], '%d/%m/%Y')
			date_to = datetime.strptime(data['date_to'], '%d/%m/%Y').replace(
				hour=23, minute=59, second=59
			)
		except (KeyError, ValueError):
			return None, 'Fechas inválidas. Usá el formato DD/MM/AAAA.'

		if date_to < date_from:
			return None, 'La fecha "Hasta" debe ser posterior a "Desde".'

		days_of_week = data.get('days_of_week') or None
		time_from = data.get('time_from') or None
		time_to = data.get('time_to') or None

		if time_from and time_to:
			try:
				datetime.strptime(time_from, '%H:%M')
				datetime.strptime(time_to, '%H:%M')
			except ValueError:
				return None, 'Horarios inválidos. Usá el formato HH:MM.'
			if time_from >= time_to:
				return None, 'El horario "Hasta" debe ser posterior al "Desde".'

		return {
			'name': name,
			'promo_type': promo_type,
			'discount_value': discount_value,
			'buy_qty': buy_qty,
			'pay_qty': pay_qty,
			'variant_id': variant_id,
			'category_id': category_id,
			'date_from': date_from,
			'date_to': date_to,
			'days_of_week': days_of_week,
			'time_from': time_from,
			'time_to': time_to,
		}, None
