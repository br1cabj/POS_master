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


def _add_column_if_missing_tx(
	conn, engine, table: str, column: str, definition: str
) -> bool:
	"""
	Like _add_column_if_missing but does NOT commit — the caller manages the
	transaction (e.g. via `with engine.begin() as conn`).
	Use for multi-column migrations that must be atomic.
	"""
	if _column_exists(engine, table, column):
		return False
	if _is_sqlite(engine):
		conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {definition}'))
	else:
		conn.execute(
			text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}')
		)
	logger.info('Migration staged: %s in %s', column, table)
	return True


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
	_v27_add_updated_at_article_history(engine)
	_v28_add_tenant_updated_at_stock_movement_category(engine)
	_v29_add_stock_unique_constraint(engine)
	_v30_add_performance_indexes(engine)
	_v31_add_updated_at_child_tables(engine)


def setup_cloud_schema(engine) -> None:
	"""
	Create (or verify) the full schema on the cloud PostgreSQL database.

	Uses SQLAlchemy `create_all(checkfirst=True)` so it is safe to call every
	time the app starts — existing tables and columns are left untouched.
	Then adds missing columns (updated_at, deleted_at, etc.) that were added
	by local migrations but may not exist in the cloud schema yet.
	"""
	from database.models import Base

	try:
		Base.metadata.create_all(engine, checkfirst=True)
		logger.info('Cloud schema verified / created.')
	except Exception as e:
		logger.error('setup_cloud_schema failed: %s', e)
		raise

	_cloud_missing_columns(engine)
	with engine.begin() as conn:
		# El índice parcial es la garantía final ante dos aperturas concurrentes
		# de caja. SQLite lo recibe mediante v30; la nube se crea por separado.
		conn.execute(
			text(
				'CREATE UNIQUE INDEX IF NOT EXISTS uq_cash_open_session '
				'ON public.cash_sessions(tenant_id, user_id) WHERE is_open'
			)
		)
	_configure_cloud_dashboard_security(engine)


