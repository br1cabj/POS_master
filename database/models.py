import uuid
from datetime import datetime

from sqlalchemy import (
	Boolean,
	CheckConstraint,
	Column,
	Date,
	DateTime,
	ForeignKey,
	Index,
	Integer,
	Numeric,
	String,
	UniqueConstraint,
	text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ==========================================
# 1. NÚCLEO Y SEGURIDAD
# ==========================================
class Tenant(Base):
	__tablename__ = 'tenants'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	users = relationship('User', back_populates='tenant')
	branches = relationship('Branch', back_populates='tenant')
	articles = relationship('Article', back_populates='tenant')
	customers = relationship('Customer', back_populates='tenant')


class User(Base):
	__tablename__ = 'users'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	username = Column(String(100), nullable=False)
	password_hash = Column(String(255), nullable=False)
	recovery_pin_hash = Column(String(255), nullable=True)
	display_name = Column(String(200), nullable=True)
	role = Column(String(50), default='cajero')
	is_active = Column(Boolean, default=True)
	deleted_at = Column(DateTime, nullable=True)
	deleted_by = Column(
		String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
	)
	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
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
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	address = Column(String(500), nullable=True)
	is_active = Column(Boolean, default=True)
	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='branches')

	warehouses = relationship('Warehouse', back_populates='branch')


class Warehouse(Base):
	__tablename__ = 'warehouses'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	is_active = Column(Boolean, default=True)
	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', foreign_keys=[tenant_id])

	branch_id = Column(
		String(36), ForeignKey('branches.id'), nullable=False, index=True
	)
	branch = relationship('Branch', back_populates='warehouses')

	stocks = relationship('Stock', back_populates='warehouse')


# ==========================================
# 3. CATÁLOGO Y VARIANTES DE PRODUCTOS
# ==========================================
class Category(Base):
	__tablename__ = 'categories'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=True, index=True)
	updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)


class Supplier(Base):
	__tablename__ = 'suppliers'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False, index=True)
	phone = Column(String(30), nullable=True)
	email = Column(String(200), nullable=True)
	address = Column(String(500), nullable=True)
	is_active = Column(Boolean, default=True)
	deleted_at = Column(DateTime, nullable=True)
	deleted_by = Column(
		String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
	)
	deleted_by_user = relationship('User', foreign_keys=[deleted_by])

	discount_pct = Column(Numeric(5, 2), nullable=True)
	discount_until = Column(DateTime, nullable=True)
	credit_balance = Column(Numeric(10, 2), default=0.0)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	purchases = relationship('Purchase', back_populates='supplier')


class Article(Base):
	__tablename__ = 'articles'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False, index=True)
	description = Column(String(1000), nullable=True)

	min_stock = Column(Integer, default=0)
	requires_batch = Column(Boolean, default=False)
	requires_serial = Column(Boolean, default=False)
	has_variants = Column(Boolean, default=False)
	is_active = Column(Boolean, default=True)
	deleted_at = Column(DateTime, nullable=True)
	deleted_by = Column(
		String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
	)
	deleted_by_user = relationship('User', foreign_keys=[deleted_by])

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='articles')

	category_id = Column(String(36), ForeignKey('categories.id'), nullable=True, index=True)
	category = relationship('Category')

	supplier_id = Column(
		String(36), ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True, index=True
	)
	supplier = relationship('Supplier')

	variants = relationship(
		'ArticleVariant', back_populates='article', cascade='all, delete-orphan'
	)


