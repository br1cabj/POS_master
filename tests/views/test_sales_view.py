"""POS regressions without a display: exercise real handlers with widget doubles."""

import queue
import tkinter
from datetime import datetime, timedelta
from decimal import Decimal
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from controllers.promo_controller import PromoController
from views.sales_view import SalesView


def _view():
	view = SimpleNamespace()
	for name, member in SalesView.__dict__.items():
		if isinstance(member, staticmethod):
			setattr(view, name, member.__func__)
		elif callable(member) and not name.startswith('__'):
			setattr(view, name, MethodType(member, view))
	view.ctx = SimpleNamespace(
		tenant_id='t', user_id='u', is_admin=True, db_engine=None
	)
	view.cart, view.db_variants, view.touch_buttons = [], [], []
	view.customer_map = {'Mayorista': {'id': 'c', 'price_list': 'B'}}
	view.customers_combo = MagicMock()
	view.customers_combo.get.return_value = 'Mayorista'
	view._active_price_list = 'A'
	view._active_promos = []
	view.promo_ctrl = PromoController.__new__(PromoController)
	view._btn_price_list = MagicMock()
	view.tree = MagicMock()
	view.tree.insert.side_effect = [f'row-{i}' for i in range(20)]
	view.entry_barcode = MagicMock()
	view.qty_entry = MagicMock()
	view.qty_entry.get.return_value = '1'
	view.entry_manual_search = view.entry_barcode
	view.entry_fast_desc, view.entry_fast_price, view.entry_fast_qty = (
		MagicMock(),
		MagicMock(),
		MagicMock(),
	)
	view.lbl_msg, view.btn_pay, view.btn_remove = MagicMock(), MagicMock(), MagicMock()
	view.update_total = MagicMock()
	view._set_msg = MagicMock()
	view._flash_new_item = MagicMock()
	view._beep_ok, view._beep_err = MagicMock(), MagicMock()
	view._restore_scan_focus = MagicMock()
	view._is_loading_data = False
	view._catalog_ok, view._cash_ready = True, True
	view._search_mode, view._barcode_timer = 'scan', None
	view._discount_pct, view._discount_amount = Decimal(0), Decimal(0)
	view.sales_ctrl = MagicMock()
	view._context_data = {}
	view.schedule, view.after, view.after_cancel = MagicMock(), MagicMock(), MagicMock()
	view._checkout_results_queue = queue.Queue()
	view._saving = False
	return view


def _variant(**changes):
	return dict(
		variant_id='v',
		name='Artículo',
		barcode='00123',
		selling_price=Decimal('100'),
		selling_price_b=Decimal('80'),
		total_stock=Decimal('20'),
		category_id='cat',
		**changes,
	)


@pytest.mark.parametrize(
	'raw',
	['NaN', 'sNaN', 'Infinity', '-Infinity', '0', '-1', 'abc', '1.00001', '1e100'],
)
def test_quantity_validation_rejects_special_invalid_or_unrepresentable_values(raw):
	with pytest.raises(ValueError):
		SalesView._positive_decimal(raw)


@pytest.mark.parametrize('raw', ['NaN', 'Infinity', '-1', '1.001', '1e100'])
def test_payment_validation(raw):
	with pytest.raises(ValueError):
		SalesView._payment_amount(raw)


def test_zero_cash_payment_allowed_for_fully_discounted_sale():
	assert SalesView._payment_amount('0') == Decimal(0)


def test_price_list_and_customer_changes_reprice_existing_cart():
	view = _view()
	view.db_variants = [_variant()]
	assert view._add_variant_to_cart(view.db_variants[0], '2')
	assert view.cart[0]['subtotal'] == Decimal('200')
	view._on_customer_changed('Mayorista')
	assert view.cart[0]['subtotal'] == Decimal('160')
	assert view.cart[0]['desc'].startswith('💼')
	view._set_price_list('A')
	assert view.cart[0]['subtotal'] == Decimal('200')


def test_zero_price_b_is_not_missing():
	view = _view()
	view._active_price_list = 'B'
	assert view._get_list_price({'selling_price': 100, 'selling_price_b': 0}) == 0


@pytest.mark.parametrize('method', ['barcode', 'touch'])
def test_all_add_paths_respect_quantity(method):
	view = _view()
	view.db_variants = [_variant()]
	view.qty_entry.get.return_value = '2,5'
	view.entry_barcode.get.return_value = '00123'
	if method == 'barcode':
		view.add_by_barcode()
	else:
		view.add_from_touch('v')
	assert view.cart[0]['qty'] == Decimal('2.5')
	assert view.cart[0]['subtotal'] == Decimal('250')


def test_invalid_scale_code_preserves_input_without_crashing():
	view = _view()
	view.entry_barcode.get.return_value = '20abcde123456'
	assert len(view.entry_barcode.get()) == 13
	view.add_by_barcode()
	assert view.cart == []
	view.entry_barcode.delete.assert_not_called()
	view._set_msg.assert_called_once()


