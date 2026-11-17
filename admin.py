import hashlib
import hmac
import os
import re
import secrets
import unicodedata
import uuid
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from io import BytesIO

import click
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError

from database import connect_database


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
POSTGRES_INIT_LOCK_KEY = 0x43475041485542

DEFAULT_CONTENT = {
    "site_name": "CGPA Hub",
    "site_tagline": "Calculate . Track . Excel",
    "home_heading": "Your Academic Success Starts Here",
    "home_description": (
        "The all-in-one platform for students to calculate GPA, track CGPA, "
        "and access helpful academic resources."
    ),
    "blog_intro": (
        "Understand your grades, solve common CGPA questions, and find practical "
        "ways to plan your next semester."
    ),
    "announcement": "",
    "footer_text": "Your academic success, our priority.",
    "footer_bible_verse": (
        "Commit thy works unto the LORD, and thy thoughts shall be established."
    ),
    "footer_bible_reference": "Proverbs 16:3 (KJV)",
    "footer_bible_verse_visible": "1",
}

POST_CATEGORY_OPTIONS = (
    ("academic", "Academic Guides"),
    ("problem-solving", "CGPA Problem Solving"),
    ("student-corner", "Student Corner"),
    ("study", "Study & Productivity"),
    ("updates", "CGPA Hub Updates"),
)
CATEGORY_LABELS = dict(POST_CATEGORY_OPTIONS)
LEGACY_CATEGORY_IDS = {"gpa": "academic", "grading": "academic"}


def category_filter_id(category):
    return LEGACY_CATEGORY_IDS.get(category, category)


def category_label(category):
    return CATEGORY_LABELS.get(category_filter_id(category), "Academic Guides")


def normalize_youtube_url(value):
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return None
        if parsed.port not in (None, 443):
            return None
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) == 2 and path_parts[0] in {"embed", "shorts", "live"}:
                video_id = path_parts[1]

    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