class ArticleVariant(Base):
	__tablename__ = 'article_variants'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	barcode = Column(String(100), nullable=True, index=True)

	attribute_1 = Column(String(200), nullable=True)
	attribute_2 = Column(String(200), nullable=True)

	cost_price = Column(Numeric(10, 2), nullable=False)
	selling_price = Column(Numeric(10, 2), nullable=False)
	selling_price_b = Column(Numeric(10, 2), nullable=True, default=None)
	cost_price_usd = Column(Numeric(10, 4), nullable=True, default=None)
	is_active = Column(Boolean, default=True)
	deleted_at = Column(DateTime, nullable=True)

	is_combo = Column(Boolean, default=False)
	show_on_touch = Column(Boolean, default=False)
	btn_color = Column(String(20), default='#1f538d')

	units_per_pack = Column(Integer, default=1)
	pack_label = Column(String(100), nullable=True)
	base_variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=True, index=True
	)

	margin_pct = Column(Numeric(5, 2), nullable=True)
	discount_pct = Column(Numeric(5, 2), nullable=True)
	discount_until = Column(DateTime, nullable=True)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	article_id = Column(
		String(36), ForeignKey('articles.id'), nullable=False, index=True
	)
	article = relationship('Article', back_populates='variants')

	base_variant = relationship(
		'ArticleVariant',
		foreign_keys='ArticleVariant.base_variant_id',
		primaryjoin='ArticleVariant.base_variant_id == ArticleVariant.id',
	)

	stocks = relationship('Stock', back_populates='variant')
	sale_details = relationship('SaleDetail', back_populates='variant')

	__table_args__ = (
		CheckConstraint('cost_price >= 0', name='chk_cost_price_positive'),
		CheckConstraint('selling_price >= 0', name='chk_selling_price_positive'),
		# A barcode is the identifier consumed by scanners.  Keeping it unique
		# across active variants avoids an ambiguous sale when two catalog entries
		# are accidentally assigned the same code.  NULL/blank values remain valid
		# while a product is being drafted.
		Index(
			'uq_article_variants_active_barcode',
			'barcode',
			unique=True,
			sqlite_where=text("barcode IS NOT NULL AND barcode <> '' AND is_active = 1"),
			postgresql_where=text("barcode IS NOT NULL AND barcode <> '' AND is_active"),
		),
	)


class ArticleHistory(Base):
	__tablename__ = 'article_history'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	date = Column(DateTime, default=datetime.now, index=True)
	updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)
	user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	action_type = Column(String(50), nullable=False)
	article_name = Column(String(200), nullable=False)
	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=True, index=True
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
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	quantity = Column(Numeric(12, 4), default=0.0)

	batch_number = Column(String(100), nullable=True, index=True)
	expiration_date = Column(Date, nullable=True)
	serial_number = Column(String(200), unique=True, nullable=True)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	warehouse_id = Column(
		String(36), ForeignKey('warehouses.id'), nullable=False, index=True
	)
	warehouse = relationship('Warehouse', back_populates='stocks')

	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=False, index=True
	)
	variant = relationship('ArticleVariant', back_populates='stocks')

	__table_args__ = (
		CheckConstraint('quantity >= 0', name='chk_stock_quantity_positive'),
		UniqueConstraint(
			'variant_id', 'warehouse_id', 'batch_number',
			name='uq_stock_variant_warehouse_batch'
		),
	)


class StockMovement(Base):
	__tablename__ = 'stock_movements'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=datetime.now, index=True)
	updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

	movement_type = Column(String(50), nullable=False)
	quantity = Column(Numeric(12, 4), nullable=False)
	reference = Column(String(200), nullable=True)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=True, index=True)
	source_warehouse_id = Column(
		String(36), ForeignKey('warehouses.id'), nullable=True, index=True
	)
	dest_warehouse_id = Column(
		String(36), ForeignKey('warehouses.id'), nullable=True, index=True
	)

	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=False, index=True
	)
	variant = relationship('ArticleVariant')

	user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
	user = relationship('User', back_populates='stock_movements')

	__table_args__ = (
		CheckConstraint('quantity > 0', name='chk_movement_qty_positive'),
	)


# ==========================================
# 5. VENTAS, CLIENTES Y CAJA
# ==========================================
class Customer(Base):
	__tablename__ = 'customers'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	phone = Column(String(30), nullable=True)
	current_balance = Column(Numeric(10, 2), default=0.0)
	price_list = Column(String(10), default='A')
	is_active = Column(Boolean, default=True)
	deleted_at = Column(DateTime, nullable=True)
	deleted_by = Column(
		String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
	)
	deleted_by_user = relationship('User', foreign_keys=[deleted_by])

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='customers')

	sales = relationship('Sale', back_populates='customer')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'name', name='uq_customer_tenant_name'),
	)


