from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession, Customer


class CustomerController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_customers(self, tenant_id):
		"""Obtiene la lista de clientes ordenados por nombre"""
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

	def add_customer(self, tenant_id, name, phone):
		"""Da de alta a un nuevo cliente con saldo 0"""
		session = self.Session()
		try:
			# Evitar nombres duplicados
			exist = (
				session.query(Customer)
				.filter_by(name=name, tenant_id=tenant_id)
				.first()
			)
			if exist:
				return False, 'Ese cliente ya existe.'

			new_customer = Customer(
				tenant_id=tenant_id,
				name=name,
				phone=phone,
				current_balance=0.0,  # Saldo inicial
			)
			session.add(new_customer)
			session.commit()
			return True, 'Cliente registrado con éxito.'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def pay_debt(self, tenant_id, user_id, customer_id, amount):
		"""Registra el pago de una deuda: sube el saldo del cliente y mete dinero a la caja"""
		session = self.Session()
		try:
			# 1. Verificar que la caja esté abierta para recibir el dinero
			active_cash = (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
			if not active_cash:
				return False, '⚠️ Abre la caja para registrar el pago.'

			# 2. Buscar al cliente y actualizar su saldo (sumarle el dinero que entregó)
			customer = session.query(Customer).filter_by(id=customer_id).first()
			if not customer:
				return False, 'Cliente no encontrado.'

			amount_float = float(amount)
			customer.current_balance += amount_float

			# 3. Registrar el ingreso en la caja
			movement = CashMovement(
				session_id=active_cash.id,
				movement_type='ingreso',
				amount=amount_float,
				description=f'Pago de Cuenta Corriente: {customer.name}',
			)
			session.add(movement)

			session.commit()
			return True, f'Pago de ${amount_float:.2f} registrado.'

		except ValueError:
			return False, 'Monto inválido.'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
