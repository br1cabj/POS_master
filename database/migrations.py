"""
database/migrations.py
======================
Schema migrations for the local SQLite database.

Each migration is idempotent: if the column/index already exists it is silently
skipped.  Run order is sequential and must never change.

For Supabase (PostgreSQL) the schema is created in one shot via
`setup_cloud_schema(engine)` which calls SQLAlchemy's `create_all()` — no need
to run these incremental SQLite migrations on the cloud.
"""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _is_sqlite(engine) -> bool:
	return engine.dialect.name == 'sqlite'


def _run_alter(conn, sql: str, label: str) -> bool:
	"""
	Execute one ALTER TABLE.  Returns True if applied, False if the column
	already existed.  Re-raises on any other error.
	"""
	try:
		conn.execute(text(sql))
		conn.commit()
		logger.info('Migration applied: %s', label)
		return True
	except Exception as e:
		msg = str(e).lower()
		if 'duplicate column' in msg or 'already exists' in msg:
			return False
		logger.error('Migration failed (%s): %s', label, e)
		raise


def _column_exists(engine, table: str, column: str) -> bool:
	"""Dialect-agnostic column existence check via SQLAlchemy inspect."""
	insp = inspect(engine)
	cols = [c['name'] for c in insp.get_columns(table)]
	return column in cols


def _add_column_if_missing(
	conn, engine, table: str, column: str, definition: str
) -> bool:
	"""
	Add `column` to `table` only when it does not exist yet.
	Uses dialect-aware syntax:
	- SQLite: ALTER TABLE … ADD COLUMN (catches duplicate-column error)
	- PostgreSQL: ALTER TABLE … ADD COLUMN IF NOT EXISTS
	"""
	if _column_exists(engine, table, column):
		return False

	if _is_sqlite(engine):
		sql = f'ALTER TABLE {table} ADD COLUMN {column} {definition}'
		return _run_alter(conn, sql, f'{column} in {table}')
	else:
		sql = f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}'
		conn.execute(text(sql))
		conn.commit()
		logger.info('Migration applied: %s in %s', column, table)
		return True


# ─── public entry points ───────────────────────────────────────────────────────


def run_migrations(engine) -> None:
	"""
	Apply all pending migrations in order.
	Call once at startup, after `get_engine()`.
	On PostgreSQL, delegates to setup_cloud_schema() (create_all) instead of
	running incremental SQLite-specific ALTER TABLE statements.
	"""
	if not _is_sqlite(engine):
		setup_cloud_schema(engine)
		return
	_v1_add_cost_price_usd(engine)
	_v2_add_recovery_pin_hash(engine)
	_v3_add_discount_amount(engine)
	_v4_add_mixto_fields(engine)
	_v5_create_quotations(engine)
	_v6_add_packaging_variants(engine)
	_v7_add_quotation_number_to_sales(engine)
	_v8_add_product_discount_fields(engine)
	_v9_add_supplier_discount_fields(engine)
	_v10_purchase_details_and_returns(engine)
	_v11_add_user_display_name(engine)
	_v12_add_sale_status_indexes(engine)
	_v13_add_price_list_fields(engine)
	_v14_add_margin_pct(engine)
	_v15_add_returned_quantity_to_sale_details(engine)
	_v16_add_updated_at(engine)
	_v17_add_updated_at_core_tables(engine)
	_v18_add_sale_method1_and_total_returned(engine)
	_v19_add_cash_movement_index(engine)
	_v20_create_promotions(engine)
	_v21_create_combo_items(engine)
	_v22_create_article_history(engine)
	_v23_add_updated_at_cash_tables(engine)
	_v24_unique_combo_ingredient(engine)
	_v25_add_deleted_at_columns(engine)
	_v26_add_customer_id_to_cash_movements(engine)


def setup_cloud_schema(engine) -> None:
	"""
	Create (or verify) the full schema on the cloud PostgreSQL database.

	Uses SQLAlchemy `create_all(checkfirst=True)` so it is safe to call every
	time the app starts — existing tables and columns are left untouched.
	Call this before the first sync cycle.
	"""
	from database.models import Base

	try:
		Base.metadata.create_all(engine, checkfirst=True)
		logger.info('Cloud schema verified / created.')
	except Exception as e:
		logger.error('setup_cloud_schema failed: %s', e)
		raise


# ─── migrations v1–v15 (unchanged) ────────────────────────────────────────────


