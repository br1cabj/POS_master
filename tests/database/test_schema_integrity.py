"""Regression tests for database-level business and tenant integrity."""

import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Article, ArticleVariant, Branch, CashSession, Stock, Tenant, User, Warehouse


def _catalogue(session):
    session.add_all([
        Tenant(id='tenant-a', name='Empresa A'),
        Tenant(id='tenant-b', name='Empresa B'),
        Branch(id='branch-a', tenant_id='tenant-a', name='Central'),
        Warehouse(id='warehouse-a', tenant_id='tenant-a', branch_id='branch-a', name='Depósito'),
        Article(id='article-a', tenant_id='tenant-a', name='Producto A', min_stock=0),
        Article(id='article-b', tenant_id='tenant-b', name='Producto B', min_stock=0),
    ])
    session.commit()


def test_variant_cannot_reference_an_article_from_another_tenant(test_db_session):
    _catalogue(test_db_session)
    test_db_session.add(ArticleVariant(
        id='variant-invalid', tenant_id='tenant-a', article_id='article-b',
        cost_price=10, selling_price=15,
    ))

    with pytest.raises(IntegrityError):
        test_db_session.commit()


def test_barcode_is_unique_per_tenant_but_not_globally(test_db_session):
    _catalogue(test_db_session)
    test_db_session.add_all([
        ArticleVariant(
            id='variant-a', tenant_id='tenant-a', article_id='article-a', barcode='779123',
            cost_price=10, selling_price=15,
        ),
        ArticleVariant(
            id='variant-b', tenant_id='tenant-b', article_id='article-b', barcode='779123',
            cost_price=10, selling_price=15,
        ),
    ])
    test_db_session.commit()


def test_stock_has_one_unbatched_balance_per_variant_and_warehouse(test_db_session):
    _catalogue(test_db_session)
    test_db_session.add(ArticleVariant(
        id='variant-a', tenant_id='tenant-a', article_id='article-a', cost_price=10, selling_price=15,
    ))
    test_db_session.commit()
    test_db_session.add(Stock(
        id='stock-a', tenant_id='tenant-a', variant_id='variant-a', warehouse_id='warehouse-a',
        batch_number='', quantity=1,
    ))
    test_db_session.commit()
    test_db_session.add(Stock(
        id='stock-duplicate', tenant_id='tenant-a', variant_id='variant-a', warehouse_id='warehouse-a',
        batch_number='', quantity=2,
    ))

    with pytest.raises(IntegrityError):
        test_db_session.commit()


def test_user_cannot_have_two_open_cash_sessions(test_db_session):
    test_db_session.add_all([
        Tenant(id='tenant-a', name='Empresa A'),
        User(id='user-a', tenant_id='tenant-a', username='admin', password_hash='hash'),
    ])
    test_db_session.commit()
    test_db_session.add(CashSession(
        id='cash-a', tenant_id='tenant-a', user_id='user-a', is_open=True,
    ))
    test_db_session.commit()
    test_db_session.add(CashSession(
        id='cash-b', tenant_id='tenant-a', user_id='user-a', is_open=True,
    ))

    with pytest.raises(IntegrityError):
        test_db_session.commit()
