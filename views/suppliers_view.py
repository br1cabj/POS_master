from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.supplier_controller import SupplierController


class SuppliersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = SupplierController(db_engine)

		self.editing_id = None
		self.suppliers_list = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# --- ESTILO ---
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

		# === PANEL IZQUIERDO: FORMULARIO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel, text='🚚 Nuevo Proveedor', font=('Arial', 18, 'bold')
		)
		self.lbl_form_title.pack(pady=20)

		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Razón Social / Nombre'
		)
		self.entry_name.pack(pady=10, padx=20, fill='x')

		self.entry_phone = ctk.CTkEntry(
			self.left_panel, placeholder_text='Teléfono o WhatsApp'
		)
		self.entry_phone.pack(pady=10, padx=20, fill='x')

		self.entry_email = ctk.CTkEntry(
			self.left_panel, placeholder_text='Correo Electrónico'
		)
		self.entry_email.pack(pady=10, padx=20, fill='x')

		self.entry_address = ctk.CTkEntry(
			self.left_panel, placeholder_text='Dirección del depósito'
		)
		self.entry_address.pack(pady=10, padx=20, fill='x')

		self.btn_save = ctk.CTkButton(
			self.left_panel, text='💾 Guardar Proveedor', command=self.save_supplier
		)
		self.btn_save.pack(pady=20)

		self.btn_cancel = ctk.CTkButton(
			self.left_panel,
			text='🔄 Limpiar / Cancelar',
			fg_color='#555555',
			command=self.reset_form,
		)
		self.btn_cancel.pack(pady=5)

		# === PANEL DERECHO: DIRECTORIO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='Directorio de Proveedores',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)
		ctk.CTkLabel(
			self.right_panel,
			text='* Doble clic para editar',
			text_color='gray',
			font=('Arial', 12, 'italic'),
		).pack(pady=(0, 10))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=20, pady=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Nombre', 'Teléfono', 'Email', 'Dirección')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=15,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col in ['Nombre', 'Email'] else 100
			self.tree.column(col, anchor='w' if col != 'ID' else 'center', width=width)

		self.tree.bind('<Double-1>', self.on_tree_double_click)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Eliminar Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.delete_supplier,
		)
		self.btn_delete.pack(pady=10)

		self.after(100, self.load_data)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self._get_tenant_id()
		self.suppliers_list = self.controller.get_all_suppliers(tenant_id)

		for s in self.suppliers_list:
			self.tree.insert(
				'',
				'end',
				values=(s['id'], s['name'], s['phone'], s['email'], s['address']),
			)

	def on_tree_double_click(self, event):
		selected = self.tree.selection()
		if not selected:
			return

		sup_id = self.tree.item(selected[0], 'values')[0]
		found = next(
			(s for s in self.suppliers_list if str(s['id']) == str(sup_id)), None
		)

		if found:
			self.reset_form()
			self.editing_id = found['id']
			self.entry_name.insert(0, found['name'])
			self.entry_phone.insert(0, found['phone'])
			self.entry_email.insert(0, found['email'])
			self.entry_address.insert(0, found['address'])

			self.lbl_form_title.configure(
				text='✏️ Editando Proveedor', text_color='#00aaff'
			)
			self.btn_save.configure(text='💾 Actualizar Datos', fg_color='#0055ff')

	def reset_form(self):
		self.editing_id = None
		self.entry_name.delete(0, 'end')
		self.entry_phone.delete(0, 'end')
		self.entry_email.delete(0, 'end')
		self.entry_address.delete(0, 'end')

		self.lbl_form_title.configure(text='🚚 Nuevo Proveedor', text_color='white')
		self.btn_save.configure(
			text='💾 Guardar Proveedor', fg_color=['#3a7ebf', '#1f538d']
		)
		self.entry_name.focus()

	def save_supplier(self):
		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()
		email = self.entry_email.get().strip()
		address = self.entry_address.get().strip()

		if not name:
			CTkMessagebox(
				title='Faltan Datos',
				message='El nombre del proveedor es obligatorio.',
				icon='warning',
			)
			return

		tenant_id = self._get_tenant_id()

		success, msg = self.controller.save_supplier(
			tenant_id, self.editing_id, name, phone, email, address
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.reset_form()
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def delete_supplier(self):
		selected = self.tree.selection()
		if not selected:
			return

		msg = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseas eliminar a este proveedor?\n(No se borrarán las compras históricas hechas a él)',
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg.get() == 'Sí':
			sup_id = self.tree.item(selected[0], 'values')[0]
			tenant_id = self._get_tenant_id()

			success, msg_response = self.controller.delete_supplier(tenant_id, sup_id)
			if success:
				self.load_data()
				self.reset_form()
				CTkMessagebox(title='Eliminado', message=msg_response, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg_response, icon='cancel')
