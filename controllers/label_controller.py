import io
import logging
import os
import platform
import re
import subprocess
import tempfile
import unicodedata
import uuid
from datetime import datetime
from typing import Optional

import barcode
from barcode.writer import ImageWriter
from fpdf import FPDF

from utils import settings_manager

logger = logging.getLogger(__name__)

TEMPLATES = {
	'supermercado': {
		'label': 'Supermercado',
		'desc': '58 × 40 mm',
		'w_mm': 58,
		'h_mm': 40,
		'icon': '🏬',
	},
	'producto': {
		'label': 'Producto completo',
		'desc': '70 × 50 mm',
		'w_mm': 70,
		'h_mm': 50,
		'icon': '📦',
	},
	'precio': {
		'label': 'Etiqueta precio',
		'desc': '50 × 30 mm',
		'w_mm': 50,
		'h_mm': 30,
		'icon': '💰',
	},
	'mini': {
		'label': 'Mini barcode',
		'desc': '38 × 25 mm',
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
	try:
		amount = float(amount or 0)
	except (ValueError, TypeError):
		amount = 0.0
	if decimals == 0:
		return f'{symbol}{amount:,.0f}'
	return f'{symbol}{amount:,.{decimals}f}'




def _split_text(text: str, max_chars: int) -> list:
	if len(text) <= max_chars:
		return [text]
	idx = text.rfind(' ', 0, max_chars)
	if idx == -1:
		idx = max_chars
	line1 = text[:idx]
	line2 = text[idx:].strip()[:max_chars]
	return [line1, line2] if line2 else [line1]


_BC_CACHE_MAXSIZE = 200


class LabelController:
	def __init__(self):
		self._tmp_dir = os.path.join(tempfile.gettempdir(), 'CloudPOS_Etiquetas')
		os.makedirs(self._tmp_dir, exist_ok=True)
		self._bc_cache: dict = {}

	@staticmethod
	def generate_internal_barcode() -> str:
		"""Genera un código Code128 interno único para artículos sin EAN."""
		return 'INT' + uuid.uuid4().hex[:11].upper()

	def _generate_barcode_png(self, code: str) -> Optional[str]:
		if not code or not str(code).strip():
			return None
		safe_code = str(code).strip()

		if safe_code in self._bc_cache:
			cached = self._bc_cache[safe_code]
			if os.path.exists(cached):
				return cached
			else:
				del self._bc_cache[safe_code]

		if len(self._bc_cache) >= _BC_CACHE_MAXSIZE:
			# Evictar la entrada más antigua (FIFO por orden de inserción del dict)
			oldest_key = next(iter(self._bc_cache))
			old_path = self._bc_cache.pop(oldest_key)
			try:
				os.unlink(old_path)
			except OSError:
				pass

		try:
			file_safe_code = re.sub(r'[^a-zA-Z0-9]', '', safe_code)[:20]
			cls = barcode.get_barcode_class('code128')
			buf = io.BytesIO()
			cls(safe_code, writer=ImageWriter()).write(
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
				self._tmp_dir, f'bc_{file_safe_code}_{uuid.uuid4().hex[:6]}.png'
			)
			with open(path, 'wb') as f:
				f.write(buf.read())
			self._bc_cache[safe_code] = path
			return path
		except Exception as e:
			logger.warning(f'No se pudo generar barcode para "{code}": {e}')
			return None

	def _draw_strikethrough(
		self, pdf, x: float, y: float, text: str, line_y_offset: float = 2.5
	):
		w = pdf.get_string_width(text)
		pdf.set_draw_color(180, 60, 60)
		pdf.set_line_width(0.4)
		pdf.line(x, y + line_y_offset, x + w, y + line_y_offset)
		pdf.set_line_width(0.2)
		pdf.set_draw_color(0, 0, 0)

	def generate_pdf(self, items: list, template_key: str = 'supermercado') -> tuple:
		if not items:
			return False, 'No hay artículos en la cola de impresión.'
		if template_key not in TEMPLATES:
			template_key = 'supermercado'

		try:
			cfg = settings_manager.load()
			company = _sanitize(cfg.get('company_name', ''))
			logo_path = cfg.get('company_logo_path', '')
			symbol = cfg.get('currency_symbol', '$')

			try:
				decimals = int(float(cfg.get('currency_decimals') or 0))
			except (ValueError, TypeError):
				decimals = 0

			list_b_name = _sanitize(cfg.get('price_list_b_name', 'Mayorista'))

			tpl = TEMPLATES[template_key]
			W = tpl['w_mm']
			H = tpl['h_mm']
			orientation = 'L' if W > H else 'P'
			format_size = (H, W) if orientation == 'L' else (W, H)

			pdf = FPDF(orientation=orientation, unit='mm', format=format_size)
			pdf.set_auto_page_break(auto=False, margin=0)

			for item in items:
				try:
					copies = max(1, int(float(item.get('copies') or 1)))
				except (ValueError, TypeError):
					copies = 1

				price_mode = str(item.get('price_mode') or 'retail')
				try:
					base_price = float(item.get('price') or 0)
				except (ValueError, TypeError):
					base_price = 0.0

				display_price = base_price
				mode_label = None
				retail_str = None

				if price_mode == 'price_b':
					price_b = item.get('selling_price_b')
					if price_b:
						try:
							display_price = float(price_b)
							mode_label = list_b_name.upper()
							retail_str = _sanitize(_fmt_price(base_price, symbol, decimals))
						except (TypeError, ValueError):
							pass

				try:
					raw_disc = item.get('discount_price')
					discount_price = float(raw_disc) if raw_disc else None
					if discount_price is not None and discount_price <= 0:
						discount_price = None
				except (ValueError, TypeError):
					discount_price = None

				discount_until = _sanitize(str(item.get('discount_until') or ''))

				enriched = dict(item)
				enriched['_display_price'] = display_price
				enriched['_mode_label'] = mode_label
				enriched['_retail_str'] = retail_str
				enriched['_discount_price'] = discount_price
				enriched['_discount_until'] = discount_until

				for _ in range(copies):
					pdf.add_page()
					getattr(self, f'_draw_{template_key}')(
						pdf, enriched, W, H, company, logo_path, symbol, decimals
					)

			out_path = os.path.join(
				self._tmp_dir, f'etiquetas_{uuid.uuid4().hex[:8]}.pdf'
			)
			pdf.output(out_path)
			self._open(out_path)
			return True, out_path

		except Exception as e:
			logger.error(f'Error generando etiquetas: {e}', exc_info=True)
			return False, str(e)

	# ── Helpers compartidos ────────────────────────────────────────────────────────

	def _draw_barcode_footer(
		self, pdf, barcode_val, W, H, bc_y, bc_h, foot_h, margin, font_size=4.0
	):
		"""Dibuja el código de barras centrado y el pie con código + fecha."""
		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			pdf.image(bc_path, x=margin, y=bc_y, w=W - margin * 2, h=bc_h)

		foot_y = H - foot_h
		pdf.set_fill_color(248, 250, 252)
		pdf.rect(0, foot_y, W, foot_h, 'F')
		pdf.set_draw_color(220, 220, 220)
		pdf.set_line_width(0.2)
		pdf.line(0, foot_y, W, foot_y)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_line_width(0.2)

		date_str = datetime.now().strftime('%d/%m/%y')
		code_txt = _sanitize(str(barcode_val)) if barcode_val else 'SIN CODIGO'
		half = (W - margin * 2) / 2

		pdf.set_font('Arial', '', font_size)
		pdf.set_text_color(100, 116, 139)
		pdf.set_xy(margin, foot_y + 0.5)
		pdf.cell(half, foot_h - 1, code_txt[:20], align='L')
		pdf.set_xy(margin + half, foot_y + 0.5)
		pdf.cell(half, foot_h - 1, f'Imp: {date_str}', align='R')
		pdf.set_text_color(0, 0, 0)

	# ── Templates ──────────────────────────────────────────────────────────────────

	def _draw_supermercado(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		"""58×40 mm — gondola estándar. Barcode centrado abajo."""
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		mode_label = item.get('_mode_label')
		is_offer = bool(discount_price and discount_price < display_price)

		HEADER_H = 6.0
		BC_H = 8.5
		FOOT_H = 3.5
		BODY_H = H - HEADER_H - BC_H - FOOT_H
		MARGIN = 2.5

		# ── Header ─────────────────────────────────────────────
		if is_offer:
			pdf.set_fill_color(220, 38, 38)
		elif mode_label:
			pdf.set_fill_color(37, 99, 235)
		else:
			pdf.set_fill_color(30, 41, 59)
		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		if is_offer:
			pdf.set_font('Arial', 'B', 7.5)
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, '* OFERTA IMPERDIBLE *', align='C')
		else:
			header_txt = mode_label if mode_label else (company[:24] if company else 'CloudPOS')
			if logo_path and os.path.exists(logo_path) and not mode_label:
				try:
					pdf.image(logo_path, x=MARGIN, y=0.8, h=HEADER_H - 1.6)
					pdf.set_xy(HEADER_H + 1.5, 0)
				except Exception:
					pdf.set_xy(MARGIN, 0)
			else:
				pdf.set_xy(MARGIN, 0)
			pdf.set_font('Arial', 'B', 6.5)
			pdf.cell(W - MARGIN * 2, HEADER_H, _sanitize(header_txt).upper(), align='L')

		pdf.set_text_color(0, 0, 0)

		# ── Nombre del producto ────────────────────────────────
		y = HEADER_H + 2.5
		display = f'{name} {attr}'.strip() if attr else name
		pdf.set_font('Arial', 'B', 10.5)
		for ln in _split_text(display, 28):
			if y + 4.5 > HEADER_H + BODY_H:
				break
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4.5, ln, align='L')
			y += 4.5

		# ── Precio ─────────────────────────────────────────────
		price_zone_top = HEADER_H + BODY_H - 13
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top)
			pdf.set_font('Arial', '', 7.5)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(W - MARGIN * 2, 4, f'Antes: {orig_str}', align='L')
			self._draw_strikethrough(pdf, MARGIN + 11, price_zone_top, orig_str, 2.2)
			pdf.set_text_color(0, 0, 0)

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 3.5)
			pdf.set_font('Arial', 'B', 22)
			pdf.set_text_color(220, 38, 38)
			pdf.cell(W - MARGIN * 2, 10, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)

			if discount_until:
				pdf.set_xy(MARGIN, price_zone_top + 13)
				pdf.set_font('Arial', 'I', 5)
				pdf.set_text_color(160, 50, 50)
				pdf.cell(W - MARGIN * 2, 3, f'Valido hasta: {discount_until}', align='L')
				pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 2)
			pdf.set_font('Arial', 'B', 24)
			pdf.set_text_color(15, 23, 42)
			pdf.cell(W - MARGIN * 2, 11, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Separador ──────────────────────────────────────────
		sep_y = HEADER_H + BODY_H
		pdf.set_draw_color(210, 210, 210)
		pdf.set_line_width(0.25)
		pdf.line(MARGIN, sep_y, W - MARGIN, sep_y)
		pdf.set_draw_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		self._draw_barcode_footer(pdf, barcode_val, W, H, sep_y + 0.5, BC_H - 1, FOOT_H, MARGIN)

	def _draw_producto(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		"""70×50 mm — producto completo con más espacio para nombre."""
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		mode_label = item.get('_mode_label')
		is_offer = bool(discount_price and discount_price < display_price)

		HEADER_H = 7.0
		BC_H = 10.0
		FOOT_H = 4.0
		BODY_H = H - HEADER_H - BC_H - FOOT_H
		MARGIN = 3.0

		# ── Header ─────────────────────────────────────────────
		accent = (220, 38, 38) if is_offer else (37, 99, 235) if mode_label else (15, 23, 42)
		pdf.set_fill_color(*accent)
		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		if is_offer:
			pdf.set_font('Arial', 'B', 9)
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, '* OFERTA IMPERDIBLE *', align='C')
		else:
			brand_txt = mode_label if mode_label else (company[:30] if company else 'CloudPOS')
			if logo_path and os.path.exists(logo_path) and not mode_label:
				try:
					pdf.image(logo_path, x=MARGIN, y=1, h=HEADER_H - 2)
					pdf.set_xy(HEADER_H + 2, 0)
				except Exception:
					pdf.set_xy(MARGIN, 0)
			else:
				pdf.set_xy(MARGIN, 0)
			pdf.set_font('Arial', 'B', 7)
			pdf.cell(W - MARGIN * 2, HEADER_H, _sanitize(brand_txt).upper(), align='L')

		pdf.set_text_color(0, 0, 0)

		# ── Nombre del producto ────────────────────────────────
		y = HEADER_H + 3.5
		pdf.set_font('Arial', 'B', 13)
		for ln in _split_text(name, 26):
			if y + 6 > HEADER_H + BODY_H - 2:
				break
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 6, ln, align='L')
			y += 6

		if attr:
			pdf.set_font('Arial', '', 8)
			pdf.set_text_color(100, 116, 139)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4, attr[:34], align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Precio ─────────────────────────────────────────────
		price_zone_top = HEADER_H + BODY_H - 16
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top)
			pdf.set_font('Arial', '', 8.5)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(W - MARGIN * 2, 4.5, f'Antes: {orig_str}', align='L')
			self._draw_strikethrough(pdf, MARGIN + 13, price_zone_top, orig_str, 2.5)
			pdf.set_text_color(0, 0, 0)

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 4)
			pdf.set_font('Arial', 'B', 26)
			pdf.set_text_color(220, 38, 38)
			pdf.cell(W - MARGIN * 2, 12, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)

			if discount_until:
				pdf.set_xy(MARGIN, price_zone_top + 16)
				pdf.set_font('Arial', 'I', 5.5)
				pdf.set_text_color(160, 50, 50)
				pdf.cell(W - MARGIN * 2, 3.5, f'Valido hasta: {discount_until}', align='L')
				pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 4)
			pdf.set_font('Arial', 'B', 28)
			pdf.set_text_color(15, 23, 42)
			pdf.cell(W - MARGIN * 2, 13, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Separador ──────────────────────────────────────────
		sep_y = HEADER_H + BODY_H
		pdf.set_draw_color(210, 210, 210)
		pdf.set_line_width(0.25)
		pdf.line(MARGIN, sep_y, W - MARGIN, sep_y)
		pdf.set_draw_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		self._draw_barcode_footer(pdf, barcode_val, W, H, sep_y + 0.5, BC_H - 1, FOOT_H, MARGIN, font_size=4.5)

	def _draw_precio(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		"""50×30 mm — etiqueta de precio puro, minimalista."""
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		is_offer = bool(discount_price and discount_price < display_price)

		BC_H = 4.5
		FOOT_H = 3.0
		MARGIN = 2.0

		# ── Borde y barra de acento superior ──────────────────
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.4)
		pdf.rect(0.5, 0.5, W - 1, H - 1)
		accent = (220, 38, 38) if is_offer else (30, 41, 59)
		pdf.set_fill_color(*accent)
		pdf.rect(0.5, 0.5, W - 1, 2.5, 'F')
		pdf.set_draw_color(0, 0, 0)

		# ── Nombre ─────────────────────────────────────────────
		y = 5.0
		full_name = f'{name} {attr}'.strip() if attr else name
		pdf.set_font('Arial', 'B', 8.5)
		pdf.set_text_color(51, 65, 85)
		pdf.set_xy(MARGIN, y)
		pdf.cell(W - MARGIN * 2, 4.5, full_name[:30], align='L')
		y += 5.0

		# ── Precio ─────────────────────────────────────────────
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', '', 6)
			pdf.set_text_color(150, 150, 150)
			pdf.cell(W - MARGIN * 2, 3, f'Antes: {orig_str}', align='C')
			self._draw_strikethrough(pdf, (W - pdf.get_string_width(orig_str)) / 2 - 4, y, orig_str, 1.8)
			y += 3.5

		price_to_show = discount_price if is_offer else display_price
		price_str = _sanitize(_fmt_price(price_to_show, symbol, decimals))
		pdf.set_xy(0, y)
		pdf.set_font('Arial', 'B', 18)
		pdf.set_text_color(220, 38, 38 if is_offer else 15)
		if not is_offer:
			pdf.set_text_color(15, 23, 42)
		pdf.cell(W, 9, price_str, align='C')
		pdf.set_text_color(0, 0, 0)

		if is_offer and discount_until:
			pdf.set_xy(MARGIN, y + 9)
			pdf.set_font('Arial', 'I', 4.5)
			pdf.set_text_color(160, 50, 50)
			pdf.cell(W - MARGIN * 2, 3, f'Hasta: {discount_until}', align='C')
			pdf.set_text_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		sep_y = H - BC_H - FOOT_H
		self._draw_barcode_footer(pdf, barcode_val, W, H, sep_y, BC_H, FOOT_H, MARGIN, font_size=3.5)

	def _draw_mini(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		"""38×25 mm — mini tag para productos pequeños."""
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		mode_label = item.get('_mode_label')
		is_offer = bool(discount_price and discount_price < display_price)

		HEADER_H = 4.0
		BC_H = 5.0
		FOOT_H = 2.8
		BODY_H = H - HEADER_H - BC_H - FOOT_H
		MARGIN = 1.5

		# ── Header ─────────────────────────────────────────────
		if is_offer:
			pdf.set_fill_color(220, 38, 38)
			header_txt = '* OFERTA *'
		elif mode_label:
			pdf.set_fill_color(37, 99, 235)
			header_txt = _sanitize(mode_label[:18])
		else:
			pdf.set_fill_color(247, 127, 0)
			header_txt = _sanitize(company[:18]) if company else 'CloudPOS'

		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)
		pdf.set_font('Arial', 'B', 6)
		pdf.set_xy(0, 0.5)
		pdf.cell(W, HEADER_H - 1, header_txt.upper(), align='C')
		pdf.set_text_color(0, 0, 0)

		# ── Nombre ─────────────────────────────────────────────
		y = HEADER_H + 1.0
		display = f'{name} {attr}'.strip() if attr else name
		pdf.set_font('Arial', 'B', 7.5)
		pdf.set_xy(MARGIN, y)
		pdf.cell(W - MARGIN * 2, 3.5, display[:22], align='L')
		y += 4.0

		# ── Precio ─────────────────────────────────────────────
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_font('Arial', '', 5.5)
			pdf.set_text_color(150, 150, 150)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 2.5, orig_str, align='L')
			self._draw_strikethrough(pdf, MARGIN, y, orig_str, 1.5)
			pdf.set_text_color(0, 0, 0)
			y += 3.0

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_font('Arial', 'B', 12)
			pdf.set_text_color(220, 38, 38)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 5, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_font('Arial', 'B', 13)
			pdf.set_text_color(247, 127, 0)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 6, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		sep_y = H - BC_H - FOOT_H
		self._draw_barcode_footer(pdf, barcode_val, W, H, sep_y, BC_H, FOOT_H, MARGIN, font_size=3.5)

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
