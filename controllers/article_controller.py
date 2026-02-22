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
			# Validar si el código de barras ya existe
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
			return session.query(Article).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()
