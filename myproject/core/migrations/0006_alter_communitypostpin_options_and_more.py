from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_communitypostpin_options_news_views_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='moderator_replies_seen_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Просмотр ответов модератора'),
        ),
    ]
