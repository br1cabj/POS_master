import logging
import time

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

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
from views.alerts_view import AlertsView
from views.articles_view import ArticlesView
from views.cash_view import CashView
from views.combo_maker_view import ComboMakerView
from views.customers_view import CustomersView
from views.data_sync_view import DataSyncView
from views.home_view import HomeView
from views.label_view import LabelView
from views.prices_view import PricesView
from views.purchases_view import PurchasesView
from views.quotation_view import QuotationView
from views.report_view import ReportView
from views.sales_history_view import SalesHistoryView
from views.sales_view import SalesView
from views.settings_view import SettingsView
from views.stock_history_view import StockHistoryView
from views.suppliers_view import SuppliersView
from views.users_view import UsersView

logger = logging.getLogger(__name__)

NAV_ITEMS_PUBLIC = [
	(HomeView, '⊞', 'Inicio', 'principal'),
	(SalesView, '🛒', 'Ventas', 'principal'),
	(CashView, '💵', 'Caja', 'principal'),
]

NAV_ITEMS_ADMIN = [
	(ArticlesView, '📦', 'Artículos', 'gestión'),
	(PricesView, '💰', 'Gestión de Precios', 'gestión'),
	(PurchasesView, '📥', 'Compras', 'gestión'),
	(CustomersView, '👥', 'Clientes / Fiado', 'gestión'),
	(SuppliersView, '🚚', 'Proveedores', 'gestión'),
	(QuotationView, '📝', 'Cotizaciones', 'gestión'),
	(LabelView, '🏷', 'Etiquetas', 'gestión'),
	(ComboMakerView, '🍔', 'Combos y Botonera', 'gestión'),
	(SalesHistoryView, '📜', 'Ventas e Historial', 'reportes'),
	(ReportView, '📋', 'Reporte de Cierre', 'reportes'),
	(StockHistoryView, '📊', 'Stock e Historial', 'reportes'),
	(AlertsView, '🔔', 'Alertas', 'reportes'),
	(UsersView, '🛠', 'Empleados', 'sistema'),
	(DataSyncView, '🔄', 'Importar / Exportar', 'sistema'),
	(SettingsView, '⚙', 'Configuración', 'sistema'),
]

_SHORTCUTS = [
	('F1', 'Ventas'),
	('F2', 'Caja'),
	('F3', 'Artículos'),
	('F4', 'Clientes'),
	('ESC', 'Inicio / Pantalla'),
	('F11', 'Pantalla Completa'),
]

