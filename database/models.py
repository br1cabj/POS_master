import uuid
from datetime import datetime, timezone

from sqlalchemy import (
	Boolean,
	CheckConstraint,
	Column,
	Date,
	DateTime,
	ForeignKey,
	ForeignKeyConstraint,
	Index,
	Integer,
	Numeric,
	String,
	UniqueConstraint,
	text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
	"""Return a naive UTC timestamp portable between SQLite and PostgreSQL."""
	return datetime.now(timezone.utc).replace(tzinfo=None)


# ==========================================
# 1. NÚCLEO Y SEGURIDAD
# ==========================================
class Tenant(Base):
	__tablename__ = 'tenants'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='users')

	sales = relationship('Sale', back_populates='user')
	stock_movements = relationship('StockMovement', back_populates='user')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'username', name='uix_tenant_username'),
		UniqueConstraint('tenant_id', 'id', name='uq_users_tenant_id'),
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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='branches')

	warehouses = relationship('Warehouse', back_populates='branch')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'id', name='uq_branches_tenant_id'),
		UniqueConstraint('tenant_id', 'name', name='uq_branch_tenant_name'),
	)


class Warehouse(Base):
	__tablename__ = 'warehouses'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False)
	is_active = Column(Boolean, default=True)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship(
		'Tenant', foreign_keys=[tenant_id], overlaps='branch,warehouses'
	)

	branch_id = Column(String(36), nullable=False, index=True)
	branch = relationship('Branch', back_populates='warehouses', overlaps='tenant')

	stocks = relationship('Stock', back_populates='warehouse')

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'branch_id'],
			['branches.tenant_id', 'branches.id'],
			name='fk_warehouse_branch_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_warehouses_tenant_id'),
		UniqueConstraint(
			'tenant_id', 'branch_id', 'name', name='uq_warehouse_tenant_branch_name'
		),
	)


# ==========================================
# 3. CATÁLOGO Y VARIANTES DE PRODUCTOS
# ==========================================
class Category(Base):
	__tablename__ = 'categories'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	name = Column(String(200), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	__table_args__ = (
		UniqueConstraint('tenant_id', 'id', name='uq_categories_tenant_id'),
		UniqueConstraint('tenant_id', 'name', name='uq_category_tenant_name'),
	)


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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	purchases = relationship('Purchase', back_populates='supplier')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'id', name='uq_suppliers_tenant_id'),
	)


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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='articles')

	category_id = Column(String(36), nullable=True, index=True)
	category = relationship('Category', overlaps='tenant,articles,supplier')

	supplier_id = Column(String(36), nullable=True, index=True)
	supplier = relationship('Supplier', overlaps='tenant,articles,category')

	variants = relationship(
		'ArticleVariant', back_populates='article', cascade='all, delete-orphan'
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'category_id'],
			['categories.tenant_id', 'categories.id'],
			name='fk_article_category_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'supplier_id'],
			['suppliers.tenant_id', 'suppliers.id'],
			ondelete='SET NULL',
			name='fk_article_supplier_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_articles_tenant_id'),
	)


class ArticleVariant(Base):
	__tablename__ = 'article_variants'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
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
	base_variant_id = Column(String(36), nullable=True, index=True)

	margin_pct = Column(Numeric(5, 2), nullable=True)
	discount_pct = Column(Numeric(5, 2), nullable=True)
	discount_until = Column(DateTime, nullable=True)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	article_id = Column(String(36), nullable=False, index=True)
	article = relationship('Article', back_populates='variants')

	base_variant = relationship(
		'ArticleVariant',
		foreign_keys='ArticleVariant.base_variant_id',
		primaryjoin='ArticleVariant.base_variant_id == ArticleVariant.id',
	)

	stocks = relationship(
		'Stock', back_populates='variant', overlaps='warehouse,stocks'
	)
	sale_details = relationship(
		'SaleDetail', back_populates='variant', overlaps='sale,items'
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'article_id'],
			['articles.tenant_id', 'articles.id'],
			name='fk_variant_article_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'base_variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_variant_base_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_article_variants_tenant_id'),
		CheckConstraint('cost_price >= 0', name='chk_cost_price_positive'),
		CheckConstraint('selling_price >= 0', name='chk_selling_price_positive'),
		# A barcode is the identifier consumed by scanners.  Keeping it unique
		# across active variants avoids an ambiguous sale when two catalog entries
		# are accidentally assigned the same code.  NULL/blank values remain valid
		# while a product is being drafted.
		Index(
			'uq_article_variants_active_barcode',
			'tenant_id',
			'barcode',
			unique=True,
			sqlite_where=text(
				"barcode IS NOT NULL AND barcode <> '' AND is_active = 1"
			),
			postgresql_where=text(
				"barcode IS NOT NULL AND barcode <> '' AND is_active"
			),
		),
	)


