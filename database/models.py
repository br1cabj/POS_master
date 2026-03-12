# database/models.py
from datetime import datetime

from sqlalchemy import (
	Boolean,
	Column,
	Date,
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
# 1. NÚCLEO Y SEGURIDAD
# ==========================================
class Tenant(Base):
	__tablename__ = 'tenants'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)

	users = relationship('User', back_populates='tenant')
	branches = relationship('Branch', back_populates='tenant')
	articles = relationship('Article', back_populates='tenant')
	customers = relationship('Customer', back_populates='tenant')


class User(Base):
	__tablename__ = 'users'
	id = Column(Integer, primary_key=True)
	username = Column(String, unique=True, nullable=False)
	password_hash = Column(String, nullable=False)
	role = Column(String, default='cajero')
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='users')

	sales = relationship('Sale', back_populates='user')
	stock_movements = relationship('StockMovement', back_populates='user')


# ==========================================
# 2. LOGÍSTICA: SUCURSALES Y ALMACENES
# ==========================================
class Branch(Base):
	"""Sucursales del negocio (Ej: Sucursal Centro, Sucursal Norte)"""

	__tablename__ = 'branches'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='branches')

	warehouses = relationship('Warehouse', back_populates='branch')


class Warehouse(Base):
	"""Almacenes dentro de una sucursal (Ej: Salón Principal, Depósito, Mostrador)"""

	__tablename__ = 'warehouses'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	is_active = Column(Boolean, default=True)

	branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False)
	branch = relationship('Branch', back_populates='warehouses')

	stocks = relationship('Stock', back_populates='warehouse')


# ==========================================
# 3. CATÁLOGO Y VARIANTES DE PRODUCTOS
# ==========================================
class Category(Base):
	__tablename__ = 'categories'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)


class Article(Base):
	"""Plantilla general del producto (Ej: Camiseta de Algodón)"""

	__tablename__ = 'articles'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	description = Column(String, nullable=True)

	# --- CONFIGURACIONES AVANZADAS DE INVENTARIO ---
	min_stock = Column(Integer, default=0)  # Alerta de stock mínimo
	requires_batch = Column(
		Boolean, default=False
	)  # Para Farmacias/Alimentos (Lote y Vencimiento)
	requires_serial = Column(
		Boolean, default=False
	)  # Para Electrónica (Números de serie únicos)
	has_variants = Column(Boolean, default=False)  # Para Ropa (Tallas/Colores)

	is_active = Column(Boolean, default=True)
	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='articles')

	category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)

	variants = relationship(
		'ArticleVariant', back_populates='article', cascade='all, delete-orphan'
	)


class ArticleVariant(Base):
	"""El producto real vendible (Ej: Camiseta - Roja - Talla M)"""

	__tablename__ = 'article_variants'
	id = Column(Integer, primary_key=True)
	barcode = Column(String, unique=True, nullable=True)

	# Atributos (Si es kiosco, estos quedan vacíos. Si es ropa, aquí va "Rojo" y "M")
	attribute_1 = Column(String, nullable=True)  # Ej: Talla
	attribute_2 = Column(String, nullable=True)  # Ej: Color

	cost_price = Column(Float, nullable=False)
	selling_price = Column(Float, nullable=False)
	is_active = Column(Boolean, default=True)

	article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
	article = relationship('Article', back_populates='variants')

	stocks = relationship('Stock', back_populates='variant')
	sale_details = relationship('SaleDetail', back_populates='variant')


# ==========================================
# 4. CONTROL DE STOCK E HISTORIAL (KARDEX)
# ==========================================
class Stock(Base):
	"""Donde vive la cantidad real de mercadería separada por ubicación y lote"""

	__tablename__ = 'stocks'
	id = Column(Integer, primary_key=True)
	quantity = Column(
		Float, default=0.0
	)  # Float para permitir ventas a granel (Ej: 1.5 Kg)

	# Datos de trazabilidad (Opcionales)
	batch_number = Column(String, nullable=True)  # Número de Lote
	expiration_date = Column(Date, nullable=True)  # Fecha de vencimiento
	serial_number = Column(String, unique=True, nullable=True)  # Serial único

	warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=False)
	warehouse = relationship('Warehouse', back_populates='stocks')

	variant_id = Column(Integer, ForeignKey('article_variants.id'), nullable=False)
	variant = relationship('ArticleVariant', back_populates='stocks')


