from django.contrib.auth.models import User
from App.models import LeaveBalance

users = [
    ("asrs1", "asrs1@example.com", "asrs1"),
    ("asrs2", "asrs2@example.com", "asrs2"),
    ("asrs3", "asrs3@example.com", "asrs3"),
]

for username, email, password in users:
    
    user = User.objects.create_user( username=username, email=email, password=password)
    
    LeaveBalance.objects.get_or_create(user=user)

print("Permanent users created successfully.")


# Make sure you have "pip django-extensions"  otherwise use "pip install django-extensions" to install it.
# Add to INSTALLED_APPS in "settings.py" as shown below:

#   INSTALLED_APPS = [
#     ...
#     "django_extensions",
# ]

# Now you can run this script using the following command:
# Command:- python manage.py makemigrations App


