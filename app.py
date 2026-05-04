# Importing Required Libraries
import os
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
import heapq


import oracledb  # Oracle DB driver (replaces sqlite3)
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
except ImportError:
    print("Warning: reportlab not installed. PDF features will not work.")

# # ==================== FLASK APP SETUP ====================

# app = Flask(__name__)
# app.secret_key = "supersecretkey"

# # Database setup
# basedir = os.path.abspath(os.path.dirname(__file__))
# instance_path = os.path.join(basedir, 'instance')
# os.makedirs(instance_path, exist_ok=True)

# # Upload folder setup
# UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
# PATIENT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'patients')
# os.makedirs(PATIENT_UPLOAD_FOLDER, exist_ok=True)

# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# db_path = os.path.join(instance_path, 'clinic.db')
# app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# db = SQLAlchemy(app)

# ==================== FLASK APP SETUP ====================

# ==================== FLASK APP SETUP ====================

app = Flask(__name__)

# 🔒 SECURITY: Use environment variables for production
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')

# Database setup
basedir = os.path.abspath(os.path.dirname(__file__))

# Upload folder setup
UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
PATIENT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'patients')
os.makedirs(PATIENT_UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# ==================== ORACLE DATABASE CONNECTION ====================
# Change username, password below to match your Oracle setup
# Default Oracle XE service name is XEPDB1
# ==================== ORACLE DATABASE CONNECTION ====================
# ⚠️  CHANGE THESE to match what you created in SQL Developer:
#     CREATE USER clinic_user IDENTIFIED BY clinic123;
#     GRANT CONNECT, RESOURCE, CREATE SESSION TO clinic_user;
#     GRANT UNLIMITED TABLESPACE TO clinic_user;
ORACLE_USER     = os.environ.get('ORACLE_USER', 'clinic_user')
ORACLE_PASSWORD = os.environ.get('ORACLE_PASSWORD', 'clinic123')
ORACLE_HOST     = os.environ.get('ORACLE_HOST', 'localhost')
ORACLE_PORT     = os.environ.get('ORACLE_PORT', '1521')
ORACLE_SERVICE  = os.environ.get('ORACLE_SERVICE', 'XEPDB1')

database_url = os.environ.get(
    'DATABASE_URL',
    f'oracle+oracledb://{ORACLE_USER}:{ORACLE_PASSWORD}@{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}'
)

# Thin mode — no Oracle Instant Client needed
oracledb.defaults.fetch_lobs = False

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'thick_mode': False}

db = SQLAlchemy(app)




def admin_required():
    if 'admin_id'  not in session:
        return False
    return True


def generate_15min_slots(start_time_str, end_time_str):
    """
    Generate 15-minute slots from a time range.
    Start time IS included, end time is NOT included.
    e.g. '09:00 AM' → '11:00 AM' gives:
    ['09:00 AM','09:15 AM','09:30 AM','09:45 AM',
     '10:00 AM','10:15 AM','10:30 AM','10:45 AM']
    """
    slots = []
    try:
        start   = datetime.strptime(start_time_str.strip(), "%I:%M %p")
        end     = datetime.strptime(end_time_str.strip(),   "%I:%M %p")
        current = start
        while current < end:
            slots.append(current.strftime("%I:%M %p"))
            current += timedelta(minutes=15)
    except Exception as e:
        print(f"generate_15min_slots error: {e}")
    return slots


def generate_time_options(start_hour=8, end_hour=22, interval=30):
    """
    Generate dropdown time options for shift pickers.
    Clinic hours: 8:00 AM to 10:00 PM, 30-min intervals.
    """
    options = []
    current = datetime.strptime(f"{start_hour:02d}:00", "%H:%M")
    end     = datetime.strptime(f"{end_hour:02d}:00",   "%H:%M")
    while current <= end:
        options.append(current.strftime("%I:%M %p"))
        current += timedelta(minutes=interval)
    return options


def get_available_slots(doctor_id, appointment_date):
    """
    Get all free 15-min slots for a doctor on a given date.
    Loops through all shifts for that day, generates slots,
    then removes already-booked ones.
    """
    day_name = appointment_date.strftime('%A')

    # Get all shifts for this doctor on this day, ordered by shift_number
    shifts = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id,
        day_of_week=day_name
    ).order_by(DoctorAvailability.shift_number).all()

    if not shifts:
        return []

    # Generate all slots across all shifts
    all_slots = []
    for shift in shifts:
        all_slots.extend(generate_15min_slots(shift.start_time, shift.end_time))

    # Get already booked slots for this date
    booked = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status.in_(['Pending', 'Scheduled'])
    ).all()
    booked_slots = [b.time_slot for b in booked]

    # Return only free slots
    free_slots = [s for s in all_slots if s not in booked_slots]
    return free_slots


@app.route("/get_doctor_times/<int:doctor_id>/<date>")
def get_doctor_times(doctor_id, date):
    try:
        appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
        day_name         = appointment_date.strftime("%A")

        shifts = DoctorAvailability.query.filter_by(
            doctor_id=doctor_id,
            day_of_week=day_name
        ).order_by(DoctorAvailability.shift_number).all()

        if not shifts:
            return jsonify({
                "working":   False,
                "available": [],
                "booked":    [],
                "shifts":    [],
                "message":   f"Doctor is not available on {day_name}"
            })

        all_slots = []
        shifts_info = []
        for shift in shifts:
            slot_list = generate_15min_slots(shift.start_time, shift.end_time)
            all_slots.extend(slot_list)
            shifts_info.append({
                "shift":      shift.shift_number,
                "start":      shift.start_time,
                "end":        shift.end_time,
                "slot_count": len(slot_list)
            })

        booked_rows = db.session.execute(text("""
            SELECT time_slot
            FROM   VW_BOOKED_SLOTS
            WHERE  doctor_id        = :did
              AND  appointment_date = TO_DATE(:dt, 'YYYY-MM-DD')
        """), {'did': doctor_id, 'dt': date}).all()

        booked_slots = [r[0] for r in booked_rows]
        free_slots   = [s for s in all_slots if s not in booked_slots]

        return jsonify({
            "working":   True,
            "available": free_slots,
            "booked":    booked_slots,
            "shifts":    shifts_info,
            "day":       day_name
        })

    except Exception as e:
        print(f"get_doctor_times error: {e}")
        return jsonify({
            "working":   False,
            "available": [],
            "booked":    [],
            "shifts":    [],
            "message":   "Error loading slots"
        }), 500

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login_admin'))

    today = datetime.now().date()
    day_name = datetime.now().strftime('%A')  # e.g. Monday

    # ── Stat cards ────────────────────────────────────────────────
    # 1. Upcoming appointments (Scheduled/Pending from today onwards)
    upcoming_count = db.session.execute(text("""
        SELECT COUNT(*) FROM appointment
        WHERE status IN ('Scheduled','Pending')
        AND appointment_date >= :today
    """), {'today': today}).scalar() or 0

    # 2. Total doctors
    total_doctors = db.session.execute(text(
        "SELECT COUNT(*) FROM doctor"
    )).scalar() or 0

    # 3. Patients seen today (completed appointments today)
    patients_today = db.session.execute(text("""
        SELECT COUNT(DISTINCT patient_id) FROM appointment
        WHERE appointment_date = :today
        AND status != 'Cancelled'
    """), {'today': today}).scalar() or 0

    # 4. Total patients registered
    total_patients = db.session.execute(text(
        "SELECT COUNT(*) FROM patient"
    )).scalar() or 0

    # ── Upcoming appointments list (next 10) ──────────────────────
    upcoming_appointments = db.session.execute(text("""
        SELECT * FROM VW_APPOINTMENT_FULL
        WHERE status IN ('Scheduled','Pending')
        AND appointment_date >= :today
        ORDER BY appointment_date ASC, appointment_id ASC
        FETCH FIRST 10 ROWS ONLY
    """), {'today': today}).mappings().all()

    # ── Doctors with schedule today ───────────────────────────────
    available_doctors = db.session.execute(text("""
        SELECT d.id, d.name, d.specialization, d.consultation_fee,
               da.start_time, da.end_time,
               (SELECT COUNT(*) FROM appointment a
                WHERE a.doctor_id = d.id
                AND a.appointment_date = :today
                AND a.status IN ('Scheduled','Pending')) AS todays_appts
        FROM doctor d
        JOIN doctor_availability da ON da.doctor_id = d.id
        WHERE da.day_of_week = :day_name
        ORDER BY d.name
    """), {'today': today, 'day_name': day_name}).mappings().all()

    # ── Today's patients (completed or scheduled today) ───────────
    todays_patients = db.session.execute(text("""
        SELECT DISTINCT patient_name, patient_age, patient_gender,
                        doctor_name, time_slot, status, priority
        FROM VW_APPOINTMENT_FULL
        WHERE appointment_date = :today
        ORDER BY time_slot ASC
    """), {'today': today}).mappings().all()

    return render_template(
        'admin/AdminDashboard.html',
        upcoming_count        = upcoming_count,
        total_doctors         = total_doctors,
        patients_today        = patients_today,
        total_patients        = total_patients,
        upcoming_appointments = upcoming_appointments,
        available_doctors     = available_doctors,
        todays_patients       = todays_patients,
        today                 = today,
        day_name              = day_name
    )


