from datetime import datetime

from sqlalchemy.orm import sessionmaker

from database.models import Article, Customer, Sale, SaleDetail


class SalesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def process_sale(self, tenant_id, user_id, cart_items):
		"""
		Procesa la venta, descuenta stock y calcula la GANANCIA (Profit)
		cart_items formato: [{'article_id': 1, 'desc': 'Coca', 'price': 150, 'qty': 2}, ...]
		"""
		session = self.Session()
		try:
			# 1. Buscar al cliente por defecto "Consumidor Final"
			default_customer = (
				session.query(Customer)
				.filter_by(name='Consumidor Final', tenant_id=tenant_id)
				.first()
			)
			customer_id = default_customer.id if default_customer else None

			# 2. Crear cabecera de venta
			new_sale = Sale(
				tenant_id=tenant_id, user_id=user_id, customer_id=customer_id
			)

			total_sale = 0.0
			total_cost = 0.0

			# 3. Procesar el carrito
			for item in cart_items:
				article = (
					session.query(Article).filter_by(id=item['article_id']).first()
				)
				if not article:
					raise Exception(f'Artículo no encontrado: {item["desc"]}')

				if article.stock < item['qty']:
					raise Exception(
						f'Stock insuficiente para {article.description}. Quedan {article.stock}.'
					)

				# Restar stock
				article.stock -= item['qty']

				# Cálculos de dinero
				subtotal = item['price'] * item['qty']
				cost_subtotal = article.cost_price * item['qty']

				total_sale += subtotal
				total_cost += cost_subtotal

				# Crear detalle
				detail = SaleDetail(
					article_id=article.id,
					description=article.description,
					quantity=item['qty'],
					unit_cost=article.cost_price,
					unit_price=item['price'],
					subtotal=subtotal,
				)
				new_sale.items.append(detail)

			# 4. Guardar totales y ganancia (Total Venta - Total Costo)
			new_sale.total_amount = total_sale
			new_sale.profit = total_sale - total_cost
			new_sale.date = datetime.utcnow()

			session.add(new_sale)
			session.commit()

			# (Nota: Omitimos temporalmente el servicio de impresión para probar la lógica primero)

			return True, f'Venta registrada. Total: ${total_sale:.2f}'

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def get_articles_for_sale(self, tenant_id):
		"""Obtiene artículos para llenar el buscador del POS"""
		session = self.Session()
		try:
			return session.query(Article).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()
