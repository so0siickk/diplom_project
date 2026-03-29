/**
 * src/pages/LessonView.tsx
 * ========================
 * Lesson reading page with an embedded RAG chat drawer.
 *
 * Layout (md+): lesson content (left 60%) | chat panel (right 40%)
 * Layout (mobile): stacked, chat below content
 *
 * Chat: POST /api/v1/chat/ { question: "<lesson context>: <user text>" }
 * "Complete lesson" button: shows confirmation alert, then navigates
 *   to the next lesson in the course (or back to course page).
 *
 * Route: /lesson/:id
 * Route state (optional): { courseId, courseTitle, moduleTitle }
 */

import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import client from '../api/client'
import type { Course, Lesson } from '../api/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

interface LocationState {
  courseId?: number
  courseTitle?: string
  moduleTitle?: string
}

// ---------------------------------------------------------------------------
// Chat panel
// ---------------------------------------------------------------------------

function ChatPanel({ lesson }: { lesson: Lesson }) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || sending) return

    // Prefix question with lesson context so RAG assistant knows the topic
    const question = `[Lesson: "${lesson.title}"] ${text}`

    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')
    setSending(true)

    try {
      const { data } = await client.post<{ answer: string }>('/api/v1/chat/', { question })
      setMessages((prev) => [...prev, { role: 'assistant', text: data.answer }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Sorry, the assistant is unavailable right now.' },
      ])
    } finally {
      setSending(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Chat header */}
      <div className="px-4 py-3 border-b border-gray-100 flex-shrink-0">
        <p className="text-sm font-semibold text-gray-800">AI Assistant</p>
        <p className="text-xs text-gray-400 mt-0.5">Ask anything about this lesson</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">
            Ask a question about the lesson content.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap
                ${msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-sm'
                  : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-100 flex-shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a question... (Enter to send)"
            disabled={sending}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                       disabled:bg-gray-50 placeholder-gray-400"
          />
          <button
            onClick={send}
            disabled={!input.trim() || sending}
            className="flex-shrink-0 rounded-xl bg-indigo-600 px-3 py-2 text-white
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
            aria-label="Send"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-gray-300 mt-1">Shift+Enter for new line</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function LessonView() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const state = (location.state ?? {}) as LocationState

  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [course, setCourse] = useState<Course | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch the lesson's course so we can find prev/next lessons
  useEffect(() => {
    if (!id) return
    setLoading(true)

    // We need to fetch the full course to know adjacent lessons.
    // Strategy: fetch lesson list via course detail.
    // If courseId is passed via route state, use it; otherwise fall back to
    // fetching the course list and finding the one containing this lesson.
    const lessonId = parseInt(id, 10)

    const loadCourse = async (courseId: number) => {
      const { data } = await client.get<Course>(`/api/v1/courses/${courseId}/`)
      setCourse(data)
      // Find the lesson inside the course
      for (const mod of data.modules) {
        const found = mod.lessons.find((l) => l.id === lessonId)
        if (found) {
          setLesson(found)
          return
        }
      }
      setError('Lesson not found in course.')
    }

    const run = async () => {
      try {
        if (state.courseId) {
          await loadCourse(state.courseId)
        } else {
          // Fallback: search all courses
          const { data: courses } = await client.get<Course[]>('/api/v1/courses/')
          let found = false
          for (const c of courses) {
            for (const mod of c.modules) {
              if (mod.lessons.some((l) => l.id === lessonId)) {
                await loadCourse(c.id)
                found = true
                break
              }
            }
            if (found) break
          }
          if (!found) setError('Lesson not found.')
        }
      } catch {
        setError('Failed to load lesson.')
      } finally {
        setLoading(false)
      }
    }

    run()
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Build flat ordered lesson list for next/prev navigation
  const flatLessons: Lesson[] = course
    ? course.modules
        .slice()
        .sort((a, b) => a.order - b.order)
        .flatMap((m) => m.lessons.slice().sort((a, b) => a.order - b.order))
    : []

  const currentIndex = lesson ? flatLessons.findIndex((l) => l.id === lesson.id) : -1
  const nextLesson = currentIndex >= 0 && currentIndex < flatLessons.length - 1
    ? flatLessons[currentIndex + 1]
    : null

  const handleComplete = () => {
    alert('Урок пройден, данные отправлены в ML')
    if (nextLesson) {
      navigate(`/lesson/${nextLesson.id}`, {
        state: { courseId: course?.id, courseTitle: state.courseTitle, moduleTitle: state.moduleTitle },
      })
    } else {
      navigate(`/course/${course?.id}`)
    }
  }

  // ---------- Loading / error states ----------

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-400">Loading lesson...</p>
      </div>
    )
  }

  if (error || !lesson || !course) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-red-500 mb-4">{error ?? 'Lesson not found.'}</p>
          <button onClick={() => navigate('/')} className="text-sm text-indigo-600 hover:underline">
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  // ---------- Main layout ----------

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Top nav */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => navigate(`/course/${course.id}`)}
          className="text-sm text-gray-400 hover:text-gray-700 transition-colors"
        >
          ← {state.courseTitle ?? 'Course'}
        </button>
        {state.moduleTitle && (
          <>
            <span className="text-gray-300">›</span>
            <span className="text-xs text-gray-400">{state.moduleTitle}</span>
          </>
        )}
        <span className="text-gray-300">›</span>
        <span className="text-sm font-semibold text-gray-800 truncate">{lesson.title}</span>
      </header>

      {/* Body: content + chat */}
      <div className="flex-1 flex overflow-hidden">
        {/* Lesson content */}
        <div className="flex-1 overflow-y-auto px-6 py-8 md:px-10">
          <article className="max-w-prose mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">{lesson.title}</h1>

            {/* Video */}
            {lesson.video_url && (
              <div className="mb-6 rounded-xl overflow-hidden aspect-video bg-black">
                <iframe
                  src={lesson.video_url}
                  title={lesson.title}
                  className="w-full h-full"
                  allowFullScreen
                />
              </div>
            )}

            {/* Text content */}
            <div className="prose prose-sm prose-gray max-w-none">
              {lesson.content ? (
                <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{lesson.content}</p>
              ) : (
                <p className="text-gray-400 italic">No content for this lesson yet.</p>
              )}
            </div>

            {/* Complete button */}
            <div className="mt-10 flex items-center gap-4">
              <button
                onClick={handleComplete}
                className="rounded-xl bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white
                           hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500
                           transition-colors"
              >
                {nextLesson ? 'Complete & next lesson →' : 'Complete lesson'}
              </button>
              {nextLesson && (
                <span className="text-xs text-gray-400">Next: {nextLesson.title}</span>
              )}
            </div>
          </article>
        </div>

        {/* RAG chat panel */}
        <div className="hidden md:flex flex-col w-[360px] flex-shrink-0">
          <ChatPanel lesson={lesson} />
        </div>
      </div>

      {/* Mobile chat toggle — simple static panel below content on small screens */}
      <div className="md:hidden border-t border-gray-200 h-64 flex-shrink-0">
        <ChatPanel lesson={lesson} />
      </div>
    </div>
  )
}
