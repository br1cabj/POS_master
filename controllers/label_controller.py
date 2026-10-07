import io
import logging
import os
import platform
import re
import subprocess
import tempfile
import time
import unicodedata
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
	'dual': {
		'label': 'Dual (A+B)',
		'desc': '70 × 50 mm',
		'w_mm': 70,
		'h_mm': 50,
		'icon': '🔄',
	},
}


def _sanitize(text: str) -> str:
	if not text:
		return ''
	# Las fuentes base de FPDF usan Latin-1. Normalizar comillas y guiones
	# tipográficos evita que un texto válido del catálogo cancele todo el PDF.
	translations = str.maketrans({
		'—': '-', '–': '-', '−': '-', '…': '...', '“': '"', '”': '"',
		'‘': "'", '’': "'", '•': '-', '·': '-',
	})
	return (
		unicodedata.normalize('NFC', str(text)).translate(translations)
		.encode('latin-1', 'replace')
		.decode('latin-1')
	)


def _fmt_price(amount: float, symbol: str = '$', decimals: int = 0) -> str:
	try:
		amount = float(amount or 0)
	except (ValueError, TypeError):
		amount = 0.0
	# La aplicación usa formato hispano: $1.234,50.  El formato de Python
	# (1,234.50) era inconsistente con el resto del POS y puede inducir a error.
	formatted = f'{amount:,.{max(0, decimals)}f}'
	return f'{symbol}{formatted.replace(",", "_").replace(".", ",").replace("_", ".")}'


def _split_text(text: str, max_chars: int) -> list:
	if len(text) <= max_chars:
		return [text]
	idx = text.rfind(' ', 0, max_chars)
	if idx == -1:
		idx = max_chars
	line1 = text[:idx]
	line2 = text[idx:].strip()[:max_chars]
	return [line1, line2] if line2 else [line1]


def _fit_text(pdf, text: str, max_width: float) -> str:
	"""Ajusta texto por ancho real de fuente y agrega puntos suspensivos."""
	text = str(text or '').strip()
	if not text or pdf.get_string_width(text) <= max_width:
		return text
	ellipsis = '...'
	while text and pdf.get_string_width(text + ellipsis) > max_width:
		text = text[:-1].rstrip()
	return (text + ellipsis) if text else ellipsis


def _wrap_label_text(pdf, text: str, max_width: float, max_lines: int) -> list[str]:
	"""Parte texto por palabras sin invadir la zona reservada de una etiqueta."""
	words = str(text or '').split()
	if not words:
		return []
	lines: list[str] = []
	current = ''
	for word in words:
		candidate = f'{current} {word}'.strip()
		if not current or pdf.get_string_width(candidate) <= max_width:
			current = candidate
			continue
		lines.append(current)
		current = word
		if len(lines) == max_lines:
			break
	if len(lines) < max_lines and current:
		lines.append(current)
	if len(lines) > max_lines:
		lines = lines[:max_lines]
	if len(lines) == max_lines and (len(' '.join(lines)) < len(' '.join(words))):
		lines[-1] = _fit_text(pdf, lines[-1], max_width - pdf.get_string_width('...')) + '...'
	return [_fit_text(pdf, line, max_width) for line in lines]


_BC_CACHE_MAXSIZE = 200


