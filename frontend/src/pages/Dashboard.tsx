/**
 * src/pages/Dashboard.tsx
 * ========================
 * Main page shown after login.
 *
 * Layout:
 *   [Header] — app title + logout button
 *   [Courses list] — cards fetched from GET /api/v1/courses/
 *   [Recommendations panel] — ML recs for the selected course
 *                             fetched from GET /analytics/api/recommendations/<id>/
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import type { Course, RecommendationItem, RecommendationsResponse } from '../api/types'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Header({ onLogout }: { onLogout: () => void }) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <span className="text-lg font-bold text-indigo-700">LMS Adaptive</span>
      <button
        onClick={onLogout}
        className="text-sm text-gray-500 hover:text-gray-800 transition-colors"
      >
        Log out
      </button>
    </header>
  )
}

function CourseCard({
  course,
  selected,
  onClick,
}: {
  course: Course
  selected: boolean
  onClick: () => void
}) {
  const lessonCount = course.modules.reduce((sum, m) => sum + m.lessons.length, 0)

  return (
    <div
      className={`rounded-xl border p-4 transition-all
        ${selected
          ? 'border-indigo-500 bg-indigo-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-indigo-300 hover:shadow-sm'
        }`}
    >
      <button onClick={onClick} className="w-full text-left">
        <h3 className="font-semibold text-gray-800 text-sm">{course.title}</h3>
        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{course.description}</p>
        <div className="mt-3 flex items-center gap-3 text-xs text-gray-400">
          <span>{course.modules.length} module{course.modules.length !== 1 ? 's' : ''}</span>
          <span>·</span>
          <span>{lessonCount} lesson{lessonCount !== 1 ? 's' : ''}</span>
        </div>
      </button>
      <div className="mt-3 pt-3 border-t border-gray-100">
        <Link
          to={`/course/${course.id}`}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          Open course →
        </Link>
      </div>
    </div>
  )
}

function RecommendationRow({ item, rank }: { item: RecommendationItem; rank: number }) {
  const riskColor =
    item.risk_score >= 0.7
      ? 'text-red-600 bg-red-50'
      : item.risk_score >= 0.4
      ? 'text-yellow-600 bg-yellow-50'
      : 'text-green-600 bg-green-50'

  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700
                       text-xs font-bold flex items-center justify-center">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{item.lesson_title}</p>
        <p className="text-xs text-gray-400">{item.module_title}</p>
      </div>
      <div className="flex-shrink-0 text-right">
        <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${riskColor}`}>
          risk {Math.round(item.risk_score * 100)}%
        </span>
        <p className="text-xs text-gray-400 mt-0.5">
          completion {Math.round(item.completion_prob * 100)}%
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const logout = useAuthStore((s) => s.logout)

  // Courses
  const [courses, setCourses] = useState<Course[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesError, setCoursesError] = useState<string | null>(null)

  // Selected course for recommendations
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null)

  // Recommendations
  const [recs, setRecs] = useState<RecommendationItem[]>([])
  const [recsLoading, setRecsLoading] = useState(false)
  const [recsError, setRecsError] = useState<string | null>(null)
  const [modelLoaded, setModelLoaded] = useState<boolean | null>(null)

  // Fetch course list on mount
  useEffect(() => {
    let cancelled = false
    setCoursesLoading(true)
    client
      .get<Course[]>('/api/v1/courses/')
      .then(({ data }) => {
        if (cancelled) return
        setCourses(data)
        if (data.length > 0) setSelectedCourseId(data[0].id)
      })
      .catch(() => {
        if (!cancelled) setCoursesError('Failed to load courses.')
      })
      .finally(() => {
        if (!cancelled) setCoursesLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // Fetch recommendations when selected course changes
  useEffect(() => {
    if (selectedCourseId === null) return
    let cancelled = false
    setRecsLoading(true)
    setRecsError(null)
    client
      .get<RecommendationsResponse>(`/analytics/api/recommendations/${selectedCourseId}/`)
      .then(({ data }) => {
        if (cancelled) return
        setRecs(data.recommendations)
        setModelLoaded(data.model_loaded)
      })
      .catch(() => {
        if (!cancelled) setRecsError('Failed to load recommendations.')
      })
      .finally(() => {
        if (!cancelled) setRecsLoading(false)
      })
    return () => { cancelled = true }
  }, [selectedCourseId])

  const selectedCourse = courses.find((c) => c.id === selectedCourseId) ?? null

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header onLogout={logout} />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* ---- Courses panel ---- */}
        <section>
          <h2 className="text-base font-semibold text-gray-700 mb-3">My Courses</h2>

          {coursesLoading && (
            <p className="text-sm text-gray-400">Loading courses...</p>
          )}

          {coursesError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {coursesError}
            </div>
          )}

          {!coursesLoading && !coursesError && courses.length === 0 && (
            <p className="text-sm text-gray-400">No courses found.</p>
          )}

          <div className="space-y-3">
            {courses.map((course) => (
              <CourseCard
                key={course.id}
                course={course}
                selected={course.id === selectedCourseId}
                onClick={() => setSelectedCourseId(course.id)}
              />
            ))}
          </div>
        </section>

        {/* ---- Recommendations panel ---- */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">
              Smart Recommendations
            </h2>
            {modelLoaded === false && (
              <span className="text-xs text-yellow-600 bg-yellow-50 border border-yellow-200
                               rounded-full px-2 py-0.5">
                ML model not loaded
              </span>
            )}
          </div>

          {selectedCourse && (
            <p className="text-xs text-gray-400 mb-3">
              For: <span className="font-medium text-gray-600">{selectedCourse.title}</span>
            </p>
          )}

          <div className="bg-white rounded-xl border border-gray-200 px-4 py-2 min-h-[200px]">
            {recsLoading && (
              <p className="text-sm text-gray-400 py-6 text-center">Loading recommendations...</p>
            )}

            {recsError && (
              <p className="text-sm text-red-500 py-6 text-center">{recsError}</p>
            )}

            {!recsLoading && !recsError && recs.length === 0 && selectedCourseId !== null && (
              <p className="text-sm text-gray-400 py-6 text-center">
                No problem topics! Keep up the good work.
              </p>
            )}

            {!recsLoading && !recsError && recs.map((item, i) => (
              <RecommendationRow key={item.lesson_id} item={item} rank={i + 1} />
            ))}

            {selectedCourseId === null && !coursesLoading && (
              <p className="text-sm text-gray-400 py-6 text-center">
                Select a course to see recommendations.
              </p>
            )}
          </div>

          {!recsLoading && recs.length > 0 && (
            <p className="text-xs text-gray-400 mt-2">
              Lessons are ranked by predicted difficulty (highest risk first).
            </p>
          )}
        </section>

      </main>
    </div>
  )
}