def _v1_add_cost_price_usd(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn,
			engine,
			'article_variants',
			'cost_price_usd',
			'NUMERIC(10, 4) DEFAULT NULL',
		)


def _v2_add_recovery_pin_hash(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'users', 'recovery_pin_hash', 'VARCHAR DEFAULT NULL'
		)


def _v3_add_discount_amount(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'sales', 'discount_amount', 'NUMERIC(10, 2) DEFAULT 0.0'
		)


def _v4_add_mixto_fields(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'sales', 'payment_method_2', 'VARCHAR DEFAULT NULL'
		)
		_add_column_if_missing(
			conn, engine, 'sales', 'amount_method_2', 'NUMERIC(10, 2) DEFAULT NULL'
		)


def _v5_create_quotations(engine) -> None:
	with engine.connect() as conn:
		try:
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS quotations (
                    id              VARCHAR(36) PRIMARY KEY,
                    number          VARCHAR NOT NULL,
                    date            DATETIME DEFAULT CURRENT_TIMESTAMP,
                    valid_until     DATE,
                    status          VARCHAR DEFAULT 'borrador',
                    total_amount    NUMERIC(10,2) NOT NULL DEFAULT 0,
                    discount_amount NUMERIC(10,2) DEFAULT 0,
                    notes           VARCHAR,
                    tenant_id       VARCHAR(36) NOT NULL REFERENCES tenants(id),
                    user_id         VARCHAR(36) NOT NULL REFERENCES users(id),
                    customer_id     VARCHAR(36) REFERENCES customers(id),
                    UNIQUE(tenant_id, number)
                )
            """)
			)
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS quotation_items (
                    id            VARCHAR(36) PRIMARY KEY,
                    description   VARCHAR NOT NULL,
                    quantity      NUMERIC(12,4) NOT NULL,
                    unit_price    NUMERIC(10,2) NOT NULL,
                    subtotal      NUMERIC(10,2) NOT NULL,
                    quotation_id  VARCHAR(36) NOT NULL REFERENCES quotations(id),
                    variant_id    VARCHAR(36) REFERENCES article_variants(id)
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_quotations_tenant_id ON quotations(tenant_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_quotations_date ON quotations(date)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_quotation_items_quotation_id ON quotation_items(quotation_id)'
				)
			)
			conn.commit()
			logger.info('v5: quotations tables ready.')
		except Exception as e:
			logger.error('v5 failed: %s', e)
			raise


def _v6_add_packaging_variants(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'article_variants', 'units_per_pack', 'INTEGER DEFAULT 1'
		)
		_add_column_if_missing(
			conn, engine, 'article_variants', 'pack_label', 'VARCHAR DEFAULT NULL'
		)
		_add_column_if_missing(
			conn,
			engine,
			'article_variants',
			'base_variant_id',
			'VARCHAR(36) DEFAULT NULL REFERENCES article_variants(id)',
		)


def _v7_add_quotation_number_to_sales(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'sales', 'quotation_number', 'VARCHAR DEFAULT NULL'
		)


def _v8_add_product_discount_fields(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn,
			engine,
			'article_variants',
			'discount_pct',
			'NUMERIC(5,2) DEFAULT NULL',
		)
		_add_column_if_missing(
			conn, engine, 'article_variants', 'discount_until', 'DATETIME DEFAULT NULL'
		)


def _v9_add_supplier_discount_fields(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'suppliers', 'discount_pct', 'NUMERIC(5,2) DEFAULT NULL'
		)
		_add_column_if_missing(
			conn, engine, 'suppliers', 'discount_until', 'DATETIME DEFAULT NULL'
		)


def _v10_purchase_details_and_returns(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'suppliers', 'credit_balance', 'NUMERIC(10,2) DEFAULT 0.0'
		)
		try:
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS purchase_details (
                    id               VARCHAR(36) PRIMARY KEY,
                    quantity         NUMERIC(12,4) NOT NULL,
                    unit_cost        NUMERIC(10,2) NOT NULL,
                    subtotal         NUMERIC(10,2) NOT NULL,
                    description      VARCHAR NOT NULL,
                    purchase_id      VARCHAR(36) NOT NULL REFERENCES purchases(id),
                    variant_id       VARCHAR(36) REFERENCES article_variants(id)
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_purchase_details_purchase_id ON purchase_details(purchase_id)'
				)
			)
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS purchase_returns (
                    id           VARCHAR(36) PRIMARY KEY,
                    date         DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reason       VARCHAR NOT NULL,
                    refund_type  VARCHAR NOT NULL,
                    total_refund NUMERIC(10,2) NOT NULL,
                    notes        VARCHAR,
                    file_path    VARCHAR,
                    purchase_id  VARCHAR(36) NOT NULL REFERENCES purchases(id),
                    user_id      VARCHAR(36) NOT NULL REFERENCES users(id),
                    tenant_id    VARCHAR(36) NOT NULL REFERENCES tenants(id)
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_purchase_returns_purchase_id ON purchase_returns(purchase_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_purchase_returns_tenant_id ON purchase_returns(tenant_id)'
				)
			)
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS purchase_return_items (
                    id                 VARCHAR(36) PRIMARY KEY,
                    quantity_returned  NUMERIC(12,4) NOT NULL,
                    unit_cost          NUMERIC(10,2) NOT NULL,
                    subtotal           NUMERIC(10,2) NOT NULL,
                    description        VARCHAR NOT NULL,
                    purchase_return_id VARCHAR(36) NOT NULL REFERENCES purchase_returns(id),
                    purchase_detail_id VARCHAR(36) REFERENCES purchase_details(id),
                    variant_id         VARCHAR(36) REFERENCES article_variants(id)
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_purchase_return_items_return_id ON purchase_return_items(purchase_return_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_purchase_return_items_detail_id ON purchase_return_items(purchase_detail_id)'
				)
			)
			conn.commit()
			logger.info('v10: purchase detail/return tables ready.')
		except Exception as e:
			logger.error('v10 failed: %s', e)
			raise


def _v11_add_user_display_name(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'users', 'display_name', 'VARCHAR DEFAULT NULL'
		)


def _v12_add_sale_status_indexes(engine) -> None:
	with engine.connect() as conn:
		try:
			conn.execute(
				text('CREATE INDEX IF NOT EXISTS ix_sales_status ON sales(status)')
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_sale_tenant_status ON sales(tenant_id, status)'
				)
			)
			conn.commit()
			logger.info('v12: sales status indexes ready.')
		except Exception as e:
			logger.error('v12 failed: %s', e)
			raise


def _v13_add_price_list_fields(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn,
			engine,
			'article_variants',
			'selling_price_b',
			'NUMERIC(10, 2) DEFAULT NULL',
		)
		_add_column_if_missing(
			conn, engine, 'customers', 'price_list', "VARCHAR DEFAULT 'A'"
		)


def _v14_add_margin_pct(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'article_variants', 'margin_pct', 'NUMERIC(5, 2) DEFAULT NULL'
		)


def _v15_add_returned_quantity_to_sale_details(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn,
			engine,
			'sale_details',
			'returned_quantity',
			'NUMERIC(12, 4) NOT NULL DEFAULT 0.0',
		)


# ─── v16: updated_at for cloud sync ───────────────────────────────────────────


def _v16_add_updated_at(engine) -> None:
	"""
	v16: Add `updated_at` to the tables that participate in cloud sync.
	Existing rows get the current timestamp so the first sync cycle picks
	them all up.
	"""
	_SYNC_TABLES = [
		'suppliers',
		'articles',
		'article_variants',
		'customers',
		'sales',
		'sale_details',
		'stocks',
		'purchases',
	]

	with engine.connect() as conn:
		for table in _SYNC_TABLES:
			# SQLite rejects non-constant defaults (CURRENT_TIMESTAMP) in ALTER TABLE.
			# Add the column as NULL-able and back-fill immediately after.
			added = _add_column_if_missing(
				conn,
				engine,
				table,
				'updated_at',
				'DATETIME DEFAULT NULL',
			)
			if added:
				conn.execute(
					text(
						f'UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'
					)
				)
				conn.commit()

		# Index updated_at on the high-volume tables.
		_HIGH_VOLUME = ('sales', 'sale_details', 'stocks', 'article_variants')
		for table in _HIGH_VOLUME:
			try:
				conn.execute(
					text(
						f'CREATE INDEX IF NOT EXISTS ix_{table}_updated_at ON {table}(updated_at)'
					)
				)
			except Exception as e:
				logger.warning('Could not create index on %s.updated_at: %s', table, e)
		conn.commit()
		logger.info('v16: updated_at columns ready for cloud sync.')


# ─── v17: updated_at for core tables (tenant, branch, warehouse, user) ────────


def _v17_add_updated_at_core_tables(engine) -> None:
	"""
	v17: Add `updated_at` to the core tables that are FK parents of the
	sync tables. Without these the cloud upsert fails with FK violations
	because Tenant/Branch/Warehouse/User rows are never pushed.
	"""
	_CORE_TABLES = ['tenants', 'branches', 'warehouses', 'users']

	with engine.connect() as conn:
		for table in _CORE_TABLES:
			# SQLite rejects non-constant defaults in ALTER TABLE — use NULL then back-fill.
			added = _add_column_if_missing(
				conn,
				engine,
				table,
				'updated_at',
				'DATETIME DEFAULT NULL',
			)
			if added:
				conn.execute(
					text(
						f'UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'
					)
				)
				conn.commit()

		for table in _CORE_TABLES:
			try:
				conn.execute(
					text(
						f'CREATE INDEX IF NOT EXISTS ix_{table}_updated_at ON {table}(updated_at)'
					)
				)
			except Exception as e:
				logger.warning('Could not create index on %s.updated_at: %s', table, e)
		conn.commit()
		logger.info('v17: updated_at columns ready for core tables.')


# ─── v18: amount_method_1 y total_returned en sales ──────────────────────────


def _v18_add_sale_method1_and_total_returned(engine) -> None:
	"""
	v18: Almacena el monto del primer método de pago en ventas mixtas y el total
	ya devuelto para evitar mutar total_amount en devoluciones parciales.
	"""
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'sales', 'amount_method_1', 'NUMERIC(10, 2) DEFAULT NULL'
		)
		_add_column_if_missing(
			conn,
			engine,
			'sales',
			'total_returned',
			'NUMERIC(10, 2) NOT NULL DEFAULT 0.0',
		)
	logger.info('v18: amount_method_1 y total_returned agregados a sales.')


# ─── v19: índice compuesto en cash_movements ──────────────────────────────────


def _v19_add_cash_movement_index(engine) -> None:
	"""v19: Índice compuesto (session_id, time) en cash_movements para consultas de arqueo."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_cash_mov_session_time ON cash_movements(session_id, time)'
				)
			)
			conn.commit()
			logger.info('v19: índice ix_cash_mov_session_time listo.')
		except Exception as e:
			logger.error('v19 failed: %s', e)


