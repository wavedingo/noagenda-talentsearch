from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("candidates", "0003_phase4_ratings"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidate",
            name="hidden_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
