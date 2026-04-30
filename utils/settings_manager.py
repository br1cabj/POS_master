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
	# Precios Mayoristas
	'wholesale_enabled': False,
	# Lista de reglas: [{"min_qty": 6, "discount_pct": 10}, ...]
	# Ordenadas de mayor a menor min_qty; se aplica la primera que coincide.
	'wholesale_rules': [],
}


def load() -> dict:
	"""Devuelve una COPIA del dict de configuración desde el caché o el disco."""
	global _cached_settings

	if _cached_settings is not None:
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

			# Asegurar tipos correctos para wholesale
			if not isinstance(merged.get('wholesale_enabled'), bool):
				merged['wholesale_enabled'] = bool(merged.get('wholesale_enabled', False))
			if not isinstance(merged.get('wholesale_rules'), list):
				merged['wholesale_rules'] = []

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


def get(key: str, default=None):
	"""Atajo para leer una sola clave directamente."""
	return load().get(key, default)


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


def get_wholesale_discount(qty: float) -> float:
	"""
	Dado una cantidad, retorna el porcentaje de descuento mayorista aplicable (0.0 si ninguno).
	Requiere que wholesale_enabled sea True y que qty supere el min_qty de alguna regla.
	Las reglas se evalúan de mayor a menor min_qty (mejor descuento primero).
	"""
	cfg = load()
	if not cfg.get('wholesale_enabled', False):
		return 0.0
	rules = cfg.get('wholesale_rules', [])
	if not rules:
		return 0.0
	# Ordenar de mayor a menor min_qty para encontrar el mejor nivel
	sorted_rules = sorted(rules, key=lambda r: r.get('min_qty', 0), reverse=True)
	for rule in sorted_rules:
		try:
			min_qty = float(rule.get('min_qty', 0))
			discount_pct = float(rule.get('discount_pct', 0))
		except (ValueError, TypeError):
			continue
		if qty >= min_qty and min_qty > 0:
			return discount_pct
	return 0.0


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

	def load(self) -> dict:
		return load()

	def save(self, settings: dict) -> bool:
		return save(settings)

	def get(self, key: str, default=None):
		return get(key, default)

	def fmt_price(self, amount: float | str | Decimal) -> str:
		return fmt_price(amount)
