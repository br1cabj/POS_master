import os
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importamos todos tus modelos
from database.models import (
	Article,
	ArticleVariant,
	Base,
	Branch,
	CashMovement,
	CashSession,
	ComboItem,
	Customer,
	Sale,
	SaleDetail,
	Stock,
	Supplier,
	Tenant,
	User,
	Warehouse,
)

DB_URL = 'sqlite:///pos_system.db'


def hash_password(password):
	return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def main():
	print('🧹 Borrando base de datos antigua...')
	if os.path.exists('pos_system.db'):
		os.remove('pos_system.db')

	print('🏗️ Creando estructura de tablas...')
	engine = create_engine(DB_URL, echo=False)
	Base.metadata.create_all(engine)
	Session = sessionmaker(bind=engine)

	with Session() as session:
		try:
			print('🏢 Creando Empresa, Sucursal y Depósito...')
			tenant = Tenant(name='Kiosco Super Test')
			session.add(tenant)
			session.flush()

			branch = Branch(name='Sede Principal', tenant_id=tenant.id)
			session.add(branch)
			session.flush()

			warehouse = Warehouse(name='Depósito General', branch_id=branch.id)
			session.add(warehouse)
			session.flush()

			print('👥 Creando Usuarios (Admin y Cajero)...')
			admin = User(
				tenant_id=tenant.id,
				username='admin',
				password_hash=hash_password('admin'),
				role='admin',
				is_active=True,
			)
			cajero = User(
				tenant_id=tenant.id,
				username='cajero',
				password_hash=hash_password('1234'),
				role='cashier',
				is_active=True,
			)
			session.add_all([admin, cajero])

			print('🚚 Creando Proveedores y Clientes...')
			prov_coca = Supplier(
				tenant_id=tenant.id,
				name='Coca-Cola Femsa',
				phone='11223344',
				is_active=True,
			)
			prov_arcor = Supplier(
				tenant_id=tenant.id,
				name='Distribuidora Arcor',
				phone='55667788',
				is_active=True,
			)
			prov_pan = Supplier(
				tenant_id=tenant.id, name='Panadería Local', is_active=True
			)
			session.add_all([prov_coca, prov_arcor, prov_pan])

			cf = Customer(
				tenant_id=tenant.id,
				name='Consumidor Final',
				current_balance=0,
				is_active=True,
			)
			juan = Customer(
				tenant_id=tenant.id,
				name='Juan Perez (Fiado)',
				current_balance=1500.0,
				is_active=True,
			)
			session.add_all([cf, juan])
			session.flush()

			print('📦 Creando Catálogo de Productos...')
			# 1. Producto Normal (Coca Cola)
			art_coca = Article(
				name='Coca-Cola 1.5L',
				tenant_id=tenant.id,
				supplier_id=prov_coca.id,
				has_variants=False,
			)
			session.add(art_coca)
			session.flush()
			var_coca = ArticleVariant(
				article_id=art_coca.id,
				barcode='77912345',
				cost_price=800,
				selling_price=1500,
			)
			session.add(var_coca)

			# 2. Producto para Balanza (Queso Tybo) - Código '123'
			art_queso = Article(
				name='Queso Tybo x Kg', tenant_id=tenant.id, has_variants=False
			)
			session.add(art_queso)
			session.flush()
			var_queso = ArticleVariant(
				article_id=art_queso.id,
				barcode='123',
				cost_price=4000,
				selling_price=7000,
			)
			session.add(var_queso)

			# 3. Producto Táctil Suelto (Bolsa de Hielo)
			art_hielo = Article(
				name='Bolsa de Hielo 2Kg', tenant_id=tenant.id, has_variants=False
			)
			session.add(art_hielo)
			session.flush()
			var_hielo = ArticleVariant(
				article_id=art_hielo.id,
				barcode=None,
				cost_price=300,
				selling_price=800,
				show_on_touch=True,
				btn_color='#1f538d',
			)  # Azul
			session.add(var_hielo)

			# 4. Ingredientes para el Combo
			art_pan = Article(
				name='Pan de Pancho (Unidad)',
				tenant_id=tenant.id,
				supplier_id=prov_pan.id,
				has_variants=False,
			)
			art_salchicha = Article(
				name='Salchicha Viena (Unidad)',
				tenant_id=tenant.id,
				supplier_id=prov_arcor.id,
				has_variants=False,
			)
			session.add_all([art_pan, art_salchicha])
			session.flush()

			var_pan = ArticleVariant(
				article_id=art_pan.id,
				barcode='PAN01',
				cost_price=100,
				selling_price=200,
			)
			var_salchicha = ArticleVariant(
				article_id=art_salchicha.id,
				barcode='SAL01',
				cost_price=200,
				selling_price=400,
			)
			session.add_all([var_pan, var_salchicha])
			session.flush()

			# 5. El Combo Mágico (Promo Pancho + Coca)
			art_promo = Article(
				name='🍔 Promo Pancho + Coca', tenant_id=tenant.id, has_variants=False
			)
			session.add(art_promo)
			session.flush()
			var_promo = ArticleVariant(
				article_id=art_promo.id,
				barcode=None,
				cost_price=0,
				selling_price=2000,
				is_combo=True,
				show_on_touch=True,
				btn_color='#e68a00',
			)  # Naranja
			session.add(var_promo)
			session.flush()

			# Receta de la Promo
			ingrediente1 = ComboItem(
				combo_id=var_promo.id, ingredient_id=var_pan.id, quantity_required=1
			)
			ingrediente2 = ComboItem(
				combo_id=var_promo.id,
				ingredient_id=var_salchicha.id,
				quantity_required=1,
			)
			ingrediente3 = ComboItem(
				combo_id=var_promo.id, ingredient_id=var_coca.id, quantity_required=1
			)
			session.add_all([ingrediente1, ingrediente2, ingrediente3])

			print('📊 Inyectando Stock a los depósitos...')
			stocks = [
				Stock(warehouse_id=warehouse.id, variant_id=var_coca.id, quantity=50),
				Stock(
					warehouse_id=warehouse.id, variant_id=var_queso.id, quantity=10.5
				),  # 10.5 Kilos
				Stock(warehouse_id=warehouse.id, variant_id=var_hielo.id, quantity=20),
				Stock(warehouse_id=warehouse.id, variant_id=var_pan.id, quantity=30),
				Stock(
					warehouse_id=warehouse.id, variant_id=var_salchicha.id, quantity=30
				),
			]
			session.add_all(stocks)

			print('💰 Abriendo una sesión de caja y simulando ventas...')
			caja = CashSession(
				tenant_id=tenant.id,
				user_id=admin.id,
				opening_balance=10000.0,
				opened_at=datetime.now() - timedelta(hours=4),
				is_open=True,
			)
			session.add(caja)
			session.flush()

			# Movimiento Manual
			mov = CashMovement(
				session_id=caja.id,
				movement_type='gasto',
				amount=1500,
				description='Pago al sodero',
			)
			session.add(mov)

			# Venta Simulada
			venta1 = Sale(
				tenant_id=tenant.id,
				user_id=admin.id,
				customer_id=cf.id,
				payment_method='efectivo',
				status='completada',
				date=datetime.now() - timedelta(hours=1),
				total_amount=1500.0,
				profit=700.0,
			)
			session.add(venta1)
			session.flush()

			detalle1 = SaleDetail(
				sale_id=venta1.id,
				variant_id=var_coca.id,
				description='Coca-Cola 1.5L',
				quantity=1,
				unit_cost=800,
				unit_price=1500,
				subtotal=1500,
			)
			session.add(detalle1)

			mov_venta = CashMovement(
				session_id=caja.id,
				movement_type='venta',
				amount=1500,
				description=f'Ticket #{venta1.id} - Pago: Efectivo',
			)
			session.add(mov_venta)

			session.commit()
			print('✅ ¡Base de datos de prueba generada con éxito!')
			print('--------------------------------------------------')
			print("🔑 Usa 'admin' / 'admin' para iniciar sesión.")
			print('--------------------------------------------------')

		except Exception as e:
			session.rollback()
			print(f'❌ Error fatal al crear la base de datos: {e}')


if __name__ == '__main__':
	main()