from datetime import datetime, timedelta

def generate_time_slots(start="09:00", end="17:00", interval=60):
    slots = []

    start_time = datetime.strptime(start, "%H:%M")
    end_time = datetime.strptime(end, "%H:%M")

    while start_time < end_time:
        slots.append(start_time.strftime("%I:%M %p"))
        start_time += timedelta(minutes=interval)

    return slots

@app.route('/admin/appointments')
def admin_appointments():
    if 'admin_id' not in session:
        return redirect(url_for('login_admin'))

    filter_patient_id = request.args.get('patient_id', '').strip()
    filter_doctor_id  = request.args.get('doctor_id',  '').strip()
    filter_date       = request.args.get('date',        '').strip()
    filter_status     = request.args.get('status',      '').strip()

    sql = text("""
        SELECT *
        FROM   VW_APPOINTMENT_FULL
        WHERE  (:patient_id IS NULL OR patient_id       = :patient_id)
          AND  (:doctor_id  IS NULL OR doctor_id        = :doctor_id)
          AND  (:appt_date  IS NULL OR appointment_date = TO_DATE(:appt_date, 'YYYY-MM-DD'))
          AND  (:status     IS NULL OR UPPER(status)    = UPPER(:status))
        ORDER BY appointment_date DESC, appointment_id DESC
    """)

    appointments = db.session.execute(sql, {
        'patient_id': int(filter_patient_id) if filter_patient_id else None,
        'doctor_id':  int(filter_doctor_id)  if filter_doctor_id  else None,
        'appt_date':  filter_date  or None,
        'status':     filter_status or None,
    }).mappings().all()

    patients = db.session.execute(
        text("SELECT id, name FROM patient ORDER BY name")
    ).mappings().all()

    doctors = db.session.execute(
        text("SELECT id, name, specialization FROM doctor ORDER BY name")
    ).mappings().all()

    return render_template(
        'admin/admin_appointments.html',
        appointments      = appointments,
        patients          = patients,
        doctors           = doctors,
        filter_patient_id = filter_patient_id,
        filter_doctor_id  = filter_doctor_id,
        filter_date       = filter_date,
        filter_status     = filter_status,
        total_count       = len(appointments)
    )

# -------------------------------
# LOAD APPOINTMENT PAGE
# -------------------------------




# -------------------------------
# FETCH PATIENT DETAILS
# -------------------------------
@app.route("/get_patient/<int:pid>")
def get_patient(pid):
    patient = Patient.query.get(pid)
    if patient:
        return jsonify({
            'id': patient.id, 'name': patient.name, 'age': patient.age,
            'gender': patient.gender, 'cnic': patient.cnic, 'email': patient.email,
            'contact': patient.contact, 'address': patient.address,
            'blood_group': patient.blood_group, 'patient_type': patient.patient_type,
        })
    return jsonify({})


# -------------------------------
# FETCH DOCTOR DETAILS
# -------------------------------
@app.route("/get_doctor/<int:did>")
def get_doctor(did):
    doctor = Doctor.query.get(did)
    if doctor:
        return jsonify({
            'id': doctor.id, 'name': doctor.name, 'age': doctor.age,
            'gender': doctor.gender, 'cnic': doctor.cnic, 'email': doctor.email,
            'contact': doctor.contact, 'specialization': doctor.specialization,
            'qualification': doctor.qualification, 'experience_years': doctor.experience_years,
            'license_number': doctor.license_number, 'current_hospital': doctor.current_hospital,
            'consultation_fee': doctor.consultation_fee,
        })
    return jsonify({})


# -------------------------------
# INSERT APPOINTMENT
# -------------------------------
@app.route("/add_appointment", methods=["POST"])
def add_appointment():
    patient_id   = int(request.form["patient_id"])
    doctor_id    = int(request.form["doctor_id"])
    appt_date    = datetime.strptime(request.form["appointment_date"], "%Y-%m-%d").date()
    time_slot    = request.form["time_slot"]
    reason       = request.form["reason"]
    priority     = request.form.get("priority", "normal")

    result = call_procedure(
        'SP_BOOK_APPOINTMENT',
        [patient_id, doctor_id, appt_date, time_slot, reason, priority],
        [oracledb.NUMBER, oracledb.STRING, oracledb.NUMBER]
    )
    code, msg = int(result[0]), result[1]

    if code == 0:
        flash("Appointment Added Successfully", "success")
    elif code == 1:
        flash(msg, "warning")
    else:
        flash(msg, "danger")

    return redirect(url_for("admin_appointments"))


@app.route("/admin/appointments/complete/<int:appointment_id>")
def complete_appointment_admin(appointment_id):
    result = call_procedure(
        'SP_COMPLETE_APPOINTMENT',
        [appointment_id, 0],
        [oracledb.NUMBER, oracledb.STRING]
    )
    code, msg = int(result[0]), result[1]
    flash(msg, 'success' if code == 0 else 'danger')
    return redirect(url_for("admin_appointments"))

@app.route("/admin/appointments/update_status", methods=["POST"])
def update_appointment_status():
    appointment_id = int(request.form["appointment_id"])
    new_status     = request.form["status"]

    result = call_procedure(
        'SP_UPDATE_APPOINTMENT_STATUS',
        [appointment_id, new_status],
        [oracledb.NUMBER, oracledb.STRING]
    )
    code, msg = int(result[0]), result[1]
    flash(msg, 'success' if code == 0 else 'danger')
    return redirect(url_for("admin_appointments"))

@app.route("/admin/appointments/delete/<int:appointment_id>")
def delete_appointment(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appt)
    db.session.commit()
    flash("Appointment deleted!")
    return redirect(url_for("admin_appointments"))

@app.route("/admin/appointments/edit/<int:appointment_id>", methods=["POST"])
def edit_appointment(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)

    patient_id       = request.form.get("patient_id_hidden")
    doctor_id        = request.form.get("doctor_id_hidden")
    appointment_date = request.form.get("appointment_date")
    time_slot        = request.form.get("time_slot")
    priority         = request.form.get("priority")
    reason           = request.form.get("reason")

    appt.patient_id       = int(patient_id)
    appt.doctor_id        = int(doctor_id)
    appt.appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    appt.time_slot        = time_slot
    appt.priority         = priority
    appt.reason           = reason

    db.session.commit()
    flash("Appointment Updated Successfully", "success")
    return redirect(url_for("admin_appointments"))

@app.route("/admin/patients")
def admin_patients():

    if 'admin_id'  not in session:
        return redirect(url_for('login_admin'))

    name = request.args.get("name")
    age = request.args.get("age")
    date = request.args.get("date")
    patient_type = request.args.get("patient_type")

    query = Patient.query

    if name:
        query = query.filter(Patient.name.ilike(f"%{name}%"))
    if age:
        query = query.filter(Patient.age == int(age))
    if date:
        filter_date = datetime.strptime(date, "%Y-%m-%d").date()
        query = query.filter(db.func.trunc(Patient.created_at) == filter_date)
    if patient_type:
        query = query.filter(Patient.patient_type == patient_type)

    patients_orm = query.all()
    patients = [{
        'id': p.id, 'name': p.name, 'age': p.age, 'gender': p.gender,
        'cnic': p.cnic, 'email': p.email, 'contact': p.contact,
        'patient_type': p.patient_type, 'created_at': p.created_at,
    } for p in patients_orm]

    return render_template(
        "admin/admin_patients.html",
        patients=patients
    )


