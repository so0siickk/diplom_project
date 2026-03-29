from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Lesson


@receiver(post_save, sender=Lesson)
def on_lesson_saved(sender, instance: Lesson, **kwargs) -> None:
    """
    При сохранении урока с PDF-файлом запускает фоновую индексацию.
    Срабатывает и при создании, и при обновлении, если pdf_file задан.
    """
    if not instance.pdf_file:
        return

    from assistant.pdf_indexer import index_pdf_async
    index_pdf_async(instance)
