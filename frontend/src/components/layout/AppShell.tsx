/**
 * components/layout/AppShell.tsx
 * ================================
 * Root layout: collapsible Sidebar + top Header.
 * All authenticated pages render as children of this shell.
 */

import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  BookOpen,
  User,
  GraduationCap,
  LogOut,
  Menu,
  PenLine,
  X,
  ChevronRight,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
  teacherOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Мои курсы',       to: '/',                       icon: <BookOpen      size={18} /> },
  { label: 'Профиль',         to: '/profile',                icon: <User          size={18} /> },
  { label: 'Инструктор',      to: '/instructor',             icon: <GraduationCap size={18} />, teacherOnly: true },
  { label: 'Редактор курсов', to: '/instructor/my-courses',  icon: <PenLine       size={18} />, teacherOnly: true },
]

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

function Sidebar({
  open,
  onClose,
  role,
}: {
  open: boolean
  onClose: () => void
  role: string
}) {
  const logout = useAuthStore((s) => s.logout)

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-20 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-full z-30 flex flex-col
          bg-white border-r border-gray-200 transition-all duration-200
          ${open ? 'w-56' : 'w-0 md:w-16'} overflow-hidden
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 h-14 border-b border-gray-100 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <BookOpen size={14} className="text-white" />
          </div>
          {open && (
            <span className="text-sm font-bold text-gray-800 whitespace-nowrap">
              LMS Adaptive
            </span>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-hidden">
          {NAV_ITEMS.filter((item) => !item.teacherOnly || role === 'teacher').map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => { if (window.innerWidth < 768) onClose() }}
              className={({ isActive }) => `
                flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg text-sm
                transition-colors whitespace-nowrap
                ${isActive
                  ? 'bg-indigo-50 text-indigo-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }
              `}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {open && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="p-2 border-t border-gray-100 flex-shrink-0">
          <button
            onClick={logout}
            className="flex items-center gap-3 px-4 py-2.5 w-full rounded-lg text-sm
                       text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <LogOut size={18} className="flex-shrink-0" />
            {open && <span>Выйти</span>}
          </button>
        </div>
      </aside>
    </>
  )
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function Header({
  sidebarOpen,
  onToggle,
  username,
}: {
  sidebarOpen: boolean
  onToggle: () => void
  username: string
}) {
  const navigate = useNavigate()

  return (
    <header
      className={`
        fixed top-0 right-0 h-14 z-10 flex items-center justify-between
        bg-white border-b border-gray-200 px-4 transition-all duration-200
        ${sidebarOpen ? 'left-56' : 'left-0 md:left-16'}
      `}
    >
      <button
        onClick={onToggle}
        className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
        aria-label="Переключить боковую панель"
      >
        {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/profile')}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm
                     text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center">
            <span className="text-xs font-semibold text-indigo-700">
              {username.charAt(0).toUpperCase()}
            </span>
          </div>
          <span className="hidden sm:block font-medium">{username}</span>
          <ChevronRight size={14} className="text-gray-400" />
        </button>
      </div>
    </header>
  )
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  // Read user info from authStore; fall back to empty strings if not yet loaded
  const username = useAuthStore((s) => (s as any).username as string | undefined) ?? ''
  const role     = useAuthStore((s) => (s as any).role     as string | undefined) ?? 'student'

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        role={role}
      />

      <Header
        sidebarOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        username={username || 'Пользователь'}
      />

      {/* Page content — offset for sidebar and header */}
      <main
        className={`
          pt-14 min-h-screen transition-all duration-200
          ${sidebarOpen ? 'md:pl-56' : 'md:pl-16'}
        `}
      >
        {children}
      </main>
    </div>
  )
}
