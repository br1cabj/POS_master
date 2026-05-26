import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base

@pytest.fixture
def test_db_session():
    # Crea una base de datos SQLite en memoria para las pruebas
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Limpieza
    session.close()
    Base.metadata.drop_all(engine)
