import logging

import bcrypt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy.orm import sessionmaker

from controllers.license_controller import LicenseController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, ORANGE, ORANGE_DIM, ORANGE_TEXT,
    SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)
from database.models import Base, Branch, Tenant, User, Warehouse
from utils.config import make_engine

logger = logging.getLogger(__name__)


class SetupWizard(ctk.CTkFrame):
	def __init__(self, master, on_complete_callback):
		super().__init__(master)
		self.on_complete_callback = on_complete_callback
		self.license_ctrl = LicenseController()
		self._busy = False  # Bloqueo anti-doble-clic

		self.pack(fill='both', expand=True, padx=40, pady=40)

		ctk.CTkLabel(
			self,
			text='🚀 Bienvenido a tu nuevo Sistema POS',
			font=('Arial', 24, 'bold'),
			text_color=ACCENT_TEXT,
		).pack(pady=10)
		ctk.CTkLabel(
			self, text='Vamos a configurar tu local por primera vez.', text_color=TEXT_MUTED
		).pack(pady=(0, 20))

		# --- DATOS DEL LOCAL ---
		ctk.CTkLabel(
			self, text='1. Nombre de tu Comercio:', font=('Arial', 14, 'bold'), text_color=TEXT_PRIMARY
		).pack(pady=(10, 5))
		self.entry_store = ctk.CTkEntry(
			self, width=300, placeholder_text='Ej: Kiosco Carlitos',
			fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
		)
		self.entry_store.pack()

		ctk.CTkLabel(
			self, text='2. Contraseña del Administrador:', font=('Arial', 14, 'bold'), text_color=TEXT_PRIMARY
		).pack(pady=(20, 5))
		self.entry_pass = ctk.CTkEntry(
			self, width=300, show='*', placeholder_text='Tu clave secreta',
			fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
		)
		self.entry_pass.pack()

		# --- LICENCIA ---
		ctk.CTkLabel(
			self, text='3. Activación del Sistema:', font=('Arial', 14, 'bold'), text_color=TEXT_PRIMARY
		).pack(pady=(30, 5))

		self.btn_demo = ctk.CTkButton(
			self,
			text='🎁 Iniciar Prueba Gratis (7 Días)',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			command=self.start_demo,
		)
		self.btn_demo.pack(pady=10)

		ctk.CTkLabel(self, text='— O ingresá tu código de compra —', text_color=TEXT_MUTED).pack()

		self.entry_license = ctk.CTkEntry(
			self, width=300, placeholder_text='XXXX-XXXX-XXXX',
			fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
		)
		self.entry_license.pack(pady=5)
		self.btn_activate = ctk.CTkButton(
			self,
			text='✅ Activar Licencia Pro',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			command=self.activate_pro,
		)
		self.btn_activate.pack()

	def _set_busy(self, busy: bool) -> None:
		"""Habilita/deshabilita botones durante el proceso de configuración."""
		self._busy = busy
		state = 'disabled' if busy else 'normal'
		self.btn_demo.configure(state=state)
		self.btn_activate.configure(state=state)

	def _setup_database(self):
		"""Crea la BD y el usuario administrador físicamente en la PC del cliente"""
		store_name = self.entry_store.get().strip()
		password = self.entry_pass.get().strip()

		engine = make_engine()
		Base.metadata.create_all(engine)  # Crea el archivo pos_system.db
		Session = sessionmaker(bind=engine)

		with Session() as session:
			# Crear Empresa
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
		if self._busy:
			return
		if not self.entry_store.get() or not self.entry_pass.get():
			CTkMessagebox(
				title='Error',
				message='Llena el nombre del local y la clave.',
				icon='cancel',
			)
			return

		self._set_busy(True)
		success, msg = self.license_ctrl.activate_demo()
		if success:
			try:
				self._setup_database()
				msg_box = CTkMessagebox(title='Listo!!', message=msg, icon='check')
				msg_box.get()
				self.after(100, self.on_complete_callback)
			except Exception as e:
				logger.error(f'Error al crear la base de datos: {e}', exc_info=True)
				CTkMessagebox(
					title='Error Fatal',
					message=f'Fallo al crear la base de datos:\n{str(e)}',
					icon='cancel',
				)
				self._set_busy(False)
		else:
			CTkMessagebox(title='Error de Licencia', message=msg, icon='cancel')
			self._set_busy(False)

	def activate_pro(self):
		if self._busy:
			return
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

		self._set_busy(True)
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
				logger.error(f'Error al crear la base de datos: {e}', exc_info=True)
				CTkMessagebox(
					title='Error Fatal',
					message=f'Fallo al crear la base de datos:\n{str(e)}',
					icon='cancel',
				)
				self._set_busy(False)
		else:
			CTkMessagebox(title='Licencia Rechazada', message=msg, icon='cancel')
			self._set_busy(False)