class ArticleHistory(Base):
	__tablename__ = 'article_history'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	date = Column(DateTime, default=utcnow, nullable=False, index=True)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)
	user_id = Column(String(36), nullable=False)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	action_type = Column(String(50), nullable=False)
	article_name = Column(String(200), nullable=False)
	variant_id = Column(String(36), nullable=True, index=True)

	old_cost = Column(Numeric(10, 2), nullable=True)
	new_cost = Column(Numeric(10, 2), nullable=True)
	old_price = Column(Numeric(10, 2), nullable=True)
	new_price = Column(Numeric(10, 2), nullable=True)

	user = relationship('User')

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_history_user_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_history_variant_same_tenant',
		),
	)


# ==========================================
# 4. CONTROL DE STOCK E HISTORIAL
# ==========================================
class Stock(Base):
	__tablename__ = 'stocks'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	quantity = Column(Numeric(12, 4), nullable=False, default=0.0)

	batch_number = Column(String(100), nullable=False, default='', index=True)
	expiration_date = Column(Date, nullable=True)
	serial_number = Column(String(200), nullable=True)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	warehouse_id = Column(String(36), nullable=False, index=True)
	warehouse = relationship(
		'Warehouse', back_populates='stocks', overlaps='variant,stocks'
	)

	variant_id = Column(String(36), nullable=False, index=True)
	variant = relationship(
		'ArticleVariant', back_populates='stocks', overlaps='warehouse,stocks'
	)

	__table_args__ = (
		CheckConstraint('quantity >= 0', name='chk_stock_quantity_positive'),
		ForeignKeyConstraint(
			['tenant_id', 'warehouse_id'],
			['warehouses.tenant_id', 'warehouses.id'],
			name='fk_stock_warehouse_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_stock_variant_same_tenant',
		),
		UniqueConstraint(
			'tenant_id',
			'variant_id',
			'warehouse_id',
			'batch_number',
			name='uq_stock_variant_warehouse_batch',
		),
		UniqueConstraint('tenant_id', 'serial_number', name='uq_stock_tenant_serial'),
	)


class StockMovement(Base):
	__tablename__ = 'stock_movements'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=utcnow, nullable=False, index=True)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	movement_type = Column(String(50), nullable=False)
	quantity = Column(Numeric(12, 4), nullable=False)
	reference = Column(String(200), nullable=True)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	source_warehouse_id = Column(String(36), nullable=True, index=True)
	dest_warehouse_id = Column(String(36), nullable=True, index=True)

	variant_id = Column(String(36), nullable=False, index=True)
	variant = relationship('ArticleVariant', overlaps='user,stock_movements')

	user_id = Column(String(36), nullable=False)
	user = relationship('User', back_populates='stock_movements', overlaps='variant')

	__table_args__ = (
		CheckConstraint('quantity > 0', name='chk_movement_qty_positive'),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_movement_variant_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_movement_user_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'source_warehouse_id'],
			['warehouses.tenant_id', 'warehouses.id'],
			name='fk_movement_source_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'dest_warehouse_id'],
			['warehouses.tenant_id', 'warehouses.id'],
			name='fk_movement_dest_same_tenant',
		),
		CheckConstraint(
			"movement_type IN ('in', 'out', 'ajuste_entrada', 'ajuste_salida', 'transferencia')",
			name='chk_stock_movement_type',
		),
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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	tenant = relationship('Tenant', back_populates='customers')

	sales = relationship('Sale', back_populates='customer', overlaps='user,items,sales')

	__table_args__ = (
		UniqueConstraint('tenant_id', 'id', name='uq_customers_tenant_id'),
		UniqueConstraint('tenant_id', 'name', name='uq_customer_tenant_name'),
		CheckConstraint("price_list IN ('A', 'B')", name='chk_customer_price_list'),
	)


