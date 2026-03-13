from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.customer_controller import CustomerController


class CustomersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = CustomerController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === ESTILO MODERNO PARA LA TABLA ===
		style = ttk.Style()
		style.theme_use('default')
		style.configure(
			'Treeview',
			background='#2b2b2b',
			foreground='white',
			rowheight=30,
			fieldbackground='#2b2b2b',
			borderwidth=0,
		)
		style.map('Treeview', background=[('selected', '#1f538d')])
		style.configure(
			'Treeview.Heading',
			background='#565b5e',
			foreground='white',
			relief='flat',
			font=('Arial', 10, 'bold'),
		)
		style.map('Treeview.Heading', background=[('active', '#343638')])

		# === PANEL IZQUIERDO: ACCIONES ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		# 1. Agregar Cliente
		ctk.CTkLabel(
			self.left_panel, text='Nuevo Cliente', font=('Arial', 18, 'bold')
		).pack(pady=(20, 10))

		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre Completo del Cliente'
		)
		self.entry_name.pack(pady=5, padx=20, fill='x')

		self.entry_phone = ctk.CTkEntry(
			self.left_panel, placeholder_text='Teléfono (Opcional)'
		)
		self.entry_phone.pack(pady=5, padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='➕ Guardar Cliente', command=self.add_customer
		)
		self.btn_add.pack(pady=10)

		ctk.CTkLabel(self.left_panel, text='------------------------').pack(pady=10)

		# 2. Cobrar Deudas
		ctk.CTkLabel(
			self.left_panel,
			text='Cobrar Deuda (Fiado)',
			font=('Arial', 18, 'bold'),
			text_color='#ff8800',
		).pack(pady=10)

		self.combo_customers = ctk.CTkComboBox(
			self.left_panel, values=['Seleccionar...'], command=self.on_customer_select
		)
		self.combo_customers.pack(pady=5, padx=20, fill='x')

		self.entry_payment = ctk.CTkEntry(
			self.left_panel, placeholder_text='Monto que abona ($)'
		)
		self.entry_payment.pack(pady=5, padx=20, fill='x')

		self.btn_pay = ctk.CTkButton(
			self.left_panel,
			text='💰 Registrar Abono',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			command=self.pay_debt,
		)
		self.btn_pay.pack(pady=20)

		# === PANEL DERECHO: DIRECTORIO Y SALDOS ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='Directorio de Clientes y Cuentas',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='* El saldo indica la deuda acumulada total del cliente.',
			text_color='gray',
			font=('Arial', 12, 'italic'),
		).pack(pady=(0, 10))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=10, pady=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Nombre', 'Teléfono', 'Deuda Acumulada')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,  # Conectamos tabla a scroll
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

		# Empaquetamos
		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('deudor', foreground='#ff6666')

		self.customer_map = {}

		self.after(100, self.load_data)

	# --- Funciones auxiliares ---
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

	def load_data(self):
		"""Carga la tabla y el combobox de clientes."""
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self._get_tenant_id()
		customers = self.controller.get_customers(tenant_id)

		self.customer_map = {
			c['name']: c for c in customers if c['name'] != 'Consumidor Final'
		}

		if self.customer_map:
			self.combo_customers.configure(values=list(self.customer_map.keys()))
			self.combo_customers.set('Seleccionar cliente...')
		else:
			self.combo_customers.configure(values=['Sin clientes'])
			self.combo_customers.set('No hay clientes registrados')

		for c in customers:
			balance = float(c.get('current_balance', 0.0))
			saldo_str = f'${balance:.2f}'

			item_id = self.tree.insert(
				'', 'end', values=(c['id'], c['name'], c.get('phone') or '-', saldo_str)
			)

			if balance > 0:
				self.tree.item(item_id, tags=('deudor',))

	def on_customer_select(self, selected_name):
		"""Autocompleta el monto total de la deuda al seleccionar un cliente"""
		if selected_name in self.customer_map:
			cliente = self.customer_map[selected_name]
			balance = float(cliente.get('current_balance', 0.0))

			self.entry_payment.delete(0, 'end')

			if balance > 0:
				self.entry_payment.insert(0, f'{balance:.2f}')
			# 🐛 SOLUCIÓN BUG 2: Dejamos el campo vacío si el saldo es <= 0
			# para que el placeholder sea visible y el usuario pueda tipear sin borrar.

	def add_customer(self):
		"""Guarda un cliente nuevo"""
		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()

		if not name:
			CTkMessagebox(
				title='Faltan datos',
				message='El nombre del cliente es obligatorio.',
				icon='warning',
			)
			return

		tenant_id = self._get_tenant_id()
		success, msg = self.controller.add_customer(tenant_id, name, phone)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.entry_name.delete(0, 'end')
			self.entry_phone.delete(0, 'end')
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def pay_debt(self):
		"""Registra el pago de una deuda"""
		name = self.combo_customers.get()
		amount_str = self.entry_payment.get().strip().replace(',', '.')

		if name not in self.customer_map or not amount_str:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un cliente y escribe el monto que abona.',
				icon='warning',
			)
			return

		# 🐛 SOLUCIÓN BUG 3: Validación rápida visual del número ANTES del popup
		try:
			amount_val = float(amount_str)
			if amount_val <= 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(
				title='Error de Monto',
				message='Por favor ingresa un número mayor a cero (Ej: 150.50).',
				icon='cancel',
			)
			return

		# Ahora que sabemos que es un número válido, mostramos la confirmación
		msg_box = CTkMessagebox(
			title='Confirmar Abono',
			message=f'¿Confirmas que {name} te está entregando ${amount_val:.2f}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() != 'Sí':
			return

		customer_id = self.customer_map[name]['id']
		tenant_id = self._get_tenant_id()
		user_id = self._get_user_id()

		success, msg = self.controller.pay_debt(
			tenant_id, user_id, customer_id, amount_str
		)

		if success:
			CTkMessagebox(title='Pago Registrado', message=msg, icon='check')
			self.entry_payment.delete(0, 'end')
			self.combo_customers.set('Seleccionar cliente...')
			self.load_data()
		else:
			CTkMessagebox(title='Error al cobrar', message=msg, icon='cancel')
