import customtkinter as ctk

from views.alerts_view import AlertsView
from views.articles_view import ArticlesView
from views.cash_view import CashView
from views.customers_view import CustomersView
from views.history_view import HistoryView
from views.purchases_view import PurchasesView
from views.sales_view import SalesView
from views.users_view import UsersView


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, current_user, logout_command, db_engine=None, **kwargs):
		super().__init__(master)
		self.master_app = master
		self.current_user = current_user

		if db_engine:
			self.db_engine = db_engine

		self.pack(fill='both', expand=True)

		# --- Sidebar (Menú Lateral) ---
		self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')

		# Título Sidebar
		ctk.CTkLabel(self.sidebar, text='MENÚ POS', font=('Arial', 20, 'bold')).pack(
			pady=30
		)

		# Botón de Artículos
		self.btn_articles = ctk.CTkButton(
			self.sidebar, text='📦 Artículos', command=self.show_articles
		)
		self.btn_articles.pack(pady=10, padx=20)

		self.btn_alerts = ctk.CTkButton(
			self.sidebar,
			text='⚠️ Alertas',
			text_color='orange',
			command=self.show_alerts,
		)
		self.btn_alerts.pack(pady=10, padx=20)

		self.btn_cash = ctk.CTkButton(
			self.sidebar, text='💰 Caja', command=self.show_cash
		)
		self.btn_cash.pack(pady=10, padx=20)

		self.btn_sales = ctk.CTkButton(
			self.sidebar, text='💰 Ventas', command=self.show_sales
		)
		self.btn_sales.pack(pady=10, padx=20)

		self.btn_purchases = ctk.CTkButton(
			self.sidebar, text='📥 Compras', command=self.show_purchases
		)
		self.btn_purchases.pack(pady=10, padx=20)

		self.btn_history = ctk.CTkButton(
			self.sidebar, text='📜 Historial', command=self.show_history
		)
		self.btn_history.pack(pady=10, padx=20)

		self.btn_customers = ctk.CTkButton(
			self.sidebar, text='👥 Clientes / Fiado', command=self.show_customers
		)
		self.btn_customers.pack(pady=10, padx=20)

		# Solo dibujamos este botón si el rol es "admin"
		if self.current_user.role == 'admin':
			self.btn_users = ctk.CTkButton(
				self.sidebar, text='👥 Empleados', command=self.show_users
			)
			self.btn_users.pack(pady=10, padx=20)

		# Botón Salir
		ctk.CTkButton(
			self.sidebar, text='Cerrar Sesión', fg_color='red', command=logout_command
		).pack(side='bottom', pady=20)

		# --- Área Principal ---
		self.main_area = ctk.CTkFrame(self)
		self.main_area.pack(side='right', fill='both', expand=True, padx=10, pady=10)

		self.current_view = None

		self.show_articles()

	def show_articles(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = ArticlesView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_users(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = UsersView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_sales(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = SalesView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_history(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = HistoryView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_cash(self):
		if self.current_view:
			self.current_view.destroy()
			self.current_view = CashView(
				self.main_area, self.current_user, self.master_app.db_engine
			)
			self.current_view.pack(fill='both', expand=True)

	def show_alerts(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = AlertsView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_purchases(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = PurchasesView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_customers(self):
		if self.current_view:
			self.current_view.destroy()
		self.current_view = CustomersView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)
