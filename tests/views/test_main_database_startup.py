"""Startup must not retain failed engines or send existing data to the setup wizard."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from main import PosApp


def test_failed_schema_validation_is_rechecked_on_retry():
	app = SimpleNamespace(db_engine=None)
	engine = Mock()
	with (
		patch('main.get_engine', return_value=engine),
		patch(
			'main.run_migrations', side_effect=[RuntimeError('bad schema'), None]
		) as migrate,
		patch('utils.sync_worker.SyncWorker') as worker,
	):
		with pytest.raises(RuntimeError, match='bad schema'):
			PosApp._get_or_create_engine(app)
		assert app.db_engine is None
		engine.dispose.assert_called_once()
		worker.assert_not_called()
		assert PosApp._get_or_create_engine(app) is engine
		assert migrate.call_count == 2
		worker.return_value.start.assert_called_once()


@pytest.mark.parametrize('schema_error', [False, True])
def test_startup_checks_the_configured_database_and_existing_licence(
	tmp_path, schema_error
):
	database = tmp_path / 'user data.db'
	licence = tmp_path / 'license.dat'
	database.touch()
	licence.touch()
	app = SimpleNamespace(
		_clear_window=Mock(),
		license_ctrl=SimpleNamespace(
			license_file=str(licence),
			check_license_status=Mock(return_value=(True, 'OK')),
		),
		_get_or_create_engine=Mock(
			side_effect=RuntimeError('bad schema') if schema_error else None
		),
		show_wizard=Mock(),
		show_login=Mock(),
		show_license_lock=Mock(),
		_show_database_error=Mock(),
	)
	with (
		patch('main.settings_get', return_value='primary'),
		patch('main.prepare_local_database', return_value=database),
	):
		PosApp.check_system_state(app)
	app.show_wizard.assert_not_called()
	if schema_error:
		app._show_database_error.assert_called_once_with('bad schema')
		app.show_login.assert_not_called()
	else:
		app.show_login.assert_called_once()
