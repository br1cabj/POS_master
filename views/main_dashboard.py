import customtkinter as ctk

from views.articles_view import ArticlesView
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

		# Botón de Artículos (Reemplaza al viejo Productos)
		self.btn_articles = ctk.CTkButton(
			self.sidebar, text='📦 Artículos', command=self.show_articles
		)
		self.btn_articles.pack(pady=10, padx=20)

		# Botones temporales desactivados
		self.btn_sales = ctk.CTkButton(
			self.sidebar, text='💰 Ventas', command=self.show_sales
		)
		self.btn_sales.pack(pady=10, padx=20)

		self.btn_history = ctk.CTkButton(
			self.sidebar, text='📜 Historial', state='disabled'
		)
		self.btn_history.pack(pady=10, padx=20)

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

		# Iniciamos mostrando la pantalla de artículos por defecto
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
