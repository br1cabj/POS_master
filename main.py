import logging
import os
import sys

import customtkinter as ctk
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


def _setup_logging():
	if getattr(sys, 'frozen', False):
		_base = os.path.dirname(sys.executable)
		log_path = os.path.join(_base, 'cloudpos.log')
		try:
			open(log_path, 'a').close()
		except OSError:
			_appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
			_base = os.path.join(_appdata, 'CloudPOS')
			os.makedirs(_base, exist_ok=True)
			log_path = os.path.join(_base, 'cloudpos.log')
	else:
		log_path = os.path.join(
			os.path.dirname(os.path.abspath(__file__)), 'cloudpos.log'
		)
	logging.basicConfig(
		filename=log_path,
		level=logging.WARNING,
		format='%(asctime)s %(name)s %(levelname)s %(message)s',
		encoding='utf-8',
	)


_setup_logging()

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

		from utils.styles import apply_treeview_style
		apply_treeview_style()

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
		# Verificar ventas pendientes de sincronizar antes de cerrar
		if hasattr(self, '_sync_worker') and self._sync_worker.is_running:
			pending = self._count_unsynced_sales()
			if pending == -1:
				# No se pudo determinar; mostrar precaución genérica
				from CTkMessagebox import CTkMessagebox

				msg = CTkMessagebox(
					master=self,
					title='Sincronización',
					message=(
						'No se pudo verificar el estado de sincronización. '
						'Podría haber ventas sin sincronizar.\n\n'
						'¿Querés cerrar de todas formas?'
					),
					icon='warning',
					option_1='Cancelar',
					option_2='Cerrar igual',
				)
				if msg.get() == 'Cancelar':
					return
			elif pending > 0:
				from CTkMessagebox import CTkMessagebox

				msg = CTkMessagebox(
					title='Ventas sin sincronizar',
					message=(
						f'Hay {pending} venta(s) reciente(s) que podrían no estar sincronizadas con la nube.\n\n'
						'¿Querés cerrar de todas formas?'
					),
					icon='warning',
					option_1='Cancelar',
					option_2='Cerrar igual',
				)
				if msg.get() != 'Cerrar igual':
					return
		if hasattr(self, '_sync_worker'):
			self._sync_worker.stop()
		if self.db_engine is not None:
			self.db_engine.dispose()
		self.destroy()

	def _count_unsynced_sales(self) -> int:
		"""Cuenta ventas creadas desde la última sincronización exitosa.
		Retorna -1 si no se pudo determinar (ej. estado corrupto)."""
		if self.db_engine is None:
			return 0
		try:
			from utils.sync_worker import _load_state

			state = _load_state()
			last_str = state.get('sales')
			if not last_str:
				return 0
			from datetime import datetime as _dt

			last_sync = _dt.fromisoformat(last_str)
			from sqlalchemy.orm import sessionmaker

			from database.models import Sale

			Session = sessionmaker(bind=self.db_engine)
			with Session() as s:
				return s.query(Sale).filter(Sale.updated_at > last_sync).count()
		except Exception as e:
			logger.error('No se pudo contar ventas sin sincronizar: %s', e)
			return -1

	def _clear_window(self):
		for widget in self.winfo_children():
			widget.destroy()

	def _get_or_create_engine(self):
		if self.db_engine is None:
			terminal_mode = settings_get('terminal_mode', 'primary')

			if terminal_mode == 'cashier':
				# Cajero: conecta al .db remoto, sin migraciones ni sync.
				# Normalizar la ruta para SQLAlchemy: las rutas UNC de Windows
				# (\\server\share\file.db) necesitan barras y 4 slashes en la URL.
				from utils.config import make_engine

				db_path = settings_get('db_remote_path', '')
				_p = db_path.replace('\\', '/')
				_url = f'sqlite://{_p}' if _p.startswith('//') else f'sqlite:///{_p}'
				self.db_engine = make_engine(_url)
				# Actualizar el DB offline de respaldo en segundo plano
				self._update_offline_backup(db_path)
			else:
				# Principal: flujo normal con migraciones y sync
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

		terminal_mode = settings_get('terminal_mode', 'primary')

		# ── Modo Cajero ──────────────────────────────────────────────────
		if terminal_mode == 'cashier':
			db_path = settings_get('db_remote_path', '')
			if db_path:
				# Show a loading screen while checking network drive
				loading_frame = ctk.CTkFrame(self)
				loading_frame.pack(fill='both', expand=True, padx=60, pady=60)
				ctk.CTkLabel(
					loading_frame,
					text='Buscando Terminal Principal...',
					font=('Arial', 20, 'bold'),
					text_color='#3498DB',
				).pack(pady=40)

				import threading

				def check_db_path():
					exists = os.path.exists(db_path)
					if self.winfo_exists():
						self.after(
							0, lambda: self._on_cashier_path_checked(exists, db_path)
						)

				threading.Thread(target=check_db_path, daemon=True).start()
				return
			# db_remote_path vacío → wizard no completado, continuar al wizard

		# ── Modo Principal (o cajero sin configurar) ─────────────────────
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

	def _on_cashier_path_checked(self, exists: bool, db_path: str):
		self._clear_window()
		if exists:
			self._get_or_create_engine()
			self.show_login()
		else:
			self._show_cashier_offline(db_path)

	def _update_offline_backup(self, remote_db_path: str):
		"""Copia el DB remoto al local de respaldo en segundo plano (no bloquea la UI)."""
		import threading as _th

		def _do():
			try:
				import sqlite3

				offline = self._offline_db_path()
				src = sqlite3.connect(remote_db_path)
				dst = sqlite3.connect(offline)
				src.backup(dst)
				src.close()
				dst.close()
				logger.info('Backup offline actualizado desde el DB remoto.')
			except Exception as e:
				logger.warning('No se pudo actualizar el backup offline: %s', e)

		_th.Thread(target=_do, daemon=True, name='OfflineBackup').start()

	def _show_cashier_offline(self, db_path: str):
		"""Pantalla de error cuando la Terminal Principal no está accesible en la red."""
		frame = ctk.CTkFrame(self)
		frame.pack(fill='both', expand=True, padx=60, pady=60)

		ctk.CTkLabel(
			frame,
			text='⚠️  Terminal Principal no disponible',
			font=('Arial', 20, 'bold'),
			text_color='#E67E22',
		).pack(pady=(40, 10))

		ctk.CTkLabel(
			frame,
			text=(
				f'No se puede acceder a la base de datos:\n{db_path}\n\n'
				'Verificá que la Terminal Principal esté encendida\n'
				'y que ambas PCs estén conectadas a la misma red.'
			),
			font=('Arial', 12),
			text_color='#AAAAAA',
			justify='center',
		).pack(pady=10)

		ctk.CTkButton(
			frame,
			text='🔄  Reintentar',
			command=self._retry_cashier,
		).pack(pady=(20, 8))

		# Botón de modo offline solo si existe un DB de respaldo local
		offline_db = self._offline_db_path()
		if os.path.exists(offline_db):
			ctk.CTkLabel(
				frame,
				text='Se detectó una base de datos local de respaldo.',
				font=('Arial', 10),
				text_color='#888888',
			).pack(pady=(0, 4))
			ctk.CTkButton(
				frame,
				text='📴  Continuar sin conexión',
				fg_color='#2C3E50',
				hover_color='#34495E',
				text_color='#ECF0F1',
				command=self._start_offline_cashier,
			).pack(pady=(0, 20))

	def _offline_db_path(self) -> str:
		"""Ruta del SQLite local de respaldo para modo offline del cajero."""
		import os

		appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
		offline_dir = os.path.join(appdata, 'CloudPOS')
		os.makedirs(offline_dir, exist_ok=True)
		return os.path.join(offline_dir, 'cashier_offline.db')

	def _start_offline_cashier(self):
		"""Abre el DB local de respaldo en modo offline."""
		offline_path = self._offline_db_path()
		from utils.config import make_engine

		self.db_engine = make_engine(f'sqlite:///{offline_path}')
		from database.migrations import run_migrations

		run_migrations(self.db_engine)
		# Guardamos en settings que estamos en modo offline para mostrar banner
		from utils.settings_manager import set as settings_set

		settings_set('cashier_offline_mode', True)
		self.show_login()

	def _retry_cashier(self):
		self._clear_window()
		# Limpiar flag de modo offline al reconectar
		from utils.settings_manager import set as settings_set

		settings_set('cashier_offline_mode', False)
		self.after(100, self.check_system_state)

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
		engine = self._get_or_create_engine()
		ctx = AppContext(
			db_engine=engine,
			current_user=current_user,
			settings=SettingsManager(),
			sync_worker=getattr(self, '_sync_worker', None),
		)

		# Auto-backup diario: solo en Terminal Principal
		if settings_get('terminal_mode', 'primary') == 'primary':
			from controllers.backup_controller import BackupController

			BackupController(engine).auto_backup_if_needed()

		# Pasar flag de modo offline al contexto para que el dashboard muestre el banner
		ctx.offline_mode = settings_get('cashier_offline_mode', False)

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
			else:
				logger.warning('Sección de onboarding desconocida: %s', navigate_to)

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
