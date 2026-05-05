import logging

from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import Article, ArticleVariant, StockMovement
from utils.config import make_engine

logger = logging.getLogger(__name__)

_default_engine = None


def _get_default_engine():
	global _default_engine
	if _default_engine is None:
		_default_engine = make_engine()
	return _default_engine


_MAX_PAGE_SIZE = 1000


class InventoryController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _get_default_engine()
		super().__init__(engine)

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
						'user_name': mov.user.username if mov.user else 'Sistema',
					}
					for mov in movements
				]
			except Exception as e:
				logger.error(
					f'Error al obtener Kardex para el tenant {tenant_id}: {e}',
					exc_info=True,
				)
				return []
