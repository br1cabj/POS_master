import logging

import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User

logger = logging.getLogger(__name__)


class AuthController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)
		# Esto servirá para gastar tiempo cuando el usuario no exista.
		self._dummy_hash = bcrypt.hashpw(b'dummy_password', bcrypt.gensalt())

	def login(self, username, password, tenant_id=None):
		"""
		Verifica las credenciales del usuario.
		🛡️ Se agregó tenant_id para evitar colisiones entre diferentes empresas.
		"""
		if not username or not password:
			logger.warning('Intento de login con campos vacíos.')
			return None

		username_clean = str(username).strip()

		with self.Session() as session:
			try:
				query = session.query(User).filter_by(
					username=username_clean,
					is_active=True,
				)

				# Si tu app usa el mismo nombre de usuario para distintas empresas:
				if tenant_id:
					query = query.filter_by(tenant_id=tenant_id)

				user = query.first()

				password_bytes = str(password).encode('utf-8')

				if user:
					stored_hash = user.password_hash
					if isinstance(stored_hash, str):
						stored_hash = stored_hash.encode('utf-8')

					# Verificamos la contraseña real
					if bcrypt.checkpw(password_bytes, stored_hash):
						logger.info(
							f'Login exitoso: {user.username} de la empresa ID {user.tenant_id}'
						)

						return {
							'id': user.id,
							'username': user.username,
							'tenant_id': user.tenant_id,
							'role': user.role,  # Sugiero devolver el rol para que el frontend arme el menú
						}
				else:
					# Si el usuario no existe, calculamos un hash de todas formas
					# para que la CPU tarde lo mismo y el atacante no pueda medir el tiempo.
					bcrypt.checkpw(password_bytes, self._dummy_hash)

				# Si falla (ya sea por mala clave o porque no existe), devolvemos el mismo mensaje
				logger.warning(
					f'Fallo de autenticación para el usuario: {username_clean}'
				)
				return None

			except Exception as e:
				logger.error(
					f'Error crítico de base de datos durante el login: {e}',
					exc_info=True,
				)
				return None
