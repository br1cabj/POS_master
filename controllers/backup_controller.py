"""
controllers/backup_controller.py
=================================
Respaldo y restauración de la base de datos local (SQLite).

- create_backup()       → copia consistente via API de SQLite (maneja WAL sin cerrar engine)
- restore_backup()      → reemplaza pos_system.db y descarta el pool de conexiones
- restore_from_cloud()  → baja datos de Supabase y reconstruye la BD local
- auto_backup_if_needed() → corre en hilo daemon, una vez por día
"""

import logging
import sqlite3
import sys
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

_LAST_BACKUP_KEY = 'last_backup'
_MAX_BACKUPS = 15


def _settings_set(key: str, value) -> None:
	# BUG 20: usar settings_manager.set() para beneficiarse del lock thread-safe
	from utils import settings_manager

	settings_manager.set(key, value)


class BackupController:
	def __init__(self, db_engine=None):
		self._engine = db_engine

	# ── rutas ─────────────────────────────────────────────────────────────────

	@staticmethod
	def _db_path() -> Path:
		if getattr(sys, 'frozen', False):
			return Path(sys.executable).parent / 'pos_system.db'
		return Path(__file__).parent.parent / 'pos_system.db'

	@staticmethod
	def backup_dir() -> Path:
		from utils.settings_manager import _app_data_dir

		d = _app_data_dir() / 'backups'
		d.mkdir(parents=True, exist_ok=True)
		return d

	# ── estado ────────────────────────────────────────────────────────────────

	@staticmethod
	def get_last_backup_str() -> str | None:
		from utils.settings_manager import get

		return get(_LAST_BACKUP_KEY, None)

	def list_backups(self) -> list[Path]:
		return sorted(self.backup_dir().glob('backup_*.db'), reverse=True)

	# ── backup ────────────────────────────────────────────────────────────────

	def create_backup(self) -> tuple[bool, str]:
		"""
		Crea un respaldo usando la API nativa de SQLite.
		No requiere cerrar el engine — maneja WAL correctamente.
		Retorna (ok, timestamp_legible | mensaje_error).
		"""
		db = self._db_path()
		if not db.exists():
			return False, 'No se encontró la base de datos local.'

		try:
			timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
			dest = self.backup_dir() / f'backup_{timestamp}.db'

			src = sqlite3.connect(str(db))
			dst = sqlite3.connect(str(dest))
			src.backup(dst)
			dst.close()
			src.close()

			# Conservar solo los últimos _MAX_BACKUPS
			all_backups = sorted(self.backup_dir().glob('backup_*.db'))
			for old in all_backups[:-_MAX_BACKUPS]:
				try:
					old.unlink()
				except Exception as e:
					logger.warning('No se pudo eliminar backup antiguo %s: %s', old, e)

			now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
			_settings_set(_LAST_BACKUP_KEY, now_str)
			logger.info('Backup creado: %s', dest)
			return True, now_str

		except Exception as e:
			logger.error('Backup falló: %s', e)
			return False, str(e)

	def auto_backup_if_needed(self) -> None:
		"""Lanza un backup en hilo daemon si no hubo uno en las últimas 24 h."""
		last = self.get_last_backup_str()
		if last:
			try:
				last_dt = datetime.strptime(last, '%d/%m/%Y %H:%M')
				if (datetime.now() - last_dt).total_seconds() < 86400:
					return
			except ValueError:
				pass
		threading.Thread(
			target=self.create_backup, daemon=True, name='AutoBackup'
		).start()

	# ── restore ───────────────────────────────────────────────────────────────

	def restore_from_cloud(self, progress_cb=None) -> tuple[bool, str]:
		"""
		Pull all synced tables from Supabase and overwrite the local SQLite database.

		Design goals:
		- Filtered by tenant_id so shared Supabase data stays isolated.
		- Cash tables limited to the last 7 days (mirrors sync policy).
		- Server-side subqueries for child tables — no large IN lists over the wire.
		- Native sqlite3 with bulk PRAGMAs for fast local write.
		- Safety backup created before any write; auto-rollback on failure.
		"""
		from datetime import timedelta

		from sqlalchemy import select

		from utils.config import get_cloud_engine, get_engine

		def _report(m: str):
			logger.info('CloudRestore: %s', m)
			if progress_cb:
				try:
					progress_cb(m)
				except Exception:
					pass

		cloud_engine = get_cloud_engine()
		if cloud_engine is None:
			return False, 'La nube no está configurada.'

		from controllers.cloud_license_controller import CloudLicenseController

		ctrl = CloudLicenseController()
		active, msg = ctrl.check_status()
		if not active:
			return False, f'Plan cloud inactivo: {msg}'

		tenant_id = ctrl.get_tenant_id()
		if not tenant_id:
			return False, 'No se encontró el Tenant ID en la licencia cloud.'

		from utils.sync_worker import _sync_models

		models = _sync_models()
		model_by_name = {m.__tablename__: m for m in models}

		cash_cutoff = datetime.now() - timedelta(days=7)
		BATCH = 1000

		# ── Pull from Supabase ──────────────────────────────────────────────────
		_report('Conectando a Supabase…')
		collected: dict[str, list[dict]] = {}

		try:
			with cloud_engine.connect() as cloud:
				for model in models:
					tname = model.__tablename__
					table = model.__table__

					# Build tenant-scoped WHERE clause.
					# Child tables use a correlated subquery to avoid sending
					# thousands of IDs over the wire.
					if tname == 'tenants':
						base_where = table.c.id == tenant_id
					elif hasattr(table.c, 'tenant_id'):
						base_where = table.c.tenant_id == tenant_id
					elif tname == 'article_variants':
						arts = model_by_name['articles'].__table__
						sub = (
							select(arts.c.id)
							.where(arts.c.tenant_id == tenant_id)
							.scalar_subquery()
						)
						base_where = table.c.article_id.in_(sub)
					elif tname == 'sale_details':
						sales = model_by_name['sales'].__table__
						sub = (
							select(sales.c.id)
							.where(sales.c.tenant_id == tenant_id)
							.scalar_subquery()
						)
						base_where = table.c.sale_id.in_(sub)
					elif tname == 'stocks':
						whs = model_by_name['warehouses'].__table__
						sub = (
							select(whs.c.id)
							.where(whs.c.tenant_id == tenant_id)
							.scalar_subquery()
						)
						base_where = table.c.warehouse_id.in_(sub)
					elif tname == 'cash_movements':
						sess = model_by_name['cash_sessions'].__table__
						sub = (
							select(sess.c.id)
							.where(sess.c.tenant_id == tenant_id)
							.where(sess.c.updated_at >= cash_cutoff)
							.scalar_subquery()
						)
						base_where = table.c.session_id.in_(sub)
					else:
						base_where = None

					stmt = select(table)
					if base_where is not None:
						stmt = stmt.where(base_where)
					# Cash 7-day window
					if tname in ('cash_sessions', 'cash_movements') and hasattr(
						table.c, 'updated_at'
					):
						stmt = stmt.where(table.c.updated_at >= cash_cutoff)

					# LIMIT/OFFSET pagination
					rows_all: list[dict] = []
					offset = 0
					while True:
						result = cloud.execute(stmt.limit(BATCH).offset(offset))
						page = [dict(r._mapping) for r in result]
						rows_all.extend(page)
						if len(page) < BATCH:
							break
						offset += BATCH

					collected[tname] = rows_all
					_report(f'{tname}: {len(rows_all)} registros descargados')

		except Exception as e:
			logger.error('Error descargando de Supabase: %s', e, exc_info=True)
			return False, f'Error de conexión a la nube: {e}'

		# ── Safety backup ───────────────────────────────────────────────────────
		_report('Creando copia de seguridad local…')
		db = self._db_path()
		if not db.exists():
			return False, 'No se encontró la base de datos local.'

		safety = db.parent / '_pre_cloud_restore.db'
		try:
			src = sqlite3.connect(str(db))
			saf = sqlite3.connect(str(safety))
			src.backup(saf)
			saf.close()
			src.close()
		except Exception as e:
			return False, f'No se pudo crear respaldo de seguridad: {e}'

		# Dispose SQLAlchemy pool so sqlite3 can write freely
		if self._engine:
			self._engine.dispose()
		try:
			get_engine().dispose()
		except Exception:
			pass

		# BUG 9: abortar si no se descargó NINGÚN dato — indica problema de conexión
		# o de tenant ID, no un tenant vacío (que tendría al menos su propio registro)
		if not any(rows for rows in collected.values()):
			return False, (
				'No se descargaron datos de la nube. '
				'Verificá la conexión y el Tenant ID antes de restaurar.'
			)

		# ── Write to local SQLite ───────────────────────────────────────────────
		_report('Escribiendo datos en la base local…')

		def _coerce(v):
			"""Normalize PostgreSQL types to sqlite3-compatible primitives."""
			if v is None:
				return None
			if isinstance(v, bool):
				return int(v)
			if isinstance(v, Decimal):
				return str(v)
			if isinstance(v, datetime):
				return v.isoformat()
			if isinstance(v, date):
				return v.isoformat()
			return v

		con = None
		con = sqlite3.connect(str(db))
		try:
			con.execute('PRAGMA foreign_keys=OFF')
			con.execute('PRAGMA synchronous=OFF')
			con.execute('PRAGMA journal_mode=WAL')
			con.execute('PRAGMA cache_size=-65536')  # 64 MB page cache

			# Clear synced tables in reverse FK order
			for model in reversed(models):
				con.execute(f'DELETE FROM "{model.__tablename__}"')

			# Bulk-insert in FK order (parents first)
			for model in models:
				tname = model.__tablename__
				rows = collected.get(tname, [])
				if not rows:
					continue
				columns = list(rows[0].keys())
				col_clause = ', '.join(f'"{c}"' for c in columns)
				placeholders = ', '.join('?' * len(columns))
				sql = f'INSERT OR REPLACE INTO "{tname}" ({col_clause}) VALUES ({placeholders})'
				data = [tuple(_coerce(row[c]) for c in columns) for row in rows]
				con.executemany(sql, data)
				_report(f'  ✓ {tname}: {len(rows)} filas')

			con.commit()
			con.execute('PRAGMA synchronous=NORMAL')
			logger.info('Restauración desde la nube completada.')

		except Exception as e:
			logger.error('Error escribiendo en SQLite: %s', e, exc_info=True)
			# Roll back via safety copy
			try:
				src = sqlite3.connect(str(safety))
				dst = sqlite3.connect(str(db))
				src.backup(dst)
				dst.close()
				src.close()
				logger.info('Revertido al respaldo de seguridad tras fallo.')
			except Exception as rb_err:
				logger.error('Rollback de seguridad también falló: %s', rb_err)
			return False, f'Error al escribir datos: {e}'
		finally:
			if con is not None:
				try:
					con.execute('PRAGMA foreign_keys=ON')
					con.close()
				except Exception:
					pass

		return True, 'OK'

	def restore_backup(self, backup_path: str) -> tuple[bool, str]:
		"""
		Restaura un respaldo sobre pos_system.db.
		Guarda una copia de seguridad del estado actual antes de sobreescribir.
		El caller debe reiniciar la app después de llamar a este método.
		"""
		src = Path(backup_path)
		if not src.exists():
			return False, 'El archivo de respaldo no existe.'

		db = self._db_path()
		try:
			# Copia de seguridad del estado actual antes de restaurar
			safety = db.parent / '_pre_restore.db'
			cur = sqlite3.connect(str(db))
			saf = sqlite3.connect(str(safety))
			cur.backup(saf)
			saf.close()
			cur.close()

			# Descartar el pool de SQLAlchemy antes de reemplazar el archivo
			if self._engine:
				self._engine.dispose()

			# Restaurar
			bk = sqlite3.connect(str(src))
			dst = sqlite3.connect(str(db))
			bk.backup(dst)
			dst.close()
			bk.close()

			logger.info('Base restaurada desde %s', src)
			return True, 'OK'

		except Exception as e:
			logger.error('Restauración fallida: %s', e)
			return False, str(e)
