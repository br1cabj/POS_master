"""
utils/migrations.py
===================
Aplica migraciones de esquema SQLite de forma segura al inicio del sistema.
Cada migración es idempotente: si la columna ya existe, simplemente se omite.
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


def _v1_add_cost_price_usd(engine) -> None:
    """
    v1: Agrega la columna cost_price_usd a article_variants.
    """
    with engine.connect() as conn:
        try:
            conn.execute(text(
                'ALTER TABLE article_variants '
                'ADD COLUMN cost_price_usd NUMERIC(10, 4) DEFAULT NULL'
            ))
            conn.commit()
            logger.info('Migracion v1 aplicada: cost_price_usd agregado a article_variants.')
        except Exception:
            pass


def _v2_add_recovery_pin_hash(engine) -> None:
    """
    v2: Agrega la columna recovery_pin_hash a users.
    Almacena (hasheado con bcrypt) el PIN de recuperacion de contrasena.
    Es nullable: usuarios existentes no tienen PIN hasta que lo configuren.
    """
    with engine.connect() as conn:
        try:
            conn.execute(text(
                'ALTER TABLE users ADD COLUMN recovery_pin_hash VARCHAR DEFAULT NULL'
            ))
            conn.commit()
            logger.info('Migracion v2 aplicada: recovery_pin_hash agregado a users.')
        except Exception:
            pass
