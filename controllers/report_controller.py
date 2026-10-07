"""
controllers/report_controller.py
==================================
Genera todos los datos necesarios para el Reporte de Cierre.

Método principal: get_report_data(tenant_id, date_from, date_to) → dict

Incluye:
  - KPIs del período (ventas, ganancia, margen, tickets, ticket promedio)
  - Comparativa vs. período anterior de igual duración
  - Desglose por método de pago
  - Conteo de anulaciones y devoluciones
  - Top 8 productos del período (cantidad + revenue)
  - Movimientos manuales de caja (gastos / ingresos)
  - Exportación a PDF (fpdf 1.7.x) y CSV
"""

import csv
import logging
import os
import tempfile
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fpdf import FPDF
from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from controllers.user_controller import get_display_name
from database.models import (
	CashMovement,
	CashSession,
	Sale,
	SaleDetail,
)
from utils.csv_utils import safe_spreadsheet_text
from utils.settings_manager import fmt_price, get, get_reports_path

logger = logging.getLogger(__name__)

_SOLD_STATUSES = ('completada', 'parcial')


def _sanitize(text: str) -> str:
	"""Elimina caracteres especiales problemáticos para FPDF (latin-1)."""
	if not text:
		return ''
	return (
		unicodedata.normalize('NFKD', str(text))
		.encode('latin-1', 'ignore')
		.decode('latin-1')
	)


class _ReportPDF(FPDF):
	"""PDF with unobtrusive page numbering for reports that span multiple pages."""

	def footer(self):
		self.set_y(-12)
		self.set_font('Arial', '', 8)
		self.set_text_color(110, 110, 110)
		self.cell(0, 6, f'Página {self.page_no()}/{{nb}}', align='C')


