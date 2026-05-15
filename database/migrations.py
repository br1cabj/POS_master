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


def _add_column_if_missing(conn, engine, table: str, column: str, definition: str) -> bool:
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
    Apply all pending SQLite migrations in order.
    Call once at startup, after `get_engine()`.
    Safe to call on PostgreSQL (skips SQLite-specific steps).
    """
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
            conn, engine, 'article_variants', 'cost_price_usd',
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
            conn.execute(text("""
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
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quotation_items (
                    id            VARCHAR(36) PRIMARY KEY,
                    description   VARCHAR NOT NULL,
                    quantity      NUMERIC(12,4) NOT NULL,
                    unit_price    NUMERIC(10,2) NOT NULL,
                    subtotal      NUMERIC(10,2) NOT NULL,
                    quotation_id  VARCHAR(36) NOT NULL REFERENCES quotations(id),
                    variant_id    VARCHAR(36) REFERENCES article_variants(id)
                )
            """))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_quotations_tenant_id ON quotations(tenant_id)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_quotations_date ON quotations(date)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_quotation_items_quotation_id ON quotation_items(quotation_id)'
            ))
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
            conn, engine, 'article_variants', 'base_variant_id',
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
            conn, engine, 'article_variants', 'discount_pct', 'NUMERIC(5,2) DEFAULT NULL'
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
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS purchase_details (
                    id               VARCHAR(36) PRIMARY KEY,
                    quantity         NUMERIC(12,4) NOT NULL,
                    unit_cost        NUMERIC(10,2) NOT NULL,
                    subtotal         NUMERIC(10,2) NOT NULL,
                    description      VARCHAR NOT NULL,
                    purchase_id      VARCHAR(36) NOT NULL REFERENCES purchases(id),
                    variant_id       VARCHAR(36) REFERENCES article_variants(id)
                )
            """))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_details_purchase_id ON purchase_details(purchase_id)'
            ))
            conn.execute(text("""
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
            """))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_returns_purchase_id ON purchase_returns(purchase_id)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_returns_tenant_id ON purchase_returns(tenant_id)'
            ))
            conn.execute(text("""
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
            """))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_return_items_return_id ON purchase_return_items(purchase_return_id)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_purchase_return_items_detail_id ON purchase_return_items(purchase_detail_id)'
            ))
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
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_sales_status ON sales(status)'
            ))
            conn.execute(text(
                'CREATE INDEX IF NOT EXISTS ix_sale_tenant_status ON sales(tenant_id, status)'
            ))
            conn.commit()
            logger.info('v12: sales status indexes ready.')
        except Exception as e:
            logger.error('v12 failed: %s', e)
            raise


def _v13_add_price_list_fields(engine) -> None:
    with engine.connect() as conn:
        _add_column_if_missing(
            conn, engine, 'article_variants', 'selling_price_b',
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
            conn, engine, 'sale_details', 'returned_quantity',
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
            added = _add_column_if_missing(
                conn, engine, table, 'updated_at',
                'DATETIME DEFAULT CURRENT_TIMESTAMP',
            )
            if added:
                # Back-fill existing rows so the first sync knows about them.
                conn.execute(
                    text(f"UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
                )
                conn.commit()

        # Index updated_at on the high-volume tables.
        _HIGH_VOLUME = ('sales', 'sale_details', 'stocks', 'article_variants')
        for table in _HIGH_VOLUME:
            try:
                conn.execute(text(
                    f'CREATE INDEX IF NOT EXISTS ix_{table}_updated_at ON {table}(updated_at)'
                ))
            except Exception:
                pass
        conn.commit()
        logger.info('v16: updated_at columns ready for cloud sync.')
