from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import os
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask

import admin
import academic_engine


class FakeResult:
    def __init__(self, row, description=()):
        self.row = row
        self.description = description

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
        if "SELECT * FROM posts LIMIT 0" in statement:
            return FakeResult(None)
        return FakeResult(None)

    def executemany(self, statement, parameters):
        self.statements.append((statement, parameters))


class DatabaseInitializationTests(unittest.TestCase):
    def test_calculator_url_aliases_return_public_pages(self):
        import app as app_module

        client = app_module.app.test_client()
        for path in (
            "/gpa",
            "/gpa-calculator",
            "/cgpa",
            "/cgpa-calculator",
            "/grade_predictor",
            "/grade-predictor",
        ):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn(b"<html", response.data.lower(), path)

    def test_public_requests_increment_page_view_totals(self):
        import app as app_module

        with TemporaryDirectory() as directory:
            app_module.app.config["TESTING"] = True
            app_module.app.instance_path = directory
            app_module.app.config["DATABASE_URL"] = ""
            app_module.app.config["ADMIN_DATABASE"] = os.path.join(
                directory,
                "cgpa_hub.sqlite3",
            )
            app_module.app.config["UPLOAD_FOLDER"] = os.path.join(
                directory,
                "uploads",
            )
            app_module.app.config["SECRET_KEY"] = "page-view-test-secret"
            admin.initialize_database(app_module.app)

            client = app_module.app.test_client()
            responses = [
                client.get("/").status_code,
                client.get("/").status_code,
                client.get("/gpa-calculator").status_code,
            ]

            with app_module.app.app_context():
                database = admin.get_db()
                rows = {
                    row["path"]: row["views"]
                    for row in database.execute(
                        "SELECT path, views FROM daily_pageviews"
                    ).fetchall()
                }

        self.assertEqual(responses, [200, 200, 200])
        self.assertEqual(rows["/"], 2)
        self.assertEqual(rows["/gpa-calculator"], 1)

    def test_four_point_academic_record(self):
        result = academic_engine.calculate_academic_record(
            [
                {
                    "code": "CSC101",
                    "unit": 3,
                    "grade": "A",
                    "session": "2025/2026",
                    "semester": "1",
                },
                {
                    "code": "MTH101",
                    "unit": 2,
                    "grade": "C",
                    "session": "2025/2026",
                    "semester": "1",
                },
            ],
            university="4",
        )
        self.assertEqual(result["total_units"], 5)
        self.assertEqual(result["total_points"], 16)
        self.assertEqual(result["cgpa"], 3.2)

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
        expected_seed_count = len(admin.SEED_POSTS) + len(admin.STARTER_POSTS)
        self.assertEqual(len(seed_statements), expected_seed_count)
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

        self.assertEqual(
            post_count,
            len(admin.SEED_POSTS) + len(admin.STARTER_POSTS),
        )
        self.assertEqual(content_count, len(admin.DEFAULT_CONTENT))

    def test_existing_database_gets_resource_posts_and_video_column(self):
        with TemporaryDirectory() as directory:
            database_path = os.path.join(directory, "cgpa_hub.sqlite3")
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE posts (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    body TEXT NOT NULL,
                    image TEXT NOT NULL,
                    image_alt TEXT NOT NULL,
                    read_time INTEGER NOT NULL,
                    is_featured INTEGER NOT NULL DEFAULT 0,
                    is_published INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO posts (
                    title, slug, category, excerpt, body, image, image_alt, read_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Existing article",
                    "existing-article",
                    "gpa",
                    "Existing description",
                    "Existing content",
                    "Images/books1.png",
                    "Books",
                    3,
                ),
            )
            connection.commit()
            connection.close()

            app = Flask("existing-database-test", instance_path=directory)
            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "SECRET_KEY": "test"},
            ):
                admin.initialize_database(app)

            connection = sqlite3.connect(database_path)
            try:
                post_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(posts)")
                }
                titles = {
                    row[0] for row in connection.execute("SELECT title FROM posts")
                }
                video_url = connection.execute(
                    "SELECT video_url FROM posts WHERE slug = 'existing-article'"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertIn("video_url", post_columns)
        self.assertEqual(video_url, "")
        self.assertIn("Existing article", titles)
        self.assertTrue(
            {post["title"] for post in admin.STARTER_POSTS}.issubset(titles)
        )

    def test_youtube_links_are_restricted_to_valid_video_urls(self):
        video_id = "abcDEF123_-"
        self.assertEqual(
            admin.normalize_youtube_url(
                f"https://www.youtube.com/watch?v={video_id}"
            ),
            f"https://www.youtube-nocookie.com/embed/{video_id}",
        )
        self.assertEqual(
            admin.normalize_youtube_url(f"https://youtu.be/{video_id}"),
            f"https://www.youtube-nocookie.com/embed/{video_id}",
        )
        self.assertEqual(admin.normalize_youtube_url(""), "")
        self.assertIsNone(
            admin.normalize_youtube_url("https://example.com/watch?v=abcDEF123_-")
        )
        self.assertIsNone(
            admin.normalize_youtube_url("javascript:alert(1)")
        )
        self.assertIsNone(
            admin.normalize_youtube_url("https://youtube.com/watch?v=short")
        )

    def test_login_remember_me_controls_persistent_session(self):
        project_root = Path(admin.__file__).resolve().parent
        with TemporaryDirectory() as directory:
            app = Flask(
                "remember-me-test",
                template_folder=str(project_root / "templates"),
                static_folder=str(project_root / "static"),
                instance_path=directory,
            )
            app.config["TESTING"] = True
            app.register_blueprint(admin.admin_bp)
            app.add_url_rule("/", endpoint="home", view_func=lambda: "")
            app.teardown_appcontext(admin.close_db)
            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "SECRET_KEY": "remember-me-test-secret"},
            ):
                admin.initialize_database(app)
                with app.app_context():
                    database = admin.get_db()
                    database.execute(
                        "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                        (
                            "remember-test",
                            admin.generate_password_hash("test-password"),
                        ),
                    )
                    database.commit()

                remembered_client = app.test_client()
                login_page = remembered_client.get("/admin/login")
                self.assertIn(b"Remember me for 30 days", login_page.data)
                with remembered_client.session_transaction() as session:
                    csrf_token = session["_admin_csrf"]
                response = remembered_client.post(
                    "/admin/login",
                    data={
                        "csrf_token": csrf_token,
                        "username": "remember-test",
                        "password": "test-password",
                        "remember_me": "1",
                    },
                )
                self.assertEqual(response.status_code, 302)
                with remembered_client.session_transaction() as session:
                    self.assertTrue(session.permanent)

                regular_client = app.test_client()
                regular_client.get("/admin/login")
                with regular_client.session_transaction() as session:
                    csrf_token = session["_admin_csrf"]
                response = regular_client.post(
                    "/admin/login",
                    data={
                        "csrf_token": csrf_token,
                        "username": "remember-test",
                        "password": "test-password",
                    },
                )
                self.assertEqual(response.status_code, 302)
                with regular_client.session_transaction() as session:
                    self.assertFalse(session.permanent)

    def test_website_settings_save_bible_verse_and_visibility(self):
        project_root = Path(admin.__file__).resolve().parent
        with TemporaryDirectory() as directory:
            app = Flask(
                "website-settings-test",
                template_folder=str(project_root / "templates"),
                static_folder=str(project_root / "static"),
                instance_path=directory,
            )
            app.config["TESTING"] = True
            app.register_blueprint(admin.admin_bp)
            app.add_url_rule("/", endpoint="home", view_func=lambda: "")
            app.teardown_appcontext(admin.close_db)
            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "SECRET_KEY": "settings-test-secret"},
            ):
                admin.initialize_database(app)
                client = app.test_client()
                with client.session_transaction() as session:
                    session["admin_id"] = 1
                    session["admin_username"] = "settings-test"
                    session["_admin_csrf"] = "test-csrf-token"

                page = client.get("/admin/settings")
                self.assertIn(
                    admin.DEFAULT_CONTENT["footer_bible_verse"].encode(),
                    page.data,
                )
                self.assertIn(
                    admin.DEFAULT_CONTENT["footer_bible_reference"].encode(),
                    page.data,
                )
                self.assertIn(b'name="footer_bible_verse_visible"', page.data)

                response = client.post(
                    "/admin/settings",
                    data={
                        "csrf_token": "test-csrf-token",
                        "site_name": "CGPA Hub",
                        "site_tagline": "Calculate . Track . Excel",
                        "footer_bible_verse": "Be strong and of a good courage.",
                        "footer_bible_reference": "Joshua 1:9 (KJV)",
                        "footer_bible_verse_visible": "1",
                    },
                    follow_redirects=True,
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Website settings updated.", response.data)

                with app.app_context():
                    content = admin.get_content()
                self.assertEqual(
                    content["footer_bible_verse"],
                    "Be strong and of a good courage.",
                )
                self.assertEqual(
                    content["footer_bible_reference"],
                    "Joshua 1:9 (KJV)",
                )
                self.assertEqual(content["footer_bible_verse_visible"], "1")
                rendered_verse = app.jinja_env.get_template(
                    "footer_verse.html"
                ).render(
                    footer_bible_verse=content["footer_bible_verse"],
                    footer_bible_reference=content["footer_bible_reference"],
                    show_footer_bible_verse=(
                        content["footer_bible_verse_visible"] == "1"
                    ),
                )
                self.assertIn("Be strong and of a good courage.", rendered_verse)
                self.assertIn("Joshua 1:9 (KJV)", rendered_verse)

                hidden_response = client.post(
                    "/admin/settings",
                    data={
                        "csrf_token": "test-csrf-token",
                        "site_name": "CGPA Hub",
                        "site_tagline": "Calculate . Track . Excel",
                        "footer_bible_verse": "Be strong and of a good courage.",
                        "footer_bible_reference": "Joshua 1:9 (KJV)",
                    },
                    follow_redirects=True,
                )
                self.assertEqual(hidden_response.status_code, 200)
                with app.app_context():
                    content = admin.get_content()
                self.assertEqual(content["footer_bible_verse_visible"], "0")
                rendered_verse = app.jinja_env.get_template(
                    "footer_verse.html"
                ).render(
                    footer_bible_verse=content["footer_bible_verse"],
                    footer_bible_reference=content["footer_bible_reference"],
                    show_footer_bible_verse=(
                        content["footer_bible_verse_visible"] == "1"
                    ),
                )
                self.assertNotIn("Be strong and of a good courage.", rendered_verse)


if __name__ == "__main__":
    unittest.main()
