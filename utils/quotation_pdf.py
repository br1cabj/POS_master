"""
utils/quotation_pdf.py
==========================
Servicio encargado de la generación de PDFs para cotizaciones.
"""

import logging
import os
import platform
import subprocess
import unicodedata

from fpdf import FPDF

from utils import settings_manager

logger = logging.getLogger(__name__)


def _sanitize(text: str) -> str:
	"""Elimina caracteres especiales problemáticos para FPDF (latin-1)."""
	if not text:
		return ''
	return (
		unicodedata.normalize('NFKD', str(text))
		.encode('latin-1', 'ignore')
		.decode('latin-1')
	)


class QuotationPDF:
	def __init__(self, data: dict, output_dir: str):
		self.data = data
		self.output_dir = output_dir

	def generate(self) -> tuple[bool, str]:
		"""Genera el PDF y lo abre automáticamente. Retorna (éxito, ruta_o_error)."""
		try:
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

			# ── CABECERA ──────────────────────────────────────────────────────
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

			if logo_ok and pdf.get_y() < header_top + 26:
				pdf.set_y(header_top + 26)

			# ── SEPARADOR ─────────────────────────────────────────────────────
			pdf.set_draw_color(200, 200, 200)
			pdf.line(18, pdf.get_y() + 2, 192, pdf.get_y() + 2)
			pdf.ln(6)

			# ── TÍTULO ────────────────────────────────────────────────────────
			status_label = _sanitize(self.data['status_label'])
			pdf.set_font('Arial', 'B', 22)
			pdf.set_text_color(30, 80, 160)
			pdf.cell(
				W,
				12,
				f'PRESUPUESTO  {_sanitize(self.data["number"])}',
				ln=False,
				align='L',
			)
			pdf.set_font('Arial', '', 10)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(0, 12, f'Estado: {status_label}', ln=True, align='R')
			pdf.set_text_color(0, 0, 0)
			pdf.ln(2)

			# ── METADATOS ─────────────────────────────────────────────────────
			col = W / 3
			pdf.set_font('Arial', 'B', 9)
			pdf.set_fill_color(240, 244, 255)
			for lbl in ['Fecha', 'Cliente', 'Válido hasta']:
				pdf.cell(col, 6, _sanitize(lbl), border=0, align='L', fill=True)
			pdf.ln(6)
			pdf.set_font('Arial', '', 9)
			pdf.cell(col, 6, _sanitize(self.data['date']), border=0, align='L')
			pdf.cell(
				col,
				6,
				_sanitize(self.data['customer_name'] or 'Consumidor Final'),
				border=0,
				align='L',
			)
			pdf.cell(
				col, 6, _sanitize(self.data['valid_until'] or '—'), border=0, align='L'
			)
			pdf.ln(10)

			# ── TABLA ÍTEMS ───────────────────────────────────────────────────
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

			pdf.set_font('Arial', '', 9)
			for idx, it in enumerate(self.data['items']):
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
			subtotal_val = sum(it['subtotal'] for it in self.data['items'])
			discount_val = float(self.data['discount_amount'])

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
			total_row('TOTAL:', fmt(self.data['total_amount']), bold=True)

			# ── NOTAS ─────────────────────────────────────────────────────────
			if self.data['notes']:
				pdf.ln(8)
				pdf.set_font('Arial', 'B', 9)
				pdf.cell(W, 5, 'Condiciones / Notas:', ln=True)
				pdf.set_font('Arial', '', 9)
				pdf.set_text_color(80, 80, 80)
				pdf.multi_cell(W, 5, _sanitize(self.data['notes']))
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

			# ── GUARDAR Y ABRIR ───────────────────────────────────────────────
			filepath = os.path.join(
				self.output_dir,
				f'cotizacion_{_sanitize(self.data["number"]).replace("-", "_")}.pdf',
			)
			pdf.output(filepath)
			self._open_file(filepath)
			return True, filepath

		except Exception as e:
			logger.error(f'Error generando PDF: {e}', exc_info=True)
			return False, str(e)

	def _open_file(self, filepath: str):
		try:
			abs_path = os.path.abspath(filepath)
			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path], capture_output=True)
			else:
				subprocess.run(['xdg-open', abs_path], capture_output=True)
		except Exception as e:
			logger.warning(f'No se pudo abrir el PDF: {e}')
