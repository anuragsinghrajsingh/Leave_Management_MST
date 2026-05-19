import os
import sys
import shutil
import zipfile
import logging
import argparse
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Setup Django Environment
project_path = Path(__file__).resolve().parent
sys.path.append(str(project_path))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leave_management.settings')

import django

# Only setup django if running as a standalone script
# (When imported by the App, Django is already setup)
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leave_management.settings')
    django.setup()

from django.conf import settings
from django.core.mail import send_mail, mail_admins
from App.services.maintenance_mode import is_maintenance_mode_enabled

# Configuration
BACKUP_DIR = settings.BASE_DIR / 'backups'
RETENTION_DAYS = 365

def get_master_logger():
    return logging.getLogger('lms_backups')

def get_email_logger():
    return logging.getLogger('lms_email_system')

def backup_timestamp():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

def backup_sqlite():
    db_path = settings.DATABASES['default']['NAME']
    timestamp = backup_timestamp()
    backup_filename = f"backup_dev_{timestamp}.sqlite3"
    backup_path = BACKUP_DIR / backup_filename
    
    get_master_logger().info("BACKUP | SQLITE | Copying database | Source=%s | RawBackup=%s", db_path, backup_path)
    shutil.copy2(db_path, backup_path)
    return backup_path

def backup_postgres():
    db_settings = settings.DATABASES['default']
    timestamp = backup_timestamp()
    backup_filename = f"backup_prod_{timestamp}.sql"
    backup_path = BACKUP_DIR / backup_filename
    
    # pg_dump command
    env = os.environ.copy()
    env['PGPASSWORD'] = db_settings.get('PASSWORD', '')
    
    cmd = [
        'pg_dump',
        '-U', db_settings.get('USER', ''),
        '-h', db_settings.get('HOST', 'localhost'),
        '-p', str(db_settings.get('PORT', '5432')),
        db_settings.get('NAME', ''),
    ]
    
    get_master_logger().info("BACKUP | POSTGRES | Running pg_dump | Host=%s | Port=%s | Database=%s | RawBackup=%s", db_settings.get('HOST', 'localhost'), db_settings.get('PORT', '5432'), db_settings.get('NAME', ''), backup_path)
    with open(backup_path, 'w') as f:
        subprocess.run(cmd, stdout=f, env=env, check=True)
    
    return backup_path

def compress_file(file_path):
    zip_path = file_path.with_suffix('.zip')
    get_master_logger().info("BACKUP | COMPRESS | Source=%s | Zip=%s", file_path, zip_path)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname=file_path.name)
    os.remove(file_path)
    return zip_path

def cleanup_old_backups():
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    for file in BACKUP_DIR.glob('backup_*'):
        file_time = datetime.fromtimestamp(file.stat().st_mtime)
        if file_time < cutoff:
            get_master_logger().info("BACKUP | CLEANUP | Removing old backup | File=%s", file)
            os.remove(file)
            deleted_count += 1
    return deleted_count

def run_backup():
    logger = get_master_logger()
    db_engine = settings.DATABASES['default']['ENGINE']
    logger.info("BACKUP | START | Engine=%s | BackupDir=%s", db_engine, BACKUP_DIR)
    
    try:
        if 'sqlite3' in db_engine:
            logger.info("BACKUP | Starting SQLite backup (Dev Mode)")
            raw_path = backup_sqlite()
        elif 'postgresql' in db_engine:
            logger.info("BACKUP | Starting PostgreSQL backup (Prod Mode)")
            raw_path = backup_postgres()
        else:
            raise Exception(f"Unsupported database engine: {db_engine}")
        
        zip_path = compress_file(raw_path)
        deleted = cleanup_old_backups()
        
        msg = f"BACKUP | SUCCESS | Created: {zip_path.name} | Old backups cleaned: {deleted}"
        logger.info(msg)
        print(msg)
        return True
        
    except Exception as e:
        error_msg = f"BACKUP | FAILED | Error: {str(e)}"
        logger.error(error_msg)
        print(error_msg)
        
        # Send Email Alert to Admin
        email_logger = get_email_logger()
        try:
            subject = "CRITICAL: LMS Database Backup Failed"
            message = f"Hello Admin,\n\nThe automated database backup for the Leave Management System has FAILED.\n\nError Details:\n{str(e)}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nPlease check the server logs immediately."
            
            email_logger.info("EMAIL | Attempting to send critical backup failure alert...")
            mail_admins(subject, message, fail_silently=False)
            email_logger.info("EMAIL | SUCCESS | Backup failure alert sent to administrators.")
            
        except Exception as mail_err:
            email_logger.error(f"EMAIL | FAILED | Could not send backup failure alert: {str(mail_err)}")
        return False

