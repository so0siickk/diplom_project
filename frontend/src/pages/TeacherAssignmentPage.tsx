import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, FileQuestion, AlertCircle } from 'lucide-react'
import AssignmentTeacherView from '../components/AssignmentTeacherView'
import client from '../api/client'
import type { OpenAssignment } from '../api/types'

// ---------------------------------------------------------------------------
// Invalid ID fallback
// ---------------------------------------------------------------------------

function InvalidIdFallback() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-500">
        <FileQuestion className="h-8 w-8" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-gray-800">Задание не найдено</h2>
        <p className="mt-1 text-sm text-gray-500">
          Идентификатор задания в URL некорректен или ссылка устарела.
        </p>
      </div>
      <Link
        to="/instructor"
        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
      >
        <ArrowLeft className="h-4 w-4" />
        Панель преподавателя
      </Link>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function PageSpinner() {
  return (
    <div className="flex justify-center py-20 text-gray-400">
      <svg className="h-8 w-8 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TeacherAssignmentPage() {
  const { assignmentId } = useParams<{ assignmentId: string }>()
  const parsedId = Number(assignmentId)

  const [assignment, setAssignment] = useState<OpenAssignment | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const isValidId = Boolean(assignmentId) && !isNaN(parsedId)

  useEffect(() => {
    if (!isValidId) {
      setLoading(false)
      return
    }

    let cancelled = false

    client
      .get<OpenAssignment>(`/api/v1/assignments/${parsedId}/`)
      .then(({ data }) => {
        if (!cancelled) setAssignment(data)
      })
      .catch(() => {
        if (!cancelled) setFetchError('Не удалось загрузить задание.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [parsedId, isValidId])

  // -- invalid URL param --
  if (!isValidId) return <InvalidIdFallback />

  // -- loading --
  if (loading) return <PageSpinner />

  // -- fetch error --
  if (fetchError || !assignment) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {fetchError ?? 'Задание не найдено.'}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link
          to="/instructor"
          className="flex items-center gap-1 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Панель преподавателя
        </Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">Проверка ответов</span>
      </div>

      {/* Header */}
      <div className="rounded-2xl border border-gray-200 bg-white px-6 py-5 shadow-sm">
        <h1 className="text-xl font-bold text-gray-900">{assignment.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-gray-500">
          {assignment.lesson_title && (
            <span>Урок: {assignment.lesson_title}</span>
          )}
          <span className="rounded-lg bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
            Макс. балл: {assignment.max_score}
          </span>
          {!assignment.is_active && (
            <span className="rounded-lg bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-500">
              Неактивно
            </span>
          )}
        </div>
      </div>

      {/* Submissions list */}
      <AssignmentTeacherView
        assignmentId={parsedId}
        maxScore={assignment.max_score}
      />
    </div>
  )
}
