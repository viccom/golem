import logging
from typing import Optional, Type, Sequence

import peewee
from os import path

from playhouse.shortcuts import RetryOperationalError

from golem.database.migration import default_migrate_dir
from golem.database.migration.migrate import migrate_schema, MigrationError

logger = logging.getLogger('golem.db')


class GolemSqliteDatabase(RetryOperationalError, peewee.SqliteDatabase):

    def sequence_exists(self, seq):
        raise NotImplementedError()


class Database:

    SCHEMA_VERSION = 13

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 db: peewee.Database,
                 fields: Sequence[Type[peewee.Field]],
                 models: Sequence[Type[peewee.Model]],
                 db_dir: str,
                 db_name: str = 'golem.db',
                 schemas_dir: Optional[str] = default_migrate_dir()) -> None:

        self.fields = fields
        self.models = models
        self.schemas_dir = schemas_dir

        self.db = db
        self.db.init(path.join(db_dir, db_name))
        self.db.connect()

        version = self.get_user_version()

        if not version:
            self._create_tables()
        elif schemas_dir and version < self.SCHEMA_VERSION:
            self._migrate_schema(version, to_version=self.SCHEMA_VERSION)

    def close(self):
        if not self.db.is_closed():
            self.db.close()

    def get_user_version(self) -> int:
        cursor = self.db.execute_sql('PRAGMA user_version').fetchone()
        return int(cursor[0])

    def set_user_version(self, version: int) -> None:
        self.db.execute_sql('PRAGMA user_version = {}'.format(version))

    def _drop_tables(self):
        logger.info("Removing tables")
        self.db.drop_tables(self.models, safe=True)

    def _create_tables(self) -> None:
        logger.info("Creating tables, schema version %r", self.SCHEMA_VERSION)

        self.db.create_tables(self.models, safe=True)
        self.set_user_version(self.SCHEMA_VERSION)

    def _migrate_schema(self, version, to_version) -> None:
        logger.info("Migrating database schema from version %r to %r",
                    version, to_version)

        try:
            if not self.schemas_dir:
                raise MigrationError("Invalid schema directory")

            migrate_schema(self, version, to_version,
                           migrate_dir=self.schemas_dir)
        except MigrationError as exc:
            logger.warning("Cannot migrate database schema: %s", exc)
            self._drop_tables()
            self._create_tables()
