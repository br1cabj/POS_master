import os
import threading
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from utils.app_paths import adopt_legacy_file, app_data_dir

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass


SECRET_SALT = 'aantesbajocabeconcontradedesdeenentrehaciahastaparaporsegunsinsobretrasmediantedurante'

# ── Local database ────────────────────────────────────────────────────────────
_default_db = f'sqlite:///{app_data_dir(create=False) / "pos_system.db"}'


def _resolve_database_url(value: str) -> str:
	# Earlier .env templates included this relative URL. Adopt that default too,
	# otherwise upgrading those installations would still write to Program Files.
	configured = value.strip()
	if configured in (
		'',
		'sqlite:///pos_system.db',
		'sqlite+pysqlite:///pos_system.db',
	):
		return _default_db
	return configured


DB_URL = _resolve_database_url(os.getenv('DATABASE_URL', ''))


def get_local_database_path(url=None) -> Path:
	"""Resolve the same SQLite file used by controllers, startup and backups."""
	parsed = make_url(url or DB_URL)
	if (
		parsed.get_backend_name() != 'sqlite'
		or not parsed.database
		or parsed.database == ':memory:'
		or parsed.database.startswith('file:')
	):
		raise ValueError(
			'Esta operación requiere una base SQLite local guardada en un archivo.'
		)
	return Path(parsed.database).expanduser().resolve()


def prepare_local_database() -> Path:
	"""Adopt older default installations without replacing an existing database."""
	path = get_local_database_path()
	path.parent.mkdir(parents=True, exist_ok=True)
	if DB_URL == _default_db:
		adopt_legacy_file('pos_system.db', database=True)
	return path


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

	if make_url(target).get_backend_name() == 'sqlite':
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
			if url is None:
				prepare_local_database()
			_shared_engine = make_engine(url)
		return _shared_engine


def get_cloud_engine() -> None:
	"""Removed by design: CloudPOS desktop never opens the VPS database."""
	return None
