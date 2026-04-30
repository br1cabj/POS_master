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


def _v1_add_cost_price_usd(engine) -> None:
	"""
	v1: Agrega la columna cost_price_usd a article_variants.
	"""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'ALTER TABLE article_variants '
					'ADD COLUMN cost_price_usd NUMERIC(10, 4) DEFAULT NULL'
				)
			)
			conn.commit()
			logger.info(
				'Migración v1 aplicada: cost_price_usd agregado a article_variants.'
			)
		except Exception:
			pass


def _v2_add_recovery_pin_hash(engine) -> None:
	"""
	v2: Agrega la columna recovery_pin_hash a users.
	Almacena (hasheado con bcrypt) el PIN de recuperación de contraseña.
	Es nullable: usuarios existentes no tienen PIN hasta que lo configuren.
	"""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'ALTER TABLE users ADD COLUMN recovery_pin_hash VARCHAR DEFAULT NULL'
				)
			)
			conn.commit()
			logger.info('Migración v2 aplicada: recovery_pin_hash agregado a users.')
		except Exception:
			pass


def _v3_add_discount_amount(engine) -> None:
	"""
	v3: Agrega la columna discount_amount a sales.
	Guarda el monto total de descuento aplicado en la venta.
	Es nullable/default 0: ventas existentes se tratan como sin descuento.
	"""
	with engine.connect() as conn:
		try:
			conn.execute(
				text(
					'ALTER TABLE sales ADD COLUMN discount_amount NUMERIC(10, 2) DEFAULT 0.0'
				)
			)
			conn.commit()
			logger.info('Migración v3 aplicada: discount_amount agregado a sales.')
		except Exception:
			pass


def _v4_add_mixto_fields(engine) -> None:
	"""
	v4: Agrega payment_method_2 y amount_method_2 a sales.
	Permiten registrar ventas con dos métodos de pago (pago mixto).
	Nullable: ventas existentes se tratan como pago simple.
	"""
	with engine.connect() as conn:
		for sql in [
			'ALTER TABLE sales ADD COLUMN payment_method_2 VARCHAR DEFAULT NULL',
			'ALTER TABLE sales ADD COLUMN amount_method_2 NUMERIC(10, 2) DEFAULT NULL',
		]:
			try:
				conn.execute(text(sql))
				conn.commit()
			except Exception:
				pass
		logger.info(
			'Migración v4 aplicada: payment_method_2 y amount_method_2 en sales.'
		)


def _v5_create_quotations(engine) -> None:
	"""
	v5: Crea las tablas quotations y quotation_items si no existen.
	Adaptado para usar UUIDs (VARCHAR(36)).
	"""
	with engine.connect() as conn:
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
		logger.info(
			'Migración v5 aplicada: tablas quotations y quotation_items creadas.'
		)


def _v7_add_quotation_number_to_sales(engine) -> None:
	"""
	v7: Agrega quotation_number a sales.
	Almacena el número legible de la cotización de origen (ej: COT-2024-001).
	Nullable: ventas directas no tienen cotización asociada.
	"""
	with engine.connect() as conn:
		try:
			conn.execute(
				text('ALTER TABLE sales ADD COLUMN quotation_number VARCHAR DEFAULT NULL')
			)
			conn.commit()
			logger.info('Migración v7 aplicada: quotation_number agregado a sales.')
		except Exception:
			pass


def _v6_add_packaging_variants(engine) -> None:
	"""
	v6: Agrega soporte de presentaciones/empaque a article_variants.
	Adaptado para que base_variant_id sea VARCHAR(36) (UUID).
	"""
	with engine.connect() as conn:
		for sql in [
			'ALTER TABLE article_variants ADD COLUMN units_per_pack INTEGER DEFAULT 1',
			'ALTER TABLE article_variants ADD COLUMN pack_label VARCHAR DEFAULT NULL',
			'ALTER TABLE article_variants ADD COLUMN base_variant_id VARCHAR(36) DEFAULT NULL REFERENCES article_variants(id)',
		]:
			try:
				conn.execute(text(sql))
				conn.commit()
			except Exception:
				pass
		logger.info(
			'Migración v6 aplicada: units_per_pack, pack_label, base_variant_id en article_variants.'
		)