class Sale(Base):
	__tablename__ = 'sales'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=utcnow, nullable=False, index=True)
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
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	user_id = Column(String(36), nullable=False, index=True)
	user = relationship('User', back_populates='sales', overlaps='customer,items,sales')

	customer_id = Column(String(36), nullable=True, index=True)
	customer = relationship(
		'Customer', back_populates='sales', overlaps='user,items,sales'
	)

	# The warehouse is recorded on the document, not inferred later from the
	# mutable stock rows.  It makes stock attribution and audits unambiguous.
	warehouse_id = Column(String(36), nullable=True, index=True)
	warehouse = relationship('Warehouse', overlaps='user,customer,items,sales')

	items = relationship(
		'SaleDetail',
		back_populates='sale',
		cascade='all, delete-orphan',
		overlaps='customer,user,variant,sale_details',
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_sale_user_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'customer_id'],
			['customers.tenant_id', 'customers.id'],
			name='fk_sale_customer_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'warehouse_id'],
			['warehouses.tenant_id', 'warehouses.id'],
			name='fk_sale_warehouse_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_sales_tenant_id'),
		Index('ix_sale_tenant_status', 'tenant_id', 'status'),
		Index('ix_sale_tenant_status_date', 'tenant_id', 'status', 'date'),
		CheckConstraint('total_amount >= 0', name='chk_sale_total_positive'),
		CheckConstraint('discount_amount >= 0', name='chk_sale_discount_positive'),
		CheckConstraint('total_returned >= 0', name='chk_sale_total_returned_positive'),
		CheckConstraint(
			'total_returned <= total_amount', name='chk_sale_returned_lte_total'
		),
		CheckConstraint(
			"status IN ('pendiente', 'completada', 'cancelada', 'devuelta', 'parcial', 'parcialmente_devuelta')",
			name='chk_sale_status',
		),
	)


class SaleDetail(Base):
	__tablename__ = 'sale_details'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	unit_price = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)
	returned_quantity = Column(Numeric(12, 4), nullable=False, default=0.0)

	# updated_at doubles as created_at for this append-only table
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	sale_id = Column(String(36), nullable=False, index=True)
	sale = relationship('Sale', back_populates='items', overlaps='variant,sale_details')

	variant_id = Column(String(36), nullable=True, index=True)
	variant = relationship(
		'ArticleVariant', back_populates='sale_details', overlaps='sale'
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'sale_id'],
			['sales.tenant_id', 'sales.id'],
			name='fk_sale_detail_sale_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_sale_detail_variant_same_tenant',
		),
		CheckConstraint('quantity > 0', name='chk_sale_detail_quantity_positive'),
		CheckConstraint('unit_cost >= 0', name='chk_sale_detail_cost_positive'),
		CheckConstraint('unit_price >= 0', name='chk_sale_detail_price_positive'),
		CheckConstraint('subtotal >= 0', name='chk_sale_detail_subtotal_positive'),
		CheckConstraint(
			'returned_quantity >= 0 AND returned_quantity <= quantity',
			name='chk_sale_detail_returned_quantity',
		),
	)


