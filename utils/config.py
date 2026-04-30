import os
import sys
from pathlib import Path

from sqlalchemy import create_engine

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass


def _app_dir() -> Path:
	"""Carpeta del ejecutable en producción, raíz del proyecto en desarrollo."""
	if getattr(sys, 'frozen', False):
		return Path(sys.executable).parent
	return Path(__file__).parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# Configuración centralizada de la aplicación
# ─────────────────────────────────────────────────────────────────────────────

# Si DATABASE_URL está definido en el entorno lo usa; si no, SQLite junto al exe
_default_db = f'sqlite:///{_app_dir() / "pos_system.db"}'
DB_URL = os.getenv('DATABASE_URL', _default_db)

SECRET_SALT = 'aantesbajocabeconcontradedesdeenentrehaciahastaparaporsegunsinsobretrasmediantedurante'


def make_engine(url: str = None):
	"""
	Fábrica de engines SQLAlchemy con configuración segura.
	- SQLite: activa check_same_thread=False para evitar errores de hilos con Tkinter.
	- PostgreSQL/Red: configura pool, recycle y pre_ping para alta concurrencia.
	"""
	target = url or DB_URL
	kwargs = {}

	if target.startswith('sqlite'):
		kwargs['connect_args'] = {'check_same_thread': False}
	else:
		kwargs['pool_size'] = 10
		kwargs['max_overflow'] = 20
		kwargs['pool_recycle'] = 3600
		kwargs['pool_pre_ping'] = True

	return create_engine(target, **kwargs)
