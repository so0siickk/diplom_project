/**
 * src/pages/CourseDetail.tsx
 * ==========================
 * Course overview page.
 *
 * Not enrolled → EnrollHero (course landing + enroll CTA)
 * Enrolled     → module accordion with lesson links
 *
 * Route: /course/:id
 */

import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Layers,
  Lock,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  User,
  Loader2,
} from 'lucide-react'
import client from '../api/client'
import type { Course } from '../api/types'

// ---------------------------------------------------------------------------
// Icon helpers
// ---------------------------------------------------------------------------

function ChevronIcon({ open }: { open: boolean }) {
  return open ? (
    <ChevronUp className="w-4 h-4 text-gray-400" />
  ) : (
    <ChevronDown className="w-4 h-4 text-gray-400" />
  )
}

// ---------------------------------------------------------------------------
// EnrollHero — shown when user is NOT enrolled
// ---------------------------------------------------------------------------

function EnrollHero({
  course,
  onEnroll,
  enrolling,
  enrollError,
}: {
  course: Course
  onEnroll: () => void
  enrolling: boolean
  enrollError: string | null
}) {
  const totalLessons = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero banner */}
      <div className="bg-gradient-to-br from-indigo-600 via-indigo-700 to-indigo-900 text-white">
        <div className="max-w-2xl mx-auto px-6 py-16">
          {/* Badge */}
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full
                           bg-white/10 border border-white/20 text-xs font-medium mb-5">
            <BookOpen size={12} />
            Free course
          </span>

          <h1 className="text-3xl font-bold leading-tight mb-3">{course.title}</h1>

          {course.description && (
            <p className="text-indigo-200 text-sm leading-relaxed mb-8 max-w-lg">
              {course.description}
            </p>
          )}

          {/* Stats */}
          <div className="flex flex-wrap gap-6 mb-10">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                <Layers size={15} />
              </div>
              <div>
                <p className="text-xl font-bold leading-none">{course.modules.length}</p>
                <p className="text-xs text-indigo-300 mt-0.5">
                  module{course.modules.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                <BookOpen size={15} />
              </div>
              <div>
                <p className="text-xl font-bold leading-none">{totalLessons}</p>
                <p className="text-xs text-indigo-300 mt-0.5">
                  lesson{totalLessons !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                <User size={15} />
              </div>
              <div>
                <p className="text-sm font-semibold leading-none">{course.owner}</p>
                <p className="text-xs text-indigo-300 mt-0.5">instructor</p>
              </div>
            </div>
          </div>

          {/* CTA */}
          {enrollError && (
            <p className="text-red-300 text-sm mb-3">{enrollError}</p>
          )}
          <button
            onClick={onEnroll}
            disabled={enrolling}
            className="flex items-center gap-2 px-8 py-3.5 bg-white text-indigo-700
                       rounded-xl font-semibold text-sm hover:bg-indigo-50 transition-colors
                       disabled:opacity-60 disabled:cursor-not-allowed shadow-lg shadow-indigo-900/30"
          >
            {enrolling ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Enrolling…
              </>
            ) : (
              <>
                <CheckCircle2 size={16} />
                Enroll Now — It's Free
              </>
            )}
          </button>
        </div>
      </div>

      {/* Course preview — locked content */}
      <div className="max-w-2xl mx-auto px-4 py-10">
        <h2 className="text-base font-semibold text-gray-700 mb-4">Course Contents</h2>
        <div className="space-y-2">
          {course.modules
            .slice()
            .sort((a, b) => a.order - b.order)
            .map((mod) => (
              <div key={mod.id} className="bg-white rounded-xl border border-gray-200">
                {/* Module header */}
                <div className="flex items-center gap-3 px-5 py-4">
                  <Layers size={15} className="text-indigo-400 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-800">{mod.title}</p>
                    {mod.description && (
                      <p className="text-xs text-gray-400 mt-0.5">{mod.description}</p>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    {mod.lessons.length} lesson{mod.lessons.length !== 1 ? 's' : ''}
                  </span>
                </div>
                {/* Locked lessons */}
                {mod.lessons.length > 0 && (
                  <ul className="border-t border-gray-100 divide-y divide-gray-100">
                    {mod.lessons
                      .slice()
                      .sort((a, b) => a.order - b.order)
                      .map((lesson) => (
                        <li key={lesson.id}
                          className="flex items-center gap-3 px-5 py-2.5">
                          <Lock size={12} className="text-gray-300 flex-shrink-0" />
                          <span className="text-sm text-gray-400">{lesson.title}</span>
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            ))}
        </div>

        {/* Bottom CTA */}
        <div className="mt-8 text-center">
          <button
            onClick={onEnroll}
            disabled={enrolling}
            className="px-6 py-2.5 bg-indigo-600 text-white text-sm font-medium
                       rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-60"
          >
            {enrolling ? 'Enrolling…' : 'Get started — Enroll for free'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CourseContent — shown when user IS enrolled
// ---------------------------------------------------------------------------

function CourseContent({
  course,
  openModules,
  onToggle,
}: {
  course: Course
  openModules: Set<number>
  onToggle: (id: number) => void
}) {
  const totalLessons = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-100 bg-white text-sm">
        <Link to="/" className="text-gray-400 hover:text-gray-700 transition-colors">
          My Courses
        </Link>
        <span className="text-gray-300">›</span>
        <span className="font-medium text-gray-700 truncate">{course.title}</span>
      </div>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Course meta */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">{course.title}</h1>
          {course.description && (
            <p className="mt-2 text-sm text-gray-500">{course.description}</p>
          )}
          <div className="mt-3 flex gap-4 text-xs text-gray-400">
            <span>{course.modules.length} module{course.modules.length !== 1 ? 's' : ''}</span>
            <span>·</span>
            <span>{totalLessons} lesson{totalLessons !== 1 ? 's' : ''}</span>
            <span>·</span>
            <span>by {course.owner}</span>
          </div>
        </div>

        {/* Modules accordion */}
        <div className="space-y-3">
          {course.modules
            .slice()
            .sort((a, b) => a.order - b.order)
            .map((mod) => {
              const isOpen = openModules.has(mod.id)
              return (
                <div key={mod.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <button
                    onClick={() => onToggle(mod.id)}
                    className="w-full flex items-center justify-between px-5 py-4
                               hover:bg-gray-50 transition-colors"
                  >
                    <div className="text-left">
                      <p className="text-sm font-semibold text-gray-800">{mod.title}</p>
                      {mod.description && (
                        <p className="text-xs text-gray-400 mt-0.5">{mod.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3 ml-4 flex-shrink-0">
                      <span className="text-xs text-gray-400">
                        {mod.lessons.length} lesson{mod.lessons.length !== 1 ? 's' : ''}
                      </span>
                      <ChevronIcon open={isOpen} />
                    </div>
                  </button>

                  {isOpen && mod.lessons.length > 0 && (
                    <ul className="border-t border-gray-100 divide-y divide-gray-100">
                      {mod.lessons
                        .slice()
                        .sort((a, b) => a.order - b.order)
                        .map((lesson) => (
                          <li key={lesson.id}>
                            <Link
                              to={`/lesson/${lesson.id}`}
                              state={{
                                courseId: course.id,
                                courseTitle: course.title,
                                moduleTitle: mod.title,
                              }}
                              className="flex items-center gap-3 px-5 py-3
                                         hover:bg-indigo-50 group transition-colors"
                            >
                              <BookOpen size={14} className="text-indigo-400 flex-shrink-0" />
                              <span className="text-sm text-gray-700
                                               group-hover:text-indigo-700 transition-colors">
                                {lesson.title}
                              </span>
                            </Link>
                          </li>
                        ))}
                    </ul>
                  )}

                  {isOpen && mod.lessons.length === 0 && (
                    <p className="px-5 py-3 text-xs text-gray-400 border-t border-gray-100">
                      No lessons in this module yet.
                    </p>
                  )}
                </div>
              )
            })}
        </div>
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function CourseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [course, setCourse] = useState<Course | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openModules, setOpenModules] = useState<Set<number>>(new Set())

  // Enrollment state
  const [isEnrolled, setIsEnrolled] = useState(false)
  const [enrolling, setEnrolling] = useState(false)
  const [enrollError, setEnrollError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    client
      .get<Course>(`/api/v1/courses/${id}/`)
      .then(({ data }) => {
        setCourse(data)
        setIsEnrolled(data.is_enrolled)
        if (data.is_enrolled) {
          setOpenModules(new Set(data.modules.map((m) => m.id)))
        }
      })
      .catch(() => setError('Failed to load course.'))
      .finally(() => setLoading(false))
  }, [id])

  const handleEnroll = async () => {
    if (!id) return
    setEnrolling(true)
    setEnrollError(null)
    try {
      await client.post(`/api/v1/courses/${id}/enroll/`)
      setIsEnrolled(true)
      // Open all modules so content is immediately visible
      if (course) {
        setOpenModules(new Set(course.modules.map((m) => m.id)))
      }
    } catch {
      setEnrollError('Failed to enroll. Please try again.')
    } finally {
      setEnrolling(false)
    }
  }

  const toggleModule = (moduleId: number) => {
    setOpenModules((prev) => {
      const next = new Set(prev)
      next.has(moduleId) ? next.delete(moduleId) : next.add(moduleId)
      return next
    })
  }

  // ---- Loading ----
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading course…</p>
      </div>
    )
  }

  // ---- Error / not found ----
  if (error || !course) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-500 mb-4">{error ?? 'Course not found.'}</p>
          <button
            onClick={() => navigate('/')}
            className="text-sm text-indigo-600 hover:underline"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  // ---- Not enrolled ----
  if (!isEnrolled) {
    return (
      <EnrollHero
        course={course}
        onEnroll={handleEnroll}
        enrolling={enrolling}
        enrollError={enrollError}
      />
    )
  }

  // ---- Enrolled ----
  return (
    <CourseContent
      course={course}
      openModules={openModules}
      onToggle={toggleModule}
    />
  )
}
