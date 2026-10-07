"""
utils/settings_manager.py
=========================
Persistencia ligera de configuración del negocio en settings.json.
Carga valores por defecto si el archivo no existe o está corrupto.
"""

import json
import logging
import os
import sys
import tempfile
import threading
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

# BUG 11: lock para que load()+save() sean atómicos entre hilos
# (hilo de backup y hilo de UI pueden escribir simultáneamente)
_settings_lock = threading.RLock()


def _app_data_dir() -> Path:
	"""Devuelve el directorio seguro para guardar datos (Appdata/Local o ~/.config)."""
	if sys.platform == 'win32':
		base_dir = Path(os.getenv('LOCALAPPDATA', os.path.expanduser('~')))
	else:
		base_dir = Path(os.path.expanduser('~')) / '.config'

	app_folder = base_dir / 'CloudPOS'
	app_folder.mkdir(parents=True, exist_ok=True)
	return app_folder


def get_user_data_dir() -> str:
	"""Return the writable per-user directory used for local app assets/data."""
	return str(_app_data_dir())


def _as_bool(value, default=False) -> bool:
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(value)
	if isinstance(value, str):
		if value.strip().lower() in {'1', 'true', 'yes', 'si', 'sí', 'on'}:
			return True
		if value.strip().lower() in {'0', 'false', 'no', 'off', ''}:
			return False
	return default


def _normalize_settings(settings: dict | None) -> dict:
	"""Merge defaults and coerce persisted values to the types used at runtime."""
	merged = {**DEFAULTS, **(settings if isinstance(settings, dict) else {})}
	try:
		decimals = int(merged['currency_decimals'])
		merged['currency_decimals'] = decimals if decimals in (0, 2) else 0
	except (ValueError, TypeError):
		merged['currency_decimals'] = 0
	try:
		tax_rate = float(str(merged['tax_rate']).replace(',', '.'))
		merged['tax_rate'] = tax_rate if 0 <= tax_rate <= 100 else 0.0
	except (ValueError, TypeError):
		merged['tax_rate'] = 0.0
	try:
		merged['low_stock_threshold'] = max(0, int(merged['low_stock_threshold']))
	except (ValueError, TypeError):
		merged['low_stock_threshold'] = 5
	try:
		chars = int(merged['printer_ticket_chars'])
		merged['printer_ticket_chars'] = min(96, max(16, chars))
	except (ValueError, TypeError):
		merged['printer_ticket_chars'] = 48
	for key in ('scale_baud', 'barcode_baud', 'poledisplay_baud'):
		try:
			merged[key] = str(int(merged[key]))
		except (ValueError, TypeError):
			merged[key] = '9600'
	for key in ('require_customer', 'show_shortcuts_bar', 'scale_enabled', 'poledisplay_enabled'):
		merged[key] = _as_bool(merged.get(key), DEFAULTS[key])
	for key in (
		'company_name', 'company_address', 'company_phone', 'company_logo_path',
		'currency_symbol', 'price_list_a_name', 'price_list_b_name', 'reports_path',
		'printer_ticket_name', 'printer_label_name', 'scale_port', 'barcode_port',
		'barcode_prefix', 'cashdrawer_port', 'poledisplay_port',
		'poledisplay_line1', 'poledisplay_line2',
	):
		if not isinstance(merged.get(key), str):
			merged[key] = str(merged.get(key) or '')
	merged['currency_symbol'] = merged['currency_symbol'].strip()[:5] or '$'
	merged['price_list_a_name'] = merged['price_list_a_name'].strip()[:40] or 'Minorista'
	merged['price_list_b_name'] = merged['price_list_b_name'].strip()[:40] or 'Mayorista'
	for key, allowed, fallback in (
		('printer_ticket_type', {'58mm', '80mm'}, '80mm'),
		('label_output_mode', {'preview', 'printer'}, 'preview'),
		('scale_protocol', {'toledo', 'fairbanks', 'generic'}, 'toledo'),
		('barcode_mode', {'hid', 'serial'}, 'hid'),
		('barcode_suffix', {'none', 'CR', 'TAB', 'CRLF'}, 'CR'),
		('cashdrawer_connection', {'printer', 'com'}, 'printer'),
	):
		if merged.get(key) not in allowed:
			merged[key] = fallback
	return merged


# ── Archivo de configuración ──────────────────────────────────────────────────
_SETTINGS_FILE = _app_data_dir() / 'settings.json'

# ── Caché en memoria ──────────────────────────────────────────────────────────
_cached_settings: dict | None = None

