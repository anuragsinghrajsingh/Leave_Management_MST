from django.core.management.base import BaseCommand

from App.services.public_holidays import get_public_holidays, sync_public_holidays


class Command(BaseCommand):
    help = "Fetch and cache India public holidays for the leave calendar."

    def handle(self, *args, **options):
        if sync_public_holidays():
            self.stdout.write(self.style.SUCCESS("Public holidays synced successfully."))
            return

        holidays = get_public_holidays()
        self.stdout.write(
            self.style.WARNING(
                f"Public holiday sync failed. Calendar will use saved/fallback holidays. Count: {len(holidays)}"
            )
        )
