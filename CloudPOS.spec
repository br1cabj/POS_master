# -*- mode: python ; coding: utf-8 -*-
import importlib.util
import os


def _pkg_dir(name):
    """Devuelve el directorio raíz de un paquete instalado."""
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise RuntimeError(f"Paquete '{name}' no encontrado – activa el venv primero.")
    return os.path.dirname(spec.origin)


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (_pkg_dir('customtkinter'), 'customtkinter/'),
        (_pkg_dir('CTkMessagebox'), 'CTkMessagebox/'),
        ('icono.ico', '.'),
    ],
    hiddenimports=[
        # ── Vistas cargadas dinámicamente vía importlib (main_dashboard.py) ──
        'views.home_view',
        'views.sales_view',
        'views.cash_view',
        'views.articles_view',
        'views.prices_view',
        'views.label_view',
        'views.combo_maker_view',
        'views.purchases_view',
        'views.supplier_returns_view',
        'views.suppliers_view',
        'views.customers_view',
        'views.quotation_view',
        'views.sales_history_view',
        'views.report_view',
        'views.stock_history_view',
        'views.alerts_view',
        'views.users_view',
        'views.data_sync_view',
        'views.settings_view',
        'views.login_view',
        # ── Vistas importadas estáticamente por otras vistas (sub-dependencias) ──
        'views.returns_view',
        'views.dollar_price_view',
        'views.price_update_view',
        'views.history_view',
        'views.article_history_view',
        'views.kardex_view',
        # ── Controladores (cargados dinámicamente o en cadenas largas) ──
        'controllers.receipt_controller',
        'controllers.article_controller',
        'controllers.auth_controller',
        'controllers.cash_controller',
        'controllers.combo_controller',
        'controllers.customer_controller',
        'controllers.dashboard_controller',
        'controllers.data_sync_controller',
        'controllers.dollar_price_controller',
        'controllers.inventory_controller',
        'controllers.label_controller',
        'controllers.license_controller',
        'controllers.cloud_license_controller',
        'controllers.purchases_controller',
        'controllers.quotation_controller',
        'controllers.report_controller',
        'controllers.returns_controller',
        'controllers.sales_controller',
        'controllers.supplier_controller',
        'controllers.supplier_returns_controller',
        'controllers.user_controller',
        'controllers.alerts_controller',
        # ── Backend de matplotlib para Tkinter ──
        'matplotlib.backends.backend_tkagg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CloudPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icono.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CloudPOS',
)