class CashSession(Base):
	__tablename__ = 'cash_sessions'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	user_id = Column(String(36), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	opened_at = Column(DateTime, default=utcnow, nullable=False)
	closed_at = Column(DateTime, nullable=True)
	is_open = Column(Boolean, default=True)

	opening_balance = Column(Numeric(10, 2), default=0.0)
	closing_balance = Column(Numeric(10, 2), default=0.0)

	expected_amount = Column(Numeric(10, 2), nullable=True)
	declared_amount = Column(Numeric(10, 2), nullable=True)
	difference = Column(Numeric(10, 2), nullable=True)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	user = relationship('User', overlaps='movements')
	movements = relationship(
		'CashMovement', back_populates='session', cascade='all, delete-orphan'
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_cash_session_user_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_cash_sessions_tenant_id'),
		Index(
			'uq_cash_open_session',
			'tenant_id',
			'user_id',
			unique=True,
			sqlite_where=text('is_open = 1'),
			postgresql_where=text('is_open'),
		),
	)


class CashMovement(Base):
	__tablename__ = 'cash_movements'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	movement_type = Column(String(50), nullable=False)
	amount = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=True)
	time = Column(DateTime, default=utcnow, nullable=False)
	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	session_id = Column(String(36), nullable=False, index=True)
	session = relationship(
		'CashSession', back_populates='movements', overlaps='customer'
	)

	# FK directa al cliente — evita búsquedas frágiles por texto en get_customer_ledger
	customer_id = Column(String(36), nullable=True, index=True)
	customer = relationship(
		'Customer', foreign_keys=[customer_id], overlaps='session,movements'
	)

	__table_args__ = (
		CheckConstraint('amount > 0', name='chk_cash_amount_positive'),
		CheckConstraint(
			"movement_type IN ('ingreso', 'gasto', 'venta', 'venta_digital', 'gasto_digital', 'devolucion', 'cobro_cliente', 'pago_proveedor')",
			name='chk_cash_movement_type',
		),
		ForeignKeyConstraint(
			['tenant_id', 'session_id'],
			['cash_sessions.tenant_id', 'cash_sessions.id'],
			name='fk_cash_movement_session_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'customer_id'],
			['customers.tenant_id', 'customers.id'],
			name='fk_cash_movement_customer_same_tenant',
		),
		Index('ix_cash_mov_session_time', 'session_id', 'time'),
	)


# ==========================================
# 6. COMPRAS Y PROVEEDORES
# ==========================================
class Purchase(Base):
	__tablename__ = 'purchases'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=utcnow, nullable=False, index=True)
	total_amount = Column(Numeric(10, 2), nullable=False)
	invoice_number = Column(String(100), nullable=True)
	status = Column(String(50), default='pagada')

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	user_id = Column(String(36), nullable=False, index=True)

	supplier_id = Column(String(36), nullable=True, index=True)
	supplier = relationship(
		'Supplier', back_populates='purchases', overlaps='items,returns'
	)

	items = relationship(
		'PurchaseDetail',
		back_populates='purchase',
		cascade='all, delete-orphan',
		overlaps='supplier,returns,variant',
	)
	returns = relationship(
		'PurchaseReturn',
		back_populates='purchase',
		cascade='all, delete-orphan',
		overlaps='supplier,items',
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_purchase_user_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'supplier_id'],
			['suppliers.tenant_id', 'suppliers.id'],
			name='fk_purchase_supplier_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_purchases_tenant_id'),
		CheckConstraint('total_amount >= 0', name='chk_purchase_total_positive'),
	)


class PurchaseDetail(Base):
	__tablename__ = 'purchase_details'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	purchase_id = Column(String(36), nullable=False, index=True)
	purchase = relationship('Purchase', back_populates='items', overlaps='variant')

	variant_id = Column(String(36), nullable=True, index=True)
	variant = relationship('ArticleVariant', overlaps='purchase,items')

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'purchase_id'],
			['purchases.tenant_id', 'purchases.id'],
			name='fk_purchase_detail_purchase_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_purchase_detail_variant_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_purchase_details_tenant_id'),
		CheckConstraint('quantity > 0', name='chk_purchase_detail_quantity_positive'),
		CheckConstraint('unit_cost >= 0', name='chk_purchase_detail_cost_positive'),
		CheckConstraint('subtotal >= 0', name='chk_purchase_detail_subtotal_positive'),
	)


