/**
 * src/pages/Dashboard.tsx
 * ========================
 * Student home page.
 *
 * Layout:
 *   [My Learning]  — enrolled courses (selector) + ML recommendations panel
 *   [Explore]      — non-enrolled courses with "Enroll" CTA
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, Layers, Loader2, Plus, Sparkles } from 'lucide-react'
import client from '../api/client'
import type { Course, RecommendationItem, RecommendationsResponse } from '../api/types'

// ---------------------------------------------------------------------------
// Sub-components — My Learning panel
// ---------------------------------------------------------------------------

function EnrolledCourseCard({
  course,
  selected,
  onClick,
}: {
  course: Course
  selected: boolean
  onClick: () => void
}) {
  const lessonCount = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div
      className={`rounded-xl border p-4 transition-all cursor-pointer ${
        selected
          ? 'border-indigo-500 bg-indigo-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-indigo-300 hover:shadow-sm'
      }`}
      onClick={onClick}
    >
      <h3 className="font-semibold text-gray-800 text-sm">{course.title}</h3>
      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{course.description}</p>
      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <span>{course.modules.length} module{course.modules.length !== 1 ? 's' : ''}</span>
          <span>·</span>
          <span>{lessonCount} lesson{lessonCount !== 1 ? 's' : ''}</span>
        </div>
        <Link
          to={`/course/${course.id}`}
          onClick={(e) => e.stopPropagation()}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          Open →
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
// Sub-components — Catalog panel
// ---------------------------------------------------------------------------

function CatalogCard({
  course,
  enrolling,
  onEnroll,
}: {
  course: Course
  enrolling: boolean
  onEnroll: () => void
}) {
  const lessonCount = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-3
                    hover:border-gray-300 transition-colors">
      <div>
        <h3 className="font-semibold text-gray-800 text-sm">{course.title}</h3>
        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{course.description}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Layers size={11} />
            {course.modules.length} module{course.modules.length !== 1 ? 's' : ''}
          </span>
          <span>·</span>
          <span className="flex items-center gap-1">
            <BookOpen size={11} />
            {lessonCount} lesson{lessonCount !== 1 ? 's' : ''}
          </span>
        </div>
        <p className="text-xs text-gray-400 mt-1">by {course.owner}</p>
      </div>
      <div className="pt-2 border-t border-gray-100">
        <button
          onClick={onEnroll}
          disabled={enrolling}
          className="w-full flex items-center justify-center gap-2 py-2 px-3
                     bg-indigo-600 text-white text-xs font-medium rounded-lg
                     hover:bg-indigo-700 transition-colors disabled:opacity-60"
        >
          {enrolling ? (
            <>
              <Loader2 size={12} className="animate-spin" />
              Enrolling…
            </>
          ) : (
            <>
              <Plus size={12} />
              Enroll for free
            </>
          )}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

function NoEnrollmentsPrompt() {
  return (
    <div className="rounded-xl border border-dashed border-gray-200 p-8 text-center">
      <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center mx-auto mb-3">
        <BookOpen size={22} className="text-indigo-400" />
      </div>
      <p className="text-sm font-medium text-gray-600 mb-1">No courses yet</p>
      <p className="text-xs text-gray-400">Enroll in a course from the catalog below to get started.</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const [courses, setCourses] = useState<Course[]>([])
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesError, setCoursesError] = useState<string | null>(null)

  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null)

  // Recommendations
  const [recs, setRecs] = useState<RecommendationItem[]>([])
  const [recsLoading, setRecsLoading] = useState(false)
  const [recsError, setRecsError] = useState<string | null>(null)
  const [modelLoaded, setModelLoaded] = useState<boolean | null>(null)

  // Per-course enrolling state (keyed by course id)
  const [enrollingId, setEnrollingId] = useState<number | null>(null)

  // Derived splits
  const enrolledCourses = courses.filter((c) => c.is_enrolled)
  const catalogCourses = courses.filter((c) => !c.is_enrolled)

  // ---- Fetch courses ----
  useEffect(() => {
    let cancelled = false
    setCoursesLoading(true)
    client
      .get<Course[]>('/api/v1/courses/')
      .then(({ data }) => {
        if (cancelled) return
        setCourses(data)
        // Auto-select first enrolled course for recommendations
        const first = data.find((c) => c.is_enrolled)
        if (first) setSelectedCourseId(first.id)
      })
      .catch(() => {
        if (!cancelled) setCoursesError('Failed to load courses.')
      })
      .finally(() => {
        if (!cancelled) setCoursesLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // ---- Fetch recommendations when selection changes ----
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

  // ---- Enroll from catalog ----
  const handleEnroll = async (courseId: number) => {
    setEnrollingId(courseId)
    try {
      await client.post(`/api/v1/courses/${courseId}/enroll/`)
      // Move course to "My Learning" locally — no page reload
      setCourses((prev) =>
        prev.map((c) => (c.id === courseId ? { ...c, is_enrolled: true } : c))
      )
      // Auto-select the newly enrolled course
      setSelectedCourseId(courseId)
    } catch {
      // Silently ignore — user can retry
    } finally {
      setEnrollingId(null)
    }
  }

  const selectedCourse = enrolledCourses.find((c) => c.id === selectedCourseId) ?? null

  return (
    <div className="flex flex-col">
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-10">

        {/* ============================================================
            SECTION 1 — MY LEARNING
        ============================================================ */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={16} className="text-indigo-500" />
            <h2 className="text-base font-semibold text-gray-800">My Learning</h2>
          </div>

          {coursesError && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3
                            text-sm text-red-700 mb-4">
              {coursesError}
            </div>
          )}

          {coursesLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                {[...Array(2)].map((_, i) => (
                  <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
                    <div className="h-3 w-40 bg-gray-200 rounded animate-pulse" />
                    <div className="h-3 w-full bg-gray-100 rounded animate-pulse" />
                  </div>
                ))}
              </div>
              <div className="bg-white rounded-xl border border-gray-200 h-40 animate-pulse" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Enrolled course list */}
              <div className="space-y-3">
                {enrolledCourses.length === 0 ? (
                  <NoEnrollmentsPrompt />
                ) : (
                  enrolledCourses.map((course) => (
                    <EnrolledCourseCard
                      key={course.id}
                      course={course}
                      selected={course.id === selectedCourseId}
                      onClick={() => setSelectedCourseId(course.id)}
                    />
                  ))
                )}
              </div>

              {/* Recommendations panel */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Sparkles size={14} className="text-indigo-400" />
                    <h3 className="text-sm font-semibold text-gray-700">Smart Recommendations</h3>
                  </div>
                  {modelLoaded === false && (
                    <span className="text-xs text-yellow-600 bg-yellow-50 border border-yellow-200
                                     rounded-full px-2 py-0.5">
                      ML model not loaded
                    </span>
                  )}
                </div>

                {selectedCourse && (
                  <p className="text-xs text-gray-400 mb-2">
                    For: <span className="font-medium text-gray-600">{selectedCourse.title}</span>
                  </p>
                )}

                <div className="bg-white rounded-xl border border-gray-200 px-4 py-2 min-h-[180px]">
                  {enrolledCourses.length === 0 ? (
                    <p className="text-sm text-gray-400 py-8 text-center">
                      Enroll in a course to see AI recommendations.
                    </p>
                  ) : recsLoading ? (
                    <p className="text-sm text-gray-400 py-6 text-center">
                      Loading recommendations…
                    </p>
                  ) : recsError ? (
                    <p className="text-sm text-red-500 py-6 text-center">{recsError}</p>
                  ) : recs.length === 0 && selectedCourseId !== null ? (
                    <p className="text-sm text-gray-400 py-6 text-center">
                      No problem topics! Keep up the good work.
                    </p>
                  ) : (
                    recs.map((item, i) => (
                      <RecommendationRow key={item.lesson_id} item={item} rank={i + 1} />
                    ))
                  )}
                </div>

                {!recsLoading && recs.length > 0 && (
                  <p className="text-xs text-gray-400 mt-2">
                    Lessons ranked by predicted difficulty (highest risk first).
                  </p>
                )}
              </div>
            </div>
          )}
        </section>

        {/* ============================================================
            SECTION 2 — EXPLORE CATALOG
        ============================================================ */}
        {!coursesLoading && catalogCourses.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Layers size={16} className="text-gray-400" />
              <h2 className="text-base font-semibold text-gray-800">Explore Catalog</h2>
              <span className="ml-1 text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">
                {catalogCourses.length}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {catalogCourses.map((course) => (
                <CatalogCard
                  key={course.id}
                  course={course}
                  enrolling={enrollingId === course.id}
                  onEnroll={() => handleEnroll(course.id)}
                />
              ))}
            </div>
          </section>
        )}

      </main>
    </div>
  )
}
