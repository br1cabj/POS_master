import bcrypt
from sqlalchemy.orm import sessionmaker
from database.models import init_db, Tenant, User

def create_initial_data():
    print("--- Iniciando configuración inicial ---")
    
    engine = init_db()
    Session = sessionmaker(bind=engine)
    session = Session()

    existing_tenant = session.query(Tenant).filter_by(name="Mi Super Tienda").first()
    if existing_tenant:
        print("¡La empresa ya existe! No haremos cambios.")
        return

    print("Creando empresa...")
    new_tenant = Tenant(name="Mi Super Tienda", subscription_status="active")
    session.add(new_tenant)
    session.commit() 

    print("Creando usuario administrador...")
    password_raw = "admin123" 
    
    # HASH
    password_bytes = password_raw.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    new_user = User(
        username="admin", 
        password_hash=hashed_password.decode('utf-8'),
        role="admin",
        tenant_id=new_tenant.id
    )
    
    session.add(new_user)
    session.commit()
    
    print("¡ÉXITO! Usuario: 'admin' / Contraseña: 'admin123' creados.")
    print("Base de datos lista para usar.")

if __name__ == "__main__":
    create_initial_data()