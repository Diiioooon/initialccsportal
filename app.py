from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import io
import csv
import secrets
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, 'static'),
    template_folder=os.path.join(BASE_DIR, 'templates')
)
app.secret_key = 'ccs_secret_key_2026'

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'database.db'))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL UNIQUE,
        lastname TEXT NOT NULL,
        firstname TEXT NOT NULL,
        midname TEXT,
        email TEXT NOT NULL UNIQUE,
        course TEXT NOT NULL,
        level TEXT NOT NULL,
        address TEXT NOT NULL,
        password TEXT NOT NULL,
        sessions INTEGER NOT NULL DEFAULT 30,
        photo TEXT DEFAULT NULL
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS sitin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL,
        name TEXT NOT NULL,
        purpose TEXT NOT NULL,
        lab TEXT NOT NULL,
        session INTEGER NOT NULL,
        date TEXT NOT NULL DEFAULT (DATE('now')),
        time_in TEXT,
        time_out TEXT,
        pc_id INTEGER
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS sitin_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL,
        name TEXT NOT NULL,
        purpose TEXT NOT NULL DEFAULT '',
        lab TEXT NOT NULL,
        session INTEGER NOT NULL,
        date TEXT NOT NULL,
        time_in TEXT,
        time_out TEXT
    )''')

    # Add pc_id column to sitin_reports if missing
    try:
        conn.execute('ALTER TABLE sitin_reports ADD COLUMN pc_id INTEGER')
    except:
        pass

    conn.execute('''CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        date TEXT NOT NULL DEFAULT (DATE('now'))
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL,
        name TEXT NOT NULL,
        lab TEXT NOT NULL,
        purpose TEXT NOT NULL DEFAULT '',
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending'
    )''')

    # Add pc_id column to reservations if missing
    try:
        conn.execute('ALTER TABLE reservations ADD COLUMN pc_id INTEGER')
    except:
        pass

    conn.execute('''CREATE TABLE IF NOT EXISTS lab_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule TEXT NOT NULL,
        created TEXT NOT NULL DEFAULT (DATE('now'))
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL UNIQUE,
        points INTEGER NOT NULL DEFAULT 0
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum TEXT NOT NULL,
        name TEXT NOT NULL,
        message TEXT NOT NULL,
        lab TEXT,
        date TEXT NOT NULL DEFAULT (DATE('now'))
    )''')

    # Add pc_id column to feedback if missing
    try:
        conn.execute('ALTER TABLE feedback ADD COLUMN pc_id INTEGER')
    except:
        pass

    conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        idnum   TEXT    NOT NULL DEFAULT 'global',
        title   TEXT    NOT NULL,
        message TEXT    NOT NULL,
        date    TEXT    NOT NULL DEFAULT (DATE('now')),
        is_read INTEGER DEFAULT 0
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS laboratory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lab_name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT ''
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS computer_units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pc_number TEXT NOT NULL,
        lab_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available',
        FOREIGN KEY (lab_id) REFERENCES laboratory(id)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS software (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        version TEXT DEFAULT '',
        license TEXT DEFAULT ''
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS pc_software (
        pc_id INTEGER,
        software_id INTEGER,
        FOREIGN KEY (pc_id) REFERENCES computer_units(id),
        FOREIGN KEY (software_id) REFERENCES software(id),
        PRIMARY KEY (pc_id, software_id)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('reservations_enabled', '1')")

    # ---------- Seed data ----------
    if conn.execute('SELECT COUNT(*) FROM lab_rules').fetchone()[0] == 0:
        rules = [
            'No food or drinks inside the laboratory.',
            'Always log in and out properly.',
            'Handle equipment with care.',
            'Keep noise to a minimum.',
            'Do not install unauthorized software.',
            'Wear your school ID at all times.',
            'Clean up your workstation before leaving.'
        ]
        for r in rules:
            conn.execute('INSERT INTO lab_rules (rule) VALUES (?)', (r,))

    if not conn.execute("SELECT * FROM users WHERE email = 'admin@ccs.com'").fetchone():
        conn.execute('''INSERT INTO users (idnum, lastname, firstname, midname, email, course, level, address, password, sessions)
                        VALUES ('0000', 'Admin', 'CCS', '', 'admin@ccs.com', 'N/A', 'N/A', 'N/A', ?, 0)''',
                     (generate_password_hash('admin123'),))

    conn.execute('''CREATE TABLE IF NOT EXISTS lab_software (
        lab_id INTEGER NOT NULL,
        software_id INTEGER NOT NULL,
        PRIMARY KEY (lab_id, software_id),
        FOREIGN KEY (lab_id) REFERENCES laboratory(id),
        FOREIGN KEY (software_id) REFERENCES software(id)
    )''')

    # Remove old Lab 1-4 (cleanup from old schema)
    old_lab_ids = [r[0] for r in conn.execute(
        "SELECT id FROM laboratory WHERE lab_name IN ('Lab 1','Lab 2','Lab 3','Lab 4')"
    ).fetchall()]
    if old_lab_ids:
        conn.execute(f"DELETE FROM computer_units WHERE lab_id IN ({','.join('?'*len(old_lab_ids))})", old_lab_ids)
        conn.execute(f"DELETE FROM laboratory WHERE id IN ({','.join('?'*len(old_lab_ids))})", old_lab_ids)

    # Seed Labs 517-530
    for lab_name in [f'Lab {n}' for n in range(517, 531)]:
        conn.execute('INSERT OR IGNORE INTO laboratory (lab_name) VALUES (?)', (lab_name,))

    # Seed 50 PCs per lab if missing
    for lab_row in conn.execute("SELECT id FROM laboratory WHERE lab_name LIKE 'Lab 5%'").fetchall():
        lab_id = lab_row[0]
        if conn.execute('SELECT COUNT(*) FROM computer_units WHERE lab_id=?', (lab_id,)).fetchone()[0] == 0:
            for pc in range(1, 51):
                conn.execute('INSERT INTO computer_units (pc_number, lab_id, status) VALUES (?,?,?)',
                             (f'PC-{pc:02d}', lab_id, 'Available'))

    # Seed software catalog if empty
    if conn.execute('SELECT COUNT(*) FROM software').fetchone()[0] == 0:
        default_sw = [
            ('Visual Studio Code','1.89','Free'),('Visual Studio 2022','17.10','Free (Community)'),
            ('Dev-C++','6.3','Free'),('Eclipse IDE','2024-03','Free'),('PyCharm Community','2024.1','Free'),
            ('NetBeans IDE','21','Free'),('Android Studio','Jellyfish','Free'),('Git','2.45','Free'),
            ('XAMPP','8.2.12','Free'),('Node.js','20.14 LTS','Free'),('Python','3.12','Free'),
            ('Java JDK','21 LTS','Free'),('MySQL Workbench','8.0','Free'),('SQLite Browser','3.12','Free'),
            ('HeidiSQL','12.6','Free'),('Cisco Packet Tracer','8.2','Free (Student)'),
            ('Wireshark','4.2','Free'),('PuTTY','0.81','Free'),('VirtualBox','7.0','Free'),
            ('VMware Workstation Player','17','Free (Personal)'),('Microsoft Office 2021','2021','Licensed'),
            ('LibreOffice','7.6','Free'),('Notepad++','8.6','Free'),('7-Zip','24.07','Free'),
            ('Adobe Photoshop','CC 2024','Licensed'),('Adobe Illustrator','CC 2024','Licensed'),
            ('Figma','Web','Free'),('GIMP','2.10','Free'),('Google Chrome','125','Free'),
            ('Mozilla Firefox','126','Free'),
        ]
        conn.executemany('INSERT OR IGNORE INTO software (name,version,license) VALUES (?,?,?)', default_sw)

    # Assign all software to all labs (517-530) if lab_software is empty
    if conn.execute('SELECT COUNT(*) FROM lab_software').fetchone()[0] == 0:
        labs = conn.execute("SELECT id FROM laboratory WHERE lab_name LIKE 'Lab 5%'").fetchall()
        sw_ids = conn.execute("SELECT id FROM software").fetchall()
        pairs = [(l[0], s[0]) for l in labs for s in sw_ids]
        conn.executemany('INSERT OR IGNORE INTO lab_software (lab_id, software_id) VALUES (?,?)', pairs)

    conn.commit()
    conn.close()

# ---------- PDF / CSV helpers ----------
def generate_pdf(title, headers, data, filename):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    table_data = [headers]
    for row in data:
        table_data.append([str(cell) if cell is not None else '' for cell in row])
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#7b2fbe')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

def generate_csv(headers, data, filename):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in data:
        writer.writerow(row)
    buffer.seek(0)
    return send_file(io.BytesIO(buffer.getvalue().encode('utf-8')), mimetype='text/csv',
                     as_attachment=True, download_name=filename)

# ---------- CSRF Protection ----------
@app.before_request
def csrf_protect():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    if request.method == "POST":
        token = session.get('csrf_token', '')
        form_token = request.form.get('csrf_token', '')
        if not token or token != form_token:
            flash('Invalid request. Please try again.', 'error')
            return redirect(request.url)

# ---------- Context processor (unread notifications) ----------
@app.context_processor
def inject_unread_count():
    if 'user_id' in session and session.get('role') == 'student':
        conn = get_db()
        count = conn.execute('''
            SELECT COUNT(*) FROM notifications
            WHERE is_read = 0 AND (idnum = ? OR idnum = 'global')
        ''', (session['user_idnum'],)).fetchone()[0]
        conn.close()
        return dict(unread_count=count)

    if 'user_id' in session and session.get('role') == 'admin':
        conn = get_db()
        count = conn.execute('''
            SELECT COUNT(*) FROM notifications
            WHERE is_read = 0 AND idnum = ?
        ''', (session['user_idnum'],)).fetchone()[0]
        conn.close()
        return dict(unread_count=count)

    return dict(unread_count=0)

# ---------- Public routes ----------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('admin_home') if session.get('role') == 'admin' else url_for('student_home'))
    return render_template('landing.html')

@app.route('/community')
def community():
    conn = get_db()
    testimonials = conn.execute('SELECT * FROM feedback ORDER BY id DESC LIMIT 10').fetchall()
    leaderboard = conn.execute('''SELECT r.idnum, r.points, u.firstname, u.lastname, u.course
                                  FROM rewards r JOIN users u ON u.idnum = r.idnum
                                  ORDER BY r.points DESC LIMIT 10''').fetchall()
    conn.close()
    return render_template('community.html', testimonials=testimonials, leaderboard=leaderboard)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('admin_home') if session.get('role') == 'admin' else url_for('student_home'))
    error = None
    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip()
        password = request.form.get('password', '').strip()
        if not login_input or not password:
            error = 'Both fields are required.'
        else:
            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email=? OR idnum=?", (login_input, login_input)).fetchone()
            conn.close()
            if user:
                stored_pw = user['password']
                if stored_pw.startswith(('pbkdf2:', 'scrypt:', 'bcrypt')):
                    valid = check_password_hash(stored_pw, password)
                else:
                    valid = (stored_pw == password)
                    if valid:
                        conn = get_db()
                        conn.execute('UPDATE users SET password=? WHERE id=?', (generate_password_hash(password), user['id']))
                        conn.commit()
                        conn.close()
                if valid:
                    session['user_id'] = user['id']
                    session['user_name'] = user['firstname'] + ' ' + user['lastname']
                    session['user_idnum'] = user['idnum']
                    session['role'] = 'admin' if user['email'] == 'admin@ccs.com' else 'student'
                    return redirect(url_for('admin_home') if session['role'] == 'admin' else url_for('student_home'))
                else:
                    error = 'Invalid credentials.'
            else:
                error = 'No account found with that email or ID number.'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('student_home'))
    error = None
    if request.method == 'POST':
        idnum = request.form['idnum'].strip()
        lastname = request.form['lastname'].strip()
        firstname = request.form['firstname'].strip()
        midname = request.form['midname'].strip()
        email = request.form['email'].strip()
        course = request.form['course']
        level = request.form['level']
        address = request.form['address'].strip()
        password = request.form['password'].strip()
        confirm = request.form['confirm'].strip()
        if not all([idnum, lastname, firstname, email, course, level, address, password, confirm]):
            error = 'All fields are required.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        else:
            conn = get_db()
            existing = conn.execute('SELECT id FROM users WHERE idnum = ? OR email = ?', (idnum, email)).fetchone()
            if existing:
                error = 'ID Number or Email already in use.'
            else:
                try:
                    conn.execute('''INSERT INTO users (idnum, lastname, firstname, midname, email, course, level, address, password)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (idnum, lastname, firstname, midname, email, course, level, address,
                                  generate_password_hash(password)))
                    conn.commit()
                    conn.close()
                    return redirect(url_for('login') + '?registered=1')
                except sqlite3.IntegrityError:
                    error = 'ID Number or Email already in use (duplicate).'
            conn.close()
        return render_template('register.html', error=error,
                               idnum=idnum, lastname=lastname, firstname=firstname,
                               midname=midname, email=email, course=course, level=level, address=address)
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Student routes ----------
def student_required():
    return 'user_id' in session and session.get('role') == 'student'

