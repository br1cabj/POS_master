import logging
import re

from sqlalchemy.orm import sessionmaker

from database.models import Supplier
from utils.config import make_engine

_default_engine = make_engine()

_EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

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

	@staticmethod
	def _validate_email(email):
		"""Retorna el email en minúsculas si es válido, None si está vacío, False si es inválido."""
		if not email:
			return None
		email_clean = str(email).strip().lower()
		if not _EMAIL_PATTERN.match(email_clean):
			return False
		return email_clean

	def save_supplier(self, tenant_id, supplier_id, name, phone, email, address):
		"""Crea o actualiza un proveedor según si se provee supplier_id."""
		if not name or not str(name).strip():
			return False, 'El nombre del proveedor es obligatorio.'

		email_clean = self._validate_email(email)
		if email and email_clean is False:
			return False, 'El formato del correo electrónico es inválido.'

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
					supplier.email = email_clean
					supplier.address = str(address).strip() if address else None
					msg = 'Proveedor actualizado correctamente.'
				else:
					session.add(
						Supplier(
							tenant_id=tenant_id,
							name=str(name).strip(),
							phone=str(phone).strip() if phone else None,
							email=email_clean,
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
