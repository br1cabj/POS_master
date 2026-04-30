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
			pdf.set_margins(left=18, top=18, right=18)
			W = 174

			# ── COLORES BASE (Inspirados en CloudPOS) ────────────────────────
			ACCENT_RGB = (37, 99, 235)  # #2563eb
			TEXT_DARK = (30, 41, 59)  # #1e293b
			TEXT_MUTED = (100, 116, 139)  # #64748b
			BORDER_COLOR = (226, 232, 240)  # #e2e8f0

			logo_ok = (
				logo_path
				and os.path.isfile(logo_path)
				and logo_path.lower().endswith(('.png', '.jpg', '.jpeg'))
			)

			# ── BLOQUE DERECHO (Documento y Fechas) ──────────────────────────
			pdf.set_y(18)
			pdf.set_font('Arial', 'B', 22)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(0, 8, 'PRESUPUESTO', ln=True, align='R')

			pdf.set_font('Arial', 'B', 12)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(0, 6, f'# {_sanitize(self.data["number"])}', ln=True, align='R')
			pdf.ln(2)

			pdf.set_font('Arial', '', 9)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.cell(0, 5, f'Fecha: {_sanitize(self.data["date"])}', ln=True, align='R')
			if self.data.get('valid_until'):
				pdf.cell(
					0,
					5,
					f'Válido hasta: {_sanitize(self.data["valid_until"])}',
					ln=True,
					align='R',
				)

			right_block_y = pdf.get_y()

			# ── BLOQUE IZQUIERDO (Empresa y Logo) ────────────────────────────
			pdf.set_xy(18, 18)
			if logo_ok:
				try:
					pdf.image(logo_path, x=18, y=18, h=16)
					pdf.set_xy(18, 38)
				except Exception:
					pdf.set_xy(18, 18)

			pdf.set_font('Arial', 'B', 14)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(90, 6, company, ln=True, align='L')

			pdf.set_font('Arial', '', 9)
			pdf.set_text_color(*TEXT_MUTED)
			if address:
				pdf.cell(90, 5, address, ln=True, align='L')
			if phone:
				pdf.cell(90, 5, f'Tel: {phone}', ln=True, align='L')

			left_block_y = pdf.get_y()

			# ── SEPARADOR Y CLIENTE ──────────────────────────────────────────
			pdf.set_y(max(right_block_y, left_block_y) + 12)
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(8)

			status_label = _sanitize(self.data.get('status_label', ''))

			pdf.set_font('Arial', '', 9)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.cell(100, 5, 'Preparado para:', ln=False)
			pdf.cell(74, 5, 'Estado:', ln=True, align='R')

			pdf.set_font('Arial', 'B', 11)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(
				100,
				6,
				_sanitize(self.data.get('customer_name') or 'Consumidor Final'),
				ln=False,
			)

			pdf.set_font('Arial', 'B', 9)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(74, 6, status_label, ln=True, align='R')
			pdf.ln(10)

			# ── TABLA DE ÍTEMS ───────────────────────────────────────────────
			col_desc = 94
			col_qty = 20
			col_price = 30
			col_sub = 30

			# Encabezado Minimalista
			pdf.set_fill_color(248, 250, 252)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.set_font('Arial', 'B', 8)
			pdf.set_draw_color(*BORDER_COLOR)

			pdf.cell(col_desc, 8, '  DESCRIPCIÓN', border='B', align='L', fill=True)
			pdf.cell(col_qty, 8, 'CANT.', border='B', align='C', fill=True)
			pdf.cell(col_price, 8, 'PRECIO UNIT.', border='B', align='R', fill=True)
			pdf.cell(col_sub, 8, 'SUBTOTAL  ', border='B', align='R', fill=True)
			pdf.ln(9)

			# Filas
			pdf.set_text_color(*TEXT_DARK)
			pdf.set_font('Arial', '', 9)

			for it in self.data['items']:
				qty = float(it['quantity'])
				qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.3f}'

				pdf.cell(
					col_desc,
					9,
					f'  {_sanitize(it["description"])[:60]}',
					border='B',
					align='L',
				)
				pdf.cell(col_qty, 9, qty_str, border='B', align='C')
				pdf.cell(col_price, 9, fmt(it['unit_price']), border='B', align='R')
				pdf.cell(col_sub, 9, f'{fmt(it["subtotal"])}  ', border='B', align='R')
				pdf.ln(9)

			pdf.ln(6)

			# ── TOTALES ──────────────────────────────────────────────────────
			subtotal_val = sum(it['subtotal'] for it in self.data['items'])
			discount_val = float(self.data.get('discount_amount', 0))

			def total_row(label, value, bold=False, color=None):
				x_lbl = 18 + col_desc + col_qty
				pdf.set_x(x_lbl)

				if bold:
					pdf.set_font('Arial', 'B', 11)
					pdf.set_text_color(*TEXT_DARK)
				else:
					pdf.set_font('Arial', '', 9)
					pdf.set_text_color(*(color or TEXT_MUTED))

				pdf.cell(col_price, 7, _sanitize(label), border=0, align='L')

				if color:
					pdf.set_text_color(*color)

				pdf.cell(col_sub, 7, f'{value}  ', border=0, align='R')
				pdf.set_text_color(*TEXT_DARK)
				pdf.ln(7)

			total_row('Subtotal', fmt(subtotal_val))
			if discount_val > 0:
				total_row('Descuento', f'-{fmt(discount_val)}', color=(220, 38, 38))

			# Línea fuerte arriba del total
			x_tot = 18 + col_desc + col_qty
			pdf.set_draw_color(*TEXT_DARK)
			pdf.line(x_tot, pdf.get_y() + 1, 192, pdf.get_y() + 1)
			pdf.ln(3)

			total_row('TOTAL', fmt(self.data['total_amount']), bold=True)

			# ── NOTAS Y PIE ──────────────────────────────────────────────────
			if self.data.get('notes'):
				pdf.set_y(pdf.get_y() + 15)
				pdf.set_font('Arial', 'B', 9)
				pdf.set_text_color(*TEXT_DARK)
				pdf.cell(W, 6, 'Notas y Condiciones:', ln=True)

				pdf.set_font('Arial', '', 9)
				pdf.set_text_color(*TEXT_MUTED)
				pdf.multi_cell(W, 5, _sanitize(self.data['notes']))

			# Forzar footer al fondo
			pdf.set_y(-25)
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(4)

			pdf.set_font('Arial', 'I', 8)
			pdf.set_text_color(148, 163, 184)
			pdf.cell(
				W,
				4,
				'Gracias por su consulta. Este presupuesto es de carácter orientativo y sujeto a modificaciones.',
				align='C',
				ln=True,
			)

			# ── GUARDAR Y ABRIR ──────────────────────────────────────────────
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
