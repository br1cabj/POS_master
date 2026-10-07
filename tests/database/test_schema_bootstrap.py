"""The version guard must detect schema drift before modifying an existing DB."""

import pytest
from sqlalchemy import CheckConstraint, MetaData, Numeric, inspect, text

from database.migrations import (
	_normalize_sql,
	run_migrations,
	setup_cloud_schema,
	validate_schema,
)
from database.models import Base
from utils.config import make_engine


@pytest.fixture
def engine():
	engine = make_engine('sqlite:///:memory:')
	yield engine
	engine.dispose()


def test_fresh_schema_is_complete_and_bootstrap_is_idempotent(engine):
	run_migrations(engine)
	setup_cloud_schema(engine)
	validate_schema(engine)
	with engine.connect() as connection:
		assert connection.execute(text('PRAGMA foreign_keys')).scalar() == 1
		assert connection.execute(
			text('SELECT version FROM cloudpos_schema_meta')
		).all() == [(1,)]
	assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())


@pytest.mark.parametrize(
	'alteration, expected',
	[
		('DROP INDEX uq_cash_open_session', 'uq_cash_open_session'),
		('DROP TABLE article_history', 'article_history'),
		('ALTER TABLE sales DROP COLUMN payment_method_2', 'payment_method_2'),
	],
)
def test_existing_schema_is_rejected_without_repair_or_version_changes(
	engine, alteration, expected
):
	run_migrations(engine)
	with engine.begin() as connection:
		connection.execute(text(alteration))
	before = set(inspect(engine).get_table_names())
	with pytest.raises(RuntimeError, match=expected):
		run_migrations(engine)
	assert set(inspect(engine).get_table_names()) == before
	with engine.connect() as connection:
		assert (
			connection.execute(
				text('SELECT version FROM cloudpos_schema_meta')
			).scalar()
			== 1
		)


@pytest.mark.parametrize(
	'replacement',
	[
		'CREATE INDEX uq_cash_open_session ON cash_sessions (tenant_id, user_id) WHERE is_open = 1',
		'CREATE UNIQUE INDEX uq_cash_open_session ON cash_sessions (tenant_id, user_id) WHERE is_open = 0',
		'CREATE UNIQUE INDEX uq_cash_open_session ON cash_sessions (id) WHERE is_open = 1',
	],
)
def test_same_index_name_cannot_hide_a_weakened_definition(engine, replacement):
	run_migrations(engine)
	with engine.begin() as connection:
		connection.execute(text('DROP INDEX uq_cash_open_session'))
		connection.execute(text(replacement))
	with pytest.raises(RuntimeError, match='uq_cash_open_session'):
		validate_schema(engine)


@pytest.mark.parametrize(
	'name',
	[
		'chk_stock_quantity_positive',
		'fk_stock_variant_same_tenant',
		'uq_stock_variant_warehouse_batch',
	],
)
def test_missing_business_or_tenant_constraint_is_rejected(engine, name):
	metadata = MetaData()
	for table in Base.metadata.sorted_tables:
		table.to_metadata(metadata)
	stock = metadata.tables['stocks']
	stock.constraints.remove(next(c for c in stock.constraints if c.name == name))
	metadata.create_all(engine)
	with pytest.raises(RuntimeError, match=name):
		run_migrations(engine)
	assert 'cloudpos_schema_meta' not in inspect(engine).get_table_names()


def test_check_constraint_with_same_name_and_weaker_condition_is_rejected(engine):
	metadata = MetaData()
	for table in Base.metadata.sorted_tables:
		table.to_metadata(metadata)
	stock = metadata.tables['stocks']
	name = 'chk_stock_quantity_positive'
	stock.constraints.remove(next(c for c in stock.constraints if c.name == name))
	stock.append_constraint(CheckConstraint('quantity >= -1', name=name))
	metadata.create_all(engine)
	with pytest.raises(RuntimeError, match=name):
		run_migrations(engine)


def test_wrong_version_is_checked_before_creating_any_application_table(engine):
	with engine.begin() as connection:
		connection.execute(
			text(
				'CREATE TABLE cloudpos_schema_meta (id INTEGER PRIMARY KEY, version INTEGER)'
			)
		)
		connection.execute(text('INSERT INTO cloudpos_schema_meta VALUES (1, 99)'))
	with pytest.raises(RuntimeError, match='v99'):
		run_migrations(engine)
	assert inspect(engine).get_table_names() == ['cloudpos_schema_meta']


@pytest.mark.parametrize('change', ['precision', 'nullable'])
def test_column_precision_and_nullability_are_validated(engine, change):
	metadata = MetaData()
	for table in Base.metadata.sorted_tables:
		table.to_metadata(metadata)
	column = metadata.tables['stocks'].c.quantity
	if change == 'precision':
		column.type = Numeric(12, 2)
	else:
		column.nullable = True
	metadata.create_all(engine)
	with pytest.raises(RuntimeError, match='stocks.quantity'):
		run_migrations(engine)


@pytest.mark.parametrize(
	'expected, reflected',
	[
		(
			"status IN ('A', 'B')",
			"((status)::text = ANY (ARRAY['A'::character varying, 'B'::character varying]::text[]))",
		),
		('quantity >= 0', '(quantity >= (0)::numeric)'),
		(
			"(promo_type <> 'nxm') OR (buy_qty > 0 AND pay_qty > 0 AND pay_qty <= buy_qty)",
			"(((promo_type)::text <> 'nxm'::text) OR ((buy_qty > 0) AND (pay_qty > 0) AND (pay_qty <= buy_qty)))",
		),
		(
			"barcode IS NOT NULL AND barcode <> '' AND is_active",
			"((barcode IS NOT NULL) AND ((barcode)::text <> ''::text) AND is_active)",
		),
	],
)
def test_postgresql_reflection_preserves_predicate_meaning(expected, reflected):
	assert _normalize_sql(expected) == _normalize_sql(reflected)


def test_boolean_grouping_and_string_case_are_not_discarded():
	assert _normalize_sql('a OR (b AND c)') != _normalize_sql('(a OR b) AND c')
	assert _normalize_sql("status IN ('A')") != _normalize_sql("status IN ('a')")
