import logging

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import Article, ArticleVariant, StockMovement

logger = logging.getLogger(__name__)


class InventoryController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_kardex(self, tenant_id, page=1, limit=100):
		"""
		Obtiene el historial de movimientos de inventario (Kardex).
		"""

		try:
			page = int(page)
			limit = int(limit)

			# Evitamos números negativos o ceros
			if page < 1:
				page = 1
			if limit < 1:
				limit = 100

			# Tope máximo inquebrantable (Hard Limit)
			if limit > 1000:
				limit = 1000

		except (ValueError, TypeError):
			# Si nos envían basura (strings, booleanos), usamos valores por defecto
			page = 1
			limit = 100

		# Calculamos el desplazamiento (offset)
		offset = (page - 1) * limit

		with self.Session() as session:
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
					.offset(offset)
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
