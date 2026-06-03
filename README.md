# <div align="center">🌿 Leave Management MST</div>
<p align="center">
  <sub>A Product of <b>MS Technology</b></sub>
</p>

<p align="center">
  <strong>The Next-Gen, High-Performance Workforce Attendance Ecosystem.</strong>
</p>

<div align="center">

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django 4.2+](https://img.shields.io/badge/Django-4.2+-092e20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![UI Glassmorphism](https://img.shields.io/badge/UI-Modern--Glass-cyan?style=for-the-badge)](https://github.com/anuragsinghrajsingh/Leave_Management_MST)

</div>

---

## 📖 1. Project Overview

The **Leave Management MST (Modern System Technologies)** Edition is an enterprise-grade, high-performance web platform designed to streamline workforce logistics, leave tracking, and communication. Built on top of a highly optimized Django core, this product eliminates legacy technical debt, reduces database locks, implements robust background task queues, and hosts a dedicated scheduler daemon to automate critical business operations.

---

## 📑 2. Table of Contents
1. [🔍 About MST Edition](#about-mst)
2. [⚙️ System Architecture](#system-architecture)
3. [🚀 Enterprise Features](#enterprise-features)
4. [🔄 System Workflows & Lifecycle](#system-workflows)
5. [📂 Directory Structure](#directory-structure)
6. [🏁 Getting Started (Local Setup)](#getting-started)
7. [🔧 Environment Configuration](#environment-configuration)
8. [🛡️ Production Deployment & Systemd Setup](#production-deployment)
9. [📈 Operations & Troubleshooting Cheatsheet](#operations-cheatsheet)
10. [📜 License & Credits](#license)

---

<a id="about-mst"></a>
## 🔍 3. About MST Edition

The MST Edition was engineered around a **"Clean Core"** philosophy—refactoring legacy structures, removing redundant assets, and separating critical business logic into isolated service files.

### 👑 The MS Technology Pillars
* **Reliability**: Fully atomic transactions, explicit database locking, and background recovery cron jobs guarantee data integrity under peak load.
* **Aesthetics**: A premium modern design language featuring Glassmorphism, dynamic HSL colors, responsive layouts, and 300ms transition animations.
* **Maintainability**: Clear division of concerns. Controllers (views) invoke atomic services rather than executing complex SQL queries directly.

---

<a id="system-architecture"></a>
## ⚙️ 4. System Architecture

```mermaid
flowchart TB
    Client[Web Browsers / HTTPS] <--> Nginx[Nginx Reverse Proxy]
    Nginx <--> Gunicorn[Gunicorn WSGI Server]
    Gunicorn <--> Django[Django Core Application]
    
    subgraph Services [Asynchronous Processing Engine]
        Django <--> QCluster[Django-Q Cluster / Worker Pool]
        QCluster -- Fallback -- > ThreadPool[ThreadPoolExecutor max_workers=8]
        LMS_Scheduler[LMS Scheduler Daemon] -- Cron Triggers --> Django
    end

    subgraph Database [Storage Layer]
        Django <--> PostgreSQL[(PostgreSQL Database)]
        PostgreSQL -- select_for_update of='self' --> Django
    end

    subgraph FileSystem [State & Backups]
        LMS_Scheduler -- pg_dump --> ZIP[Compressed ZIP Backups]
        Django -- Write --> Logs[System Logs & Startup State]
    end
```

### Stack Components
* **Core Framework**: Django 4.2 LTS / Python 3.8+
* **Primary Database**: PostgreSQL (configured with transaction pooling)
* **Background Queue**: Django-Q (ORM broker) with `ThreadPoolExecutor` fallback
* **Daemon Scheduler**: Dedicated Advanced Python Scheduler (APScheduler) process
* **Web Server Proxy**: Nginx + Gunicorn (WSGI)
* **Frontend**: Asynchronous JavaScript (Promises / AJAX), dynamic HSL variables

---

<a id="enterprise-features"></a>
## 🚀 5. Enterprise Features

### 1. Dedicated LMS Scheduler Daemon
A standalone, foreground-safe scheduler CLI daemon command (`python manage.py run_lms_scheduler`) configured with signal handlers (`SIGTERM` / `SIGINT`) to ensure graceful shutdowns. It runs:
* **Nightly Backups** (Daily at 02:00)
* **Weekly HR Mission Control PDF Reports** (Monday at 09:00)
* **India Public Holiday Sync** (Monthly on Day 1 at 03:00)
* **Admin Email Job Auto-Recovery** (Every 5 minutes)
* **Scheduler Keep-Alive Ping** (Every 6 hours)
* **Startup Catch-up Routines** (checks for and runs missed nightly backups or weekly reports due to server downtime)

### 2. High-Fidelity PDF Reporting Engine
Extracts weekly HR attendance metrics and compiles a high-density, styled PDF attachment containing:
* Total requests, approval rates, pending tasks, and rejected applications
* Visual employee attendance tables and organizational health indicators
* Headless Chromium rendering support for high-resolution document generation

### 3. Asynchronous Email & Notification Cluster
Processes bulk administrator emails (onboarding, password resetting, custom reminders, locks/unlocks) in parallel.
* **ORM Job Queueing**: Jobs are split into `AdminEmailJob` and `AdminEmailJobItem` records.
* **Auto-Recovery Cron**: In the event of a worker crash, a background cron scans for items in a `running` state for $> 15$ minutes, resets their state to `queued`, and re-triggers execution.

### 4. Robust Leave Calculation Engine
Supports five leave types, each validated with precise business rules:
* **Short Leave**: Same-day, max 2 hours, working hours only (10:00 - 19:00), max 2/month, deducts 0.25 days.
* **Half Leave**: Same-day, max 4 hours, working hours only, max 1/month, deducts 0.5 days.
* **Full-Day Leaves (Sick, Earned, Unpaid)**: Spans multiple days, integrated with a **Work-From-Home (WFH) Bridge** and India Public Holiday calendar overrides to calculate exact leave deductions.

### 5. PostgreSQL Deadlock Mitigation
Critical transactional state changes (Approve, Reject, Apply, Delete) utilize Django's `select_for_update(of=("self",))` row-locking API. This locks only the target row inside the `Leave` table, allowing related `User` and `Profile` tables to remain readable, completely eliminating PostgreSQL lock contention and deadlock conditions.

### 6. Automated Self-Healing Backups
Integrates a python utility (`manage_backups.py`) executing `pg_dump` commands to build database archives.
* **Zip Compression**: Dumps are automatically compressed, tagged with timestamps, and cleaned up using a retention policy.
* **Failed Dump Cleanup**: If a backup fails, the utility intercepts the exception and deletes the temporary or incomplete `.sql` files to protect storage.

---

<a id="system-workflows"></a>
## 🔄 6. System Workflows

### Leave Application & Impact Validation Flow
```mermaid
sequenceDiagram
    participant User as Employee Portal
    participant View as views.apply_leave
    participant DB as PostgreSQL Database
    participant Push as Notification Services

    User->>View: Submit Leave Form (Dates/Times/Type)
    View->>DB: Lock Leave Table
    View->>View: Check overlap / Validate against holiday list
    View->>View: Verify monthly limits (Short/Half)
    View->>View: Compute exact balance deductions
    alt Valid Request
        View->>DB: Create Leave Record & Save
        View->>Push: Enqueue HR Push notifications & Emails
        View->>User: Success response (Refresh Grid)
    else Invalid Request
        View->>User: Error response (Modal Feedback)
    end
```

---

<a id="directory-structure"></a>
## 📂 7. Directory Structure

```text
├── Leave Management/
│   ├── App/
│   │   ├── management/
│   │   │   └── commands/
│   │   │       └── run_lms_scheduler.py   # Dedicated Scheduler CLI Daemon
│   │   ├── services/
│   │   │   ├── scheduler.py               # APScheduler Core Configuration
│   │   │   ├── startup_checks.py          # Missed task checks & startup routines
│   │   │   ├── admin_bulk_email_jobs.py   # Async bulk mail & recovery logic
│   │   │   ├── background_tasks.py        # Django-Q & ThreadPool task executor
│   │   │   ├── uptime_tracker.py          # Localized uptime recording
│   │   │   └── public_holidays.py         # Google Holiday Calendar synchronization
│   │   ├── models.py                      # Core Database Schemas
│   │   ├── admin.py                       # Custom Django Admin views & bulk actions
│   │   └── views.py                       # Web View Controllers (Employee/HR/Portal)
│   ├── leave_management/
│   │   ├── settings.py                    # Django configuration (settings, Q_CLUSTER)
│   │   └── urls.py                        # Central routing index
│   ├── static/                            # Front-End design assets (CSS, JS)
│   ├── templates/                         # HTML Templates (Glass UI components)
│   └── manage_backups.py                  # Database Backup & Restore Utility
├── backups/                               # PostgreSQL Compressed Backups (.zip)
├── logs/                                  # System Runtime log files
└── runtime/                               # Runtime state files (app_startup.json)
```

---

<a id="getting-started"></a>
## 🏁 8. Getting Started (Local Setup)

### Prerequisites
* Python 3.8 or higher
* PostgreSQL 12+
* Virtual Environment utility (`virtualenv`)

### Setup Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/anuragsinghrajsingh/Leave_Management_MST.git
   cd Leave_Management_MST
   ```

2. **Initialize Virtual Environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment variables**:
   Create a `.env` file in the project root folder. Reference the [Configuration section](#environment-configuration) below.

5. **Execute Database Migrations**:
   ```bash
   python "Leave Management/manage.py" migrate
   ```

6. **Create a Superuser**:
   ```bash
   python "Leave Management/manage.py" createsuperuser
   ```

7. **Start the Development Servers**:
   Run the web server:
   ```bash
   python "Leave Management/manage.py" runserver
   ```
   Run the task queue (in a separate terminal):
   ```bash
   python "Leave Management/manage.py" qcluster
   ```
   Run the scheduler daemon (in a separate terminal):
   ```bash
   python "Leave Management/manage.py" run_lms_scheduler
   ```

---

<a id="environment-configuration"></a>
## 🔧 9. Environment Configuration

The application uses an environment-driven configuration setup. Create a `.env` file in the root folder with the following variables:

```ini
# Core Django Settings
SECRET_KEY=your_secure_mst_secret_key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,yourdomain.com

# Database Connection URL (PostgreSQL)
DATABASE_URL=postgres://db_user:db_password@127.0.0.1:5432/db_name

# Email SMTP Server Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=notifications@yourdomain.com
EMAIL_HOST_PASSWORD=your_app_specific_smtp_password
DEFAULT_FROM_EMAIL=Leave Management <notifications@yourdomain.com>

# System URLs
PORTAL_BASE_URL=http://127.0.0.1:8000

# Background Worker Settings
LMS_Q_WORKERS=2
LMS_Q_TIMEOUT=120
LMS_Q_RETRY=300
LMS_Q_QUEUE_LIMIT=100
LMS_Q_BULK=20

# Operational Triggers
LMS_SKIP_UPTIME_RECORD=0
```

---

<a id="production-deployment"></a>
## 🛡️ 10. Production Deployment & Systemd Setup

For highly reliable production deployments, all background workloads must be managed by the host OS as persistent system services (`systemd`).

### 1. Gunicorn Web Server Service
File: `/etc/systemd/system/gunicorn.service`
```ini
[Unit]
Description=Gunicorn Web App Daemon
After=network.target postgresql.service

[Service]
User=mstleave
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 leave_management.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. Django-Q Background Worker Service
File: `/etc/systemd/system/qcluster.service`
```ini
[Unit]
Description=Django-Q Queue Cluster Daemon
After=network.target postgresql.service

[Service]
User=mstleave
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/python manage.py qcluster
Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. LMS Scheduler Daemon Service
File: `/etc/systemd/system/lms_scheduler.service`
```ini
[Unit]
Description=LMS APScheduler Daemon Process
After=network.target postgresql.service qcluster.service

[Service]
User=mstleave
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/python manage.py run_lms_scheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

### Service Administration Commands
Execute these commands to register, start, and verify the background daemons:
```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services to run on boot
sudo systemctl enable gunicorn qcluster lms_scheduler

# Start all components
sudo systemctl start gunicorn qcluster lms_scheduler

# Inspect service statuses
sudo systemctl status gunicorn qcluster lms_scheduler
```

---

<a id="operations-cheatsheet"></a>
## 📈 11. Operations & Troubleshooting Cheatsheet

### 1. Log Inspection Commands
View the real-time logging output of your application components:
```bash
# View Gunicorn logs (HTTP layer)
sudo journalctl -u gunicorn -n 100 -f --no-pager

# View Queue cluster logs (Background tasks)
sudo journalctl -u qcluster -n 100 -f --no-pager

# View Scheduler logs (Cron tasks)
sudo journalctl -u lms_scheduler -n 100 -f --no-pager
```

### 2. Live Database Maintenance
Run manual database backups or restorations using the CLI:
```bash
# Run manual database backup
python "Leave Management/manage_backups.py" --action backup

# Restore database from a compressed backup zip
python "Leave Management/manage_backups.py" --action restore --file backups/backup_prod_2026-05-31_02-00-00.zip
```

### 3. Debugging Missed Backups & Reports
Check the status of missed cron tasks inside the Django shell:
```bash
python "Leave Management/manage.py" shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

### 4. Verifying Django-Q Worker Process Counts
```bash
# Count active python qcluster processes
pgrep -fc "manage.py qcluster"
```

---

<a id="license"></a>
## 📜 12. License & Credits

* **License**: Proprietary - All Rights Reserved. Created as part of the **MS Technology** workforce productivity suite.
* **Author**: Anurag Singh Raj Singh ([anuragsinghrajsingh@gmail.com](mailto:anuragsinghrajsingh@gmail.com))
* **Copyright**: &copy; 2026 MS Technology. Engineering the Future of Work.