def _configure_cloud_dashboard_security(engine) -> None:
	"""Install database-enforced, tenant-scoped read access for the web UI.

	The browser never receives password hashes.  It obtains an opaque, expiring
	session token through a SECURITY DEFINER login function; RLS derives the
	tenant from that token on every REST query.
	"""
	if _is_sqlite(engine):
		return
	with engine.begin() as conn:
		conn.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto'))
		conn.execute(text('''
			CREATE TABLE IF NOT EXISTS public.cloudpos_web_sessions (
				token_hash TEXT PRIMARY KEY,
				tenant_id VARCHAR(36) NOT NULL,
				user_id VARCHAR(36) NOT NULL,
				role VARCHAR(50) NOT NULL,
				expires_at TIMESTAMP NOT NULL
			)
		'''))
		conn.execute(text('''
			CREATE TABLE IF NOT EXISTS public.cloudpos_web_login_attempts (
				tenant_id VARCHAR(36) NOT NULL,
				username TEXT NOT NULL,
				attempts INTEGER NOT NULL DEFAULT 0,
				locked_until TIMESTAMP NULL,
				last_attempt TIMESTAMP NOT NULL DEFAULT now(),
				PRIMARY KEY (tenant_id, username)
			)
		'''))
		conn.execute(text('''
			CREATE OR REPLACE FUNCTION public.cloudpos_web_session()
			RETURNS TABLE(id VARCHAR, username VARCHAR, display_name VARCHAR, role VARCHAR, tenant_id VARCHAR)
			LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, extensions AS $$
				-- El rol se lee de users en cada petición: revocar permisos a un
				-- usuario tiene efecto inmediato, sin esperar que venza su sesión.
				SELECT u.id, u.username, u.display_name, u.role, s.tenant_id
				FROM public.cloudpos_web_sessions s
				JOIN public.users u ON u.id = s.user_id
				WHERE s.token_hash = encode(digest(COALESCE((NULLIF(current_setting('request.headers', true), '')::jsonb ->> 'x-cloudpos-session'), ''), 'sha256'), 'hex')
				  AND s.expires_at > now() AND u.is_active = true AND u.deleted_at IS NULL
			$$
		'''))
		conn.execute(text('''
			CREATE OR REPLACE FUNCTION public.cloudpos_web_login(p_username TEXT, p_password TEXT, p_tenant_id VARCHAR)
			RETURNS TABLE(session_token TEXT, id VARCHAR, username VARCHAR, display_name VARCHAR, role VARCHAR, tenant_id VARCHAR)
			LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, extensions AS $$
			DECLARE usr public.users%ROWTYPE; token TEXT;
			BEGIN
				IF COALESCE(trim(p_username), '') = ''
					OR COALESCE(p_password, '') = '' OR p_tenant_id IS NULL THEN
					RETURN;
				END IF;
				DELETE FROM public.cloudpos_web_login_attempts
				WHERE last_attempt < now() - interval '1 day';
				IF EXISTS (
					SELECT 1 FROM public.cloudpos_web_login_attempts
					WHERE tenant_id = p_tenant_id AND username = p_username
					  AND locked_until > now()
				) THEN RETURN; END IF;
				SELECT * INTO usr FROM public.users
				WHERE users.username = p_username AND users.tenant_id = p_tenant_id
				  AND users.is_active = true AND users.deleted_at IS NULL LIMIT 1;
				IF NOT FOUND OR usr.password_hash IS NULL OR crypt(p_password, usr.password_hash) <> usr.password_hash THEN
					INSERT INTO public.cloudpos_web_login_attempts(tenant_id, username, attempts, locked_until, last_attempt)
					VALUES (p_tenant_id, p_username, 1, NULL, now())
					ON CONFLICT (tenant_id, username) DO UPDATE SET
						attempts = CASE WHEN cloudpos_web_login_attempts.last_attempt <= now() - interval '5 minutes'
							THEN 1 ELSE cloudpos_web_login_attempts.attempts + 1 END,
						locked_until = CASE WHEN cloudpos_web_login_attempts.last_attempt <= now() - interval '5 minutes'
							THEN NULL WHEN cloudpos_web_login_attempts.attempts + 1 >= 5
							THEN now() + interval '5 minutes' ELSE NULL END,
						last_attempt = now();
					RETURN;
				END IF;
				DELETE FROM public.cloudpos_web_login_attempts
				WHERE tenant_id = p_tenant_id AND username = p_username;
				DELETE FROM public.cloudpos_web_sessions WHERE expires_at <= now();
				token := encode(gen_random_bytes(32), 'hex');
				INSERT INTO public.cloudpos_web_sessions(token_hash, tenant_id, user_id, role, expires_at)
				VALUES (encode(digest(token, 'sha256'), 'hex'), usr.tenant_id, usr.id, usr.role, now() + interval '8 hours');
				RETURN QUERY SELECT token, usr.id, usr.username, usr.display_name, usr.role, usr.tenant_id;
			END $$
		'''))
		conn.execute(text('''
			CREATE OR REPLACE FUNCTION public.cloudpos_current_tenant()
			RETURNS VARCHAR LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, extensions AS $$
				SELECT tenant_id FROM public.cloudpos_web_session() LIMIT 1
			$$
		'''))
		conn.execute(text('''
			CREATE OR REPLACE FUNCTION public.cloudpos_current_user()
			RETURNS VARCHAR LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, extensions AS $$
				SELECT id FROM public.cloudpos_web_session() LIMIT 1
			$$
		'''))
		conn.execute(text('''
			CREATE OR REPLACE FUNCTION public.cloudpos_web_is_manager()
			RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, extensions AS $$
				SELECT COALESCE((SELECT role IN ('admin', 'supervisor') FROM public.cloudpos_web_session() LIMIT 1), false)
			$$
		'''))
		conn.execute(text('REVOKE ALL ON FUNCTION public.cloudpos_web_login(TEXT, TEXT, VARCHAR) FROM PUBLIC'))
		conn.execute(text('REVOKE ALL ON FUNCTION public.cloudpos_web_session() FROM PUBLIC'))
		conn.execute(text('REVOKE ALL ON FUNCTION public.cloudpos_current_tenant() FROM PUBLIC'))
		conn.execute(text('REVOKE ALL ON FUNCTION public.cloudpos_current_user() FROM PUBLIC'))
		conn.execute(text('REVOKE ALL ON FUNCTION public.cloudpos_web_is_manager() FROM PUBLIC'))
		conn.execute(text('GRANT EXECUTE ON FUNCTION public.cloudpos_web_login(TEXT, TEXT, VARCHAR) TO anon'))
		conn.execute(text('GRANT EXECUTE ON FUNCTION public.cloudpos_web_session() TO anon'))
		conn.execute(text('GRANT EXECUTE ON FUNCTION public.cloudpos_current_tenant() TO anon'))
		conn.execute(text('GRANT EXECUTE ON FUNCTION public.cloudpos_current_user() TO anon'))
		conn.execute(text('GRANT EXECUTE ON FUNCTION public.cloudpos_web_is_manager() TO anon'))

		direct_tables = (
			'tenants', 'branches', 'warehouses', 'suppliers', 'categories', 'articles',
			'article_history', 'stock_movements', 'customers', 'sales', 'cash_sessions',
			'purchases', 'purchase_returns', 'quotations', 'promotions',
		)
		manager_tables = {
			'suppliers', 'article_history', 'cash_sessions', 'purchases',
			'purchase_returns', 'promotions',
		}
		for table_name in direct_tables:
			predicate = (
				"tenant_id IS NULL OR tenant_id = public.cloudpos_current_tenant()"
				if table_name == 'categories'
				else "tenant_id = public.cloudpos_current_tenant()"
			)
			if table_name == 'tenants':
				predicate = 'id = public.cloudpos_current_tenant()'
			if table_name in manager_tables:
				predicate = f'({predicate}) AND public.cloudpos_web_is_manager()'
			conn.execute(text(f'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY'))
			conn.execute(text(f'DROP POLICY IF EXISTS cloudpos_tenant_read ON public.{table_name}'))
			conn.execute(text(f'CREATE POLICY cloudpos_tenant_read ON public.{table_name} FOR SELECT TO anon USING ({predicate})'))
			conn.execute(text(f'REVOKE ALL ON TABLE public.{table_name} FROM anon'))
			conn.execute(text(f'GRANT SELECT ON TABLE public.{table_name} TO anon'))

		child_policies = {
			'article_variants': 'EXISTS (SELECT 1 FROM public.articles a WHERE a.id = article_variants.article_id AND a.tenant_id = public.cloudpos_current_tenant())',
			'stocks': 'EXISTS (SELECT 1 FROM public.article_variants v JOIN public.articles a ON a.id = v.article_id WHERE v.id = stocks.variant_id AND a.tenant_id = public.cloudpos_current_tenant())',
			'sale_details': 'EXISTS (SELECT 1 FROM public.sales s WHERE s.id = sale_details.sale_id AND s.tenant_id = public.cloudpos_current_tenant())',
			'purchase_details': 'EXISTS (SELECT 1 FROM public.purchases p WHERE p.id = purchase_details.purchase_id AND p.tenant_id = public.cloudpos_current_tenant())',
			'purchase_return_items': 'EXISTS (SELECT 1 FROM public.purchase_returns r WHERE r.id = purchase_return_items.purchase_return_id AND r.tenant_id = public.cloudpos_current_tenant())',
			'quotation_items': 'EXISTS (SELECT 1 FROM public.quotations q WHERE q.id = quotation_items.quotation_id AND q.tenant_id = public.cloudpos_current_tenant())',
			'cash_movements': 'EXISTS (SELECT 1 FROM public.cash_sessions c WHERE c.id = cash_movements.session_id AND c.tenant_id = public.cloudpos_current_tenant())',
			'combo_items': 'EXISTS (SELECT 1 FROM public.article_variants v JOIN public.articles a ON a.id = v.article_id WHERE v.id = combo_items.combo_id AND a.tenant_id = public.cloudpos_current_tenant())',
		}
		manager_child_tables = {
			'purchase_details', 'purchase_return_items', 'cash_movements',
		}
		for table_name, predicate in child_policies.items():
			if table_name in manager_child_tables:
				predicate = f'({predicate}) AND public.cloudpos_web_is_manager()'
			conn.execute(text(f'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY'))
			conn.execute(text(f'DROP POLICY IF EXISTS cloudpos_tenant_read ON public.{table_name}'))
			conn.execute(text(f'CREATE POLICY cloudpos_tenant_read ON public.{table_name} FOR SELECT TO anon USING ({predicate})'))
			conn.execute(text(f'REVOKE ALL ON TABLE public.{table_name} FROM anon'))
			conn.execute(text(f'GRANT SELECT ON TABLE public.{table_name} TO anon'))

		conn.execute(text('ALTER TABLE public.users ENABLE ROW LEVEL SECURITY'))
		conn.execute(text('DROP POLICY IF EXISTS cloudpos_tenant_read ON public.users'))
		conn.execute(text('''
			CREATE POLICY cloudpos_tenant_read ON public.users FOR SELECT TO anon USING (
				tenant_id = public.cloudpos_current_tenant()
				AND (public.cloudpos_web_is_manager() OR id = public.cloudpos_current_user())
			)
		'''))
		conn.execute(text('REVOKE ALL ON TABLE public.users FROM anon'))
		conn.execute(text('GRANT SELECT (id, username, display_name, role, is_active, deleted_at, tenant_id, updated_at) ON TABLE public.users TO anon'))
		conn.execute(text('REVOKE ALL ON TABLE public.cloudpos_web_sessions FROM PUBLIC'))
		conn.execute(text('REVOKE ALL ON TABLE public.cloudpos_web_login_attempts FROM PUBLIC'))


