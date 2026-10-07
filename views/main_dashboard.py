import importlib
import logging
import queue
import threading
import time
from tkinter import TclError

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy.exc import SQLAlchemyError

from controllers.cash_controller import CashController
from core.context import AppContext
from utils.styles import (
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV,
	FONT_NAV_BOLD,
	FONT_SMALL,
	FONT_TITLE,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED_DIM,
	RED_TEXT,
	SURFACE0,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_nav_button,
	section_divider,
)

logger = logging.getLogger(__name__)

# ─── Lazy view loader ─────────────────────────────────────────────────────────
_view_cache: dict = {}


def _load_view_class(dotted_path: str) -> type:
	"""Importa y cachea una clase de vista por 'module.path.ClassName'."""
	if dotted_path not in _view_cache:
		module_path, cls_name = dotted_path.rsplit('.', 1)
		mod = importlib.import_module(module_path)
		_view_cache[dotted_path] = getattr(mod, cls_name)
	return _view_cache[dotted_path]


def _to_path(view) -> str:
	"""Normaliza una clase de vista o path string a path string."""
	if isinstance(view, str):
		return view
	return _CLASS_PATHS.get(view.__name__, '')


# ─── Constantes de path para cada vista ──────────────────────────────────────
_HOME = 'views.home_view.HomeView'
_SALES = 'views.sales_view.SalesView'
_CASH = 'views.cash_view.CashView'
_ARTICLES = 'views.articles_view.ArticlesView'
_PRICES = 'views.prices_view.PricesView'
_LABEL = 'views.label_view.LabelView'
_COMBO = 'views.combo_maker_view.ComboMakerView'
_PURCHASES = 'views.purchases_view.PurchasesView'
_SUP_RETS = 'views.supplier_returns_view.SupplierReturnsView'
_SUPPLIERS = 'views.suppliers_view.SuppliersView'
_CUSTOMERS = 'views.customers_view.CustomersView'
_QUOTATION = 'views.quotation_view.QuotationView'
_SALES_HIS = 'views.sales_history_view.SalesHistoryView'
_REPORT = 'views.report_view.ReportView'
_STOCK_HIS = 'views.stock_history_view.StockHistoryView'
_ALERTS = 'views.alerts_view.AlertsView'
_USERS = 'views.users_view.UsersView'
_DATA_SYNC = 'views.data_sync_view.DataSyncView'
_SETTINGS = 'views.settings_view.SettingsView'

# Lookup inverso: nombre de clase → path (para cuando código externo pasa una clase)
_CLASS_PATHS = {
	'HomeView': _HOME,
	'SalesView': _SALES,
	'CashView': _CASH,
	'ArticlesView': _ARTICLES,
	'PricesView': _PRICES,
	'LabelView': _LABEL,
	'ComboMakerView': _COMBO,
	'PurchasesView': _PURCHASES,
	'SupplierReturnsView': _SUP_RETS,
	'SuppliersView': _SUPPLIERS,
	'CustomersView': _CUSTOMERS,
	'QuotationView': _QUOTATION,
	'SalesHistoryView': _SALES_HIS,
	'ReportView': _REPORT,
	'StockHistoryView': _STOCK_HIS,
	'AlertsView': _ALERTS,
	'UsersView': _USERS,
	'DataSyncView': _DATA_SYNC,
	'SettingsView': _SETTINGS,
}

NAV_ITEMS_PUBLIC = [
	(_HOME, '⊞', 'Inicio', 'principal'),
	(_SALES, '🛒', 'Ventas', 'principal'),
	(_CASH, '💵', 'Caja', 'principal'),
	(_CUSTOMERS, '👥', 'Clientes / Fiado', 'principal'),
]

