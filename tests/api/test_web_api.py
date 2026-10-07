"""Regression coverage for the VPS-only web data boundary."""
import sys
import os
from pathlib import Path

import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

sys.path.insert(0, 'web-api')

from app.main import create_app  # noqa: E402
from database.models import Article, ArticleVariant, Customer, Tenant, User  # noqa: E402


def _seed(engine):
	with Session(engine) as session:
		tenant_a = Tenant(id='tenant-a', name='A')
		tenant_b = Tenant(id='tenant-b', name='B')
		user = User(
			id='user-a', tenant_id='tenant-a', username='admin', display_name='Admin A',
			role='admin', is_active=True,
			password_hash=bcrypt.hashpw(b'secret', bcrypt.gensalt()).decode('utf-8'),
		)
		session.add_all([
			tenant_a, tenant_b, user,
			Customer(id='customer-a', tenant_id='tenant-a', name='Cliente A', is_active=True),
			Customer(id='customer-b', tenant_id='tenant-b', name='Cliente B', is_active=True),
			Article(id='article-a', tenant_id='tenant-a', name='Producto A', min_stock=1),
		])
		session.add(ArticleVariant(
			id='variant-a', article_id='article-a', barcode='779000', cost_price=10,
			selling_price=15, is_active=True,
		))
		session.commit()


def test_web_api_authenticates_and_never_crosses_tenant_boundary():
	# Avoid pytest's shared Windows temp directory, which can be locked by the
	# desktop application or antivirus.  This file is removed after the test.
	database_path = Path('.web-api-test.db').resolve()
	database_path.unlink(missing_ok=True)
	app = create_app(f'sqlite:///{database_path}')
	try:
		with TestClient(app) as client:
			_seed(app.state.engine)
			login = client.post('/api/v1/auth/login', json={
			'username': 'admin', 'password': 'secret', 'tenant_id': 'tenant-a',
			})
			assert login.status_code == 200
			token = login.json()['session_token']
			headers = {'Authorization': f'Bearer {token}'}

			response = client.post('/api/v1/data/customers', json={
			'select': 'id,name,tenant_id', 'order': {'column': 'name', 'ascending': True},
			}, headers=headers)
			assert response.status_code == 200
			assert response.json() == [{'id': 'customer-a', 'name': 'Cliente A', 'tenant_id': 'tenant-a'}]

			# The nested data shape used by the dashboard is served by the API, not PostgREST.
			variants = client.post('/api/v1/data/article_variants', json={
				'select': 'barcode,article:articles(name,min_stock)',
			}, headers=headers)
			assert variants.status_code == 200
			assert variants.json() == [{'barcode': '779000', 'article': {'name': 'Producto A', 'min_stock': 1}}]

			# Password hashes cannot be selected even by an authenticated administrator.
			secret = client.post('/api/v1/data/users', json={'select': 'username,password_hash'}, headers=headers)
			assert secret.status_code == 400

			client.post('/api/v1/auth/logout', headers=headers)
			assert client.get('/api/v1/auth/session', headers=headers).status_code == 401
	finally:
		database_path.unlink(missing_ok=True)


def test_sync_requires_a_provisioned_device_and_filters_sensitive_fields():
	database_path = Path('.web-api-sync-test.db').resolve()
	database_path.unlink(missing_ok=True)
	os.environ['CLOUDPOS_ADMIN_API_KEY'] = 'test-admin-key'
	app = create_app(f'sqlite:///{database_path}')
	try:
		with TestClient(app) as client:
			_seed(app.state.engine)
			provision = client.post('/api/v1/admin/devices', json={
				'tenant_id': 'tenant-a', 'name': 'Caja principal', 'cloud_username': 'owner', 'cloud_password': 'cloud-password-123',
			}, headers={'X-CloudPOS-Admin-Key': 'test-admin-key'})
			assert provision.status_code == 200
			token = provision.json()['device_token']
			denied = client.post('/api/v1/sync/events', json={'events': [{
				'event_id': 'one', 'table': 'customers', 'payload': {'id': 'new', 'tenant_id': 'tenant-a', 'name': 'Nuevo'},
			}]})
			assert denied.status_code == 401
			accepted = client.post('/api/v1/sync/events', json={'events': [{
				'event_id': 'two', 'table': 'customers', 'payload': {'id': 'new', 'tenant_id': 'tenant-a', 'name': 'Nuevo'},
			}]}, headers={'Authorization': f'Bearer {token}'})
			assert accepted.status_code == 200
			secret = client.post('/api/v1/sync/events', json={'events': [{
				'event_id': 'three', 'table': 'customers', 'payload': {'id': 'bad', 'tenant_id': 'tenant-a', 'name': 'No', 'password_hash': 'never'},
			}]}, headers={'Authorization': f'Bearer {token}'})
			assert secret.status_code == 400
	finally:
		os.environ.pop('CLOUDPOS_ADMIN_API_KEY', None)
		database_path.unlink(missing_ok=True)
