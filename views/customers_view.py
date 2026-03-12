from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox


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
			text_color='#ff8800',  # Naranja
		).pack(pady=10)

		# NUEVO: Le agregamos el 'command' para que autocompleta el monto al seleccionar
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
			fg_color='green',
			hover_color='#216e41',
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

		# Configuramos la tabla
		columns = ('ID', 'Nombre', 'Teléfono', 'Deuda Acumulada')
		style = ttk.Style()
		style.configure('Treeview', font=('Arial', 12), rowheight=25)

		self.tree = ttk.Treeview(self.right_panel, columns=columns, show='headings')

		for col in columns:
			self.tree.heading(col, text=col)
			if col == 'Nombre':
				self.tree.column(col, anchor='w', width=200)
			elif col == 'Deuda Acumulada':
				self.tree.column(col, anchor='center', width=120)
			else:
				self.tree.column(col, anchor='center', width=80)

		self.tree.pack(fill='both', expand=True, padx=10, pady=10)

		self.load_data()

	def load_data(self):
		"""Carga la tabla y el combobox de clientes (omitiendo al Consumidor Final)"""
		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Traemos a los clientes activos desde la base de datos
		customers = self.controller.get_customers(self.current_user.tenant_id)

		# Guardamos a los clientes reales en un diccionario para usarlos rápido
		self.customer_map = {
			c.name: c for c in customers if c.name != 'Consumidor Final'
		}

		# Actualizamos la lista desplegable
		if self.customer_map:
			self.combo_customers.configure(values=list(self.customer_map.keys()))
			self.combo_customers.set('Seleccionar cliente...')
		else:
			self.combo_customers.set('No hay clientes registrados')

		# Llenamos la tabla visual
		for c in customers:
			# Solo pintamos de rojo si realmente debe dinero
			saldo_str = f'${c.current_balance:.2f}'
			item_id = self.tree.insert(
				'', 'end', values=(c.id, c.name, c.phone or '-', saldo_str)
			)

			# Opcional: Podríamos pintar la fila de rojo si la deuda es mayor a 0 usando tags
			if c.current_balance > 0:
				self.tree.item(item_id, tags=('deudor',))

		self.tree.tag_configure('deudor', foreground='red')

	def on_customer_select(self, selected_name):
		"""NUEVO: Autocompleta el monto total de la deuda al seleccionar un cliente"""
		if selected_name in self.customer_map:
			cliente = self.customer_map[selected_name]

			# Limpiamos la casilla
			self.entry_payment.delete(0, 'end')

			# Si debe dinero, sugerimos pagar el total
			if cliente.current_balance > 0:
				self.entry_payment.insert(0, str(cliente.current_balance))
			else:
				self.entry_payment.insert(0, '0.0')

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

		success, msg = self.controller.add_customer(
			self.current_user.tenant_id, name, phone
		)

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
		amount_str = self.entry_payment.get().strip()

		if name not in self.customer_map or not amount_str:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un cliente y escribe el monto que abona.',
				icon='warning',
			)
			return

		# Pedimos confirmación antes de meter mano a la caja
		confirm = CTkMessagebox(
			title='Confirmar Abono',
			message=f'¿Confirmas que {name} te está entregando ${amount_str}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		).get()
		if confirm != 'Sí':
			return

		customer_id = self.customer_map[name].id

		# Llamamos al controlador para que haga la matemática
		success, msg = self.controller.pay_debt(
			self.current_user.tenant_id, self.current_user.id, customer_id, amount_str
		)

		if success:
			CTkMessagebox(title='Pago Registrado', message=msg, icon='check')
			self.entry_payment.delete(0, 'end')
			self.combo_customers.set('Seleccionar cliente...')
			self.load_data()
		else:
			CTkMessagebox(title='Error al cobrar', message=msg, icon='cancel')
