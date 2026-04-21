import logging

import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User
from utils.config import make_engine

_default_engine = make_engine()

logger = logging.getLogger(__name__)

ALLOWED_ROLES = ['admin', 'cajero', 'gerente']


class UserController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def get_users(self, tenant_id):
		with self.SessionLocal() as session:
			try:
				return [
					{'id': u.id, 'username': u.username, 'role': u.role}
					for u in session.query(User)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener usuarios: {e}', exc_info=True)
				return []

	def add_user(self, tenant_id, username, password, role):
		"""Crea un empleado con contraseña hasheada. Reactiva usuarios inactivos en lugar de duplicar."""
		username_clean = str(username).strip()
		if not username_clean:
			return False, 'El nombre de usuario es obligatorio.'
		if not password or len(str(password).strip()) < 6:
			return False, 'La contraseña debe tener al menos 6 caracteres.'

		role_clean = str(role).strip().lower()
		if role_clean not in ALLOWED_ROLES:
			return False, 'Rol inválido o no permitido en el sistema.'

		with self.SessionLocal() as session:
			try:
				hashed_pw = bcrypt.hashpw(
					str(password).encode('utf-8'), bcrypt.gensalt()
				).decode('utf-8')
				exist = (
					session.query(User)
					.filter_by(username=username_clean, tenant_id=tenant_id)
					.first()
				)

				if exist:
					if exist.is_active:
						return (
							False,
							'Ese nombre de usuario ya está en uso en su negocio.',
						)
					exist.is_active = True
					exist.password_hash = hashed_pw
					exist.role = role_clean
					session.commit()
					return True, f'Empleado {username_clean} reactivado con éxito.'

				session.add(
					User(
						tenant_id=tenant_id,
						username=username_clean,
						password_hash=hashed_pw,
						role=role_clean,
					)
				)
				session.commit()
				return True, f'Empleado {username_clean} creado como {role_clean}.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al crear usuario {username_clean}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar crear el usuario.'

	def delete_user(self, tenant_id, user_id, current_user_id=None):
		"""Baja lógica del empleado. Impide auto-eliminación durante sesión activa."""
		if current_user_id and str(user_id) == str(current_user_id):
			return (
				False,
				'No puedes eliminar tu propia cuenta mientras tienes la sesión iniciada.',
			)

		with self.SessionLocal() as session:
			try:
				user = (
					session.query(User)
					.filter_by(id=user_id, tenant_id=tenant_id)
					.first()
				)
				if not user:
					return (
						False,
						'Usuario no encontrado o no tienes permiso para borrarlo.',
					)
				user.is_active = False
				session.commit()
				return True, 'Empleado eliminado correctamente.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al eliminar usuario {user_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar eliminar el usuario.'
