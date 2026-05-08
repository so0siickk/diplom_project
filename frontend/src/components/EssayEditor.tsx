import { useEffect, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
} from 'lucide-react'
import { isAxiosError } from 'axios'
import client from '../api/client'
import type { Assignment } from '../api/types'

// ---------------------------------------------------------------------------
// Local response type — mirrors EssaySubmissionSerializer
// ---------------------------------------------------------------------------

interface SubmissionResponse {
  id: number
  assignment: number
  assignment_title: string
  text_content: string
  ai_feedback: string | null
  score: number | null
  created_at: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function wordCount(text: string): number {
  return text.trim() === '' ? 0 : text.trim().split(/\s+/).length
}

const MIN_WORDS = 10

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Attemptsbadge({
  used,
  max,
}: {
  used: number
  max: number
}) {
  return (
    <span className="inline-flex items-center rounded-full border border-gray-200
                     bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-500">
      Попытка: {used} из {max || '∞'}
    </span>
  )
}

function AiReviewCard({
  aiFeedback,
  score,
  maxScore,
}: {
  aiFeedback: string
  score: number
  maxScore: number
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        AI Review
      </p>
      <div className="rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500
                      to-purple-600 p-5 text-white shadow-md">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles size={15} className="flex-shrink-0 text-yellow-300" />
            <span className="text-sm font-semibold">GigaChat Review</span>
          </div>
          <div className="flex-shrink-0 text-right">
            <span className="text-2xl font-bold">{score}</span>
            <span className="text-sm text-white/60"> / {maxScore}</span>
          </div>
        </div>
        <p className="text-sm leading-relaxed text-white/90 whitespace-pre-wrap">
          {aiFeedback}
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  assignment: Assignment
}

export default function EssayEditor({ assignment }: Props) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<SubmissionResponse | null>(null)
  const [attemptsUsed, setAttemptsUsed] = useState(0)
  const [editing, setEditing] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Load existing submissions on mount
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data } = await client.get<SubmissionResponse[]>(
          `/api/v1/essay-assignments/${assignment.id}/my-submissions/`,
        )
        if (!cancelled && data.length > 0) {
          setResult(data[0])
          setText(data[0].text_content)
          setAttemptsUsed(data.length)
        }
      } catch {
        // empty / 404 = no prior submission
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [assignment.id])

  const hasAttemptsLeft =
    assignment.max_attempts === 0 || attemptsUsed < assignment.max_attempts

  // Form is locked only when there is a result AND the user is NOT in retry mode
  const alreadySubmitted = result !== null && !editing

  const words = wordCount(text)
  const tooShort = words < MIN_WORDS

  const canRetry =
    result !== null &&
    result.ai_feedback !== null &&
    result.score !== null &&
    hasAttemptsLeft &&
    !editing

  const handleSubmit = async () => {
    if (submitting || alreadySubmitted || tooShort) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const { data } = await client.post<SubmissionResponse>(
        `/api/v1/essay-assignments/${assignment.id}/submit/`,
        { text_content: text },
      )
      setResult(data)
      setAttemptsUsed((n) => n + 1)
      setEditing(false)
    } catch (err) {
      if (isAxiosError(err)) {
        const detail = err.response?.data?.detail as string | undefined
        setSubmitError(detail ?? 'Не удалось отправить задание.')
      } else {
        setSubmitError('Не удалось отправить задание.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-10 text-gray-400">
        <Loader2 size={22} className="animate-spin" />
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-white overflow-hidden">

      {/* ── Header ── */}
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50">
            <FileText size={18} className="text-blue-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">{assignment.title}</p>
            <p className="text-xs text-gray-400">Эссе · до {assignment.max_score} баллов</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Attemptsbadge used={attemptsUsed} max={assignment.max_attempts} />
          {alreadySubmitted && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-green-200
                             bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
              <CheckCircle2 size={11} />
              Отправлено
            </span>
          )}
        </div>
      </div>

      {/* ── Description ── */}
      {assignment.description && (
        <p className="border-b border-gray-100 bg-gray-50 px-5 py-3 text-xs text-gray-500">
          {assignment.description}
        </p>
      )}

      {/* ── Textarea ── */}
      <div className="border-b border-gray-100 px-5 py-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={alreadySubmitted}
          placeholder="Напишите ваш ответ здесь…"
          rows={10}
          className="w-full resize-none rounded-lg border border-gray-200 bg-white px-4 py-3
                     text-sm leading-relaxed text-gray-800 placeholder-gray-300
                     transition-colors focus:border-blue-400 focus:outline-none
                     focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed
                     disabled:bg-gray-50 disabled:text-gray-500"
        />
        <div className="mt-1.5 flex items-center justify-between">
          <p className="text-xs text-gray-400">
            {words} {words === 1 ? 'слово' : words >= 2 && words <= 4 ? 'слова' : 'слов'}
          </p>
          {!alreadySubmitted && tooShort && words > 0 && (
            <p className="text-xs text-amber-500">Минимум 10 слов</p>
          )}
        </div>
      </div>

      {/* ── Submit button ── */}
      <div className="flex items-center gap-3 px-5 py-4">
        <button
          onClick={handleSubmit}
          disabled={submitting || alreadySubmitted || tooShort}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5
                     text-sm font-semibold text-white transition-colors hover:bg-blue-700
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                     disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={13} />}
          {submitting ? 'Отправка…' : alreadySubmitted ? 'Уже отправлено' : 'Отправить на проверку ИИ'}
        </button>
        {submitting && (
          <p className="text-xs text-gray-400">Эссе отправляется на AI-проверку…</p>
        )}
      </div>

      {/* ── Error banner ── */}
      {submitError && (
        <div className="mx-5 mb-4 flex items-start gap-2 rounded-lg border border-red-200
                        bg-red-50 px-4 py-3">
          <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-red-500" />
          <p className="text-xs text-red-700">{submitError}</p>
        </div>
      )}

      {/* ── AI Review (hidden while editing) ── */}
      {result && !editing && (
        <div className="space-y-3 border-t border-gray-100 px-5 py-5">
          {result.ai_feedback !== null && result.score !== null ? (
            <>
              <AiReviewCard
                aiFeedback={result.ai_feedback}
                score={result.score}
                maxScore={assignment.max_score}
              />
              {canRetry && (
                <button
                  onClick={() => setEditing(true)}
                  className="inline-flex items-center gap-2 rounded-lg border border-blue-200
                             bg-blue-50 px-4 py-2 text-xs font-semibold text-blue-700
                             transition-colors hover:bg-blue-100"
                >
                  <RotateCcw size={13} />
                  Исправить ответ
                </button>
              )}
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-yellow-300 bg-yellow-50 p-4">
              <p className="text-xs text-yellow-700">
                AI-проверка ещё не завершена. Обновите страницу через несколько секунд.
              </p>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