class StockMovement(Base):
	"""Historial inmutable de todo lo que pasa con el inventario"""

	__tablename__ = 'stock_movements'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)

	# Tipos: 'in' (compra), 'out' (venta), 'transfer' (traslado), 'adjustment' (ajuste manual/conteo)
	movement_type = Column(String, nullable=False)
	quantity = Column(Float, nullable=False)
	reference = Column(
		String, nullable=True
	)  # Ej: "Venta Ticket #105" o "Merma por rotura"

	# Para transferencias, de dónde sale y a dónde va
	source_warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=True)
	dest_warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=True)

	variant_id = Column(Integer, ForeignKey('article_variants.id'), nullable=False)

	variant = relationship('ArticleVariant')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='stock_movements')


# ==========================================
# 5. VENTAS, CLIENTES Y CAJA (Adaptados a las Variantes)
# ==========================================
class Customer(Base):
	__tablename__ = 'customers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	current_balance = Column(Float, default=0.0)
	is_active = Column(Boolean, default=True)
	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='customers')


class Sale(Base):
	__tablename__ = 'sales'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, nullable=False)
	profit = Column(Float, nullable=False)
	payment_method = Column(String, default='efectivo')
	status = Column(String, default='completada')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='sales')
	customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)


class SaleDetail(Base):
	__tablename__ = 'sale_details'
	id = Column(Integer, primary_key=True)
	quantity = Column(Float, nullable=False)
	unit_cost = Column(Float, nullable=False)
	unit_price = Column(Float, nullable=False)
	subtotal = Column(Float, nullable=False)
	description = Column(String, nullable=False)

	sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)
	sale = relationship('Sale', back_populates='items')

	# Ahora la venta se enlaza a la Variante específica, no al artículo general
	variant_id = Column(Integer, ForeignKey('article_variants.id'), nullable=True)
	variant = relationship('ArticleVariant', back_populates='sale_details')


class CashSession(Base):
	__tablename__ = 'cash_sessions'
	id = Column(Integer, primary_key=True)
	opening_time = Column(DateTime, default=datetime.utcnow)
	closing_time = Column(DateTime, nullable=True)
	opening_balance = Column(Float, default=0.0)
	closing_balance = Column(Float, default=0.0)
	is_open = Column(Boolean, default=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)


class CashMovement(Base):
	__tablename__ = 'cash_movements'
	id = Column(Integer, primary_key=True)
	movement_type = Column(String, nullable=False)
	amount = Column(Float, nullable=False)
	description = Column(String, nullable=True)
	time = Column(DateTime, default=datetime.utcnow)
	session_id = Column(Integer, ForeignKey('cash_sessions.id'), nullable=False)


# ==========================================
# 6. COMPRAS Y PROVEEDORES
# ==========================================
class Supplier(Base):
	"""Directorio de proveedores para reabastecer el inventario"""

	__tablename__ = 'suppliers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	email = Column(String, nullable=True)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)

	purchases = relationship('Purchase', back_populates='supplier')


class Purchase(Base):
	"""Registro de ingreso de mercadería comprada a proveedores"""

	__tablename__ = 'purchases'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, nullable=False)
	invoice_number = Column(String, nullable=True)
	status = Column(String, default='pagada')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

	supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True)
	supplier = relationship('Supplier', back_populates='purchases')


# ==========================================
# CONFIGURACIÓN DEL MOTOR
# ==========================================


def init_db(database_url='sqlite:///pos_system.db'):
	engine = create_engine(database_url, connect_args={'check_same_thread': False})
	Base.metadata.create_all(bind=engine)
	return engine
