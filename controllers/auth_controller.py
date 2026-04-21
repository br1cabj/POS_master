import logging

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import User

DB_URL = 'sqlite:///pos_system.db'
_default_engine = create_engine(DB_URL)

logger = logging.getLogger(__name__)


class AuthController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)
		self._dummy_hash = bcrypt.hashpw(b'dummy_password', bcrypt.gensalt())

	def login(self, username, password, tenant_id=None):
		"""
		Autentica al usuario y retorna sus datos, o None si las credenciales son inválidas.
		Ejecuta bcrypt.checkpw() incluso cuando el usuario no existe para equiparar
		el tiempo de respuesta y prevenir enumeración de usuarios por timing attack.
		"""
		if not username or not password:
			logger.warning('Intento de login con campos vacíos.')
			return None

		username_clean = str(username).strip()

		with self.SessionLocal() as session:
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

					if bcrypt.checkpw(password_bytes, stored_hash):
						logger.info(
							f'Login exitoso: {user.username} — empresa ID {user.tenant_id}'
						)
						return {
							'id': user.id,
							'username': user.username,
							'tenant_id': user.tenant_id,
							'role': user.role,
						}
				else:
					bcrypt.checkpw(password_bytes, self._dummy_hash)

				logger.warning(f'Fallo de autenticación para: {username_clean}')
				return None

			except Exception as e:
				logger.error(
					f'Error de base de datos durante el login: {e}', exc_info=True
				)
				return None
