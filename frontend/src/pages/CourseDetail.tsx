/**
 * src/pages/CourseDetail.tsx
 * ==========================
 * Course overview page: module accordion with lesson links.
 * Route: /course/:id
 */

import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import type { Course } from '../api/types'

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  )
}

function BookIcon() {
  return (
    <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
    </svg>
  )
}

export default function CourseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [course, setCourse] = useState<Course | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openModules, setOpenModules] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!id) return
    setLoading(true)
    client
      .get<Course>(`/api/v1/courses/${id}/`)
      .then(({ data }) => {
        setCourse(data)
        // Open all modules by default
        setOpenModules(new Set(data.modules.map((m) => m.id)))
      })
      .catch(() => setError('Failed to load course.'))
      .finally(() => setLoading(false))
  }, [id])

  const toggleModule = (moduleId: number) => {
    setOpenModules((prev) => {
      const next = new Set(prev)
      next.has(moduleId) ? next.delete(moduleId) : next.add(moduleId)
      return next
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading course...</p>
      </div>
    )
  }

  if (error || !course) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-500 mb-4">{error ?? 'Course not found.'}</p>
          <button onClick={() => navigate('/')} className="text-sm text-indigo-600 hover:underline">
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  const totalLessons = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate('/')}
          className="text-sm text-gray-400 hover:text-gray-700 transition-colors"
        >
          ← Dashboard
        </button>
        <span className="text-gray-300">|</span>
        <span className="text-sm font-semibold text-gray-800 truncate">{course.title}</span>
      </header>

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

        {/* Modules */}
        <div className="space-y-3">
          {course.modules
            .slice()
            .sort((a, b) => a.order - b.order)
            .map((mod) => {
              const isOpen = openModules.has(mod.id)
              return (
                <div key={mod.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  {/* Module header */}
                  <button
                    onClick={() => toggleModule(mod.id)}
                    className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
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

                  {/* Lessons list */}
                  {isOpen && mod.lessons.length > 0 && (
                    <ul className="border-t border-gray-100 divide-y divide-gray-100">
                      {mod.lessons
                        .slice()
                        .sort((a, b) => a.order - b.order)
                        .map((lesson) => (
                          <li key={lesson.id}>
                            <Link
                              to={`/lesson/${lesson.id}`}
                              state={{ courseId: course.id, courseTitle: course.title, moduleTitle: mod.title }}
                              className="flex items-center gap-3 px-5 py-3 hover:bg-indigo-50
                                         group transition-colors"
                            >
                              <BookIcon />
                              <span className="text-sm text-gray-700 group-hover:text-indigo-700 transition-colors">
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
