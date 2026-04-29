<div align="center">

# 🌿 Leave Management MST
### The Modern, High-Performance Employee Attendance Solution

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-4.2%2B-092e20.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

**[Explore the Docs](#-getting-started) • [Report a Bug](https://github.com/anuragsinghrajsingh/Leave_Management_MST/issues) • [Request a Feature](https://github.com/anuragsinghrajsingh/Leave_Management_MST/issues)**

</div>

---

## 📖 Introduction

**Leave Management MST** (Modern System Technologies) is a premium, streamlined application designed to simplify the complex process of managing employee leave requests. Built with a focus on **speed, security, and superior aesthetics**, this version is the refined successor to traditional attendance systems.

Whether you are managing a small team or a fast-scaling organization, MST provides the tools to handle leave lifecycles with absolute confidence.

---

## ✨ Key Features

- **🚀 Unified Management Dashboard**: One-click oversight for all pending, approved, and rejected leaves.
- **🛡️ Smart Confirmation Workflow**: Promise-based modal systems that prevent accidental status changes.
- **🎨 Premium Modern UI**: A sophisticated interface featuring glassmorphism, dynamic gradients, and fluid micro-animations.
- **⚡ High-Performance Architecture**: Optimized backend logic with over 30 legacy files removed for a "Clean Core" experience.
- **📱 Fully Responsive**: Optimized for seamless use across desktops, tablets, and mobile devices.
- **📝 Contextual Rejection Notes**: Administrators can provide detailed feedback when declining requests.

---

## 🛠️ Technology Stack

| Category | Technology |
| :--- | :--- |
| **Backend** | Python 3.8+, Django 4.2+ |
| **Frontend** | HTML5, Modern CSS3 (Grid/Variables), Vanilla JavaScript |
| **Database** | SQLite (Default), PostgreSQL Compatible |
| **Styling** | Custom HSL-Tailored Design System |

---

## 🚀 Getting Started

Follow these steps to get your local development environment up and running.

### 1. Prerequisites
Ensure you have the following installed:
*   Python 3.8 or higher
*   Git

### 2. Installation & Setup
```bash
# Clone the repository
git clone https://github.com/anuragsinghrajsingh/Leave_Management_MST.git

# Navigate to project directory
cd Leave_Management_MST

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Initialization
```bash
# Apply migrations
python manage.py migrate

# Create a superuser (Admin)
python manage.py createsuperuser
```

### 4. Run the Application
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 📁 Project Structure

A clean, modular organization for maximum maintainability:

```text
├── Leave Management/
│   ├── App/            # Core business logic (Models, Views, Admin)
│   ├── static/         # Modernized CSS and JS assets
│   ├── templates/      # Optimized UI templates and partials
│   └── manage.py       # Django management script
├── README.md           # Project Documentation
└── requirements.txt    # Project Dependencies
```

---

## 👤 Author

**Anurag Singh Raj Singh**
*   **GitHub**: [@anuragsinghrajsingh](https://github.com/anuragsinghrajsingh)

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
<div align="center">
Built with ❤️ for a modern workforce.
</div>
