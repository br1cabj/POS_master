import os
import sys
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
_C = b'\x11\x0e\x1d\x00\x02\x01\x07\x12\x1b\x03YNM\x15\x0c\x1c\x1a\x04\x1d\x0b\x07H$\x08(+])\x01\x10-($\x1a \x16\x13*!\x07\x0bO\x0b\x08\x11\x1b\x15\x02\x08\n\t\x12\x1c\x01\x19\x16\x1e\x16\x0b\x1d\x02\x04]\x1c\x17\x02\x04\x16\x13\x12\x16C\x06\x0bSTZGWK\x05\x1d\x12\x1a\x13\x17\x04\x12'
_r = lambda d, k: ''.join(chr(b ^ ord(k[i % len(k)])) for i, b in enumerate(d))
DATABASE_CLOUD_URL = os.getenv('DATABASE_CLOUD_URL', _r(_C, SECRET_SALT))

# Supabase REST API (used by the UI for status checks and future realtime).
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

# True when cloud sync is configured and should run.
CLOUD_SYNC_ENABLED = bool(DATABASE_CLOUD_URL)

# How often the background worker syncs (seconds). Default: 5 minutes.
CLOUD_SYNC_INTERVAL = int(os.getenv('CLOUD_SYNC_INTERVAL', '300'))


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


def get_engine(url: str = None) -> Engine:
    """Returns the shared local (SQLite) engine — singleton."""
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = make_engine(url)
    return _shared_engine


def get_cloud_engine() -> Engine | None:
    """
    Returns the shared cloud (PostgreSQL/Supabase) engine — singleton.
    Returns None when DATABASE_CLOUD_URL is not configured.
    """
    global _cloud_engine
    if _cloud_engine is None and DATABASE_CLOUD_URL:
        _cloud_engine = make_cloud_engine()
    return _cloud_engine
