from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_communitypostpin'),
    ]

    operations = [
        migrations.AddField(
            model_name='news',
            name='views_count',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
    ]
