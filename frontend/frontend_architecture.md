# Frontend Architecture — LMS Adaptive

> **Стек:** React 18 · TypeScript · Vite · Tailwind CSS · Zustand · Axios · React Router v6  
> **Дата среза:** 2026-04-21  
> **Backend base URL:** `http://127.0.0.1:8000`

---

## 1. Дерево роутинга

### 1.1 Схема защиты маршрутов

```
BrowserRouter
├── /login                          — публичный (без токена)
│
├── PrivateRoute                    — проверяет isAuthenticated из authStore
│   │                                 → редирект на /login при отсутствии токена
│   │
│   ├── ShellRoute                  — PrivateRoute + AppShell (sidebar + header)
│   │   └── <страница>
│   │
│   └── RoleRoute(role)             — ShellRoute + проверка authStore.role
│       └── <страница>              → редирект на / при несовпадении роли
│
└── /lesson/:id                     — PrivateRoute без AppShell (собственный header)
```

### 1.2 Полная таблица маршрутов

| URL | Компонент страницы | Защита | Доступ |
|---|---|---|---|
| `/login` | `Login` | — | Все |
| `/` | `Dashboard` | ShellRoute | Авторизованные |
| `/profile` | `ProfilePage` | ShellRoute | Авторизованные |
| `/course/:id` | `CourseDetail` | ShellRoute | Авторизованные |
| `/lesson/:id` | `LessonView` | PrivateRoute | Авторизованные |
| `/instructor` | `InstructorDashboard` | ShellRoute | Авторизованные |
| `/instructor/my-courses` | `MyCourses` | ShellRoute | Авторизованные |
| `/instructor/new` | `CourseEditor` | ShellRoute | Авторизованные |
| `/instructor/edit/:id` | `CourseEditor` | ShellRoute | Авторизованные |
| `/instructor/courses/:courseId` | `TeacherCoursePage` | **RoleRoute(teacher)** | Только teacher |
| `/instructor/assignments/:assignmentId` | `TeacherAssignmentPage` | **RoleRoute(teacher)** | Только teacher |
| `/courses/:courseId/assignments/:assignmentId` | `StudentAssignmentPage` | **RoleRoute(student)** | Только student |
| `*` | `NotFoundPage` (inline) | — | Все |

> **Примечание:** маршруты `/instructor/my-courses`, `/instructor/new`, `/instructor/edit/:id`  
> защищены через `ShellRoute` (только аутентификация), но навигационные ссылки в `AppShell`  
> отфильтрованы по `role === 'teacher'`. Жёсткая ролевая защита через `RoleRoute` реализована  
> только для трёх новых маршрутов (documents и assignments).

---

## 2. Layout: AppShell

**Файл:** `src/components/layout/AppShell.tsx`

Единая обёртка для всех аутентифицированных страниц (кроме `LessonView`).

```
┌──────────────────────────────────────────────────────┐
│  Header (fixed, h-14)                                │
│  [☰]                              [аватар username →]│
├────────────┬─────────────────────────────────────────┤
│  Sidebar   │                                         │
│  (fixed)   │   <children>  (main, pt-14, pl-56/16)  │
│  w-56/16   │                                         │
│  collapsed │                                         │
│  on mobile │                                         │
└────────────┴─────────────────────────────────────────┘
```

**Состояния:**
- `sidebarOpen: boolean` — локальный `useState`, переключается кнопкой в Header
- На мобильных при `sidebarOpen=true` — backdrop-overlay с закрытием по клику

**Навигация в Sidebar** фильтруется по роли:

```ts
NAV_ITEMS.filter(item => !item.teacherOnly || role === 'teacher')
```

| Пункт меню | URL | teacherOnly |
|---|---|---|
| Мои курсы | `/` | — |
| Профиль | `/profile` | — |
| Инструктор | `/instructor` | ✓ |
| Редактор курсов | `/instructor/my-courses` | ✓ |

---

## 3. Страницы

### 3.1 Dashboard (`/`)

**Роль:** студент (основной потребитель).

**Стейт:**

