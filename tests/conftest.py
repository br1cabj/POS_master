import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from database.models import Base

@pytest.fixture
def test_db_session():
    # Crea una base de datos SQLite en memoria para las pruebas
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, 'connect')
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        # SQLite otherwise accepts broken foreign keys, hiding the exact
        # integrity errors production PostgreSQL would reject.
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Limpieza
    session.close()
    Base.metadata.drop_all(engine)
