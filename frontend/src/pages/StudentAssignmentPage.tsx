import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, FileQuestion } from 'lucide-react'
import AssignmentStudentView from '../components/AssignmentStudentView'

// ---------------------------------------------------------------------------
// Invalid ID fallback
// ---------------------------------------------------------------------------

function InvalidIdFallback() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-500">
        <FileQuestion className="h-8 w-8" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-gray-800">Задание не найдено</h2>
        <p className="mt-1 text-sm text-gray-500">
          Идентификатор задания в URL некорректен или ссылка устарела.
        </p>
      </div>
      <Link
        to="/"
        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
      >
        <ArrowLeft className="h-4 w-4" />
        На главную
      </Link>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function StudentAssignmentPage() {
  const { courseId, assignmentId } = useParams<{
    courseId: string
    assignmentId: string
  }>()

  const parsedCourseId = Number(courseId)
  const parsedAssignmentId = Number(assignmentId)

  if (
    !assignmentId ||
    isNaN(parsedAssignmentId) ||
    !courseId ||
    isNaN(parsedCourseId)
  ) {
    return <InvalidIdFallback />
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link
          to={`/course/${parsedCourseId}`}
          className="flex items-center gap-1 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          К курсу
        </Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">Задание</span>
      </div>

      {/* Assignment view */}
      <AssignmentStudentView assignmentId={parsedAssignmentId} />
    </div>
  )
}
