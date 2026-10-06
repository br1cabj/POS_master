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

# ── Cloud / Supabase ──────────────────────────────────────────────────────────
# Never embed a database URI (even obfuscated) in a distributable client.  A
# missing value deliberately keeps sync disabled, as documented in .env.example.
DATABASE_CLOUD_URL = os.getenv('DATABASE_CLOUD_URL', '').strip()

# Supabase REST API (used by the UI for status checks and future realtime).
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

# True when cloud sync is configured and should run.
CLOUD_SYNC_ENABLED = bool(DATABASE_CLOUD_URL)

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


def make_cloud_engine() -> Engine | None:
	"""
	Creates a PostgreSQL engine pointing at Supabase.
	Returns None when DATABASE_CLOUD_URL is not set.
	Uses a smaller pool than the local engine since sync is background-only.
	"""
	if not DATABASE_CLOUD_URL:
		return None
	return create_engine(
		DATABASE_CLOUD_URL,
		pool_size=3,
		max_overflow=5,
		pool_recycle=1800,
		pool_pre_ping=True,
		pool_timeout=15,
	)


_shared_engine: Engine | None = None
_cloud_engine: Engine | None = None
_engine_lock = threading.Lock()
_cloud_engine_lock = threading.Lock()


def get_engine(url: str = None) -> Engine:
	"""Returns the shared local (SQLite) engine — singleton."""
	global _shared_engine
	with _engine_lock:
		if _shared_engine is None:
			_shared_engine = make_engine(url)
		return _shared_engine


def get_cloud_engine() -> Engine | None:
	"""
	Returns the shared cloud (PostgreSQL/Supabase) engine — singleton.
	Returns None when DATABASE_CLOUD_URL is not configured.
	"""
	global _cloud_engine
	with _cloud_engine_lock:
		if _cloud_engine is None and DATABASE_CLOUD_URL:
			_cloud_engine = make_cloud_engine()
		return _cloud_engine