# -------------------------------
# ADD PATIENT
# -------------------------------
@app.route("/admin/patient/add", methods=["POST"])
def add_patient():
    if 'admin_id' not in session:
        return redirect(url_for('login_admin'))

    name = request.form["name"]
    age = request.form["age"]
    gender = request.form["gender"]
    cnic = request.form["cnic"]
    email = request.form["email"]
    contact = request.form["contact"]

    # Walk-in patient
    password = "pass1234"
    patient_type = "Walk-in"

    try:
        new_patient = Patient(
            name=name,
            age=int(age),
            gender=gender,
            cnic=cnic,
            email=email,
            password=password,
            contact=contact,
            patient_type=patient_type
        )
        db.session.add(new_patient)
        db.session.commit()
        flash("Walk-in patient added successfully!")
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding patient: {e}", "danger")

    return redirect(url_for("admin_patients"))


# -------------------------------
# EDIT PATIENT
# -------------------------------
@app.route("/admin/patient/edit/<int:patient_id>", methods=["POST"])
def update_patient(patient_id):
    if 'admin_id'  not in session:
        return redirect(url_for('login_admin'))

    name = request.form.get("name")
    age = request.form.get("age")
    gender = request.form.get("gender")
    cnic = request.form.get("cnic")
    email = request.form.get("email")
    contact = request.form.get("contact")

    try:
        patient = Patient.query.get_or_404(patient_id)
        patient.name    = name
        patient.age     = int(age)
        patient.gender  = gender
        patient.cnic    = cnic
        patient.email   = email
        patient.contact = contact
        db.session.commit()
        flash("Patient updated successfully!")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating patient: {e}")

    return redirect(url_for("admin_patients"))


# -------------------------------
# DELETE PATIENT
# -------------------------------
@app.route("/admin/patient/delete/<int:patient_id>")
def delete_patient(patient_id):

    if 'admin_id'  not in session:
        return redirect(url_for('login_admin'))

    try:
        patient = Patient.query.get_or_404(patient_id)
        # The Patient model has cascade='all, delete-orphan' on appointments,
        # so related appointment rows are removed automatically.
        db.session.delete(patient)
        db.session.commit()
        flash("Patient deleted successfully!")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting patient: {e}", "danger")

    return redirect(url_for("admin_patients"))



# -------------------------------
# DOCTOR MANAGEMENT
# -------------------------------

# ==================== ORACLE DB CONNECTION HELPER ====================
# This replaces the old sqlite3.connect() approach.
# Uses oracledb to get a raw connection when needed for raw SQL queries.
def get_db_connection():
    conn = oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=f'{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE}'
    )
    conn.autocommit = False
    return conn

def call_procedure(proc_name, in_params, out_types):
    """
    Generic helper to call any Oracle stored procedure.
    proc_name  : string, e.g. 'SP_BOOK_APPOINTMENT'
    in_params  : list of input values in order
    out_types  : list of oracledb types for OUT params
    Returns a list of OUT parameter values in the same order as out_types.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        out_vars = [cur.var(t) for t in out_types]
        cur.callproc(proc_name, in_params + out_vars)
        return [v.getvalue() for v in out_vars]
    finally:
        cur.close()
        conn.close()


# ------------------- Admin: View Doctors -------------------
@app.route("/admin/doctors")
def admin_doctors():
    name_filter           = request.args.get("name",           "").strip()
    specialization_filter = request.args.get("specialization", "").strip()

    sql = text("""
        SELECT *
        FROM   VW_DOCTOR_SUMMARY
        WHERE  (:name IS NULL OR LOWER(name)           LIKE LOWER('%'||:name||'%'))
          AND  (:spec IS NULL OR LOWER(specialization) LIKE LOWER('%'||:spec||'%'))
        ORDER BY id
    """)

    doctor_list = db.session.execute(sql, {
        'name': name_filter           or None,
        'spec': specialization_filter or None,
    }).mappings().all()

    return render_template("admin/admin_doctors.html", doctors=doctor_list)

# ------------------- Admin: Add Doctor -------------------

import oracledb
from flask import flash

@app.route("/admin/doctor/add", methods=["POST"])
def add_doctor():
    if 'admin_id' not in session:
        return redirect(url_for("login"))

    data = request.form
    default_password = "pass1234"

    try:
        new_doctor = Doctor(
            name=data['name'],
            age=int(data['age']),
            gender=data['gender'],
            cnic=data['cnic'],
            email=data['email'],
            contact=data['contact'],
            specialization=data['specialization'],
            qualification=data['qualification'],
            experience_years=int(data['experience_years']),
            license_number=data['license_number'],
            current_hospital=data['current_hospital'],
            consultation_fee=float(data['consultation_fee']),
            password=default_password
        )
        db.session.add(new_doctor)
        db.session.commit()
        flash("Doctor added successfully!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding doctor: {e}", "danger")

    return redirect(url_for("admin_doctors"))


# ------------------- Admin: Edit Doctor -------------------

@app.route("/admin/doctor/edit/<int:id>", methods=["POST"])
def edit_doctor(id):
    if 'admin_id' not in session:
        return redirect(url_for("login"))

    data = request.form
    try:
        doctor = Doctor.query.get_or_404(id)
        doctor.name             = data['name']
        doctor.age              = int(data['age'])
        doctor.gender           = data['gender']
        doctor.contact          = data['contact']
        doctor.specialization   = data['specialization']
        doctor.qualification    = data['qualification']
        doctor.experience_years = int(data['experience_years'])
        doctor.current_hospital = data['current_hospital']
        doctor.consultation_fee = float(data['consultation_fee'])
        db.session.commit()
        flash("Doctor updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating doctor: {e}", "danger")

    return redirect(url_for("admin_doctors"))

# ------------------- Admin: Delete Doctor -------------------

@app.route("/admin/doctor/delete/<int:id>", methods=["GET"])
def delete_doctor(id):
    if 'admin_id' not in session:
        return redirect(url_for("login"))

    try:
        doctor = Doctor.query.get_or_404(id)
        db.session.delete(doctor)
        db.session.commit()
        flash("Doctor deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting doctor: {e}", "danger")

    return redirect(url_for("admin_doctors"))

@app.route('/admin/patients/<int:patient_id>')
def admin_patient_details(patient_id):
    return render_template('admin/admin_patient_details.html')

@app.route('/admin/payments')
def admin_payments():
    return render_template('admin/admin_payments.html')

@app.route('/admin/rooms')
def admin_rooms():
    return render_template('admin/admin_rooms.html')




# app = Flask(__name__)
# app.secret_key = "supersecretkey"

# # Database setup
# basedir = os.path.abspath(os.path.dirname(__file__))

# # Upload folder setup
# UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
# PATIENT_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'patients')
# os.makedirs(PATIENT_UPLOAD_FOLDER, exist_ok=True)

# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# # 🔹 IMPORTANT: Point directly to the edited DB file
# db_path = os.path.join(basedir, 'clinic.db')  # changed from instance_path
# app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# db = SQLAlchemy(app)


# ==================== DATABASE MODELS ====================
# Oracle does NOT auto-increment IDs like SQLite.
# We use db.Sequence() which creates a named Oracle SEQUENCE object.
# SQLAlchemy calls NEXTVAL on the sequence before each INSERT automatically.

class Doctor(db.Model):
    __tablename__ = 'doctor'
    id = db.Column(db.Integer, db.Sequence('doctor_id_seq', start=1, increment=1), primary_key=True)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    cnic = db.Column(db.String(20), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(100))
    contact = db.Column(db.String(20))
    specialization = db.Column(db.String(100))
    qualification = db.Column(db.String(100))
    experience_years = db.Column(db.Integer)
    license_number = db.Column(db.String(50))
    current_hospital = db.Column(db.String(100))
    consultation_fee = db.Column(db.Float, default=2000.0)

    # Relationships
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    medical_records = db.relationship('MedicalRecord', backref='doctor', lazy=True)
    prescriptions = db.relationship('Prescription', backref='doctor', lazy=True)


class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'
    id           = db.Column(db.Integer, db.Sequence('doc_avail_id_seq', start=1, increment=1), primary_key=True)
    doctor_id    = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    day_of_week  = db.Column(db.String(20),  nullable=False)  # e.g. 'Monday'
    shift_number = db.Column(db.Integer,     default=1)        # 1, 2, 3...
    start_time   = db.Column(db.String(10),  nullable=False)   # e.g. '09:00 AM'
    end_time     = db.Column(db.String(10),  nullable=False)   # e.g. '01:00 PM'
    created_at   = db.Column(db.DateTime,    default=datetime.utcnow)

    doctor = db.relationship('Doctor', backref='availabilities')


class Patient(db.Model):
    __tablename__ = 'patient'
    id = db.Column(db.Integer, db.Sequence('patient_id_seq', start=1, increment=1), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    cnic = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200))
    blood_group = db.Column(db.String(5))
    profile_picture = db.Column(db.String(200))
    emergency_contact = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    patient_type = db.Column(db.String(20))

    # Relationships
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    medical_records = db.relationship('MedicalRecord', backref='patient', lazy=True, cascade='all, delete-orphan')
    vitals = db.relationship('Vitals', backref='patient', lazy=True, cascade='all, delete-orphan')
    prescriptions = db.relationship('Prescription', backref='patient', lazy=True, cascade='all, delete-orphan')


class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, db.Sequence('admin_id_seq', start=1, increment=1), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    cnic = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    position = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(50))
    department = db.Column(db.String(50))


class Appointment(db.Model):
    __tablename__ = 'appointment'
    id = db.Column(db.Integer, db.Sequence('appointment_id_seq', start=1, increment=1), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='scheduled')
    completed_at = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), default='normal')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MedicalRecord(db.Model):
    __tablename__ = 'medical_record'
    id = db.Column(db.Integer, db.Sequence('med_record_id_seq', start=1, increment=1), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    visit_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    diagnosis = db.Column(db.Text, nullable=False)
    treatment = db.Column(db.Text)
    prescription = db.Column(db.Text)
    vitals = db.Column(db.Text)  # JSON string
    notes = db.Column(db.Text)
    follow_up_date = db.Column(db.Date)


class Vitals(db.Model):
    __tablename__ = 'vitals'
    id = db.Column(db.Integer, db.Sequence('vitals_id_seq', start=1, increment=1), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    heart_rate = db.Column(db.Integer)
    blood_pressure_systolic = db.Column(db.Integer)
    blood_pressure_diastolic = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    oxygen_saturation = db.Column(db.Integer)
    weight = db.Column(db.Float)
    height = db.Column(db.Float)
    bmi = db.Column(db.Float)
    notes = db.Column(db.Text)


class Prescription(db.Model):
    __tablename__ = 'prescription'
    id = db.Column(db.Integer, db.Sequence('prescription_id_seq', start=1, increment=1), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    medication = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text)
    refills = db.Column(db.Integer, default=0)
    active = db.Column(db.SmallInteger, default=1)  # Oracle: 1=True, 0=False

# ==================== HELPER FUNCTIONS ====================

def clear_sessions():
    """Clear all login sessions"""
    session.pop('admin', None)
    session.pop('doctor', None)
    session.pop('patient', None)
    session.pop('patient_id', None)
    session.pop('user_type', None)

def patient_login_required(f):
    """Decorator to require patient login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'patient' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login_patient'))
        return f(*args, **kwargs)
    return decorated_function

