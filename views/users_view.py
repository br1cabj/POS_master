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

		columns = ('ID', 'Usuario', 'Rol')
		self.tree = ttk.Treeview(
			self.right_panel, columns=columns, show='headings', height=15
		)
		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor='center')
		self.tree.pack(fill='both', expand=True, padx=20, pady=10)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Eliminar Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.delete_user,
		)
		self.btn_delete.pack(pady=10)

		# Carga diferida para que la UI se dibuje rápido
		self.after(50, self.load_data)

	def load_data(self):
		"""Carga los usuarios desde la BD y los dibuja en la tabla"""
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Manejo seguro del usuario activo
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# Obtenemos lista de diccionarios
		users = self.controller.get_users(tenant_id)

		for u in users:
			# Ahora accedemos a las claves del diccionario
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

		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

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

		# Manejo seguro del usuario activo
		current_username = (
			self.current_user.get('username')
			if isinstance(self.current_user, dict)
			else self.current_user.username
		)

		# Evitar que el admin se borre a sí mismo
		if selected_username == current_username:
			CTkMessagebox(
				title='Acción Denegada',
				message='No puedes borrar tu propia cuenta mientras estás en sesión.',
				icon='cancel',
			)
			return

		# CTkMessagebox asíncrono
		msg_box = CTkMessagebox(
			title='Confirmar',
			message=f'¿Seguro que deseas eliminar al empleado {selected_username}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() == 'Sí':
			# Le pasamos el ID del usuario actual al controlador para que también valide (Doble Capa)
			current_id = (
				self.current_user.get('id')
				if isinstance(self.current_user, dict)
				else self.current_user.id
			)

			success, msg = self.controller.delete_user(
				user_id, current_user_id=current_id
			)
			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')
