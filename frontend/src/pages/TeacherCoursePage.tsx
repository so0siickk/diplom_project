import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, FolderOpen } from 'lucide-react'
import CourseDocumentUploader from '../components/CourseDocumentUploader'

// ---------------------------------------------------------------------------
// Invalid ID fallback
// ---------------------------------------------------------------------------

function InvalidIdFallback() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-500">
        <FolderOpen className="h-8 w-8" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-gray-800">Курс не найден</h2>
        <p className="mt-1 text-sm text-gray-500">
          Идентификатор курса в URL некорректен.
        </p>
      </div>
      <Link
        to="/instructor/my-courses"
        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
      >
        <ArrowLeft className="h-4 w-4" />
        Мои курсы
      </Link>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TeacherCoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const id = Number(courseId)

  if (!courseId || isNaN(id)) {
    return <InvalidIdFallback />
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link
          to="/instructor/my-courses"
          className="flex items-center gap-1 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Мои курсы
        </Link>
        <span>/</span>
        <span className="text-gray-800 font-medium">Материалы курса #{id}</span>
      </div>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Учебные материалы</h1>
        <p className="mt-1 text-sm text-gray-500">
          Загружайте PDF и DOCX-файлы — они автоматически индексируются для RAG-ассистента.
        </p>
      </div>

      {/* Uploader */}
      <CourseDocumentUploader courseId={id} />
    </div>
  )
}
