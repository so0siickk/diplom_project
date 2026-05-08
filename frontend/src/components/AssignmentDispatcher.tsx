import type { Assignment } from '../api/types'
import CodeEditor from './CodeEditor'
import EssayEditor from './EssayEditor'
import QuizPlayer from './QuizPlayer'

function AiDialogStub({ assignment }: { assignment: Assignment }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5
                         text-xs font-medium text-indigo-700">
          AI-диалог
        </span>
        <span className="text-xs text-gray-400">до {assignment.max_score} баллов</span>
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{assignment.title}</h3>
      <p className="text-xs text-gray-500 mb-4">{assignment.description}</p>
      <div className="rounded-lg border border-dashed border-indigo-200 bg-indigo-50 px-4 py-6 text-center">
        <p className="text-xs text-indigo-400">Здесь будет диалог с AI-собеседником для: <span className="font-medium">{assignment.title}</span></p>
      </div>
    </div>
  )
}


function FileUploadStub({ assignment }: { assignment: Assignment }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center rounded-full bg-orange-50 px-2.5 py-0.5
                         text-xs font-medium text-orange-700">
          Файл
        </span>
        <span className="text-xs text-gray-400">до {assignment.max_score} баллов</span>
      </div>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">{assignment.title}</h3>
      <p className="text-xs text-gray-500 mb-4">{assignment.description}</p>
      <div className="rounded-lg border-2 border-dashed border-gray-300 bg-gray-50
                      px-4 py-8 text-center">
        <p className="text-xs text-gray-400">Здесь будет загрузка файла для: <span className="font-medium">{assignment.title}</span></p>
      </div>
    </div>
  )
}

function UnknownTypeStub({ assignment }: { assignment: Assignment }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4">
      <p className="text-xs text-red-600">
        Неизвестный тип задания: <code className="font-mono">{assignment.assignment_type}</code>
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

interface Props {
  assignment: Assignment
}

export default function AssignmentDispatcher({ assignment }: Props) {
  switch (assignment.assignment_type) {
    case 'essay':
      return <EssayEditor assignment={assignment} />
    case 'code':
      return <CodeEditor assignment={assignment} />
    case 'ai_dialog':
      return <AiDialogStub assignment={assignment} />
    case 'quiz': {
      // quiz_id lives in assignment.content, fallback to assignment.id
      const quizId = (assignment.content.quiz_id as number | undefined) ?? assignment.id
      return <QuizPlayer quizId={quizId} />
    }
    case 'file_upload':
      return <FileUploadStub assignment={assignment} />
    default:
      return <UnknownTypeStub assignment={assignment} />
  }
}