class Sale(Base):
	__tablename__ = 'sales'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=datetime.now, index=True)
	total_amount = Column(Numeric(10, 2), nullable=False)
	discount_amount = Column(Numeric(10, 2), default=0.0)
	amount_method_2 = Column(Numeric(10, 2), nullable=True)
	# amount_method_1 almacena el monto del primer método en pagos mixtos.
	# Evita reconstruirlo desde descripciones de CashMovement en devoluciones.
	amount_method_1 = Column(Numeric(10, 2), nullable=True)
	# total_returned acumula el monto ya devuelto. No mutar total_amount.
	total_returned = Column(Numeric(10, 2), nullable=False, default=0.0)
	profit = Column(Numeric(10, 2), nullable=False)
	payment_method = Column(String(50), default='efectivo')
	payment_method_2 = Column(String(50), nullable=True)
	status = Column(String(50), default='completada', index=True)
	quotation_number = Column(String(50), nullable=True)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
	user = relationship('User', back_populates='sales')

	customer_id = Column(
		String(36), ForeignKey('customers.id'), nullable=True, index=True
	)
	customer = relationship('Customer', back_populates='sales')

	items = relationship(
		'SaleDetail', back_populates='sale', cascade='all, delete-orphan'
	)

	__table_args__ = (
		Index('ix_sale_tenant_status', 'tenant_id', 'status'),
		Index('ix_sale_tenant_status_date', 'tenant_id', 'status', 'date'),
		CheckConstraint('total_amount >= 0', name='chk_sale_total_positive'),
		CheckConstraint('discount_amount >= 0', name='chk_sale_discount_positive'),
		CheckConstraint('total_returned >= 0', name='chk_sale_total_returned_positive'),
		CheckConstraint('total_returned <= total_amount', name='chk_sale_returned_lte_total'),
	)


class SaleDetail(Base):
	__tablename__ = 'sale_details'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	unit_price = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)
	returned_quantity = Column(Numeric(12, 4), nullable=False, default=0.0)

	# updated_at doubles as created_at for this append-only table
	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	sale_id = Column(String(36), ForeignKey('sales.id'), nullable=False, index=True)
	sale = relationship('Sale', back_populates='items')

	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=True, index=True
	)
	variant = relationship('ArticleVariant', back_populates='sale_details')


class CashSession(Base):
	__tablename__ = 'cash_sessions'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	opened_at = Column(DateTime, default=datetime.now)
	closed_at = Column(DateTime, nullable=True)
	is_open = Column(Boolean, default=True)

	opening_balance = Column(Numeric(10, 2), default=0.0)
	closing_balance = Column(Numeric(10, 2), default=0.0)

	expected_amount = Column(Numeric(10, 2), nullable=True)
	declared_amount = Column(Numeric(10, 2), nullable=True)
	difference = Column(Numeric(10, 2), nullable=True)

	updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

	user = relationship('User')
	movements = relationship(
		'CashMovement', back_populates='session', cascade='all, delete-orphan'
	)


class CashMovement(Base):
	__tablename__ = 'cash_movements'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	movement_type = Column(String(50), nullable=False)
	amount = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=True)
	time = Column(DateTime, default=datetime.now)
	updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

	session_id = Column(
		String(36), ForeignKey('cash_sessions.id'), nullable=False, index=True
	)
	session = relationship('CashSession', back_populates='movements')

	# FK directa al cliente — evita búsquedas frágiles por texto en get_customer_ledger
	customer_id = Column(String(36), ForeignKey('customers.id'), nullable=True, index=True)
	customer = relationship('Customer', foreign_keys=[customer_id])

	__table_args__ = (
		CheckConstraint('amount > 0', name='chk_cash_amount_positive'),
		Index('ix_cash_mov_session_time', 'session_id', 'time'),
	)


# ==========================================
# 6. COMPRAS Y PROVEEDORES
# ==========================================
class Purchase(Base):
	__tablename__ = 'purchases'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=datetime.now, index=True)
	total_amount = Column(Numeric(10, 2), nullable=False)
	invoice_number = Column(String(100), nullable=True)
	status = Column(String(50), default='pagada')

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)

	supplier_id = Column(
		String(36), ForeignKey('suppliers.id'), nullable=True, index=True
	)
	supplier = relationship('Supplier', back_populates='purchases')

	items = relationship(
		'PurchaseDetail', back_populates='purchase', cascade='all, delete-orphan'
	)
	returns = relationship(
		'PurchaseReturn', back_populates='purchase', cascade='all, delete-orphan'
	)


class PurchaseDetail(Base):
	__tablename__ = 'purchase_details'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	purchase_id = Column(
		String(36), ForeignKey('purchases.id'), nullable=False, index=True
	)
	purchase = relationship('Purchase', back_populates='items')

	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=True, index=True
	)
	variant = relationship('ArticleVariant')