SEED_POSTS = [
    {
        "title": "How to calculate your GPA",
        "category": "gpa",
        "excerpt": "Learn how grades and course units come together in a simple semester GPA calculation.",
        "image": "522099927e2af7a76ab1ca67a52b3ccd.jpg",
        "alt": "Study materials for working out a GPA",
        "read_time": 4,
        "body": (
            "Your Grade Point Average (GPA) is a weighted average of your course "
            "grades for one semester. Each course contributes according to its "
            "credit units, so a higher-unit course has more influence on the result.\n\n"
            "For each course, multiply its grade point by its credit units. Add "
            "those quality points together, then divide by the total number of "
            "credit units. The result is your semester GPA.\n\n"
            "For example, if your courses add up to 60 quality points over 15 "
            "credit units, your GPA is 60 ÷ 15 = 4.00. Always confirm the grade "
            "point scale and repeat-course rules used by your institution."
        ),
    },
    {
        "title": "Understanding your CGPA",
        "category": "gpa",
        "excerpt": "What CGPA means, how it differs from GPA, and why it matters for your academic journey.",
        "image": "5e613082b1f41a852a07ad23017508af.jpg",
        "alt": "Books arranged for a university study session",
        "read_time": 4,
        "body": (
            "Your Cumulative Grade Point Average (CGPA) combines your academic "
            "results across semesters. GPA describes one semester; CGPA gives "
            "you a broader view of your performance over time.\n\n"
            "To calculate it, add the quality points from all completed courses "
            "and divide by the total credit units counted by your institution. "
            "Because course units carry different weights, CGPA is not always "
            "the simple average of semester GPAs.\n\n"
            "Check your student handbook for the rules on withdrawals, repeats, "
            "and exclusions so your calculation matches your university's policy."
        ),
    },
    {
        "title": "How to improve your GPA",
        "category": "study",
        "excerpt": "Practical ways to plan your study time, stay consistent, and make progress through the semester.",
        "image": "6e92d5436836fc828a79e51f2e63ccf7.jpg",
        "alt": "A calm place to focus and study",
        "read_time": 5,
        "body": (
            "Improving your GPA starts with a plan you can keep. At the start "
            "of each week, list upcoming classes, assignment deadlines, and "
            "short revision sessions. Small, regular reviews make it easier "
            "to spot confusing topics before exams.\n\n"
            "Use active recall: close your notes and try to explain a concept "
            "or solve a practice question from memory. Then revisit the parts "
            "you missed. Study groups can help too, especially when everyone "
            "arrives with questions and a clear topic to cover.\n\n"
            "Protect time for sleep and breaks. If a course remains difficult, "
            "ask your lecturer or a classmate for help early rather than waiting "
            "until the end of the semester."
        ),
    },
    {
        "title": "Understanding the 5-point grading system",
        "category": "grading",
        "excerpt": "A clear breakdown of grade points and how the five-point scale is used in Nigerian universities.",
        "image": "ce469c725d7ecb03f059d7569411f664.jpg",
        "alt": "Notes and books for reviewing university grades",
        "read_time": 4,
        "body": (
            "In a five-point grading system, letter grades correspond to grade "
            "points on a scale that typically ranges from zero to five. Those "
            "grade points are multiplied by course units to calculate quality "
            "points for GPA and CGPA.\n\n"
            "The exact mark boundaries and letter-grade values can differ "
            "between institutions and programmes. Check your department's "
            "handbook or official result guide rather than relying on a scale "
            "from another university.\n\n"
            "Once you know your institution's scale, record each course's grade "
            "and credit units, then use the GPA calculator to apply the weighting."
        ),
    },
    {
        "title": "How carryover courses affect your GPA",
        "category": "gpa",
        "excerpt": "Get a clearer picture of repeat courses, course units, and what to check in your school's rules.",
        "image": "5b9cc83932aee09221b56e8e01dcb86d.jpg",
        "alt": "Textbooks ready for another semester",
        "read_time": 4,
        "body": (
            "A carryover course is a course you need to take again after not "
            "meeting its pass requirements. How it affects your GPA depends "
            "on your institution's rules: some schools replace an earlier "
            "grade, while others include both attempts or apply another method.\n\n"
            "Before estimating your result, check the current student handbook "
            "or ask your academic adviser how repeat attempts are recorded and "
            "whether the course units count again.\n\n"
            "Keep a record of the course, units, and each attempt. That makes "
            "it easier to understand your transcript and plan the semester ahead."
        ),
    },
    {
        "title": "7 study habits for stronger results",
        "category": "study",
        "excerpt": "Simple routines that can help you stay organised, prepare well, and feel less rushed at exam time.",
        "image": "2968ee4c7b4b57b263f385efb0f74fa0.jpg",
        "alt": "Study materials arranged on a desk",
        "read_time": 5,
        "body": (
            "Build a routine around manageable habits: attend classes, review "
            "your notes soon after each lecture, and break large assignments "
            "into smaller steps with their own deadlines.\n\n"
            "Practise retrieving information from memory, work through sample "
            "questions, and keep a list of topics to ask about. Study in focused "
            "blocks, put away distractions, and take short breaks between them.\n\n"
            "Finally, make time for sleep and start exam revision early. Consistent "
            "effort usually works better than trying to learn everything at once."
        ),
    },
]

