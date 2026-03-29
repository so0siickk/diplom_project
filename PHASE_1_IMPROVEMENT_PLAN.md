# PHASE_1_IMPROVEMENT_PLAN.md — Технический долг Этапа 1

## 1. Оптимизация БД (Django ORM)
- [x] `courses/views.py` — добавить `prefetch_related('modules__lessons')` в `CourseListAPIView` и `CourseDetailAPIView` (N+1 на вложенном сериализаторе)
- [x] `courses/views.py` — добавить `select_related('owner')` к тем же QuerySet-ам (N+1 на поле `owner.username`)
- [x] `courses/views.py` — добавить `prefetch_related` в SSR-вьюху `CourseDetailTemplateView`
- [x] `analytics/models.py` — добавить `db_index=True` на поля `user` и `lesson` в `UserLessonProgress` + составной индекс `progress_user_lesson_idx`
- [x] `courses/models.py` — добавить `db_index=True` на поле `order` в `Module` и `Lesson` (используется в `ordering`)

## 2. Улучшение RAG (LangChain)
- [x] `assistant/vector_store.py` — `RecursiveCharacterTextSplitter` с `separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]`
- [x] `assistant/vector_store.py` — метаданные чанков: `chunk_index`, `total_chunks`, полный набор ID
- [x] `assistant/vector_store.py` — дедупликация через `_delete_lesson_chunks` (удаление по `lesson_id` перед `add_documents`)

## 3. Автоматизация контента (PDF-парсинг)
- [x] `courses/models.py` — добавлено поле `pdf_file = models.FileField(upload_to='lessons/pdfs/', ...)`
- [x] Создана миграция `courses/migrations/0003_add_lesson_pdf_file.py`
- [x] `courses/signals.py` — `post_save`-сигнал: при непустом `pdf_file` запускает `index_pdf_async`
- [x] `assistant/pdf_indexer.py` — `PyPDFLoader` → `RecursiveCharacterTextSplitter` → ChromaDB в `threading.Thread`
- [x] `courses/apps.py` — подключён `import courses.signals` в `ready()`

## 4. Безопасность и хардкод
- [x] `config/settings.py` — переход на `django-environ`; все переменные через `env()`
- [x] `config/settings.py` — `DATABASE_URL` через `env.db()` (PostgreSQL-ready)
- [x] Создан `.env.example` с заглушками
- [x] Создан `code/.gitignore` с `.env`, `media/`, `chroma_db/`, `.venv/`
- [x] Хардкод `SECRET_KEY` удалён из `settings.py`, перенесён в `.env`