# ─── cloud schema column sync ───────────────────────────────────────────────────


def _cloud_missing_columns(engine) -> None:
	"""
	Agrega columnas faltantes a tablas existentes en la cloud (PostgreSQL).
	Esto es necesario porque create_all() solo crea tablas nuevas, no modifica
	tablas existentes para agregarles columnas.
	Las columnas aqui listadas fueron agregadas por migraciones locales pero
	pueden no existir aun en el schema cloud.
	"""
	if _is_sqlite(engine):
		return

	_COLUMNS_TO_SYNC = [
		('users', 'deleted_at', 'TIMESTAMP DEFAULT NULL'),
		('users', 'deleted_by', 'VARCHAR(36) DEFAULT NULL'),
		('users', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('articles', 'deleted_at', 'TIMESTAMP DEFAULT NULL'),
		('articles', 'deleted_by', 'VARCHAR(36) DEFAULT NULL'),
		('articles', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('article_variants', 'deleted_at', 'TIMESTAMP DEFAULT NULL'),
		('article_variants', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('suppliers', 'deleted_at', 'TIMESTAMP DEFAULT NULL'),
		('suppliers', 'deleted_by', 'VARCHAR(36) DEFAULT NULL'),
		('suppliers', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('customers', 'deleted_at', 'TIMESTAMP DEFAULT NULL'),
		('customers', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('cash_sessions', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('cash_movements', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('cash_movements', 'customer_id', 'VARCHAR(36) DEFAULT NULL'),
		('article_history', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('stock_movements', 'tenant_id', 'VARCHAR(36) DEFAULT NULL'),
		('stock_movements', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('categories', 'tenant_id', 'VARCHAR(36) DEFAULT NULL'),
		('categories', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('sales', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('sale_details', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('stocks', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('purchases', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('purchase_details', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('purchase_returns', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('purchase_return_items', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('quotations', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('quotation_items', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('combo_items', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('tenants', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('branches', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
		('warehouses', 'updated_at', 'TIMESTAMP DEFAULT NULL'),
	]

	insp = inspect(engine)
	existing_cols_cache: dict[str, set] = {}

	def _get_cols(table: str) -> set:
		if table not in existing_cols_cache:
			existing_cols_cache[table] = {c['name'] for c in insp.get_columns(table)}
		return existing_cols_cache[table]

	with engine.connect() as conn:
		for table, column, definition in _COLUMNS_TO_SYNC:
			if column in _get_cols(table):
				continue
			sql = f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}'
			try:
				conn.execute(text(sql))
				logger.info('Cloud column added: %s.%s', table, column)
			except Exception as e:
				logger.warning('Cloud column sync failed for %s.%s: %s', table, column, e)
		conn.commit()
	logger.info('Cloud column sync complete.')


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
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'sales', 'payment_method_2', 'VARCHAR DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'sales', 'amount_method_2', 'NUMERIC(10, 2) DEFAULT NULL')
	logger.info('v4: mixto fields ready.')


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
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'article_variants', 'units_per_pack', 'INTEGER DEFAULT 1')
		_add_column_if_missing_tx(conn, engine, 'article_variants', 'pack_label', 'VARCHAR DEFAULT NULL')
		_add_column_if_missing_tx(
			conn, engine, 'article_variants', 'base_variant_id',
			'VARCHAR(36) DEFAULT NULL REFERENCES article_variants(id)',
		)
	logger.info('v6: packaging variants ready.')


def _v7_add_quotation_number_to_sales(engine) -> None:
	with engine.connect() as conn:
		_add_column_if_missing(
			conn, engine, 'sales', 'quotation_number', 'VARCHAR DEFAULT NULL'
		)


def _v8_add_product_discount_fields(engine) -> None:
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'article_variants', 'discount_pct', 'NUMERIC(5,2) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'article_variants', 'discount_until', 'DATETIME DEFAULT NULL')
	logger.info('v8: product discount fields ready.')


def _v9_add_supplier_discount_fields(engine) -> None:
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'suppliers', 'discount_pct', 'NUMERIC(5,2) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'suppliers', 'discount_until', 'DATETIME DEFAULT NULL')
	logger.info('v9: supplier discount fields ready.')


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
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'article_variants', 'selling_price_b', 'NUMERIC(10, 2) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'customers', 'price_list', "VARCHAR DEFAULT 'A'")
	logger.info('v13: price list fields ready.')


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
	with engine.begin() as conn:
		_add_column_if_missing_tx(conn, engine, 'sales', 'amount_method_1', 'NUMERIC(10, 2) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'sales', 'total_returned', 'NUMERIC(10, 2) NOT NULL DEFAULT 0.0')
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
			raise


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
                    quantity_required  NUMERIC(12,4) NOT NULL,
                    CONSTRAINT chk_combo_qty_positive CHECK (quantity_required > 0)
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
	with engine.begin() as conn:
		for table in _TABLES:
			_add_column_if_missing_tx(conn, engine, table, 'deleted_at', 'DATETIME DEFAULT NULL')
			_add_column_if_missing_tx(conn, engine, table, 'deleted_by', 'VARCHAR(36) DEFAULT NULL')
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
		except Exception as e:
			logger.warning('v26: no se pudo crear índice customer_id: %s', e)
		finally:
			conn.commit()
	logger.info('v26: customer_id en cash_movements listo.')


def _v27_add_updated_at_article_history(engine) -> None:
	"""v27: Agrega updated_at a article_history (sync incremental) e índice en articles.category_id."""
	with engine.connect() as conn:
		added = _add_column_if_missing(
			conn, engine,
			'article_history', 'updated_at',
			'DATETIME DEFAULT NULL',
		)
		if added:
			conn.execute(
				text(
					'UPDATE article_history SET updated_at = date WHERE updated_at IS NULL AND date IS NOT NULL'
				)
			)
			conn.execute(
				text(
					'UPDATE article_history SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'
				)
			)
			conn.commit()
		try:
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_articles_category_id ON articles(category_id)'
				)
			)
		except Exception as e:
			logger.warning('v27: no se pudo crear índice category_id: %s', e)
		conn.commit()
	logger.info('v27: updated_at en article_history e índice articles.category_id listos.')


# ─── v28: tenant_id + updated_at en stock_movements y categories ──────────────


def _v28_add_tenant_updated_at_stock_movement_category(engine) -> None:
	"""
	v28: Agrega tenant_id y updated_at a stock_movements y categories para
	habilitar el sync incremental multi-tenant de ambas tablas.
	Backfill automático: tenant_id se infiere desde el warehouse para movimientos
	existentes, y desde el primer tenant para categorías.
	"""
	with engine.begin() as conn:
		# stock_movements: tenant_id + updated_at
		_add_column_if_missing_tx(conn, engine, 'stock_movements', 'tenant_id', 'VARCHAR(36) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'stock_movements', 'updated_at', 'DATETIME DEFAULT NULL')
		# categories: tenant_id + updated_at
		_add_column_if_missing_tx(conn, engine, 'categories', 'tenant_id', 'VARCHAR(36) DEFAULT NULL')
		_add_column_if_missing_tx(conn, engine, 'categories', 'updated_at', 'DATETIME DEFAULT NULL')

	# Backfill stock_movements.tenant_id desde la cadena warehouse→branch→tenant
	with engine.connect() as conn:
		try:
			if _is_sqlite(engine):
				conn.execute(text("""
					UPDATE stock_movements
					SET tenant_id = (
						SELECT b.tenant_id
						FROM warehouses wh
						JOIN branches b ON b.id = wh.branch_id
						WHERE wh.id = COALESCE(
							stock_movements.dest_warehouse_id,
							stock_movements.source_warehouse_id
						)
						LIMIT 1
					)
					WHERE tenant_id IS NULL
				"""))
			else:
				conn.execute(text("""
					UPDATE stock_movements sm
					SET tenant_id = b.tenant_id
					FROM warehouses wh
					JOIN branches b ON b.id = wh.branch_id
					WHERE wh.id = COALESCE(sm.dest_warehouse_id, sm.source_warehouse_id)
					  AND sm.tenant_id IS NULL
				"""))
		except Exception as e:
			logger.warning('v28: backfill stock_movements.tenant_id falló: %s', e)

		try:
			conn.execute(text("""
				UPDATE stock_movements
				SET updated_at = date
				WHERE updated_at IS NULL AND date IS NOT NULL
			"""))
			conn.execute(text("""
				UPDATE stock_movements
				SET updated_at = CURRENT_TIMESTAMP
				WHERE updated_at IS NULL
			"""))
		except Exception as e:
			logger.warning('v28: backfill stock_movements.updated_at falló: %s', e)

		# Backfill categories.tenant_id con el primer tenant disponible
		try:
			conn.execute(text("""
				UPDATE categories
				SET tenant_id = (SELECT id FROM tenants ORDER BY rowid LIMIT 1)
				WHERE tenant_id IS NULL
			"""))
			conn.execute(text("""
				UPDATE categories
				SET updated_at = CURRENT_TIMESTAMP
				WHERE updated_at IS NULL
			"""))
		except Exception as e:
			logger.warning('v28: backfill categories falló: %s', e)

		# Índices
		for idx_sql in [
			'CREATE INDEX IF NOT EXISTS ix_stock_movements_tenant_id ON stock_movements(tenant_id)',
			'CREATE INDEX IF NOT EXISTS ix_stock_movements_updated_at ON stock_movements(updated_at)',
			'CREATE INDEX IF NOT EXISTS ix_categories_tenant_id ON categories(tenant_id)',
			'CREATE INDEX IF NOT EXISTS ix_categories_updated_at ON categories(updated_at)',
		]:
			try:
				conn.execute(text(idx_sql))
			except Exception as e:
				logger.warning('v28: índice falló: %s — %s', idx_sql, e)

		conn.commit()

	logger.info('v28: tenant_id + updated_at en stock_movements y categories listos.')


def _v29_add_stock_unique_constraint(engine) -> None:
	"""v29: Agrega índice único en stocks(variant_id, warehouse_id, batch_number)
	para prevenir duplicados silenciosos que causaban desviación de inventario."""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_variant_warehouse_batch '
					'ON stocks(variant_id, warehouse_id, batch_number)'
				)
			)
			conn.commit()
			logger.info('v29: índice único uq_stock_variant_warehouse_batch creado.')
		except Exception as e:
			# Si ya hay duplicados, el índice fallará — loggear para que el admin lo sepa
			logger.error(
				'v29: no se pudo crear índice único en stocks '
				'(probablemente existen duplicados): %s',
				e,
			)
			raise


def _v30_add_performance_indexes(engine) -> None:
	"""v30: Agrega índices faltantes para mejorar performance en queries frecuentes."""
	with engine.connect() as conn:
		# Índice en sale_details.variant_id para reportes de productos más vendidos
		try:
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_sale_details_variant_id ON sale_details(variant_id)'
				)
			)
			logger.info('v30: índice ix_sale_details_variant_id creado.')
		except Exception as e:
			logger.warning('v30: no se pudo crear índice ix_sale_details_variant_id: %s', e)

		# Índices en stock_movements para reportes de Kardex por almacén
		for col in ('source_warehouse_id', 'dest_warehouse_id'):
			try:
				conn.execute(
					text(
						f'CREATE INDEX IF NOT EXISTS ix_stock_movements_{col} ON stock_movements({col})'
					)
				)
				logger.info('v30: índice ix_stock_movements_%s creado.', col)
			except Exception as e:
				logger.warning('v30: no se pudo crear índice ix_stock_movements_%s: %s', col, e)

		# Índice parcial único para evitar dos cajas abiertas por mismo usuario
		try:
			conn.execute(
				text(
					'CREATE UNIQUE INDEX IF NOT EXISTS uq_cash_open_session '
					'ON cash_sessions(tenant_id, user_id) WHERE is_open = 1'
				)
			)
			logger.info('v30: índice parcial único uq_cash_open_session creado.')
		except Exception as e:
			logger.warning('v30: no se pudo crear índice uq_cash_open_session: %s', e)

		conn.commit()


# ─── v31: updated_at en tablas hijas que faltaban ─────────────────────────────


def _v31_add_updated_at_child_tables(engine) -> None:
	"""
	v31: Agrega updated_at a purchase_details, purchase_returns,
	purchase_return_items, quotations, quotation_items y combo_items
	para habilitar el sync incremental de estas tablas a la nube.
	"""
	_CHILD_TABLES = [
		('purchase_details', 'purchase_id'),
		('purchase_returns', 'purchase_id'),
		('purchase_return_items', 'purchase_return_id'),
		('quotations', 'date'),
		('quotation_items', 'quotation_id'),
		('combo_items', 'combo_id'),
	]

	with engine.connect() as conn:
		for table, backfill_col in _CHILD_TABLES:
			added = _add_column_if_missing(
				conn, engine, table, 'updated_at', 'DATETIME DEFAULT NULL'
			)
			if added:
				conn.execute(
					text(
						f'UPDATE {table} SET updated_at = {backfill_col} WHERE updated_at IS NULL'
					)
				)
				conn.execute(
					text(
						f'UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL'
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
				logger.warning('v31: no se pudo crear índice en %s.updated_at: %s', table, e)
		conn.commit()
		logger.info('v31: updated_at en tablas hijas listo para sync incremental.')
