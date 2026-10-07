from datetime import date
from decimal import Decimal

from controllers.quotation_controller import QuotationController
from controllers.returns_controller import ReturnsController
from controllers.supplier_returns_controller import SupplierReturnsController
from database.models import (
	CashMovement,
	CashSession,
	Article,
	ArticleVariant,
	Branch,
	Purchase,
	PurchaseDetail,
	Quotation,
	QuotationItem,
	Sale,
	SaleDetail,
	Supplier,
	Stock,
	Tenant,
	User,
	Warehouse,
)


def _seed_user(session):
	tenant = Tenant(id='tenant-return-guard', name='Tenant de prueba')
	user = User(
		id='user-return-guard',
		tenant_id=tenant.id,
		username='guard',
		password_hash='not-used-in-test',
	)
	session.add_all([tenant, user])
	session.commit()
	return tenant, user


def test_partial_return_rejects_repeated_detail_id(test_db_session):
	tenant, user = _seed_user(test_db_session)
	sale = Sale(
		id='sale-return-guard',
		tenant_id=tenant.id,
		user_id=user.id,
		total_amount=Decimal('10'),
		profit=Decimal('5'),
		payment_method='efectivo',
		status='completada',
	)
	detail = SaleDetail(
		id='sale-detail-return-guard',
		tenant_id=tenant.id,
		sale_id=sale.id,
		description='Artículo',
		quantity=Decimal('1'),
		unit_cost=Decimal('5'),
		unit_price=Decimal('10'),
		subtotal=Decimal('10'),
	)
	test_db_session.add_all([
		sale,
		detail,
		CashSession(
			id='cash-return-guard', tenant_id=tenant.id, user_id=user.id,
			is_open=True, opening_balance=Decimal('0'),
		),
	])
	test_db_session.commit()

	ok, message = ReturnsController(test_db_session.bind).return_items(
		tenant.id,
		sale.id,
		user.id,
		[
			{'detail_id': detail.id, 'qty_to_return': '1'},
			{'detail_id': detail.id, 'qty_to_return': '1'},
		],
	)

	assert not ok
	assert 'máximo disponible' in message
	test_db_session.refresh(detail)
	assert detail.returned_quantity == Decimal('0')


def test_supplier_return_rejects_repeated_detail_id(test_db_session):
	tenant, user = _seed_user(test_db_session)
	supplier = Supplier(id='supplier-return-guard', tenant_id=tenant.id, name='Proveedor')
	purchase = Purchase(
		id='purchase-return-guard', tenant_id=tenant.id, user_id=user.id,
		supplier_id=supplier.id, total_amount=Decimal('10'), status='pagada',
	)
	detail = PurchaseDetail(
		id='purchase-detail-return-guard', tenant_id=tenant.id, purchase_id=purchase.id,
		description='Artículo', quantity=Decimal('1'),
		unit_cost=Decimal('10'), subtotal=Decimal('10'),
	)
	test_db_session.add_all([supplier, purchase, detail])
	test_db_session.commit()

	ok, message = SupplierReturnsController(test_db_session.bind).process_return(
		tenant.id,
		user.id,
		purchase.id,
		[
			{'detail_id': detail.id, 'qty_to_return': '1', 'unit_cost': '999'},
			{'detail_id': detail.id, 'qty_to_return': '1', 'unit_cost': '999'},
		],
		'Producto defectuoso',
		'credito',
	)

	assert not ok
	assert 'disponible para devolver' in message


def test_digital_refund_does_not_reduce_physical_cash(test_db_session):
	tenant, user = _seed_user(test_db_session)
	test_db_session.add(
		CashSession(
			id='cash-digital-refund', tenant_id=tenant.id, user_id=user.id,
			is_open=True, opening_balance=Decimal('0'),
		)
	)
	test_db_session.commit()

	ReturnsController(test_db_session.bind)._register_financial_reversal(
		test_db_session,
		tenant.id,
		user.id,
		Sale(payment_method='transferencia'),
		Decimal('10'),
		'Reintegro digital de prueba',
	)
	test_db_session.commit()

	movement = test_db_session.query(CashMovement).one()
	assert movement.movement_type == 'gasto_digital'


def test_quote_conversion_uses_fefo_batches_and_digital_cash_movement(test_db_session):
	tenant, user = _seed_user(test_db_session)
	branch = Branch(id='branch-quote-guard', tenant_id=tenant.id, name='Principal')
	warehouse = Warehouse(
		id='warehouse-quote-guard', tenant_id=tenant.id, branch_id=branch.id,
		name='Depósito',
	)
	article = Article(id='article-quote-guard', tenant_id=tenant.id, name='Artículo')
	variant = ArticleVariant(
		id='variant-quote-guard', tenant_id=tenant.id, article_id=article.id,
		cost_price=Decimal('4'), selling_price=Decimal('10'),
	)
	quotation = Quotation(
		id='quotation-guard', tenant_id=tenant.id, user_id=user.id,
		number='COT-0001', status='enviada', total_amount=Decimal('20'),
	)
	item = QuotationItem(
		id='quotation-item-guard', tenant_id=tenant.id, quotation_id=quotation.id,
		description='Artículo', quantity=Decimal('2'), unit_price=Decimal('10'),
		subtotal=Decimal('20'), variant_id=variant.id,
	)
	first_batch = Stock(
		id='stock-quote-first', tenant_id=tenant.id, variant_id=variant.id, warehouse_id=warehouse.id,
		batch_number='B-1', expiration_date=date(2026, 1, 1), quantity=Decimal('1'),
	)
	second_batch = Stock(
		id='stock-quote-second', tenant_id=tenant.id, variant_id=variant.id, warehouse_id=warehouse.id,
		batch_number='B-2', expiration_date=date(2026, 2, 1), quantity=Decimal('2'),
	)
	test_db_session.add_all([
		branch, warehouse, article, variant, quotation, item, first_batch, second_batch,
		CashSession(
			id='cash-quote-guard', tenant_id=tenant.id, user_id=user.id,
			is_open=True, opening_balance=Decimal('0'),
		),
	])
	test_db_session.commit()

	ok, sale_id = QuotationController(test_db_session.bind).convert_to_sale(
		quotation.id, user.id, 'transferencia', warehouse.id, tenant.id
	)

	assert ok, sale_id
	test_db_session.refresh(first_batch)
	test_db_session.refresh(second_batch)
	assert first_batch.quantity == Decimal('0')
	assert second_batch.quantity == Decimal('1')
	movement = test_db_session.query(CashMovement).one()
	assert movement.movement_type == 'venta_digital'
