from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from sqlalchemy.engine import Engine

	from utils.settings_manager import SettingsManager
	from utils.sync_worker import SyncWorker


@dataclass
class AppContext:
	"""Holds shared application state for the lifetime of a user session."""

	db_engine: 'Engine'
	current_user: dict
	settings: 'SettingsManager'
	sync_worker: 'Optional[SyncWorker]' = field(default=None)

	@property
	def tenant_id(self) -> str:
		if isinstance(self.current_user, dict):
			return self.current_user.get('tenant_id', '')
		return self.current_user.tenant_id

	@property
	def user_id(self) -> str:
		if isinstance(self.current_user, dict):
			return self.current_user.get('id', '')
		return self.current_user.id

	@property
	def username(self) -> str:
		if isinstance(self.current_user, dict):
			return self.current_user.get('username', 'Usuario')
		return getattr(self.current_user, 'username', 'Usuario')

	@property
	def role(self) -> str:
		if isinstance(self.current_user, dict):
			return self.current_user.get('role', 'user')
		return getattr(self.current_user, 'role', 'user')

	@property
	def is_admin(self) -> bool:
		return str(self.role).strip().lower() in ('admin', 'gerente')