def calculate_bmi(weight, height):
    """Calculate BMI from weight (kg) and height (cm)"""
    if weight and height and height > 0:
        height_m = height / 100
        return round(weight / (height_m ** 2), 2)
    return None

def check_vital_alerts(vitals):
    """Check if any vitals are in abnormal range"""
    alerts = []
    
    if vitals.heart_rate:
        if vitals.heart_rate < 60:
            alerts.append(('Heart Rate', 'Low', vitals.heart_rate))
        elif vitals.heart_rate > 100:
            alerts.append(('Heart Rate', 'High', vitals.heart_rate))
    
    if vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic:
        if vitals.blood_pressure_systolic > 140 or vitals.blood_pressure_diastolic > 90:
            alerts.append(('Blood Pressure', 'High', f"{vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}"))
        elif vitals.blood_pressure_systolic < 90 or vitals.blood_pressure_diastolic < 60:
            alerts.append(('Blood Pressure', 'Low', f"{vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic}"))
    
    if vitals.temperature:
        if vitals.temperature > 100.4:
            alerts.append(('Temperature', 'Fever', vitals.temperature))
        elif vitals.temperature < 97:
            alerts.append(('Temperature', 'Low', vitals.temperature))
    
    if vitals.oxygen_saturation:
        if vitals.oxygen_saturation < 95:
            alerts.append(('Oxygen Saturation', 'Low', vitals.oxygen_saturation))
    
    return alerts

# ==================== EXISTING ROUTES (Keep as is) ====================

@app.route('/')
def home():
    return render_template('index.html')

