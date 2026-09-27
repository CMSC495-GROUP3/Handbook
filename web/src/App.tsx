import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { TOKEN_KEY, isTokenExpired } from './api/client'
import LoginForm from './components/Auth/LoginForm'
import Sidebar from './components/Layout/Sidebar'
import SidebarToggle from './components/Layout/SidebarToggle'
import { BrandMark, Wordmark } from './components/Layout/Brand'
import { useSidebar } from './hooks/useSidebar'
import ChatPage from './pages/ChatPage'
import DocumentLibraryPage from './pages/DocumentLibraryPage'
import EscalationsPage from './pages/EscalationsPage'
import CoverageGapsPage from './pages/CoverageGapsPage'

/** True when localStorage holds a JWT that has not yet expired. */
function readIsAuthenticated(): boolean {
  const token = localStorage.getItem(TOKEN_KEY)
  if (!token) return false
  if (isTokenExpired(token)) {
    localStorage.removeItem(TOKEN_KEY)
    return false
  }
  return true
}

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const sidebar = useSidebar()

  return (
    <div className="flex h-svh w-full overflow-hidden">
      <Sidebar
        open={sidebar.open}
        isDesktop={sidebar.isDesktop}
        onToggle={sidebar.toggle}
        onNavigate={sidebar.isDesktop ? undefined : sidebar.close}
      />
      {!sidebar.isDesktop && sidebar.open && (
        <div
          className="fixed inset-0 z-30 bg-ink/35"
          onClick={sidebar.close}
          aria-hidden="true"
        />
      )}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* On desktop the sidebar is always on screen, expanded or as a rail,
            so only phones need a bar to reach it from. */}
        {!sidebar.isDesktop && (
          <div className="flex h-13 shrink-0 items-center gap-2.5 border-b border-rule px-2">
            <SidebarToggle kind="menu" open={sidebar.open} onToggle={sidebar.toggle} />
            <BrandMark size={24} />
            <Wordmark className="text-[19px] leading-none" />
          </div>
        )}
        {children}
      </main>
    </div>
  )
}

export default function App() {
  // Single source of truth for auth state lives here.
  // LoginForm calls onSuccess() which updates this state directly,
  // so App re-renders immediately and switches to the protected layout.
  const [isAuthenticated, setIsAuthenticated] = useState(readIsAuthenticated)

  if (!isAuthenticated) {
    return <LoginForm onSuccess={() => setIsAuthenticated(true)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route
          path="/chat"
          element={
            <ProtectedLayout>
              <ChatPage />
            </ProtectedLayout>
          }
        />
        <Route
          path="/documents"
          element={
            <ProtectedLayout>
              <DocumentLibraryPage />
            </ProtectedLayout>
          }
        />
        <Route
          path="/escalations"
          element={
            <ProtectedLayout>
              <EscalationsPage />
            </ProtectedLayout>
          }
        />
        <Route
          path="/gaps"
          element={
            <ProtectedLayout>
              <CoverageGapsPage />
            </ProtectedLayout>
          }
        />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
