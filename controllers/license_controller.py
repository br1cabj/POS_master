import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import sys
import uuid
from datetime import datetime, timedelta

from utils.config import SECRET_SALT

logger = logging.getLogger(__name__)

_TRIAL_DAYS = 7
_APPDATA_FOLDER = 'CloudPOS'
_APPDATA_FILE = 'pref.dat'


def _app_dir() -> str:
    """Directorio del ejecutable en producción, raíz del proyecto en desarrollo."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─── Huella de máquina ────────────────────────────────────────────────────────

def _machine_id() -> str:
    """
    Genera un ID estable de la máquina combinando MAC + hostname + usuario.
    Sobrevive reinstalaciones y restauraciones de backup de la app.
    """
    try:
        parts = [
            str(uuid.getnode()),                                         # MAC address
            platform.node(),                                             # hostname
            os.environ.get('USERNAME') or os.environ.get('USER') or '', # usuario OS
        ]
        raw = '|'.join(parts)
        return hmac.new(
            SECRET_SALT.encode('utf-8'),
            raw.encode('utf-8'),
            'sha256',
        ).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()[:32]


# ─── Registro en APPDATA ──────────────────────────────────────────────────────

def _appdata_path() -> str:
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    folder = os.path.join(base, _APPDATA_FOLDER)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, _APPDATA_FILE)


def _sign_record(mid: str, ts: str) -> str:
    key = (SECRET_SALT + mid).encode('utf-8')
    msg = f'{mid}|{ts}'.encode('utf-8')
    return hmac.new(key, msg, 'sha256').hexdigest()


def _read_appdata_record() -> dict | None:
    """
    Lee el registro de trial desde APPDATA.
    Retorna None si no existe, está corrupto o la firma no valida.
    """
    path = _appdata_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            raw = f.read().strip()
        decoded = base64.b64decode(raw.encode('utf-8')).decode('utf-8')
        data = json.loads(decoded)
        if _sign_record(data['mid'], data['ts']) != data.get('sig'):
            logger.warning('Registro APPDATA con firma inválida.')
            return None
        return data
    except Exception:
        return None


def _write_appdata_record(mid: str, ts: str) -> None:
    data = {'mid': mid, 'ts': ts, 'sig': _sign_record(mid, ts)}
    encoded = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
    with open(_appdata_path(), 'w') as f:
        f.write(encoded)


# ─── Controlador ─────────────────────────────────────────────────────────────

class LicenseController:
    def __init__(self):
        self.license_file = os.path.join(_app_dir(), 'license.dat')

    def _generate_signature(self, license_type, expiration_date):
        raw = f'{license_type}|{expiration_date}|{SECRET_SALT}'
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _write_license(self, data: dict):
        encoded = base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
        with open(self.license_file, 'w') as f:
            f.write(encoded)

    def _read_license(self) -> dict:
        with open(self.license_file, 'r') as f:
            raw = f.read().strip()
        try:
            decoded = base64.b64decode(raw.encode('utf-8')).decode('utf-8')
            return json.loads(decoded)
        except Exception:
            raise ValueError('Archivo de licencia corrupto o en formato inválido.')

    # ── Demo ──────────────────────────────────────────────────────────────────

    def activate_demo(self):
        """
        Activa el período de prueba de 7 días.
        Bloquea si esta máquina ya agotó su demo, usando el registro en APPDATA
        como fuente de verdad (sobrevive reinstalaciones y restauraciones de backup).
        """
        mid = _machine_id()
        record = _read_appdata_record()

        if record and record.get('mid') == mid:
            try:
                start = datetime.fromisoformat(record['ts'])
            except Exception:
                start = datetime.now() - timedelta(days=_TRIAL_DAYS + 1)
            end = start + timedelta(days=_TRIAL_DAYS)
            if datetime.now() > end:
                return False, (
                    'Esta máquina ya utilizó el período de prueba gratuito.\n'
                    'Contactá al proveedor para adquirir una licencia.'
                )

        expire_date = (datetime.now() + timedelta(days=_TRIAL_DAYS)).strftime('%Y-%m-%d')
        data = {
            'type': 'DEMO',
            'expiration': expire_date,
            'signature': self._generate_signature('DEMO', expire_date),
        }
        self._write_license(data)

        # Registrar en APPDATA solo en el primer uso de esta máquina
        if not record or record.get('mid') != mid:
            try:
                _write_appdata_record(mid, datetime.now().isoformat())
            except Exception as e:
                logger.warning('No se pudo escribir el registro APPDATA: %s', e)

        return True, f'¡Demo de {_TRIAL_DAYS} días activada con éxito!'

    # ── Licencia pagada ───────────────────────────────────────────────────────

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

            if len(exp_str) != 8:
                return False, 'Formato de licencia inválido.'

            exp_date = f'{exp_str[:4]}-{exp_str[4:6]}-{exp_str[6:8]}'

            try:
                datetime.strptime(exp_date, '%Y-%m-%d')
            except ValueError:
                return False, 'La licencia contiene una fecha de vencimiento inválida.'

            if provided_sig != self._generate_signature(l_type, exp_date)[:16]:
                return False, 'La licencia es falsa o ha sido alterada.'

            stored_expiration = '2099-12-31' if l_type in ('FULL', 'VITA') else exp_date
            data = {
                'type': l_type,
                'expiration': stored_expiration,
                'signature': self._generate_signature(l_type, stored_expiration),
            }
            self._write_license(data)
            return True, f'¡Licencia {l_type} activada exitosamente!'
        except Exception:
            return False, 'Error al procesar la licencia.'

    # ── Verificación de estado ────────────────────────────────────────────────

    def check_license_status(self):
        """
        Retorna (válida, mensaje).

        Para licencias DEMO, el registro en APPDATA es la fuente de verdad:
        - Si existe y corresponde a esta máquina → su fecha manda.
        - Si no existe pero hay un license.dat DEMO válido → se migra el registro
          reconstruyendo la fecha de inicio desde la fecha de expiración guardada.
        Esto hace que restaurar un backup o reinstalar la app no resetee el trial.
        """
        if not os.path.exists(self.license_file):
            return False, 'NO_LICENSE'

        try:
            data = self._read_license()

            expected_sig = self._generate_signature(data['type'], data['expiration'])
            if data.get('signature') != expected_sig:
                return False, 'CORRUPT_LICENSE'

            if data['type'] in ('FULL', 'VITA'):
                return True, 'VITALICIA'

            if data['type'] == 'DEMO':
                return self._check_demo_status(data)

            # Licencia de tipo temporal (no DEMO ni vitalicia)
            exp_date = datetime.strptime(data['expiration'], '%Y-%m-%d')
            if datetime.now() > exp_date:
                return False, 'EXPIRED'
            dias = max(0, (exp_date - datetime.now()).days)
            return True, f'{data["type"]} ({dias} días restantes)'

        except ValueError:
            return False, 'CORRUPT_LICENSE'
        except Exception:
            return False, 'CORRUPT_LICENSE'

    def _check_demo_status(self, license_data: dict):
        """
        Verifica el estado de un demo usando APPDATA como fuente de verdad.
        Migra usuarios existentes que no tienen registro APPDATA todavía.
        """
        mid = _machine_id()
        record = _read_appdata_record()

        if record and record.get('mid') == mid:
            # APPDATA existe y es de esta máquina → es la fuente de verdad
            try:
                start = datetime.fromisoformat(record['ts'])
            except Exception:
                return False, 'CORRUPT_LICENSE'
            end = start + timedelta(days=_TRIAL_DAYS)
            if datetime.now() > end:
                return False, 'EXPIRED'
            dias = max(0, (end - datetime.now()).days)
            return True, f'DEMO ({dias} días restantes)'

        # No hay registro APPDATA (instalación anterior al fix o máquina distinta).
        # Usar la fecha del license.dat y migrar el registro.
        try:
            exp_date = datetime.strptime(license_data['expiration'], '%Y-%m-%d')
        except ValueError:
            return False, 'CORRUPT_LICENSE'

        if datetime.now() > exp_date:
            return False, 'EXPIRED'

        # Reconstruir la fecha de inicio y escribir el registro APPDATA
        reconstructed_start = (exp_date - timedelta(days=_TRIAL_DAYS)).isoformat()
        try:
            _write_appdata_record(mid, reconstructed_start)
        except Exception as e:
            logger.warning('No se pudo migrar el registro APPDATA: %s', e)

        dias = max(0, (exp_date - datetime.now()).days)
        return True, f'DEMO ({dias} días restantes)'
