import logging

import customtkinter as ctk

from controllers.auth_controller import AuthController

logger = logging.getLogger(__name__)


class LoginView(ctk.CTkFrame):
	def __init__(self, master, db_engine, on_login_success):
		super().__init__(master)
		self.db_engine = db_engine
		self.on_login_success = on_login_success
		self.auth_ctrl = AuthController(db_engine)

		self.grid_rowconfigure(0, weight=1)
		self.grid_rowconfigure(2, weight=1)
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(2, weight=1)

		# === TARJETA CENTRAL (CARD) ===
		self.login_frame = ctk.CTkFrame(self, corner_radius=20, fg_color='#2b2b2b')
		self.login_frame.grid(row=1, column=1, padx=20, pady=20, ipadx=20, ipady=20)

		ctk.CTkLabel(
			self.login_frame,
			text='☁️ CloudPOS',
			font=('Arial', 36, 'bold'),
			text_color='#00aaff',
		).pack(pady=(20, 0))

		ctk.CTkLabel(
			self.login_frame,
			text='Sistema de Gestión',
			font=('Arial', 16, 'italic'),
			text_color='gray',
		).pack(pady=(0, 30))

		self.entry_tenant = ctk.CTkEntry(
			self.login_frame,
			width=280,
			height=40,
			placeholder_text='Código de Empresa (Ej: 1)',
		)
		self.entry_tenant.pack(pady=(0, 10), padx=40)
		self.entry_tenant.insert(0, '1')

		# Campo de Usuario
		self.entry_username = ctk.CTkEntry(
			self.login_frame, width=280, height=40, placeholder_text='Usuario'
		)
		self.entry_username.pack(pady=10, padx=40)

		# Campo de Contraseña
		self.entry_password = ctk.CTkEntry(
			self.login_frame,
			width=280,
			height=40,
			placeholder_text='Contraseña',
			show='*',
		)
		self.entry_password.pack(pady=10, padx=40)

		# Checkbox para mostrar/ocultar contraseña
		self.check_show_pass = ctk.CTkCheckBox(
			self.login_frame,
			text='Mostrar contraseña',
			font=('Arial', 12),
			text_color='gray',
			command=self.toggle_password,
		)
		self.check_show_pass.pack(pady=(5, 15), padx=40, anchor='w')

		# Botón de Inicio de Sesión
		self.btn_login = ctk.CTkButton(
			self.login_frame,
			text='INICIAR SESIÓN',
			width=280,
			height=45,
			font=('Arial', 14, 'bold'),
			command=self.trigger_login,
		)
		self.btn_login.pack(pady=(10, 10))

		# Etiqueta para mostrar errores
		self.lbl_error = ctk.CTkLabel(
			self.login_frame, text='', text_color='#ff3333', font=('Arial', 13, 'bold')
		)
		self.lbl_error.pack(pady=(0, 10))

		# === EVENTOS DE TECLADO ===
		self.entry_tenant.bind('<Return>', self.handle_tenant_return)
		self.entry_username.bind('<Return>', self.handle_username_return)
		self.entry_password.bind('<Return>', lambda e: self.trigger_login())

		# Ponemos el cursor en el usuario ya que la empresa viene pre-llenada
		self.entry_username.focus()

	def toggle_password(self):
		"""Muestra u oculta los asteriscos de la contraseña según el checkbox"""
		if self.check_show_pass.get():
			self.entry_password.configure(show='')
		else:
			self.entry_password.configure(show='*')

	# --- Lógica de navegación por teclado ---
	def handle_tenant_return(self, event):
		if not self.entry_username.get():
			self.entry_username.focus()
		else:
			self.handle_username_return(event)

	def handle_username_return(self, event):
		if not self.entry_password.get():
			self.entry_password.focus()
		else:
			self.trigger_login()

	def trigger_login(self):
		"""Valida visualmente y pasa a la verificación en base de datos"""
		self.lbl_error.configure(text='')

		tenant_val = self.entry_tenant.get().strip()
		user = self.entry_username.get().strip()
		pwd = self.entry_password.get().strip()

		if not tenant_val or not user or not pwd:
			self.show_error('Por favor, completa todos los campos.')
			return

		try:
			tenant_id = int(tenant_val)
		except ValueError:
			self.show_error('El código de empresa debe ser un número.')
			return

		self.btn_login.configure(state='disabled', text='CONECTANDO...')
		self.after(50, lambda: self._execute_login(tenant_id, user, pwd))

	def _execute_login(self, tenant_id: int, username: str, pwd: str):
		"""
		Delega la autenticación a AuthController, que incluye protección
		contra timing attacks y manejo correcto de bytes/str en el hash.
		"""
		try:
			user_dict = self.auth_ctrl.login(username, pwd, tenant_id=tenant_id)
			if user_dict:
				self.on_login_success(user_dict)
			else:
				self.show_error('Usuario o contraseña incorrectos.')
		except Exception as e:
			logger.error(f'Error inesperado durante el login: {e}', exc_info=True)
			self.show_error('Error de conexión a la base de datos.')

	def show_error(self, message):
		"""Muestra el mensaje de error y reactiva el botón"""
		self.lbl_error.configure(text=message)
		self.btn_login.configure(state='normal', text='INICIAR SESIÓN')
