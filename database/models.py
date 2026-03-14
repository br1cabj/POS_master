from datetime import datetime

from sqlalchemy import (
	Boolean,
	CheckConstraint,
	Column,
	Date,
	DateTime,
	ForeignKey,
	Integer,
	Numeric,
	String,
	UniqueConstraint,
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

	username = Column(String, nullable=False)
	password_hash = Column(String, nullable=False)
	role = Column(String, default='cajero')
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='users')

	sales = relationship('Sale', back_populates='user')
	stock_movements = relationship('StockMovement', back_populates='user')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'username', name='uix_tenant_username'),
	)


# ==========================================
# 2. LOGÍSTICA: SUCURSALES Y ALMACENES
# ==========================================
class Branch(Base):
	__tablename__ = 'branches'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='branches')

	warehouses = relationship('Warehouse', back_populates='branch')


class Warehouse(Base):
	__tablename__ = 'warehouses'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	is_active = Column(Boolean, default=True)

	branch_id = Column(Integer, ForeignKey('branches.id'), nullable=False, index=True)
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
	__tablename__ = 'articles'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	description = Column(String, nullable=True)

	min_stock = Column(Integer, default=0)
	requires_batch = Column(Boolean, default=False)
	requires_serial = Column(Boolean, default=False)
	has_variants = Column(Boolean, default=False)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='articles')

	category_id = Column(Integer, ForeignKey('categories.id'), nullable=True)

	supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True, index=True)
	supplier = relationship('Supplier')

	# El borrado en cascada aquí está bien porque borrar un artículo padre lógicamente
	variants = relationship(
		'ArticleVariant', back_populates='article', cascade='all, delete-orphan'
	)


class ArticleVariant(Base):
	__tablename__ = 'article_variants'
	id = Column(Integer, primary_key=True)

	barcode = Column(String, nullable=True, index=True)

	attribute_1 = Column(String, nullable=True)
	attribute_2 = Column(String, nullable=True)

	cost_price = Column(Numeric(10, 2), nullable=False)
	selling_price = Column(Numeric(10, 2), nullable=False)
	is_active = Column(Boolean, default=True)

	article_id = Column(Integer, ForeignKey('articles.id'), nullable=False, index=True)
	article = relationship('Article', back_populates='variants')

	stocks = relationship('Stock', back_populates='variant')
	sale_details = relationship('SaleDetail', back_populates='variant')

	is_combo = Column(Boolean, default=False)
	show_on_touch = Column(Boolean, default=False)
	btn_color = Column(String, default='#1f538d')

	__table_args__ = (
		CheckConstraint('cost_price >= 0', name='chk_cost_price_positive'),
		CheckConstraint('selling_price >= 0', name='chk_selling_price_positive'),
	)


class ArticleHistory(Base):
	__tablename__ = 'article_history'
	id = Column(Integer, primary_key=True)

	date = Column(DateTime, default=datetime.utcnow, index=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)

	action_type = Column(
		String, nullable=False
	)  # Ej: 'CREACIÓN', 'EDICIÓN MANUAL', 'AUMENTO MASIVO', 'ELIMINACIÓN'
	article_name = Column(String, nullable=False)
	variant_id = Column(
		Integer, ForeignKey('article_variants.id'), nullable=True, index=True
	)

	old_cost = Column(Numeric(10, 2), nullable=True)
	new_cost = Column(Numeric(10, 2), nullable=True)
	old_price = Column(Numeric(10, 2), nullable=True)
	new_price = Column(Numeric(10, 2), nullable=True)

	user = relationship('User')


# ==========================================
# 4. CONTROL DE STOCK E HISTORIAL
# ==========================================
class Stock(Base):
	__tablename__ = 'stocks'
	id = Column(Integer, primary_key=True)

	quantity = Column(Numeric(12, 4), default=0.0)

	batch_number = Column(String, nullable=True, index=True)
	expiration_date = Column(Date, nullable=True)
	serial_number = Column(String, unique=True, nullable=True)

	warehouse_id = Column(
		Integer, ForeignKey('warehouses.id'), nullable=False, index=True
	)
	warehouse = relationship('Warehouse', back_populates='stocks')

	variant_id = Column(
		Integer, ForeignKey('article_variants.id'), nullable=False, index=True
	)
	variant = relationship('ArticleVariant', back_populates='stocks')

	__table_args__ = (
		CheckConstraint('quantity >= 0', name='chk_stock_quantity_positive'),
	)


