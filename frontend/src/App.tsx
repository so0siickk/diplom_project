import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import AppShell from './components/layout/AppShell'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import CourseDetail from './pages/CourseDetail'
import LessonView from './pages/LessonView'
import ProfilePage from './pages/ProfilePage'
import InstructorDashboard from './pages/InstructorDashboard'
import MyCourses from './pages/MyCourses'
import CourseEditor from './pages/CourseEditor'

const NotFoundPage = () => (
  <div className="p-8">
    <h1 className="text-xl font-semibold text-gray-700">404 — Page not found</h1>
  </div>
)

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

// Pages wrapped in AppShell (sidebar + header)
function ShellRoute({ children }: { children: React.ReactNode }) {
  return (
    <PrivateRoute>
      <AppShell>{children}</AppShell>
    </PrivateRoute>
  )
}

export default function App() {
  const fetchProfile = useAuthStore((s) => s.fetchProfile)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  // Restore username/role on hard reload when token already exists
  useEffect(() => {
    if (isAuthenticated) fetchProfile()
  }, [isAuthenticated]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Shell pages */}
        <Route path="/"          element={<ShellRoute><Dashboard /></ShellRoute>} />
        <Route path="/profile"   element={<ShellRoute><ProfilePage /></ShellRoute>} />
        <Route path="/course/:id"    element={<ShellRoute><CourseDetail /></ShellRoute>} />
        <Route path="/instructor"            element={<ShellRoute><InstructorDashboard /></ShellRoute>} />
        <Route path="/instructor/my-courses" element={<ShellRoute><MyCourses /></ShellRoute>} />
        <Route path="/instructor/new"        element={<ShellRoute><CourseEditor /></ShellRoute>} />
        <Route path="/instructor/edit/:id"   element={<ShellRoute><CourseEditor /></ShellRoute>} />

        {/* Full-screen lesson view (has its own header) */}
        <Route
          path="/lesson/:id"
          element={<PrivateRoute><LessonView /></PrivateRoute>}
        />

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
