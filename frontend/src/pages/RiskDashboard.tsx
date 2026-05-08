import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Search,
  Users,
} from 'lucide-react'
import client from '../api/client'
import type { RiskLevel, StudentStat } from '../api/types'

// ---------------------------------------------------------------------------
// Risk helpers
// ---------------------------------------------------------------------------

function getRiskLevel(score: number | null): RiskLevel {
  if (score === null) return 'unknown'
  if (score >= 0.60) return 'red'
  if (score >= 0.30) return 'yellow'
  return 'green'
}

const RISK_CFG = {
  red: {
    label: 'Высокий риск',
    labelShort: 'Высокий',
    bg: 'bg-[#ff8a8a]/10',
    border: 'border-[#ff8a8a]/30',
    text: 'text-[#ff8a8a]',
    dot: 'bg-[#ff8a8a]',
    rowTint: 'bg-[#ff8a8a]/[0.025]',
    filterBg: 'bg-[#ff8a8a]/15 border-[#ff8a8a]/40 text-[#ff8a8a]',
  },
  yellow: {
    label: 'Средний риск',
    labelShort: 'Средний',
    bg: 'bg-yellow-400/10',
    border: 'border-yellow-400/30',
    text: 'text-yellow-400',
    dot: 'bg-yellow-400',
    rowTint: 'bg-yellow-400/[0.02]',
    filterBg: 'bg-yellow-400/15 border-yellow-400/40 text-yellow-400',
  },
  green: {
    label: 'Низкий риск',
    labelShort: 'Низкий',
    bg: 'bg-[#deff9a]/10',
    border: 'border-[#deff9a]/30',
    text: 'text-[#deff9a]',
    dot: 'bg-[#deff9a]',
    rowTint: '',
    filterBg: 'bg-[#deff9a]/15 border-[#deff9a]/40 text-[#deff9a]',
  },
  unknown: {
    label: 'Нет данных',
    labelShort: 'Нет данных',
    bg: 'bg-gray-600/10',
    border: 'border-gray-600/30',
    text: 'text-gray-500',
    dot: 'bg-gray-600',
    rowTint: '',
    filterBg: 'bg-gray-600/15 border-gray-600/40 text-gray-500',
  },
} as const

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RiskBadge({ level }: { level: RiskLevel }) {
  const cfg = RISK_CFG[level]
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold
                  border ${cfg.bg} ${cfg.border} ${cfg.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.labelShort}
    </span>
  )
}

interface StatCardProps {
  label: string
  value: number
  level?: RiskLevel
}

