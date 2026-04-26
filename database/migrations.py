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


def _v1_add_cost_price_usd(engine) -> None:
    """
    v1: Agrega la columna cost_price_usd a article_variants.
    Permite guardar el precio base en dólares para recalcular automáticamente
    cuando cambia el tipo de cambio.
    """
    with engine.connect() as conn:
        try:
            conn.execute(text(
                'ALTER TABLE article_variants '
                'ADD COLUMN cost_price_usd NUMERIC(10, 4) DEFAULT NULL'
            ))
            conn.commit()
            logger.info('Migración v1 aplicada: cost_price_usd agregado a article_variants.')
        except Exception:
            # La columna ya existe — comportamiento esperado después del primer arranque
            pass
