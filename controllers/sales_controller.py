# controllers/sales_controller.py
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from database.models import Product, Sale, SaleDetail


class SalesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def process_sale(self, tenant_id, user_id, cart_items):
		session = self.Session()
		try:
			new_sale = Sale(tenant_id=tenant_id, user_id=user_id, total_amount=0)

			total_sale = 0

			for item in cart_items:
				product_db = (
					session.query(Product).filter_by(id=item['product_id']).first()
				)

				if not product_db:
					raise Exception(f'Producto {item["name"]} no encontrado.')

				if product_db.stock < item['qty']:
					raise Exception(
						f'Stock insuficiente para {item["name"]}. Quedan {product_db.stock}.'
					)

				product_db.stock -= item['qty']

				subtotal = item['price'] * item['qty']
				total_sale += subtotal

				detail = SaleDetail(
					product_name=item['name'],
					quantity=item['qty'],
					unit_price=item['price'],
					subtotal=subtotal,
				)

				new_sale.items.append(detail)

			new_sale.total_amount = total_sale
			new_sale.date = datetime.utcnow()

			session.add(new_sale)
			session.commit()

			return True, f'Venta registrada. Total: ${total_sale}'

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
