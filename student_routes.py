
import hmac
import secrets

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    jsonify,
)

from admin import get_db
from student_auth import (
    register_student,
    create_verification_code,
    send_verification_email,
    verify_student_email,
    authenticate_student,
    save_student_record,
    get_student_record,
)

student_bp = Blueprint("student", __name__, url_prefix="/student")


# -------------------------
# CSRF PROTECTION
# -------------------------

def get_student_csrf_token():
    if "_student_csrf" not in session:
        session["_student_csrf"] = secrets.token_hex(32)

    return session["_student_csrf"]


def validate_student_csrf():
    submitted = (
        request.form.get("csrf_token", "")
        or request.headers.get("X-CSRF-Token", "")
    )

    stored = session.get("_student_csrf", "")

    return bool(
        submitted
        and stored
        and hmac.compare_digest(submitted, stored)
    )


@student_bp.before_request
def protect_student_forms():
    if request.method == "POST":
        if not validate_student_csrf():
            return "Invalid form submission. Please refresh and try again.", 400


@student_bp.app_context_processor
def inject_student_csrf():
    return {"student_csrf_token": get_student_csrf_token}


# -------------------------
# STUDENT REGISTRATION
# ------------------------- 

@student_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("student_register.html")

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if password != confirm_password:
        flash("Your passwords do not match.", "error")
        return render_template("student_register.html"), 400

    db = get_db()

    result = register_student(db,full_name, email, password)

    if not result["success"]:
        flash(result.get("message", "Registration failed."), "error")
        return render_template("student_register.html"), 400

    student_id = result["student_id"]

    try:
        code = create_verification_code(
            db,
            student_id,
            current_app.config["SECRET_KEY"]
        )
        print("DEBUG VERIFICATION CODE:", code)

        send_verification_email(email, code, allow_dev_mode= True)

    except Exception:
        current_app.logger.exception(
            "Student Registration verification error."
        )

        session["pending_student_id"] = student_id
        session["pending_student_email"] = email

        flash(
            "Account created, but email delivery failed. "
            "Please try again later.",
            "error"
        )

        return redirect(url_for("student.verify"))

    session["pending_student_id"] = student_id
    session["pending_student_email"] = email

    flash("Verification code sent to your email.", "success")

    return redirect(url_for("student.verify"))


# -------------------------
# EMAIL VERIFICATION
# -------------------------

@student_bp.route("/verify", methods=["GET", "POST"])
def verify():

    student_id = session.get("pending_student_id")

    if not student_id:
        flash("Please register first.", "error")
        return redirect(url_for("student.register"))

    if request.method == "GET":
        return render_template(
            "student_verify.html",
            email=session.get("pending_student_email")
        )

    code = request.form.get("code", "").strip()

    db = get_db()

    success = verify_student_email(
        db,
        student_id,
        code,
        current_app.config["SECRET_KEY"]
    )

    if success:

        session.pop("pending_student_id", None)
        session.pop("pending_student_email", None)

        flash(
            "Email verified successfully. You can now log in.",
            "success"
        )

        return redirect(url_for("student.login"))

    flash("Invalid or expired verification code.", "error")

    return render_template(
        "student_verify.html",
        email=session.get("pending_student_email")
    ), 400


# -------------------------
# STUDENT LOGIN
# -------------------------

    # Clear the old session before creating the authenticated session.
    session.clear()

    session["student_id"] = student["id"]
    session["student_email"] = student["email"]

    session["_student_csrf"] = secrets.token_hex(32)

    flash("Login successful.", "success")

    return redirect(url_for("dashboard"))


# -------------------------
# STUDENT LOGOUT
# -------------------------
@student_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("student_login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    db = get_db()

    student = authenticate_student(db, email, password)

    # Check if login details are incorrect
    if not student:
        flash("Invalid email or password.", "error")
        return render_template("student_login.html")

    # Check if student's email is not verified
    if not student["verified"]:

        session["pending_student_id"] = student["id"]
        session["pending_student_email"] = student["email"]

        try:
            code = create_verification_code(
                db,
                student["id"],
                current_app.config["SECRET_KEY"]
            )

            send_verification_email(
                student["email"],
                code,
                allow_dev_mode=True
            )

            flash("A new verification code has been sent to your email.", "success")

        except Exception:
            current_app.logger.exception("Login verification email error.")
            flash("Unable to send verification email. Please try again later.", "error")

        return redirect(url_for("student.verify"))

    # Clear the old session before creating the authenticated session.
    session.clear()

    session["student_id"] = student["id"]
    session["student_email"] = student["email"]

    session["_student_csrf"] = secrets.token_hex(32)

    flash("Login successful.", "success")

    return redirect(url_for("dashboard"))


    
@student_bp.route("/logout", methods=["POST"])
def logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for("student.login"))


# -------------------------
# STUDENT RECORD API
# -------------------------

@student_bp.route("/records/<record_type>", methods=["GET", "POST"])
def student_records(record_type):

    student_id = session.get("student_id")

    if not student_id:
        return jsonify({"error": "Please log in first."}), 401

    if record_type not in ("gpa", "cgpa"):
        return jsonify({"error": "Invalid record type."}), 400

    db = get_db()

    if request.method == "GET":

        record = get_student_record(
            db,
            student_id,
            record_type
        )

        return jsonify({
            "record": record
        })

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    record_data = data.get("record")

    if record_data is None:
        return jsonify({"error": "Record data is missing."}), 400

    try:

        save_student_record(
            db,
            student_id,
            record_type,
            record_data
        )

        return jsonify({
            "success": True,
            "message": "Record saved successfully."
        })

    except (ValueError, TypeError):

        return jsonify({
            "error": "Unable to save record."
        }), 400
