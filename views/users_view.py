from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.user_controller import UserController


class UsersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = UserController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# --- ESTILO MODERNO PARA LA TABLA ---
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

		# === PANEL IZQUIERDO: NUEVO EMPLEADO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel, text='Nuevo Empleado', font=('Arial', 18, 'bold')
		).pack(pady=20)

		self.entry_user = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre de usuario'
		)
		self.entry_user.pack(pady=10, padx=20, fill='x')

		self.entry_pass = ctk.CTkEntry(
			self.left_panel, placeholder_text='Contraseña', show='*'
		)
		self.entry_pass.pack(pady=10, padx=20, fill='x')

		ctk.CTkLabel(self.left_panel, text='Rol de acceso:').pack(pady=(10, 0))
		self.combo_role = ctk.CTkComboBox(self.left_panel, values=['cajero', 'admin'])
		self.combo_role.pack(pady=10, padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='➕ Crear Cuenta', command=self.add_user
		)
		self.btn_add.pack(pady=20)

		# === PANEL DERECHO: LISTA DE USUARIOS ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel, text='Directorio de Empleados', font=('Arial', 18, 'bold')
		).pack(pady=10)

		# 🛡️ MEJORA: Contenedor y Scrollbar para la tabla
		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=20, pady=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Usuario', 'Rol')
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
			self.tree.column(col, anchor='center')

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Eliminar Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.delete_user,
		)
		self.btn_delete.pack(pady=10)

		self.after(50, self.load_data)

	# --- Funciones Auxiliares DRY ---
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

	def _get_username(self):
		return (
			self.current_user.get('username')
			if isinstance(self.current_user, dict)
			else self.current_user.username
		)

	def load_data(self):
		"""Carga los usuarios desde la BD y los dibuja en la tabla"""
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self._get_tenant_id()
		users = self.controller.get_users(tenant_id)

		for u in users:
			role_display = '👑 Admin' if u.get('role') == 'admin' else '👤 Cajero'
			self.tree.insert(
				'', 'end', values=(u.get('id'), u.get('username'), role_display)
			)

	def add_user(self):
		"""Envía los datos al controlador para crear un usuario"""
		username = self.entry_user.get().strip()
		password = self.entry_pass.get().strip()
		role = self.combo_role.get()

		if not username or not password:
			CTkMessagebox(
				title='Error',
				message='Usuario y contraseña son obligatorios.',
				icon='warning',
			)
			return

		tenant_id = self._get_tenant_id()

		success, msg = self.controller.add_user(tenant_id, username, password, role)

		if success:
			CTkMessagebox(title='Éxito', message=msg, icon='check')
			self.entry_user.delete(0, 'end')
			self.entry_pass.delete(0, 'end')
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def delete_user(self):
		"""Inicia el proceso de borrado lógico de un usuario"""
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un usuario de la tabla.',
				icon='info',
			)
			return

		values = self.tree.item(selected[0], 'values')
		user_id = values[0]
		selected_username = values[1]

		current_username = self._get_username()

		# Evitar que el admin se borre a sí mismo
		if selected_username == current_username:
			CTkMessagebox(
				title='Acción Denegada',
				message='No puedes borrar tu propia cuenta mientras estás en sesión.',
				icon='cancel',
			)
			return

		msg_box = CTkMessagebox(
			title='Confirmar',
			message=f'¿Seguro que deseas eliminar al empleado {selected_username}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() == 'Sí':
			tenant_id = self._get_tenant_id()
			current_id = self._get_user_id()

			# 🐛 SOLUCIÓN BUG 1: Pasamos el tenant_id como primer parámetro
			success, msg = self.controller.delete_user(
				tenant_id, user_id, current_user_id=current_id
			)

			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')
