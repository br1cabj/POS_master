import logging

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import Article, ArticleVariant, Stock
from utils.config import make_engine

_default_engine = make_engine()

logger = logging.getLogger(__name__)


class AlertsController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def get_low_stock_variants(self, tenant_id, threshold=5):
		"""Retorna variantes activas con stock total <= threshold, ordenadas de menor a mayor."""
		with self.SessionLocal() as session:
			try:
				return [
					{
						'variant_id': row.variant_id,
						'barcode': row.barcode,
						'name': row.name,
						'stock': row.total_stock,
						'threshold': threshold,
					}
					for row in (
						session.query(
							ArticleVariant.id.label('variant_id'),
							ArticleVariant.barcode,
							Article.name,
							func.coalesce(func.sum(Stock.quantity), 0).label(
								'total_stock'
							),
						)
						.join(Article, ArticleVariant.article_id == Article.id)
						.outerjoin(Stock, ArticleVariant.id == Stock.variant_id)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.group_by(
							ArticleVariant.id, ArticleVariant.barcode, Article.name
						)
						.having(func.coalesce(func.sum(Stock.quantity), 0) <= threshold)
						.order_by(func.coalesce(func.sum(Stock.quantity), 0).asc())
						.all()
					)
				]
			except Exception as e:
				logger.error(f'Error en alertas de stock: {e}', exc_info=True)
				return []
