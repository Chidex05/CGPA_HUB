
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import requests
from werkzeug.security import generate_password_hash, check_password_hash


# --------------------------------------------------
# GENERAL UTILITIES
# --------------------------------------------------

def normalize_email(email):
    return (email or "").strip().lower()


def validate_email(email):
    email = normalize_email(email)

    if len(email) > 254:
        return False

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email
        )
    )


def validate_password(password):
    return isinstance(password, str) and len(password) >= 8



def register_student(db, full_name, email, password):
    full_name = " ".join(full_name.strip().split())

    if not full_name or len(full_name) < 2:
        return {
            "success": False,
            "message": "Enter your full name."
        }

    if len(full_name) > 100:
        return {
            "success": False,
            "message": "Full name must not exceed 100 characters."
        }

    email = normalize_email(email)

    if not validate_email(email):
        return {
            "success": False,
            "message": "Enter a valid email address."
        }

    if not validate_password(password):
        return {
            "success": False,
            "message": "Password must be at least 8 characters."
        }

    password_hash = generate_password_hash(password)

    try:
        cursor = db.execute(
            """
            INSERT INTO students (
                full_name, email, password_hash, is_verified
            )
            VALUES (?, ?, ?, 0)
            RETURNING id
            """,
            (full_name, email, password_hash)
        )

        row = cursor.fetchone()
        student_id = row["id"]

        db.commit()

        return {
            "success": True,
            "student_id": student_id,
            "email": email
        }

    except Exception:
        db.rollback()

        return {
            "success": False,
            "message": "Unable to create account. This email may already be registered."
        }

        row = cursor.fetchone()
        student_id = row["id"]

        db.commit()

        return {
            "success": True,
            "student_id": student_id,
            "email": email
        }

    except Exception:
        db.rollback()

        return {
            "success": False,
            "message": "Unable to create account. This email may already be registered."
        }


# --------------------------------------------------
# VERIFICATION CODE CREATION
# --------------------------------------------------
def generate_verification_code():
    return f"{secrets.randbelow(1000000):06d}"


def hash_verification_code(code, secret_key):
    return hmac.new(
        secret_key.encode(),
        code.encode(),
        hashlib.sha256
    ).hexdigest()
    
def utc_now():
    return datetime.now(timezone.utc)

def timestamp_string(value):
    return value.isoformat()

def create_verification_code(db, student_id, secret_key):
    code = generate_verification_code()
    code_hash = hash_verification_code(code, secret_key)

    now = utc_now()
    expires = now + timedelta(minutes=10)

    try:
        db.execute(
            """
            INSERT INTO email_verification
                (student_id, code_hash, expires_at, attempts, created_at)
            VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                code_hash = excluded.code_hash,
                expires_at = excluded.expires_at,
                attempts = 0,
                created_at = excluded.created_at
            """,
            (
                student_id,
                code_hash,
                timestamp_string(expires),
                timestamp_string(now)
            )
        )

        db.commit()

        return code

    except Exception:
        db.rollback()
        raise


def send_verification_email(email, code, allow_dev_mode=False):
    api_key = os.environ.get("BREVO_API_KEY")
    sender = os.environ.get("EMAIL_FROM")
    if not api_key or not sender:
        raise RuntimeError("Brevo Email service configuration is missing.")

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "sender":{"email": sender
                      },
            "to": [
                {"email":email}
            ],
            "subject": "Verify your CGPA Hub account",
            "textContent": (
                f"Your CGPA Hub verification code is {code}.\n\n"
                "This code expires in 10 minutes.\n"
                "If you did not request this, ignore this email."
            )
        },
        timeout=20
    )

    response.raise_for_status()
    return True


def send_newsletter_email(email, subject, html_content):
    api_key = os.environ.get("BREVO_API_KEY")
    sender = os.environ.get("EMAIL_FROM")

    if not api_key or not sender:
        raise RuntimeError("Brevo email configuration is missing.")

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "sender": {
                "email": sender
            },
            "to": [
                {"email": email}
            ],
            "subject": subject,
            "htmlContent": html_content
        },
        timeout=20
    )

    response.raise_for_status()
    return True




# --------------------------------------------------
# VERIFY STUDENT EMAIL
# --------------------------------------------------

def verify_student_email(db, student_id, submitted_code, secret_key):
    if not isinstance(submitted_code, str):
        return False

    submitted_code = submitted_code.strip()

    if not re.fullmatch(r"\d{6}", submitted_code):
        return False

    cursor = db.execute(
        """
        SELECT code_hash, expires_at, attempts
        FROM email_verification
        WHERE student_id = ?
        """,
        (student_id,)
    )

    verification = cursor.fetchone()

    if not verification:
        return False

    if verification["attempts"] >= 5:
        return False

    stored_expiry = datetime.fromisoformat(
        verification["expires_at"]
    )

    if stored_expiry.tzinfo is None:
        stored_expiry = stored_expiry.replace(
            tzinfo=timezone.utc
        )

    if utc_now() > stored_expiry:
        return False

    submitted_hash = hash_verification_code(
        submitted_code,
        secret_key
    )

    if not hmac.compare_digest(
        submitted_hash,
        verification["code_hash"]
    ):
        db.execute(
            """
            UPDATE email_verification
            SET attempts = attempts + 1
            WHERE student_id = ?
            """,
            (student_id,)
        )

        db.commit()
        return False

    db.execute(
        """
        UPDATE students
        SET is_verified = 1
        WHERE id = ?
        """,
        (student_id,)
    )

    db.execute(
        """
        DELETE FROM email_verification
        WHERE student_id = ?
        """,
        (student_id,)
    )

    db.commit()
    return True


# --------------------------------------------------
# STUDENT LOGIN
# --------------------------------------------------

def authenticate_student(db, email, password):
    email = normalize_email(email)

    cursor = db.execute(
        """
        SELECT id, email, password_hash, is_verified
        FROM students
        WHERE email = ?
        """,
        (email,)
    )

    student = cursor.fetchone()

    if not student:
        return None

    if not check_password_hash(
        student["password_hash"],
        password
    ):
        return None

    if not student["is_verified"]:
        return {
            "id": student["id"],
            "email": student["email"],
            "verified": False
        }

    return {
        "id": student["id"],
        "email": student["email"],
        "verified": True
    }


# --------------------------------------------------
# STUDENT RECORD STORAGE
# --------------------------------------------------

def save_student_record(db, student_id, record_type, record_data):
    import json

    if record_type not in ("gpa", "cgpa"):
        raise ValueError("Invalid record type.")

    serialized = json.dumps(record_data)

    now = timestamp_string(utc_now())

    db.execute(
        """
        INSERT INTO student_records
            (student_id, record_type, record_data, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id, record_type) DO UPDATE SET
            record_data = excluded.record_data,
            updated_at = excluded.updated_at
        """,
        (student_id, record_type, serialized, now)
    )

    db.commit()


def get_student_record(db, student_id, record_type):
    import json

    if record_type not in ("gpa", "cgpa"):
        return None

    cursor = db.execute(
        """
        SELECT record_data
        FROM student_records
        WHERE student_id = ?
        AND record_type = ?
        """,
        (student_id, record_type)
    )

    row = cursor.fetchone()

    if not row:
        return None

    return json.loads(row["record_data"])