def test_scale_uses_same_discounts_and_list_as_other_products():
	view = _view()
	view.db_variants = [dict(_variant(), barcode='00001', discount_pct=10)]
	view._active_price_list = 'B'
	view.entry_barcode.get.return_value = (
		'2000001005000'  # PLU 1, importe 5.00 a precio A 100.
	)
	view.add_by_barcode()
	assert view.cart[0]['qty'] == Decimal('.05')
	assert view.cart[0]['price'] == Decimal('72')
	assert view.cart[0]['subtotal'] == Decimal('3.60')


def test_exact_registered_ean_wins_over_scale_prefix():
	view = _view()
	view.db_variants = [dict(_variant(), barcode='2000001005000')]
	view.entry_barcode.get.return_value = '2000001005000'
	view.qty_entry.get.return_value = '3'
	view.add_by_barcode()
	assert view.cart[0]['qty'] == Decimal(3)
	assert view.cart[0]['subtotal'] == Decimal(300)


def test_expired_promos_are_not_used_from_cache():
	view = _view()
	view._active_promos = [
		dict(
			id='p',
			name='Promo',
			variant_id='v',
			is_active=True,
			date_from=datetime.now() - timedelta(days=2),
			date_to=datetime.now() - timedelta(days=1),
		)
	]
	assert view._find_promo_for_variant(_variant()) is None


def test_clear_cart_keeps_selected_customer_price_list():
	view = _view()
	view.cart = [{'tree_id': 'r'}]
	view._flash_timers = {}
	view._set_discount_pct = MagicMock()
	view.clear_entire_cart()
	assert view.cart == []
	assert view._active_price_list == 'B'
	view._btn_price_list.configure.assert_called()


def test_enter_cannot_select_result_from_old_query():
	view = _view()
	view._dropdown_query = 'viejo'
	view._dropdown_items = [_variant()]
	view.entry_barcode.get.return_value = 'nuevo'
	view._close_dropdown = MagicMock()
	view._update_dropdown = MagicMock()
	view._select_from_dropdown = MagicMock()
	view._select_first_dropdown_item()
	view._select_from_dropdown.assert_not_called()
	view._update_dropdown.assert_called_once()


def test_missing_restore_line_does_not_cancel_original_or_restore_partially():
	view = _view()
	view.db_variants = [_variant()]
	view._context_data = {'cancel_original_sale': True}
	sale = dict(
		id='original',
		items=[
			{'variant_id': 'v', 'quantity': 1},
			{'variant_id': 'deleted', 'quantity': 1, 'description': 'Eliminado'},
		],
	)
	with patch('controllers.returns_controller.ReturnsController') as returns:
		assert not view._load_restored_sale(sale)
		returns.assert_not_called()
	assert view.cart == []
	view.tree.insert.assert_not_called()
	assert view._context_data['cancel_original_sale']


def test_successful_restore_uses_customer_b_and_cancels_after_rendering():
	view = _view()
	view.db_variants = [_variant()]
	view._context_data = {'cancel_original_sale': True}
	line = dict(
		variant_id='v',
		qty=Decimal(2),
		price=Decimal(80),
		subtotal=Decimal(160),
		desc='Artículo',
	)
	view.sales_ctrl.quote_cart.return_value = ([line], Decimal(160))
	sale = dict(
		id='original',
		customer_name='Mayorista',
		items=[{'variant_id': 'v', 'quantity': 2}],
	)
	with patch('controllers.returns_controller.ReturnsController') as returns:

		def cancel(*args):
			assert len(view.cart) == 1
			view.tree.item.assert_called()
			return True, 'OK'

		returns.return_value.cancel_sale.side_effect = cancel
		assert view._load_restored_sale(sale)
	view.sales_ctrl.quote_cart.assert_called_once()
	assert view.sales_ctrl.quote_cart.call_args.args[2] == 'B'
	assert not view._context_data['cancel_original_sale']


def test_failed_cancellation_rolls_back_prepared_cart():
	view = _view()
	view.db_variants = [_variant()]
	view._context_data = {'cancel_original_sale': True}
	view.sales_ctrl.quote_cart.return_value = (
		[
			dict(
				variant_id='v',
				qty=Decimal(1),
				price=Decimal(100),
				subtotal=Decimal(100),
				desc='Artículo',
			)
		],
		Decimal(100),
	)
	with patch('controllers.returns_controller.ReturnsController') as returns:
		returns.return_value.cancel_sale.return_value = False, 'Caja cerrada'
		assert not view._load_restored_sale(
			dict(id='original', items=[{'variant_id': 'v', 'quantity': 1}])
		)
	assert view.cart == []
	assert view._context_data['cancel_original_sale']


def test_pay_state_requires_cart_catalog_and_cash():
	view = _view()
	for loading, catalog, cash, cart, expected in [
		(False, True, True, [], 'disabled'),
		(True, True, True, [1], 'disabled'),
		(False, False, True, [1], 'disabled'),
		(False, True, False, [1], 'disabled'),
		(False, True, True, [1], 'normal'),
	]:
		view._is_loading_data, view._catalog_ok, view._cash_ready, view.cart = (
			loading,
			catalog,
			cash,
			cart,
		)
		view._refresh_pay_state()
		view.btn_pay.configure.assert_called_with(state=expected)


