from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0007_add_assignment_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='max_attempts',
            field=models.IntegerField(
                default=1,
                help_text='0 — безлимит',
                verbose_name='Максимальное число попыток',
            ),
        ),
    ]
