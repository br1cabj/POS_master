import bcrypt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from controllers.license_controller import LicenseController

# Importamos para crear la base de datos de cero
from database.models import Base, Branch, Tenant, User, Warehouse

DB_URL = 'sqlite:///pos_system.db'


class SetupWizard(ctk.CTkFrame):
	def __init__(self, master, on_complete_callback):
		super().__init__(master)
		self.on_complete_callback = on_complete_callback
		self.license_ctrl = LicenseController()

		self.pack(fill='both', expand=True, padx=40, pady=40)

		ctk.CTkLabel(
			self,
			text='🚀 Bienvenido a tu nuevo Sistema POS',
			font=('Arial', 24, 'bold'),
			text_color='#00aaff',
		).pack(pady=10)
		ctk.CTkLabel(
			self, text='Vamos a configurar tu local por primera vez.', text_color='gray'
		).pack(pady=(0, 20))

		# --- DATOS DEL LOCAL ---
		ctk.CTkLabel(
			self, text='1. Nombre de tu Comercio:', font=('Arial', 14, 'bold')
		).pack(pady=(10, 5))
		self.entry_store = ctk.CTkEntry(
			self, width=300, placeholder_text='Ej: Kiosco Carlitos'
		)
		self.entry_store.pack()

		ctk.CTkLabel(
			self, text='2. Contraseña del Administrador:', font=('Arial', 14, 'bold')
		).pack(pady=(20, 5))
		self.entry_pass = ctk.CTkEntry(
			self, width=300, show='*', placeholder_text='Tu clave secreta'
		)
		self.entry_pass.pack()

		# --- LICENCIA ---
		ctk.CTkLabel(
			self, text='3. Activación del Sistema:', font=('Arial', 14, 'bold')
		).pack(pady=(30, 5))

		self.btn_demo = ctk.CTkButton(
			self,
			text='🎁 Iniciar Prueba Gratis (7 Días)',
			fg_color='#e68a00',
			hover_color='#cc7a00',
			command=self.start_demo,
		)
		self.btn_demo.pack(pady=10)

		ctk.CTkLabel(self, text='- O ingresa tu código de compra -').pack()

		self.entry_license = ctk.CTkEntry(
			self, width=300, placeholder_text='Ej: MES-20260413-A1B2...'
		)
		self.entry_license.pack(pady=5)
		self.btn_activate = ctk.CTkButton(
			self,
			text='✅ Activar Licencia Pro',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			command=self.activate_pro,
		)
		self.btn_activate.pack()

	def _setup_database(self):
		"""Crea la BD y el usuario administrador físicamente en la PC del cliente"""
		store_name = self.entry_store.get().strip()
		password = self.entry_pass.get().strip()

		engine = create_engine(DB_URL)
		Base.metadata.create_all(engine)  # Crea el archivo pos_system.db
		Session = sessionmaker(bind=engine)

		with Session() as session:
			# Crear Empresa (Sin la palabra active=True que daba error)
			tenant = Tenant(name=store_name)
			session.add(tenant)
			session.flush()

			# Depósito Básico
			branch = Branch(name='Sede Principal', tenant_id=tenant.id)
			session.add(branch)
			session.flush()
			warehouse = Warehouse(name='Depósito General', branch_id=branch.id)
			session.add(warehouse)

			# Usuario Admin
			hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode(
				'utf-8'
			)
			admin = User(
				tenant_id=tenant.id,
				username='admin',
				password_hash=hashed,
				role='admin',
				is_active=True,
			)
			session.add(admin)

			session.commit()

	def start_demo(self):
		if not self.entry_store.get() or not self.entry_pass.get():
			CTkMessagebox(
				title='Error',
				message='Llena el nombre del local y la clave.',
				icon='cancel',
			)
			return

		success, msg = self.license_ctrl.activate_demo()
		if success:
			try:
				self._setup_database()
				msg_box = CTkMessagebox(title='Listo!!', message=msg, icon='check')
				msg_box.get()
				self.after(
					100, self.on_complete_callback
				)  # Pasa a la pantalla de Login
			except Exception as e:
				CTkMessagebox(
					title='Error Fatal',
					message=f'Fallo al crear la base de datos:\n{str(e)}',
					icon='cancel',
				)

	def activate_pro(self):
		if (
			not self.entry_store.get()
			or not self.entry_pass.get()
			or not self.entry_license.get()
		):
			CTkMessagebox(
				title='Error',
				message='Llena todos los campos incluyendo la licencia.',
				icon='cancel',
			)
			return

		success, msg = self.license_ctrl.activate_license(
			self.entry_license.get().strip()
		)
		if success:
			try:
				self._setup_database()
				msg_box = CTkMessagebox(title='Listo!!', message=msg, icon='check')
				msg_box.get()
				self.after(100, self.on_complete_callback)
			except Exception as e:
				CTkMessagebox(
					title='Error Fatal',
					message=f'Fallo al crear la base de datos:\n{str(e)}',
					icon='cancel',
				)
		else:
			CTkMessagebox(title='Licencia Rechazada', message=msg, icon='cancel')
