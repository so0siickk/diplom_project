"""
dataset_builder.py
==================
Подключается к Django ORM и собирает агрегированные признаки по парам
(пользователь, урок) для обучения ML-модели.

Запуск как скрипт:
    python ml_analytics/dataset_builder.py [--output dataset.csv]

Признаки (feature space)
------------------------
По уроку в рамках курса:
  lesson_order          — порядковый номер урока в модуле
  module_order          — порядковый номер модуля в курсе
  lesson_position_ratio — lesson_order / общее число уроков в курсе (0–1)

Накопленная история студента ДО данного урока:
  prev_avg_score        — средний балл за предыдущие уроки (0–1)
  prev_avg_time         — среднее время на предыдущих уроках (сек)
  prev_avg_attempts     — среднее число попыток на предыдущих уроках
  prev_completion_rate  — доля завершённых предыдущих уроков (0–1)
  prev_lessons_done     — абсолютное число завершённых уроков до этого

Текущий урок:
  time_spent_seconds    — время на текущем уроке
  attempt_count         — число попыток на текущем уроке
  quiz_score            — балл за текущий тест

Целевая переменная:
  target (int 0/1)      — 1, если урок завершён (is_completed=True)
"""

import os
import sys
import argparse
import django

# --- Bootstrap Django ---
_CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'code'))
sys.path.insert(0, _CODE_DIR)
os.chdir(_CODE_DIR)  # SQLite path resolves relative to code/
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
# -----------------------

import pandas as pd
from django.db.models import Avg, Count, Q

from analytics.models import UserLessonProgress
from courses.models import Course


def _build_course_lesson_map() -> dict[int, dict[int, dict]]:
    """
    Возвращает структуру:
      { course_id: { lesson_id: {order, module_order, total_in_course} } }
    """
    course_map: dict[int, dict[int, dict]] = {}
    for course in Course.objects.prefetch_related('modules__lessons').all():
        lessons_info: dict[int, dict] = {}
        total = sum(m.lessons.count() for m in course.modules.all())
        global_order = 0
        for module in course.modules.order_by('order').all():
            for lesson in module.lessons.order_by('order').all():
                global_order += 1
                lessons_info[lesson.id] = {
                    'lesson_order': lesson.order,
                    'module_order': module.order,
                    'lesson_position_ratio': global_order / max(total, 1),
                    'total_lessons_in_course': total,
                }
        course_map[course.id] = lessons_info
    return course_map


def build_dataset() -> pd.DataFrame:
    """
    Основная функция. Возвращает DataFrame с признаками и целевой переменной.
    """
    course_map = _build_course_lesson_map()

    records = (
        UserLessonProgress.objects
        .select_related('user', 'lesson__module__course')
        .order_by('user_id', 'lesson__module__course_id', 'lesson__order')
        .values(
            'id',
            'user_id',
            'lesson_id',
            'lesson__module__course_id',
            'lesson__module__order',
            'lesson__order',
            'is_completed',
            'time_spent_seconds',
            'attempt_count',
            'quiz_score',
        )
    )

    rows = []
    # Накапливаем историю по каждому пользователю в каждом курсе
    # ключ: (user_id, course_id) → list of предыдущих записей
    history: dict[tuple[int, int], list[dict]] = {}

    for rec in records:
        uid = rec['user_id']
        cid = rec['lesson__module__course_id']
        lid = rec['lesson_id']
        key = (uid, cid)

        prev = history.get(key, [])

        # Признаки из истории
        if prev:
            prev_scores = [r['quiz_score'] for r in prev if r['quiz_score'] is not None]
            prev_times = [r['time_spent_seconds'] for r in prev]
            prev_attempts = [r['attempt_count'] for r in prev]
            prev_completed = [r['is_completed'] for r in prev]
            prev_avg_score = sum(prev_scores) / len(prev_scores) if prev_scores else 0.0
            prev_avg_time = sum(prev_times) / len(prev_times) if prev_times else 0.0
            prev_avg_attempts = sum(prev_attempts) / len(prev_attempts) if prev_attempts else 1.0
            prev_completion_rate = sum(prev_completed) / len(prev_completed)
            prev_lessons_done = sum(prev_completed)
        else:
            prev_avg_score = 0.0
            prev_avg_time = 0.0
            prev_avg_attempts = 1.0
            prev_completion_rate = 0.0
            prev_lessons_done = 0

        # Позиционные признаки урока
        lesson_meta = course_map.get(cid, {}).get(lid, {})
        lesson_order = lesson_meta.get('lesson_order', 0)
        module_order = lesson_meta.get('module_order', 0)
        lesson_position_ratio = lesson_meta.get('lesson_position_ratio', 0.0)

        rows.append({
            # Мета (не используется как признак, нужна для отладки)
            'user_id': uid,
            'lesson_id': lid,
            'course_id': cid,
            # Позиционные признаки
            'lesson_order': lesson_order,
            'module_order': module_order,
            'lesson_position_ratio': lesson_position_ratio,
            # История студента
            'prev_avg_score': round(prev_avg_score, 4),
            'prev_avg_time': round(prev_avg_time, 2),
            'prev_avg_attempts': round(prev_avg_attempts, 4),
            'prev_completion_rate': round(prev_completion_rate, 4),
            'prev_lessons_done': prev_lessons_done,
            # Текущий урок
            'time_spent_seconds': rec['time_spent_seconds'],
            'attempt_count': rec['attempt_count'],
            'quiz_score': rec['quiz_score'] if rec['quiz_score'] is not None else 0.0,
            # Цель
            'target': int(rec['is_completed']),
        })

        # Обновляем историю
        history.setdefault(key, []).append({
            'quiz_score': rec['quiz_score'],
            'time_spent_seconds': rec['time_spent_seconds'],
            'attempt_count': rec['attempt_count'],
            'is_completed': rec['is_completed'],
        })

    df = pd.DataFrame(rows)
    print(f'[dataset_builder] Записей: {len(df)}, '
          f'target=1: {df["target"].sum()} ({df["target"].mean():.1%})')
    return df


FEATURE_COLS = [
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
    'quiz_score',
]
TARGET_COL = 'target'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build ML dataset from Django ORM')
    parser.add_argument('--output', default='ml_analytics/dataset.csv')
    args = parser.parse_args()

    df = build_dataset()
    df.to_csv(args.output, index=False)
    print(f'[dataset_builder] Сохранено в {args.output}')
    print(df[FEATURE_COLS + [TARGET_COL]].describe().to_string())
