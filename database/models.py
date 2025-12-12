# database/models.py
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# --- Modelo Empresa ---
class Tenant(Base):
  __tablename__ = 'tenants'

  id = Column(Integer, primary_key=True)
  name = Column(String, nullable=False)
  subscription_status = Column(String, default="active")
  created_at = Column(DateTime, default=datetime.utcnow)
  users = relationship("User", back_populates="tenant")
  products = relationship("Product", back_populates="tenant")

# --- Modelo Usuario ---
class User(Base): 
  __tablename__ = 'users'

  id = Column(Integer, primary_key=True)
  username = Column(String, unique=True, nullable=False)
  password_hash = Column(String, nullable=False) 
  role = Column(String, default="cajero") 
    
  # Multitenancy
  tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
  tenant = relationship("Tenant", back_populates="users")

# --- Modelo Producto ---

class Product(Base):
  __tablename__ = 'products'

  id = Column(Integer, primary_key=True)
  name = Column(String, nullable=False)
  price = Column(Float, nullable=False)
  stock = Column(Integer, default=0)
    
  # Multitenancy
  tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
  tenant = relationship("Tenant", back_populates="products")

# --- INIT DB (PRUEBA)
def init_db(db_name='pos_system.db'):
  engine = create_engine(f'sqlite:///{db_name}', echo=True)
  Base.metadata.create_all(engine)
  return engine