function StatCard({ label, value, level }: StatCardProps) {
  const colorClass = level ? RISK_CFG[level].text : 'text-white'
  return (
    <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] px-5 py-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${colorClass}`}>{value}</p>
    </div>
  )
}

type FilterOption = RiskLevel | 'all'

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function RiskDashboard() {
  const [students, setStudents] = useState<StudentStat[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<FilterOption>('all')

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const { data } = await client.get<StudentStat[]>('/analytics/api/students-stats/')
      // Sort by risk (highest first) by default
      const sorted = [...data].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1))
      setStudents(sorted)
      setLastUpdated(new Date())
    } catch {
      setError('Не удалось загрузить данные аналитики.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // --------------- Derived stats ---------------
  const summary = useMemo(() => ({
    total: students.length,
    red: students.filter((s) => getRiskLevel(s.risk_score) === 'red').length,
    yellow: students.filter((s) => getRiskLevel(s.risk_score) === 'yellow').length,
    green: students.filter((s) => getRiskLevel(s.risk_score) === 'green').length,
  }), [students])

  // --------------- Filtered list ---------------
  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    return students.filter((s) => {
      const matchLevel = filter === 'all' || getRiskLevel(s.risk_score) === filter
      const matchSearch =
        !q ||
        s.username.toLowerCase().includes(q) ||
        (s.highest_risk_lesson?.toLowerCase().includes(q) ?? false)
      return matchLevel && matchSearch
    })
  }, [students, search, filter])

  // --------------- Loading ---------------
  if (loading) {
    return (
      <div className="min-h-screen bg-[#1a1a1a] flex items-center justify-center gap-3">
        <Loader2 className="w-5 h-5 text-[#deff9a] animate-spin" />
        <span className="text-sm text-gray-400">Загрузка данных аналитики...</span>
      </div>
    )
  }

  // --------------- Error ---------------
  if (error) {
    return (
      <div className="min-h-screen bg-[#1a1a1a] flex items-center justify-center">
        <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-8 text-center max-w-sm">
          <AlertTriangle className="w-8 h-8 text-[#ff8a8a] mx-auto mb-3" />
          <p className="text-sm text-gray-300 mb-4">{error}</p>
          <button
            onClick={() => fetchData()}
            className="rounded-xl bg-[#2a2a2a] border border-[#3a3a3a] px-4 py-2 text-sm
                       text-white hover:border-[#deff9a]/40 transition-colors"
          >
            Попробовать снова
          </button>
        </div>
      </div>
    )
  }

  // --------------- Main ---------------
  return (
    <div className="min-h-screen bg-[#1a1a1a] px-6 py-8">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ---- Page header ---- */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white">Аналитика студентов</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Мониторинг успеваемости и рисков академической неуспеваемости
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {lastUpdated && (
              <span className="text-xs text-gray-600 hidden sm:block">
                Обновлено: {lastUpdated.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="flex items-center gap-2 rounded-xl border border-[#2e2e2e] bg-[#202020]
                         px-3 py-2 text-sm text-gray-400 hover:text-[#deff9a] hover:border-[#deff9a]/30
                         transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              <span className="hidden sm:block">Обновить</span>
            </button>
          </div>
        </div>

        {/* ---- Summary cards ---- */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Всего студентов" value={summary.total} />
          <StatCard label="Высокий риск" value={summary.red} level="red" />
          <StatCard label="Средний риск" value={summary.yellow} level="yellow" />
          <StatCard label="Низкий риск" value={summary.green} level="green" />
        </div>

        {/* ---- Filter + search ---- */}
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по имени или проблемной теме..."
              className="w-full rounded-xl border border-[#2e2e2e] bg-[#202020] pl-9 pr-4 py-2.5
                         text-sm text-white placeholder-gray-600
                         focus:outline-none focus:border-[#deff9a]/40 transition-colors"
            />
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1.5">
            {(['all', 'red', 'yellow', 'green'] as FilterOption[]).map((opt) => {
              const active = filter === opt
              const cfg = opt !== 'all' ? RISK_CFG[opt] : null
              return (
                <button
                  key={opt}
                  onClick={() => setFilter(opt)}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-all
                    ${active
                      ? cfg
                        ? cfg.filterBg
                        : 'bg-white/10 border-white/20 text-white'
                      : 'border-[#2e2e2e] bg-[#202020] text-gray-500 hover:text-gray-300 hover:border-[#3a3a3a]'
                    }`}
                >
                  {opt === 'all' ? 'Все' : RISK_CFG[opt].labelShort}
                </button>
              )
            })}
          </div>
        </div>

        {/* ---- Table ---- */}
        {filtered.length === 0 ? (
          <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] py-16 text-center">
            <Users className="w-8 h-8 text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500">
              {search || filter !== 'all'
                ? 'Ни один студент не соответствует фильтру.'
                : 'Студентов пока нет.'}
            </p>
          </div>
        ) : (
          <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_90px_90px_1fr_140px] gap-4 px-5 py-3
                            border-b border-[#2e2e2e] bg-[#1e1e1e]">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Студент</span>
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Ср. балл</span>
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Уроков</span>
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Проблемная тема</span>
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide text-right">Риск</span>
            </div>

            {/* Table rows */}
            <div className="divide-y divide-[#2e2e2e]">
              {filtered.map((student) => {
                const level = getRiskLevel(student.risk_score)
                const cfg = RISK_CFG[level]
                const avgPct =
                  student.avg_score !== null
                    ? `${Math.round(student.avg_score * 100)}%`
                    : '—'

                return (
                  <div
                    key={student.user_id}
                    className={`grid grid-cols-[1fr_90px_90px_1fr_140px] gap-4 px-5 py-3.5
                                items-center hover:bg-[#222] transition-colors ${cfg.rowTint}`}
                  >
                    {/* Student */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center
                                    text-xs font-bold ${cfg.bg} ${cfg.text} border ${cfg.border}`}
                      >
                        {student.username.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm font-medium text-white truncate">
                        {student.username}
                      </span>
                    </div>

                    {/* Avg score */}
                    <div className="text-right">
                      <span
                        className={`text-sm font-semibold tabular-nums
                          ${student.avg_score === null
                            ? 'text-gray-600'
                            : student.avg_score >= 0.7
                            ? 'text-[#deff9a]'
                            : student.avg_score >= 0.5
                            ? 'text-yellow-400'
                            : 'text-[#ff8a8a]'
                          }`}
                      >
                        {avgPct}
                      </span>
                    </div>

                    {/* Lessons completed */}
                    <div className="text-right">
                      <span className="text-sm text-white tabular-nums">
                        {student.lessons_completed}
                      </span>
                    </div>

                    {/* Problem area */}
                    <div className="min-w-0">
                      {student.highest_risk_lesson ? (
                        <span
                          className={`text-xs ${cfg.text} truncate block`}
                          title={student.highest_risk_lesson}
                        >
                          {student.highest_risk_lesson}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-600">—</span>
                      )}
                    </div>

                    {/* Risk badge */}
                    <div className="flex justify-end">
                      <RiskBadge level={level} />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Footer: count */}
            <div className="px-5 py-3 border-t border-[#2e2e2e] bg-[#1e1e1e]">
              <p className="text-xs text-gray-600">
                Показано: {filtered.length} из {students.length}
              </p>
            </div>
          </div>
        )}

        {/* ---- Legend ---- */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-600 pb-4">
          <span>Порог риска:</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#deff9a]" />
            Низкий (score &lt; 0.30)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-yellow-400" />
            Средний (0.30 – 0.60)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#ff8a8a]" />
            Высокий (&ge; 0.60)
          </span>
        </div>
      </div>
    </div>
  )
}
