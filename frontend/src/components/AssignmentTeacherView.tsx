import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  Clock,
  Sparkles,
  User,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import client from '../api/client'
import type { AssignmentSubmission, SubmissionStatus } from '../api/types'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  assignmentId: number
  maxScore: number
}

// ---------------------------------------------------------------------------
// Approve form state per submission
// ---------------------------------------------------------------------------

interface ApproveFormState {
  score: string
  comment: string
  loading: boolean
  error: string | null
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  SubmissionStatus,
  { label: string; icon: React.ReactNode; classes: string }
> = {
  pending: {
    label: 'Ожидает AI',
    icon: <Clock className="w-3 h-3" />,
    classes: 'bg-yellow-100 text-yellow-700 ring-yellow-200',
  },
  ai_checked: {
    label: 'Проверено AI',
    icon: <Sparkles className="w-3 h-3" />,
    classes: 'bg-violet-100 text-violet-700 ring-violet-200',
  },
  approved: {
    label: 'Утверждено',
    icon: <CheckCircle2 className="w-3 h-3" />,
    classes: 'bg-green-100 text-green-700 ring-green-200',
  },
}

function StatusBadge({ status }: { status: SubmissionStatus }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${cfg.classes}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Single submission row
// ---------------------------------------------------------------------------

function SubmissionRow({
  submission,
  maxScore,
  onApproved,
}: {
  submission: AssignmentSubmission
  maxScore: number
  onApproved: (updated: AssignmentSubmission) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [form, setForm] = useState<ApproveFormState>({
    score: String(submission.final_score ?? submission.ai_evaluation?.score ?? ''),
    comment: submission.teacher_comment ?? '',
    loading: false,
    error: null,
  })

  const handleApprove = async () => {
    const scoreNum = parseInt(form.score, 10)
    if (isNaN(scoreNum) || scoreNum < 0 || scoreNum > maxScore) {
      setForm((f) => ({
        ...f,
        error: `Балл должен быть от 0 до ${maxScore}.`,
      }))
      return
    }

    setForm((f) => ({ ...f, loading: true, error: null }))

    try {
      const { data } = await client.patch<AssignmentSubmission>(
        `/api/v1/submissions/${submission.id}/approve/`,
        { final_score: scoreNum, teacher_comment: form.comment || null },
      )
      onApproved(data)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string; final_score?: string[] } } })
          ?.response?.data?.detail ??
        (err as { response?: { data?: { final_score?: string[] } } })?.response?.data
          ?.final_score?.[0] ??
        'Не удалось утвердить оценку.'
      setForm((f) => ({ ...f, loading: false, error: msg }))
    }
  }

  const aiScore = submission.ai_evaluation?.score
  const displayScore = submission.final_score ?? aiScore

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-gray-500">
          <User className="h-4 w-4" />
        </div>

        <span className="flex-1 text-sm font-medium text-gray-800 truncate">
          {submission.student_username}
        </span>

        {displayScore !== null && displayScore !== undefined && (
          <span className="text-sm font-semibold text-indigo-600 shrink-0">
            {displayScore}
            <span className="text-xs font-normal text-gray-400"> / {maxScore}</span>
          </span>
        )}

        <StatusBadge status={submission.status} />

        <button className="ml-1 text-gray-400 hover:text-gray-600 shrink-0">
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-4">
          {/* Student answer */}
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
              Ответ студента
            </p>
            <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
              {submission.answer_text}
            </div>
            <p className="mt-1 text-xs text-gray-400">
              {new Date(submission.submitted_at).toLocaleString('ru-RU')}
            </p>
          </div>

          {/* AI evaluation */}
          {submission.ai_evaluation && (
            <div className="rounded-lg bg-violet-50 px-4 py-3 space-y-2 ring-1 ring-violet-100">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-violet-700">
                <Sparkles className="h-3.5 w-3.5" />
                Оценка AI — {submission.ai_evaluation.score} / {maxScore}
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">
                {submission.ai_evaluation.feedback}
              </p>
            </div>
          )}

          {/* Approve form — only if not yet approved */}
          {submission.status !== 'approved' ? (
            <div className="space-y-3 rounded-lg bg-gray-50 px-4 py-3 ring-1 ring-gray-200">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Утвердить оценку
              </p>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <label
                    htmlFor={`score-${submission.id}`}
                    className="text-sm text-gray-600 shrink-0"
                  >
                    Балл:
                  </label>
                  <input
                    id={`score-${submission.id}`}
                    type="number"
                    min={0}
                    max={maxScore}
                    value={form.score}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, score: e.target.value, error: null }))
                    }
                    className="w-20 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-center shadow-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                  />
                  <span className="text-sm text-gray-400">/ {maxScore}</span>
                </div>
              </div>

              <textarea
                placeholder="Комментарий (необязательно)..."
                value={form.comment}
                onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))}
                rows={2}
                className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 placeholder-gray-400 shadow-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
              />

              {form.error && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600 ring-1 ring-red-200">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  {form.error}
                </div>
              )}

              <button
                onClick={handleApprove}
                disabled={form.loading}
                className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-green-700 active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
              >
                {form.loading ? (
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Утвердить оценку
              </button>
            </div>
          ) : (
            <div className="rounded-lg bg-green-50 px-4 py-3 ring-1 ring-green-200 space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-green-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Итоговый балл утверждён: {submission.final_score} / {maxScore}
              </div>
              {submission.teacher_comment && (
                <p className="text-sm text-green-800">{submission.teacher_comment}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AssignmentTeacherView({ assignmentId, maxScore }: Props) {
  const [submissions, setSubmissions] = useState<AssignmentSubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setFetchError(null)
      try {
        const { data } = await client.get<AssignmentSubmission[]>(
          `/api/v1/assignments/${assignmentId}/submissions/`,
        )
        if (!cancelled) setSubmissions(data)
      } catch {
        if (!cancelled) setFetchError('Не удалось загрузить ответы студентов.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [assignmentId])

  const handleApproved = (updated: AssignmentSubmission) => {
    setSubmissions((prev) =>
      prev.map((s) => (s.id === updated.id ? updated : s)),
    )
  }

  // ---------------------------------------------------------------------------
  // Stats bar
  // ---------------------------------------------------------------------------

  const total = submissions.length
  const approved = submissions.filter((s) => s.status === 'approved').length
  const aiChecked = submissions.filter((s) => s.status === 'ai_checked').length
  const pending = submissions.filter((s) => s.status === 'pending').length

  // ---------------------------------------------------------------------------
  // Render
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
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
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

  return (
    <div className="space-y-5">
      {/* Stats bar */}
      {total > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Всего ответов', value: total, color: 'text-gray-800' },
            { label: 'Ожидают AI', value: pending, color: 'text-yellow-600' },
            { label: 'Проверено AI', value: aiChecked, color: 'text-violet-600' },
            { label: 'Утверждено', value: approved, color: 'text-green-600' },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm text-center"
            >
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Submissions list */}
      {submissions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 py-14 text-center">
          <User className="mx-auto h-8 w-8 text-gray-300 mb-3" />
          <p className="text-sm text-gray-400">Студенты ещё не отправили ответы</p>
        </div>
      ) : (
        <div className="space-y-3">
          {submissions.map((sub) => (
            <SubmissionRow
              key={sub.id}
              submission={sub}
              maxScore={maxScore}
              onApproved={handleApproved}
            />
          ))}
        </div>
      )}
    </div>
  )
}
