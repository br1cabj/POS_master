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
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, columnspan=3, pady=(30, 5), sticky='ew')

		welcome_text = f'¡Bienvenido de nuevo, {username.capitalize()}!'
		self.lbl_welcome = ctk.CTkLabel(
			header_frame, text=welcome_text, font=('Arial', 32, 'bold')
		)
		self.lbl_welcome.pack(side='left', padx=20)

		# 🛡️ MEJORA: Botón de refresco para el Dashboard
		self.btn_refresh = ctk.CTkButton(
			header_frame,
			text='🔄 Actualizar Dashboard',
			command=self.load_dashboard_data,
			width=150,
		)
		self.btn_refresh.pack(side='right', padx=20)

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
		# ZONA INFERIOR: GRÁFICO Y TOP 5
		# ==========================================

		# 1. Contenedor del Gráfico
		self.chart_frame = ctk.CTkFrame(self, corner_radius=15)
		self.chart_frame.grid(
			row=3, column=0, columnspan=2, padx=(20, 10), pady=(20, 30), sticky='nsew'
		)
		self.canvas_widget = None  # 🛡️ Guardamos la referencia para limpiar memoria

		# 2. Contenedor del Ranking Top 5
		self.top_frame = ctk.CTkFrame(self, corner_radius=15, fg_color='#1E1E1E')
		self.top_frame.grid(
			row=3, column=2, padx=(10, 20), pady=(20, 30), sticky='nsew'
		)

		# Lanzamos la carga de datos
		self.after(150, self.load_dashboard_data)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def create_stat_card(self, row, col, title, text_var, bg_color):
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
		# Deshabilitar botón temporalmente para evitar spam de clics
		if hasattr(self, 'btn_refresh'):
			self.btn_refresh.configure(state='disabled')

		tenant_id = self._get_tenant_id()

		# 1. Actualizar Tarjetas
		revenue, profit, tickets = self.controller.get_today_stats(tenant_id)

		# 🐛 SOLUCIÓN BUG 3: Conversión segura a float desde Decimal
		self.var_revenue.set(f'${float(revenue):.2f}')
		self.var_profit.set(f'${float(profit):.2f}')
		self.var_tickets.set(str(tickets))

		# 2. Dibujar Gráfico
		self.draw_weekly_chart(tenant_id)

		# 3. Dibujar Top 5
		self.draw_top_products(tenant_id)

		# Reactivar botón
		if hasattr(self, 'btn_refresh'):
			self.btn_refresh.configure(state='normal')

	def draw_weekly_chart(self, tenant_id):
		# 🐛 SOLUCIÓN BUG 1: Destruir el canvas anterior para evitar memory leaks
		if self.canvas_widget:
			self.canvas_widget.destroy()
			self.canvas_widget = None

		# Limpiar etiquetas previas en el frame del gráfico
		for widget in self.chart_frame.winfo_children():
			widget.destroy()

		dates, totals = self.controller.get_weekly_sales(tenant_id)

		if not dates:
			ctk.CTkLabel(
				self.chart_frame,
				text='No hay suficientes datos esta semana.',
				text_color='gray',
				font=('Arial', 16),
			).place(relx=0.5, rely=0.5, anchor='center')
			return

		fig = Figure(figsize=(6, 3.5), dpi=100)
		fig.patch.set_facecolor('#2B2B2B')

		ax = fig.add_subplot(111)
		ax.set_facecolor('#2B2B2B')
		ax.yaxis.grid(True, linestyle='--', alpha=0.2, color='white')

		# Convertimos los totales (Decimales) a float para que Matplotlib pueda dibujarlos
		float_totals = [float(t) for t in totals]
		ax.bar(dates, float_totals, color='#00aaff', width=0.4)

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
		self.canvas_widget = canvas.get_tk_widget()
		self.canvas_widget.pack(fill='both', expand=True, padx=15, pady=15)

	def draw_top_products(self, tenant_id):
		"""Dibuja una lista elegante con los productos más vendidos"""
		# 🐛 SOLUCIÓN BUG 2: Limpiar los items viejos antes de dibujar los nuevos
		for widget in self.top_frame.winfo_children():
			widget.destroy()

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

		for index, item in enumerate(top_items):
			desc = item.get('description', 'Desconocido')
			qty = float(item.get('quantity', 0))
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
