import customtkinter as ctk


class CashView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.cash_controller import CashController

		self.controller = CashController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# Contenedor central para que se vea bonito
		self.center_frame = ctk.CTkFrame(self, width=400, corner_radius=15)
		self.center_frame.grid(row=0, column=0, padx=20, pady=20)

		self.lbl_title = ctk.CTkLabel(
			self.center_frame, text='Control de Caja', font=('Arial', 24, 'bold')
		)
		self.lbl_title.pack(pady=20, padx=50)

		# Elementos dinámicos
		self.lbl_status = ctk.CTkLabel(self.center_frame, text='', font=('Arial', 16))
		self.lbl_status.pack(pady=10)

		self.entry_amount = ctk.CTkEntry(
			self.center_frame, placeholder_text='Monto ($)', font=('Arial', 18)
		)
		self.entry_amount.pack(pady=10)

		self.btn_action = ctk.CTkButton(
			self.center_frame,
			text='',
			font=('Arial', 16, 'bold'),
			height=40,
			command=self.handle_action,
		)
		self.btn_action.pack(pady=20)

		self.lbl_msg = ctk.CTkLabel(self.center_frame, text='')
		self.lbl_msg.pack(pady=10)

		self.active_session = None
		self.refresh_view()

	def refresh_view(self):
		"""Revisa la base de datos y cambia la pantalla según el estado de la caja"""
		self.active_session = self.controller.get_active_session(
			self.current_user.tenant_id, self.current_user.id
		)

		if self.active_session:
			# ESTADO: CAJA ABIERTA
			self.lbl_status.configure(
				text=f'CAJA ABIERTA\nFondo Inicial: ${self.active_session.opening_balance:.2f}',
				text_color='green',
			)
			self.entry_amount.configure(
				placeholder_text='Efectivo real en caja al cerrar'
			)
			self.btn_action.configure(
				text='CERRAR CAJA', fg_color='red', hover_color='#aa0000'
			)
		else:
			# ESTADO: CAJA CERRADA
			self.lbl_status.configure(
				text='CAJA CERRADA\nDebes abrirla para poder vender.',
				text_color='orange',
			)
			self.entry_amount.configure(placeholder_text='Fondo de cambio inicial ($)')
			self.btn_action.configure(
				text='ABRIR CAJA', fg_color='green', hover_color='#00aa00'
			)

		self.entry_amount.delete(0, 'end')

	def handle_action(self):
		"""Decide si abre o cierra dependiendo del estado actual"""
		amount_str = self.entry_amount.get().strip()

		if not amount_str.replace('.', '', 1).isdigit():
			self.lbl_msg.configure(
				text='Por favor, ingresa un número válido.', text_color='red'
			)
			return

		amount = float(amount_str)

		if self.active_session:
			# Acción: CERRAR
			success, msg = self.controller.close_session(self.active_session.id, amount)
		else:
			# Acción: ABRIR
			success, msg = self.controller.open_session(
				self.current_user.tenant_id, self.current_user.id, amount
			)

		if success:
			self.lbl_msg.configure(text=msg, text_color='green')
			self.refresh_view()  # Recargar la pantalla
		else:
			self.lbl_msg.configure(text=msg, text_color='red')
