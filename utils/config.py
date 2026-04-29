import os

from sqlalchemy import create_engine

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass

# ──────────────────────────────────────────────────────
# Configuración centralizada de la aplicación
# Lee desde variables de entorno; valores por defecto
# solo para desarrollo local. En producción define
# DATABASE_URL y SECRET_SALT en un archivo .env
# ──────────────────────────────────────────────────────

DB_URL = os.getenv('DATABASE_URL', 'sqlite:///pos_system.db')
SECRET_SALT = os.getenv('SECRET_SALT', 'CloudPOS_SaaS_2026_Secreto_X99')


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
		# Configuración robusta para bases de datos en red
		kwargs['pool_size'] = 10  # Cantidad de conexiones simultáneas por defecto
		kwargs['max_overflow'] = 20  # Conexiones extra permitidas en picos de uso
		kwargs['pool_recycle'] = 3600
		kwargs['pool_pre_ping'] = True

	return create_engine(target, **kwargs)
