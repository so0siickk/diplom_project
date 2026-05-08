from django.db import models
from django.conf import settings


class Course(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField(max_length=200, verbose_name="Название курса")
    description = models.TextField(verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"


class Module(models.Model):
    course = models.ForeignKey(Course, related_name='modules', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name="Название модуля")
    description = models.TextField(blank=True, verbose_name="Описание модуля")
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядковый номер")

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    class Meta:
        ordering = ['order']
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"


class Lesson(models.Model):
    module = models.ForeignKey(Module, related_name='lessons', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, verbose_name="Название урока")
    content = models.TextField(verbose_name="Текст лекции (для AI)")
    video_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на видео")
    pdf_file = models.FileField(
        upload_to='lessons/pdfs/',
        blank=True,
        null=True,
        verbose_name="PDF-материал",
    )
    order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Порядковый номер")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"


def _document_upload_path(instance: "CourseDocument", filename: str) -> str:
    """Сохраняет файлы в course_documents/<course_id>/<filename>."""
    return f"course_documents/{instance.course_id}/{filename}"


class CourseDocument(models.Model):
    """
    Загружаемый преподавателем документ (PDF или DOCX), привязанный к курсу.

    После успешного парсинга extracted_text передаётся в RAG-сервис
    для векторизации и сохранения в ChromaDB.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает парсинга"
        PARSED  = "parsed",  "Текст извлечён"
        INDEXED = "indexed", "Проиндексировано в RAG"
        ERROR   = "error",   "Ошибка"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Курс",
    )
    file = models.FileField(
        upload_to=_document_upload_path,
        verbose_name="Файл",
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name="Исходное имя файла",
    )
    extracted_text = models.TextField(
        blank=True,
        default="",
        verbose_name="Извлечённый текст",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="Статус",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name="Сообщение об ошибке",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
        verbose_name="Загружено преподавателем",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Документ курса"
        verbose_name_plural = "Документы курса"

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.course.title})"


class Assignment(models.Model):
    class Type(models.TextChoices):
        ESSAY       = 'essay',        'Эссе'
        CODE        = 'code',         'Код'
        AI_DIALOG   = 'ai_dialog',    'ИИ-диалог'
        QUIZ        = 'quiz',         'Тест'
        FILE_UPLOAD = 'file_upload',  'Загрузка файла'

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='course_assignments',
        verbose_name='Урок',
    )
    title = models.CharField(max_length=255, verbose_name='Название задания')
    description = models.TextField(verbose_name='Условие задания')
    assignment_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.ESSAY,
        db_index=True,
        verbose_name='Тип задания',
    )
    content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Специфичные данные задания',
    )
    max_score = models.IntegerField(default=10, verbose_name='Максимальный балл')
    max_attempts = models.IntegerField(
        default=1,
        verbose_name='Максимальное число попыток',
        help_text='0 — безлимит',
    )
    order = models.IntegerField(default=0, db_index=True, verbose_name='Порядок')

    class Meta:
        ordering = ['order']
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'

    def __str__(self) -> str:
        return f'{self.lesson.title} / {self.title}'


def _material_upload_path(instance: "LessonMaterial", filename: str) -> str:
    return f"lesson_materials/{instance.lesson_id}/{filename}"


class LessonMaterial(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name='Урок',
    )
    title = models.CharField(max_length=255, verbose_name='Название материала')
    file = models.FileField(upload_to=_material_upload_path, verbose_name='Файл')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Материал урока'
        verbose_name_plural = 'Материалы урока'

    def __str__(self) -> str:
        return f'{self.lesson.title} / {self.title}'


class Quiz(models.Model):
    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name='quiz',
        verbose_name='Урок',
    )
    title = models.CharField(max_length=255, verbose_name='Название теста')

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'

    def __str__(self) -> str:
        return f'{self.lesson.title} / {self.title}'


class Question(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Тест',
    )
    text = models.TextField(verbose_name='Текст вопроса')
    is_multiple_choice = models.BooleanField(
        default=False,
        verbose_name='Множественный выбор',
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'

    def __str__(self) -> str:
        return self.text[:80]


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        verbose_name='Вопрос',
    )
    text = models.CharField(max_length=500, verbose_name='Текст варианта')
    is_correct = models.BooleanField(default=False, verbose_name='Правильный')

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответа'

    def __str__(self) -> str:
        return self.text[:80]


class Enrollment(models.Model):
    """Records that a user is enrolled in a course."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'course')]
        ordering = ['-enrolled_at']
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'

    def __str__(self) -> str:
        return f'{self.user.username} -> {self.course.title}'