| Переменная | Тип | Назначение |
|---|---|---|
| `courses` | `Course[]` | Все курсы с флагом `is_enrolled` |
| `selectedCourseId` | `number \| null` | Курс для ML-рекомендаций |
| `recs` | `RecommendationItem[]` | Рекомендации от ML-модели |
| `modelLoaded` | `boolean \| null` | Флаг: ML-модель загружена |
| `enrollingId` | `number \| null` | ID курса в процессе записи |

**API-запросы:**
- `GET /api/v1/courses/` — при маунте (все курсы сразу)
- `GET /analytics/api/recommendations/:courseId/` — при смене `selectedCourseId`
- `POST /api/v1/courses/:id/enroll/` — запись на курс (обновляет `is_enrolled` локально без рефетча)

**Логика:** курсы делятся на `enrolledCourses` и `catalogCourses` через `Array.filter`. Первый записанный курс автоматически становится `selectedCourseId`.

---

### 3.2 CourseDetail (`/course/:id`)

Страница курса. Два состояния:
- **Не записан** → `EnrollHero` (CTA для записи)
- **Записан** → аккордеон модулей с уроками

Навигация на урок передаёт `{ courseId, courseTitle, moduleTitle }` через `router state` для корректной работы навигации prev/next в `LessonView`.

---

### 3.3 LessonView (`/lesson/:id`)

**Полноэкранная страница** (без `AppShell`, собственный header).

**Layout:**
```
┌────────────────────────────────────────────┬──────────────┐
│  Lesson content (flex-1, overflow-y-auto)  │  ChatPanel   │
│  · заголовок, video iframe, текст          │  w-[360px]   │
│  · кнопка "Завершить и следующий урок →"   │  (md+)       │
└────────────────────────────────────────────┴──────────────┘
│  ChatPanel (h-64, только mobile)                          │
└───────────────────────────────────────────────────────────┘
```

**ChatPanel (встроенный sub-компонент):**
- Стейт: `messages: ChatMessage[]`, `input`, `sending`
- `POST /api/v1/chat/` с `{ question, lesson_id }`
- Ответ AI рендерится через `<ReactMarkdown>` (поддержка markdown)
- `Enter` — отправка, `Shift+Enter` — новая строка

**Навигация по урокам:**
1. Получает курс по `courseId` из `router state` или перебором всех курсов (fallback)
2. Строит плоский отсортированный массив `flatLessons`
3. При нажатии "Завершить": `POST /analytics/api/complete/:lessonId/` (non-blocking), затем `navigate` к следующему уроку или к странице курса

---

### 3.4 TeacherCoursePage (`/instructor/courses/:courseId`)

Страница управления материалами курса для преподавателя.

- Валидация `courseId` из `useParams`: если `undefined` или `NaN` — `<InvalidIdFallback>`
- Breadcrumb → `/instructor/my-courses`
- Рендерит `<CourseDocumentUploader courseId={id} />`

---

### 3.5 StudentAssignmentPage (`/courses/:courseId/assignments/:assignmentId`)

Страница прохождения задания для студента.

- Валидирует оба параметра: `courseId` и `assignmentId`
- Breadcrumb → `/course/:courseId`
- Рендерит `<AssignmentStudentView assignmentId={id} />`

---

### 3.6 TeacherAssignmentPage (`/instructor/assignments/:assignmentId`)

Страница проверки ответов для преподавателя.

**Стейт:** `assignment: OpenAssignment | null`, `loading`, `fetchError`

**Инициализация:**
```
useEffect → GET /api/v1/assignments/:id/
  → setAssignment(data)          // получаем реальный maxScore и заголовок
  → рендер <AssignmentTeacherView maxScore={assignment.max_score} />
```

Карточка-header отображает название задания, урок, `max_score` и флаг `is_active`.

---

### 3.7 CourseEditor (`/instructor/new` и `/instructor/edit/:id`)

CMS-редактор курса. Два режима в одном компоненте (определяется по наличию `:id`).

**Layout:** двухколоночный split — дерево структуры курса слева, контекстная форма справа.

