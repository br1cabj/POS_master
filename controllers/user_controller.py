import logging

import bcrypt

from controllers.base import BaseController
from database.models import User
from utils.config import make_engine

logger = logging.getLogger(__name__)

_default_engine = None


def _get_default_engine():
	global _default_engine
	if _default_engine is None:
		_default_engine = make_engine()
	return _default_engine


ALLOWED_ROLES = ['admin', 'cajero', 'gerente']
_PIN_MIN_LEN = 4


class UserController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _get_default_engine()
		super().__init__(engine)

	# =========================================================
	# LECTURA
	# =========================================================
	def get_users(self, tenant_id):
		with self._Session() as session:
			try:
				return [
					{
						'id': u.id,
						'username': u.username,
						'role': u.role,
						'has_recovery_pin': bool(u.recovery_pin_hash),
					}
					for u in session.query(User)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener usuarios: {e}', exc_info=True)
				return []

	# =========================================================
	# CREACION
	# =========================================================
	def add_user(self, tenant_id, username, password, role, recovery_pin=None):
		username_clean = str(username).strip()
		if not username_clean:
			return False, 'El nombre de usuario es obligatorio.'
		if not password or len(str(password).strip()) < 6:
			return False, 'La contraseña debe tener al menos 6 caracteres.'

		role_clean = str(role).strip().lower()
		if role_clean not in ALLOWED_ROLES:
			return False, 'Rol inválido o no permitido en el sistema.'

		pin_hash = None
		if recovery_pin:
			pin_clean = str(recovery_pin).strip()
			if len(pin_clean) < _PIN_MIN_LEN:
				return (
					False,
					f'El PIN de recuperación debe tener al menos {_PIN_MIN_LEN} dígitos.',
				)
			pin_hash = bcrypt.hashpw(
				pin_clean.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')

		with self._Session() as session:
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
					if pin_hash:
						exist.recovery_pin_hash = pin_hash
					session.commit()
					return True, f'Empleado {username_clean} reactivado con éxito.'

				new_user = User(
					tenant_id=tenant_id,
					username=username_clean,
					password_hash=hashed_pw,
					recovery_pin_hash=pin_hash,
					role=role_clean,
				)
				session.add(new_user)
				session.commit()
				return True, f'Empleado {username_clean} creado como {role_clean}.'

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al crear usuario {username_clean}: {e}', exc_info=True
				)
				return False, 'Error interno al intentar crear el usuario.'

	# =========================================================
	# RESET POR ADMIN
	# =========================================================
	def reset_password_by_admin(self, tenant_id, target_user_id, new_password):
		if not new_password or len(str(new_password).strip()) < 6:
			return False, 'La nueva contraseña debe tener al menos 6 caracteres.'

		with self._Session() as session:
			try:
				user = (
					session.query(User)
					.filter_by(id=target_user_id, tenant_id=tenant_id, is_active=True)
					.first()
				)
				if not user:
					return False, 'Usuario no encontrado.'

				user.password_hash = bcrypt.hashpw(
					str(new_password).strip().encode('utf-8'), bcrypt.gensalt()
				).decode('utf-8')
				session.commit()
				return (
					True,
					f'Contraseña de {user.username} restablecida correctamente.',
				)

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al restablecer contrasena (admin): {e}', exc_info=True
				)
				return False, 'Error interno al restablecer la contraseña.'

	# =========================================================
	# RESET CON PIN (auto-servicio)
	# =========================================================
	def reset_password_with_pin(self, tenant_id, username, recovery_pin, new_password):
		if not username or not recovery_pin or not new_password:
			return False, 'Todos los campos son obligatorios.'

		if len(str(new_password).strip()) < 6:
			return False, 'La nueva contraseña debe tener al menos 6 caracteres.'

		with self._Session() as session:
			try:
				user = (
					session.query(User)
					.filter_by(
						username=str(username).strip(),
						tenant_id=tenant_id,
						is_active=True,
					)
					.first()
				)

				if not user or not user.recovery_pin_hash:
					bcrypt.checkpw(b'dummy', bcrypt.hashpw(b'dummy', bcrypt.gensalt()))
					return False, 'Usuario o PIN incorrecto.'

				stored_hash = user.recovery_pin_hash
				if isinstance(stored_hash, str):
					stored_hash = stored_hash.encode('utf-8')

				if not bcrypt.checkpw(
					str(recovery_pin).strip().encode('utf-8'), stored_hash
				):
					return False, 'Usuario o PIN incorrecto.'

				user.password_hash = bcrypt.hashpw(
					str(new_password).strip().encode('utf-8'), bcrypt.gensalt()
				).decode('utf-8')
				session.commit()
				logger.info(f'Contraseña restablecida via PIN para: {user.username}')
				return True, 'Contraseña restablecida. Ya podés iniciar sesión.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error en recuperación con PIN: {e}', exc_info=True)
				return False, 'Error interno al procesar la recuperación.'

	# =========================================================
	# ACTUALIZAR PIN
	# =========================================================
	def set_recovery_pin(self, tenant_id, user_id, recovery_pin):
		pin_clean = str(recovery_pin).strip()
		if len(pin_clean) < _PIN_MIN_LEN:
			return False, f'El PIN debe tener al menos {_PIN_MIN_LEN} dígitos.'

		with self._Session() as session:
			try:
				user = (
					session.query(User)
					.filter_by(id=user_id, tenant_id=tenant_id, is_active=True)
					.first()
				)
				if not user:
					return False, 'Usuario no encontrado.'

				user.recovery_pin_hash = bcrypt.hashpw(
					pin_clean.encode('utf-8'), bcrypt.gensalt()
				).decode('utf-8')
				session.commit()
				return True, f'PIN de recuperación actualizado para {user.username}.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al actualizar PIN: {e}', exc_info=True)
				return False, 'Error interno al actualizar el PIN.'

	# =========================================================
	# ELIMINAR
	# =========================================================
	def delete_user(self, tenant_id, user_id, current_user_id=None):
		if current_user_id and str(user_id) == str(current_user_id):
			return (
				False,
				'No puedes eliminar tu propia cuenta mientras tienes la sesión iniciada.',
			)

		with self._Session() as session:
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
