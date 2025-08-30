# 🗓️ Auto Timetable Generator

An automated timetable generator built with Python (Flask + SQLite + OR-Tools) that helps IT departments generate conflict-free timetables for MCA classes.  
The system is secured with a login (accessible only to the Head of Department), and allows adding teachers, subjects, and classes, then generates and exports timetables.

---

## 🚀 Features
- Secure Login: Only the HOD can access and modify timetables.
- Teacher & Subject Management: Add teachers and assign subjects.
- Automatic Timetable Generation:
  - Ensures no teacher is double-booked.
  - Ensures no class overlaps.
  - Uses Google OR-Tools (constraint solver).
- View Timetable in a clean table layout (web browser).
- Export Timetable to Excel for offline usage.

---

## 📂 Project Structure
```bash
Auto_TimeTable_Generator/
├── app.py              # Main Flask application
├── templates/          # HTML templates
│   ├── login.html
│   ├── dashboard.html
│   ├── modify_teacher.html
│   ├── timetable.html
├── timetable.db        # SQLite database
└── README.md           # Project documentation
```
---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/timetable_project.git
cd timetable_project
````

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, install manually:

```bash
pip install flask ortools pandas
```

### 4. Run the Application

```bash
python app.py
```

### 5. Access in Browser

Go to:
👉 `http://127.0.0.1:5000`

---

## 🔑 Default Login

* **Username**: `admin`
* **Password**: `pswrd`

(You can change this in the database `users` table.)

---

## 📊 Usage

1. **Login** as HOD.
2. **Add Teachers** (with their subject).
3. **Generate Timetable** (conflict-free using OR-Tools).
4. **View Timetable** in the browser.
5. **Export Timetable** to Excel for offline sharing.

---

## 🛠️ Technologies Used

* **Python**
* **Flask** – Web framework
* **SQLite** – Lightweight database
* **Google OR-Tools** – Constraint solver for scheduling

---

## 📌 Future Improvements

* Add multiple departments (not just IT).
* Support custom number of periods and days.
* More advanced conflict resolution (teacher availability, lab timings, etc.).
* Role-based access (Faculty vs. HOD).
* Deploy on **Heroku / PythonAnywhere / AWS**.

---

## 👨‍💻 Author

Developed with ❤️ by **\[Anuraj]**
