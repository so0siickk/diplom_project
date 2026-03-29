from django.core.management.base import BaseCommand
from courses.models import Course
from assistant.vector_store import index_course_content


class Command(BaseCommand):
    help = 'Индексирует все курсы в векторную базу данных'

    def handle(self, *args, **options):
        self.stdout.write("Начинаем полную переиндексацию...")

        courses = Course.objects.all()
        for course in courses:
            index_course_content(course)

        self.stdout.write(self.style.SUCCESS('Готово! База знаний обновлена.'))