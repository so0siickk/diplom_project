/**
 * src/api/types.ts
 * ================
 * TypeScript interfaces mirroring backend serializers and API response shapes.
 */

export type AssignmentType = 'essay' | 'code' | 'ai_dialog' | 'quiz' | 'file_upload'

export interface Assignment {
  id: number
  lesson: number
  title: string
  description: string
  assignment_type: AssignmentType
  // Flexible payload: schema differs per assignment_type
  content: Record<string, unknown>
  max_score: number
  max_attempts: number  // 0 = unlimited
  order: number
}

export interface Lesson {
  id: number
  title: string
  content: string
  video_url: string | null
  order: number
  assignments?: Assignment[]
}

export interface Module {
  id: number
  title: string
  description: string
  order: number
  lessons: Lesson[]
}

export interface Course {
  id: number
  title: string
  description: string
  owner: string
  created_at: string
  modules: Module[]
  is_enrolled: boolean
}

export interface RecommendationItem {
  lesson_id: number
  lesson_title: string
  module_title: string
  completion_prob: number
  risk_score: number
}

export interface RecommendationsResponse {
  course_id: number
  course_title: string
  model_loaded: boolean
  recommendations: RecommendationItem[]
}

export interface ChatResponse {
  answer: string
}

// ---------------------------------------------------------------------------
// Course Documents
// ---------------------------------------------------------------------------

export type DocumentStatus = 'pending' | 'parsed' | 'error'

export interface CourseDocument {
  id: number
  original_filename: string
  status: DocumentStatus
  status_display: string
  error_message: string | null
  uploaded_by: string
  uploaded_at: string
}

// ---------------------------------------------------------------------------
// Assignments
// ---------------------------------------------------------------------------

export interface OpenAssignment {
  id: number
  lesson: number | null
  lesson_title: string | null
  created_by: string
  title: string
  description: string
  max_score: number
  is_active: boolean
  created_at: string
}

export type SubmissionStatus = 'pending' | 'ai_checked' | 'approved'

export interface AIEvaluation {
  id: number
  score: number
  feedback: string
  model_name: string
  evaluated_at: string
}

export interface AssignmentSubmission {
  id: number
  student_username: string
  answer_text: string
  submitted_at: string
  status: SubmissionStatus
  status_display: string
  ai_evaluation: AIEvaluation | null
  final_score: number | null
  teacher_comment: string | null
}

// ---------------------------------------------------------------------------
// Lesson Materials (file attachments)
// ---------------------------------------------------------------------------

export interface LessonFile {
  id: number
  filename: string
  file_url: string
  file_size_bytes: number | null
  content_type: string | null
  uploaded_at: string
}

// ---------------------------------------------------------------------------
// Quiz
// ---------------------------------------------------------------------------

export interface QuizOption {
  id: number
  text: string
}

export interface QuizQuestion {
  id: number
  text: string
  is_multiple_choice: boolean
  order: number
  options: QuizOption[]
}

export interface Quiz {
  id: number
  title: string
  description: string | null
  questions: QuizQuestion[]
}

export interface QuizSubmitResponse {
  score_percent: number
  correct_answers: number
  total_questions: number
  is_passed: boolean
  needs_review: boolean
  recommended_action?: string
}

// ---------------------------------------------------------------------------
// Risk Dashboard (teacher view)
// ---------------------------------------------------------------------------

export type RiskLevel = 'red' | 'yellow' | 'green' | 'unknown'

export interface StudentStat {
  user_id: number
  username: string
  lessons_completed: number
  avg_score: number | null
  highest_risk_lesson: string | null
  risk_score: number | null
}
