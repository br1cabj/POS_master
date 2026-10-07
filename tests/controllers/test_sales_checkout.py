from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from controllers.sales_controller import SalesController
from database.models import CashMovement, Promotion, Sale, Stock, Warehouse
from tests.controllers.test_sales_pricing_guards import _sale_environment


def test_catalog_returns_stock_from_resolved_warehouse(test_db_session):
	tenant, _user, _category, variant = _sale_environment(test_db_session)
	controller = SalesController(test_db_session.bind)
	rows = controller.get_articles_for_sale(tenant.id)
	assert len(rows) == 1
	assert rows[0]['variant_id'] == variant.id
	assert rows[0]['total_stock'] == Decimal(20)
	assert rows[0]['selling_price_b'] == Decimal(80)


def test_catalog_keeps_zero_wholesale_price(test_db_session):
	tenant, _user, _category, variant = _sale_environment(test_db_session)
	variant.selling_price_b = Decimal(0)
	test_db_session.commit()
	controller = SalesController(test_db_session.bind)
	assert controller.get_articles_for_sale(tenant.id)[0]['selling_price_b'] == Decimal(
		0
	)
	assert controller.search_articles(tenant.id, 'Gaseosa')[0][
		'selling_price_b'
	] == Decimal(0)


def test_catalog_errors_are_not_disguised_as_empty_catalog(test_db_session):
	controller = SalesController(test_db_session.bind)
	with patch.object(
		controller, '_resolve_warehouse', side_effect=RuntimeError('DB unavailable')
	):
		with pytest.raises(RuntimeError, match='DB unavailable'):
			controller.get_articles_for_sale('t')


def test_quote_uses_current_database_prices_and_never_writes(test_db_session):
	tenant, _user, _category, variant = _sale_environment(test_db_session)
	controller = SalesController(test_db_session.bind)
	lines, total = controller.quote_cart(
		tenant.id, [dict(variant_id=variant.id, qty='2', price='1')], 'B', '10'
	)
	assert lines[0]['price'] == Decimal(80)
	assert lines[0]['subtotal'] == Decimal(160)
	assert total == Decimal(144)
	assert test_db_session.query(Sale).count() == 0
	assert test_db_session.query(CashMovement).count() == 0
	assert test_db_session.query(Stock).one().quantity == Decimal(20)


def test_changed_total_rolls_back_stock_sale_and_cash(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	controller = SalesController(test_db_session.bind)
	ok, message = controller.process_sale(
		tenant.id,
		user.id,
		[dict(variant_id=variant.id, qty='2', price='100')],
		payment_method='tarjeta',
		price_list='B',
		expected_total='200',
	)
	assert not ok
	assert 'precios cambiaron' in message.lower()
	test_db_session.expire_all()
	assert test_db_session.query(Sale).count() == 0
	assert test_db_session.query(CashMovement).count() == 0
	assert test_db_session.query(Stock).one().quantity == Decimal(20)


def test_fractional_quantity_quote_matches_stored_rounded_total(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	variant.selling_price = Decimal('10.01')
	test_db_session.commit()
	controller = SalesController(test_db_session.bind)
	cart = [dict(variant_id=variant.id, qty='.3333', price='10.01')]
	lines, total = controller.quote_cart(tenant.id, cart)
	assert total == Decimal('3.34')
	with patch('controllers.receipt_controller.ReceiptController.generate_pdf'):
		ok, message = controller.process_sale(
			tenant.id, user.id, lines, expected_total=total, paid_amount='3.34'
		)
	assert ok, message
	test_db_session.expire_all()
	sale = test_db_session.query(Sale).one()
	assert sale.total_amount == total
	assert sale.items[0].subtotal == total


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-1', '0', '1.001'])
def test_invalid_split_payment_cannot_fall_back_to_simple_sale(test_db_session, amount):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	ok, _msg = SalesController(test_db_session.bind).process_sale(
		tenant.id,
		user.id,
		[dict(variant_id=variant.id, qty='1', price='100')],
		payment_method='efectivo',
		payment_method_2='tarjeta',
		amount_method_2=amount,
	)
	assert not ok
	assert test_db_session.query(Sale).count() == 0


def test_qr_aliases_cannot_be_used_as_two_distinct_methods(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	ok, message = SalesController(test_db_session.bind).process_sale(
		tenant.id,
		user.id,
		[dict(variant_id=variant.id, qty='1', price='100')],
		payment_method='qr',
		payment_method_2='QR Billetera',
		amount_method_2='50',
	)
	assert not ok
	assert 'distintos' in message


def test_missing_warehouse_returns_regular_failure_tuple(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	test_db_session.query(Warehouse).update({'is_active': False})
	test_db_session.commit()
	result = SalesController(test_db_session.bind).process_sale(
		tenant.id, user.id, [dict(variant_id=variant.id, qty='1', price='100')]
	)
	assert isinstance(result, tuple) and result[0] is False


@pytest.mark.parametrize('field', ['qty', 'discount_pct', 'paid_amount'])
def test_nonfinite_sale_values_are_rejected_without_writes(test_db_session, field):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	cart = [dict(variant_id=variant.id, qty='1', price='100')]
	kwargs = {}
	if field == 'qty':
		cart[0]['qty'] = 'Infinity'
	else:
		kwargs[field] = 'Infinity'
	ok, _message = SalesController(test_db_session.bind).process_sale(
		tenant.id, user.id, cart, **kwargs
	)
	assert not ok
	assert test_db_session.query(Sale).count() == 0


def test_checkout_quote_rejects_stock_shortage_before_payment(test_db_session):
	tenant, _user, _category, variant = _sale_environment(test_db_session)
	with pytest.raises(ValueError, match='Stock insuficiente'):
		SalesController(test_db_session.bind).quote_cart(
			tenant.id,
			[dict(variant_id=variant.id, qty='21', price='100')],
			validate_stock=True,
		)
	assert test_db_session.query(Sale).count() == 0
	assert test_db_session.query(Stock).one().quantity == Decimal(20)


def test_expired_promotion_between_quote_and_save_rolls_back(test_db_session):
	tenant, user, category, variant = _sale_environment(test_db_session)
	promo = Promotion(
		tenant_id=tenant.id,
		name='Oferta',
		promo_type='pct',
		discount_value=Decimal(10),
		category_id=category.id,
		date_from=datetime.now() - timedelta(days=2),
		date_to=datetime.now() + timedelta(days=1),
	)
	test_db_session.add(promo)
	test_db_session.commit()
	controller = SalesController(test_db_session.bind)
	lines, total = controller.quote_cart(
		tenant.id, [dict(variant_id=variant.id, qty='1', price='1')]
	)
	assert total == Decimal(90)
	promo.date_to = datetime.now() - timedelta(days=1)
	test_db_session.commit()
	ok, msg = controller.process_sale(
		tenant.id, user.id, lines, payment_method='transferencia', expected_total=total
	)
	assert not ok and 'precios cambiaron' in msg.lower()
	assert test_db_session.query(Sale).count() == 0


def test_format_failure_cannot_leave_committed_sale_reported_as_failed(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	with patch(
		'controllers.sales_controller.settings_manager.fmt_price',
		side_effect=PermissionError('settings'),
	):
		ok, _message = SalesController(test_db_session.bind).process_sale(
			tenant.id, user.id, [dict(variant_id=variant.id, qty='1', price='100')]
		)
	assert not ok
	assert test_db_session.query(Sale).count() == 0
	assert test_db_session.query(CashMovement).count() == 0
