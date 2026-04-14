# 🏢 Leave Management System

![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)

A comprehensive, production-ready internal HR web application built with **Django**. This system provides strict, role-based access control (Admin, HR, Employee) and streamlines the entire lifecycle of requesting, validating, and managing workforce holidays.

It features interactive, API-driven feeds and a robust internal communications system.

---

## ✨ Key Features

- **🛡️ Rigid Role-Based Access Control (RBAC)**
  - Dedicated dynamic portals isolated by role: system `Admin`, Human Resources (`HR`), and general `Employee`.
- **📅 Advanced Leave Logic & Validation**
  - Handles five distinct leave types: *Short, Half, Casual, Sick, and Earned*.
  - Strict time-based validation (e.g., Short variations are bounded rigidly to standard working hours, max 2 hours).
  - Automatically manages complex numeric balances (Earned vs. Sick) and unpaid leaves.
- **💬 Real-Time Internal Communication Ecosystem**
  - Features an asynchronous Notification System avoiding traditional polling.
  - Granular history tracking for notifications (separating exact timestamps for `Seen` vs. `Read`).
  - Allows HR to broadcast company-wide `Announcements` or handle 1-on-1 `Direct Messages` with employees.
- **🚀 Secure Architecture**
  - Utilizes localized caching techniques and standard Django defensive programming to prevent access tunneling and database collisions via simultaneous requests.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.13, Django 6.0
- **Database:** SQLite3 (Easily migrated to PostgreSQL/MySQL via Django ORM)
- **Frontend Engine:** Django Templates augmented with JS/JSON endpoints 
- **Utilities:** 
  - `Pillow` (Image Processing)
  - `ics` (Dynamic calendar integration)
  - `requests`

---

## ⚙️ Installation & Setup (Local Environment)

Follow these steps to get the project perfectly running on your local machine.

### 1. Clone the Repository
```bash
git clone https://github.com/anuragsinghrajsingh/Leave_Management.git
cd Leave_Management
```

### 2. Set Up Virtual Environment
```bash
# Create the virtual environment
python -m venv virtual_env

# Activate it (Windows)
.\virtual_env\Scripts\activate
# Activate it (Mac/Linux)
source virtual_env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirement.txt
```

### 4. Database Migrations
```bash
cd "Leave Management"
python manage.py migrate
```
*(You may also want to run `python manage.py createsuperuser` to set up your first Admin account).*

### 5. Start the Server
```bash
python manage.py runserver
```
Visit http://127.0.0.1:8000/ to view the application!

---

*This application is maintained securely and acts as a central hub for employee tracking.*