class StockMovement(Base):
	__tablename__ = 'stock_movements'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow, index=True)

	movement_type = Column(String, nullable=False)
	quantity = Column(Numeric(12, 4), nullable=False)
	reference = Column(String, nullable=True)

	source_warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=True)
	dest_warehouse_id = Column(Integer, ForeignKey('warehouses.id'), nullable=True)

	variant_id = Column(
		Integer, ForeignKey('article_variants.id'), nullable=False, index=True
	)
	variant = relationship('ArticleVariant')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='stock_movements')

	__table_args__ = (
		CheckConstraint('quantity > 0', name='chk_movement_qty_positive'),
	)


# ==========================================
# 5. VENTAS, CLIENTES Y CAJA
# ==========================================
class Customer(Base):
	__tablename__ = 'customers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	current_balance = Column(
		Numeric(10, 2), default=0.0
	)  # Aquí sí permitimos negativos por si hay saldo a favor
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='customers')

	sales = relationship('Sale', back_populates='customer')


class Sale(Base):
	__tablename__ = 'sales'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow, index=True)
	total_amount = Column(Numeric(10, 2), nullable=False)
	profit = Column(Numeric(10, 2), nullable=False)
	payment_method = Column(String, default='efectivo')
	status = Column(String, default='completada')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	user = relationship('User', back_populates='sales')

	customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
	customer = relationship('Customer', back_populates='sales')

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)


class SaleDetail(Base):
	__tablename__ = 'sale_details'
	id = Column(Integer, primary_key=True)
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	unit_price = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String, nullable=False)

	sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False, index=True)
	sale = relationship('Sale', back_populates='items')

	variant_id = Column(Integer, ForeignKey('article_variants.id'), nullable=True)
	variant = relationship('ArticleVariant', back_populates='sale_details')


class CashSession(Base):
	__tablename__ = 'cash_sessions'
	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)

	opened_at = Column(DateTime, default=datetime.utcnow)
	closed_at = Column(DateTime, nullable=True)
	is_open = Column(Boolean, default=True)

	opening_balance = Column(Numeric(10, 2), default=0.0)
	closing_balance = Column(Numeric(10, 2), default=0.0)

	expected_amount = Column(Numeric(10, 2), nullable=True)
	declared_amount = Column(Numeric(10, 2), nullable=True)
	difference = Column(Numeric(10, 2), nullable=True)

	user = relationship('User')
	movements = relationship('CashMovement', back_populates='session')


class CashMovement(Base):
	__tablename__ = 'cash_movements'
	id = Column(Integer, primary_key=True)
	movement_type = Column(String, nullable=False)
	amount = Column(Numeric(10, 2), nullable=False)
	description = Column(String, nullable=True)
	time = Column(DateTime, default=datetime.utcnow)

	session_id = Column(
		Integer, ForeignKey('cash_sessions.id'), nullable=False, index=True
	)
	session = relationship('CashSession', back_populates='movements')

	__table_args__ = (CheckConstraint('amount > 0', name='chk_cash_amount_positive'),)


# ==========================================
# 6. COMPRAS Y PROVEEDORES
# ==========================================
class Supplier(Base):
	__tablename__ = 'suppliers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	email = Column(String, nullable=True)
	address = Column(String, nullable=True)
	is_active = Column(Boolean, default=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	purchases = relationship('Purchase', back_populates='supplier')


class Purchase(Base):
	__tablename__ = 'purchases'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow, index=True)
	total_amount = Column(Numeric(10, 2), nullable=False)
	invoice_number = Column(String, nullable=True)
	status = Column(String, default='pagada')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

	supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=True, index=True)
	supplier = relationship('Supplier', back_populates='purchases')


class ComboItem(Base):
	__tablename__ = 'combo_items'
	id = Column(Integer, primary_key=True)

	combo_id = Column(
		Integer, ForeignKey('article_variants.id'), nullable=False, index=True
	)

	ingredient_id = Column(Integer, ForeignKey('article_variants.id'), nullable=False)

	quantity_required = Column(Numeric(12, 4), nullable=False)

	combo = relationship(
		'ArticleVariant', foreign_keys=[combo_id], backref='ingredients'
	)
	ingredient = relationship('ArticleVariant', foreign_keys=[ingredient_id])


# ==========================================
# CONFIGURACIÓN DEL MOTOR
# ==========================================
def init_db(database_url='sqlite:///pos_system.db'):
	engine = create_engine(database_url, connect_args={'check_same_thread': False})
	Base.metadata.create_all(bind=engine)
	return engine
