from sqlalchemy.orm import joinedload, sessionmaker

from database.models import ArticleVariant, StockMovement, User


class InventoryController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_kardex(self, tenant_id):
		"""
		Obtiene el historial completo de movimientos de inventario (Kardex)
		para el negocio actual, ordenado desde el más reciente al más antiguo.
		"""
		session = self.Session()
		try:
			# Traemos los movimientos, cargando los datos del producto y del usuario al mismo tiempo
			return (
				session.query(StockMovement)
				.options(
					joinedload(StockMovement.variant).joinedload(
						ArticleVariant.article
					),
					joinedload(StockMovement.user),
				)
				.join(User)
				.filter(User.tenant_id == tenant_id)
				.order_by(StockMovement.date.desc())
				.all()
			)

		except Exception as e:
			print(f'Error al obtener Kardex: {e}')
			return []
		finally:
			session.close()
