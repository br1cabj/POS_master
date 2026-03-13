import logging

from sqlalchemy.orm import sessionmaker

from database.models import Supplier

logger = logging.getLogger(__name__)


class SupplierController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_all_suppliers(self, tenant_id):
		with self.Session() as session:
			try:
				# Traemos solo los proveedores activos de esta empresa
				suppliers = (
					session.query(Supplier)
					.filter_by(tenant_id=tenant_id, is_active=True)
					.order_by(Supplier.name)
					.all()
				)

				return [
					{
						'id': s.id,
						'name': s.name,
						'phone': s.phone or '',
						'email': s.email or '',
						'address': s.address or '',
					}
					for s in suppliers
				]
			except Exception as e:
				logger.error(f'Error al obtener proveedores: {e}', exc_info=True)
				return []

	def save_supplier(self, tenant_id, supplier_id, name, phone, email, address):
		if not name or not str(name).strip():
			return False, 'El nombre del proveedor es obligatorio.'

		with self.Session() as session:
			try:
				if supplier_id:
					# MODO EDICIÓN
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
					# MODO CREACIÓN
					new_supplier = Supplier(
						tenant_id=tenant_id,
						name=str(name).strip(),
						phone=str(phone).strip() if phone else None,
						email=str(email).strip() if email else None,
						address=str(address).strip() if address else None,
					)
					session.add(new_supplier)
					msg = 'Proveedor registrado con éxito.'

				session.commit()
				return True, msg
			except Exception as e:
				session.rollback()
				logger.error(f'Error guardando proveedor: {e}', exc_info=True)
				return False, 'Error interno de base de datos.'

	def delete_supplier(self, tenant_id, supplier_id):
		with self.Session() as session:
			try:
				supplier = (
					session.query(Supplier)
					.filter_by(id=supplier_id, tenant_id=tenant_id)
					.first()
				)
				if not supplier:
					return False, 'Proveedor no encontrado.'

				# Hacemos (soft-delete)
				supplier.is_active = False
				session.commit()
				return True, 'Proveedor eliminado del directorio.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error borrando proveedor: {e}', exc_info=True)
				return False, 'No se pudo eliminar al proveedor.'
