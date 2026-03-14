import hashlib
import json
import os
from datetime import datetime, timedelta

# 🛑 TU SECRETO COMERCIAL (Nunca le des esto a nadie)
SECRET_SALT = 'KioscoPOS_SaaS_2026_Secreto_X99'


class LicenseController:
	def __init__(self):
		self.license_file = 'license.dat'  # Archivo oculto donde se guarda el estado

	def _generate_signature(self, license_type, expiration_date):
		"""Genera una firma matemática imposible de falsificar sin el SECRET_SALT"""
		raw_string = f'{license_type}|{expiration_date}|{SECRET_SALT}'
		return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()[
			:16
		]  # Firma corta de 16 letras

	def activate_demo(self):
		"""Activa una prueba de 7 días"""
		expire_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
		signature = self._generate_signature('DEMO', expire_date)

		data = {'type': 'DEMO', 'expiration': expire_date, 'signature': signature}
		with open(self.license_file, 'w') as f:
			json.dump(data, f)
		return True, '¡Demo de 7 días activada con éxito!'

	def activate_license(self, license_key):
		"""Valida una clave comprada (Ej: MES-20260413-A1B2C3D4E5F6G7H8)"""
		try:
			parts = license_key.split('-')
			if len(parts) != 3:
				return False, 'Formato de licencia inválido.'

			l_type, exp_str, provided_signature = parts[0], parts[1], parts[2]

			# Formatear la fecha para validar
			exp_date = f'{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:8]}'

			# Comprobar si la firma es matemáticamente correcta
			expected_signature = self._generate_signature(l_type, exp_date)

			if provided_signature != expected_signature:
				return False, 'La licencia es falsa o ha sido alterada.'

			# Guardar la licencia válida en el archivo
			data = {
				'type': l_type,
				'expiration': exp_date if l_type != 'FULL' else '2099-12-31',
				'signature': expected_signature,
			}
			with open(self.license_file, 'w') as f:
				json.dump(data, f)

			return True, f'¡Licencia {l_type} activada exitosamente!'

		except Exception:
			return False, 'Error al leer la licencia.'

	def check_license_status(self):
		"""Devuelve si el programa puede abrirse o está bloqueado"""
		if not os.path.exists(self.license_file):
			return False, 'NO_LICENSE'

		try:
			with open(self.license_file, 'r') as f:
				data = json.load(f)

			if data['type'] == 'FULL':
				return True, 'VITALICIA'

			# Verificar expiración
			exp_date = datetime.strptime(data['expiration'], '%Y-%m-%d')
			if datetime.now() > exp_date:
				return False, 'EXPIRED'

			# Cuántos días le quedan
			dias_restantes = (exp_date - datetime.now()).days
			return True, f'{data["type"]} ({dias_restantes} días restantes)'

		except Exception:
			return False, 'CORRUPT_LICENSE'
