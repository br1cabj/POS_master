from datetime import datetime

from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession


class CashController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_active_session(self, tenant_id, user_id):
		session = self.Session()
		try:
			return (
				session.query(CashSession)
				.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
				.first()
			)
		finally:
			session.close()

	def open_session(self, tenant_id, user_id, opening_balance):
		session = self.Session()
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
				opening_balance=float(opening_balance),
				opening_time=datetime.utcnow(),
				is_open=True,
			)
			session.add(new_session)
			session.commit()
			return True, 'Caja abierta exitosamente.'
		except Exception as e:
			session.rollback()
			return False, f'Error: {str(e)}'
		finally:
			session.close()

	def close_session(self, session_id, closing_balance):
		session = self.Session()
		try:
			cash_session = session.query(CashSession).filter_by(id=session_id).first()
			if not cash_session:
				return False, 'Turno no encontrado.'

			cash_session.closing_balance = float(closing_balance)
			cash_session.closing_time = datetime.utcnow()
			cash_session.is_open = False
			session.commit()
			return True, 'Caja cerrada correctamente.'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()

	def get_session_summary(self, session_id):
		"""Calcula los totales de la caja en tiempo real"""
		session = self.Session()
		try:
			movements = (
				session.query(CashMovement).filter_by(session_id=session_id).all()
			)

			total_ventas = sum(
				m.amount for m in movements if m.movement_type == 'venta'
			)
			total_ingresos = sum(
				m.amount for m in movements if m.movement_type == 'ingreso'
			)
			total_gastos = sum(
				m.amount for m in movements if m.movement_type == 'gasto'
			)

			return total_ventas, total_ingresos, total_gastos
		finally:
			session.close()

	def add_manual_movement(self, session_id, mov_type, amount, description):
		"""Registra un ingreso o retiro de dinero manual"""
		session = self.Session()
		try:
			new_mov = CashMovement(
				session_id=session_id,
				movement_type=mov_type,
				amount=float(amount),
				description=description,
			)
			session.add(new_mov)
			session.commit()
			return True, 'Movimiento registrado con éxito.'
		except Exception as e:
			session.rollback()
			return False, str(e)
		finally:
			session.close()
