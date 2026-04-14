/**
 * src/pages/CourseEditor.tsx
 * ===========================
 * Interactive CMS for course content:
 *   Left  — collapsible tree (modules + lessons)
 *   Right — context-sensitive form (course / module / lesson editor)
 *
 * Routes:
 *   /instructor/new          — create a new course
 *   /instructor/edit/:id     — edit an existing course
 *
 * On lesson save the backend automatically re-indexes content for the RAG assistant.
 */

import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
  Layers,
  Loader2,
  PenLine,
  Plus,
  Save,
  Settings,
  Trash2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import client from '../api/client'
import type { Course as ApiCourse } from '../api/types'

// ---------------------------------------------------------------------------
// Draft types
// ---------------------------------------------------------------------------

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

interface DraftLesson {
  _key: string
  id: number | null
  title: string
  content: string
  video_url: string
  order: number
}

interface DraftModule {
  _key: string
  id: number | null
  title: string
  description: string
  order: number
  expanded: boolean
  lessons: DraftLesson[]
}

interface DraftCourse {
  id: number | null
  title: string
  description: string
  modules: DraftModule[]
}

type Selection =
  | { type: 'course' }
  | { type: 'module'; mi: number }
  | { type: 'lesson'; mi: number; li: number }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _kc = 0
const nk = () => `_new_${++_kc}`

function hydrate(api: ApiCourse): DraftCourse {
  return {
    id: api.id,
    title: api.title,
    description: api.description,
    modules: [...api.modules]
      .sort((a, b) => a.order - b.order)
      .map((m) => ({
        _key: String(m.id),
        id: m.id,
        title: m.title,
        description: m.description,
        order: m.order,
        expanded: true,
        lessons: [...m.lessons]
          .sort((a, b) => a.order - b.order)
          .map((l) => ({
            _key: String(l.id),
            id: l.id,
            title: l.title,
            content: l.content,
            video_url: l.video_url ?? '',
            order: l.order,
          })),
      })),
  }
}

function emptyDraft(): DraftCourse {
  return { id: null, title: '', description: '', modules: [] }
}

// ---------------------------------------------------------------------------
// Save button
// ---------------------------------------------------------------------------

