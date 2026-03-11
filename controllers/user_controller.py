import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User


class UserController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_users(self, tenant_id):
		"""Obtiene la lista de empleados activos."""
		session = self.Session()
		try:
			return (
				session.query(User).filter_by(tenant_id=tenant_id, is_active=True).all()
			)
		except Exception as e:
			print(f'Error al obtener usuarios: {e}')
			return []
		finally:
			session.close()

	def add_user(self, tenant_id, username, password, role):
		"""Crea un nuevo empleado o reactiva uno borrado lógicamente."""
		session = self.Session()
		try:
			# 1. Encriptación
			hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
			hashed_pw = hashed_bytes.decode('utf-8')

			# 2. Buscamos si el usuario ya existe (activo o borrado)
			exist = (
				session.query(User)
				.filter_by(username=username, tenant_id=tenant_id)
				.first()
			)

			if exist:
				if exist.is_active:
					return False, 'Ese nombre de usuario ya está en uso.'
				else:
					# Reactivamos y actualizamos con la nueva contraseña encriptada
					exist.is_active = True
					exist.password_hash = hashed_pw
					exist.role = role
					session.commit()
					return True, f'Empleado {username} reactivado con éxito.'

			# 3. Si es un usuario completamente nuevo
			new_user = User(
				tenant_id=tenant_id,
				username=username,
				password_hash=hashed_pw,
				role=role,
			)
			session.add(new_user)
			session.commit()
			return True, f'Empleado {username} creado como {role}.'

		except Exception as e:
			session.rollback()  # Revertimos si hay un error en la base de datos
			return False, f'Error interno: {e}'
		finally:
			session.close()

	def delete_user(self, user_id):
		"""Realiza un borrado lógico del empleado."""
		session = self.Session()
		try:
			user = session.query(User).filter_by(id=user_id).first()
			if not user:
				return False, 'Usuario no encontrado.'

			# Borrado Lógico de seguridad
			user.is_active = False
			session.commit()
			return True, 'Empleado eliminado correctamente.'

		except Exception as e:
			session.rollback()
			return False, f'Error al eliminar: {e}'
		finally:
			session.close()
