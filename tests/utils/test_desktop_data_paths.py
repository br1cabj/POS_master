"""Moving desktop data must preserve WAL transactions, licences and backups."""

import sqlite3

import pytest
from sqlalchemy import text

from controllers.backup_controller import BackupController
from controllers.cloud_license_controller import CloudLicenseController
from controllers.license_controller import LicenseController
from database.migrations import run_migrations
from utils import app_paths, config


@pytest.fixture
def paths(tmp_path, monkeypatch):
	installation = tmp_path / 'Program Files' / 'CloudPOS'
	installation.mkdir(parents=True)
	data = tmp_path / 'User data' / 'CloudPOS'

	def data_dir(*, create=True):
		if create:
			data.mkdir(parents=True, exist_ok=True)
		return data

	monkeypatch.setattr(app_paths, 'installation_dir', lambda: installation)
	monkeypatch.setattr(app_paths, 'app_data_dir', data_dir)
	url = f'sqlite:///{data / "pos_system.db"}'
	monkeypatch.setattr(config, '_default_db', url)
	monkeypatch.setattr(config, 'DB_URL', url)
	return installation, data


def test_legacy_database_adoption_preserves_committed_wal_and_original(paths):
	installation, data = paths
	original = sqlite3.connect(installation / 'pos_system.db')
	try:
		original.execute('PRAGMA journal_mode=WAL')
		original.execute('PRAGMA wal_autocheckpoint=0')
		original.execute('CREATE TABLE preserved (value TEXT)')
		original.execute("INSERT INTO preserved VALUES ('sale in WAL')")
		original.commit()
		assert (installation / 'pos_system.db-wal').exists()
		assert config.prepare_local_database() == data / 'pos_system.db'
		with sqlite3.connect(data / 'pos_system.db') as copy:
			assert copy.execute('SELECT value FROM preserved').fetchall() == [
				('sale in WAL',)
			]
			copy.execute("INSERT INTO preserved VALUES ('new sale')")
		config.prepare_local_database()
		with sqlite3.connect(data / 'pos_system.db') as copy:
			assert copy.execute('SELECT COUNT(*) FROM preserved').fetchone()[0] == 2
		assert original.execute('SELECT COUNT(*) FROM preserved').fetchone()[0] == 1
	finally:
		original.close()


def test_legacy_licences_are_copied_and_current_licence_is_never_replaced(paths):
	installation, data = paths
	(installation / 'license.dat').write_bytes(b'existing licence')
	(installation / 'cloud_license.dat').write_bytes(b'existing cloud licence')
	assert LicenseController().license_file == str(data / 'license.dat')
	assert CloudLicenseController()._file == str(data / 'cloud_license.dat')
	assert (data / 'cloud_license.dat').read_bytes() == b'existing cloud licence'
	(data / 'license.dat').write_bytes(b'new licence')
	LicenseController()
	assert (data / 'license.dat').read_bytes() == b'new licence'
	assert (installation / 'license.dat').read_bytes() == b'existing licence'


def test_corrupt_legacy_database_cannot_publish_an_empty_destination(paths):
	installation, data = paths
	(installation / 'pos_system.db').write_bytes(b'not a SQLite database')
	with pytest.raises(sqlite3.DatabaseError):
		config.prepare_local_database()
	assert not (data / 'pos_system.db').exists()
	assert not list(data.glob('.pos_system.db-*'))
	assert (installation / 'pos_system.db').read_bytes() == b'not a SQLite database'


def test_explicit_database_location_is_respected_without_copying_legacy_data(
	paths, tmp_path, monkeypatch
):
	installation, data = paths
	(installation / 'pos_system.db').write_bytes(b'legacy')
	explicit = tmp_path / 'custom location' / 'business.db'
	monkeypatch.setattr(config, 'DB_URL', f'sqlite:///{explicit}')
	assert config.prepare_local_database() == explicit
	assert BackupController()._db_path() == explicit
	assert explicit.parent.is_dir()
	assert not explicit.exists()
	assert not (data / 'pos_system.db').exists()


def test_old_env_template_also_uses_the_writable_default(paths):
	assert config._resolve_database_url('sqlite:///pos_system.db') == config._default_db
	assert config._resolve_database_url('  ') == config._default_db


def test_backup_restore_uses_the_new_data_path_and_rejects_bad_schema(
	paths, tmp_path, monkeypatch
):
	_, data = paths
	config.prepare_local_database()
	engine = config.make_engine()
	try:
		run_migrations(engine)
		with engine.begin() as connection:
			connection.execute(
				text(
					"INSERT INTO tenants (id, name, updated_at) VALUES ('a', 'Original', CURRENT_TIMESTAMP)"
				)
			)
		backup_dir = tmp_path / 'backups'
		backup_dir.mkdir()
		monkeypatch.setattr(
			BackupController, 'backup_dir', staticmethod(lambda: backup_dir)
		)
		monkeypatch.setattr(
			'controllers.backup_controller._settings_set', lambda *args: None
		)
		controller = BackupController(engine)
		assert controller._db_path() == data / 'pos_system.db'
		assert controller.create_backup()[0]
		backup = controller.list_backups()[0]
		with engine.begin() as connection:
			connection.execute(text("UPDATE tenants SET name='Changed' WHERE id='a'"))
		assert controller.restore_backup(str(backup)) == (True, 'OK')
		with engine.connect() as connection:
			assert (
				connection.execute(text('SELECT name FROM tenants')).scalar()
				== 'Original'
			)
		assert controller.restore_backup(str(data / 'pos_system.db'))[0] is False
		with sqlite3.connect(backup) as connection:
			connection.execute('DROP INDEX uq_cash_open_session')
		ok, message = controller.restore_backup(str(backup))
		assert not ok
		assert 'uq_cash_open_session' in message
		with engine.connect() as connection:
			assert (
				connection.execute(text('SELECT name FROM tenants')).scalar()
				== 'Original'
			)
	finally:
		engine.dispose()
