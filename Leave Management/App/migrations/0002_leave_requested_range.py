from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="leave",
            name="requested_from_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="leave",
            name="requested_to_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