NAV_ITEMS_ADMIN = [
	# ── Principal (Admin) ───────────────────────────────────────────────────
	(_QUOTATION, '📝', 'Cotizaciones', 'principal'),
	# ── Catálogo: todo lo que se vende ──────────────────────────────────────
	(_ARTICLES, '📦', 'Artículos', 'catálogo'),
	(_PRICES, '💰', 'Gestión de Precios', 'catálogo'),
	(_LABEL, '🏷', 'Etiquetas', 'catálogo'),
	(_COMBO, '🍔', 'Combos y Botonera', 'catálogo'),
	# ── Compras: todo lo que se compra y con quién ──────────────────────────
	(_PURCHASES, '📥', 'Compras', 'compras'),
	(_SUP_RETS, '↩', 'Dev. a Proveedor', 'compras'),
	(_SUPPLIERS, '🚚', 'Proveedores', 'compras'),
	# ── Reportes ────────────────────────────────────────────────────────────
	(_SALES_HIS, '📜', 'Ventas e Historial', 'reportes'),
	(_REPORT, '📋', 'Reporte de Cierre', 'reportes'),
	(_STOCK_HIS, '📊', 'Stock e Historial', 'reportes'),
	(_ALERTS, '🔔', 'Alertas', 'reportes'),
	# ── Sistema ─────────────────────────────────────────────────────────────
	(_USERS, '🛠', 'Empleados', 'sistema'),
	(_DATA_SYNC, '🔄', 'Importar / Exportar', 'sistema'),
	(_SETTINGS, '⚙', 'Configuración', 'sistema'),
]

ADMIN_VIEW_PATHS = frozenset(item[0] for item in NAV_ITEMS_ADMIN)
# El respaldo del cajero se abre en SQLite de solo lectura. Estas pantallas no
# escriben; Ventas conserva acceso únicamente para consultar el catálogo.
OFFLINE_READ_ONLY_VIEW_PATHS = frozenset(
	{
		_HOME,
		_SALES,
		_SALES_HIS,
		_REPORT,
		_STOCK_HIS,
		_ALERTS,
	}
)

_SHORTCUTS = [
	('F1', 'Ventas'),
	('F2', 'Caja'),
	('F3', 'Artículos'),
	('F4', 'Clientes'),
	('ESC', 'Inicio / Pantalla'),
	('F11', 'Pantalla Completa'),
]

