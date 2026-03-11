# controllers/article_controller.py
from sqlalchemy.orm import sessionmaker

from database.models import Article


class ArticleController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def add_article(
		self,
		barcode,
		description,
		cost_price,
		price_1,
		price_2,
		price_3,
		stock,
		min_stock,
		tenant_id,
	):
		"""Crea un artículo con toda la información comercial"""
		session = self.Session()
		try:
			if barcode:
				existing = (
					session.query(Article)
					.filter_by(barcode=barcode, tenant_id=tenant_id)
					.first()
				)
				if existing:
					return False, f'El código de barras {barcode} ya está en uso.'

			new_article = Article(
				barcode=barcode,
				description=description,
				cost_price=float(cost_price) if cost_price else 0.0,
				price_1=float(price_1),
				price_2=float(price_2) if price_2 else 0.0,
				price_3=float(price_3) if price_3 else 0.0,
				stock=int(stock) if stock else 0,
				min_stock=int(min_stock) if min_stock else 5,
				tenant_id=tenant_id,
			)
			session.add(new_article)
			session.commit()
			return True, 'Artículo guardado con éxito'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def get_articles(self, tenant_id):
		"""Obtiene el catálogo completo de la empresa"""
		session = self.Session()
		try:
			return (
				session.query(Article)
				.filter_by(tenant_id=tenant_id, is_active=True)
				.all()
			)
		finally:
			session.close()

	def get_low_stock_articles(self, tenant_id):
		"""
		Consulta a la base de datos los artículos en estado crítico.
		Compara la columna 'stock' con 'min_stock'.
		"""
		session = self.Session()
		try:
			return (
				session.query(Article)
				.filter(
					Article.tenant_id == tenant_id, Article.stock <= Article.min_stock
				)
				.all()
			)
		except Exception as e:
			print(f'Error al obtener alertas de stock: {e}')
			return []
		finally:
			session.close()

	def delete_article(self, article_id):
		session = self.Session()
		try:
			article = session.query(Article).filter_by(id=article_id).first()
			if not article:
				return False, 'Artículo no encontrado'

			article.is_active = False

			session.commit()
			return True, 'Artículo eliminado correctamente.'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
