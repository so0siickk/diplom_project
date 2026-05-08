import { useEffect, useState } from 'react'
import Editor from '@monaco-editor/react'
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Terminal,
} from 'lucide-react'
import { isAxiosError } from 'axios'
import client from '../api/client'
import type { Assignment } from '../api/types'

// ---------------------------------------------------------------------------
// Local response type — mirrors CodeSubmissionSerializer
// ---------------------------------------------------------------------------

interface CodeSubmissionResponse {
  uuid: string
  assignment: number
  assignment_title: string
  code_content: string
  status: string
  status_display: string
  output: string
  ai_feedback: string | null
  score: number | null
  submitted_at: string
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Attemptsbadge({ used, max }: { used: number; max: number }) {
  return (
    <span className="inline-flex items-center rounded-full border border-gray-200
                     bg-gray-50 px-2.5 py-1 text-xs font-medium text-gray-500">
      Попытка: {used} из {max || '∞'}
    </span>
  )
}

function ConsoleOutput({
  result,
  maxScore,
}: {
  result: CodeSubmissionResponse
  maxScore: number
}) {
  const timestamp = new Date(result.submitted_at).toLocaleString('ru-RU')

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        Console Output
      </p>
      <div className="rounded-lg bg-gray-950 px-5 py-4 font-mono text-xs leading-6 space-y-0.5">
        <p className="text-gray-500">$ python submission.py</p>
        <p className="text-green-400">&gt; Submitted at {timestamp}</p>
        <p className="text-gray-400">&gt; Status: {result.status_display}</p>
        {result.output && (
          <p className="text-cyan-300 whitespace-pre-wrap">&gt; {result.output}</p>
        )}
        {result.score !== null ? (
          <p className="text-yellow-400">
            &gt; AI score: {result.score} / {maxScore}
          </p>
        ) : (
          <p className="text-yellow-600">&gt; AI evaluation pending…</p>
        )}
      </div>
    </div>
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
        <div className="flex items-start justify-between gap-3 mb-3">
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

export default function CodeEditor({ assignment }: Props) {
  const starterCode =
    (assignment.content?.starter_code as string | undefined) ??
    '# Напишите ваш код здесь\n\ndef solution():\n    pass\n\nprint(solution())\n'

  const [code, setCode] = useState(starterCode)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<CodeSubmissionResponse | null>(null)
  const [attemptsUsed, setAttemptsUsed] = useState(0)
  const [editing, setEditing] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Load submission history on mount
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const { data } = await client.get<CodeSubmissionResponse[]>(
          `/api/v1/code-assignments/${assignment.id}/my-submissions/`,
        )
        if (!cancelled && data.length > 0) {
          setResult(data[0])
          setCode(data[0].code_content)
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

  // Editor is locked when there is a result AND the user is not retrying
  const alreadySubmitted = result !== null && !editing

  const canRetry =
    result !== null &&
    result.ai_feedback !== null &&
    result.score !== null &&
    hasAttemptsLeft &&
    !editing

  const handleSubmit = async () => {
    if (submitting || alreadySubmitted) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const { data } = await client.post<CodeSubmissionResponse>(
        `/api/v1/code-assignments/${assignment.id}/submit/`,
        { code_content: code },
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
    <div className="rounded-xl border border-violet-200 bg-white overflow-hidden">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50">
            <Terminal size={18} className="text-violet-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800">{assignment.title}</p>
            <p className="text-xs text-gray-400">Python · до {assignment.max_score} баллов</p>
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

      {/* ── Monaco Editor ── */}
      <div className="border-b border-gray-100">
        <Editor
          height="280px"
          language="python"
          theme="vs-dark"
          value={code}
          onChange={(val) => setCode(val ?? '')}
          loading={
            <div className="flex h-[280px] items-center justify-center bg-gray-900">
              <Loader2 size={20} className="animate-spin text-violet-400" />
            </div>
          }
          options={{
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            lineNumbers: 'on',
            folding: true,
            wordWrap: 'on',
            padding: { top: 12, bottom: 12 },
            readOnly: alreadySubmitted,
          }}
        />
      </div>

      {/* ── Submit ── */}
      <div className="flex items-center gap-3 px-5 py-4">
        <button
          onClick={handleSubmit}
          disabled={submitting || alreadySubmitted}
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2.5
                     text-sm font-semibold text-white transition-colors hover:bg-violet-700
                     focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2
                     disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Play size={13} fill="currentColor" />
          )}
          {submitting ? 'Отправка…' : alreadySubmitted ? 'Уже отправлено' : 'Запустить и проверить'}
        </button>
        {submitting && (
          <p className="text-xs text-gray-400">Код отправляется на AI-проверку…</p>
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

      {/* ── Results (hidden while editing) ── */}
      {result && !editing && (
        <div className="space-y-4 border-t border-gray-100 px-5 py-5">
          <ConsoleOutput result={result} maxScore={assignment.max_score} />

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
                  className="inline-flex items-center gap-2 rounded-lg border border-violet-200
                             bg-violet-50 px-4 py-2 text-xs font-semibold text-violet-700
                             transition-colors hover:bg-violet-100"
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
