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

# ==============================================================
# MULTITENANT(tenants, users)


# --- Modelo TENANT ---
class Tenant(Base):
	__tablename__ = 'tenants'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	subscription_status = Column(String, default='active')
	created_at = Column(DateTime, default=datetime.utcnow)

	users = relationship('User', back_populates='tenant')
	articles = relationship('Article', back_populates='tenant')
	customers = relationship('Customer', back_populates='tenant')
	suppliers = relationship('Supplier', back_populates='tenant')
	sales = relationship('Sale', back_populates='tenant')
	purchases = relationship('Purchase', back_populates='tenant')
	cash_sessions = relationship('CashSession', back_populates='tenant')


# --- Modelo USER ---
class User(Base):
	__tablename__ = 'users'

	id = Column(Integer, primary_key=True)
	username = Column(String, unique=True, nullable=False)
	password_hash = Column(String, nullable=False)
	role = Column(String, default='cajero')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='users')

	sales = relationship('Sale', back_populates='user')
	purchases = relationship('Purchase', back_populates='user')
	cash_sessions = relationship('CashSession', back_populates='user')


# ==============================================================
# CATALOG(article, customers,supplier)


# --- Modelo ARTICLE ---
class Article(Base):
	__tablename__ = 'articles'
	id = Column(Integer, primary_key=True)
	barcode = Column(String, unique=True, nullable=False)
	description = Column(String, nullable=False)

	cost_price = Column(Float, default=0.0)
	price_1 = Column(Float, nullable=False)
	price_2 = Column(Float, default=0.0)
	price_3 = Column(Float, default=0.0)

	stock = Column(Integer, default=0)
	min_stock = Column(Integer, default=5)

	image_path = Column(String, nullable=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='articles')


# --- Modelo CUSTOMER ---
class Customer(Base):
	__tablename__ = 'customers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)

	current_balance = Column(Float, default=0.0)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='customers')
	sales = relationship('Sale', back_populates='customer')


# --- Modelo Supplier
class Supplier(Base):
	__tablename__ = 'suppliers'
	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='suppliers')
	purchases = relationship('Purchase', back_populates='supplier')


# ==============================================================
# TRANSACTIONS(sale, purchase)


# --- Modelo Sale
class Sale(Base):
	__tablename__ = 'sales'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, default=0.0)
	profit = Column(Float, default=0.0)

	customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
	customer = relationship('Customer', back_populates='sales')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='sales')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='sales')

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)


class SaleDetail(Base):
	__tablename__ = 'sale_details'
	id = Column(Integer, primary_key=True)
	sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)

	article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
	description = Column(String)

	quantity = Column(Integer, nullable=False)
	unit_cost = Column(Float, nullable=False)
	unit_price = Column(Float, nullable=False)
	subtotal = Column(Float, nullable=False)

	sale = relationship('Sale', back_populates='items')


# --- Modelo Purchase ---
class Purchase(Base):
	__tablename__ = 'purchases'
	id = Column(Integer, primary_key=True)
	date = Column(DateTime, default=datetime.utcnow)
	total_amount = Column(Float, default=0.0)

	supplier_id = Column(Integer, ForeignKey('suppliers.id'), nullable=False)
	supplier = relationship('Supplier', back_populates='purchases')

	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='purchases')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='purchases')


# ==============================================================
#  FINANCES (Session, Movements)


# --- Modelo CashSession ---
class CashSession(Base):
	__tablename__ = 'cash_sessions'
	id = Column(Integer, primary_key=True)
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


# --- Modelo CashMovement
class CashMovement(Base):
	__tablename__ = 'cash_movements'
	id = Column(Integer, primary_key=True)
	session_id = Column(Integer, ForeignKey('cash_sessions.id'), nullable=False)

	movement_type = Column(String, nullable=False)
	amount = Column(Float, nullable=False)
	description = Column(String, nullable=True)
	date = Column(DateTime, default=datetime.utcnow)

	session = relationship('CashSession', back_populates='movements')


# --- INIT ---
def init_db(db_name='pos_system.db'):
	engine = create_engine(f'sqlite:///{db_name}')
	Base.metadata.create_all(engine)
	return engine
