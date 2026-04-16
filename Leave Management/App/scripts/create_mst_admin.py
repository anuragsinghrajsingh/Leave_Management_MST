import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leave_management.settings')
django.setup()

from django.contrib.auth import get_user_model
from App.models import Profile

User = get_user_model()

def create_master_admin():
    username = 'mst'
    password = 'MstSrv@05'
    email = 'admin@mst-india.com'
    role = 'Admin'
    phone = '+910123456789'

    if not User.objects.filter(username=username).exists():
        print(f"Creating superuser {username}...")
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        # Update custom role
        user.role = role
        user.save()

        # Update associated Profile (created via signals)
        profile = user.profile
        profile.phone = phone
        profile.role = role  # Ensure sync
        profile.department = "Management"
        profile.save()
        
        print("Superuser created successfully!")
    else:
        print(f"User {username} already exists.")

if __name__ == "__main__":
    create_master_admin()