_VIEW_SHORTCUTS = {
	_SALES: 'F1',
	_CASH: 'F2',
	_ARTICLES: 'F3',
	_CUSTOMERS: 'F4',
	_HOME: 'ESC',
}


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, ctx: AppContext, logout_command, onboarding_command=None, **kwargs):
		super().__init__(master, fg_color=SURFACE1, **kwargs)
		self.master_app = master
		self.ctx = ctx
		self._external_logout_command = logout_command
		self._onboarding_command = onboarding_command
		self._active_view_path = _HOME
		self._nav_buttons: dict = {}
		self._clock_job = None
		self._cash_job = None
		self._cash_trigger_job = None
		self._cash_poll_job = None
		self._cash_result_queue: queue.Queue = queue.Queue()
		self._cash_request_in_flight = False
		self._sync_job = None
		self._setup_bind_job = None
		self._active_toasts = []
		self._teardown_done = False

		# Instancia única para evitar fugas de conexión de DB
		self._cash_ctrl = CashController(ctx.db_engine)

		self.pack(fill='both', expand=True)

		self.username = (ctx.username or 'Usuario').strip() or 'Usuario'
		self.is_admin = ctx.is_admin
		self.role_label = str(ctx.role or 'Usuario').strip().capitalize()

		self._build_sidebar()
		self._build_main_area()

		self.ctx.navigate = self.safe_switch_view
		self.ctx.show_toast = self.show_toast
		self.is_fullscreen = False

		self._setup_global_binds()

		self.after(60, lambda: self.safe_switch_view(_HOME))
		self.after(400, self._refresh_cash_dot)

	def _build_sidebar(self):
		self.sidebar = ctk.CTkFrame(self, width=280, fg_color=SURFACE0, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')
		self.sidebar.pack_propagate(False)

		logo_frame = ctk.CTkFrame(self.sidebar, fg_color='transparent')
		logo_frame.pack(fill='x', padx=16, pady=(20, 0))

		ctk.CTkLabel(
			logo_frame,
			text='☁ CloudPOS',
			font=FONT_TITLE,
			text_color=ACCENT_TEXT,
			anchor='w',
		).pack(side='left')

		self.lbl_dot = ctk.CTkLabel(
			logo_frame,
			text='● Cerrada',
			font=('Arial', 11, 'bold'),
			text_color=RED_TEXT,
			cursor='hand2',
		)
		self.lbl_dot.pack(side='right', padx=(0, 4))
		self.lbl_dot.bind('<Button-1>', lambda e: self._go_to_cash())

		ctk.CTkLabel(
			self.sidebar,
			text='Sistema de Gestión',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(fill='x', padx=18, pady=(2, 10))

		section_divider(self.sidebar).pack(fill='x', padx=0)

		self._active_tab = 'principal'
		self._nav_by_section: dict[str, list] = {}
		self._tab_buttons: dict[str, ctk.CTkButton] = {}

		tabs = ['principal']
		if self.is_admin:
			tabs += ['catálogo', 'compras', 'reportes', 'sistema']

		self._build_tab_bar(tabs)
		section_divider(self.sidebar).pack(fill='x', padx=0)

		self.menu_scroll = ctk.CTkScrollableFrame(
			self.sidebar, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		self.menu_scroll.pack(fill='both', expand=True, padx=0, pady=4)

		for view_path, icon, label, section in NAV_ITEMS_PUBLIC:
			self._add_nav_btn(view_path, icon, label, section=section)

		if self.is_admin:
			for view_path, icon, label, section in NAV_ITEMS_ADMIN:
				self._add_nav_btn(
					view_path, icon, label, requires_admin=True, section=section
				)

		self._switch_tab('principal')

		section_divider(self.sidebar).pack(fill='x', padx=0, pady=(4, 0))
		self._build_user_card()

	def _build_tab_bar(self, tabs: list):
		_TAB_LABELS = {
			'principal': 'Principal',
			'catálogo': 'Catálogo',
			'compras': 'Compras',
			'reportes': 'Reportes',
			'sistema': 'Sistema',
		}
		columns = min(3, len(tabs))
		rows = (len(tabs) + columns - 1) // columns
		tab_bar = ctk.CTkFrame(self.sidebar, fg_color='transparent', height=38 * rows)
		tab_bar.pack(fill='x')
		tab_bar.pack_propagate(False)

		for col in range(columns):
			tab_bar.grid_columnconfigure(col, weight=1)
		for row in range(rows):
			tab_bar.grid_rowconfigure(row, weight=1)

		for index, section in enumerate(tabs):
			row, col = divmod(index, columns)
			btn = ctk.CTkButton(
				tab_bar,
				text=_TAB_LABELS.get(section, section.capitalize()),
				font=FONT_SMALL,
				fg_color='transparent',
				hover_color=SURFACE2,
				text_color=TEXT_MUTED,
				corner_radius=0,
				border_width=0,
				height=38,
				command=lambda s=section: self._switch_tab(s),
			)
			btn.grid(row=row, column=col, sticky='nsew')
			self._tab_buttons[section] = btn

	def _switch_tab(self, section: str):
		self._active_tab = section

		for sec, btn in self._tab_buttons.items():
			if sec == section:
				btn.configure(fg_color=ACCENT_DIM, text_color=ACCENT_TEXT)
			else:
				btn.configure(fg_color='transparent', text_color=TEXT_MUTED)

		for items in self._nav_by_section.values():
			for _, btn in items:
				btn.pack_forget()

		for _, btn in self._nav_by_section.get(section, []):
			btn.pack(fill='x', padx=8, pady=2)

	def _section_for_view(self, view_path: str) -> str:
		for sec, items in self._nav_by_section.items():
			for vp, _ in items:
				if vp == view_path:
					return sec
		return 'principal'

	def _add_nav_btn(
		self, view_path: str, icon, label, requires_admin=False, section='principal'
	):
		shortcut_key = _VIEW_SHORTCUTS.get(view_path)
		btn = make_nav_button(
			self.menu_scroll,
			icon,
			label,
			command=lambda vp=view_path, ra=requires_admin: self.safe_switch_view(
				vp, ra
			),
			active=False,
			shortcut=shortcut_key,
		)
		if getattr(self.ctx, 'offline_mode', False) and view_path not in OFFLINE_READ_ONLY_VIEW_PATHS:
			btn.configure(state='disabled')
		self._nav_buttons[view_path] = btn
		self._nav_by_section.setdefault(section, []).append((view_path, btn))

	def _build_user_card(self):
		card = ctk.CTkFrame(
			self.sidebar,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', padx=10, pady=10)

		inner = ctk.CTkFrame(card, fg_color='transparent')
		inner.pack(fill='x', padx=12, pady=10)

		avatar = ctk.CTkLabel(
			inner,
			text=self.username[0].upper() if self.username else '?',
			font=FONT_HEADING,
			width=34,
			height=34,
			fg_color=ACCENT_DIM,
			text_color=ACCENT_TEXT,
			corner_radius=17,
		)
		avatar.pack(side='left')

		info = ctk.CTkFrame(inner, fg_color='transparent')
		info.pack(side='left', padx=10, fill='x', expand=True)

		ctk.CTkLabel(
			info,
			text=self.username.capitalize(),
			font=FONT_NAV_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w')

		role_color = ACCENT_DIM if self.is_admin else SURFACE3
		role_text_color = ACCENT_TEXT if self.is_admin else TEXT_SECONDARY
		ctk.CTkLabel(
			info,
			text=f'  {self.role_label}  ',
			font=('Arial', 9, 'bold'),
			fg_color=role_color,
			text_color=role_text_color,
			corner_radius=4,
			anchor='w',
		).pack(anchor='w', pady=(2, 0))

		if self.is_admin and callable(self._onboarding_command):
			ctk.CTkButton(
				card,
				text='✨  Abrir inicio rápido',
				fg_color='transparent',
				hover_color=SURFACE3,
				text_color=ACCENT_TEXT,
				font=FONT_SMALL,
				height=30,
				border_width=0,
				command=self._onboarding_command,
			).pack(fill='x', padx=8, pady=(8, 0))

		ctk.CTkButton(
			card,
			text='Cerrar Sesión',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			font=FONT_SMALL,
			height=30,
			border_width=0,
			command=self.handle_logout,
		).pack(fill='x', padx=8, pady=(0, 6))

	def _update_nav_highlight(self, active_view_path: str):
		target_section = self._section_for_view(active_view_path)
		self._switch_tab(target_section)

		for view_path, btn in self._nav_buttons.items():
			if view_path == active_view_path:
				btn.configure(
					fg_color=ACCENT_DIM, text_color=ACCENT_TEXT, font=FONT_NAV_BOLD
				)
			else:
				btn.configure(
					fg_color='transparent', text_color=TEXT_SECONDARY, font=FONT_NAV
				)

	def _build_main_area(self):
		area_container = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=0)
		area_container.pack(side='right', fill='both', expand=True)

		# Banner de modo offline — visible solo cuando el cajero opera sin red
		if getattr(self.ctx, 'offline_mode', False):
			offline_banner = ctk.CTkFrame(
				area_container,
				fg_color='#7D3C00',
				corner_radius=0,
				height=28,
			)
			offline_banner.pack(side='top', fill='x')
			offline_banner.pack_propagate(False)
			ctk.CTkLabel(
				offline_banner,
				text='📴  MODO SIN CONEXIÓN — Solo lectura. Para procesar ventas, reconectá la red y reiniciá.',
				font=('Arial', 9, 'bold'),
				text_color='#F5CBA7',
			).pack(side='left', padx=12, pady=4)

		self._build_shortcuts_bar(area_container)

		self.main_area = ctk.CTkFrame(
			area_container, fg_color=SURFACE1, corner_radius=0
		)
		self.main_area.pack(side='top', fill='both', expand=True)
		self.current_view = None

	def _build_shortcuts_bar(self, parent):
		bar = ctk.CTkFrame(
			parent,
			fg_color=SURFACE0,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
			height=34,
		)
		bar.pack(side='bottom', fill='x')
		bar.pack_propagate(False)

		global_shortcuts = ctk.CTkFrame(bar, fg_color='transparent')
		global_shortcuts.pack(side='left', padx=12, fill='y')

		shortcut_text = '  ·  '.join(f'{key} {desc}' for key, desc in _SHORTCUTS)
		ctk.CTkLabel(
			global_shortcuts,
			text=shortcut_text,
			font=('Arial', 9),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(fill='y')

		self.lbl_clock = ctk.CTkLabel(
			bar, text='', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
		)
		self.lbl_clock.pack(side='right', padx=16)
		self.update_clock()

		self.lbl_view_shortcuts = ctk.CTkLabel(
			bar, text='', font=('Arial', 9, 'italic'), text_color=TEXT_MUTED
		)
		self.lbl_view_shortcuts.pack(side='right', padx=12)

		# ── Indicador de sync ──────────────────────────────────────────────────
		self.lbl_sync = ctk.CTkLabel(
			bar,
			text='',
			font=('Arial', 9),
			text_color=TEXT_MUTED,
			cursor='hand2' if self.is_admin else '',
		)
		self.lbl_sync.pack(side='right', padx=(0, 8))
		if self.is_admin:
			self.lbl_sync.bind('<Button-1>', lambda e: self._handle_sync_click())
			self.lbl_sync.bind('<Button-3>', lambda e: self._force_sync_now())
		self.after(5000, self._refresh_sync_indicator)

	def _handle_sync_click(self):
		"""Click izquierdo: si hay error muestra detalle, si no va a settings cloud."""
		if not self.is_admin:
			self.show_toast(
				'El estado de sincronización está disponible para administradores.',
				type_='info',
			)
			return
		worker = getattr(self.ctx, 'sync_worker', None)
		ok, _last_time, error = worker.get_status() if worker else (None, None, '')
		if worker and not ok and error:
			CTkMessagebox(
				master=self,
				title='Sync Cloud',
				message=f'Error de sincronización:\n{error}',
				icon='cancel',
			)
		else:
			self.safe_switch_view(_SETTINGS, requires_admin=True)

	def _force_sync_now(self):
		"""Click derecho: fuerza un sync manual inmediato."""
		if not self.is_admin:
			return
		worker = getattr(self.ctx, 'sync_worker', None)
		if worker and worker.is_running:
			worker.force_sync()
			CTkMessagebox(
				master=self,
				title='Sync Cloud',
				message='Sincronización manual iniciada.',
				icon='check',
			)
			self.after(2000, self._refresh_sync_indicator)
		else:
			CTkMessagebox(
				master=self.winfo_toplevel(),
				title='Sync no disponible',
				message='El sync cloud no está activo.\nActivá tu plan cloud en Configuración > Licencias.',
				icon='warning',
			)

	def _refresh_sync_indicator(self):
		if not self.winfo_exists():
			return
		worker = getattr(self.ctx, 'sync_worker', None)
		if worker is None or not worker.is_running:
			if hasattr(self, 'lbl_sync'):
				self.lbl_sync.configure(text='')
		else:
			ok, t, _error = worker.get_status()
			time_str = t.strftime('%H:%M') if t else '–'
			if ok is None:
				dot, color = '● Sync pendiente', TEXT_MUTED
			elif ok:
				dot, color = f'● Sync {time_str}', '#4CAF50'
			else:
				dot, color = '● Sync error', '#E74C3C'
			if hasattr(self, 'lbl_sync'):
				self.lbl_sync.configure(text=dot, text_color=color)
		self._sync_job = self.after(30000, self._refresh_sync_indicator)

	def _setup_global_binds(self):
		self.master_app.bind('<F1>', lambda e: self._run_shortcut(_SALES))
		self.master_app.bind('<F2>', lambda e: self._run_shortcut(_CASH))
		self.master_app.bind(
			'<F3>', lambda e: self._run_shortcut(_ARTICLES)
		)
		self.master_app.bind(
			'<F4>', lambda e: self._run_shortcut(_CUSTOMERS)
		)
		self.master_app.bind('<Escape>', self._handle_escape)
		self._setup_bind_job = self.after(100, self._bind_fullscreen_shortcut)

	def _bind_fullscreen_shortcut(self):
		self._setup_bind_job = None
		if self.winfo_exists():
			self.master_app.bind('<F11>', self.toggle_fullscreen)

	def _run_shortcut(self, view_path: str):
		"""Evita reconstruir la vista actual y respeta diálogos modales activos."""
		try:
			grabbed = self.master_app.grab_current()
		except TclError:
			grabbed = None
		if grabbed and grabbed is not self.master_app:
			return None
		self.safe_switch_view(view_path)
		return 'break'

	def _clear_global_binds(self):
		for key in ('<F1>', '<F2>', '<F3>', '<F4>', '<Escape>', '<F11>'):
			try:
				self.master_app.unbind(key)
			except TclError:
				logger.debug('El binding %s ya no estaba disponible.', key)

	def _reposition_toasts(self):
		"""Calcula el offset dinámico para apilar toasts sin superponerlos."""
		base_rely = 0.95
		offset = 0.09
		for i, toast in enumerate(reversed(self._active_toasts)):
			if toast.winfo_exists():
				toast.place(relx=0.98, rely=base_rely - (i * offset), anchor='se')

	def _remove_toast(self, toast):
		"""Elimina el toast de la cola y actualiza las posiciones."""
		if toast in self._active_toasts:
			self._active_toasts.remove(toast)
		if toast.winfo_exists():
			toast.destroy()
		self._reposition_toasts()

	def show_toast(self, message: str, type_: str = 'success', duration: int = 3000):
		if not self.winfo_exists():
			return

		_MAX_TOASTS = 4
		while len(self._active_toasts) >= _MAX_TOASTS:
			self._remove_toast(self._active_toasts[0])

		_COLORS = {
			'success': (GREEN_DIM, GREEN_TEXT),
			'error': (RED_DIM, RED_TEXT),
			'warning': (ORANGE_DIM, ORANGE_TEXT),
			'info': (SURFACE2, TEXT_SECONDARY),
		}
		fg, text_col = _COLORS.get(type_, (GREEN_DIM, GREEN_TEXT))

		toast = ctk.CTkFrame(
			self, fg_color=SURFACE2, border_width=1, border_color=fg, corner_radius=8
		)
		lbl = ctk.CTkLabel(
			toast, text=message, text_color=text_col, font=FONT_BODY_BOLD
		)
		lbl.pack(padx=20, pady=12)

		self._active_toasts.append(toast)
		self._reposition_toasts()

		self.after(duration, lambda t=toast: self._remove_toast(t))

	def _dispose_view(self, view_instance):
		"""Cancela recursos de una vista antes de destruirla sin dejarla en segundo plano."""
		try:
			if view_instance and view_instance.winfo_exists():
				view_instance.destroy()
		except TclError:
			logger.debug('La vista anterior ya estaba destruida.')

	def _cleanup_view(self, view_instance):
		if not view_instance:
			return
		try:
			if hasattr(view_instance, 'destroy_custom'):
				view_instance.destroy_custom()
			elif hasattr(view_instance, 'cleanup'):
				view_instance.cleanup()
		except Exception as exc:
			logger.error('La limpieza de una vista falló: %s', exc, exc_info=True)
		self._dispose_view(view_instance)

	def safe_switch_view(self, view, requires_admin=False, context_data=None):
		if not self.winfo_exists():
			return

		# Normaliza: acepta clase o path string
		view_path = _to_path(view)
		if not view_path:
			logger.error('Vista no registrada: %s', view)
			return

		if (requires_admin or view_path in ADMIN_VIEW_PATHS) and not self.is_admin:
			CTkMessagebox(
				master=self.winfo_toplevel(),
				title='Acceso Restringido',
				message='Necesitás permisos de administrador para acceder a esta sección.',
				icon='cancel',
			)
			return
		if (
			getattr(self.ctx, 'offline_mode', False)
			and view_path not in OFFLINE_READ_ONLY_VIEW_PATHS
		):
			self.show_toast(
				'Esta sección no está disponible mientras la base está en solo lectura.',
				type_='warning',
			)
			return
		if self.current_view and self._active_view_path == view_path and context_data is None:
			if hasattr(self.current_view, 'set_initial_focus'):
				self.current_view.set_initial_focus()
			return
		try:
			view_class = _load_view_class(view_path)
		except (ImportError, AttributeError, ValueError) as exc:
			logger.error('No se pudo importar la vista %s: %s', view_path, exc, exc_info=True)
			self.show_toast('No se pudo abrir la sección. Revisá los registros.', type_='error')
			return

		if self.current_view and self._active_view_path != view_path:
			if (
				hasattr(self.current_view, 'has_unsaved_changes')
				and self.current_view.has_unsaved_changes()
			):
				msg = CTkMessagebox(
					master=self.winfo_toplevel(),
					title='Cambios sin guardar',
					message='Tenés cambios sin guardar. ¿Querés salir igual?',
					icon='warning',
					option_1='Cancelar',
					option_2='Salir sin guardar',
				)
				if msg.get() != 'Salir sin guardar':
					return

		if self.current_view:
			old_view = self.current_view
			self.current_view = None
			self._cleanup_view(old_view)

		# Limpieza residual
		if self.main_area.winfo_exists():
			for widget in list(self.main_area.winfo_children()):
				self._dispose_view(widget)

		# Indicador de carga mientras se instancia la vista
		_loading = ctk.CTkFrame(self.main_area, fg_color=SURFACE1, corner_radius=0)
		_loading.pack(fill='both', expand=True)
		ctk.CTkLabel(
			_loading,
			text='Cargando...',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).place(relx=0.5, rely=0.5, anchor='center')
		self.update_idletasks()  # Fuerza el render del indicador antes de instanciar la vista

		kwargs = {}
		if context_data is not None:
			kwargs['context_data'] = context_data
		if view_path == _HOME:
			kwargs['navigate'] = self.safe_switch_view

		try:
			self.current_view = view_class(self.main_area, self.ctx, **kwargs)
			self.current_view.pack(fill='both', expand=True)
		except Exception as e:
			logger.error('Error al cargar vista: %s', e, exc_info=True)
			self.current_view = None
			err_label = ctk.CTkLabel(
				self.main_area,
				text='Error al cargar la vista.\nRevisá los registros.',
				text_color='#ef4444',
			)
			err_label.pack(expand=True)
		finally:
			self._dispose_view(_loading)

		if self.current_view:
			self._active_view_path = view_path
			self._update_nav_highlight(view_path)

		if self.current_view and hasattr(self.current_view, 'set_initial_focus'):
			self.after(50, self.current_view.set_initial_focus)

		if (
			hasattr(self, 'lbl_view_shortcuts')
			and self.lbl_view_shortcuts.winfo_exists()
		):
			if view_path == _SALES:
				self.lbl_view_shortcuts.configure(
					text='F5 Cobrar  ·  F6 Lector  ·  F7 Libre  ·  Supr Quitar'
				)
			else:
				self.lbl_view_shortcuts.configure(text='')

		self._request_cash_dot_refresh(delay_ms=200)

	def _go_to_cash(self):
		self.safe_switch_view(_CASH)

	def _request_cash_dot_refresh(self, delay_ms: int = 0):
		"""Concentra solicitudes repetidas de estado de caja en una sola consulta."""
		if self._cash_trigger_job:
			try:
				self.after_cancel(self._cash_trigger_job)
			except TclError:
				pass
		self._cash_trigger_job = self.after(delay_ms, self._refresh_cash_dot)

	def _refresh_cash_dot(self):
		self._cash_trigger_job = None
		if not self.winfo_exists():
			return
		if self._cash_request_in_flight:
			return
		self._cash_request_in_flight = True

		def _run():
			try:
				session = self._cash_ctrl.get_active_session(
					self.ctx.tenant_id, self.ctx.user_id
				)
			except (SQLAlchemyError, RuntimeError) as exc:
				logger.warning('No se pudo actualizar el estado de caja: %s', exc)
				session = None
			# El worker no toca Tkinter: el hilo principal consume esta cola.
			self._cash_result_queue.put(session)

		threading.Thread(target=_run, daemon=True, name='CashStatusRefresh').start()
		self._cash_poll_job = self.after(50, self._consume_cash_dot_result)

	def _consume_cash_dot_result(self):
		self._cash_poll_job = None
		if not self.winfo_exists():
			return
		try:
			session = self._cash_result_queue.get_nowait()
		except queue.Empty:
			self._cash_poll_job = self.after(50, self._consume_cash_dot_result)
			return
		self._cash_request_in_flight = False
		color = '#22c55e' if session else RED_TEXT
		label = '● Abierta' if session else '● Cerrada'
		if hasattr(self, 'lbl_dot') and self.lbl_dot.winfo_exists():
			self.lbl_dot.configure(text_color=color, text=label)
		self._cash_job = self.after(30_000, self._refresh_cash_dot)

	def _cancel_dashboard_jobs(self):
		for job_attr in (
			'_clock_job',
			'_cash_job',
			'_cash_trigger_job',
			'_cash_poll_job',
			'_sync_job',
			'_setup_bind_job',
		):
			job = getattr(self, job_attr, None)
			if job:
				try:
					self.after_cancel(job)
				except TclError:
					pass
				setattr(self, job_attr, None)

	def handle_logout(self):
		self._cancel_dashboard_jobs()
		self._clear_global_binds()
		self._external_logout_command()

	def update_clock(self):
		if not self.winfo_exists():
			return
		if hasattr(self, 'lbl_clock') and self.lbl_clock.winfo_exists():
			time_str = time.strftime('%H:%M:%S')
			date_str = time.strftime('%d/%m/%Y')
			self.lbl_clock.configure(text=f'{date_str}   {time_str}')
		self._clock_job = self.after(1000, self.update_clock)

	def toggle_fullscreen(self, event=None):
		if not self.winfo_exists():
			return
		top = self.winfo_toplevel()
		self.is_fullscreen = not self.is_fullscreen
		top.attributes('-fullscreen', self.is_fullscreen)

	def _handle_escape(self, event=None):
		try:
			grabbed = self.master_app.grab_current()
		except TclError:
			grabbed = None
		if grabbed and grabbed is not self.master_app:
			return 'break'
		if self.is_fullscreen:
			self.is_fullscreen = False
			self.winfo_toplevel().attributes('-fullscreen', False)
		else:
			self.safe_switch_view(_HOME)
		return 'break'

	def destroy(self):
		if self._teardown_done:
			return
		self._teardown_done = True
		self._cancel_dashboard_jobs()
		self._clear_global_binds()
		if getattr(self.ctx, 'navigate', None) == self.safe_switch_view:
			self.ctx.navigate = None
		if getattr(self.ctx, 'show_toast', None) == self.show_toast:
			self.ctx.show_toast = None
		super().destroy()
