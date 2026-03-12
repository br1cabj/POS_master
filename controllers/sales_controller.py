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
		"""Obtiene el catálogo de productos disponibles para vender."""
		session = self.Session()
		try:
			return (
				session.query(Article)
				.filter_by(tenant_id=tenant_id, is_active=True)
				.all()
			)
		finally:
			session.close()

	def get_customers(self, tenant_id):
		"""Obtiene la lista de clientes para el selector de la interfaz."""
		session = self.Session()
		try:
			return (
				session.query(Customer)
				.filter_by(tenant_id=tenant_id, is_active=True)
				.order_by(Customer.name)
				.all()
			)
		finally:
			session.close()

	def get_history(self, tenant_id):
		"""Obtiene el historial completo de ventas con sus relaciones."""
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
		"""Obtiene el detalle (los items) de un ticket específico."""
		session = self.Session()
		try:
			return session.query(SaleDetail).filter_by(sale_id=sale_id).all()
		finally:
			session.close()

	# --- FUNCIÓN PRINCIPAL DE VENTAS ---
	def process_sale(
		self,
		tenant_id,
		user_id,
		cart_items,
		customer_id=None,
		is_fiado=False,
		payment_method='efectivo',
	):
		"""
		Procesa la venta completa. Calcula totales, resta stock,
		actualiza la caja o la cuenta corriente y genera el PDF.
		"""
		session = self.Session()
		try:
			# 1. Verificación de Caja Abierta
			active_cash = (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
			if not active_cash:
				return False, '⚠️ ¡Debes ABRIR LA CAJA en el menú antes de vender!'

			# 2. Asignación de Cliente por Defecto
			if not customer_id:
				default_customer = (
					session.query(Customer)
					.filter_by(name='Consumidor Final', tenant_id=tenant_id)
					.first()
				)
				customer_id = default_customer.id if default_customer else None

			# 3. Preparación de la Venta Maestra
			metodo_final = 'fiado' if is_fiado else payment_method.lower()
			estado_final = 'pendiente' if is_fiado else 'completada'

			new_sale = Sale(
				tenant_id=tenant_id,
				user_id=user_id,
				customer_id=customer_id,
				payment_method=metodo_final,
				status=estado_final,
				date=datetime.utcnow(),
			)

			total_sale = 0.0
			total_cost = 0.0

			# 4. Procesamiento del Carrito (Detalles y Stock)
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

					# Descontamos el stock
					article.stock -= item['qty']
					cost_price = article.cost_price
				else:
					# Venta rápida sin artículo en base de datos
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

			# 5. Calculamos y asignamos totales financieros
			new_sale.total_amount = total_sale
			new_sale.profit = total_sale - total_cost

			session.add(new_sale)
			session.flush()  # Obtenemos el ID de la venta temporalmente

			# 6. Movimiento Financiero
			if is_fiado:
				if not customer_id:
					return False, 'Debes seleccionar un cliente para fiar.'
				customer = session.query(Customer).filter_by(id=customer_id).first()
				if customer:
					customer.current_balance += total_sale
			else:
				movement = CashMovement(
					session_id=active_cash.id,
					movement_type='venta',
					amount=total_sale,
					description=f'Ticket #{new_sale.id} - Pago: {payment_method.capitalize()}',
				)
				session.add(movement)

			# Confirmamos todos los cambios en la base de datos
			session.commit()

			# 7. Generación del Ticket (PDF)
			from controllers.receipt_controller import ReceiptController

			customer_str = 'Consumidor Final'
			if customer_id:
				c = session.query(Customer).filter_by(id=customer_id).first()
				if c:
					customer_str = c.name

			date_str = new_sale.date.strftime('%Y-%m-%d %H:%M')

			pdf_maker = ReceiptController()
			pdf_maker.generate_pdf(
				sale_id=new_sale.id,
				date_str=date_str,
				items_list=cart_items,
				total=total_sale,
				customer_name=customer_str,
			)

			# Retornamos el éxito
			return (
				True,
				f'Venta registrada ({metodo_final.capitalize()}). Total: ${total_sale:.2f}',
			)

		except Exception as e:
			session.rollback()
			return False, f'Error al procesar venta: {str(e)}'
		finally:
			session.close()
