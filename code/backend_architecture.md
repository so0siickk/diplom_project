# Backend Architecture — LMS Platform

> **Актуально на:** 2026-04-21
> **Стек:** Python 3.12 · Django 5.0.1 · DRF 3.16 · PostgreSQL 15 · ChromaDB 0.5 · LangChain 0.3

---

## Содержание

1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Структура приложений](#2-структура-приложений)
3. [Модели данных и схема БД](#3-модели-данных-и-схема-бд)
4. [REST API — полный реестр эндпоинтов](#4-rest-api--полный-реестр-эндпоинтов)
5. [Сервисный слой (бизнес-логика)](#5-сервисный-слой-бизнес-логика)
6. [Внешние интеграции](#6-внешние-интеграции)
7. [ML-подсистема](#7-ml-подсистема)
8. [Инфраструктура и контейнеризация](#8-инфраструктура-и-контейнеризация)
9. [Аутентификация и авторизация](#9-аутентификация-и-авторизация)
10. [Конфигурация и переменные окружения](#10-конфигурация-и-переменные-окружения)

---

## 1. Обзор архитектуры

Платформа реализована как **модульный монолит**: единое Django-приложение, разделённое на независимые Django-app'ы с чёткими границами ответственности. Фронтенд (React SPA) взаимодействует с бэкендом **исключительно через версионированный REST API** `/api/v1/` и `/analytics/api/`.

```
┌─────────────────────────────────────────────────────────────────┐
│                     React SPA (порт 5173)                       │
│               Axios + JWT Bearer token interceptor              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/JSON
┌──────────────────────────▼──────────────────────────────────────┐
│               Django 5 + DRF (порт 8000)                        │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ courses  │  │analytics │  │ assistant  │  │ assignments │  │
│  └────┬─────┘  └────┬─────┘  └─────┬──────┘  └──────┬──────┘  │
│       │              │              │                 │         │
│  ┌────▼──────────────▼──────────────▼─────────────────▼──────┐ │
│  │                   users / config                           │ │
│  └──────────────────────────────────────────────────────────-─┘ │
└───────┬──────────────────┬──────────────────────────────────────┘
        │                  │
┌───────▼──────┐  ┌────────▼──────────────────────────────────────┐
│ PostgreSQL 15│  │  ChromaDB (embedded, ./chroma_db/)             │
│   lms_db     │  │  collection: course_materials                  │
└──────────────┘  └───────────────────────────────────────────────┘
```

---

## 2. Структура приложений

### Дерево директорий

```
code/                          ← корень Django-проекта
├── config/                    ← settings, urls, wsgi
├── users/                     ← расширенная модель User с ролями
├── courses/                   ← LMS-ядро: контент + документы
│   └── services/
│       └── document_parser.py ← извлечение текста PDF/DOCX
├── analytics/                 ← прогресс студентов + ML-рекомендации
│   └── management/commands/
│       └── generate_synthetic_data.py
├── assistant/                 ← RAG-ассистент на GigaChat + ChromaDB
│   ├── services/
│   │   └── vectorizer.py      ← векторизация CourseDocument
│   ├── vector_store.py        ← ChromaDB-синглтон, индексация уроков
│   ├── pdf_indexer.py         ← асинхронная индексация PDF-вложений
│   └── rag.py                 ← LangChain RetrievalQA цепочка
├── assignments/               ← задания с открытым ответом + AI-грейдер
│   └── services/
│       └── ai_grader.py       ← формирование промпта + вызов LLM
└── manage.py

ml_analytics/                  ← offline ML-конвейер (вне Django)
├── dataset_builder.py         ← сборка датасета из ORM
├── train.py                   ← обучение HistGBDT + GridSearchCV
└── evaluate.py                ← оценка метрик на тестовой выборке

ai_module/                     ← артефакты ML
├── model.pkl                  ← обученный sklearn Pipeline
└── meta.json                  ← гиперпараметры, метрики, feature importances
```

### Описание app'ов

| App | Назначение |
|---|---|
| `config` | Настройки, корневой `urls.py`, WSGI-точка входа |
| `users` | Расширенный `AbstractUser` с полем `role` (student/teacher) |
| `courses` | Модели контента (Course→Module→Lesson→Enrollment), загрузка документов (CourseDocument), CRUD API |
| `analytics` | Отслеживание прогресса студентов (UserLessonProgress), ML-рекомендации, дашборд преподавателя |
| `assistant` | RAG-пайплайн: векторизация контента уроков и документов, семантический поиск, генерация ответов через GigaChat |
| `assignments` | Задания с открытым ответом (OpenAssignment), приём ответов студентов (AssignmentSubmission), AI-проверка (AIEvaluation) |

---

## 3. Модели данных и схема БД

### 3.1 Диаграмма связей (ERD)

```
User (users_user)
 │
 ├─── Course.owner ──────────────────────── Course (courses_course)
 │                                             │
 ├─── Enrollment.user ──────────────────── Enrollment.course
 │                                             │
 ├─── UserLessonProgress.user               Module.course ──── Module (courses_module)
 │                                             │                  │
 ├─── QuizAttempt.user                      Lesson.module ──── Lesson (courses_lesson)
 │                                             │
 ├─── AssignmentSubmission.student         UserLessonProgress.lesson
 │                                         QuizAttempt.lesson
 ├─── CourseDocument.uploaded_by           OpenAssignment.lesson (nullable)
 │
 └─── OpenAssignment.created_by ────────── OpenAssignment (assignments)
                                                │
                                           AssignmentSubmission.assignment
                                                │
                                           AIEvaluation.submission (1:1)

CourseDocument.course ──────────────────── Course
```

### 3.2 Модели по приложениям

#### `users` — Пользователи

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `username` | CharField | Уникальный логин |
| `email` | EmailField | |
| `password` | CharField | Хэш (Django PBKDF2) |
| `role` | CharField | `student` / `teacher` (default: `student`) |
| *наследует* | AbstractUser | first\_name, last\_name, is\_staff, is\_active, … |

---

#### `courses` — Учебный контент

**Course**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `owner` | FK → User | Преподаватель-автор |
| `title` | CharField(200) | |
| `description` | TextField | |
| `created_at` | DateTimeField | auto\_now\_add |

**Module** *(ordering: `order`)*

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `course` | FK → Course | CASCADE, related\_name=`modules` |
| `title` | CharField(200) | |
| `description` | TextField | blank |
| `order` | PositiveIntegerField | db\_index |

**Lesson** *(ordering: `order`)*

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `module` | FK → Module | CASCADE, related\_name=`lessons` |
| `title` | CharField(200) | |
| `content` | TextField | Текст лекции — основа для RAG |
| `video_url` | URLField | nullable |
| `pdf_file` | FileField | `upload_to=lessons/pdfs/`, nullable |
| `order` | PositiveIntegerField | db\_index |

**Enrollment**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `user` | FK → User | CASCADE |
| `course` | FK → Course | CASCADE |
| `enrolled_at` | DateTimeField | auto\_now\_add |
| *constraint* | unique\_together | `(user, course)` |

**CourseDocument**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `course` | FK → Course | CASCADE, related\_name=`documents` |
| `uploaded_by` | FK → User | SET\_NULL nullable |
| `file` | FileField | `course_documents/<course_id>/` |
| `original_filename` | CharField(255) | |
| `extracted_text` | TextField | Сырой текст после парсинга |
| `status` | CharField | `pending` → `parsed` → `indexed` / `error` |
| `error_message` | TextField | blank; детали сбоя |
| `uploaded_at` | DateTimeField | auto\_now\_add |

> **Жизненный цикл статуса:**
> `PENDING` *(файл сохранён)* → `PARSED` *(текст извлечён, HTTP-ответ отдан)* → `INDEXED` *(вектора в ChromaDB, фоновый поток)* / `ERROR`

---

#### `analytics` — Аналитика прогресса

**UserLessonProgress**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `user` | FK → User | CASCADE, db\_index |
| `lesson` | FK → Lesson | CASCADE, db\_index |
| `is_completed` | BooleanField | default=False |
| `completed_at` | DateTimeField | auto\_now |
| `time_spent_seconds` | PositiveIntegerField | ML-признак |
| `attempt_count` | PositiveIntegerField | ML-признак |
| `quiz_score` | FloatField(0–1) | ML-признак; nullable |
| *constraint* | unique\_together | `(user, lesson)` |
| *index* | composite | `(user, lesson)` — `progress_user_lesson_idx` |

**QuizAttempt**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `user` | FK → User | |
| `lesson` | FK → Lesson | |
| `score` | FloatField(0–1) | Балл за данную попытку |
| `created_at` | DateTimeField | auto\_now\_add, db\_index |

---

#### `assignments` — Задания с AI-проверкой

**OpenAssignment**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `lesson` | FK → Lesson | CASCADE nullable — необязательная привязка |
| `created_by` | FK → User | CASCADE — преподаватель |
| `title` | CharField(255) | |
| `description` | TextField | Публичное условие (видят студенты) |
| `reference_answer` | TextField | **Приватно** — только для промпта LLM |
| `max_score` | PositiveSmallIntegerField | 1–100, default=100 |
| `is_active` | BooleanField | False = задание закрыто |
| `created_at` / `updated_at` | DateTimeField | |

**AssignmentSubmission**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `assignment` | FK → OpenAssignment | CASCADE |
| `student` | FK → User | CASCADE |
| `answer_text` | TextField | Ответ студента |
| `submitted_at` | DateTimeField | auto\_now\_add |
| `status` | CharField | `pending` → `ai_checked` → `approved` |
| `final_score` | PositiveSmallIntegerField | nullable; выставляет преподаватель |
| `teacher_comment` | TextField | blank |
| *constraint* | unique\_together | `(assignment, student)` |

**AIEvaluation**

| Поле | Тип | Описание |
|---|---|---|
| `id` | PK | |
| `submission` | OneToOne → Submission | CASCADE |
| `score` | PositiveSmallIntegerField(0–100) | Оценка LLM |
| `feedback` | TextField | Развёрнутый текстовый разбор |
| `model_name` | CharField(100) | Идентификатор использованной модели |
| `prompt_tokens` | PositiveIntegerField | nullable; мониторинг расходов API |
| `completion_tokens` | PositiveIntegerField | nullable |
| `evaluated_at` | DateTimeField | auto\_now\_add |

### 3.3 Хранилище векторов (ChromaDB)

ChromaDB работает в **embedded-режиме** (SQLite + файловая система). Данные уроков, PDF и загруженных документов хранятся в единой коллекции `course_materials`.

**Схема метаданных чанка**

| Ключ | Тип | Источник |
|---|---|---|
| `source` | `"lesson"` / `"pdf"` / `"document"` | Тип источника |
| `course_id` | str(int) | Для фильтрации RAG-запросов |
| `lesson_id` | str(int) | Только для уроков и PDF |
| `document_id` | str(int) | Только для CourseDocument |
| `lesson_title` / `original_filename` | str | Для отладки |
| `chunk_index` | int | Порядковый номер чанка |
| `total_chunks` | int | Всего чанков из источника |

---

## 4. REST API — полный реестр эндпоинтов

### 4.1 Аутентификация

| Метод | URL | Доступ | Описание |
|---|---|---|---|
| POST | `/api/token/` | Публичный | Получить access + refresh JWT |
| POST | `/api/token/refresh/` | Публичный | Обновить access-токен |

### 4.2 Документация API

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/schema/` | Скачать OpenAPI YAML |
| GET | `/api/schema/swagger-ui/` | Интерактивный Swagger UI |

### 4.3 Курсы (`courses` app)

| Метод | URL | Роль | Описание |
|---|---|---|---|
| GET | `/api/v1/courses/` | Все | Список всех курсов с модулями и уроками |
| POST | `/api/v1/courses/` | Teacher | Создать курс |
| GET | `/api/v1/courses/{id}/` | Все | Детальный просмотр |
| PUT/PATCH | `/api/v1/courses/{id}/` | Owner | Редактировать |
| DELETE | `/api/v1/courses/{id}/` | Owner | Удалить |
| POST | `/api/v1/courses/{id}/enroll/` | Student | Записаться на курс |
| GET | `/api/v1/courses/{id}/documents/` | Все | Список загруженных документов (без текста) |
| POST | `/api/v1/courses/{id}/documents/` | Owner | Загрузить PDF/DOCX, запустить парсинг + векторизацию |
| GET | `/api/v1/modules/` | Все | Список модулей |
| POST | `/api/v1/modules/` | Teacher | Создать модуль |
| GET/PUT/PATCH/DELETE | `/api/v1/modules/{id}/` | Owner | CRUD |
| GET | `/api/v1/lessons/` | Enrolled/Owner | Список уроков (только доступных) |
| POST | `/api/v1/lessons/` | Teacher | Создать урок → автоиндексация в ChromaDB |
| GET/PUT/PATCH/DELETE | `/api/v1/lessons/{id}/` | Enrolled/Owner | CRUD + переиндексация при изменении |

### 4.4 Аналитика (`analytics` app)

| Метод | URL | Роль | Описание |
|---|---|---|---|
| GET | `/analytics/api/profile/` | Authenticated | Персональная статистика: уроки, средний балл, курсы |
| GET | `/analytics/api/students-stats/` | Teacher/Staff | Все студенты с ML-риском и прогрессом |
| POST | `/analytics/api/complete/{lesson_id}/` | Student | Отметить урок завершённым; тело: `{time_spent_seconds, quiz_score}` |
| GET | `/analytics/api/recommendations/{course_id}/` | Student | Top-N уроков по убыванию ML-риска провала |

### 4.5 AI-ассистент (`assistant` app)

| Метод | URL | Роль | Описание |
|---|---|---|---|
| POST | `/api/v1/chat/` | Authenticated | RAG-вопрос. Тело: `{question, lesson_id?}`. Ответ: `{answer}` |

### 4.6 Задания (`assignments` app)

| Метод | URL | Роль | Описание |
|---|---|---|---|
| GET | `/api/v1/assignments/` | Authenticated | Список: teacher — свои, student — активные |
| POST | `/api/v1/assignments/` | Teacher | Создать задание с эталонным ответом |
| GET | `/api/v1/assignments/{id}/` | Authenticated | Детальный просмотр |
| PUT/PATCH | `/api/v1/assignments/{id}/` | Owner | Редактировать |
| DELETE | `/api/v1/assignments/{id}/` | Owner | Удалить |
| POST | `/api/v1/assignments/{id}/submit/` | Student | Отправить ответ → немедленно запускает AI-проверку |
| GET | `/api/v1/assignments/{id}/submissions/` | Owner | Все ответы студентов с AI-оценкой |
| GET | `/api/v1/assignments/{id}/my-submission/` | Student | Свой ответ + AI-фидбек |
| GET | `/api/v1/submissions/` | Authenticated | Список ответов (teacher — все, student — свои) |
| GET | `/api/v1/submissions/{id}/` | Owner/Student | Детальный просмотр |
| PATCH | `/api/v1/submissions/{id}/approve/` | Teacher | Утвердить итоговый балл. Тело: `{final_score, teacher_comment}` |
| POST | `/api/v1/submissions/{id}/regrade/` | Teacher | Повторно запустить AI-проверку |

---

## 5. Сервисный слой (бизнес-логика)

### 5.1 `courses/services/document_parser.py` — Парсинг файлов

**Синхронный сервис.** Вызывается в основном потоке HTTP-запроса.

```
POST /api/v1/courses/{id}/documents/
        │
        ▼
CourseDocumentUploadSerializer.validate_file()
  - проверка расширения (.pdf / .docx)
  - проверка размера (≤ 20 МБ)
        │
        ▼
CourseDocument.create(status=PENDING)
        │
        ▼
extract_text_from_file(file_obj, ext)
  ├── .pdf  → _parse_pdf()   — pypdf.PdfReader, постраничная конкатенация
  └── .docx → _parse_docx()  — docx.Document, параграфы + таблицы
        │
   success ──► document.status = PARSED, save()
   failure ──► document.status = ERROR, error_message = str(exc), save()
```

**Обработка ошибок:**

| Исключение | Причина | HTTP-ответ |
|---|---|---|
| `UnsupportedFileTypeError` | Расширение не .pdf/.docx | 400 |
| `ParsingError` | Битый файл / PDF-скан без текста | 400 |
| `RuntimeError` | Зависимость не установлена | 500 |
| `Exception` (другое) | Непредвиденная ошибка | 500 |

---

### 5.2 `assistant/services/vectorizer.py` — Векторизация документов

**Асинхронный сервис.** Запускается в daemon-потоке **после** того, как HTTP-ответ уже отдан.

```
document.status == PARSED
        │
        ▼
index_document_async(document)
  └── threading.Thread(daemon=True, name="vectorizer-doc-{id}")
            │
            ▼ (в фоновом потоке)
  _run_document_indexing(document_id, course_id, text, filename)
            │
            ▼
  index_course_document(document_id, course_id, text, filename)
    ├── text.strip() == "" → return 0 (логируем warning, не падаем)
    ├── Оборачиваем текст в langchain.Document с метаданными
    ├── _TEXT_SPLITTER.split_documents() — chunk_size=1000, overlap=200
    ├── vectorstore._collection.delete(where={"document_id": str(id)})
    └── vectorstore.add_documents(splits)
            │
       success ──► CourseDocument.objects.filter(pk=id).update(status=INDEXED)
       failure ──► CourseDocument.objects.filter(pk=id).update(status=ERROR)
                   + logger.exception (подробности в логах сервера)
```

> **Важно:** в поток передаются только примитивные значения (`int`, `str`), не ORM-объект. Это предотвращает проблемы с Django DB-соединением в дочернем потоке. ORM-объект доступен только в основном потоке.

---

### 5.3 `assistant/vector_store.py` — Индексация уроков

**Синхронный вызов.** Вызывается в `LessonViewSet.perform_create/perform_update`. Ошибки не прерывают HTTP-ответ (перехватываются в `_reindex()`).

```
LessonViewSet.perform_create(serializer)
        │
        ▼
lesson = serializer.save()
        │
        ▼
index_lesson_content(lesson, course_title)
  ├── Формируем строку: "Курс: {title}. Тема: {lesson.title}. Содержание: {content}"
  ├── Оборачиваем в langchain.Document с метаданными (source="lesson", course_id, lesson_id)
  ├── _TEXT_SPLITTER.split_documents()
  ├── _delete_lesson_chunks(vectorstore, lesson.id)  ← очищаем старые чанки
  └── vectorstore.add_documents(splits)
```

---

### 5.4 `assistant/pdf_indexer.py` — Индексация PDF-вложений

**Асинхронный сервис.** Запускается при сохранении урока с `pdf_file`.

```
index_pdf_async(lesson)
  └── threading.Thread(daemon=True)
            │
            ▼
  _run_pdf_indexing(lesson)
    ├── PyPDFLoader(lesson.pdf_file.path).load()
    ├── Добавляем метаданные к каждой странице
    ├── _TEXT_SPLITTER.split_documents()
    ├── _delete_lesson_chunks(vectorstore, lesson.id)
    └── vectorstore.add_documents()
```

---

### 5.5 `assistant/rag.py` — Генерация ответа (RAG-цепочка)

**Синхронный вызов** в рамках HTTP-запроса `POST /api/v1/chat/`.

```
ask_assistant(query, lesson_id=None)
        │
        ▼
get_vectorstore()  ← ChromaDB singleton
        │
        ▼
retriever = vectorstore.as_retriever(
    search_kwargs={
        "k": 4,
        "filter": {"lesson_id": str(lesson_id)}  ← если lesson_id передан
    }
)
        │
        ▼
RetrievalQA.from_chain_type(
    llm=GigaChat(temperature=0.1),
    chain_type="stuff",        ← конкатенирует все 4 чанка в один контекст
    retriever=retriever,
    chain_type_kwargs={"prompt": PromptTemplate(...)}
)
        │
        ▼
qa_chain.invoke({"query": query})
        │
        ▼
return result["result"]  ← только текст ответа
```

**Промпт-стратегия:** системный промпт запрещает LLM упоминать источники и требует отвечать строго на основе контекста. Если вопрос не по теме — одна фраза-отказ.

---

### 5.6 `assignments/services/ai_grader.py` — AI-грейдер заданий

**Синхронный вызов** в рамках HTTP-запроса `POST /assignments/{id}/submit/`.

> **Production note:** при высокой нагрузке рекомендуется вынести в Celery-задачу.

```
grade_submission(submission)
        │
        ▼
build_grading_prompt(submission)
  └── Формирует промпт с полями:
      - assignment.title / description
      - assignment.reference_answer  ← ПРИВАТНО, студент не видит
      - submission.answer_text
      - assignment.max_score
        │
        ▼
_call_llm_stub(prompt, max_score)       ← ТЕКУЩЕЕ СОСТОЯНИЕ: заглушка
  [или _call_llm_real() — закомментировано, см. раздел 6]
        │
        ▼
Парсим JSON: {"score": int, "feedback": str}
        │
        ▼
AIEvaluation.objects.create(...)    ← atomic transaction
submission.status = AI_CHECKED      ← обновляем статус
submission.save()
```

**Алгоритм заглушки** (детерминированный):
- Вычисляет пересечение ключевых слов ответа и эталона
- Учитывает соотношение длин текстов
- Формула: `score = (0.4 * length_ratio + 0.6 * keyword_overlap) * max_score`

---

### 5.7 `analytics/services.py` — ML-рекомендации

**Синхронный вызов** в рамках HTTP-запросов к `/analytics/api/`.

```
load_model()  ← AppConfig.ready() при старте Django
  └── joblib.load("ai_module/model.pkl") → sklearn Pipeline (singleton _model)

get_recommendations(user, course, top_n)
  ├── Исключаем завершённые уроки
  ├── Для каждого незавершённого урока:
  │   └── build_feature_vector(user, lesson) → np.ndarray(1, 12)
  │       ├── Позиционные признаки (lesson_order, module_order, ratio)
  │       ├── Исторические агрегаты (prev_avg_score, prev_avg_time, …)
  │       └── Текущие метрики (time_spent, attempt_count, quiz_score)
  │   └── model.predict_proba(X)[0, 1] → P(completion)
  │   └── risk_score = 1.0 - P(completion)
  ├── Сортируем по risk_score DESC
  └── Возвращаем top_n элементов
```

---

## 6. Внешние интеграции

### 6.1 GigaChat (LLM)

| Параметр | Значение |
|---|---|
| Провайдер | ПАО «Сбербанк» |
| Библиотека | `langchain-gigachat` 0.3.x |
| Модель | `GigaChat` (RAG), `GigaChat-Pro` (грейдер, закомментировано) |
| Аутентификация | `GIGACHAT_AUTHORIZATION_KEY` из `.env` |
| `temperature` | `0.1` — детерминированный режим |
| `verify_ssl_certs` | `False` (самоподписанный сертификат Сбера) |

**Текущий статус AI-грейдера:**

```python
# ai_grader.py — текущее состояние
raw = _call_llm_stub(prompt, max_score)   # ← используется заглушка

# Для переключения на реальный GigaChat — раскомментировать:
# raw = _call_llm_real(prompt, max_score)
# и добавить в _call_llm_real():
#   from langchain_gigachat import GigaChat
#   llm = GigaChat(credentials=settings.GIGACHAT_AUTHORIZATION_KEY, model="GigaChat-Pro", ...)
```

**RAG-ассистент** использует **живой GigaChat** в `rag.py` — полностью подключён.

---

### 6.2 ChromaDB (векторная база данных)

| Параметр | Значение |
|---|---|
| Режим | Embedded (локальный, без отдельного сервера) |
| Путь | `code/chroma_db/` |
| Бэкенд хранения | SQLite + HNSW-индекс на диске |
| Коллекция | `course_materials` |
| Поиск | ANN (приближённый поиск ближайших соседей) |
| Метрика | Косинусное сходство |

> **Ограничение:** embedded ChromaDB не поддерживает конкурентные операции **записи** из разных процессов. При нагрузке >5 одновременных преподавателей, редактирующих контент, рекомендуется переход на ChromaDB Server или Qdrant.

---

### 6.3 HuggingFace Embeddings

| Параметр | Значение |
|---|---|
| Модель | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Библиотека | `langchain-huggingface` 0.1.x |
| Размерность вектора | 384 |
| Инференс | CPU (GPU не требуется) |
| Размер модели | ~120 МБ |
| Языки | Многоязычная, русский — поддерживается |

Модель загружается **один раз** при первом вызове `get_vectorstore()` и кэшируется в `~/.cache/huggingface/`.

---

### 6.4 scikit-learn (ML-модель)

| Параметр | Значение |
|---|---|
| Алгоритм | `HistGradientBoostingClassifier` |
| Конвейер | `StandardScaler` → `HistGBDT` |
| Сериализация | `joblib` → `ai_module/model.pkl` |
| Загрузка | Singleton при `AppConfig.ready()` |
| Fallback | При отсутствии модели возвращается `p=0.5` |

---

## 7. ML-подсистема

### 7.1 Вектор признаков (12 признаков)

| # | Признак | Тип | Описание |
|---|---|---|---|
| 1 | `lesson_order` | int | Позиция урока в модуле |
| 2 | `module_order` | int | Позиция модуля в курсе |
| 3 | `lesson_position_ratio` | float [0,1] | Глобальная позиция урока в курсе |
| 4 | `prev_avg_score` | float [0,1] | Средний балл по предыдущим урокам |
| 5 | `prev_avg_time` | float | Среднее время на предыдущих уроках (сек) |
| 6 | `prev_avg_attempts` | float | Среднее число попыток |
| 7 | `prev_completion_rate` | float [0,1] | Доля завершённых предыдущих уроков |
| 8 | `prev_lessons_done` | int | Количество завершённых предыдущих уроков |
| 9 | `time_spent_seconds` | int | Время на текущем уроке |
| 10 | `attempt_count` | int | Число попыток на текущем уроке |
| 11 | `quiz_taken` | binary {0,1} | Был ли открыт тест |
| 12 | `quiz_score` | float [0,1] | Балл теста (0 если не открывался) |

**Таргет:** `is_completed` ∈ {0, 1}

### 7.2 Offline обучение

```bash
# Сгенерировать синтетические данные (если нет реальных)
python manage.py generate_synthetic_data --records 2000 --users 50

# Обучить модель (с GridSearchCV)
python ml_analytics/train.py

# Быстрый режим без перебора (фиксированные параметры)
python ml_analytics/train.py --no-grid

# Оценить качество
python ml_analytics/evaluate.py
```

### 7.3 GridSearchCV — сетка гиперпараметров

| Параметр | Значения |
|---|---|
| `max_iter` | 200, 400 |
| `max_depth` | 3, 5 |
| `learning_rate` | 0.05, 0.1 |
| `min_samples_leaf` | 10, 20 |

Оптимизируется по **ROC-AUC**, 3-кратная кросс-валидация, стратифицированное разбиение 80/20.

---

## 8. Инфраструктура и контейнеризация

### 8.1 Docker Compose — сервисы

| Сервис | Образ | Порт | Описание |
|---|---|---|---|
| `db` | `postgres:15-alpine` | 5432 | PostgreSQL; healthcheck: `pg_isready` |
| `backend` | `./code/Dockerfile` | 8000 | Django + DRF; зависит от `db` (healthcheck) |
| `frontend` | `./frontend/Dockerfile` | 5173 | React + Vite dev-server |

### 8.2 Граф зависимостей и порядок запуска

```
db (healthy) ──► backend (migrate + runserver) ──► frontend (npm run dev)
```

### 8.3 Запуск

```bash
# Первый запуск
cp code/.env.example code/.env   # заполнить секреты
docker compose up --build

# Повторный запуск
docker compose up

# Только бэкенд (для разработки)
docker compose up db backend
```

### 8.4 Хранилища данных (Docker Volumes)

| Volume | Содержимое | Поведение при `docker compose down` |
|---|---|---|
| `postgres_data` | Данные PostgreSQL | **Сохраняется** |
| `node_modules` (named) | Зависимости фронтенда | Сохраняется |
| `./code/chroma_db` | Векторный индекс ChromaDB | Bind-mount; сохраняется |
| `./ai_module` | `model.pkl`, `meta.json` | Bind-mount; сохраняется |

---

## 9. Аутентификация и авторизация

### 9.1 JWT-схема

Реализована через `djangorestframework-simplejwt`.

| Токен | Время жизни | Назначение |
|---|---|---|
| access\_token | 5 минут | Прикрепляется к каждому запросу: `Authorization: Bearer <token>` |
| refresh\_token | 24 часа | Используется для «тихого» обновления access |

**Настройки:**
- `ROTATE_REFRESH_TOKENS = True` — при каждом обновлении выдаётся новый refresh-токен
- `BLACKLIST_AFTER_ROTATION = True` — старый refresh-токен аннулируется

### 9.2 Permission-классы

| Класс | Приложение | Логика |
|---|---|---|
| `IsOwnerOrReadOnly` | `courses` | Чтение — все авторизованные; запись — только `course.owner` или staff |
| `IsEnrolledOrOwner` | `courses` | Доступ к уроку — записанный студент или owner |
| `IsTeacher` | `assignments` | Только `role == "teacher"` или staff |
| `IsTeacherOrReadOnly` | `assignments` | Безопасные методы — все; мутации — только teacher/staff |
| `IsAssignmentAuthorOrReadOnly` | `assignments` | Изменять задание — только его автор |
| `IsSubmissionOwnerOrTeacher` | `assignments` | Студент видит свои; teacher видит ответы на свои задания |

### 9.3 Ролевая матрица

| Операция | Student | Teacher | Staff |
|---|---|---|---|
| Просмотр курсов | ✅ | ✅ | ✅ |
| Создание курса | ❌ | ✅ | ✅ |
| Запись на курс | ✅ | ❌ | ✅ |
| Просмотр уроков | Только enrolled | Только свои | ✅ |
| Загрузка документов | ❌ | Owner only | ✅ |
| Личная статистика | ✅ | ❌ | ✅ |
| Статистика студентов | ❌ | ✅ | ✅ |
| ML-рекомендации | ✅ | ❌ | ✅ |
| Отправить задание | ✅ | ❌ | ✅ |
| Утвердить балл | ❌ | Owner only | ✅ |

---

## 10. Конфигурация и переменные окружения

Файл: `code/.env` (не хранится в репозитории).

| Переменная | Обязательна | Описание |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DEBUG` | ✅ | `True` / `False` |
| `ALLOWED_HOSTS` | ✅ | Список хостов через запятую |
| `DATABASE_URL` | ✅ | `postgres://user:pass@host:5432/db` |
| `GIGACHAT_AUTHORIZATION_KEY` | ✅ | Bearer-ключ для GigaChat API |

### Установка зависимостей

```bash
# Backend (Poetry)
cd code
poetry install

# Дополнительно для парсинга DOCX (если не установлено)
poetry add python-docx

# Frontend
cd frontend
npm install
```

### Миграции

```bash
cd code
python manage.py makemigrations
python manage.py migrate
```

---

*Документ сгенерирован на основе анализа исходного кода. При внесении архитектурных изменений — обновлять соответствующие разделы.*