@app.route('/student')
def student_home():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    student = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    stats = conn.execute('''SELECT COUNT(*) as total,
                            SUM((julianday(time_out||':00') - julianday(time_in||':00'))*24) as hours
                            FROM sitin_reports WHERE idnum=? AND time_in!="" AND time_out!=""''',
                         (student['idnum'],)).fetchone()
    total_sessions = stats['total'] or 0
    total_hours = round(stats['hours'] or 0, 2)
    avg_duration = round(total_hours / total_sessions, 2) if total_sessions else 0
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    lab_rules = conn.execute('SELECT * FROM lab_rules ORDER BY id').fetchall()
    testimonials = conn.execute('SELECT * FROM feedback ORDER BY id DESC LIMIT 5').fetchall()
    conn.close()
    return render_template('student/home.html',
                           student=student,
                           announcements=announcements,
                           lab_rules=lab_rules,
                           testimonials=testimonials,
                           total_sessions=total_sessions,
                           total_hours=total_hours,
                           avg_duration=avg_duration)

# --- Student AJAX endpoint ---
@app.route('/student/get_pcs/<lab_name>')
def student_get_pcs(lab_name):
    if 'user_id' not in session:
        return {'pcs': []}
    conn = get_db()
    lab = conn.execute('SELECT id FROM laboratory WHERE lab_name = ?', (lab_name,)).fetchone()
    if not lab:
        conn.close()
        return {'pcs': []}
    pcs = conn.execute('''
        SELECT cu.id, cu.pc_number, cu.status,
               CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as occupied
        FROM computer_units cu
        LEFT JOIN sitin s ON s.pc_id = cu.id AND (s.time_out IS NULL OR s.time_out = '')
        WHERE cu.lab_id = ?
        ORDER BY cu.pc_number
    ''', (lab['id'],)).fetchall()
    conn.close()
    return {'pcs': [dict(pc) for pc in pcs]}

