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

		HEADER_H = 6.0
		FOOTER_H = 4.0
		RIGHT_W = 20.0
		LEFT_W = W - RIGHT_W
		BODY_H = H - HEADER_H - FOOTER_H

		# Header - Brand or OFFER focus
		is_offer = bool(discount_price and discount_price < display_price)
		
		if is_offer:
			pdf.set_fill_color(220, 38, 38) # Red 600
		else:
			pdf.set_fill_color(30, 41, 59) # Slate 800
			
		pdf.rect(0, 0, W, HEADER_H, 'F')
		
		# Logo or Company Name
		if logo_path and os.path.exists(logo_path) and not is_offer:
			try:
				pdf.image(logo_path, x=1.5, y=1, h=HEADER_H-2)
				pdf.set_xy(HEADER_H + 1, 0)
			except:
				pdf.set_xy(1.5, 0)
		else:
			pdf.set_xy(1.5, 0)

		pdf.set_text_color(255, 255, 255)
		pdf.set_font('Arial', 'B', 7)
		
		if is_offer:
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, '🔥 ¡OFERTA IMPERDIBLE! 🔥', align='C')
		else:
			header_txt = mode_label if mode_label else company[:20] if company else 'CloudPOS'
			pdf.cell(LEFT_W - 2, HEADER_H, _sanitize(header_txt).upper(), align='L')
			pdf.set_font('Arial', '', 5)
			pdf.set_xy(LEFT_W, 0)
			pdf.cell(RIGHT_W - 1, HEADER_H, 'S.MERCADO', align='R')

		pdf.set_text_color(0, 0, 0)
		
		# Body
		y = HEADER_H + 2
		display = f'{name} {attr}'.strip() if attr else name
		
		pdf.set_font('Arial', 'B', 11)
		lines = _split_text(display, 22)
		for ln in lines:
			if y + 4.5 > H - FOOTER_H: break
			pdf.set_xy(2, y)
			pdf.cell(LEFT_W - 3, 4.5, ln, align='L')
			y += 4.5

		# Price Section
		y_price = H - FOOTER_H - 12
		if is_offer:
			# Strikethrough original
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(2, y_price - 3.5)
			pdf.set_font('Arial', '', 8)
			pdf.set_text_color(120, 120, 120)
			pdf.cell(LEFT_W - 3, 4, f'Antes: {orig_str}', align='L')
			self._draw_strikethrough(pdf, 10, y_price - 3.5, orig_str, 2.5)
			
			# New price in RED
			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(2, y_price + 1)
			pdf.set_font('Arial', 'B', 20)
			pdf.set_text_color(220, 38, 38)
			pdf.cell(LEFT_W - 3, 8, disc_str, align='L')
			
			# Date validation
			if discount_until:
				pdf.set_xy(2, y_price + 9)
				pdf.set_font('Arial', 'I', 5)
				pdf.set_text_color(150, 50, 50)
				pdf.cell(LEFT_W - 3, 3, f'Válido hasta: {discount_until}', align='L')
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(2, y_price)
			pdf.set_font('Arial', 'B', 20)
			pdf.set_text_color(15, 23, 42)
			pdf.cell(LEFT_W - 3, 10, price_str, align='L')

		# Barcode
		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			bc_x = LEFT_W + 1
			bc_y = HEADER_H + 2
			bc_w = RIGHT_W - 2
			bc_h = BODY_H - 2
			pdf.image(bc_path, x=bc_x, y=bc_y, w=bc_w, h=bc_h)
			
		# Footer
		pdf.set_fill_color(248, 250, 252)
		pdf.rect(0, H - FOOTER_H, W, FOOTER_H, 'F')
		pdf.set_draw_color(226, 232, 240)
		pdf.line(0, H - FOOTER_H, W, H - FOOTER_H)
		
		pdf.set_xy(2, H - FOOTER_H + 0.5)
		pdf.set_font('Arial', '', 4)
		pdf.set_text_color(100, 116, 139)
		footer_txt = f'IVA INCLUIDO  ·  {barcode_val}'
		if is_offer: footer_txt = f'PROMOCIÓN LIMITADA  ·  {barcode_val}'
		pdf.cell(W - 4, 3, footer_txt, align='L')

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
		is_offer = bool(discount_price and discount_price < display_price)

		# Design Constants
		accent_color = (220, 38, 38) if is_offer else (37, 99, 235) if mode_label else (15, 23, 42)
		pdf.set_fill_color(*accent_color)
		pdf.rect(0, 0, W, 2.5, 'F') # Top bar

		y = 4.5
		if is_offer:
			pdf.set_fill_color(220, 38, 38)
			pdf.rect(W-25, 0, 25, 8, 'F')
			pdf.set_text_color(255, 255, 255)
			pdf.set_font('Arial', 'B', 8)
			pdf.set_xy(W-25, 0)
			pdf.cell(25, 8, 'OFERTA', align='C')
			pdf.set_text_color(*accent_color)
		
		if logo_path and os.path.exists(logo_path) and not is_offer:
			pdf.image(logo_path, x=W-12, y=3.5, h=6)
		
		pdf.set_xy(4, y)
		pdf.set_font('Arial', 'B', 7)
		pdf.set_text_color(*accent_color)
		pdf.cell(W-20, 4, company[:25].upper() if company else 'CLOUD POS', align='L')
		y += 6

		# Product Name
		pdf.set_font('Arial', 'B', 14)
		pdf.set_text_color(0, 0, 0)
		lines = _split_text(name, 24)
		for ln in lines:
			if y + 6 > H - 15: break
			pdf.set_xy(4, y)
			pdf.cell(W - 8, 6, ln, align='L')
			y += 6

		# Big Price
		y_price = H - 16
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(4, y_price - 4)
			pdf.set_font('Arial', '', 9)
			pdf.set_text_color(120, 120, 120)
			pdf.cell(W - 8, 5, f'Antes: {orig_str}', align='L')
			self._draw_strikethrough(pdf, 14, y_price - 4, orig_str, 3)

			price_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_text_color(220, 38, 38)
			if discount_until:
				pdf.set_xy(4, H-6)
				pdf.set_font('Arial', 'I', 5.5)
				pdf.cell(W-30, 4, f'Promoción válida hasta: {discount_until}', align='L')
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_text_color(0, 0, 0)
			
		pdf.set_xy(4, y_price)
		pdf.set_font('Arial', 'B', 24)
		pdf.cell(W - 8, 10, price_str, align='L')

		# Barcode Footer
		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			pdf.image(bc_path, x=W-26, y=H-13, w=22, h=9)
			pdf.set_xy(W-25, H-4)
			pdf.set_font('Arial', '', 4)
			pdf.cell(20, 3, str(barcode_val), align='C')

	def _draw_precio(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			display_price = float(item.get('_display_price') or item.get('price') or 0)
		except (ValueError, TypeError):
			display_price = 0.0

		discount_price = item.get('_discount_price')

		# Minimalist Price Tag
		pdf.set_draw_color(226, 232, 240)
		pdf.set_line_width(0.5)
		pdf.rect(1, 1, W-2, H-2)

		y = 4
		pdf.set_xy(3, y)
		pdf.set_font('Arial', 'B', 9)
		pdf.set_text_color(51, 65, 85)
		pdf.cell(W-6, 5, name[:28], align='L')
		y += 5

		if attr:
			pdf.set_xy(3, y)
			pdf.set_font('Arial', '', 7)
			pdf.set_text_color(100, 116, 139)
			pdf.cell(W-6, 4, attr[:32], align='L')
			y += 4

		# Center Price
		pdf.set_xy(0, H/2 - 2)
		pdf.set_font('Arial', 'B', 16)
		if discount_price:
			pdf.set_text_color(220, 38, 38)
			price_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
		else:
			pdf.set_text_color(15, 23, 42)
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
		pdf.cell(W, 10, price_str, align='C')

		# Small Barcode
		bc_path = self._generate_barcode_png(barcode_val)
		if bc_path:
			pdf.image(bc_path, x=W/2 - 10, y=H-8, w=20, h=5)

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
