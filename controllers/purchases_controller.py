from datetime import datetime

from sqlalchemy.orm import sessionmaker

from database.models import Article, CashMovement, CashSession, Purchase, Supplier


class PurchasesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_suppliers(self, tenant_id):
		"""Obtiene la lista de proveedores de la base de datos."""
		session = self.Session()
		try:
			return session.query(Supplier).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()

	def get_articles(self, tenant_id):
		"""Obtiene el catálogo de artículos."""
		session = self.Session()
		try:
			return session.query(Article).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()

	def process_purchase(self, tenant_id, user_id, supplier_id, cart_items):
		"""
		Registra la compra, aumenta el stock de los artículos
		y registra el gasto en la caja actual.
		"""
		session = self.Session()
		try:
			# 1. Verificar si la caja está abierta (para poder pagarle al proveedor)
			active_cash = (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
			if not active_cash:
				return (
					False,
					'⚠️ Debes ABRIR LA CAJA para registrar pagos a proveedores.',
				)

			total_purchase = sum(item['subtotal'] for item in cart_items)

			# 2. Registrar el total de la compra
			new_purchase = Purchase(
				tenant_id=tenant_id,
				user_id=user_id,
				supplier_id=supplier_id,
				total_amount=total_purchase,
				date=datetime.utcnow(),
			)
			session.add(new_purchase)
			session.flush()  # Obtenemos el ID de la compra sin guardar permanentemente aún

			# 3. Sumar el stock a los artículos
			for item in cart_items:
				article = (
					session.query(Article).filter_by(id=item['article_id']).first()
				)
				if article:
					article.stock += item['qty']
					# Actualizamos el costo del artículo si el proveedor lo cambió
					article.cost_price = item['cost']

			# 4. Descontar el dinero de la caja (Movimiento de Gasto)
			movement = CashMovement(
				session_id=active_cash.id,
				movement_type='gasto',
				amount=total_purchase,
				description=f'Pago a proveedor (Compra #{new_purchase.id})',
			)
			session.add(movement)

			session.commit()
			return (
				True,
				f'Compra registrada exitosamente. Total pagado: ${total_purchase:.2f}',
			)

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
