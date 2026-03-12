from datetime import datetime

from sqlalchemy.orm import joinedload, sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	CashMovement,
	CashSession,
	Purchase,
	Stock,
	StockMovement,
	Supplier,
	Warehouse,
)


class PurchasesController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_suppliers(self, tenant_id):
		"""Obtiene la lista de proveedores activos de la base de datos."""
		session = self.Session()
		try:
			return (
				session.query(Supplier)
				.filter_by(tenant_id=tenant_id, is_active=True)
				.all()
			)
		finally:
			session.close()

	def get_variants(self, tenant_id):
		"""
		NUEVO: Obtiene el catálogo de variantes en lugar de los artículos genéricos,
		para saber exactamente qué producto físico estamos comprando.
		"""
		session = self.Session()
		try:
			return (
				session.query(ArticleVariant)
				.options(joinedload(ArticleVariant.article))
				.join(Article)
				.filter(Article.tenant_id == tenant_id, ArticleVariant.is_active)
				.all()
			)
		finally:
			session.close()

	def process_purchase(self, tenant_id, user_id, supplier_id, cart_items):
		"""
		Registra la compra, aumenta el stock físico en el almacén,
		crea el registro de auditoría (Kardex) y descuenta el dinero de la caja.
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
			session.flush()  # Obtenemos el ID de la compra (new_purchase.id)

			# Buscamos el almacén por defecto por si tenemos que crear un stock desde cero
			branch = (
				session.query(Branch)
				.filter_by(tenant_id=tenant_id, name='Sede Principal')
				.first()
			)
			default_warehouse = (
				session.query(Warehouse)
				.filter_by(branch_id=branch.id, name='Depósito General')
				.first()
				if branch
				else None
			)

			# 3. Sumar el stock a los artículos e historial (Kardex)
			for item in cart_items:
				variant_id = item[
					'variant_id'
				]  # Ahora recibimos variant_id desde la vista
				qty = item['qty']
				new_cost = item['cost']

				variant = session.query(ArticleVariant).filter_by(id=variant_id).first()
				if not variant:
					raise Exception(
						'Una de las variantes compradas ya no existe en la base de datos.'
					)

				# Actualizamos el costo de la variante si el proveedor nos cobró distinto
				variant.cost_price = new_cost

				# Buscamos dónde está guardado este producto
				stock_record = (
					session.query(Stock).filter_by(variant_id=variant_id).first()
				)

				if stock_record:
					# Si ya existía, simplemente le sumamos la cantidad comprada
					stock_record.quantity += qty
					warehouse_id = stock_record.warehouse_id
				else:
					# Si nunca habíamos tenido stock de esto, lo creamos en el depósito general
					if not default_warehouse:
						raise Exception(
							"No se encontró el 'Depósito General' para ingresar la mercadería."
						)
					stock_record = Stock(
						quantity=qty,
						warehouse_id=default_warehouse.id,
						variant_id=variant_id,
					)
					session.add(stock_record)
					warehouse_id = default_warehouse.id

				# --- NUEVO: REGISTRO HISTÓRICO DE ENTRADA (KARDEX) ---
				movimiento_entrada = StockMovement(
					movement_type='in',  # 'in' = Entrada
					quantity=qty,
					reference=f'Compra Proveedor #{new_purchase.id}',
					dest_warehouse_id=warehouse_id,
					variant_id=variant_id,
					user_id=user_id,
				)
				session.add(movimiento_entrada)
				# ----------------------------------------------------

			# 4. Descontar el dinero de la caja (Movimiento de Gasto)
			movement = CashMovement(
				session_id=active_cash.id,
				movement_type='gasto',
				amount=total_purchase,
				description=f'Pago a proveedor (Compra #{new_purchase.id})',
			)
			session.add(movement)

			# Confirmar todo
			session.commit()
			return (
				True,
				f'Compra registrada exitosamente. Total pagado: ${total_purchase:.2f}',
			)

		except Exception as e:
			session.rollback()
			return False, f'Error al registrar la compra: {str(e)}'
		finally:
			session.close()
