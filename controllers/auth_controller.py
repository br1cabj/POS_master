import bcrypt
from sqlalchemy.orm import sessionmaker
from database.models import User

class AuthController:
  def __init__(self, db_engine):
    self.Session = sessionmaker(bind=db_engine)

  def login(self, username, password):
    session = self.Session()

    user = session.query(User).filter_by(username=username).first()

    if user: 
      password_bytes = password.encode('utf-8')
      stored_hash = user.password_hash.encode('utf-8')

      if bcrypt.checkpw(password_bytes, stored_hash):
        print(f'Login exitoso: {user.username} de la empresa ID {user.tenant_id}')
        return user
  
    print('Fallo de autenticacion')
    return None