STARTER_POSTS = [
    {
        "title": "Understanding the 4-Point Grading System",
        "category": "academic",
        "excerpt": "Learn the common A-to-F grade values used by 4-point GPA and CGPA systems, and when to confirm institution-specific rules.",
        "image": "ce469c725d7ecb03f059d7569411f664.jpg",
        "alt": "Notes and books for reviewing a four-point grading scale",
        "read_time": 4,
        "body": (
            "A 4-point grading system assigns grade points on a scale with A "
            "equal to 4 and F equal to 0. A common letter-grade mapping is "
            "A = 4, B = 3, C = 2, D = 1, and E or F = 0. Multiply each "
            "grade point by the course units and divide the total quality "
            "points by total units to calculate GPA or CGPA.\n\n"
            "Worked example: 3 units with an A contribute 12 quality points, "
            "2 units with a B contribute 6, and 3 units with a C contribute "
            "6. Across 8 units, the GPA is (12 + 6 + 6) / 8 = 3.00.\n\n"
            "Do not assume every school uses the same scale or degree "
            "classification cutoffs. Some universities use different meanings "
            "for D or E, different repeat-course rules, or their own honours "
            "class boundaries. Always confirm the official grading policy in "
            "your institution's handbook."
        ),
    },
    {
        "title": "Understanding GPA vs CGPA: What's the Difference?",
        "category": "academic",
        "excerpt": "Learn what GPA and CGPA measure, how they relate, and why course units matter when comparing them.",
        "image": "5e613082b1f41a852a07ad23017508af.jpg",
        "alt": "Books arranged for a university study session",
        "read_time": 4,
        "body": (
            "GPA (Grade Point Average) summarizes your results for a particular "
            "semester. CGPA (Cumulative Grade Point Average) summarizes the "
            "results counted across multiple semesters. They use related "
            "information, but they answer different questions: GPA shows how "
            "one semester went, while CGPA shows your cumulative record.\n\n"
            "Both calculations usually multiply each course's grade point by "
            "its credit units, add those quality points, then divide by the "
            "total credit units included. Because units carry different "
            "weights, CGPA is not necessarily the simple average of semester "
            "GPAs. The exact calculation can also depend on your institution's "
            "rules for repeats, withdrawals, and excluded courses.\n\n"
            "Example: if two semesters have the same total units, their GPA "
            "values contribute equally to the combined CGPA. If one semester "
            "has more counted units, it contributes more. For an accurate "
            "result, use the units and grades on your transcript and confirm "
            "which attempts your school includes."
        ),
    },
    {
        "title": "How to Calculate Your CGPA Using Course Units",
        "category": "academic",
        "excerpt": "Follow a course-by-course example to see how grade points and units combine into a weighted average.",
        "image": "522099927e2af7a76ab1ca67a52b3ccd.jpg",
        "alt": "Study materials for working out a CGPA",
        "read_time": 5,
        "body": (
            "A common way to calculate CGPA is to divide total quality points "
            "by the total credit units counted. For each course, multiply its "
            "grade point by its course units to get quality points. Add the "
            "quality points for all included courses, then divide by their "
            "combined units.\n\n"
            "Worked example on a five-point scale: imagine four courses. You "
            "earn 5 points in a 3-unit course, 4 points in a 2-unit course, "
            "3 points in another 3-unit course, and 2 points in a 2-unit "
            "course. Their quality points are 15, 8, 9, and 4. The total is "
            "36 quality points over 10 units, so the weighted average is "
            "36 / 10 = 3.60.\n\n"
            "For a cumulative result, include all courses and attempts that "
            "your institution counts, not just the current semester. Use the "
            "grade-point scale in your handbook; grade boundaries and repeat "
            "rules can differ between schools. Keep full precision while "
            "adding, and round only the final result according to your "
            "institution's convention."
        ),
    },
    {
        "title": "How to Improve Your CGPA in the Next Semester",
        "category": "study",
        "excerpt": "Build a realistic semester plan around course priorities, steady revision, feedback, and support.",
        "image": "6e92d5436836fc828a79e51f2e63ccf7.jpg",
        "alt": "A calm place to focus and study",
        "read_time": 5,
        "body": (
            "Start with a clear picture of where you are. Review your results "
            "and course feedback, identify topics that caused difficulty, and "
            "note important deadlines for the coming semester. If you have a "
            "target CGPA, calculate what is realistic using your completed "
            "units and planned workload rather than relying on guesswork.\n\n"
            "Give every course regular attention. Make a weekly timetable "
            "that includes lectures, short review sessions, assignment time, "
            "and breaks. Practise active recall by answering questions "
            "without looking at your notes, then use the gaps you find to "
            "guide your next study session. Begin major assignments and exam "
            "revision early enough to ask for help.\n\n"
            "Check your progress during the semester, not only after results "
            "are released. Ask lecturers, tutors, classmates, or academic "
            "advisers for support when you need it. Consistent habits can "
            "improve your preparation, but no study plan can guarantee a "
            "particular grade or result."
        ),
    },
    {
        "title": "What GPA Do You Need to Reach Your Desired CGPA?",
        "category": "problem-solving",
        "excerpt": "Use a weighted-average formula and worked example to estimate the GPA needed over your next courses.",
        "image": "5b9cc83932aee09221b56e8e01dcb86d.jpg",
        "alt": "Textbooks ready for another semester",
        "read_time": 5,
        "body": (
            "You can estimate the GPA needed in upcoming courses if you know "
            "your current CGPA, completed units, desired CGPA, and planned "
            "units. When all of those units count under the same rules, use:\n\n"
            "Required GPA = (desired CGPA x (completed units + planned units) "
            "- current CGPA x completed units) / planned units.\n\n"
            "Worked example: your current CGPA is 3.20 over 60 units, and you "
            "want a 3.50 CGPA after taking 20 more units. The calculation is "
            "(3.50 x 80 - 3.20 x 60) / 20 = (280 - 192) / 20 = 4.40. You "
            "would need a 4.40 GPA across those 20 units to reach that "
            "estimated target.\n\n"
            "Compare the required GPA with the highest possible GPA on your "
            "scale. If it is above the maximum, the target cannot be reached "
            "in that number of units; consider a longer timeline or another "
            "target. This estimate assumes a straightforward unit-weighted "
            "average. Repeated courses, exclusions, or special rounding "
            "policies can change the result, so check your school's rules. "
            "Use the CGPA calculator to explore your own numbers."
        ),
    },
    {
        "title": "Five Common Mistakes Students Make When Calculating CGPA",
        "category": "student-corner",
        "excerpt": "Avoid common calculation errors involving course units, grade scales, semester averages, repeats, and rounding.",
        "image": "ce469c725d7ecb03f059d7569411f664.jpg",
        "alt": "Notes and books for reviewing university grades",
        "read_time": 4,
        "body": (
            "1. Taking a simple average of course grades. Courses often have "
            "different units, so multiply each grade point by its units "
            "before combining results.\n\n"
            "2. Averaging semester GPAs without checking their unit totals. "
            "A semester with more counted units usually has more influence "
            "on a cumulative weighted average.\n\n"
            "3. Using the wrong grade-point scale. Confirm the scale and "
            "grade boundaries published by your own institution instead of "
            "copying another school's table.\n\n"
            "4. Guessing how a repeated course is counted. Some institutions "
            "replace an earlier grade; others use different rules. Check "
            "your current handbook or ask an academic adviser.\n\n"
            "5. Rounding too early or including the wrong courses. Keep "
            "precision during intermediate steps, and verify which courses "
            "and attempts belong in the calculation. Round only the final "
            "answer as your institution requires."
        ),
    },
]


