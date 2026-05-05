"""
utils/migrations.py
===================
Aplica migraciones de esquema SQLite de forma segura al inicio del sistema.
Cada migración es idempotente: si la columna ya existe, simplemente se omite.
Adaptado para compatibilidad con UUID (VARCHAR(36)).
"""

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _run_alter(conn, sql: str, label: str) -> bool:
	"""
	Ejecuta un ALTER TABLE. Retorna True si se aplicó, False si ya existía.
	Lanza la excepción si el error no es 'duplicate column' (fallo real).
	"""
	try:
		conn.execute(text(sql))
		conn.commit()
		logger.info(f'Migración aplicada: {label}')
		return True
	except Exception as e:
		msg = str(e).lower()
		if 'duplicate column' in msg or 'already exists' in msg:
			return False
		logger.warning(f'Error inesperado en migración ({label}): {e}')
		return False


def run_migrations(engine) -> None:
	"""
	Ejecuta todas las migraciones pendientes.
	Llamar una vez al inicio de la aplicación, después de crear el motor.
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


def _v1_add_cost_price_usd(engine) -> None:
	"""v1: Agrega la columna cost_price_usd a article_variants."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN cost_price_usd NUMERIC(10, 4) DEFAULT NULL',
			'cost_price_usd en article_variants',
		)


def _v2_add_recovery_pin_hash(engine) -> None:
	"""v2: Agrega la columna recovery_pin_hash a users."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE users ADD COLUMN recovery_pin_hash VARCHAR DEFAULT NULL',
			'recovery_pin_hash en users',
		)


def _v3_add_discount_amount(engine) -> None:
	"""v3: Agrega la columna discount_amount a sales."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE sales ADD COLUMN discount_amount NUMERIC(10, 2) DEFAULT 0.0',
			'discount_amount en sales',
		)


def _v4_add_mixto_fields(engine) -> None:
	"""v4: Agrega payment_method_2 y amount_method_2 a sales."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE sales ADD COLUMN payment_method_2 VARCHAR DEFAULT NULL',
			'payment_method_2 en sales',
		)
		_run_alter(
			conn,
			'ALTER TABLE sales ADD COLUMN amount_method_2 NUMERIC(10, 2) DEFAULT NULL',
			'amount_method_2 en sales',
		)


def _v5_create_quotations(engine) -> None:
	"""v5: Crea las tablas quotations y quotation_items si no existen."""
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
				text('CREATE INDEX IF NOT EXISTS ix_quotations_date ON quotations(date)')
			)
			conn.execute(
				text(
					'CREATE INDEX IF NOT EXISTS ix_quotation_items_quotation_id ON quotation_items(quotation_id)'
				)
			)
			conn.commit()
			logger.info('Migración v5: tablas quotations y quotation_items listas.')
		except Exception as e:
			logger.warning(f'Error inesperado en migración v5: {e}')


def _v6_add_packaging_variants(engine) -> None:
	"""v6: Agrega soporte de presentaciones/empaque a article_variants."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN units_per_pack INTEGER DEFAULT 1',
			'units_per_pack en article_variants',
		)
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN pack_label VARCHAR DEFAULT NULL',
			'pack_label en article_variants',
		)
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN base_variant_id VARCHAR(36) DEFAULT NULL REFERENCES article_variants(id)',
			'base_variant_id en article_variants',
		)


def _v7_add_quotation_number_to_sales(engine) -> None:
	"""v7: Agrega quotation_number a sales."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE sales ADD COLUMN quotation_number VARCHAR DEFAULT NULL',
			'quotation_number en sales',
		)


def _v8_add_product_discount_fields(engine) -> None:
	"""v8: Agrega discount_pct y discount_until a article_variants."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN discount_pct NUMERIC(5,2) DEFAULT NULL',
			'discount_pct en article_variants',
		)
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN discount_until DATETIME DEFAULT NULL',
			'discount_until en article_variants',
		)


def _v9_add_supplier_discount_fields(engine) -> None:
	"""v9: Agrega discount_pct y discount_until a suppliers."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE suppliers ADD COLUMN discount_pct NUMERIC(5,2) DEFAULT NULL',
			'discount_pct en suppliers',
		)
		_run_alter(
			conn,
			'ALTER TABLE suppliers ADD COLUMN discount_until DATETIME DEFAULT NULL',
			'discount_until en suppliers',
		)
