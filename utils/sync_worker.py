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

from sqlalchemy import and_, inspect as sa_inspect, or_
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
		ArticleHistory,
		ArticleVariant,
		Branch,
		CashMovement,
		CashSession,
		Category,
		ComboItem,
		Customer,
		Promotion,
		Purchase,
		PurchaseDetail,
		PurchaseReturn,
		PurchaseReturnItem,
		Quotation,
		QuotationItem,
		Sale,
		SaleDetail,
		Stock,
		StockMovement,
		Supplier,
		Tenant,
		User,
		Warehouse,
	)

	# Order matters: parents must be inserted before children to satisfy FKs.
	return [
		Tenant,
		Branch,
		Warehouse,
		User,
		Supplier,
		Category,
		Article,
		ArticleVariant,
		ArticleHistory,  # child of User/Tenant/ArticleVariant
		ComboItem,  # child of ArticleVariant
		Customer,
		Purchase,
		PurchaseDetail,  # child of Purchase
		PurchaseReturn,  # child of Purchase
		PurchaseReturnItem,  # child of PurchaseReturn
		Sale,
		SaleDetail,
		Quotation,  # child of Tenant/User/Customer
		QuotationItem,  # child of Quotation/ArticleVariant
		Stock,
		StockMovement,  # child of Tenant/Warehouse/ArticleVariant/User
		Promotion,
		CashSession,  # 7-day window enforced in _cycle()
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
		except Exception as e:
			logger.error('sync_state.json corrupted, resetting watermarks: %s', e)
	return {}


def _save_state(state: dict) -> None:
	try:
		_state_file().write_text(
			json.dumps(state, default=str, indent=2), encoding='utf-8'
		)
	except Exception as e:
		logger.warning('Could not persist sync state: %s', e)


def _read_cursor(value) -> tuple[datetime, str]:
	"""Read both legacy timestamp watermarks and the lossless v2 cursor."""
	if isinstance(value, dict):
		try:
			return datetime.fromisoformat(value['updated_at']), str(value.get('id', ''))
		except (KeyError, TypeError, ValueError):
			return datetime.min, ''
	if value:
		try:
			return datetime.fromisoformat(value), ''
		except (TypeError, ValueError):
			logger.warning('Invalid sync cursor %r; replaying table safely.', value)
	return datetime.min, ''


def _write_cursor(state: dict, table_name: str, row) -> None:
	"""Persist a total ordering cursor, not only a possibly duplicated timestamp."""
	state[table_name] = {'updated_at': row.updated_at.isoformat(), 'id': str(row.id)}


def _rows_after_cursor(query, model, cursor_time: datetime, cursor_id: str):
	"""Return rows strictly after ``(updated_at, id)`` in a deterministic order."""
	return (
		query.filter(
			or_(
				model.updated_at > cursor_time,
				and_(model.updated_at == cursor_time, model.id > cursor_id),
			)
		)
		.order_by(model.updated_at, model.id)
		.limit(_SYNC_BATCH_SIZE)
	)


# ─── row serialization ─────────────────────────────────────────────────────────


# Fields that must never be uploaded to the cloud.
_CLOUD_EXCLUDED_FIELDS = frozenset()


def _row_to_dict(row) -> dict:
	"""Convert an ORM instance to a plain dict (column values only, no rels)."""
	mapper = sa_inspect(type(row))
	result = {}
	for attr in mapper.column_attrs:
		if attr.key in _CLOUD_EXCLUDED_FIELDS:
			continue
		val = getattr(row, attr.key)
		# Decimal objects are passed through as-is; psycopg2/SQLAlchemy
		# correctly map them to PostgreSQL NUMERIC without precision loss.
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
		self._state_lock = threading.Lock()
		# Estado de la última sincronización (leído desde el hilo principal para el indicador)
		self.last_sync_ok: bool | None = None  # None = nunca sincronizó
		self.last_sync_time: datetime | None = None
		self.last_sync_error: str = ''

	def start(self) -> None:
		if get_cloud_engine() is None:
			logger.info('Cloud sync disabled — DATABASE_CLOUD_URL not set.')
			return
		from controllers.cloud_license_controller import CloudLicenseController

		active, msg = CloudLicenseController().check_status()
		if not active:
			logger.info('Cloud sync disabled — no active cloud plan (%s).', msg)
			return
		if not self._thread.is_alive():
			self._stop.clear()
			self._thread.start()
			logger.info('Cloud sync worker started (interval=%ds).', CLOUD_SYNC_INTERVAL)

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
		# Verify cloud plan is still active before each cycle.
		# Handles expiry while the app is running without requiring a restart.
		from controllers.cloud_license_controller import CloudLicenseController

		active, reason = CloudLicenseController().check_status()
		if not active:
			with self._state_lock:
				self.last_sync_ok = False
				self.last_sync_error = reason
			logger.info('Sync skipped — cloud plan not active: %s', reason)
			return

		cloud_engine = get_cloud_engine()
		if cloud_engine is None:
			return

		# Guarantee the cloud schema exists (safe to call repeatedly).
		try:
			from database.migrations import setup_cloud_schema

			setup_cloud_schema(cloud_engine)
		except Exception as e:
			logger.error('Cannot set up cloud schema, skipping cycle: %s', e)
			with self._state_lock:
				self.last_sync_ok = False
				self.last_sync_error = str(e)
			return

		state = _load_state()
		CloudSession = sessionmaker(bind=cloud_engine)
		sync_time = datetime.now()
		total_pushed = 0
		had_error = False

		with self._LocalSession() as local, CloudSession() as cloud:
			for model in _sync_models():
				if not hasattr(model, 'updated_at'):
					continue

				table_name = model.__tablename__
				last_sync, last_id = _read_cursor(state.get(table_name))

				# Cash tables: never push data older than 7 days to the cloud.
				if table_name in ('cash_sessions', 'cash_movements'):
					cutoff = sync_time - timedelta(days=_CASH_SYNC_DAYS)
					if last_sync < cutoff:
						last_sync = cutoff
						last_id = ''

				# Pre-sync parent tables to avoid FK violations.
				# For example, article_variants needs its article to exist first.
				self._ensure_parents_synced(local, cloud, model, state)

				try:
					rows_q = _rows_after_cursor(
						local.query(model), model, last_sync, last_id
					).all()
				except Exception as e:
					logger.error('Could not query %s: %s', table_name, e)
					continue

				if not rows_q:
					continue

				data = [_row_to_dict(r) for r in rows_q]

				try:
					pushed = _upsert_batch(cloud, model, data)
					# Commit each table independently so a failure in one table
					# only rolls back that table, not all previously synced data.
					cloud.commit()
					total_pushed += pushed
					# Always advance to the last ordered row.  A timestamp alone is not a
					# cursor: many rows can share it, so the primary key is persisted too.
					_write_cursor(state, table_name, rows_q[-1])
					logger.debug('Synced %d rows → %s', pushed, table_name)
				except Exception as e:
					logger.error('Upsert failed for %s: %s', table_name, e)
					cloud.rollback()
					had_error = True
					self.last_sync_error = f'{table_name}: {e}'
					# Don't update state for this table so it retries next cycle.

		if total_pushed:
			logger.info('Sync complete: %d rows pushed to Supabase.', total_pushed)

		_save_state(state)
		with self._state_lock:
			if not had_error:
				self.last_sync_ok = True
				self.last_sync_time = datetime.now()
				self.last_sync_error = ''
			else:
				self.last_sync_ok = False

	def _ensure_parents_synced(self, local_session, cloud_session, model, state) -> None:
		"""
		Before syncing a child table, ensure its parent table(s) are also synced.
		This prevents FK violations when the parent row hasn't been pushed yet.
		"""
		_TABLE_PARENTS = {
			'article_variants': ['articles'],
			'article_history': ['articles', 'users'],
			'stocks': ['article_variants', 'warehouses'],
			'stock_movements': ['article_variants', 'warehouses', 'users'],
			'sale_details': ['sales', 'article_variants'],
			'purchase_details': ['purchases', 'article_variants'],
			'purchase_return_items': ['purchase_returns', 'article_variants'],
			'quotation_items': ['quotations', 'article_variants'],
			'combo_items': ['article_variants'],
			'cash_movements': ['cash_sessions', 'users'],
		}

		table_name = model.__tablename__
		parent_names = _TABLE_PARENTS.get(table_name, [])
		if not parent_names:
			return

		parent_models = {m.__tablename__: m for m in _sync_models()}
		synced_this_cycle = set()

		for parent_name in parent_names:
			if parent_name not in parent_models:
				continue
			if parent_name in synced_this_cycle:
				continue

			parent_model = parent_models[parent_name]
			if not hasattr(parent_model, 'updated_at'):
				continue

			parent_table = parent_model.__tablename__
			last_sync, last_id = _read_cursor(state.get(parent_table))

			parent_rows = _rows_after_cursor(
				local_session.query(parent_model), parent_model, last_sync, last_id
			).all()

			if not parent_rows:
				continue

			parent_data = [_row_to_dict(r) for r in parent_rows]
			try:
				_upsert_batch(cloud_session, parent_model, parent_data)
				cloud_session.commit()
				synced_this_cycle.add(parent_table)
				_write_cursor(state, parent_table, parent_rows[-1])
				logger.debug('Pre-synced %d parent rows → %s', len(parent_rows), parent_table)
			except Exception as e:
				logger.warning('Pre-sync failed for %s: %s', parent_table, e)
				cloud_session.rollback()

	# ── public helpers ────────────────────────────────────────────────────────

	@property
	def is_running(self) -> bool:
		return self._thread.is_alive()

	def force_sync(self) -> None:
		"""Trigger an immediate sync cycle in a background thread (non-blocking)."""
		threading.Thread(target=self._cycle, daemon=True, name='ForcedSync').start()
