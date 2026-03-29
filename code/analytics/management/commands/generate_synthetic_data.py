"""
Management-команда: генерация синтетических данных прогресса студентов.

Профили (определяются один раз на пару user+course):
  top                 (25%) -- вдумчивый, сдаёт тесты, высокая завершаемость
  speedrunner         (15%) -- пролистывает, средний балл, непостоянная завершаемость
  struggling          (35%) -- читает долго, балл низкий, часто бросает
  high_scorer_dropout (10%) -- OULAD-паттерн: отличные баллы, но бросает в середине курса
  low_scorer_persister(15%) -- низкий балл, но дочитывает всё (упорство без понимания)

Ключевое изменение vs v1:
  - quiz_score и is_completed развязаны: завершение определяется вовлечённостью,
    а не только баллом. quiz_score имеет малый вклад (~15% от ±0.5 deviation).
  - Добавлен quiz_taken_prob: часть студентов не сдаёт тест совсем
    (quiz_score=NULL). Это отдельный сигнал дисengagement.
  - Добавлен гауссов шум (+/-8% std) для реалистичного перекрытия классов.

Запуск:
  python manage.py generate_synthetic_data
  python manage.py generate_synthetic_data --records 1500 --users 30 --clear
"""

import random
from dataclasses import dataclass
from typing import Optional, Tuple

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
    # Базовое время: (множитель от base_time, std-множитель)
    time_mean_factor: float
    time_std_factor: float
    # Число попыток
    attempt_min: int
    attempt_max: int
    # Диапазон quiz_score (если тест сдан)
    score_low: float
    score_high: float
    # Вероятность ВООБЩЕ сдавать тест (0 = quiz_score=NULL)
    quiz_taken_prob: float
    # Базовая вероятность завершить урок (ДО корректировок)
    base_completion_prob: float


PROFILES: dict[str, ProfileParams] = {
    'top': ProfileParams(
        name='Top student',
        time_mean_factor=1.0,
        time_std_factor=0.15,
        attempt_min=1,
        attempt_max=2,
        score_low=0.80,
        score_high=1.00,
        quiz_taken_prob=0.95,
        base_completion_prob=0.88,
    ),
    'speedrunner': ProfileParams(
        name='Speedrunner',
        time_mean_factor=0.30,
        time_std_factor=0.10,
        attempt_min=3,
        attempt_max=5,
        score_low=0.40,
        score_high=0.70,
        quiz_taken_prob=0.70,
        base_completion_prob=0.62,
    ),
    'struggling': ProfileParams(
        name='Struggling',
        time_mean_factor=1.80,
        time_std_factor=0.30,
        attempt_min=3,
        attempt_max=7,
        score_low=0.18,
        score_high=0.50,
        quiz_taken_prob=0.58,
        base_completion_prob=0.45,
    ),
    # OULAD-inspired: получает хорошие баллы, но бросает — burnout / life events
    'high_scorer_dropout': ProfileParams(
        name='High scorer dropout',
        time_mean_factor=0.90,
        time_std_factor=0.20,
        attempt_min=1,
        attempt_max=3,
        score_low=0.72,
        score_high=0.95,
        quiz_taken_prob=0.88,
        base_completion_prob=0.32,  # низкая! несмотря на хорошие баллы
    ),
    # OULAD-inspired: упорный, но не понимает материал — всё равно дочитывает
    'low_scorer_persister': ProfileParams(
        name='Low scorer persister',
        time_mean_factor=2.10,
        time_std_factor=0.25,
        attempt_min=4,
        attempt_max=8,
        score_low=0.22,
        score_high=0.48,
        quiz_taken_prob=0.55,
        base_completion_prob=0.80,  # высокая! несмотря на плохие баллы
    ),
}

PROFILE_WEIGHTS = [
    ('top',                 0.25),
    ('speedrunner',         0.15),
    ('struggling',          0.35),
    ('high_scorer_dropout', 0.10),
    ('low_scorer_persister',0.15),
]


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


def _compute_completion(
    p: ProfileParams,
    quiz_taken: bool,
    quiz_score: Optional[float],
) -> bool:
    """
    Вычисляет is_completed с развязанной зависимостью от quiz_score.

    Слагаемые вероятности:
      base:          профиль определяет основу (~60-80% вклада)
      engagement:    +0.08 если тест сдан, -0.12 если нет
      score_signal:  маленький сигнал от балла (±0.075 max)
      noise:         гаусс с std=0.08 (реалистичное перекрытие классов)
    """
    prob = p.base_completion_prob

    # Вовлечённость: факт сдачи теста важнее самого балла
    if quiz_taken and quiz_score is not None:
        prob += 0.08
        # Небольшой вклад балла: deviation от 0.5, масштаб 0.15
        prob += (quiz_score - 0.5) * 0.15
    else:
        prob -= 0.12  # не сдал тест — сигнал дисengagement

    # Гауссов шум для реалистичного перекрытия классов
    prob += random.gauss(0.0, 0.08)

    # Ограничиваем [0.05, 0.95] — нет абсолютной определённости
    prob = max(0.05, min(0.95, prob))
    return random.random() < prob


def _generate_attempt_scores(
    p: ProfileParams,
    attempt_count: int,
    final_score: float,
) -> list[float]:
    """Оценки за попытки: ранние хуже финальной (имитация обучения)."""
    if attempt_count == 1:
        return [final_score]
    scores = []
    for i in range(attempt_count - 1):
        penalty = random.uniform(0.08, 0.30) * (1 - i / attempt_count)
        scores.append(round(max(0.0, final_score - penalty), 3))
    scores.append(round(final_score, 3))
    return scores


