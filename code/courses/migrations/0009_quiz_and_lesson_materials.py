from django.db import migrations, models
import django.db.models.deletion
import courses.models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_add_max_attempts_to_assignment'),
    ]

    operations = [
        # LessonMaterial
        migrations.CreateModel(
            name='LessonMaterial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название материала')),
                ('file', models.FileField(upload_to=courses.models._material_upload_path, verbose_name='Файл')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='materials',
                    to='courses.lesson',
                    verbose_name='Урок',
                )),
            ],
            options={
                'verbose_name': 'Материал урока',
                'verbose_name_plural': 'Материалы урока',
                'ordering': ['uploaded_at'],
            },
        ),
        # Quiz
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Название теста')),
                ('lesson', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quiz',
                    to='courses.lesson',
                    verbose_name='Урок',
                )),
            ],
            options={
                'verbose_name': 'Тест',
                'verbose_name_plural': 'Тесты',
            },
        ),
        # Question
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Текст вопроса')),
                ('is_multiple_choice', models.BooleanField(default=False, verbose_name='Множественный выбор')),
                ('quiz', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='questions',
                    to='courses.quiz',
                    verbose_name='Тест',
                )),
            ],
            options={
                'verbose_name': 'Вопрос',
                'verbose_name_plural': 'Вопросы',
            },
        ),
        # Choice
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=500, verbose_name='Текст варианта')),
                ('is_correct', models.BooleanField(default=False, verbose_name='Правильный')),
                ('question', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='choices',
                    to='courses.question',
                    verbose_name='Вопрос',
                )),
            ],
            options={
                'verbose_name': 'Вариант ответа',
                'verbose_name_plural': 'Варианты ответа',
            },
        ),
    ]
