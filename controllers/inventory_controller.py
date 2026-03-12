import logging

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import Article, ArticleVariant, StockMovement

logger = logging.getLogger(__name__)


class InventoryController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_kardex(self, tenant_id, limit=1000):
		"""
		Obtiene el historial de movimientos de inventario (Kardex).
		"""
		with self.Session() as session:
			try:
				# Traemos los movimientos con un límite de seguridad
				movements = (
					session.query(StockMovement)
					.options(
						joinedload(StockMovement.variant).joinedload(
							ArticleVariant.article
						),
						joinedload(StockMovement.user),
					)
					# Hacemos JOIN con Article para asegurar que filtramos por el tenant correcto
					# independientemente de si el movimiento tiene o no un usuario asignado
					.join(ArticleVariant, StockMovement.variant_id == ArticleVariant.id)
					.join(Article, ArticleVariant.article_id == Article.id)
					.filter(Article.tenant_id == tenant_id)
					.order_by(StockMovement.date.desc())
					.limit(limit)  # <-- La protección contra la "Bomba de Tiempo"
					.all()
				)

				# Mapeamos a una lista de diccionarios para la interfaz gráfica
				# Así evitamos el DetachedInstanceError
				return [
					{
						'id': mov.id,
						'date': mov.date,
						'movement_type': mov.movement_type,  # Ej: 'in', 'out'
						'quantity': mov.quantity,
						'reference': mov.reference,
						# Manejo seguro por si algún dato fue borrado de la BD
						'article_name': mov.variant.article.name
						if mov.variant and mov.variant.article
						else 'Desconocido',
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
