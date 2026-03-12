import logging

import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User

logger = logging.getLogger(__name__)


class UserController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_users(self, tenant_id):
		"""Obtiene la lista de empleados activos como diccionarios para la UI."""
		with self.Session() as session:
			try:
				users = (
					session.query(User)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				)

				# Devolvemos diccionarios para evitar el DetachedInstanceError
				return [
					{
						'id': u.id,
						'username': u.username,
						'role': u.role,
						# No devolvemos el password_hash por seguridad
					}
					for u in users
				]
			except Exception as e:
				logger.error(f'Error al obtener usuarios: {e}', exc_info=True)
				return []

	def add_user(self, tenant_id, username, password, role):
		"""Crea un nuevo empleado o reactiva uno borrado lógicamente."""
		# 1. Validación temprana de UI
		username_clean = str(username).strip()
		if not username_clean or not password:
			return False, 'El nombre de usuario y la contraseña son obligatorios.'

		with self.Session() as session:
			try:
				# 2. Encriptación
				hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
				hashed_pw = hashed_bytes.decode('utf-8')

				# 3. Buscamos si el usuario ya existe (activo o borrado)
				exist = (
					session.query(User)
					.filter_by(username=username_clean, tenant_id=tenant_id)
					.first()
				)

				if exist:
					if exist.is_active:
						return False, 'Ese nombre de usuario ya está en uso.'
					else:
						# Reactivamos y actualizamos con la nueva contraseña
						exist.is_active = True
						exist.password_hash = hashed_pw
						exist.role = role
						session.commit()
						return True, f'Empleado {username_clean} reactivado con éxito.'

				# 4. Si es un usuario completamente nuevo
				new_user = User(
					tenant_id=tenant_id,
					username=username_clean,
					password_hash=hashed_pw,
					role=role,
				)
				session.add(new_user)
				session.commit()
				return True, f'Empleado {username_clean} creado como {role}.'

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al crear usuario {username_clean}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar crear el usuario.'

	def delete_user(self, user_id, current_user_id=None):
		"""Realiza un borrado lógico del empleado."""
		# 1. Validación de seguridad para evitar que el admin se borre a sí mismo
		if current_user_id and str(user_id) == str(current_user_id):
			return (
				False,
				'No puedes eliminar tu propia cuenta mientras tienes la sesión iniciada.',
			)

		with self.Session() as session:
			try:
				user = session.query(User).filter_by(id=user_id).first()
				if not user:
					return False, 'Usuario no encontrado.'

				# Borrado Lógico
				user.is_active = False
				session.commit()
				return True, 'Empleado eliminado correctamente.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al eliminar usuario {user_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar eliminar el usuario.'
