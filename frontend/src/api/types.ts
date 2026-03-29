/**
 * src/api/types.ts
 * ================
 * TypeScript interfaces mirroring backend serializers and API response shapes.
 */

export interface Lesson {
  id: number
  title: string
  content: string
  video_url: string | null
  order: number
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
