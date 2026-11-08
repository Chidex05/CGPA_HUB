import math

# UNIVERSITY GRADING CONFIGURATION
UNIVERSITY_RULES = {
    "RSU": {
        "name": "Rivers State University",
        "max_grade_point": 5,
        "grades": {
            "A": 5,
            "B": 4,
            "C": 3,
            "D": 2,
            "E": 1,
            "F": 0
        }
    }

def get_university_rules(university="RSU"):
    rules = UNIVERSITY_RULES.get(university)

    if not rules:
        raise ValueError("University grading system not supported.")

    return rules


def validate_course(course, grade_points):
    if not isinstance(course, dict):
        raise ValueError("Invalid course information.")

    code = str(course.get("code", "")).strip().upper()
    grade = str(course.get("grade", "")).strip().upper()

    try:
        unit = float(course.get("unit"))
    except (TypeError, ValueError):
        raise ValueError("Invalid course unit.")

    if not code:
        raise ValueError("Course code is required.")

    if not math.isfinite(unit) or not unit.is_integer() or unit <= 0:
        raise ValueError("Course unit must be a positive whole number.")

    if grade not in grade_points:
        raise ValueError("Invalid course grade.")

    return {
        "code": code,
        "unit": int(unit),
        "grade": grade,
        "points": grade_points[grade]
    }


def calculate_academic_record(courses, university="RSU"):

    rules = get_university_rules(university)
    grade_points = rules["grades"]

    if not isinstance(courses, list) or not courses:
        raise ValueError("Please add at least one course.")

    total_units = 0
    total_points = 0

    semesters = {}

    for course in courses:

        validated = validate_course(course, grade_points)

        unit = validated["unit"]
        points = validated["points"]

        session = str(course.get("session", "")).strip()
        semester = str(course.get("semester", "")).strip()

        if not session or not semester:
            raise ValueError(
                "Every course must have an academic session and semester."
            )

        total_units += unit
        total_points += unit * points

        key = (session, semester)

        if key not in semesters:
            semesters[key] = {
                "session": session,
                "semester": semester,
                "total_units": 0,
                "total_points": 0
            }

        semesters[key]["total_units"] += unit
        semesters[key]["total_points"] += unit * points

    semester_results = []

    for record in semesters.values():

        semester_gpa = (
            record["total_points"] / record["total_units"]
        )

        semester_results.append({
            **record,
            "gpa": round(semester_gpa, 2)
        })

    cgpa = total_points / total_units if total_units else 0

    return {
        "university": rules["name"],
        "total_units": total_units,
        "total_points": total_points,
        "cgpa": round(cgpa, 2),
        "semester_results": semester_results
    }