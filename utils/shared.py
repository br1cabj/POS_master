import logging
from decimal import Decimal, InvalidOperation

from database.models import Branch, Warehouse

logger = logging.getLogger(__name__)


def parse_decimal(value, default=None):
	"""
	Convierte un valor a Decimal de forma segura.
	Acepta strings con coma (ej. '1,50') y números.
	Retorna `default` si el valor es inválido.
	"""
	try:
		if isinstance(value, str):
			value = value.replace(',', '.')
		return Decimal(str(value))
	except (ValueError, TypeError, InvalidOperation):
		return default


def get_or_create_default_warehouse(session, tenant_id):
	"""
	Retorna el ID del depósito 'Depósito General' de la 'Sede Principal'.
	Si no existe, crea la sucursal y/o el depósito automáticamente.
	Lanza excepción si falla para que el caller pueda hacer rollback.
	"""
	branch = (
		session.query(Branch)
		.filter_by(tenant_id=tenant_id, name='Sede Principal')
		.first()
	)
	if not branch:
		branch = Branch(name='Sede Principal', tenant_id=tenant_id)
		session.add(branch)
		session.flush()

	warehouse = (
		session.query(Warehouse)
		.filter_by(branch_id=branch.id, name='Depósito General')
		.first()
	)
	if not warehouse:
		warehouse = Warehouse(name='Depósito General', branch_id=branch.id)
		session.add(warehouse)
		session.flush()

	return warehouse.id
