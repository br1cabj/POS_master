import base64
import hashlib
import json
import logging
import os
import sys
from datetime import datetime

from utils.config import SECRET_SALT

logger = logging.getLogger(__name__)

_CLOUD_SALT = SECRET_SALT + '_cloud_v1'


def _app_dir() -> str:
	if getattr(sys, 'frozen', False):
		return os.path.dirname(sys.executable)
	return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CloudLicenseController:
	"""
	Gestiona la activación y validación del plan cloud.

	Formato del código de activación:
	    CLOUD-AAAAMMDD-<tenant_id_32hex>-<firma_16hex>

	Ejemplo:
	    CLOUD-20261231-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4-9f3c1a2b4d5e6f7a

	El tenant_id es un UUID v4 sin guiones (32 caracteres hex).
	La firma es los primeros 16 caracteres del SHA-256 de
	    "CLOUD|<tenant_id_con_guiones>|<AAAAMMDD>|<_CLOUD_SALT>"
	"""

	def __init__(self):
		self._file = os.path.join(_app_dir(), 'cloud_license.dat')

	# ── helpers ───────────────────────────────────────────────────────────────

	def _sign(self, tenant_id: str, expiry: str) -> str:
		raw = f'CLOUD|{tenant_id}|{expiry}|{_CLOUD_SALT}'
		return hashlib.sha256(raw.encode()).hexdigest()[:16]

	def _write(self, data: dict) -> None:
		encoded = base64.b64encode(json.dumps(data).encode()).decode()
		with open(self._file, 'w') as f:
			f.write(encoded)

	def _read(self) -> dict:
		with open(self._file, 'r') as f:
			raw = f.read().strip()
		try:
			return json.loads(base64.b64decode(raw).decode())
		except Exception:
			raise ValueError('Archivo de plan cloud corrupto.')

	# ── public API ────────────────────────────────────────────────────────────

	def activate(self, code: str) -> tuple[bool, str]:
		"""Valida y persiste un código de activación cloud."""
		try:
			parts = code.strip().upper().split('-')
			if len(parts) != 4 or parts[0] != 'CLOUD':
				return False, 'Formato inválido. Esperado: CLOUD-AAAAMMDD-TENANTID-FIRMA'

			_, exp_str, tenant_hex, sig = parts

			if len(exp_str) != 8:
				return False, 'Fecha de vencimiento inválida en el código.'

			if len(tenant_hex) != 32 or not all(c in '0123456789ABCDEF' for c in tenant_hex):
				return False, 'Tenant ID inválido en el código.'

			exp_date = f'{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:8]}'
			try:
				datetime.strptime(exp_date, '%Y-%m-%d')
			except ValueError:
				return False, 'La fecha del código no es válida.'

			t = tenant_hex.lower()
			tenant_id = f'{t[:8]}-{t[8:12]}-{t[12:16]}-{t[16:20]}-{t[20:]}'

			expected = self._sign(tenant_id, exp_date)
			if sig.lower() != expected.lower():
				return False, 'Código inválido o alterado.'

			self._write({
				'tenant_id': tenant_id,
				'expiry': exp_date,
				'signature': expected,
			})
			exp_fmt = f'{exp_str[6:8]}/{exp_str[4:6]}/{exp_str[:4]}'
			return True, f'Plan cloud activado hasta el {exp_fmt}.'

		except Exception as e:
			logger.error('cloud_license activate error: %s', e)
			return False, 'Error inesperado al procesar el código.'

	def check_status(self) -> tuple[bool, str]:
		"""Devuelve (activo, mensaje_legible)."""
		if not os.path.exists(self._file):
			return False, 'Sin plan cloud activo'
		try:
			data = self._read()
			expected = self._sign(data['tenant_id'], data['expiry'])
			if data.get('signature') != expected:
				return False, 'Plan cloud inválido'

			exp = datetime.strptime(data['expiry'], '%Y-%m-%d')
			if datetime.now() > exp:
				return False, 'Plan cloud vencido'

			days = (exp - datetime.now()).days
			return True, f'Activo · {days} días restantes'
		except Exception:
			return False, 'Error al leer plan cloud'

	def get_tenant_id(self) -> str | None:
		"""Retorna el tenant_id si el plan está activo, None si no."""
		active, _ = self.check_status()
		if not active:
			return None
		try:
			return self._read()['tenant_id']
		except Exception:
			return None
