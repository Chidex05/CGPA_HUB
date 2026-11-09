from flask import Flask, render_template, request, jsonify
from academic_engine import calculate_academic_record

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/cgpa')
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
    app.run(debug=True)