@app.route('/student/reservation', methods=['GET', 'POST'])
def student_reservation():
    if not student_required():
        return redirect(url_for('login'))
    
    conn = get_db()
    status_row = conn.execute("SELECT value FROM settings WHERE key = 'reservations_enabled'").fetchone()
    reservations_enabled = (status_row['value'] == '1') if status_row else True
    conn.close()

    if not reservations_enabled:
        flash('Reservations are currently disabled by the administrator.', 'error')
        # We still want to show the page so they can see their history, but disable the form
    
    error = None
    if request.method == 'POST':
        if not reservations_enabled:
            flash('Reservations are currently disabled.', 'error')
            return redirect(url_for('student_reservation'))
        lab = request.form['lab'].strip()
        purpose = request.form['purpose'].strip()
        date = request.form['date'].strip()
        time = request.form['time'].strip()
        pc_id = request.form.get('pc_id', '').strip()

        if not all([lab, purpose, date, time]):
            error = 'All fields are required.'
        else:
            conn = get_db()
            if conn.execute('''SELECT id FROM reservations
                               WHERE idnum=? AND lab=? AND date=? AND time=? AND status!="Rejected"''',
                            (session['user_idnum'], lab, date, time)).fetchone():
                error = 'You already have a reservation for this slot.'
            elif conn.execute('''SELECT id FROM reservations
                                 WHERE lab=? AND date=? AND time=? AND status IN ("Pending","Approved")''',
                              (lab, date, time)).fetchone():
                error = 'This slot is already reserved by another student.'
            else:
                lab_row = conn.execute('SELECT id FROM laboratory WHERE lab_name=?', (lab,)).fetchone()
                if lab_row and conn.execute('SELECT COUNT(*) FROM computer_units WHERE lab_id=? AND status="Available"',
                                            (lab_row['id'],)).fetchone()[0] == 0:
                    error = 'No available computers in this lab.'
                else:
                    conn.execute('''INSERT INTO reservations (idnum, name, lab, purpose, date, time, pc_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (session['user_idnum'], session['user_name'],
                                  lab, purpose, date, time, pc_id if pc_id else None))
                    # Notify the student
                    conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                                    VALUES (?, ?, ?, 0)''',
                                 (session['user_idnum'], 'Reservation Submitted',
                                  f'Your reservation for {lab} on {date} at {time} is pending.'))
                    # Notify the admin
                    admin_idnum = conn.execute('SELECT idnum FROM users WHERE email="admin@ccs.com"').fetchone()['idnum']
                    conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                                    VALUES (?, ?, ?, 0)''',
                                 (admin_idnum, 'New Reservation',
                                  f'{session["user_name"]} reserved {lab} on {date} at {time}.'))
                    conn.commit()
                    flash('Reservation submitted!', 'success')
                    return redirect(url_for('student_reservation'))
            conn.close()

    conn = get_db()
    labs = conn.execute('SELECT * FROM laboratory ORDER BY lab_name').fetchall()
    # Get reservations with PC number
    reservations = conn.execute('''
        SELECT r.*, cu.pc_number
        FROM reservations r
        LEFT JOIN computer_units cu ON r.pc_id = cu.id
        WHERE r.idnum = ?
        ORDER BY r.id DESC
    ''', (session['user_idnum'],)).fetchall()
    conn.close()
    return render_template('student/reservationStudent.html',
                           error=error,
                           labs=labs,
                           reservations=reservations,
                           reservations_enabled=reservations_enabled)

@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    student = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    error = success = None
    if request.method == 'POST':
        lastname = request.form['lastname'].strip()
        firstname = request.form['firstname'].strip()
        midname = request.form['midname'].strip()
        email = request.form['email'].strip()
        course = request.form['course']
        level = request.form['level']
        address = request.form['address'].strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        if not all([lastname, firstname, email, address]):
            error = 'Required fields missing.'
        elif new_password and (len(new_password) < 8 or new_password != confirm_password):
            error = 'Password must be at least 8 characters and match.'
        else:
            password = student['password']
            if new_password:
                password = generate_password_hash(new_password)
            photo = student['photo']
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f'profile_{session["user_id"]}.{ext}'
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    photo = filename
            conn.execute('''UPDATE users SET lastname=?, firstname=?, midname=?, email=?, course=?, level=?, address=?, password=?, photo=?
                            WHERE id=?''',
                         (lastname, firstname, midname, email, course, level, address, password, photo, session['user_id']))
            conn.commit()
            session['user_name'] = firstname + ' ' + lastname
            success = 'Profile updated!'
            student = conn.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('student/profile.html', student=student, error=error, success=success)

@app.route('/student/labrules')
def student_labrules():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    rules = conn.execute('SELECT * FROM lab_rules ORDER BY id').fetchall()
    conn.close()
    return render_template('student/labrules.html', rules=rules)

@app.route('/student/rewards')
def student_rewards():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    reward = conn.execute('SELECT * FROM rewards WHERE idnum=?', (session['user_idnum'],)).fetchone()
    leaderboard = conn.execute('''SELECT r.idnum, r.points, u.firstname, u.lastname
                                  FROM rewards r JOIN users u ON u.idnum = r.idnum
                                  ORDER BY r.points DESC LIMIT 10''').fetchall()
    conn.close()
    points = reward['points'] if reward else 0
    return render_template('student/rewards.html', points=points, leaderboard=leaderboard)

@app.route('/student/history', methods=['GET', 'POST'])
def student_history():
    if not student_required():
        return redirect(url_for('login'))
    error = success = None
    if request.method == 'POST':
        message = request.form['message'].strip()
        lab = request.form.get('lab', '').strip()
        pc_id = request.form.get('pc_id', '').strip()
        if not message:
            error = 'Feedback cannot be empty.'
        else:
            conn = get_db()
            conn.execute('INSERT INTO feedback (idnum, name, message, lab, pc_id) VALUES (?, ?, ?, ?, ?)',
                         (session['user_idnum'], session['user_name'], message,
                          lab if lab else None,
                          pc_id if pc_id else None))
            conn.commit()
            conn.close()
            success = 'Feedback submitted!'

    conn = get_db()
    # Get history with PC number
    rows = conn.execute('''
        SELECT sr.*, cu.pc_number
        FROM sitin_reports sr
        LEFT JOIN computer_units cu ON sr.pc_id = cu.id
        WHERE sr.idnum = ?
        ORDER BY sr.id DESC
    ''', (session['user_idnum'],)).fetchall()
    conn.close()

    records = []
    for r in rows:
        r = dict(r)
        duration = ''
        if r['time_in'] and r['time_out']:
            try:
                t_in = datetime.strptime(r['time_in'], '%H:%M')
                t_out = datetime.strptime(r['time_out'], '%H:%M')
                delta = t_out - t_in
                hours, remainder = divmod(delta.seconds, 3600)
                minutes = remainder // 60
                duration = f'{hours}h {minutes:02d}m'
            except:
                duration = 'N/A'
        else:
            duration = 'N/A'
        r['duration'] = duration
        records.append(r)

    return render_template('student/history.html', records=records, success=success, error=error)

@app.route('/student/notifications')
def student_notifications():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('''
        UPDATE notifications SET is_read = 1
        WHERE is_read = 0 AND (idnum = ? OR idnum = 'global')
    ''', (session['user_idnum'],))
    conn.commit()
    notifications = conn.execute('''
        SELECT * FROM notifications
        WHERE idnum = ? OR idnum = 'global'
        ORDER BY id DESC
    ''', (session['user_idnum'],)).fetchall()
    conn.close()
    return render_template('student/notifications.html', notifications=notifications)

@app.route('/student/notifications/mark_all_read')
def mark_all_notifications_read():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('''
        UPDATE notifications SET is_read = 1
        WHERE is_read = 0 AND (idnum = ? OR idnum = 'global')
    ''', (session['user_idnum'],))
    conn.commit()
    conn.close()
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('student_notifications'))

@app.route('/student/lab_availability')
def student_lab_availability():
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    labs = conn.execute('SELECT * FROM laboratory').fetchall()
    availability = []
    for lab in labs:
        computers = conn.execute('''
            SELECT cu.id, cu.pc_number, cu.status,
                   CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as occupied
            FROM computer_units cu
            LEFT JOIN sitin s ON s.pc_id = cu.id
            WHERE cu.lab_id = ?
            ORDER BY cu.pc_number
        ''', (lab['id'],)).fetchall()
        availability.append({'lab': lab, 'computers': computers})
    conn.close()
    return render_template('student/lab_availability.html', availability=availability)

# ---------- Admin routes ----------
def admin_required():
    return 'user_id' in session and session.get('role') == 'admin'

@app.route('/admin')
def admin_home():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    total_students = conn.execute("SELECT COUNT(*) FROM users WHERE email!='admin@ccs.com'").fetchone()[0]
    current_sitin = conn.execute('SELECT COUNT(*) FROM sitin').fetchone()[0]
    total_sitin = conn.execute('SELECT COUNT(*) FROM sitin_reports').fetchone()[0]
    course_counts = conn.execute("SELECT course, COUNT(*) as cnt FROM users WHERE email!='admin@ccs.com' GROUP BY course").fetchall()
    announcements = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('admin/home.html',
                           total_students=total_students,
                           current_sitin=current_sitin,
                           total_sitin=total_sitin,
                           course_counts=course_counts,
                           announcements=announcements)

@app.route('/admin/announcement', methods=['POST'])
def post_announcement():
    if not admin_required():
        return redirect(url_for('login'))
    content = request.form['content'].strip()
    if content:
        conn = get_db()
        conn.execute('INSERT INTO announcements (content) VALUES (?)', (content,))
        conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                        VALUES ('global', ?, ?, 0)''', ('New Announcement', content))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_home'))