**Draft-модель:** курс хранится локально как `DraftCourse` / `DraftModule` / `DraftLesson` с `_key` (временный UUID для React keys). Сохранение идёт попунктно через PATCH/POST.

---

### 3.8 InstructorDashboard (`/instructor`)

Таблица прогресса студентов с ML risk-индикаторами.

- `GET /analytics/api/students-stats/` → список `StudentStat[]`
- Risk-уровень вычисляется на фронте: `score >= 0.7` → high, `>= 0.4` → medium, иначе low

---

## 4. Ключевые UI-компоненты

### 4.1 CourseDocumentUploader

**Файл:** `src/components/CourseDocumentUploader.tsx`  
**Props:** `courseId: number`

#### Стейт

| Переменная | Тип | Назначение |
|---|---|---|
| `documents` | `CourseDocument[]` | Список файлов с бэка |
| `loadingDocs` | `boolean` | Индикатор загрузки списка |
| `fetchError` | `string \| null` | Ошибка GET-запроса |
| `isDragging` | `boolean` | Визуальная подсветка drop-зоны |
| `uploading` | `boolean` | Идёт загрузка файла |
| `uploadError` | `string \| null` | Ошибка POST-запроса |

#### Drag & Drop (нативный HTML5)

Для предотвращения «flickering» при наведении на дочерние элементы используется `dragCounter` ref:

```ts
const dragCounter = useRef(0)

onDragEnter → dragCounter.current += 1; if (1) setIsDragging(true)
onDragLeave → dragCounter.current -= 1; if (0) setIsDragging(false)
onDrop      → dragCounter.current = 0;  setIsDragging(false); uploadFile(file)
```

#### Загрузка файла

```ts
const formData = new FormData()
formData.append('file', file)
await client.post(`/api/v1/courses/${courseId}/documents/`, formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
})
await fetchDocuments() // рефетч списка после успеха
```

Допустимые MIME-типы: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

#### Статус-бейджи

| Статус бэка | Цвет | Метка |
|---|---|---|
| `pending` | Жёлтый | В обработке |
| `parsed` | Зелёный | Готово |
| `error` | Красный | Ошибка + `error_message` под строкой |

---

### 4.2 AssignmentStudentView

**Файл:** `src/components/AssignmentStudentView.tsx`  
**Props:** `assignmentId: number`

#### Инициализация (параллельный fetch)

```ts
const [assignmentRes, submissionRes] = await Promise.allSettled([
  client.get(`/api/v1/assignments/${assignmentId}/`),
  client.get(`/api/v1/assignments/${assignmentId}/my-submission/`),
])
```

`submissionRes` со статусом `rejected` (404 — ещё не отвечал) не считается ошибкой — `submission` остаётся `null`.

#### Логика отображения

```
submission === null
  → <textarea> + кнопка "Отправить на проверку AI"
  → POST /api/v1/assignments/:id/submit/ { answer_text }
  → onSuccess: setSubmission(data)

submission !== null
  → disabled <textarea> с answer_text
  → <SubmissionStatusBadge status={...} />
  → блок AI-оценки (если ai_evaluation !== null):
      · ScoreDisplay: final_score ?? ai_evaluation.score  /  max_score
      · Текстовый feedback на фиолетовом фоне
  → если status === 'approved' && teacher_comment:
      · Зелёный блок с комментарием преподавателя
```

#### ScoreDisplay — цветовая шкала

| Процент от max_score | Цвет |
|---|---|
| ≥ 80% | Зелёный |
| 50–79% | Жёлтый |
| < 50% | Красный |

---

### 4.3 AssignmentTeacherView

**Файл:** `src/components/AssignmentTeacherView.tsx`  
**Props:** `assignmentId: number`, `maxScore: number`

#### Инициализация

```ts
GET /api/v1/assignments/${assignmentId}/submissions/
→ setSubmissions(data)
```

#### Структура

