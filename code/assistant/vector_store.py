import os
from django.conf import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document


CHROMA_DB_DIR = os.path.join(settings.BASE_DIR, 'chroma_db')

_TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
)


def get_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    return Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embeddings,
        collection_name="course_materials",
    )


def _delete_lesson_chunks(vectorstore: Chroma, lesson_id: int) -> None:
    """Удаляет все чанки урока перед повторной индексацией."""
    vectorstore._collection.delete(where={"lesson_id": str(lesson_id)})


def index_lesson_content(lesson, course_title: str) -> int:
    """
    Индексирует один урок: удаляет старые чанки, создаёт новые с метаданными.
    Возвращает количество записанных фрагментов.
    """
    if not lesson.content:
        return 0

    full_text = (
        f"Курс: {course_title}. "
        f"Тема урока: {lesson.title}. "
        f"Содержание: {lesson.content}"
    )
    raw_doc = Document(
        page_content=full_text,
        metadata={
            "source": "lesson",
            "course_id": str(lesson.module.course_id),
            "lesson_id": str(lesson.id),
            "lesson_title": lesson.title,
        },
    )

    splits = _TEXT_SPLITTER.split_documents([raw_doc])

    for idx, chunk in enumerate(splits):
        chunk.metadata["chunk_index"] = idx
        chunk.metadata["total_chunks"] = len(splits)

    vectorstore = get_vectorstore()
    _delete_lesson_chunks(vectorstore, lesson.id)
    vectorstore.add_documents(documents=splits)

    return len(splits)


def index_course_content(course) -> None:
    """
    Переиндексирует все уроки курса.
    """
    print(f"Начинаем индексацию курса: {course.title}")
    total = 0

    for module in course.modules.prefetch_related('lessons').all():
        for lesson in module.lessons.all():
            total += index_lesson_content(lesson, course.title)

    if total == 0:
        print("Нет контента для индексации.")
    else:
        print(f"Успешно проиндексировано {total} фрагментов.")