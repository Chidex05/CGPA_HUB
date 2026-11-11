import os
import re
import sqlite3

class DatabaseError(Exception):
    """Raised when a configured database operation fails."""


class Database:
    def __init__(self, connection, is_postgres, error_types):
        self.connection = connection
        self.is_postgres = is_postgres
        self.error_types = error_types

    def execute(self, query, parameters=()):
        if self.is_postgres:
            query = re.sub(r"\?", "%s", query)
        try:
            return self.connection.execute(query, parameters)
        except self.error_types as error:
            raise DatabaseError("The database query failed.") from error

    def executemany(self, query, parameters):
        if self.is_postgres:
            query = re.sub(r"\?", "%s", query)
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, parameters)
            return cursor
        except self.error_types as error:
            raise DatabaseError("The database query failed.") from error

    def commit(self):
        try:
            self.connection.commit()
        except self.error_types as error:
            raise DatabaseError("The database transaction failed.") from error

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        try:
            if exc_info[0] is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def postgres_row_factory(cursor):
    column_indexes = {
        column.name: index
        for index, column in enumerate(cursor.description or ())
    }

    class HybridRow(tuple):
        def __getitem__(self, key):
            if isinstance(key, str):
                key = column_indexes[key]
            return super().__getitem__(key)

    return HybridRow


def connect_database(database_url=None, database_path=None):
    database_url = (database_url or os.environ.get("DATABASE_URL") or "").strip()
    if database_url:
        try:
            import psycopg

            connection = psycopg.connect(
                database_url,
                row_factory=postgres_row_factory,
                prepare_threshold=None,
            )
        except ImportError as error:
            raise RuntimeError(
                "Install psycopg to use the configured PostgreSQL DATABASE_URL."
            ) from error
        except psycopg.Error as error:
            raise DatabaseError("Could not connect to the configured PostgreSQL database.") from error
        return Database(connection, True, (psycopg.Error,))

    if not database_path:
        raise RuntimeError("A local database path is required when DATABASE_URL is unset.")
    try:
        connection = sqlite3.connect(database_path)
    except sqlite3.Error as error:
        raise DatabaseError("Could not connect to the local SQLite database.") from error
    connection.row_factory = sqlite3.Row
    return Database(connection, False, (sqlite3.Error,))
