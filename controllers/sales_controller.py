from datetime import datetime

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	CashMovement,
	CashSession,
	Customer,
	Sale,
	SaleDetail,
)


class SalesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_articles_for_sale(self, tenant_id):
		session = self.Session()
		try:
			return session.query(Article).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()

	# --- NUEVA FUNCIÓN: Obtener clientes para el selector ---
	def get_customers(self, tenant_id):
		session = self.Session()
		try:
			return (
				session.query(Customer)
				.filter_by(tenant_id=tenant_id)
				.order_by(Customer.name)
				.all()
			)
		finally:
			session.close()

	def get_history(self, tenant_id):
		session = self.Session()
		try:
			return (
				session.query(Sale)
				.options(joinedload(Sale.customer), joinedload(Sale.user))
				.filter_by(tenant_id=tenant_id)
				.order_by(Sale.date.desc())
				.all()
			)
		except Exception as e:
			print(f'Error al leer historial: {e}')
			return []
		finally:
			session.close()

	def get_sale_details(self, sale_id):
		session = self.Session()
		try:
			return session.query(SaleDetail).filter_by(sale_id=sale_id).all()
		finally:
			session.close()

	# --- FUNCIÓN ACTUALIZADA CON LÓGICA DE FIADO ---
	def process_sale(
		self, tenant_id, user_id, cart_items, customer_id=None, is_fiado=False
	):
		"""Procesa la venta. Si es_fiado=True, crea deuda y no afecta la caja."""
		session = self.Session()
		try:
			active_cash = (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
			if not active_cash:
				return False, '⚠️ ¡Debes ABRIR LA CAJA en el menú antes de vender!'

			if not customer_id:
				default_customer = (
					session.query(Customer)
					.filter_by(name='Consumidor Final', tenant_id=tenant_id)
					.first()
				)
				customer_id = default_customer.id if default_customer else None

			new_sale = Sale(
				tenant_id=tenant_id, user_id=user_id, customer_id=customer_id
			)
			total_sale = 0.0
			total_cost = 0.0

			for item in cart_items:
				if item.get('article_id') is not None:
					article = (
						session.query(Article).filter_by(id=item['article_id']).first()
					)
					if not article:
						raise Exception(f'Artículo no encontrado: {item["desc"]}')
					if article.stock < item['qty']:
						raise Exception(
							f'Stock insuficiente para {article.description}'
						)

					article.stock -= item['qty']
					cost_price = article.cost_price
				else:
					cost_price = 0.0

				subtotal = item['price'] * item['qty']
				cost_subtotal = cost_price * item['qty']

				total_sale += subtotal
				total_cost += cost_subtotal

				detail = SaleDetail(
					article_id=item.get('article_id'),
					description=item['desc'],
					quantity=item['qty'],
					unit_cost=cost_price,
					unit_price=item['price'],
					subtotal=subtotal,
				)
				new_sale.items.append(detail)

			new_sale.total_amount = total_sale
			new_sale.profit = total_sale - total_cost
			new_sale.date = datetime.utcnow()

			session.add(new_sale)
			session.flush()

			# --- LA MAGIA DEL FIADO ---
			if is_fiado:
				# 1. Buscamos al cliente y le restamos el total a su saldo (Deuda)
				customer = session.query(Customer).filter_by(id=customer_id).first()
				if customer:
					customer.current_balance -= total_sale
				# Nota: NO creamos CashMovement, porque no entró dinero físico a la caja
			else:
				# VENTA NORMAL: Registramos el dinero en la caja
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='venta',
					amount=total_sale,
					description=f'Ingreso por Venta #{new_sale.id}',
				)
				session.add(movement)

			session.commit()

			tipo = 'FIADO' if is_fiado else 'EFECTIVO'
			return True, f'Venta registrada ({tipo}). Total: ${total_sale:.2f}'

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
