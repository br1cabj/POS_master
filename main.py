import logging
import os

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.license_controller import LicenseController
from utils.config import make_engine
from views.login_view import LoginView
from views.main_dashboard import MainDashboard
from views.setup_wizard_view import SetupWizard

logger = logging.getLogger(__name__)

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')


class PosApp(ctk.CTk):
	def __init__(self):
		super().__init__()
		self.title('CloudPOS - Sistema de Gestión')
		self.geometry('1000x600')

		try:
			self.iconbitmap('icono.ico')
		except FileNotFoundError:
			logger.warning('Archivo de icono no encontrado: icono.ico')
		except Exception as e:
			logger.error(f'Error al cargar el icono: {e}')

		self.license_ctrl = LicenseController()
		self.db_engine = None
		self.protocol('WM_DELETE_WINDOW', self._on_close)
		self.check_system_state()

	def _on_close(self):
		if self.db_engine is not None:
			self.db_engine.dispose()
		self.destroy()

	def _clear_window(self):
		for widget in self.winfo_children():
			widget.destroy()

	def _get_or_create_engine(self):
		if self.db_engine is None:
			self.db_engine = make_engine()
		return self.db_engine

	def check_system_state(self):
		self._clear_window()

		if not os.path.exists('pos_system.db') or not os.path.exists('license.dat'):
			self.show_wizard()
			return

		self._get_or_create_engine()

		is_valid, status_msg = self.license_ctrl.check_license_status()
		if is_valid:
			self.show_login()
		else:
			self.show_license_lock(status_msg)

	def show_wizard(self):
		SetupWizard(self, on_complete_callback=self.check_system_state).pack(
			fill='both', expand=True
		)

	def show_login(self):
		self._clear_window()
		LoginView(
			self, self._get_or_create_engine(), on_login_success=self.start_dashboard
		).pack(fill='both', expand=True)

	def start_dashboard(self, current_user):
		self._clear_window()
		MainDashboard(
			self,
			current_user,
			logout_command=self.show_login,
			db_engine=self._get_or_create_engine(),
		).pack(fill='both', expand=True)

	def show_license_lock(self, error_type):
		self._clear_window()
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

		entry_renewal = ctk.CTkEntry(
			frame, width=300, placeholder_text='Ingresa el nuevo código de licencia'
		)
		entry_renewal.pack(pady=10)
		ctk.CTkButton(
			frame,
			text='Renovar y Desbloquear',
			command=lambda: self.renew_license(entry_renewal),
		).pack(pady=10)

	def renew_license(self, entry_widget):
		key = entry_widget.get().strip()
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