# ─── v20: tabla de promociones con vigencia ───────────────────────────────────


def _v20_create_promotions(engine) -> None:
	"""v20: Crea la tabla promotions para promociones temporales (% desc, NxM, precio fijo)."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS promotions (
                    id              VARCHAR(36) PRIMARY KEY,
                    tenant_id       VARCHAR(36) NOT NULL REFERENCES tenants(id),
                    name            VARCHAR NOT NULL,
                    is_active       BOOLEAN NOT NULL DEFAULT 1,
                    promo_type      VARCHAR NOT NULL,
                    discount_value  NUMERIC(10,2) DEFAULT NULL,
                    buy_qty         INTEGER DEFAULT NULL,
                    pay_qty         INTEGER DEFAULT NULL,
                    variant_id      VARCHAR(36) REFERENCES article_variants(id),
                    category_id     VARCHAR(36) REFERENCES categories(id),
                    date_from       DATETIME NOT NULL,
                    date_to         DATETIME NOT NULL,
                    days_of_week    VARCHAR DEFAULT NULL,
                    time_from       VARCHAR DEFAULT NULL,
                    time_to         VARCHAR DEFAULT NULL,
                    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_promotions_tenant_id ON promotions(tenant_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_promotions_variant_id ON promotions(variant_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_promotions_date_range ON promotions(date_from, date_to)'
				)
			)
			conn.commit()
			logger.info('v20: tabla promotions lista.')
		except Exception as e:
			logger.error('v20 failed: %s', e)
			raise


# ─── v21: tabla combo_items ───────────────────────────────────────────────────


def _v21_create_combo_items(engine) -> None:
	"""v21: Crea la tabla combo_items para el armado de combos/recetas."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS combo_items (
                    id                VARCHAR(36) PRIMARY KEY,
                    combo_id          VARCHAR(36) NOT NULL REFERENCES article_variants(id),
                    ingredient_id     VARCHAR(36) NOT NULL REFERENCES article_variants(id),
                    quantity_required  NUMERIC(12,4) NOT NULL
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_combo_items_combo_id ON combo_items(combo_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_combo_items_ingredient_id ON combo_items(ingredient_id)'
				)
			)
			conn.commit()
			logger.info('v21: tabla combo_items lista.')
		except Exception as e:
			logger.error('v21 failed: %s', e)
			raise


