import threading
from decimal import Decimal, InvalidOperation

import customtkinter as ctk

from controllers.cash_controller import CashController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV,
	FONT_NAV_BOLD,
	FONT_SMALL,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)


class CashView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = CashController(ctx.db_engine)
		self.active_session = None
		self._mov_type = 'gasto'
		self._poll_timer = None

		self.grid_columnconfigure(0, weight=2)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)

		self._build_left_panel()
		self._build_right_panel()

		self.bind('<Destroy>', self._on_destroy_cash)
		self.after(50, lambda: self._select_mov_type('gasto'))
		self.after(100, self.refresh_view)

	def _on_destroy_cash(self, event=None):
		if hasattr(self, '_poll_timer') and self._poll_timer:
			self.after_cancel(self._poll_timer)
			self._poll_timer = None

	def _build_left_panel(self):
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, padx=(16, 8), pady=16, sticky='nsew')
		self.left_panel.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self.left_panel,
			text='Control de Caja',
			font=('Arial', 20, 'bold'),
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(24, 4), padx=24, sticky='ew')

		self.lbl_status = ctk.CTkLabel(
			self.left_panel, text='', font=('Arial', 16, 'bold')
		)
		self.lbl_status.grid(row=1, column=0, pady=(0, 2), padx=24)

		self.lbl_session_info = ctk.CTkLabel(
			self.left_panel, text='', font=FONT_SMALL, text_color=TEXT_MUTED
		)
		self.lbl_session_info.grid(row=2, column=0, pady=(0, 12), padx=24)

		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).grid(
			row=3, column=0, sticky='ew', padx=24, pady=(0, 12)
		)

		self.frame_totals = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		self.frame_totals.grid(row=4, column=0, sticky='ew', padx=24, pady=(0, 4))
		self.frame_totals.grid_columnconfigure(0, weight=1)

		self._lbl_totals = {}
		rows_data = [
			('apertura', 'Fondo de apertura:', TEXT_SECONDARY),
			('ingresos', 'Ingresos manuales (+):', GREEN_TEXT),
			('gastos', 'Retiros / Gastos (-):', RED_TEXT),
		]
		for i, (key, label, color) in enumerate(rows_data):
			ctk.CTkLabel(
				self.frame_totals,
				text=label,
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				anchor='w',
			).grid(row=i, column=0, sticky='w', pady=4)
			lbl_val = ctk.CTkLabel(
				self.frame_totals,
				text='$0.00',
				font=FONT_BODY_BOLD,
				text_color=color,
				anchor='e',
			)
			lbl_val.grid(row=i, column=1, sticky='e', pady=4)
			self._lbl_totals[key] = lbl_val

		self.lbl_blind_note = ctk.CTkLabel(
			self.left_panel,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			wraplength=220,
			justify='center',
		)
		self.lbl_blind_note.grid(row=5, column=0, padx=24, pady=(8, 4))

		self.frame_presets = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		self.frame_presets.grid(row=6, column=0, sticky='ew', padx=24, pady=(0, 4))

		ctk.CTkLabel(
			self.frame_presets,
			text='FONDO INICIAL RÁPIDO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(0, 4))

		presets_row = ctk.CTkFrame(self.frame_presets, fg_color='transparent')
		presets_row.pack(fill='x')
		for amount in [0, 500, 1000, 2000, 5000]:
			ctk.CTkButton(
				presets_row,
				text='$0' if amount == 0 else f'${amount:,}',
				width=56,
				height=30,
				font=FONT_SMALL,
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
				corner_radius=6,
				command=lambda a=amount: self._set_preset_amount(a),
			).pack(side='left', padx=(0, 4))

		self.entry_amount = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Fondo inicial ($)',
			font=('Arial', 16),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=44,
		)
		self.entry_amount.grid(row=7, column=0, pady=(0, 10), padx=24, sticky='ew')
		self.entry_amount.bind('<Return>', lambda e: self.handle_action())

		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).grid(
			row=8, column=0, sticky='ew', padx=24, pady=(0, 12)
		)

		self.btn_action = ctk.CTkButton(
			self.left_panel,
			text='',
			font=FONT_HEADING,
			height=48,
			corner_radius=8,
			cursor='hand2',
			command=self.handle_action,
		)
		self.btn_action.grid(row=9, column=0, pady=(0, 24), padx=24, sticky='ew')

	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, padx=(8, 16), pady=16, sticky='nsew')
		self.right_panel.grid_columnconfigure(0, weight=1)
		self.right_panel.grid_rowconfigure(2, weight=1)

		form_frame = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		form_frame.grid(row=0, column=0, sticky='ew', padx=24, pady=(24, 12))
		form_frame.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			form_frame,
			text='Registrar Gasto / Ingreso',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w', pady=(0, 2))

		ctk.CTkLabel(
			form_frame,
			text='Registra movimientos manuales de efectivo durante el turno.',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, sticky='w', pady=(0, 10))

		type_row = ctk.CTkFrame(form_frame, fg_color='transparent')
		type_row.grid(row=3, column=0, sticky='ew', pady=(0, 10))
		type_row.grid_columnconfigure((0, 1), weight=1)

		self.btn_tipo_gasto = ctk.CTkButton(
			type_row,
			text='Gasto / Retiro',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=40,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			cursor='hand2',
			command=lambda: self._select_mov_type('gasto'),
		)
		self.btn_tipo_gasto.grid(row=0, column=0, sticky='ew', padx=(0, 4))

		self.btn_tipo_ingreso = ctk.CTkButton(
			type_row,
			text='Ingreso de Efectivo',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=40,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			cursor='hand2',
			command=lambda: self._select_mov_type('ingreso'),
		)
		self.btn_tipo_ingreso.grid(row=0, column=1, sticky='ew')

		self.entry_mov_desc = ctk.CTkEntry(
			form_frame,
			placeholder_text='Descripción  (Ej: Pago a proveedor, Cambio de caja)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=FONT_BODY,
		)
		self.entry_mov_desc.grid(row=4, column=0, sticky='ew', pady=(0, 8))
		self.entry_mov_desc.bind('<Return>', lambda e: self.entry_mov_amount.focus())

		self.entry_mov_amount = ctk.CTkEntry(
			form_frame,
			placeholder_text='Monto ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=FONT_BODY,
		)
		self.entry_mov_amount.grid(row=5, column=0, sticky='ew', pady=(0, 10))
		self.entry_mov_amount.bind('<Return>', lambda e: self.save_movement())

		self.btn_mov = ctk.CTkButton(
			form_frame,
			text='Guardar Movimiento',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=44,
			corner_radius=8,
			font=FONT_NAV_BOLD,
			cursor='hand2',
			command=self.save_movement,
		)
		self.btn_mov.grid(row=6, column=0, sticky='ew')

		ctk.CTkFrame(self.right_panel, height=1, fg_color=BORDER).grid(
			row=1, column=0, sticky='ew', padx=24, pady=(0, 0)
		)

		history_frame = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		history_frame.grid(row=2, column=0, sticky='nsew', padx=24, pady=(0, 24))
		history_frame.grid_columnconfigure(0, weight=1)
		history_frame.grid_rowconfigure(1, weight=1)

		ctk.CTkLabel(
			history_frame,
			text='Historial del Turno',
			font=FONT_NAV_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w', pady=(12, 6))

		self.history_scroll = ctk.CTkScrollableFrame(
			history_frame,
			fg_color=SURFACE1,
			corner_radius=8,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		self.history_scroll.grid(row=1, column=0, sticky='nsew')
		self.history_scroll.grid_columnconfigure(0, weight=1)

	def refresh_view(self):
		if not self.winfo_exists():
			return

		if hasattr(self, '_poll_timer') and self._poll_timer:
			self.after_cancel(self._poll_timer)

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id
		self.active_session = self.controller.get_active_session(tenant_id, user_id)

		if self.active_session:
			self._show_open_state()
			self._poll_timer = self.after(15000, self.refresh_view)
		else:
			self._show_closed_state()

	def _show_open_state(self):
		sess = self.active_session
		opening = float(sess.get('opening_balance', 0.0))
		opening_time = sess.get('opening_time')
		session_id = sess.get('id')
		tenant_id = self.ctx.tenant_id

		hora_str = opening_time.strftime('%H:%M') if opening_time else '--:--'

		self.lbl_status.configure(text='CAJA ABIERTA', text_color=GREEN_TEXT)
		self.lbl_session_info.configure(
			text=f'Turno #{session_id}   -   Abierta a las {hora_str}'
		)

		_, ingresos, gastos, _digital = self.controller.get_session_summary(
			tenant_id, session_id
		)
		self._lbl_totals['apertura'].configure(text=f'${opening:,.2f}')
		self._lbl_totals['ingresos'].configure(text=f'${float(ingresos):,.2f}')
		self._lbl_totals['gastos'].configure(text=f'${float(gastos):,.2f}')

		self.lbl_blind_note.configure(
			text='Las ventas del sistema están ocultas (arqueo ciego).\n'
			'Al cerrar, contá tus billetes y declará el total físico.'
		)

		self.frame_totals.grid()
		self.lbl_blind_note.grid()
		self.frame_presets.grid_remove()
		self.entry_amount.grid_remove()

		self.btn_action.configure(
			text='Cerrar Turno - Contar Caja',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
		)

		self._set_form_state('normal')
		self._refresh_history(tenant_id, session_id)

	def _show_closed_state(self):
		self.lbl_status.configure(text='CAJA CERRADA', text_color=ORANGE_TEXT)
		self.lbl_session_info.configure(text='Abrí la caja para empezar a operar.')
		self.lbl_blind_note.configure(text='')

		self.frame_totals.grid_remove()
		self.frame_presets.grid()
		self.entry_amount.grid()

		self.btn_action.configure(
			text='ABRIR CAJA',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
		)

		self._set_form_state('disabled')
		self._clear_history()

	def _refresh_history(self, tenant_id, session_id):
		self._clear_history()
		movements = self.controller.get_movements_list(tenant_id, session_id)

		if not movements:
			ctk.CTkLabel(
				self.history_scroll,
				text='No hay movimientos registrados en este turno.',
				font=FONT_BODY,
				text_color=TEXT_MUTED,
			).pack(pady=24)
			return

		for mov in movements:
			self._build_movement_row(mov)

	def _clear_history(self):
		for widget in self.history_scroll.winfo_children():
			widget.destroy()

	def _build_movement_row(self, mov):
		mov_type = mov['type']
		is_gasto = mov_type == 'gasto'
		amount_color = RED_TEXT if is_gasto else GREEN_TEXT
		accent_color = RED if is_gasto else GREEN
		prefix = '-' if is_gasto else '+'
		_type_labels = {
			'venta': 'Venta Efectivo',
			'venta_digital': 'Venta Digital',
			'ingreso': 'Ingreso Manual',
			'gasto': 'Retiro / Gasto',
		}
		type_label = _type_labels.get(mov_type, 'Movimiento')

		row = ctk.CTkFrame(
			self.history_scroll,
			fg_color=SURFACE2,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		row.pack(fill='x', pady=(0, 5), padx=2)
		row.grid_columnconfigure(1, weight=1)

		ctk.CTkFrame(row, width=4, fg_color=accent_color, corner_radius=0).grid(
			row=0, column=0, rowspan=2, sticky='ns'
		)

		ctk.CTkLabel(
			row,
			text=type_label,
			font=FONT_LABEL_BOLD,
			text_color=amount_color,
			anchor='w',
		).grid(row=0, column=1, sticky='w', padx=(10, 4), pady=(6, 0))

		ctk.CTkLabel(
			row,
			text=mov['description'],
			font=FONT_BODY,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=1, column=1, sticky='w', padx=(10, 4), pady=(0, 6))

		ctk.CTkLabel(
			row,
			text=f'{prefix}${mov["amount"]:,.2f}',
			font=FONT_NAV_BOLD,
			text_color=amount_color,
			anchor='e',
		).grid(row=0, column=2, padx=(4, 12), pady=(6, 0), sticky='e')

		ctk.CTkLabel(
			row, text=mov['time'], font=FONT_LABEL, text_color=TEXT_MUTED, anchor='e'
		).grid(row=1, column=2, padx=(4, 12), pady=(0, 6), sticky='e')

	def _set_preset_amount(self, amount):
		self.entry_amount.delete(0, 'end')
		self.entry_amount.insert(0, str(amount))
		self.entry_amount.focus()

	def _set_form_state(self, state):
		for w in [
			self.btn_tipo_gasto,
			self.btn_tipo_ingreso,
			self.entry_mov_desc,
			self.entry_mov_amount,
			self.btn_mov,
		]:
			try:
				w.configure(state=state)
			except Exception:
				pass

	def handle_action(self):
		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		if self.active_session:
			self.show_blind_close_popup()
		else:
			self.clear_field_errors(self.entry_amount)
			amount_str = self.entry_amount.get().strip().replace(',', '.')
			if not amount_str:
				self.mark_field_error(self.entry_amount)
				self.show_warning('Ingresá el monto de apertura (puede ser 0).')
				return
			try:
				from decimal import Decimal as _D

				_apertura = _D(amount_str)
				if _apertura < 0:
					self.mark_field_error(self.entry_amount)
					self.show_error('El monto de apertura no puede ser negativo.')
					return
			except Exception:
				self.mark_field_error(self.entry_amount)
				self.show_error('Ingresá un monto válido.')
				return

			original = self.btn_action.cget('text')
			self.set_loading(self.btn_action, True)

			def _run_open():
				try:
					ok, result_msg = self.controller.open_session(
						tenant_id, user_id, amount_str
					)
				except Exception as exc:
					ok, result_msg = False, str(exc)
				if self.winfo_exists():
					self.after(0, lambda: _on_open_done(ok, result_msg))

			def _on_open_done(ok, result_msg):
				self.set_loading(self.btn_action, False, original)
				if ok:
					self.show_success(result_msg)
					self.entry_amount.delete(0, 'end')
					self.clear_field_errors(self.entry_amount)
					self.refresh_view()
				else:
					self.show_error(result_msg)

			threading.Thread(target=_run_open, daemon=True).start()

	def _select_mov_type(self, mov_type: str):
		self._mov_type = mov_type
		if mov_type == 'gasto':
			self.btn_tipo_gasto.configure(
				fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT, border_color=RED
			)
			self.btn_tipo_ingreso.configure(
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_color=BORDER,
			)
			self.entry_mov_amount.configure(border_color=RED)
			self.entry_mov_desc.configure(border_color=RED)
		else:
			self.btn_tipo_ingreso.configure(
				fg_color=GREEN_DIM,
				hover_color=GREEN,
				text_color=GREEN_TEXT,
				border_color=GREEN,
			)
			self.btn_tipo_gasto.configure(
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_color=BORDER,
			)
			self.entry_mov_amount.configure(border_color=GREEN)
			self.entry_mov_desc.configure(border_color=GREEN)

	def save_movement(self):
		btn = getattr(self, 'btn_mov', None)
		if btn:
			btn.configure(state='disabled')
		try:
			self.clear_field_errors(self.entry_mov_desc, self.entry_mov_amount)

			desc = self.entry_mov_desc.get().strip()
			amount_str = self.entry_mov_amount.get().strip().replace(',', '.')
			mov_type = self._mov_type
			tenant_id = self.ctx.tenant_id

			if not desc:
				self.mark_field_error(self.entry_mov_desc)
				return

			if not amount_str:
				self.mark_field_error(self.entry_mov_amount)
				return

			try:
				amount_val = Decimal(amount_str)
				if amount_val <= 0:
					self.mark_field_error(self.entry_mov_amount)
					self.show_error('El monto debe ser mayor a cero.')
					return
			except (InvalidOperation, Exception):
				self.mark_field_error(self.entry_mov_amount)
				self.show_error('Monto inválido.')
				return

			if not self.active_session:
				self.show_error('No hay caja abierta. Abrí la caja primero.')
				return

			session_id = self.active_session.get('id')
			success, msg = self.controller.add_manual_movement(
				tenant_id, session_id, mov_type, amount_str, desc
			)

			if success:
				self.entry_mov_desc.delete(0, 'end')
				self.entry_mov_amount.delete(0, 'end')
				self.clear_field_errors(self.entry_mov_desc, self.entry_mov_amount)
				self.entry_mov_desc.focus()
				self._show_open_state()
			else:
				self.show_error(msg)
		finally:
			if btn:
				try:
					btn.configure(state='normal')
				except Exception:
					pass

	def show_blind_close_popup(self):
		if hasattr(self, 'popup') and self.popup is not None:
			try:
				if self.popup.winfo_exists():
					self.popup.focus()
					return
			except Exception:
				pass
		self.popup = ctk.CTkToplevel(self)
		self.popup.title('Arqueo de Caja - Cierre de Turno')

		screen_height = self.winfo_screenheight()
		max_height = min(750, screen_height - 100)
		self.popup.geometry(f'420x{max_height}')

		self.popup.configure(fg_color=SURFACE1)
		self.popup.attributes('-topmost', True)
		self.popup.grab_set()
		self.popup.protocol('WM_DELETE_WINDOW', self._cancel_blind_close)

		ctk.CTkLabel(
			self.popup,
			text='Contá tus billetes',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(22, 4))

		ctk.CTkLabel(
			self.popup,
			text='Ingresá la cantidad de cada billete y moneda que tenés en caja.\n'
			'El sistema comparará con el total esperado al confirmar.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			wraplength=360,
			justify='center',
		).pack(pady=(0, 16))

		self.scroll_container = ctk.CTkScrollableFrame(
			self.popup, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		self.scroll_container.pack(fill='both', expand=True, padx=10, pady=(0, 10))

		bill_denominations = [10000, 5000, 2000, 1000, 500, 200, 100, 50, 20, 10]
		coin_denominations = [5, 2, 1]
		self.bill_entries = {}

		grid_frame = ctk.CTkFrame(self.scroll_container, fg_color='transparent')
		grid_frame.pack(fill='x', padx=10)
		grid_frame.grid_columnconfigure(0, weight=1)

		row_idx = 0
		ctk.CTkLabel(
			grid_frame, text='BILLETES', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
		).grid(row=row_idx, column=0, columnspan=2, pady=(0, 5), sticky='w')
		row_idx += 1

		for denom in bill_denominations:
			ctk.CTkLabel(
				grid_frame,
				text=f'Billetes de ${denom:,}:',
				font=FONT_NAV,
				text_color=TEXT_SECONDARY,
				anchor='e',
			).grid(row=row_idx, column=0, sticky='e', pady=4, padx=10)

			entry = ctk.CTkEntry(
				grid_frame,
				width=90,
				height=36,
				font=FONT_HEADING,
				justify='center',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
			)
			entry.grid(row=row_idx, column=1, pady=4)
			entry.insert(0, '0')
			entry.bind('<KeyRelease>', self._calculate_realtime_total)
			entry.bind(
				'<FocusIn>',
				lambda e: e.widget.after(
					10, lambda w=e.widget: w.select_range(0, 'end')
				),
			)
			self.bill_entries[denom] = entry
			row_idx += 1

		ctk.CTkLabel(
			grid_frame, text='MONEDAS', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
		).grid(row=row_idx, column=0, columnspan=2, pady=(15, 5), sticky='w')
		row_idx += 1

		for denom in coin_denominations:
			ctk.CTkLabel(
				grid_frame,
				text=f'Monedas de ${denom:,}:',
				font=FONT_NAV,
				text_color=TEXT_SECONDARY,
				anchor='e',
			).grid(row=row_idx, column=0, sticky='e', pady=4, padx=10)

			entry = ctk.CTkEntry(
				grid_frame,
				width=90,
				height=36,
				font=FONT_HEADING,
				justify='center',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
			)
			entry.grid(row=row_idx, column=1, pady=4)
			entry.insert(0, '0')
			entry.bind('<KeyRelease>', self._calculate_realtime_total)
			entry.bind(
				'<FocusIn>',
				lambda e: e.widget.after(
					10, lambda w=e.widget: w.select_range(0, 'end')
				),
			)
			self.bill_entries[denom] = entry
			row_idx += 1

		ctk.CTkLabel(
			grid_frame,
			text='OTROS / AJUSTES',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=row_idx, column=0, columnspan=2, pady=(15, 5), sticky='w')
		row_idx += 1

		ctk.CTkLabel(
			grid_frame,
			text='Ajuste manual ($):',
			font=FONT_NAV,
			text_color=TEXT_SECONDARY,
			anchor='e',
		).grid(row=row_idx, column=0, sticky='e', pady=4, padx=10)

		self.entry_otros = ctk.CTkEntry(
			grid_frame,
			width=90,
			height=36,
			font=FONT_HEADING,
			justify='center',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_otros.grid(row=row_idx, column=1, pady=4)
		self.entry_otros.insert(0, '0')
		self.entry_otros.bind('<KeyRelease>', self._calculate_realtime_total)
		self.entry_otros.bind(
			'<FocusIn>',
			lambda e: e.widget.after(10, lambda w=e.widget: w.select_range(0, 'end')),
		)

		all_denoms = bill_denominations + coin_denominations
		_ordered_entries = [self.bill_entries[d] for d in all_denoms] + [
			self.entry_otros
		]

		for _idx, _e in enumerate(_ordered_entries[:-1]):
			_nxt = _ordered_entries[_idx + 1]
			_e.bind(
				'<Return>',
				lambda evt, n=_nxt: (
					n.focus(),
					n.after(10, lambda target=n: target.select_range(0, 'end')),
				),
			)

		_ordered_entries[-1].bind('<Return>', lambda evt: self._confirm_blind_close())

		self.lbl_popup_total = ctk.CTkLabel(
			self.popup,
			text='Total Declarado: $0.00',
			font=('Arial', 22, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self.lbl_popup_total.pack(pady=10)

		self.current_counted_total = '0.00'

		btn_frame = ctk.CTkFrame(self.popup, fg_color='transparent')
		btn_frame.pack(fill='x', padx=30, pady=(0, 16))

		self._btn_blind_confirm = ctk.CTkButton(
			btn_frame,
			text='CONFIRMAR Y CERRAR TURNO',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=50,
			font=FONT_HEADING,
			corner_radius=8,
			command=self._confirm_blind_close,
		)
		self._btn_blind_confirm.pack(pady=(0, 8), fill='x')

		ctk.CTkButton(
			btn_frame,
			text='Cancelar - Seguir operando',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=36,
			corner_radius=8,
			command=self._cancel_blind_close,
		).pack(fill='x')

		self.after(100, lambda: _ordered_entries[0].focus())

	def _cancel_blind_close(self):
		self.popup.destroy()

	def _calculate_realtime_total(self, event=None):
		total = Decimal('0.0')
		for denom, entry in self.bill_entries.items():
			qty = entry.get().strip()
			if qty.strip().isdigit():
				total += Decimal(str(denom)) * Decimal(qty.strip())

		otros = self.entry_otros.get().strip().replace(',', '.')
		if otros:
			try:
				val_otros = Decimal(otros)
				total += val_otros
			except (InvalidOperation, ValueError):
				pass

		self.lbl_popup_total.configure(text=f'Total Declarado: ${total:,.2f}')
		self.current_counted_total = str(total)

	def _confirm_blind_close(self, *args):
		if not self.active_session:
			self.show_error('La sesión de caja ya fue cerrada.')
			return
		if hasattr(self, '_btn_blind_confirm'):
			self._btn_blind_confirm.configure(state='disabled')
		try:
			total = Decimal(self.current_counted_total)
			if total == Decimal('0'):
				if not self.confirm(
					'⚠ Estás declarando $0.00 en caja.\n\n'
					'Esto generará una diferencia negativa igual al total de ventas registradas.\n\n'
					'¿Estás seguro de que querés continuar con monto declarado en cero?',
					title='Advertencia: monto declarado en cero',
				):
					return
			if not self.confirm(
				f'Vas a declarar ${total:,.2f} en caja.\n\n'
				'Esta acción cierra el turno y no se puede deshacer.\n'
				'El sistema calculará la diferencia contra las ventas registradas.',
				title='Confirmar cierre de turno',
			):
				return

			tenant_id = self.ctx.tenant_id
			session_id = self.active_session.get('id')
			success, msg = self.controller.close_session(
				tenant_id, session_id, self.current_counted_total
			)

			if success:
				self.popup.destroy()
				self.show_success(msg, title='Turno Finalizado')
				self.refresh_view()
			else:
				self.show_error(msg)
		finally:
			try:
				if (
					hasattr(self, '_btn_blind_confirm')
					and self._btn_blind_confirm.winfo_exists()
				):
					self._btn_blind_confirm.configure(state='normal')
			except Exception:
				pass
