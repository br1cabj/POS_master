import bcrypt
import customtkinter as ctk
from sqlalchemy.orm import sessionmaker

from database.models import User


class LoginView(ctk.CTkFrame):
	def __init__(self, master, db_engine, on_login_success):
		super().__init__(master)
		self.db_engine = db_engine
		self.on_login_success = on_login_success

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

	def _execute_login(self, tenant_id, username, pwd):
		"""🔐 Verifica las credenciales en la base de datos local"""
		Session = sessionmaker(bind=self.db_engine)

		with Session() as session:
			try:
				# Buscamos al usuario en la base de datos
				user_obj = (
					session.query(User)
					.filter_by(tenant_id=tenant_id, username=username, is_active=True)
					.first()
				)

				# Verificamos que exista y que la contraseña encriptada coincida
				if user_obj and bcrypt.checkpw(
					pwd.encode('utf-8'), user_obj.password_hash.encode('utf-8')
				):
					# Convertimos el objeto de la base de datos a un diccionario para pasarlo al sistema
					user_dict = {
						'id': user_obj.id,
						'tenant_id': user_obj.tenant_id,
						'username': user_obj.username,
						'role': user_obj.role,
					}

					self.on_login_success(user_dict)

				else:
					self.show_error('Usuario o contraseña incorrectos.')

			except Exception as e:
				self.show_error('Error de conexión a la base de datos.')
				print(f'Error Login: {e}')

	def show_error(self, message):
		"""Muestra el mensaje de error y reactiva el botón"""
		self.lbl_error.configure(text=message)
		self.btn_login.configure(state='normal', text='INICIAR SESIÓN')
