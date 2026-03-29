"""
Создаёт 3 демо-курса с модулями и уроками для тестирования ML-пайплайна.
Запуск: python manage.py populate_demo_courses
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from courses.models import Course, Module, Lesson

User = get_user_model()

COURSES = [
    {
        'title': 'Python для начинающих',
        'description': 'Базовый курс по Python',
        'modules': [
            {'title': 'Основы синтаксиса', 'lessons': [
                'Переменные и типы данных',
                'Условные операторы',
                'Циклы for и while',
                'Функции',
            ]},
            {'title': 'Структуры данных', 'lessons': [
                'Списки и кортежи',
                'Словари и множества',
                'Строки и форматирование',
            ]},
            {'title': 'ООП', 'lessons': [
                'Классы и объекты',
                'Наследование',
                'Полиморфизм',
                'Магические методы',
            ]},
        ],
    },
    {
        'title': 'Машинное обучение: основы',
        'description': 'Введение в ML с scikit-learn',
        'modules': [
            {'title': 'Введение в ML', 'lessons': [
                'Что такое машинное обучение',
                'Типы задач ML',
                'Обзор scikit-learn',
            ]},
            {'title': 'Линейные модели', 'lessons': [
                'Линейная регрессия',
                'Логистическая регрессия',
                'Регуляризация',
                'Кросс-валидация',
            ]},
            {'title': 'Ансамблевые методы', 'lessons': [
                'Деревья решений',
                'Random Forest',
                'Gradient Boosting',
                'Настройка гиперпараметров',
            ]},
        ],
    },
    {
        'title': 'Django: от нуля до деплоя',
        'description': 'Полный курс по веб-разработке на Django',
        'modules': [
            {'title': 'Основы Django', 'lessons': [
                'Установка и первый проект',
                'Модели и ORM',
                'Views и URLconf',
                'Шаблоны',
            ]},
            {'title': 'Django REST Framework', 'lessons': [
                'Сериализаторы',
                'API Views',
                'Аутентификация',
            ]},
            {'title': 'Деплой', 'lessons': [
                'PostgreSQL и настройки',
                'Nginx и Gunicorn',
                'Docker и CI/CD',
            ]},
        ],
    },
]


class Command(BaseCommand):
    help = 'Создаёт демо-курсы для тестирования ML-пайплайна.'

    def handle(self, *args, **options):
        teacher, _ = User.objects.get_or_create(
            username='demo_teacher',
            defaults={'role': 'teacher', 'email': 'teacher@example.com'},
        )
        if not teacher.has_usable_password():
            teacher.set_unusable_password()
            teacher.save()

        created_lessons = 0
        for course_data in COURSES:
            course, created = Course.objects.get_or_create(
                title=course_data['title'],
                defaults={'owner': teacher, 'description': course_data['description']},
            )
            if not created:
                self.stdout.write(f'Курс уже существует: {course.title}')
                continue

            for m_order, mod_data in enumerate(course_data['modules'], start=1):
                module = Module.objects.create(
                    course=course,
                    title=mod_data['title'],
                    order=m_order,
                )
                for l_order, lesson_title in enumerate(mod_data['lessons'], start=1):
                    Lesson.objects.create(
                        module=module,
                        title=lesson_title,
                        content=(
                            f'Лекция по теме «{lesson_title}». '
                            f'В данном уроке рассматриваются ключевые концепции '
                            f'и практические примеры по теме {lesson_title}. '
                            f'Студент изучает теоретическую базу и закрепляет '
                            f'знания с помощью практических заданий и тестов. '
                            f'Материал охватывает основные аспекты темы, '
                            f'включая типичные ошибки и способы их исправления.'
                        ),
                        order=l_order,
                    )
                    created_lessons += 1

            self.stdout.write(f'Создан курс: {course.title}')

        self.stdout.write(self.style.SUCCESS(
            f'Готово. Создано уроков: {created_lessons}'
        ))
