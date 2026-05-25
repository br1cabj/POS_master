from __future__ import annotations

import logging

from sqlalchemy.orm import sessionmaker

from utils.config import get_engine


class BaseController:
	"""Base class for all controllers."""

	def __init__(self, db_engine=None):
		engine = db_engine if db_engine is not None else get_engine()
		self._engine = engine
		self._Session = sessionmaker(bind=engine)
		self.logger = logging.getLogger(self.__class__.__name__)
