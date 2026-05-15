import logging
import os
import sys

import customtkinter as ctk

def _setup_logging():
	_base = (
		os.path.dirname(sys.executable)
		if getattr(sys, 'frozen', False)
		else os.path.dirname(os.path.abspath(__file__))
	)
	log_path = os.path.join(_base, 'cloudpos.log')
	logging.basicConfig(
		filename=log_path,
		level=logging.WARNING,
		format='%(asctime)s %(name)s %(levelname)s %(message)s',
		encoding='utf-8',
	)

_setup_logging()
from CTkMessagebox import CTkMessagebox

from controllers.license_controller import LicenseController
from core.context import AppContext
from database.migrations import run_migrations
from utils.config import get_engine
from utils.settings_manager import SettingsManager
from utils.settings_manager import get as settings_get
from views.login_view import LoginView
from views.main_dashboard import MainDashboard
from views.onboarding_view import OnboardingView
from views.setup_wizard_view import SetupWizard

logger = logging.getLogger(__name__)

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')

_SECTION_VIEW_MAP = {}


def _load_section_map():
	"""Importa las clases de vista solo cuando hace falta."""
	global _SECTION_VIEW_MAP
	if _SECTION_VIEW_MAP:
		return
	from views.articles_view import ArticlesView
	from views.cash_view import CashView
	from views.suppliers_view import SuppliersView

	_SECTION_VIEW_MAP = {
		'articles': ArticlesView,
		'suppliers': SuppliersView,
		'cash': CashView,
	}


class PosApp(ctk.CTk):
	def __init__(self):
		super().__init__()
		self.title('CloudPOS - Sistema de Gestion')
		self.geometry('1000x600')

		try:
			_base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
			self.iconbitmap(os.path.join(_base, 'icono.ico'))
		except FileNotFoundError:
			logger.warning('Archivo de icono no encontrado: icono.ico')
		except Exception as e:
			logger.error(f'Error al cargar el icono: {e}')

		self.license_ctrl = LicenseController()
		self.db_engine = None
		self.protocol('WM_DELETE_WINDOW', self._on_close)
		self.check_system_state()

	def _on_close(self):
		if hasattr(self, '_sync_worker'):
			self._sync_worker.stop()
		if self.db_engine is not None:
			self.db_engine.dispose()
		self.destroy()

	def _clear_window(self):
		for widget in self.winfo_children():
			widget.destroy()

	def _get_or_create_engine(self):
		if self.db_engine is None:
			self.db_engine = get_engine()
			run_migrations(self.db_engine)
			from utils.sync_worker import SyncWorker
			self._sync_worker = SyncWorker(self.db_engine)
			self._sync_worker.start()
		return self.db_engine

	# =========================================================
	# FLUJO PRINCIPAL
	# =========================================================
	def check_system_state(self):
		self._clear_window()

		_dir = (
			os.path.dirname(sys.executable)
			if getattr(sys, 'frozen', False)
			else os.path.dirname(os.path.abspath(__file__))
		)
		_db = os.path.join(_dir, 'pos_system.db')
		_lic = os.path.join(_dir, 'license.dat')
		if not os.path.exists(_db) or not os.path.exists(_lic):
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
		"""
		Decide si mostrar el onboarding (primer login) o el dashboard directamente.
		El flag 'onboarding_shown' se escribe en settings.json desde OnboardingView._done().
		"""
		self._clear_window()
		ctx = AppContext(
			db_engine=self._get_or_create_engine(),
			current_user=current_user,
			settings=SettingsManager(),
		)

		onboarding_shown = settings_get('onboarding_shown', False)

		if not onboarding_shown and current_user.get('role') == 'admin':
			self._show_onboarding(ctx)
		else:
			self._show_dashboard(ctx)

	def _show_onboarding(self, ctx):
		"""Muestra el onboarding post-primer-login."""
		self._clear_window()
		OnboardingView(
			self,
			ctx=ctx,
			on_done=lambda section: self._after_onboarding(ctx, section),
		).pack(fill='both', expand=True)

	def _after_onboarding(self, ctx, section):
		"""Callback de OnboardingView: muestra el dashboard y navega a la seccion si aplica."""
		self._show_dashboard(ctx, navigate_to=section)

	def _show_dashboard(self, ctx, navigate_to=None):
		self._clear_window()
		dashboard = MainDashboard(
			self,
			ctx=ctx,
			logout_command=self.show_login,
		)
		dashboard.pack(fill='both', expand=True)

		# Navegar a seccion solicitada desde el onboarding
		if navigate_to:
			_load_section_map()
			view_class = _SECTION_VIEW_MAP.get(navigate_to)
			if view_class:
				self.after(150, lambda vc=view_class: dashboard.safe_switch_view(vc))

	# =========================================================
	# BLOQUEO DE LICENCIA
	# =========================================================
	def show_license_lock(self, error_type):
		self._clear_window()
		frame = ctk.CTkFrame(self)
		frame.pack(fill='both', expand=True, padx=50, pady=50)

		ctk.CTkLabel(
			frame,
			text='SISTEMA BLOQUEADO',
			font=('Arial', 24, 'bold'),
			text_color='red',
		).pack(pady=20)

		motivo = (
			'Tu periodo de prueba o licencia ha expirado.'
			if error_type == 'EXPIRED'
			else 'Licencia alterada o no encontrada.'
		)
		ctk.CTkLabel(frame, text=motivo).pack(pady=10)
		ctk.CTkLabel(
			frame,
			text='Contacta a tu proveedor para renovar y obtené tu nuevo código de activación.',
		).pack(pady=20)

		entry_renewal = ctk.CTkEntry(
			frame, width=300, placeholder_text='Ingresa el nuevo codigo de licencia'
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
				title='Gracias!',
				message='Sistema desbloqueado. Gracias por tu pago.',
				icon='check',
			)
			self.check_system_state()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')


if __name__ == '__main__':
	app = PosApp()
	app.mainloop()
