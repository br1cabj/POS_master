from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.customer_controller import CustomerController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	apply_treeview_style,
)


class CustomersView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = CustomerController(ctx.db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		# ── Panel izquierdo: Acciones ────────────────────────────────────
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		# Sección: Nuevo cliente
		ctk.CTkLabel(
			self.left_panel,
			text='Nuevo Cliente',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(22, 16))

		ctk.CTkLabel(
			self.left_panel,
			text='NOMBRE COMPLETO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 2))
		self.entry_name = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Nombre Completo',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_name.pack(pady=(0, 6), padx=20, fill='x')

		ctk.CTkLabel(
			self.left_panel,
			text='TELÉFONO (OPCIONAL)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 2))
		self.entry_phone = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Teléfono (Opcional)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_phone.pack(pady=(0, 10), padx=20, fill='x')

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

		# Divisor
		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER, corner_radius=0).pack(
			fill='x', padx=14, pady=(0, 16)
		)

		# Sección: Cobrar deuda
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

		self.entry_payment = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Monto que abona ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_payment.pack(pady=(0, 12), padx=20, fill='x')

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

		# ── Panel derecho: Directorio ────────────────────────────────────
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

		ctk.CTkLabel(
			self.right_panel,
			text='El saldo indica la deuda acumulada total del cliente.',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 6))

		# ── Barra de búsqueda en tiempo real ──────────────────────────────
		search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		search_row.pack(fill='x', padx=14, pady=(0, 6))

		self._search_var = ctk.StringVar()
		self._search_var.trace_add('write', self._filter_tree)
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
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			width=100,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(8, 0))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 14))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Nombre', 'Teléfono', 'Deuda Acumulada')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			if col == 'Nombre':
				self.tree.column(col, anchor='w', width=200)
			elif col == 'Deuda Acumulada':
				self.tree.column(col, anchor='center', width=120)
			else:
				self.tree.column(col, anchor='center', width=80)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('deudor', foreground=RED_TEXT)

		# Label empty state
		self.lbl_empty_customers = ctk.CTkLabel(
			self.table_container,
			text='👤\nNo hay clientes registrados.\nAgregá el primero con el formulario.',
			font=('Arial', 13),
			text_color=TEXT_MUTED,
			justify='center',
		)

		# ── Botón Seleccionar para Cobro ─────────────────────────────────
		btn_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btn_row.pack(fill='x', padx=14, pady=(4, 14))

		ctk.CTkButton(
			btn_row,
			text='💰  Seleccionar para Cobro',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self._select_for_payment,
		).pack(side='left', fill='x', expand=True)

		self.customer_map = {}
		self._all_customers = []
		self.after(100, self.load_data)

	def _select_for_payment(self):
		"""Carga el cliente seleccionado en la tabla al combo de Cobro."""
		selected = self.tree.selection()
		if not selected:
			from CTkMessagebox import CTkMessagebox

			CTkMessagebox(
				title='Selección',
				message='Seleccioná un cliente de la tabla primero.',
				icon='info',
			)
			return
		values = self.tree.item(selected[0], 'values')
		name = values[1] if len(values) > 1 else ''
		if name and name in self.customer_map:
			self.combo_customers.set(name)
			self.on_customer_select(name)

	def _filter_tree(self, *args):
		"""Filtra la tabla en tiempo real."""
		q = self._search_var.get().lower()
		matches = (
			[
				c
				for c in self._all_customers
				if q in (c.get('name') or '').lower()
				or q in (c.get('phone') or '').lower()
			]
			if q
			else self._all_customers
		)

		for item in self.tree.get_children():
			self.tree.delete(item)

		for c in matches:
			balance = float(c.get('current_balance') or 0.0)
			saldo_str = f'${balance:.2f}'
			item_id = self.tree.insert(
				'',
				'end',
				values=(c['id'], c['name'], c.get('phone') or '-', saldo_str),
			)
			if balance > 0:
				self.tree.item(item_id, tags=('deudor',))

		# Mostrar / ocultar empty state
		if hasattr(self, 'lbl_empty_customers'):
			if not matches:
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
				text=f'{shown} de {total}' if q else f'{total} clientes'
			)

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

	def on_customer_select(self, selected_name):
		if selected_name in self.customer_map:
			cliente = self.customer_map[selected_name]
			balance = float(cliente.get('current_balance') or 0.0)
			self.entry_payment.delete(0, 'end')
			if balance > 0:
				self.entry_payment.insert(0, f'{balance:.2f}')

	def add_customer(self):
		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()

		if not name:
			CTkMessagebox(
				title='Faltan datos',
				message='El nombre del cliente es obligatorio.',
				icon='warning',
			)
			return

		tenant_id = self.ctx.tenant_id
		success, msg = self.controller.add_customer(tenant_id, name, phone)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.entry_name.delete(0, 'end')
			self.entry_phone.delete(0, 'end')
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def pay_debt(self):
		name = self.combo_customers.get()
		amount_str = self.entry_payment.get().strip().replace(',', '.')

		if name not in self.customer_map or not amount_str:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un cliente y escribí el monto que abona.',
				icon='warning',
			)
			return

		customer = self.customer_map[name]

		try:
			amount = float(amount_str)
			if amount <= 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(
				title='Error de Monto',
				message='Ingresá un número mayor a cero (Ej: 150.50).',
				icon='cancel',
			)
			return

		msg_box = CTkMessagebox(
			title='Confirmar Abono',
			message=f'Registrar un abono de ${amount:.2f} para {customer["name"]}?',
			icon='question',
			option_1='Cancelar',
			option_2='Confirmar',
		)
		if msg_box.get() != 'Confirmar':
			return

		tenant_id = self.ctx.tenant_id
		success, msg = self.controller.register_payment(
			tenant_id, customer['id'], amount
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.entry_payment.delete(0, 'end')
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
