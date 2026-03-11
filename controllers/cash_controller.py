from datetime import datetime

from sqlalchemy.orm import sessionmaker

from database.models import CashSession


class CashController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_active_session(self, tenant_id, user_id):
		"""Busca si el usuario ya tiene un turno de caja abierto"""
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
		"""Abre un nuevo turno de caja"""
		session = self.Session()
		try:
			# Doble verificación por si acaso
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
			return True, 'Caja abierta exitosamente. ¡Buen turno!'
		except Exception as e:
			session.rollback()
			return False, f'Error: {str(e)}'
		finally:
			session.close()

	def close_session(self, session_id, closing_balance):
		"""Cierra el turno de caja actual"""
		session = self.Session()
		try:
			cash_session = session.query(CashSession).filter_by(id=session_id).first()
			if not cash_session:
				return False, 'Turno de caja no encontrado.'

			cash_session.closing_balance = float(closing_balance)
			cash_session.closing_time = datetime.utcnow()
			cash_session.is_open = False

			session.commit()
			return True, 'Caja cerrada correctamente. ¡Buen descanso!'
		except Exception as e:
			session.rollback()
			return False, f'Error al cerrar: {str(e)}'
		finally:
			session.close()
