import hashlib
from datetime import datetime, timedelta

# DEBE SER EXACTAMENTE EL MISMO QUE PUSISTE EN TU PROGRAMA
SECRET_SALT = 'KioscoPOS_SaaS_2026_Secreto_X99'


def generar_clave(tipo_licencia, dias_duracion):
	fecha_expiracion = (datetime.now() + timedelta(days=dias_duracion)).strftime(
		'%Y%m%d'
	)
	fecha_formateada = (
		f'{fecha_expiracion[:4]}-{fecha_expiracion[4:6]}-{fecha_expiracion[6:8]}'
	)

	# Firma matemática
	raw_string = f'{tipo_licencia}|{fecha_formateada}|{SECRET_SALT}'
	firma = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()[:16]

	clave_final = f'{tipo_licencia}-{fecha_expiracion}-{firma}'

	print('\n-------------------------------------------------')
	print(f'✅ Pago Recibido. Plan: {tipo_licencia}')
	print(f'📅 Vence el: {fecha_formateada}')
	print(f'🔑 ENVÍA ESTA CLAVE AL CLIENTE:  {clave_final}')
	print('-------------------------------------------------\n')


# Pruebas:
print('1. Para Suscripción Mensual (30 días):')
generar_clave('MES', 30)

print('2. Para Suscripción Anual (365 días):')
generar_clave('ANUAL', 365)

print('3. Para Programa Comprado (Vitalicia):')
generar_clave('FULL', 36500)  # 100 años
