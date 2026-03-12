# database/models.py
from datetime import datetime

from sqlalchemy import (
	Boolean,
	Column,
	DateTime,
	Float,
	ForeignKey,
	Integer,
	String,
	create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ==========================================
# TABLAS DE CONFIGURACIÓN Y USUARIOS
# ==========================================
class Tenant(Base):
	"""Representa el negocio o tienda principal"""

	__tablename__ = 'tenants'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)

	users = relationship('User', back_populates='tenant', cascade='all, delete-orphan')
	articles = relationship(
		'Article', back_populates='tenant', cascade='all, delete-orphan'
	)
	categories = relationship(
		'Category', back_populates='tenant', cascade='all, delete-orphan'
	)
	sales = relationship('Sale', back_populates='tenant', cascade='all, delete-orphan')
	customers = relationship(
		'Customer', back_populates='tenant', cascade='all, delete-orphan'
	)
	suppliers = relationship(
		'Supplier', back_populates='tenant', cascade='all, delete-orphan'
	)
	cash_sessions = relationship(
		'CashSession', back_populates='tenant', cascade='all, delete-orphan'
	)
	purchases = relationship(
		'Purchase', back_populates='tenant', cascade='all, delete-orphan'
	)


class User(Base):
	"""Usuarios que usan el sistema (Administradores o Cajeros)"""

	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	username = Column(String, unique=True, nullable=False)
	password_hash = Column(String, nullable=False)

	# --- FUTURO: Módulo de Permisos ---
	role = Column(String, default='cajero')  # Puede ser 'admin' o 'cajero'
	is_active = Column(Boolean, default=True)  # Borrado lógico de usuarios

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='users')

	sales = relationship('Sale', back_populates='user')
	cash_sessions = relationship('CashSession', back_populates='user')
	purchases = relationship('Purchase', back_populates='user')


# ==========================================
# TABLAS DE INVENTARIO Y CATÁLOGO
# ==========================================
class Category(Base):
	"""NUEVO: Para clasificar los productos y hacer reportes estadísticos"""

	__tablename__ = 'categories'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='categories')

	articles = relationship('Article', back_populates='category')


class Article(Base):
	"""Catálogo de productos"""

	__tablename__ = 'articles'
	id = Column(Integer, primary_key=True)
	barcode = Column(String, unique=True, nullable=True)
	description = Column(String, nullable=False)
	cost_price = Column(Float, nullable=False)
	price_1 = Column(Float, nullable=False)
	price_2 = Column(Float, nullable=True)
	price_3 = Column(Float, nullable=True)
	stock = Column(Integer, default=0)
	min_stock = Column(Integer, default=0)

	# --- FUTURO: Categorías e Impuestos ---
	category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
	category = relationship('Category', back_populates='articles')
	tax_rate = Column(
		Float, default=0.0
	)  # Por si en el futuro necesitas calcular IVA/Impuestos

	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='articles')

	sale_details = relationship('SaleDetail', back_populates='article')


# ==========================================
# TABLAS DE TERCEROS (CLIENTES Y PROVEEDORES)
# ==========================================
class Customer(Base):
	"""Directorio de clientes y cuentas corrientes"""

	__tablename__ = 'customers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	current_balance = Column(Float, default=0.0)

	# --- FUTURO: Datos extendidos de clientes ---
	email = Column(String, nullable=True)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)  # Borrado lógico

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='customers')

	sales = relationship('Sale', back_populates='customer')


class Supplier(Base):
	"""Directorio de proveedores"""

	__tablename__ = 'suppliers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)

	# --- FUTURO: Datos de contacto del proveedor ---
	phone = Column(String, nullable=True)
	email = Column(String, nullable=True)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)  # Borrado lógico

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='suppliers')

	purchases = relationship('Purchase', back_populates='supplier')


# ==========================================
# TABLAS DE VENTAS Y COMPRAS
# ==========================================
class Sale(Base):
	"""Cabecera de la venta (El ticket general)"""

	__tablename__ = 'sales'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, nullable=False)
	profit = Column(Float, nullable=False)

	# --- Control financiero detallado ---
	payment_method = Column(
		String, default='efectivo'
	)  # efectivo, tarjeta, transferencia, fiado
	status = Column(String, default='completada')  # completada, cancelada, pendiente

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='sales')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='sales')

	customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
	customer = relationship('Customer', back_populates='sales')

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)


class SaleDetail(Base):
	"""Detalle de cada artículo vendido en un ticket"""

	__tablename__ = 'sale_details'
	id = Column(Integer, primary_key=True)
	quantity = Column(Integer, nullable=False)
	unit_cost = Column(Float, nullable=False)
	unit_price = Column(Float, nullable=False)
	subtotal = Column(Float, nullable=False)
	description = Column(String, nullable=False)

	sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)
	sale = relationship('Sale', back_populates='items')

	article_id = Column(Integer, ForeignKey('articles.id'), nullable=True)
	article = relationship('Article', back_populates='sale_details')


class Purchase(Base):
	"""Registro de ingreso de mercadería a proveedores"""

	__tablename__ = 'purchases'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, nullable=False)

	# --- FUTURO: Control de facturas de proveedores ---
	invoice_number = Column(String, nullable=True)  # Número de factura del proveedor
	status = Column(String, default='pagada')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='purchases')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='purchases')

	supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
	supplier = relationship('Supplier', back_populates='purchases')


# ==========================================
# TABLAS DE CONTROL DE CAJA
# ==========================================
class CashSession(Base):
	"""Turnos de caja (Apertura y Cierre)"""

	__tablename__ = 'cash_sessions'
	id = Column(Integer, primary_key=True)
	opening_time = Column(DateTime, default=datetime.utcnow)
	closing_time = Column(DateTime, nullable=True)
	opening_balance = Column(Float, default=0.0)
	closing_balance = Column(Float, default=0.0)
	is_open = Column(Boolean, default=True)

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='cash_sessions')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='cash_sessions')

	movements = relationship(
		'CashMovement', back_populates='session', cascade='all, delete-orphan'
	)


class CashMovement(Base):
	"""Movimientos individuales de dinero (Ventas, Gastos, Ingresos)"""

	__tablename__ = 'cash_movements'
	id = Column(Integer, primary_key=True)
	movement_type = Column(String, nullable=False)  # 'ingreso', 'gasto', 'venta'
	amount = Column(Float, nullable=False)
	description = Column(String, nullable=True)
	time = Column(DateTime, default=datetime.utcnow)

	session_id = Column(Integer, ForeignKey('cash_sessions.id'), nullable=False)
	session = relationship('CashSession', back_populates='movements')


def init_db(database_url='sqlite:///pos_system.db'):
	"""
	Crea el motor de la base de datos y construye todas las tablas
	basadas en los modelos definidos arriba.
	"""
	# connect_args={'check_same_thread': False} es importante para SQLite en aplicaciones gráficas
	engine = create_engine(database_url, connect_args={'check_same_thread': False})

	# Esta línea lee todas las clases que heredan de "Base" y crea las tablas físicas
	Base.metadata.create_all(bind=engine)

	return engine
