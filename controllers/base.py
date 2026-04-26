from __future__ import annotations
import logging
from sqlalchemy.orm import sessionmaker


class BaseController:
    """Base class for all controllers.

    Centralises session factory creation and logger setup so subclasses
    don't repeat boilerplate in every __init__.
    """

    def __init__(self, db_engine):
        self._engine = db_engine
        self._Session = sessionmaker(bind=db_engine)
        self.logger = logging.getLogger(self.__class__.__name__)
