"""Schema bootstrap and version guard for the clean CloudPOS database.

CloudPOS has no production data yet, so the historical chain of ad-hoc ALTER
statements was intentionally replaced by one declarative baseline.  The ORM
models are now the single source of truth for both local SQLite and the VPS.

This module does not attempt a destructive in-place upgrade of a legacy
database.  A legacy database with data must be exported and migrated through a
dedicated, reviewed tool instead of silently weakening tenant constraints.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_META_TABLE = 'cloudpos_schema_meta'
_REQUIRED_TENANT_COLUMNS = {
	'article_variants', 'stocks', 'stock_movements', 'sale_details',
	'cash_movements', 'purchase_details', 'purchase_return_items',
	'combo_items', 'quotation_items',
}


def _create_meta_table(connection) -> None:
	connection.execute(
		text(
			f'''CREATE TABLE IF NOT EXISTS {_META_TABLE} (
				id INTEGER PRIMARY KEY CHECK (id = 1),
				version INTEGER NOT NULL,
				applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
			)'''
		)
	)


def _has_clean_baseline(engine) -> bool:
	"""Return whether the essential tenant-scoped columns are present."""
	inspector = inspect(engine)
	tables = set(inspector.get_table_names())
	if not _REQUIRED_TENANT_COLUMNS.issubset(tables):
		return False
	for table in _REQUIRED_TENANT_COLUMNS:
		if 'tenant_id' not in {column['name'] for column in inspector.get_columns(table)}:
			return False
	return True


def _ensure_schema(engine) -> None:
	from database.models import Base

	# Never run create_all over a partially matching legacy database.  Some DDL
	# operations would succeed before the incompatibility is discovered, leaving
	# an already-existing installation in an ambiguous half-upgraded state.
	existing_tables = set(inspect(engine).get_table_names())
	known_tables = set(Base.metadata.tables)
	if existing_tables.intersection(known_tables) and not _has_clean_baseline(engine):
		raise RuntimeError(
			'La base existente pertenece al esquema legado. Como esta versión usa '
			'un diseño nuevo con aislamiento estricto por empresa, creá una base '
			'vacía o ejecutá una migración de datos revisada antes de iniciarla.'
		)

	# Declarative creation is atomic per DDL statement and applies the same
	# constraints/indexes in a brand-new SQLite database and PostgreSQL.
	Base.metadata.create_all(engine, checkfirst=True)
	if not _has_clean_baseline(engine):
		raise RuntimeError(
			'La base existente pertenece al esquema legado. Como esta versión usa '
			'un diseño nuevo con aislamiento estricto por empresa, creá una base '
			'vacía o ejecutá una migración de datos revisada antes de iniciarla.'
		)

	with engine.begin() as connection:
		_create_meta_table(connection)
		current = connection.execute(
			text(f'SELECT version FROM {_META_TABLE} WHERE id = 1')
		).scalar_one_or_none()
		if current is None:
			connection.execute(
				text(f'INSERT INTO {_META_TABLE} (id, version) VALUES (1, :version)'),
				{'version': SCHEMA_VERSION},
			)
			logger.info('CloudPOS schema baseline v%s initialized.', SCHEMA_VERSION)
		elif int(current) != SCHEMA_VERSION:
			raise RuntimeError(
				f'Esquema CloudPOS incompatible: se encontró v{current} y la aplicación '
				f'requiere v{SCHEMA_VERSION}. No se realizará una migración automática.'
			)


def run_migrations(engine) -> None:
	"""Initialize or validate the local offline database schema."""
	_ensure_schema(engine)


def setup_cloud_schema(engine) -> None:
	"""Initialize or validate the VPS reporting-replica schema."""
	_ensure_schema(engine)
