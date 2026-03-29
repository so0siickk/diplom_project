"""
Management-команда: генерация синтетических данных прогресса студентов.

Профили (определяются один раз на пару user+course):
  top          (30%) — вдумчивый студент, хорошо сдаёт тесты
  speedrunner  (20%) — пролистывает лекции, много попыток, средний балл
  struggling   (50%) — читает долго, но балл всё равно низкий

Запуск:
  python manage.py generate_synthetic_data
  python manage.py generate_synthetic_data --records 500 --users 15
"""

import random
from dataclasses import dataclass
from typing import Tuple

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import models, transaction

from analytics.models import QuizAttempt, UserLessonProgress
from courses.models import Course, Lesson

User = get_user_model()


# ---------------------------------------------------------------------------
# Параметры профилей
# ---------------------------------------------------------------------------

@dataclass
class ProfileParams:
    name: str
    # time_spent_seconds: (mean_factor от base_time, std_factor)
    time_mean_factor: float
    time_std_factor: float
    # attempt_count: (min, max)
    attempt_min: int
    attempt_max: int
    # quiz_score финального теста: (low, high)
    score_low: float
    score_high: float
    # вероятность завершить урок
    completion_prob: float


PROFILES: dict[str, ProfileParams] = {
    'top': ProfileParams(
        name='Отличник',
        time_mean_factor=1.0,
        time_std_factor=0.15,
        attempt_min=1,
        attempt_max=2,
        score_low=0.80,
        score_high=1.00,
        completion_prob=0.95,
    ),
    'speedrunner': ProfileParams(
        name='Спидраннер',
        time_mean_factor=0.30,
        time_std_factor=0.10,
        attempt_min=3,
        attempt_max=5,
        score_low=0.40,
        score_high=0.70,
        completion_prob=0.70,
    ),
    'struggling': ProfileParams(
        name='Отстающий',
        time_mean_factor=1.80,
        time_std_factor=0.30,
        attempt_min=3,
        attempt_max=7,
        score_low=0.20,
        score_high=0.55,
        completion_prob=0.55,
    ),
}

PROFILE_WEIGHTS = [('top', 0.30), ('speedrunner', 0.20), ('struggling', 0.50)]


def _pick_profile() -> str:
    r = random.random()
    cumulative = 0.0
    for name, weight in PROFILE_WEIGHTS:
        cumulative += weight
        if r < cumulative:
            return name
    return 'struggling'


def _base_time(lesson: Lesson) -> int:
    """Базовое время чтения: ~200 слов/мин, минимум 60 сек."""
    word_count = len(lesson.content.split()) if lesson.content else 100
    return max(60, int(word_count / 200 * 60))


def _generate_attempt_scores(
    p: ProfileParams,
    attempt_count: int,
    final_score: float,
) -> list[float]:
    """
    Генерирует оценки за каждую попытку.
    Последняя попытка == final_score, предыдущие — ниже (обучение имитируется).
    """
    if attempt_count == 1:
        return [final_score]

    scores = []
    for i in range(attempt_count - 1):
        # Ранние попытки хуже финальной на случайный процент
        penalty = random.uniform(0.10, 0.35) * (1 - i / attempt_count)
        raw = max(0.0, final_score - penalty)
        scores.append(round(raw, 3))

    scores.append(round(final_score, 3))
    return scores


def _generate_progress(
    user: User,
    lesson: Lesson,
    profile_key: str,
) -> Tuple[UserLessonProgress, list[float]]:
    """Строит объект UserLessonProgress и список оценок попыток."""
    p = PROFILES[profile_key]
    base = _base_time(lesson)

    # Время на уроке
    mean_t = base * p.time_mean_factor
    std_t = base * p.time_std_factor
    time_spent = max(30, int(random.gauss(mean_t, std_t)))

    # Число попыток
    attempt_count = random.randint(p.attempt_min, p.attempt_max)

    # Финальный балл
    final_score = round(random.uniform(p.score_low, p.score_high), 3)

    # Факт завершения
    is_completed = random.random() < p.completion_prob

    progress = UserLessonProgress(
        user=user,
        lesson=lesson,
        is_completed=is_completed,
        time_spent_seconds=time_spent,
        attempt_count=attempt_count,
        quiz_score=final_score,
    )

    attempt_scores = _generate_attempt_scores(p, attempt_count, final_score)
    return progress, attempt_scores


