"""
controllers/quotation_controller.py
====================================
Gestión de cotizaciones / presupuestos.
Incluye CRUD, generación de PDF A4 con logo, conversión a venta y duplicado.
"""

import logging
import os
import platform
import subprocess
import tempfile
import unicodedata
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from controllers.base import BaseController
from database.models import (
	Article,
	ArticleVariant,
	CashMovement,
	CashSession,
	Quotation,
	QuotationItem,
	Sale,
	SaleDetail,
	Stock,
)
from utils import settings_manager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _sanitize(text: str) -> str:
	if not text:
		return ''
	return (
		unicodedata.normalize('NFKD', str(text))
		.encode('latin-1', 'ignore')
		.decode('latin-1')
	)


def _to_dec(value, default=Decimal('0')) -> Decimal:
	try:
		if isinstance(value, str):
			value = value.replace(',', '.')
		return Decimal(str(value))
	except Exception:
		return default


# ─────────────────────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────────────────────


class QuotationController(BaseController):
	STATUS_LABELS = {
		'borrador': 'Borrador',
		'enviada': 'Enviada',
		'aceptada': 'Aceptada',
		'rechazada': 'Rechazada',
		'vencida': 'Vencida',
	}

	STATUS_COLORS = {
		'borrador': '#6b7280',
		'enviada': '#2563eb',
		'aceptada': '#16a34a',
		'rechazada': '#dc2626',
		'vencida': '#d97706',
	}

	def __init__(self, db_engine):
		super().__init__(db_engine)
		self._pdf_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Cotizaciones')
		os.makedirs(self._pdf_dir, exist_ok=True)

	# ── Helpers internos ──────────────────────────────────────────────────────

	def _next_number(self, session: Session, tenant_id: int) -> str:
		last = (
			session.query(Quotation)
			.filter_by(tenant_id=tenant_id)
			.order_by(Quotation.id.desc())
			.first()
		)
		n = 1
		if last:
			try:
				n = int(last.number.split('-')[-1]) + 1
			except Exception:
				n = last.id + 1
		return f'COT-{n:04d}'

	def _row_to_dict(self, q: Quotation) -> dict:
		cname = q.customer.name if q.customer else ''
		uname = q.user.username if q.user else ''
		items = []
		for it in q.items:
			items.append(
				{
					'id': it.id,
					'description': it.description,
					'quantity': float(it.quantity),
					'unit_price': float(it.unit_price),
					'subtotal': float(it.subtotal),
					'variant_id': it.variant_id,
				}
			)
		return {
			'id': q.id,
			'number': q.number,
			'date': q.date.strftime('%d/%m/%Y %H:%M') if q.date else '',
			'valid_until': q.valid_until.strftime('%d/%m/%Y') if q.valid_until else '',
			'valid_until_raw': q.valid_until,
			'status': q.status,
			'status_label': self.STATUS_LABELS.get(q.status, q.status),
			'total_amount': float(q.total_amount),
			'discount_amount': float(q.discount_amount or 0),
			'notes': q.notes or '',
			'customer_id': q.customer_id,
			'customer_name': cname,
			'user_name': uname,
			'items': items,
		}

	# ── CRUD ──────────────────────────────────────────────────────────────────

	def list_quotations(self, tenant_id: int, status: str = None) -> list[dict]:
		with self._Session() as s:
			q = s.query(Quotation).filter_by(tenant_id=tenant_id)
			if status and status != 'todas':
				q = q.filter_by(status=status)
			rows = q.order_by(Quotation.date.desc()).all()
			return [self._row_to_dict(r) for r in rows]

	def get_quotation(self, quotation_id: int) -> dict | None:
		with self._Session() as s:
			q = s.get(Quotation, quotation_id)
			return self._row_to_dict(q) if q else None

	def create_quotation(
		self,
		tenant_id: int,
		user_id: int,
		items: list[dict],
		customer_id: int = None,
		valid_days: int = 15,
		notes: str = '',
		discount_amount: float = 0,
	) -> tuple[bool, str | dict]:
		try:
			with self._Session() as s:
				number = self._next_number(s, tenant_id)
				discount = _to_dec(discount_amount)

				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < 0:
					total = Decimal('0')

				valid_until = None
				if valid_days and valid_days > 0:
					valid_until = (
						datetime.utcnow() + timedelta(days=valid_days)
					).date()

				q = Quotation(
					number=number,
					tenant_id=tenant_id,
					user_id=user_id,
					customer_id=customer_id or None,
					valid_until=valid_until,
					total_amount=total,
					discount_amount=discount,
					notes=notes,
					status='borrador',
				)
				s.add(q)
				s.flush()

				for it in items:
					qi = QuotationItem(
						quotation_id=q.id,
						description=it.get('description', ''),
						quantity=_to_dec(it.get('quantity', 1)),
						unit_price=_to_dec(it.get('unit_price', 0)),
						subtotal=_to_dec(it.get('subtotal', 0)),
						variant_id=it.get('variant_id') or None,
					)
					s.add(qi)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, q.id))
		except Exception as e:
			logger.error(f'Error creando cotización: {e}', exc_info=True)
			return False, str(e)

	def update_quotation(
		self,
		quotation_id: int,
		items: list[dict],
		customer_id: int = None,
		valid_until: date = None,
		notes: str = '',
		discount_amount: float = 0,
		status: str = None,
	) -> tuple[bool, str | dict]:
		try:
			with self._Session() as s:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'

				discount = _to_dec(discount_amount)
				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < 0:
					total = Decimal('0')

				q.customer_id = customer_id or None
				q.valid_until = valid_until
				q.notes = notes
				q.discount_amount = discount
				q.total_amount = total
				if status:
					q.status = status

				# Reemplazar ítems
				for old in list(q.items):
					s.delete(old)
				s.flush()

				for it in items:
					qi = QuotationItem(
						quotation_id=q.id,
						description=it.get('description', ''),
						quantity=_to_dec(it.get('quantity', 1)),
						unit_price=_to_dec(it.get('unit_price', 0)),
						subtotal=_to_dec(it.get('subtotal', 0)),
						variant_id=it.get('variant_id') or None,
					)
					s.add(qi)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, q.id))
		except Exception as e:
			logger.error(
				f'Error actualizando cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)

	def set_status(self, quotation_id: int, new_status: str) -> tuple[bool, str]:
		valid = set(self.STATUS_LABELS.keys())
		if new_status not in valid:
			return False, f'Estado inválido: {new_status}'
		try:
			with self._Session() as s:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				q.status = new_status
				s.commit()
			return True, new_status
		except Exception as e:
			logger.error(f'Error cambiando estado: {e}', exc_info=True)
			return False, str(e)

	def delete_quotation(self, quotation_id: int) -> tuple[bool, str]:
		try:
			with self._Session() as s:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				s.delete(q)
				s.commit()
			return True, 'Eliminada.'
		except Exception as e:
			logger.error(
				f'Error eliminando cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)

	def duplicate_quotation(
		self, quotation_id: int, user_id: int
	) -> tuple[bool, str | dict]:
		"""Crea una copia como borrador con número nuevo."""
		try:
			with self._Session() as s:
				orig = s.get(Quotation, quotation_id)
				if not orig:
					return False, 'Cotización no encontrada.'

				number = self._next_number(s, orig.tenant_id)
				days_valid = (
					(orig.valid_until - datetime.utcnow().date()).days
					if orig.valid_until
					else 15
				)

				new_q = Quotation(
					number=number,
					tenant_id=orig.tenant_id,
					user_id=user_id,
					customer_id=orig.customer_id,
					valid_until=(
						(datetime.utcnow() + timedelta(days=max(days_valid, 15))).date()
						if orig.valid_until
						else None
					),
					total_amount=orig.total_amount,
					discount_amount=orig.discount_amount,
					notes=orig.notes,
					status='borrador',
				)
				s.add(new_q)
				s.flush()

				for it in orig.items:
					s.add(
						QuotationItem(
							quotation_id=new_q.id,
							description=it.description,
							quantity=it.quantity,
							unit_price=it.unit_price,
							subtotal=it.subtotal,
							variant_id=it.variant_id,
						)
					)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, new_q.id))
		except Exception as e:
			logger.error(
				f'Error duplicando cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)

	def convert_to_sale(
		self,
		quotation_id: int,
		user_id: int,
		payment_method: str = 'efectivo',
		warehouse_id: int = None,
	) -> tuple[bool, str]:
		"""
		Convierte una cotización aceptada en una venta real.
		Descuenta stock si hay variant_id en los ítems.
		Retorna (True, sale_id_str) o (False, mensaje_error).
		"""
		try:
			with self._Session() as s:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if q.status == 'rechazada':
					return False, 'No se puede convertir una cotización rechazada.'

				# Calcular profit aproximado (sin costo real disponible aquí)
				profit = q.total_amount  # se guarda como 100% si no hay costo

				sale = Sale(
					tenant_id=q.tenant_id,
					user_id=user_id,
					customer_id=q.customer_id,
					total_amount=q.total_amount,
					discount_amount=q.discount_amount,
					profit=profit,
					payment_method=payment_method,
					status='completada',
				)
				s.add(sale)
				s.flush()

				for it in q.items:
					sd = SaleDetail(
						sale_id=sale.id,
						description=it.description,
						quantity=it.quantity,
						unit_cost=Decimal('0'),
						unit_price=it.unit_price,
						subtotal=it.subtotal,
						variant_id=it.variant_id,
					)
					s.add(sd)

					# Descontar stock si hay variante y almacén
					if it.variant_id and warehouse_id:
						stock_row = (
							s.query(Stock)
							.filter_by(
								variant_id=it.variant_id, warehouse_id=warehouse_id
							)
							.first()
						)
						if stock_row:
							stock_row.quantity = max(
								Decimal('0'),
								stock_row.quantity - it.quantity,
							)

				# Movimiento de caja si hay sesión abierta
				cash_session = (
					s.query(CashSession)
					.filter_by(tenant_id=q.tenant_id, is_open=True)
					.first()
				)
				if cash_session and q.total_amount > 0:
					s.add(
						CashMovement(
							session_id=cash_session.id,
							movement_type='venta',
							amount=q.total_amount,
							description=f'Ticket #{sale.id} (desde {q.number})',
						)
					)

				q.status = 'aceptada'
				s.commit()
				return True, str(sale.id)
		except Exception as e:
			logger.error(
				f'Error convirtiendo cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)

	# ── Catálogo de artículos para autocompletar ──────────────────────────────

	def search_variants(self, tenant_id: int, query: str) -> list[dict]:
		"""Busca variantes por nombre o código de barras para el formulario."""
		try:
			with self._Session() as s:
				q_str = f'%{query}%'
				rows = (
					s.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						Article.is_active,
						ArticleVariant.is_active,
					)
					.filter(
						(Article.name.ilike(q_str))
						| (ArticleVariant.barcode.ilike(q_str))
					)
					.limit(30)
					.all()
				)
				result = []
				for v in rows:
					label = v.article.name
					if v.attribute_1:
						label += f' – {v.attribute_1}'
					if v.attribute_2:
						label += f' / {v.attribute_2}'
					result.append(
						{
							'variant_id': v.id,
							'label': label,
							'selling_price': float(v.selling_price),
							'barcode': v.barcode or '',
						}
					)
				return result
		except Exception as e:
			logger.error(f'Error buscando variantes: {e}', exc_info=True)
			return []

	# ── PDF ───────────────────────────────────────────────────────────────────

	def generate_pdf(self, quotation_id: int) -> tuple[bool, str]:
		try:
			from fpdf import FPDF

			data = self.get_quotation(quotation_id)
			if not data:
				return False, 'Cotización no encontrada.'

			cfg = settings_manager.load()
			company = _sanitize(cfg.get('company_name', 'Mi Negocio'))
			address = _sanitize(cfg.get('company_address', ''))
			phone = _sanitize(cfg.get('company_phone', ''))
			logo_path = cfg.get('company_logo_path', '')
			symbol = cfg.get('currency_symbol', '$')
			decimals = int(cfg.get('currency_decimals', 0))

			def fmt(v):
				if decimals == 0:
					return f'{symbol}{float(v):,.0f}'
				return f'{symbol}{float(v):,.{decimals}f}'

			pdf = FPDF(orientation='P', unit='mm', format='A4')
			pdf.set_auto_page_break(auto=True, margin=18)
			pdf.add_page()
			pdf.set_margins(left=18, top=12, right=18)
			W = 174  # ancho útil

			# ── LOGO ──────────────────────────────────────────────────────────
			logo_ok = (
				logo_path
				and os.path.isfile(logo_path)
				and logo_path.lower().endswith(('.png', '.jpg', '.jpeg'))
			)
			header_top = pdf.get_y()
			if logo_ok:
				try:
					pdf.image(logo_path, x=18, y=header_top, h=22)
					pdf.set_y(header_top)
					pdf.set_x(58)
					name_w = W - 40
				except Exception:
					logo_ok = False

			if not logo_ok:
				pdf.set_x(18)
				name_w = W

			# ── CABECERA empresa ──────────────────────────────────────────────
			pdf.set_font('Arial', 'B', 18)
			pdf.cell(name_w, 9, company, ln=True, align='L' if not logo_ok else 'R')
			pdf.set_font('Arial', '', 9)
			if address:
				pdf.set_x(18 if not logo_ok else 58)
				pdf.cell(name_w, 5, address, ln=True, align='L' if not logo_ok else 'R')
			if phone:
				pdf.set_x(18 if not logo_ok else 58)
				pdf.cell(
					name_w,
					5,
					f'Tel: {phone}',
					ln=True,
					align='L' if not logo_ok else 'R',
				)

			# Garantizar al menos 26mm de alto para el logo
			if logo_ok and pdf.get_y() < header_top + 26:
				pdf.set_y(header_top + 26)

			# ── LÍNEA SEPARADORA ──────────────────────────────────────────────
			pdf.set_draw_color(200, 200, 200)
			pdf.line(18, pdf.get_y() + 2, 192, pdf.get_y() + 2)
			pdf.ln(6)

			# ── TÍTULO COTIZACIÓN ─────────────────────────────────────────────
			status_label = _sanitize(data['status_label'])
			pdf.set_font('Arial', 'B', 22)
			pdf.set_text_color(30, 80, 160)
			pdf.cell(
				W, 12, f'PRESUPUESTO  {_sanitize(data["number"])}', ln=False, align='L'
			)
			pdf.set_font('Arial', '', 10)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(0, 12, f'Estado: {status_label}', ln=True, align='R')
			pdf.set_text_color(0, 0, 0)
			pdf.ln(2)

			# ── DATOS CABECERA: fecha | cliente | validez ─────────────────────
			col = W / 3
			pdf.set_font('Arial', 'B', 9)
			pdf.set_fill_color(240, 244, 255)
			for lbl in ['Fecha', 'Cliente', 'Válido hasta']:
				pdf.cell(col, 6, _sanitize(lbl), border=0, align='L', fill=True)
			pdf.ln(6)
			pdf.set_font('Arial', '', 9)
			pdf.cell(col, 6, _sanitize(data['date']), border=0, align='L')
			pdf.cell(
				col,
				6,
				_sanitize(data['customer_name'] or 'Consumidor Final'),
				border=0,
				align='L',
			)
			pdf.cell(col, 6, _sanitize(data['valid_until'] or '—'), border=0, align='L')
			pdf.ln(10)

			# ── TABLA DE ÍTEMS ────────────────────────────────────────────────
			# Encabezado
			pdf.set_fill_color(30, 80, 160)
			pdf.set_text_color(255, 255, 255)
			pdf.set_font('Arial', 'B', 9)
			col_desc = 88
			col_qty = 22
			col_price = 32
			col_sub = 32
			pdf.cell(col_desc, 7, 'Descripción', border=0, align='L', fill=True)
			pdf.cell(col_qty, 7, 'Cant.', border=0, align='C', fill=True)
			pdf.cell(col_price, 7, 'Precio Unit.', border=0, align='R', fill=True)
			pdf.cell(col_sub, 7, 'Subtotal', border=0, align='R', fill=True)
			pdf.ln(7)
			pdf.set_text_color(0, 0, 0)

			# Filas alternadas
			pdf.set_font('Arial', '', 9)
			for idx, it in enumerate(data['items']):
				fill = idx % 2 == 0
				pdf.set_fill_color(248, 250, 255) if fill else pdf.set_fill_color(
					255, 255, 255
				)
				qty = float(it['quantity'])
				qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.3f}'
				pdf.cell(
					col_desc,
					6,
					_sanitize(it['description'])[:55],
					border=0,
					align='L',
					fill=fill,
				)
				pdf.cell(col_qty, 6, qty_str, border=0, align='C', fill=fill)
				pdf.cell(
					col_price, 6, fmt(it['unit_price']), border=0, align='R', fill=fill
				)
				pdf.cell(
					col_sub, 6, fmt(it['subtotal']), border=0, align='R', fill=fill
				)
				pdf.ln(6)

			pdf.ln(3)
			pdf.set_draw_color(200, 200, 200)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(4)

			# ── TOTALES ───────────────────────────────────────────────────────
			subtotal_val = sum(it['subtotal'] for it in data['items'])
			discount_val = float(data['discount_amount'])

			def total_row(label, value, bold=False, color=None):
				x_lbl = 18 + col_desc + col_qty
				pdf.set_x(x_lbl)
				if bold:
					pdf.set_font('Arial', 'B', 10)
				else:
					pdf.set_font('Arial', '', 9)
				if color:
					pdf.set_text_color(*color)
				pdf.cell(col_price, 6, _sanitize(label), border=0, align='L')
				pdf.cell(col_sub, 6, value, border=0, align='R')
				if color:
					pdf.set_text_color(0, 0, 0)
				pdf.ln(6)

			total_row('Subtotal:', fmt(subtotal_val))
			if discount_val > 0:
				total_row('Descuento:', f'-{fmt(discount_val)}', color=(180, 100, 0))
			total_row('TOTAL:', fmt(data['total_amount']), bold=True)

			# ── NOTAS ─────────────────────────────────────────────────────────
			if data['notes']:
				pdf.ln(8)
				pdf.set_font('Arial', 'B', 9)
				pdf.cell(W, 5, 'Condiciones / Notas:', ln=True)
				pdf.set_font('Arial', '', 9)
				pdf.set_text_color(80, 80, 80)
				pdf.multi_cell(W, 5, _sanitize(data['notes']))
				pdf.set_text_color(0, 0, 0)

			# ── PIE ───────────────────────────────────────────────────────────
			pdf.ln(10)
			pdf.set_font('Arial', 'I', 8)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(
				W,
				5,
				'Gracias por su consulta. Este presupuesto es orientativo y puede variar.',
				align='C',
			)

			# ── GUARDAR ───────────────────────────────────────────────────────
			filepath = os.path.join(
				self._pdf_dir,
				f'cotizacion_{_sanitize(data["number"]).replace("-", "_")}.pdf',
			)
			pdf.output(filepath)
			self._open_file(filepath)
			return True, filepath

		except Exception as e:
			logger.error(
				f'Error generando PDF cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)

	def _open_file(self, filepath: str) -> bool:
		try:
			abs_path = os.path.abspath(filepath)
			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path], capture_output=True)
			else:
				subprocess.run(['xdg-open', abs_path], capture_output=True)
			return True
		except Exception as e:
			logger.warning(f'No se pudo abrir el PDF: {e}')
			return False
