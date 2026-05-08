"""
assistant/services/vectorizer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Сервис векторизации текстового контента CourseDocument для RAG-ассистента.

Вписывается в существующую инфраструктуру ChromaDB:
  - reuses get_vectorstore() и _TEXT_SPLITTER из assistant/vector_store.py
  - metadata-схема совместима с rag.py (тот же фильтр по course_id)
  - паттерн фонового потока — как в assistant/pdf_indexer.py

Жизненный цикл статуса CourseDocument после вызова этого модуля:
    PARSED  → (поток) → INDEXED
                    ↘  ERROR (если ChromaDB недоступна)
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from langchain.docstore.document import Document

from assistant.vector_store import _TEXT_SPLITTER, get_vectorstore

if TYPE_CHECKING:
    # Отложенный импорт избегает циклической зависимости:
    # courses → assistant, assistant → courses (только при TYPE_CHECKING)
    from courses.models import CourseDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Внутренние утилиты ChromaDB
# ---------------------------------------------------------------------------

def _delete_document_chunks(document_id: int) -> None:
    """
    Удаляет все чанки документа из ChromaDB перед повторной индексацией.

    Использует тот же паттерн, что _delete_lesson_chunks в vector_store.py:
    фильтр по метаданным коллекции.
    """
    vectorstore = get_vectorstore()
    vectorstore._collection.delete(where={"document_id": str(document_id)})
    logger.debug("Удалены старые чанки document_id=%d", document_id)


# ---------------------------------------------------------------------------
# Публичный синхронный API
# ---------------------------------------------------------------------------

def index_course_document(
    document_id: int,
    course_id: int,
    text: str,
    original_filename: str = "",
) -> int:
    """
    Разбивает текст на чанки и сохраняет их в ChromaDB с метаданными.

    Метаданные каждого чанка:
        source          = "document"         — тип источника
        document_id     = str(document_id)   — для удаления при переиндексации
        course_id       = str(course_id)     — для фильтрации запросов RAG
        original_filename                    — для отладки и логирования
        chunk_index     = int                — позиция чанка в документе
        total_chunks    = int                — общий счётчик

    Args:
        document_id:       PK записи CourseDocument.
        course_id:         PK родительского Course (используется RAG-фильтром).
        text:              извлечённый текст документа (из extracted_text).
        original_filename: исходное имя файла (только для метаданных).

    Returns:
        Количество проиндексированных чанков (0 если текст пуст).

    Raises:
        RuntimeError: если ChromaDB недоступна или HuggingFace-модель не загружена.
    """
    text = text.strip()
    if not text:
        logger.warning(
            "document_id=%d: пустой текст, индексация пропущена.", document_id
        )
        return 0

    # Оборачиваем текст в LangChain Document с базовыми метаданными.
    # chunk_index / total_chunks добавляются после сплиттера (размер неизвестен заранее).
    raw_doc = Document(
        page_content=text,
        metadata={
            "source": "document",
            "document_id": str(document_id),
            "course_id": str(course_id),
            "original_filename": original_filename,
        },
    )

    # Используем общий сплиттер проекта (chunk_size=1000, overlap=200)
    splits = _TEXT_SPLITTER.split_documents([raw_doc])

    for idx, chunk in enumerate(splits):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["total_chunks"] = len(splits)

    vectorstore = get_vectorstore()
    # Атомарно: сначала чистим старые чанки (на случай переиндексации)
    vectorstore._collection.delete(where={"document_id": str(document_id)})
    vectorstore.add_documents(documents=splits)

    logger.info(
        "document_id=%d (course_id=%d) проиндексирован: %d чанков, файл=%r",
        document_id,
        course_id,
        len(splits),
        original_filename,
    )
    return len(splits)


# ---------------------------------------------------------------------------
# Фоновый поток — паттерн из pdf_indexer.py
# ---------------------------------------------------------------------------

def _run_document_indexing(
    document_id: int,
    course_id: int,
    text: str,
    original_filename: str,
) -> None:
    """
    Worker-функция для daemon-потока.

    Принимает только примитивные типы (не ORM-объект), чтобы избежать
    проблем с закрытием Django DB-соединения в дочернем потоке.
    После завершения индексации обновляет статус документа через ORM
    (Django автоматически открывает новое соединение в потоке при первом обращении).
    """
    # Импорт внутри функции — разрывает потенциальный цикл на уровне модулей
    from courses.models import CourseDocument

    try:
        count = index_course_document(
            document_id=document_id,
            course_id=course_id,
            text=text,
            original_filename=original_filename,
        )
        # Обновляем статус одним UPDATE-запросом (без загрузки всего объекта)
        CourseDocument.objects.filter(pk=document_id).update(
            status=CourseDocument.Status.INDEXED,
        )
        logger.info(
            "[vectorizer] document_id=%d: индексация завершена (%d чанков).",
            document_id,
            count,
        )

    except Exception:
        # Исключение в daemon-потоке не долетает до основного потока —
        # записываем подробности в лог и помечаем документ как ошибочный.
        logger.exception(
            "[vectorizer] document_id=%d: ошибка индексации в фоновом потоке.",
            document_id,
        )
        try:
            CourseDocument.objects.filter(pk=document_id).update(
                status=CourseDocument.Status.ERROR,
                error_message="Ошибка векторизации. Подробности — в логах сервера.",
            )
        except Exception:
            logger.exception(
                "[vectorizer] Не удалось обновить статус document_id=%d после ошибки.",
                document_id,
            )


def index_document_async(document: "CourseDocument") -> None:
    """
    Запускает индексацию документа в фоновом daemon-потоке.

    Возвращает управление немедленно — HTTP-ответ не блокируется.
    Статус документа обновится до INDEXED (или ERROR) асинхронно.

    Args:
        document: сохранённый объект CourseDocument со статусом PARSED.
                  Из него извлекаются только примитивные значения — сам
                  объект в поток не передаётся.
    """
    thread = threading.Thread(
        target=_run_document_indexing,
        args=(
            document.id,
            document.course_id,
            document.extracted_text,
            document.original_filename,
        ),
        daemon=True,
        name=f"vectorizer-doc-{document.id}",  # имя для отладки в thread dump
    )
    thread.start()
    logger.debug(
        "Запущен фоновый поток %r для document_id=%d",
        thread.name,
        document.id,
    )
