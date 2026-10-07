"""
utils/quotation_pdf.py
==========================
Servicio encargado de la generación de PDFs para cotizaciones.
"""

import logging
import os
import platform
import re
import subprocess
import textwrap
import unicodedata

from fpdf import FPDF, XPos, YPos

from utils import settings_manager

logger = logging.getLogger(__name__)


class _QuotationDocument(FPDF):
	"""Documento con un pie repetible para que todas las páginas sean autosuficientes."""

	def footer(self):
		self.set_y(-18)
		self.set_draw_color(200, 200, 200)
		self.line(18, self.get_y(), 192, self.get_y())
		self.ln(3)
		self.set_font('Helvetica', 'I', 8)
		self.set_text_color(110, 110, 110)
		self.cell(
			174,
			4,
			'Presupuesto orientativo y sujeto a modificaciones.  Página '
			f'{self.page_no()}/{{nb}}',
			align='C',
		)


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

			pdf = _QuotationDocument(orientation='P', unit='mm', format='A4')
			pdf.set_margins(left=18, top=18, right=18)
			pdf.alias_nb_pages()
			# Dejamos espacio para el pie, que se repite en cada página.
			pdf.set_auto_page_break(auto=True, margin=25)
			pdf.add_page()
			W = 174

			# ── COLORES HÍBRIDOS (Clásico + Moderno) ─────────────────────────
			ACCENT_RGB = (37, 99, 235)  # Azul CloudPOS
			TEXT_DARK = (0, 0, 0)  # Negro puro para máxima legibilidad
			TEXT_MUTED = (80, 80, 80)  # Gris oscuro (antes era muy claro)
			BORDER_COLOR = (200, 200, 200)  # Gris clásico para la grilla
			TABLE_HEADER = (235, 240, 245)  # Fondo gris-azulado suave

			logo_ok = (
				logo_path
				and os.path.isfile(logo_path)
				and logo_path.lower().endswith(('.png', '.jpg', '.jpeg'))
			)

			# ── BLOQUE DERECHO (Documento y Fechas) ──────────────────────────
			pdf.set_y(18)
			pdf.set_font('Helvetica', 'B', 22)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(0, 8, 'PRESUPUESTO', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')

			pdf.set_font('Helvetica', 'B', 14)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(
				0, 6, f'Nro: {_sanitize(self.data["number"])}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R'
			)
			pdf.ln(2)

			pdf.set_font('Helvetica', 'B', 10)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.cell(
				0, 5, f'Fecha: {_sanitize(self.data["date"])}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R'
			)
			if self.data.get('valid_until'):
				pdf.cell(
					0,
					5,
					f'Válido hasta: {_sanitize(self.data["valid_until"])}',
					new_x=XPos.LMARGIN,
					new_y=YPos.NEXT,
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

			pdf.set_font('Helvetica', 'B', 16)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(90, 7, company, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

			pdf.set_font('Helvetica', '', 10)
			pdf.set_text_color(*TEXT_MUTED)
			if address:
				pdf.cell(90, 5, address, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
			if phone:
				pdf.cell(90, 5, f'Teléfono: {phone}', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

			left_block_y = pdf.get_y()

			# ── SEPARADOR Y CLIENTE (Estilo clásico) ─────────────────────────
			pdf.set_y(max(right_block_y, left_block_y) + 10)
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(6)

			status_label = _sanitize(self.data.get('status_label', ''))

			# Fila de etiquetas
			pdf.set_font('Helvetica', 'B', 10)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.cell(100, 5, 'CLIENTE:', new_x=XPos.RIGHT, new_y=YPos.TOP)
			pdf.cell(74, 5, 'ESTADO:', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')

			# Fila de datos
			pdf.set_font('Helvetica', 'B', 12)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(
				100,
				6,
				_sanitize(self.data.get('customer_name') or 'Consumidor Final'),
				new_x=XPos.RIGHT,
				new_y=YPos.TOP,
			)

			pdf.set_font('Helvetica', 'B', 11)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(74, 6, status_label.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
			pdf.ln(8)

			# ── TABLA DE ÍTEMS (Grilla tradicional, paginada) ────────────────
			col_desc = 94
			col_qty = 20
			col_price = 30
			col_sub = 30

			def draw_table_header():
				pdf.set_fill_color(*TABLE_HEADER)
				pdf.set_text_color(*TEXT_DARK)
				pdf.set_font('Helvetica', 'B', 9)
				pdf.set_draw_color(*BORDER_COLOR)
				pdf.set_line_width(0.3)
				pdf.cell(
					col_desc, 8, ' DESCRIPCIÓN DEL ARTÍCULO', border=1, align='L', fill=True
				)
				pdf.cell(col_qty, 8, 'CANT.', border=1, align='C', fill=True)
				pdf.cell(col_price, 8, 'PRECIO UNIT.', border=1, align='C', fill=True)
				pdf.cell(col_sub, 8, 'SUBTOTAL', border=1, align='C', fill=True)
				pdf.ln(8)

			draw_table_header()

			# Las descripciones se envuelven sin truncarlas. Antes de cada fila se
			# reserva espacio, por lo que no quedan partidas entre páginas.
			for it in self.data['items']:
				qty = float(it['quantity'])
				qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.3f}'
				description = _sanitize(it['description']).strip()
				lines = textwrap.wrap(description, width=57, break_long_words=True) or ['']
				wrapped_description = ' \n '.join(lines)
				row_height = max(8, len(lines) * 5)
				if pdf.get_y() + row_height > 267:
					pdf.add_page()
					draw_table_header()
				y = pdf.get_y()
				pdf.set_font('Helvetica', '', 9)
				pdf.set_xy(18, y)
				pdf.multi_cell(col_desc, 5, f' {wrapped_description}', border=1, align='L')
				pdf.set_xy(18 + col_desc, y)
				pdf.cell(col_qty, row_height, qty_str, border=1, align='C')
				pdf.cell(col_price, row_height, fmt(it['unit_price']), border=1, align='R')
				pdf.cell(col_sub, row_height, f'{fmt(it["subtotal"])} ', border=1, align='R')
				pdf.set_y(y + row_height)

			pdf.ln(6)

			# ── TOTALES ──────────────────────────────────────────────────────
			subtotal_val = sum(it['subtotal'] for it in self.data['items'])
			discount_val = float(self.data.get('discount_amount', 0))

			x_lbl = 18 + col_desc + col_qty

			def total_row(label, value, is_total=False, color=None):
				pdf.set_x(x_lbl)

				if is_total:
					# Caja de total clásico
					pdf.set_font('Helvetica', 'B', 12)
					pdf.set_text_color(*TEXT_DARK)
					pdf.set_fill_color(*TABLE_HEADER)
					pdf.cell(
						col_price,
						10,
						f' {_sanitize(label)}',
						border='LTB',
						align='L',
						fill=True,
					)
					pdf.cell(
						col_sub, 10, f'{value} ', border='RTB', align='R', fill=True
					)
				else:
					pdf.set_font('Helvetica', 'B', 10)
					if color:
						pdf.set_text_color(*color)
					else:
						pdf.set_text_color(*TEXT_MUTED)

					pdf.cell(col_price, 7, _sanitize(label), border=0, align='L')
					pdf.cell(col_sub, 7, f'{value} ', border=0, align='R')

				pdf.set_text_color(*TEXT_DARK)
				pdf.ln(10 if is_total else 7)

			total_row('Subtotal:', fmt(subtotal_val))
			if discount_val > 0:
				total_row('Descuento:', f'-{fmt(discount_val)}', color=(200, 30, 30))

			pdf.ln(2)
			total_row('TOTAL:', fmt(self.data['total_amount']), is_total=True)

			# ── NOTAS Y CONDICIONES ──────────────────────────────────────────
			if self.data.get('notes'):
				pdf.set_y(pdf.get_y() + 10)
				pdf.set_font('Helvetica', 'B', 10)
				pdf.set_text_color(*TEXT_DARK)
				pdf.cell(W, 6, 'Notas y Condiciones:', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

				pdf.set_font('Helvetica', '', 10)
				pdf.set_text_color(*TEXT_MUTED)
				pdf.multi_cell(W, 5, _sanitize(self.data['notes']))

			# ── GUARDAR Y ABRIR ──────────────────────────────────────────────
			os.makedirs(self.output_dir, exist_ok=True)
			safe_number = re.sub(r'[^\w\-]', '', str(self.data.get('number', 'sin_numero')))
			safe_number = safe_number.replace('-', '_')[:50]
			filepath = os.path.join(
				self.output_dir,
				f'cotizacion_{safe_number}.pdf',
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
			if not os.path.exists(abs_path):
				logger.warning('PDF no encontrado, no se puede abrir: %s', abs_path)
				return
			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path], capture_output=True)
			else:
				subprocess.run(['xdg-open', abs_path], capture_output=True)
		except Exception as e:
			logger.warning(f'No se pudo abrir el PDF: {e}')
