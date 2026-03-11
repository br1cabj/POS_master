import customtkinter as ctk


class HomeView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.dashboard_controller import DashboardController

		self.controller = DashboardController(db_engine)

		# Configuramos la grilla para que las 3 tarjetas se expandan equitativamente
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=1)
		self.grid_columnconfigure(2, weight=1)

		# --- ENCABEZADO DE BIENVENIDA ---
		welcome_text = (
			f'¡Bienvenido de nuevo, {self.current_user.username.capitalize()}!'
		)
		self.lbl_welcome = ctk.CTkLabel(
			self, text=welcome_text, font=('Arial', 32, 'bold')
		)
		self.lbl_welcome.grid(row=0, column=0, columnspan=3, pady=(40, 5))

		self.lbl_subtitle = ctk.CTkLabel(
			self,
			text='Aquí tienes el resumen de tu negocio el día de hoy.',
			font=('Arial', 16),
			text_color='gray',
		)
		self.lbl_subtitle.grid(row=1, column=0, columnspan=3, pady=(0, 40))

		# --- CARGAMOS LOS DATOS ---
		revenue, profit, tickets = self.controller.get_today_stats(
			self.current_user.tenant_id
		)

		# --- CREAMOS LAS TARJETAS (CARDS) ---
		# Tarjeta 1: Ingresos Brutos
		self.create_stat_card(
			row=2,
			col=0,
			title='💰 VENTAS DEL DÍA',
			value=f'${revenue:.2f}',
			bg_color='#2A8C55',
		)

		# Tarjeta 2: Ganancia Neta
		self.create_stat_card(
			row=2,
			col=1,
			title='📈 GANANCIA NETA',
			value=f'${profit:.2f}',
			bg_color='#2B5B84',
		)

		# Tarjeta 3: Tickets Emitidos
		self.create_stat_card(
			row=2,
			col=2,
			title='🧾 TICKETS EMITIDOS',
			value=str(tickets),
			bg_color='#D97736',
		)

	def create_stat_card(self, row, col, title, value, bg_color):
		"""Función auxiliar para dibujar tarjetas estilizadas"""
		card = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=15)
		# Sticky 'nsew' hace que la tarjeta se expanda en todas direcciones
		card.grid(row=row, column=col, padx=20, pady=20, sticky='nsew')

		# Título de la tarjeta
		lbl_title = ctk.CTkLabel(
			card, text=title, font=('Arial', 14, 'bold'), text_color='white'
		)
		lbl_title.pack(pady=(30, 10))

		# Valor de la estadística
		lbl_value = ctk.CTkLabel(
			card, text=value, font=('Arial', 40, 'bold'), text_color='white'
		)
		lbl_value.pack(pady=(0, 30))
