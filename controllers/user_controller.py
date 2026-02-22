import bcrypt
from sqlalchemy.orm import sessionmaker

from database.models import User


class UserController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def add_user(self, username, password, role, tenant_id):
		"""Crea un nuevo usuario encriptando su contraseña"""
		session = self.Session()
		try:
			# 1. Verificar si el nombre de usuario ya existe
			existing_user = session.query(User).filter_by(username=username).first()
			if existing_user:
				return False, f"El usuario '{username}' ya existe. Elige otro."

			password_bytes = password.encode('utf-8')
			salt = bcrypt.gensalt()
			hashed_password = bcrypt.hashpw(password_bytes, salt)

			# 3. Crear el usuario
			new_user = User(
				username=username,
				password_hash=hashed_password.decode('utf-8'),
				role=role,
				tenant_id=tenant_id,
			)

			session.add(new_user)
			session.commit()
			return True, f"Usuario '{username}' creado exitosamente."

		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def get_users(self, tenant_id):
		"""Obtiene todos los usuarios de la empresa actual"""
		session = self.Session()
		try:
			return session.query(User).filter_by(tenant_id=tenant_id).all()
		finally:
			session.close()
