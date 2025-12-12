import bcrypt
from sqlalchemy.orm import sessionmaker
from database.models import init_db, Tenant, User

def create_initial_data():
  print('Creando datos iniciales...')

  engine = init_db()
  Session = sessionmaker(bind=engine)
  session = Session()

  existing_tenant = session.query(Tenant).filter_by(name='TIENDA').first()
  if existing_tenant:
    print('La empresa ya existe')
    return