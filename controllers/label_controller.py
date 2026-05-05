import io
import logging
import os
import platform
import re
import subprocess
import tempfile
import unicodedata
import uuid
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


def _compute_wholesale_price(base_price: float, rule: dict) -> float:
	try:
		pct = float(rule.get('discount_pct') or 0)
		return round(base_price * (1 - pct / 100), 2)
	except (TypeError, ValueError):
		return base_price


def _split_text(text: str, max_chars: int) -> list:
	if len(text) <= max_chars:
		return [text]
	idx = text.rfind(' ', 0, max_chars)
	if idx == -1:
		idx = max_chars
	line1 = text[:idx]
	line2 = text[idx:].strip()[:max_chars]
	return [line1, line2] if line2 else [line1]


class LabelController:
	def __init__(self):
		self._tmp_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Etiquetas')
		os.makedirs(self._tmp_dir, exist_ok=True)
		self._bc_cache: dict = {}

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

			wholesale_enabled = cfg.get('wholesale_enabled', False)
			wholesale_rules = sorted(
				cfg.get('wholesale_rules', []),
				key=lambda r: float(r.get('min_qty') or 0),
				reverse=True,
			)

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

				if wholesale_enabled and price_mode.startswith('wholesale_'):
					try:
						rule_idx = int(price_mode.split('_', 1)[1])
						if 0 <= rule_idx < len(wholesale_rules):
							rule = wholesale_rules[rule_idx]
							display_price = _compute_wholesale_price(base_price, rule)
							min_qty = int(float(rule.get('min_qty') or 0))
							pct = float(rule.get('discount_pct') or 0)
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

	def _draw_supermercado(self, pdf, item, W, H, company, logo_path, symbol, decimals):
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

		HEADER_H = 4.5
		FOOTER_H = 3.5
		RIGHT_W = 18.0
		LEFT_W = W - RIGHT_W
		BODY_H = H - HEADER_H - FOOTER_H

		pdf.set_fill_color(26, 26, 46)
		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		if mode_label:
			pdf.set_xy(0, 0.5)
			pdf.set_font('Arial', 'B', 5.5)
			pdf.cell(W, 3.5, mode_label, align='C')
		else:
			lbl_left = _sanitize(company[:14]) if company else 'CloudPOS'
			pdf.set_xy(1, 0.5)
			pdf.set_font('Arial', 'B', 5.5)
			pdf.cell(LEFT_W - 1, 3.5, lbl_left, align='L')
			pdf.set_xy(LEFT_W, 0.5)
			pdf.set_font('Arial', '', 5)
			pdf.cell(RIGHT_W - 1, 3.5, 'SUPERMERCADO', align='R')

		pdf.set_text_color(0, 0, 0)
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.2)
		pdf.line(LEFT_W, HEADER_H, LEFT_W, H - FOOTER_H)
		pdf.set_draw_color(0, 0, 0)

		y = HEADER_H + 1.5
		display = f'{name} {attr}'.strip() if attr else name
		lines = _split_text(display, 24)

		pdf.set_font('Arial', 'B', 10)
		for ln in lines:
			if y + 4.5 > H - FOOTER_H - 1:
				break
			pdf.set_xy(1.5, y)
			pdf.cell(LEFT_W - 2, 4.5, ln, align='L')
			y += 4.5

		sku_str = str(barcode_val)[:16]
		if sku_str:
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', '', 5)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(LEFT_W - 2, 3, 'SKU: ' + sku_str, align='L')
			pdf.set_text_color(0, 0, 0)
			y += 3

		y += 0.5

		if discount_price and discount_price < display_price:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', '', 7)
			pdf.set_text_color(160, 160, 160)
			pdf.cell(LEFT_W - 2, 4, orig_str, align='L')
			self._draw_strikethrough(pdf, 1.5, y, orig_str, 2.5)
			pdf.set_text_color(0, 0, 0)
			y += 4

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', 'B', 14)
			pdf.set_text_color(180, 30, 30)
			pdf.cell(LEFT_W - 2, 7, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)
			y += 7

			if discount_until:
				pdf.set_xy(1.5, y)
				pdf.set_font('Arial', 'I', 5)
				pdf.set_text_color(120, 60, 60)
				pdf.cell(LEFT_W - 2, 3, f'Valido hasta: {discount_until}', align='L')
				pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', 'B', 16)
			pdf.set_text_color(26, 26, 46)
			pdf.cell(LEFT_W - 2, 9, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			bc_x = LEFT_W + 1
			bc_y = HEADER_H + 1.5
			bc_w = RIGHT_W - 2
			bc_h = BODY_H - 4
			pdf.image(bc_path, x=bc_x, y=bc_y, w=bc_w, h=bc_h)
			pdf.set_xy(LEFT_W, bc_y + bc_h + 0.3)
			pdf.set_font('Arial', '', 4)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(RIGHT_W, 2, str(barcode_val)[:14], align='C')
			pdf.set_text_color(0, 0, 0)

		footer_y = H - FOOTER_H
		pdf.set_fill_color(245, 245, 245)
		pdf.rect(0, footer_y, W, FOOTER_H, 'F')
		pdf.set_draw_color(215, 215, 215)
		pdf.set_line_width(0.2)
		pdf.line(0, footer_y, W, footer_y)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_xy(1.5, footer_y + 0.8)
		pdf.set_font('Arial', '', 4.5)
		pdf.set_text_color(130, 130, 130)
		pdf.cell(W - 2, 2.5, 'IVA incluido', align='L')
		pdf.set_text_color(0, 0, 0)

	def _draw_producto(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')
		category = _sanitize(item.get('category', ''))

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		mode_label = item.get('_mode_label')
		retail_str = item.get('_retail_str')

		STRIPE_H = 2.5
		FOOTER_H = 8.0
		MARGIN = 2.5

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
		else:
			pdf.set_fill_color(193, 18, 31)
		pdf.rect(0, 0, W, STRIPE_H, 'F')

		if mode_label:
			pdf.set_text_color(255, 255, 255)
			pdf.set_xy(0, 0.3)
			pdf.set_font('Arial', 'B', 6)
			pdf.cell(W, STRIPE_H - 0.3, mode_label, align='C')
			pdf.set_text_color(0, 0, 0)

		y = STRIPE_H + 1.5

		if category:
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'B', 6)
			pdf.set_text_color(193, 18, 31)
			pdf.cell(W - MARGIN * 2, 3.5, category[:28].upper(), align='L')
			pdf.set_text_color(0, 0, 0)
			y += 3.5

		lines = _split_text(name, 28)
		pdf.set_font('Arial', 'B', 12)
		for ln in lines:
			if y + 5.5 > H - FOOTER_H - 1:
				break
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 5.5, ln, align='L')
			y += 5.5

		if attr:
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'I', 7)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(W - MARGIN * 2, 3.5, attr[:38], align='L')
			pdf.set_text_color(0, 0, 0)
			y += 3.5

		y += 1.5

		if discount_price and discount_price < display_price:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', '', 8)
			pdf.set_text_color(160, 160, 160)
			pdf.cell(W - MARGIN * 2, 5, orig_str, align='L')
			self._draw_strikethrough(pdf, MARGIN, y, orig_str, 3.0)
			pdf.set_text_color(0, 0, 0)
			y += 5

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'B', 20)
			pdf.set_text_color(193, 18, 31)
			pdf.cell(W - MARGIN * 2, 10, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)
			y += 10

			if discount_until:
				pdf.set_xy(MARGIN, y)
				pdf.set_font('Arial', 'I', 5.5)
				pdf.set_text_color(120, 60, 60)
				pdf.cell(
					W - MARGIN * 2, 3, f'Valido hasta: {discount_until}', align='L'
				)
				pdf.set_text_color(0, 0, 0)
		else:
			if retail_str:
				pdf.set_xy(MARGIN, y)
				pdf.set_font('Arial', 'I', 7)
				pdf.set_text_color(160, 160, 160)
				pdf.cell(W - MARGIN * 2, 4, f'Minorista: {retail_str}', align='L')
				pdf.set_text_color(0, 0, 0)
				y += 4

			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'B', 20)
			pdf.set_text_color(193, 18, 31)
			pdf.cell(W - MARGIN * 2, 10, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		footer_y = H - FOOTER_H
		pdf.set_fill_color(248, 248, 248)
		pdf.rect(0, footer_y, W, FOOTER_H, 'F')
		pdf.set_draw_color(215, 215, 215)
		pdf.set_line_width(0.2)
		pdf.line(0, footer_y, W, footer_y)
		pdf.set_draw_color(0, 0, 0)

		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			bc_w = W - MARGIN * 8
			bc_h = FOOTER_H - 2.5
			bc_x = (W - bc_w) / 2
			pdf.image(bc_path, x=bc_x, y=footer_y + 0.5, w=bc_w, h=bc_h)

		pdf.set_xy(0, footer_y + FOOTER_H - 2.5)
		pdf.set_font('Arial', '', 4.5)
		pdf.set_text_color(150, 150, 150)
		pdf.cell(W, 2, str(barcode_val), align='C')
		pdf.set_text_color(0, 0, 0)

	def _draw_precio(self, pdf, item, W, H, company, logo_path, symbol, decimals):
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
		retail_str = item.get('_retail_str')

		HEADER_H = 7.0
		FOOTER_H = 4.0
		BC_W = 18.0
		LEFT_W = W - BC_W

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
		else:
			pdf.set_fill_color(45, 106, 79)
		pdf.rect(0, 0, W, HEADER_H, 'F')

		display = f'{name} {attr}'.strip() if attr else name
		pdf.set_text_color(255, 255, 255)

		lines = _split_text(display, 26)
		line_h = HEADER_H / max(len(lines), 1)
		for i, ln in enumerate(lines):
			pdf.set_xy(1.5, i * line_h + 0.5)
			font_sz = 8 if len(display) > 22 else 10
			pdf.set_font('Arial', 'B', font_sz)
			pdf.cell(W - 3, line_h - 0.5, ln, align='L')

		if mode_label:
			pdf.set_xy(0, 0.5)
			pdf.set_font('Arial', 'B', 7)
			pdf.cell(W, HEADER_H - 1, mode_label, align='C')

		pdf.set_text_color(0, 0, 0)

		y = HEADER_H + 1.0

		if discount_price and discount_price < display_price:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', '', 7)
			pdf.set_text_color(160, 160, 160)
			pdf.cell(LEFT_W - 2, 4, orig_str, align='L')
			self._draw_strikethrough(pdf, 1.5, y, orig_str, 2.5)
			pdf.set_text_color(0, 0, 0)
			y += 4

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', 'B', 16)
			pdf.set_text_color(180, 30, 30)
			pdf.cell(LEFT_W - 2, 8, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)

			if discount_until:
				pdf.set_xy(1.5, y + 8)
				pdf.set_font('Arial', 'I', 4.5)
				pdf.set_text_color(120, 60, 60)
				pdf.cell(LEFT_W - 2, 3, f'Hasta: {discount_until}', align='L')
				pdf.set_text_color(0, 0, 0)
		else:
			if retail_str and mode_label:
				pdf.set_xy(1.5, y)
				pdf.set_font('Arial', 'I', 5)
				pdf.set_text_color(120, 120, 120)
				pdf.cell(LEFT_W - 2, 3.5, f'Min: {retail_str}', align='L')
				pdf.set_text_color(0, 0, 0)
				y += 3.5

			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(1.5, y)
			pdf.set_font('Arial', 'B', 18)
			pdf.set_text_color(45, 106, 79)
			pdf.cell(LEFT_W - 2, 10, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			bc_x = LEFT_W + 1
			bc_y = HEADER_H + 0.8
			bc_w = BC_W - 2
			bc_h = H - HEADER_H - FOOTER_H - 1
			pdf.image(bc_path, x=bc_x, y=bc_y, w=bc_w, h=bc_h)

		footer_y = H - FOOTER_H
		pdf.set_fill_color(245, 245, 245)
		pdf.rect(0, footer_y, W, FOOTER_H, 'F')
		pdf.set_draw_color(210, 210, 210)
		pdf.set_line_width(0.2)
		pdf.line(0, footer_y, W, footer_y)
		pdf.set_draw_color(0, 0, 0)

		pdf.set_xy(1.5, footer_y + 0.8)
		pdf.set_font('Arial', '', 4.5)
		pdf.set_text_color(120, 120, 120)
		pdf.cell(W - 3, 2.5, f'{barcode_val}  ·  IVA incluido', align='L')
		pdf.set_text_color(0, 0, 0)

	def _draw_mini(self, pdf, item, W, H, company, logo_path, symbol, decimals):
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

		HEADER_H = 4.0
		FOOTER_H = 4.5
		MARGIN = 1.5

		if mode_label:
			pdf.set_fill_color(37, 99, 235)
			header_left = mode_label[:20]
		elif discount_price:
			pdf.set_fill_color(200, 60, 0)
			header_left = 'OFERTA'
		else:
			pdf.set_fill_color(247, 127, 0)
			header_left = _sanitize(company[:16]) if company else 'CloudPOS'

		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		pdf.set_xy(MARGIN, 0.5)
		pdf.set_font('Arial', 'B', 6)
		pdf.cell(W / 2 - MARGIN, 3, header_left, align='L')

		if company and not mode_label:
			pdf.set_xy(W / 2, 0.5)
			pdf.set_font('Arial', '', 5.5)
			pdf.cell(W / 2 - MARGIN, 3, _sanitize(company[:14]), align='R')

		pdf.set_text_color(0, 0, 0)

		y = HEADER_H + 1.0
		display = f'{name} {attr}'.strip() if attr else name

		pdf.set_xy(MARGIN, y)
		pdf.set_font('Arial', 'B', 8)
		pdf.cell(W - MARGIN * 2, 4, display[:22], align='L')
		y += 4

		if discount_price and discount_price < display_price:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', '', 6)
			pdf.set_text_color(160, 160, 160)
			pdf.cell(W - MARGIN * 2, 3, orig_str, align='L')
			self._draw_strikethrough(pdf, MARGIN, y, orig_str, 2.0)
			pdf.set_text_color(0, 0, 0)
			y += 3

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'B', 12)
			pdf.set_text_color(200, 60, 0)
			pdf.cell(W - MARGIN * 2, 6, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)
			y += 6

			if discount_until:
				pdf.set_xy(MARGIN, y)
				pdf.set_font('Arial', 'I', 4.5)
				pdf.set_text_color(120, 60, 60)
				pdf.cell(W - MARGIN * 2, 2.5, f'Hasta: {discount_until}', align='L')
				pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Arial', 'B', 14)
			pdf.set_text_color(247, 127, 0)
			pdf.cell(W - MARGIN * 2, 7, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		footer_y = H - FOOTER_H
		pdf.set_fill_color(40, 40, 40)
		pdf.rect(0, footer_y, W, FOOTER_H, 'F')

		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			bc_w = W - 3
			bc_h = FOOTER_H - 1.2
			pdf.image(bc_path, x=1.5, y=footer_y + 0.2, w=bc_w, h=bc_h)

		pdf.set_xy(0, footer_y + FOOTER_H - 2)
		pdf.set_font('Arial', '', 4)
		pdf.set_text_color(180, 180, 180)
		pdf.cell(W, 1.8, str(barcode_val)[:18], align='C')
		pdf.set_text_color(0, 0, 0)

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
