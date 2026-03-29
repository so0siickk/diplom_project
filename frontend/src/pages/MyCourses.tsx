/**
 * src/pages/MyCourses.tsx
 * ========================
 * Instructor's course list: edit, view stats, delete, create new.
 * Route: /instructor/my-courses  (teacher only)
 */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Edit3, BarChart2, Trash2, BookOpen, Layers } from 'lucide-react'
import client from '../api/client'
import type { Course } from '../api/types'
import { useAuthStore } from '../store/authStore'

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-4">
        <BookOpen size={28} className="text-indigo-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-700 mb-1">No courses yet</h3>
      <p className="text-sm text-gray-400 mb-5 max-w-xs">
        Create your first course and start building lesson content.
      </p>
      <button
        onClick={onCreate}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white
                   text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
      >
        <Plus size={15} />
        Create Course
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Course card
// ---------------------------------------------------------------------------

function CourseCard({
  course,
  onEdit,
  onDelete,
  confirmingDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  course: Course
  onEdit: () => void
  onDelete: () => void
  confirmingDelete: boolean
  onConfirmDelete: () => void
  onCancelDelete: () => void
}) {
  const lessonCount = course.modules.reduce((s, m) => s + m.lessons.length, 0)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4
                    hover:border-gray-300 transition-colors">
      {/* Meta */}
      <div className="flex-1">
        <h3 className="font-semibold text-gray-900 text-sm leading-snug">{course.title}</h3>
        {course.description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">{course.description}</p>
        )}
        <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
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
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
        <button
          onClick={onEdit}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                     bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Edit3 size={12} />
          Edit
        </button>
        <Link
          to="/instructor"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                     bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition-colors"
        >
          <BarChart2 size={12} />
          Stats
        </Link>

        <div className="flex-1" />

        {confirmingDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-red-600 font-medium">Delete?</span>
            <button
              onClick={onConfirmDelete}
              className="px-2 py-1 text-xs font-medium bg-red-600 text-white
                         rounded-lg hover:bg-red-700 transition-colors"
            >
              Yes
            </button>
            <button
              onClick={onCancelDelete}
              className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-600
                         rounded-lg hover:bg-gray-200 transition-colors"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={onDelete}
            className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50
                       rounded-lg transition-colors"
            title="Delete course"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function MyCourses() {
  const navigate = useNavigate()
  const username = useAuthStore((s) => (s as any).username as string | undefined) ?? ''

  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  useEffect(() => {
    if (!username) return
    client
      .get<Course[]>('/api/v1/courses/')
      .then(({ data }) => setCourses(data.filter((c) => c.owner === username)))
      .catch(() => setError('Failed to load courses.'))
      .finally(() => setLoading(false))
  }, [username])

  const handleDelete = async (id: number) => {
    try {
      await client.delete(`/api/v1/courses/${id}/`)
      setCourses((prev) => prev.filter((c) => c.id !== id))
    } catch {
      setError('Failed to delete course. It may have dependent data.')
    } finally {
      setConfirmDeleteId(null)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">My Courses</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Manage course content — changes are auto-indexed for the AI assistant.
          </p>
        </div>
        <button
          onClick={() => navigate('/instructor/new')}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white
                     text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus size={15} />
          New Course
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3
                        text-sm text-red-700 mb-6">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
              <div className="h-4 w-40 bg-gray-200 rounded animate-pulse" />
              <div className="h-3 w-full bg-gray-100 rounded animate-pulse" />
              <div className="h-3 w-2/3 bg-gray-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && !error && courses.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-200">
          <EmptyState onCreate={() => navigate('/instructor/new')} />
        </div>
      )}

      {/* Grid */}
      {!loading && courses.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course) => (
            <CourseCard
              key={course.id}
              course={course}
              onEdit={() => navigate(`/instructor/edit/${course.id}`)}
              confirmingDelete={confirmDeleteId === course.id}
              onDelete={() => setConfirmDeleteId(course.id)}
              onConfirmDelete={() => handleDelete(course.id)}
              onCancelDelete={() => setConfirmDeleteId(null)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
