from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import os
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask

import admin


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class RecordingPostgresDatabase:
    is_postgres = True

    def __init__(self):
        self.statements = []

    def execute(self, statement, parameters=()):
        self.statements.append((statement, parameters))
        if "SELECT COUNT(*) AS count FROM posts" in statement:
            return FakeResult({"count": 0})
        return FakeResult(None)

    def executemany(self, statement, parameters):
        self.statements.append((statement, parameters))


class DatabaseInitializationTests(unittest.TestCase):
    def test_postgres_initialization_locks_before_schema_and_seeding(self):
        database = RecordingPostgresDatabase()
        app = Flask("postgres-initialization-test")

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://example/database", "SECRET_KEY": "test"},
        ), patch.object(
            admin,
            "connect_database",
            return_value=nullcontext(database),
        ):
            admin.initialize_database(app)

        self.assertIn("pg_advisory_xact_lock", database.statements[0][0])
        self.assertEqual(
            database.statements[0][1],
            (admin.POSTGRES_INIT_LOCK_KEY,),
        )
        seed_statements = [
            call[0]
            for call in database.statements
            if "INSERT INTO posts" in call[0]
        ]
        self.assertEqual(len(seed_statements), len(admin.SEED_POSTS))
        self.assertTrue(
            all("ON CONFLICT (slug) DO NOTHING" in statement for statement in seed_statements)
        )

    def test_concurrent_local_initialization_keeps_one_seed_set(self):
        with TemporaryDirectory() as directory:
            def initialize(_):
                app = Flask("sqlite-initialization-test", instance_path=directory)
                admin.initialize_database(app)

            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "SECRET_KEY": "test"},
            ):
                with ThreadPoolExecutor(max_workers=8) as executor:
                    list(executor.map(initialize, range(16)))

            connection = sqlite3.connect(os.path.join(directory, "cgpa_hub.sqlite3"))
            try:
                post_count = connection.execute(
                    "SELECT COUNT(*) FROM posts"
                ).fetchone()[0]
                content_count = connection.execute(
                    "SELECT COUNT(*) FROM site_content"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(post_count, len(admin.SEED_POSTS))
        self.assertEqual(content_count, len(admin.DEFAULT_CONTENT))


if __name__ == "__main__":
    unittest.main()