# ── Valores por defecto ───────────────────────────────────────────────────────
DEFAULTS: dict = {
	# Empresa
	'company_name': 'Mi Negocio',
	'company_address': '',
	'company_phone': '',
	'company_logo_path': '',
	# Moneda
	'currency_symbol': '$',
	'currency_decimals': 0,  # 0 = enteros  |  2 = centavos
	# Ventas
	'tax_rate': 0.0,  # porcentaje, ej. 21.0
	'low_stock_threshold': 5,
	'require_customer': False,
	# UI
	'show_shortcuts_bar': True,
	# Dólar (Argentina)
	'dollar_type': 'blue',  # 'blue' | 'oficial' | 'mep'
	'dollar_rate': 0.0,
	'dollar_margin_pct': 30.0,
	# Rutas de salida
	'reports_path': '',
	# Listas de precios
	'price_list_a_name': 'Minorista',
	'price_list_b_name': 'Mayorista',
	# Periféricos — Impresora de tickets
	'printer_ticket_name': '',
	'printer_ticket_type': '80mm',  # '58mm' | '80mm'
	'printer_ticket_chars': 48,
	# Periféricos — Impresora de etiquetas
	'printer_label_name': '',
	# "preview" conserva el PDF para revisión; "printer" lo envía al driver de
	# Windows seleccionado. Nunca se mandan comandos ZPL a impresoras genéricas.
	'label_output_mode': 'preview',  # 'preview' | 'printer'
	# Periféricos — Balanza
	'scale_enabled': False,
	'scale_port': 'COM1',
	'scale_baud': '9600',
	'scale_protocol': 'toledo',  # 'toledo' | 'fairbanks' | 'generic'
	# Periféricos — Lector de código de barras
	'barcode_mode': 'hid',  # 'hid' | 'serial'
	'barcode_port': 'COM2',
	'barcode_baud': '9600',
	'barcode_prefix': '',
	'barcode_suffix': 'CR',  # 'none' | 'CR' | 'TAB' | 'CRLF'
	# Modo terminal
	'terminal_mode': 'primary',  # 'primary' | 'cashier'
	'db_remote_path': '',  # Ruta UNC al .db del principal (solo en modo cajero)
	# Periféricos — Cajón de dinero
	'cashdrawer_connection': 'printer',  # 'printer' | 'com'
	'cashdrawer_port': 'COM3',
	# Periféricos — Pantalla de cliente (pole display)
	'poledisplay_enabled': False,
	'poledisplay_port': 'COM4',
	'poledisplay_baud': '9600',
	'poledisplay_line1': 'Bienvenido!',
	'poledisplay_line2': '',
}


def load(force_reload: bool = False) -> dict:
	"""
	Devuelve una COPIA del dict de configuración desde el caché o el disco.
	Si force_reload es True, ignora el caché en memoria y fuerza la lectura del archivo.
	"""
	global _cached_settings

	with _settings_lock:
		if _cached_settings is not None and not force_reload:
			return _cached_settings.copy()

		try:
			if _SETTINGS_FILE.exists():
				with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
					saved = json.load(f)
				_cached_settings = _normalize_settings(saved)
				return _cached_settings.copy()
		except PermissionError as e:
			logger.error(f'Sin permisos para leer settings.json: {e}')
			# Si ya hay caché, usarlo; si no, lanzar error para que el llamador decida
			if _cached_settings is not None:
				return _cached_settings.copy()
			raise
		except json.JSONDecodeError as e:
			logger.error(f'settings.json está corrupto: {e}')
			# Hacer backup del archivo corrupto antes de usar defaults
			try:
				backup = _SETTINGS_FILE.with_suffix('.json.bak')
				_SETTINGS_FILE.rename(backup)
				logger.info(f'Backup de settings corrupto guardado en: {backup}')
			except Exception as bak_err:
				logger.warning(f'No se pudo hacer backup de settings.json: {bak_err}')
		except Exception as e:
			logger.error(f'Error inesperado leyendo settings.json: {e}')

		_cached_settings = dict(DEFAULTS)
		return _cached_settings.copy()


def save(settings: dict) -> bool:
	"""Atomically save normalized settings and update the in-process cache."""
	global _cached_settings
	with _settings_lock:
		temp_path = None
		try:
			normalized = _normalize_settings(settings)
			fd, temp_name = tempfile.mkstemp(
				prefix=f'{_SETTINGS_FILE.name}.', suffix='.tmp', dir=_SETTINGS_FILE.parent
			)
			temp_path = Path(temp_name)
			with os.fdopen(fd, 'w', encoding='utf-8') as f:
				json.dump(normalized, f, ensure_ascii=False, indent=2)
				f.flush()
				os.fsync(f.fileno())
			os.replace(temp_path, _SETTINGS_FILE)
			_cached_settings = normalized.copy()
			return True
		except Exception as e:
			logger.error(f'No se pudo guardar settings.json: {e}')
			return False
		finally:
			if temp_path is not None:
				try:
					temp_path.unlink(missing_ok=True)
				except OSError:
					pass


def get(key: str, default=None, force_reload: bool = False):
	"""Atajo para leer una sola clave directamente. Permite forzar la recarga."""
	return load(force_reload=force_reload).get(key, default)


def set(key: str, value) -> None:
	"""Actualiza una sola clave en settings.json de forma atómica."""
	with _settings_lock:
		current = load()
		current[key] = value
		save(current)


def get_reports_path() -> str:
	"""Retorna la carpeta de destino para reportes."""
	custom = get('reports_path', '')
	if custom and os.path.isdir(custom):
		return custom

	home = os.path.expanduser('~')
	for candidate in ('Desktop', 'Escritorio'):
		path = os.path.join(home, candidate)
		if os.path.isdir(path):
			return path
	return home


def fmt_price(amount: float | str | Decimal) -> str:
	"""Formatea un precio aplicando formato latino (1.500,00) de manera segura."""
	cfg = load()
	symbol = cfg.get('currency_symbol', '$')
	decimals = cfg.get('currency_decimals', 0)

	try:
		val = float(amount) if amount is not None else 0.0
	except (ValueError, TypeError):
		val = 0.0

	if decimals == 0:
		base_fmt = f'{val:,.0f}'
	else:
		base_fmt = f'{val:,.{decimals}f}'

	latam_fmt = base_fmt.replace(',', 'X').replace('.', ',').replace('X', '.')

	return f'{symbol}{latam_fmt}'


class SettingsManager:
	"""Wrapper de instancia sobre las funciones del módulo para inyección en AppContext."""

	def load(self, force_reload: bool = False) -> dict:
		return load(force_reload=force_reload)

	def save(self, settings: dict) -> bool:
		return save(settings)

	def get(self, key: str, default=None, force_reload: bool = False):
		return get(key, default, force_reload=force_reload)

	def set(self, key: str, value) -> None:
		set(key, value)

	def fmt_price(self, amount) -> str:
		return fmt_price(amount)
