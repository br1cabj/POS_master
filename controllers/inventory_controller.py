import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, sessionmaker

from database.models import Article, ArticleVariant, StockMovement

DB_URL = 'sqlite:///pos_system.db'
_default_engine = create_engine(DB_URL)

logger = logging.getLogger(__name__)


class InventoryController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def get_kardex(self, tenant_id, page=1, limit=100):
		"""Retorna el kardex paginado del tenant. Hard limit: 1000 registros por página."""
		try:
			page, limit = max(1, int(page)), min(max(1, int(limit)), 1000)
		except (ValueError, TypeError):
			page, limit = 1, 100

		with self.SessionLocal() as session:
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
