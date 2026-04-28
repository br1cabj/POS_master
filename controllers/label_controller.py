"""
controllers/label_controller.py
================================
Generación de PDFs de etiquetas de precio/producto.
Usa fpdf (1.7.x) + python-barcode + Pillow.
Soporta 4 templates y N copias por variante.
"""

import io
import logging
import os
import platform
import subprocess
import tempfile
import time
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# ── Templates disponibles ─────────────────────────────────────────────────────
TEMPLATES = {
	'supermercado': {
		'label': 'Supermercado',
		'desc': '58 × 40 mm  •  nombre + barcode + precio',
		'w_mm': 58,
		'h_mm': 40,
		'icon': '🏪',
	},
	'producto': {
		'label': 'Producto completo',
		'desc': '70 × 50 mm  •  logo + nombre + atributos + barcode + precio',
		'w_mm': 70,
		'h_mm': 50,
		'icon': '📦',
	},
	'precio': {
		'label': 'Etiqueta precio',
		'desc': '50 × 30 mm  •  nombre + precio grande + barcode',
		'w_mm': 50,
		'h_mm': 30,
		'icon': '💰',
	},
	'mini': {
		'label': 'Mini barcode',
		'desc': '38 × 25 mm  •  barcode + nombre + precio',
		'w_mm': 38,
		'h_mm': 25,
		'icon': '🔖',
	},
}


def _sanitize(text: str) -> str:
	if not text:
		return ''
	return (
		unicodedata.normalize('NFKD', str(text))
		.encode('latin-1', 'ignore')
		.decode('latin-1')
	)


def _fmt_price(amount: float, symbol: str = '$', decimals: int = 0) -> str:
	if decimals == 0:
		return f'{symbol}{amount:,.0f}'
	return f'{symbol}{amount:,.{decimals}f}'