```
┌─ Stats bar ─────────────────────────────────────────┐
│  Всего  │  Ожидают AI  │  Проверено AI  │  Утверждено│
└─────────────────────────────────────────────────────┘

┌─ SubmissionRow (аккордеон) ─────────────────────────┐
│  [avatar] username          score/max   [статус]  [v]│
│  ─────────────────────────────────────────────────── │
│  [expanded]                                          │
│  · Ответ студента (scrollable, max-h-48)             │
│  · Блок AI-оценки (фиолетовый, score + feedback)     │
│  · Форма утверждения: number input + textarea        │
│    → PATCH /api/v1/submissions/:id/approve/          │
│      { final_score, teacher_comment }                │
│    → onApproved: локальное обновление строки         │
└─────────────────────────────────────────────────────┘
```

#### Форма утверждения (inline, per-row стейт)

```ts
interface ApproveFormState {
  score: string       // string для controlled input
  comment: string
  loading: boolean
  error: string | null
}
```

Клиентская валидация: `0 ≤ score ≤ maxScore`. После успешного `PATCH` строка обновляется через `onApproved(updatedSubmission)` без повторного запроса к `/submissions/`.

---

## 5. Взаимодействие с API

### 5.1 Axios-клиент

**Файл:** `src/api/client.ts`

```
axios.create({ baseURL: 'http://127.0.0.1:8000' })
```

#### Interceptor: REQUEST

Каждый исходящий запрос получает заголовок:
```
Authorization: Bearer <access_token>  ← из localStorage
```

#### Interceptor: RESPONSE (silent token refresh)

```
401 + !_retry
  → isRefreshing === true?
      → push в failedQueue (Promise, resolve/reject позже)
  → isRefreshing === false:
      → POST /api/token/refresh/ (raw axios, без interceptor)
      → saveTokens(access, refresh?)   // ROTATE_REFRESH_TOKENS=True
      → flushQueue(null, newToken)      // разблокировать очередь
      → retry originalRequest
  → refresh провалился:
      → flushQueue(error, null)
      → clearTokens()
      → window.location.replace('/login')
```

Механизм `failedQueue` обеспечивает **concurrent-request safety**: при одновременных 401-ошибках рефреш выполняется ровно один раз.

### 5.2 Полный реестр API-эндпоинтов

| Метод | URL | Вызывается из | Назначение |
|---|---|---|---|
| `POST` | `/api/token/` | `auth.ts: login()` | Получить пару токенов |
| `POST` | `/api/token/refresh/` | `client.ts` interceptor | Обновить access token |
| `GET` | `/analytics/api/profile/` | `authStore` | Роль и username |
| `GET` | `/api/v1/courses/` | Dashboard, LessonView (fallback) | Все курсы |
| `GET` | `/api/v1/courses/:id/` | CourseDetail, LessonView | Детали курса |
| `POST` | `/api/v1/courses/:id/enroll/` | Dashboard | Запись на курс |
| `GET` | `/analytics/api/recommendations/:id/` | Dashboard | ML-рекомендации |
| `POST` | `/analytics/api/complete/:lessonId/` | LessonView | Отметить урок выполненным |
| `GET` | `/analytics/api/profile/` | ProfilePage | Статистика профиля |
| `GET` | `/analytics/api/students-stats/` | InstructorDashboard | Прогресс студентов |
| `POST` | `/api/v1/chat/` | LessonView / ChatPanel | RAG-ассистент |
| `GET` | `/api/v1/courses/:id/documents/` | CourseDocumentUploader | Список документов |
| `POST` | `/api/v1/courses/:id/documents/` | CourseDocumentUploader | Загрузка файла |
| `GET` | `/api/v1/assignments/:id/` | TeacherAssignmentPage | Детали задания |
| `GET` | `/api/v1/assignments/:id/my-submission/` | AssignmentStudentView | Ответ студента |
| `POST` | `/api/v1/assignments/:id/submit/` | AssignmentStudentView | Отправить ответ |
| `GET` | `/api/v1/assignments/:id/submissions/` | AssignmentTeacherView | Все ответы |
| `PATCH` | `/api/v1/submissions/:id/approve/` | AssignmentTeacherView | Утвердить оценку |

### 5.3 Паттерны работы с данными

