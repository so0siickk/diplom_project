from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from courses.models import Lesson


class UserLessonProgress(models.Model):
    """Агрегированный прогресс пользователя по уроку."""

    PROFILE_CHOICES = (
        ('top', 'Отличник'),
        ('speedrunner', 'Спидраннер'),
        ('struggling', 'Отстающий'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='progress',
        db_index=True,
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='student_progress',
        db_index=True,
    )
    is_completed = models.BooleanField(default=False, verbose_name='Пройден')
    completed_at = models.DateTimeField(auto_now=True, verbose_name='Дата последнего действия')

    # --- Поля для ML ---
    time_spent_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name='Время на уроке (сек)',
    )
    attempt_count = models.PositiveIntegerField(
        default=1,
        verbose_name='Число попыток',
    )
    quiz_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Результат теста (0–1)',
    )

    class Meta:
        unique_together = ['user', 'lesson']
        indexes = [
            models.Index(fields=['user', 'lesson'], name='progress_user_lesson_idx'),
        ]
        verbose_name = 'Прогресс по уроку'
        verbose_name_plural = 'Прогресс обучения'

    def __str__(self) -> str:
        score = f'{self.quiz_score:.2f}' if self.quiz_score is not None else '—'
        return (
            f'{"✅" if self.is_completed else "⏳"} '
            f'{self.user.username} → {self.lesson.title} '
            f'[{self.time_spent_seconds}с / x{self.attempt_count} / {score}]'
        )


class QuizAttempt(models.Model):
    """Отдельная попытка прохождения теста по уроку."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        db_index=True,
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        db_index=True,
    )
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name='Балл за попытку (0–1)',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Попытка теста'
        verbose_name_plural = 'Попытки тестов'

    def __str__(self) -> str:
        return f'{self.user.username} → {self.lesson.title}: {self.score:.2f}'
