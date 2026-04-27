import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fpdf import FPDF
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import CashMovement, CashSession
from utils.config import make_engine
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)

_default_engine = make_engine()


class CashController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		super().__init__(engine)
		self.reports_dir = 'reportes_caja'
		os.makedirs(self.reports_dir, exist_ok=True)

	def _parse_decimal(self, value):
		return parse_decimal(value, default=None)

	def get_active_session(self, tenant_id, user_id):
		"""Retorna la sesión de caja abierta del usuario, o None si no hay ninguna."""
		with self._Session() as session:
			try:
				active = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if not active:
					return None
				return {
					'id': active.id,
					'tenant_id': active.tenant_id,
					'user_id': active.user_id,
					'opening_balance': active.opening_balance,
					'opening_time': active.opened_at,
				}
			except Exception as e:
				logger.error(
					f'Error al buscar sesión activa de caja: {e}', exc_info=True
				)
				return None

	def open_session(self, tenant_id, user_id, opening_balance):
		"""Abre una nueva sesión de caja. Falla si ya existe una activa para el usuario."""
		parsed = self._parse_decimal(opening_balance)
		if parsed is None or parsed < Decimal('0.0'):
			return (
				False,
				'El monto de apertura debe ser un número válido y no negativo.',
			)

		with self._Session() as session:
			try:
				# with_for_update() evita race condition si dos procesos abren caja simultáneamente
				existing = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.with_for_update()
					.first()
				)
				if existing:
					return False, 'Ya tienes una caja abierta.'

				session.add(
					CashSession(
						tenant_id=tenant_id,
						user_id=user_id,
						opening_balance=parsed,
						opened_at=datetime.now(),
						is_open=True,
					)
				)
				session.commit()
				return True, 'Caja abierta exitosamente.'
			except Exception as e:
				session.rollback()
				logger.error(f'Error al abrir caja: {e}', exc_info=True)
				return False, 'Error interno al intentar abrir la caja.'

	def close_session(self, tenant_id, session_id, declared_amount):
		"""
		Cierra la caja realizando el arqueo blind close: calcula el monto esperado,
		compara con el declarado, persiste la diferencia y genera el Reporte Z en PDF.
		El PDF se genera post-commit para no bloquear la transacción.
		"""
		parsed_declared = self._parse_decimal(declared_amount)
		if parsed_declared is None or parsed_declared < Decimal('0.0'):
			return False, 'El monto declarado debe ser un número válido y no negativo.'

		with self._Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.options(joinedload(CashSession.user))
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)
				if not cash_session:
					return False, 'Turno de caja no encontrado o no tienes permiso.'
				if not cash_session.is_open:
					return False, 'Esta caja ya se encuentra cerrada.'

				ventas, ingresos, gastos = self.get_session_summary(
					tenant_id, session_id
				)
				opening = cash_session.opening_balance or Decimal('0.0')
				expected = opening + ventas + ingresos - gastos
				difference = parsed_declared - expected

				cash_session.expected_amount = expected
				cash_session.declared_amount = parsed_declared
				cash_session.difference = difference
				cash_session.closed_at = datetime.now()
				cash_session.is_open = False
				if hasattr(cash_session, 'closing_balance'):
					cash_session.closing_balance = parsed_declared

				user_name = (
					cash_session.user.username if cash_session.user else 'Cajero'
				)
				session.commit()

				pdf_path = self._generate_z_report_pdf(
					cash_session.id,
					user_name,
					opening,
					ventas,
					ingresos,
					gastos,
					expected,
					parsed_declared,
					difference,
				)

				estado = (
					'SOBRANTE'
					if difference > 0
					else 'FALTANTE'
					if difference < 0
					else 'CUADRE PERFECTO'
				)
				return True, (
					f'Caja cerrada correctamente.\n\n'
					f'Resultado del Arqueo: {estado}\n'
					f'Diferencia: ${abs(difference):.2f}\n\n'
					f'Reporte Z guardado en: {pdf_path}'
				)
			except Exception as e:
				session.rollback()
				logger.error(f'Error al cerrar caja {session_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar cerrar la caja.'

	def get_session_summary(self, tenant_id, session_id):
		"""Retorna (ventas, ingresos, gastos) como Decimals para la sesión indicada."""
		with self._Session() as session:
			try:
				if (
					not session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				):
					return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

				totals = {
					'venta': Decimal('0.0'),
					'ingreso': Decimal('0.0'),
					'gasto': Decimal('0.0'),
				}
				for mov_type, amount in (
					session.query(
						CashMovement.movement_type, func.sum(CashMovement.amount)
					)
					.filter_by(session_id=session_id)
					.group_by(CashMovement.movement_type)
					.all()
				):
					if mov_type in totals:
						totals[mov_type] = (
							Decimal(str(amount)) if amount else Decimal('0.0')
						)

				return totals['venta'], totals['ingreso'], totals['gasto']
			except Exception as e:
				logger.error(
					f'Error al generar resumen de caja {session_id}: {e}', exc_info=True
				)
				return Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

	def add_manual_movement(self, tenant_id, session_id, mov_type, amount, description):
		"""Registra un movimiento manual. Solo opera sobre sesiones activas del tenant."""
		parsed = self._parse_decimal(amount)
		if parsed is None or parsed <= Decimal('0.0'):
			return False, 'El monto debe ser un número válido y mayor a cero.'
		if mov_type not in ['ingreso', 'gasto', 'venta']:
			return False, 'Tipo de movimiento no válido.'
		if not description or not str(description).strip():
			return False, 'La descripción del movimiento es obligatoria.'

		with self._Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)
				if not cash_session or not cash_session.is_open:
					return False, 'Sesión de caja no encontrada o ya está cerrada.'

				session.add(
					CashMovement(
						session_id=session_id,
						movement_type=mov_type,
						amount=parsed,
						description=str(description).strip(),
					)
				)
				session.commit()
				return True, 'Movimiento registrado con éxito.'
			except Exception as e:
				session.rollback()
				logger.error(
					f'Error al registrar movimiento en caja {session_id}: {e}',
					exc_info=True,
				)
				return False, 'Error interno al registrar el movimiento.'

	def _generate_z_report_pdf(
		self,
		session_id,
		username,
		opening,
		ventas,
		ingresos,
		gastos,
		expected,
		declared,
		difference,
	):
		"""Genera el Reporte Z en formato A5. Retorna la ruta del archivo creado."""
		pdf = FPDF(format='A5')
		pdf.add_page()
		pdf.set_auto_page_break(auto=True, margin=15)

		pdf.set_font('Arial', 'B', 16)
		pdf.cell(0, 10, 'REPORTE Z - CIERRE DE CAJA', ln=True, align='C')
		pdf.set_font('Arial', '', 10)
		pdf.cell(
			0,
			5,
			f'Fecha de Cierre: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
			ln=True,
			align='C',
		)
		pdf.cell(
			0,
			5,
			f'Turno Nro: {session_id} | Cajero: {username.capitalize()}',
			ln=True,
			align='C',
		)
		pdf.line(10, 35, 138, 35)
		pdf.ln(10)

		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'RESUMEN DE MOVIMIENTOS', ln=True)
		pdf.set_font('Arial', '', 12)
		for label, value in [
			('Monto de Apertura (+):', opening),
			('Total Ventas (+):', ventas),
			('Ingresos Manuales (+):', ingresos),
			('Retiros / Gastos (-):', gastos),
		]:
			pdf.cell(80, 8, label)
			pdf.cell(0, 8, f'${value:.2f}', ln=True, align='R')

		pdf.line(10, pdf.get_y() + 2, 138, pdf.get_y() + 2)
		pdf.ln(5)

		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'ARQUEO DE CAJA (BLIND CLOSE)', ln=True)
		pdf.set_font('Arial', '', 12)
		pdf.cell(80, 8, 'Monto Esperado (Sistema):')
		pdf.cell(0, 8, f'${expected:.2f}', ln=True, align='R')
		pdf.cell(80, 8, 'Monto Declarado (Cajero):')
		pdf.cell(0, 8, f'${declared:.2f}', ln=True, align='R')

		if difference < 0:
			pdf.set_text_color(200, 0, 0)

		estado = (
			'SOBRANTE'
			if difference > 0
			else 'FALTANTE'
			if difference < 0
			else 'CUADRE PERFECTO'
		)
		pdf.set_font('Arial', 'B', 14)
		pdf.cell(80, 10, f'DIFERENCIA ({estado}):')
		pdf.cell(0, 10, f'${difference:.2f}', ln=True, align='R')
		pdf.set_text_color(0, 0, 0)

		pdf.ln(20)
		pdf.set_font('Arial', '', 10)
		pdf.cell(0, 5, '_______________________', ln=True, align='C')
		pdf.cell(0, 5, 'Firma del Cajero', ln=True, align='C')

		filename = os.path.join(
			self.reports_dir,
			f'ReporteZ_Turno{session_id}_{datetime.now().strftime("%Y%m%d")}.pdf',
		)
		pdf.output(filename)
		return filename
