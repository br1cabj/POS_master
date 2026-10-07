"""Build actual Tk widgets off-screen; never open the user's real database."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import customtkinter as ctk
import pytest

from core.context import AppContext
from tests.controllers.test_sales_pricing_guards import _sale_environment
from views.sales_view import SalesView


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_real_sales_widgets_and_dialogs_build_at_common_scalings(
	test_db_session, scale
):
	tenant, user, _category, _variant = _sale_environment(test_db_session)
	root = ctk.CTk()
	root.withdraw()
	root.geometry('1280x900')
	ctk.set_widget_scaling(scale)
	original_toplevel = ctk.CTkToplevel
	dialogs = []

	def hidden_dialog(*args, **kwargs):
		dialog = original_toplevel(*args, **kwargs)
		dialog.withdraw()
		dialog.grab_set = MagicMock()
		dialogs.append(dialog)
		return dialog

	view = None
	try:
		ctx = AppContext(
			test_db_session.bind,
			{'id': user.id, 'tenant_id': tenant.id, 'role': 'admin'},
			MagicMock(),
		)
		with (
			patch.object(SalesView, 'load_data'),
			patch('views.sales_view.ctk.CTkToplevel', side_effect=hidden_dialog),
		):
			view = SalesView(root, ctx)
			view.pack(fill='both', expand=True)
			variants = view.sales_ctrl.get_articles_for_sale(tenant.id)
			variants[0]['show_on_touch'] = True
			variants[0]['total_stock'] = Decimal('20.5')
			view._cash_ctrl.get_active_session = MagicMock(return_value=object())
			view._apply_catalog_payload('Consumidor Final', variants, [], [])
			view.qty_entry.delete(0, 'end')
			view.qty_entry.insert(0, '2')
			assert view._add_variant_to_cart(variants[0], '2')
			assert view.cart[0]['subtotal'] == Decimal(200)
			view._set_price_list('B')
			assert view.cart[0]['subtotal'] == Decimal(160)
			view._open_dropdown(variants)
			view._move_dropdown_selection(1)
			view._close_dropdown()
			view.process_sale()
			assert view.popup is not None
			assert view.current_total == Decimal(160)
			view._select_payment('Transferencia')
			view._mixto_var.set(True)
			view._toggle_mixto()
			view.entry_amount_2.insert(0, '60')
			view._on_amount2_change()
			assert '100' in view._lbl_amount_1_auto.cget('text')
			view._cancel_checkout()
			assert view.popup is None
			view.tree.selection_set(view.cart[0]['tree_id'])
			view._on_cart_double_click()
			view._open_venta_libre_popup()
			free_dialog = next(
				w for w in dialogs if w.winfo_exists() and w.title() == 'Venta Libre'
			)

			def children(widget):
				result = list(widget.winfo_children())
				return result + [child for item in result for child in children(item)]

			entries = [w for w in children(free_dialog) if isinstance(w, ctk.CTkEntry)]
			entries[0].insert(0, 'Artículo libre')
			entries[1].insert(0, 'Infinity')
			button = next(
				w for w in children(free_dialog) if isinstance(w, ctk.CTkButton)
			)
			button.invoke()
			assert free_dialog.winfo_exists()
			assert len(view.cart) == 1
			assert entries[0].get() == 'Artículo libre'
			entries[1].delete(0, 'end')
			entries[1].insert(0, '10.25')
			button.invoke()
			assert not free_dialog.winfo_exists()
			assert len(view.cart) == 2
			root.update_idletasks()
	finally:
		if view is not None and view.winfo_exists():
			view.destroy_custom()
			view.destroy()
		root.destroy()
		ctk.set_widget_scaling(1.0)
