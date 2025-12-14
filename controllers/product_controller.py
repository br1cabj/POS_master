from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from database.models import Product


class ProductController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def add_product(self, name, price, stock, tenant_id):
		"""
		Crea un nuevo producto. Realiza validación de tipos antes de tocar la DB.
		"""

		if not name:
			return False, 'El nombre es obligatorio'

		try:
			price_val = float(price)
			stock_val = int(stock)
		except ValueError:
			return False, 'Precio o Stock deben ser números válidos'

		with self.Session() as session:
			try:
				new_product = Product(
					name=name, price=price_val, stock=stock_val, tenant_id=tenant_id
				)
				session.add(new_product)
				session.commit()
				return True, 'Producto guardado con éxito'

			except SQLAlchemyError as e:
				session.rollback()
				return False, f'Error de base de datos: {str(e)}'
			except Exception as e:
				session.rollback()
				return False, f'Error inesperado: {str(e)}'

	def get_products(self, tenant_id):
		"""Obtiene todos los productos de un tenant de forma segura para la UI"""
		with self.Session() as session:
			try:
				products = session.query(Product).filter_by(tenant_id=tenant_id).all()

				session.expunge_all()

				return products
			except Exception as e:
				print(f'Error al obtener productos: {e}')
				return []
