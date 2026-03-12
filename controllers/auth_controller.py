import logging

import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User

logger = logging.getLogger(__name__)


class AuthController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def login(self, username, password):
		"""
		Verifica las credenciales del usuario.
		Retorna un diccionario con los datos del usuario si es exitoso, o None si falla.
		"""
		# Validación temprana básica
		if not username or not password:
			logger.warning('Intento de login con campos vacíos.')
			return None

		with self.Session() as session:
			try:
				user = session.query(User).filter_by(username=username).first()

				if user:
					password_bytes = password.encode('utf-8')

					# A veces la BD devuelve el hash como string, aseguramos que sea bytes para bcrypt
					stored_hash = user.password_hash
					if isinstance(stored_hash, str):
						stored_hash = stored_hash.encode('utf-8')

					if bcrypt.checkpw(password_bytes, stored_hash):
						logger.info(
							f'Login exitoso: {user.username} de la empresa ID {user.tenant_id}'
						)

						# Extraemos solo lo necesario a un diccionario para evitar el DetachedInstanceError
						return {
							'id': user.id,
							'username': user.username,
							'tenant_id': user.tenant_id,
							# 'role': user.role,
							# 'is_admin': user.is_admin
						}

				# Usamos el mismo mensaje para ambos casos por seguridad (previene enumeración de usuarios)
				logger.warning(f'Fallo de autenticación para el usuario: {username}')
				return None

			except Exception as e:
				logger.error(
					f'Error crítico de base de datos durante el login: {e}',
					exc_info=True,
				)
				return None
