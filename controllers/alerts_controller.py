import logging

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import Article, ArticleVariant, Stock

logger = logging.getLogger(__name__)


class AlertsController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_low_stock_variants(self, tenant_id, threshold=5):
		with self.Session() as session:
			try:
				query = (
					session.query(
						ArticleVariant.id.label('variant_id'),
						ArticleVariant.barcode,
						Article.name,
						func.coalesce(func.sum(Stock.quantity), 0).label('total_stock'),
					)
					.join(Article, ArticleVariant.article_id == Article.id)
					.outerjoin(Stock, ArticleVariant.id == Stock.variant_id)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
					.group_by(ArticleVariant.id, ArticleVariant.barcode, Article.name)
					.having(func.coalesce(func.sum(Stock.quantity), 0) <= threshold)
					.order_by(func.coalesce(func.sum(Stock.quantity), 0).asc())
				)

				results = query.all()

				return [
					{
						'variant_id': row.variant_id,
						'barcode': row.barcode,
						'name': row.name,
						'stock': row.total_stock,
						'threshold': threshold,
					}
					for row in results
				]

			except Exception as e:
				# Guardamos el error en un archivo de log para revisarlo después
				logger.error(f'Error de BD en alertas de stock: {e}', exc_info=True)

				# Devolvemos una lista vacía para no romper la interfaz gráfica
				return []
