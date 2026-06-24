import pytest
from unittest.mock import MagicMock, patch
from views.prices_view import PricesView

@patch('views.prices_view._TABS')
def test_prices_view_switch_tab_lazy_loading(mock_tabs):
    # Arrange
    view = MagicMock(spec=PricesView)
    view._active_idx = 0
    view._loaded_views = {0: False, 1: False, 2: False}
    
    frame0 = MagicMock()
    frame1 = MagicMock()
    frame2 = MagicMock()
    view._frames = [frame0, frame1, frame2]
    
    view_cls_0 = MagicMock()
    view_cls_1 = MagicMock()
    view_cls_2 = MagicMock()
    
    # Set up our mocked _TABS
    mock_tabs.__getitem__.side_effect = lambda idx: [
        ('🛠️', 'Atributos y Precios', view_cls_0),
        ('📈', 'Ajuste de Precios', view_cls_1),
        ('💵', 'Precios al Dólar', view_cls_2)
    ][idx]
    
    instance0 = MagicMock()
    view_cls_0.return_value = instance0
    view.ctx = MagicMock()
    view._tab_btns = [MagicMock(), MagicMock(), MagicMock()]

    # Act - Switch to Tab 0 (not loaded yet)
    PricesView._switch_tab(view, 0)

    # Assert - Tab 0 instantiated and packed
    view_cls_0.assert_called_once_with(frame0, view.ctx)
    instance0.pack.assert_called_once_with(fill='both', expand=True)
    assert view._loaded_views[0] == instance0
    
    # Act - Switch to Tab 1 (not loaded yet)
    instance1 = MagicMock()
    view_cls_1.return_value = instance1
    PricesView._switch_tab(view, 1)
    
    # Assert - Tab 1 instantiated and packed, frame 0 forgets packing
    view_cls_1.assert_called_once_with(frame1, view.ctx)
    instance1.pack.assert_called_once_with(fill='both', expand=True)
    assert view._loaded_views[1] == instance1
    frame0.pack_forget.assert_called_once()
    
    # Act - Switch back to Tab 0 (already loaded!)
    PricesView._switch_tab(view, 0)
    
    # Assert - Since Tab 0 was already loaded, it should call load_data
    # view_cls_0 should not be instantiated again
    assert view_cls_0.call_count == 1
    instance0.load_data.assert_called_once()