# Patient Signup (KEEP ORIGINAL)
@app.route('/signup/patient', methods=['GET', 'POST'])
def signup_patient():
    clear_sessions()
    if request.method == 'POST':
        try:
            patient = Patient(
                name=request.form['name'],
                age=request.form['age'],
                gender=request.form['gender'],
                cnic=request.form['cnic'],
                email=request.form['email'],
                password=request.form['password'],  # In production, use hashing
                contact=request.form['contact'],
                patient_type = "Registered"
            )
            db.session.add(patient)
            db.session.commit()
            flash("Patient account created successfully!", "success")
            return redirect(url_for('login_patient'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating account: {str(e)}", "error")
    return render_template('PatientSignIn.html')

# Doctor Signup (KEEP ORIGINAL)
@app.route('/signup/doctor', methods=['GET', 'POST'])
def signup_doctor():
    clear_sessions()
    if request.method == 'POST':
        try:
            doctor = Doctor(
                name=request.form['name'],
                age=request.form['age'],
                gender=request.form['gender'],
                cnic=request.form['cnic'],
                email=request.form['email'],
                password=request.form['password'],
                contact=request.form['contact'],
                specialization=request.form['specialization'],
                qualification=request.form['qualification'],
                experience_years=request.form['experience_years'],
                license_number=request.form['license_number'],
                current_hospital=request.form['current_hospital'],
            )
            db.session.add(doctor)
            db.session.commit()
            flash("Doctor account created successfully!", "success")
            return redirect(url_for('login_doctor'))
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            if 'ORA-00001' in error_msg:
                flash("An account with this email or CNIC already exists.", "error")
            else:
                flash(f"Error creating account: {error_msg}", "error")

# Admin Signup (KEEP ORIGINAL)
from werkzeug.security import generate_password_hash

@app.route("/admin/signup", methods=["GET", "POST"])
def signup_admin():

    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        gender = request.form["gender"]
        cnic = request.form["cnic"]
        position = request.form["position"]
        email = request.form["email"]
        contact = request.form["contact"]
        title = request.form["title"]
        department = request.form["department"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Password match check
        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("signup_admin"))

        try:
            new_admin = Admin(
                name=name,
                age=int(age),
                gender=gender,
                cnic=cnic,
                email=email,
                password=password,
                contact=contact,
                position=position,
                title=title,
                department=department
            )
            db.session.add(new_admin)
            db.session.commit()
            flash("Admin account created successfully", "success")
            return redirect(url_for("login_admin"))

        except Exception as e:
            db.session.rollback()
            print("ERROR:", e)
            flash(str(e), "danger")

    return render_template("ADMINSIGNIN.html")

# Patient Login (ENHANCED)
@app.route('/login/patient', methods=['GET','POST'])
def login_patient():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        patient = Patient.query.filter_by(email=email, password=password).first()
        
        if patient:
            session.pop('doctor', None)
            session.pop('admin', None)
            session['patient'] = patient.name
            session['patient_id'] = patient.id
            session['user_type'] = 'patient'
            
            flash(f"Welcome, {patient.name}!", "success")
            return redirect(url_for('patient_dashboard'))
        else:
            flash("Invalid email or password", "error")
    
    return render_template('PatientLogin.html')

# Doctor Login (KEEP ORIGINAL)
@app.route('/login/doctor', methods=['GET', 'POST'])
def login_doctor():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        doctor = Doctor.query.filter_by(email=email, password=password).first()
        
        if doctor:
            # Clear other roles
            session.pop('patient', None)
            session.pop('admin', None)
            
            # Store doctor's name in session
            session['doctor'] = doctor.name
            
            # Welcome message
            flash(f"Welcome, Dr. {doctor.name}!", "doctor")
            
            # Redirect to doctor dashboard
            return redirect(url_for('dashboard_doctor'))
        else:
            flash("Invalid email or password", "doctor")
    
    return render_template('DoctorLogin.html')

# Admin Login (KEEP ORIGINAL)
from werkzeug.security import check_password_hash

@app.route("/admin/login", methods=["GET", "POST"])
def login_admin():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        admin = Admin.query.filter_by(email=email).first()

        if admin and admin.password == password:
            session["admin_id"]   = admin.id
            session["admin_name"] = admin.name
            flash("Login successful", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("AdminLogin.html")

# Old Dashboards (KEEP for backward compatibility)
@app.route('/dashboard/patient')
def dashboard_patient_old():
    if 'patient' not in session:
        return redirect(url_for('login_patient'))
    return redirect(url_for('patient_dashboard'))

# @app.route('/dashboard/doctor')
# def dashboard_doctor():
#     if 'doctor' not in session:
#         return redirect(url_for('login_doctor'))
    
#     doctor = Doctor.query.filter_by(name=session['doctor']).first()
    
#     if not doctor:
#         flash("Session expired. Please login again.", "danger")
#         return redirect(url_for('login_doctor'))
    
#     return render_template('DoctorDashboard.html', doctor=doctor)


@app.route('/logout')
def logout():
    clear_sessions()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('home'))

# ==================== NEW PATIENT PORTAL ROUTES ====================

# UPDATED PATIENT ROUTES WITH PROPER DATABASE INTEGRATION
# Add these routes to your app.py, replacing the existing patient routes

# ==================== PATIENT PORTAL ROUTES (FIXED) ====================

@app.route('/patient/dashboard')
@patient_login_required
def patient_dashboard():
    patient_id = session.get('patient_id')
    patient = Patient.query.get_or_404(patient_id)
    
    # Get upcoming appointments
    today = datetime.now().date()
    upcoming_appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.appointment_date >= today,
        Appointment.status == 'scheduled'
    ).order_by(Appointment.appointment_date, Appointment.time_slot).limit(5).all()
    
    # Get recent medical records
    recent_records = MedicalRecord.query.filter_by(
        patient_id=patient_id
    ).order_by(MedicalRecord.visit_date.desc()).limit(5).all()
    
    # Get latest vitals
    latest_vitals = Vitals.query.filter_by(
        patient_id=patient_id
    ).order_by(Vitals.date.desc()).first()
    
    # Get active prescriptions
    active_prescriptions = Prescription.query.filter_by(
        patient_id=patient_id,
        active=1
    ).order_by(Prescription.date.desc()).limit(5).all()
    
    # Check for vital alerts
    vital_alerts = []
    if latest_vitals:
        vital_alerts = check_vital_alerts(latest_vitals)
    
    return render_template('patient/dashboard.html',
                         patient=patient,
                         upcoming_appointments=upcoming_appointments,
                         recent_records=recent_records,
                         latest_vitals=latest_vitals,
                         active_prescriptions=active_prescriptions,
                         vital_alerts=vital_alerts,
                         now=datetime.now())

@app.route('/patient/book-appointment', methods=['GET', 'POST'])
@patient_login_required
def book_appointment():
    patient_id = session.get('patient_id')

    if request.method == 'POST':
        try:
            doctor_id = int(request.form.get('doctor_id'))
            date_str  = request.form.get('date')
            time_slot = request.form.get('time')
            reason    = request.form.get('reason')
            priority  = request.form.get('priority', 'normal')

            if not all([doctor_id, date_str, time_slot, reason]):
                flash('Please fill in all required fields.', 'error')
                return redirect(url_for('book_appointment'))

            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            result = call_procedure(
                'SP_BOOK_APPOINTMENT',
                [patient_id, doctor_id, appt_date, time_slot, reason, priority],
                [oracledb.NUMBER, oracledb.STRING, oracledb.NUMBER]
            )
            code, msg = int(result[0]), result[1]

            if code == 0:
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('view_appointments'))
            elif code == 1:
                flash(msg, 'warning')
            else:
                flash(msg, 'error')

        except Exception as e:
            flash(f'Error booking appointment: {str(e)}', 'error')

    doctors         = Doctor.query.all()
    specializations = db.session.query(Doctor.specialization).distinct().all()
    specializations = [s[0] for s in specializations if s[0]]

    return render_template('patient/book-appointment.html',
        doctors         = doctors,
        specializations = specializations,
        today           = datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/patient/appointments')
@patient_login_required
def view_appointments():
    patient_id = session.get('patient_id')

    upcoming = db.session.execute(text("""
        SELECT *
        FROM   VW_PATIENT_APPOINTMENTS
        WHERE  patient_id    = :pid
          AND  appt_category = 'upcoming'
        ORDER BY appointment_date ASC, time_slot ASC
    """), {'pid': patient_id}).mappings().all()

    past = db.session.execute(text("""
        SELECT *
        FROM   VW_PATIENT_APPOINTMENTS
        WHERE  patient_id    = :pid
          AND  appt_category = 'past'
        ORDER BY appointment_date DESC, time_slot DESC
    """), {'pid': patient_id}).mappings().all()

    return render_template('patient/view-appointments.html',
        upcoming_appointments = upcoming,
        past_appointments     = past
    )

@app.route('/patient/appointment/<int:appointment_id>/cancel', methods=['POST'])
@patient_login_required
def cancel_appointment(appointment_id):
    patient_id = session.get('patient_id')

    result = call_procedure(
        'SP_CANCEL_APPOINTMENT',
        [appointment_id, patient_id],
        [oracledb.NUMBER, oracledb.STRING]
    )
    code, msg = int(result[0]), result[1]
    flash(msg, 'success' if code == 0 else 'error')
    return redirect(url_for('view_appointments'))

@app.route('/patient/medical-records')
@patient_login_required
def medical_records():
    patient_id = session.get('patient_id')
    
    # Get all medical records for this patient
    records = MedicalRecord.query.filter_by(
        patient_id=patient_id
    ).order_by(MedicalRecord.visit_date.desc()).all()
    
    return render_template('patient/medical-records.html', records=records)

@app.route('/patient/prescriptions')
@patient_login_required
def prescriptions():
    patient_id = session.get('patient_id')
    
    # Get active prescriptions
    active = Prescription.query.filter_by(
        patient_id=patient_id,
        active=1
    ).order_by(Prescription.date.desc()).all()
    
    # Get past prescriptions
    past = Prescription.query.filter_by(
        patient_id=patient_id,
        active=0
    ).order_by(Prescription.date.desc()).all()
    
    return render_template('patient/prescriptions.html',
                         active_prescriptions=active,
                         past_prescriptions=past)

@app.route('/patient/vitals', methods=['GET', 'POST'])
@patient_login_required
def patient_vitals():
    patient_id = session.get('patient_id')
    
    if request.method == 'POST':
        try:
            # Get form data
            weight = float(request.form.get('weight')) if request.form.get('weight') else None
            height = float(request.form.get('height')) if request.form.get('height') else None
            
            # Calculate BMI if both weight and height are provided
            bmi = calculate_bmi(weight, height) if weight and height else None
            
            # Create new vitals record
            vitals = Vitals(
                patient_id=patient_id,
                date=datetime.utcnow(),
                heart_rate=int(request.form.get('heart_rate')) if request.form.get('heart_rate') else None,
                blood_pressure_systolic=int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None,
                blood_pressure_diastolic=int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None,
                temperature=float(request.form.get('temperature')) if request.form.get('temperature') else None,
                oxygen_saturation=int(request.form.get('oxygen_saturation')) if request.form.get('oxygen_saturation') else None,
                weight=weight,
                height=height,
                bmi=bmi,
                notes=request.form.get('notes')
            )
            
            db.session.add(vitals)
            db.session.commit()
            
            # Check for alerts
            alerts = check_vital_alerts(vitals)
            if alerts:
                alert_msg = "Warning: " + ", ".join([f"{a[0]} is {a[1]}" for a in alerts])
                flash(alert_msg, 'warning')
            else:
                flash('Vitals recorded successfully!', 'success')
            
            return redirect(url_for('patient_vitals'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording vitals: {str(e)}', 'error')
            print(f"Vitals recording error: {str(e)}")  # Debug logging
    
    # GET request - show vitals form and history
    all_vitals = Vitals.query.filter_by(
        patient_id=patient_id
    ).order_by(Vitals.date.desc()).all()
    
    return render_template('patient/vitals.html', vitals_list=all_vitals)

@app.route('/patient/profile', methods=['GET', 'POST'])
@patient_login_required
def patient_profile():
    patient_id = session.get('patient_id')
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        try:
            # Update basic information
            patient.name = request.form.get('name')
            patient.age = int(request.form.get('age'))
            patient.gender = request.form.get('gender')
            patient.contact = request.form.get('contact')
            patient.address = request.form.get('address')
            patient.blood_group = request.form.get('blood_group')
            patient.emergency_contact = request.form.get('emergency_contact')
            
            # Handle profile picture upload
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    filename = secure_filename(f"patient_{patient_id}_{file.filename}")
                    filepath = os.path.join(PATIENT_UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    patient.profile_picture = filename
            
            # Change password if provided
            if request.form.get('new_password'):
                patient.password = request.form.get('new_password')
            
            # Update session name if changed
            if patient.name != session['patient']:
                session['patient'] = patient.name
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('patient_profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            print(f"Profile update error: {str(e)}")  # Debug logging
    
    return render_template('patient/profile.html', patient=patient)

# ==================== API ROUTES ====================

# ==================== PATIENT API ROUTES ====================
# Add these API routes to your app.py

@app.route('/api/doctors/available')
@patient_login_required
def available_doctors():
    date_str = request.args.get('date')
    specialization = request.args.get('specialization')
    
    query = Doctor.query
    
    if specialization:
        query = query.filter_by(specialization=specialization)
    
    doctors = query.all()
    
    result = []
    for doctor in doctors:
        booked_slots = []
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                appointments = Appointment.query.filter_by(
                    doctor_id=doctor.id,
                    appointment_date=date,
                    status='scheduled'
                ).all()
                booked_slots = [a.time_slot for a in appointments]  # Use time_slot here
            except ValueError:
                pass
        
        result.append({
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization,
            'qualification': doctor.qualification,
            'experience_years': doctor.experience_years,
            'consultation_fee': doctor.consultation_fee,
            'booked_slots': booked_slots
        })
    
    return jsonify(result)

def check_appointment_fields():
    """Check what fields exist in the Appointment model"""
    try:
        appointments = Appointment.query.limit(1).all()
        if appointments:
            apt = appointments[0]
            print(f"✅ Appointment fields:")
            print(f"   - appointment_date: {hasattr(apt, 'appointment_date')}")
            print(f"   - time_slot: {hasattr(apt, 'time_slot')}")
            print(f"   - date: {hasattr(apt, 'date')}")
            print(f"   - time: {hasattr(apt, 'time')}")
        else:
            print("ℹ️ No appointments found in database")
    except Exception as e:
        print(f"❌ Error checking appointments: {e}")

# # Call this in your main block
# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#         check_appointment_fields()
#         init_sample_data()
#     app.run(debug=True)

@app.route('/api/patient/vitals')
@patient_login_required
def vitals_api():
    """Get patient vitals data for charts"""
    patient_id = session.get('patient_id')
    days = request.args.get('days', 30, type=int)
    
    start_date = datetime.now() - timedelta(days=days)
    vitals = Vitals.query.filter(
        Vitals.patient_id == patient_id,
        Vitals.date >= start_date
    ).order_by(Vitals.date).all()
    
    data = {
        'dates': [],
        'heart_rate': [],
        'bp_systolic': [],
        'bp_diastolic': [],
        'temperature': [],
        'oxygen_saturation': [],
        'weight': [],
        'bmi': []
    }
    
    for v in vitals:
        data['dates'].append(v.date.strftime('%Y-%m-%d'))
        data['heart_rate'].append(v.heart_rate)
        data['bp_systolic'].append(v.blood_pressure_systolic)
        data['bp_diastolic'].append(v.blood_pressure_diastolic)
        data['temperature'].append(v.temperature)
        data['oxygen_saturation'].append(v.oxygen_saturation)
        data['weight'].append(v.weight)
        data['bmi'].append(v.bmi)
    
    return jsonify(data)

@app.route('/api/patient/appointments')
@patient_login_required
def appointments_api():
    """Get patient appointments for priority queue display"""
    patient_id = session.get('patient_id')
    
    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        status='Scheduled'
    ).order_by(Appointment.appointment_date, Appointment.time_slot).all()
    
    data = []
    priority_order = {'emergency': 1, 'urgent': 2, 'normal': 3}
    
    for a in appointments:
        data.append({
            'id': a.id,
            'doctor': a.doctor.name,
            'date': a.appointment_date.strftime('%Y-%m-%d'),
            'time': a.time_slot,
            'priority': a.priority,
            'priority_value': priority_order.get(a.priority, 3),
            'reason': a.reason
        })
    
    # Sort by date first, then by priority
    data.sort(key=lambda x: (x['date'], x['priority_value'], x['time']))
    
    return jsonify(data)

# ==================== PDF GENERATION ROUTES ====================

@app.route('/patient/download-medical-summary')
@patient_login_required
def download_medical_summary():
    """Generate and download a PDF summary of medical records"""
    try:
        patient_id = session.get('patient_id')
        patient = Patient.query.get_or_404(patient_id)
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Header
        p.setFont("Helvetica-Bold", 20)
        p.drawString(1*inch, height - 1*inch, "Medical Summary Report")
        
        # Patient Info
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, height - 1.5*inch, "Patient Information")
        p.setFont("Helvetica", 10)
        y = height - 1.8*inch
        p.drawString(1*inch, y, f"Name: {patient.name}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Age: {patient.age} | Gender: {patient.gender}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Blood Group: {patient.blood_group or 'N/A'}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Contact: {patient.contact}")
        
        # Recent Records
        y -= 0.5*inch
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, y, "Recent Medical Records")
        p.setFont("Helvetica", 9)
        
        records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(
            MedicalRecord.visit_date.desc()
        ).limit(10).all()
        
        y -= 0.3*inch
        for record in records:
            if y < 2*inch:  # Start new page if running out of space
                p.showPage()
                y = height - 1*inch
            
            p.drawString(1*inch, y, f"Date: {record.visit_date.strftime('%Y-%m-%d')}")
            y -= 0.15*inch
            p.drawString(1*inch, y, f"Diagnosis: {record.diagnosis[:60]}")
            y -= 0.15*inch
            p.drawString(1*inch, y, f"Doctor: Dr. {record.doctor.name}")
            y -= 0.3*inch
        
        p.save()
        buffer.seek(0)
        
        return send_file(buffer, as_attachment=True, download_name='medical_summary.pdf',
                        mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('patient_dashboard'))

@app.route('/patient/download-prescription/<int:prescription_id>')
@patient_login_required
def download_prescription(prescription_id):
    """Generate and download a PDF prescription"""
    try:
        patient_id = session.get('patient_id')
        prescription = Prescription.query.filter_by(
            id=prescription_id,
            patient_id=patient_id
        ).first_or_404()
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Header
        p.setFont("Helvetica-Bold", 18)
        p.drawString(1*inch, height - 1*inch, "Prescription")
        
        # Doctor Info
        p.setFont("Helvetica-Bold", 11)
        p.drawString(1*inch, height - 1.5*inch, f"Dr. {prescription.doctor.name}")
        p.setFont("Helvetica", 9)
        p.drawString(1*inch, height - 1.7*inch, f"{prescription.doctor.specialization}")
        p.drawString(1*inch, height - 1.9*inch, f"License: {prescription.doctor.license_number}")
        
        # Patient Info
        p.setFont("Helvetica-Bold", 11)
        p.drawString(1*inch, height - 2.3*inch, "Patient Information")
        p.setFont("Helvetica", 9)
        p.drawString(1*inch, height - 2.5*inch, f"Name: {prescription.patient.name}")
        p.drawString(1*inch, height - 2.7*inch, f"Age: {prescription.patient.age}")
        p.drawString(1*inch, height - 2.9*inch, f"Date: {prescription.date.strftime('%Y-%m-%d')}")
        
        # Prescription Details
        p.setFont("Helvetica-Bold", 12)
        p.drawString(1*inch, height - 3.4*inch, "Medication")
        p.setFont("Helvetica", 10)
        y = height - 3.7*inch
        p.drawString(1*inch, y, f"Medication: {prescription.medication}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Dosage: {prescription.dosage}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Frequency: {prescription.frequency}")
        y -= 0.2*inch
        p.drawString(1*inch, y, f"Duration: {prescription.duration}")
        
        if prescription.instructions:
            y -= 0.3*inch
            p.setFont("Helvetica-Bold", 10)
            p.drawString(1*inch, y, "Instructions:")
            p.setFont("Helvetica", 9)
            y -= 0.2*inch
            # Word wrap instructions
            instructions = prescription.instructions[:200]
            p.drawString(1*inch, y, instructions)
        
        p.save()
        buffer.seek(0)
        
        return send_file(buffer, as_attachment=True, 
                        download_name=f'prescription_{prescription_id}.pdf',
                        mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('prescriptions'))

# ==================== DATABASE INITIALIZATION ====================



#               DOCTOR DASHBOARD

@app.route('/dashboard/doctor')
def dashboard_doctor():
    if 'doctor' not in session:
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    if not doctor:
        flash("Session expired. Please login again.", "danger")
        return redirect(url_for('login_doctor'))

    day_name = datetime.now().strftime('%A')

    stats = db.session.execute(
        text("SELECT * FROM VW_DOCTOR_DAILY_STATS WHERE doctor_id = :id"),
        {'id': doctor.id}
    ).mappings().first()

    todays_appointments = db.session.execute(text("""
        SELECT *
        FROM   VW_APPOINTMENT_FULL
        WHERE  doctor_id        = :id
          AND  appointment_date = TRUNC(SYSDATE)
          AND  UPPER(status)    = 'SCHEDULED'
        ORDER BY time_slot
    """), {'id': doctor.id}).mappings().all()

    todays_schedule = DoctorAvailability.query.filter_by(
        doctor_id=doctor.id,
        day_of_week=day_name
    ).all()

    return render_template('DoctorDashboard.html',
        doctor                 = doctor,
        todays_appointments    = todays_appointments,
        todays_count           = stats['todays_scheduled_count']   if stats else 0,
        patients_seen          = stats['patients_seen_today']      if stats else 0,
        appointments_this_week = stats['appointments_this_week']   if stats else 0,
        prescriptions_today    = 0,
        todays_schedule        = todays_schedule
    )


# 1. DOCTOR VIEW APPOINTMENTS
@app.route('/doctor/appointments')
def doctor_appointments():
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    if not doctor:
        flash("Doctor not found", "danger")
        return redirect(url_for('login_doctor'))

    rows = db.session.execute(text("""
        SELECT *
        FROM   VW_APPOINTMENT_FULL
        WHERE  doctor_id     = :did
          AND  UPPER(status) = 'SCHEDULED'
        ORDER BY appointment_date, time_slot
    """), {'did': doctor.id}).mappings().all()

    priority_queue = []
    for row in rows:
        priority_value = PRIORITY_VALUES.get(row['priority'], 3)
        data = {
            'id':           row['appointment_id'],
            'patient_id':   row['patient_id'],
            'patient_name': row['patient_name'],
            'date':         row['appointment_date'].strftime('%Y-%m-%d'),
            'time':         row['time_slot'],
            'priority':     row['priority'],
            'reason':       row['reason'],
            'status':       row['status'],
        }
        heapq.heappush(priority_queue, (
            priority_value,
            (row['appointment_date'], row['time_slot']),
            data
        ))

    sorted_appointments = []
    while priority_queue:
        _, _, data = heapq.heappop(priority_queue)
        sorted_appointments.append(data)

    return render_template('doctor_appointments.html', appointments=sorted_appointments)
 
 
# complete_appointment ────────────────────────────

@app.route('/appointment/complete/<int:appointment_id>', methods=['POST'])
def complete_appointment(appointment_id):
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    if not doctor:
        return redirect(url_for('login_doctor'))

    result = call_procedure(
        'SP_COMPLETE_APPOINTMENT',
        [appointment_id, doctor.id],
        [oracledb.NUMBER, oracledb.STRING]
    )
    code, msg = int(result[0]), result[1]
    flash(msg, 'success' if code == 0 else 'danger')
    return redirect(url_for('doctor_appointments'))


#  2. VIEW PATIENT MEDICAL HISTORY HISTORY
# ============================================
# PATIENT LIST - ALL PATIENTS
# ============================================

@app.route('/doctor/patient-history')
def doctor_patient_history():
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    patients = Patient.query.all()
    return render_template('patient_medical_history.html', patients=patients)


# ============================================
# PATIENT MEDICAL HISTORY - DETAILED VIEW
# ============================================

@app.route('/doctor/patient/<int:patient_id>')
def patient_medical_history(patient_id):
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()

    if not doctor:
        flash("Session expired. Please login again.", "danger")
        return redirect(url_for('login_doctor'))

    patient = Patient.query.get_or_404(patient_id)

    prescriptions = Prescription.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).order_by(Prescription.date.desc()).all()

    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).order_by(Appointment.appointment_date.desc()).all()

    return render_template('patient_medical_history.html',
        patient=patient,
        prescriptions=prescriptions,
        appointments=appointments,
        doctor=doctor,
        stats={
            'total_visits':        len(appointments),
            'total_prescriptions': len(prescriptions),
            'completed':           len([a for a in appointments if a.status == 'completed']),
            'scheduled':           len([a for a in appointments if a.status == 'scheduled'])
        })



