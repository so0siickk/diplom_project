# VKR_PLAN.md — План перехода к Этапам 2 и 3

## Базовая линия (Этап 1 — ЗАВЕРШЁН)

Реализованы и работают:
- LMS-ядро: модели `Course → Module → Lesson`, CRUD через Django Admin и шаблоны
- Система пользователей: `AbstractUser` с ролями `student` / `teacher`
- Трекинг прогресса: `UserLessonProgress` (флаг `is_completed` + timestamp)
- PoC RAG-ассистента: LangChain `RetrievalQA` → GigaChat → ChromaDB
- REST API: DRF-эндпоинты для курсов + `POST /chat/` для ассистента
- DB: SQLite (dev); миграции готовы

---

## ЭТАП 2 — ML-модель предиктивной аналитики

### 2.1 Проектирование данных

**Что нужно:**
Текущая модель `UserLessonProgress` фиксирует только факт завершения урока. Для ML необходимо расширить сбор поведенческих сигналов.

**Задачи:**
1. Добавить в `UserLessonProgress` поля:
   - `time_spent_seconds` (IntegerField) — время на уроке
   - `attempt_count` (PositiveIntegerField, default=1) — число попыток
   - `quiz_score` (FloatField, null=True) — результат теста (0.0–1.0)
2. Создать модель `QuizAttempt` (`user`, `lesson`, `score`, `created_at`)
3. Написать management-команду `generate_synthetic_data` для генерации 500–1000 синтетических записей прогресса (для обучения модели до накопления реальных данных)
4. Файл `ml_analytics/dataset_builder.py` — скрипт экспорта данных из Django ORM в pandas DataFrame

**Артефакты:** миграции, `ml_analytics/dataset_builder.py`, `ml_analytics/synthetic_data.py`

---

### 2.2 Обучение ML-модели

**Задача модели:** по истории взаимодействия пользователя с курсом предсказать вероятность успешного завершения следующего урока. На основе этого — выдавать рекомендации.

**Подход (градиентный бустинг как baseline):**

```
Признаки (features):
  - avg_quiz_score        — средний балл за предыдущие тесты
  - avg_time_spent        — среднее время на урок (в модуле)
  - completion_rate       — % завершённых уроков в текущем модуле
  - attempt_count         — среднее число попыток
  - lesson_order          — порядковый номер урока

Целевая переменная (target):
  - is_completed (bool) → вероятность завершения следующего урока
```

**Задачи:**
1. `ml_analytics/train.py` — обучение `sklearn` Pipeline (StandardScaler + GradientBoostingClassifier)
2. `ml_analytics/evaluate.py` — оценка: ROC-AUC, F1, матрица ошибок
3. Сохранение артефакта: `ai_module/model.pkl` (joblib)
4. Jupyter Notebook `ml_analytics/exploration.ipynb` — EDA и визуализация признаков

**Критерий готовности:** ROC-AUC ≥ 0.75 на тестовой выборке (80/20 split)

**Артефакты:** `ml_analytics/train.py`, `ml_analytics/evaluate.py`, `ai_module/model.pkl`, `ml_analytics/exploration.ipynb`

---

### 2.3 Интеграция аналитики в Django

**Задача:** модель из `ai_module/model.pkl` используется Django для формирования персональных рекомендаций в реальном времени.

**Задачи:**
1. Создать Django-приложение `recommendations/` (или сервисный слой внутри `analytics/`)
2. Написать `analytics/services.py`:
   - `build_feature_vector(user, lesson) → np.ndarray` — сборка вектора признаков из ORM
   - `predict_success_probability(user, lesson) → float` — вызов модели
   - `get_recommendations(user, course) → List[Lesson]` — топ-N уроков с наименьшей predicted probability (приоритет слабых зон)
3. Новый API-эндпоинт: `GET /api/recommendations/<course_id>/` → JSON со списком рекомендованных уроков
4. Кэширование предсказаний через Django cache framework (timeout 1 час) для снижения нагрузки
5. Загрузка модели при старте приложения через `AppConfig.ready()` (singleton)

**Артефакты:** `analytics/services.py`, `analytics/urls.py` (обновление), `analytics/apps.py` (обновление)

