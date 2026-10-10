import os
import hmac
import sqlite3
import uuid

from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from secrets import token_urlsafe

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


# ============================================================
# BASE PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# SQLite database
DATABASE = BASE_DIR / "campus_items.db"

# Public uploaded images
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

# Private student ID card images
PRIVATE_UPLOAD_DIR = BASE_DIR / "private" / "student_ids"


# ============================================================
# APPLICATION SETTINGS
# ============================================================

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

CATEGORIES = [
    "Electronics",
    "Accessories",
    "Books",
    "Clothing",
    "ID & Cards",
    "Other",
]


app = Flask(__name__)


# ------------------------------------------------------------
# Secret key
# ------------------------------------------------------------

app.config["SECRET_KEY"] = os.environ.get(
    "CAMPUS_SECRET_KEY",
    "local-demo-secret-change-before-deployment"
)


# ------------------------------------------------------------
# Upload limit
# ------------------------------------------------------------

app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024


# ------------------------------------------------------------
# Session security
# ------------------------------------------------------------

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Railway HTTPS
if os.environ.get("RAILWAY_ENVIRONMENT"):
    app.config["SESSION_COOKIE_SECURE"] = True
else:
    app.config["SESSION_COOKIE_SECURE"] = False


# ------------------------------------------------------------
# Admin password
# ------------------------------------------------------------

ADMIN_PASSWORD = os.environ.get(
    "CAMPUS_ADMIN_PASSWORD",
    "campusadmin"
)


# ------------------------------------------------------------
# Create required directories
# ------------------------------------------------------------

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    """
    Create a connection to SQLite database.
    """

    connection = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    # Enable foreign key support
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


