import os
import sys
import threading
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass


def _app_dir() -> Path:
	"""Project root in dev, executable directory when frozen."""
	if getattr(sys, 'frozen', False):
		return Path(sys.executable).parent
	return Path(__file__).parent.parent


SECRET_SALT = 'aantesbajocabeconcontradedesdeenentrehaciahastaparaporsegunsinsobretrasmediantedurante'

# ── Local database ────────────────────────────────────────────────────────────
_default_db = f'sqlite:///{_app_dir() / "pos_system.db"}'
DB_URL = os.getenv('DATABASE_URL', _default_db)

# ── Optional Cloud add-on ───────────────────────────────────────────────────
# The desktop never receives PostgreSQL credentials.  It publishes its local
# reporting replica to the VPS through the authenticated Sync API only.
CLOUDPOS_SYNC_API_URL = os.getenv('CLOUDPOS_SYNC_API_URL', '').strip().rstrip('/')
CLOUDPOS_DEVICE_TOKEN = os.getenv('CLOUDPOS_DEVICE_TOKEN', '').strip()
# Compatibility only: desktop code must not use a cloud DB connection.
DATABASE_CLOUD_URL = ''

# True when cloud sync is configured and should run.
CLOUD_SYNC_ENABLED = bool(CLOUDPOS_SYNC_API_URL and CLOUDPOS_DEVICE_TOKEN)

# How often the background worker syncs (seconds). Default: 5 minutes.
try:
	CLOUD_SYNC_INTERVAL = max(30, int(os.getenv('CLOUD_SYNC_INTERVAL', '300')))
except ValueError:
	CLOUD_SYNC_INTERVAL = 300


@event.listens_for(Engine, 'connect')
def _configure_connection(dbapi_conn, _):
	"""Apply SQLite PRAGMAs only to SQLite connections, skip PostgreSQL."""
	if type(dbapi_conn).__module__ != 'sqlite3':
		return
	try:
		dbapi_conn.execute('PRAGMA foreign_keys=ON')
		dbapi_conn.execute('PRAGMA journal_mode=WAL')
		dbapi_conn.execute('PRAGMA synchronous=NORMAL')
		dbapi_conn.execute('PRAGMA cache_size=-32000')
		dbapi_conn.execute('PRAGMA temp_store=MEMORY')
	except Exception:
		pass


def make_engine(url: str = None) -> Engine:
	"""
	SQLAlchemy engine factory.
	- SQLite: disables same-thread check (required by Tkinter's thread model).
	- PostgreSQL: configures connection pool for concurrent access.
	"""
	target = url or DB_URL
	kwargs: dict = {}

	if target.startswith('sqlite'):
		kwargs['connect_args'] = {'check_same_thread': False}
	else:
		kwargs['pool_size'] = 10
		kwargs['max_overflow'] = 20
		kwargs['pool_recycle'] = 3600
		kwargs['pool_pre_ping'] = True

	return create_engine(target, **kwargs)


_shared_engine: Engine | None = None
_engine_lock = threading.Lock()


def get_engine(url: str = None) -> Engine:
	"""Returns the shared local (SQLite) engine — singleton."""
	global _shared_engine
	with _engine_lock:
		if _shared_engine is None:
			_shared_engine = make_engine(url)
		return _shared_engine


def get_cloud_engine() -> None:
	"""Removed by design: CloudPOS desktop never opens the VPS database."""
	return None