_VIEW_SHORTCUTS = {
	SalesView: 'F1',
	CashView: 'F2',
	ArticlesView: 'F3',
	CustomersView: 'F4',
	HomeView: 'ESC',
}


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, ctx: AppContext, logout_command, **kwargs):
		super().__init__(master, fg_color=SURFACE1, **kwargs)
		self.master_app = master
		self.ctx = ctx
		self._external_logout_command = logout_command
		self._active_view_class = HomeView
		self._nav_buttons: dict = {}
		self._clock_job = None

		self.pack(fill='both', expand=True)

		self.username = ctx.username
		self.is_admin = ctx.is_admin
		self.role_label = (ctx.role or 'Usuario').capitalize()

		self._build_sidebar()
		self._build_main_area()

		self.ctx.navigate = self.safe_switch_view
		self.is_fullscreen = False

		self._setup_global_binds()

		self.after(60, lambda: self.safe_switch_view(HomeView))
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
			font=('Arial', 9, 'bold'),
			text_color=RED_TEXT,
		)
		self.lbl_dot.pack(side='right', padx=(0, 4))

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
			tabs += ['gestión', 'reportes', 'sistema']

		self._build_tab_bar(tabs)
		section_divider(self.sidebar).pack(fill='x', padx=0)

		self.menu_scroll = ctk.CTkScrollableFrame(
			self.sidebar, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		self.menu_scroll.pack(fill='both', expand=True, padx=0, pady=4)

		for view_cls, icon, label, section in NAV_ITEMS_PUBLIC:
			self._add_nav_btn(view_cls, icon, label, section=section)

		if self.is_admin:
			for view_cls, icon, label, section in NAV_ITEMS_ADMIN:
				self._add_nav_btn(
					view_cls, icon, label, requires_admin=True, section=section
				)

		self._switch_tab('principal')

		section_divider(self.sidebar).pack(fill='x', padx=0, pady=(4, 0))
		self._build_user_card()

	def _build_tab_bar(self, tabs: list):
		_TAB_LABELS = {
			'principal': 'Principal',
			'gestión': 'Gestión',
			'reportes': 'Reportes',
			'sistema': 'Sistema',
		}
		tab_bar = ctk.CTkFrame(self.sidebar, fg_color='transparent', height=38)
		tab_bar.pack(fill='x')
		tab_bar.pack_propagate(False)

		for col, section in enumerate(tabs):
			tab_bar.grid_columnconfigure(col, weight=1)

		for col, section in enumerate(tabs):
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
			btn.grid(row=0, column=col, sticky='nsew')
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

	def _section_for_view(self, view_class) -> str:
		for sec, items in self._nav_by_section.items():
			for vc, _ in items:
				if vc is view_class:
					return sec
		return 'principal'

	def _add_nav_btn(
		self, view_cls, icon, label, requires_admin=False, section='principal'
	):
		shortcut_key = _VIEW_SHORTCUTS.get(view_cls)
		btn = make_nav_button(
			self.menu_scroll,
			icon,
			label,
			command=lambda vc=view_cls, ra=requires_admin: self.safe_switch_view(
				vc, ra
			),
			active=False,
			shortcut=shortcut_key,
		)
		self._nav_buttons[view_cls] = btn
		self._nav_by_section.setdefault(section, []).append((view_cls, btn))

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
			text=self.username[0].upper(),
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

	def _update_nav_highlight(self, active_view_class):
		target_section = self._section_for_view(active_view_class)
		if target_section != self._active_tab:
			self._switch_tab(target_section)

		for view_cls, btn in self._nav_buttons.items():
			if view_cls == active_view_class:
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

		for key, desc in _SHORTCUTS:
			chip = ctk.CTkFrame(global_shortcuts, fg_color=SURFACE2, corner_radius=5)
			chip.pack(side='left', padx=(0, 6), pady=5)
			ctk.CTkLabel(
				chip,
				text=f' {key} ',
				font=('Arial', 9, 'bold'),
				text_color=ACCENT_TEXT,
				fg_color=ACCENT_DIM,
				corner_radius=4,
			).pack(side='left', padx=(3, 0), pady=2)
			ctk.CTkLabel(
				chip, text=f' {desc} ', font=('Arial', 9), text_color=TEXT_MUTED
			).pack(side='left', pady=2)

		self.lbl_clock = ctk.CTkLabel(
			bar, text='', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
		)
		self.lbl_clock.pack(side='right', padx=16)
		self.update_clock()

		self.lbl_view_shortcuts = ctk.CTkLabel(
			bar, text='', font=('Arial', 9, 'italic'), text_color=TEXT_MUTED
		)
		self.lbl_view_shortcuts.pack(side='right', padx=12)

	def _setup_global_binds(self):
		self.master_app.bind('<F1>', lambda e: self.safe_switch_view(SalesView))
		self.master_app.bind('<F2>', lambda e: self.safe_switch_view(CashView))
		self.master_app.bind(
			'<F3>', lambda e: self.safe_switch_view(ArticlesView, requires_admin=True)
		)
		self.master_app.bind(
			'<F4>', lambda e: self.safe_switch_view(CustomersView, requires_admin=True)
		)
		self.master_app.bind('<Escape>', self._handle_escape)
		self.after(
			100, lambda: self.winfo_toplevel().bind('<F11>', self.toggle_fullscreen)
		)

	def show_toast(self, message: str, type_: str = 'success', duration: int = 3000):
		if not self.winfo_exists():
			return

		fg, text_col = (
			(GREEN_DIM, GREEN_TEXT) if type_ == 'success' else (RED_DIM, RED_TEXT)
		)

		toast = ctk.CTkFrame(
			self, fg_color=SURFACE2, border_width=1, border_color=fg, corner_radius=8
		)
		lbl = ctk.CTkLabel(
			toast, text=message, text_color=text_col, font=FONT_BODY_BOLD
		)
		lbl.pack(padx=20, pady=12)

		toast.place(relx=0.98, rely=0.92, anchor='se')

		self.after(duration, toast.destroy)

	def safe_switch_view(self, view_class, requires_admin=False, context_data=None):
		if not self.winfo_exists():
			return

		if requires_admin and not self.is_admin:
			CTkMessagebox(
				title='Acceso Restringido',
				message='Necesitás permisos de administrador para acceder a esta sección.',
				icon='cancel',
			)
			return

		if self.current_view and self._active_view_class is not view_class:
			if (
				hasattr(self.current_view, 'has_unsaved_changes')
				and self.current_view.has_unsaved_changes()
			):
				msg = CTkMessagebox(
					title='Cambios sin guardar',
					message='Tenés cambios sin guardar. ¿Querés salir igual?',
					icon='warning',
					option_1='Cancelar',
					option_2='Salir sin guardar',
				)
				if msg.get() != 'Salir sin guardar':
					return

		if self.current_view:
			self.current_view.destroy()
			self.current_view = None

		if self.main_area.winfo_exists():
			for widget in list(self.main_area.winfo_children()):
				widget.destroy()

		self._active_view_class = view_class
		self._update_nav_highlight(view_class)

		kwargs = {'show_toast': self.show_toast}
		if context_data is not None:
			kwargs['context_data'] = context_data
		if view_class is HomeView:
			kwargs['navigate'] = self.safe_switch_view

		self.current_view = view_class(self.main_area, self.ctx, **kwargs)
		self.current_view.pack(fill='both', expand=True)

		if hasattr(self.current_view, 'set_initial_focus'):
			self.after(50, self.current_view.set_initial_focus)

		if (
			hasattr(self, 'lbl_view_shortcuts')
			and self.lbl_view_shortcuts.winfo_exists()
		):
			if view_class is SalesView:
				self.lbl_view_shortcuts.configure(
					text='F5 Cobrar  ·  F6 Lector  ·  F7 Libre  ·  Supr Quitar'
				)
			else:
				self.lbl_view_shortcuts.configure(text='')

		self.after(200, self._refresh_cash_dot)

	def _refresh_cash_dot(self):
		if not self.winfo_exists():
			return
		try:
			from controllers.cash_controller import CashController

			ctrl = CashController(self.ctx.db_engine)
			session = ctrl.get_active_session(self.ctx.tenant_id, self.ctx.user_id)
			color = '#22c55e' if session else RED_TEXT
			label = '● Abierta' if session else '● Cerrada'
		except Exception:
			color = TEXT_SECONDARY
			label = '●'

		if hasattr(self, 'lbl_dot') and self.lbl_dot.winfo_exists():
			self.lbl_dot.configure(text_color=color, text=label)

	def handle_logout(self):
		for key in ('<F1>', '<F2>', '<F3>', '<F4>', '<Escape>', '<F11>'):
			try:
				self.master_app.unbind(key)
			except Exception:
				pass
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
		if self.is_fullscreen:
			self.is_fullscreen = False
			self.winfo_toplevel().attributes('-fullscreen', False)
		else:
			self.safe_switch_view(HomeView)

	def destroy(self):
		if hasattr(self, '_clock_job') and self._clock_job:
			try:
				self.after_cancel(self._clock_job)
			except Exception:
				pass
			self._clock_job = None
		super().destroy()
