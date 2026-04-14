# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.contrib.auth.models import User
# from .models import LeaveBalance

# @receiver(post_save, sender=User)
# def create_leave_balance(sender, instance, created, **kwargs):
#     if created:
#         LeaveBalance.objects.create(user=instance)


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Leave, LeaveBalance, Profile



User = get_user_model()

@receiver(post_save, sender=User)
def create_leave_balance(sender, instance, created, **kwargs):
    if created:
        LeaveBalance.objects.get_or_create(user=instance)




@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    
    if created:
        Profile.objects.create(
            user=instance,
            employee_id=f"EMP{instance.id:04d}", # ✅ SYNC ON CREATE
            department="Not Assigned",
            role=instance.role,  # ✅ SYNC ON CREATE
            date_of_joining=instance.date_joined.date(),
        )

    else:
        # ✅ SYNC ON UPDATE
        if hasattr(instance, "profile"):
            profile = instance.profile
            
            # update ONLY if changed (clean)
            if profile.role != instance.role:
                profile.role = instance.role
                profile.save(update_fields=["role"])
            
            
# @receiver(post_save, sender=settings.AUTH_USER_MODEL)
# def sync_profile_role(sender, instance, **kwargs):
#     if hasattr(instance, "profile"):
#         instance.profile.role = instance.role
#         instance.profile.save(update_fields=["role"])