function SaveBtn({ status, onClick }: { status: SaveStatus; onClick: () => void }) {
  const map: Record<SaveStatus, { label: string; cls: string; icon: React.ReactNode }> = {
    idle:   { label: 'Сохранить',           cls: 'bg-indigo-600 hover:bg-indigo-700 text-white',  icon: <Save size={14} /> },
    saving: { label: 'Сохранение…',         cls: 'bg-indigo-400 cursor-not-allowed text-white',   icon: <Loader2 size={14} className="animate-spin" /> },
    saved:  { label: 'Сохранено',           cls: 'bg-emerald-600 text-white',                     icon: <CheckCircle2 size={14} /> },
    error:  { label: 'Ошибка — повторить', cls: 'bg-red-600 hover:bg-red-700 text-white',        icon: <AlertCircle size={14} /> },
  }
  const { label, cls, icon } = map[status]

  return (
    <button
      onClick={onClick}
      disabled={status === 'saving'}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                  transition-colors ${cls}`}
    >
      {icon}
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Field components
// ---------------------------------------------------------------------------

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1.5">{label}</label>
      {children}
    </div>
  )
}

const inputCls =
  'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg ' +
  'focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white'

// ---------------------------------------------------------------------------
// Panel: Course settings
// ---------------------------------------------------------------------------

function CoursePanel({
  draft, onUpdate, saveStatus, onSave,
}: {
  draft: DraftCourse
  onUpdate: (p: Partial<Pick<DraftCourse, 'title' | 'description'>>) => void
  saveStatus: SaveStatus
  onSave: () => void
}) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-base font-semibold text-gray-900">Настройки курса</h2>
        <SaveBtn status={saveStatus} onClick={onSave} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <Field label="Заголовок">
          <input
            value={draft.title}
            onChange={(e) => onUpdate({ title: e.target.value })}
            placeholder="например, Введение в машинное обучение"
            className={inputCls}
          />
        </Field>
        <Field label="Описание">
          <textarea
            value={draft.description}
            onChange={(e) => onUpdate({ description: e.target.value })}
            rows={4}
            placeholder="Что студенты узнают на этом курсе?"
            className={`${inputCls} resize-none`}
          />
        </Field>

        {draft.id === null && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100
                         rounded-lg px-3 py-2">
            Сначала сохраните курс — затем вы сможете добавлять модули и уроки.
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Panel: Module settings
// ---------------------------------------------------------------------------

function ModulePanel({
  mod, mi, courseUnsaved, onUpdate, saveStatus, onSave,
}: {
  mod: DraftModule
  mi: number
  courseUnsaved: boolean
  onUpdate: (p: Partial<Pick<DraftModule, 'title' | 'description' | 'order'>>) => void
  saveStatus: SaveStatus
  onSave: () => void
}) {
  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-base font-semibold text-gray-900">Модуль {mi + 1}</h2>
        <SaveBtn status={saveStatus} onClick={onSave} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <Field label="Заголовок">
          <input
            value={mod.title}
            onChange={(e) => onUpdate({ title: e.target.value })}
            placeholder="Заголовок модуля"
            className={inputCls}
          />
        </Field>
        <Field label="Описание (необязательно)">
          <textarea
            value={mod.description}
            onChange={(e) => onUpdate({ description: e.target.value })}
            rows={3}
            placeholder="Краткое описание этого модуля"
            className={`${inputCls} resize-none`}
          />
        </Field>
        <Field label="Порядок отображения">
          <input
            type="number"
            min={1}
            value={mod.order}
            onChange={(e) => onUpdate({ order: Number(e.target.value) })}
            className={`${inputCls} w-24`}
          />
        </Field>

        {courseUnsaved && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100
                         rounded-lg px-3 py-2">
            Сохраните курс перед сохранением этого модуля.
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Panel: Lesson editor
// ---------------------------------------------------------------------------

function LessonPanel({
  lesson, moduleUnsaved, tab, onTabChange, onUpdate, saveStatus, onSave,
}: {
  lesson: DraftLesson
  moduleUnsaved: boolean
  tab: 'edit' | 'preview'
  onTabChange: (t: 'edit' | 'preview') => void
  onUpdate: (p: Partial<Pick<DraftLesson, 'title' | 'content' | 'video_url' | 'order'>>) => void
  saveStatus: SaveStatus
  onSave: () => void
}) {
  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-base font-semibold text-gray-900">Редактор урока</h2>
        <div className="flex items-center gap-3">
          {saveStatus === 'saved' && (
            <span className="text-xs text-emerald-600 bg-emerald-50 border border-emerald-100
                              rounded-full px-2 py-0.5">
              Индекс RAG обновлен
            </span>
          )}
          <SaveBtn status={saveStatus} onClick={onSave} />
        </div>
      </div>

      <div className="space-y-4">
        {/* Title */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <Field label="Заголовок">
            <input
              value={lesson.title}
              onChange={(e) => onUpdate({ title: e.target.value })}
              placeholder="Заголовок урока"
              className={inputCls}
            />
          </Field>
        </div>

        {/* Markdown editor with preview */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {/* Tab bar */}
          <div className="flex items-center gap-1 px-4 py-2 border-b border-gray-100 bg-gray-50">
            {(['edit', 'preview'] as const).map((t) => (
              <button
                key={t}
                onClick={() => onTabChange(t)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                            rounded-lg transition-colors ${
                  tab === t
                    ? 'bg-white text-indigo-700 shadow-sm border border-gray-200'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
              >
                {t === 'edit' ? <PenLine size={12} /> : <Eye size={12} />}
                {t === 'edit' ? 'Редактировать' : 'Предпросмотр'}
              </button>
            ))}
            <span className="ml-auto text-[10px] text-gray-300 pr-1">Markdown</span>
          </div>

          {/* Content area */}
          <div className="p-5">
            {tab === 'edit' ? (
              <textarea
                value={lesson.content}
                onChange={(e) => onUpdate({ content: e.target.value })}
                rows={20}
                placeholder={'# Заголовок урока\n\nНапишите содержание урока в Markdown…\n\n## Секция\n\nТекст параграфа здесь.'}
                className="w-full text-sm text-gray-800 leading-relaxed resize-y font-mono
                           focus:outline-none placeholder-gray-300 bg-transparent"
                style={{ minHeight: '360px' }}
              />
            ) : (
              <div className="prose prose-sm max-w-none min-h-[360px] text-gray-800">
                {lesson.content ? (
                  <ReactMarkdown>{lesson.content}</ReactMarkdown>
                ) : (
                  <p className="text-gray-300 italic text-sm">Пока нечего просматривать.</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Video URL */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <Field label="URL видео (необязательно)">
            <input
              value={lesson.video_url}
              onChange={(e) => onUpdate({ video_url: e.target.value })}
              placeholder="https://youtube.com/watch?v=..."
              className={inputCls}
            />
          </Field>
        </div>

        {moduleUnsaved && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100
                         rounded-lg px-3 py-2">
            Сохраните модуль перед сохранением этого урока.
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tree (left sidebar)
// ---------------------------------------------------------------------------

function Tree({
  draft,
  selection,
  onSelect,
  onToggleModule,
  onAddModule,
  onAddLesson,
  onDeleteModule,
  onDeleteLesson,
  onBack,
}: {
  draft: DraftCourse
  selection: Selection
  onSelect: (s: Selection) => void
  onToggleModule: (mi: number) => void
  onAddModule: () => void
  onAddLesson: (mi: number) => void
  onDeleteModule: (mi: number) => void
  onDeleteLesson: (mi: number, li: number) => void
  onBack: () => void
}) {
  const isModule = (mi: number) =>
    selection.type === 'module' && selection.mi === mi
  const isLesson = (mi: number, li: number) =>
    selection.type === 'lesson' && selection.mi === mi && selection.li === li

  return (
    <aside className="w-72 flex-shrink-0 bg-white border-r border-gray-200
                       flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-100 flex-shrink-0">
        <button
          onClick={onBack}
          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700
                     hover:bg-gray-100 transition-colors"
          title="Назад к Моим курсам"
        >
          <ArrowLeft size={15} />
        </button>
        <span className="text-xs font-semibold text-gray-600 truncate">
          {draft.title || 'Новый курс'}
        </span>
      </div>

      {/* Scrollable tree */}
      <div className="flex-1 overflow-y-auto py-1">
        {/* Course settings row */}
        <TreeRow
          depth={0}
          icon={<Settings size={13} className="text-gray-400" />}
          label="Настройки курса"
          active={selection.type === 'course'}
          onClick={() => onSelect({ type: 'course' })}
        />

        {/* Modules */}
        {draft.modules.map((mod, mi) => (
          <div key={mod._key}>
            {/* Module row */}
            <div
              className={`flex items-center gap-1 px-2 py-1.5 group cursor-pointer select-none
                          ${isModule(mi) ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
              onClick={() => onSelect({ type: 'module', mi })}
            >
              {/* Expand toggle */}
              <button
                onClick={(e) => { e.stopPropagation(); onToggleModule(mi) }}
                className="p-0.5 text-gray-400 hover:text-gray-600 flex-shrink-0"
              >
                {mod.expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              </button>

              <Layers size={13} className="flex-shrink-0 text-gray-400" />

              <span className={`flex-1 text-sm truncate ${
                isModule(mi) ? 'text-indigo-700 font-medium' : 'text-gray-700'
              }`}>
                {mod.title || 'Без названия'}
              </span>

              {mod.id === null && (
                <span className="text-[10px] text-amber-500 flex-shrink-0 mr-1">не сохранено</span>
              )}

              <button
                onClick={(e) => { e.stopPropagation(); onDeleteModule(mi) }}
                className="opacity-0 group-hover:opacity-100 p-0.5 flex-shrink-0
                           text-gray-300 hover:text-red-500 transition-all"
                title="Удалить модуль"
              >
                <Trash2 size={12} />
              </button>
            </div>

            {/* Lessons */}
            {mod.expanded && (
              <div>
                {mod.lessons.map((lesson, li) => (
                  <div
                    key={lesson._key}
                    className={`flex items-center gap-1 pl-10 pr-2 py-1.5 group cursor-pointer
                                ${isLesson(mi, li) ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
                    onClick={() => onSelect({ type: 'lesson', mi, li })}
                  >
                    <FileText size={12} className="flex-shrink-0 text-gray-300" />
                    <span className={`flex-1 text-sm truncate ${
                      isLesson(mi, li) ? 'text-indigo-700 font-medium' : 'text-gray-600'
                    }`}>
                      {lesson.title || 'Без названия'}
                    </span>
                    {lesson.id === null && (
                      <span className="text-[10px] text-amber-500 flex-shrink-0 mr-1">не сохранено</span>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); onDeleteLesson(mi, li) }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 flex-shrink-0
                                 text-gray-300 hover:text-red-500 transition-all"
                      title="Удалить урок"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}

                {/* Add lesson button */}
                <button
                  onClick={() => onAddLesson(mi)}
                  disabled={mod.id === null}
                  className="flex items-center gap-1.5 pl-10 pr-3 py-1.5 w-full text-xs
                             text-gray-400 hover:text-indigo-600 hover:bg-indigo-50
                             transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Plus size={11} />
                  Добавить урок
                </button>
              </div>
            )}
          </div>
        ))}

        {/* Add module button */}
        <div className="border-t border-gray-100 mt-1">
          <button
            onClick={onAddModule}
            disabled={draft.id === null}
            className="flex items-center gap-1.5 w-full px-3 py-2 text-xs
                       text-gray-400 hover:text-indigo-600 hover:bg-indigo-50
                       transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title={draft.id === null ? 'Сначала сохраните курс' : 'Добавить новый модуль'}
          >
            <Plus size={13} />
            Добавить модуль
          </button>
        </div>
      </div>
    </aside>
  )
}

function TreeRow({
  depth, icon, label, active, onClick,
}: {
  depth: number
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{ paddingLeft: `${(depth + 1) * 12}px` }}
      className={`w-full flex items-center gap-2 pr-3 py-2 text-sm transition-colors
                  ${active ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-600 hover:bg-gray-50'}`}
    >
      {icon}
      <span className="truncate">{label}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function CourseEditor() {
  const { id } = useParams<{ id?: string }>()
  const navigate = useNavigate()

  const [draft, setDraft] = useState<DraftCourse>(emptyDraft())
  const [loading, setLoading] = useState(!!id)
  const [selection, setSelection] = useState<Selection>({ type: 'course' })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [lessonTab, setLessonTab] = useState<'edit' | 'preview'>('edit')

  // Reset save status on selection change
  const select = (s: Selection) => {
    setSelection(s)
    setSaveStatus('idle')
  }

  // ---- Load existing course ----
  useEffect(() => {
    if (!id) return
    setLoading(true)
    client
      .get<ApiCourse>(`/api/v1/courses/${id}/`)
      .then(({ data }) => setDraft(hydrate(data)))
      .catch(() => navigate('/instructor/my-courses', { replace: true }))
      .finally(() => setLoading(false))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Draft updaters ----
  const updCourse = (patch: Partial<Pick<DraftCourse, 'title' | 'description'>>) =>
    setDraft((p) => ({ ...p, ...patch }))

  const updModule = (mi: number, patch: Partial<Pick<DraftModule, 'title' | 'description' | 'order' | 'expanded'>>) =>
    setDraft((p) => {
      const modules = [...p.modules]
      modules[mi] = { ...modules[mi], ...patch }
      return { ...p, modules }
    })

  const updLesson = (
    mi: number,
    li: number,
    patch: Partial<Pick<DraftLesson, 'title' | 'content' | 'video_url' | 'order'>>,
  ) =>
    setDraft((p) => {
      const modules = [...p.modules]
      const lessons = [...modules[mi].lessons]
      lessons[li] = { ...lessons[li], ...patch }
      modules[mi] = { ...modules[mi], lessons }
      return { ...p, modules }
    })

  // ---- Save wrapper ----
  const withStatus = async (fn: () => Promise<void>) => {
    setSaveStatus('saving')
    try {
      await fn()
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2500)
    } catch {
      setSaveStatus('error')
    }
  }

  // ---- Save course ----
  const saveCourse = () =>
    withStatus(async () => {
      const payload = { title: draft.title, description: draft.description }
      if (draft.id === null) {
        const { data } = await client.post<{ id: number }>('/api/v1/courses/', payload)
        setDraft((p) => ({ ...p, id: data.id }))
        navigate(`/instructor/edit/${data.id}`, { replace: true })
      } else {
        await client.patch(`/api/v1/courses/${draft.id}/`, payload)
      }
    })

  // ---- Save module ----
  const saveModule = (mi: number) =>
    withStatus(async () => {
      const m = draft.modules[mi]
      if (!draft.id) throw new Error('Save course first')
      const payload = { course: draft.id, title: m.title, description: m.description, order: m.order }
      if (m.id === null) {
        const { data } = await client.post<{ id: number }>('/api/v1/modules/', payload)
        setDraft((p) => {
          const modules = [...p.modules]
          modules[mi] = { ...modules[mi], id: data.id }
          return { ...p, modules }
        })
      } else {
        await client.patch(`/api/v1/modules/${m.id}/`, payload)
      }
    })

  // ---- Save lesson ----
  const saveLesson = (mi: number, li: number) =>
    withStatus(async () => {
      const l = draft.modules[mi].lessons[li]
      const moduleId = draft.modules[mi].id
      if (!moduleId) throw new Error('Save module first')
      const payload = {
        module: moduleId,
        title: l.title,
        content: l.content,
        video_url: l.video_url || null,
        order: l.order,
      }
      if (l.id === null) {
        const { data } = await client.post<{ id: number }>('/api/v1/lessons/', payload)
        setDraft((p) => {
          const modules = [...p.modules]
          const lessons = [...modules[mi].lessons]
          lessons[li] = { ...lessons[li], id: data.id }
          modules[mi] = { ...modules[mi], lessons }
          return { ...p, modules }
        })
      } else {
        await client.patch(`/api/v1/lessons/${l.id}/`, payload)
      }
    })

  // ---- Delete module ----
  const deleteModule = async (mi: number) => {
    const m = draft.modules[mi]
    if (m.id !== null) await client.delete(`/api/v1/modules/${m.id}/`)
    setDraft((p) => ({ ...p, modules: p.modules.filter((_, i) => i !== mi) }))
    select({ type: 'course' })
  }

  // ---- Delete lesson ----
  const deleteLesson = async (mi: number, li: number) => {
    const l = draft.modules[mi].lessons[li]
    if (l.id !== null) await client.delete(`/api/v1/lessons/${l.id}/`)
    setDraft((p) => {
      const modules = [...p.modules]
      modules[mi] = { ...modules[mi], lessons: modules[mi].lessons.filter((_, i) => i !== li) }
      return { ...p, modules }
    })
    select({ type: 'module', mi })
  }

  // ---- Add module ----
  const addModule = () => {
    const newMod: DraftModule = {
      _key: nk(),
      id: null,
      title: 'Новый модуль',
      description: '',
      order: draft.modules.length + 1,
      expanded: true,
      lessons: [],
    }
    setDraft((p) => ({ ...p, modules: [...p.modules, newMod] }))
    select({ type: 'module', mi: draft.modules.length })
  }

  // ---- Add lesson ----
  const addLesson = (mi: number) => {
    const newLesson: DraftLesson = {
      _key: nk(),
      id: null,
      title: 'Новый урок',
      content: '',
      video_url: '',
      order: draft.modules[mi].lessons.length + 1,
    }
    setDraft((p) => {
      const modules = [...p.modules]
      modules[mi] = { ...modules[mi], lessons: [...modules[mi].lessons, newLesson] }
      return { ...p, modules }
    })
    select({ type: 'lesson', mi, li: draft.modules[mi].lessons.length })
  }

  // ---- Loading state ----
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-sm text-gray-400">Загрузка курса…</p>
      </div>
    )
  }

  // ---- Render ----
  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* ── Left tree ── */}
      <Tree
        draft={draft}
        selection={selection}
        onSelect={select}
        onToggleModule={(mi) => updModule(mi, { expanded: !draft.modules[mi].expanded })}
        onAddModule={addModule}
        onAddLesson={addLesson}
        onDeleteModule={deleteModule}
        onDeleteLesson={deleteLesson}
        onBack={() => navigate('/instructor/my-courses')}
      />

      {/* ── Right form ── */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        {selection.type === 'course' && (
          <CoursePanel
            draft={draft}
            onUpdate={updCourse}
            saveStatus={saveStatus}
            onSave={saveCourse}
          />
        )}

        {selection.type === 'module' && (() => {
          const { mi } = selection
          return (
            <ModulePanel
              mod={draft.modules[mi]}
              mi={mi}
              courseUnsaved={draft.id === null}
              onUpdate={(patch) => updModule(mi, patch)}
              saveStatus={saveStatus}
              onSave={() => saveModule(mi)}
            />
          )
        })()}

        {selection.type === 'lesson' && (() => {
          const { mi, li } = selection
          return (
            <LessonPanel
              lesson={draft.modules[mi].lessons[li]}
              moduleUnsaved={draft.modules[mi].id === null}
              tab={lessonTab}
              onTabChange={setLessonTab}
              onUpdate={(patch) => updLesson(mi, li, patch)}
              saveStatus={saveStatus}
              onSave={() => saveLesson(mi, li)}
            />
          )
        })()}
      </main>
    </div>
  )
}
