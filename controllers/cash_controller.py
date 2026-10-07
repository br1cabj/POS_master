"""
controllers/cash_controller.py
==============================
Controlador de sesiones de caja, arqueos y reportes Z.
"""

import logging
import os
import unicodedata
from datetime import datetime
from decimal import Decimal

from fpdf import FPDF
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
from database.models import CashMovement, CashSession
from utils.settings_manager import fmt_price, get, get_reports_path
from utils.shared import parse_decimal

logger = logging.getLogger(__name__)


def _sanitize(text: str) -> str:
	"""Elimina caracteres especiales problemáticos para la codificación latin-1 de FPDF."""
	if not text:
		return ''
	return (
		unicodedata.normalize('NFKD', str(text))
		.encode('latin-1', 'ignore')
		.decode('latin-1')
	)


def _pdf_money(amount) -> str:
	value = fmt_price(amount)
	for symbol, replacement in (('€', 'EUR '), ('£', 'GBP '), ('¥', 'JPY ')):
		value = value.replace(symbol, replacement)
	return _sanitize(value)


class CashController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _parse_decimal(self, value):
		"""Convierte un valor a Decimal de forma segura."""
		return parse_decimal(value, default=None)

	def get_active_session(self, tenant_id, user_id):
		"""Retorna un diccionario con los datos de la sesión activa del usuario, o None si no existe."""
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
					'Error al buscar sesión activa de caja: %s', e, exc_info=True
				)
				return None

	def open_session(self, tenant_id, user_id, opening_balance):
		"""Abre una nueva sesión de caja. Retorna una tupla (bool, str) con el resultado de la operación."""
		parsed = self._parse_decimal(opening_balance)
		if parsed is None or parsed < Decimal('0.0'):
			return False, 'El monto de apertura debe ser numérico y no negativo.'

		with self._Session() as session:
			try:
				existing = (
					session.query(CashSession)
					.filter_by(tenant_id=tenant_id, user_id=user_id, is_open=True)
					.with_for_update()
					.first()
				)
				if existing:
					return False, 'El usuario ya posee una caja abierta.'

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
				logger.error('Error al abrir caja: %s', e, exc_info=True)
				return False, 'Error interno del servidor al abrir la caja.'

	def close_session(self, tenant_id, session_id, declared_amount):
		"""Ejecuta el cierre ciego de caja, calcula diferencias, persiste el estado y genera el Reporte Z."""
		parsed_declared = self._parse_decimal(declared_amount)
		if parsed_declared is None or parsed_declared < Decimal('0.0'):
			return False, 'El monto declarado debe ser numérico y no negativo.'

		with self._Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.options(joinedload(CashSession.user))
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)
				if not cash_session:
					return False, 'Turno de caja inexistente o acceso denegado.'
				if not cash_session.is_open:
					return (
						False,
						'La sesión de caja seleccionada ya se encuentra cerrada.',
					)

				ventas, ingresos, gastos, ventas_digital = self.get_session_summary(
					tenant_id, session_id, db_session=session
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
					get_display_name(cash_session.user)
					if cash_session.user
					else 'Cajero'
				)
				session.commit()

				# PDF generation is non-fatal: the session is already committed
				pdf_path = None
				try:
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
						ventas_digital,
						cash_session.closed_at,
					)
				except Exception as pdf_err:
					logger.warning(
						'Caja %s cerrada, pero falló la generación del Reporte Z: %s',
						session_id,
						pdf_err,
					)

				estado = (
					'SOBRANTE'
					if difference > 0
					else 'FALTANTE'
					if difference < 0
					else 'CUADRE PERFECTO'
				)

				pdf_msg = (
					f'\n\nReporte Z guardado en: {pdf_path}'
					if pdf_path
					else '\n\nAdvertencia: No se pudo generar el Reporte Z.'
				)

				return True, (
					f'Caja cerrada correctamente.\n\n'
					f'Resultado del Arqueo: {estado}\n'
					f'Diferencia: {fmt_price(abs(difference))}' + pdf_msg
				)
			except Exception as e:
				session.rollback()
				logger.error(
					'Error al cerrar caja %s: %s', session_id, e, exc_info=True
				)
				return False, 'Error interno del servidor al cerrar la caja.'

	def get_session_summary(self, tenant_id, session_id, db_session=None):
		"""
		Calcula los totales de ventas, ingresos y egresos de la sesión.
		Acepta una sesión de SQLAlchemy existente para prevenir deadlocks.
		"""
		if db_session is not None:
			return self._compute_session_summary(db_session, tenant_id, session_id)
		with self._Session() as session:
			return self._compute_session_summary(session, tenant_id, session_id)

	def _compute_session_summary(self, session, tenant_id, session_id):
		"""Lógica interna de cálculo de resumen de caja sobre una sesión ya abierta."""
		try:
			cash_session = (
				session.query(CashSession)
				.filter_by(id=session_id, tenant_id=tenant_id)
				.first()
			)
			if not cash_session:
				return Decimal('0.0'), Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

			totals = {
				'ingreso': Decimal('0.0'),
				'gasto': Decimal('0.0'),
			}

			for mov_type, amount in (
				session.query(CashMovement.movement_type, func.sum(CashMovement.amount))
				.filter_by(session_id=session_id)
				.group_by(CashMovement.movement_type)
				.all()
			):
				if mov_type in totals:
					totals[mov_type] = (
						Decimal(str(amount)) if amount else Decimal('0.0')
					)

			# Solo las ventas en efectivo ('venta') afectan el saldo físico de caja.
			# Las ventas digitales ('venta_digital': tarjeta, transferencia, QR) no
			# ingresan al cajón y se excluyen del expected_amount para evitar diferencias
			# incorrectas en el arqueo ciego.
			_raw_ventas = (
				session.query(func.sum(CashMovement.amount))
				.filter(
					CashMovement.session_id == session_id,
					CashMovement.movement_type == 'venta',
				)
				.scalar()
			)
			total_ventas = Decimal(str(_raw_ventas)) if _raw_ventas else Decimal('0.0')

			_raw_digital = (
				session.query(func.sum(CashMovement.amount))
				.filter(
					CashMovement.session_id == session_id,
					CashMovement.movement_type == 'venta_digital',
				)
				.scalar()
			)
			total_digital = (
				Decimal(str(_raw_digital)) if _raw_digital else Decimal('0.0')
			)

			return total_ventas, totals['ingreso'], totals['gasto'], total_digital

		except Exception as e:
			logger.error(
				'Error al generar resumen de caja %s: %s', session_id, e, exc_info=True
			)
			return Decimal('0.0'), Decimal('0.0'), Decimal('0.0'), Decimal('0.0')

	def get_movements_list(self, tenant_id, session_id):
		"""Recupera el historial de movimientos manuales asociados a una sesión específica."""
		with self._Session() as session:
			try:
				if (
					not session.query(CashSession)
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				):
					return []

				movements = (
					session.query(CashMovement)
					.filter_by(session_id=session_id)
					.order_by(CashMovement.time.desc())
					.all()
				)
				return [
					{
						'id': m.id,
						'type': m.movement_type,
						'amount': float(m.amount),
						'description': m.description or '',
						'time': m.time.strftime('%H:%M') if m.time else '--:--',
					}
					for m in movements
				]
			except Exception as e:
				logger.error(
					'Error al obtener movimientos de caja %s: %s',
					session_id,
					e,
					exc_info=True,
				)
				return []

	def add_manual_movement(self, tenant_id, session_id, mov_type, amount, description):
		"""Inserta un nuevo movimiento de caja manual (ingreso o gasto) en la base de datos."""
		parsed = self._parse_decimal(amount)
		if parsed is None or parsed <= Decimal('0.0'):
			return False, 'El monto debe ser numérico y mayor a cero.'
		if mov_type not in ['ingreso', 'gasto']:
			return (
				False,
				'Tipo de movimiento no soportado. Solo se permiten "ingreso" o "gasto".',
			)
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
					return False, 'Sesión de caja inexistente o inactiva.'

				session.add(
					CashMovement(
						tenant_id=tenant_id,
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
					'Error al registrar movimiento en caja %s: %s',
					session_id,
					e,
					exc_info=True,
				)
				return False, 'Error interno del servidor al procesar el movimiento.'

	def get_latest_closed_session_id(self, tenant_id, user_id):
		"""Return the current user's most recently closed cash session, if any."""
		with self._Session() as session:
			row = (
				session.query(CashSession.id)
				.filter(
					CashSession.tenant_id == tenant_id,
					CashSession.user_id == user_id,
					CashSession.is_open.is_(False),
				)
				.order_by(CashSession.closed_at.desc())
				.first()
			)
			return row[0] if row else None

	def regenerate_z_report(self, tenant_id, session_id):
		"""Recreate a closed shift's Z report without changing its persisted cash close."""
		with self._Session() as session:
			try:
				cash_session = (
					session.query(CashSession)
					.options(joinedload(CashSession.user))
					.filter_by(id=session_id, tenant_id=tenant_id)
					.first()
				)
				if not cash_session or cash_session.is_open:
					return False, 'No se encontró un turno cerrado para generar el Reporte Z.'
				ventas, ingresos, gastos, ventas_digital = self.get_session_summary(
					tenant_id, session_id, db_session=session
				)
				opening = Decimal(str(cash_session.opening_balance or 0))
				expected = Decimal(str(cash_session.expected_amount or 0))
				declared = Decimal(
					str(cash_session.declared_amount or cash_session.closing_balance or 0)
				)
				difference = Decimal(str(cash_session.difference or 0))
				username = get_display_name(cash_session.user) if cash_session.user else 'Cajero'
				path = self._generate_z_report_pdf(
					cash_session.id, username, opening, ventas, ingresos, gastos,
					expected, declared, difference, ventas_digital, cash_session.closed_at,
				)
				return True, path
			except Exception as e:
				logger.error('No se pudo regenerar el Reporte Z %s: %s', session_id, e, exc_info=True)
				return False, 'No se pudo generar el Reporte Z. Revisá la carpeta de reportes y los permisos.'

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
		ventas_digital=None,
		closed_at=None,
	):
		"""Crea el documento PDF del Reporte Z y lo almacena en el directorio del usuario."""
		pdf = FPDF(format='A5')
		pdf.add_page()
		pdf.set_auto_page_break(auto=True, margin=15)

		company_name = get('company_name', 'Mi Negocio')
		logo_path = get('company_logo_path', '')
		header_x, header_width = 10, 128
		if logo_path and os.path.isfile(logo_path):
			try:
				pdf.image(logo_path, x=12, y=8, w=18, h=18, keep_aspect_ratio=True)
				header_x, header_width = 32, 106
			except Exception as exc:
				logger.warning('No se pudo insertar el logo en el Reporte Z: %s', exc)
		pdf.set_font('Arial', 'B', 10)
		pdf.set_xy(header_x, 8)
		pdf.cell(header_width, 6, _sanitize(company_name)[:55], align='C')
		pdf.set_xy(10, 17)
		pdf.set_font('Arial', 'B', 16)
		pdf.cell(128, 8, 'REPORTE Z - CIERRE DE CAJA', ln=True, align='C')
		pdf.set_font('Arial', '', 10)
		pdf.cell(
			0,
			5,
			'Fecha de Cierre: ' + (closed_at or datetime.now()).strftime('%d/%m/%Y %H:%M'),
			ln=True,
			align='C',
		)
		pdf.cell(
			0,
			5,
			_sanitize(
				'Turno Nro: ' + str(session_id) + ' | Cajero: ' + username.capitalize()
			),
			ln=True,
			align='C',
		)
		pdf.line(10, 40, 138, 40)
		pdf.set_y(40)
		pdf.ln(5)

		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'RESUMEN DE MOVIMIENTOS', ln=True)
		pdf.set_font('Arial', '', 12)

		rows_pdf = [
			('Monto de Apertura (+):', opening),
			('Ventas Efectivo (+):', ventas),
			('Ingresos Manuales (+):', ingresos),
			('Retiros / Gastos (-):', gastos),
		]
		if ventas_digital and ventas_digital > 0:
			rows_pdf.insert(2, ('Ventas Digitales (*):', ventas_digital))
		for label, value in rows_pdf:
			pdf.cell(80, 8, label)
			pdf.cell(0, 8, _pdf_money(value), ln=True, align='R')
		if ventas_digital and ventas_digital > 0:
			pdf.set_font('Arial', 'I', 9)
			pdf.cell(
				0,
				5,
				'(*) Tarjeta / Transferencia / QR. No afectan el saldo fisico.',
				ln=True,
			)
			pdf.set_font('Arial', '', 12)

		pdf.line(10, pdf.get_y() + 2, 138, pdf.get_y() + 2)
		pdf.ln(5)

		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'ARQUEO DE CAJA (BLIND CLOSE)', ln=True)
		pdf.set_font('Arial', '', 12)
		pdf.cell(80, 8, 'Monto Esperado (Sistema):')
		pdf.cell(0, 8, _pdf_money(expected), ln=True, align='R')
		pdf.cell(80, 8, 'Monto Declarado (Cajero):')
		pdf.cell(0, 8, _pdf_money(declared), ln=True, align='R')

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
		pdf.cell(0, 10, _pdf_money(difference), ln=True, align='R')
		pdf.set_text_color(0, 0, 0)

		pdf.ln(20)
		pdf.set_font('Arial', '', 10)
		pdf.cell(0, 5, '_______________________', ln=True, align='C')
		pdf.cell(0, 5, 'Firma del Cajero', ln=True, align='C')

		os.makedirs(get_reports_path(), exist_ok=True)
		filename = os.path.join(
			get_reports_path(),
			f'ReporteZ_Turno{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.pdf',
		)
		pdf.output(filename)
		return filename