---

## ЭТАП 3 — Frontend-интерфейс и написание ВКР

### 3.1 REST API (расширение для SPA)

**Задачи:**
1. Перевести настройки БД на PostgreSQL (`config/settings.py`)
2. Добавить аутентификацию через JWT (djangorestframework-simplejwt):
   - `POST /api/auth/token/` — получение пары access/refresh
   - `POST /api/auth/token/refresh/`
3. Новые эндпоинты (DRF):
   - `GET /api/courses/` — список курсов с прогрессом пользователя
   - `GET /api/courses/<id>/modules/` — модули курса с уроками
   - `POST /api/analytics/complete/<lesson_id>/` — отметить урок выполненным
   - `GET /api/recommendations/<course_id>/` — рекомендации (из Этапа 2)
   - `POST /api/chat/` — RAG-ассистент
4. Настроить CORS (`django-cors-headers`) для разработки SPA на отдельном порту
5. Документация API через drf-spectacular (OpenAPI 3.0)

**Артефакты:** обновлённые `urls.py`, `serializers.py` в каждом приложении, `requirements` расширен

---

### 3.2 SPA-фронтенд (React + TypeScript)

**Структура проекта:** `frontend/` в корне репозитория

```
frontend/
├── src/
│   ├── api/          ← axios-клиент + типы запросов/ответов
│   ├── components/   ← переиспользуемые UI-компоненты
│   ├── pages/        ← CourseList, CourseDetail, LessonDetail, Chat
│   ├── store/        ← Zustand (глобальный стейт: auth, прогресс)
│   └── App.tsx
├── package.json
└── vite.config.ts
```

**Ключевые экраны:**
1. **Каталог курсов** — список с прогресс-барами и рекомендациями
2. **Страница курса** — модули, уроки, визуализация прогресса (Chart.js)
3. **Страница урока** — контент + кнопка «Завершить» + интеграция чата
4. **Чат-ассистент** — floating widget, стриминг ответов через SSE (или polling)
5. **Панель рекомендаций** — «Слабые темы» на основе ML-предсказаний

---

### 3.3 Написание глав ВКР

| Глава | Содержание | Приоритет |
|---|---|---|
| Введение | Актуальность, цели, задачи, предмет/объект | Высокий |
| Глава 1. Анализ предметной области | Обзор LMS, адаптивное обучение, RAG, ML в образовании, обзор аналогов | Высокий |
| Глава 2. Проектирование системы | Архитектурные решения, модели данных (ER), диаграммы компонентов, API-контракты | Высокий |
| Глава 3. Реализация backend (Этап 1+2) | Django-приложения, RAG-пайплайн, ML-модель, интеграция рекомендаций | Средний |
| Глава 4. Реализация frontend (Этап 3) | SPA, компоненты, взаимодействие с API | Средний |
| Глава 5. Тестирование и эксперименты | Unit/интеграционные тесты, A/B-эксперимент (если возможно), оценка ML | Средний |
| Заключение | Выводы, достигнутые результаты, направления развития | Низкий |
| Список источников | ГОСТ Р 7.0.5-2008, 30–50 источников | Низкий |

---

## Дорожная карта (порядок выполнения)

```
Этап 2:
  [2.1] Расширение моделей + синтетические данные   → 1–2 дня
  [2.2] Обучение ML-модели (train.py + evaluate.py) → 2–3 дня
  [2.3] Интеграция в Django (services.py + API)     → 2–3 дня

Этап 3:
  [3.1] Расширение REST API + JWT + OpenAPI         → 2–3 дня
  [3.2] React SPA (4–5 экранов)                     → 5–7 дней
  [3.3] Написание глав ВКР (параллельно с 3.1–3.2) → непрерывно
```

---

## Ключевые технические риски

| Риск | Митигация |
|---|---|
| Недостаточно реальных данных для ML | Синтетическая генерация + early stopping |
| GigaChat API rate limits | Кэш ответов в Redis, fallback-сообщение |
| Производительность ChromaDB при росте курсов | Индекс HNSW, sharding по course_id |
| CORS и JWT на dev-окружении | django-cors-headers + настройки simplejwt |
