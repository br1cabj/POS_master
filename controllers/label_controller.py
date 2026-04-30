"""
controllers/label_controller.py
================================
Generación de PDFs de etiquetas de precio/producto.
Usa fpdf (1.7.x o fpdf2) + python-barcode + Pillow.
Soporta 4 templates y N copias por variante.
Desde v2.1: precio mayorista/minorista en template "precio".
"""

import io
import logging
import os
import platform
import re
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
		'icon': '🏬',
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


def _compute_wholesale_price(base_price: float, rule: dict) -> float:
	"""Aplica descuento de una regla mayorista a un precio base."""
	try:
		pct = float(rule.get('discount_pct', 0))
		return round(base_price * (1 - pct / 100), 2)
	except (TypeError, ValueError):
		return base_price


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

			# BUG FIX: Evitar que caracteres especiales en el código rompan la ruta del archivo
			file_safe_code = re.sub(r'[^a-zA-Z0-9]', '', safe_code)[:20]

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

			path = os.path.join(
				self._tmp_dir, f'bc_{file_safe_code}_{int(time.time() * 1000)}.png'
			)
			with open(path, 'wb') as f:
				f.write(buf.read())

			tracker_set.add(path)
			return path
		except Exception as e:
			logger.warning(f'No se pudo generar barcode para "{code}": {e}')
			return None

	def _cleanup_temp_files(self, file_paths: set):
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
		"""Genera un PDF con todas las etiquetas y lo abre."""
		if not items:
			return False, 'No hay artículos en la cola de impresión.'

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

			# BUG FIX: Conversiones robustas
			try:
				decimals = int(float(cfg.get('currency_decimals', 0)))
			except (ValueError, TypeError):
				decimals = 0

			wholesale_enabled = cfg.get('wholesale_enabled', False)
			wholesale_rules = sorted(
				cfg.get('wholesale_rules', []),
				key=lambda r: float(r.get('min_qty', 0)),
				reverse=True,
			)

			tpl = TEMPLATES[template_key]
			W = tpl['w_mm']
			H = tpl['h_mm']

			pdf = FPDF(unit='mm', format=(W, H))
			pdf.set_auto_page_break(auto=False, margin=0)

			for item in items:
				# BUG FIX: Casteo seguro doble (float -> int) para evitar ValueError con strings como '1.0'
				try:
					copies = max(1, int(float(item.get('copies', 1))))
				except (ValueError, TypeError):
					copies = 1

				price_mode = item.get('price_mode', 'retail')

				try:
					base_price = float(item.get('price', 0))
				except (ValueError, TypeError):
					base_price = 0.0

				display_price = base_price
				mode_label = None
				retail_str = None

				if wholesale_enabled and price_mode.startswith('wholesale_'):
					try:
						rule_idx = int(price_mode.split('_', 1)[1])
						if 0 <= rule_idx < len(wholesale_rules):
							rule = wholesale_rules[rule_idx]
							display_price = _compute_wholesale_price(base_price, rule)

							# BUG FIX: Casteos seguros para las reglas mayoristas
							min_qty = int(float(rule.get('min_qty', 0)))
							pct = float(rule.get('discount_pct', 0))

							pct_str = (
								f'{int(pct)}' if pct.is_integer() else f'{pct:.1f}'
							)
							mode_label = _sanitize(
								f'MAYORISTA x{min_qty}u  -{pct_str}%'
							)
							retail_str = _sanitize(
								_fmt_price(base_price, symbol, decimals)
							)
					except (ValueError, IndexError):
						pass

				enriched = dict(item)
				enriched['_display_price'] = display_price
				enriched['_mode_label'] = mode_label
				enriched['_retail_str'] = retail_str

				for _ in range(copies):
					pdf.add_page()
					getattr(self, f'_draw_{template_key}')(
						pdf,
						enriched,
						W,
						H,
						company,
						logo_path,
						symbol,
						decimals,
						temp_pngs,
					)

			timestamp = int(time.time())
			out_path = os.path.join(self._tmp_dir, f'etiquetas_{timestamp}.pdf')
			pdf.output(out_path, 'F')

			self._open(out_path)
			return True, out_path

		except Exception as e:
			logger.error(f'Error generando etiquetas: {e}', exc_info=True)
			return False, str(e)
		finally:
			self._cleanup_temp_files(temp_pngs)

	# ── Templates ─────────────────────────────────────────────────────────────

	def _draw_supermercado(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		display_price = item.get('_display_price', float(item.get('price', 0)))
		price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
		mode_label = item.get('_mode_label')
		retail_str = item.get('_retail_str')

		margin = 2
		y = 1

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
			pdf.set_text_color(255, 255, 255)
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'B', 5)
			pdf.cell(W, 3.5, mode_label, align='C', fill=True)
			pdf.set_text_color(0, 0, 0)
			y += 3.5
		elif company:
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'B', 6)
			pdf.cell(W, 4, company[:30], align='C')
			y += 4

		pdf.set_xy(margin, y)
		pdf.set_font('Arial', 'B', 9)
		display = name[:26]
		if attr:
			display = (name[:18] + ' ' + attr)[:26]
		pdf.cell(W - margin * 2, 5, display, align='C')
		y += 5

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_y = y + 1
			bc_h = 12
			bc_w = W - margin * 4
			pdf.image(bc_path, x=margin * 2, y=bc_y, w=bc_w, h=bc_h)
			pdf.set_xy(0, bc_y + bc_h + 0.5)
			pdf.set_font('Arial', '', 5)
			pdf.cell(W, 3, str(barcode), align='C')
			price_y = bc_y + bc_h + 4
		else:
			price_y = y + 3

		if retail_str:
			pdf.set_xy(0, price_y - 3)
			pdf.set_font('Arial', 'I', 5)
			pdf.set_text_color(150, 150, 150)
			pdf.cell(W, 3, f'Minorista: {retail_str}', align='C')
			pdf.set_text_color(0, 0, 0)

		pdf.set_xy(0, price_y)
		pdf.set_font('Arial', 'B', 16)
		pdf.cell(W, 10, price_str, align='C')

	def _draw_producto(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		display_price = item.get('_display_price', float(item.get('price', 0)))
		price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
		mode_label = item.get('_mode_label')
		retail_str = item.get('_retail_str')

		margin = 2
		y = 2

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
			pdf.set_text_color(255, 255, 255)
			pdf.set_xy(0, 0)
			pdf.set_font('Arial', 'B', 6)
			pdf.cell(W, 4, mode_label, align='C', fill=True)
			pdf.set_text_color(0, 0, 0)
			y = 5
		else:
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

		if retail_str:
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'I', 6)
			pdf.set_text_color(150, 150, 150)
			pdf.cell(W, 3, f'Minorista: {retail_str}', align='C')
			pdf.set_text_color(0, 0, 0)
			y += 3

		pdf.set_xy(0, y)
		pdf.set_font('Arial', 'B', 18)
		pdf.cell(W, 10, price_str, align='C')

	def _draw_precio(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		display_price = item.get('_display_price', float(item.get('price', 0)))
		mode_label = item.get('_mode_label')
		retail_str = item.get('_retail_str')
		price_str = _sanitize(_fmt_price(display_price, symbol, decimals))

		margin = 2
		y = 0

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
			pdf.set_text_color(255, 255, 255)
			pdf.rect(0, 0, W, 5.5, 'F')
			pdf.set_xy(0, 0.5)
			pdf.set_font('Arial', 'B', 7)
			pdf.cell(W, 4.5, mode_label, align='C')
			pdf.set_text_color(0, 0, 0)
			y = 5.5
		else:
			y = 2

		display = name[:22]
		if attr:
			display = (name[:14] + ' ' + attr)[:22]
		pdf.set_xy(margin, y)
		pdf.set_font('Arial', 'B', 7 if mode_label else 8)
		pdf.cell(W - margin * 2, 4.5, display, align='C')
		y += 4.5

		font_size = 18 if mode_label else 20
		pdf.set_xy(0, y)
		pdf.set_font('Arial', 'B', font_size)
		pdf.cell(W, 9, price_str, align='C')
		y += 9

		if retail_str and mode_label:
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'I', 5.5)
			pdf.set_text_color(120, 120, 120)
			pdf.cell(W, 3, f'Minorista: {retail_str}', align='C')
			pdf.set_text_color(0, 0, 0)
			y += 3

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path and y < H - 4:
			bc_h = min(5.5, H - y - 2.5)
			bc_w = W - margin * 8
			pdf.image(bc_path, x=margin * 4, y=y, w=bc_w, h=bc_h)
			if y + bc_h + 0.5 < H:
				pdf.set_xy(0, y + bc_h + 0.3)
				pdf.set_font('Arial', '', 4)
				pdf.cell(W, 2, str(barcode), align='C')
		elif company and not mode_label:
			pdf.set_xy(0, y)
			pdf.set_font('Arial', 'I', 5)
			pdf.cell(W, 3, company, align='C')

	def _draw_mini(
		self, pdf, item, W, H, company, logo_path, symbol, decimals, tracker_set
	):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode = item.get('barcode', '')
		display_price = item.get('_display_price', float(item.get('price', 0)))
		price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
		mode_label = item.get('_mode_label')
		retail_str = item.get('_retail_str')

		margin = 1

		bc_path = self._generate_barcode_png(barcode, tracker_set)
		if bc_path:
			bc_h = 9
			bc_w = W - margin * 4
			pdf.image(bc_path, x=margin * 2, y=2, w=bc_w, h=bc_h)
			pdf.set_xy(0, 11.5)
			pdf.set_font('Arial', '', 4)
			pdf.cell(W, 2, str(barcode), align='C')
			name_y = 14
		else:
			name_y = 2

		display = name[:18]
		if attr:
			display = (name[:10] + ' ' + attr)[:18]

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
			pdf.set_text_color(255, 255, 255)
			pdf.set_xy(0, name_y)
			pdf.set_font('Arial', 'B', 5)
			pdf.cell(W, 3, mode_label[:24], align='C', fill=True)
			pdf.set_text_color(0, 0, 0)
			name_y += 3

		pdf.set_xy(margin, name_y)
		pdf.set_font('Arial', 'B', 6)
		pdf.cell(W - margin * 2, 3.5, display, align='C')

		pdf.set_xy(0, name_y + 3.5)
		pdf.set_font('Arial', 'B', 9)
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
