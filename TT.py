import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import hashlib
from ortools.sat.python import cp_model
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret-key-for-dev')

# Database connection
def connect_db():
    try:
        conn = sqlite3.connect('timetable.db')
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

# Database Initialization
def init_db():
    conn = connect_db()
    if conn is None:
        print("Failed to initialize database: No connection.")
        return

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            subject TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            slot INTEGER NOT NULL,
            teacher_name TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_name, slot) ON CONFLICT REPLACE
        );
    """)
    conn.commit()

    # Optional: Add a default admin user if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        hashed_password = generate_password_hash("admin") # Hash default admin password
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", hashed_password))
        conn.commit()
        print("Default admin user created: username='admin', password='admin'")

    conn.close()

# --- Routes ---

# Route 1: Login System
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return render_template('login.html', error="Username and password are required.")
        
        conn = connect_db()
        if conn is None:
            return render_template('login.html', error="Database connection failed.")
        
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data['password'], password):
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid Credentials.")
    
    return render_template('login.html')

# Dashboard
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    if conn is None:
        return render_template('dashboard.html', user=session['user'], 
                               number_of_teachers="N/A", 
                               last_generated_timetable="Error fetching data",
                               error_message="Database connection failed.")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM teachers")
    number_of_teachers = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(timestamp) FROM timetable")
    last_generated_timestamp_db = cursor.fetchone()[0]

    if last_generated_timestamp_db:
        last_generated_timetable = datetime.strptime(last_generated_timestamp_db, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
    else:
        last_generated_timetable = "Never generated"
    
    conn.close()
    
    return render_template('dashboard.html', 
                           user=session['user'], 
                           number_of_teachers=number_of_teachers, 
                           last_generated_timetable=last_generated_timetable)

# Route 2 & 3: Add/Delete Teacher
@app.route('/modify_teacher', methods=['GET', 'POST'])
def modify_teacher():
    if 'user' not in session:
        return redirect(url_for('login'))

    success_message = None
    error_message = None

    conn = connect_db()
    if conn is None:
        return render_template('modify_teacher.html', error_message="Database connection failed.")

    cursor = conn.cursor()

    if request.method == 'POST':
        if 'name' in request.form and 'subject' in request.form: # Add Teacher
            name = request.form.get('name').strip()
            subject = request.form.get('subject').strip()

            if not name or not subject:
                error_message = "Teacher name and subject are required."
            else:
                try:
                    cursor.execute("INSERT INTO teachers (name, subject) VALUES (?, ?)", (name, subject))
                    conn.commit()
                    success_message = f"Teacher '{name}' added successfully!"
                except sqlite3.IntegrityError:
                    error_message = f"Teacher '{name}' already exists."
                except sqlite3.Error as e:
                    error_message = f"Error adding teacher: {e}"

        elif 'delete_name' in request.form: # Delete Teacher
            delete_name = request.form.get('delete_name').strip()

            if not delete_name:
                error_message = "Teacher name to delete is required."
            else:
                try:
                    cursor.execute("DELETE FROM teachers WHERE name = ?", (delete_name,))
                    if cursor.rowcount > 0:
                        conn.commit()
                        success_message = f"Teacher '{delete_name}' deleted successfully!"
                    else:
                        error_message = f"Teacher '{delete_name}' not found."
                except sqlite3.Error as e:
                    error_message = f"Error deleting teacher: {e}"
    
    # Always fetch the latest list of teachers for display
    cursor.execute("SELECT name, subject FROM teachers ORDER BY name ASC")
    teachers = cursor.fetchall()
    conn.close()

    return render_template('modify_teacher.html', 
                           teachers=teachers, 
                           success_message=success_message, 
                           error_message=error_message)


# Route 4 (GET): Display Timetable Page with last generated data
@app.route('/generate_timetable', methods=['GET'])
def view_generate_timetable_page():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    if conn is None:
        return render_template('timetable.html', error_message="Database connection failed.")
    
    cursor = conn.cursor()
    
    # Fetch the last generated timetable from the database
    # This will be passed to the template to display if available
    last_generated_timetable_data = {}
    cursor.execute("SELECT class_name, slot, teacher_name FROM timetable ORDER BY class_name, slot")
    rows = cursor.fetchall()

    if rows:
        for row in rows:
            class_name = row['class_name']
            teacher_name = row['teacher_name']
            slot = row['slot'] # Use slot to correctly order periods

            if class_name not in last_generated_timetable_data:
                # Initialize with placeholder None values for all 5 periods
                last_generated_timetable_data[class_name] = [None] * 5
            
            # Place the teacher name at the correct index (slot - 1)
            if 1 <= slot <= 5: # Ensure slot is within expected range
                last_generated_timetable_data[class_name][slot - 1] = teacher_name
            else:
                print(f"Warning: Unexpected slot number {slot} for class {class_name}")

    conn.close()
    
    return render_template('timetable.html', timetable=last_generated_timetable_data)

# NEW Route (POST): Process Timetable Generation
@app.route('/generate_timetable_process', methods=['POST'])
def generate_timetable_process():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    error_message = None
    generated_timetable_display = {}

    conn = connect_db()
    if conn is None:
        return jsonify({"error": "Database connection failed."}), 500
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, subject FROM teachers")
    teachers_data = cursor.fetchall()
    conn.close()

    if not teachers_data:
        return jsonify({"error": "No teachers registered. Please add teachers to generate a timetable."}), 400

    teachers_map = {t['id']: t['name'] for t in teachers_data}
    teacher_ids = [t['id'] for t in teachers_data]
    
    classes = ['MCA I', 'MCA II', 'MSC I', 'MSC II']
    periods = range(1, 6)

    model = cp_model.CpModel()

    timetable_vars = {}
    for class_name in classes:
        for period in periods:
            timetable_vars[(class_name, period)] = model.NewIntVar(min(teacher_ids), max(teacher_ids), f'c{class_name}_p{period}')

    # Constraints:
    # 1. A teacher can only teach one class at a time (per period).
    for period in periods:
        assigned_teachers_in_period = [timetable_vars[(class_name, period)] for class_name in classes]
        if len(set(teacher_ids)) >= len(classes):
            model.AddAllDifferent(assigned_teachers_in_period)
        else:
            return jsonify({"error": "Not enough unique teachers to assign a different teacher to each class for every period."}), 400

    # 2. Each class should have a different teacher for each of its periods.
    for class_name in classes:
        class_teachers = [timetable_vars[(class_name, period)] for period in periods]
        if len(set(teacher_ids)) >= len(periods):
            model.AddAllDifferent(class_teachers)
        else:
             return jsonify({"error": f"Not enough unique teachers for class '{class_name}' to have a different teacher for each period."}), 400


    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = 60

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        conn = connect_db()
        if conn is None:
            return jsonify({"error": "Database connection failed for saving."}), 500
        cursor = conn.cursor()
        cursor.execute("DELETE FROM timetable") # Clear old timetable
        conn.commit()

        for class_name in classes:
            generated_timetable_display[class_name] = []
            for period in periods:
                teacher_id = solver.Value(timetable_vars[(class_name, period)])
                teacher_name = teachers_map.get(teacher_id, f"Unknown Teacher ID: {teacher_id}")
                generated_timetable_display[class_name].append(teacher_name)
                
                cursor.execute("INSERT INTO timetable (class_name, slot, teacher_name) VALUES (?, ?, ?)",
                               (class_name, period, teacher_name))
        
        conn.commit()
        conn.close()
        
        return jsonify({"timetable": generated_timetable_display, "success_message": "Timetable generated successfully!"})
    else:
        conn.close()
        if status == cp_model.INFEASIBLE:
            error_message = "The current set of teachers and classes makes it impossible to generate a timetable that satisfies all constraints. Please check the number of teachers or simplify constraints."
        elif status == cp_model.MODEL_INVALID:
             error_message = "The timetable model itself is invalid. This indicates an issue with constraint formulation."
        elif status == cp_model.UNKNOWN:
             error_message = "The solver could not determine a solution within the given time limit. Try increasing the time limit or simplifying the problem."
        else:
            error_message = "An unexpected error occurred during timetable generation."
        
        return jsonify({"error": error_message}), 500

# NEW: Route for LLM-powered Timetable Analysis
@app.route('/analyze_timetable', methods=['POST'])
def analyze_timetable():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    timetable_data = data.get('timetable')

    if not timetable_data:
        return jsonify({"error": "No timetable data provided for analysis."}), 400

    # Format timetable data for the LLM
    formatted_timetable = "Generated Timetable:\n\n"
    for class_name, teachers in timetable_data.items():
        formatted_timetable += f"Class {class_name}:\n"
        for i, teacher in enumerate(teachers):
            formatted_timetable += f"  Period {i+1}: {teacher}\n"
        formatted_timetable += "\n"

    prompt = f"""
    Analyze the following school timetable and provide constructive feedback, potential issues, and creative suggestions for improvement.
    Consider aspects like teacher workload distribution, subject variety per day, and flow between periods.
    If possible, suggest alternative arrangements or highlight areas that might lead to teacher fatigue or student disengagement.

    {formatted_timetable}

    Provide your analysis in a clear, concise, and professional manner.
    """

    # Call Gemini API
    api_key = os.environ.get('GEMINI_API_KEY')
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }

    try:
        import requests
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get('candidates') and len(result['candidates']) > 0 and \
           result['candidates'][0].get('content') and \
           result['candidates'][0]['content'].get('parts') and \
           len(result['candidates'][0]['content']['parts']) > 0:
            
            analysis_text = result['candidates'][0]['content']['parts'][0]['text']
            return jsonify({"analysis": analysis_text})
        else:
            return jsonify({"error": "Gemini API response format unexpected."}), 500
    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({"error": f"Failed to get analysis from AI: {e}"}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred during analysis: {e}"}), 500


# Route 5: Export Timetable to Excel
@app.route('/export_timetable')
def export_timetable():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    if conn is None:
        return "Database connection failed for export.", 500
    
    try:
        df = pd.read_sql_query("SELECT class_name, slot, teacher_name, timestamp FROM timetable ORDER BY class_name, slot", conn)
        if df.empty:
            conn.close()
            return "No timetable data to export.", 404
        
        pivot_df = df.pivot_table(index='class_name', columns='slot', values='teacher_name', aggfunc='first')
        pivot_df.columns = [f'Period {col}' for col in pivot_df.columns]
        pivot_df.reset_index(inplace=True)
        pivot_df.rename(columns={'class_name': 'Class'}, inplace=True)

        excel_filename = "timetable.xlsx"
        pivot_df.to_excel(excel_filename, index=False)
        return f"Timetable exported successfully to {excel_filename}!"
    except Exception as e:
        print(f"Error exporting timetable: {e}")
        return f"Error exporting timetable: {e}", 500
    finally:
        if conn:
            conn.close()

# Logout route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

