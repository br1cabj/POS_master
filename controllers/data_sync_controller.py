import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy.orm import sessionmaker

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
from utils.config import make_engine

_default_engine = make_engine()

logger = logging.getLogger(__name__)


class DataSyncController:
	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else _default_engine
		self.SessionLocal = sessionmaker(bind=engine)

	def _get_default_warehouse(self, session, tenant_id):
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

	def export_template(self, tenant_id, entity_type, save_path):
		"""Exporta artículos o clientes a Excel. Incluye fila de ejemplo si no hay datos."""
		try:
			with self.SessionLocal() as session:
				if entity_type == 'Artículos':
					variants = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.is_active,
						)
						.all()
					)
					data = [
						{
							'Nombre': v.article.name,
							'Codigo_Barras': v.barcode or '',
							'Costo': float(v.cost_price),
							'Precio_Venta': float(v.selling_price),
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
							'Nombre': 'Ejemplo Coca Cola',
							'Codigo_Barras': '779123456',
							'Costo': 500.0,
							'Precio_Venta': 800.0,
							'Stock': 24,
							'Proveedor': '',
						}
					]

					pd.DataFrame(data).to_excel(
						save_path, index=False, engine='openpyxl'
					)
					return True, f'Plantilla de Artículos exportada en:\n{save_path}'

				if entity_type == 'Clientes':
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
					return True, f'Plantilla de Clientes exportada en:\n{save_path}'

				return False, 'Tipo de entidad no soportada para exportar.'
		except Exception as e:
			logger.error(f'Error exportando Excel: {e}', exc_info=True)
			return False, f'Error al exportar: {e}'

	def import_articles_from_excel(self, tenant_id, user_id, file_path):
		"""
		Importa artículos con lógica upsert: actualiza precios si el barcode existe,
		crea el producto completo si no. Registra cambios de precio en ArticleHistory.
		Omite filas con datos faltantes, valores negativos o formatos inválidos.
		"""
		try:
			df = pd.read_excel(file_path, engine='openpyxl')

			for col in ['Nombre', 'Codigo_Barras', 'Costo', 'Precio_Venta']:
				if col not in df.columns:
					return False, f"El Excel no tiene la columna obligatoria: '{col}'."

			df = df.fillna('')
			created = updated = 0

			with self.SessionLocal() as session:
				warehouse_id = self._get_default_warehouse(session, tenant_id)

				for _, row in df.iterrows():
					name = str(row['Nombre']).strip()
					barcode = str(row['Codigo_Barras']).strip().replace('.0', '')

					if not name or not barcode:
						continue

					try:
						cost = Decimal(str(row['Costo']))
						price = Decimal(str(row['Precio_Venta']))
						stock_val = (
							Decimal(str(row.get('Stock', 0)))
							if row.get('Stock')
							else Decimal('0.0')
						)
					except (InvalidOperation, TypeError):
						continue

					if cost < 0 or price < 0 or stock_val < 0:
						continue

					existing = (
						session.query(ArticleVariant)
						.join(Article)
						.filter(
							Article.tenant_id == tenant_id,
							ArticleVariant.barcode == barcode,
						)
						.first()
					)

					if existing:
						session.add(
							ArticleHistory(
								tenant_id=tenant_id,
								user_id=user_id,
								action_type='IMPORTACIÓN EXCEL',
								article_name=name,
								variant_id=existing.id,
								old_cost=existing.cost_price,
								new_cost=cost,
								old_price=existing.selling_price,
								new_price=price,
							)
						)
						existing.cost_price = cost
						existing.selling_price = price
						existing.article.name = name
						updated += 1
					else:
						if warehouse_id is None:
							logger.warning(
								f'Sin depósito para tenant {tenant_id}. Producto "{name}" omitido.'
							)
							continue

						article = Article(
							name=name, tenant_id=tenant_id, has_variants=False
						)
						session.add(article)
						session.flush()

						variant = ArticleVariant(
							barcode=barcode,
							cost_price=cost,
							selling_price=price,
							article_id=article.id,
						)
						session.add(variant)
						session.flush()

						session.add(
							Stock(
								quantity=stock_val,
								warehouse_id=warehouse_id,
								variant_id=variant.id,
							)
						)

						if stock_val > 0:
							session.add(
								StockMovement(
									movement_type='in',
									quantity=stock_val,
									reference='Importación Excel',
									dest_warehouse_id=warehouse_id,
									variant_id=variant.id,
									user_id=user_id,
								)
							)
						created += 1

				session.commit()
				return (
					True,
					f'Importación exitosa.\n- Productos Creados: {created}\n- Precios Actualizados: {updated}',
				)

		except Exception as e:
			logger.error(f'Error importando Excel: {e}', exc_info=True)
			return (
				False,
				f'El archivo está corrupto o tiene un formato inválido.\nDetalle: {e}',
			)