@contextmanager
def db_session():
    """
    Safely open, commit and close database connection.
    """

    connection = connect_db()

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    with db_session() as db:

        # ----------------------------------------------------
        # ITEMS TABLE
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                title TEXT NOT NULL,

                description TEXT NOT NULL,

                category TEXT NOT NULL,

                kind TEXT NOT NULL
                    CHECK(kind IN ('lost', 'found')),

                location TEXT NOT NULL,

                event_date TEXT NOT NULL,

                contact TEXT NOT NULL,

                image TEXT,

                status TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open', 'resolved')),

                created_at TEXT NOT NULL
            )
            """
        )


        # ----------------------------------------------------
        # STUDENTS TABLE
        # ----------------------------------------------------

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                full_name TEXT NOT NULL,

                email TEXT NOT NULL
                    COLLATE NOCASE UNIQUE,

                password_hash TEXT NOT NULL,

                id_card_image TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'active', 'rejected')),

                created_at TEXT NOT NULL
            )
            """
        )


        # ----------------------------------------------------
        # Add owner_id to old databases
        # ----------------------------------------------------

        item_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(items)"
            ).fetchall()
        }

        if "owner_id" not in item_columns:

            db.execute(
                """
                ALTER TABLE items
                ADD COLUMN owner_id INTEGER
                REFERENCES students(id)
                """
            )


        # ----------------------------------------------------
        # Demo items
        # ----------------------------------------------------

        count = db.execute(
            "SELECT COUNT(*) FROM items"
        ).fetchone()[0]


        if count == 0:

            examples = [

                (
                    "Wireless earbuds",
                    "White charging case with a small blue sticker on the lid.",
                    "Electronics",
                    "found",
                    "Library, second floor",
                    "2026-09-26",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-26T13:20:00",
                ),

                (
                    "Blue water bottle",
                    "Tall insulated bottle, navy blue, initials may be on the base.",
                    "Accessories",
                    "lost",
                    "Engineering Block, Lab 204",
                    "2026-09-25",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-25T16:45:00",
                ),

                (
                    "Calculus textbook",
                    "Single-variable calculus, 8th edition. Name written inside the cover.",
                    "Books",
                    "found",
                    "Cafeteria, outdoor tables",
                    "2026-09-24",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-24T11:10:00",
                ),

                (
                    "Student ID card",
                    "Found near the north entrance. Please describe the card to verify ownership.",
                    "ID & Cards",
                    "found",
                    "North Gate",
                    "2026-09-23",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-23T09:05:00",
                ),

                (
                    "Black laptop sleeve",
                    "Lost a slim 14-inch sleeve with a small white tag inside.",
                    "Accessories",
                    "lost",
                    "Main Auditorium",
                    "2026-09-22",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-22T18:30:00",
                ),

                (
                    "Silver keyring",
                    "Three keys on a plain silver ring, one has a red cap.",
                    "Other",
                    "found",
                    "Sports Complex reception",
                    "2026-09-21",
                    "student@example.edu",
                    None,
                    "open",
                    "2026-09-21T14:15:00",
                ),
            ]


            db.executemany(
                """
                INSERT INTO items
                (
                    title,
                    description,
                    category,
                    kind,
                    location,
                    event_date,
                    contact,
                    image,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                examples,
            )


# ============================================================
# CSRF
# ============================================================

def auth_csrf_token():

    return session.setdefault(
        "csrf_token",
        token_urlsafe(32)
    )


def valid_csrf_token():

    submitted = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token", "")
    )

    stored = session.get("csrf_token", "")

    if not submitted or not stored:
        return False

    return hmac.compare_digest(
        stored,
        submitted
    )


# ============================================================
# CURRENT STUDENT
# ============================================================

def current_student():

    student_id = session.get("student_id")

    if not student_id:
        return None


    with db_session() as db:

        student = db.execute(
            """
            SELECT
                id,
                full_name,
                email,
                status
            FROM students
            WHERE id = ?
            """,
            (student_id,),
        ).fetchone()


    if student is None:

        session.pop("student_id", None)

        return None


    if student["status"] != "active":

        session.pop("student_id", None)

        return None


    return dict(student)


# ============================================================
# STUDENT LOGIN REQUIRED
# ============================================================

def active_student_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        student = current_student()

        if student is None:

            if request.path.startswith("/api/"):

                return jsonify(
                    error="Sign in with an approved campus account to continue."
                ), 401

            return redirect(
                url_for("student_login")
            )


        return view(
            student,
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# ADMIN LOGIN REQUIRED
# ============================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("is_admin"):

            return jsonify(
                error="Admin sign-in required."
            ), 401


        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# HOME PAGE
# ============================================================

@app.get("/")
def home():

    student = current_student()

    return render_template(
        "index.html",
        categories=CATEGORIES,
        student=student,
        csrf_token=(
            auth_csrf_token()
            if student
            else ""
        ),
    )


# ============================================================
# STUDENT REGISTRATION PAGE
# ============================================================

@app.get("/register")
def student_register_page():

    return render_template(
        "auth.html",
        mode="register",
        csrf_token=auth_csrf_token(),
    )


# ============================================================
# STUDENT REGISTRATION
# ============================================================

@app.post("/register")
def student_register():

    if not valid_csrf_token():

        flash(
            "Your registration page expired. Please try again.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    full_name = request.form.get(
        "full_name",
        ""
    ).strip()


    email = request.form.get(
        "email",
        ""
    ).strip().lower()


    password = request.form.get(
        "password",
        "")


    # --------------------------------------------------------
    # Name validation
    # --------------------------------------------------------

    if not full_name or len(full_name) > 100:

        flash(
            "Enter your name (up to 100 characters).",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    # --------------------------------------------------------
    # Email validation
    # --------------------------------------------------------

    if (
        "@" not in email
        or len(email) > 160
        or email.startswith("@")
        or email.endswith("@")
    ):

        flash(
            "Enter a valid campus email address.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    # --------------------------------------------------------
    # Campus domain
    # --------------------------------------------------------

    campus_domain = (
        os.environ.get(
            "CAMPUS_EMAIL_DOMAIN",
            ""
        )
        .strip()
        .lower()
        .lstrip("@")
    )


    if (
        campus_domain
        and email.rsplit("@", 1)[-1] != campus_domain
    ):

        flash(
            f"Use your @{campus_domain} campus email address.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    # --------------------------------------------------------
    # Password
    # --------------------------------------------------------

    if len(password) < 10:

        flash(
            "Choose a password with at least 10 characters.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    # --------------------------------------------------------
    # Student ID upload
    # --------------------------------------------------------

    upload = request.files.get("id_card")


    safe_name = secure_filename(
        upload.filename
        if upload
        else ""
    )


    extension = (
        safe_name.rsplit(".", 1)[-1].lower()
        if "." in safe_name
        else ""
    )


    if (
        not upload
        or not upload.filename
        or extension not in ALLOWED_EXTENSIONS
    ):

        flash(
            "Upload a clear JPG, PNG, or WebP photo of your campus ID card.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    # --------------------------------------------------------
    # Save student
    # --------------------------------------------------------

    with db_session() as db:

        duplicate = db.execute(
            """
            SELECT id
            FROM students
            WHERE email = ?
            """,
            (email,),
        ).fetchone()


        if duplicate:

            flash(
                "An account with that email already exists.",
                "error"
            )

            return redirect(
                url_for("student_register_page")
            )


        image_name = (
            f"{uuid.uuid4().hex}.{extension}"
        )


        upload.save(
            PRIVATE_UPLOAD_DIR / image_name
        )


        db.execute(
            """
            INSERT INTO students
            (
                full_name,
                email,
                password_hash,
                id_card_image,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                full_name,
                email,
                generate_password_hash(password),
                image_name,
                datetime.now().isoformat(
                    timespec="seconds"
                ),
            ),
        )


    flash(
        "Registration received. An admin must approve your campus ID before you can sign in.",
        "success"
    )


    return redirect(
        url_for("student_login")
    )


