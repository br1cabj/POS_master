import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Supplier

DB_URL = 'sqlite:///pos_system.db'
_default_engine = create_engine(DB_URL)

logger = logging.getLogger(__name__)


class SupplierController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def get_all_suppliers(self, tenant_id):
		with self.SessionLocal() as session:
			try:
				return [
					{
						'id': s.id,
						'name': s.name,
						'phone': s.phone or '',
						'email': s.email or '',
						'address': s.address or '',
					}
					for s in session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.order_by(Supplier.name)
					.all()
				]
			except Exception as e:
				logger.error(f'Error al obtener proveedores: {e}', exc_info=True)
				return []

	def save_supplier(self, tenant_id, supplier_id, name, phone, email, address):
		"""Crea o actualiza un proveedor según si se provee supplier_id."""
		if not name or not str(name).strip():
			return False, 'El nombre del proveedor es obligatorio.'

		with self.SessionLocal() as session:
			try:
				if supplier_id:
					supplier = (
						session.query(Supplier)
						.filter_by(id=supplier_id, tenant_id=tenant_id)
						.first()
					)
					if not supplier:
						return False, 'Proveedor no encontrado.'
					supplier.name = str(name).strip()
					supplier.phone = str(phone).strip() if phone else None
					supplier.email = str(email).strip() if email else None
					supplier.address = str(address).strip() if address else None
					msg = 'Proveedor actualizado correctamente.'
				else:
					session.add(
						Supplier(
							tenant_id=tenant_id,
							name=str(name).strip(),
							phone=str(phone).strip() if phone else None,
							email=str(email).strip() if email else None,
							address=str(address).strip() if address else None,
						)
					)
					msg = 'Proveedor registrado con éxito.'

				session.commit()
				return True, msg
			except Exception as e:
				session.rollback()
				logger.error(f'Error guardando proveedor: {e}', exc_info=True)
				return False, 'Error interno de base de datos.'

	def delete_supplier(self, tenant_id, supplier_id):
		"""Baja lógica del proveedor para preservar historial de compras."""
		with self.SessionLocal() as session:
			try:
				supplier = (
					session.query(Supplier)
					.filter_by(id=supplier_id, tenant_id=tenant_id)
					.first()
				)
				if not supplier:
					return False, 'Proveedor no encontrado.'
				supplier.is_active = False
				session.commit()
				return True, 'Proveedor eliminado del directorio.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error borrando proveedor: {e}', exc_info=True)
				return False, 'No se pudo eliminar al proveedor.'
