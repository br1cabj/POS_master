import pytest
from decimal import Decimal
from utils.shared import parse_decimal, get_or_create_default_warehouse
from database.models import Branch, Warehouse

class TestParseDecimal:
    def test_parse_valid_string_with_dot(self):
        assert parse_decimal("15.50") == Decimal("15.50")

    def test_parse_valid_string_with_comma(self):
        assert parse_decimal("15,50") == Decimal("15.50")

    def test_parse_integer(self):
        assert parse_decimal(15) == Decimal("15")

    def test_parse_float(self):
        # Flotantes pueden tener problemas de precisión, se convierten a string en la función
        assert parse_decimal(15.5) == Decimal("15.5")

    def test_parse_none(self):
        assert parse_decimal(None) is None
        assert parse_decimal(None, default=Decimal("0.0")) == Decimal("0.0")

    def test_parse_empty_string(self):
        assert parse_decimal("") is None
        assert parse_decimal("   ", default=Decimal("0")) == Decimal("0")

    def test_parse_invalid_string(self):
        assert parse_decimal("abc") is None
        assert parse_decimal("15.5.5", default=Decimal("1")) == Decimal("1")


class TestGetOrCreateDefaultWarehouse:
    def test_creates_branch_and_warehouse_when_not_exist(self, test_db_session):
        tenant_id = "test-tenant-123"
        
        # Ejecutar función
        warehouse_id = get_or_create_default_warehouse(test_db_session, tenant_id)
        
        # Verificar que retornó un ID
        assert warehouse_id is not None
        
        # Verificar en base de datos - Sucursal
        branch = test_db_session.query(Branch).filter_by(tenant_id=tenant_id, name='Sede Principal').first()
        assert branch is not None
        assert branch.name == 'Sede Principal'
        
        # Verificar en base de datos - Depósito
        warehouse = test_db_session.query(Warehouse).filter_by(tenant_id=tenant_id, id=warehouse_id).first()
        assert warehouse is not None
        assert warehouse.name == 'Depósito General'
        assert warehouse.branch_id == branch.id

    def test_returns_existing_warehouse(self, test_db_session):
        tenant_id = "test-tenant-456"
        
        # Ejecutar por primera vez para crear
        warehouse_id_1 = get_or_create_default_warehouse(test_db_session, tenant_id)
        
        # Ejecutar por segunda vez
        warehouse_id_2 = get_or_create_default_warehouse(test_db_session, tenant_id)
        
        # Verificar que es el mismo ID
        assert warehouse_id_1 == warehouse_id_2
        
        # Verificar que no se duplicaron registros
        branches_count = test_db_session.query(Branch).filter_by(tenant_id=tenant_id).count()
        warehouses_count = test_db_session.query(Warehouse).filter_by(tenant_id=tenant_id).count()
        
        assert branches_count == 1
        assert warehouses_count == 1
