import hashlib
import os
from datetime import datetime, timedelta

try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass

SECRET_SALT = os.getenv('SECRET_SALT', 'CloudPOS_SaaS_2026_Secreto_X99')


def generar_clave(tipo_licencia, dias_duracion):
	fecha_expiracion = (datetime.now() + timedelta(days=dias_duracion)).strftime(
		'%Y%m%d'
	)
	fecha_formateada = (
		f'{fecha_expiracion[:4]}-{fecha_expiracion[4:6]}-{fecha_expiracion[6:8]}'
	)

	# Firma matemática
	raw_string = f'{tipo_licencia}|{fecha_formateada}|{SECRET_SALT}'
	firma = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()[:16].upper()

	firma_bloques = '-'.join([firma[i : i + 4] for i in range(0, len(firma), 4)])

	clave_final = f'{tipo_licencia}-{fecha_expiracion}-{firma_bloques}'

	print('\n' + '═' * 50)
	print(f'✅ PAGO RECIBIDO. Plan: {tipo_licencia}')
	print(f'📅 Vence el: {fecha_formateada}')
	print('\n🔑 ENVÍA ESTA CLAVE AL CLIENTE:\n')
	print(f'   {clave_final}')
	print('\n' + '═' * 50 + '\n')

	return clave_final


if __name__ == '__main__':
	print('\n🛠️  GENERADOR DE LICENCIAS CLOUDPOS  🛠️\n')
	print('1. Suscripción Mensual (30 días)')
	print('2. Suscripción Anual (365 días)')
	print('3. Licencia Vitalicia (100 años)')

	try:
		opcion = input('\nElige una opción (1/2/3): ').strip()

		if opcion == '1':
			generar_clave('MES', 30)
		elif opcion == '2':
			generar_clave('ANUAL', 365)
		elif opcion == '3':
			generar_clave('FULL', 36500)
		else:
			print('❌ Opción inválida. Debes ingresar 1, 2 o 3.')

	except KeyboardInterrupt:
		print('\nOperación cancelada.')