def _generate_progress(
    user: User,
    lesson: Lesson,
    profile_key: str,
) -> Tuple[UserLessonProgress, list[float]]:
    """Строит UserLessonProgress и список оценок попыток."""
    p = PROFILES[profile_key]
    base = _base_time(lesson)

    time_spent = max(30, int(random.gauss(
        base * p.time_mean_factor,
        base * p.time_std_factor,
    )))
    attempt_count = random.randint(p.attempt_min, p.attempt_max)

    # Решаем: студент вообще сдаёт тест?
    quiz_taken = random.random() < p.quiz_taken_prob
    if quiz_taken:
        quiz_score: Optional[float] = round(
            random.uniform(p.score_low, p.score_high), 3
        )
    else:
        quiz_score = None  # явный сигнал: тест не открывался

    is_completed = _compute_completion(p, quiz_taken, quiz_score)

    progress = UserLessonProgress(
        user=user,
        lesson=lesson,
        is_completed=is_completed,
        time_spent_seconds=time_spent,
        attempt_count=attempt_count,
        quiz_score=quiz_score,
    )

    attempt_scores: list[float] = []
    if quiz_taken and quiz_score is not None:
        attempt_scores = _generate_attempt_scores(p, attempt_count, quiz_score)

    return progress, attempt_scores


class Command(BaseCommand):
    help = 'Generate synthetic student progress data for ML training (v2, OULAD-inspired).'

    def add_arguments(self, parser):
        parser.add_argument('--records', type=int, default=1500,
                            help='Target number of UserLessonProgress records (default: 1500)')
        parser.add_argument('--users', type=int, default=30,
                            help='Minimum number of synthetic students (default: 30)')
        parser.add_argument('--clear', action='store_true',
                            help='Delete existing synthetic data before generating')

    def handle(self, *args, **options):
        target_records: int = options['records']
        min_users: int = options['users']

        lessons = list(Lesson.objects.select_related('module__course').order_by('id'))
        if not lessons:
            self.stderr.write(self.style.ERROR('No lessons in DB. Create courses first.'))
            return

        students = self._ensure_students(min_users)
        self.stdout.write(f'Students in DB: {len(students)}')

        if options['clear']:
            deleted, _ = UserLessonProgress.objects.filter(
                user__username__startswith='synth_student_'
            ).delete()
            QuizAttempt.objects.filter(
                user__username__startswith='synth_student_'
            ).delete()
            self.stdout.write(f'Deleted {deleted} old progress records.')

        # Один профиль на пару (user, course)
        courses = {lesson.module.course_id for lesson in lessons}
        user_course_profile: dict[tuple[int, int], str] = {}
        for student in students:
            for course_id in courses:
                user_course_profile[(student.pk, course_id)] = _pick_profile()

        # Статистика профилей
        profile_counts: dict[str, int] = {k: 0 for k in PROFILES}
        for pk in user_course_profile.values():
            profile_counts[pk] += 1
        counts_str = ', '.join(f'{k}={v}' for k, v in profile_counts.items())
        self.stdout.write(f'Profile assignments: {counts_str}')

        # Генерация
        progress_to_create: list[UserLessonProgress] = []
        attempts_to_create: list[QuizAttempt] = []
        lessons_per_student = max(1, target_records // len(students))

        for student in students:
            sampled = random.sample(lessons, min(lessons_per_student, len(lessons)))
            for lesson in sampled:
                if UserLessonProgress.objects.filter(user=student, lesson=lesson).exists():
                    continue
                profile_key = user_course_profile[(student.pk, lesson.module.course_id)]
                progress, attempt_scores = _generate_progress(student, lesson, profile_key)
                progress_to_create.append(progress)
                for score in attempt_scores:
                    attempts_to_create.append(
                        QuizAttempt(user=student, lesson=lesson, score=score)
                    )

        with transaction.atomic():
            created = UserLessonProgress.objects.bulk_create(
                progress_to_create, ignore_conflicts=True
            )
            QuizAttempt.objects.bulk_create(attempts_to_create, ignore_conflicts=False)

        self.stdout.write(self.style.SUCCESS(
            f'Created: {len(created)} progress records, {len(attempts_to_create)} quiz attempts.'
        ))
        self._print_stats()

    def _ensure_students(self, min_count: int) -> list:
        existing = list(User.objects.filter(
            username__startswith='synth_student_', role='student'
        ))
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
            existing = list(User.objects.filter(
                username__startswith='synth_student_', role='student'
            ))
        return existing

    def _print_stats(self) -> None:
        from django.db.models import Avg, Count

        self.stdout.write('\n--- Synthetic data stats ---')
        qs = UserLessonProgress.objects.filter(
            user__username__startswith='synth_student_'
        ).aggregate(
            total=Count('id'),
            completed=Count('id', filter=models.Q(is_completed=True)),
            quiz_taken=Count('id', filter=models.Q(quiz_score__isnull=False)),
            avg_time=Avg('time_spent_seconds'),
            avg_attempts=Avg('attempt_count'),
            avg_score=Avg('quiz_score'),
        )
        completion_rate = qs['completed'] / max(qs['total'], 1)
        quiz_taken_rate = qs['quiz_taken'] / max(qs['total'], 1)
        self.stdout.write(
            f'  Total records   : {qs["total"]}\n'
            f'  Completed       : {qs["completed"]} ({completion_rate:.1%})\n'
            f'  Quiz taken      : {qs["quiz_taken"]} ({quiz_taken_rate:.1%})\n'
            f'  Avg time (sec)  : {qs["avg_time"]:.0f}\n'
            f'  Avg attempts    : {qs["avg_attempts"]:.2f}\n'
            f'  Avg quiz score  : {qs["avg_score"]:.3f} (excl. NULL)\n'
        )
