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
