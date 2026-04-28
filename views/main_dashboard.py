import logging
import time

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.context import AppContext
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, RED, RED_TEXT,
    SURFACE0, SURFACE1, SURFACE2, SURFACE3, TEXT_MUTED, TEXT_PRIMARY,
    TEXT_SECONDARY, FONT_NAV, FONT_NAV_BOLD, FONT_LABEL,
    make_nav_button, make_section_label, section_divider,
)

# Importamos todas las vistas
from views.alerts_view import AlertsView
from views.articles_view import ArticlesView
from views.cash_view import CashView
from views.combo_maker_view import ComboMakerView
from views.customers_view import CustomersView
from views.data_sync_view import DataSyncView
from views.home_view import HomeView
from views.prices_view import PricesView
from views.purchases_view import PurchasesView
from views.report_view import ReportView
from views.sales_history_view import SalesHistoryView
from views.sales_view import SalesView
from views.settings_view import SettingsView
from views.stock_history_view import StockHistoryView
from views.suppliers_view import SuppliersView
from views.quotation_view import QuotationView
from views.users_view import UsersView

logger = logging.getLogger(__name__)

# Mapa de rutas: view_class → (icon, label, section)
NAV_ITEMS_PUBLIC = [
    (HomeView,     '⊞',  'Inicio',          'principal'),
    (SalesView,    '🛒', 'Ventas',           'principal'),
    (CashView,     '💵', 'Caja',             'principal'),
]

NAV_ITEMS_ADMIN = [
    (ArticlesView,    '📦', 'Artículos',           'gestión'),
    (PricesView,      '💰', 'Gestión de Precios',  'gestión'),
    (PurchasesView,   '📥', 'Compras',             'gestión'),
    (CustomersView,   '👥', 'Clientes / Fiado',    'gestión'),
    (SuppliersView,   '🚚', 'Proveedores',         'gestión'),
    (QuotationView,   '📝', 'Cotizaciones',        'gestión'),
    (ComboMakerView,  '🍔', 'Combos y Botonera',   'gestión'),
    (SalesHistoryView,'📜', 'Ventas e Historial',  'reportes'),
    (ReportView,      '📋', 'Reporte de Cierre',   'reportes'),
    (StockHistoryView,'📊', 'Stock e Historial',   'reportes'),
    (AlertsView,      '🔔', 'Alertas',             'reportes'),
    (UsersView,       '🛠', 'Empleados',           'sistema'),
    (DataSyncView,    '🔄', 'Importar / Exportar', 'sistema'),
    (SettingsView,    '⚙',  'Configuración',       'sistema'),
]

# Atajos de teclado que se muestran en la barra inferior
_SHORTCUTS = [
    ('F1', 'Ventas'),
    ('F2', 'Caja'),
    ('F3', 'Artículos'),
    ('F4', 'Clientes'),
    ('ESC', 'Inicio'),
    ('F11', 'Pantalla Completa'),
]

# Atajos específicos por vista (se muestran en el lado derecho de la barra)
_VIEW_SHORTCUTS = {}  # Populated after view imports


