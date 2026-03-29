import threading
from langchain_community.document_loaders import PyPDFLoader
from .vector_store import _TEXT_SPLITTER, _delete_lesson_chunks, get_vectorstore


def _run_pdf_indexing(lesson) -> None:
    """
    Выполняется в отдельном потоке.
    Парсит PDF, разбивает на чанки, сохраняет в ChromaDB.
    """
    pdf_path = lesson.pdf_file.path
    course_title = lesson.module.course.title

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    for page in pages:
        page.metadata.update({
            "source": "pdf",
            "course_id": str(lesson.module.course_id),
            "lesson_id": str(lesson.id),
            "lesson_title": lesson.title,
        })

    splits = _TEXT_SPLITTER.split_documents(pages)

    for idx, chunk in enumerate(splits):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["total_chunks"] = len(splits)
        chunk.metadata.setdefault("course_title", course_title)

    vectorstore = get_vectorstore()
    _delete_lesson_chunks(vectorstore, lesson.id)
    vectorstore.add_documents(documents=splits)

    print(f"[pdf_indexer] Урок '{lesson.title}': проиндексировано {len(splits)} фрагментов.")


def index_pdf_async(lesson) -> None:
    """Запускает индексацию PDF в фоновом потоке."""
    thread = threading.Thread(
        target=_run_pdf_indexing,
        args=(lesson,),
        daemon=True,
    )
    thread.start()