# ─── v22: tabla article_history ───────────────────────────────────────────────


def _v22_create_article_history(engine) -> None:
	"""v22: Crea la tabla article_history para auditoría de cambios de artículos."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text("""
                CREATE TABLE IF NOT EXISTS article_history (
                    id           VARCHAR(36) PRIMARY KEY,
                    date         DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id      VARCHAR(36) NOT NULL REFERENCES users(id),
                    tenant_id    VARCHAR(36) NOT NULL REFERENCES tenants(id),
                    action_type  VARCHAR NOT NULL,
                    article_name VARCHAR NOT NULL,
                    variant_id   VARCHAR(36) REFERENCES article_variants(id),
                    old_cost     NUMERIC(10, 2) DEFAULT NULL,
                    new_cost     NUMERIC(10, 2) DEFAULT NULL,
                    old_price    NUMERIC(10, 2) DEFAULT NULL,
                    new_price    NUMERIC(10, 2) DEFAULT NULL
                )
            """)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_article_history_tenant_id ON article_history(tenant_id)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_article_history_date ON article_history(date)'
				)
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_article_history_variant_id ON article_history(variant_id)'
				)
			)
			conn.commit()
			logger.info('v22: tabla article_history lista.')
		except Exception as e:
			logger.error('v22 failed: %s', e)
			raise


# ─── v23: updated_at en tablas de caja (para sync 7 días) ────────────────────


def _v23_add_updated_at_cash_tables(engine) -> None:
	"""v23: Agrega updated_at a cash_sessions y cash_movements para habilitar el sync cloud."""
	_CASH_TABLES = [
		('cash_sessions', 'opened_at'),
		('cash_movements', 'time'),
	]
	with engine.connect() as conn:
		for table, backfill_col in _CASH_TABLES:
			added = _add_column_if_missing(
				conn, engine, table, 'updated_at', 'DATETIME DEFAULT NULL'
			)
			if added:
				conn.execute(
					text(
						f'UPDATE {table} SET updated_at = {backfill_col} WHERE updated_at IS NULL'
					)
				)
				conn.commit()
			try:
				conn.execute(
					text(
						f'CREATE INDEX IF NOT EXISTS ix_{table}_updated_at ON {table}(updated_at)'
					)
				)
			except Exception as e:
				logger.warning('Could not create index on %s.updated_at: %s', table, e)
		conn.commit()
		logger.info('v23: updated_at en cash_sessions y cash_movements listo.')


# ─── v24: unique index en combo_items ────────────────────────────────────────


def _v24_unique_combo_ingredient(engine) -> None:
	"""v24: Garantiza que (combo_id, ingredient_id) sea único en combo_items."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'CREATE UNIQUE INDEX IF NOT EXISTS uq_combo_ingredient ON combo_items(combo_id, ingredient_id)'
				)
			)
			conn.commit()
			logger.info('v24: índice único uq_combo_ingredient listo.')
		except Exception as e:
			logger.error('v24 failed: %s', e)
			raise