#3 PRESCRIPTIONS


@app.route('/doctor/prescriptions', methods=['GET', 'POST'])
def doctor_prescriptions():
    if 'doctor' not in session:
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    patients = Patient.query.all()

    if request.method == 'POST':
        if 'patient_id' not in request.form or request.form['patient_id'] == "":
            flash("Please select a patient before adding a prescription.", "danger")
            return redirect(url_for('doctor_prescriptions'))

        new_prescription = Prescription(
            patient_id=int(request.form['patient_id']),
            doctor_id=doctor.id,
            date=datetime.utcnow() + timedelta(hours=5),
            medication=request.form['medication'],
            dosage=request.form['dosage'],
            frequency=request.form.get('frequency', 'As directed'),
            duration=request.form['duration'],
            instructions=request.form.get('instructions', ''),
            refills=0,
            active=1
        )

        db.session.add(new_prescription)
        db.session.commit()

        flash("Prescription made", "success")
        return redirect(url_for('doctor_prescriptions'))

    prescriptions_query = db.session.execute(text("""
        SELECT *
        FROM   VW_PRESCRIPTION_DETAIL
        WHERE  doctor_id = :did
        ORDER BY prescription_date DESC
    """), {'did': doctor.id}).mappings().all()

    stack = []
    for row in prescriptions_query:
        stack.append({
            'id':           row['id'],
            'patient_name': row['patient_name'],
            'medication':   row['medication'],
            'dosage':       row['dosage'],
            'frequency':    row['frequency'],
            'duration':     row['duration'],
            'instructions': row['instructions'],
            'date':         row['prescription_date'].strftime('%Y-%m-%d %H:%M')
                            if row['prescription_date'] else '',
            'active':       row['active'],
        })

    return render_template(
        'doctor_prescriptions.html',
        stack=stack,
        patients=patients,
        doctor=doctor
    )