class MainDashboard(ctk.CTkFrame):
    def __init__(self, master, ctx: AppContext, logout_command, **kwargs):
        super().__init__(master, fg_color=SURFACE1, **kwargs)
        self.master_app = master
        self.ctx = ctx
        self._external_logout_command = logout_command
        self._active_view_class = HomeView
        self._nav_buttons: dict = {}   # view_class → CTkButton
        self._clock_job = None

        self.pack(fill='both', expand=True)

        # ── Usuario ────────────────────────────────────────────────────────
        self.username   = ctx.username
        self.is_admin   = ctx.is_admin
        self.role_label = ctx.role.capitalize()

        # ── Layout principal ───────────────────────────────────────────────
        self._build_sidebar()
        self._build_main_area()

        # ── Inyectar navigate en contexto (para vistas que lo necesitan) ───
        self.ctx.navigate = self.safe_switch_view

        # ── Reloj pantalla completa ────────────────────────────────────────
        self.is_fullscreen = False
        self.lbl_clock = ctk.CTkLabel(
            self, text='', font=('Arial', 12, 'bold'), text_color=TEXT_MUTED
        )
        self.update_clock()
        self.after(100, self._setup_fullscreen_binds)

        # ── Atajos globales ────────────────────────────────────────────────
        self.master_app.bind('<F1>', lambda e: self.safe_switch_view(SalesView))
        self.master_app.bind('<F2>', lambda e: self.safe_switch_view(CashView))
        self.master_app.bind('<F3>', lambda e: self.safe_switch_view(ArticlesView, requires_admin=True))
        self.master_app.bind('<F4>', lambda e: self.safe_switch_view(CustomersView, requires_admin=True))
        self.master_app.bind('<Escape>', lambda e: self.safe_switch_view(HomeView))

        # ── Carga inicial ──────────────────────────────────────────────────
        self.after(60, lambda: self.safe_switch_view(HomeView))
        self.after(400, self._refresh_cash_dot)

    # =========================================================
    # SIDEBAR
    # =========================================================
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=220, fg_color=SURFACE0, corner_radius=0
        )
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        # ── Logo ──────────────────────────────────────────────────────────
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        logo_frame.pack(fill='x', padx=16, pady=(22, 0))

        ctk.CTkLabel(
            logo_frame,
            text='☁ CloudPOS',
            font=('Arial', 18, 'bold'),
            text_color=ACCENT_TEXT,
            anchor='w',
        ).pack(side='left')

        # Dot de estado (verde = caja activa)
        self.lbl_dot = ctk.CTkLabel(
            logo_frame,
            text='● Cerrada',
            font=('Arial', 9, 'bold'),
            text_color='#f87171',
        )
        self.lbl_dot.pack(side='right', padx=(0, 4))

        ctk.CTkLabel(
            self.sidebar,
            text='Sistema de Gestión',
            font=('Arial', 10),
            text_color=TEXT_MUTED,
            anchor='w',
        ).pack(fill='x', padx=18, pady=(2, 16))

        section_divider(self.sidebar).pack(fill='x', padx=12, pady=(0, 12))

        # ── Scrollable nav ────────────────────────────────────────────────
        self.menu_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color='transparent', scrollbar_button_color=SURFACE3
        )
        self.menu_scroll.pack(fill='both', expand=True, padx=0, pady=0)

        # Sección pública
        make_section_label(self.menu_scroll, 'Principal').pack(
            fill='x', padx=16, pady=(4, 4)
        )
        for view_cls, icon, label, _ in NAV_ITEMS_PUBLIC:
            self._add_nav_btn(view_cls, icon, label)

        # Sección admin
        if self.is_admin:
            sections_seen = []
            for view_cls, icon, label, section in NAV_ITEMS_ADMIN:
                if section not in sections_seen:
                    sections_seen.append(section)
                    section_divider(self.menu_scroll).pack(fill='x', padx=12, pady=(10, 6))
                    make_section_label(self.menu_scroll, section).pack(
                        fill='x', padx=16, pady=(0, 4)
                    )
                self._add_nav_btn(view_cls, icon, label, requires_admin=True)

        # ── User card ─────────────────────────────────────────────────────
        section_divider(self.sidebar).pack(fill='x', padx=12, pady=(8, 0))
        self._build_user_card()

    def _add_nav_btn(self, view_cls, icon, label, requires_admin=False):
        btn = make_nav_button(
            self.menu_scroll, icon, label,
            command=lambda vc=view_cls, ra=requires_admin: self.safe_switch_view(vc, ra),
            active=False,
        )
        btn.pack(fill='x', padx=8, pady=2)
        self._nav_buttons[view_cls] = btn

    def _build_user_card(self):
        card = ctk.CTkFrame(
            self.sidebar, fg_color=SURFACE2, corner_radius=10,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill='x', padx=10, pady=10)

        inner = ctk.CTkFrame(card, fg_color='transparent')
        inner.pack(fill='x', padx=12, pady=10)

        # Avatar circular
        avatar = ctk.CTkLabel(
            inner,
            text=self.username[0].upper(),
            font=('Arial', 14, 'bold'),
            width=34, height=34,
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

        # Badge de rol
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

        # Logout
        ctk.CTkButton(
            card,
            text='Cerrar Sesión',
            fg_color='transparent',
            hover_color=SURFACE3,
            text_color=TEXT_MUTED,
            font=('Arial', 11),
            height=30,
            border_width=0,
            command=self.handle_logout,
        ).pack(fill='x', padx=8, pady=(0, 6))

    def _update_nav_highlight(self, active_view_class):
        """Marca el botón activo y desmarca todos los demás."""
        for view_cls, btn in self._nav_buttons.items():
            if view_cls == active_view_class:
                btn.configure(fg_color=ACCENT_DIM, text_color=ACCENT_TEXT, font=FONT_NAV_BOLD)
            else:
                btn.configure(fg_color='transparent', text_color=TEXT_SECONDARY, font=FONT_NAV)

    # =========================================================
    # MAIN AREA + SHORTCUTS BAR
    # =========================================================
    def _build_main_area(self):
        # Contenedor que envuelve barra de atajos + área de contenido
        area_container = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=0)
        area_container.pack(side='right', fill='both', expand=True)

        # IMPORTANTE: la barra inferior debe empaquetarse ANTES que el área expansible
        self._build_shortcuts_bar(area_container)

        self.main_area = ctk.CTkFrame(area_container, fg_color=SURFACE1, corner_radius=0)
        self.main_area.pack(side='top', fill='both', expand=True)
        self.current_view = None

    def _build_shortcuts_bar(self, parent):
        """Barra fija en la parte inferior con los atajos de teclado visibles."""
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

        inner = ctk.CTkFrame(bar, fg_color='transparent')
        inner.pack(side='left', padx=12, fill='y')

        self.lbl_view_shortcuts = ctk.CTkLabel(
            bar,
            text='',
            font=('Arial', 9, 'italic'),
            text_color=TEXT_MUTED,
        )
        self.lbl_view_shortcuts.pack(side='right', padx=12)

        for key, desc in _SHORTCUTS:
            chip = ctk.CTkFrame(inner, fg_color=SURFACE2, corner_radius=5)
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
                chip,
                text=f' {desc} ',
                font=('Arial', 9),
                text_color=TEXT_MUTED,
            ).pack(side='left', pady=2)

    # =========================================================
    # NAVEGACIÓN
    # =========================================================
    def safe_switch_view(self, view_class, requires_admin=False):
        if requires_admin and not self.is_admin:
            logger.warning('Acceso denegado: se requiere rol de administrador.')
            CTkMessagebox(
                title='Acceso Restringido',
                message='Necesitás permisos de administrador para acceder a esta sección.',
                icon='cancel',
            )
            return

        if self.current_view:
            self.current_view.destroy()
            self.current_view = None

        for widget in self.main_area.winfo_children():
            widget.destroy()

        self._active_view_class = view_class
        self._update_nav_highlight(view_class)

        # HomeView recibe el callback de navegación para los accesos directos
        if view_class is HomeView:
            self.current_view = HomeView(
                self.main_area, self.ctx,
                navigate=self.safe_switch_view,
            )
        else:
            self.current_view = view_class(self.main_area, self.ctx)

        self.current_view.pack(fill='both', expand=True)

        # Actualizar atajos contextuales en la barra inferior
        if hasattr(self, 'lbl_view_shortcuts'):
            from views.sales_view import SalesView as _SV
            if view_class is _SV:
                self.lbl_view_shortcuts.configure(
                    text='F5 Cobrar  ·  F6 Lector  ·  F7 Libre  ·  Supr Quitar'
                )
            else:
                self.lbl_view_shortcuts.configure(text='')

        # Refrescar dot de estado de caja
        self.after(200, self._refresh_cash_dot)

    def _refresh_cash_dot(self):
        """Actualiza el color del dot según si hay caja abierta."""
        try:
            from controllers.cash_controller import CashController
            ctrl = CashController(self.ctx.db_engine)
            session = ctrl.get_active_session(self.ctx.tenant_id, self.ctx.user_id)
            color = '#22c55e' if session else '#f87171'
            label = '● Abierta' if session else '● Cerrada'
        except Exception:
            color = '#888888'
            label = '●'
        if hasattr(self, 'lbl_dot'):
            self.lbl_dot.configure(text_color=color, text=label)

    def handle_logout(self):
        for key in ('<F1>', '<F2>', '<F3>', '<F4>', '<Escape>'):
            self.master_app.unbind(key)
        self._external_logout_command()

    # =========================================================
    # RELOJ Y FULLSCREEN
    # =========================================================
    def _setup_fullscreen_binds(self):
        top = self.winfo_toplevel()
        top.bind('<F11>', self.toggle_fullscreen)
        top.bind('<Escape>', self.exit_fullscreen)

    def update_clock(self):
        self.lbl_clock.configure(text=time.strftime('%d/%m/%Y  |  %H:%M:%S'))
        self._clock_job = self.after(1000, self.update_clock)

    def toggle_fullscreen(self, event=None):
        top = self.winfo_toplevel()
        self.is_fullscreen = not self.is_fullscreen
        top.attributes('-fullscreen', self.is_fullscreen)
        if self.is_fullscreen:
            self.lbl_clock.pack(side='bottom', anchor='se', padx=20, pady=5)
        else:
            self.lbl_clock.pack_forget()

    def exit_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.winfo_toplevel().attributes('-fullscreen', False)
            self.lbl_clock.pack_forget()

    def destroy(self):
        if hasattr(self, '_clock_job') and self._clock_job:
            self.after_cancel(self._clock_job)
            self._clock_job = None
        super().destroy()
