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
			# Aumentamos el margen inferior a 25 para dar respiro a los totales
			pdf.set_auto_page_break(auto=True, margin=25)
			pdf.add_page()
			pdf.set_margins(left=18, top=18, right=18)
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
			pdf.set_font('Arial', 'B', 22)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(0, 8, 'PRESUPUESTO', ln=True, align='R')

			pdf.set_font('Arial', 'B', 14)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(0, 6, f'Nro: {_sanitize(self.data["number"])}', ln=True, align='R')
			pdf.ln(2)

			pdf.set_font('Arial', 'B', 10)
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

			pdf.set_font('Arial', 'B', 16)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(90, 7, company, ln=True, align='L')

			pdf.set_font('Arial', '', 10)
			pdf.set_text_color(*TEXT_MUTED)
			if address:
				pdf.cell(90, 5, address, ln=True, align='L')
			if phone:
				pdf.cell(90, 5, f'Teléfono: {phone}', ln=True, align='L')

			left_block_y = pdf.get_y()

			# ── SEPARADOR Y CLIENTE (Estilo clásico) ─────────────────────────
			pdf.set_y(max(right_block_y, left_block_y) + 10)
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(6)

			status_label = _sanitize(self.data.get('status_label', ''))

			# Fila de etiquetas
			pdf.set_font('Arial', 'B', 10)
			pdf.set_text_color(*TEXT_MUTED)
			pdf.cell(100, 5, 'CLIENTE:', ln=False)
			pdf.cell(74, 5, 'ESTADO:', ln=True, align='R')

			# Fila de datos
			pdf.set_font('Arial', 'B', 12)
			pdf.set_text_color(*TEXT_DARK)
			pdf.cell(
				100,
				6,
				_sanitize(self.data.get('customer_name') or 'Consumidor Final'),
				ln=False,
			)

			pdf.set_font('Arial', 'B', 11)
			pdf.set_text_color(*ACCENT_RGB)
			pdf.cell(74, 6, status_label.upper(), ln=True, align='R')
			pdf.ln(8)

			# ── TABLA DE ÍTEMS (Grilla Tradicional) ──────────────────────────
			col_desc = 94
			col_qty = 20
			col_price = 30
			col_sub = 30

			pdf.set_fill_color(*TABLE_HEADER)
			pdf.set_text_color(*TEXT_DARK)
			pdf.set_font('Arial', 'B', 9)
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.set_line_width(0.3)

			# Encabezado cerrado
			pdf.cell(
				col_desc, 8, ' DESCRIPCIÓN DEL ARTÍCULO', border=1, align='L', fill=True
			)
			pdf.cell(col_qty, 8, 'CANT.', border=1, align='C', fill=True)
			pdf.cell(col_price, 8, 'PRECIO UNIT.', border=1, align='C', fill=True)
			pdf.cell(col_sub, 8, 'SUBTOTAL', border=1, align='C', fill=True)
			pdf.ln(8)

			# Filas de productos
			pdf.set_font('Arial', '', 10)  # Letra más grande para lectura fácil
			for it in self.data['items']:
				qty = float(it['quantity'])
				qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.3f}'

				# Bordes L (Left), R (Right), B (Bottom) para efecto grilla
				pdf.cell(
					col_desc,
					9,
					f' {_sanitize(it["description"])[:52]}',
					border='LRB',
					align='L',
				)
				pdf.cell(col_qty, 9, qty_str, border='LRB', align='C')
				pdf.cell(col_price, 9, fmt(it['unit_price']), border='LRB', align='R')
				pdf.cell(col_sub, 9, f'{fmt(it["subtotal"])} ', border='LRB', align='R')
				pdf.ln(9)

			pdf.ln(6)

			# ── TOTALES ──────────────────────────────────────────────────────
			subtotal_val = sum(it['subtotal'] for it in self.data['items'])
			discount_val = float(self.data.get('discount_amount', 0))

			x_lbl = 18 + col_desc + col_qty

			def total_row(label, value, is_total=False, color=None):
				pdf.set_x(x_lbl)

				if is_total:
					# Caja de total clásico
					pdf.set_font('Arial', 'B', 12)
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
					pdf.set_font('Arial', 'B', 10)
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
				pdf.set_font('Arial', 'B', 10)
				pdf.set_text_color(*TEXT_DARK)
				pdf.cell(W, 6, 'Notas y Condiciones:', ln=True)

				pdf.set_font('Arial', '', 10)
				pdf.set_text_color(*TEXT_MUTED)
				pdf.multi_cell(W, 5, _sanitize(self.data['notes']))

			# ── PIE DE PÁGINA (Solución a la hoja extra) ─────────────────────
			# Desactivamos el salto automático momentáneamente para asegurar
			# que el pie entre siempre al final sin empujar una página nueva.
			pdf.set_auto_page_break(False)

			pdf.set_y(-20)  # A 20mm del borde inferior
			pdf.set_draw_color(*BORDER_COLOR)
			pdf.line(18, pdf.get_y(), 192, pdf.get_y())
			pdf.ln(4)

			pdf.set_font('Arial', 'I', 9)
			pdf.set_text_color(130, 130, 130)
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