@app.route('/doctor/prescriptions/delete/<int:prescription_id>', methods=['POST'])
def delete_prescription(prescription_id):
    if 'doctor' not in session:
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()

    prescription = Prescription.query.filter_by(
        id=prescription_id,
        doctor_id=doctor.id
    ).first_or_404()

    db.session.delete(prescription)
    db.session.commit()
    flash("Prescription deleted successfully!", "success")

    return redirect(url_for('doctor_prescriptions'))


# 4. Book Appointment
# ============================================
# DOCTOR BOOKS APPOINTMENT
# ============================================

@app.route('/docbook/appointment', methods=['GET', 'POST'])
def docbook_appointment():
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    doctor   = Doctor.query.filter_by(name=session['doctor']).first()
    patients = Patient.query.all()

    if request.method == 'POST':
        try:
            appt_date  = datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date()
            time_slot  = request.form['time_slot']
            patient_id = int(request.form['patient_id'])
            priority   = request.form.get('priority', 'normal')
            reason     = request.form['reason']

            result = call_procedure(
                'SP_BOOK_APPOINTMENT',
                [patient_id, doctor.id, appt_date, time_slot, reason, priority],
                [oracledb.NUMBER, oracledb.STRING, oracledb.NUMBER]
            )
            code, msg = int(result[0]), result[1]

            if code == 0:
                flash("Appointment successfully scheduled!", "success")
                return redirect(url_for('doctor_appointments'))
            elif code == 1:
                flash(msg, "warning")
            else:
                flash(msg, "danger")

        except Exception as e:
            flash(f"Error booking appointment: {str(e)}", "danger")

    return render_template('docbook_appointment.html',
        doctor    = doctor,
        patients  = patients,
        doctor_id = doctor.id,
        today     = datetime.now().strftime('%Y-%m-%d')
    )
    

