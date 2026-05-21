import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
from database.models import Article, ArticleVariant, Stock, StockMovement, User

logger = logging.getLogger(__name__)

_MAX_PAGE_SIZE = 1000


class InventoryController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def get_kardex(self, tenant_id, page=1, limit=100):
		"""Retorna el kardex paginado del tenant. Hard limit: _MAX_PAGE_SIZE registros por página."""
		try:
			page, limit = max(1, int(page)), min(max(1, int(limit)), _MAX_PAGE_SIZE)
		except (ValueError, TypeError):
			page, limit = 1, 100

		with self._Session() as session:
			try:
				movements = (
					session.query(StockMovement)
					.options(
						joinedload(StockMovement.variant).joinedload(
							ArticleVariant.article
						),
						joinedload(StockMovement.user),
					)
					.join(ArticleVariant, StockMovement.variant_id == ArticleVariant.id)
					.join(Article, ArticleVariant.article_id == Article.id)
					.filter(Article.tenant_id == tenant_id)
					.order_by(StockMovement.date.desc())
					.limit(limit)
					.offset((page - 1) * limit)
					.all()
				)
				return [
					{
						'id': mov.id,
						'date': mov.date,
						'movement_type': mov.movement_type,
						'quantity': mov.quantity,
						'reference': mov.reference,
						'article_name': mov.variant.article.name
						if mov.variant and mov.variant.article
						else 'Producto Eliminado',
						'barcode': mov.variant.barcode if mov.variant else 'N/A',
						'user_name': get_display_name(mov.user) if mov.user else 'Sistema',
					}
					for mov in movements
				]
			except Exception as e:
				logger.error(
					f'Error al obtener Kardex para el tenant {tenant_id}: {e}',
					exc_info=True,
				)
				return []

	_ADJUST_REASONS = [
		'Conteo físico',
		'Robo / pérdida',
		'Merma o vencimiento',
		'Daño en mercadería',
		'Corrección de error',
		'Otro',
	]

	@staticmethod
	def get_adjust_reasons():
		return list(InventoryController._ADJUST_REASONS)

	def adjust_stock(self, tenant_id, user_id, variant_id, new_qty_raw, reason, notes=''):
		"""Ajusta el stock de una variante al valor exacto indicado y registra el movimiento."""
		try:
			new_qty = Decimal(str(new_qty_raw)).quantize(Decimal('0.0001'))
		except (InvalidOperation, ValueError):
			return False, 'Cantidad inválida.'
		if new_qty < 0:
			return False, 'El stock no puede ser negativo.'

		with self._Session() as session:
			try:
				variant = (
					session.query(ArticleVariant)
					.join(Article)
					.filter(ArticleVariant.id == variant_id, Article.tenant_id == tenant_id)
					.first()
				)
				if not variant:
					return False, 'Producto no encontrado.'

				user = (
					session.query(User)
					.filter_by(id=user_id, tenant_id=tenant_id, is_active=True)
					.first()
				)
				if not user:
					return False, 'Usuario no válido.'

				stocks = session.query(Stock).filter_by(variant_id=variant_id).with_for_update().all()
				if not stocks:
					return False, 'No hay registro de stock para este producto.'

				current_total = sum(s.quantity for s in stocks)
				delta = new_qty - current_total

				if delta == 0:
					return False, 'El stock ya está en ese valor. Sin cambios.'

				# Verificar factibilidad total antes de distribuir entre almacenes
				if current_total + delta < 0:
					return (
						False,
						f'Stock insuficiente. Total disponible: {float(current_total):.2f} unidades.',
					)

				# Distribuir el delta entre almacenes (primero los de mayor stock para reducciones)
				remaining = delta
				stocks_sorted = sorted(stocks, key=lambda s: s.quantity, reverse=(delta < 0))
				primary = stocks_sorted[0]
				for st in stocks_sorted:
					if remaining == 0:
						break
					if delta < 0:
						take = max(remaining, -int(st.quantity))
						st.quantity += take
						remaining -= take
					else:
						st.quantity += remaining
						remaining = 0

				abs_delta = abs(delta)
				mov_type = 'ajuste_entrada' if delta > 0 else 'ajuste_salida'
				ref = f'Motivo: {reason}'
				if notes:
					ref += f' | Nota: {notes}'
				ref += f' | Anterior: {float(current_total):.2f} → Nuevo: {float(new_qty):.2f}'

				session.add(
					StockMovement(
						movement_type=mov_type,
						quantity=abs_delta,
						reference=ref,
						variant_id=variant_id,
						user_id=user_id,
						source_warehouse_id=primary.warehouse_id,
						tenant_id=tenant_id,
					)
				)

				session.commit()

				sign = f'+{float(abs_delta):.2f}' if delta > 0 else f'-{float(abs_delta):.2f}'
				return (
					True,
					f'Stock ajustado ({sign}). Nuevo total: {float(new_qty):.2f} unidades.',
				)

			except Exception as e:
				session.rollback()
				logger.error(f'Error al ajustar stock {variant_id}: {e}', exc_info=True)
				return False, 'Error interno al ajustar el stock.'
