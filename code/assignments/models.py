import uuid as uuid_module

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from courses.models import Assignment as CourseAssignment, Lesson


class OpenAssignment(models.Model):
    """
    Задание с открытым ответом, создаваемое преподавателем.

    Привязывается к уроку (опционально). Содержит публичное описание задания
    для студента и приватный эталонный ответ / критерии оценки, которые
    передаются LLM-грейдеру, но скрыты от студентов.
    """

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="assignments",
        null=True,
        blank=True,
        verbose_name="Урок",
        help_text="Необязательная привязка к уроку курса.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_assignments",
        verbose_name="Автор задания",
    )
    title = models.CharField(max_length=255, verbose_name="Название задания")
    description = models.TextField(
        verbose_name="Условие задания",
        help_text="Текст задания, который видит студент.",
    )
    # Хранится только на сервере — не попадает в студенческий сериализатор
    reference_answer = models.TextField(
        verbose_name="Эталонный ответ / критерии оценки",
        help_text="Используется как контекст для LLM-грейдера. Студентам не показывается.",
    )
    max_score = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Максимальный балл",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно",
        help_text="Неактивные задания не принимают новые ответы.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Задание"
        verbose_name_plural = "Задания"

    def __str__(self) -> str:
        return self.title


class AssignmentSubmission(models.Model):
    """
    Ответ студента на задание.

    Жизненный цикл статуса:
        PENDING → AI_CHECKED (после ответа LLM) → APPROVED (после решения преподавателя)
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        AI_CHECKED = "ai_checked", "Проверено AI"
        APPROVED = "approved", "Утверждено преподавателем"

    assignment = models.ForeignKey(
        OpenAssignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Задание",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
        verbose_name="Студент",
    )
    answer_text = models.TextField(verbose_name="Ответ студента")
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Статус",
    )
    # Финальный балл — устанавливается преподавателем (может совпасть с AI-оценкой)
    final_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Итоговый балл",
    )
    teacher_comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Комментарий преподавателя",
    )

    class Meta:
        # Один студент — один ответ на одно задание
        unique_together = [("assignment", "student")]
        ordering = ["-submitted_at"]
        verbose_name = "Ответ студента"
        verbose_name_plural = "Ответы студентов"

    def __str__(self) -> str:
        return f"{self.student.username} → {self.assignment.title}"


class AIEvaluation(models.Model):
    """
    Результат автоматической оценки ответа студента языковой моделью.

    Связь OneToOne гарантирует, что один ответ получает ровно одну AI-оценку.
    При необходимости переоценки старая запись удаляется и создаётся новая.
    """

    submission = models.OneToOneField(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name="ai_evaluation",
        verbose_name="Ответ студента",
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Оценка AI (0–100)",
    )
    feedback = models.TextField(verbose_name="Текстовый фидбек от AI")
    model_name = models.CharField(
        max_length=100,
        default="stub",
        verbose_name="Название модели LLM",
    )
    # Служебные поля для мониторинга расходов API
    prompt_tokens = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Токенов в промпте"
    )
    completion_tokens = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Токенов в ответе"
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Оценка AI"
        verbose_name_plural = "Оценки AI"

    def __str__(self) -> str:
        return f"AI score {self.score}/100 for «{self.submission}»"


# ---------------------------------------------------------------------------
# CodeSubmission — попытка студента на задание типа «code»
# ---------------------------------------------------------------------------

class CodeSubmission(models.Model):
    """
    Хранит одну попытку студента на задание типа Assignment.Type.CODE.

    Жизненный цикл статуса:
        PENDING → SUCCESS / FAILED (по результату subprocess)
    AI-фидбек и оценка пишутся синхронно после выполнения кода.
    Множественные попытки разрешены — студент может итерировать код.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'В обработке'
        SUCCESS = 'success', 'Выполнено успешно'
        FAILED  = 'failed',  'Ошибка выполнения'

    uuid = models.UUIDField(
        default=uuid_module.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name='UUID попытки',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='code_submissions',
        verbose_name='Студент',
    )
    assignment = models.ForeignKey(
        CourseAssignment,
        on_delete=models.CASCADE,
        related_name='code_submissions',
        verbose_name='Задание',
    )
    code_content = models.TextField(verbose_name='Код студента')
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Статус выполнения',
    )
    output = models.TextField(
        blank=True,
        default='',
        verbose_name='Вывод выполнения (stdout + stderr)',
    )
    ai_feedback = models.TextField(
        blank=True,
        default='',
        verbose_name='Фидбек от AI',
    )
    score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Оценка AI',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Попытка кода'
        verbose_name_plural = 'Попытки кода'

    def __str__(self) -> str:
        return f'{self.student.username} → {self.assignment.title} [{self.uuid}]'


# ---------------------------------------------------------------------------
# EssaySubmission — попытка студента на задание типа «essay»
# ---------------------------------------------------------------------------

class EssaySubmission(models.Model):
    """
    Письменный ответ студента на задание типа Assignment.Type.ESSAY.

    Множественные попытки разрешены — студент может улучшать ответ.
    AI-фидбек и оценка пишутся синхронно сразу после отправки.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='essay_submissions',
        verbose_name='Студент',
    )
    assignment = models.ForeignKey(
        CourseAssignment,
        on_delete=models.CASCADE,
        related_name='essay_submissions',
        verbose_name='Задание',
    )
    text_content = models.TextField(verbose_name='Текст ответа')
    ai_feedback = models.TextField(
        blank=True,
        null=True,
        verbose_name='Фидбек от AI',
    )
    score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Оценка AI',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Попытка эссе'
        verbose_name_plural = 'Попытки эссе'

    def __str__(self) -> str:
        return f'{self.student.username} → {self.assignment.title}'