class LabelController:
	def __init__(self):
		self._tmp_dir = os.path.join(tempfile.gettempdir(), 'CloudPOS_Etiquetas')
		os.makedirs(self._tmp_dir, exist_ok=True)
		self._bc_cache: dict = {}
		self.last_delivery_message = ''
		self._clean_old_temp_files()

	def _clean_old_temp_files(self, max_age_hours: int = 24):
		"""Elimina archivos temporales de etiquetas y barcodes más antiguos que max_age_hours."""
		try:
			cutoff = time.time() - (max_age_hours * 3600)
			for fname in os.listdir(self._tmp_dir):
				fpath = os.path.join(self._tmp_dir, fname)
				try:
					if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
						os.unlink(fpath)
				except OSError:
					pass
		except OSError:
			pass

	@staticmethod
	def generate_internal_barcode() -> str:
		"""Genera un código Code128 interno único para artículos sin EAN."""
		return 'INT' + uuid.uuid4().hex[:11].upper()

	@staticmethod
	def _check_digit(digits: str) -> int:
		"""Calcula el dígito de control GS1 para EAN/UPC."""
		return (10 - sum(
			int(digit) * (3 if index % 2 == 0 else 1)
			for index, digit in enumerate(reversed(digits))
		) % 10) % 10

	@classmethod
	def barcode_spec(cls, code: str) -> tuple[str, str]:
		"""Valida un código y devuelve la simbología y los datos para python-barcode.

		EAN-8, EAN-13 y UPC-A se validan con checksum. Los identificadores internos
		y alfanuméricos siguen usando Code128, que es apropiado para el POS.
		"""
		value = str(code or '').strip()
		if not value:
			raise ValueError('La etiqueta requiere un código de barras.')
		if len(value) > 48 or any(ord(char) < 32 or ord(char) > 126 for char in value):
			raise ValueError('El código contiene caracteres no imprimibles o es demasiado largo.')
		if value.isdigit() and len(value) in (8, 12, 13):
			if cls._check_digit(value[:-1]) != int(value[-1]):
				raise ValueError(f'El código {value} tiene un dígito verificador inválido.')
			# python-barcode recibe los dígitos sin checksum y lo vuelve a calcular.
			return ({8: 'ean8', 12: 'upc', 13: 'ean13'}[len(value)], value[:-1])
		return 'code128', value

	@classmethod
	def validate_barcode(cls, code: str) -> Optional[str]:
		try:
			cls.barcode_spec(code)
			return None
		except ValueError as error:
			return str(error)

	def ensure_variant_barcode(self, db_engine, tenant_id: str, variant_id: str) -> str:
		"""Asigna y persiste un Code128 interno a una variante que no tenía código."""
		from sqlalchemy.orm import sessionmaker as _sm
		from database.models import Article, ArticleVariant

		Session = _sm(bind=db_engine)
		with Session() as session:
			variant = (
				session.query(ArticleVariant)
				.join(Article, ArticleVariant.article_id == Article.id)
				.filter(ArticleVariant.id == variant_id, Article.tenant_id == tenant_id)
				.first()
			)
			if not variant:
				raise ValueError('El artículo ya no existe o no pertenece a esta empresa.')
			if variant.barcode and str(variant.barcode).strip():
				return str(variant.barcode).strip()
			# Aunque una colisión UUID es extremadamente improbable, se comprueba antes
			# de guardar para que el código sea realmente escaneable y único por empresa.
			for _ in range(5):
				candidate = self.generate_internal_barcode()
				exists = (
					session.query(ArticleVariant.id)
					.join(Article, ArticleVariant.article_id == Article.id)
					.filter(Article.tenant_id == tenant_id, ArticleVariant.barcode == candidate)
					.first()
				)
				if not exists:
					variant.barcode = candidate
					session.commit()
					return candidate
			raise RuntimeError('No se pudo reservar un código interno único.')

	def save_manual_article(
		self, db_engine, tenant_id: str, name: str, price: float, barcode_val: str
	) -> str:
		"""
		Persiste el artículo manual en la DB bajo la categoría 'Artículos Manuales'.
		Reutiliza el Article si ya existe con ese nombre, siempre crea una Variant nueva.
		Retorna el variant_id (UUID real) para que sea escaneable en ventas.
		"""
		from sqlalchemy.orm import sessionmaker as _sm

		from database.models import Article, ArticleVariant, Category

		name = str(name or '').strip()
		if not name:
			raise ValueError('El nombre del artículo es obligatorio.')
		try:
			price = Decimal(str(price))
		except (InvalidOperation, ValueError, TypeError) as error:
			raise ValueError('El precio es inválido.') from error
		if price < 0:
			raise ValueError('El precio no puede ser negativo.')
		barcode_val = str(barcode_val or '').strip() or self.generate_internal_barcode()
		error = self.validate_barcode(barcode_val)
		if error:
			raise ValueError(error)

		Session = _sm(bind=db_engine)
		with Session() as session:
			# Categoría por tenant para "Artículos Manuales"
			cat = (
				session.query(Category)
				.filter_by(name='Artículos Manuales', tenant_id=tenant_id)
				.first()
			)
			if not cat:
				cat = Category(name='Artículos Manuales', tenant_id=tenant_id)
				session.add(cat)
				session.flush()

			# Article por nombre + tenant (reutilizar si existe)
			article = (
				session.query(Article)
				.filter(
					Article.name == name,
					Article.tenant_id == tenant_id,
					Article.category_id == cat.id,
					Article.deleted_at.is_(None),
				)
				.first()
			)
			if not article:
				article = Article(
					name=name,
					tenant_id=tenant_id,
					category_id=cat.id,
					is_active=True,
				)
				session.add(article)
				session.flush()

			# El barcode es identificador de venta: buscarlo en toda la empresa, no
			# solamente en el artículo manual actual.
			variant = (
				session.query(ArticleVariant)
				.join(Article, ArticleVariant.article_id == Article.id)
				.filter(
					Article.tenant_id == tenant_id,
					ArticleVariant.barcode == barcode_val,
					ArticleVariant.is_active.is_(True),
					ArticleVariant.deleted_at.is_(None),
				)
				.first()
			)
			if variant:
				if variant.article_id != article.id:
					raise ValueError('Ese código ya pertenece a otro artículo de esta empresa.')
				variant.selling_price = price
			else:
				variant = ArticleVariant(
					tenant_id=tenant_id,
					article_id=article.id,
					barcode=barcode_val,
					cost_price=0,
					selling_price=price,
					is_active=True,
				)
				session.add(variant)
				session.flush()

				from database.models import Branch, Stock, Warehouse

				branch = (
					session.query(Branch)
					.filter_by(tenant_id=tenant_id, name='Sede Principal')
					.first()
				)
				if branch:
					warehouse = (
						session.query(Warehouse)
						.filter_by(branch_id=branch.id, name='Depósito General')
						.first()
					)
					if warehouse:
						session.add(
							Stock(
								tenant_id=tenant_id,
								quantity=0,
								warehouse_id=warehouse.id,
								variant_id=variant.id,
							)
						)

			session.commit()
			return variant.id

	def _generate_barcode_png(self, code: str, target_width_mm: float = 45) -> Optional[str]:
		try:
			symbology, encoded_value = self.barcode_spec(code)
		except ValueError as error:
			logger.warning('Código descartado al generar etiqueta: %s', error)
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
			cls = barcode.get_barcode_class(symbology)
			buf = io.BytesIO()
			# Mantiene una zona silenciosa generosa y reduce los módulos en códigos
			# largos para no deformarlos al ajustarlos al ancho de la etiqueta.
			module_width = max(0.18, min(0.32, (target_width_mm - 6) / max(80, len(safe_code) * 13)))
			cls(encoded_value, writer=ImageWriter()).write(
				buf,
				options={
					'write_text': False,
					'quiet_zone': 2.5,
					'module_height': 8,
					'module_width': module_width,
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

	def _validate_items(self, items: list) -> Optional[str]:
		for position, item in enumerate(items, start=1):
			name = str(item.get('name') or '').strip()
			if not name:
				return f'La etiqueta {position} no tiene nombre de artículo.'
			error = self.validate_barcode(item.get('barcode', ''))
			if error:
				return f'{name}: {error}'
			try:
				if int(float(item.get('copies', 1))) < 1:
					raise ValueError
			except (TypeError, ValueError):
				return f'{name}: la cantidad de copias debe ser mayor a cero.'
		return None

	def generate_pdf(
		self, items: list, template_key: str = 'supermercado', deliver: bool = True
	) -> tuple:
		if not items:
			return False, 'No hay artículos en la cola de impresión.'
		if error := self._validate_items(items):
			return False, error
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
					if price_b is not None:
						try:
							display_price = float(price_b)
							mode_label = list_b_name.upper()
							retail_str = _sanitize(
								_fmt_price(base_price, symbol, decimals)
							)
						except (TypeError, ValueError):
							pass
				elif price_mode == 'both':
					# mode_label no debe sobreescribirse para no pintar el header azul
					# pero queremos que en plantillas duales se use
					pass

				try:
					raw_disc = item.get('discount_price')
					discount_price = float(raw_disc) if raw_disc is not None else None
					if discount_price is not None and discount_price < 0:
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
			if deliver:
				self._deliver_pdf(out_path, cfg)
			return True, out_path

		except Exception as e:
			logger.error(f'Error generando etiquetas: {e}', exc_info=True)
			return False, str(e)

	def render_preview_image(self, item: dict, template_key: str = 'supermercado'):
		"""Renderiza exactamente la misma página que se envía a impresión.

		La vista previa no reproduce coordenadas ni reglas en la UI: rasteriza el
		PDF generado por las plantillas para eliminar diferencias visuales.
		"""
		pdf_path = None
		try:
			ok, result = self.generate_pdf([dict(item)], template_key, deliver=False)
			if not ok:
				raise ValueError(result)
			pdf_path = result
			import pypdfium2 as pdfium

			document = pdfium.PdfDocument(pdf_path)
			try:
				page = document[0]
				# 3x produce texto y barras nítidas antes de reducir en la UI.
				return page.render(scale=3).to_pil().convert('RGB')
			finally:
				document.close()
		finally:
			if pdf_path:
				try:
					os.unlink(pdf_path)
				except OSError:
					pass

	# ── Helpers compartidos ────────────────────────────────────────────────────────

	def _draw_barcode_footer(
		self, pdf, barcode_val, W, H, bc_y, bc_h, foot_h, margin, font_size=4.0
	):
		"""Dibuja el código de barras centrado y el pie con código + fecha."""
		bc_path = self._generate_barcode_png(barcode_val, W - margin * 2)
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

		pdf.set_font('Helvetica', '', font_size)
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

		# ── Borde sutil ────────────────────────────────────────
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.3)
		pdf.rect(0.2, 0.2, W - 0.4, H - 0.4)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_line_width(0.2)

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
			offer_header = f'OFERTA HASTA {discount_until}' if discount_until else '* OFERTA *'
			pdf.set_font('Helvetica', 'B', 6.2)
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, _fit_text(pdf, offer_header, W - 4), align='C')
		else:
			header_txt = (
				mode_label if mode_label else (company[:24] if company else 'CloudPOS')
			)
			if logo_path and os.path.exists(logo_path) and not mode_label:
				try:
					pdf.image(logo_path, x=MARGIN, y=0.8, h=HEADER_H - 1.6)
					pdf.set_xy(HEADER_H + 1.5, 0)
				except Exception as e:
					logger.warning('No se pudo cargar el logo en etiqueta: %s', e)
					pdf.set_xy(MARGIN, 0)
			else:
				pdf.set_xy(MARGIN, 0)
			pdf.set_font('Helvetica', 'B', 6.5)
			pdf.cell(W - MARGIN * 2, HEADER_H, _sanitize(header_txt).upper(), align='L')

		pdf.set_text_color(0, 0, 0)

		# ── Nombre: zona fija de dos líneas; no puede invadir el precio ──
		display = f'{name} - {attr}'.strip(' -') if attr else name
		pdf.set_font('Helvetica', 'B', 8.8 if is_offer else 9.5)
		lines = _wrap_label_text(pdf, display, W - MARGIN * 2, 2)
		y = HEADER_H + 1.2
		for line in lines:
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 3.5, line, align='L')
			y += 3.5

		# ── Precio: bloque reservado debajo del nombre ─────────
		price_zone_top = HEADER_H + 8.5
		if is_offer:
			before_label = 'Antes: '
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top)
			pdf.set_font('Helvetica', '', 6.5)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(W - MARGIN * 2, 3, before_label + orig_str, align='L')
			strike_x = MARGIN + pdf.get_string_width(before_label)
			self._draw_strikethrough(pdf, strike_x, price_zone_top, orig_str, 1.7)
			pdf.set_text_color(0, 0, 0)

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 2.8)
			pdf.set_font('Helvetica', 'B', 19)
			pdf.set_text_color(220, 38, 38)
			pdf.cell(W - MARGIN * 2, 8.5, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)

		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 1)
			pdf.set_font('Helvetica', 'B', 21)
			pdf.set_text_color(15, 23, 42)
			pdf.cell(W - MARGIN * 2, 9.5, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Separador ──────────────────────────────────────────
		sep_y = HEADER_H + BODY_H
		pdf.set_draw_color(210, 210, 210)
		pdf.set_line_width(0.25)
		pdf.line(MARGIN, sep_y, W - MARGIN, sep_y)
		pdf.set_draw_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		self._draw_barcode_footer(
			pdf, barcode_val, W, H, sep_y + 0.5, BC_H - 1, FOOT_H, MARGIN
		)

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

		# ── Borde sutil ────────────────────────────────────────
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.3)
		pdf.rect(0.2, 0.2, W - 0.4, H - 0.4)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_line_width(0.2)

		# ── Header ─────────────────────────────────────────────
		accent = (
			(220, 38, 38) if is_offer else (37, 99, 235) if mode_label else (15, 23, 42)
		)
		pdf.set_fill_color(*accent)
		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		if is_offer:
			offer_header = f'OFERTA HASTA {discount_until}' if discount_until else '* OFERTA *'
			pdf.set_font('Helvetica', 'B', 7.5)
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, _fit_text(pdf, offer_header, W - 6), align='C')
		else:
			brand_txt = (
				mode_label if mode_label else (company[:30] if company else 'CloudPOS')
			)
			if logo_path and os.path.exists(logo_path) and not mode_label:
				try:
					pdf.image(logo_path, x=MARGIN, y=1, h=HEADER_H - 2)
					pdf.set_xy(HEADER_H + 2, 0)
				except Exception as e:
					logger.warning('No se pudo cargar el logo en etiqueta producto: %s', e)
					pdf.set_xy(MARGIN, 0)
			else:
				pdf.set_xy(MARGIN, 0)
			pdf.set_font('Helvetica', 'B', 7)
			pdf.cell(W - MARGIN * 2, HEADER_H, _sanitize(brand_txt).upper(), align='L')

		pdf.set_text_color(0, 0, 0)

		# ── Identificación: dos líneas + atributo, con altura protegida ──
		pdf.set_font('Helvetica', 'B', 11 if is_offer else 12)
		lines = _wrap_label_text(pdf, name, W - MARGIN * 2, 2)
		y = HEADER_H + 1.8
		for line in lines:
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4.5, line, align='L')
			y += 4.5
		if attr:
			pdf.set_font('Helvetica', '', 6.5)
			pdf.set_text_color(100, 116, 139)
			pdf.set_xy(MARGIN, HEADER_H + 10.8)
			pdf.cell(W - MARGIN * 2, 3, _fit_text(pdf, attr, W - MARGIN * 2), align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Precio: ocupa siempre el bloque inferior sin tocar el título ──
		price_zone_top = HEADER_H + 15
		if is_offer:
			before_label = 'Antes: '
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top)
			pdf.set_font('Helvetica', '', 7)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(W - MARGIN * 2, 3, before_label + orig_str, align='L')
			strike_x = MARGIN + pdf.get_string_width(before_label)
			self._draw_strikethrough(pdf, strike_x, price_zone_top, orig_str, 1.8)
			pdf.set_text_color(0, 0, 0)

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 3)
			pdf.set_font('Helvetica', 'B', 23)
			pdf.set_text_color(220, 38, 38)
			pdf.cell(W - MARGIN * 2, 10, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)

		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_xy(MARGIN, price_zone_top + 2)
			pdf.set_font('Helvetica', 'B', 25)
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
		self._draw_barcode_footer(
			pdf, barcode_val, W, H, sep_y + 0.5, BC_H - 1, FOOT_H, MARGIN, font_size=4.5
		)

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
		pdf.set_font('Helvetica', 'B', 8.5)
		pdf.set_text_color(51, 65, 85)
		pdf.set_xy(MARGIN, y)
		pdf.cell(W - MARGIN * 2, 4.5, _fit_text(pdf, full_name, W - MARGIN * 2), align='L')
		y += 5.0

		# ── Precio ─────────────────────────────────────────────
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			full_text = f'Antes: {orig_str}'
			pdf.set_xy(MARGIN, y)
			pdf.set_font('Helvetica', '', 6)
			pdf.set_text_color(150, 150, 150)
			pdf.cell(W - MARGIN * 2, 3, full_text, align='C')
			full_w = pdf.get_string_width(full_text)
			prefix_w = pdf.get_string_width('Antes: ')
			cell_center = MARGIN + (W - MARGIN * 2) / 2
			strike_x = cell_center - full_w / 2 + prefix_w
			self._draw_strikethrough(pdf, strike_x, y, orig_str, 1.8)
			y += 3.5

		price_to_show = discount_price if is_offer else display_price
		price_str = _sanitize(_fmt_price(price_to_show, symbol, decimals))
		pdf.set_xy(0, y)
		pdf.set_font('Helvetica', 'B', 18)
		pdf.set_text_color(220, 38, 38 if is_offer else 15)
		if not is_offer:
			pdf.set_text_color(15, 23, 42)
		pdf.cell(W, 9, price_str, align='C')
		pdf.set_text_color(0, 0, 0)

		if is_offer and discount_until:
			pdf.set_xy(MARGIN, y + 9)
			pdf.set_font('Helvetica', 'I', 4.5)
			pdf.set_text_color(160, 50, 50)
			pdf.cell(W - MARGIN * 2, 3, f'Hasta: {discount_until}', align='C')
			pdf.set_text_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		sep_y = H - BC_H - FOOT_H
		self._draw_barcode_footer(
			pdf, barcode_val, W, H, sep_y, BC_H, FOOT_H, MARGIN, font_size=3.5
		)

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
		mode_label = item.get('_mode_label')
		is_offer = bool(discount_price and discount_price < display_price)

		HEADER_H = 4.0
		BC_H = 5.0
		FOOT_H = 2.8
		MARGIN = 1.5

		# ── Borde sutil ────────────────────────────────────────
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.3)
		pdf.rect(0.2, 0.2, W - 0.4, H - 0.4)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_line_width(0.2)

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
		pdf.set_font('Helvetica', 'B', 6)
		pdf.set_xy(0, 0.5)
		pdf.cell(W, HEADER_H - 1, header_txt.upper(), align='C')
		pdf.set_text_color(0, 0, 0)

		# ── Nombre: una sola línea siempre completa o con elipsis ──
		y = HEADER_H + 0.8
		display = f'{name} - {attr}'.strip(' -') if attr else name
		pdf.set_font('Helvetica', 'B', 6.5)
		pdf.set_xy(MARGIN, y)
		pdf.cell(W - MARGIN * 2, 2.8, _fit_text(pdf, display, W - MARGIN * 2), align='L')
		y = HEADER_H + 3.7

		# ── Precio ─────────────────────────────────────────────
		if is_offer:
			orig_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_font('Helvetica', '', 5)
			pdf.set_text_color(150, 150, 150)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 2, orig_str, align='L')
			self._draw_strikethrough(pdf, MARGIN, y, orig_str, 1.3)
			pdf.set_text_color(0, 0, 0)
			y += 2.3

			disc_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_font('Helvetica', 'B', 10.5)
			pdf.set_text_color(220, 38, 38)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4.2, disc_str, align='L')
			pdf.set_text_color(0, 0, 0)
		else:
			price_str = _sanitize(_fmt_price(display_price, symbol, decimals))
			pdf.set_font('Helvetica', 'B', 11)
			pdf.set_text_color(247, 127, 0)
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4.8, price_str, align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		sep_y = H - BC_H - FOOT_H
		self._draw_barcode_footer(
			pdf, barcode_val, W, H, sep_y, BC_H, FOOT_H, MARGIN, font_size=3.5
		)

	def _draw_dual(self, pdf, item, W, H, company, logo_path, symbol, decimals):
		"""70×50 mm — muestra ambos precios (minorista + mayorista)."""
		name = _sanitize(item.get('name', ''))
		attr = _sanitize(item.get('attribute', ''))
		barcode_val = item.get('barcode', '')

		try:
			base_price = float(item.get('price') or 0)
		except (ValueError, TypeError):
			base_price = 0.0

		price_b = item.get('selling_price_b')
		try:
			price_b_val = float(price_b) if price_b is not None else None
		except (ValueError, TypeError):
			price_b_val = None

		discount_price = item.get('_discount_price')
		discount_until = item.get('_discount_until', '')
		is_offer = bool(discount_price and discount_price < base_price)

		HEADER_H = 7.0
		BC_H = 10.0
		FOOT_H = 4.0
		MARGIN = 3.0

		# ── Borde sutil ────────────────────────────────────────
		pdf.set_draw_color(200, 200, 200)
		pdf.set_line_width(0.3)
		pdf.rect(0.2, 0.2, W - 0.4, H - 0.4)
		pdf.set_draw_color(0, 0, 0)
		pdf.set_line_width(0.2)

		# ── Header ─────────────────────────────────────────────
		accent = (220, 38, 38) if is_offer else (30, 41, 59)
		pdf.set_fill_color(*accent)
		pdf.rect(0, 0, W, HEADER_H, 'F')
		pdf.set_text_color(255, 255, 255)

		if is_offer:
			offer_header = f'OFERTA HASTA {discount_until}' if discount_until else '* OFERTA *'
			pdf.set_font('Helvetica', 'B', 7.5)
			pdf.set_xy(0, 0)
			pdf.cell(W, HEADER_H, _fit_text(pdf, offer_header, W - 6), align='C')
		else:
			brand_txt = company[:30] if company else 'CloudPOS'
			if logo_path and os.path.exists(logo_path):
				try:
					pdf.image(logo_path, x=MARGIN, y=1, h=HEADER_H - 2)
					pdf.set_xy(HEADER_H + 2, 0)
				except Exception as e:
					logger.warning('No se pudo cargar el logo en etiqueta dual: %s', e)
					pdf.set_xy(MARGIN, 0)
			else:
				pdf.set_xy(MARGIN, 0)
			pdf.set_font('Helvetica', 'B', 7)
			pdf.cell(W - MARGIN * 2, HEADER_H, _sanitize(brand_txt).upper(), align='L')

		pdf.set_text_color(0, 0, 0)

		# ── Identificación: bloque superior independiente de los precios ──
		pdf.set_font('Helvetica', 'B', 10)
		lines = _wrap_label_text(pdf, name, W - MARGIN * 2, 2)
		y = HEADER_H + 1.7
		for line in lines:
			pdf.set_xy(MARGIN, y)
			pdf.cell(W - MARGIN * 2, 4, line, align='L')
			y += 4
		if attr:
			pdf.set_font('Helvetica', '', 6.5)
			pdf.set_text_color(100, 116, 139)
			pdf.set_xy(MARGIN, HEADER_H + 9.8)
			pdf.cell(W - MARGIN * 2, 2.7, _fit_text(pdf, attr, W - MARGIN * 2), align='L')
			pdf.set_text_color(0, 0, 0)

		# ── Dos columnas con tarjetas independientes para cada lista ──
		price_zone_y = HEADER_H + 14
		gap = 2.0
		column_w = (W - MARGIN * 2 - gap) / 2
		left_x = MARGIN
		right_x = MARGIN + column_w + gap
		for x in (left_x, right_x):
			pdf.set_fill_color(248, 250, 252)
			pdf.set_draw_color(226, 232, 240)
			pdf.rect(x, price_zone_y, column_w, 10.5, 'DF')
		pdf.set_draw_color(0, 0, 0)

		# Minorista
		pdf.set_xy(left_x + 1, price_zone_y + 0.5)
		pdf.set_font('Helvetica', 'B', 5)
		pdf.set_text_color(100, 116, 139)
		pdf.cell(column_w - 2, 2, 'MINORISTA', align='L')
		if is_offer:
			orig_str = _sanitize(_fmt_price(base_price, symbol, decimals))
			pdf.set_xy(left_x + 1, price_zone_y + 2.4)
			pdf.set_font('Helvetica', '', 5)
			pdf.set_text_color(140, 140, 140)
			pdf.cell(column_w - 2, 2, f'Antes: {orig_str}', align='L')
			strike_x = left_x + 1 + pdf.get_string_width('Antes: ')
			self._draw_strikethrough(pdf, strike_x, price_zone_y + 2.4, orig_str, 1.3)
			price_y = price_zone_y + 4.3
			price_a_str = _sanitize(_fmt_price(discount_price, symbol, decimals))
			pdf.set_text_color(220, 38, 38)
		else:
			price_y = price_zone_y + 3.3
			price_a_str = _sanitize(_fmt_price(base_price, symbol, decimals))
			pdf.set_text_color(15, 23, 42)
		pdf.set_xy(left_x + 1, price_y)
		pdf.set_font('Helvetica', 'B', 11)
		pdf.cell(column_w - 2, 4.5, _fit_text(pdf, price_a_str, column_w - 2), align='L')

		# Mayorista
		pdf.set_xy(right_x + 1, price_zone_y + 0.5)
		pdf.set_font('Helvetica', 'B', 5)
		pdf.set_text_color(100, 116, 139)
		pdf.cell(column_w - 2, 2, 'MAYORISTA', align='L')
		price_b_str = _sanitize(_fmt_price(price_b_val, symbol, decimals)) if price_b_val is not None else 'No disponible'
		pdf.set_xy(right_x + 1, price_zone_y + 3.3)
		pdf.set_font('Helvetica', 'B', 10 if price_b_val is not None else 6)
		pdf.set_text_color(37, 99, 235 if price_b_val is not None else 140)
		pdf.cell(column_w - 2, 4.5, _fit_text(pdf, price_b_str, column_w - 2), align='L')
		pdf.set_text_color(0, 0, 0)

		# ── Barcode + footer ───────────────────────────────────
		sep_y = H - BC_H - FOOT_H
		self._draw_barcode_footer(
			pdf, barcode_val, W, H, sep_y, BC_H, FOOT_H, MARGIN, font_size=3.5
		)

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

	def _deliver_pdf(self, filepath: str, config: dict):
		"""Entrega el PDF por el driver configurado o lo abre para revisión.

		Las impresoras Zebra, Dymo y genéricas reciben un PDF mediante su driver;
		no se les envía ZPL arbitrario, que podría imprimir basura o cortar papel.
		"""
		printer = str(config.get('printer_label_name') or '').strip()
		mode = config.get('label_output_mode', 'preview')
		if mode == 'printer' and printer and not printer.startswith('('):
			try:
				if platform.system() != 'Windows':
					raise OSError('La impresión directa por driver está disponible en Windows.')
				import win32api  # type: ignore

				result = win32api.ShellExecute(
					0, 'printto', os.path.abspath(filepath), f'"{printer}"', '.', 0
				)
				if result <= 32:
					raise OSError(f'Windows devolvió el código {result}.')
				self.last_delivery_message = f'PDF enviado a «{printer}».'
				return
			except ImportError:
				self.last_delivery_message = (
					'PDF generado y abierto: instalá pywin32 para enviarlo al driver seleccionado.'
				)
			except Exception as error:
				logger.warning('No se pudo enviar el PDF a la impresora: %s', error)
				self.last_delivery_message = f'No se pudo enviar a «{printer}»: {error}. PDF abierto.'
			else:
				return
		else:
			self.last_delivery_message = 'PDF generado y abierto para revisar o imprimir.'
		self._open(filepath)
