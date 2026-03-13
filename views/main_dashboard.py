import customtkinter as ctk

# Importamos todas las vistas
from views.alerts_view import AlertsView
from views.articles_view import ArticlesView
from views.cash_view import CashView
from views.customers_view import CustomersView
from views.history_view import HistoryView
from views.home_view import HomeView
from views.kardex_view import KardexView
from views.purchases_view import PurchasesView
from views.sales_view import SalesView
from views.suppliers_view import SuppliersView
from views.users_view import UsersView


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, current_user, logout_command, db_engine=None, **kwargs):
		super().__init__(master, **kwargs)
		self.master_app = master
		self.current_user = current_user
		self.db_engine = db_engine

		# Guardamos el comando de logout original para envolverlo luego
		self._external_logout_command = logout_command

		self.pack(fill='both', expand=True)

		# --- Manejo seguro del usuario ---
		self.username = (
			self.current_user.get('username', 'Usuario')
			if isinstance(self.current_user, dict)
			else self.current_user.username
		)
		raw_role = (
			self.current_user.get('role', 'user')
			if isinstance(self.current_user, dict)
			else getattr(self.current_user, 'role', 'user')
		)
		self.is_admin = (
			str(raw_role).strip().lower() == 'admin'
			or str(self.username).strip().lower() == 'admin'
		)

		# --- Área Principal ---
		self.main_area = ctk.CTkFrame(self)
		self.main_area.pack(side='right', fill='both', expand=True, padx=10, pady=10)
		self.current_view = None

		# --- Sidebar (Menú Lateral) ---
		self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')

		ctk.CTkLabel(self.sidebar, text='MENÚ POS', font=('Arial', 20, 'bold')).pack(
			pady=(30, 5)
		)
		ctk.CTkLabel(
			self.sidebar,
			text=f'👤 {self.username.capitalize()}',
			text_color='gray',
		).pack(pady=(0, 20))

		# --- CONTENEDOR DE BOTONES ---
		self.menu_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color='transparent')
		self.menu_scroll.pack(fill='both', expand=True, padx=0, pady=0)

		# 1. BOTONES PÚBLICOS
		self.btn_home = ctk.CTkButton(
			self.menu_scroll,
			text='🏠 Inicio / Resumen',
			command=lambda: self.safe_switch_view(HomeView),
		)
		self.btn_home.pack(pady=5, padx=20)

		self.btn_sales = ctk.CTkButton(
			self.menu_scroll,
			text='💰 Ventas',
			command=lambda: self.safe_switch_view(SalesView),
		)
		self.btn_sales.pack(pady=5, padx=20)

		self.btn_cash = ctk.CTkButton(
			self.menu_scroll,
			text='💵 Caja',
			command=lambda: self.safe_switch_view(CashView),
		)
		self.btn_cash.pack(pady=5, padx=20)

		# 2. BOTONES PRIVADOS (Solo Administradores)
		if self.is_admin:
			ctk.CTkLabel(
				self.menu_scroll,
				text='--- Gestión ---',
				text_color='gray',
				font=('Arial', 10),
			).pack(pady=(10, 0))

			self.btn_articles = ctk.CTkButton(
				self.menu_scroll,
				text='📦 Artículos',
				command=lambda: self.safe_switch_view(
					ArticlesView, requires_admin=True
				),
			)
			self.btn_articles.pack(pady=5, padx=20)

			self.btn_kardex = ctk.CTkButton(
				self.menu_scroll,
				text='📊 Kardex / Inventario',
				fg_color='#005580',
				hover_color='#003d5c',
				command=lambda: self.safe_switch_view(KardexView, requires_admin=True),
			)
			self.btn_kardex.pack(pady=5, padx=20)

			self.btn_purchases = ctk.CTkButton(
				self.menu_scroll,
				text='📥 Compras',
				command=lambda: self.safe_switch_view(
					PurchasesView, requires_admin=True
				),
			)
			self.btn_purchases.pack(pady=5, padx=20)

			self.btn_customers = ctk.CTkButton(
				self.menu_scroll,
				text='👥 Clientes / Fiado',
				command=lambda: self.safe_switch_view(
					CustomersView, requires_admin=True
				),
			)
			self.btn_customers.pack(pady=5, padx=20)

			self.btn_history = ctk.CTkButton(
				self.menu_scroll,
				text='📜 Historial Ventas',
				command=lambda: self.safe_switch_view(HistoryView, requires_admin=True),
			)
			self.btn_history.pack(pady=5, padx=20)

			self.btn_suppliers = ctk.CTkButton(
				self.menu_scroll,
				text='🚚 Proveedores',
				command=lambda: self.safe_switch_view(
					SuppliersView, requires_admin=True
				),
			)
			self.btn_suppliers.pack(pady=5, padx=20)

			self.btn_alerts = ctk.CTkButton(
				self.menu_scroll,
				text='⚠️ Alertas',
				text_color='orange',
				command=lambda: self.safe_switch_view(AlertsView, requires_admin=True),
			)
			self.btn_alerts.pack(pady=5, padx=20)

			self.btn_users = ctk.CTkButton(
				self.menu_scroll,
				text='🛠️ Empleados',
				fg_color='#444444',
				command=lambda: self.safe_switch_view(UsersView, requires_admin=True),
			)
			self.btn_users.pack(pady=5, padx=20)

		# --- Botón Salir ---
		ctk.CTkButton(
			self.sidebar,
			text='Cerrar Sesión',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.handle_logout,
		).pack(side='bottom', pady=20, padx=20)

		# --- INICIALIZACIÓN ---
		self.after(50, lambda: self.safe_switch_view(HomeView))

		# --- ATAJOS GLOBALES DE NAVEGACION ---
		self.master_app.bind('<F1>', lambda e: self.safe_switch_view(SalesView))
		self.master_app.bind('<F2>', lambda e: self.safe_switch_view(CashView))
		self.master_app.bind(
			'<F3>', lambda e: self.safe_switch_view(ArticlesView, requires_admin=True)
		)
		self.master_app.bind(
			'<F4>', lambda e: self.safe_switch_view(CustomersView, requires_admin=True)
		)
		self.master_app.bind('<Escape>', lambda e: self.safe_switch_view(HomeView))

	# =========================================================
	# FUNCIONES MAESTRAS DE NAVEGACIÓN Y LIMPIEZA
	# =========================================================

	def safe_switch_view(self, view_class, requires_admin=False):
		"""
		🛡️ ESCUDO: Destruye la vista actual y carga la nueva solo si tiene permisos.
		"""
		# Verificación de Seguridad para atajos de teclado
		if requires_admin and not self.is_admin:
			print(
				'Acceso denegado: Se requiere rol de administrador.'
			)  # Podrías usar CTkMessagebox aquí
			return

		# 1. Limpieza profunda
		if self.current_view:
			# Si la vista tiene un método de destrucción propio (ej. para limpiar gráficos), lo llamamos
			if hasattr(self.current_view, 'destroy_custom'):
				self.current_view.destroy_custom()

			self.current_view.destroy()
			self.current_view = None

		# Por si quedó algún widget huérfano
		for widget in self.main_area.winfo_children():
			widget.destroy()

		# 2. Instanciamos y mostramos la nueva pantalla
		self.current_view = view_class(
			self.main_area, self.current_user, self.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def handle_logout(self):
		"""
		Limpiamos los eventos globales antes de cerrar sesión.
		"""
		self.master_app.unbind('<F1>')
		self.master_app.unbind('<F2>')
		self.master_app.unbind('<F3>')
		self.master_app.unbind('<F4>')
		self.master_app.unbind('<Escape>')

		# Llamamos al comando de logout original (que volverá a la pantalla de login)
		self._external_logout_command()
