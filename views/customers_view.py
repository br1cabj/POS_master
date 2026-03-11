from tkinter import ttk

import customtkinter as ctk


class CustomersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.customer_controller import CustomerController

		self.controller = CustomerController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: ACCIONES ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		# 1. Agregar Cliente
		ctk.CTkLabel(
			self.left_panel, text='Nuevo Cliente', font=('Arial', 18, 'bold')
		).pack(pady=10)
		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre del Cliente'
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
			text_color='orange',
		).pack(pady=10)
		self.combo_customers = ctk.CTkComboBox(
			self.left_panel, values=['Seleccionar...']
		)
		self.combo_customers.pack(pady=5, padx=20, fill='x')

		self.entry_payment = ctk.CTkEntry(
			self.left_panel, placeholder_text='Monto que entrega ($)'
		)
		self.entry_payment.pack(pady=5, padx=20, fill='x')

		self.btn_pay = ctk.CTkButton(
			self.left_panel,
			text='💰 Registrar Pago',
			fg_color='green',
			command=self.pay_debt,
		)
		self.btn_pay.pack(pady=10)

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='')
		self.lbl_msg.pack(pady=10)

		# === PANEL DERECHO: DIRECTORIO Y SALDOS ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='Directorio y Cuentas Corrientes',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)
		ctk.CTkLabel(
			self.right_panel,
			text='* Saldos negativos (-) indican que el cliente debe dinero.',
			text_color='gray',
		).pack(pady=5)

		columns = ('ID', 'Nombre', 'Teléfono', 'Saldo Actual')
		self.tree = ttk.Treeview(self.right_panel, columns=columns, show='headings')

		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor='center')
		self.tree.column('Nombre', width=200, anchor='w')

		self.tree.pack(fill='both', expand=True, padx=10, pady=10)

		self.load_data()

	def load_data(self):
		"""Carga la tabla y el combobox de clientes (omitiendo al Consumidor Final genérico)"""
		for item in self.tree.get_children():
			self.tree.delete(item)

		customers = self.controller.get_customers(self.current_user.tenant_id)

		# Guardamos a los clientes reales en un diccionario para usarlos en el combobox
		self.customer_map = {
			c.name: c for c in customers if c.name != 'Consumidor Final'
		}

		if self.customer_map:
			self.combo_customers.configure(values=list(self.customer_map.keys()))
			self.combo_customers.set(list(self.customer_map.keys())[0])

		for c in customers:
			saldo_str = f'${c.current_balance:.2f}'
			self.tree.insert('', 'end', values=(c.id, c.name, c.phone, saldo_str))

	def add_customer(self):
		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()

		if not name:
			self.lbl_msg.configure(text='El nombre es obligatorio', text_color='red')
			return

		success, msg = self.controller.add_customer(
			self.current_user.tenant_id, name, phone
		)
		self.lbl_msg.configure(text=msg, text_color='green' if success else 'red')

		if success:
			self.entry_name.delete(0, 'end')
			self.entry_phone.delete(0, 'end')
			self.load_data()

	def pay_debt(self):
		name = self.combo_customers.get()
		amount_str = self.entry_payment.get().strip()

		if name not in self.customer_map or not amount_str:
			self.lbl_msg.configure(
				text='Selecciona cliente y un monto.', text_color='red'
			)
			return

		customer_id = self.customer_map[name].id
		success, msg = self.controller.pay_debt(
			self.current_user.tenant_id, self.current_user.id, customer_id, amount_str
		)

		self.lbl_msg.configure(text=msg, text_color='green' if success else 'red')
		if success:
			self.entry_payment.delete(0, 'end')
			self.load_data()