class Command(BaseCommand):
    help = 'Генерирует синтетические данные прогресса студентов для обучения ML-модели.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--records',
            type=int,
            default=1000,
            help='Целевое число записей UserLessonProgress (по умолчанию 1000)',
        )
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Минимальное число студентов (по умолчанию 20)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить существующие синтетические данные перед генерацией',
        )

    def handle(self, *args, **options):
        target_records: int = options['records']
        min_users: int = options['users']

        lessons = list(
            Lesson.objects.select_related('module__course').order_by('id')
        )
        if not lessons:
            self.stderr.write(
                self.style.ERROR('Нет уроков в БД. Создайте хотя бы один курс.')
            )
            return

        # --- Студенты ---
        students = self._ensure_students(min_users)
        self.stdout.write(f'Студентов в БД: {len(students)}')

        if options['clear']:
            deleted, _ = UserLessonProgress.objects.filter(
                user__username__startswith='synth_student_'
            ).delete()
            QuizAttempt.objects.filter(
                user__username__startswith='synth_student_'
            ).delete()
            self.stdout.write(f'Удалено {deleted} старых записей.')

        # --- Назначаем профили: один профиль на пару (user, course) ---
        courses = {lesson.module.course_id for lesson in lessons}
        user_course_profile: dict[tuple[int, int], str] = {}
        for student in students:
            for course_id in courses:
                user_course_profile[(student.pk, course_id)] = _pick_profile()

        # Статистика профилей
        profile_counts: dict[str, int] = {'top': 0, 'speedrunner': 0, 'struggling': 0}
        for pk in user_course_profile.values():
            profile_counts[pk] += 1

        self.stdout.write(
            f'Profili (user x course): '
            f'otlichnikov={profile_counts["top"]}, '
            f'spidrannerov={profile_counts["speedrunner"]}, '
            f'otstayuschikh={profile_counts["struggling"]}'
        )

        # --- Генерация ---
        progress_to_create: list[UserLessonProgress] = []
        attempts_to_create: list[QuizAttempt] = []

        # Каждый студент проходит случайное подмножество уроков
        lessons_per_student = max(1, target_records // len(students))

        for student in students:
            sampled = random.sample(lessons, min(lessons_per_student, len(lessons)))
            for lesson in sampled:
                if UserLessonProgress.objects.filter(
                    user=student, lesson=lesson
                ).exists():
                    continue

                profile_key = user_course_profile[
                    (student.pk, lesson.module.course_id)
                ]
                progress, attempt_scores = _generate_progress(
                    student, lesson, profile_key
                )
                progress_to_create.append(progress)

                for score in attempt_scores:
                    attempts_to_create.append(
                        QuizAttempt(user=student, lesson=lesson, score=score)
                    )

        # --- Bulk insert ---
        with transaction.atomic():
            created_progress = UserLessonProgress.objects.bulk_create(
                progress_to_create, ignore_conflicts=True
            )
            QuizAttempt.objects.bulk_create(attempts_to_create, ignore_conflicts=False)

        self.stdout.write(
            self.style.SUCCESS(
                f'Создано: {len(created_progress)} записей прогресса, '
                f'{len(attempts_to_create)} попыток тестов.'
            )
        )

        # --- Итоговая статистика по профилям ---
        self._print_stats()

    def _ensure_students(self, min_count: int) -> list:
        """Создаёт недостающих синтетических студентов."""
        existing = list(
            User.objects.filter(
                username__startswith='synth_student_', role='student'
            )
        )
        to_create = min_count - len(existing)
        if to_create > 0:
            new_users = [
                User(
                    username=f'synth_student_{i + len(existing) + 1:03d}',
                    email=f'synth_{i + len(existing) + 1}@example.com',
                    role='student',
                )
                for i in range(to_create)
            ]
            for u in new_users:
                u.set_unusable_password()
            User.objects.bulk_create(new_users, ignore_conflicts=True)
            existing = list(
                User.objects.filter(
                    username__startswith='synth_student_', role='student'
                )
            )
        return existing

    def _print_stats(self) -> None:
        from django.db.models import Avg, Count

        self.stdout.write('\n--- Статистика по синтетическим данным ---')
        qs = (
            UserLessonProgress.objects.filter(
                user__username__startswith='synth_student_'
            )
            .aggregate(
                total=Count('id'),
                completed=Count('id', filter=models.Q(is_completed=True)),
                avg_time=Avg('time_spent_seconds'),
                avg_attempts=Avg('attempt_count'),
                avg_score=Avg('quiz_score'),
            )
        )
        self.stdout.write(
            f'  Всего записей  : {qs["total"]}\n'
            f'  Завершено       : {qs["completed"]}\n'
            f'  Среднее время   : {qs["avg_time"]:.0f} сек\n'
            f'  Средние попытки : {qs["avg_attempts"]:.2f}\n'
            f'  Средний балл    : {qs["avg_score"]:.3f}\n'
        )
