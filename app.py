from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import os
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CATEGORIES = {
    "Classroom": "Maintenance Department",
    "Hostel": "Hostel Department",
    "Laboratory": "Lab Department",
    "Library": "Library Department",
    "Canteen": "Canteen Department",
    "Sanitation": "Sanitation Department",
    "Electrical": "Electrical Department",
    "Plumbing": "Plumbing Department",
    "Maintenance": "Maintenance Department",
    "Wi-Fi/Internet": "IT Department",
    "Transport": "Transport Department",
    "Other": "General Administration"
}
DEPARTMENTS = sorted(set(CATEGORIES.values()))

# Demo staff accounts. The admin can assign by department; the system chooses
# an available staff member with the lowest active workload.
DEFAULT_STAFF = [
    ("electrical1", "Electrical Staff 1", "Electrical Department", "staff123"),
    ("electrical2", "Electrical Staff 2", "Electrical Department", "staff123"),
    ("plumbing1", "Plumbing Staff 1", "Plumbing Department", "staff123"),
    ("plumbing2", "Plumbing Staff 2", "Plumbing Department", "staff123"),
    ("maintenance1", "Maintenance Staff 1", "Maintenance Department", "staff123"),
    ("maintenance2", "Maintenance Staff 2", "Maintenance Department", "staff123"),
    ("hostel1", "Hostel Staff 1", "Hostel Department", "staff123"),
    ("hostel2", "Hostel Staff 2", "Hostel Department", "staff123"),
    ("lab1", "Lab Staff 1", "Lab Department", "staff123"),
    ("lab2", "Lab Staff 2", "Lab Department", "staff123"),
    ("library1", "Library Staff 1", "Library Department", "staff123"),
    ("library2", "Library Staff 2", "Library Department", "staff123"),
    ("canteen1", "Canteen Staff 1", "Canteen Department", "staff123"),
    ("canteen2", "Canteen Staff 2", "Canteen Department", "staff123"),
    ("sanitation1", "Sanitation Staff 1", "Sanitation Department", "staff123"),
    ("sanitation2", "Sanitation Staff 2", "Sanitation Department", "staff123"),
    ("it1", "IT Staff 1", "IT Department", "staff123"),
    ("it2", "IT Staff 2", "IT Department", "staff123"),
    ("transport1", "Transport Staff 1", "Transport Department", "staff123"),
    ("transport2", "Transport Staff 2", "Transport Department", "staff123"),
    ("general1", "General Admin Staff 1", "General Administration", "staff123"),
    ("general2", "General Admin Staff 2", "General Administration", "staff123"),
]


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def add_column_if_missing(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            register_number TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            photo TEXT,
            anonymous INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pending',
            assigned_to TEXT,
            admin_remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
        )
    """)

    # Safe upgrades for databases created by the earlier version of the app.
    add_column_if_missing(conn, "complaints", "assigned_department", "TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            password TEXT NOT NULL,
            on_leave INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER,
            complaint_id INTEGER,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
        )
    """)

    admin = conn.execute("SELECT id FROM admins WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )

    for username, name, department, password in DEFAULT_STAFF:
        exists = conn.execute("SELECT id FROM staff WHERE username = ?", (username,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO staff (username, name, department, password) VALUES (?, ?, ?, ?)",
                (username, name, department, generate_password_hash(password))
            )

    # Keep older complaints useful by filling their department from category.
    for category, department in CATEGORIES.items():
        conn.execute(
            "UPDATE complaints SET assigned_department = ? WHERE category = ? AND (assigned_department IS NULL OR assigned_department = '')",
            (department, category)
        )

    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def student_logged_in():
    return session.get("role") == "student"


def admin_logged_in():
    return session.get("role") == "admin"


def staff_logged_in():
    return session.get("role") == "staff"


def choose_available_staff(conn, department):
    """Return the available staff member with the lowest active workload."""
    return conn.execute("""
        SELECT staff.*, COUNT(complaints.id) AS active_count
        FROM staff
        LEFT JOIN complaints
          ON complaints.assigned_to = staff.name
         AND complaints.status = 'Assigned'
        WHERE staff.department = ? AND staff.on_leave = 0
        GROUP BY staff.id
        ORDER BY active_count ASC, staff.id ASC
        LIMIT 1
    """, (department,)).fetchone()


def create_staff_notification(conn, staff_id, complaint):
    message = (
        f"New complaint #{complaint['id']} assigned to you. "
        f"{complaint['category']} issue at {complaint['location']} "
        f"(Priority: {complaint['priority']})."
    )
    conn.execute("""
        INSERT INTO notifications (staff_id, complaint_id, message)
        VALUES (?, ?, ?)
    """, (staff_id, complaint["id"], message))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        register_number = request.form.get("register_number", "").strip()
        department = request.form.get("department", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not all([name, register_number, department, email, password]):
            flash("Please fill all fields.", "danger")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return redirect(url_for("register"))

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO students (name, register_number, department, email, password)
                VALUES (?, ?, ?, ?, ?)
            """, (name, register_number, department, email, generate_password_hash(password)))
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("student_login"))
        except sqlite3.IntegrityError:
            flash("Register number or email already exists.", "danger")
            return redirect(url_for("register"))
        finally:
            conn.close()
    return render_template("register.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        student = conn.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
        conn.close()
        if student and check_password_hash(student["password"], password):
            session.clear()
            session["role"] = "student"
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            flash("Welcome back!", "success")
            return redirect(url_for("student_dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("student_login.html")


@app.route("/student/dashboard")
def student_dashboard():
    if not student_logged_in():
        flash("Please login as a student.", "warning")
        return redirect(url_for("student_login"))
    conn = get_db()
    complaints = conn.execute("""
        SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC
    """, (session["student_id"],)).fetchall()
    conn.close()
    total = len(complaints)
    pending = sum(c["status"] == "Pending" for c in complaints)
    assigned = sum(c["status"] == "Assigned" for c in complaints)
    resolved = sum(c["status"] == "Resolved" for c in complaints)
    return render_template("student_dashboard.html", complaints=complaints, total=total,
                           pending=pending, assigned=assigned, resolved=resolved)


@app.route("/student/complaint/new", methods=["GET", "POST"])
def submit_complaint():
    if not student_logged_in():
        flash("Please login as a student.", "warning")
        return redirect(url_for("student_login"))
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "Medium")
        anonymous = 1 if request.form.get("anonymous") == "on" else 0
        photo = request.files.get("photo")
        priorities = {"Low", "Medium", "High"}

        if category not in CATEGORIES:
            flash("Please select a valid category.", "danger")
            return redirect(url_for("submit_complaint"))
        if not location or not description:
            flash("Location and description are required.", "danger")
            return redirect(url_for("submit_complaint"))
        if priority not in priorities:
            flash("Please select a valid priority.", "danger")
            return redirect(url_for("submit_complaint"))

        filename = None
        if photo and photo.filename:
            if not allowed_file(photo.filename):
                flash("Only PNG, JPG, JPEG, GIF and WEBP images are allowed.", "danger")
                return redirect(url_for("submit_complaint"))
            extension = photo.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{extension}"
            photo.save(os.path.join(UPLOAD_FOLDER, secure_filename(filename)))

        conn = get_db()
        conn.execute("""
            INSERT INTO complaints
            (student_id, category, location, description, priority, photo, anonymous, assigned_department)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (session["student_id"], category, location, description, priority,
              filename, anonymous, CATEGORIES[category]))
        conn.commit()
        conn.close()
        flash("Complaint submitted successfully.", "success")
        return redirect(url_for("student_dashboard"))
    return render_template("submit_complaint.html")


@app.route("/student/complaints")
def my_complaints():
    if not student_logged_in():
        flash("Please login as a student.", "warning")
        return redirect(url_for("student_login"))
    conn = get_db()
    complaints = conn.execute("SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC",
                              (session["student_id"],)).fetchall()
    conn.close()
    return render_template("my_complaints.html", complaints=complaints)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["role"] = "admin"
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin username or password.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_logged_in():
        flash("Please login as admin.", "warning")
        return redirect(url_for("admin_login"))
    conn = get_db()
    complaints = conn.execute("""
        SELECT complaints.*, students.name AS student_name,
               students.register_number, students.department, students.email
        FROM complaints
        LEFT JOIN students ON complaints.student_id = students.id
        ORDER BY complaints.created_at DESC
    """).fetchall()
    conn.close()
    total = len(complaints)
    pending = sum(c["status"] == "Pending" for c in complaints)
    assigned = sum(c["status"] == "Assigned" for c in complaints)
    resolved = sum(c["status"] == "Resolved" for c in complaints)
    return render_template("admin_dashboard.html", complaints=complaints, total=total,
                           pending=pending, assigned=assigned, resolved=resolved)


@app.route("/admin/complaint/<int:complaint_id>", methods=["GET", "POST"])
def complaint_details(complaint_id):
    if not admin_logged_in():
        flash("Please login as admin.", "warning")
        return redirect(url_for("admin_login"))

    conn = get_db()
    complaint = conn.execute("""
        SELECT complaints.*, students.name AS student_name,
               students.register_number, students.department, students.email
        FROM complaints
        LEFT JOIN students ON complaints.student_id = students.id
        WHERE complaints.id = ?
    """, (complaint_id,)).fetchone()

    if not complaint:
        conn.close()
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        department = request.form.get("assigned_department", "").strip()
        status = request.form.get("status", "Pending")
        remarks = request.form.get("admin_remarks", "").strip()

        if department not in DEPARTMENTS:
            department = CATEGORIES.get(complaint["category"], "General Administration")
        if status not in {"Pending", "Assigned", "Resolved"}:
            status = "Pending"

        assigned_staff = None
        if status == "Assigned":
            assigned_staff = choose_available_staff(conn, department)
            if not assigned_staff:
                conn.execute("""
                    UPDATE complaints
                    SET assigned_department = ?, assigned_to = NULL, status = 'Pending', admin_remarks = ?
                    WHERE id = ?
                """, (department, remarks, complaint_id))
                conn.commit()
                conn.close()
                flash(f"No available staff in {department}. Complaint remains Pending.", "warning")
                return redirect(url_for("complaint_details", complaint_id=complaint_id))

        if status == "Resolved":
            # Keep the current staff assignment when admin resolves the complaint.
            assigned_to = complaint["assigned_to"]
        else:
            assigned_to = assigned_staff["name"] if assigned_staff else None

        conn.execute("""
            UPDATE complaints
            SET assigned_department = ?, assigned_to = ?, status = ?, admin_remarks = ?
            WHERE id = ?
        """, (department, assigned_to, status, remarks, complaint_id))

        # Reload the complaint after the update so the notification has current details.
        updated = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
        if status == "Assigned" and assigned_staff:
            create_staff_notification(conn, assigned_staff["id"], updated)
            flash(f"Complaint assigned to {assigned_staff['name']} ({department}). Notification sent.", "success")
        else:
            flash("Complaint updated successfully.", "success")

        conn.commit()
        conn.close()
        return redirect(url_for("complaint_details", complaint_id=complaint_id))

    conn.close()
    return render_template("complaint_details.html", complaint=complaint, departments=DEPARTMENTS,
                           suggested_department=CATEGORIES.get(complaint["category"], "General Administration"))


@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        staff = conn.execute("SELECT * FROM staff WHERE username = ?", (username,)).fetchone()
        conn.close()
        if staff and check_password_hash(staff["password"], password):
            session.clear()
            session["role"] = "staff"
            session["staff_id"] = staff["id"]
            session["staff_name"] = staff["name"]
            session["staff_department"] = staff["department"]
            flash("Staff login successful.", "success")
            return redirect(url_for("staff_dashboard"))
        flash("Invalid staff username or password.", "danger")
    return render_template("staff_login.html")


@app.route("/staff/dashboard")
def staff_dashboard():
    if not staff_logged_in():
        flash("Please login as staff.", "warning")
        return redirect(url_for("staff_login"))
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff WHERE id = ?", (session["staff_id"],)).fetchone()
    complaints = conn.execute("""
        SELECT complaints.*, students.name AS student_name, students.register_number
        FROM complaints
        LEFT JOIN students ON complaints.student_id = students.id
        WHERE complaints.assigned_to = ?
        ORDER BY complaints.created_at DESC
    """, (staff["name"],)).fetchall()
    notifications = conn.execute("""
        SELECT notifications.*, complaints.category, complaints.location, complaints.priority
        FROM notifications
        LEFT JOIN complaints ON notifications.complaint_id = complaints.id
        WHERE notifications.staff_id = ?
        ORDER BY notifications.created_at DESC
        LIMIT 20
    """, (staff["id"],)).fetchall()
    conn.close()
    return render_template("staff_dashboard.html", staff=staff, complaints=complaints,
                           notifications=notifications)


@app.route("/staff/complaint/<int:complaint_id>", methods=["GET", "POST"])
def staff_complaint(complaint_id):
    if not staff_logged_in():
        flash("Please login as staff.", "warning")
        return redirect(url_for("staff_login"))
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff WHERE id = ?", (session["staff_id"],)).fetchone()
    complaint = conn.execute("""
        SELECT complaints.*, students.name AS student_name, students.register_number
        FROM complaints
        LEFT JOIN students ON complaints.student_id = students.id
        WHERE complaints.id = ? AND complaints.assigned_to = ?
    """, (complaint_id, staff["name"])).fetchone()
    if not complaint:
        conn.close()
        flash("Complaint is not assigned to you.", "danger")
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        status = request.form.get("status", "Assigned")
        remarks = request.form.get("admin_remarks", "").strip()
        if status not in {"Assigned", "Resolved"}:
            status = "Assigned"
        conn.execute("UPDATE complaints SET status = ?, admin_remarks = ? WHERE id = ?",
                     (status, remarks, complaint_id))
        conn.execute("UPDATE notifications SET is_read = 1 WHERE staff_id = ? AND complaint_id = ?",
                     (staff["id"], complaint_id))
        conn.commit()
        conn.close()
        flash("Complaint updated successfully.", "success")
        return redirect(url_for("staff_complaint", complaint_id=complaint_id))

    conn.close()
    return render_template("staff_complaint.html", complaint=complaint, staff=staff)


@app.route("/staff/notifications/read/<int:notification_id>")
def read_notification(notification_id):
    if not staff_logged_in():
        return redirect(url_for("staff_login"))
    conn = get_db()
    notification = conn.execute("SELECT * FROM notifications WHERE id = ? AND staff_id = ?",
                                 (notification_id, session["staff_id"])).fetchone()
    if notification:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        complaint_id = notification["complaint_id"]
        conn.close()
        return redirect(url_for("staff_complaint", complaint_id=complaint_id))
    conn.close()
    return redirect(url_for("staff_dashboard"))


@app.route("/staff/toggle-leave", methods=["POST"])
def toggle_staff_leave():
    if not staff_logged_in():
        flash("Please login as staff.", "warning")
        return redirect(url_for("staff_login"))
    conn = get_db()
    staff = conn.execute("SELECT * FROM staff WHERE id = ?", (session["staff_id"],)).fetchone()
    new_value = 0 if staff["on_leave"] else 1
    conn.execute("UPDATE staff SET on_leave = ? WHERE id = ?", (new_value, staff["id"]))
    conn.commit()
    conn.close()
    flash("Leave status updated.", "info")
    return redirect(url_for("staff_dashboard"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.errorhandler(413)
def file_too_large(error):
    flash("Photo is too large. Maximum size is 5 MB.", "danger")
    return redirect(url_for("submit_complaint"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
