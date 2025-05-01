import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS employees 
                 (id INTEGER PRIMARY KEY, name TEXT, email TEXT, start_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks 
                 (employee_id INTEGER, task TEXT, completed INTEGER, due_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS documents 
                 (employee_id INTEGER, doc_name TEXT, file_path TEXT)''')
    conn.commit()
    conn.close()

# Add employee to database
def add_employee(name, email, start_date):
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("INSERT INTO employees (name, email, start_date) VALUES (?, ?, ?)", 
              (name, email, start_date))
    employee_id = c.lastrowid
    # Default tasks
    tasks = [
        ("Complete Paperwork", start_date + " 17:00"),
        ("Attend Training Session", start_date + " 17:00"),
        ("Submit ID Copy", start_date + " 17:00")
    ]
    for task, due_date in tasks:
        c.execute("INSERT INTO tasks (employee_id, task, completed, due_date) VALUES (?, ?, ?, ?)",
                  (employee_id, task, 0, due_date))
    conn.commit()
    conn.close()
    return employee_id

# Get employee tasks
def get_tasks(employee_id):
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("SELECT task, completed, due_date FROM tasks WHERE employee_id = ?", (employee_id,))
    tasks = c.fetchall()
    conn.close()
    return tasks

# Update task status
def update_task(employee_id, task, completed):
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("UPDATE tasks SET completed = ? WHERE employee_id = ? AND task = ?", 
              (1 if completed else 0, employee_id, task))
    conn.commit()
    conn.close()

# Upload document
def upload_document(employee_id, doc_name, file):
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    file_path = os.path.join(upload_dir, f"{employee_id}_{doc_name}_{file.name}")
    with open(file_path, "wb") as f:
        f.write(file.read())
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("INSERT INTO documents (employee_id, doc_name, file_path) VALUES (?, ?, ?)",
              (employee_id, doc_name, file_path))
    conn.commit()
    conn.close()
    return file_path

# Get documents
def get_documents(employee_id):
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("SELECT doc_name, file_path FROM documents WHERE employee_id = ?", (employee_id,))
    docs = c.fetchall()
    conn.close()
    return docs

# Calculate progress
def calculate_progress(tasks):
    if not tasks:
        return 0
    completed = sum(1 for _, completed, _ in tasks if completed)
    return (completed / len(tasks)) * 100

# Send reminder email (mock implementation)
def send_reminder_email(email, tasks):
    incomplete_tasks = [task for task, completed, due_date in tasks if not completed and datetime.strptime(due_date, "%Y-%m-%d %H:%M") < datetime.now()]
    if incomplete_tasks:
        subject = "Onboarding Task Reminder"
        body = f"Dear Employee,\n\nPlease complete the following tasks:\n" + "\n".join(incomplete_tasks)
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = "onboarding@company.com"
        msg["To"] = email
        # Mock SMTP (replace with real SMTP settings)
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login("your_email@gmail.com", "your_password")
                server.send_message(msg)
            st.write(f"Reminder sent to {email}")
        except Exception as e:
            st.write(f"Failed to send reminder: {e}")

# Scheduler for reminders
scheduler = BackgroundScheduler()
def check_reminders():
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("SELECT id, email FROM employees")
    employees = c.fetchall()
    for emp_id, email in employees:
        tasks = get_tasks(emp_id)
        send_reminder_email(email, tasks)
    conn.close()

scheduler.add_job(check_reminders, "interval", minutes=60)  # Check every hour
scheduler.start()

# Streamlit App
st.title("Employee Onboarding Tool")

# Initialize database
init_db()

# Sidebar for navigation
st.sidebar.title("Navigation")
option = st.sidebar.selectbox("Choose an option", ["Add Employee", "Onboarding Dashboard"])

if option == "Add Employee":
    st.header("Add New Employee")
    with st.form("employee_form"):
        name = st.text_input("Employee Name")
        email = st.text_input("Employee Email")
        start_date = st.date_input("Start Date")
        submitted = st.form_submit_button("Add Employee")
        if submitted:
            add_employee(name, email, str(start_date))
            st.success(f"Employee {name} added successfully!")

else:
    st.header("Onboarding Dashboard")
    conn = sqlite3.connect("onboarding.db")
    c = conn.cursor()
    c.execute("SELECT id, name FROM employees")
    employees = c.fetchall()
    conn.close()

    if not employees:
        st.write("No employees added yet.")
    else:
        selected_employee = st.selectbox("Select Employee", [name for _, name in employees])
        employee_id = next(id for id, name in employees if name == selected_employee)

        # Checklist
        st.subheader("Onboarding Checklist")
        tasks = get_tasks(employee_id)
        for task, completed, due_date in tasks:
            checked = st.checkbox(f"{task} (Due: {due_date})", value=bool(completed), key=f"{employee_id}_{task}")
            if checked != bool(completed):
                update_task(employee_id, task, checked)

        # Document Upload
        st.subheader("Document Upload")
        doc_name = st.text_input("Document Name")
        uploaded_file = st.file_uploader("Upload Document", key=f"upload_{employee_id}")
        if st.button("Submit Document"):
            if doc_name and uploaded_file:
                upload_document(employee_id, doc_name, uploaded_file)
                st.success("Document uploaded successfully!")
            else:
                st.error("Please provide a document name and file.")

        # Display Documents
        st.subheader("Uploaded Documents")
        docs = get_documents(employee_id)
        for doc_name, file_path in docs:
            st.write(f"{doc_name}: {file_path}")

        # Progress Visualization
        st.subheader("Onboarding Progress")
        progress = calculate_progress(tasks)
        fig = px.pie(values=[progress, 100-progress], names=["Completed", "Remaining"], title="Task Completion")
        st.plotly_chart(fig)

# Note: For HR system integration, use APIs (e.g., BambooHR API) with `requests` library.
