"""
utils/settings_manager.py
=========================
Persistencia ligera de configuración del negocio en settings.json.
Carga valores por defecto si el archivo no existe o está corrupto.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Archivo de configuración ──────────────────────────────────────────────────
_SETTINGS_FILE = Path(__file__).parent.parent / 'settings.json'

# ── Caché en memoria (Solución al cuello de botella I/O) ──────────────────────
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
	'reports_path': '',  # carpeta de destino para reportes; vacío = Desktop
}


def load() -> dict:
	"""Devuelve el dict de configuración, utilizando caché en memoria para evitar leer el disco constantemente."""
	global _cached_settings

	if _cached_settings is not None:
		return _cached_settings

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
			return _cached_settings
	except Exception as e:
		logger.warning(f'No se pudo leer settings.json, usando defaults: {e}')

	_cached_settings = dict(DEFAULTS)
	return _cached_settings


def save(settings: dict) -> bool:
	"""Guarda el dict en settings.json y actualiza el caché. Retorna True si tuvo éxito."""
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
	"""Atajo para leer una sola clave directamente desde el caché."""
	return load().get(key, default)


def get_reports_path() -> str:
	"""Retorna la carpeta de destino para reportes.

	Prioridad:
	  1. Ruta configurada en settings (si existe y es un directorio válido).
	  2. ~/Desktop
	  3. ~/Escritorio  (Windows en español)
	  4. ~ (home del usuario como último recurso)
	"""
	custom = get('reports_path', '')
	if custom and os.path.isdir(custom):
		return custom

	home = os.path.expanduser('~')
	for candidate in ('Desktop', 'Escritorio'):
		path = os.path.join(home, candidate)
		if os.path.isdir(path):
			return path
	return home


def fmt_price(amount: float) -> str:
	"""Formatea un precio aplicando formato latino (1.500,00) de manera eficiente."""
	cfg = load()
	symbol = cfg.get('currency_symbol', '$')
	decimals = cfg.get('currency_decimals', 0)

	# Formateo base en estándar US
	if decimals == 0:
		base_fmt = f'{amount:,.0f}'
	else:
		base_fmt = f'{amount:,.{decimals}f}'

	# Reemplazo rápido para formato latino: miles con punto, decimales con coma
	latam_fmt = base_fmt.replace(',', 'X').replace('.', ',').replace('X', '.')

	return f'{symbol}{latam_fmt}'


class SettingsManager:
	"""
	Wrapper de instancia sobre las funciones del módulo.
	Mantiene la compatibilidad con inyecciones de dependencias como AppContext.
	"""

	def load(self) -> dict:
		return load()

	def save(self, settings: dict) -> bool:
		return save(settings)

	def get(self, key: str, default=None):
		return get(key, default)

	def fmt_price(self, amount: float) -> str:
		return fmt_price(amount)