# ============================================================
# LOGIN PAGE
# ============================================================

@app.get("/login")
def student_login():

    return render_template(
        "auth.html",
        mode="login",
        csrf_token=auth_csrf_token(),
    )


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
def student_login_submit():

    if not valid_csrf_token():

        flash(
            "Your sign-in page expired. Please try again.",
            "error"
        )

        return redirect(
            url_for("student_login")
        )


    email = request.form.get(
        "email",
        ""
    ).strip().lower()


    password = request.form.get(
        "password",
        ""
    )


    with db_session() as db:

        student = db.execute(
            """
            SELECT *
            FROM students
            WHERE email = ?
            """,
            (email,),
        ).fetchone()


    # --------------------------------------------------------
    # Invalid login
    # --------------------------------------------------------

    if (
        student is None
        or not check_password_hash(
            student["password_hash"],
            password
        )
    ):

        flash(
            "Email or password is incorrect.",
            "error"
        )

        return redirect(
            url_for("student_login")
        )


    # --------------------------------------------------------
    # Pending
    # --------------------------------------------------------

    if student["status"] == "pending":

        flash(
            "Your campus ID is awaiting admin approval.",
            "pending"
        )

        return redirect(
            url_for("student_login")
        )


    # --------------------------------------------------------
    # Rejected
    # --------------------------------------------------------

    if student["status"] != "active":

        flash(
            "This registration was not approved. Contact your campus administrator.",
            "error"
        )

        return redirect(
            url_for("student_login")
        )


    # --------------------------------------------------------
    # Successful login
    # --------------------------------------------------------

    session.clear()

    session["student_id"] = student["id"]

    session["csrf_token"] = token_urlsafe(32)


    return redirect(
        url_for("student_dashboard")
    )


# ============================================================
# STUDENT LOGOUT
# ============================================================

