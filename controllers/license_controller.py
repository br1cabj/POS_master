import hashlib
import json
import os
from datetime import datetime, timedelta

SECRET_SALT = 'KioscoPOS_SaaS_2026_Secreto_X99'


class LicenseController:
	def __init__(self):
		self.license_file = 'license.dat'

	def _generate_signature(self, license_type, expiration_date):
		raw = f'{license_type}|{expiration_date}|{SECRET_SALT}'
		return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

	def activate_demo(self):
		"""Activa una licencia de prueba válida por 7 días."""
		expire_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
		data = {
			'type': 'DEMO',
			'expiration': expire_date,
			'signature': self._generate_signature('DEMO', expire_date),
		}
		with open(self.license_file, 'w') as f:
			json.dump(data, f)
		return True, '¡Demo de 7 días activada con éxito!'

	def activate_license(self, license_key):
		"""
		Valida y activa una clave de licencia con formato TIPO-AAAAMMDD-FIRMA.
		Verifica la firma criptográfica antes de persistir.
		"""
		try:
			parts = license_key.strip().split('-')
			if len(parts) != 3:
				return False, 'Formato de licencia inválido.'

			l_type, exp_str, provided_sig = parts
			exp_date = f'{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:8]}'

			if provided_sig != self._generate_signature(l_type, exp_date):
				return False, 'La licencia es falsa o ha sido alterada.'

			data = {
				'type': l_type,
				'expiration': '2099-12-31' if l_type == 'FULL' else exp_date,
				'signature': self._generate_signature(l_type, exp_date),
			}
			with open(self.license_file, 'w') as f:
				json.dump(data, f)

			return True, f'¡Licencia {l_type} activada exitosamente!'
		except Exception:
			return False, 'Error al procesar la licencia.'

	def check_license_status(self):
		"""Retorna (válida, mensaje). El mensaje es un código de estado o días restantes."""
		if not os.path.exists(self.license_file):
			return False, 'NO_LICENSE'

		try:
			with open(self.license_file, 'r') as f:
				data = json.load(f)

			if data['type'] == 'FULL':
				return True, 'VITALICIA'

			exp_date = datetime.strptime(data['expiration'], '%Y-%m-%d')
			if datetime.now() > exp_date:
				return False, 'EXPIRED'

			dias_restantes = (exp_date - datetime.now()).days
			return True, f'{data["type"]} ({dias_restantes} días restantes)'
		except Exception:
			return False, 'CORRUPT_LICENSE'
