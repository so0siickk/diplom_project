import { useEffect, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  Download,
  ExternalLink,
  File,
  FileText,
  Loader2,
} from 'lucide-react'
import client, { BACKEND_URL } from '../api/client'
import type { LessonFile } from '../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getFileIcon(filename: string): React.ReactNode {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  if (['pdf', 'doc', 'docx'].includes(ext)) {
    return <FileText className="w-5 h-5 flex-shrink-0 text-[#deff9a]" />
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return <File className="w-5 h-5 flex-shrink-0 text-[#deff9a]" />
  }
  return <File className="w-5 h-5 flex-shrink-0 text-[#deff9a]" />
}

function formatSize(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function resolveUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${BACKEND_URL}${url}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  lessonId: number
}

export default function LessonMaterials({ lessonId }: Props) {
  const [files, setFiles] = useState<LessonFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    client
      .get<LessonFile[]>(`/api/v1/lessons/${lessonId}/files/`)
      .then(({ data }) => setFiles(data))
      .catch(() => setError('Не удалось загрузить материалы урока.'))
      .finally(() => setLoading(false))
  }, [lessonId])

  // ---------- Header (shared) ----------
  const header = (
    <div className="flex items-center gap-2 mb-4">
      <BookOpen className="w-4 h-4 text-[#deff9a]" />
      <h3 className="text-sm font-semibold text-white">Материалы урока</h3>
      {files.length > 0 && (
        <span className="ml-auto text-xs text-gray-500">
          {files.length}{' '}
          {files.length === 1
            ? 'файл'
            : files.length < 5
            ? 'файла'
            : 'файлов'}
        </span>
      )}
    </div>
  )

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-5">
        {header}
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 text-[#deff9a] animate-spin" />
        </div>
      </div>
    )
  }

  // ---------- Error ----------
  if (error) {
    return (
      <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-5">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      </div>
    )
  }

  // ---------- Empty state ----------
  if (files.length === 0) {
    return (
      <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-5">
        {header}
        <p className="text-sm text-gray-600 text-center py-4">
          Материалов к этому уроку пока нет.
        </p>
      </div>
    )
  }

  // ---------- File list ----------
  return (
    <div className="rounded-2xl bg-[#202020] border border-[#2e2e2e] p-5">
      {header}
      <ul className="space-y-2">
        {files.map((file) => {
          const url = resolveUrl(file.file_url)
          return (
            <li
              key={file.id}
              className="group flex items-center gap-3 rounded-xl border border-[#2e2e2e]
                         bg-[#1a1a1a] px-4 py-3 hover:border-[#deff9a]/30 hover:bg-[#222]
                         transition-all duration-150"
            >
              {getFileIcon(file.filename)}

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {file.filename}
                </p>
                {file.file_size_bytes !== null && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    {formatSize(file.file_size_bytes)}
                  </p>
                )}
              </div>

              {/* Action buttons — visible on hover */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Открыть в новой вкладке"
                  className="rounded-lg p-1.5 text-gray-500 hover:text-[#deff9a]
                             hover:bg-[#2a2a2a] transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <a
                  href={url}
                  download={file.filename}
                  title="Скачать"
                  className="rounded-lg p-1.5 text-gray-500 hover:text-[#deff9a]
                             hover:bg-[#2a2a2a] transition-colors"
                >
                  <Download className="w-4 h-4" />
                </a>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