class PurchaseReturn(Base):
	__tablename__ = 'purchase_returns'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	date = Column(DateTime, default=utcnow, nullable=False, index=True)
	reason = Column(String(200), nullable=False)
	refund_type = Column(String(50), nullable=False)
	total_refund = Column(Numeric(10, 2), nullable=False)
	notes = Column(String(1000), nullable=True)
	file_path = Column(String(500), nullable=True)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	purchase_id = Column(String(36), nullable=False, index=True)
	purchase = relationship('Purchase', back_populates='returns', overlaps='items')

	user_id = Column(String(36), nullable=False, index=True)
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)

	items = relationship(
		'PurchaseReturnItem',
		back_populates='purchase_return',
		cascade='all, delete-orphan',
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'purchase_id'],
			['purchases.tenant_id', 'purchases.id'],
			name='fk_purchase_return_purchase_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_purchase_return_user_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_purchase_returns_tenant_id'),
		CheckConstraint('total_refund >= 0', name='chk_purchase_return_total_positive'),
	)


class PurchaseReturnItem(Base):
	__tablename__ = 'purchase_return_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	quantity_returned = Column(Numeric(12, 4), nullable=False)
	unit_cost = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)
	description = Column(String(500), nullable=False)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	purchase_return_id = Column(String(36), nullable=False, index=True)
	purchase_return = relationship(
		'PurchaseReturn', back_populates='items', overlaps='variant'
	)

	purchase_detail_id = Column(String(36), nullable=True, index=True)
	variant_id = Column(String(36), nullable=True)
	variant = relationship('ArticleVariant', overlaps='purchase_return,items')

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'purchase_return_id'],
			['purchase_returns.tenant_id', 'purchase_returns.id'],
			name='fk_purchase_return_item_parent_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'purchase_detail_id'],
			['purchase_details.tenant_id', 'purchase_details.id'],
			name='fk_purchase_return_item_detail_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_purchase_return_item_variant_same_tenant',
		),
		CheckConstraint(
			'quantity_returned > 0', name='chk_purchase_return_item_quantity_positive'
		),
		CheckConstraint(
			'unit_cost >= 0', name='chk_purchase_return_item_cost_positive'
		),
		CheckConstraint(
			'subtotal >= 0', name='chk_purchase_return_item_subtotal_positive'
		),
	)


class ComboItem(Base):
	__tablename__ = 'combo_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	combo_id = Column(String(36), nullable=False, index=True)
	ingredient_id = Column(String(36), nullable=False, index=True)
	quantity_required = Column(Numeric(12, 4), nullable=False)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	combo = relationship(
		'ArticleVariant',
		foreign_keys=[combo_id],
		backref='ingredients',
		overlaps='ingredient',
	)
	ingredient = relationship(
		'ArticleVariant', foreign_keys=[ingredient_id], overlaps='combo,ingredients'
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'combo_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_combo_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'ingredient_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_combo_ingredient_same_tenant',
		),
		UniqueConstraint(
			'tenant_id', 'combo_id', 'ingredient_id', name='uq_combo_ingredient'
		),
		CheckConstraint('combo_id <> ingredient_id', name='chk_combo_not_self'),
		CheckConstraint('quantity_required > 0', name='chk_combo_qty_positive'),
	)


