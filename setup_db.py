# setup_db.py
from decimal import Decimal

import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import Branch, Customer, Supplier, Tenant, User, Warehouse, init_db


def create_initial_data():
	print('--- Iniciando configuración de la Base de Datos 2.0 ---')

	# 1. Conectamos a la base de datos
	engine = init_db()
	Session = sessionmaker(bind=engine)

	# 🛡️ ESCUDO: Usamos "with" para garantizar el manejo seguro de la transacción
	with Session() as session:
		try:
			# 2. Verificamos si ya existe la empresa base
			existing_tenant = (
				session.query(Tenant).filter_by(name='Mi Super Tienda').first()
			)
			if existing_tenant:
				print('¡La base de datos ya está inicializada! No haremos cambios.')
				return

			# 3. Crear la Empresa (Tenant)
			print('Creando empresa...')
			new_tenant = Tenant(name='Mi Super Tienda')
			session.add(new_tenant)

			# Hacemos un "flush" para que la BD le asigne un ID temporal (ej. 1) a new_tenant
			# sin guardar permanentemente todavía. Lo necesitamos para los siguientes pasos.
			session.flush()

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
				current_balance=Decimal('0.0'),
				tenant_id=new_tenant.id,
			)
			session.add(default_customer)

			# 6. Crear Proveedor Genérico
			print('Creando Proveedor Genérico...')
			default_supplier = Supplier(
				name='Proveedor General', phone='N/A', tenant_id=new_tenant.id
			)
			session.add(default_supplier)

			# 7. 🛡️ MEJORA: Crear Sucursal y Almacén (Infraestructura logística)
			print('Creando Infraestructura Logística...')
			main_branch = Branch(name='Sede Principal', tenant_id=new_tenant.id)
			session.add(main_branch)
			session.flush()  # Generamos el ID de la sucursal

			main_warehouse = Warehouse(
				name='Depósito General', branch_id=main_branch.id
			)
			session.add(main_warehouse)

			# 8. Guardar todo en la base de datos de forma definitiva
			session.commit()

			print('\n=============================================')
			print('¡ÉXITO! Base de datos 2.0 lista y sembrada.')
			print(f'Empresa ID configurada: {new_tenant.id}')
			print('---------------------------------------------')
			print('Credenciales de acceso inicial:')
			print('Código de Empresa: 1')
			print('Usuario: admin')
			print('Contraseña: admin123')
			print('=============================================')

		except Exception as e:
			# Si ALGO falla en los pasos del 3 al 7, deshacemos TODO
			# para no dejar una base de datos corrupta a la mitad.
			session.rollback()
			print(f'\n❌ Error crítico al inicializar la base de datos: {e}')


if __name__ == '__main__':
	create_initial_data()