@app.route('/admin/announcement/delete/<int:id>')
def delete_announcement(id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_home'))

@app.route('/admin/students')
def admin_students():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    students = conn.execute("SELECT * FROM users WHERE email!='admin@ccs.com'").fetchall()
    conn.close()
    return render_template('admin/students.html', students=students)

@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    student = conn.execute('SELECT * FROM users WHERE id=?', (id,)).fetchone()
    if request.method == 'POST':
        idnum = request.form['idnum'].strip()
        lastname = request.form['lastname'].strip()
        firstname = request.form['firstname'].strip()
        midname = request.form['midname'].strip()
        email = request.form['email'].strip()
        course = request.form['course']
        level = request.form['level']
        address = request.form['address'].strip()
        sessions = request.form.get('sessions', 30)
        conn.execute('''UPDATE users SET idnum=?, lastname=?, firstname=?, midname=?, email=?, course=?, level=?, address=?, sessions=? WHERE id=?''',
                     (idnum, lastname, firstname, midname, email, course, level, address, sessions, id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_students'))
    conn.close()
    return render_template('admin/edit_student.html', student=student)

@app.route('/admin/students/delete/<int:id>')
def delete_student(id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_students'))

@app.route('/admin/students/reset_sessions')
def reset_sessions():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("UPDATE users SET sessions=30 WHERE email!='admin@ccs.com'")
    conn.commit()
    conn.close()
    return redirect(url_for('admin_students'))

@app.route('/admin/search')
def admin_search():
    if not admin_required():
        return redirect(url_for('login'))
    query = request.args.get('q', '').strip()
    students = []
    if query:
        conn = get_db()
        students = conn.execute('''SELECT * FROM users WHERE idnum LIKE ? OR lastname LIKE ? OR firstname LIKE ?''',
                                (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        conn.close()
    return render_template('admin/search.html', students=students, query=query)

# ---------- AJAX endpoint: get PCs available in a lab (admin) ----------
@app.route('/admin/get_pcs/<lab_name>')
def get_pcs(lab_name):
    if not admin_required():
        return {'pcs': []}
    conn = get_db()
    lab = conn.execute('SELECT id FROM laboratory WHERE lab_name = ?', (lab_name,)).fetchone()
    if not lab:
        conn.close()
        return {'pcs': []}
    pcs = conn.execute('''
        SELECT cu.id, cu.pc_number, cu.status,
               CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as occupied
        FROM computer_units cu
        LEFT JOIN sitin s ON s.pc_id = cu.id
        WHERE cu.lab_id = ?
        ORDER BY cu.pc_number
    ''', (lab['id'],)).fetchall()
    conn.close()
    return {'pcs': [dict(pc) for pc in pcs]}

@app.route('/admin/sitin', methods=['GET', 'POST'])
def admin_sitin():
    if not admin_required():
        return redirect(url_for('login'))
    error = None
    if request.method == 'POST':
        idnum = request.form['idnum'].strip()
        purpose = request.form['purpose'].strip()
        lab = request.form['lab'].strip()
        pc_id = request.form.get('pc_id', '').strip()
        if not all([idnum, purpose, lab]):
            error = 'All fields are required.'
        else:
            conn = get_db()
            student = conn.execute('SELECT * FROM users WHERE idnum=?', (idnum,)).fetchone()
            if not student:
                error = 'Student ID not found.'
            elif student['sessions'] <= 0:
                error = 'No sessions left.'
            elif pc_id:
                pc = conn.execute('SELECT * FROM computer_units WHERE id=?', (pc_id,)).fetchone()
                if not pc:
                    error = 'Invalid PC selected.'
                elif pc['status'] in ('Unavailable', 'Under Maintenance'):
                    error = 'Selected PC is not available (unavailable or under maintenance).'
                elif conn.execute('SELECT id FROM sitin WHERE pc_id=?', (pc_id,)).fetchone():
                    error = 'That PC is already in use.'
                else:
                    time_in = datetime.now().strftime('%H:%M')
                    conn.execute('''INSERT INTO sitin (idnum, name, purpose, lab, session, time_in, pc_id)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (idnum, student['firstname']+' '+student['lastname'],
                                  purpose, lab, student['sessions'], time_in, pc_id))
                    conn.execute('UPDATE users SET sessions = sessions - 1 WHERE idnum=?', (idnum,))
                    conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                                    VALUES (?, ?, ?, 0)''',
                                 (idnum, 'New Sit-in Session',
                                  f'You have been registered for {purpose} in {lab}.'))
                    conn.commit()
                    flash('Sit-in started.', 'success')
                    conn.close()
                    return redirect(url_for('admin_sitin'))
            else:
                error = 'Please select a PC.'
            conn.close()

    conn = get_db()
    labs = conn.execute('SELECT * FROM laboratory ORDER BY lab_name').fetchall()
    conn.close()
    return render_template('admin/sitin.html', error=error, labs=labs)

@app.route('/admin/sitin/records')
def admin_sitin_records():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    # Include pc_number
    records = conn.execute('''
        SELECT s.*, cu.pc_number
        FROM sitin s
        LEFT JOIN computer_units cu ON s.pc_id = cu.id
        ORDER BY s.id DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/sitin_records.html', records=records)

@app.route('/admin/sitin/end/<int:record_id>')
def end_sitin(record_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    record = conn.execute('SELECT * FROM sitin WHERE id=?', (record_id,)).fetchone()
    if record:
        time_out = datetime.now().strftime('%H:%M')
        conn.execute('''INSERT INTO sitin_reports (idnum, name, purpose, lab, session, date, time_in, time_out, pc_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (record['idnum'], record['name'], record['purpose'], record['lab'], record['session'],
                      record['date'], record['time_in'] or '', time_out, record['pc_id']))
        conn.execute('DELETE FROM sitin WHERE id=?', (record_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_sitin_records'))

@app.route('/admin/reports')
def admin_reports():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    # Include pc_number
    records = conn.execute('''
        SELECT sr.*, cu.pc_number
        FROM sitin_reports sr
        LEFT JOIN computer_units cu ON sr.pc_id = cu.id
        ORDER BY sr.id DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/reports.html', records=records)

@app.route('/admin/reports/delete/<int:record_id>')
def delete_sitin_report(record_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM sitin_reports WHERE id=?', (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reports'))

@app.route('/admin/reports/clear')
def clear_sitin_reports():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM sitin_reports')
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reports'))

@app.route('/student/reservation/cancel/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    if not student_required():
        return redirect(url_for('login'))
    conn = get_db()
    reservation = conn.execute(
        'SELECT * FROM reservations WHERE id=? AND idnum=?',
        (reservation_id, session['user_idnum'])
    ).fetchone()
    if not reservation:
        flash('Reservation not found.', 'error')
    elif reservation['status'] == 'Approved':
        flash('Approved reservations cannot be cancelled. Please contact the admin.', 'error')
    elif reservation['status'] in ('Rejected', 'Cancelled'):
        flash('This reservation is already cancelled or rejected.', 'error')
    else:
        conn.execute('UPDATE reservations SET status=? WHERE id=?', ('Cancelled', reservation_id))
        conn.execute('''INSERT INTO notifications (idnum, title, message, is_read) VALUES (?, ?, ?, 0)''',
                     (session['user_idnum'], 'Reservation Cancelled',
                      f'You cancelled your reservation for {reservation["lab"]} on {reservation["date"]} at {reservation["time"]}.'))
        conn.commit()
        flash('Reservation cancelled successfully.', 'success')
    conn.close()
    return redirect(url_for('student_reservation'))

@app.route('/admin/reservation', methods=['GET', 'POST'])
def admin_reservation():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    # Include pc_number
    reservations = conn.execute('''
        SELECT r.*, cu.pc_number
        FROM reservations r
        LEFT JOIN computer_units cu ON r.pc_id = cu.id
        ORDER BY r.id DESC
    ''').fetchall()
    
    # Get reservation status
    status_row = conn.execute("SELECT value FROM settings WHERE key = 'reservations_enabled'").fetchone()
    reservations_enabled = (status_row['value'] == '1') if status_row else True
    
    conn.close()
    return render_template('admin/reservation.html', reservations=reservations, reservations_enabled=reservations_enabled)

@app.route('/admin/reservation/toggle', methods=['POST'])
def toggle_reservation():
    if not admin_required():
        return redirect(url_for('login'))
    
    enabled = request.form.get('enabled') == '1'
    conn = get_db()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'reservations_enabled'", ('1' if enabled else '0',))
    conn.commit()
    conn.close()
    
    status_text = "enabled" if enabled else "disabled"
    flash(f"Reservations have been {status_text}.", "success")
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/approve/<int:reservation_id>')
def approve_reservation(reservation_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    reservation = conn.execute('SELECT * FROM reservations WHERE id=?', (reservation_id,)).fetchone()
    if reservation:
        conn.execute("UPDATE reservations SET status='Approved' WHERE id=?", (reservation_id,))
        student = conn.execute('SELECT * FROM users WHERE idnum=?', (reservation['idnum'],)).fetchone()
        if student and student['sessions'] > 0:
            time_in = datetime.now().strftime('%H:%M')
            pc_id = reservation['pc_id'] if 'pc_id' in reservation.keys() else None
            conn.execute('''INSERT INTO sitin (idnum, name, purpose, lab, session, time_in, pc_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (reservation['idnum'], reservation['name'],
                          reservation['purpose'], reservation['lab'],
                          student['sessions'], time_in, pc_id))
            conn.execute('UPDATE users SET sessions = sessions - 1 WHERE idnum=?', (reservation['idnum'],))
        conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                        VALUES (?, ?, ?, 0)''',
                     (reservation['idnum'], 'Reservation Approved',
                      f'Your reservation for {reservation["lab"]} on {reservation["date"]} has been approved.'))
        conn.commit()
        flash('Reservation approved.', 'success')
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/reject/<int:reservation_id>')
def reject_reservation(reservation_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    reservation = conn.execute('SELECT * FROM reservations WHERE id=?', (reservation_id,)).fetchone()
    if reservation:
        conn.execute("UPDATE reservations SET status='Rejected' WHERE id=?", (reservation_id,))
        conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                        VALUES (?, ?, ?, 0)''',
                     (reservation['idnum'], 'Reservation Rejected',
                      f'Your reservation for {reservation["lab"]} on {reservation["date"]} has been rejected.'))
        conn.commit()
        flash('Reservation rejected.', 'info')
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/delete/<int:reservation_id>')
def delete_reservation(reservation_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM reservations WHERE id=?', (reservation_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/reservation/clear')
def clear_reservations():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM reservations')
    conn.commit()
    conn.close()
    return redirect(url_for('admin_reservation'))

@app.route('/admin/analytics')
def admin_analytics():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    by_purpose = conn.execute('SELECT purpose, COUNT(*) as cnt FROM sitin_reports GROUP BY purpose ORDER BY cnt DESC').fetchall()
    by_lab = conn.execute('SELECT lab, COUNT(*) as cnt FROM sitin_reports GROUP BY lab ORDER BY cnt DESC').fetchall()
    by_date = conn.execute('SELECT date, COUNT(*) as cnt FROM sitin_reports GROUP BY date ORDER BY date DESC LIMIT 14').fetchall()

    total_sessions = conn.execute('SELECT COUNT(*) FROM sitin_reports').fetchone()[0]
    total_hours = 0
    avg_duration = 0
    longest_session = 0
    rows = conn.execute('SELECT time_in, time_out FROM sitin_reports WHERE time_in!="" AND time_out!=""').fetchall()
    for r in rows:
        try:
            t_in = datetime.strptime(r['time_in'], '%H:%M')
            t_out = datetime.strptime(r['time_out'], '%H:%M')
            diff = (t_out - t_in).seconds / 3600
            total_hours += diff
            if diff > longest_session:
                longest_session = diff
        except:
            pass
    if len(rows) > 0:
        avg_duration = total_hours / len(rows)

    top_students = conn.execute('''SELECT idnum, name, COUNT(*) as session_count
                                   FROM sitin_reports GROUP BY idnum ORDER BY session_count DESC LIMIT 5''').fetchall()
    most_used_lab = conn.execute('SELECT lab, COUNT(*) as cnt FROM sitin_reports GROUP BY lab ORDER BY cnt DESC LIMIT 1').fetchone()
    peak_hours = conn.execute('SELECT time_in FROM sitin_reports WHERE time_in!=""').fetchall()
    peak_bucket = {}
    for p in peak_hours:
        try:
            hour = p['time_in'].split(':')[0]
            peak_bucket[hour] = peak_bucket.get(hour, 0) + 1
        except:
            pass
    peak_hour = max(peak_bucket, key=peak_bucket.get) if peak_bucket else 'N/A'

    conn.close()
    return render_template('admin/analytics.html',
                           by_purpose=by_purpose,
                           by_lab=by_lab,
                           by_date=by_date,
                           total_sessions=total_sessions,
                           total_hours=round(total_hours, 2),
                           avg_duration=round(avg_duration, 2),
                           longest_session=round(longest_session, 2),
                           top_students=top_students,
                           most_used_lab=most_used_lab['lab'] if most_used_lab else '-',
                           peak_hour=peak_hour)

@app.route('/admin/labrules', methods=['GET', 'POST'])
def admin_labrules():
    if not admin_required():
        return redirect(url_for('login'))
    if request.method == 'POST':
        rule = request.form['rule'].strip()
        if rule:
            conn = get_db()
            conn.execute('INSERT INTO lab_rules (rule) VALUES (?)', (rule,))
            conn.commit()
            conn.close()
    return redirect(url_for('admin_labrules_view'))

@app.route('/admin/labrules/view')
def admin_labrules_view():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rules = conn.execute('SELECT * FROM lab_rules ORDER BY id').fetchall()
    conn.close()
    return render_template('admin/labrules.html', rules=rules)

@app.route('/admin/labrules/delete/<int:rule_id>')
def delete_labrule(rule_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM lab_rules WHERE id=?', (rule_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_labrules_view'))

@app.route('/admin/rewards', methods=['GET', 'POST'])
def admin_rewards():
    if not admin_required():
        return redirect(url_for('login'))
    error = success = None
    if request.method == 'POST':
        idnum = request.form['idnum'].strip()
        points = request.form.get('points', '0').strip()
        try:
            points = int(points)
        except:
            error = 'Points must be a number.'
        if not error:
            conn = get_db()
            student = conn.execute('SELECT * FROM users WHERE idnum=?', (idnum,)).fetchone()
            if not student:
                error = 'Student ID not found.'
            else:
                conn.execute('''INSERT INTO rewards (idnum, points) VALUES (?, ?)
                                ON CONFLICT(idnum) DO UPDATE SET points = points + excluded.points''',
                             (idnum, points))
                conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                                VALUES (?, ?, ?, 0)''',
                             (idnum, 'Points Received',
                              f'You have been awarded {points} points!'))
                conn.commit()
                success = f'Added {points} points to {student["firstname"]} {student["lastname"]}'
            conn.close()
    conn = get_db()
    leaderboard = conn.execute('''SELECT r.idnum, r.points, u.firstname, u.lastname, u.course
                                  FROM rewards r JOIN users u ON u.idnum = r.idnum
                                  ORDER BY r.points DESC''').fetchall()
    conn.close()
    return render_template('admin/rewards.html', leaderboard=leaderboard, error=error, success=success)

@app.route('/admin/feedback')
def admin_feedback():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    feedbacks = conn.execute('''
        SELECT f.*, cu.pc_number
        FROM feedback f
        LEFT JOIN computer_units cu ON f.pc_id = cu.id
        ORDER BY f.id DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/feedback.html', feedbacks=feedbacks)

@app.route('/admin/feedback/delete/<int:feedback_id>', methods=['POST'])
def delete_feedback(feedback_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM feedback WHERE id=?', (feedback_id,))
    conn.commit()
    conn.close()
    flash('Feedback deleted.', 'success')
    return redirect(url_for('admin_feedback'))

@app.route('/admin/notifications', methods=['GET', 'POST'])
def admin_notifications():
    if not admin_required():
        return redirect(url_for('login'))
    success = None
    if request.method == 'POST':
        title = request.form['title'].strip()
        message = request.form['message'].strip()
        if title and message:
            conn = get_db()
            conn.execute('''INSERT INTO notifications (idnum, title, message, is_read)
                            VALUES ('global', ?, ?, 0)''', (title, message))
            conn.commit()
            conn.close()
            success = 'Notification sent to all students!'

    conn = get_db()
    admin_idnum = session['user_idnum']
    conn.execute('''UPDATE notifications SET is_read = 1
                    WHERE is_read = 0 AND idnum = ?''', (admin_idnum,))
    conn.commit()
    notifications = conn.execute('''
        SELECT * FROM notifications
        WHERE idnum = ? OR idnum = 'global'
        ORDER BY id DESC
    ''', (admin_idnum,)).fetchall()
    conn.close()
    return render_template('admin/notifications.html', notifications=notifications, success=success)

@app.route('/admin/notifications/mark_all_read')
def admin_mark_all_notifications_read():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    admin_idnum = session['user_idnum']
    conn.execute('''UPDATE notifications SET is_read = 1
                    WHERE is_read = 0 AND idnum = ?''', (admin_idnum,))
    conn.commit()
    conn.close()
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('admin_notifications'))

@app.route('/admin/notifications/delete/<int:notif_id>')
def delete_notification(notif_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM notifications WHERE id=?', (notif_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_notifications'))

# ---------- Software / Lab management ----------
@app.route('/admin/software', methods=['GET', 'POST'])
def admin_software():
    if not admin_required():
        return redirect(url_for('login'))
    error = success = None
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        if action == 'add':
            name = request.form.get('name', '').strip()
            version = request.form.get('version', '').strip()
            lic = request.form.get('license', '').strip()
            lab_id = request.form.get('lab_id') # Optional: add directly to this lab
            if not name:
                error = 'Software name is required.'
            else:
                try:
                    cur = conn.cursor()
                    cur.execute('INSERT INTO software (name, version, license) VALUES (?, ?, ?)', (name, version, lic))
                    sw_id = cur.lastrowid
                    if lab_id:
                        cur.execute('INSERT OR IGNORE INTO lab_software (lab_id, software_id) VALUES (?, ?)', (lab_id, sw_id))
                    conn.commit()
                    success = f'Software "{name}" added.'
                    if lab_id:
                        conn.close()
                        return redirect(url_for('admin_software', lab_id=lab_id))
                except sqlite3.IntegrityError:
                    error = 'Software already exists.'

    labs = conn.execute("SELECT * FROM laboratory WHERE lab_name LIKE 'Lab 5%' ORDER BY lab_name").fetchall()
    softwares = conn.execute('SELECT * FROM software ORDER BY name').fetchall()

    # Which lab is selected — check GET param, then POST form data, then default to first lab
    try:
        raw_lab_id = request.args.get('lab_id') or request.form.get('lab_id')
        selected_lab_id = int(raw_lab_id) if raw_lab_id else (labs[0]['id'] if labs else 0)
    except (ValueError, TypeError):
        selected_lab_id = labs[0]['id'] if labs else 0

    # Only fetch assigned software for the selected lab
    assigned_ids = []
    if selected_lab_id:
        rows = conn.execute('SELECT software_id FROM lab_software WHERE lab_id=?', (selected_lab_id,)).fetchall()
        assigned_ids = [r['software_id'] for r in rows]

    conn.close()
    return render_template('admin/software.html', softwares=softwares, labs=labs,
                           selected_lab_id=selected_lab_id, assigned_ids=assigned_ids,
                           error=error, success=success)

@app.route('/admin/software/assign/<int:lab_id>', methods=['POST'])
def assign_lab_software(lab_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    software_ids = request.form.getlist('software_ids')
    conn.execute('DELETE FROM lab_software WHERE lab_id=?', (lab_id,))
    for sw_id in software_ids:
        conn.execute('INSERT OR IGNORE INTO lab_software (lab_id, software_id) VALUES (?, ?)', (lab_id, sw_id))
    conn.commit()
    conn.close()
    flash('Software updated for lab.', 'success')
    return redirect(url_for('admin_software', lab_id=lab_id))

@app.route('/admin/software/import', methods=['POST'])
def import_software():
    if not admin_required():
        return redirect(url_for('login'))
    if 'csv_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('admin_software'))
    file = request.files['csv_file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('admin_software'))
    if file and file.filename.endswith('.csv'):
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        conn = get_db()
        count = 0
        skipped = 0
        for row in csv_input:
            name = row.get('name', '').strip()
            version = row.get('version', '').strip()
            lic = row.get('license', '').strip()
            if name:
                try:
                    conn.execute('INSERT INTO software (name, version, license) VALUES (?, ?, ?)', (name, version, lic))
                    count += 1
                except sqlite3.IntegrityError:
                    skipped += 1
        conn.commit()
        conn.close()
        flash(f'Imported {count} software records. {skipped} duplicates skipped.', 'success')
    else:
        flash('Invalid file format. Please upload a CSV file.', 'error')
    return redirect(url_for('admin_software'))

@app.route('/admin/software/delete/<int:sw_id>')
def delete_software(sw_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM software WHERE id=?', (sw_id,))
    conn.execute('DELETE FROM lab_software WHERE software_id=?', (sw_id,))
    conn.commit()
    conn.close()
    # Preserve lab_id from query parameter if present
    lab_id = request.args.get('lab_id')
    flash('Software removed from catalog.', 'success')
    return redirect(url_for('admin_software', lab_id=lab_id) if lab_id else url_for('admin_software'))

@app.route('/admin/computers', methods=['GET', 'POST'])
def admin_computers():
    if not admin_required():
        return redirect(url_for('login'))
    error = success = None
    conn = get_db()
    
    if request.method == 'POST':
        pc_number = request.form['pc_number'].strip()
        lab_id = request.form['lab_id']
        status = request.form.get('status', 'Available')
        if not pc_number or not lab_id:
            error = 'PC number and lab are required.'
        else:
            conn.execute('INSERT INTO computer_units (pc_number, lab_id, status) VALUES (?, ?, ?)',
                         (pc_number, lab_id, status))
            conn.commit()
            success = 'Computer unit added.'
            conn.close()
            return redirect(url_for('admin_computers', lab_id=lab_id))
    
    computers = conn.execute('''
        SELECT cu.id, cu.pc_number, cu.status, l.lab_name, l.id as lab_id,
               (SELECT COUNT(*) FROM sitin s WHERE s.pc_id = cu.id AND (s.time_out IS NULL OR s.time_out = '')) as occupied
        FROM computer_units cu
        JOIN laboratory l ON cu.lab_id = l.id
        ORDER BY l.lab_name, cu.pc_number
    ''').fetchall()
    labs = conn.execute("SELECT * FROM laboratory WHERE lab_name LIKE 'Lab 5%' ORDER BY lab_name").fetchall()
    
    # Get selected lab from URL param or POST form data, default to first lab
    try:
        raw_lab_id = request.args.get('lab_id') or request.form.get('lab_id')
        selected_lab_id = int(raw_lab_id) if raw_lab_id else (labs[0]['id'] if labs else 0)
    except (ValueError, TypeError):
        selected_lab_id = labs[0]['id'] if labs else 0
    
    conn.close()
    return render_template('admin/computers.html', computers=computers, labs=labs, 
                          selected_lab_id=selected_lab_id, error=error, success=success)

@app.route('/admin/computers/delete/<int:pc_id>', methods=['POST'])
def delete_computer_unit(pc_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    # Get lab_id before deleting
    pc = conn.execute('SELECT lab_id FROM computer_units WHERE id=?', (pc_id,)).fetchone()
    lab_id = pc['lab_id'] if pc else None
    conn.execute('DELETE FROM computer_units WHERE id=?', (pc_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_computers', lab_id=lab_id) if lab_id else url_for('admin_computers'))

@app.route('/admin/computers/maintenance/<int:pc_id>', methods=['POST'])
def toggle_maintenance(pc_id):
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    pc = conn.execute('SELECT status, lab_id FROM computer_units WHERE id=?', (pc_id,)).fetchone()
    lab_id = None
    if pc:
        lab_id = pc['lab_id']
        new_status = 'Available' if pc['status'] == 'Under Maintenance' else 'Under Maintenance'
        conn.execute('UPDATE computer_units SET status=? WHERE id=?', (new_status, pc_id))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_computers', lab_id=lab_id) if lab_id else url_for('admin_computers'))

@app.route('/admin/pc/<int:pc_id>/software', methods=['GET', 'POST'])
def assign_software(pc_id):
    if not admin_required():
        return redirect(url_for('login'))
    error = success = None
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action', 'save_software')
        if action == 'add_software':
            # Inline add new software from the Manage page
            sw_name = request.form.get('sw_name', '').strip()
            sw_version = request.form.get('sw_version', '').strip()
            sw_license = request.form.get('sw_license', '').strip()
            if not sw_name:
                error = 'Software name is required.'
            else:
                try:
                    conn.execute('INSERT INTO software (name, version, license) VALUES (?, ?, ?)',
                                 (sw_name, sw_version, sw_license))
                    conn.commit()
                    success = f'Software "{sw_name}" added successfully.'
                except sqlite3.IntegrityError:
                    error = f'Software "{sw_name}" already exists.'
        else:
            # Save checkbox assignments
            software_ids = request.form.getlist('software_ids')
            conn.execute('DELETE FROM pc_software WHERE pc_id=?', (pc_id,))
            for sw_id in software_ids:
                conn.execute('INSERT INTO pc_software (pc_id, software_id) VALUES (?, ?)', (pc_id, sw_id))
            conn.commit()
            success = 'Software assignments updated.'
    pc = conn.execute('''SELECT cu.*, l.lab_name FROM computer_units cu
                         JOIN laboratory l ON cu.lab_id = l.id WHERE cu.id=?''', (pc_id,)).fetchone()
    all_software = conn.execute('SELECT * FROM software ORDER BY name').fetchall()
    assigned = conn.execute('SELECT software_id FROM pc_software WHERE pc_id=?', (pc_id,)).fetchall()
    assigned_ids = [row['software_id'] for row in assigned]
    conn.close()
    return render_template('admin/assign_software.html',
                           pc=pc, all_software=all_software, assigned_ids=assigned_ids, error=error, success=success)

# ---------- Export routes ----------
@app.route('/admin/reservations/export/pdf')
def export_reservations_pdf():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT * FROM reservations ORDER BY id DESC').fetchall()
    conn.close()
    headers = ['ID', 'ID Number', 'Name', 'Lab', 'Purpose', 'Date', 'Time', 'Status']
    data = [[r['id'], r['idnum'], r['name'], r['lab'], r['purpose'], r['date'], r['time'], r['status']] for r in rows]
    return generate_pdf('Reservations Report', headers, data, 'reservations.pdf')

@app.route('/admin/reservations/export/csv')
def export_reservations_csv():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT * FROM reservations ORDER BY id DESC').fetchall()
    conn.close()
    headers = ['ID', 'ID Number', 'Name', 'Lab', 'Purpose', 'Date', 'Time', 'Status']
    data = [[r['id'], r['idnum'], r['name'], r['lab'], r['purpose'], r['date'], r['time'], r['status']] for r in rows]
    return generate_csv(headers, data, 'reservations.csv')

@app.route('/admin/reports/export/pdf')
def export_reports_pdf():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT * FROM sitin_reports ORDER BY id DESC').fetchall()
    conn.close()
    headers = ['ID', 'ID Number', 'Name', 'Purpose', 'Lab', 'Session', 'Date', 'Time In', 'Time Out']
    data = [[r['id'], r['idnum'], r['name'], r['purpose'], r['lab'], r['session'], r['date'],
             r['time_in'] or '', r['time_out'] or ''] for r in rows]
    return generate_pdf('Sit-in Reports', headers, data, 'sitin_reports.pdf')

@app.route('/admin/reports/export/csv')
def export_reports_csv():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT * FROM sitin_reports ORDER BY id DESC').fetchall()
    conn.close()
    headers = ['ID', 'ID Number', 'Name', 'Purpose', 'Lab', 'Session', 'Date', 'Time In', 'Time Out']
    data = [[r['id'], r['idnum'], r['name'], r['purpose'], r['lab'], r['session'], r['date'],
             r['time_in'] or '', r['time_out'] or ''] for r in rows]
    return generate_csv(headers, data, 'sitin_reports.csv')

@app.route('/admin/students/export/pdf')
def export_students_pdf():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute("SELECT * FROM users WHERE email!='admin@ccs.com' ORDER BY lastname").fetchall()
    conn.close()
    headers = ['ID Number', 'Last Name', 'First Name', 'Middle Name', 'Email', 'Course', 'Level', 'Sessions']
    data = [[r['idnum'], r['lastname'], r['firstname'], r['midname'], r['email'], r['course'], r['level'], r['sessions']] for r in rows]
    return generate_pdf('Student Records', headers, data, 'students.pdf')

@app.route('/admin/students/export/csv')
def export_students_csv():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute("SELECT * FROM users WHERE email!='admin@ccs.com' ORDER BY lastname").fetchall()
    conn.close()
    headers = ['ID Number', 'Last Name', 'First Name', 'Middle Name', 'Email', 'Course', 'Level', 'Sessions']
    data = [[r['idnum'], r['lastname'], r['firstname'], r['midname'], r['email'], r['course'], r['level'], r['sessions']] for r in rows]
    return generate_csv(headers, data, 'students.csv')

@app.route('/admin/analytics/export/pdf')
def export_analytics_pdf():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT purpose, COUNT(*) as cnt FROM sitin_reports GROUP BY purpose ORDER BY cnt DESC').fetchall()
    conn.close()
    headers = ['Purpose', 'Count']
    data = [[r['purpose'], r['cnt']] for r in rows]
    return generate_pdf('Analytics by Purpose', headers, data, 'analytics.pdf')

@app.route('/admin/analytics/export/csv')
def export_analytics_csv():
    if not admin_required():
        return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT purpose, COUNT(*) as cnt FROM sitin_reports GROUP BY purpose ORDER BY cnt DESC').fetchall()
    conn.close()
    headers = ['Purpose', 'Count']
    data = [[r['purpose'], r['cnt']] for r in rows]
    return generate_csv(headers, data, 'analytics.csv')

# ---------- Run ----------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)