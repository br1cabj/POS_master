import pytest
from unittest.mock import MagicMock
from views.customers_view import CustomersView

def test_customers_sorting():
    # Mock CustomersView and self.tree
    view = MagicMock(spec=CustomersView)
    view.tree = MagicMock()
    view.tree.get_children.return_value = ['item1', 'item2', 'item3']

    # 1. Test ID sorting (numerical instead of alphabetical)
    values = {'item1': '15', 'item2': '2', 'item3': '100'}
    view.tree.set.side_effect = lambda k, col: values[k]

    CustomersView._sort(view, 'ID', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item2', '', 0) # 2
    assert move_calls[1][0] == ('item1', '', 1) # 15
    assert move_calls[2][0] == ('item3', '', 2) # 100

    # 2. Test Deuda Acumulada sorting (debts positive, credits negative)
    # Expecting: A favor (-10.00) < Zero (0.00) < Debtor (+150.50)
    values = {'item1': '$150.50', 'item2': 'A favor: $10.00', 'item3': '$0.00'}
    view.tree.set.side_effect = lambda k, col: values[k]

    view.tree.reset_mock()
    CustomersView._sort(view, 'Deuda Acumulada', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item2', '', 0)
    assert move_calls[1][0] == ('item3', '', 1)
    assert move_calls[2][0] == ('item1', '', 2)

    # 3. Test Último Fiado sorting (DD/MM/YYYY dates, placeholder '-' at start/end)
    # Expected ascending: - (placeholder), 01/01/2025, 24/06/2026
    values = {'item1': '24/06/2026', 'item2': '-', 'item3': '01/01/2025'}
    view.tree.set.side_effect = lambda k, col: values[k]

    view.tree.reset_mock()
    CustomersView._sort(view, 'Último Fiado', False)
    move_calls = view.tree.move.call_args_list
    assert move_calls[0][0] == ('item2', '', 0)
    assert move_calls[1][0] == ('item3', '', 1)
    assert move_calls[2][0] == ('item1', '', 2)
