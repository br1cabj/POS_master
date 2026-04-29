"""
utils/shared.py
===============
Funciones de utilidad compartidas y operaciones comunes de base de datos.
"""

import logging
from decimal import Decimal, InvalidOperation

from database.models import Branch, Warehouse

logger = logging.getLogger(__name__)


def parse_decimal(value, default=None):
	"""
	Convierte un valor a Decimal de forma segura.
	Acepta strings con coma (ej. '1,50') y numéricos.
	Retorna `default` si el valor es nulo, vacío o inválido.
	"""
	if value is None:
		return default

	try:
		if isinstance(value, str):
			value = value.strip().replace(',', '.')
			if not value:
				return default
		return Decimal(str(value))
	except (ValueError, TypeError, InvalidOperation):
		return default


def get_or_create_default_warehouse(session, tenant_id):
	"""
	Recupera el ID del depósito 'Depósito General' de la 'Sede Principal'.
	Si las entidades no existen, las crea garantizando el aislamiento por tenant.
	Lanza excepción en cascada si falla para permitir el rollback del caller.
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
		.filter_by(tenant_id=tenant_id, branch_id=branch.id, name='Depósito General')
		.first()
	)
	if not warehouse:
		warehouse = Warehouse(
			name='Depósito General', branch_id=branch.id, tenant_id=tenant_id
		)
		session.add(warehouse)
		session.flush()

	return warehouse.id
