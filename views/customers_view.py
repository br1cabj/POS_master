from tkinter import ttk

import customtkinter as ctk

from controllers.customer_controller import CustomerController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_LABEL,
	FONT_NAV,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)


class CustomersView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = CustomerController(ctx.db_engine)

		self._search_timer = None
		self.customer_map = {}
		self._all_customers = []
		self._editing_customer_id = None
		self._only_debtors = False

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		self._build_left_panel()
		self._build_right_panel()

		self.after(100, self.load_data)

	# =========================================================
	# PANEL IZQUIERDO: FORMULARIOS
	# =========================================================
	def _build_left_panel(self):
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		# ── Sección: Nuevo / Editar Cliente ──
		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel,
			text='Nuevo Cliente',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		)
		self.lbl_form_title.pack(pady=(22, 16))

		ctk.CTkLabel(
			self.left_panel,
			text='NOMBRE COMPLETO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 2))

		self.entry_name = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Ej: Juan Pérez',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_name.pack(pady=(0, 6), padx=20, fill='x')
		self.entry_name.bind(
			'<KeyRelease>',
			lambda e: self.entry_name.configure(border_color=BORDER_ACTIVE),
		)

		ctk.CTkLabel(
			self.left_panel,
			text='TELÉFONO (OPCIONAL)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 2))

		self.entry_phone = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Ej: 3512345678',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_phone.pack(pady=(0, 10), padx=20, fill='x')

		import utils.settings_manager as _sm_c
		_name_a = _sm_c.get('price_list_a_name', 'Minorista')
		_name_b = _sm_c.get('price_list_b_name', 'Mayorista')

		ctk.CTkLabel(
			self.left_panel,
			text='LISTA DE PRECIOS',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 4))

		self._price_list_var = ctk.StringVar(value='A')
		price_list_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		price_list_row.pack(padx=20, fill='x', pady=(0, 10))

		self._btn_list_a = ctk.CTkButton(
			price_list_row,
			text=f'A · {_name_a}',
			height=32,
			font=('Arial', 11, 'bold'),
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=6,
			command=lambda: self._select_price_list('A'),
		)
		self._btn_list_a.pack(side='left', expand=True, fill='x', padx=(0, 4))

		self._btn_list_b = ctk.CTkButton(
			price_list_row,
			text=f'B · {_name_b}',
			height=32,
			font=('Arial', 11, 'bold'),
			fg_color='transparent',
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			command=lambda: self._select_price_list('B'),
		)
		self._btn_list_b.pack(side='left', expand=True, fill='x', padx=(4, 0))

		self.btn_add = ctk.CTkButton(
			self.left_panel,
			text='➕  Guardar Cliente',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			command=self.add_customer,
		)
		self.btn_add.pack(pady=(0, 20), padx=20, fill='x')

		self.btn_cancel_edit = ctk.CTkButton(
			self.left_panel,
			text='Cancelar Edición',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=38,
			corner_radius=8,
			command=self._cancel_edit,
		)
		# Oculto por defecto, se muestra solo al editar

		# Divisor
		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER, corner_radius=0).pack(
			fill='x', padx=14, pady=(0, 16)
		)

		# ── Sección: Cobrar Deuda ──
		ctk.CTkLabel(
			self.left_panel,
			text='Cobrar Deuda (Fiado)',
			font=('Arial', 15, 'bold'),
			text_color=ORANGE_TEXT,
		).pack(pady=(0, 12))

		ctk.CTkLabel(
			self.left_panel,
			text='CLIENTE',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w')

		self.combo_customers = ctk.CTkComboBox(
			self.left_panel,
			values=['Seleccionar...'],
			command=self.on_customer_select,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.combo_customers.pack(pady=(2, 8), padx=20, fill='x')

		self.lbl_debt_info = ctk.CTkLabel(
			self.left_panel,
			text='',
			font=('Arial', 11),
			text_color=ORANGE_TEXT,
			anchor='w',
		)
		self.lbl_debt_info.pack(padx=20, anchor='w', pady=(0, 4))

		self.entry_payment = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Monto que abona ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_payment.pack(pady=(0, 12), padx=20, fill='x')
		self.entry_payment.bind(
			'<FocusIn>', lambda e: self.entry_payment.select_range(0, 'end')
		)

		self.btn_pay = ctk.CTkButton(
			self.left_panel,
			text='💰  Registrar Abono',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=40,
			corner_radius=8,
			command=self.pay_debt,
		)
		self.btn_pay.pack(pady=(0, 20), padx=20, fill='x')

	# =========================================================
	# PANEL DERECHO: DIRECTORIO Y TABLA
	# =========================================================
	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(16, 4))

		ctk.CTkLabel(
			hdr,
			text='Directorio de Clientes y Cuentas',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		self.btn_toggle_filter = ctk.CTkButton(
			hdr,
			text='Solo deudores',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=28,
			width=120,
			corner_radius=6,
			cursor='hand2',
			command=self._toggle_debtor_filter,
		)
		self.btn_toggle_filter.pack(side='right')

		self.lbl_total_debt_header = ctk.CTkLabel(
			hdr,
			text='',
			font=('Arial', 10, 'bold'),
			text_color=ORANGE_TEXT,
		)
		self.lbl_total_debt_header.pack(side='right', padx=(0, 8))

		ctk.CTkLabel(
			self.right_panel,
			text='Hacé doble clic en un cliente para ver su Estado de Cuenta.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 6))

		# ── Buscador ──
		search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		search_row.pack(fill='x', padx=14, pady=(0, 6))

		self._search_var = ctk.StringVar()
		self._trace_search = self._search_var.trace_add('write', self._on_search_change)

		ctk.CTkEntry(
			search_row,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por nombre o teléfono...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		).pack(side='left', fill='x', expand=True)

		self.lbl_count = ctk.CTkLabel(
			search_row,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			width=100,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(8, 0))

		# ── Tabla ──
		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 14))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Nombre', 'Teléfono', 'Deuda Acumulada', 'Último Fiado')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		col_config = {
			'ID': ('center', 40),
			'Nombre': ('w', 190),
			'Teléfono': ('center', 90),
			'Deuda Acumulada': ('e', 110),
			'Último Fiado': ('center', 90),
		}
		for col in columns:
			self.tree.heading(col, text=col)
			anchor, width = col_config[col]
			self.tree.column(col, anchor=anchor, width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# Tags de colores para saldos
		self.tree.tag_configure('deudor', foreground=RED_TEXT)
		self.tree.tag_configure('a_favor', foreground=GREEN_TEXT)

		# Evento de doble clic (Abre el Modal de Estado de Cuenta)
		self.tree.bind('<Double-1>', self._open_customer_ledger_modal)

		# ── Estado Vacío (Empty State) ──
		self.lbl_empty_customers = ctk.CTkLabel(
			self.table_container,
			text='👤\nNo hay clientes registrados.\nAgregá el primero usando el panel izquierdo.',
			font=FONT_NAV,
			text_color=TEXT_MUTED,
			justify='center',
		)

		# ── Total deuda ──
		self.lbl_total_debt = ctk.CTkLabel(
			self.right_panel,
			text='',
			font=('Arial', 10, 'bold'),
			text_color=ORANGE_TEXT,
			anchor='e',
		)
		self.lbl_total_debt.pack(fill='x', padx=16, pady=(0, 2))

		# ── Botón Inferior ──
		btn_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btn_row.pack(fill='x', padx=14, pady=(0, 14))

		ctk.CTkButton(
			btn_row,
			text='💰  Cobrar Deuda',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self._select_for_payment,
		).pack(side='left', fill='x', expand=True, padx=(0, 5))

		ctk.CTkButton(
			btn_row,
			text='✏️  Editar Cliente',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self._edit_selected,
		).pack(side='left', fill='x', expand=True, padx=(5, 0))

	# =========================================================
	# LÓGICA Y FUNCIONES
	# =========================================================
	def _toggle_debtor_filter(self):
		self._only_debtors = not self._only_debtors
		if self._only_debtors:
			self.btn_toggle_filter.configure(
				fg_color=ACCENT_DIM, border_color=ACCENT, text_color=ACCENT_TEXT
			)
		else:
			self.btn_toggle_filter.configure(
				fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_MUTED
			)
		self._filter_tree()

	def _select_for_payment(self):
		"""Carga el cliente seleccionado en la tabla al combo de Cobro del panel izquierdo."""
		selected = self.tree.selection()
		if not selected:
			self.show_warning(
				'Seleccioná un cliente de la tabla primero.', 'Selección requerida'
			)
			return

		values = self.tree.item(selected[0], 'values')
		name = values[1] if len(values) > 1 else ''

		if name and name in self.customer_map:
			self.combo_customers.set(name)
			self.on_customer_select(name)
			self.entry_payment.focus_set()
		else:
			self.show_warning('Este cliente no tiene una cuenta de cobro registrada.', 'Sin cuenta')

	def _edit_selected(self):
		"""Prepara el formulario de la izquierda para editar un cliente existente."""
		selected = self.tree.selection()
		if not selected:
			self.show_warning(
				'Seleccioná un cliente de la tabla para editar.', 'Selección requerida'
			)
			return

		values = self.tree.item(selected[0], 'values')
		customer_id = str(values[0])

		customer_data = next(
			(c for c in self._all_customers if str(c['id']) == customer_id), None
		)
		if not customer_data:
			return

		self._editing_customer_id = customer_data['id']

		self.lbl_form_title.configure(text='Editar Cliente', text_color=ACCENT_TEXT)

		self.entry_name.delete(0, 'end')
		self.entry_name.insert(0, customer_data.get('name', ''))
		self.entry_name.configure(border_color=BORDER_ACTIVE)

		self.entry_phone.delete(0, 'end')
		self.entry_phone.insert(0, customer_data.get('phone', '') or '')

		self._select_price_list(customer_data.get('price_list', 'A'))

		self.btn_add.configure(text='💾  Actualizar Cliente')
		self.btn_add.pack(pady=(0, 8), padx=20, fill='x')
		self.btn_cancel_edit.pack(pady=(0, 20), padx=20, fill='x')

		self.entry_name.focus_set()

	def _select_price_list(self, key: str):
		self._price_list_var.set(key)
		if key == 'B':
			self._btn_list_a.configure(fg_color='transparent', border_color=BORDER, text_color=TEXT_MUTED)
			self._btn_list_b.configure(fg_color=ACCENT_DIM, border_color=ACCENT, text_color=ACCENT_TEXT)
		else:
			self._btn_list_a.configure(fg_color=ACCENT_DIM, border_color=ACCENT, text_color=ACCENT_TEXT)
			self._btn_list_b.configure(fg_color='transparent', border_color=BORDER, text_color=TEXT_MUTED)

	def _cancel_edit(self):
		"""Limpia el formulario de edición y regresa al modo de nuevo cliente."""
		self._editing_customer_id = None
		self.lbl_form_title.configure(text='Nuevo Cliente', text_color=TEXT_PRIMARY)
		self.entry_name.delete(0, 'end')
		self.entry_name.configure(border_color=BORDER_ACTIVE)
		self.entry_phone.delete(0, 'end')
		self._select_price_list('A')

		self.btn_cancel_edit.pack_forget()
		self.btn_add.configure(text='➕  Guardar Cliente')
		self.btn_add.pack(pady=(0, 20), padx=20, fill='x')

	def _open_customer_ledger_modal(self, event=None):
		"""Abre un modal con el Estado de Cuenta detallado del cliente seleccionado."""
		selected = self.tree.selection()
		if not selected:
			return

		values = self.tree.item(selected[0], 'values')
		customer_id = str(values[0])
		name = values[1]
		phone = values[2]

		# Extraemos el balance desde los datos originales en lugar de parsear el texto
		customer_data = next(
			(c for c in self._all_customers if str(c['id']) == customer_id), None
		)
		if customer_data:
			balance = float(customer_data.get('current_balance') or 0.0)
		else:
			balance = 0.0

		# Crear el Modal
		modal = ctk.CTkToplevel(self)
		modal.title(f'Estado de Cuenta - {name}')
		modal.geometry('750x640')
		modal.attributes('-topmost', True)
		modal.grab_set()
		modal.bind('<Escape>', lambda e: modal.destroy())

		# Cabecera
		header = ctk.CTkFrame(modal, fg_color=SURFACE2)
		header.pack(fill='x', padx=16, pady=16)

		ctk.CTkLabel(
			header, text=name, font=('Arial', 20, 'bold'), text_color=TEXT_PRIMARY
		).pack(side='left', padx=16, pady=12)

		color_saldo = RED_TEXT if balance > 0 else GREEN_TEXT
		texto_saldo = (
			f'DEUDA: ${balance:.2f}' if balance > 0 else f'A FAVOR: ${abs(balance):.2f}'
		)
		if balance == 0:
			color_saldo = TEXT_PRIMARY
			texto_saldo = 'SALDO: $0.00'

		ctk.CTkLabel(
			header, text=texto_saldo, font=('Arial', 20, 'bold'), text_color=color_saldo
		).pack(side='right', padx=16)

		# Tabla de Historial
		table_frame = ctk.CTkFrame(modal, fg_color='transparent')
		table_frame.pack(fill='both', expand=True, padx=16)

		scroll = ttk.Scrollbar(table_frame, orient='vertical')
		cols = ('Fecha', 'Concepto', 'Cargo (Compró)', 'Abono (Pagó)')
		tree_history = ttk.Treeview(
			table_frame, columns=cols, show='tree headings', yscrollcommand=scroll.set
		)
		scroll.configure(command=tree_history.yview)

		tree_history.column('#0', width=18, minwidth=18, stretch=False)
		tree_history.heading('Fecha', text='Fecha')
		tree_history.heading('Concepto', text='Concepto')
		tree_history.heading('Cargo (Compró)', text='Cargo (Deuda)')
		tree_history.heading('Abono (Pagó)', text='Abono (Pago)')

		tree_history.column('Fecha', width=120, anchor='center')
		tree_history.column('Concepto', width=270, anchor='w')
		tree_history.column('Cargo (Compró)', width=110, anchor='e')
		tree_history.column('Abono (Pagó)', width=110, anchor='e')

		tree_history.tag_configure('cargo', foreground=RED_TEXT)
		tree_history.tag_configure('abono', foreground=GREEN_TEXT)
		tree_history.tag_configure('item_row', foreground=TEXT_MUTED)

		scroll.pack(side='right', fill='y')
		tree_history.pack(side='left', fill='both', expand=True)

		# Cargar datos desde el controlador
		ledger = self.controller.get_customer_ledger(self.ctx.tenant_id, customer_id)
		for row in ledger:
			date_str = (
				row['date'].strftime('%d/%m/%Y %H:%M')
				if hasattr(row['date'], 'strftime')
				else str(row['date'])[:16]
			)
			if row['type'] == 'cargo':
				parent_id = tree_history.insert(
					'',
					'end',
					values=(date_str, row['concept'], f'${row["amount"]:.2f}', '-'),
					tags=('cargo',),
					open=True,
				)
				for item in row.get('items', []):
					qty = item['quantity']
					qty_str = f'{qty:.0f}' if qty == int(qty) else f'{qty:.2f}'
					tree_history.insert(
						parent_id,
						'end',
						values=(
							'',
							f'  ↳ {item["description"]}  x{qty_str} @ ${item["unit_price"]:.2f}',
							f'${item["subtotal"]:.2f}',
							'',
						),
						tags=('item_row',),
					)
			else:
				tree_history.insert(
					'',
					'end',
					values=(date_str, row['concept'], '-', f'${row["amount"]:.2f}'),
					tags=('abono',),
				)

		# ── Sección abono rápido ──
		pay_frame = ctk.CTkFrame(
			modal, fg_color=SURFACE2, corner_radius=8, border_width=1, border_color=BORDER
		)
		pay_frame.pack(fill='x', padx=16, pady=(8, 0))

		ctk.CTkLabel(
			pay_frame,
			text='Registrar abono:',
			font=('Arial', 11, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(side='left', padx=12, pady=8)

		entry_modal_payment = ctk.CTkEntry(
			pay_frame,
			placeholder_text='Monto ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=32,
			width=120,
		)
		entry_modal_payment.pack(side='left', padx=6, pady=8)

		def _do_modal_payment():
			amount_str = entry_modal_payment.get().strip().replace(',', '.')
			try:
				amount = float(amount_str)
				if amount <= 0:
					raise ValueError
			except ValueError:
				self.show_warning('Ingresá un monto válido mayor a cero.', 'Error')
				return
			if not self.confirm(
				f'¿Registrar abono de ${amount:.2f} para {name}?', 'Confirmar'
			):
				return
			success, msg = self.controller.pay_debt(
				self.ctx.tenant_id, self.ctx.user_id, customer_id, amount
			)
			if success:
				self.show_success(msg)
				modal.destroy()
				self.load_data()
			else:
				self.show_error(msg)

		ctk.CTkButton(
			pay_frame,
			text='💰 Abonar',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=32,
			corner_radius=8,
			command=_do_modal_payment,
		).pack(side='left', padx=6, pady=8)

		# Footer
		footer = ctk.CTkFrame(modal, fg_color='transparent')
		footer.pack(fill='x', padx=16, pady=16)

		btn_export = ctk.CTkButton(
			footer,
			text='📄 Exportar PDF',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_PRIMARY,
			border_width=1,
			border_color=BORDER,
			height=36,
			command=lambda: self._export_ledger(name, phone, balance, ledger),
		)
		btn_export.pack(side='left')

		ctk.CTkButton(
			footer,
			text='Cerrar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_PRIMARY,
			border_width=1,
			border_color=BORDER,
			height=36,
			command=modal.destroy,
		).pack(side='right')

	def _export_ledger(self, name, phone, balance, ledger):
		"""Llama al controlador de recibos para exportar el PDF."""
		from controllers.receipt_controller import ReceiptController

		rc = ReceiptController()
		success, msg = rc.export_account_statement(name, phone, balance, ledger)
		if success:
			self.show_success('PDF generado y abierto correctamente.')
		else:
			self.show_error(msg)

	def _on_search_change(self, *args):
		"""Aplica un retraso (debounce) a la búsqueda para no saturar la UI."""
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_tree)

	def destroy_custom(self):
		if self._search_timer:
			try:
				self.after_cancel(self._search_timer)
			except Exception:
				pass
		if getattr(self, '_trace_search', None):
			try:
				self._search_var.trace_remove('write', self._trace_search)
			except Exception:
				pass

	def _filter_tree(self, *args):
		"""Filtra la tabla en tiempo real, respetando el filtro de solo deudores."""
		q = self._search_var.get().lower()

		source = (
			[c for c in self._all_customers if float(c.get('current_balance') or 0) > 0]
			if self._only_debtors
			else self._all_customers
		)

		matches = (
			[
				c
				for c in source
				if q in (c.get('name') or '').lower()
				or q in (c.get('phone') or '').lower()
			]
			if q
			else source
		)

		for item in list(self.tree.get_children()):
			self.tree.delete(item)

		for c in matches:
			balance = float(c.get('current_balance') or 0.0)

			if balance > 0:
				saldo_str = f'${balance:.2f}'
				tags = ('deudor',)
			elif balance < 0:
				saldo_str = f'A favor: ${abs(balance):.2f}'
				tags = ('a_favor',)
			else:
				saldo_str = '$0.00'
				tags = ()

			last_mov = c.get('last_movement')
			last_mov_str = last_mov.strftime('%d/%m/%Y') if last_mov and hasattr(last_mov, 'strftime') else '-'

			self.tree.insert(
				'',
				'end',
				values=(c['id'], c['name'], c.get('phone') or '-', saldo_str, last_mov_str),
				tags=tags,
			)

		# Ocultar o mostrar empty state
		if hasattr(self, 'lbl_empty_customers'):
			if not matches:
				if self._only_debtors:
					empty_text = '✅\nNingún cliente tiene deuda pendiente.'
				elif q:
					empty_text = '🔍\nNo se encontraron clientes con ese criterio.'
				else:
					empty_text = '👤\nNo hay clientes registrados.\nAgregá el primero usando el panel izquierdo.'
				self.lbl_empty_customers.configure(text=empty_text)
				self.tree.pack_forget()
				self.tree_scroll.pack_forget()
				self.lbl_empty_customers.pack(expand=True)
			else:
				self.lbl_empty_customers.pack_forget()
				if not self.tree.winfo_ismapped():
					self.tree_scroll.pack(side='right', fill='y')
					self.tree.pack(side='left', fill='both', expand=True)

		total = len(self._all_customers)
		shown = len(matches)
		if hasattr(self, 'lbl_count'):
			self.lbl_count.configure(
				text=f'{shown} de {total}' if (q or self._only_debtors) else f'{total} clientes'
			)

		# Total deuda de todos los clientes (no solo los visibles)
		total_debt = sum(
			float(c.get('current_balance') or 0)
			for c in self._all_customers
			if float(c.get('current_balance') or 0) > 0
		)
		debt_text = f'Deuda total: ${total_debt:.2f}' if total_debt > 0 else ''
		if hasattr(self, 'lbl_total_debt'):
			self.lbl_total_debt.configure(text=debt_text)
		if hasattr(self, 'lbl_total_debt_header'):
			self.lbl_total_debt_header.configure(text=debt_text)

	def load_data(self):
		tenant_id = self.ctx.tenant_id
		customers = self.controller.get_customers(tenant_id)
		self._all_customers = customers

		self.customer_map = {
			c['name']: c for c in customers if c['name'] != 'Consumidor Final'
		}

		if self.customer_map:
			self.combo_customers.configure(values=list(self.customer_map.keys()))
			self.combo_customers.set('Seleccionar cliente...')
		else:
			self.combo_customers.configure(values=['Sin clientes'])
			self.combo_customers.set('No hay clientes registrados')

		self._filter_tree()

	def add_customer(self):
		import re as _re
		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()

		if not name:
			self.entry_name.configure(border_color=RED)
			self.entry_name.focus_set()
			self.show_warning('El nombre del cliente es obligatorio.', 'Faltan datos')
			return

		if phone and not _re.match(r'^[\d\s\+\-\(\)]{6,20}$', phone):
			self.entry_phone.configure(border_color=RED)
			self.entry_phone.focus_set()
			self.show_warning(
				'El teléfono solo puede contener números, espacios y los caracteres + - ( ).\nMínimo 6 y máximo 20 caracteres.',
				'Formato de teléfono inválido',
			)
			return

		tenant_id = self.ctx.tenant_id

		orig_text = self.btn_add.cget('text')
		self.btn_add.configure(state='disabled', text='⏳ Procesando...')
		self.update_idletasks()

		price_list = self._price_list_var.get()

		try:
			if self._editing_customer_id:
				success, msg = self.controller.update_customer(
					tenant_id, self._editing_customer_id, name, phone, price_list=price_list
				)
			else:
				success, msg = self.controller.add_customer(tenant_id, name, phone, price_list=price_list)
		finally:
			self.btn_add.configure(state='normal', text=orig_text)

		if success:
			self.show_success(msg)
			self._cancel_edit()
			self.load_data()
		else:
			self.entry_name.configure(border_color=RED)
			self.entry_name.focus_set()
			self.show_error(msg)

	def on_customer_select(self, name: str):
		"""Actualiza el label de deuda al seleccionar un cliente en el combo."""
		customer = self.customer_map.get(name)
		if not customer:
			self.lbl_debt_info.configure(text='')
			return
		balance = float(customer.get('current_balance') or 0.0)
		if balance > 0:
			self.lbl_debt_info.configure(
				text=f'Deuda actual: ${balance:.2f}', text_color=ORANGE_TEXT
			)
		elif balance < 0:
			self.lbl_debt_info.configure(
				text=f'A favor: ${abs(balance):.2f}', text_color=GREEN_TEXT
			)
		else:
			self.lbl_debt_info.configure(text='Sin deuda', text_color=TEXT_MUTED)

	def pay_debt(self):
		name = self.combo_customers.get()
		amount_str = self.entry_payment.get().strip().replace(',', '.')

		if name not in self.customer_map or not amount_str:
			self.show_warning(
				'Seleccioná un cliente y escribí el monto que abona.', 'Atención'
			)
			return

		customer = self.customer_map[name]

		try:
			amount = float(amount_str)
			if amount <= 0:
				raise ValueError
		except ValueError:
			self.show_warning(
				'Ingresá un número mayor a cero (Ej: 150.50).', 'Error de Monto'
			)
			return

		current_balance = float(customer.get('current_balance') or 0.0)
		if current_balance > 0 and amount > current_balance:
			favor = amount - current_balance
			if not self.confirm(
				f'El monto ${amount:.2f} supera la deuda actual de ${current_balance:.2f}.\n'
				f'El cliente quedará con un saldo a favor de ${favor:.2f}.\n\n'
				'¿Querés continuar de todas formas?',
				'Pago superior a la deuda',
			):
				return

		if not self.confirm(
			f'¿Registrar un abono de ${amount:.2f} para {customer["name"]}?',
			'Confirmar Abono',
		):
			return

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		orig_text = self.btn_pay.cget('text')
		self.btn_pay.configure(state='disabled', text='⏳ Procesando...')
		self.update_idletasks()

		try:
			success, msg = self.controller.pay_debt(
				tenant_id, user_id, customer['id'], amount
			)
		finally:
			self.btn_pay.configure(state='normal', text=orig_text)

		if success:
			self.show_success(msg)
			self.entry_payment.delete(0, 'end')
			self.combo_customers.set('Seleccionar cliente...')
			self.load_data()
		else:
			self.show_error(msg)
