import io
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from flask import Flask, Response, flash, redirect, render_template, request, url_for


app = Flask(__name__)
app.secret_key = "flask-course-demo-secret"

# Demo credentials for a classroom/local example.
VALID_USERNAME = "admin"
VALID_PASSWORD = "password123"
DATABASE_PATH = Path(__file__).with_name("students.db")
VALID_STATUSES = {"Active", "Pending", "Completed"}

SEED_STUDENTS = [
    ("Aiman Hakim", "aiman@example.com", "Python Basics", "Active"),
    ("Siti Nur", "siti@example.com", "Flask Web App", "Pending"),
    ("Daniel Tan", "daniel@example.com", "HTML and CSS", "Completed"),
]


def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = None

    try:
        connection = get_db_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                course TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Active', 'Pending', 'Completed'))
            )
            """
        )

        total_students = connection.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0]

        if total_students == 0:
            connection.executemany(
                """
                INSERT INTO students (name, email, course, status)
                VALUES (?, ?, ?, ?)
                """,
                SEED_STUDENTS,
            )

        connection.commit()
    except sqlite3.Error:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()


def get_students():
    connection = get_db_connection()

    try:
        students = connection.execute(
            """
            SELECT id, name, email, course, status
            FROM students
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    return students


def get_student_counts():
    connection = get_db_connection()

    try:
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_count
            FROM students
            """
        ).fetchone()
    finally:
        connection.close()

    return {
        "total_count": counts["total_count"] or 0,
        "active_count": counts["active_count"] or 0,
        "completed_count": counts["completed_count"] or 0,
    }


def get_dashboard_data():
    connection = get_db_connection()

    try:
        course_rows = connection.execute(
            """
            SELECT course, COUNT(*) AS total
            FROM students
            GROUP BY course
            ORDER BY total DESC, course
            """
        ).fetchall()
        status_rows = connection.execute(
            """
            SELECT status, COUNT(*) AS total
            FROM students
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()
        student_rows = connection.execute(
            """
            SELECT id, name
            FROM students
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    return {
        "course_rows": course_rows,
        "status_rows": status_rows,
        "student_rows": student_rows,
    }


def read_student_form():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    status = request.form.get("status", "").strip()

    if not name or not email or not course or not status:
        raise ValueError("Please complete all student fields.")

    if status not in VALID_STATUSES:
        raise ValueError("Please choose a valid status.")

    return {
        "name": name,
        "email": email,
        "course": course,
        "status": status,
    }


@app.route("/", methods=["GET", "POST"])
def login():
    message = ""
    message_type = ""
    login_success = False

    try:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                raise ValueError("Please enter both username and password.")

            if username == VALID_USERNAME and password == VALID_PASSWORD:
                login_success = True
            else:
                raise PermissionError("Invalid username or password.")

    except ValueError as error:
        message = str(error)
        message_type = "warning"
    except PermissionError as error:
        message = str(error)
        message_type = "error"
    except Exception:
        message = "Something went wrong. Please try again."
        message_type = "error"
    else:
        if login_success:
            return redirect(url_for("home"))
    finally:
        # This block always runs, even if validation raises an error.
        app.logger.info("Login request handled.")

    return render_template(
        "login.html",
        message=message,
        message_type=message_type,
    )
@app.route("/home", methods=["GET"])
def home():
    try:
        students = get_students()
        counts = get_student_counts()
    except sqlite3.Error:
        app.logger.exception("Read students failed.")
        flash("Could not load records from the database.", "error")
        students = []
        counts = {
            "total_count": 0,
            "active_count": 0,
            "completed_count": 0,
        }
    finally:
        app.logger.info("Home request handled.")

    return render_template(
        "home.html",
        students=students,
        total_count=counts["total_count"],
        active_count=counts["active_count"],
        completed_count=counts["completed_count"],
    )


@app.route("/dashboard", methods=["GET"])
def dashboard():
    try:
        counts = get_student_counts()
    except sqlite3.Error:
        app.logger.exception("Read dashboard counts failed.")
        flash("Could not load dashboard data from SQLite.", "error")
        counts = {
            "total_count": 0,
            "active_count": 0,
            "completed_count": 0,
        }
    finally:
        app.logger.info("Dashboard page request handled.")

    return render_template(
        "dashboard.html",
        total_count=counts["total_count"],
        active_count=counts["active_count"],
        completed_count=counts["completed_count"],
    )


@app.route("/dashboard-chart.png", methods=["GET"])
def dashboard_chart():
    chart_buffer = io.BytesIO()
    fig = None

    try:
        data = get_dashboard_data()
        course_rows = data["course_rows"]
        status_rows = data["status_rows"]
        student_rows = data["student_rows"]

        course_labels = [row["course"] for row in course_rows]
        course_totals = [row["total"] for row in course_rows]
        status_labels = [row["status"] for row in status_rows]
        status_totals = [row["total"] for row in status_rows]
        student_ids = [row["id"] for row in student_rows]
        cumulative_totals = list(range(1, len(student_rows) + 1))

        # Create a 2x2 dashboard
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("Student Database Dashboard", fontsize=20, fontweight="bold")

        if not student_rows:
            for axis in axes.flat:
                axis.text(
                    0.5,
                    0.5,
                    "No database records yet",
                    ha="center",
                    va="center",
                    fontsize=13,
                )
                axis.set_axis_off()
        else:
            # Chart 1: Bar - Course registration count from SQLite
            axes[0, 0].bar(
                course_labels,
                course_totals,
                color="#3498db",
            )
            axes[0, 0].set_title("Students by Course")
            axes[0, 0].set_ylabel("Students")
            axes[0, 0].tick_params(axis="x", rotation=25)

            # Chart 2: Line - Record growth by SQLite student ID
            axes[0, 1].plot(
                student_ids,
                cumulative_totals,
                marker="o",
                color="#2ecc71",
            )
            axes[0, 1].set_title("Database Record Growth")
            axes[0, 1].set_xlabel("Student ID")
            axes[0, 1].set_ylabel("Total Records")
            axes[0, 1].grid(True, alpha=0.3)

            # Chart 3: Pie - Student status distribution from SQLite
            axes[1, 0].pie(
                status_totals,
                labels=status_labels,
                autopct="%1.0f%%",
                colors=["#2ecc71", "#3498db", "#f39c12"],
            )
            axes[1, 0].set_title("Students by Status")

            # Chart 4: Horizontal bar - Status count from SQLite
            axes[1, 1].barh(
                status_labels,
                status_totals,
                color="#9b59b6",
            )
            axes[1, 1].set_title("Status Count")
            axes[1, 1].set_xlabel("Students")

        fig.tight_layout()
        fig.savefig(chart_buffer, format="png", dpi=140)
        chart_buffer.seek(0)
    except Exception:
        app.logger.exception("Student dashboard chart failed.")
        return Response(
            "Could not generate student dashboard chart.",
            status=500,
            mimetype="text/plain",
        )
    else:
        return Response(chart_buffer.getvalue(), mimetype="image/png")
    finally:
        if fig:
            plt.close(fig)
        chart_buffer.close()


@app.route("/students", methods=["POST"])
def create_student():
    connection = None

    try:
        student_data = read_student_form()
        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO students (name, email, course, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                student_data["name"],
                student_data["email"],
                student_data["course"],
                student_data["status"],
            ),
        )
        connection.commit()
    except ValueError as error:
        flash(str(error), "warning")
    except sqlite3.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Create student database error.")
        flash("Could not save the record to SQLite. Please try again.", "error")
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Create student failed.")
        flash("Could not create the record. Please try again.", "error")
    else:
        flash("Student record saved to SQLite successfully.", "success")
    finally:
        if connection:
            connection.close()
        app.logger.info("Create request handled.")

    return redirect(url_for("home"))


@app.route("/students/<int:student_id>/update", methods=["POST"])
def update_student(student_id):
    connection = None

    try:
        student_data = read_student_form()
        connection = get_db_connection()
        result = connection.execute(
            """
            UPDATE students
            SET name = ?, email = ?, course = ?, status = ?
            WHERE id = ?
            """,
            (
                student_data["name"],
                student_data["email"],
                student_data["course"],
                student_data["status"],
                student_id,
            ),
        )

        if result.rowcount == 0:
            raise LookupError("Student record was not found.")

        connection.commit()
    except ValueError as error:
        flash(str(error), "warning")
    except LookupError as error:
        if connection:
            connection.rollback()
        flash(str(error), "error")
    except sqlite3.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Update student database error.")
        flash("Could not update the SQLite record. Please try again.", "error")
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Update student failed.")
        flash("Could not update the record. Please try again.", "error")
    else:
        flash("SQLite record updated successfully.", "success")
    finally:
        if connection:
            connection.close()
        app.logger.info("Update request handled.")

    return redirect(url_for("home"))


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    connection = None

    try:
        connection = get_db_connection()
        result = connection.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,),
        )

        if result.rowcount == 0:
            raise LookupError("Student record was not found.")

        connection.commit()
    except LookupError as error:
        if connection:
            connection.rollback()
        flash(str(error), "error")
    except sqlite3.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Delete student database error.")
        flash("Could not delete the SQLite record. Please try again.", "error")
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Delete student failed.")
        flash("Could not delete the record. Please try again.", "error")
    else:
        flash("SQLite record deleted successfully.", "success")
    finally:
        if connection:
            connection.close()
        app.logger.info("Delete request handled.")

    return redirect(url_for("home"))

@app.errorhandler(404)
def page_not_found(error):
    return render_template(
        "login.html",
        message="Page not found. Please log in from here.",
        message_type="warning",
    ), 404


@app.errorhandler(500)
def server_error(error):
    return render_template(
        "login.html",
        message="Server error handled gracefully. Please try again.",
        message_type="error",
    ), 500



init_db()

if __name__ == "__main__":
    app.run(debug=True)
