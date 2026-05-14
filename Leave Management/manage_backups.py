import os
import sys
import shutil
import zipfile
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Setup Django Environment
project_path = Path(__file__).resolve().parent
sys.path.append(str(project_path))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leave_management.settings')

import django
django.setup()

from django.conf import settings

# Configuration
BACKUP_DIR = settings.BASE_DIR / 'backups'
RETENTION_DAYS = 365

def get_master_logger():
    return logging.getLogger('lms_master')

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

if __name__ == '__main__':
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    run_backup()
