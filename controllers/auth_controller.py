import logging

import bcrypt

from controllers.base import BaseController
from database.models import User

logger = logging.getLogger(__name__)


class AuthController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)
		self._dummy_hash = bcrypt.hashpw(b'dummy_password', bcrypt.gensalt())

	def get_first_tenant_id(self):
		"""
		Retorna el ID del primer tenant activo.
		En instalaciones de un solo negocio siempre hay uno.
		"""
		from database.models import Tenant

		with self._Session() as session:
			try:
				tenant = session.query(Tenant).order_by(Tenant.id).first()
				return tenant.id if tenant else None
			except Exception as e:
				logger.error(f'Error al obtener tenant_id: {e}', exc_info=True)
				return None

	def login(self, username, password, tenant_id=None):
		"""
		Autentica al usuario y retorna sus datos, o None si las credenciales son invalidas.
		Ejecuta bcrypt.checkpw() incluso cuando el usuario no existe para equiparar
		el tiempo de respuesta y prevenir enumeracion de usuarios por timing attack.
		"""
		if not username or not password:
			logger.warning('Intento de login con campos vacios.')
			return None

		username_clean = str(username).strip()

		with self._Session() as session:
			try:
				query = session.query(User).filter_by(
					username=username_clean, is_active=True
				)
				if tenant_id:
					query = query.filter_by(tenant_id=tenant_id)

				user = query.first()
				password_bytes = str(password).encode('utf-8')

				if user:
					stored_hash = user.password_hash
					if isinstance(stored_hash, str):
						stored_hash = stored_hash.encode('utf-8')

					try:
						if bcrypt.checkpw(password_bytes, stored_hash):
							logger.info(
								f'Login exitoso: {user.username} - empresa ID {user.tenant_id}'
							)
							return {
								'id': user.id,
								'username': user.username,
								'tenant_id': user.tenant_id,
								'role': user.role,
							}
					except Exception as bcrypt_err:
						logger.error(
							f'Error al verificar credenciales para {username_clean}: {bcrypt_err}',
							exc_info=True,
						)
						return None
				else:
					bcrypt.checkpw(password_bytes, self._dummy_hash)

				logger.warning(f'Fallo de autenticacion para: {username_clean}')
				return None

			except Exception as e:
				logger.error(
					f'Error de base de datos durante el login: {e}', exc_info=True
				)
				return None
