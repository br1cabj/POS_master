import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy.orm import sessionmaker

from database.models import (
	Article,
	ArticleVariant,
	Branch,
	Customer,
	Stock,
	StockMovement,
	Warehouse,
)

logger = logging.getLogger(__name__)


class DataSyncController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def _get_default_warehouse(self, session, tenant_id):
		branch = (
			session.query(Branch)
			.filter_by(tenant_id=tenant_id, name='Sede Principal')
			.first()
		)
		warehouse = (
			session.query(Warehouse)
			.filter_by(branch_id=branch.id, name='Depósito General')
			.first()
		)
		return warehouse.id if warehouse else None

	# ==========================================
	# EXPORTACIÓN / PLANTILLAS
	# ==========================================
	def export_template(self, tenant_id, entity_type, save_path):
		"""Genera un Excel con los datos actuales o una plantilla vacía"""
		try:
			with self.Session() as session:
				if entity_type == 'Artículos':
					data = []
					variants = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.is_active,
						)
						.all()
					)

					for v in variants:
						stock_qty = sum(s.quantity for s in v.stocks) if v.stocks else 0
						data.append(
							{
								'Nombre': v.article.name,
								'Codigo_Barras': v.barcode or '',
								'Costo': float(v.cost_price),
								'Precio_Venta': float(v.selling_price),
								'Stock': float(stock_qty),
								'Proveedor': v.article.supplier.name
								if v.article.supplier
								else '',
							}
						)

					# Si no hay datos, creamos una fila de ejemplo
					if not data:
						data.append(
							{
								'Nombre': 'Ejemplo Coca Cola',
								'Codigo_Barras': '779123456',
								'Costo': 500.0,
								'Precio_Venta': 800.0,
								'Stock': 24,
								'Proveedor': '',
							}
						)

					df = pd.DataFrame(data)
					df.to_excel(save_path, index=False, engine='openpyxl')
					return True, f'Plantilla de Artículos exportada en:\n{save_path}'

				elif entity_type == 'Clientes':
					customers = (
						session.query(Customer)
						.filter_by(tenant_id=tenant_id, is_active=True)
						.all()
					)
					data = [
						{
							'Nombre': c.name,
							'Telefono': c.phone,
							'Deuda_Actual': float(c.current_balance),
						}
						for c in customers
					]
					if not data:
						data.append(
							{
								'Nombre': 'Juan Perez',
								'Telefono': '1122334455',
								'Deuda_Actual': 0.0,
							}
						)

					pd.DataFrame(data).to_excel(
						save_path, index=False, engine='openpyxl'
					)
					return True, f'Plantilla de Clientes exportada en:\n{save_path}'

				return False, 'Tipo de entidad no soportada para exportar.'

		except Exception as e:
			logger.error(f'Error exportando Excel: {e}', exc_info=True)
			return False, f'Error al exportar: {e}'

	# ==========================================
	# IMPORTACIÓN (MOTOR UPSERT)
	# ==========================================
	def import_articles_from_excel(self, tenant_id, user_id, file_path):
		"""Lee el Excel. Si el código existe, actualiza precios. Si no, lo crea."""
		try:
			df = pd.read_excel(file_path, engine='openpyxl')

			# Validar columnas obligatorias
			required_columns = ['Nombre', 'Codigo_Barras', 'Costo', 'Precio_Venta']
			for col in required_columns:
				if col not in df.columns:
					return False, f"El Excel no tiene la columna obligatoria: '{col}'."

			df = df.fillna('')  # Rellenar nulos

			created_count = 0
			updated_count = 0

			with self.Session() as session:
				warehouse_id = self._get_default_warehouse(session, tenant_id)

				for index, row in df.iterrows():
					name = str(row['Nombre']).strip()
					barcode = (
						str(row['Codigo_Barras']).strip().replace('.0', '')
					)  # Limpieza de números de excel

					if not name or not barcode:
						continue  # Saltamos filas vacías

					try:
						cost = Decimal(str(row['Costo']))
						price = Decimal(str(row['Precio_Venta']))
						stock_val = (
							Decimal(str(row.get('Stock', 0)))
							if row.get('Stock')
							else Decimal('0.0')
						)
					except (InvalidOperation, TypeError):
						continue  # Saltamos si los precios no son números

					# Buscar si ya existe por código de barras
					existing_variant = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == barcode,
						)
						.first()
					)

					if existing_variant:
						# ACTUALIZAMOS PRECIOS (No tocamos el stock aquí por seguridad contable)
						existing_variant.cost_price = cost
						existing_variant.selling_price = price
						existing_variant.article.name = name
						updated_count += 1
					else:
						# CREAMOS PRODUCTO NUEVO
						new_article = Article(
							name=name, tenant_id=tenant_id, has_variants=False
						)
						session.add(new_article)
						session.flush()

						new_variant = ArticleVariant(
							barcode=barcode,
							cost_price=cost,
							selling_price=price,
							article_id=new_article.id,
						)
						session.add(new_variant)
						session.flush()

						new_stock = Stock(
							quantity=stock_val,
							warehouse_id=warehouse_id,
							variant_id=new_variant.id,
						)
						session.add(new_stock)

						if stock_val > 0:
							mov = StockMovement(
								movement_type='in',
								quantity=stock_val,
								reference='Importación Excel',
								dest_warehouse_id=warehouse_id,
								variant_id=new_variant.id,
								user_id=user_id,
							)
							session.add(mov)

						created_count += 1

				session.commit()
				return (
					True,
					f'Importación exitosa.\n- Productos Creados: {created_count}\n- Precios Actualizados: {updated_count}',
				)

		except Exception as e:
			logger.error(f'Error importando Excel: {e}', exc_info=True)
			return (
				False,
				f'El archivo está corrupto o tiene un formato inválido.\nDetalle: {e}',
			)
