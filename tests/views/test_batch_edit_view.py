import pytest
from unittest.mock import MagicMock
from views.batch_edit_view import BatchEditView

def test_sorting_key():
    # Mock BatchEditView and self.tree
    view = MagicMock(spec=BatchEditView)
    view.tree = MagicMock()
    view.tree.get_children.return_value = ['item1', 'item2', 'item3']

    # 1. Test string sorting (e.g. Producto) ascending
    # '—' maps to 'zzzzzzzz', so expected: item3 (Banana), item1 (Manzana), item2 (—)
    values = {'item1': 'Manzana', 'item2': '—', 'item3': 'Banana'}
    view.tree.set.side_effect = lambda k, col: values[k]

    BatchEditView._sort(view, 'Producto', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item3', '', 0)
    assert move_calls[1][0] == ('item1', '', 1)
    assert move_calls[2][0] == ('item2', '', 2)

    # 2. Test string sorting descending (reverse=True)
    # '—' maps to '', so expected: item1 (Manzana), item3 (Banana), item2 (—)
    view.tree.reset_mock()
    BatchEditView._sort(view, 'Producto', True)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item1', '', 0)
    assert move_calls[1][0] == ('item3', '', 1)
    assert move_calls[2][0] == ('item2', '', 2)

    # 3. Test currency sorting (P.Venta / P.Costo)
    values = {'item1': '$150.50', 'item2': '$9.99', 'item3': '$20.00'}
    view.tree.set.side_effect = lambda k, col: values[k]

    view.tree.reset_mock()
    BatchEditView._sort(view, 'P.Venta', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item2', '', 0) # 9.99
    assert move_calls[1][0] == ('item3', '', 1) # 20.00
    assert move_calls[2][0] == ('item1', '', 2) # 150.50

    # 4. Test stock sorting (numerical instead of alphabetical)
    # Alphabetically, "100" < "15" < "2.5".
    # Numerically, 2.5 < 15 < 100.
    values = {'item1': '100', 'item2': '2.5', 'item3': '15'}
    view.tree.set.side_effect = lambda k, col: values[k]

    view.tree.reset_mock()
    BatchEditView._sort(view, 'Stock', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item2', '', 0) # 2.5
    assert move_calls[1][0] == ('item3', '', 1) # 15
    assert move_calls[2][0] == ('item1', '', 2) # 100

    # 5. Test checkboxes sorting (Sel)
    values = {'item1': '☑', 'item2': '☐', 'item3': '☑'}
    view.tree.set.side_effect = lambda k, col: values[k]

    view.tree.reset_mock()
    BatchEditView._sort(view, 'Sel', False)
    move_calls = view.tree.move.call_args_list
    # ☐ sorts as 0, ☑ sorts as 1, so item2 must be at index 0
    assert move_calls[0][0] == ('item2', '', 0)