class PurchaseReturn(Base):
	__tablename__ = 'purchase_returns'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=datetime.now, index=True)
	reason = Column(String(200), nullable=False)
	refund_type = Column(String(50), nullable=False)
	total_refund = Column(Numeric(10, 2), nullable=False)
	notes = Column(String(1000), nullable=True)
	file_path = Column(String(500), nullable=True)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	purchase_id = Column(
		String(36), ForeignKey('purchases.id'), nullable=False, index=True
	)
	purchase = relationship('Purchase', back_populates='returns')

	user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	items = relationship(
		'PurchaseReturnItem',
		back_populates='purchase_return',
		cascade='all, delete-orphan',
	)


class PurchaseReturnItem(Base):
	__tablename__ = 'purchase_return_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	quantity_returned = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	purchase_return_id = Column(
		String(36), ForeignKey('purchase_returns.id'), nullable=False, index=True
	)
	purchase_return = relationship('PurchaseReturn', back_populates='items')

	purchase_detail_id = Column(
		String(36), ForeignKey('purchase_details.id'), nullable=True, index=True
	)
	variant_id = Column(String(36), ForeignKey('article_variants.id'), nullable=True)
	variant = relationship('ArticleVariant')


class ComboItem(Base):
	__tablename__ = 'combo_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	combo_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=False, index=True
	)
	ingredient_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=False, index=True
	)
	quantity_required = Column(Numeric(12, 4), nullable=False)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	combo = relationship(
		'ArticleVariant', foreign_keys=[combo_id], backref='ingredients'
	)
	ingredient = relationship('ArticleVariant', foreign_keys=[ingredient_id])

	__table_args__ = (
		UniqueConstraint('combo_id', 'ingredient_id', name='uq_combo_ingredient'),
		CheckConstraint('quantity_required > 0', name='chk_combo_qty_positive'),
	)


# ==========================================
# 7. COTIZACIONES / PRESUPUESTOS
# ==========================================
class Quotation(Base):
	__tablename__ = 'quotations'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	number = Column(String(50), nullable=False)
	date = Column(DateTime, default=datetime.now, index=True)
	valid_until = Column(Date, nullable=True)
	status = Column(String(50), default='borrador')

	total_amount = Column(Numeric(10, 2), nullable=False, default=0)
	discount_amount = Column(Numeric(10, 2), default=0)
	notes = Column(String(1000), nullable=True)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
	customer_id = Column(
		String(36), ForeignKey('customers.id'), nullable=True, index=True
	)

	user = relationship('User')
	customer = relationship('Customer')
	items = relationship(
		'QuotationItem', back_populates='quotation', cascade='all, delete-orphan'
	)

	__table_args__ = (
		UniqueConstraint('tenant_id', 'number', name='uix_tenant_quotation_number'),
	)


class QuotationItem(Base):
	__tablename__ = 'quotation_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	description = Column(String(500), nullable=False)
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_price = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	quotation_id = Column(
		String(36), ForeignKey('quotations.id'), nullable=False, index=True
	)
	quotation = relationship('Quotation', back_populates='items')

	variant_id = Column(String(36), ForeignKey('article_variants.id'), nullable=True)
	variant = relationship('ArticleVariant')


# ==========================================
# 8. PROMOCIONES CON VIGENCIA
# ==========================================
class Promotion(Base):
	__tablename__ = 'promotions'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	name = Column(String(200), nullable=False)
	is_active = Column(Boolean, default=True)

	# 'pct' = descuento %, 'nxm' = lleva N paga M, 'fixed' = precio fijo especial
	promo_type = Column(String(50), nullable=False)
	discount_value = Column(
		Numeric(10, 2), nullable=True
	)  # % para pct, precio para fixed
	buy_qty = Column(Integer, nullable=True)  # N en NxM
	pay_qty = Column(Integer, nullable=True)  # M en NxM

	variant_id = Column(
		String(36), ForeignKey('article_variants.id'), nullable=True, index=True
	)
	category_id = Column(
		String(36), ForeignKey('categories.id'), nullable=True, index=True
	)

	date_from = Column(DateTime, nullable=False)
	date_to = Column(DateTime, nullable=False)
	# "0,1,2,3,4,5,6" donde 0=Lunes (Python weekday)
	days_of_week = Column(String(20), nullable=True)
	time_from = Column(String(10), nullable=True)  # "HH:MM"
	time_to = Column(String(10), nullable=True)  # "HH:MM"

	updated_at = Column(
		DateTime, default=datetime.now, onupdate=datetime.now, index=True
	)

	variant = relationship('ArticleVariant', foreign_keys=[variant_id])
	category = relationship('Category', foreign_keys=[category_id])
