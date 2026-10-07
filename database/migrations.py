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
import re

from sqlalchemy import (
	CheckConstraint,
	ForeignKeyConstraint,
	UniqueConstraint,
	inspect,
	text,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_META_TABLE = 'cloudpos_schema_meta'


def _create_meta_table(connection) -> None:
	connection.execute(
		text(
			f"""CREATE TABLE IF NOT EXISTS {_META_TABLE} (
				id INTEGER PRIMARY KEY CHECK (id = 1),
				version INTEGER NOT NULL,
				applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
			)"""
		)
	)


def _normalize_sql(expression):
	"""Canonicalize the baseline's boolean predicates, including PostgreSQL reflection.

	PostgreSQL adds casts/grouping and rewrites IN as ANY(ARRAY[...]). Boolean
	AND/OR grouping is preserved so weakened checks cannot compare as equal.
	"""
	sql = str(expression)
	sql = re.sub(
		r'::(?:character varying|text|numeric|integer|boolean)(?:\[\])?',
		'',
		sql,
		flags=re.IGNORECASE,
	)
	sql = re.sub(
		r'=\s*ANY\s*\(\s*ARRAY\s*\[([^\]]*)\]\s*\)',
		r' IN (\1)',
		sql,
		flags=re.IGNORECASE,
	)
	tokens = re.findall(
		r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|<=|>=|<>|!=|[A-Za-z_][A-Za-z_0-9]*|\d+(?:\.\d+)?|[^\s]",
		sql,
	)
	tokens = [t if t.startswith("'") else t.strip('"').lower() for t in tokens]

	def canonical(parts):
		while parts and parts[0] == '(' and parts[-1] == ')':
			depth = 0
			for i, token in enumerate(parts):
				depth += (token == '(') - (token == ')')
				if depth == 0:
					break
			if i != len(parts) - 1:
				break
			parts = parts[1:-1]
		for operator in ('or', 'and'):
			depth, start, segments = 0, 0, []
			for i, token in enumerate(parts):
				depth += (token == '(') - (token == ')')
				if depth == 0 and token == operator:
					segments.append(canonical(parts[start:i]))
					start = i + 1
			if segments:
				segments.append(canonical(parts[start:]))
				flattened = []
				for segment in segments:
					if len(segment) == 2 and segment[0] == operator:
						flattened.extend(segment[1])
					else:
						flattened.append(segment)
				return operator, tuple(flattened)
		return tuple(t for t in parts if t not in ('(', ')'))

	return canonical(tokens)


def _check_version(connection, inspector):
	if _META_TABLE not in inspector.get_table_names():
		return None
	current = connection.execute(
		text(f'SELECT version FROM {_META_TABLE} WHERE id = 1')
	).scalar_one_or_none()
	if current is not None and int(current) != SCHEMA_VERSION:
		raise RuntimeError(
			f'Esquema CloudPOS incompatible: se encontró v{current} y la aplicación '
			f'requiere v{SCHEMA_VERSION}. No se realizará una migración automática.'
		)
	return current


def _schema_issues(connection, inspector):
	from database.models import Base

	issues = []
	existing = set(inspector.get_table_names())
	for table in Base.metadata.sorted_tables:
		name = table.name
		if name not in existing:
			issues.append(f'{name}: falta la tabla')
			continue
		columns = {c['name']: c for c in inspector.get_columns(name)}
		for expected in table.columns:
			actual = columns.get(expected.name)
			if actual is None:
				issues.append(f'{name}.{expected.name}: falta la columna')
				continue
			kind = expected.type.dialect_impl(connection.dialect)
			if kind._type_affinity is not actual['type']._type_affinity or any(
				getattr(kind, attr, None) != getattr(actual['type'], attr, None)
				for attr in ('length', 'precision', 'scale', 'timezone')
			):
				issues.append(f'{name}.{expected.name}: tipo incompatible')
			if bool(actual['nullable']) != bool(expected.nullable):
				issues.append(f'{name}.{expected.name}: nulabilidad incompatible')
		if tuple(inspector.get_pk_constraint(name)['constrained_columns']) != tuple(
			c.name for c in table.primary_key
		):
			issues.append(f'{name}: clave primaria incompatible')

		actual_unique = {
			tuple(c['column_names']) for c in inspector.get_unique_constraints(name)
		}
		actual_checks = {
			c['name']: c['sqltext'] for c in inspector.get_check_constraints(name)
		}
		actual_fks = inspector.get_foreign_keys(name)
		for constraint in table.constraints:
			if isinstance(constraint, UniqueConstraint):
				if tuple(c.name for c in constraint.columns) not in actual_unique:
					issues.append(
						f'{name}: falta la restricción única {constraint.name}'
					)
			elif isinstance(constraint, CheckConstraint):
				actual = actual_checks.get(constraint.name)
				if actual is None or _normalize_sql(actual) != _normalize_sql(
					constraint.sqltext
				):
					issues.append(
						f'{name}: falta o cambió la restricción {constraint.name}'
					)
			elif isinstance(constraint, ForeignKeyConstraint):

				def matches(actual):
					options = actual.get('options', {})
					return (
						tuple(actual['constrained_columns'])
						== tuple(c.name for c in constraint.columns)
						and actual['referred_table']
						== constraint.elements[0].column.table.name
						and tuple(actual['referred_columns'])
						== tuple(e.column.name for e in constraint.elements)
						and (
							actual.get('referred_schema')
							or inspector.default_schema_name
						)
						== (
							constraint.elements[0].column.table.schema
							or inspector.default_schema_name
						)
						and bool(options.get('deferrable'))
						== bool(constraint.deferrable)
						and (options.get('initially') or 'IMMEDIATE').upper()
						== (constraint.initially or 'IMMEDIATE').upper()
						and (options.get('ondelete') or 'NO ACTION').upper()
						== (constraint.ondelete or 'NO ACTION').upper()
						and (options.get('onupdate') or 'NO ACTION').upper()
						== (constraint.onupdate or 'NO ACTION').upper()
					)

				if not any(matches(actual) for actual in actual_fks):
					issues.append(
						f'{name}: falta o cambió la clave foránea {constraint.name or tuple(constraint.columns.keys())}'
					)

		indexes = {index['name']: index for index in inspector.get_indexes(name)}
		for expected in table.indexes:
			actual = indexes.get(expected.name)
			where = expected.dialect_options[connection.dialect.name].get('where')
			if actual is None or (
				tuple(actual['column_names']) != tuple(c.name for c in expected.columns)
				or bool(actual['unique']) != bool(expected.unique)
				or _normalize_sql(
					actual.get('dialect_options', {}).get(
						f'{connection.dialect.name}_where', ''
					)
				)
				!= _normalize_sql(where if where is not None else '')
			):
				issues.append(f'{name}: falta o cambió el índice {expected.name}')
	return issues


def _assert_schema(connection):
	issues = _schema_issues(connection, inspect(connection))
	if issues:
		detail = '\n'.join(f'• {issue}' for issue in issues[:10])
		if len(issues) > 10:
			detail += f'\n• Y {len(issues) - 10} diferencias adicionales.'
		raise RuntimeError(
			'La base existente tiene un esquema incompleto, alterado o legado. '
			'No se modificarán sus datos; requiere una migración revisada.\n\n' + detail
		)


def validate_schema(engine) -> None:
	"""Validate all ORM tables and the version without creating or repairing anything."""
	with engine.connect() as connection:
		_check_version(connection, inspect(connection))
		_assert_schema(connection)


def _ensure_schema(engine) -> None:
	from database.models import Base

	with engine.begin() as connection:
		inspector = inspect(connection)
		current = _check_version(connection, inspector)
		existing = set(inspector.get_table_names())
		if existing.intersection(Base.metadata.tables) or _META_TABLE in existing:
			_assert_schema(connection)
		else:
			Base.metadata.create_all(connection, checkfirst=True)
			_assert_schema(connection)
		_create_meta_table(connection)
		if current is None:
			connection.execute(
				text(f'INSERT INTO {_META_TABLE} (id, version) VALUES (1, :version)'),
				{'version': SCHEMA_VERSION},
			)
			logger.info('CloudPOS schema baseline v%s initialized.', SCHEMA_VERSION)


def run_migrations(engine) -> None:
	"""Initialize or validate the local offline database schema."""
	_ensure_schema(engine)


def setup_cloud_schema(engine) -> None:
	"""Initialize or validate the VPS reporting-replica schema."""
	_ensure_schema(engine)