def test_delete_shortcut_does_not_remove_cart_while_typing_and_f6_forces_focus():
	view = _view()
	top = MagicMock()
	top.grab_current.return_value = None
	top.focus_get.return_value = MagicMock(spec=tkinter.Entry)
	handlers = {}
	top.bind.side_effect = lambda key, handler, **kw: handlers.setdefault(key, handler)
	view.winfo_toplevel = lambda: top
	view.winfo_ismapped = lambda: True
	view.bind = MagicMock()
	view.remove_from_cart = MagicMock()
	view.setup_shortcuts()
	assert handlers['<Delete>']() is None
	view.remove_from_cart.assert_not_called()
	handlers['<F6>']()
	view._restore_scan_focus.assert_called_once_with(force=True)
	top.focus_get.return_value = MagicMock(spec=tkinter.ttk.Treeview)
	assert handlers['<Delete>']() == 'break'
	view.remove_from_cart.assert_called_once()


def test_invalid_free_sale_returns_failure_without_changing_cart():
	view = _view()
	view.entry_fast_desc.get.return_value = 'Artículo libre'
	view.entry_fast_price.get.return_value = 'Infinity'
	view.entry_fast_qty.get.return_value = '1'
	assert view.add_fast_to_cart() is False
	assert view.cart == []


def test_changed_checkout_quote_updates_cart_and_requires_confirmation():
	view = _view()
	view.cart = [
		dict(
			tree_id='r',
			qty=Decimal(1),
			price=Decimal(100),
			subtotal=Decimal(100),
			desc='Artículo',
		)
	]
	view.sales_ctrl.quote_cart.return_value = (
		[dict(view.cart[0], price=Decimal(80), subtotal=Decimal(80))],
		Decimal(80),
	)
	view.confirm = MagicMock(return_value=False)
	assert not view._prepare_checkout()
	assert view.cart[0]['subtotal'] == Decimal(80)
	view.confirm.assert_called_once()


def test_checkout_worker_uses_snapshot_and_ui_only_consumes_queue():
	view = _view()
	view.current_total = Decimal(100)
	view.cart = [dict(variant_id='v', qty=Decimal(1), price=Decimal(100))]
	view.sales_ctrl.process_sale.return_value = True, 'OK'
	view._finish_sale = MagicMock()
	with patch('views.sales_view.threading.Thread') as thread:
		thread.side_effect = lambda **kw: SimpleNamespace(start=kw['target'])
		view.finalize_sale(None, False, 'Efectivo', paid_amount='100')
	assert view._saving
	view._finish_sale.assert_not_called()
	assert view.sales_ctrl.process_sale.call_args.kwargs['expected_total'] == Decimal(
		100
	)
	view._poll_checkout_results()
	assert not view._saving
	view._finish_sale.assert_called_once_with(True, 'OK')


def test_catalog_failure_keeps_previous_data_and_disables_checkout():
	view = _view()
	view.db_variants = [_variant()]
	view._is_loading_data = True
	view._apply_catalog_payload('Mayorista', [], [], [], error='DB unavailable')
	assert view.db_variants == [_variant()]
	assert not view._catalog_ok
	assert not view._is_loading_data
	view.btn_pay.configure.assert_called_with(state='disabled')
	view.entry_barcode.focus.assert_not_called()


def test_error_messages_persist_but_success_messages_expire():
	view = _view()
	view._msg_timer_id = None
	from views.sales_view import RED_TEXT

	SalesView._set_msg(view, 'Error', RED_TEXT)
	view.schedule.assert_not_called()
	SalesView._set_msg(view, 'Agregado')
	view.schedule.assert_called_once()


def test_mixed_payment_summary_updates_when_first_method_changes():
	view = _view()
	view._mixto_var = MagicMock()
	view._mixto_var.get.return_value = True
	view._pay_btns = {}
	view._on_amount2_change = MagicMock()
	view._select_payment('QR')
	assert view._payment_method == 'QR'
	view._on_amount2_change.assert_called_once()


def test_restore_render_failure_does_not_cancel_original():
	view = _view()
	view.db_variants = [_variant()]
	view._context_data = {'cancel_original_sale': True}
	view.sales_ctrl.quote_cart.return_value = (
		[
			dict(
				variant_id='v',
				qty=Decimal(1),
				price=Decimal(100),
				subtotal=Decimal(100),
				desc='Artículo',
			)
		],
		Decimal(100),
	)
	view.tree.item.side_effect = RuntimeError('render failed')
	with patch('controllers.returns_controller.ReturnsController') as returns:
		assert not view._load_restored_sale(
			dict(id='original', items=[{'variant_id': 'v', 'quantity': 1}])
		)
		returns.assert_not_called()
	assert view.cart == []
	assert view._context_data['cancel_original_sale']
