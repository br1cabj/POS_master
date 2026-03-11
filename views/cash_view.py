import customtkinter as ctk


class CashView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.cash_controller import CashController

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
		self.refresh_view()

	def refresh_view(self):
		self.active_session = self.controller.get_active_session(
			self.current_user.tenant_id, self.current_user.id
		)

		if self.active_session:
			# Traer los totales calculados
			ventas, ingresos, gastos = self.controller.get_session_summary(
				self.active_session.id
			)
			fondo = self.active_session.opening_balance
			total_esperado = fondo + ventas + ingresos - gastos

			# Mostrar resumen detallado
			resumen_texto = (
				f'Fondo Inicial : ${fondo:.2f}\n'
				f'+ Ventas      : ${ventas:.2f}\n'
				f'+ Otros Ingr. : ${ingresos:.2f}\n'
				f'- Gastos      : ${gastos:.2f}\n'
				f'------------------------\n'
				f'TOTAL EN CAJA : ${total_esperado:.2f}'
			)

			self.lbl_status.configure(
				text='🟢 CAJA ABIERTA', text_color='green', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(text=resumen_texto)
			self.entry_amount.configure(
				placeholder_text='¿Cuánto dinero cuentas en físico?'
			)
			self.btn_action.configure(
				text='CERRAR CAJA', fg_color='red', hover_color='#aa0000'
			)

			# Habilitar panel derecho
			for widget in self.right_panel.winfo_children():
				widget.configure(state='normal')
		else:
			self.lbl_status.configure(
				text='🔴 CAJA CERRADA', text_color='orange', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(
				text='Debes abrirla para poder vender\no registrar movimientos.'
			)
			self.entry_amount.configure(placeholder_text='Fondo inicial ($)')
			self.btn_action.configure(
				text='ABRIR CAJA', fg_color='green', hover_color='#00aa00'
			)

			# Deshabilitar panel derecho
			for widget in self.right_panel.winfo_children():
				if isinstance(widget, (ctk.CTkEntry, ctk.CTkButton, ctk.CTkComboBox)):
					widget.configure(state='disabled')

		self.entry_amount.delete(0, 'end')

	def handle_action(self):
		amount_str = self.entry_amount.get().strip()
		if not amount_str.replace('.', '', 1).isdigit():
			self.lbl_msg.configure(text='Ingresa un número válido.', text_color='red')
			return

		amount = float(amount_str)

		if self.active_session:
			success, msg = self.controller.close_session(self.active_session.id, amount)
		else:
			success, msg = self.controller.open_session(
				self.current_user.tenant_id, self.current_user.id, amount
			)

		if success:
			self.lbl_msg.configure(text=msg, text_color='green')
			self.refresh_view()
		else:
			self.lbl_msg.configure(text=msg, text_color='red')

	def save_movement(self):
		desc = self.entry_mov_desc.get().strip()
		amount_str = self.entry_mov_amount.get().strip()
		mov_type = self.combo_mov_type.get()

		if not desc or not amount_str.replace('.', '', 1).isdigit():
			self.lbl_mov_msg.configure(text='Campos inválidos.', text_color='red')
			return

		success, msg = self.controller.add_manual_movement(
			self.active_session.id, mov_type, amount_str, desc
		)

		if success:
			self.lbl_mov_msg.configure(text=msg, text_color='green')
			self.entry_mov_desc.delete(0, 'end')
			self.entry_mov_amount.delete(0, 'end')
			self.refresh_view()
		else:
			self.lbl_mov_msg.configure(text=msg, text_color='red')