@app.post("/student/logout")
def student_logout():

    if not valid_csrf_token():

        return (
            "Invalid security token.",
            400
        )


    session.clear()


    return redirect(
        url_for("home")
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@app.get("/student")
@active_student_required
def student_dashboard(student):

    with db_session() as db:

        items = db.execute(
            """
            SELECT *
            FROM items
            WHERE owner_id = ?
            ORDER BY created_at DESC
            """,
            (student["id"],),
        ).fetchall()


    return render_template(
        "student.html",
        student=student,
        items=[
            dict(row)
            for row in items
        ],
        csrf_token=auth_csrf_token(),
    )


# ============================================================
# ADMIN PAGE
# ============================================================

@app.get("/admin")
def admin_page():

    csrf_token = session.setdefault(
        "csrf_token",
        token_urlsafe(32)
    )


    return render_template(
        "admin.html",
        authenticated=session.get(
            "is_admin",
            False
        ),
        csrf_token=csrf_token,
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.post("/admin/login")
def admin_login():

    if not valid_csrf_token():

        flash(
            "Your sign-in page expired. Please try again.",
            "error"
        )

        return redirect(
            url_for("admin_page")
        )


    password = request.form.get(
        "password",
        ""
    )


    if not hmac.compare_digest(
        password,
        ADMIN_PASSWORD
    ):

        flash(
            "That password did not match.",
            "error"
        )

        return redirect(
            url_for("admin_page")
        )


    session.clear()

    session["is_admin"] = True

    session["csrf_token"] = token_urlsafe(32)


    return redirect(
        url_for("admin_page")
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.post("/admin/logout")
def admin_logout():

    if not valid_csrf_token():

        return jsonify(
            error="Invalid security token."
        ), 400


    session.clear()


    return redirect(
        url_for("admin_page")
    )


# ============================================================
# ADMIN - ITEMS
# ============================================================

@app.get("/api/admin/items")
@admin_required
def admin_items():

    with db_session() as db:

        rows = db.execute(
            """
            SELECT *
            FROM items
            ORDER BY created_at DESC
            """
        ).fetchall()


        counts = db.execute(
            """
            SELECT
                COUNT(*) total,
                SUM(status = 'open') open,
                SUM(status = 'resolved') resolved,
                SUM(kind = 'lost') lost,
                SUM(kind = 'found') found
            FROM items
            """
        ).fetchone()


    return jsonify(
        {
            "items": [
                dict(row)
                for row in rows
            ],

            "counts": {
                key: value or 0
                for key, value
                in dict(counts).items()
            },
        }
    )


# ============================================================
# ADMIN - STUDENTS
# ============================================================

@app.get("/api/admin/students")
@admin_required
def admin_students():

    with db_session() as db:

        rows = db.execute(
            """
            SELECT
                id,
                full_name,
                email,
                status,
                created_at
            FROM students
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 0
                    ELSE 1
                END,
                created_at DESC
            """
        ).fetchall()


        pending = db.execute(
            """
            SELECT COUNT(*)
            FROM students
            WHERE status = 'pending'
            """
        ).fetchone()[0]


    return jsonify(
        {
            "students": [
                dict(row)
                for row in rows
            ],
            "pending": pending,
        }
    )


# ============================================================
# ADMIN - VIEW STUDENT ID CARD
# ============================================================

@app.get(
    "/admin/students/<int:student_id>/id-card"
)
@admin_required
def admin_student_id_card(student_id):

    with db_session() as db:

        student = db.execute(
            """
            SELECT id_card_image
            FROM students
            WHERE id = ?
            """,
            (student_id,),
        ).fetchone()


    if student is None:

        return (
            "Student not found.",
            404
        )


    path = (
        PRIVATE_UPLOAD_DIR
        / student["id_card_image"]
    )


    if not path.is_file():

        return (
            "ID card image not found.",
            404
        )


    extension = path.suffix.lower()


    mimetype = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(
        extension,
        "application/octet-stream"
    )


    return app.response_class(
        path.read_bytes(),
        mimetype=mimetype,
        headers={
            "Cache-Control": "private, no-store"
        },
    )


# ============================================================
# ADMIN - APPROVE / REJECT STUDENT
# ============================================================

@app.post(
    "/api/admin/students/<int:student_id>/decision"
)
@admin_required
def admin_student_decision(student_id):

    if not valid_csrf_token():

        return jsonify(
            error="Invalid security token."
        ), 400


    data = request.get_json(
        silent=True
    ) or {}


    decision = data.get(
        "decision"
    )


    if decision not in {
        "approve",
        "reject"
    }:

        return jsonify(
            error="Choose approve or reject."
        ), 400


    status = (
        "active"
        if decision == "approve"
        else "rejected"
    )


    with db_session() as db:

        result = db.execute(
            """
            UPDATE students
            SET status = ?
            WHERE id = ?
            AND status = 'pending'
            """,
            (
                status,
                student_id
            ),
        )


    if result.rowcount == 0:

        return jsonify(
            error="This application is no longer pending."
        ), 404


    return jsonify(
        success=True,
        status=status
    )


# ============================================================
# ADMIN - ITEM STATUS
# ============================================================

@app.post(
    "/api/admin/items/<int:item_id>/status"
)
@admin_required
def admin_set_status(item_id):

    if not valid_csrf_token():

        return jsonify(
            error="Invalid security token."
        ), 400


    data = request.get_json(
        silent=True
    ) or {}


    status = data.get(
        "status"
    )


    if status not in {
        "open",
        "resolved"
    }:

        return jsonify(
            error="Choose a valid listing status."
        ), 400


    with db_session() as db:

        result = db.execute(
            """
            UPDATE items
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                item_id
            ),
        )


    if result.rowcount == 0:

        return jsonify(
            error="Listing not found."
        ), 404


    return jsonify(
        success=True
    )


# ============================================================
# PUBLIC - LIST ITEMS
# ============================================================

@app.get("/api/items")
def list_items():

    kind = request.args.get(
        "kind",
        "all"
    ).lower()


    category = request.args.get(
        "category",
        "all"
    )


    search = request.args.get(
        "q",
        ""
    ).strip()


    conditions = [
        "status = 'open'"
    ]


    values = []


    # --------------------------------------------------------
    # Lost / Found filter
    # --------------------------------------------------------

    if kind in {
        "lost",
        "found"
    }:

        conditions.append(
            "kind = ?"
        )

        values.append(
            kind
        )


    # --------------------------------------------------------
    # Category filter
    # --------------------------------------------------------

    if category in CATEGORIES:

        conditions.append(
            "category = ?"
        )

        values.append(
            category
        )


    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if search:

        conditions.append(
            """
            (
                title LIKE ?
                OR description LIKE ?
                OR location LIKE ?
            )
            """
        )


        values.extend(
            [
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
            ]
        )


    query = (
        "SELECT * FROM items WHERE "
        + " AND ".join(conditions)
        + " ORDER BY created_at DESC"
    )


    with db_session() as db:

        rows = db.execute(
            query,
            values
        ).fetchall()


        counts = db.execute(
            """
            SELECT
                COUNT(*) total,
                SUM(kind = 'lost') lost,
                SUM(kind = 'found') found
            FROM items
            WHERE status = 'open'
            """
        ).fetchone()


    return jsonify(
        {
            "items": [
                dict(row)
                for row in rows
            ],

            "counts": dict(counts),
        }
    )


# ============================================================
# CREATE LOST / FOUND ITEM
# ============================================================

@app.post("/api/items")
def create_item():

    student = current_student()


    if student is None:

        return jsonify(
            error="Sign in with an approved campus account before posting."
        ), 401


    # --------------------------------------------------------
    # Form data
    # --------------------------------------------------------

    data = request.form


    title = data.get(
        "title",
        ""
    ).strip()


    description = data.get(
        "description",
        ""
    ).strip()


    category = data.get(
        "category",
        ""
    )


    kind = data.get(
        "kind",
        ""
    )


    location = data.get(
        "location",
        ""
    ).strip()


    event_date = data.get(
        "event_date",
        ""
    )


    contact = student["email"]


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not title or len(title) > 90:

        return jsonify(
            error="Enter a title between 1 and 90 characters."
        ), 400


    if not description or len(description) > 1200:

        return jsonify(
            error="Add a description of up to 1,200 characters."
        ), 400


    if (
        category not in CATEGORIES
        or kind not in {
            "lost",
            "found"
        }
    ):

        return jsonify(
            error="Choose a valid type and category."
        ), 400


    if not location or len(location) > 120:

        return jsonify(
            error="Enter a campus location (up to 120 characters)."
        ), 400


    try:

        datetime.strptime(
            event_date,
            "%Y-%m-%d"
        )

    except ValueError:

        return jsonify(
            error="Choose the date you lost or found the item."
        ), 400


    # --------------------------------------------------------
    # Image
    # --------------------------------------------------------

    image_name = None


    upload = request.files.get(
        "image"
    )


    if upload and upload.filename:

        safe_name = secure_filename(
            upload.filename
        )


        extension = (
            safe_name.rsplit(".", 1)[-1].lower()
            if "." in safe_name
            else ""
        )


        if extension not in ALLOWED_EXTENSIONS:

            return jsonify(
                error="Image must be JPG, PNG, or WebP."
            ), 400


        image_name = (
            f"{uuid.uuid4().hex}.{extension}"
        )


        upload.save(
            UPLOAD_DIR / image_name
        )


    # --------------------------------------------------------
    # Database insert
    # --------------------------------------------------------

    with db_session() as db:

        cursor = db.execute(
            """
            INSERT INTO items
            (
                title,
                description,
                category,
                kind,
                location,
                event_date,
                contact,
                image,
                status,
                created_at,
                owner_id
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?,
                'open',
                ?, ?
            )
            """,
            (
                title,
                description,
                category,
                kind,
                location,
                event_date,
                contact,
                image_name,
                datetime.now().isoformat(
                    timespec="seconds"
                ),
                student["id"],
            ),
        )


        item_id = cursor.lastrowid


    return jsonify(
        {
            "id": item_id
        }
    ), 201


# ============================================================
# RESOLVE OWN ITEM
# ============================================================

@app.post(
    "/api/items/<int:item_id>/resolve"
)
def resolve_item(item_id):

    student = current_student()


    if student is None:

        return jsonify(
            error="Sign in with an approved campus account to update your listing."
        ), 401


    with db_session() as db:

        result = db.execute(
            """
            UPDATE items
            SET status = 'resolved'
            WHERE id = ?
            AND owner_id = ?
            AND status = 'open'
            """,
            (
                item_id,
                student["id"]
            ),
        )


    if result.rowcount == 0:

        return jsonify(
            error="This listing is no longer open."
        ), 404


    return jsonify(
        success=True
    )


# ============================================================
# ERROR: FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def file_too_large(_error):

    if request.path == "/register":

        flash(
            "The uploaded image must be smaller than 4 MB.",
            "error"
        )

        return redirect(
            url_for("student_register_page")
        )


    return jsonify(
        error="Image must be smaller than 4 MB."
    ), 413


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return jsonify(
        {
            "status": "ok",
            "application": "Campus Lost and Found Portal"
        }
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_db()


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
