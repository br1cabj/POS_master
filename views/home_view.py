import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class HomeView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.dashboard_controller import DashboardController

		self.controller = DashboardController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=1)
		self.grid_columnconfigure(2, weight=1)
		self.grid_rowconfigure(3, weight=1)

		# --- ENCABEZADO ---
		welcome_text = (
			f'¡Bienvenido de nuevo, {self.current_user.username.capitalize()}!'
		)
		self.lbl_welcome = ctk.CTkLabel(
			self, text=welcome_text, font=('Arial', 32, 'bold')
		)
		self.lbl_welcome.grid(row=0, column=0, columnspan=3, pady=(30, 5))

		self.lbl_subtitle = ctk.CTkLabel(
			self,
			text='Resumen de actividad y rendimiento de tu negocio.',
			font=('Arial', 16),
			text_color='gray',
		)
		self.lbl_subtitle.grid(row=1, column=0, columnspan=3, pady=(0, 20))

		# --- TARJETAS (CARDS) EN FILA 2 ---
		revenue, profit, tickets = self.controller.get_today_stats(
			self.current_user.tenant_id
		)
		self.create_stat_card(
			row=2,
			col=0,
			title='💰 VENTAS DE HOY',
			value=f'${revenue:.2f}',
			bg_color='#2A8C55',
		)
		self.create_stat_card(
			row=2,
			col=1,
			title='📈 GANANCIA HOY',
			value=f'${profit:.2f}',
			bg_color='#2B5B84',
		)
		self.create_stat_card(
			row=2, col=2, title='🧾 TICKETS HOY', value=str(tickets), bg_color='#D97736'
		)

		# ==========================================
		# ZONA INFERIOR: GRÁFICO (Izquierda) Y TOP 5 (Derecha)
		# ==========================================

		# 1. Contenedor del Gráfico (Ocupa 2 columnas)
		self.chart_frame = ctk.CTkFrame(self, corner_radius=15)
		self.chart_frame.grid(
			row=3, column=0, columnspan=2, padx=(20, 10), pady=(20, 30), sticky='nsew'
		)
		self.draw_weekly_chart()

		# 2. Contenedor del Ranking Top 5 (Ocupa 1 columna)
		self.top_frame = ctk.CTkFrame(self, corner_radius=15, fg_color='#1E1E1E')
		self.top_frame.grid(
			row=3, column=2, padx=(10, 20), pady=(20, 30), sticky='nsew'
		)
		self.draw_top_products()

	def create_stat_card(self, row, col, title, value, bg_color):
		card = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=15)
		card.grid(row=row, column=col, padx=20, pady=10, sticky='nsew')

		lbl_title = ctk.CTkLabel(
			card, text=title, font=('Arial', 14, 'bold'), text_color='white'
		)
		lbl_title.pack(pady=(20, 10))

		lbl_value = ctk.CTkLabel(
			card, text=value, font=('Arial', 36, 'bold'), text_color='white'
		)
		lbl_value.pack(pady=(0, 20))

	def draw_weekly_chart(self):
		dates, totals = self.controller.get_weekly_sales(self.current_user.tenant_id)
		if not dates:
			return

		# Gráfico más compacto: figsize=(6, 3.5)
		fig = Figure(figsize=(6, 3.5), dpi=100)
		fig.patch.set_facecolor('#2B2B2B')

		ax = fig.add_subplot(111)
		ax.set_facecolor('#2B2B2B')

		# Agregamos una cuadrícula horizontal muy suave para que se lea mejor
		ax.yaxis.grid(True, linestyle='--', alpha=0.2, color='white')

		bars = ax.bar(dates, totals, color='#00aaff', width=0.4)  # Barras más finas

		ax.tick_params(colors='white')
		ax.spines['bottom'].set_color('white')
		ax.spines['left'].set_color('white')
		ax.spines['top'].set_visible(False)
		ax.spines['right'].set_visible(False)

		ax.set_title(
			'Evolución de Ventas (Últimos 7 Días)', color='white', fontsize=12, pad=10
		)

		# Incrustamos
		canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
		canvas.draw()
		canvas.get_tk_widget().pack(fill='both', expand=True, padx=15, pady=15)

	def draw_top_products(self):
		"""Dibuja una lista elegante con los productos más vendidos"""
		ctk.CTkLabel(
			self.top_frame,
			text='🏆 Top 5 Más Vendidos',
			font=('Arial', 16, 'bold'),
			text_color='#f0ad4e',
		).pack(pady=(20, 15))

		top_items = self.controller.get_top_products(self.current_user.tenant_id)

		if not top_items:
			ctk.CTkLabel(
				self.top_frame, text='Aún no hay ventas registradas.', text_color='gray'
			).pack(pady=20)
			return

		# Dibujamos cada producto como un pequeño renglón
		for index, item in enumerate(top_items):
			desc = item[0]
			qty = item[1]

			# Cortamos el texto si el nombre del producto es muy largo
			if len(desc) > 20:
				desc = desc[:17] + '...'

			row_frame = ctk.CTkFrame(self.top_frame, fg_color='transparent')
			row_frame.pack(fill='x', padx=20, pady=8)

			# Número y Nombre a la izquierda
			ctk.CTkLabel(
				row_frame, text=f'{index + 1}. {desc}', font=('Arial', 14)
			).pack(side='left')

			# Cantidad a la derecha
			ctk.CTkLabel(
				row_frame,
				text=f'{qty} ud.',
				font=('Arial', 14, 'bold'),
				text_color='#00aaff',
			).pack(side='right')
