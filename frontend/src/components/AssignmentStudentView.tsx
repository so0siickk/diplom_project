import { useEffect, useState } from 'react'
import {
  Send,
  CheckCircle2,
  Clock,
  AlertCircle,
  Sparkles,
  BookOpen,
} from 'lucide-react'
import client from '../api/client'
import type {
  OpenAssignment,
  AssignmentSubmission,
  SubmissionStatus,
} from '../api/types'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  assignmentId: number
}

// ---------------------------------------------------------------------------
// Status badge (submission)
// ---------------------------------------------------------------------------

const SUBMISSION_STATUS: Record<
  SubmissionStatus,
  { label: string; icon: React.ReactNode; classes: string }
> = {
  pending: {
    label: 'Ожидает проверки AI',
    icon: <Clock className="w-3.5 h-3.5" />,
    classes: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  },
  ai_checked: {
    label: 'Проверено AI',
    icon: <Sparkles className="w-3.5 h-3.5" />,
    classes: 'bg-violet-100 text-violet-800 ring-violet-200',
  },
  approved: {
    label: 'Утверждено преподавателем',
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
    classes: 'bg-green-100 text-green-800 ring-green-200',
  },
}

function SubmissionStatusBadge({ status }: { status: SubmissionStatus }) {
  const cfg = SUBMISSION_STATUS[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ring-1 ring-inset ${cfg.classes}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Score display
// ---------------------------------------------------------------------------

function ScoreDisplay({
  score,
  maxScore,
}: {
  score: number | null
  maxScore: number
}) {
  if (score === null) return null
  const pct = Math.round((score / maxScore) * 100)
  const color =
    pct >= 80
      ? 'text-green-600'
      : pct >= 50
        ? 'text-yellow-600'
        : 'text-red-600'

  return (
    <div className="flex items-baseline gap-1">
      <span className={`text-3xl font-bold ${color}`}>{score}</span>
      <span className="text-sm text-gray-400">/ {maxScore}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <svg
      className="h-5 w-5 animate-spin text-white"
      fill="none"
      viewBox="0 0 24 24"
    >
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
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AssignmentStudentView({ assignmentId }: Props) {
  const [assignment, setAssignment] = useState<OpenAssignment | null>(null)
  const [submission, setSubmission] = useState<AssignmentSubmission | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [answerText, setAnswerText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // -- initial fetch --

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setFetchError(null)
      try {
        const [assignmentRes, submissionRes] = await Promise.allSettled([
          client.get<OpenAssignment>(`/api/v1/assignments/${assignmentId}/`),
          client.get<AssignmentSubmission>(
            `/api/v1/assignments/${assignmentId}/my-submission/`,
          ),
        ])

        if (cancelled) return

        if (assignmentRes.status === 'fulfilled') {
          setAssignment(assignmentRes.value.data)
        } else {
          setFetchError('Не удалось загрузить задание.')
          return
        }

        if (submissionRes.status === 'fulfilled') {
          setSubmission(submissionRes.value.data)
        }
        // 404 means no submission yet — leave submission as null
      } catch {
        if (!cancelled) setFetchError('Ошибка при загрузке данных.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [assignmentId])

  // -- submit answer --

  const handleSubmit = async () => {
    if (!answerText.trim()) return

    setSubmitting(true)
    setSubmitError(null)

    try {
      const { data } = await client.post<AssignmentSubmission>(
        `/api/v1/assignments/${assignmentId}/submit/`,
        { answer_text: answerText.trim() },
      )
      setSubmission(data)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Не удалось отправить ответ. Попробуйте снова.'
      setSubmitError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render states
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex justify-center py-16 text-gray-400">
        <svg className="h-8 w-8 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          />
        </svg>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
        <AlertCircle className="h-4 w-4 shrink-0" />
        {fetchError}
      </div>
    )
  }

  if (!assignment) return null

  return (
    <div className="space-y-6">
      {/* Assignment header */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{assignment.title}</h2>
            {assignment.lesson_title && (
              <p className="text-xs text-gray-400">Урок: {assignment.lesson_title}</p>
            )}
          </div>
          <span className="ml-auto shrink-0 rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
            Макс. балл: {assignment.max_score}
          </span>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-gray-700 whitespace-pre-wrap">
          {assignment.description}
        </p>
      </div>

      {/* Not yet answered — input form */}
      {!submission && (
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-gray-700">Ваш ответ</h3>

          <textarea
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            rows={8}
            placeholder="Введите развёрнутый ответ..."
            disabled={submitting}
            className="w-full resize-y rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-800 placeholder-gray-400 shadow-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:opacity-50"
          />

          {submitError && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700 ring-1 ring-red-200">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {submitError}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={submitting || !answerText.trim()}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
          >
            {submitting ? <Spinner /> : <Send className="h-4 w-4" />}
            Отправить на проверку AI
          </button>
        </div>
      )}

      {/* Already submitted — result view */}
      {submission && (
        <div className="space-y-4">
          {/* Answer card */}
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-700">Ваш ответ</h3>
              <SubmissionStatusBadge status={submission.status} />
            </div>

            <textarea
              readOnly
              value={submission.answer_text}
              rows={6}
              className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700"
            />

            <p className="text-xs text-gray-400">
              Отправлено:{' '}
              {new Date(submission.submitted_at).toLocaleString('ru-RU')}
            </p>
          </div>

          {/* AI feedback card */}
          {submission.ai_evaluation && (
            <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-2 text-violet-700">
                <Sparkles className="h-4 w-4" />
                <span className="text-sm font-semibold">Оценка искусственного интеллекта</span>
              </div>

              <div className="flex items-end gap-4">
                <ScoreDisplay
                  score={submission.final_score ?? submission.ai_evaluation.score}
                  maxScore={assignment.max_score}
                />
                {submission.final_score !== null &&
                  submission.final_score !== submission.ai_evaluation.score && (
                    <span className="mb-1 text-xs text-gray-500">
                      AI предложил: {submission.ai_evaluation.score}
                    </span>
                  )}
              </div>

              <div className="rounded-xl bg-white/70 px-4 py-3 text-sm leading-relaxed text-gray-700 backdrop-blur-sm ring-1 ring-violet-100">
                {submission.ai_evaluation.feedback}
              </div>

              <p className="text-xs text-violet-400">
                Модель: {submission.ai_evaluation.model_name} ·{' '}
                {new Date(submission.ai_evaluation.evaluated_at).toLocaleString('ru-RU')}
              </p>
            </div>
          )}

          {/* Teacher comment */}
          {submission.status === 'approved' && submission.teacher_comment && (
            <div className="rounded-2xl border border-green-200 bg-green-50 p-5 space-y-1">
              <p className="text-xs font-semibold text-green-700">Комментарий преподавателя</p>
              <p className="text-sm text-green-800">{submission.teacher_comment}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
