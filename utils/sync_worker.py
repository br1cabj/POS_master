"""
utils/sync_worker.py
====================
Background thread that pushes local SQLite changes to Supabase (PostgreSQL).

Architecture
------------
- Runs as a daemon thread alongside the Tkinter UI; never blocks the UI.
- On each cycle it finds rows where `updated_at >= last_sync_time` for each
  synced table and upserts them into the cloud database via SQLAlchemy.
- Sync state (last_sync_time per table) is persisted in AppData so it
  survives restarts.
- Fails silently on network / credential errors and retries on the next tick.

To enable: set DATABASE_CLOUD_URL in .env and restart the app.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from utils.config import CLOUD_SYNC_INTERVAL, get_cloud_engine, get_engine

_SYNC_BATCH_SIZE = 500

logger = logging.getLogger(__name__)


# ─── tables to sync (dependency order: parents before children) ───────────────
# Import lazily inside functions to avoid circular-import issues at module load.

_CASH_SYNC_DAYS = 7  # ventana máxima de historial de caja sincronizado a la nube


def _sync_models():
    from database.models import (
        Article,
        ArticleVariant,
        Branch,
        CashMovement,
        CashSession,
        Customer,
        Promotion,
        Purchase,
        Sale,
        SaleDetail,
        Stock,
        Supplier,
        Tenant,
        User,
        Warehouse,
    )
    # Order matters: parents must be pushed before children to satisfy FKs.
    return [
        Tenant,
        Branch,
        Warehouse,
        User,
        Supplier,
        Article,
        ArticleVariant,
        Customer,
        Purchase,
        Sale,
        SaleDetail,
        Stock,
        Promotion,
        CashSession,   # 7-day window enforced in _cycle()
        CashMovement,  # 7-day window enforced in _cycle()
    ]


# ─── state persistence ─────────────────────────────────────────────────────────

def _state_file() -> Path:
    from utils.settings_manager import _app_data_dir
    return _app_data_dir() / 'sync_state.json'


def _load_state() -> dict:
    f = _state_file()
    if f.exists():
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    try:
        _state_file().write_text(
            json.dumps(state, default=str, indent=2), encoding='utf-8'
        )
    except Exception as e:
        logger.warning('Could not persist sync state: %s', e)


# ─── row serialization ─────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convert an ORM instance to a plain dict (column values only, no rels)."""
    mapper = sa_inspect(type(row))
    result = {}
    for attr in mapper.column_attrs:
        val = getattr(row, attr.key)
        # Convert Decimal to str so psycopg2 binds NUMERIC columns without
        # floating-point precision loss (float(Decimal('10.15')) ≠ 10.15 exactly).
        from decimal import Decimal as _Decimal
        if isinstance(val, _Decimal):
            val = str(val)
        result[attr.key] = val
    return result


# ─── cloud upsert ──────────────────────────────────────────────────────────────

def _upsert_batch(cloud_session, model, rows: list[dict]) -> int:
    """
    Upsert a batch of rows into the cloud PostgreSQL table.
    Uses `INSERT … ON CONFLICT DO UPDATE` so re-running is idempotent.
    Returns the number of rows processed.
    """
    if not rows:
        return 0

    table = model.__table__
    pk_names = {col.name for col in table.primary_key.columns}

    stmt = pg_insert(table).values(rows)
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in table.columns
        if col.name not in pk_names
    }
    if update_cols:
        stmt = stmt.on_conflict_do_update(
            index_elements=list(pk_names),
            set_=update_cols,
        )
    else:
        stmt = stmt.on_conflict_do_nothing()

    cloud_session.execute(stmt)
    return len(rows)


# ─── sync worker ───────────────────────────────────────────────────────────────