# ==========================================
# 7. COTIZACIONES / PRESUPUESTOS
# ==========================================
class Quotation(Base):
	__tablename__ = 'quotations'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	number = Column(String(50), nullable=False)
	date = Column(DateTime, default=utcnow, nullable=False, index=True)
	valid_until = Column(Date, nullable=True)
	status = Column(String(50), default='borrador')

	total_amount = Column(Numeric(10, 2), nullable=False, default=0)
	discount_amount = Column(Numeric(10, 2), default=0)
	notes = Column(String(1000), nullable=True)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	user_id = Column(String(36), nullable=False, index=True)
	customer_id = Column(String(36), nullable=True, index=True)

	user = relationship('User', overlaps='customer,items')
	customer = relationship('Customer', overlaps='user,items')
	items = relationship(
		'QuotationItem',
		back_populates='quotation',
		cascade='all, delete-orphan',
		overlaps='user,customer,variant',
	)

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'user_id'],
			['users.tenant_id', 'users.id'],
			name='fk_quotation_user_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'customer_id'],
			['customers.tenant_id', 'customers.id'],
			name='fk_quotation_customer_same_tenant',
		),
		UniqueConstraint('tenant_id', 'id', name='uq_quotations_tenant_id'),
		UniqueConstraint('tenant_id', 'number', name='uix_tenant_quotation_number'),
		CheckConstraint('total_amount >= 0', name='chk_quotation_total_positive'),
		CheckConstraint(
			'discount_amount >= 0 AND discount_amount <= total_amount',
			name='chk_quotation_discount_valid',
		),
		CheckConstraint(
			"status IN ('borrador', 'enviada', 'aceptada', 'rechazada', 'vencida', 'convertida', 'cancelada')",
			name='chk_quotation_status',
		),
	)


class QuotationItem(Base):
	__tablename__ = 'quotation_items'
	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

	tenant_id = Column(String(36), ForeignKey('tenants.id'), nullable=False, index=True)
	description = Column(String(500), nullable=False)
	quantity = Column(Numeric(12, 4), nullable=False)
	unit_price = Column(Numeric(10, 2), nullable=False)
	subtotal = Column(Numeric(10, 2), nullable=False)

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	quotation_id = Column(String(36), nullable=False, index=True)
	quotation = relationship('Quotation', back_populates='items', overlaps='variant')

	variant_id = Column(String(36), nullable=True)
	variant = relationship('ArticleVariant', overlaps='quotation,items')

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'quotation_id'],
			['quotations.tenant_id', 'quotations.id'],
			name='fk_quotation_item_quotation_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_quotation_item_variant_same_tenant',
		),
		CheckConstraint('quantity > 0', name='chk_quotation_item_quantity_positive'),
		CheckConstraint('unit_price >= 0', name='chk_quotation_item_price_positive'),
		CheckConstraint('subtotal >= 0', name='chk_quotation_item_subtotal_positive'),
	)


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

	variant_id = Column(String(36), nullable=True, index=True)
	category_id = Column(String(36), nullable=True, index=True)

	date_from = Column(DateTime, nullable=False)
	date_to = Column(DateTime, nullable=False)
	# "0,1,2,3,4,5,6" donde 0=Lunes (Python weekday)
	days_of_week = Column(String(20), nullable=True)
	time_from = Column(String(10), nullable=True)  # "HH:MM"
	time_to = Column(String(10), nullable=True)  # "HH:MM"

	updated_at = Column(
		DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
	)

	variant = relationship('ArticleVariant', foreign_keys=[variant_id])
	category = relationship('Category', foreign_keys=[category_id])

	__table_args__ = (
		ForeignKeyConstraint(
			['tenant_id', 'variant_id'],
			['article_variants.tenant_id', 'article_variants.id'],
			name='fk_promotion_variant_same_tenant',
		),
		ForeignKeyConstraint(
			['tenant_id', 'category_id'],
			['categories.tenant_id', 'categories.id'],
			name='fk_promotion_category_same_tenant',
		),
		CheckConstraint(
			"promo_type IN ('pct', 'nxm', 'fixed')", name='chk_promotion_type'
		),
		CheckConstraint('date_to >= date_from', name='chk_promotion_date_range'),
		CheckConstraint(
			"(promo_type <> 'nxm') OR (buy_qty > 0 AND pay_qty > 0 AND pay_qty <= buy_qty)",
			name='chk_promotion_nxm_values',
		),
		CheckConstraint(
			"(promo_type <> 'pct') OR (discount_value > 0 AND discount_value <= 100)",
			name='chk_promotion_pct_value',
		),
		CheckConstraint(
			"(promo_type <> 'fixed') OR discount_value >= 0",
			name='chk_promotion_fixed_value',
		),
	)
