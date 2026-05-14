import os
import sys
import shutil
import zipfile
import logging
import argparse
import subprocess
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

# Configuration
BACKUP_DIR = settings.BASE_DIR / 'backups'
RETENTION_DAYS = 365

def get_master_logger():
    return logging.getLogger('lms_backups')

def get_email_logger():
    return logging.getLogger('lms_email_system')

def backup_sqlite():
    db_path = settings.DATABASES['default']['NAME']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"LMS_backup_dev_{timestamp}.sqlite3"
    backup_path = BACKUP_DIR / backup_filename
    
    shutil.copy2(db_path, backup_path)
    return backup_path

def backup_postgres():
    db_settings = settings.DATABASES['default']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"LMS_backup_prod_{timestamp}.sql"
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
    
    with open(backup_path, 'w') as f:
        subprocess.run(cmd, stdout=f, env=env, check=True)
    
    return backup_path

def compress_file(file_path):
    zip_path = file_path.with_suffix('.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_path, arcname=file_path.name)
    os.remove(file_path)
    return zip_path

def cleanup_old_backups():
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    for file in BACKUP_DIR.glob('LMS_backup_*'):
        file_time = datetime.fromtimestamp(file.stat().st_mtime)
        if file_time < cutoff:
            os.remove(file)
            deleted_count += 1
    return deleted_count

def run_backup():
    logger = get_master_logger()
    db_engine = settings.DATABASES['default']['ENGINE']
    
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

def restore_database():
    """Restores the database from a selected backup file."""
    print("\n--- DATABASE RESTORE UTILITY ---")
    
    # 1. Check for backups
    backups = sorted(list(BACKUP_DIR.glob("*.zip")), reverse=True)
    if not backups:
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
            print("Restore cancelled.")
            return
        selected_backup = backups[choice]
    except (ValueError, IndexError):
        print("[ERROR] Invalid selection.")
        return

    # 4. Confirmation
    confirm = input(f"\nWARNING: This will overwrite your current database with '{selected_backup.name}'.\nAre you absolutely sure? (type 'YES' to confirm): ")
    if confirm != "YES":
        print("Restore cancelled.")
        return

    # 5. Perform Restore
    logger = get_master_logger()
    try:
        db_path = settings.DATABASES['default']['NAME']
        
        # Create a temporary backup of the current database just in case
        if Path(db_path).exists():
            shutil.copy2(db_path, f"{db_path}.pre_restore.bak")
        
        # Unzip and restore
        with zipfile.ZipFile(selected_backup, 'r') as zip_ref:
            zip_ref.extractall(settings.BASE_DIR)
            
        msg = f"RESTORE | SUCCESS | Database restored from {selected_backup.name}"
        logger.info(msg)
        print(f"\n[SUCCESS] {msg}")
        print("Current database has been replaced. A safety backup was saved as 'db.sqlite3.pre_restore.bak'.")

    except Exception as e:
        error_msg = f"RESTORE | FAILED | Error: {str(e)}"
        logger.error(error_msg)
        print(f"\n[ERROR] {error_msg}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="LMS Database Backup & Restore Utility")
    parser.add_argument("--backup", action="store_true", help="Perform a database backup")
    parser.add_argument("--restore", action="store_true", help="Restore the database from a backup file")
    
    args = parser.parse_args()
    
    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.restore:
        restore_database()
    else:
        # Default action is backup if no args or --backup is provided
        run_backup()
