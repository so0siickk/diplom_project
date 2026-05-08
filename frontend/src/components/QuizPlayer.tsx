import { useEffect, useState } from 'react'
import { AlertCircle, Info, Loader2, RotateCcw, XCircle } from 'lucide-react'
import client from '../api/client'
import type { Quiz, QuizSubmitResponse } from '../api/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Answers = Record<number, number[]>

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function updateAnswer(
  prev: Answers,
  questionId: number,
  optionId: number,
  isMultiple: boolean,
): Answers {
  const current = prev[questionId] ?? []
  if (isMultiple) {
    const next = current.includes(optionId)
      ? current.filter((id) => id !== optionId)
      : [...current, optionId]
    return { ...prev, [questionId]: next }
  }
  return { ...prev, [questionId]: [optionId] }
}

function scoreColor(pct: number): string {
  if (pct >= 80) return 'text-[#deff9a]'
  if (pct >= 50) return 'text-yellow-400'
  return 'text-red-400'
}

function scoreMessage(pct: number): string {
  if (pct >= 90) return 'Отличный результат!'
  if (pct >= 70) return 'Хороший результат!'
  if (pct >= 50) return 'Неплохо, но есть куда расти.'
  return 'Стоит повторить материал урока.'
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface CheckboxIndicatorProps {
  checked: boolean
}

function CheckboxIndicator({ checked }: CheckboxIndicatorProps) {
  return (
    <span
      className={`w-4 h-4 flex-shrink-0 rounded border flex items-center justify-center transition-colors
        ${checked ? 'bg-[#deff9a] border-[#deff9a]' : 'border-gray-600 bg-transparent'}`}
    >
      {checked && (
        <svg
          className="w-2.5 h-2.5 text-[#1a1a1a]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={3}
            d="M5 13l4 4L19 7"
          />
        </svg>
      )}
    </span>
  )
}

interface RadioIndicatorProps {
  checked: boolean
}

function RadioIndicator({ checked }: RadioIndicatorProps) {
  return (
    <span
      className={`w-4 h-4 flex-shrink-0 rounded-full border-2 flex items-center justify-center transition-colors
        ${checked ? 'border-[#deff9a]' : 'border-gray-600'}`}
    >
      {checked && <span className="w-2 h-2 rounded-full bg-[#deff9a]" />}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Result screen
// ---------------------------------------------------------------------------

interface ResultScreenProps {
  result: QuizSubmitResponse
  onRetry: () => void
}

function ResultScreen({ result, onRetry }: ResultScreenProps) {
  const pct = Math.round(result.score_percent)
  const colorClass = scoreColor(pct)
  const message = scoreMessage(pct)
  const passed = result.is_passed

  return (
    <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] overflow-hidden">
      {/* Score area */}
      <div className="px-8 pt-10 pb-6 text-center">
        <div className={`text-7xl font-bold mb-3 tabular-nums ${colorClass}`}>
          {pct}%
        </div>

        {/* Pass / fail pill */}
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold mb-3
            ${passed
              ? 'bg-[#deff9a]/10 border border-[#deff9a]/30 text-[#deff9a]'
              : 'bg-[#ff8a8a]/10 border border-[#ff8a8a]/30 text-[#ff8a8a]'
            }`}
        >
          {passed ? (
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <XCircle className="w-3 h-3" />
          )}
          {passed ? 'Тест пройден' : 'Тест не пройден'}
        </span>

        <p className="text-white text-base font-semibold mb-1">Ваш результат</p>
        <p className="text-gray-400 text-sm mb-1">
          {result.correct_answers} из {result.total_questions} верных ответов
        </p>
        <p className={`text-sm font-medium ${colorClass}`}>{message}</p>
      </div>

      {/* Warning / info banners */}
      <div className="px-6 pb-6 space-y-3">
        {/* Failed warning */}
        {!passed && (
          <div className="flex items-start gap-3 rounded-xl bg-[#ff8a8a]/8 border border-[#ff8a8a]/20 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-[#ff8a8a] flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-[#ff8a8a]">
                Тест не пройден (менее 50%)
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                Для успешного завершения урока необходимо набрать не менее 50%.
              </p>
            </div>
          </div>
        )}

        {/* Needs review */}
        {result.needs_review && (
          <div className="flex items-start gap-3 rounded-xl bg-yellow-400/[0.06] border border-yellow-400/20 px-4 py-3">
            <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-yellow-300">
              Рекомендуем повторить материал урока перед следующей попыткой.
            </p>
          </div>
        )}

        {/* Recommended action */}
        {result.recommended_action && (
          <div className="flex items-start gap-3 rounded-xl bg-[#deff9a]/[0.05] border border-[#deff9a]/20 px-4 py-3">
            <Info className="w-4 h-4 text-[#deff9a] flex-shrink-0 mt-0.5" />
            <p className="text-sm text-gray-300">
              <span className="font-medium text-[#deff9a]">Рекомендация: </span>
              {result.recommended_action}
            </p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-6 pb-8 text-center">
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-xl border border-[#2e2e2e]
                     bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white
                     hover:border-[#deff9a]/40 hover:text-[#deff9a] transition-all duration-150"
        >
          <RotateCcw className="w-4 h-4" />
          Пройти ещё раз
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface Props {
  quizId: number
  onComplete?: (result: QuizSubmitResponse) => void
}

export default function QuizPlayer({ quizId, onComplete }: Props) {
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [answers, setAnswers] = useState<Answers>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [result, setResult] = useState<QuizSubmitResponse | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    client
      .get<Quiz>(`/api/v1/quizzes/${quizId}/`)
      .then(({ data }) => setQuiz(data))
      .catch(() => setError('Не удалось загрузить тест.'))
      .finally(() => setLoading(false))
  }, [quizId])

  const handleAnswerChange = (
    questionId: number,
    optionId: number,
    isMultiple: boolean,
  ) => {
    setAnswers((prev) => updateAnswer(prev, questionId, optionId, isMultiple))
  }

  const handleSubmit = async () => {
    if (!quiz || submitting) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const { data } = await client.post<QuizSubmitResponse>(
        `/api/quizzes/${quizId}/submit/`,
        { answers },
      )
      setResult(data)
      onComplete?.(data)
    } catch {
      setSubmitError('Ошибка при отправке теста. Попробуйте ещё раз.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleRetry = () => {
    setResult(null)
    setAnswers({})
    setSubmitError(null)
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-6 flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-[#deff9a] animate-spin flex-shrink-0" />
        <span className="text-sm text-gray-400">Загрузка теста...</span>
      </div>
    )
  }

  // ---------- Fetch error ----------
  if (error || !quiz) {
    return (
      <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-6 flex items-center gap-3 text-red-400">
        <AlertCircle className="w-5 h-5 flex-shrink-0" />
        <span className="text-sm">{error ?? 'Тест не найден.'}</span>
      </div>
    )
  }

  // ---------- Result screen ----------
  if (result) {
    return <ResultScreen result={result} onRetry={handleRetry} />
  }

  // ---------- Quiz ----------
  const questions = [...quiz.questions].sort((a, b) => a.order - b.order)

  const answeredCount = questions.filter(
    (q) => (answers[q.id] ?? []).length > 0,
  ).length
  const allAnswered = answeredCount === questions.length

  return (
    <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#2e2e2e]">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-sm font-semibold text-white">{quiz.title}</h3>
          <span className="text-xs text-gray-500 flex-shrink-0">
            {answeredCount} / {questions.length} отвечено
          </span>
        </div>
        {quiz.description && (
          <p className="text-xs text-gray-400 mt-1">{quiz.description}</p>
        )}
        {/* Progress bar */}
        <div className="mt-3 h-0.5 bg-[#2e2e2e] rounded-full overflow-hidden">
          <div
            className="h-full bg-[#deff9a] rounded-full transition-all duration-300"
            style={{
              width: `${(answeredCount / questions.length) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Questions */}
      <div className="divide-y divide-[#2e2e2e]">
        {questions.map((q, idx) => {
          const selectedIds = answers[q.id] ?? []
          const isAnswered = selectedIds.length > 0

          return (
            <div key={q.id} className="px-6 py-5">
              {/* Question row */}
              <div className="flex items-start gap-3 mb-4">
                <span
                  className={`mt-0.5 w-6 h-6 flex-shrink-0 rounded-full flex items-center
                    justify-center text-xs font-semibold transition-colors
                    ${isAnswered
                      ? 'bg-[#deff9a] text-[#1a1a1a]'
                      : 'bg-[#2a2a2a] text-gray-500'
                    }`}
                >
                  {idx + 1}
                </span>
                <div>
                  <p className="text-sm font-medium text-white leading-relaxed">
                    {q.text}
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    {q.is_multiple_choice
                      ? 'Несколько верных ответов'
                      : 'Один верный ответ'}
                  </p>
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2 ml-9">
                {q.options.map((opt) => {
                  const selected = selectedIds.includes(opt.id)
                  return (
                    <label
                      key={opt.id}
                      className={`flex items-center gap-3 rounded-xl border px-4 py-3
                                  cursor-pointer select-none transition-all duration-150
                                  ${
                                    selected
                                      ? 'border-[#deff9a]/40 bg-[#deff9a]/[0.06]'
                                      : 'border-[#2e2e2e] bg-[#1a1a1a] hover:border-[#3a3a3a] hover:bg-[#222]'
                                  }`}
                    >
                      <input
                        type={q.is_multiple_choice ? 'checkbox' : 'radio'}
                        name={`question-${q.id}`}
                        value={opt.id}
                        checked={selected}
                        onChange={() =>
                          handleAnswerChange(q.id, opt.id, q.is_multiple_choice)
                        }
                        className="sr-only"
                      />
                      {q.is_multiple_choice ? (
                        <CheckboxIndicator checked={selected} />
                      ) : (
                        <RadioIndicator checked={selected} />
                      )}
                      <span
                        className={`text-sm ${
                          selected ? 'text-white font-medium' : 'text-gray-300'
                        }`}
                      >
                        {opt.text}
                      </span>
                    </label>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-[#2e2e2e] flex items-center gap-4">
        {/* Status hint */}
        <div className="flex-1">
          {submitError ? (
            <div className="flex items-center gap-2 text-red-400 text-xs">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              <span>{submitError}</span>
            </div>
          ) : allAnswered ? (
            <p className="text-xs text-[#deff9a]">Все вопросы отвечены</p>
          ) : (
            <p className="text-xs text-gray-600">
              Осталось: {questions.length - answeredCount}
            </p>
          )}
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={submitting || !allAnswered}
          className={`rounded-xl px-6 py-2.5 text-sm font-semibold transition-all duration-150
            ${
              allAnswered && !submitting
                ? 'bg-[#deff9a] text-[#1a1a1a] hover:bg-[#cbf082] hover:shadow-[0_0_24px_rgba(222,255,154,0.18)]'
                : 'bg-[#2a2a2a] text-gray-600 cursor-not-allowed'
            }`}
        >
          {submitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Отправка...
            </span>
          ) : (
            'Завершить тест'
          )}
        </button>
      </div>
    </div>
  )
}
