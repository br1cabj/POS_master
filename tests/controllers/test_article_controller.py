from decimal import Decimal

from controllers.article_controller import ArticleController
from database.models import ArticleHistory, ArticleVariant, Category, Tenant, User


def _catalog_environment(session):
	tenant = Tenant(id='tenant-articles', name='Almacén')
	session.add(tenant)
	session.commit()
	user = User(
		id='user-articles',
		tenant_id=tenant.id,
		username='admin',
		password_hash='hash',
		role='admin',
	)
	category = Category(id='category-articles', tenant_id=tenant.id, name='Bebidas')
	session.add_all([user, category])
	session.commit()
	return tenant, user, category


def _create_base(controller, tenant, user, category):
	ok, message = controller.add_simple_article(
		tenant.id,
		user.id,
		'Gaseosa',
		'INT-ARTICLE-001',
		Decimal('100'),
		Decimal('150'),
		Decimal('24'),
		category_id=category.id,
		margin_pct=Decimal('50'),
	)
	assert ok, message
	return controller.get_all_variants(tenant.id, include_packaging=False)[0]


def test_base_cost_update_recalculates_packs_and_audits_every_price_change(test_db_session):
	tenant, user, category = _catalog_environment(test_db_session)
	controller = ArticleController(test_db_session.get_bind())
	base = _create_base(controller, tenant, user, category)

	ok, message = controller.add_packaging_variant(
		tenant.id, base['variant_id'], 'Caja x6', 6, Decimal('1000'), 'INT-ARTICLE-006'
	)
	assert ok, message

	ok, message = controller.update_article(
		tenant.id,
		user.id,
		base['variant_id'],
		'Gaseosa',
		'INT-ARTICLE-001',
		Decimal('120'),
		Decimal('180'),
		category_id=category.id,
		margin_pct=Decimal('50'),
	)
	assert ok, message
	test_db_session.expire_all()
	packs = controller.get_packaging_variants(tenant.id, base['variant_id'])
	assert packs[0]['selling_price'] == 1000.0
	assert test_db_session.query(ArticleHistory).count() == 2
	assert controller.delete_variant(tenant.id, base['variant_id'])[0] is False


def test_bulk_base_cost_keeps_pack_cost_derived_and_records_history(test_db_session):
	tenant, user, category = _catalog_environment(test_db_session)
	controller = ArticleController(test_db_session.get_bind())
	base = _create_base(controller, tenant, user, category)
	ok, message = controller.add_packaging_variant(
		tenant.id, base['variant_id'], 'Caja x12', 12, Decimal('2200'), 'INT-ARTICLE-012'
	)
	assert ok, message

	ok, message = controller.bulk_update_variants(
		tenant.id, user.id, [base['variant_id']], {'cost_price': Decimal('125')}
	)
	assert ok, message
	test_db_session.expire_all()
	pack = controller.get_packaging_variants(tenant.id, base['variant_id'])[0]
	pack_variant = test_db_session.get(ArticleVariant, pack['variant_id'])
	assert pack_variant.cost_price == Decimal('1500')
	assert test_db_session.query(ArticleHistory).count() == 2


def test_catalog_main_list_excludes_packaging_and_inactive_parent(test_db_session):
	tenant, user, category = _catalog_environment(test_db_session)
	controller = ArticleController(test_db_session.get_bind())
	base = _create_base(controller, tenant, user, category)
	assert controller.add_packaging_variant(
		tenant.id, base['variant_id'], 'Caja x6', 6, Decimal('1000'), 'INT-ARTICLE-LIST'
	)[0]

	assert len(controller.get_all_variants(tenant.id, include_packaging=False)) == 1
	all_variants = controller.get_all_variants(tenant.id, include_packaging=True)
	assert len(all_variants) == 2
	assert next(v for v in all_variants if v['pack_label'])['total_stock'] == Decimal('4')
	assert controller.bulk_update_variants(
		tenant.id, user.id, [base['variant_id']], {'is_active': False}
	)[0] is False
