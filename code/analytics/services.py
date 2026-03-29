"""
analytics/services.py
=====================
ML-сервис предиктивной аналитики.

Публичный API модуля:
    load_model()                        -- загружает model.pkl в память (вызывается из AppConfig.ready)
    get_model()                         -- возвращает загруженный Pipeline (singleton)
    build_feature_vector(user, lesson)  -- собирает вектор признаков из ORM
    predict_completion_prob(user, lesson) -> float  -- P(завершит урок)
    get_recommendations(user, course)   -- список уроков в порядке убывания риска невыполнения
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from courses.models import Course, Lesson
    from users.models import User

# ---------------------------------------------------------------------------
# Пути к артефактам
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_MODEL_PATH = os.path.join(_BASE_DIR, 'ai_module', 'model.pkl')

# Порядок признаков должен точно совпадать с тем, на чём обучалась модель.
# Источник истины — ai_module/meta.json → feature_cols.
FEATURE_COLS: list[str] = [
    'lesson_order',
    'module_order',
    'lesson_position_ratio',
    'prev_avg_score',
    'prev_avg_time',
    'prev_avg_attempts',
    'prev_completion_rate',
    'prev_lessons_done',
    'time_spent_seconds',
    'attempt_count',
    'quiz_taken',    # 1 = quiz was attempted, 0 = never opened
    'quiz_score',    # 0.0 when quiz_taken=0
]

# ---------------------------------------------------------------------------
# Singleton: модель загружается один раз при старте Django
# ---------------------------------------------------------------------------
_model = None  # type: ignore[assignment]


def load_model() -> None:
    """
    Загружает Pipeline из model.pkl в модульную переменную.
    Вызывается из AnalyticsConfig.ready().
    Безопасна при повторном вызове (idempotent).
    """
    global _model
    if _model is not None:
        return

    if not os.path.exists(_MODEL_PATH):
        import warnings
        warnings.warn(
            f'ML model not found at {_MODEL_PATH}. '
            'Run: python ml_analytics/train.py',
            stacklevel=2,
        )
        return

    import joblib
    _model = joblib.load(_MODEL_PATH)


def get_model():
    """Возвращает загруженный Pipeline или None, если модель не найдена."""
    return _model


# ---------------------------------------------------------------------------
# Сборка вектора признаков
# ---------------------------------------------------------------------------

def _get_lesson_position(lesson: 'Lesson') -> tuple[float, int, int]:
    """
    Возвращает (lesson_position_ratio, lesson_order, module_order).
    lesson_position_ratio = глобальный порядковый номер / всего уроков в курсе.
    """
    from courses.models import Lesson as LessonModel

    course = lesson.module.course
    all_lessons = list(
        LessonModel.objects
        .filter(module__course=course)
        .order_by('module__order', 'order')
        .values_list('id', flat=True)
    )
    total = len(all_lessons)
    try:
        global_idx = all_lessons.index(lesson.id) + 1  # 1-based
    except ValueError:
        global_idx = 1

    ratio = global_idx / max(total, 1)
    return ratio, lesson.order, lesson.module.order


def build_feature_vector(user: 'User', lesson: 'Lesson') -> np.ndarray:
    """
    Собирает вектор из 11 признаков для пары (user, lesson).

    Признаки истории ('prev_*') вычисляются по всем урокам того же курса,
    которые идут РАНЬШЕ текущего (по module__order, lesson__order).
    Текущий прогресс по уроку берётся из UserLessonProgress, если запись есть.
    """
    from analytics.models import UserLessonProgress

    lesson_position_ratio, lesson_order, module_order = _get_lesson_position(lesson)

    # Прогресс по предыдущим урокам того же курса
    prev_qs = (
        UserLessonProgress.objects
        .filter(
            user=user,
            lesson__module__course=lesson.module.course,
        )
        .exclude(lesson=lesson)
        .filter(
            lesson__module__order__lt=module_order
        )
        .values('quiz_score', 'time_spent_seconds', 'attempt_count', 'is_completed')
    )
    # Также включаем уроки того же модуля с меньшим порядком
    prev_same_module = (
        UserLessonProgress.objects
        .filter(
            user=user,
            lesson__module=lesson.module,
            lesson__order__lt=lesson_order,
        )
        .values('quiz_score', 'time_spent_seconds', 'attempt_count', 'is_completed')
    )

    prev_records = list(prev_qs) + list(prev_same_module)

    if prev_records:
        scores = [r['quiz_score'] for r in prev_records if r['quiz_score'] is not None]
        prev_avg_score = float(np.mean(scores)) if scores else 0.0
        prev_avg_time = float(np.mean([r['time_spent_seconds'] for r in prev_records]))
        prev_avg_attempts = float(np.mean([r['attempt_count'] for r in prev_records]))
        prev_completion_rate = float(
            np.mean([float(r['is_completed']) for r in prev_records])
        )
        prev_lessons_done = sum(1 for r in prev_records if r['is_completed'])
    else:
        prev_avg_score = 0.0
        prev_avg_time = 0.0
        prev_avg_attempts = 1.0
        prev_completion_rate = 0.0
        prev_lessons_done = 0

    # Текущий прогресс по этому уроку (если уже начат)
    try:
        current = UserLessonProgress.objects.get(user=user, lesson=lesson)
        time_spent = current.time_spent_seconds
        attempt_count = current.attempt_count
        quiz_taken = 1.0 if current.quiz_score is not None else 0.0
        quiz_score = current.quiz_score if current.quiz_score is not None else 0.0
    except UserLessonProgress.DoesNotExist:
        time_spent = 0
        attempt_count = 1
        quiz_taken = 0.0
        quiz_score = 0.0

    vector = np.array([
        lesson_order,
        module_order,
        lesson_position_ratio,
        prev_avg_score,
        prev_avg_time,
        prev_avg_attempts,
        prev_completion_rate,
        float(prev_lessons_done),
        float(time_spent),
        float(attempt_count),
        quiz_taken,
        quiz_score,
    ], dtype=np.float64)

    return vector.reshape(1, -1)


# ---------------------------------------------------------------------------
# Предсказание и рекомендации
# ---------------------------------------------------------------------------

def predict_completion_prob(user: 'User', lesson: 'Lesson') -> float:
    """
    Возвращает P(студент завершит урок) в диапазоне [0.0, 1.0].
    Если модель не загружена — возвращает 0.5 (нейтральное значение).
    """
    model = get_model()
    if model is None:
        return 0.5

    X = build_feature_vector(user, lesson)
    prob: float = model.predict_proba(X)[0, 1]
    return round(float(prob), 4)


def get_recommendations(
    user: 'User',
    course: 'Course',
    top_n: int = 5,
) -> list[dict]:
    """
    Возвращает список незавершённых уроков курса, отсортированных по убыванию
    риска провала (т.е. по возрастанию P(completion)).

    Формат каждого элемента:
        {
            'lesson_id': int,
            'lesson_title': str,
            'module_title': str,
            'completion_prob': float,   # P(завершит)
            'risk_score': float,        # 1 - completion_prob
        }
    """
    from analytics.models import UserLessonProgress
    from courses.models import Lesson

    # Уже завершённые уроки — исключаем
    completed_ids = set(
        UserLessonProgress.objects
        .filter(user=user, lesson__module__course=course, is_completed=True)
        .values_list('lesson_id', flat=True)
    )

    pending_lessons = list(
        Lesson.objects
        .filter(module__course=course)
        .exclude(id__in=completed_ids)
        .select_related('module__course')
        .order_by('module__order', 'order')
    )

    if not pending_lessons:
        return []

    model = get_model()

    results = []
    for lesson in pending_lessons:
        if model is not None:
            X = build_feature_vector(user, lesson)
            prob = round(float(model.predict_proba(X)[0, 1]), 4)
        else:
            prob = 0.5

        results.append({
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'module_title': lesson.module.title,
            'completion_prob': prob,
            'risk_score': round(1.0 - prob, 4),
        })

    # Сортируем: сначала уроки с наибольшим риском провала
    results.sort(key=lambda x: x['risk_score'], reverse=True)
    return results[:top_n]
