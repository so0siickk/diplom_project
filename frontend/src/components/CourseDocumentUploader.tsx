import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, FileText, AlertCircle, CheckCircle2, Clock, X } from 'lucide-react'
import client from '../api/client'
import type { CourseDocument, DocumentStatus } from '../api/types'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  courseId: number
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  DocumentStatus,
  { label: string; classes: string; icon: React.ReactNode }
> = {
  pending: {
    label: 'В обработке',
    classes: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
    icon: <Clock className="w-3 h-3" />,
  },
  parsed: {
    label: 'Готово',
    classes: 'bg-green-100 text-green-800 ring-green-200',
    icon: <CheckCircle2 className="w-3 h-3" />,
  },
  error: {
    label: 'Ошибка',
    classes: 'bg-red-100 text-red-800 ring-red-200',
    icon: <AlertCircle className="w-3 h-3" />,
  },
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset ${cfg.classes}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Allowed MIME types and extensions (must match backend ALLOWED_EXTENSIONS)
// ---------------------------------------------------------------------------

const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]
const ALLOWED_EXT_LABEL = 'PDF, DOCX'

function isAllowedFile(file: File): boolean {
  return ALLOWED_MIME.includes(file.type)
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CourseDocumentUploader({ courseId }: Props) {
  const [documents, setDocuments] = useState<CourseDocument[]>([])
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const dragCounter = useRef(0)

  // -- fetch existing documents --

  const fetchDocuments = useCallback(async () => {
    setLoadingDocs(true)
    setFetchError(null)
    try {
      const { data } = await client.get<CourseDocument[]>(
        `/api/v1/courses/${courseId}/documents/`,
      )
      setDocuments(data)
    } catch {
      setFetchError('Не удалось загрузить список документов.')
    } finally {
      setLoadingDocs(false)
    }
  }, [courseId])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  // -- upload --

  const uploadFile = async (file: File) => {
    if (!isAllowedFile(file)) {
      setUploadError(`Недопустимый формат. Разрешены: ${ALLOWED_EXT_LABEL}`)
      return
    }

    setUploading(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      await client.post(`/api/v1/courses/${courseId}/documents/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      await fetchDocuments()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Ошибка при загрузке файла.'
      setUploadError(msg)
    } finally {
      setUploading(false)
    }
  }

  // -- drag & drop handlers --

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    dragCounter.current += 1
    if (dragCounter.current === 1) setIsDragging(true)
  }

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    dragCounter.current -= 1
    if (dragCounter.current === 0) setIsDragging(false)
  }

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    dragCounter.current = 0
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
    e.target.value = ''
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Загрузить документ"
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
        className={[
          'relative flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-12 cursor-pointer transition-colors select-none',
          isDragging
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-gray-300 bg-gray-50 hover:border-indigo-400 hover:bg-indigo-50/40',
          uploading ? 'pointer-events-none opacity-60' : '',
        ].join(' ')}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={onFileChange}
        />

        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
          {uploading ? (
            <svg
              className="h-7 w-7 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
          ) : (
            <Upload className="h-7 w-7" />
          )}
        </div>

        <div className="text-center">
          <p className="text-sm font-medium text-gray-700">
            {uploading
              ? 'Загружается...'
              : 'Перетащите файл сюда или нажмите для выбора'}
          </p>
          <p className="mt-1 text-xs text-gray-400">{ALLOWED_EXT_LABEL} · до 20 МБ</p>
        </div>
      </div>

      {/* Upload error */}
      {uploadError && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{uploadError}</span>
          <button
            onClick={() => setUploadError(null)}
            className="ml-auto text-red-400 hover:text-red-600"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Documents list */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-600 uppercase tracking-wide">
          Загруженные материалы
        </h3>

        {loadingDocs ? (
          <div className="flex justify-center py-8 text-gray-400">
            <svg className="h-6 w-6 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          </div>
        ) : fetchError ? (
          <p className="text-sm text-red-500">{fetchError}</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">
            Документы ещё не загружены
          </p>
        ) : (
          <ul className="divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
            {documents.map((doc) => (
              <li key={doc.id} className="flex flex-col gap-1 px-4 py-3">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 shrink-0 text-indigo-400" />
                  <span className="flex-1 truncate text-sm font-medium text-gray-800">
                    {doc.original_filename}
                  </span>
                  <StatusBadge status={doc.status} />
                </div>

                {doc.status === 'error' && doc.error_message && (
                  <p className="ml-8 text-xs text-red-500">{doc.error_message}</p>
                )}

                <p className="ml-8 text-xs text-gray-400">
                  Загружено: {doc.uploaded_by} ·{' '}
                  {new Date(doc.uploaded_at).toLocaleString('ru-RU')}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
