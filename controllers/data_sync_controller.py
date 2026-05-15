"""
controllers/data_sync_controller.py
===================================
Controlador para la sincronizacion masiva de datos mediante archivos Excel.
Incluye deteccion automatica de columnas por alias, preview pre-importacion
y reporte detallado de resultado (creados / actualizados / saltados).
"""

import logging
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from controllers.base import BaseController
from database.models import (
	Article,
	ArticleHistory,
	ArticleVariant,
	Branch,
	Customer,
	Stock,
	StockMovement,
	Warehouse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de alias de columnas: acepta variantes comunes de nombres de columna.
# Clave = nombre canonico interno; Valor = lista de variantes aceptadas.
# ---------------------------------------------------------------------------
_COLUMN_ALIASES = {
	'Nombre': [
		'nombre',
		'name',
		'articulo',
		'producto',
		'descripcion',
		'item',
		'mercaderia',
		'detalle',
	],
	'Codigo_Barras': [
		'codigo_barras',
		'codigobarras',
		'barcode',
		'codigo',
		'cod',
		'sku',
		'ean',
		'ean13',
		'cod_barras',
		'codigo de barras',
		'id_producto',
		'referencia',
		'ref',
	],
	'Costo': [
		'costo',
		'cost',
		'precio_costo',
		'costo_unitario',
		'precio de costo',
		'p_costo',
		'pcosto',
	],
	'Precio_Venta': [
		'precio_venta',
		'precio',
		'price',
		'venta',
		'selling_price',
		'precio de venta',
		'pvp',
		'p_venta',
		'pventa',
	],
	'Stock': [
		'stock',
		'cantidad',
		'quantity',
		'existencias',
		'inventario',
		'cant',
		'qty',
	],
	'Precio_Lista_B': [
		'precio_lista_b',
		'precio_mayorista',
		'precio_b',
		'lista_b',
		'selling_price_b',
		'precio b',
		'p_lista_b',
	],
	'Proveedor': [
		'proveedor',
		'supplier',
		'vendor',
		'marca',
		'fabricante',
	],
}

# Especificacion publica de columnas (la vista la usa para mostrar el Mapa de Referencia)
COLUMN_SPEC = [
	{
		'canonical': 'Nombre',
		'required': True,
		'type': 'Texto',
		'example': 'Cerveza Quilmes 1L',
		'description': 'Nombre del producto',
	},
	{
		'canonical': 'Codigo_Barras',
		'required': True,
		'type': 'Texto / Numero',
		'example': '7790895000084',
		'description': 'Codigo de barras o SKU unico',
	},
	{
		'canonical': 'Costo',
		'required': True,
		'type': 'Numero',
		'example': '420.50',
		'description': 'Precio de costo sin simbolo ($)',
	},
	{
		'canonical': 'Precio_Venta',
		'required': True,
		'type': 'Numero',
		'example': '650.00',
		'description': 'Precio de venta al publico',
	},
	{
		'canonical': 'Precio_Lista_B',
		'required': False,
		'type': 'Numero',
		'example': '550.00',
		'description': 'Precio de venta Lista B (mayorista). Dejar vacío si no aplica.',
	},
	{
		'canonical': 'Stock',
		'required': False,
		'type': 'Numero',
		'example': '48',
		'description': 'Stock inicial (solo articulos nuevos)',
	},
	{
		'canonical': 'Proveedor',
		'required': False,
		'type': 'Texto',
		'example': 'Quilmes S.A.',
		'description': 'Nombre del proveedor (opcional)',
	},
]


def _clean_col(s):
	"""Normaliza un nombre de columna: minusculas, sin tildes, guion bajo por espacio."""
	s = str(s).strip().lower()
	s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
	return s.replace(' ', '_')


def _normalize_df_columns(df):
	"""
	Renombra las columnas del DataFrame a sus nombres canonicos via _COLUMN_ALIASES.
	Retorna (df_renombrado, rename_map) donde rename_map es {original: canonical}.
	Si dos columnas del CSV mapean al mismo nombre canónico, la primera gana y se
	registra un warning para la segunda para facilitar depuración.
	"""
	rename_map = {}
	used_canonicals: dict[str, str] = {}  # canonical -> columna original que lo reclamó

	for col in df.columns:
		col_clean = _clean_col(col)
		matched_canonical = None

		for canonical, aliases in _COLUMN_ALIASES.items():
			if col_clean == _clean_col(canonical) or col_clean in [
				_clean_col(a) for a in aliases
			]:
				matched_canonical = canonical
				break

		if matched_canonical is None:
			continue  # columna desconocida, se ignora

		if matched_canonical in used_canonicals:
			logger.warning(
				'Columna "%s" ignorada: el canónico "%s" ya fue mapeado desde la columna "%s".',
				col, matched_canonical, used_canonicals[matched_canonical],
			)
		else:
			rename_map[col] = matched_canonical
			used_canonicals[matched_canonical] = col

	return df.rename(columns=rename_map), rename_map


class DataSyncController(BaseController):
	"""
	Controlador encargado de la exportacion e importacion de entidades del sistema.
	Aplica reglas de negocio durante la carga masiva (Upsert y Cascada de precios).
	"""

	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def _get_default_warehouse(self, session, tenant_id):
		"""Resuelve el deposito predeterminado para asignar stock inicial."""
		branch = (
			session.query(Branch)
			.filter_by(tenant_id=tenant_id, name='Sede Principal')
			.first()
		)
		if not branch:
			return None
		warehouse = (
			session.query(Warehouse)
			.filter_by(branch_id=branch.id, name='Depósito General')
			.first()
		)
		return warehouse.id if warehouse else None

	# ------------------------------------------------------------------
	# PREVIEW: lectura rapida para mostrar estado de columnas antes de importar
	# ------------------------------------------------------------------
	def preview_import_file(self, file_path):
		"""
		Lee el encabezado y las primeras filas del Excel. Retorna:
		  - column_status: lista de dicts {canonical, required, found, original_col}
		  - rows: primeras 3 filas como lista de dicts (columnas canonicas)
		  - error: string si hay error critico, None si OK
		"""
		try:
			df = pd.read_excel(file_path, engine='openpyxl', nrows=5)
		except Exception as e:
			return [], [], f'No se pudo leer el archivo: {e}'

		df_norm, rename_map = _normalize_df_columns(df)
		original_by_canonical = {v: k for k, v in rename_map.items()}

		column_status = []
		for spec in COLUMN_SPEC:
			canonical = spec['canonical']
			found = canonical in df_norm.columns
			column_status.append(
				{
					'canonical': canonical,
					'required': spec['required'],
					'found': found,
					'original_col': original_by_canonical.get(canonical),
				}
			)

		preview_cols = ['Nombre', 'Codigo_Barras', 'Costo', 'Precio_Venta', 'Stock']
		rows = []
		for _, row in df_norm.head(3).iterrows():
			rows.append(
				{
					col: str(row[col]) if col in df_norm.columns else '-'
					for col in preview_cols
				}
			)

		return column_status, rows, None

	# ------------------------------------------------------------------
	# EXPORT
	# ------------------------------------------------------------------
	def export_template(self, tenant_id, entity_type, save_path):
		"""
		Genera un archivo Excel con los datos actuales de la entidad solicitada.
		Si no hay registros, genera una fila de ejemplo como plantilla.
		"""
		try:
			with self._Session() as session:
				if entity_type == 'Articulos':
					variants = (
						session.query(ArticleVariant)
						.options(
							joinedload(ArticleVariant.stocks),
							joinedload(ArticleVariant.article).joinedload(Article.supplier),
						)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.is_active,
							ArticleVariant.base_variant_id.is_(None),
						)
						.all()
					)
					data = [
						{
							'Nombre': v.article.name,
							'Codigo_Barras': v.barcode or '',
							'Costo': float(v.cost_price),
							'Precio_Venta': float(v.selling_price),
							'Precio_Lista_B': float(v.selling_price_b) if v.selling_price_b else '',
							'Stock': float(
								sum(s.quantity for s in v.stocks) if v.stocks else 0
							),
							'Proveedor': v.article.supplier.name
							if v.article.supplier
							else '',
						}
						for v in variants
					] or [
						{
							'Nombre': 'Cerveza Quilmes 1L',
							'Codigo_Barras': '7790895000084',
							'Costo': 420.0,
							'Precio_Venta': 650.0,
							'Precio_Lista_B': '',
							'Stock': 48,
							'Proveedor': 'Quilmes S.A.',
						}
					]

					pd.DataFrame(data).to_excel(
						save_path, index=False, engine='openpyxl'
					)
					return True, 'Plantilla de Articulos exportada con exito.'

				if entity_type == 'Clientes':
					customers = (
						session.query(Customer)
						.filter_by(tenant_id=tenant_id, is_active=True)
						.all()
					)
					data = [
						{
							'Nombre': c.name,
							'Telefono': c.phone or '',
							'Deuda_Actual': float(c.current_balance),
						}
						for c in customers
					] or [
						{
							'Nombre': 'Juan Perez',
							'Telefono': '1122334455',
							'Deuda_Actual': 0.0,
						}
					]

					pd.DataFrame(data).to_excel(
						save_path, index=False, engine='openpyxl'
					)
					return True, 'Plantilla de Clientes exportada con exito.'

				return False, 'Tipo de entidad no soportada para exportacion.'
		except Exception as e:
			logger.error('Error exportando Excel: %s', e, exc_info=True)
			return False, f'Error al exportar: {e}'

	# ------------------------------------------------------------------
	# IMPORT ARTICLES
	# ------------------------------------------------------------------
	def import_articles_from_excel(self, tenant_id, user_id, file_path):
		"""
		Procesa la importacion de articulos aplicando logica Upsert:
		- Codigo de barras existente: actualiza nombre y precios (preserva stock).
		- Codigo de barras nuevo: crea el articulo con su stock inicial.
		- Cascada de costos: si es variante base, actualiza el costo de sus presentaciones.
		- Columnas detectadas automaticamente via alias (_COLUMN_ALIASES).
		Retorna (success, mensaje_resumen).
		"""
		try:
			df = pd.read_excel(file_path, engine='openpyxl')

			# Normalizar columnas antes de validar
			df, _ = _normalize_df_columns(df)

			required_columns = ['Nombre', 'Codigo_Barras', 'Costo', 'Precio_Venta']
			missing = [c for c in required_columns if c not in df.columns]
			if missing:
				return (
					False,
					f'Columnas obligatorias no encontradas: {", ".join(missing)}.\n'
					'Revisa el Mapa de Referencia para ver los nombres y alias aceptados.',
				)

			df = df.fillna('')
			created = updated = skipped = 0
			skip_reasons = []

			with self._Session() as session:
				warehouse_id = self._get_default_warehouse(session, tenant_id)

				# Pre-normalizar barcodes y pre-cargar variantes existentes (evita N+1)
				_pre_barcodes = []
				for _raw in df['Codigo_Barras'].dropna():
					_s = str(_raw).strip()
					try:
						_d = Decimal(_s)
						if _d == _d.to_integral_value():
							_s = str(int(_d))
					except InvalidOperation:
						pass
					if _s and _s != 'nan':
						_pre_barcodes.append(_s)
				existing_by_barcode: dict = {}
				if _pre_barcodes:
					existing_by_barcode = {
						v.barcode: v
						for v in (
							session.query(ArticleVariant)
							.options(joinedload(ArticleVariant.article))
							.join(Article)
							.filter(
								Article.tenant_id == tenant_id,
								ArticleVariant.barcode.in_(_pre_barcodes),
								ArticleVariant.is_active == True,  # noqa: E712
							)
							.all()
						)
					}

				created_barcodes: set = set()
				for row in df.itertuples():
					row_num = row.Index + 2  # +2 por encabezado y base-0
					name = str(row.Nombre).strip()
					# Normalizar codigos de barras: pandas convierte enteros a float (ej: "7790000000001.0")
					raw_bc = str(row.Codigo_Barras).strip()
					try:
						bc_dec = Decimal(raw_bc)
						# Si es un entero exacto (sin parte fraccionaria real), formatear sin decimales
						if bc_dec == bc_dec.to_integral_value():
							raw_bc = str(int(bc_dec))
					except InvalidOperation:
						pass  # No es numérico: conservar como string (ej: "ABC-001")
					barcode = raw_bc

					if not name or not barcode or barcode in ('', 'nan'):
						skipped += 1
						skip_reasons.append(f'Fila {row_num}: nombre o barcode vacio.')
						continue

					try:
						cost = Decimal(str(row.Costo).replace(',', '.'))
						price = Decimal(str(row.Precio_Venta).replace(',', '.'))
						stock_raw = str(getattr(row, 'Stock', '')).replace(',', '.').strip()
						stock_val = (
							Decimal(stock_raw)
							if stock_raw and stock_raw not in ('', 'nan')
							else Decimal('0')
						)
						price_b_raw = str(getattr(row, 'Precio_Lista_B', '')).replace(',', '.').strip()
						price_b = (
							Decimal(price_b_raw)
							if price_b_raw and price_b_raw not in ('', 'nan')
							else None
						)
						if price_b is not None and price_b <= 0:
							price_b = None
					except (InvalidOperation, TypeError, ValueError):
						skipped += 1
						skip_reasons.append(
							f'Fila {row_num}: valores numericos invalidos.'
						)
						continue

					if cost < 0 or price < 0 or stock_val < 0:
						skipped += 1
						skip_reasons.append(
							f'Fila {row_num}: valores negativos no permitidos.'
						)
						continue

					if cost > 0 and price < cost:
						skip_reasons.append(
							f'Fila {row_num} ({name}): advertencia - precio de venta '
							f'(${price}) menor al costo (${cost}), se importa de todas formas.'
						)

					existing = existing_by_barcode.get(barcode)

					if not existing and barcode in created_barcodes:
						skipped += 1
						skip_reasons.append(
							f'Fila {row_num} ({name}): barcode duplicado dentro del archivo.'
						)
						continue

					if existing:
						old_cost = existing.cost_price
						old_price = existing.selling_price

						session.add(
							ArticleHistory(
								tenant_id=tenant_id,
								user_id=user_id,
								action_type='IMPORTACION EXCEL',
								article_name=name,
								variant_id=existing.id,
								old_cost=old_cost,
								new_cost=cost,
								old_price=old_price,
								new_price=price,
							)
						)

						existing.cost_price = cost
						existing.selling_price = price
						existing.article.name = name
						if price_b is not None:
							existing.selling_price_b = price_b

						# Cascada de costos hacia presentaciones hijas
						if old_cost != cost and existing.base_variant_id is None:
							child_variants = (
								session.query(ArticleVariant)
								.filter(
									ArticleVariant.base_variant_id == existing.id,
									ArticleVariant.is_active == True,  # noqa: E712
								)
								.all()
							)
							for child in child_variants:
								child.cost_price = cost * (child.units_per_pack or 1)

						updated += 1

					else:
						article = Article(
							name=name,
							tenant_id=tenant_id,
							has_variants=False,
						)
						session.add(article)
						session.flush()

						variant = ArticleVariant(
							barcode=barcode,
							cost_price=cost,
							selling_price=price,
							selling_price_b=price_b,
							article_id=article.id,
						)
						session.add(variant)
						session.flush()
						created_barcodes.add(barcode)

						if warehouse_id and stock_val > 0:
							session.add(
								Stock(
									quantity=stock_val,
									warehouse_id=warehouse_id,
									variant_id=variant.id,
								)
							)
							session.add(
								StockMovement(
									movement_type='in',
									quantity=stock_val,
									reference='Importacion Excel',
									dest_warehouse_id=warehouse_id,
									variant_id=variant.id,
									user_id=user_id,
								)
							)
						elif stock_val > 0:
							skip_reasons.append(
								f'Fila {row_num} ({name}): artículo creado sin stock inicial '
								'(depósito predeterminado no encontrado).'
							)
						created += 1

				session.commit()

			# Construir mensaje resumen
			parts = []
			if created:
				parts.append(
					f'{created} articulo{"s" if created != 1 else ""} creado{"s" if created != 1 else ""}'
				)
			if updated:
				parts.append(f'{updated} actualizado{"s" if updated != 1 else ""}')
			if skipped:
				parts.append(f'{skipped} saltado{"s" if skipped != 1 else ""}')

			summary = 'Importacion completada: ' + ', '.join(parts) + '.'
			if skip_reasons:
				detail = '\n'.join(skip_reasons[:5])
				if len(skip_reasons) > 5:
					detail += f'\n...y {len(skip_reasons) - 5} mas.'
				summary += f'\n\nFilas con problemas:\n{detail}'

			return True, summary

		except Exception as e:
			logger.error('Error importando Excel: %s', e, exc_info=True)
			return False, f'Error al importar: {e}'

	def import_customers_from_excel(self, tenant_id, file_path):
		"""Importacion masiva de clientes desde Excel."""
		try:
			df = pd.read_excel(file_path, engine='openpyxl')
			df, _ = _normalize_df_columns(df)

			if 'Nombre' not in df.columns:
				return (
					False,
					"La columna 'Nombre' es obligatoria para importar clientes.",
				)

			df = df.fillna('')
			created = updated = skipped = 0

			with self._Session() as session:
				# Pre-cargar todos los clientes que coincidan con los nombres del archivo
				# en una sola query, evitando N+1.
				names_in_file = [
					str(r.Nombre).strip()
					for r in df.itertuples()
					if str(r.Nombre).strip() and str(r.Nombre).strip() != 'nan'
				]
				existing_map: dict = {
					c.name: c
					for c in session.query(Customer)
					.filter(
						Customer.tenant_id == tenant_id,
						Customer.name.in_(names_in_file),
						Customer.is_active == True,  # noqa: E712
					)
					.all()
				}

				for row in df.itertuples():
					name = str(row.Nombre).strip()
					if not name or name == 'nan':
						skipped += 1
						continue

					phone = str(getattr(row, 'Telefono', '')).strip()
					if phone in ('nan', ''):
						phone = None

					existing = existing_map.get(name)
					if existing:
						if phone:
							existing.phone = phone
						updated += 1
					else:
						new_customer = Customer(
							tenant_id=tenant_id,
							name=name,
							phone=phone,
							current_balance=Decimal('0'),
						)
						session.add(new_customer)
						existing_map[name] = new_customer  # evita duplicados dentro del mismo archivo
						created += 1

				session.commit()

			return (
				True,
				f'Clientes: {created} creados, {updated} actualizados, {skipped} saltados.',
			)
		except Exception as e:
			logger.error('Error importando clientes: %s', e, exc_info=True)
			return False, f'Error al importar clientes: {e}'
