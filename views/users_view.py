from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox


class UsersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.user_controller import UserController

		self.controller = UserController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

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

		self.load_data()

	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		users = self.controller.get_users(self.current_user.tenant_id)
		for u in users:
			# Ponemos un candado visual si es admin
			role_display = '👑 Admin' if u.role == 'admin' else '👤 Cajero'
			self.tree.insert('', 'end', values=(u.id, u.username, role_display))

	def add_user(self):
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

		success, msg = self.controller.add_user(
			self.current_user.tenant_id, username, password, role
		)
		if success:
			CTkMessagebox(title='Éxito', message=msg, icon='check')
			self.entry_user.delete(0, 'end')
			self.entry_pass.delete(0, 'end')
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def delete_user(self):
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
		username = values[1]

		# Evitar que el admin se borre a sí mismo
		if username == self.current_user.username:
			CTkMessagebox(
				title='Acción Denegada',
				message='No puedes borrar tu propia cuenta mientras estás en sesión.',
				icon='cancel',
			)
			return

		confirm = CTkMessagebox(
			title='Confirmar',
			message=f'¿Seguro que deseas eliminar al empleado {username}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		).get()
		if confirm == 'Sí':
			success, msg = self.controller.delete_user(user_id)
			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg, icon='check')
