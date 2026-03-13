import customtkinter as ctk


class LoginView(ctk.CTkFrame):
	# 🛡️ MEJORA: El login_command en tu main.py ahora deberá recibir 3 parámetros: (tenant, user, pwd)
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

		# 🛡️ ESCUDO MULTITENANT: Campo de Empresa (Tenant)
		self.entry_tenant = ctk.CTkEntry(
			self.login_frame,
			width=250,
			height=35,
			placeholder_text='Código de Empresa (Ej: 1)',
		)
		self.entry_tenant.pack(pady=(0, 10), padx=40)

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
		# 🛡️ MEJORA: Cadena de saltos con la tecla Enter
		self.entry_tenant.bind('<Return>', self.handle_tenant_return)
		self.entry_username.bind('<Return>', self.handle_username_return)
		self.entry_password.bind('<Return>', lambda e: self.trigger_login())

		# Ponemos el cursor automáticamente en el campo de la empresa al abrir
		self.entry_tenant.focus()

	def toggle_password(self):
		"""Muestra u oculta los asteriscos de la contraseña según el checkbox"""
		if self.check_show_pass.get():
			self.entry_password.configure(show='')
		else:
			self.entry_password.configure(show='*')

	# --- Lógica de navegación por teclado ---
	def handle_tenant_return(self, event):
		"""Salta de Empresa a Usuario"""
		if not self.entry_username.get():
			self.entry_username.focus()
		else:
			self.handle_username_return(event)

	def handle_username_return(self, event):
		"""Salta de Usuario a Contraseña."""
		if not self.entry_password.get():
			self.entry_password.focus()
		else:
			self.trigger_login()

	def trigger_login(self):
		"""Valida, cambia el estado de la UI y lanza el comando a main.py"""
		self.lbl_error.configure(text='')

		tenant_val = self.entry_tenant.get().strip()
		user = self.entry_username.get().strip()
		pwd = self.entry_password.get().strip()

		if not tenant_val or not user or not pwd:
			self.show_error('Por favor, completa todos los campos.')
			return

		# Validamos que el código de empresa sea un número para evitar errores tempranos
		try:
			tenant_id = int(tenant_val)
		except ValueError:
			self.show_error('El código de empresa debe ser un número.')
			return

		# Feedback visual para el usuario: Evitamos que haga doble clic
		self.btn_login.configure(state='disabled', text='CONECTANDO...')

		self.after(50, lambda: self._execute_login(tenant_id, user, pwd))

	def _execute_login(self, tenant_id, user, pwd):
		"""Delega la ejecución a main.py y restaura la vista si falla."""
		# 🐛 SOLUCIÓN BUG 1: Pasamos los tres parámetros al orquestador principal
		self.login_command(tenant_id, user, pwd)

		# Restauramos el botón si la vista no fue destruida (login fallido)
		if self.winfo_exists():
			self.btn_login.configure(state='normal', text='INICIAR SESIÓN')

	def show_error(self, message):
		"""Esta función es llamada desde main.py si el usuario/clave son incorrectos"""
		self.lbl_error.configure(text=message)
		self.btn_login.configure(state='normal', text='INICIAR SESIÓN')
