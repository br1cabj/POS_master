import customtkinter as ctk


class LoginView(ctk.CTkFrame):
	def __init__(self, master, login_command):
		super().__init__(master)
		self.login_command = login_command

		self.grid_rowconfigure(0, weight=1)
		self.grid_rowconfigure(2, weight=1)
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(2, weight=1)

		# === TARJETA CENTRAL (CARD) ===
		self.login_frame = ctk.CTkFrame(self, corner_radius=15)
		self.login_frame.grid(row=1, column=1, padx=20, pady=20)

		# Ícono / Título
		ctk.CTkLabel(self.login_frame, text='🏪', font=('Arial', 60)).pack(
			pady=(30, 10)
		)
		ctk.CTkLabel(
			self.login_frame, text='Bienvenido al Sistema', font=('Arial', 24, 'bold')
		).pack(pady=(0, 20))

		# Campo de Usuario
		self.entry_username = ctk.CTkEntry(
			self.login_frame, width=250, height=35, placeholder_text='Usuario'
		)
		self.entry_username.pack(pady=10, padx=40)

		# Campo de Contraseña
		self.entry_password = ctk.CTkEntry(
			self.login_frame,
			width=250,
			height=35,
			placeholder_text='Contraseña',
			show='*',
		)
		self.entry_password.pack(pady=10, padx=40)

		# Checkbox para mostrar/ocultar contraseña
		self.check_show_pass = ctk.CTkCheckBox(
			self.login_frame,
			text='Mostrar contraseña',
			font=('Arial', 12),
			command=self.toggle_password,
		)
		self.check_show_pass.pack(pady=(5, 15), padx=40, anchor='w')

		# Botón de Inicio de Sesión
		self.btn_login = ctk.CTkButton(
			self.login_frame,
			text='INICIAR SESIÓN',
			width=250,
			height=40,
			font=('Arial', 14, 'bold'),
			command=self.trigger_login,
		)
		self.btn_login.pack(pady=(10, 10))

		# Etiqueta para mostrar errores (roja, vacía por defecto)
		self.lbl_error = ctk.CTkLabel(
			self.login_frame, text='', text_color='#d9534f', font=('Arial', 12)
		)
		self.lbl_error.pack(pady=(0, 20))

		# === EVENTOS DE TECLADO ===
		# Conectamos funciones específicas para mejorar la experiencia con el teclado
		self.entry_username.bind('<Return>', self.handle_username_return)
		self.entry_password.bind('<Return>', lambda e: self.trigger_login())

		# Ponemos el cursor automáticamente en el campo de usuario al abrir
		self.entry_username.focus()

	def toggle_password(self):
		"""Muestra u oculta los asteriscos de la contraseña según el checkbox"""
		# En CustomTkinter, .get() devuelve 1 o 0. Evaluamos directamente.
		if self.check_show_pass.get():
			self.entry_password.configure(show='')
		else:
			self.entry_password.configure(show='*')

	def handle_username_return(self, event):
		"""Si presiona Enter en el usuario, salta a la contraseña si está vacía."""
		if not self.entry_password.get():
			self.entry_password.focus()
		else:
			self.trigger_login()

	def trigger_login(self):
		"""Valida, cambia el estado de la UI y lanza el comando a main.py"""
		self.lbl_error.configure(text='')
		user = self.entry_username.get().strip()
		pwd = self.entry_password.get().strip()

		if not user or not pwd:
			self.show_error('Por favor, ingresa tu usuario y contraseña.')
			return

		# Feedback visual para el usuario: Evitamos que haga doble clic
		self.btn_login.configure(state='disabled', text='CONECTANDO...')

		# Usamos self.after para que la UI se actualice visualmente antes
		# de que el controlador empiece a buscar en la base de datos
		self.after(50, lambda: self._execute_login(user, pwd))

	def _execute_login(self, user, pwd):
		"""Delega la ejecución a main.py y restaura la vista si falla."""
		self.login_command(user, pwd)

		# Restauramos el botón. (Si el login fue exitoso, main.py destruirá
		if self.winfo_exists():
			self.btn_login.configure(state='normal', text='INICIAR SESIÓN')

	def show_error(self, message):
		"""Esta función es llamada desde main.py si el usuario/clave son incorrectos"""
		self.lbl_error.configure(text=message)
		self.btn_login.configure(state='normal', text='INICIAR SESIÓN')