class ReportController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	# =========================================================
	# CONSULTA PRINCIPAL
	# =========================================================
	def get_report_data(self, tenant_id: int, date_from: date, date_to: date) -> dict:
		"""
		Devuelve un dict con todos los datos del reporte para el período indicado.
		También incluye la comparativa con el período anterior de la misma duración.
		"""
		if date_from > date_to:
			raise ValueError(
				'La fecha inicial no puede ser posterior a la fecha final.'
			)
		dt_from = datetime.combine(date_from, datetime.min.time())
		dt_to = datetime.combine(date_to, datetime.max.time())

		# Período anterior de igual duración para comparativa
		delta = (date_to - date_from) + timedelta(days=1)
		prev_to = date_from - timedelta(days=1)
		prev_from = prev_to - timedelta(days=delta.days - 1)
		dt_prev_from = datetime.combine(prev_from, datetime.min.time())
		dt_prev_to = datetime.combine(prev_to, datetime.max.time())

		with self._Session() as session:
			try:
				current = self._query_period(session, tenant_id, dt_from, dt_to)
				previous = self._query_period(
					session, tenant_id, dt_prev_from, dt_prev_to
				)
				movements = self._query_movements(session, tenant_id, dt_from, dt_to)
				top = self._query_top_products(session, tenant_id, dt_from, dt_to)
				cancels = self._query_cancellations(session, tenant_id, dt_from, dt_to)

				return {
					'_tenant_id': tenant_id,
					'period': {'from': date_from, 'to': date_to},
					'current': current,
					'previous': previous,
					'movements': movements,
					'top_products': top,
					'cancellations': cancels,
				}
			except Exception as e:
				logger.error('Error al generar reporte: %s', e, exc_info=True)
				raise

	# =========================================================
	# QUERIES INTERNAS
	# =========================================================
	def _query_period(self, session, tenant_id, dt_from, dt_to) -> dict:
		"""KPIs + desglose por método de pago para un rango de fechas."""
		row = (
			session.query(
				func.coalesce(
					func.sum(Sale.total_amount - func.coalesce(Sale.total_returned, 0)),
					0,
				),
				func.coalesce(func.sum(Sale.profit), 0),
				func.count(Sale.id),
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
			)
			.first()
		)
		revenue = float(row[0] or 0)
		profit = float(row[1] or 0)
		tickets = int(row[2] or 0)
		margin = (profit / revenue * 100) if revenue > 0 else 0.0
		avg = revenue / tickets if tickets > 0 else 0.0

		by_method = {}
		payment_rows = (
			session.query(
				Sale.payment_method,
				Sale.payment_method_2,
				Sale.total_amount,
				Sale.total_returned,
				Sale.amount_method_1,
				Sale.amount_method_2,
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
			)
			.all()
		)
		for pm1, pm2, gross, returned, amount1, amount2 in payment_rows:
			gross = Decimal(str(gross or 0))
			returned = min(Decimal(str(returned or 0)), gross)
			net = max(gross - returned, Decimal('0'))
			if net <= 0:
				continue
			second = Decimal(str(amount2 or 0)) if pm2 else Decimal('0')
			first = Decimal(str(amount1)) if amount1 is not None else gross - second
			original_paid = first + second
			if original_paid <= 0:
				first, second, original_paid = gross, Decimal('0'), gross
			second_net = (
				(net * second / original_paid).quantize(
					Decimal('0.01'), rounding=ROUND_HALF_UP
				)
				if pm2 and second > 0
				else Decimal('0')
			)
			for method, method_net in (
				(pm1 or 'efectivo', net - second_net),
				(pm2, second_net),
			):
				if not method or method_net <= 0:
					continue
				key = str(method).strip().casefold() or 'efectivo'
				info = by_method.setdefault(key, {'total': Decimal('0'), 'count': 0})
				info['total'] += method_net
				info['count'] += 1
		by_method = {
			method: {'total': float(info['total']), 'count': info['count']}
			for method, info in by_method.items()
		}

		return {
			'revenue': revenue,
			'profit': profit,
			'tickets': tickets,
			'margin': margin,
			'avg_ticket': avg,
			'by_method': by_method,
		}

	def _query_top_products(self, session, tenant_id, dt_from, dt_to, limit=8) -> list:
		rows = (
			session.query(
				Sale.id,
				SaleDetail.description,
				SaleDetail.quantity,
				SaleDetail.returned_quantity,
				SaleDetail.subtotal,
				SaleDetail.unit_price,
				Sale.total_amount,
			)
			.join(Sale)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
			)
			.all()
		)
		gross_by_sale = {}
		for sale_id, _description, _qty, _returned_qty, subtotal, *_ in rows:
			gross_by_sale[sale_id] = gross_by_sale.get(sale_id, Decimal('0')) + Decimal(
				str(subtotal or 0)
			)
		products = {}
		for (
			sale_id,
			description,
			qty,
			returned_qty,
			subtotal,
			unit_price,
			sale_total,
		) in rows:
			qty = Decimal(str(qty or 0))
			retained_qty = max(qty - Decimal(str(returned_qty or 0)), Decimal('0'))
			if retained_qty <= 0:
				continue
			gross_items = gross_by_sale.get(sale_id, Decimal('0'))
			discount_factor = Decimal(str(sale_total or 0)) / max(
				gross_items, Decimal('0.01')
			)
			# Sales store line subtotals before the sale-wide discount. Allocate that
			# discount proportionally, then subtract quantities actually returned.
			unit_net = Decimal(str(unit_price or 0)) * max(
				min(discount_factor, Decimal('1')), Decimal('0')
			)
			entry = products.setdefault(
				str(description or ''),
				{'quantity': Decimal('0'), 'revenue': Decimal('0')},
			)
			entry['quantity'] += retained_qty
			entry['revenue'] += retained_qty * unit_net
		return [
			{
				'description': description,
				'quantity': float(values['quantity']),
				'revenue': float(values['revenue']),
			}
			for description, values in sorted(
				products.items(), key=lambda item: item[1]['quantity'], reverse=True
			)[:limit]
		]

	def _query_cancellations(self, session, tenant_id, dt_from, dt_to) -> dict:
		row = (
			session.query(
				func.count(Sale.id),
				func.coalesce(
					func.sum(
						case(
							(
								Sale.status.in_(('anulada', 'cancelada')),
								Sale.total_amount,
							),
							(
								Sale.status == 'devuelta',
								case(
									(Sale.total_returned > 0, Sale.total_returned),
									else_=Sale.total_amount,
								),
							),
							(
								Sale.status == 'parcial',
								func.coalesce(Sale.total_returned, 0),
							),
							else_=0,
						)
					),
					0,
				),
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(('anulada', 'cancelada', 'devuelta', 'parcial')),
			)
			.first()
		)
		return {
			'count': int(row[0] or 0),
			'total': float(row[1] or 0),
		}

	def _query_movements(self, session, tenant_id, dt_from, dt_to) -> dict:
		"""Gastos e ingresos manuales de caja en el período."""
		rows = (
			session.query(
				CashMovement.movement_type,
				CashMovement.description,
				CashMovement.amount,
				CashMovement.time,
			)
			.join(CashSession)
			.filter(
				CashSession.tenant_id == tenant_id,
				CashMovement.movement_type.in_(('gasto', 'ingreso')),
				CashMovement.time.between(dt_from, dt_to),
				or_(
					CashMovement.description.is_(None),
					~CashMovement.description.ilike('%Ticket #%'),
				),
			)
			.order_by(CashMovement.time)
			.all()
		)
		gastos = [r for r in rows if r[0] == 'gasto']
		ingresos = [r for r in rows if r[0] == 'ingreso']
		return {
			'gastos': [
				{'desc': r[1], 'amount': float(r[2]), 'time': r[3]} for r in gastos
			],
			'ingresos': [
				{'desc': r[1], 'amount': float(r[2]), 'time': r[3]} for r in ingresos
			],
			# Sumar con Decimal para evitar errores de precisión flotante, luego convertir
			'total_gastos': float(sum(Decimal(str(r[2] or 0)) for r in gastos)),
			'total_ingresos': float(sum(Decimal(str(r[2] or 0)) for r in ingresos)),
		}

	# =========================================================
	# EXPORTACIÓN PDF
	# =========================================================
	def export_pdf(self, data: dict, company_name: str = 'Mi Negocio') -> str:
		"""Genera un PDF A4 con el reporte completo. Retorna la ruta del archivo."""
		period = data['period']
		current = data['current']
		prev = data['previous']
		top = data['top_products']
		cancels = data['cancellations']
		movs = data['movements']

		date_from_str = period['from'].strftime('%d/%m/%Y')
		date_to_str = period['to'].strftime('%d/%m/%Y')
		period_label = (
			f'{date_from_str}'
			if date_from_str == date_to_str
			else f'{date_from_str} al {date_to_str}'
		)

		pdf = _ReportPDF('P', 'mm', 'A4')
		pdf.alias_nb_pages()
		pdf.set_auto_page_break(auto=True, margin=15)
		pdf.add_page()
		W = 190
		pdf.set_title(f'Reporte de cierre {period_label}')
		pdf.set_author(_sanitize(company_name))

		# ── Encabezado ────────────────────────────────────────
		logo_path = get('company_logo_path', '')
		header_x, header_w = 10, W
		if logo_path and os.path.isfile(logo_path):
			try:
				pdf.image(logo_path, x=12, y=10, w=22, h=22, keep_aspect_ratio=True)
				header_x, header_w = 38, 162
			except Exception as exc:
				logger.warning('No se pudo insertar el logo en el reporte: %s', exc)
		company_label = _sanitize(company_name.upper())[:70]
		company_font_size = min(20, max(10, 500 // max(len(company_label), 1)))
		pdf.set_font('Arial', 'B', company_font_size)
		pdf.set_xy(header_x, 12)
		pdf.cell(
			header_w,
			9,
			company_label,
			new_x='LMARGIN',
			new_y='LAST',
			align='C',
		)
		pdf.set_xy(header_x, 21)
		pdf.set_font('Arial', '', 11)
		pdf.cell(
			header_w, 6, 'REPORTE DE CIERRE', new_x='LMARGIN', new_y='LAST', align='C'
		)
		pdf.set_xy(10, 34)
		pdf.set_font('Arial', 'B', 13)
		pdf.cell(
			W,
			8,
			_sanitize(f'Periodo: {period_label}'),
			new_x='LMARGIN',
			new_y='NEXT',
			align='C',
		)
		pdf.set_font('Arial', '', 9)
		pdf.cell(
			W,
			5,
			f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
			new_x='LMARGIN',
			new_y='NEXT',
			align='C',
		)
		pdf.ln(4)
		pdf.line(10, pdf.get_y(), 200, pdf.get_y())
		pdf.ln(6)

		# ── KPIs ─────────────────────────────────────────────
		self._pdf_section(pdf, 'RESUMEN GENERAL')

		def _pct_change(curr, prev, percentage_points=False):
			if percentage_points:
				delta = curr - prev
				arrow = '(+)' if delta >= 0 else '(-)'
				return f'{arrow} {abs(delta):.1f} pp vs periodo anterior'
			if prev == 0:
				return '- vs anterior'
			pct = (curr - prev) / prev * 100
			# CORRECCIÓN: Caracteres seguros para FPDF 1.7.2
			arrow = '(+)' if pct >= 0 else '(-)'
			return f'{arrow} {abs(pct):.1f}% vs periodo anterior'

		kpis = [
			(
				'Total Ventas',
				self._pdf_money(current['revenue']),
				_pct_change(current['revenue'], prev['revenue']),
			),
			(
				'Ganancia Neta',
				self._pdf_money(current['profit']),
				_pct_change(current['profit'], prev['profit']),
			),
			(
				'Margen',
				f'{current["margin"]:.1f}%',
				_pct_change(current['margin'], prev['margin'], percentage_points=True),
			),
			(
				'Tickets Emitidos',
				str(current['tickets']),
				_pct_change(current['tickets'], prev['tickets']),
			),
			(
				'Ticket Promedio',
				self._pdf_money(current['avg_ticket']),
				_pct_change(current['avg_ticket'], prev['avg_ticket']),
			),
		]
		for label, value, comp in kpis:
			pdf.set_font('Arial', '', 11)
			pdf.cell(80, 7, _sanitize(label + ':'))
			pdf.set_font('Arial', 'B', 11)
			pdf.cell(40, 7, value)
			pdf.set_font('Arial', 'I', 9)
			pdf.cell(0, 7, _sanitize(comp), new_x='LMARGIN', new_y='NEXT')
		pdf.ln(4)

		# ── Por método de pago ────────────────────────────────
		self._pdf_section(pdf, 'DESGLOSE POR METODO DE PAGO')
		for method, info in current['by_method'].items():
			pdf.set_font('Arial', '', 11)
			pdf.cell(60, 7, _sanitize(method.capitalize() + ':'))
			pdf.set_font('Arial', 'B', 11)
			pdf.cell(50, 7, self._pdf_money(info['total']))
			pdf.set_font('Arial', '', 10)
			pdf.cell(0, 7, f'({info["count"]} tickets)', new_x='LMARGIN', new_y='NEXT')
		pdf.ln(4)

		# ── Anulaciones ───────────────────────────────────────
		self._pdf_section(pdf, 'ANULACIONES Y DEVOLUCIONES')
		pdf.set_font('Arial', '', 11)
		pdf.cell(80, 7, 'Tickets anulados/devueltos:')
		pdf.set_font('Arial', 'B', 11)
		pdf.cell(
			0,
			7,
			f'{cancels["count"]}  ({self._pdf_money(cancels["total"])})',
			new_x='LMARGIN',
			new_y='NEXT',
		)
		pdf.ln(4)

		# ── Top productos ────────────────────────────────────
		if top:
			self._pdf_section(pdf, f'TOP {len(top)} PRODUCTOS DEL PERIODO')
			for i, item in enumerate(top, 1):
				qty = item['quantity']
				qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.2f}'
				pdf.set_font('Arial', '', 10)
				desc = _sanitize(item['description'])[:35]
				pdf.cell(10, 6, f'{i}.')
				pdf.cell(90, 6, desc)
				pdf.set_font('Arial', 'B', 10)
				pdf.cell(25, 6, f'{qty_str} u', align='R')
				pdf.cell(
					0,
					6,
					self._pdf_money(item['revenue']),
					new_x='LMARGIN',
					new_y='NEXT',
					align='R',
				)
			pdf.ln(4)

		# ── Movimientos de caja ───────────────────────────────
		movement_time_format = (
			'%d/%m %H:%M' if period['from'] != period['to'] else '%H:%M'
		)
		if movs['gastos'] or movs['ingresos']:
			self._pdf_section(pdf, 'MOVIMIENTOS MANUALES DE CAJA')
			if movs['ingresos']:
				pdf.set_font('Arial', 'BI', 10)
				pdf.cell(
					W,
					6,
					f'Ingresos  (Total: {self._pdf_money(movs["total_ingresos"])})',
					new_x='LMARGIN',
					new_y='NEXT',
				)
				for m in movs['ingresos']:
					pdf.set_font('Arial', '', 10)
					t = m['time'].strftime(movement_time_format) if m['time'] else ''
					pdf.cell(20, 5, t)
					pdf.cell(120, 5, _sanitize(m['desc'] or '')[:50])
					pdf.cell(
						0,
						5,
						self._pdf_money(m['amount']),
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
				pdf.ln(2)
			if movs['gastos']:
				pdf.set_font('Arial', 'BI', 10)
				pdf.cell(
					W,
					6,
					f'Gastos  (Total: {self._pdf_money(movs["total_gastos"])})',
					new_x='LMARGIN',
					new_y='NEXT',
				)
				for m in movs['gastos']:
					pdf.set_font('Arial', '', 10)
					t = m['time'].strftime(movement_time_format) if m['time'] else ''
					pdf.cell(20, 5, t)
					pdf.cell(120, 5, _sanitize(m['desc'] or '')[:50])
					pdf.cell(
						0,
						5,
						self._pdf_money(m['amount']),
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
				pdf.ln(4)

		# ── Firma ────────────────────────────────────────────
		pdf.ln(10)
		pdf.set_font('Arial', '', 10)
		pdf.cell(
			W,
			5,
			'___________________________',
			new_x='LMARGIN',
			new_y='NEXT',
			align='C',
		)
		pdf.cell(
			W, 5, 'Firma del responsable', new_x='LMARGIN', new_y='NEXT', align='C'
		)

		# Guardar en un destino único y reemplazarlo solo cuando el PDF esté completo.
		filepath = self._unique_export_path('Reporte', period, '.pdf')
		fd, temp_path = tempfile.mkstemp(
			prefix='cloudpos-report-', suffix='.pdf', dir=os.path.dirname(filepath)
		)
		os.close(fd)
		try:
			pdf.output(temp_path)
			os.replace(temp_path, filepath)
		except Exception:
			try:
				os.remove(temp_path)
			except OSError:
				pass
			raise
		return filepath

	@staticmethod
	def _pdf_money(amount) -> str:
		value = fmt_price(amount)
		for symbol, replacement in (('€', 'EUR '), ('£', 'GBP '), ('¥', 'JPY ')):
			value = value.replace(symbol, replacement)
		return _sanitize(value)

	@staticmethod
	def _unique_export_path(prefix: str, period: dict, extension: str) -> str:
		folder = get_reports_path()
		os.makedirs(folder, exist_ok=True)
		date_part = (
			f'{period["from"].strftime("%Y%m%d")}_{period["to"].strftime("%Y%m%d")}'
		)
		stamp = datetime.now().strftime('%H%M%S_%f')
		return os.path.join(
			folder, f'{prefix}_{date_part}_{stamp}_{uuid.uuid4().hex[:6]}{extension}'
		)

	def _pdf_section(self, pdf, title: str):
		pdf.set_font('Arial', 'B', 12)
		pdf.set_fill_color(40, 40, 40)
		pdf.set_text_color(255, 255, 255)  # CORRECCIÓN: Letra blanca para fondo oscuro
		pdf.cell(
			190, 8, f'  {_sanitize(title)}', new_x='LMARGIN', new_y='NEXT', fill=True
		)
		pdf.set_text_color(0, 0, 0)  # Vuelve a negro
		pdf.ln(2)

	# =========================================================
	# EXPORTACIÓN CSV
	# =========================================================
	def export_csv(self, data: dict) -> str:
		"""Exporta ventas del período a CSV. Retorna la ruta del archivo."""
		period = data['period']
		dt_from = datetime.combine(period['from'], datetime.min.time())
		dt_to = datetime.combine(period['to'], datetime.max.time())

		filepath = self._unique_export_path('Ventas', period, '.csv')

		with self._Session() as session:
			sales = (
				session.query(Sale)
				.options(joinedload(Sale.customer), joinedload(Sale.user))
				.filter(
					Sale.tenant_id == data['_tenant_id'],
					Sale.date.between(dt_from, dt_to),
					Sale.status.in_(_SOLD_STATUSES),
				)
				.order_by(Sale.date)
				.all()
			)
			fd, temp_path = tempfile.mkstemp(
				prefix='cloudpos-sales-', suffix='.csv', dir=os.path.dirname(filepath)
			)
			try:
				with os.fdopen(fd, 'w', newline='', encoding='utf-8-sig') as f:
					w = csv.writer(f, delimiter=';')
					w.writerow(
						[
							'ID',
							'Fecha',
							'Cliente',
							'Vendedor',
							'Total original',
							'Devoluciones',
							'Total neto',
							'Ganancia neta',
							'Método 1',
							'Monto método 1',
							'Método 2',
							'Monto método 2',
							'Estado',
						]
					)
					for s in sales:
						gross = Decimal(str(s.total_amount or 0))
						net = max(
							gross - Decimal(str(s.total_returned or 0)), Decimal('0')
						)
						method2_amount = Decimal(str(s.amount_method_2 or 0))
						method1_amount = (
							Decimal(str(s.amount_method_1))
							if s.amount_method_1 is not None
							else gross - method2_amount
						)
						paid_total = method1_amount + method2_amount
						if paid_total > 0:
							net_method2 = (
								(net * method2_amount / paid_total).quantize(
									Decimal('0.01'), rounding=ROUND_HALF_UP
								)
								if s.payment_method_2 and method2_amount > 0
								else Decimal('0')
							)
							net_method1 = net - net_method2
						else:
							net_method1, net_method2 = net, Decimal('0')
						w.writerow(
							[
								s.id,
								s.date.strftime('%d/%m/%Y %H:%M') if s.date else '',
								safe_spreadsheet_text(
									s.customer.name
									if s.customer
									else 'Consumidor Final'
								),
								safe_spreadsheet_text(
									get_display_name(s.user) if s.user else '—'
								),
								float(s.total_amount or 0),
								float(s.total_returned or 0),
								float((s.total_amount or 0) - (s.total_returned or 0)),
								float(s.profit or 0),
								safe_spreadsheet_text(s.payment_method or ''),
								float(net_method1),
								safe_spreadsheet_text(s.payment_method_2 or ''),
								float(net_method2),
								safe_spreadsheet_text(s.status or ''),
							]
						)
				os.replace(temp_path, filepath)
			except Exception:
				try:
					os.remove(temp_path)
				except OSError:
					pass
				raise
		return filepath