**Отмена запросов при анмаунте:**
```ts
useEffect(() => {
  let cancelled = false
  client.get(...).then(({ data }) => {
    if (!cancelled) setState(data)
  })
  return () => { cancelled = true }
}, [dep])
```

**Параллельный fetch с частичной ошибкой:**
```ts
const [a, b] = await Promise.allSettled([reqA, reqB])
// a.status === 'rejected' не блокирует обработку b
```

**Оптимистичное обновление UI:**  
Dashboard после `POST /enroll/` обновляет `is_enrolled` локально без рефетча списка курсов.

---

## 6. Управление состоянием

### 6.1 Zustand AuthStore

**Файл:** `src/store/authStore.ts`

```ts
interface AuthState {
  isAuthenticated: boolean   // Boolean(getAccessToken()) при инициализации
  isLoading: boolean         // активен login()
  error: string | null       // ошибка логина
  username: string           // из /analytics/api/profile/
  role: string               // 'student' | 'teacher', default: 'student'

  login()      // POST /api/token/ → saveTokens → fetchProfile
  logout()     // clearTokens → redirect /login
  checkAuth()  // синхронная проверка токена в localStorage
  fetchProfile() // GET /analytics/api/profile/ → set username+role
}
```

**Инициализация после перезагрузки страницы:**
```ts
// App.tsx
useEffect(() => {
  if (isAuthenticated) fetchProfile()
}, [isAuthenticated])
```

Токен уже есть в `localStorage` → `isAuthenticated = true` → `fetchProfile` восстанавливает `username` и `role`.

### 6.2 Токены в localStorage

| Ключ | Содержимое |
|---|---|
| `lms_access_token` | JWT access token |
| `lms_refresh_token` | JWT refresh token |

Управление: `getAccessToken()`, `getRefreshToken()`, `saveTokens()`, `clearTokens()` — всё в `src/api/client.ts`.

### 6.3 Локальный стейт компонентов

Компоненты не используют внешний store для данных страниц. Весь data-fetching — локальный `useState` + `useEffect`. Паттерн единый:

```
loading → fetch → data | error
```

Стейт ошибок разделён по источнику:
- `fetchError` — ошибка GET при загрузке
- `uploadError` / `submitError` — ошибка POST/PATCH при действии пользователя

---

## 7. TypeScript-типы (src/api/types.ts)

```ts
// Курсы
interface Lesson         { id, title, content, video_url, order }
interface Module         { id, title, description, order, lessons: Lesson[] }
interface Course         { id, title, description, owner, created_at, modules, is_enrolled }

// Документы курса
type DocumentStatus = 'pending' | 'parsed' | 'error'
interface CourseDocument { id, original_filename, status, status_display,
                           error_message, uploaded_by, uploaded_at }

// Задания
interface OpenAssignment { id, lesson, lesson_title, created_by, title,
                           description, max_score, is_active, created_at }

// Ответы студентов
type SubmissionStatus = 'pending' | 'ai_checked' | 'approved'
interface AIEvaluation   { id, score, feedback, model_name, evaluated_at }
interface AssignmentSubmission { id, student_username, answer_text, submitted_at,
                                 status, status_display, ai_evaluation,
                                 final_score, teacher_comment }

// ML
interface RecommendationItem    { lesson_id, lesson_title, module_title,
                                  completion_prob, risk_score }
interface RecommendationsResponse { course_id, course_title, model_loaded,
                                    recommendations }
```

---

## 8. Зависимости (ключевые)

| Пакет | Версия | Назначение |
|---|---|---|
| `react` + `react-dom` | 18.x | UI-фреймворк |
| `react-router-dom` | 6.x | Клиентский роутинг |
| `zustand` | 4.x | Глобальный стейт (authStore) |
| `axios` | 1.x | HTTP-клиент с interceptors |
| `tailwindcss` | 3.x | Утилитарный CSS |
| `lucide-react` | latest | SVG-иконки |
| `react-markdown` | latest | Рендер markdown (чат, редактор) |
| `vite` | 5.x | Сборщик и dev-сервер |