class SyncWorker:
    """
    Manages the background sync thread.

    Usage (from main.py):
        worker = SyncWorker(db_engine)
        worker.start()          # no-op when cloud not configured
        ...
        worker.stop()           # called on window close
    """

    def __init__(self, local_engine=None):
        self._local_engine = local_engine or get_engine()
        self._LocalSession = sessionmaker(bind=self._local_engine)
        self._stop = threading.Event()
        self._cycle_lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name='CloudSyncWorker',
            daemon=True,
        )

    def start(self) -> None:
        if get_cloud_engine() is None:
            logger.info('Cloud sync disabled — DATABASE_CLOUD_URL not set.')
            return
        from controllers.cloud_license_controller import CloudLicenseController
        active, msg = CloudLicenseController().check_status()
        if not active:
            logger.info('Cloud sync disabled — no active cloud plan (%s).', msg)
            return
        self._thread.start()
        logger.info(
            'Cloud sync worker started (interval=%ds).', CLOUD_SYNC_INTERVAL
        )

    def stop(self) -> None:
        self._stop.set()

    # ── internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        # Brief startup delay so the app UI is fully loaded before first sync.
        self._stop.wait(timeout=15)

        while not self._stop.is_set():
            try:
                self._cycle()
            except Exception as e:
                logger.error('Sync cycle crashed: %s', e, exc_info=True)
            self._stop.wait(timeout=CLOUD_SYNC_INTERVAL)

    def _cycle(self) -> None:
        if not self._cycle_lock.acquire(blocking=False):
            logger.debug('Sync cycle already running, skipping.')
            return
        try:
            self._do_cycle()
        finally:
            self._cycle_lock.release()

    def _do_cycle(self) -> None:
        cloud_engine = get_cloud_engine()
        if cloud_engine is None:
            return

        # Guarantee the cloud schema exists (safe to call repeatedly).
        try:
            from database.migrations import setup_cloud_schema
            setup_cloud_schema(cloud_engine)
        except Exception as e:
            logger.error('Cannot set up cloud schema, skipping cycle: %s', e)
            return

        state = _load_state()
        CloudSession = sessionmaker(bind=cloud_engine)
        sync_time = datetime.now()
        total_pushed = 0

        with self._LocalSession() as local, CloudSession() as cloud:
            for model in _sync_models():
                if not hasattr(model, 'updated_at'):
                    continue

                table_name = model.__tablename__
                last_str = state.get(table_name)
                last_sync = (
                    datetime.fromisoformat(last_str)
                    if last_str
                    else datetime.min
                )

                # Cash tables: never push data older than 7 days to the cloud.
                if table_name in ('cash_sessions', 'cash_movements'):
                    cutoff = sync_time - timedelta(days=_CASH_SYNC_DAYS)
                    if last_sync < cutoff:
                        last_sync = cutoff

                try:
                    rows_q = (
                        local.query(model)
                        .filter(model.updated_at >= last_sync)
                        .order_by(model.updated_at)
                        .limit(_SYNC_BATCH_SIZE)
                        .all()
                    )
                except Exception as e:
                    logger.error('Could not query %s: %s', table_name, e)
                    continue

                if not rows_q:
                    state[table_name] = sync_time.isoformat()
                    continue

                data = [_row_to_dict(r) for r in rows_q]

                try:
                    pushed = _upsert_batch(cloud, model, data)
                    # Commit each table independently so a failure in one table
                    # only rolls back that table, not all previously synced data.
                    cloud.commit()
                    total_pushed += pushed
                    # Only advance the watermark when the batch was smaller than the
                    # limit — if we hit the limit there may be more rows to process,
                    # so keep the same last_sync so the next cycle re-queries them.
                    if len(rows_q) < _SYNC_BATCH_SIZE:
                        state[table_name] = sync_time.isoformat()
                    logger.debug('Synced %d rows → %s', pushed, table_name)
                except Exception as e:
                    logger.error('Upsert failed for %s: %s', table_name, e)
                    cloud.rollback()
                    # Don't update state for this table so it retries next cycle.

        if total_pushed:
            logger.info('Sync complete: %d rows pushed to Supabase.', total_pushed)

        _save_state(state)

    # ── public helpers ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def force_sync(self) -> None:
        """Trigger an immediate sync cycle in a background thread (non-blocking)."""
        threading.Thread(target=self._cycle, daemon=True, name='ForcedSync').start()