# # 5. Edit Profile
# # ============================================
# # DOCTOR EDIT PROFILE
# # ============================================

@app.route('/doctor/editprofile', methods=['GET', 'POST'])
def doctor_editprofile():
    # Check if doctor is logged in
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))
    
    # Get current doctor from database
    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    
    # If doctor not found
    if not doctor:
        flash("Session expired. Please login again.", "danger")
        session.pop('doctor', None)
        return redirect(url_for('login_doctor'))
    
    if request.method == 'POST':
        try:
            # Update doctor information from form
            doctor.name = request.form.get('name')
            doctor.age = request.form.get('age')
            doctor.gender = request.form.get('gender')
            doctor.cnic = request.form.get('cnic')
            doctor.email = request.form.get('email')
            doctor.contact = request.form.get('contact')
            doctor.specialization = request.form.get('specialization')
            doctor.qualification = request.form.get('qualification')
            doctor.experience_years = request.form.get('experience_years')
            doctor.license_number = request.form.get('license_number')
            doctor.current_hospital = request.form.get('current_hospital')
            
            # Update session if name changed
            session['doctor'] = doctor.name
            
            # Save to database
            db.session.commit()
            
            flash("Profile updated successfully!", "success")
            return redirect(url_for('dashboard_doctor'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {str(e)}", "danger")
    
    return render_template('doctor_editprofile.html', doctor=doctor)


# 6. Schedule Management
PRIORITY_VALUES = {
    'emergency': 1,
    'urgent': 2,
    'normal': 3    
}

@app.route('/doctor/schedule', methods=['GET', 'POST'])
def doctor_schedule():
    if 'doctor' not in session:
        flash("Please login first", "danger")
        return redirect(url_for('login_doctor'))

    doctor = Doctor.query.filter_by(name=session['doctor']).first()
    if not doctor:
        flash("Session expired. Please login again.", "danger")
        return redirect(url_for('login_doctor'))

    if request.method == 'POST':
        try:
            days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']

            # Clear all existing shifts for this doctor
            DoctorAvailability.query.filter_by(doctor_id=doctor.id).delete()
            db.session.flush()

            has_error = False

            for day in days:
                if not request.form.get(f'{day}_enabled'):
                    continue  # Day not enabled — skip

                shift_number = 1
                prev_end_time = None  # Track previous shift's end for overlap validation

                # Keep reading shifts until no more exist in form
                # Form sends: {day}_shift_0_start, {day}_shift_0_end, {day}_shift_1_start...
                shift_index = 0
                while True:
                    start_key = f'{day}_shift_{shift_index}_start'
                    end_key   = f'{day}_shift_{shift_index}_end'

                    start_time = request.form.get(start_key, '').strip()
                    end_time   = request.form.get(end_key,   '').strip()

                    # No more shifts for this day
                    if not start_time and not end_time:
                        break

                    # Validate both provided
                    if not start_time or not end_time:
                        flash(f"⚠️ {day.capitalize()} Shift {shift_number}: Please select both start and end time.", "danger")
                        has_error = True
                        shift_index += 1
                        continue

                    # Parse times
                    try:
                        s = datetime.strptime(start_time, "%I:%M %p")
                        e = datetime.strptime(end_time,   "%I:%M %p")
                    except ValueError:
                        flash(f"❌ {day.capitalize()} Shift {shift_number}: Invalid time format.", "danger")
                        has_error = True
                        shift_index += 1
                        continue

                    # Validate end > start
                    if e <= s:
                        flash(
                            f"❌ {day.capitalize()} Shift {shift_number}: "
                            f"End time ({end_time}) must be after start time ({start_time}).",
                            "danger"
                        )
                        has_error = True
                        shift_index += 1
                        continue

                    # Validate minimum 30 minutes
                    diff_mins = int((e - s).seconds / 60)
                    if diff_mins < 30:
                        flash(
                            f"⚠️ {day.capitalize()} Shift {shift_number}: "
                            f"Minimum shift duration is 30 minutes (currently {diff_mins} mins).",
                            "warning"
                        )
                        has_error = True
                        shift_index += 1
                        continue

                    # Validate shift doesn't overlap with previous shift
                    if prev_end_time:
                        prev_end = datetime.strptime(prev_end_time, "%I:%M %p")
                        if s <= prev_end:
                            flash(
                                f"❌ {day.capitalize()} Shift {shift_number}: "
                                f"Start time ({start_time}) must be after Shift {shift_number-1} "
                                f"end time ({prev_end_time}).",
                                "danger"
                            )
                            has_error = True
                            shift_index += 1
                            continue

                    # All valid — save this shift
                    db.session.add(DoctorAvailability(
                        doctor_id    = doctor.id,
                        day_of_week  = day.capitalize(),
                        shift_number = shift_number,
                        start_time   = start_time,
                        end_time     = end_time
                    ))

                    prev_end_time = end_time
                    shift_number += 1
                    shift_index  += 1

            db.session.commit()

            if not has_error:
                flash('✅ Schedule saved successfully!', 'success')
                return redirect(url_for('dashboard_doctor'))
            else:
                flash('⚠️ Some shifts had errors and were not saved. Please review.', 'warning')

        except Exception as e:
            db.session.rollback()
            flash(f'Error saving schedule: {str(e)}', 'error')

    # GET — load existing shifts organised by day
    rows = DoctorAvailability.query.filter_by(
        doctor_id=doctor.id
    ).order_by(
        DoctorAvailability.day_of_week,
        DoctorAvailability.shift_number
    ).all()

    # Build dict: { 'monday': [{'shift':1,'start':'09:00 AM','end':'01:00 PM'}, ...], ... }
    availability_by_day = {}
    for row in rows:
        day_lower = row.day_of_week.lower()
        if day_lower not in availability_by_day:
            availability_by_day[day_lower] = []
        availability_by_day[day_lower].append({
            'shift': row.shift_number,
            'start': row.start_time,
            'end':   row.end_time
        })

    # Time options for dropdowns: 8 AM to 10 PM, 30-min intervals
    time_options = generate_time_options(start_hour=8, end_hour=22, interval=30)

    return render_template(
        'doctor_schedule.html',
        availability = availability_by_day,
        time_options = time_options,
        all_days     = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    )
 
 




def check_appointment_fields():
    """Sanity check — verifies Appointment model fields are accessible"""
    try:
        appt = Appointment.query.limit(1).first()
        if appt:
            print(f"✅ Appointment fields OK — sample id: {appt.id}")
        else:
            print("ℹ️  No appointments in database yet")
    except Exception as e:
        print(f"❌ Appointment field check failed: {e}")


# ==================== RUN APP ====================

if __name__ == '__main__':
    with app.app_context():
        try:
            # Step 1: Drop old tables if they exist (cleans up any bad previous runs)
            # This is safe to run every time — it won't fail if tables don't exist
            # db.drop_all()
           # print("  Old tables dropped (if any existed)")

            # Step 2: Create all tables fresh with Sequences in clinic_user schema
            db.create_all()
            print(" Tables created in Oracle under clinic_user schema")

            #No need of sample data Step 3: Insert sample data
            # init_sample_data()

            # Step 4: Sanity check
            check_appointment_fields()
            print("🏥 Total Doctors:", Doctor.query.count())
            print("👥 Total Patients:", Patient.query.count())

        except Exception as e:
            print(f" Startup error: {e}")
            import traceback
            traceback.print_exc()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)