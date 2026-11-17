import logging
import os
import re
import sys
import uuid
from datetime import date, timedelta

from flask import Flask, abort, has_request_context, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.exceptions import HTTPException
from academic_engine import calculate_academic_record
from admin import (
    POST_CATEGORY_OPTIONS,
    admin_bp,
    category_filter_id,
    category_label,
    close_db,
    get_content,
    get_db,
    initialize_database,
)
from database import DatabaseError

logger = logging.getLogger("cgpa_hub")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    log_handler = logging.StreamHandler(sys.stderr)
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(log_handler)

_CONNECTION_URL_PATTERN = re.compile(
    r"\b((?:postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?)://)[^\s\"'<>]+",
    re.IGNORECASE,
)
_CREDENTIAL_PATTERN = re.compile(
    r"""(?i)(["']?(?:password|passwd|secret|token|api[_-]?key|authorization|service[_-]?role[_-]?key)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}\]]+)"""
)
_SENSITIVE_ENV_MARKERS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "KEY",
    "CREDENTIAL",
    "DATABASE_URL",
    "AUTH",
    "SUPABASE",
)


def _sanitize_log_text(value):
    text = str(value)
    text = _CREDENTIAL_PATTERN.sub(r"\1[REDACTED]", text)
    text = _CONNECTION_URL_PATTERN.sub(r"\1[REDACTED]", text)
    for name, secret in os.environ.items():
        if secret and len(secret) >= 4 and any(
            marker in name.upper() for marker in _SENSITIVE_ENV_MARKERS
        ):
            text = text.replace(secret, "[REDACTED]")
    return text[:1000]


def _log_sanitized_exception(error, context):
    incident_id = uuid.uuid4().hex
    exception_chain = []
    seen_exceptions = set()
    current = error
    frames = []

    while current is not None and id(current) not in seen_exceptions:
        seen_exceptions.add(id(current))
        exception_chain.append(
            f"{type(current).__name__}: {_sanitize_log_text(current)}"
        )
        traceback = current.__traceback__
        while traceback is not None and len(frames) < 40:
            code = traceback.tb_frame.f_code
            frames.append(
                f"{os.path.basename(code.co_filename)}:{traceback.tb_lineno}:{code.co_name}"
            )
            traceback = traceback.tb_next
        previous = current
        current = previous.__cause__
        if current is None and not previous.__suppress_context__:
            current = previous.__context__

    method = request.method if has_request_context() else "-"
    endpoint = request.endpoint if has_request_context() else "-"
    logger.error(
        "incident_id=%s context=%s method=%s endpoint=%s exceptions=%s frames=%s",
        incident_id,
        context,
        method,
        endpoint,
        " <- ".join(exception_chain),
        ",".join(frames),
    )
    return incident_id


app = Flask(__name__)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_SECURE"] = (
os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
)
app.register_blueprint(admin_bp)
app.teardown_appcontext(close_db)


@app.route('/uploads/<path:filename>')
def uploaded_image(filename):
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        abort(404)
    return send_from_directory(upload_folder, filename)


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return error
    incident_id = _log_sanitized_exception(error, context="request")
    response = app.response_class("Internal Server Error", status=500, mimetype="text/plain")
    response.headers["X-Error-ID"] = incident_id
    return response


try:
    initialize_database(app)
except Exception as error:
    incident_id = _log_sanitized_exception(error, context="startup")
    raise RuntimeError(
        f"Application startup failed; see sanitized log incident {incident_id}."
    ) from None

@app.route('/')
def home():
    return render_template('home.html', content=get_content())

@app.route('/cgpa')
@app.route('/cgpa-calculator')
def cgpa():
    return render_template('cgpa.html')

@app.route('/blog')
def blog():
    database = get_db()
    posts = database.execute(
        """
        SELECT * FROM posts
        WHERE is_published = 1
        ORDER BY is_featured DESC, created_at DESC, id DESC
        """
    ).fetchall()
    featured = next((post for post in posts if post["is_featured"]), None)
    if featured is None and posts:
        featured = posts[0]
    return render_template(
        'blog.html',
        posts=posts,
        featured=featured,
        category_options=POST_CATEGORY_OPTIONS,
        category_filter_id=category_filter_id,
        category_label=category_label,
        content=get_content(),
    )


