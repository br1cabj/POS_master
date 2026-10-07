from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from controllers.inventory_controller import InventoryController
from controllers.sales_controller import SalesController
from database.models import Article, ArticleVariant, Branch, Stock, Tenant, User, Warehouse
from utils.sync_worker import _read_cursor, _rows_after_cursor, _write_cursor


def test_fefo_stock_deduction_preserves_fractional_quantities():
	first = SimpleNamespace(
		id='stock-a', warehouse_id='warehouse-a', expiration_date=datetime(2026, 1, 1).date(),
		quantity=Decimal('0.25'),
	)
	second = SimpleNamespace(
		id='stock-b', warehouse_id='warehouse-a', expiration_date=datetime(2026, 2, 1).date(),
		quantity=Decimal('0.75'),
	)
	no_expiry = SimpleNamespace(
		id='stock-c', warehouse_id='warehouse-a', expiration_date=None, quantity=Decimal('5'),
	)

	allocations = SalesController._take_from_stock_rows(
		[no_expiry, second, first], Decimal('0.50')
	)

	assert [(row.id, qty) for row, qty in allocations] == [
		('stock-a', Decimal('0.25')),
		('stock-b', Decimal('0.25')),
	]
	assert first.quantity == Decimal('0')
	assert second.quantity == Decimal('0.50')
	assert no_expiry.quantity == Decimal('5')


def test_fefo_stock_deduction_rejects_insufficient_total_without_mutation():
	stock = SimpleNamespace(
		id='stock-a', warehouse_id='warehouse-a', expiration_date=None, quantity=Decimal('0.5')
	)

	with pytest.raises(ValueError, match='Stock insuficiente'):
		SalesController._take_from_stock_rows([stock], Decimal('0.6'))
	assert stock.quantity == Decimal('0.5')


def test_inventory_adjustment_removes_fractional_stock_exactly(test_db_session):
	tenant = Tenant(id='tenant-stock', name='Stock SA')
	user = User(
		id='user-stock', tenant_id=tenant.id, username='stock', password_hash='unused'
	)
	branch = Branch(id='branch-stock', tenant_id=tenant.id, name='Principal')
	warehouse = Warehouse(
		id='warehouse-stock', branch_id=branch.id, tenant_id=tenant.id, name='Depósito'
	)
	article = Article(id='article-stock', tenant_id=tenant.id, name='Harina')
	variant = ArticleVariant(
		id='variant-stock', tenant_id=tenant.id, article_id=article.id, cost_price=Decimal('1'), selling_price=Decimal('2')
	)
	stock = Stock(
		id='stock-fraction', tenant_id=tenant.id, variant_id=variant.id, warehouse_id=warehouse.id, quantity=Decimal('1.5')
	)
	test_db_session.add_all([tenant, user, branch, warehouse, article, variant, stock])
	test_db_session.commit()

	ok, _ = InventoryController(test_db_session.bind).adjust_stock(
		tenant.id, user.id, variant.id, '0.2000', 'Conteo físico'
	)

	assert ok
	test_db_session.refresh(stock)
	assert stock.quantity == Decimal('0.2000')


def test_sync_cursor_keeps_rows_with_the_same_timestamp(test_db_session):
	timestamp = datetime(2026, 1, 1, 12, 0, 0)
	first = Tenant(id='tenant-a', name='A', updated_at=timestamp)
	second = Tenant(id='tenant-b', name='B', updated_at=timestamp)
	test_db_session.add_all([first, second])
	test_db_session.commit()

	rows = _rows_after_cursor(
		test_db_session.query(Tenant), Tenant, timestamp, first.id
	).all()
	state = {}
	_write_cursor(state, 'tenants', second)

	assert [row.id for row in rows] == [second.id]
	assert _read_cursor(state['tenants']) == (timestamp, second.id)
	assert _read_cursor(timestamp.isoformat()) == (timestamp, '')
