"""
utils/settings_manager.py
=========================
Persistencia ligera de configuración del negocio en settings.json.
Carga valores por defecto si el archivo no existe o está corrupto.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Archivo de configuración ──────────────────────────────────────────────────
_SETTINGS_FILE = Path(__file__).parent.parent / 'settings.json'

# ── Valores por defecto ───────────────────────────────────────────────────────
DEFAULTS: dict = {
    # Empresa
    'company_name':     'Mi Negocio',
    'company_address':  '',
    'company_phone':    '',
    # Moneda
    'currency_symbol':  '$',
    'currency_decimals': 0,          # 0 = enteros  |  2 = centavos
    # Ventas
    'tax_rate':          0.0,        # porcentaje, ej. 21.0
    'low_stock_threshold': 5,        # unidades mínimas antes de alerta
    'require_customer':  False,      # pedir cliente en cada venta
    # UI
    'show_shortcuts_bar': True,
    # Dólar (Argentina)
    'dollar_type':       'blue',   # 'blue' | 'oficial' | 'mep'
    'dollar_rate':        0.0,     # cotización manual ingresada por el usuario
    'dollar_margin_pct':  30.0,    # margen de ganancia aplicado al recalcular
}


def load() -> dict:
    """Devuelve el dict completo de configuración (defaults + guardados)."""
    try:
        if _SETTINGS_FILE.exists():
            with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            return {**DEFAULTS, **saved}
    except Exception as e:
        logger.warning(f'No se pudo leer settings.json: {e}')
    return dict(DEFAULTS)


def save(settings: dict) -> bool:
    """Guarda el dict en settings.json. Retorna True si tuvo éxito."""
    try:
        with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f'No se pudo guardar settings.json: {e}')
        return False


def get(key: str, default=None):
    """Atajo para leer una sola clave."""
    return load().get(key, default)


def fmt_price(amount: float) -> str:
    """
    Formatea un precio usando las configuraciones de moneda guardadas.
    Ejemplo: fmt_price(1500) → '$1,500'  o  '$1.500,00'
    """
    cfg = load()
    symbol = cfg.get('currency_symbol', '$')
    decimals = cfg.get('currency_decimals', 0)
    if decimals == 0:
        return f'{symbol}{amount:,.0f}'
    return f'{symbol}{amount:,.{decimals}f}'


class SettingsManager:
    """
    Wrapper de instancia sobre las funciones del módulo.
    Permite usar SettingsManager() como objeto (compatibilidad con AppContext).
    """

    def load(self) -> dict:
        return load()

    def save(self, settings: dict) -> bool:
        return save(settings)

    def get(self, key: str, default=None):
        return get(key, default)

    def fmt_price(self, amount: float) -> str:
        return fmt_price(amount)
