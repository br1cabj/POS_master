from datetime import datetime

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import Product, Sale, SaleDetail


class SalesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def process_sale(self, tenant_id, user_id, cart_items):
		session = self.Session()
		try:
			new_sale = Sale(
				tenant_id=tenant_id,
				user_id=user_id,
				total_amount=0,
				date=datetime.utcnow(),
			)

			total_sale = 0

			for item in cart_items:
				product_db = (
					session.query(Product)
					.filter_by(id=item['product_id'], tenant_id=tenant_id)
					.with_for_update()
					.first()
				)

				if not product_db:
					raise Exception(
						f'Producto "{item["name"]}" no encontrado o no disponible.'
					)

				if product_db.stock < item['qty']:
					raise Exception(
						f'Stock insuficiente para "{item["name"]}". Disponibles: {product_db.stock}.'
					)

				product_db.stock -= item['qty']

				subtotal = item['price'] * item['qty']
				total_sale += subtotal

				detail = SaleDetail(
					tenant_id=tenant_id,
					product_name=item['name'],
					quantity=item['qty'],
					unit_price=item['price'],
					subtotal=subtotal,
				)

				new_sale.items.append(detail)

			new_sale.total_amount = total_sale

			session.add(new_sale)
			session.commit()

			return True, f'Venta registrada exitosamente. Total: ${total_sale:.2f}'

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def get_history(self, tenant_id):
		session = self.Session()
		try:
			sales = (
				session.query(Sale)
				.options(joinedload(Sale.user), joinedload(Sale.items))
				.filter_by(tenant_id=tenant_id)
				.order_by(Sale.date.desc())
				.all()
			)
			return sales
		except Exception as e:
			print(f'Error al obtener historial de ventas: {e}')
			return []
		finally:
			session.close()

	def get_sale_details(self, sale_id):
		session = self.Session()
		try:
			details = session.query(SaleDetail).filter_by(sale_id=sale_id).all()
			return details
		finally:
			session.close()
