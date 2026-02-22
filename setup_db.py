# setup_db.py
import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import Customer, Supplier, Tenant, User, init_db


def create_initial_data():
	print('--- Iniciando configuración de la Base de Datos 2.0 ---')

	# 1. Conectamos a la base de datos
	engine = init_db()
	Session = sessionmaker(bind=engine)
	session = Session()

	# 2. Verificamos si ya existe una empresa
	existing_tenant = session.query(Tenant).filter_by(name='Mi Super Tienda').first()
	if existing_tenant:
		print('¡La base de datos ya está inicializada! No haremos cambios.')
		return

	# 3. Crear la Empresa (Tenant)
	print('Creando empresa...')
	new_tenant = Tenant(name='Mi Super Tienda')
	session.add(new_tenant)
	session.commit()

	# 4. Crear el Usuario Admin
	print('Creando usuario administrador...')
	password_bytes = 'admin123'.encode('utf-8')
	salt = bcrypt.gensalt()
	hashed_password = bcrypt.hashpw(password_bytes, salt)

	new_user = User(
		username='admin',
		password_hash=hashed_password.decode('utf-8'),
		role='admin',
		tenant_id=new_tenant.id,
	)
	session.add(new_user)

	# 5. Crear Cliente "Consumidor Final"
	print('Creando Consumidor Final...')
	default_customer = Customer(
		name='Consumidor Final',
		phone='N/A',
		current_balance=0.0,
		tenant_id=new_tenant.id,
	)
	session.add(default_customer)

	# 6. NUEVO: Crear Proveedor Genérico
	print('Creando Proveedor Genérico...')
	default_supplier = Supplier(
		name='Proveedor General', phone='N/A', tenant_id=new_tenant.id
	)
	session.add(default_supplier)

	# Guardar todo en la base de datos
	session.commit()

	print('¡ÉXITO! Base de datos 2.0 lista y sembrada.')
	print("Usuario: 'admin' / Contraseña: 'admin123'")


if __name__ == '__main__':
	create_initial_data()