def restore_database():
    """Restores the database from a selected backup file."""
    get_master_logger().info("RESTORE | MANUAL_RUN | Opened restore utility.")
    print("\n--- DATABASE RESTORE UTILITY ---")

    if not is_maintenance_mode_enabled():
        print("[ERROR] Enable maintenance mode before restoring a database backup.")
        get_master_logger().warning("RESTORE | BLOCKED | Maintenance mode is not enabled.")
        return
    
    # 1. Check for backups
    backups = sorted(list(BACKUP_DIR.glob("*.zip")), reverse=True)
    if not backups:
        get_master_logger().warning("RESTORE | BLOCKED | No backup files found | Dir=%s", BACKUP_DIR)
        print("[ERROR] No backup files found in the 'backups/' directory.")
        return

    # 2. List available backups
    print("\nAvailable Backups:")
    for i, backup in enumerate(backups):
        size = backup.stat().st_size / 1024
        print(f"[{i}] {backup.name} ({size:.2f} KB)")

    # 3. Get User Selection
    try:
        choice = int(input("\nEnter the number of the backup to restore (or -1 to cancel): "))
        if choice == -1:
            get_master_logger().info("RESTORE | CANCELLED | User selected cancel before choosing backup.")
            print("Restore cancelled.")
            return
        selected_backup = backups[choice]
        get_master_logger().info("RESTORE | SELECTED | Backup=%s", selected_backup)
    except (ValueError, IndexError):
        get_master_logger().warning("RESTORE | BLOCKED | Invalid backup selection.")
        print("[ERROR] Invalid selection.")
        return

    # 4. Confirmation
    print("Confirmation is case-sensitive. Type YES exactly as shown.")
    confirm = input(f"\nWARNING: This will overwrite your current database with '{selected_backup.name}'.\nAre you absolutely sure? (type 'YES' to confirm): ")
    if confirm != "YES":
        get_master_logger().info("RESTORE | CANCELLED | Final YES confirmation declined | Backup=%s", selected_backup)
        print("Restore cancelled.")
        return

    try:
        get_master_logger().info("RESTORE | START | Backup=%s", selected_backup)
        msg = restore_backup_file(selected_backup)
        print(f"\n[SUCCESS] {msg}")

    except Exception as e:
        error_msg = f"RESTORE | FAILED | Error: {str(e)}"
        get_master_logger().error(error_msg)
        print(f"\n[ERROR] {error_msg}")


def restore_backup_file(selected_backup):
    selected_backup = Path(selected_backup)
    if not selected_backup.exists() or selected_backup.suffix.lower() != ".zip":
        get_master_logger().error("RESTORE | BLOCKED | Invalid selected backup | File=%s", selected_backup)
        raise Exception("Selected backup file does not exist or is not a ZIP file.")

    db_engine = settings.DATABASES['default']['ENGINE']
    get_master_logger().info("RESTORE | ENGINE | Engine=%s | Backup=%s", db_engine, selected_backup)

    if 'sqlite3' in db_engine:
        restore_sqlite(selected_backup)
    elif 'postgresql' in db_engine:
        restore_postgres(selected_backup)
    else:
        raise Exception(f"Unsupported database engine: {db_engine}")

    msg = f"RESTORE | SUCCESS | Database restored from {selected_backup.name}"
    get_master_logger().info(msg)
    return msg


def restore_sqlite(selected_backup):
    db_path = Path(settings.DATABASES['default']['NAME'])
    get_master_logger().info("RESTORE | SQLITE | Preparing restore | DbPath=%s | Backup=%s", db_path, selected_backup)

    with zipfile.ZipFile(selected_backup, 'r') as zip_ref:
        sqlite_members = [
            member for member in zip_ref.namelist()
            if member.endswith(".sqlite3") and "/" not in member and "\\" not in member
        ]

        if len(sqlite_members) != 1:
            get_master_logger().error("RESTORE | SQLITE | Invalid archive member count | Count=%s", len(sqlite_members))
            raise Exception("Selected backup must contain exactly one SQLite .sqlite3 file.")

        safety_backup = db_path.with_suffix(f"{db_path.suffix}.pre_restore.bak")
        if db_path.exists():
            shutil.copy2(db_path, safety_backup)
            get_master_logger().info("RESTORE | SQLITE | Safety backup created | File=%s", safety_backup)

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_path = Path(zip_ref.extract(sqlite_members[0], temp_dir))
            shutil.copy2(extracted_path, db_path)

    print(f"Current SQLite database has been replaced. Safety backup: {safety_backup}")


def restore_postgres(selected_backup):
    db_settings = settings.DATABASES['default']
    get_master_logger().info("RESTORE | POSTGRES | Preparing restore | Backup=%s | Database=%s", selected_backup, db_settings.get('NAME', ''))

    with zipfile.ZipFile(selected_backup, 'r') as zip_ref:
        sql_members = [
            member for member in zip_ref.namelist()
            if member.endswith(".sql") and "/" not in member and "\\" not in member
        ]

        if len(sql_members) != 1:
            get_master_logger().error("RESTORE | POSTGRES | Invalid archive member count | Count=%s", len(sql_members))
            raise Exception("Selected backup must contain exactly one PostgreSQL .sql file.")

        with tempfile.TemporaryDirectory() as temp_dir:
            sql_path = Path(zip_ref.extract(sql_members[0], temp_dir))

            env = os.environ.copy()
            env['PGPASSWORD'] = db_settings.get('PASSWORD', '')

            cmd = [
                'psql',
                '-U', db_settings.get('USER', ''),
                '-h', db_settings.get('HOST', 'localhost') or 'localhost',
                '-p', str(db_settings.get('PORT', '5432') or '5432'),
                '-d', db_settings.get('NAME', ''),
                '-f', str(sql_path),
            ]

            get_master_logger().info("RESTORE | POSTGRES | Running psql restore | Host=%s | Port=%s | Database=%s", db_settings.get('HOST', 'localhost') or 'localhost', db_settings.get('PORT', '5432') or '5432', db_settings.get('NAME', ''))
            subprocess.run(cmd, env=env, check=True)

    print("PostgreSQL database has been restored using psql.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LMS Database Backup & Restore Utility")
    parser.add_argument("--backup", action="store_true", help="Perform a database backup")
    parser.add_argument("--restore", action="store_true", help="Restore the database from a backup file")
    
    args = parser.parse_args()
    get_master_logger().info("BACKUP_SCRIPT | MANUAL_RUN | Args=%s", vars(args))
    
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.restore:
        restore_database()
    else:
        # Default action is backup if no args or --backup is provided
        run_backup()
