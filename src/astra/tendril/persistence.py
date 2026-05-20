from __future__ import annotations

from .repository import TendrilDatabase, TendrilRepository
from .schema import TendrilSchema
from .settings import TendrilSettings


class TendrilPersistence:
    def __init__(self, settings: TendrilSettings) -> None:
        self.settings = settings
        self.database = TendrilDatabase(settings.persistence_db_path)
        self.tendril = TendrilRepository(self.database)
        self._initialized = False

    def bootstrap(self) -> None:
        if self._initialized:
            return
        self.settings.data_root.mkdir(parents=True, exist_ok=True)
        with self.database.connect() as conn:
            TendrilSchema(conn).initialize()
        self._initialized = True
