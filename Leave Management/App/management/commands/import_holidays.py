import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from App.models import CompanyHoliday


class Command(BaseCommand):
    help = "Import company holidays from CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["csv_file"]

        with open(file_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            created = 0
            skipped = 0

            for row in reader:
                name = row["name"]
                date_str = row["date"]

                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                    obj, is_created = CompanyHoliday.objects.get_or_create(
                        date=date_obj,
                        defaults={"name": name}
                    )

                    if is_created:
                        created += 1
                    else:
                        skipped += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing row: {row} - {e}")
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete. Created: {created}, Skipped: {skipped}"
            )
        )
