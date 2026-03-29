/**
 * src/pages/ProfilePage.tsx
 * ==========================
 * Personal profile: stats card + placeholder achievements.
 * Route: /profile
 */

import { useEffect, useState } from 'react'
import { BookCheck, Star, LibraryBig, TrendingUp } from 'lucide-react'
import client from '../api/client'

interface ProfileData {
  username: string
  role: string
  lessons_completed: number
  lessons_started: number
  avg_score: number | null
  courses_enrolled: number
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
  color: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 flex items-start gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Placeholder achievements
// ---------------------------------------------------------------------------

const ACHIEVEMENTS = [
  { emoji: '🎯', label: 'First lesson', desc: 'Completed your first lesson' },
  { emoji: '🔥', label: '3-day streak',  desc: 'Studied 3 days in a row' },
  { emoji: '📚', label: 'Bookworm',      desc: 'Read 10+ lessons' },
]

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  const [data, setData] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get<ProfileData>('/analytics/api/profile/')
      .then(({ data }) => setData(data))
      .finally(() => setLoading(false))
  }, [])

  const completionRate = data && data.lessons_started > 0
    ? Math.round((data.lessons_completed / data.lessons_started) * 100)
    : 0

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">

      {/* Profile header */}
      <div className="flex items-center gap-5 mb-8">
        <div className="w-16 h-16 rounded-2xl bg-indigo-600 flex items-center justify-center flex-shrink-0">
          <span className="text-2xl font-bold text-white">
            {data?.username?.charAt(0).toUpperCase() ?? '?'}
          </span>
        </div>
        <div>
          {loading ? (
            <div className="h-6 w-32 bg-gray-200 rounded animate-pulse" />
          ) : (
            <>
              <h1 className="text-xl font-bold text-gray-900">{data?.username}</h1>
              <span className={`
                inline-block mt-1 text-xs font-medium px-2.5 py-0.5 rounded-full
                ${data?.role === 'teacher'
                  ? 'bg-purple-100 text-purple-700'
                  : 'bg-indigo-100 text-indigo-700'
                }
              `}>
                {data?.role === 'teacher' ? 'Instructor' : 'Student'}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Stats grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-200 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          <StatCard
            icon={<BookCheck size={20} className="text-indigo-600" />}
            label="Lessons completed"
            value={data?.lessons_completed ?? 0}
            sub={`of ${data?.lessons_started ?? 0} started`}
            color="bg-indigo-50"
          />
          <StatCard
            icon={<Star size={20} className="text-amber-500" />}
            label="Average score"
            value={data?.avg_score != null ? `${Math.round(data.avg_score * 100)}%` : '—'}
            sub="across all quizzes"
            color="bg-amber-50"
          />
          <StatCard
            icon={<LibraryBig size={20} className="text-emerald-600" />}
            label="Courses enrolled"
            value={data?.courses_enrolled ?? 0}
            color="bg-emerald-50"
          />
          <StatCard
            icon={<TrendingUp size={20} className="text-sky-600" />}
            label="Completion rate"
            value={`${completionRate}%`}
            sub="lessons completed / started"
            color="bg-sky-50"
          />
        </div>
      )}

      {/* Progress bar */}
      {!loading && data && data.lessons_started > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5 mb-8">
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium text-gray-700">Overall progress</span>
            <span className="text-gray-400">{completionRate}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2">
            <div
              className="bg-indigo-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${completionRate}%` }}
            />
          </div>
        </div>
      )}

      {/* Achievements (placeholder) */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Achievements
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {ACHIEVEMENTS.map((a) => (
            <div
              key={a.label}
              className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3"
            >
              <span className="text-2xl">{a.emoji}</span>
              <div>
                <p className="text-sm font-semibold text-gray-800">{a.label}</p>
                <p className="text-xs text-gray-400">{a.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
