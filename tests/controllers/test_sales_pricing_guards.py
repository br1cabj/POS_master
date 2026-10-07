from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from controllers.sales_controller import SalesController
from database.models import (
	Article,
	ArticleVariant,
	Branch,
	CashSession,
	Category,
	Promotion,
	Sale,
	Stock,
	Tenant,
	User,
	Warehouse,
)


def _sale_environment(session, role='cajero'):
	tenant = Tenant(id='tenant-sale', name='Negocio')
	session.add(tenant)
	session.flush()
	user = User(
		id='user-sale',
		tenant_id=tenant.id,
		username='cajero',
		password_hash='hash',
		role=role,
	)
	branch = Branch(id='branch-sale', tenant_id=tenant.id, name='Principal')
	warehouse = Warehouse(
		id='warehouse-sale', tenant_id=tenant.id, branch_id=branch.id, name='Depósito'
	)
	category = Category(id='category-sale', tenant_id=tenant.id, name='Bebidas')
	session.add_all([user, branch, category])
	session.flush()
	article = Article(
		id='article-sale', tenant_id=tenant.id, category_id=category.id, name='Gaseosa'
	)
	variant = ArticleVariant(
		id='variant-sale',
		tenant_id=tenant.id,
		article_id=article.id,
		cost_price=Decimal('40'),
		selling_price=Decimal('100'),
		selling_price_b=Decimal('80'),
	)
	stock = Stock(
		id='stock-sale',
		tenant_id=tenant.id,
		variant_id=variant.id,
		warehouse_id=warehouse.id,
		quantity=Decimal('20'),
	)
	cash = CashSession(
		id='cash-sale', tenant_id=tenant.id, user_id=user.id, opening_balance=Decimal('0')
	)
	session.add_all([warehouse, article])
	session.flush()
	session.add_all([variant, cash])
	session.flush()
	session.add(stock)
	session.commit()
	return tenant, user, category, variant


def test_sale_recalculates_category_promo_and_ignores_client_price(test_db_session):
	tenant, user, category, variant = _sale_environment(test_db_session)
	test_db_session.add(
		Promotion(
			tenant_id=tenant.id,
			name='Bebidas 10%',
			promo_type='pct',
			discount_value=Decimal('10'),
			category_id=category.id,
			date_from=datetime.now() - timedelta(days=1),
			date_to=datetime.now() + timedelta(days=1),
		)
	)
	test_db_session.commit()

	with patch('controllers.receipt_controller.ReceiptController.generate_pdf'):
		ok, message = SalesController(test_db_session.get_bind()).process_sale(
			tenant.id,
			user.id,
			[{'variant_id': variant.id, 'qty': '2', 'price': '1', 'desc': 'Manipulado'}],
			payment_method='efectivo',
			price_list='B',
		)

	assert ok, message
	sale = test_db_session.query(Sale).one()
	assert sale.total_amount == Decimal('144.00')  # Lista B (80) y promo de categoría (10%).
	assert sale.items[0].unit_price == Decimal('72.00')
	assert sale.items[0].description == '🎯 Bebidas 10%'


def test_cashier_cannot_apply_excessive_discount_or_free_sale(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	controller = SalesController(test_db_session.get_bind())

	ok, message = controller.process_sale(
		tenant.id,
		user.id,
		[{'variant_id': variant.id, 'qty': '1', 'price': '100'}],
		payment_method='efectivo',
		discount_pct=Decimal('21'),
	)
	assert not ok
	assert 'hasta 20%' in message

	ok, message = controller.process_sale(
		tenant.id,
		user.id,
		[{'variant_id': None, 'qty': '1', 'price': '100', 'desc': 'Servicio'}],
		payment_method='efectivo',
	)
	assert not ok
	assert 'administradora' in message


def test_sale_only_deducts_the_selected_warehouse(test_db_session):
	tenant, user, _category, variant = _sale_environment(test_db_session)
	primary = test_db_session.get(Warehouse, 'warehouse-sale')
	second = Warehouse(
		id='warehouse-sale-2', tenant_id=tenant.id, branch_id='branch-sale', name='Secundario'
	)
	test_db_session.add_all([
		second,
		Stock(
			id='stock-sale-2', tenant_id=tenant.id, variant_id=variant.id,
			warehouse_id=second.id, quantity=Decimal('100'),
		),
	])
	test_db_session.commit()

	ok, message = SalesController(test_db_session.get_bind()).process_sale(
		tenant.id,
		user.id,
		[{'variant_id': variant.id, 'qty': '21', 'price': '100'}],
		payment_method='efectivo',
		warehouse_id=primary.id,
	)

	assert not ok
	assert 'Stock insuficiente' in message
