import hashlib
import sys
from datetime import datetime, timedelta

if sys.stdout.encoding.lower() != 'utf-8':
	if hasattr(sys.stdout, 'reconfigure'):
		sys.stdout.reconfigure(encoding='utf-8')


try:
	from dotenv import load_dotenv

	load_dotenv()
except ImportError:
	pass

SECRET_SALT = 'aantesbajocabeconcontradedesdeenentrehaciahastaparaporsegunsinsobretrasmediantedurante'


def generar_clave(tipo_licencia, dias_duracion):
	fecha_expiracion = (datetime.now() + timedelta(days=dias_duracion)).strftime(
		'%Y%m%d'
	)
	fecha_formateada = (
		f'{fecha_expiracion[:4]}-{fecha_expiracion[4:6]}-{fecha_expiracion[6:8]}'
	)

	# Firma matemática — debe coincidir exactamente con LicenseController._generate_signature
	raw_string = f'{tipo_licencia}|{fecha_formateada}|{SECRET_SALT}'
	firma = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()[:16]  # 16 chars, lowercase

	clave_final = f'{tipo_licencia}-{fecha_expiracion}-{firma}'

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
			generar_clave('ANO', 365)
		elif opcion == '3':
			generar_clave('VITA', 36500)
		else:
			print('Opción inválida.')
	except KeyboardInterrupt:
		print('\nCancelado.')
