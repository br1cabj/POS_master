"""Validation and persistence boundary for application settings."""

from __future__ import annotations

from utils import settings_manager


class SettingsController:
	"""Keep invalid runtime configuration out of the shared settings store."""

	@staticmethod
	def validate(settings: dict) -> list[str]:
		errors = []
		if not isinstance(settings.get('company_name'), str) or not settings['company_name'].strip():
			errors.append('El nombre del negocio es obligatorio.')
		if not str(settings.get('currency_symbol', '')).strip():
			errors.append('El símbolo de moneda no puede quedar vacío.')
		try:
			decimals = int(settings.get('currency_decimals', 0))
			if decimals not in (0, 2):
				errors.append('Los decimales de moneda deben ser 0 o 2.')
		except (ValueError, TypeError):
			errors.append('La cantidad de decimales debe ser válida.')
		try:
			tax_rate = float(str(settings.get('tax_rate', 0)).replace(',', '.'))
			if not 0 <= tax_rate <= 100:
				errors.append('El IVA debe estar entre 0 y 100%.')
		except (ValueError, TypeError):
			errors.append('El porcentaje de IVA debe ser numérico.')
		try:
			if int(settings.get('low_stock_threshold', 0)) < 0:
				errors.append('El umbral de stock no puede ser negativo.')
		except (ValueError, TypeError):
			errors.append('El umbral de stock debe ser un número entero.')
		for key, label in (
			('price_list_a_name', 'Lista A'),
			('price_list_b_name', 'Lista B'),
		):
			value = str(settings.get(key, '')).strip()
			if not value or len(value) > 40:
				errors.append(f'{label}: ingresá un nombre de 1 a 40 caracteres.')
		try:
			chars = int(settings.get('printer_ticket_chars', 48))
			if not 16 <= chars <= 96:
				errors.append('Los caracteres por línea deben estar entre 16 y 96.')
		except (ValueError, TypeError):
			errors.append('Los caracteres por línea deben ser un número entero.')
		for key, label in (
			('poledisplay_line1', 'Línea 1 de pantalla'),
			('poledisplay_line2', 'Línea 2 de pantalla'),
		):
			if len(str(settings.get(key, ''))) > 20:
				errors.append(f'{label}: el máximo es 20 caracteres.')
		return errors

	def save(self, settings: dict) -> tuple[bool, str]:
		errors = self.validate(settings)
		if errors:
			return False, '\n'.join(errors)
		if not settings_manager.save(settings):
			return False, 'No se pudo guardar la configuración en el disco.'
		return True, ''
