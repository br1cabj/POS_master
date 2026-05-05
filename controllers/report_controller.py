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
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal

from fpdf import FPDF
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import (
	CashMovement,
	CashSession,
	Sale,
	SaleDetail,
)
from utils.config import make_engine
from utils.settings_manager import get_reports_path

logger = logging.getLogger(__name__)

_default_engine = None


def _get_default_engine():
	global _default_engine
	if _default_engine is None:
		_default_engine = make_engine()
	return _default_engine


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


class ReportController(BaseController):
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _get_default_engine()
		super().__init__(engine)

	# =========================================================
	# CONSULTA PRINCIPAL
	# =========================================================
	def get_report_data(self, tenant_id: int, date_from: date, date_to: date) -> dict:
		"""
		Devuelve un dict con todos los datos del reporte para el período indicado.
		También incluye la comparativa con el período anterior de la misma duración.
		"""
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
				logger.error(f'Error al generar reporte: {e}', exc_info=True)
				return self._empty_report(tenant_id, date_from, date_to)

	# =========================================================
	# QUERIES INTERNAS
	# =========================================================
	def _query_period(self, session, tenant_id, dt_from, dt_to) -> dict:
		"""KPIs + desglose por método de pago para un rango de fechas."""
		row = (
			session.query(
				func.coalesce(func.sum(Sale.total_amount), 0),
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
		# Deduct amount_method_2 from method 1 totals so mixed-payment sales
		# are correctly distributed across both methods
		for pm, total, count in (
			session.query(
				Sale.payment_method,
				func.coalesce(
					func.sum(Sale.total_amount - func.coalesce(Sale.amount_method_2, 0)), 0
				),
				func.count(Sale.id),
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
			)
			.group_by(Sale.payment_method)
			.all()
		):
			by_method[pm or 'efectivo'] = {
				'total': float(total or 0),
				'count': int(count or 0),
			}
		# Add method 2 amounts separately
		for pm2, total2, count2 in (
			session.query(
				Sale.payment_method_2,
				func.coalesce(func.sum(Sale.amount_method_2), 0),
				func.count(Sale.id),
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
				Sale.payment_method_2.isnot(None),
				Sale.amount_method_2 > 0,
			)
			.group_by(Sale.payment_method_2)
			.all()
		):
			key2 = pm2 or 'efectivo'
			if key2 in by_method:
				by_method[key2]['total'] += float(total2 or 0)
				by_method[key2]['count'] += int(count2 or 0)
			else:
				by_method[key2] = {
					'total': float(total2 or 0),
					'count': int(count2 or 0),
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
				SaleDetail.description,
				func.sum(SaleDetail.quantity).label('qty'),
				func.sum(SaleDetail.subtotal).label('revenue'),
			)
			.join(Sale)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(_SOLD_STATUSES),
			)
			.group_by(SaleDetail.description)
			.order_by(func.sum(SaleDetail.quantity).desc())
			.limit(limit)
			.all()
		)
		return [
			{
				'description': r[0],
				'quantity': float(r[1] or 0),
				'revenue': float(r[2] or 0),
			}
			for r in rows
		]

	def _query_cancellations(self, session, tenant_id, dt_from, dt_to) -> dict:
		row = (
			session.query(
				func.count(Sale.id),
				func.coalesce(func.sum(Sale.total_amount), 0),
			)
			.filter(
				Sale.tenant_id == tenant_id,
				Sale.date.between(dt_from, dt_to),
				Sale.status.in_(
					('anulada', 'devuelta')
				),  # CORRECCIÓN: Removido 'parcial'
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
				~CashMovement.description.ilike('%Ticket #%'),
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

		pdf = FPDF('P', 'mm', 'A4')
		pdf.set_auto_page_break(auto=True, margin=15)
		pdf.add_page()
		W = 190

		# ── Encabezado ────────────────────────────────────────
		pdf.set_font('Arial', 'B', 20)
		pdf.cell(W, 10, _sanitize(company_name.upper()), ln=1, align='C')
		pdf.set_font('Arial', '', 11)
		pdf.cell(W, 6, 'REPORTE DE CIERRE', ln=1, align='C')
		pdf.set_font('Arial', 'B', 13)
		pdf.cell(W, 8, _sanitize(f'Periodo: {period_label}'), ln=1, align='C')
		pdf.set_font('Arial', '', 9)
		pdf.cell(
			W,
			5,
			f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
			ln=1,
			align='C',
		)
		pdf.ln(4)
		pdf.line(10, pdf.get_y(), 200, pdf.get_y())
		pdf.ln(6)

		# ── KPIs ─────────────────────────────────────────────
		self._pdf_section(pdf, 'RESUMEN GENERAL')

		def _pct_change(curr, prev):
			if prev == 0:
				return '- vs anterior'
			pct = (curr - prev) / prev * 100
			# CORRECCIÓN: Caracteres seguros para FPDF 1.7.2
			arrow = '(+)' if pct >= 0 else '(-)'
			return f'{arrow} {abs(pct):.1f}% vs periodo anterior'

		kpis = [
			(
				'Total Ventas',
				f'${current["revenue"]:,.0f}',
				_pct_change(current['revenue'], prev['revenue']),
			),
			(
				'Ganancia Neta',
				f'${current["profit"]:,.0f}',
				_pct_change(current['profit'], prev['profit']),
			),
			(
				'Margen',
				f'{current["margin"]:.1f}%',
				_pct_change(current['margin'], prev['margin']),
			),
			(
				'Tickets Emitidos',
				str(current['tickets']),
				_pct_change(current['tickets'], prev['tickets']),
			),
			(
				'Ticket Promedio',
				f'${current["avg_ticket"]:,.0f}',
				_pct_change(current['avg_ticket'], prev['avg_ticket']),
			),
		]
		for label, value, comp in kpis:
			pdf.set_font('Arial', '', 11)
			pdf.cell(80, 7, _sanitize(label + ':'))
			pdf.set_font('Arial', 'B', 11)
			pdf.cell(40, 7, value)
			pdf.set_font('Arial', 'I', 9)
			pdf.cell(0, 7, _sanitize(comp), ln=1)
		pdf.ln(4)

		# ── Por método de pago ────────────────────────────────
		self._pdf_section(pdf, 'DESGLOSE POR METODO DE PAGO')
		for method, info in current['by_method'].items():
			pdf.set_font('Arial', '', 11)
			pdf.cell(60, 7, _sanitize(method.capitalize() + ':'))
			pdf.set_font('Arial', 'B', 11)
			pdf.cell(50, 7, f'${info["total"]:,.0f}')
			pdf.set_font('Arial', '', 10)
			pdf.cell(0, 7, f'({info["count"]} tickets)', ln=1)
		pdf.ln(4)

		# ── Anulaciones ───────────────────────────────────────
		self._pdf_section(pdf, 'ANULACIONES Y DEVOLUCIONES')
		pdf.set_font('Arial', '', 11)
		pdf.cell(80, 7, 'Tickets anulados/devueltos:')
		pdf.set_font('Arial', 'B', 11)
		pdf.cell(0, 7, f'{cancels["count"]}  (${cancels["total"]:,.0f})', ln=1)
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
				pdf.cell(0, 6, f'${item["revenue"]:,.0f}', ln=1, align='R')
			pdf.ln(4)

		# ── Movimientos de caja ───────────────────────────────
		if movs['gastos'] or movs['ingresos']:
			self._pdf_section(pdf, 'MOVIMIENTOS MANUALES DE CAJA')
			if movs['ingresos']:
				pdf.set_font('Arial', 'BI', 10)
				pdf.cell(
					W, 6, f'Ingresos  (Total: ${movs["total_ingresos"]:,.0f})', ln=1
				)
				for m in movs['ingresos']:
					pdf.set_font('Arial', '', 10)
					t = m['time'].strftime('%H:%M') if m['time'] else ''
					pdf.cell(20, 5, t)
					pdf.cell(120, 5, _sanitize(m['desc'] or '')[:50])
					pdf.cell(0, 5, f'${m["amount"]:,.0f}', ln=1, align='R')
				pdf.ln(2)
			if movs['gastos']:
				pdf.set_font('Arial', 'BI', 10)
				pdf.cell(W, 6, f'Gastos  (Total: ${movs["total_gastos"]:,.0f})', ln=1)
				for m in movs['gastos']:
					pdf.set_font('Arial', '', 10)
					t = m['time'].strftime('%H:%M') if m['time'] else ''
					pdf.cell(20, 5, t)
					pdf.cell(120, 5, _sanitize(m['desc'] or '')[:50])
					pdf.cell(0, 5, f'${m["amount"]:,.0f}', ln=1, align='R')
				pdf.ln(4)

		# ── Firma ────────────────────────────────────────────
		pdf.ln(10)
		pdf.set_font('Arial', '', 10)
		pdf.cell(W, 5, '___________________________', ln=1, align='C')
		pdf.cell(W, 5, 'Firma del responsable', ln=1, align='C')

		# Guardar
		fname = f'Reporte_{period["from"].strftime("%Y%m%d")}_{period["to"].strftime("%Y%m%d")}.pdf'
		filepath = os.path.join(get_reports_path(), fname)
		pdf.output(filepath)
		return filepath

	def _pdf_section(self, pdf, title: str):
		pdf.set_font('Arial', 'B', 12)
		pdf.set_fill_color(40, 40, 40)
		pdf.set_text_color(255, 255, 255)  # CORRECCIÓN: Letra blanca para fondo oscuro
		pdf.cell(190, 8, f'  {_sanitize(title)}', ln=1, fill=True)
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

		desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
		if not os.path.isdir(desktop):
			desktop = os.path.expanduser('~')
		fname = f'Ventas_{period["from"].strftime("%Y%m%d")}_{period["to"].strftime("%Y%m%d")}.csv'
		filepath = os.path.join(desktop, fname)

		with self._Session() as session:
			sales = (
				session.query(Sale)
				.options(joinedload(Sale.customer), joinedload(Sale.user))
				.filter(
					Sale.tenant_id == data['_tenant_id'],
					Sale.date.between(dt_from, dt_to),
				)
				.order_by(Sale.date)
				.all()
			)
			with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
				w = csv.writer(f)
				w.writerow(
					[
						'ID',
						'Fecha',
						'Cliente',
						'Vendedor',
						'Total',
						'Ganancia',
						'Método',
						'Estado',
					]
				)
				for s in sales:
					w.writerow(
						[
							s.id,
							s.date.strftime('%d/%m/%Y %H:%M') if s.date else '',
							s.customer.name if s.customer else 'Consumidor Final',
							s.user.username if s.user else '—',
							float(s.total_amount or 0),
							float(s.profit or 0),
							s.payment_method or '',
							s.status or '',
						]
					)
		return filepath

	# =========================================================
	# HELPER
	# =========================================================
	@staticmethod
	def _empty_report(tenant_id, date_from, date_to) -> dict:
		_empty = {
			'revenue': 0,
			'profit': 0,
			'tickets': 0,
			'margin': 0,
			'avg_ticket': 0,
			'by_method': {},
		}
		return {
			'_tenant_id': tenant_id,
			'period': {'from': date_from, 'to': date_to},
			'current': _empty,
			'previous': _empty,
			'movements': {
				'gastos': [],
				'ingresos': [],
				'total_gastos': 0,
				'total_ingresos': 0,
			},
			'top_products': [],
			'cancellations': {'count': 0, 'total': 0},
		}
