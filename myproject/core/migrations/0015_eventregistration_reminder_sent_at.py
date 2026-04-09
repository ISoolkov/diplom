from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_feedbackmessage_moderation_attachment"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventregistration",
            name="reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
