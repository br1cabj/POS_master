import customtkinter as ctk

from views.alerts_view import AlertsView
from views.articles_view import ArticlesView
from views.cash_view import CashView
from views.customers_view import CustomersView
from views.history_view import HistoryView

# Importamos todas las vistas (¡Incluyendo la nueva HomeView!)
from views.home_view import HomeView
from views.purchases_view import PurchasesView
from views.sales_view import SalesView
from views.users_view import UsersView


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, current_user, logout_command, db_engine=None, **kwargs):
		super().__init__(master, **kwargs)
		self.master_app = master
		self.current_user = current_user
		self.db_engine = db_engine

		self.pack(fill='both', expand=True)

		# --- Área Principal ---
		self.main_area = ctk.CTkFrame(self)
		self.main_area.pack(side='right', fill='both', expand=True, padx=10, pady=10)
		self.current_view = None

		# --- Sidebar (Menú Lateral) ---
		self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')

		# Título Sidebar
		ctk.CTkLabel(self.sidebar, text='MENÚ POS', font=('Arial', 20, 'bold')).pack(
			pady=(30, 10)
		)

		# Etiqueta de usuario activo
		ctk.CTkLabel(
			self.sidebar,
			text=f'👤 {self.current_user.username.capitalize()}',
			text_color='gray',
		).pack(pady=(0, 20))

		# --- BOTONES DEL MENÚ ---
		# 1. BOTONES PÚBLICOS (Todos los roles pueden verlos)
		self.btn_home = ctk.CTkButton(
			self.sidebar,
			text='🏠 Inicio / Resumen',
			command=lambda: self.switch_view(HomeView),
		)
		self.btn_home.pack(pady=5, padx=20)

		self.btn_sales = ctk.CTkButton(
			self.sidebar, text='💰 Ventas', command=lambda: self.switch_view(SalesView)
		)
		self.btn_sales.pack(pady=5, padx=20)

		self.btn_cash = ctk.CTkButton(
			self.sidebar, text='💵 Caja', command=lambda: self.switch_view(CashView)
		)
		self.btn_cash.pack(pady=5, padx=20)

		# 2. BOTONES PRIVADOS
		if self.current_user.role == 'admin':
			self.btn_customers = ctk.CTkButton(
				self.sidebar,
				text='👥 Clientes / Fiado',
				command=lambda: self.switch_view(CustomersView),
			)
			self.btn_customers.pack(pady=5, padx=20)

			self.btn_articles = ctk.CTkButton(
				self.sidebar,
				text='📦 Artículos',
				command=lambda: self.switch_view(ArticlesView),
			)
			self.btn_articles.pack(pady=5, padx=20)

			self.btn_purchases = ctk.CTkButton(
				self.sidebar,
				text='📥 Compras',
				command=lambda: self.switch_view(PurchasesView),
			)
			self.btn_purchases.pack(pady=5, padx=20)

			self.btn_history = ctk.CTkButton(
				self.sidebar,
				text='📜 Historial',
				command=lambda: self.switch_view(HistoryView),
			)
			self.btn_history.pack(pady=5, padx=20)

			self.btn_alerts = ctk.CTkButton(
				self.sidebar,
				text='⚠️ Alertas',
				text_color='orange',
				command=lambda: self.switch_view(AlertsView),
			)
			self.btn_alerts.pack(pady=5, padx=20)

			self.btn_users = ctk.CTkButton(
				self.sidebar,
				text='🛠️ Empleados',
				fg_color='#444444',
				command=lambda: self.switch_view(UsersView),
			)
			self.btn_users.pack(pady=5, padx=20)

		# Botón Salir
		ctk.CTkButton(
			self.sidebar,
			text='Cerrar Sesión',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=logout_command,
		).pack(side='bottom', pady=20)

		# --- INICIALIZACIÓN ---
		# Abrimos el Dashboard visual por defecto al arrancar
		self.switch_view(HomeView)

	# =========================================================
	# FUNCIÓN MAESTRA DE NAVEGACIÓN
	# =========================================================
	def switch_view(self, view_class):
		"""
		Destruye la vista actual y carga la nueva vista solicitada.
		:param view_class: La clase de la vista que queremos instanciar.
		"""
		# 1. Si hay una pantalla abierta, la borramos
		if self.current_view:
			self.current_view.destroy()

		# 2. Creamos la nueva pantalla pasando los 3 argumentos obligatorios
		self.current_view = view_class(
			self.main_area, self.current_user, self.db_engine
		)

		# 3. La mostramos en pantalla
		self.current_view.pack(fill='both', expand=True)
