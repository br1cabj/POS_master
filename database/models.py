from datetime import datetime

from sqlalchemy import (
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


# --- Modelo EMPRESA ---
class Tenant(Base):
	__tablename__ = 'tenants'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	subscription_status = Column(String, default='active')
	created_at = Column(DateTime, default=datetime.utcnow)

	users = relationship('User', back_populates='tenant')
	products = relationship('Product', back_populates='tenant')
	sales = relationship('Sale', back_populates='tenant')


# --- Modelo USUARIO ---
class User(Base):
	__tablename__ = 'users'

	id = Column(Integer, primary_key=True)
	username = Column(String, unique=True, nullable=False)
	password_hash = Column(String, nullable=False)
	role = Column(String, default='cajero')

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='users')
	sales = relationship('Sale', back_populates='user')


# --- Modelo PRODUCTO ---
class Product(Base):
	__tablename__ = 'products'

	id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False)
	price = Column(Float, nullable=False)
	stock = Column(Integer, default=0)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	tenant = relationship('Tenant', back_populates='products')


# --- Modelo VENTA
class Sale(Base):
	__tablename__ = 'sales'

	id = Column(Integer, primary_key=True)
	total_amount = Column(Float, default=0.0)
	date = Column(DateTime, default=datetime.utcnow)

	tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

	tenant = relationship('Tenant', back_populates='sales')
	user = relationship('User', back_populates='sales')

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)


# --- Modelo DETALLE VENTAS
class SaleDetail(Base):
	__tablename__ = 'sale_details'

	id = Column(Integer, primary_key=True)
	sale_id = Column(Integer, ForeignKey('sales.id'), nullable=False)
	product_name = Column(
		String
	)  # Guardamos el nombre por si borran el producto original
	quantity = Column(Integer, nullable=False)
	unit_price = Column(Float, nullable=False)
	subtotal = Column(Float, nullable=False)

	sale = relationship('Sale', back_populates='items')


def init_db(db_name='pos_system.db'):
	engine = create_engine(f'sqlite:///{db_name}')
	Base.metadata.create_all(engine)
	return engine
