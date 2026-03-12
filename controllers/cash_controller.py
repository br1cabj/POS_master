import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession

logger = logging.getLogger(__name__)


class CashController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_float(self, value):
		"""Función auxiliar para convertir valores de la UI a float de forma segura"""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return float(value)
		except (ValueError, TypeError):
			return None

	def get_active_session(self, tenant_id, user_id):
		"""Devuelve un diccionario con los datos de la caja si está abierta, o None"""
		with self.Session() as session:
			try:
				active = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if active:
					return {
						'id': active.id,
						'tenant_id': active.tenant_id,
						'user_id': active.user_id,
						'opening_balance': active.opening_balance,
						'opening_time': active.opening_time,
					}
				return None
			except Exception as e:
				logger.error(
					f'Error al buscar sesión activa de caja: {e}', exc_info=True
				)
				return None

	def open_session(self, tenant_id, user_id, opening_balance):
		parsed_balance = self._parse_float(opening_balance)
		if parsed_balance is None or parsed_balance < 0:
			return (
				False,
				'El monto de apertura debe ser un número válido y no negativo.',
			)

		with self.Session() as session:
			try:
				active = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if active:
					return False, 'Ya tienes una caja abierta.'

				new_session = CashSession(
					tenant_id=tenant_id,
					user_id=user_id,
					opening_balance=parsed_balance,
					opening_time=datetime.utcnow(),
					is_open=True,
				)
				session.add(new_session)
				session.commit()
				return True, 'Caja abierta exitosamente.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al abrir caja: {e}', exc_info=True)
				return False, 'Error interno al intentar abrir la caja.'

	def close_session(self, session_id, closing_balance):
		parsed_balance = self._parse_float(closing_balance)
		if parsed_balance is None or parsed_balance < 0:
			return False, 'El monto de cierre debe ser un número válido y no negativo.'

		with self.Session() as session:
			try:
				cash_session = (
					session.query(CashSession).filter_by(id=session_id).first()
				)
				if not cash_session:
					return False, 'Turno de caja no encontrado.'

				cash_session.closing_balance = parsed_balance
				cash_session.closing_time = datetime.utcnow()
				cash_session.is_open = False
				session.commit()
				return True, 'Caja cerrada correctamente.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al cerrar caja {session_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar cerrar la caja.'

	def get_session_summary(self, session_id):
		"""Calcula los totales de la caja sumando directamente en la base de datos"""
		with self.Session() as session:
			try:
				# Agrupamos por tipo de movimiento y sumamos
				results = (
					session.query(
						CashMovement.movement_type, func.sum(CashMovement.amount)
					)
					.filter_by(session_id=session_id)
					.group_by(CashMovement.movement_type)
					.all()
				)

				# Inicializamos contadores
				total_ventas = 0.0
				total_ingresos = 0.0
				total_gastos = 0.0

				# Asignamos los valores agrupados
				for mov_type, total_amount in results:
					# func.sum puede devolver None si no hay registros, lo aseguramos a 0.0
					monto = float(total_amount or 0.0)

					if mov_type == 'venta':
						total_ventas = monto
					elif mov_type == 'ingreso':
						total_ingresos = monto
					elif mov_type == 'gasto':
						total_gastos = monto

				return total_ventas, total_ingresos, total_gastos

			except Exception as e:
				logger.error(
					f'Error al generar resumen de caja {session_id}: {e}', exc_info=True
				)
				# Retornamos ceros para no romper la UI si hay un fallo
				return 0.0, 0.0, 0.0

	def add_manual_movement(self, session_id, mov_type, amount, description):
		"""Registra un ingreso o retiro de dinero manual"""
		parsed_amount = self._parse_float(amount)
		if parsed_amount is None or parsed_amount <= 0:
			return False, 'El monto del movimiento debe ser un número mayor a cero.'

		if mov_type not in ['ingreso', 'gasto', 'venta']:
			return False, 'Tipo de movimiento no válido.'

		if not description or len(description.strip()) == 0:
			return False, 'La descripción del movimiento es obligatoria.'

		with self.Session() as session:
			try:
				new_mov = CashMovement(
					session_id=session_id,
					movement_type=mov_type,
					amount=parsed_amount,
					description=description.strip(),
				)
				session.add(new_mov)
				session.commit()
				return True, 'Movimiento registrado con éxito.'

			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al registrar movimiento manual en caja {session_id}: {e}',
					exc_info=True,
				)
				return False, 'Error interno al registrar el movimiento.'
