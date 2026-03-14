from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

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
			self.left_panel, text='', font=('Courier', 14), justify='center'
		)
		self.lbl_summary.pack(pady=10)

		self.entry_amount = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Monto de Apertura ($)',
			font=('Arial', 16),
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

		# --- PANEL DERECHO: MOVIMIENTOS MANUALES ---
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

	# --- Métodos auxiliares DRY ---
	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def _get_user_id(self):
		return (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

	def refresh_view(self):
		tenant_id = self._get_tenant_id()
		user_id = self._get_user_id()

		self.active_session = self.controller.get_active_session(tenant_id, user_id)

		if self.active_session:
			fondo = float(self.active_session.get('opening_balance', 0.0))

			# ARQUEO CIEGO
			resumen_texto = (
				f'Fondo Inicial : ${fondo:.2f}\n\n'
				f'🔒 MODO ARQUEO CIEGO ACTIVO 🔒\n'
				f'El total de ventas es secreto.\n'
				f'Al cerrar turno, deberás contar tus\nbilletes y declarar lo que tienes.'
			)

			self.lbl_status.configure(
				text='🟢 CAJA ABIERTA', text_color='#00cc66', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(text=resumen_texto, text_color='#00aaff')

			# Ocultamos el campo de monto de apertura porque ya está abierta
			self.entry_amount.pack_forget()

			self.btn_action.configure(
				text='🔒 INICIAR CIERRE CIEGO',
				fg_color='#d9534f',
				hover_color='#c9302c',
			)
			self._set_panel_state(self.right_panel, 'normal')
		else:
			self.lbl_status.configure(
				text='🔴 CAJA CERRADA', text_color='#ffaa00', font=('Arial', 18, 'bold')
			)
			self.lbl_summary.configure(
				text='\nDebes abrirla para poder vender\no registrar movimientos.\n',
				text_color='white',
			)

			# Mostramos el campo para poner la plata inicial
			self.entry_amount.pack(pady=10, before=self.btn_action)
			self.entry_amount.configure(placeholder_text='Fondo inicial ($)')

			self.btn_action.configure(
				text='ABRIR CAJA', fg_color='#5cb85c', hover_color='#4cae4c'
			)
			self._set_panel_state(self.right_panel, 'disabled')

	def _set_panel_state(self, panel, state):
		for widget in panel.winfo_children():
			if hasattr(widget, 'configure') and not isinstance(widget, ctk.CTkLabel):
				try:
					widget.configure(state=state)
				except ValueError:
					pass

	def handle_action(self):
		tenant_id = self._get_tenant_id()
		user_id = self._get_user_id()

		if self.active_session:
			# Si la caja está abierta, abrimos la calculadora de billetes
			self.show_blind_close_popup()
		else:
			# Si está cerrada, procesamos la apertura normalmente
			amount_str = self.entry_amount.get().strip().replace(',', '.')
			if not amount_str:
				self.lbl_msg.configure(
					text='Ingresa un monto inicial.', text_color='#ff3333'
				)
				return

			success, msg = self.controller.open_session(tenant_id, user_id, amount_str)
			if success:
				self.lbl_msg.configure(text=msg, text_color='#00cc66')
				self.entry_amount.delete(0, 'end')
				self.refresh_view()
			else:
				self.lbl_msg.configure(text=msg, text_color='#ff3333')

	def save_movement(self):
		desc = self.entry_mov_desc.get().strip()
		amount_str = self.entry_mov_amount.get().strip().replace(',', '.')
		mov_type = self.combo_mov_type.get()
		tenant_id = self._get_tenant_id()

		if not desc or not amount_str:
			self.lbl_mov_msg.configure(
				text='Descripción y monto son obligatorios.', text_color='#ff3333'
			)
			return

		session_id = self.active_session.get('id')
		success, msg = self.controller.add_manual_movement(
			tenant_id, session_id, mov_type, amount_str, desc
		)

		if success:
			CTkMessagebox(title='Éxito', message=msg, icon='check')
			self.lbl_mov_msg.configure(text='', text_color='#00cc66')
			self.entry_mov_desc.delete(0, 'end')
			self.entry_mov_amount.delete(0, 'end')
		else:
			self.lbl_mov_msg.configure(text=msg, text_color='#ff3333')

	# ==========================================
	# 🧮 CALCULADORA DE BILLETES (BLIND CLOSE)
	# ==========================================
	def show_blind_close_popup(self):
		self.popup = ctk.CTkToplevel(self)
		self.popup.title('Arqueo de Caja')
		self.popup.geometry('350x650')
		self.popup.attributes('-topmost', True)
		self.popup.grab_set()

		ctk.CTkLabel(
			self.popup, text='Cuenta tus billetes', font=('Arial', 20, 'bold')
		).pack(pady=(20, 5))
		ctk.CTkLabel(
			self.popup,
			text='Ingresa la CANTIDAD de billetes que tienes:',
			text_color='gray',
		).pack(pady=(0, 15))

		# Denominaciones comunes de billetes (Modificable según país)
		denominations = [10000, 2000, 1000, 500, 200, 100, 50]
		self.bill_entries = {}

		grid_frame = ctk.CTkFrame(self.popup, fg_color='transparent')
		grid_frame.pack(fill='x', padx=30)

		for i, denom in enumerate(denominations):
			ctk.CTkLabel(
				grid_frame, text=f'Billetes de ${denom}:', font=('Arial', 14)
			).grid(row=i, column=0, sticky='e', pady=5, padx=10)
			entry = ctk.CTkEntry(grid_frame, width=80, justify='center')
			entry.grid(row=i, column=1, pady=5)
			entry.insert(0, '0')
			entry.bind('<KeyRelease>', self._calculate_realtime_total)
			self.bill_entries[denom] = entry

		# Campo extra para monedas o cambio chico
		ctk.CTkLabel(grid_frame, text='Monedas/Otros ($):', font=('Arial', 14)).grid(
			row=len(denominations), column=0, sticky='e', pady=15, padx=10
		)
		self.entry_otros = ctk.CTkEntry(grid_frame, width=80, justify='center')
		self.entry_otros.grid(row=len(denominations), column=1, pady=15)
		self.entry_otros.insert(0, '0')
		self.entry_otros.bind('<KeyRelease>', self._calculate_realtime_total)

		self.lbl_popup_total = ctk.CTkLabel(
			self.popup,
			text='Total Declarado: $0.00',
			font=('Arial', 22, 'bold'),
			text_color='#00aaff',
		)
		self.lbl_popup_total.pack(pady=20)

		self.current_counted_total = '0.00'

		ctk.CTkButton(
			self.popup,
			text='💾 CONFIRMAR Y CERRAR TURNO',
			fg_color='#d9534f',
			hover_color='#c9302c',
			height=45,
			font=('Arial', 14, 'bold'),
			command=self._confirm_blind_close,
		).pack(pady=10)

		ctk.CTkButton(
			self.popup, text='Cancelar', fg_color='#555555', command=self.popup.destroy
		).pack()

	def _calculate_realtime_total(self, event=None):
		total = Decimal('0.0')
		for denom, entry in self.bill_entries.items():
			qty = entry.get().strip()
			if qty.isdigit():
				total += Decimal(str(denom)) * Decimal(qty)

		otros = self.entry_otros.get().strip().replace(',', '.')
		if otros:
			try:
				total += Decimal(otros)
			except (InvalidOperation, ValueError):
				pass

		self.lbl_popup_total.configure(text=f'Total Declarado: ${total:.2f}')
		self.current_counted_total = str(total)

	def _confirm_blind_close(self):
		msg_box = CTkMessagebox(
			title='Advertencia',
			message=f'Estás declarando que tienes exactamente ${self.current_counted_total} en tu caja.\n¿Estás seguro? Esta acción no se puede deshacer y generará el Reporte Z.',
			icon='warning',
			option_1='Revisar de nuevo',
			option_2='Sí, Cerrar Caja',
		)

		if msg_box.get() == 'Sí, Cerrar Caja':
			tenant_id = self._get_tenant_id()
			session_id = self.active_session.get('id')

			success, msg = self.controller.close_session(
				tenant_id, session_id, self.current_counted_total
			)

			if success:
				self.popup.destroy()
				CTkMessagebox(
					title='Turno Finalizado', message=msg, icon='check', width=450
				)  # Mensaje más ancho para que quepa la ruta del PDF
				self.refresh_view()
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')
