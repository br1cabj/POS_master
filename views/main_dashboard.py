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
from views.users_view import UsersView


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, current_user, logout_command, db_engine=None, **kwargs):
		super().__init__(master, **kwargs)
		self.master_app = master
		self.current_user = current_user
		self.db_engine = db_engine

		self.pack(fill='both', expand=True)

		# --- Manejo seguro del usuario (Diccionario u Objeto) ---
		username = (
			self.current_user.get('username', 'Usuario')
			if isinstance(self.current_user, dict)
			else self.current_user.username
		)
		role = (
			self.current_user.get('role', 'user')
			if isinstance(self.current_user, dict)
			else getattr(self.current_user, 'role', 'user')
		)

		# --- Área Principal ---
		self.main_area = ctk.CTkFrame(self)
		self.main_area.pack(side='right', fill='both', expand=True, padx=10, pady=10)
		self.current_view = None

		# --- Sidebar (Menú Lateral) ---
		self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')

		# Título Sidebar (Fijo arriba)
		ctk.CTkLabel(self.sidebar, text='MENÚ POS', font=('Arial', 20, 'bold')).pack(
			pady=(30, 5)
		)

		# Etiqueta de usuario activo (Fijo arriba)
		ctk.CTkLabel(
			self.sidebar,
			text=f'👤 {username.capitalize()}',
			text_color='gray',
		).pack(pady=(0, 20))

		# --- CONTENEDOR DE BOTONES CON SCROLL ---
		self.menu_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color='transparent')
		self.menu_scroll.pack(fill='both', expand=True, padx=0, pady=0)

		# --- BOTONES DEL MENÚ ---
		# 1. BOTONES PÚBLICOS (Todos los roles pueden verlos)
		self.btn_home = ctk.CTkButton(
			self.menu_scroll,
			text='🏠 Inicio / Resumen',
			command=lambda: self.switch_view(HomeView),
		)
		self.btn_home.pack(pady=5, padx=20)

		self.btn_sales = ctk.CTkButton(
			self.menu_scroll,
			text='💰 Ventas',
			command=lambda: self.switch_view(SalesView),
		)
		self.btn_sales.pack(pady=5, padx=20)

		self.btn_cash = ctk.CTkButton(
			self.menu_scroll, text='💵 Caja', command=lambda: self.switch_view(CashView)
		)
		self.btn_cash.pack(pady=5, padx=20)

		# 2. BOTONES PRIVADOS (Solo Administradores)
		if str(role).lower() == 'admin' or str(username).lower() == 'admin':
			ctk.CTkLabel(
				self.menu_scroll,
				text='--- Gestión ---',
				text_color='gray',
				font=('Arial', 10),
			).pack(pady=(10, 0))

			self.btn_articles = ctk.CTkButton(
				self.menu_scroll,
				text='📦 Artículos',
				command=lambda: self.switch_view(ArticlesView),
			)
			self.btn_articles.pack(pady=5, padx=20)

			# --- KARDEX / AUDITORÍA ---
			self.btn_kardex = ctk.CTkButton(
				self.menu_scroll,
				text='📊 Kardex / Inventario',
				fg_color='#005580',
				hover_color='#003d5c',
				command=lambda: self.switch_view(KardexView),
			)
			self.btn_kardex.pack(pady=5, padx=20)

			self.btn_purchases = ctk.CTkButton(
				self.menu_scroll,
				text='📥 Compras',
				command=lambda: self.switch_view(PurchasesView),
			)
			self.btn_purchases.pack(pady=5, padx=20)

			self.btn_customers = ctk.CTkButton(
				self.menu_scroll,
				text='👥 Clientes / Fiado',
				command=lambda: self.switch_view(CustomersView),
			)
			self.btn_customers.pack(pady=5, padx=20)

			self.btn_history = ctk.CTkButton(
				self.menu_scroll,
				text='📜 Historial Ventas',
				command=lambda: self.switch_view(HistoryView),
			)
			self.btn_history.pack(pady=5, padx=20)

			self.btn_alerts = ctk.CTkButton(
				self.menu_scroll,
				text='⚠️ Alertas',
				text_color='orange',
				command=lambda: self.switch_view(AlertsView),
			)
			self.btn_alerts.pack(pady=5, padx=20)

			self.btn_users = ctk.CTkButton(
				self.menu_scroll,
				text='🛠️ Empleados',
				fg_color='#444444',
				command=lambda: self.switch_view(UsersView),
			)
			self.btn_users.pack(pady=5, padx=20)

		# --- Botón Salir (Fijo abajo, fuera del scroll) ---
		ctk.CTkButton(
			self.sidebar,
			text='Cerrar Sesión',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=logout_command,
		).pack(side='bottom', pady=20, padx=20)

		# --- INICIALIZACIÓN ---
		# Abrimos el Dashboard visual por defecto al arrancar, pero con un micro-retraso
		# para que la ventana principal termine de dibujarse primero.
		self.after(50, lambda: self.switch_view(HomeView))

		# --- ATAJOS GLOBALES DE NAVEGACION ---
		self.master_app.bind('<F1>', lambda e: self.switch_view(SalesView))
		self.master_app.bind('<F2>', lambda e: self.switch_view(CashView))
		self.master_app.bind('<F3>', lambda e: self.switch_view(ArticlesView))
		self.master_app.bind('<F4>', lambda e: self.switch_view(CustomersView))
		self.master_app.bind('<Escape>', lambda e: self.switch_view(HomeView))

	# =========================================================
	# FUNCIÓN MAESTRA DE NAVEGACIÓN
	# =========================================================
	def switch_view(self, view_class):
		"""
		Destruye la vista actual y carga la nueva vista solicitada.
		:param view_class: La clase de la vista que queremos instanciar.
		"""
		# 1. Limpieza agresiva de memoria (Mejor práctica en Tkinter)
		for widget in self.main_area.winfo_children():
			widget.destroy()

		self.current_view = None

		# 2. Creamos la nueva pantalla pasando los 3 argumentos obligatorios
		self.current_view = view_class(
			self.main_area, self.current_user, self.db_engine
		)

		# 3. La mostramos en pantalla
		self.current_view.pack(fill='both', expand=True)
