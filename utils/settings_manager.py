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
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)


def _app_data_dir() -> Path:
	"""Devuelve el directorio seguro para guardar datos (Appdata/Local o ~/.config)."""
	if sys.platform == 'win32':
		base_dir = Path(os.getenv('LOCALAPPDATA', os.path.expanduser('~')))
	else:
		base_dir = Path(os.path.expanduser('~')) / '.config'

	app_folder = base_dir / 'CloudPOS'
	app_folder.mkdir(parents=True, exist_ok=True)
	return app_folder


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
	'printer_ticket_type': '80mm',   # '58mm' | '80mm' | 'laser'
	'printer_ticket_chars': 48,
	# Periféricos — Impresora de etiquetas
	'printer_label_name': '',
	# Periféricos — Balanza
	'scale_enabled': False,
	'scale_port': 'COM1',
	'scale_baud': '9600',
	'scale_protocol': 'toledo',      # 'toledo' | 'fairbanks' | 'generic'
	# Periféricos — Lector de código de barras
	'barcode_mode': 'hid',           # 'hid' | 'serial'
	'barcode_port': 'COM2',
	'barcode_baud': '9600',
	'barcode_prefix': '',
	'barcode_suffix': 'CR',          # 'none' | 'CR' | 'TAB' | 'CRLF'
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

	if _cached_settings is not None and not force_reload:
		return _cached_settings.copy()

	try:
		if _SETTINGS_FILE.exists():
			with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
				saved = json.load(f)
			merged = {**DEFAULTS, **saved}
			try:
				merged['currency_decimals'] = int(merged['currency_decimals'])
			except (ValueError, TypeError):
				merged['currency_decimals'] = 0
			try:
				merged['tax_rate'] = float(merged['tax_rate'])
			except (ValueError, TypeError):
				merged['tax_rate'] = 0.0
			try:
				merged['low_stock_threshold'] = int(merged['low_stock_threshold'])
			except (ValueError, TypeError):
				merged['low_stock_threshold'] = 5

			_cached_settings = merged
			return _cached_settings.copy()
	except Exception as e:
		logger.warning(f'No se pudo leer settings.json, usando defaults: {e}')

	_cached_settings = dict(DEFAULTS)
	return _cached_settings.copy()


def save(settings: dict) -> bool:
	"""Guarda el dict en settings.json y actualiza el caché."""
	global _cached_settings
	try:
		with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
			json.dump(settings, f, ensure_ascii=False, indent=2)

		_cached_settings = settings.copy()
		return True
	except Exception as e:
		logger.error(f'No se pudo guardar settings.json: {e}')
		return False


def get(key: str, default=None, force_reload: bool = False):
	"""Atajo para leer una sola clave directamente. Permite forzar la recarga."""
	return load(force_reload=force_reload).get(key, default)


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

	def fmt_price(self, amount) -> str:
		return fmt_price(amount)
