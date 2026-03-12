import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from controllers.dashboard_controller import DashboardController


class HomeView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = DashboardController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=1)
		self.grid_columnconfigure(2, weight=1)
		self.grid_rowconfigure(3, weight=1)

		# 1. Manejo seguro del usuario
		username = (
			self.current_user.get('username', 'Usuario')
			if isinstance(self.current_user, dict)
			else self.current_user.username
		)

		# --- ENCABEZADO ---
		welcome_text = f'¡Bienvenido de nuevo, {username.capitalize()}!'

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

		# --- VARIABLES REACTIVAS PARA LAS TARJETAS ---
		self.var_revenue = ctk.StringVar(value='Cargando...')
		self.var_profit = ctk.StringVar(value='Cargando...')
		self.var_tickets = ctk.StringVar(value='...')

		# --- TARJETAS (CARDS) EN FILA 2 ---
		self.create_stat_card(
			row=2,
			col=0,
			title='💰 VENTAS DE HOY',
			text_var=self.var_revenue,
			bg_color='#2A8C55',
		)
		self.create_stat_card(
			row=2,
			col=1,
			title='📈 GANANCIA HOY',
			text_var=self.var_profit,
			bg_color='#2B5B84',
		)
		self.create_stat_card(
			row=2,
			col=2,
			title='🧾 TICKETS HOY',
			text_var=self.var_tickets,
			bg_color='#D97736',
		)

		# ==========================================
		# ZONA INFERIOR: GRÁFICO (Izquierda) Y TOP 5 (Derecha)
		# ==========================================

		# 1. Contenedor del Gráfico (Ocupa 2 columnas)
		self.chart_frame = ctk.CTkFrame(self, corner_radius=15)
		self.chart_frame.grid(
			row=3, column=0, columnspan=2, padx=(20, 10), pady=(20, 30), sticky='nsew'
		)

		# Etiqueta temporal mientras carga el gráfico
		self.lbl_chart_loading = ctk.CTkLabel(
			self.chart_frame, text='Generando gráfico...', font=('Arial', 14, 'italic')
		)
		self.lbl_chart_loading.place(relx=0.5, rely=0.5, anchor='center')

		# 2. Contenedor del Ranking Top 5 (Ocupa 1 columna)
		self.top_frame = ctk.CTkFrame(self, corner_radius=15, fg_color='#1E1E1E')
		self.top_frame.grid(
			row=3, column=2, padx=(10, 20), pady=(20, 30), sticky='nsew'
		)

		self.lbl_top_loading = ctk.CTkLabel(
			self.top_frame, text='Cargando ranking...', font=('Arial', 14, 'italic')
		)
		self.lbl_top_loading.place(relx=0.5, rely=0.5, anchor='center')

		# Lanzamos la carga de datos un instante DESPUÉS de dibujar la pantalla vacía
		self.after(150, self.load_dashboard_data)

	def create_stat_card(self, row, col, title, text_var, bg_color):
		"""Crea la tarjeta y le asigna un StringVar para que se actualice sola"""
		card = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=15)
		card.grid(row=row, column=col, padx=20, pady=10, sticky='nsew')

		lbl_title = ctk.CTkLabel(
			card, text=title, font=('Arial', 14, 'bold'), text_color='white'
		)
		lbl_title.pack(pady=(20, 10))

		lbl_value = ctk.CTkLabel(
			card, textvariable=text_var, font=('Arial', 36, 'bold'), text_color='white'
		)
		lbl_value.pack(pady=(0, 20))

	def load_dashboard_data(self):
		"""Descarga la información de la BD y actualiza la UI"""
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# 1. Actualizar Tarjetas
		revenue, profit, tickets = self.controller.get_today_stats(tenant_id)
		self.var_revenue.set(f'${revenue:.2f}')
		self.var_profit.set(f'${profit:.2f}')
		self.var_tickets.set(str(tickets))

		# 2. Dibujar Gráfico
		self.draw_weekly_chart(tenant_id)

		# 3. Dibujar Top 5
		self.draw_top_products(tenant_id)

	def draw_weekly_chart(self, tenant_id):
		dates, totals = self.controller.get_weekly_sales(tenant_id)

		# Quitamos el label de "Cargando..."
		if self.lbl_chart_loading:
			self.lbl_chart_loading.destroy()

		if not dates:
			ctk.CTkLabel(
				self.chart_frame,
				text='No hay suficientes datos esta semana.',
				text_color='gray',
			).place(relx=0.5, rely=0.5, anchor='center')
			return

		fig = Figure(figsize=(6, 3.5), dpi=100)
		fig.patch.set_facecolor('#2B2B2B')

		ax = fig.add_subplot(111)
		ax.set_facecolor('#2B2B2B')

		ax.yaxis.grid(True, linestyle='--', alpha=0.2, color='white')

		ax.bar(dates, totals, color='#00aaff', width=0.4)

		ax.tick_params(colors='white')
		ax.spines['bottom'].set_color('white')
		ax.spines['left'].set_color('white')
		ax.spines['top'].set_visible(False)
		ax.spines['right'].set_visible(False)

		ax.set_title(
			'Evolución de Ventas (Últimos 7 Días)', color='white', fontsize=12, pad=10
		)

		canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
		canvas.draw()
		canvas.get_tk_widget().pack(fill='both', expand=True, padx=15, pady=15)

	def draw_top_products(self, tenant_id):
		"""Dibuja una lista elegante con los productos más vendidos"""
		# Quitamos el label de "Cargando..."
		if self.lbl_top_loading:
			self.lbl_top_loading.destroy()

		ctk.CTkLabel(
			self.top_frame,
			text='🏆 Top 5 Más Vendidos',
			font=('Arial', 16, 'bold'),
			text_color='#f0ad4e',
		).pack(pady=(20, 15))

		top_items = self.controller.get_top_products(tenant_id)

		if not top_items:
			ctk.CTkLabel(
				self.top_frame, text='Aún no hay ventas registradas.', text_color='gray'
			).pack(pady=20)
			return

		# Dibujamos cada producto leyendo desde el DICCIONARIO
		for index, item in enumerate(top_items):
			desc = item.get('description', 'Desconocido')
			# Aseguramos que sea int/float en caso de que venga como Decimal
			qty = float(item.get('quantity', 0))
			# Si es un número entero exacto, le quitamos el ".0" visualmente
			qty_str = f'{int(qty)}' if qty.is_integer() else f'{qty:.2f}'

			if len(desc) > 20:
				desc = desc[:17] + '...'

			row_frame = ctk.CTkFrame(self.top_frame, fg_color='transparent')
			row_frame.pack(fill='x', padx=20, pady=8)

			ctk.CTkLabel(
				row_frame, text=f'{index + 1}. {desc}', font=('Arial', 14)
			).pack(side='left')

			ctk.CTkLabel(
				row_frame,
				text=f'{qty_str} ud.',
				font=('Arial', 14, 'bold'),
				text_color='#00aaff',
			).pack(side='right')
