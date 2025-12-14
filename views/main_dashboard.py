import customtkinter as ctk

from views.products_view import ProductsView
from views.sales_view import SalesView


class MainDashboard(ctk.CTkFrame):
	def __init__(self, master, current_user, logout_command):
		super().__init__(master)

		# Referencias
		self.master_app = master
		self.current_user = current_user

		self.db_engine = getattr(master, 'db_engine', None)
		if not self.db_engine:
			print('ADVERTENCIA: No se encontró db_engine en la App principal.')

		# Configuración del Frame principal
		self.pack(fill='both', expand=True)

		# --- 1. SIDEBAR (Menú Lateral) ---
		self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
		self.sidebar.pack(side='left', fill='y')

		# Título Sidebar
		self.lbl_title = ctk.CTkLabel(
			self.sidebar, text='MENÚ POS', font=('Arial', 20, 'bold')
		)
		self.lbl_title.pack(pady=30)

		# Botones del Menú
		self.btn_products = ctk.CTkButton(
			self.sidebar,
			text='📦 Productos',
			command=self.show_products,
			fg_color='transparent',
			border_width=2,
			text_color=('gray10', '#DCE4EE'),
		)
		self.btn_products.pack(pady=10, padx=20, fill='x')

		self.btn_sales = ctk.CTkButton(
			self.sidebar,
			text='💰 Ventas',
			fg_color='transparent',
			border_width=2,
			text_color=('gray10', '#DCE4EE'),
		)
		self.btn_sales.pack(pady=10, padx=20)

		# Botón Salir
		self.spacer = ctk.CTkFrame(self.sidebar, fg_color='transparent')
		self.spacer.pack(side='top', fill='both', expand=True)

		self.btn_logout = ctk.CTkButton(
			self.sidebar,
			text='Cerrar Sesión',
			fg_color='firebrick',
			hover_color='darkred',
			command=logout_command,
		)
		self.btn_logout.pack(side='bottom', pady=20, padx=20, fill='x')

		# --- 2. ÁREA PRINCIPAL ---
		self.main_area = ctk.CTkFrame(self, fg_color='transparent')
		self.main_area.pack(side='right', fill='both', expand=True, padx=10, pady=10)

		# Variable para rastrear la vista actual
		self.current_view = None

		# Cargar vista inicial
		self.show_products()

	def highlight_btn(self, active_btn: ctk.CTkButton):
		"""Pequeña función visual para resaltar el botón activo"""

		self.btn_products.configure(fg_color='transparent')

		# Pintamos el activo con el color del tema
		active_btn.configure(fg_color=['#3B8ED0', '#1F6AA5'])

	def show_products(self):
		"""Cambia la vista principal a Productos"""

		# 1. Efecto visual en el botón
		self.highlight_btn(self.btn_products)

		# 2. Limpiar vista anterior
		if self.current_view:
			self.current_view.destroy()

		self.current_view = ProductsView(
			self.main_area, self.current_user, self.db_engine
		)
		self.current_view.pack(fill='both', expand=True)

	def show_sales(self):
		if self.current_view:
			self.current_view.destroy()

		self.current_view = SalesView(
			self.main_area, self.current_user, self.master_app.db_engine
		)
		self.current_view.pack(fill='both', expand=True)
