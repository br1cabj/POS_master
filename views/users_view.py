from tkinter import ttk

import customtkinter as ctk


class UsersView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Importamos el controlador
		from controllers.user_controller import UserController

		self.controller = UserController(db_engine)

		# --- ESTRUCTURA ---
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: NUEVO USUARIO ===
		self.left_panel = ctk.CTkFrame(self, width=250)
		self.left_panel.grid(row=0, column=0, sticky='ns', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel, text='Nuevo Empleado', font=('Arial', 20, 'bold')
		).pack(pady=20)

		self.entry_username = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre de Usuario'
		)
		self.entry_username.pack(pady=10, padx=20, fill='x')

		self.entry_password = ctk.CTkEntry(
			self.left_panel, placeholder_text='Contraseña', show='*'
		)
		self.entry_password.pack(pady=10, padx=20, fill='x')

		# Selector de Rol
		ctk.CTkLabel(self.left_panel, text='Rol del Empleado:').pack(pady=(10, 0))
		self.combo_role = ctk.CTkComboBox(self.left_panel, values=['cajero', 'admin'])
		self.combo_role.pack(pady=5, padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Crear Usuario', command=self.save_user
		)
		self.btn_add.pack(pady=20, padx=20, fill='x')

		# Etiqueta para mensajes de éxito/error
		self.lbl_message = ctk.CTkLabel(self.left_panel, text='', text_color='green')
		self.lbl_message.pack(pady=5)

		# === PANEL DERECHO: LISTA DE USUARIOS ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel, text='Empleados Registrados', font=('Arial', 20, 'bold')
		).pack(pady=10)

		# Tabla de usuarios
		self.tree = ttk.Treeview(
			self.right_panel, columns=('ID', 'Usuario', 'Rol'), show='headings'
		)
		self.tree.heading('ID', text='ID')
		self.tree.heading('Usuario', text='Nombre de Usuario')
		self.tree.heading('Rol', text='Rol')

		self.tree.column('ID', width=50, anchor='center')
		self.tree.column('Usuario', width=200, anchor='center')
		self.tree.column('Rol', width=100, anchor='center')

		self.tree.pack(fill='both', expand=True, padx=20, pady=10)

		# Cargar datos al iniciar
		self.refresh_list()

	def save_user(self):
		username = self.entry_username.get().strip()
		password = self.entry_password.get().strip()
		role = self.combo_role.get()

		if username and password:
			success, message = self.controller.add_user(
				username, password, role, self.current_user.tenant_id
			)

			if success:
				self.lbl_message.configure(text=message, text_color='green')
				self.refresh_list()
				# Limpiar campos
				self.entry_username.delete(0, 'end')
				self.entry_password.delete(0, 'end')
			else:
				self.lbl_message.configure(text=message, text_color='red')
		else:
			self.lbl_message.configure(
				text='Completa todos los campos', text_color='red'
			)

	def refresh_list(self):
		# Limpiar tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Pedir usuarios a la BD
		users = self.controller.get_users(self.current_user.tenant_id)

		# Llenar tabla
		for u in users:
			self.tree.insert('', 'end', values=(u.id, u.username, u.role.capitalize()))