class LabelController:
	def __init__(self):
		self._tmp_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Etiquetas')
		os.makedirs(self._tmp_dir, exist_ok=True)

	# ── Helpers internos ──────────────────────────────────────────────────────

	def _generate_barcode_png(self, code: str, tracker_set: set) -> Optional[str]:
		"""Genera PNG de barcode CODE128. Retorna la ruta y la registra para limpieza."""
		if not code or not str(code).strip():
			return None
		try:
			import barcode
			from barcode.writer import ImageWriter

			safe_code = str(code).strip()
			cls = barcode.get_barcode_class('code128')
			buf = io.BytesIO()
			cls(
				safe_code,
				writer=ImageWriter(),
			).write(
				buf,
				options={
					'write_text': False,
					'quiet_zone': 1,
					'module_height': 8,
					'module_width': 0.8,
					'font_size': 0,
					'text_distance': 1,
				},
			)
			buf.seek(0)

			# Nombre único para evitar colisiones si se ejecuta en paralelo
			path = os.path.join(
				self._tmp_dir, f'bc_{safe_code[:20]}_{int(time.time() * 1000)}.png'
			)
			with open(path, 'wb') as f:
				f.write(buf.read())

			tracker_set.add(path)
			return path
		except Exception as e:
			logger.warning(f'No se pudo generar barcode para "{code}": {e}')
			return None

	def _cleanup_temp_files(self, file_paths: set):
		"""Elimina los PNGs temporales generados en la sesión actual."""
		for path in file_paths:
			try:
				if os.path.exists(path):
					os.remove(path)
			except Exception as e:
				logger.debug(f'No se pudo borrar temporal {path}: {e}')

	# ── API pública ───────────────────────────────────────────────────────────

	def generate_pdf(
		self,
		items: list[dict],
		template_key: str = 'supermercado',
	) -> tuple[bool, str]:
		"""
		Genera un PDF con todas las etiquetas y lo abre.
		"""
		if not items:
			return False, 'No hay artículos en la cola de impresión.'

		# Solución al bug de fallback
		if template_key not in TEMPLATES:
			template_key = 'supermercado'

		temp_pngs = set()

		try:
			from fpdf import FPDF

			from utils import settings_manager

			cfg = settings_manager.load()
			company = _sanitize(cfg.get('company_name', ''))
			logo_path = cfg.get('company_logo_path', '')
			symbol = cfg.get('currency_symbol', '$')
			decimals = int(cfg.get('currency_decimals', 0))

			tpl = TEMPLATES[template_key]
			W = tpl['w_mm']
			H = tpl['h_mm']

			pdf = FPDF(unit='mm', format=(W, H))
			pdf.set_auto_page_break(auto=False, margin=0)

			for item in items:
				copies = max(1, int(item.get('copies', 1)))
				for _ in range(copies):
					pdf.add_page()
					# Delegamos la llamada de forma segura
					getattr(self, f'_draw_{template_key}')(
						pdf, item, W, H, company, logo_path, symbol, decimals, temp_pngs
					)

			# Evita el PermissionError en Windows al renombrar la salida
			timestamp = int(time.time())
			out_path = os.path.join(self._tmp_dir, f'etiquetas_{timestamp}.pdf')
			pdf.output(out_path, 'F')

			self._open(out_path)
			return True, out_path

		except Exception as e:
			logger.error(f'Error generando etiquetas: {e}', exc_info=True)
			return False, str(e)
		finally:
			# Limpieza garantizada de basura en disco
			self._cleanup_temp_files(temp_pngs)

	# ── Templates ─────────────────────────────────────────────────────────────

	def _draw_supermercado(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		price = float(item.get('price', 0))
		price_str = _sanitize(_fmt_price(price, symbol, decimals))

		margin = 2

		if company:
			pdf.set_xy(0, 1)
			pdf.set_font('Arial', 'B', 6)
			pdf.cell(W, 4, company[:30], align='C')

		pdf.set_xy(margin, 6 if company else 3)
		pdf.set_font('Arial', 'B', 9)
		display = name[:26]
		if attr:
			display = (name[:18] + ' ' + attr)[:26]
		pdf.cell(W - margin * 2, 5, display, align='C')

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_y = 13
			bc_h = 13
			bc_w = W - margin * 4
			pdf.image(bc_path, x=margin * 2, y=bc_y, w=bc_w, h=bc_h)
			pdf.set_xy(0, bc_y + bc_h + 0.5)
			pdf.set_font('Arial', '', 5)
			pdf.cell(W, 3, str(barcode), align='C')
			price_y = bc_y + bc_h + 4
		else:
			price_y = 18

		pdf.set_xy(0, price_y)
		pdf.set_font('Arial', 'B', 16)
		pdf.cell(W, 10, price_str, align='C')

	def _draw_producto(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		price = float(item.get('price', 0))
		price_str = _sanitize(_fmt_price(price, symbol, decimals))

		margin = 2
		y = 2

		logo_ok = (
			logo_path
			and os.path.isfile(logo_path)
			and logo_path.lower().endswith(('.png', '.jpg', '.jpeg'))
		)
		if logo_ok:
			try:
				pdf.image(logo_path, x=margin, y=y, h=8)
				pdf.set_xy(14, y + 1)
				pdf.set_font('Arial', 'B', 7)
				pdf.cell(W - 16, 4, company[:28], align='L')
				y += 9
			except Exception:
				logo_ok = False

		if not logo_ok and company:
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'B', 7)
			pdf.cell(W, 4, company[:36], align='C')
			y += 5

		pdf.set_draw_color(180, 180, 180)
		pdf.line(margin, y, W - margin, y)
		y += 2

		pdf.set_xy(margin, y)
		pdf.set_font('Arial', 'B', 10)
		pdf.cell(W - margin * 2, 5, name[:30], align='C')
		y += 5

		if attr:
			pdf.set_xy(margin, y)
			pdf.set_font('Arial', 'I', 7)
			pdf.cell(W - margin * 2, 3, attr[:34], align='C')
			y += 4

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_h = 10
			bc_w = W - margin * 6
			pdf.image(bc_path, x=margin * 3, y=y, w=bc_w, h=bc_h)
			pdf.set_xy(0, y + bc_h + 0.5)
			pdf.set_font('Arial', '', 5)
			pdf.cell(W, 3, str(barcode), align='C')
			y += bc_h + 4

		pdf.set_xy(0, y)
		pdf.set_font('Arial', 'B', 18)
		pdf.cell(W, 10, price_str, align='C')

	def _draw_precio(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		price = float(item.get('price', 0))
		price_str = _sanitize(_fmt_price(price, symbol, decimals))

		margin = 2

		pdf.set_xy(margin, 2)
		pdf.set_font('Arial', 'B', 8)
		display = name[:22]
		if attr:
			display = (name[:14] + ' ' + attr)[:22]
		pdf.cell(W - margin * 2, 5, display, align='C')

		pdf.set_xy(0, 8)
		pdf.set_font('Arial', 'B', 20)
		pdf.cell(W, 12, price_str, align='C')

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_h = 6
			bc_w = W - margin * 8
			pdf.image(bc_path, x=margin * 4, y=21, w=bc_w, h=bc_h)
			pdf.set_xy(0, 27)
			pdf.set_font('Arial', '', 4)
			pdf.cell(W, 2, str(barcode), align='C')
		elif company:
			pdf.set_xy(0, 25)
			pdf.set_font('Arial', 'I', 5)
			pdf.cell(W, 3, company, align='C')

	def _draw_mini(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		price = float(item.get('price', 0))
		price_str = _sanitize(_fmt_price(price, symbol, decimals))

		margin = 1

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_h = 10
			bc_w = W - margin * 4
			pdf.image(bc_path, x=margin * 2, y=2, w=bc_w, h=bc_h)
			pdf.set_xy(0, 12.5)
			pdf.set_font('Arial', '', 4)
			pdf.cell(W, 2, str(barcode), align='C')
			name_y = 15
		else:
			name_y = 3

		display = name[:18]
		if attr:
			display = (name[:10] + ' ' + attr)[:18]
		pdf.set_xy(margin, name_y)
		pdf.set_font('Arial', 'B', 7)
		pdf.cell(W - margin * 2, 4, display, align='C')

		pdf.set_xy(0, name_y + 4)
		pdf.set_font('Arial', 'B', 10)
		pdf.cell(W, 5, price_str, align='C')

	# ── Abrir archivo ─────────────────────────────────────────────────────────

	def _open(self, filepath: str):
		try:
			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(os.path.abspath(filepath), 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', filepath], capture_output=True)
			else:
				subprocess.run(['xdg-open', filepath], capture_output=True)
		except Exception as e:
			logger.warning(f'No se pudo abrir el PDF de etiquetas: {e}')