def get_db():
    if "admin_db" not in g:
        g.admin_db = connect_database(
            current_app.config.get("DATABASE_URL"),
            current_app.config["ADMIN_DATABASE"],
        )
    return g.admin_db


def close_db(_error=None):
    database = g.pop("admin_db", None)
    if database is not None:
        database.close()


def initialize_database(app):
    app.config["DATABASE_URL"] = os.environ.get("DATABASE_URL", "").strip()
    app.config["ADMIN_DATABASE"] = os.path.join(app.instance_path, "cgpa_hub.sqlite3")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    if not app.config["DATABASE_URL"]:
        os.makedirs(app.instance_path, exist_ok=True)

    is_postgres = bool(app.config["DATABASE_URL"])
    identity_column = (
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
        if is_postgres
        else "INTEGER PRIMARY KEY"
    )
    timestamp_default = (
        "CURRENT_TIMESTAMP::text"
        if is_postgres
        else "CURRENT_TIMESTAMP"
    )
    schema = [
        f"""
            CREATE TABLE IF NOT EXISTS admins (
                id {identity_column},
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT {timestamp_default}
            )
        """,
        """
            CREATE TABLE IF NOT EXISTS site_content (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS posts (
                id {identity_column},
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                body TEXT NOT NULL,
                image TEXT NOT NULL,
                image_alt TEXT NOT NULL,
                read_time INTEGER NOT NULL,
                video_url TEXT NOT NULL DEFAULT '',
                is_featured INTEGER NOT NULL DEFAULT 0,
                is_published INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT {timestamp_default},
                updated_at TEXT NOT NULL DEFAULT {timestamp_default}
            )
        """,
        """
            CREATE TABLE IF NOT EXISTS daily_pageviews (
                view_date TEXT NOT NULL,
                path TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (view_date, path)
            )
        """,
        """
            CREATE TABLE IF NOT EXISTS login_attempts (
                key_hash TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL,
                window_started TEXT NOT NULL
            )
        """,
        """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """,
    ]

    with connect_database(
        app.config["DATABASE_URL"],
        app.config["ADMIN_DATABASE"],
    ) as database:
        if database.is_postgres:
            database.execute(
                "SELECT pg_advisory_xact_lock(?)",
                (POSTGRES_INIT_LOCK_KEY,),
            )
        else:
            database.execute("BEGIN IMMEDIATE")

        for statement in schema:
            database.execute(statement)
        post_columns = {
            column.name if hasattr(column, "name") else column[0]
            for column in database.execute("SELECT * FROM posts LIMIT 0").description or ()
        }
        if "video_url" not in post_columns:
            database.execute(
                "ALTER TABLE posts ADD COLUMN video_url TEXT NOT NULL DEFAULT ''"
            )
        database.executemany(
            """
            INSERT INTO site_content (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO NOTHING
            """,
            list(DEFAULT_CONTENT.items()),
        )
        post_count = database.execute(
            "SELECT COUNT(*) AS count FROM posts"
        ).fetchone()["count"]
        posts_to_seed = (SEED_POSTS if post_count == 0 else []) + STARTER_POSTS
        for post in posts_to_seed:
            slug = slugify(post["title"])
            database.execute(
                """
                INSERT INTO posts (
                    title, slug, category, excerpt, body, image, image_alt,
                    read_time, video_url, is_featured, is_published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, 1)
                ON CONFLICT (slug) DO NOTHING
                """,
                (
                    post["title"],
                    slug,
                    post["category"],
                    post["excerpt"],
                    post["body"],
                    f"Images/{post['image']}",
                    post["alt"],
                    post["read_time"],
                    int(post["category"] == "gpa" and slug == "how-to-calculate-your-gpa"),
                ),
            )
        if not os.environ.get("SECRET_KEY"):
            database.execute(
                """
                INSERT INTO app_meta (key, value) VALUES ('session_secret', ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (secrets.token_hex(32),),
            )
            app.config["SECRET_KEY"] = database.execute(
                "SELECT value FROM app_meta WHERE key = 'session_secret'"
            ).fetchone()["value"]
        else:
            app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
        cutoff_date = (date.today() - timedelta(days=90)).isoformat()
        database.execute(
            "DELETE FROM daily_pageviews WHERE view_date < ?",
            (cutoff_date,),
        )


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:100].rstrip("-")


def csrf_token():
    if "_admin_csrf" not in session:
        session["_admin_csrf"] = secrets.token_urlsafe(32)
    return session["_admin_csrf"]


def require_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("_admin_csrf", "")
    if not expected or not hmac.compare_digest(submitted, expected):
        abort(400, description="Your form session expired. Please reload and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def get_content():
    content = DEFAULT_CONTENT.copy()
    content.update(dict(get_db().execute("SELECT key, value FROM site_content").fetchall()))
    return content


def available_images():
    image_dir = Path(current_app.static_folder) / "Images"
    images = [
        f"Images/{filename}"
        for filename in os.listdir(image_dir)
        if Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    if upload_dir.is_dir():
        images.extend(
            f"/uploads/{filename}"
            for filename in os.listdir(upload_dir)
            if Path(filename).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
    return sorted(images)


def save_cover_image(upload):
    if not upload or not upload.filename:
        return None, None

    filename = secure_filename(upload.filename)
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None, "Choose a JPG, PNG, or WebP image."

    try:
        payload = upload.read()
        if len(payload) > 5 * 1024 * 1024:
            return None, "The cover image must be 5 MB or smaller."
        with Image.open(BytesIO(payload)) as image:
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            image_format = image.format
            if image_format not in {"JPEG", "PNG", "WEBP"}:
                return None, "Choose a JPG, PNG, or WebP image."
    except (UnidentifiedImageError, OSError):
        return None, "The selected file is not a valid image."

    cloudinary_url = os.environ.get("CLOUDINARY_URL", "").strip()
    cloudinary_configured = bool(cloudinary_url) or all(
        os.environ.get(key, "").strip()
        for key in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    )
    if cloudinary_configured:
        try:
            import cloudinary
            import cloudinary.uploader

            if cloudinary_url:
                cloudinary.config(secure=True)
            else:
                cloudinary.config(
                    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
                    api_key=os.environ["CLOUDINARY_API_KEY"],
                    api_secret=os.environ["CLOUDINARY_API_SECRET"],
                    secure=True,
                )
            uploaded = cloudinary.uploader.upload(
                BytesIO(payload),
                folder="cgpa-hub/blog",
                resource_type="image",
                overwrite=False,
                unique_filename=True,
            )
            secure_url = uploaded.get("secure_url")
            if secure_url:
                return secure_url, None
        except Exception:
            return None, "The image could not be uploaded. Please try again."

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(payload)
    return f"/uploads/{stored_name}", None


def unique_slug(title, post_id=None):
    base_slug = slugify(title)
    if not base_slug:
        raise ValueError("The title must contain at least one letter or number.")
    slug = base_slug
    suffix = 2
    while True:
        existing = get_db().execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone()
        if existing is None or existing["id"] == post_id:
            return slug
        slug = f"{base_slug[:94]}-{suffix}"
        suffix += 1


def validate_post_form():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    excerpt = request.form.get("excerpt", "").strip()
    body = request.form.get("body", "").strip()
    uploaded_image, upload_error = save_cover_image(request.files.get("cover_image"))
    image = uploaded_image or request.form.get("image", "").strip()
    image_alt = request.form.get("image_alt", "").strip()
    video_url = normalize_youtube_url(request.form.get("video_url", ""))
    try:
        read_time = int(request.form.get("read_time", ""))
    except ValueError:
        read_time = 0

    slug_source = request.form.get("slug", "").strip() or title
    errors = []
    if not title or len(title) > 160:
        errors.append("Enter a title between 1 and 160 characters.")
    if not slugify(slug_source):
        errors.append("The URL slug must contain at least one letter or number.")
    if category not in CATEGORY_LABELS:
        errors.append("Choose a valid article category.")
    if video_url is None:
        errors.append("Enter a valid YouTube video link or leave the field blank.")
    if not excerpt or len(excerpt) > 280:
        errors.append("Enter an excerpt between 1 and 280 characters.")
    if not body:
        errors.append("Article content cannot be empty.")
    if upload_error:
        errors.append(upload_error)
    if (
        image not in available_images()
        and not (
            image.startswith("https://")
            and urlsplit(image).hostname in {"res.cloudinary.com", "cloudinary.com"}
        )
        and not image.startswith("/uploads/")
    ):
        errors.append("Choose an image from the available library.")
    if not image_alt or len(image_alt) > 180:
        errors.append("Enter image alt text between 1 and 180 characters.")
    if not 1 <= read_time <= 120:
        errors.append("Reading time must be between 1 and 120 minutes.")
    if errors:
        for error in errors:
            flash(error, "error")
        return None

    return {
        "title": title,
        "slug": unique_slug(slug_source),
        "category": category,
        "excerpt": excerpt,
        "body": body,
        "image": image,
        "image_alt": image_alt,
        "video_url": video_url,
        "read_time": read_time,
        "is_featured": int(request.form.get("is_featured") == "1"),
        "is_published": int(request.form.get("is_published") == "1"),
    }


def set_login_attempts(key_hash, attempts, window_started):
    get_db().execute(
        """
        INSERT INTO login_attempts (key_hash, attempts, window_started)
        VALUES (?, ?, ?)
        ON CONFLICT(key_hash) DO UPDATE SET
            attempts = excluded.attempts,
            window_started = excluded.window_started
        """,
        (key_hash, attempts, window_started),
    )
    get_db().commit()


@admin_bp.before_request
def enforce_admin_csrf():
    if request.method == "POST":
        require_csrf()


@admin_bp.after_request
def disable_admin_caching(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        database = get_db()
        now = date.today()
        address = request.remote_addr or "unknown"
        attempt_key = hmac.new(
            current_app.config["SECRET_KEY"].encode(),
            address.encode(),
            hashlib.sha256,
        ).hexdigest()
        attempt = database.execute(
            "SELECT attempts, window_started FROM login_attempts WHERE key_hash = ?",
            (attempt_key,),
        ).fetchone()
        window_start = now.isoformat()
        attempt_count = 0
        if attempt:
            try:
                elapsed = (now - date.fromisoformat(attempt["window_started"][:10])).days
            except ValueError:
                elapsed = 1
            if elapsed == 0:
                window_start = attempt["window_started"]
                attempt_count = attempt["attempts"]

        if attempt_count >= 10:
            flash("Too many sign-in attempts. Try again tomorrow.", "error")
            return render_template("admin/login.html"), 429

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        account = database.execute(
            "SELECT id, username, password_hash FROM admins WHERE username = ?",
            (username,),
        ).fetchone()
        if account and check_password_hash(account["password_hash"], password):
            database.execute("DELETE FROM login_attempts WHERE key_hash = ?", (attempt_key,))
            database.commit()
            session.clear()
            session.permanent = request.form.get("remember_me") == "1"
            session["admin_id"] = account["id"]
            session["admin_username"] = account["username"]
            destination = request.args.get("next", "")
            parsed_destination = urlsplit(destination)
            if (
                not destination.startswith("/")
                or destination.startswith("//")
                or "\\" in destination
                or parsed_destination.netloc
            ):
                destination = url_for("admin.dashboard")
            return redirect(destination)

        set_login_attempts(attempt_key, attempt_count + 1, window_start)
        flash("The username or password was not recognised.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    database = get_db()
    today = date.today()
    week_ago = today - timedelta(days=6)
    summary = {
        "published_posts": database.execute(
            "SELECT COUNT(*) FROM posts WHERE is_published = 1"
        ).fetchone()[0],
        "draft_posts": database.execute(
            "SELECT COUNT(*) FROM posts WHERE is_published = 0"
        ).fetchone()[0],
        "views_today": database.execute(
            "SELECT COALESCE(SUM(views), 0) FROM daily_pageviews WHERE view_date = ?",
            (today.isoformat(),),
        ).fetchone()[0],
        "views_week": database.execute(
            "SELECT COALESCE(SUM(views), 0) FROM daily_pageviews WHERE view_date >= ?",
            (week_ago.isoformat(),),
        ).fetchone()[0],
    }
    recent_posts = database.execute(
        "SELECT id, title, slug, is_published, updated_at FROM posts ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()
    top_pages = database.execute(
        """
        SELECT path, SUM(views) AS views
        FROM daily_pageviews
        WHERE view_date >= ?
        GROUP BY path ORDER BY views DESC LIMIT 5
        """,
        (week_ago.isoformat(),),
    ).fetchall()
    daily_views = database.execute(
        """
        SELECT view_date, SUM(views) AS views
        FROM daily_pageviews
        WHERE view_date >= ?
        GROUP BY view_date ORDER BY view_date
        """,
        (week_ago.isoformat(),),
    ).fetchall()
    return render_template(
        "admin/dashboard.html",
        summary=summary,
        recent_posts=recent_posts,
        top_pages=top_pages,
        daily_views=daily_views,
        content=get_content(),
    )


@admin_bp.route("/analytics")
@admin_required
def analytics():
    database = get_db()
    start = date.today() - timedelta(days=29)
    daily_views = database.execute(
        """
        SELECT view_date, SUM(views) AS views
        FROM daily_pageviews
        WHERE view_date >= ?
        GROUP BY view_date ORDER BY view_date
        """,
        (start.isoformat(),),
    ).fetchall()
    top_pages = database.execute(
        """
        SELECT path, SUM(views) AS views
        FROM daily_pageviews
        WHERE view_date >= ?
        GROUP BY path ORDER BY views DESC LIMIT 20
        """,
        (start.isoformat(),),
    ).fetchall()
    return render_template(
        "admin/analytics.html",
        daily_views=daily_views,
        top_pages=top_pages,
        period_total=sum(row["views"] for row in daily_views),
        content=get_content(),
    )


@admin_bp.route("/posts")
@admin_required
def posts():
    post_list = get_db().execute(
        "SELECT * FROM posts ORDER BY is_published, updated_at DESC"
    ).fetchall()
    return render_template(
        "admin/posts.html",
        posts=post_list,
        category_label=category_label,
        content=get_content(),
    )


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@admin_required
def new_post():
    if request.method == "POST":
        post = validate_post_form()
        if post:
            database = get_db()
            database.execute(
                """
                UPDATE posts SET is_featured = 0
                WHERE is_featured = 1 AND ? = 1
                """,
                (post["is_featured"],),
            )
            database.execute(
                """
                INSERT INTO posts (
                    title, slug, category, excerpt, body, image, image_alt,
                    read_time, video_url, is_featured, is_published, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                tuple(post[key] for key in (
                    "title", "slug", "category", "excerpt", "body", "image",
                    "image_alt", "read_time", "video_url", "is_featured", "is_published",
                )),
            )
            database.commit()
            flash("Article saved.", "success")
            return redirect(url_for("admin.posts"))
        form_data = request.form
    else:
        form_data = {}
    return render_template(
        "admin/post_form.html",
        post=form_data,
        images=available_images(),
        category_options=POST_CATEGORY_OPTIONS,
        category_filter_id=category_filter_id,
        content=get_content(),
    )


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_post(post_id):
    database = get_db()
    existing = database.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if existing is None:
        abort(404)
    if request.method == "POST":
        post = validate_post_form()
        if post:
            database.execute(
                """
                UPDATE posts SET is_featured = 0
                WHERE is_featured = 1 AND id != ? AND ? = 1
                """,
                (post_id, post["is_featured"]),
            )
            database.execute(
                """
                UPDATE posts SET
                    title = ?, slug = ?, category = ?, excerpt = ?, body = ?,
                    image = ?, image_alt = ?, read_time = ?, video_url = ?, is_featured = ?,
                    is_published = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                tuple(post[key] for key in (
                    "title", "slug", "category", "excerpt", "body", "image",
                    "image_alt", "read_time", "video_url", "is_featured", "is_published",
                )) + (post_id,),
            )
            database.commit()
            flash("Article updated.", "success")
            return redirect(url_for("admin.posts"))
        form_data = request.form
    else:
        form_data = existing
    return render_template(
        "admin/post_form.html",
        post=form_data,
        images=available_images(),
        category_options=POST_CATEGORY_OPTIONS,
        category_filter_id=category_filter_id,
        content=get_content(),
    )


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def delete_post(post_id):
    database = get_db()
    result = database.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    if result.rowcount == 0:
        abort(404)
    database.commit()
    flash("Article deleted.", "success")
    return redirect(url_for("admin.posts"))


@admin_bp.route("/content", methods=["GET", "POST"])
@admin_required
def content_editor():
    content = get_content()
    if request.method == "POST":
        updated = {
            "home_heading": request.form.get("home_heading", "").strip(),
            "home_description": request.form.get("home_description", "").strip(),
            "blog_intro": request.form.get("blog_intro", "").strip(),
            "announcement": request.form.get("announcement", "").strip(),
            "footer_text": request.form.get("footer_text", "").strip(),
        }
        limits = {
            "home_heading": 100,
            "home_description": 500,
            "blog_intro": 500,
            "announcement": 220,
            "footer_text": 180,
        }
        errors = [
            f"{key.replace('_', ' ').capitalize()} must be no more than {limit} characters."
            for key, limit in limits.items()
            if len(updated[key]) > limit
        ]
        if errors:
            for error in errors:
                flash(error, "error")
            content.update(updated)
        else:
            database = get_db()
            database.executemany(
                """
                INSERT INTO site_content (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                updated.items(),
            )
            database.commit()
            flash("Site content updated.", "success")
            return redirect(url_for("admin.content_editor"))
    return render_template("admin/content.html", content=content)


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    content = get_content()
    if request.method == "POST":
        updated = {
            "site_name": request.form.get("site_name", "").strip(),
            "site_tagline": request.form.get("site_tagline", "").strip(),
            "footer_bible_verse": request.form.get("footer_bible_verse", "").strip(),
            "footer_bible_reference": request.form.get(
                "footer_bible_reference", ""
            ).strip(),
            "footer_bible_verse_visible": (
                "1" if request.form.get("footer_bible_verse_visible") == "1" else "0"
            ),
        }
        errors = []
        if not updated["site_name"] or len(updated["site_name"]) > 60:
            errors.append("Site name must be between 1 and 60 characters.")
        if len(updated["site_tagline"]) > 100:
            errors.append("Site tagline must be 100 characters or fewer.")
        if len(updated["footer_bible_verse"]) > 1000:
            errors.append("Bible verse must be 1,000 characters or fewer.")
        if len(updated["footer_bible_reference"]) > 100:
            errors.append("Bible verse reference must be 100 characters or fewer.")
        if updated["footer_bible_verse_visible"] == "1":
            if not updated["footer_bible_verse"]:
                errors.append("Enter a Bible verse or turn off its display.")
            if not updated["footer_bible_reference"]:
                errors.append("Enter a Bible verse reference or turn off its display.")

        if errors:
            for error in errors:
                flash(error, "error")
            content.update(updated)
        else:
            database = get_db()
            database.executemany(
                """
                INSERT INTO site_content (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                updated.items(),
            )
            database.commit()
            flash("Website settings updated.", "success")
            return redirect(url_for("admin.settings"))
        content.update(updated)
    return render_template("admin/settings.html", content=content)


@admin_bp.app_context_processor
def inject_admin_template_helpers():
    return {"csrf_token": csrf_token, "admin_content": get_content}


@admin_bp.cli.command("create-admin")
def create_admin_command():
    """Create or replace an administrator account from a trusted terminal."""
    username = click.prompt("Admin username").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
        raise click.ClickException("Use 3–40 letters, numbers, dots, underscores, or hyphens.")
    password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
    if len(password) < 12:
        raise click.ClickException("Use a password with at least 12 characters.")
    database = connect_database(
        current_app.config.get("DATABASE_URL"),
        current_app.config["ADMIN_DATABASE"],
    )
    try:
        database.execute(
            """
            INSERT INTO admins (username, password_hash) VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash
            """,
            (username, generate_password_hash(password)),
        )
        database.commit()
    finally:
        database.close()
    click.echo(f"Admin account ready for {username}.")
