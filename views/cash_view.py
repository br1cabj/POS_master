import customtkinter as ctk

from controllers.cash_controller import CashController


class CashView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = CashController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# --- PANEL IZQUIERDO: ESTADO DE CAJA Y ARQUEO ---
		self.left_panel = ctk.CTkFrame(self, corner_radius=15)
		self.left_panel.grid(row=0, column=0, padx=10, pady=20, sticky='nsew')

		self.lbl_title = ctk.CTkLabel(
			self.left_panel, text='Control de Caja', font=('Arial', 24, 'bold')
		)
		self.lbl_title.pack(pady=20)

		self.lbl_status = ctk.CTkLabel(self.left_panel, text='', font=('Arial', 16))
		self.lbl_status.pack(pady=5)

		self.lbl_summary = ctk.CTkLabel(
			self.left_panel, text='', font=('Courier', 14), justify='left'
		)
		self.lbl_summary.pack(pady=10)

		self.entry_amount = ctk.CTkEntry(
			self.left_panel, placeholder_text='Monto ($)', font=('Arial', 16)
		)
		self.entry_amount.pack(pady=10)

		self.btn_action = ctk.CTkButton(
			self.left_panel,
			text='',
			font=('Arial', 16, 'bold'),
			height=40,
			command=self.handle_action,
		)
		self.btn_action.pack(pady=10)

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='')
		self.lbl_msg.pack(pady=5)

		# --- PANEL DERECHO: MOVIMIENTOS MANUALES (Solo visible si está abierta) ---
		self.right_panel = ctk.CTkFrame(self, corner_radius=15)
		self.right_panel.grid(row=0, column=1, padx=10, pady=20, sticky='nsew')

		ctk.CTkLabel(
			self.right_panel,
			text='Registrar Gasto / Ingreso',
			font=('Arial', 20, 'bold'),
		).pack(pady=20)

		self.combo_mov_type = ctk.CTkComboBox(
			self.right_panel, values=['gasto', 'ingreso']
		)
		self.combo_mov_type.pack(pady=10)

		self.entry_mov_desc = ctk.CTkEntry(
			self.right_panel,
			placeholder_text='Descripción (Ej. Pago de agua)',
			width=250,
		)
		self.entry_mov_desc.pack(pady=10)

		self.entry_mov_amount = ctk.CTkEntry(
			self.right_panel, placeholder_text='Monto ($)'
		)
		self.entry_mov_amount.pack(pady=10)

		self.btn_mov = ctk.CTkButton(
			self.right_panel, text='Guardar Movimiento', command=self.save_movement
		)
		self.btn_mov.pack(pady=20)

		self.lbl_mov_msg = ctk.CTkLabel(self.right_panel, text='')
		self.lbl_mov_msg.pack(pady=5)

		self.active_session = None

		# Cargamos los datos con un ligero retraso para una apertura fluida
		self.after(100, self.refresh_view)

	def refresh_view(self):
		# 1. Manejo seguro del usuario (Diccionario u Objeto)
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)
		user_id = (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

		self.active_session = self.controller.get_active_session(tenant_id, user_id)

		if self.active_session:
			# 2. Acceso a datos de la sesión como diccionario
			session_id = self.active_session.get('id')
			fondo = float(self.active_session.get('opening_balance', 0.0))

			ventas, ingresos, gastos = self.controller.get_session_summary(session_id)
			total_esperado = fondo + ventas + ingresos - gastos

			resumen_texto = (
				f'Fondo Inicial : ${fondo:.2f}\n'
				f'+ Ventas      : ${ventas:.2f}\n'
				f'+ Otros Ingr. : ${ingresos:.2f}\n'
				f'- Gastos      : ${gastos:.2f}\n'
				f'------------------------\n'
				f'TOTAL EN CAJA : ${total_esperado:.2f}'
			)

			self.lbl_status.configure(
				text='🟢 CAJA ABIERTA', text_color='#00cc66', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(text=resumen_texto)
			self.entry_amount.configure(
				placeholder_text='¿Cuánto dinero cuentas en físico?'
			)
			self.btn_action.configure(
				text='CERRAR CAJA', fg_color='#d9534f', hover_color='#c9302c'
			)

			# Habilitar panel derecho de forma segura
			for widget in self.right_panel.winfo_children():
				if isinstance(widget, (ctk.CTkEntry, ctk.CTkButton, ctk.CTkComboBox)):
					widget.configure(state='normal')
		else:
			self.lbl_status.configure(
				text='🔴 CAJA CERRADA', text_color='#ffaa00', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(
				text='\nDebes abrirla para poder vender\no registrar movimientos.\n'
			)
			self.entry_amount.configure(placeholder_text='Fondo inicial ($)')
			self.btn_action.configure(
				text='ABRIR CAJA', fg_color='#5cb85c', hover_color='#4cae4c'
			)

			# Deshabilitar panel derecho
			for widget in self.right_panel.winfo_children():
				if isinstance(widget, (ctk.CTkEntry, ctk.CTkButton, ctk.CTkComboBox)):
					widget.configure(state='disabled')

		self.entry_amount.delete(0, 'end')

	def handle_action(self):
		amount_str = self.entry_amount.get().strip().replace(',', '.')

		try:
			amount = float(amount_str)
		except ValueError:
			self.lbl_msg.configure(
				text='Ingresa un monto numérico válido.', text_color='#ff3333'
			)
			return

		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)
		user_id = (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

		if self.active_session:
			success, msg = self.controller.close_session(
				self.active_session.get('id'), amount
			)
		else:
			success, msg = self.controller.open_session(tenant_id, user_id, amount)

		if success:
			self.lbl_msg.configure(text=msg, text_color='#00cc66')
			self.refresh_view()
		else:
			self.lbl_msg.configure(text=msg, text_color='#ff3333')

	def save_movement(self):
		desc = self.entry_mov_desc.get().strip()
		amount_str = self.entry_mov_amount.get().strip().replace(',', '.')
		mov_type = self.combo_mov_type.get()

		try:
			amount = float(amount_str)
			if amount <= 0:
				raise ValueError
		except ValueError:
			self.lbl_mov_msg.configure(
				text='Monto inválido. Debe ser mayor a 0.', text_color='#ff3333'
			)
			return

		if not desc:
			self.lbl_mov_msg.configure(
				text='La descripción es obligatoria.', text_color='#ff3333'
			)
			return

		success, msg = self.controller.add_manual_movement(
			self.active_session.get('id'), mov_type, amount_str, desc
		)

		if success:
			self.lbl_mov_msg.configure(text=msg, text_color='#00cc66')
			self.entry_mov_desc.delete(0, 'end')
			self.entry_mov_amount.delete(0, 'end')
			self.refresh_view()
		else:
			self.lbl_mov_msg.configure(text=msg, text_color='#ff3333')
