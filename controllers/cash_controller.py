import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession

logger = logging.getLogger(__name__)


class CashController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _parse_decimal(self, value):
		"""Usamos Decimal en lugar de float para dinero exacto."""
		try:
			if isinstance(value, str):
				value = value.replace(',', '.')
			return Decimal(str(value))
		except (ValueError, TypeError, InvalidOperation):
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
		parsed_balance = self._parse_decimal(opening_balance)
		if parsed_balance is None or parsed_balance < Decimal('0.0'):
			return (
				False,
				'El monto de apertura debe ser un número válido y no negativo.',
			)

		with self.Session() as session:
			try:
				# Verificamos si ya hay una caja abierta para este usuario y tenant
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

	def close_session(self, tenant_id, session_id, closing_balance):
		"""🛡️ ESCUDO: Requiere tenant_id"""
		parsed_balance = self._parse_decimal(closing_balance)
		if parsed_balance is None or parsed_balance < Decimal('0.0'):
			return False, 'El monto de cierre debe ser un número válido y no negativo.'

		with self.Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)

				if not cash_session:
					return False, 'Turno de caja no encontrado o no tienes permiso.'

				if not cash_session.is_open:
					return False, 'Esta caja ya se encuentra cerrada.'

				cash_session.closing_balance = parsed_balance
				cash_session.closing_time = datetime.utcnow()
				cash_session.is_open = False
				session.commit()
				return True, 'Caja cerrada correctamente.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al cerrar caja {session_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar cerrar la caja.'

	def get_session_summary(self, tenant_id, session_id):
		"""🛡️ ESCUDO: Requiere tenant_id para evitar espionaje financiero"""
		with self.Session() as session:
			try:
				valid_session = (
					session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)
				if not valid_session:
					return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

				results = (
					session.query(
						CashMovement.movement_type, func.sum(CashMovement.amount)
					)
					.filter_by(session_id=session_id)
					.group_by(CashMovement.movement_type)
					.all()
				)

				total_ventas = Decimal('0.0')
				total_ingresos = Decimal('0.0')
				total_gastos = Decimal('0.0')

				for mov_type, total_amount in results:
					# func.sum devuelve None si no hay registros, lo aseguramos a Decimal
					monto = (
						Decimal(str(total_amount)) if total_amount else Decimal('0.0')
					)

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
				return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

	def add_manual_movement(self, tenant_id, session_id, mov_type, amount, description):
		"""Requiere tenant_id y validar estado de la caja"""
		parsed_amount = self._parse_decimal(amount)
		if parsed_amount is None or parsed_amount <= Decimal('0.0'):
			return (
				False,
				'El monto del movimiento debe ser un número válido y mayor a cero.',
			)

		if mov_type not in ['ingreso', 'gasto', 'venta']:
			return False, 'Tipo de movimiento no válido.'

		if not description or len(str(description).strip()) == 0:
			return False, 'La descripción del movimiento es obligatoria.'

		with self.Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)

				if not cash_session:
					return False, 'Sesión de caja no encontrada o no autorizada.'

				if not cash_session.is_open:
					return (
						False,
						'No puedes agregar movimientos a una caja que ya está cerrada.',
					)

				new_mov = CashMovement(
					session_id=session_id,
					movement_type=mov_type,
					amount=parsed_amount,
					description=str(description).strip(),
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
