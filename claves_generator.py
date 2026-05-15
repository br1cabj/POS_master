import hashlib
import sys
import uuid
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
_CLOUD_SALT = SECRET_SALT + '_cloud_v1'

_SEP = '═' * 54


# ── Licencia local ────────────────────────────────────────────

def generar_clave(tipo_licencia, dias_duracion):
	fecha_expiracion = (datetime.now() + timedelta(days=dias_duracion)).strftime('%Y%m%d')
	fecha_formateada = f'{fecha_expiracion[:4]}-{fecha_expiracion[4:6]}-{fecha_expiracion[6:8]}'

	raw_string = f'{tipo_licencia}|{fecha_formateada}|{SECRET_SALT}'
	firma = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()[:16]
	clave_final = f'{tipo_licencia}-{fecha_expiracion}-{firma}'

	print(f'\n{_SEP}')
	print(f'  PAGO RECIBIDO  ·  Plan: {tipo_licencia}')
	print(f'  Vence el: {fecha_formateada}')
	print(f'\n  ENVIA ESTA CLAVE AL CLIENTE:\n')
	print(f'     {clave_final}')
	print(f'{_SEP}\n')
	return clave_final


# ── Plan cloud ────────────────────────────────────────────────

def generar_codigo_cloud(tenant_id: str, dias_duracion: int) -> str:
	"""
	Genera un código de activación cloud.

	Formato: CLOUD-AAAAMMDD-<tenant_id_32hex>-<firma_16hex>

	El cliente lo ingresa en Configuración > Plan Cloud del POS.
	El tenant_id debe existir previamente en la tabla 'tenants' de Supabase.
	"""
	fecha_exp = (datetime.now() + timedelta(days=dias_duracion)).strftime('%Y%m%d')
	fecha_fmt = f'{fecha_exp[:4]}-{fecha_exp[4:6]}-{fecha_exp[6:8]}'

	raw = f'CLOUD|{tenant_id}|{fecha_fmt}|{_CLOUD_SALT}'
	firma = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

	tenant_hex = tenant_id.replace('-', '').upper()
	codigo = f'CLOUD-{fecha_exp}-{tenant_hex}-{firma}'

	print(f'\n{_SEP}')
	print(f'  PLAN CLOUD ACTIVADO')
	print(f'  Vence el: {fecha_fmt}  ({dias_duracion} días)')
	print(f'  Tenant ID: {tenant_id}')
	print(f'\n  ENVIA ESTE CODIGO AL CLIENTE:\n')
	print(f'     {codigo}')
	print(f'\n  El cliente lo ingresa en:')
	print(f'  Configuracion > Licencias y Plan > Plan Cloud')
	print(f'{_SEP}\n')
	return codigo


def _menu_cloud():
	print('\n  --- PLAN CLOUD ---\n')
	print('  Tenant ID (UUID del cliente en Supabase).')
	print('  Dejá vacío para generar uno nuevo.\n')

	raw = input('  Tenant ID: ').strip()
	if raw:
		tenant_id = raw.lower()
		# validación básica de formato UUID
		try:
			uuid.UUID(tenant_id)
		except ValueError:
			print('\n  ERROR: el Tenant ID no tiene formato UUID válido.')
			print('  Ejemplo: a1b2c3d4-e5f6-7890-abcd-ef1234567890\n')
			return
	else:
		tenant_id = str(uuid.uuid4())
		print(f'\n  Nuevo Tenant ID generado: {tenant_id}')
		print('  Agregalo a la tabla "tenants" de Supabase antes de enviar el código.\n')

	print('\n  Duración del plan:')
	print('  1. Mensual    (30 días)')
	print('  2. Trimestral (90 días)')
	print('  3. Semestral  (180 días)')
	print('  4. Anual      (365 días)')

	op = input('\n  Elige una opción (1/2/3/4): ').strip()
	duraciones = {'1': 30, '2': 90, '3': 180, '4': 365}
	dias = duraciones.get(op)
	if dias is None:
		print('\n  Opción inválida.\n')
		return

	generar_codigo_cloud(tenant_id, dias)


# ── Menú principal ────────────────────────────────────────────

if __name__ == '__main__':
	print(f'\n{_SEP}')
	print('   GENERADOR DE CLAVES  —  CloudPOS')
	print(f'{_SEP}')
	print('\n  LICENCIA LOCAL (pago único):')
	print('    1. Mensual       (30 días)')
	print('    2. Anual         (365 días)')
	print('    3. Vitalicia     (sin vencimiento)')
	print('\n  PLAN CLOUD (suscripción):')
	print('    4. Código Cloud  (sync + acceso móvil)')
	print('\n    0. Salir')

	try:
		opcion = input('\n  Elige una opción: ').strip()
		if opcion == '1':
			generar_clave('MES', 30)
		elif opcion == '2':
			generar_clave('ANO', 365)
		elif opcion == '3':
			generar_clave('VITA', 36500)
		elif opcion == '4':
			_menu_cloud()
		elif opcion == '0':
			pass
		else:
			print('\n  Opción inválida.\n')
	except KeyboardInterrupt:
		print('\n\n  Cancelado.\n')
