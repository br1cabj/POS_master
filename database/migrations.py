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
	Lanza la excepción si el error no es 'duplicate column' o 'already exists' (fallo real).
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
		logger.error(f'Fallo real en migración ({label}): {e}')
		raise


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
	_v10_purchase_details_and_returns(engine)
	_v11_add_user_display_name(engine)
	_v12_add_sale_status_indexes(engine)
	_v13_add_price_list_fields(engine)
	_v14_add_margin_pct(engine)
	_v15_add_returned_quantity_to_sale_details(engine)


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
			logger.info('Migración v5: tablas quotations y quotation_items listas.')
		except Exception as e:
			logger.error(f'Error en migración v5: {e}')
			raise


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


def _v10_purchase_details_and_returns(engine) -> None:
	"""v10: Tablas de detalle de compras, devoluciones a proveedor y crédito de proveedor."""
	with engine.connect() as conn:
		# credit_balance en suppliers
		_run_alter(
			conn,
			'ALTER TABLE suppliers ADD COLUMN credit_balance NUMERIC(10,2) DEFAULT 0.0',
			'credit_balance en suppliers',
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
			logger.info('Migración v10: tablas de devoluciones a proveedor listas.')
		except Exception as e:
			logger.error(f'Error en migración v10: {e}')
			raise


def _v11_add_user_display_name(engine) -> None:
	"""v11: Agrega display_name a users para nombre visible en tickets/reportes."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE users ADD COLUMN display_name VARCHAR DEFAULT NULL',
			'display_name en users',
		)


def _v12_add_sale_status_indexes(engine) -> None:
	"""v12: Agrega índices en sales.status y (tenant_id, status) para filtros de estado."""
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
			logger.info('Migración v12: índices de sales.status creados.')
		except Exception as e:
			logger.error(f'Error en migración v12: {e}')
			raise


def _v13_add_price_list_fields(engine) -> None:
	"""v13: Agrega selling_price_b a article_variants y price_list a customers."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN selling_price_b NUMERIC(10, 2) DEFAULT NULL',
			'selling_price_b en article_variants',
		)
		_run_alter(
			conn,
			"ALTER TABLE customers ADD COLUMN price_list VARCHAR DEFAULT 'A'",
			'price_list en customers',
		)


def _v14_add_margin_pct(engine) -> None:
	"""v14: Agrega margin_pct a article_variants."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE article_variants ADD COLUMN margin_pct NUMERIC(5, 2) DEFAULT NULL',
			'margin_pct en article_variants',
		)


def _v15_add_returned_quantity_to_sale_details(engine) -> None:
	"""v15: Agrega returned_quantity a sale_details para rastrear devoluciones parciales por ítem."""
	with engine.connect() as conn:
		_run_alter(
			conn,
			'ALTER TABLE sale_details ADD COLUMN returned_quantity NUMERIC(12, 4) NOT NULL DEFAULT 0.0',
			'returned_quantity en sale_details',
		)