@app.route('/blog/<slug>')
def blog_article(slug):
    post = get_db().execute(
        "SELECT * FROM posts WHERE slug = ? AND is_published = 1",
        (slug,),
    ).fetchone()
    if post is None:
        abort(404)
    return render_template(
        'article.html',
        post=post,
        category_label=category_label,
        content=get_content(),
    )


@app.route('/gpa-calculator')
@app.route('/gpa')
def gpa():
    return render_template('gpa.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/grade_predictor')
@app.route('/grade-predictor')
def grade_predictor():
    return render_template('grade_predictor.html')


@app.context_processor
def inject_current_year():
    content = get_content()
    return {
        "now_year": date.today().year,
        "footer_bible_verse": content["footer_bible_verse"],
        "footer_bible_reference": content["footer_bible_reference"],
        "show_footer_bible_verse": content["footer_bible_verse_visible"] == "1",
    }


def blog_image_url(image):
    if str(image).startswith("/uploads/"):
        return url_for("uploaded_image", filename=str(image).removeprefix("/uploads/"))
    if str(image).startswith("https://"):
        return str(image)
    return url_for("static", filename=str(image))


app.jinja_env.globals["blog_image_url"] = blog_image_url


@app.after_request
def record_public_pageview(response):
    tracked_pages = {"home", "blog", "blog_article", "gpa", "cgpa", "dashboard", "grade_predictor"}
    if (
        request.method == "GET"
        and request.endpoint in tracked_pages
        and response.status_code < 400
    ):
        try:
            database = get_db()
            database.execute(
                """
                INSERT INTO daily_pageviews (view_date, path, views)
                VALUES (?, ?, 1)
                ON CONFLICT(view_date, path) DO UPDATE SET views = views + 1
                """,
                (date.today().isoformat(), request.path),
            )
            database.commit()
        except DatabaseError as error:
            _log_sanitized_exception(error, context="pageview")
    return response


@app.route('/calculate-gpa', methods=['POST'])
def calculate_gpa():
    data = request.get_json()
    grading_system = str(data.get("grading_system", "5")).strip()
    grades = (
        {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0, "F": 0}
        if grading_system in {"4", "4-point", "4_point"}
        else {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
    )
    total_units = 0
    total_gradepoints = 0
    
    try:
        # FIXED: Changed from 'courses' to 'gpaCourses' to perfectly match your GPA page JavaScript payload key
        courses = data.get('gpaCourses', [])
        if not courses:
            return jsonify({"error": "Please add at least one course"}), 400
            
        for course in courses:
            unit = float(course['unit'])
            grade = str(course['grade']).upper().strip()
            
            if unit <= 0 or grade not in grades:
                return jsonify({"error": "Invalid course unit or grade."}), 400
                
            total_units += unit
            total_gradepoints += unit * grades[grade]
            
        if total_units == 0:
            return jsonify({"error": "Total course units cannot be zero."}), 400
            
        gpa = total_gradepoints / total_units
        
        return jsonify({
            "total_courses": len(courses),    
            "total_units": total_units,
            "total_gradepoints": total_gradepoints,
            "gpa": round(gpa, 2)
        })
        
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Please check your course information"}), 400


        
@app.route('/calculate-cgpa', methods=['POST'])
def calculate_cgpa():
    data = request.get_json(silent=True) or {}
    courses = data.get('courses', [])
    selected_session = str(data.get('selected_session', '')).strip()
    grading_system = str(data.get('grading_system', '5')).strip()

    try:
        result = calculate_academic_record(
            courses,
            university=grading_system if grading_system in {"4", "5"} else "RSU"
        )

        semester_1_gpa = 0
        semester_2_gpa = 0

        for record in result["semester_results"]:
            if record["session"] == selected_session:

                if record["semester"] == "1":
                    semester_1_gpa = record["gpa"]

                elif record["semester"] == "2":
                    semester_2_gpa = record["gpa"]

        return jsonify({
            "total_units": result["total_units"],
            "total_points": result["total_points"],
            "cgpa": result["cgpa"],
            "selected_session": selected_session,
            "semester_1_gpa": semester_1_gpa,
            "semester_2_gpa": semester_2_gpa,
            "semester_results": result["semester_results"]
        })

    except (ValueError, TypeError, KeyError) as error:
        return jsonify({
            "error": str(error)
        }), 400


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() == "true")
