from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession, Customer


class CustomerController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_customers(self, tenant_id):
		"""Obtiene la lista de clientes activos ordenados por nombre"""
		session = self.Session()
		try:
			return (
				session.query(Customer)
				.filter_by(
					tenant_id=tenant_id, is_active=True
				)  # Solo traemos los activos
				.order_by(Customer.name)
				.all()
			)
		finally:
			session.close()

	def add_customer(self, tenant_id, name, phone):
		"""Da de alta a un nuevo cliente o reactiva a uno borrado"""
		session = self.Session()
		try:
			exist = (
				session.query(Customer)
				.filter_by(name=name, tenant_id=tenant_id)
				.first()
			)

			if exist:
				if exist.is_active:
					return False, 'Ese cliente ya existe en el sistema.'
				else:
					# Reactivamos al cliente borrado
					exist.is_active = True
					exist.phone = phone
					session.commit()
					return True, 'Cliente reactivado con éxito.'

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
			return False, f'Error al crear cliente: {str(e)}'
		finally:
			session.close()

	def pay_debt(self, tenant_id, user_id, customer_id, amount):
		"""Registra el pago de una deuda: descuenta el saldo del cliente y mete dinero a la caja"""
		session = self.Session()
		try:
			amount_float = float(amount)

			# Validación de seguridad
			if amount_float <= 0:
				return False, 'El monto a abonar debe ser mayor a cero.'

			# 1. Verificar que la caja esté abierta para recibir el dinero
			active_cash = (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
			if not active_cash:
				return False, '⚠️ Abre la caja para registrar el pago.'

			# 2. Buscar al cliente y actualizar su saldo
			customer = session.query(Customer).filter_by(id=customer_id).first()
			if not customer:
				return False, 'Cliente no encontrado.'
			customer.current_balance -= amount_float

			# 3. Registrar el ingreso en la caja
			movement = CashMovement(
				session_id=active_cash.id,
				movement_type='ingreso',
				amount=amount_float,
				description=f'Abono de Cuenta Corriente: {customer.name}',
			)
			session.add(movement)

			session.commit()
			return (
				True,
				f'Pago de ${amount_float:.2f} registrado. Nueva deuda: ${customer.current_balance:.2f}',
			)

		except ValueError:
			return False, 'Monto inválido. Usa solo números.'
		except Exception as e:
			session.rollback()
			return False, f'Error al procesar el pago: {str(e)}'
		finally:
			session.close()
