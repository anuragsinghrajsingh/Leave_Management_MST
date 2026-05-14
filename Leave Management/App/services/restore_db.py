import os
import subprocess
import sys
from pathlib import Path

def main():
    """
    Emergency Database Restore Wrapper.
    Launches the full interactive restore utility from manage_backups.py.
    """
    print("="*40)
    print("   LMS EMERGENCY DATABASE RESTORE")
    print("="*40)
    
    # Identify the correct python executable
    python_exe = sys.executable
    
    # Path to the main backup script (it is 2 levels up from services/)
    backup_script = Path(__file__).resolve().parent.parent.parent / "manage_backups.py"
    
    if not backup_script.exists():
        print(f"[ERROR] Could not find {backup_script.name} in the current directory.")
        return

    try:
        # Run the restore command
        subprocess.run([python_exe, str(backup_script), "--restore"], check=True)
    except KeyboardInterrupt:
        print("\n\n[INFO] Restore process interrupted by user.")
    except subprocess.CalledProcessError:
        print("\n[ERROR] The restore process encountered an error.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
