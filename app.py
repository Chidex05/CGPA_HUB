import os
from datetime import date

from flask import Flask, abort, render_template, request, jsonify
from academic_engine import calculate_academic_record
from admin import admin_bp, close_db, get_content, get_db, initialize_database
from database import DatabaseError

app = Flask(__name__)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
)
app.register_blueprint(admin_bp)
app.teardown_appcontext(close_db)
initialize_database(app)

@app.route('/')
def home():
    return render_template('home.html', content=get_content())

@app.route('/cgpa')
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
    return render_template('article.html', post=post, content=get_content())


@app.route('/gpa-calculator')
def gpa():
    return render_template('gpa.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/grade_predictor')
def grade_predictor():
    return render_template('grade_predictor.html')


@app.context_processor
def inject_current_year():
    return {"now_year": date.today().year}


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
        except DatabaseError:
            app.logger.exception("Could not record an aggregated page view")
    return response


@app.route('/calculate-gpa', methods=['POST'])
def calculate_gpa():
    grades = {
        "A": 5,
        "B": 4,
        "C": 3,
        "D": 2,
        "E": 1,
        "F": 0
    }
    
    data = request.get_json()
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

    try:
        result = calculate_academic_record(
            courses,
            university="RSU"
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
