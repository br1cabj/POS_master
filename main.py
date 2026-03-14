import os

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy import create_engine

# Importamos tus controladores y vistas
from controllers.license_controller import LicenseController
from views.login_view import LoginView
from views.main_dashboard import MainDashboard
from views.setup_wizard_view import SetupWizard

# Ruta de tu base de datos
DB_URL = 'sqlite:///pos_system.db'

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')


class PosApp(ctk.CTk):
	def __init__(self):
		super().__init__()
		self.title('CloudPOS - Sistema de Gestión')
		self.geometry('1000x600')

		# 1. PONER EL ÍCONO
		try:
			self.iconbitmap('icono.ico')
		except Exception:
			pass

		self.license_ctrl = LicenseController()

		# Arrancamos el motor de base de datos
		self.db_engine = create_engine(DB_URL)

		self.check_system_state()

	def check_system_state(self):
		"""Decide a qué pantalla enviar al usuario"""
		# Limpiar ventana completa
		for widget in self.winfo_children():
			widget.destroy()

		# 1. ¿Es la primera vez que se abre el sistema?
		if not os.path.exists('pos_system.db') or not os.path.exists('license.dat'):
			self.show_wizard()
			return

		# 2. El sistema existe. ¿Pagó la licencia?
		is_valid, status_msg = self.license_ctrl.check_license_status()

		if is_valid:
			# Todo en orden, ir al Login normal
			self.show_login()
		else:
			# Licencia vencida o alterada
			self.show_license_lock(status_msg)

	def show_wizard(self):
		# Llama a la pantalla de configuración inicial
		SetupWizard(self, on_complete_callback=self.check_system_state)
		# El pack() ya se hace dentro de SetupWizard

	def show_login(self):
		# 🔌 CONEXIÓN REAL AL LOGIN
		login_frame = LoginView(
			self, self.db_engine, on_login_success=self.start_dashboard
		)
		login_frame.pack(fill='both', expand=True)

	def start_dashboard(self, current_user):
		# 🔌 CONEXIÓN REAL AL SISTEMA
		for widget in self.winfo_children():
			widget.destroy()

		dashboard = MainDashboard(self, current_user, self.db_engine)
		dashboard.pack(fill='both', expand=True)

	def show_license_lock(self, error_type):
		"""Pantalla de bloqueo para clientes morosos"""
		frame = ctk.CTkFrame(self)
		frame.pack(fill='both', expand=True, padx=50, pady=50)

		ctk.CTkLabel(
			frame,
			text='⚠️ SISTEMA BLOQUEADO',
			font=('Arial', 24, 'bold'),
			text_color='red',
		).pack(pady=20)

		motivo = (
			'Tu período de prueba o licencia ha expirado.'
			if error_type == 'EXPIRED'
			else 'Licencia alterada o no encontrada.'
		)
		ctk.CTkLabel(frame, text=motivo).pack(pady=10)
		ctk.CTkLabel(
			frame,
			text='Contacta a tu proveedor para renovar y obtén tu nuevo código de activación.',
		).pack(pady=20)

		self.entry_renewal = ctk.CTkEntry(
			frame, width=300, placeholder_text='Ingresa el nuevo código de licencia'
		)
		self.entry_renewal.pack(pady=10)

		ctk.CTkButton(
			frame, text='Renovar y Desbloquear', command=self.renew_license
		).pack(pady=10)

	def renew_license(self):
		key = self.entry_renewal.get().strip()
		success, msg = self.license_ctrl.activate_license(key)
		if success:
			CTkMessagebox(
				title='¡Gracias!',
				message='Sistema desbloqueado. Gracias por tu pago.',
				icon='check',
			)
			self.check_system_state()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')


if __name__ == '__main__':
	app = PosApp()
	app.mainloop()
