from flask import Flask, render_template, request, jsonify

from flask import Flask, render_template, request, jsonify,Response,send_from_directory

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')


@app.route('/cgpa-calculator')
def cgpa():
    return render_template('cgpa.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')


@app.route('/gpa-calculator')
def gpa():
    return render_template('gpa.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/grade_predictor')
def grade_predictor():
    return render_template('grade_predictor.html')

from flask import send_from_directory, Response

@app.route('/google522d4e4c65fb761d.html')
def google_verification():
    return send_from_directory('static', 'google522d4e4c65fb761d.html')

@app.route('/sitemap.xml')
def sitemap():
    urls = """
    <url>
        <loc>https://cgpa-hub-ecru.vercel.app/</loc>
    </url>
    <url>
        <loc>https://cgpa-hub-ecru.vercel.app/gpa-calculator</loc>
    </url>
    <url>
        <loc>https://cgpa-hub-ecru.vercel.app/cgpa-calculator</loc>
    </url>
    <url>
        <loc>https://cgpa-hub-ecru.vercel.app/grade_predictor</loc>
    </url>
    <url>
        <loc>https://cgpa-hub-ecru.vercel.app/blog</loc>
    </url>
    """
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    {urls}
</urlset>"""
    
    return Response(xml_content, mimetype='application/xml')


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
    data = request.get_json()
    courses = data.get('courses', [])

    grade_points = {
        'A': 5, 'B': 4, 'C': 3, 'D': 2, 'E': 1, 'F': 0
    }

    if not courses:
        return jsonify({'error': 'Please add at least one course.'}), 400

    total_units = 0
    total_points = 0

    # Track variables to separate semesters overall
    semester_1_units = 0
    semester_1_points = 0
    semester_2_units = 0
    semester_2_points = 0

    for course in courses:
        unit = int(course['unit'])
        grade = course['grade'].upper()
        semester = str(course.get('semester', '1'))

        if unit <= 0:
            return jsonify({'error': 'Credit units must be greater than zero.'}), 400

        if grade not in grade_points:
            return jsonify({'error': 'Invalid grade entered.'}), 400

        points = unit * grade_points[grade]
        total_units += unit
        total_points += points

        # Group data into universal semester variables safely
        if semester == '1':
            semester_1_units += unit
            semester_1_points += points
        elif semester == '2':
            semester_2_units += unit
            semester_2_points += points

    # Calculate final cumulative tracking scores
    cgpa = total_points / total_units if total_units > 0 else 0
    semester_1_gpa = semester_1_points / semester_1_units if semester_1_units > 0 else 0
    semester_2_gpa = semester_2_points / semester_2_units if semester_2_units > 0 else 0

    return jsonify({
        'total_units': total_units,
        'total_points': total_points,
        'semester_1_gpa': semester_1_gpa,
        'semester_2_gpa': semester_2_gpa,
        'cgpa': cgpa
    })


if __name__ == '__main__':
    app.run(debug=True)
