/**
 * src/pages/InstructorDashboard.tsx
 * ===================================
 * Teacher view: per-student progress table with ML risk indicators.
 * Route: /instructor  (teacher/staff only)
 */

import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  MinusCircle,
  Users,
  BookOpen,
  TrendingDown,
} from 'lucide-react'
import client from '../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StudentStat {
  user_id: number
  username: string
  lessons_completed: number
  avg_score: number | null
  highest_risk_lesson: string | null
  risk_score: number | null
}

// ---------------------------------------------------------------------------
// Risk helpers
// ---------------------------------------------------------------------------

type RiskLevel = 'high' | 'medium' | 'low' | 'none'

function getRiskLevel(score: number | null): RiskLevel {
  if (score === null) return 'none'
  if (score >= 0.7)  return 'high'
  if (score >= 0.4)  return 'medium'
  return 'low'
}

const RISK_CONFIG: Record<RiskLevel, {
  label: string
  badge: string
  icon: React.ReactNode
}> = {
  high: {
    label: 'Высокий',
    badge: 'bg-red-100 text-red-700 border-red-200',
    icon: <AlertTriangle size={13} className="text-red-500" />,
  },
  medium: {
    label: 'Средний',
    badge: 'bg-amber-100 text-amber-700 border-amber-200',
    icon: <MinusCircle size={13} className="text-amber-500" />,
  },
  low: {
    label: 'Низкий',
    badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    icon: <CheckCircle2 size={13} className="text-emerald-500" />,
  },
  none: {
    label: '—',
    badge: 'bg-gray-100 text-gray-400 border-gray-200',
    icon: null,
  },
}

function RiskBadge({ score }: { score: number | null }) {
  const level = getRiskLevel(score)
  const cfg   = RISK_CONFIG[level]
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium ${cfg.badge}`}>
      {cfg.icon}
      {cfg.label}
      {score !== null && ` · ${Math.round(score * 100)}%`}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Score pill
// ---------------------------------------------------------------------------

function ScorePill({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-300 text-sm">—</span>
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? 'text-emerald-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  return <span className={`text-sm font-semibold ${color}`}>{pct}%</span>
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-4">
        <Users size={28} className="text-indigo-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-700 mb-1">Студентов пока нет</h3>
      <p className="text-sm text-gray-400 max-w-xs">
        Как только студенты запишутся и начнут проходить уроки, здесь появится их прогресс и оценки рисков.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Summary cards
// ---------------------------------------------------------------------------

function SummaryCards({ students }: { students: StudentStat[] }) {
  const total       = students.length
  const highRisk    = students.filter((s) => getRiskLevel(s.risk_score) === 'high').length
  const avgLessons  = total > 0
    ? Math.round(students.reduce((s, r) => s + r.lessons_completed, 0) / total)
    : 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      {[
        { icon: <Users size={18} className="text-indigo-600" />, label: 'Всего студентов', value: total,        bg: 'bg-indigo-50' },
        { icon: <TrendingDown size={18} className="text-red-500" />, label: 'Высокий риск',   value: highRisk,    bg: 'bg-red-50' },
        { icon: <BookOpen size={18} className="text-emerald-600" />, label: 'Среднее кол-во уроков', value: avgLessons, bg: 'bg-emerald-50' },
      ].map((card) => (
        <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${card.bg}`}>
            {card.icon}
          </div>
          <div>
            <p className="text-xs text-gray-400">{card.label}</p>
            <p className="text-xl font-bold text-gray-900">{card.value}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function InstructorDashboard() {
  const [students, setStudents] = useState<StudentStat[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState<string | null>(null)
  const [sortKey,  setSortKey]  = useState<'risk_score' | 'lessons_completed' | 'avg_score'>('risk_score')

  useEffect(() => {
    client.get<StudentStat[]>('/analytics/api/students-stats/')
      .then(({ data }) => setStudents(data))
      .catch(() => setError('Не удалось загрузить данные студентов.'))
      .finally(() => setLoading(false))
  }, [])

  const sorted = [...students].sort((a, b) => {
    if (sortKey === 'risk_score') {
      return (b.risk_score ?? -1) - (a.risk_score ?? -1)
    }
    if (sortKey === 'lessons_completed') {
      return b.lessons_completed - a.lessons_completed
    }
    // avg_score
    return (b.avg_score ?? -1) - (a.avg_score ?? -1)
  })

  const SortBtn = ({ k, label }: { k: typeof sortKey; label: string }) => (
    <button
      onClick={() => setSortKey(k)}
      className={`text-xs px-2 py-1 rounded-lg border transition-colors ${
        sortKey === k
          ? 'bg-indigo-600 text-white border-indigo-600'
          : 'bg-white text-gray-500 border-gray-200 hover:border-indigo-300'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">Панель управления инструктора</h1>
        <p className="text-sm text-gray-400 mt-0.5">
          Оценки рисков на базе ML помогают выявить студентов, которым требуется внимание.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-6">
          {error}
        </div>
      )}

      {/* Summary */}
      {!loading && students.length > 0 && <SummaryCards students={students} />}

      {/* Sort controls */}
      {!loading && students.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-gray-400 mr-1">Сортировать по:</span>
          <SortBtn k="risk_score"        label="Риску ↓" />
          <SortBtn k="lessons_completed" label="Урокам ↓" />
          <SortBtn k="avg_score"         label="Баллам ↓" />
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex gap-4 px-6 py-4 border-b border-gray-100 last:border-0">
              <div className="w-8 h-8 rounded-full bg-gray-200 animate-pulse flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-3 w-32 bg-gray-200 rounded animate-pulse" />
                <div className="h-3 w-48 bg-gray-100 rounded animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      ) : students.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-200">
          <EmptyState />
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          {/* Table head */}
          <div className="grid grid-cols-[2fr_1fr_1fr_3fr_1fr] gap-4 px-6 py-3
                          bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-500 uppercase tracking-wide">
            <span>Студент</span>
            <span>Прогресс</span>
            <span>Средний балл</span>
            <span>Тема под риском</span>
            <span>Уровень риска</span>
          </div>

          {/* Table rows */}
          {sorted.map((s) => (
            <div
              key={s.user_id}
              onClick={() => console.log('student id:', s.user_id)}
              className="grid grid-cols-[2fr_1fr_1fr_3fr_1fr] gap-4 px-6 py-4
                         border-b border-gray-100 last:border-0 items-center
                         hover:bg-gray-50 cursor-pointer transition-colors group"
            >
              {/* Student */}
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold text-indigo-600">
                    {s.username.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="text-sm font-medium text-gray-800 group-hover:text-indigo-700 transition-colors">
                  {s.username}
                </span>
              </div>

              {/* Progress */}
              <div className="flex items-center gap-1.5">
                <BookOpen size={13} className="text-gray-300 flex-shrink-0" />
                <span className="text-sm text-gray-700">{s.lessons_completed}</span>
              </div>

              {/* Avg score */}
              <ScorePill score={s.avg_score} />

              {/* Topic at risk */}
              <span className="text-sm text-gray-500 truncate">
                {s.highest_risk_lesson ?? (
                  <span className="text-gray-300 italic">Нет ожидаемых уроков</span>
                )}
              </span>

              {/* Risk badge */}
              <RiskBadge score={s.risk_score} />
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-300 mt-3">
        Оценка риска = 1 − P(completion), предсказанная ML-моделью. Обновляется при каждом запросе рекомендации.
      </p>
    </div>
  )
}
