from sqlalchemy.orm import joinedload, sessionmaker

from database.models import Article, ArticleVariant


class AlertsController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_low_stock_variants(self, tenant_id, threshold=5):
		"""
		Calcula el stock total de cada producto y devuelve una lista
		con aquellos que están por debajo o igual al umbral especificado.
		"""
		session = self.Session()
		try:
			# Traemos todas las variantes activas con sus stocks y su artículo padre
			variants = (
				session.query(ArticleVariant)
				.options(
					joinedload(ArticleVariant.article),
					joinedload(ArticleVariant.stocks),
				)
				.join(Article)
				.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
				.all()
			)

			low_stock_items = []

			for variant in variants:
				# Sumamos el stock físico en todos los almacenes
				total_stock = sum(s.quantity for s in variant.stocks)

				# Comparamos con el nivel crítico
				if total_stock <= threshold:
					low_stock_items.append(
						{
							'variant_id': variant.id,
							'barcode': variant.barcode,
							'name': variant.article.name,
							'stock': total_stock,
							'threshold': threshold,
						}
					)

			# Ordenamos la lista para que los que tienen menos stock (o stock negativo) salgan primero
			low_stock_items.sort(key=lambda x: x['stock'])

			return low_stock_items

		except Exception as e:
			print(f'Error al obtener alertas de stock: {e}')
			return []
		finally:
			session.close()
