import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fpdf import FPDF
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import CashMovement, CashSession

logger = logging.getLogger(__name__)


class CashController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

		# 🛡️ Crear carpeta para los reportes si no existe
		self.reports_dir = 'reportes_caja'
		if not os.path.exists(self.reports_dir):
			os.makedirs(self.reports_dir)

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
						# Para compatibilidad si usabas opening_time
						'opening_time': active.opened_at
						if hasattr(active, 'opened_at')
						else active.opening_time,
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
					opened_at=datetime.now(),
					is_open=True,
				)
				session.add(new_session)
				session.commit()
				return True, 'Caja abierta exitosamente.'

			except Exception as e:
				session.rollback()
				logger.error(f'Error al abrir caja: {e}', exc_info=True)
				return False, 'Error interno al intentar abrir la caja.'

	# 🛡️ MEJORA NIVEL DIOS: CIERRE CIEGO
	def close_session(self, tenant_id, session_id, declared_amount):
		"""Cierra la caja calculando faltantes/sobrantes y genera el Reporte Z"""
		parsed_declared = self._parse_decimal(declared_amount)
		if parsed_declared is None or parsed_declared < Decimal('0.0'):
			return False, 'El monto declarado debe ser un número válido y no negativo.'

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

				# 1. Calculamos el monto esperado de forma estricta
				total_ventas, total_ingresos, total_gastos = self.get_session_summary(
					tenant_id, session_id
				)

				opening = cash_session.opening_balance or Decimal('0.0')
				expected_amount = opening + total_ventas + total_ingresos - total_gastos

				# 2. Calculamos la diferencia (Negativo = Faltante plata, Positivo = Sobra plata)
				difference = parsed_declared - expected_amount

				# 3. Guardamos los datos de auditoría
				cash_session.expected_amount = expected_amount
				cash_session.declared_amount = parsed_declared
				cash_session.difference = difference

				cash_session.closed_at = datetime.now()
				cash_session.is_open = False

				# Para retrocompatibilidad si aún tienes la columna vieja
				if hasattr(cash_session, 'closing_balance'):
					cash_session.closing_balance = parsed_declared

				session.commit()

				# 4. 🖨️ Generamos el Reporte Z en PDF
				user_name = (
					cash_session.user.username if cash_session.user else 'Cajero'
				)
				pdf_path = self._generate_z_report_pdf(
					cash_session.id,
					user_name,
					opening,
					total_ventas,
					total_ingresos,
					total_gastos,
					expected_amount,
					parsed_declared,
					difference,
				)

				# Formateamos el mensaje para la UI
				estado_dif = (
					'SOBRANTE'
					if difference > 0
					else 'FALTANTE'
					if difference < 0
					else 'CUADRE PERFECTO'
				)
				msg = f'Caja cerrada correctamente.\n\nResultado del Arqueo: {estado_dif}\nDiferencia: ${abs(difference):.2f}\n\nReporte Z guardado en: {pdf_path}'

				return True, msg

			except Exception as e:
				session.rollback()
				logger.error(f'Error al cerrar caja {session_id}: {e}', exc_info=True)
				return False, 'Error interno al intentar cerrar la caja.'

	def get_session_summary(self, tenant_id, session_id):
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
				if not cash_session or not cash_session.is_open:
					return False, 'Sesión de caja no encontrada o ya está cerrada.'

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

	# ==========================================
	# 🖨️ GENERADOR DEL REPORTE Z
	# ==========================================
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
		"""Crea un PDF detallado ideal para imprimir en tiquetera o guardar en la oficina"""
		pdf = FPDF(format='A5')  # Formato pequeño, similar a un ticket largo
		pdf.add_page()
		pdf.set_auto_page_break(auto=True, margin=15)

		# Encabezado
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

		# Resumen de Movimientos
		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'RESUMEN DE MOVIMIENTOS', ln=True)
		pdf.set_font('Arial', '', 12)

		pdf.cell(80, 8, 'Monto de Apertura (+):')
		pdf.cell(0, 8, f'${opening:.2f}', ln=True, align='R')

		pdf.cell(80, 8, 'Total Ventas (+):')
		pdf.cell(0, 8, f'${ventas:.2f}', ln=True, align='R')

		pdf.cell(80, 8, 'Ingresos Manuales (+):')
		pdf.cell(0, 8, f'${ingresos:.2f}', ln=True, align='R')

		pdf.cell(80, 8, 'Retiros / Gastos (-):')
		pdf.cell(0, 8, f'${gastos:.2f}', ln=True, align='R')

		pdf.line(10, pdf.get_y() + 2, 138, pdf.get_y() + 2)
		pdf.ln(5)

		# Arqueo
		pdf.set_font('Arial', 'B', 12)
		pdf.cell(0, 8, 'ARQUEO DE CAJA (BLIND CLOSE)', ln=True)
		pdf.set_font('Arial', '', 12)

		pdf.cell(80, 8, 'Monto Esperado (Sistema):')
		pdf.cell(0, 8, f'${expected:.2f}', ln=True, align='R')

		pdf.cell(80, 8, 'Monto Declarado (Cajero):')
		pdf.cell(0, 8, f'${declared:.2f}', ln=True, align='R')

		# Color rojo para faltante, negro para sobrante/cuadre
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
		pdf.set_text_color(0, 0, 0)  # Reset color

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