# ─── v25: deleted_at / deleted_by para soft-delete ───────────────────────────


def _v25_add_deleted_at_columns(engine) -> None:
	"""v25: Agrega deleted_at y deleted_by a las tablas que soportan soft-delete."""
	_TABLES = ['customers', 'articles', 'article_variants', 'suppliers', 'users']
	with engine.connect() as conn:
		for table in _TABLES:
			_add_column_if_missing(conn, engine, table, 'deleted_at', 'DATETIME DEFAULT NULL')
			_add_column_if_missing(
				conn, engine, table, 'deleted_by', 'VARCHAR(36) DEFAULT NULL'
			)
	logger.info('v25: columnas deleted_at/deleted_by listas.')


# ─── v26: customer_id en cash_movements ──────────────────────────────────────


def _v26_add_customer_id_to_cash_movements(engine) -> None:
	"""v26: FK customer_id en cash_movements para reemplazar búsquedas ILIKE en el libro mayor."""
	with engine.connect() as conn:
		_add_column_if_missing(
			conn,
			engine,
			'cash_movements',
			'customer_id',
			'VARCHAR(36) DEFAULT NULL REFERENCES customers(id)',
		)
		try:
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_cash_movements_customer_id ON cash_movements(customer_id)'
				)
			)
			conn.commit()
		except Exception as e:
			logger.warning('v26: no se pudo crear índice customer_id: %s', e)
	logger.info('v26: customer_id en cash_movements listo.')
