import os

from sqlalchemy import create_engine

# ──────────────────────────────────────────────────────
# Configuración centralizada de la aplicación
# Lee desde variables de entorno; valores por defecto
# solo para desarrollo local.  En producción define
# DATABASE_URL y SECRET_SALT en un archivo .env
# ──────────────────────────────────────────────────────

DB_URL = os.getenv('DATABASE_URL', 'sqlite:///pos_system.db')
SECRET_SALT = os.getenv('SECRET_SALT', 'KioscoPOS_SaaS_2026_Secreto_X99')


def make_engine(url: str = None):
	"""
	Fábrica de engines SQLAlchemy con configuración segura.
	- SQLite: activa check_same_thread=False para uso con tkinter.
	- Otros motores: configura pool_size, max_overflow y pool_recycle.
	"""
	target = url or DB_URL
	kwargs = {'pool_recycle': 3600}

	if target.startswith('sqlite'):
		kwargs['connect_args'] = {'check_same_thread': False}
	else:
		kwargs['pool_size'] = 5
		kwargs['max_overflow'] = 10

	return create_engine(target, **kwargs)
