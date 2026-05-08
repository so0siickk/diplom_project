"""
Fills the DB with synthetic analytics data for Instructor Dashboard screenshots.

Groups (applied to shuffled student list):
  - top     (30%): 2-3 lessons completed, scores 8-10
  - mid     (50%): 1-2 lessons completed, scores 4-7
  - lagging (20%): 0-1 lesson  completed, scores 0-3 / code FAILED

Run:
    python manage.py seed_analytics

Re-run safe: existing records are skipped, not duplicated.
No external APIs are called -- all submissions are created directly in the DB.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from analytics.models import UserLessonProgress
from assignments.models import CodeSubmission, EssaySubmission
from courses.models import Assignment, Lesson

User = get_user_model()

# ---------------------------------------------------------------------------
# Group keys
# ---------------------------------------------------------------------------

_TOP = 'top'
_MID = 'mid'
_LAG = 'lag'

# ---------------------------------------------------------------------------
# Per-group numeric parameters
# ---------------------------------------------------------------------------

_SCORE_RANGE  = {_TOP: (8, 10),   _MID: (4, 7),    _LAG: (0, 3)}
_LESSON_COUNT = {_TOP: (2, 3),    _MID: (1, 2),    _LAG: (0, 1)}
_TIME_SEC     = {_TOP: (300, 600), _MID: (120, 300), _LAG: (30, 120)}
_ATTEMPTS     = {_TOP: (1, 2),    _MID: (2, 4),    _LAG: (3, 6)}
_QUIZ_SCORE   = {_TOP: (0.80, 1.0), _MID: (0.40, 0.75), _LAG: (0.0, 0.35)}

# ---------------------------------------------------------------------------
# Fake submission content (stored in DB -- Russian text is fine here)
# ---------------------------------------------------------------------------

_CODE_CONTENT = {
    _TOP: (
        'def solution(items):\n'
        '    return sorted(set(items), reverse=True)\n'
    ),
    _MID: (
        'def solution(items):\n'
        '    result = list(set(items))\n'
        '    result.sort(reverse=True)\n'
        '    return result\n'
    ),
    _LAG: 'print(items)\n',
}

_CODE_OUTPUT = {
    _TOP: '[9, 7, 5, 3, 1]\nAll tests passed.',
    _MID: '[9, 7, 5, 3, 1]',
    _LAG: "NameError: name 'items' is not defined",
}

_CODE_STATUS = {
    _TOP: CodeSubmission.Status.SUCCESS,
    _MID: CodeSubmission.Status.SUCCESS,
    _LAG: CodeSubmission.Status.FAILED,
}

_CODE_FEEDBACK = {
    _TOP: (
        'Отличная работа! Код лаконичен и эффективен. '
        'Использование set() для удаления дубликатов — верное решение. '
        'Все тесты пройдены.'
    ),
    _MID: (
        'Решение корректно, но можно упростить до одной строки с sorted(set(...)). '
        'Логика верна, стиль кода требует небольшой доработки.'
    ),
    _LAG: (
        'Программа выдаёт NameError: переменная items не определена. '
        'Повторите материал урока по функциям и параметрам.'
    ),
}

_ESSAY_CONTENT = {
    _TOP: (
        'Данная тема охватывает ключевые аспекты изучаемого материала. '
        'В эссе последовательно раскрываются основные понятия, '
        'приводятся конкретные примеры из практики и делаются обоснованные '
        'выводы на основании лекционного материала. '
        'Автор демонстрирует глубокое понимание изученных концепций '
        'и умеет применять их в нестандартных ситуациях.'
    ),
    _MID: (
        'Тема в целом раскрыта, однако ряд аспектов требует уточнения. '
        'Основные понятия изложены верно, примеры присутствуют, '
        'но аргументация местами недостаточно развёрнута. '
        'Структура ответа соответствует требованиям задания.'
    ),
    _LAG: (
        'Тема изложена поверхностно. '
        'Конкретные примеры и развёрнутая аргументация отсутствуют. '
        'Рекомендуется повторно изучить лекционный материал и перечитать условие задания.'
    ),
}

_ESSAY_FEEDBACK = {
    _TOP: (
        'Отличная работа! Материал полностью усвоен, ответ развёрнут и аргументирован. '
        'Студент верно использует терминологию из лекции.'
    ),
    _MID: (
        'Неплохо, но есть отдельные недочёты. '
        'Рекомендуется дополнить раздел с примерами и усилить аргументацию.'
    ),
    _LAG: (
        'Много ошибок, повторите материал. '
        'Ответ не соответствует требованиям задания.'
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand_past_dt(days: int = 7):
    """Return a tz-aware datetime randomly offset within the last `days` days."""
    offset_sec = random.randint(0, days * 24 * 3600)
    return timezone.now() - timedelta(seconds=offset_sec)


def _split_into_groups(students: list) -> list[tuple[str, object]]:
    """
    Return [(group_key, user), ...] for a shuffled student list.
    Ratios: top=30%, mid=50%, lag=20%.
    """
    total = len(students)
    n_top = max(1, round(total * 0.30))
    n_mid = max(1, round(total * 0.50))

    result = []
    result += [(_TOP, s) for s in students[:n_top]]
    result += [(_MID, s) for s in students[n_top:n_top + n_mid]]
    result += [(_LAG, s) for s in students[n_top + n_mid:]]
    return result


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Seeds synthetic analytics data for dashboard screenshots (no external APIs).'

    def handle(self, *args, **options) -> None:
        students = list(
            User.objects.filter(role='student', is_staff=False).order_by('id')
        )
        if not students:
            self.stdout.write(self.style.WARNING('No student accounts found. Aborting.'))
            return

        lessons = list(Lesson.objects.select_related('module__course').order_by('id')[:3])
        if not lessons:
            self.stdout.write(self.style.WARNING('No lessons found. Aborting.'))
            return

        lesson_ids = [l.pk for l in lessons]
        code_assignments = list(
            Assignment.objects.filter(
                lesson_id__in=lesson_ids,
                assignment_type=Assignment.Type.CODE,
            )
        )
        essay_assignments = list(
            Assignment.objects.filter(
                lesson_id__in=lesson_ids,
                assignment_type=Assignment.Type.ESSAY,
            )
        )

        self.stdout.write(
            f'Students: {len(students)} | Lessons: {len(lessons)} | '
            f'Code tasks: {len(code_assignments)} | Essay tasks: {len(essay_assignments)}'
        )

        random.shuffle(students)
        grouped = _split_into_groups(students)

        progress_created = code_created = essay_created = 0

        for group, user in grouped:
            num_lessons = random.randint(*_LESSON_COUNT[group])
            chosen_lessons = random.sample(lessons, min(num_lessons, len(lessons)))

            # --- UserLessonProgress ------------------------------------------
            for lesson in chosen_lessons:
                _, created = UserLessonProgress.objects.get_or_create(
                    user=user,
                    lesson=lesson,
                    defaults={
                        'is_completed': True,
                        'time_spent_seconds': random.randint(*_TIME_SEC[group]),
                        'attempt_count': random.randint(*_ATTEMPTS[group]),
                        'quiz_score': round(random.uniform(*_QUIZ_SCORE[group]), 2),
                    },
                )
                if created:
                    # auto_now=True blocks direct assignment; bypass via update()
                    UserLessonProgress.objects.filter(
                        user=user, lesson=lesson
                    ).update(completed_at=_rand_past_dt())
                    progress_created += 1

            score = random.randint(*_SCORE_RANGE[group])

            # --- CodeSubmission ----------------------------------------------
            for assignment in code_assignments:
                if CodeSubmission.objects.filter(
                    student=user, assignment=assignment
                ).exists():
                    continue

                sub = CodeSubmission.objects.create(
                    student=user,
                    assignment=assignment,
                    code_content=_CODE_CONTENT[group],
                    status=_CODE_STATUS[group],
                    output=_CODE_OUTPUT[group],
                    ai_feedback=_CODE_FEEDBACK[group],
                    score=score,
                )
                # auto_now_add=True blocks direct assignment; bypass via update()
                CodeSubmission.objects.filter(pk=sub.pk).update(
                    submitted_at=_rand_past_dt()
                )
                code_created += 1

            # --- EssaySubmission ---------------------------------------------
            for assignment in essay_assignments:
                if EssaySubmission.objects.filter(
                    student=user, assignment=assignment
                ).exists():
                    continue

                sub = EssaySubmission.objects.create(
                    student=user,
                    assignment=assignment,
                    text_content=_ESSAY_CONTENT[group],
                    ai_feedback=_ESSAY_FEEDBACK[group],
                    score=score,
                )
                EssaySubmission.objects.filter(pk=sub.pk).update(
                    created_at=_rand_past_dt()
                )
                essay_created += 1

        n_top = sum(1 for g, _ in grouped if g == _TOP)
        n_mid = sum(1 for g, _ in grouped if g == _MID)
        n_lag = sum(1 for g, _ in grouped if g == _LAG)

        self.stdout.write(
            f'Groups: top={n_top}, mid={n_mid}, lagging={n_lag}'
        )
        self.stdout.write(self.style.SUCCESS(
            f'Done: {progress_created} progress rows | '
            f'{code_created} code submissions | '
            f'{essay_created} essay submissions'
        ))
