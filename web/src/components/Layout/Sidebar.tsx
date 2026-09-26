import { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { Menu, MenuButton, MenuItems, MenuItem } from '@headlessui/react'
import {
  Plus, MessageCircleQuestionMark, BookOpen, LogOut, Pencil, Trash2,
  Check, X, ChevronRight, FolderOpen, FolderPlus, Folder, ClipboardList,
  BookDashed,
} from 'lucide-react'
import { useConversations } from '../../hooks/useConversations'
import { useProjects } from '../../hooks/useProjects'
import { useAuth } from '../../hooks/useAuth'
import { BrandMark, Wordmark } from './Brand'
import SidebarToggle from './SidebarToggle'
import ThemeToggle from './ThemeToggle'
import type { Conversation, Project } from '../../types'

interface SidebarProps {
  open: boolean
  isDesktop: boolean
  onToggle: () => void
  /** Called after any navigation; the phone layout closes the drawer here. */
  onNavigate?: () => void
}

// One row style for everything in the rail: conversations, projects, nav.
const ROW = 'flex w-full min-w-0 cursor-pointer items-center gap-2.5 rounded-md text-[13.5px] transition-colors'
const ROW_IDLE = 'text-ink hover:bg-paper-3'
const ROW_ACTIVE = 'bg-accent-soft font-medium text-accent-ink'
const ICON_BUTTON = 'flex shrink-0 cursor-pointer items-center justify-center rounded transition-colors'
const RAIL_BUTTON = 'flex h-10 w-10 cursor-pointer items-center justify-center rounded-md transition-colors'

export default function Sidebar({ open, isDesktop, onToggle, onNavigate }: SidebarProps) {
  const routerNavigate = useNavigate()
  const navigate = (to: string) => {
    routerNavigate(to)
    onNavigate?.()
  }
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const activeSessionId = searchParams.get('session_id')
  const onLibrary = location.pathname === '/documents'
  const onEscalations = location.pathname === '/escalations'
  const onGaps = location.pathname === '/gaps'

  const { conversations, fetchConversations, renameConversation, assignToProject, deleteConversation } = useConversations()
  const { projects, fetchProjects, createProject, deleteProject } = useProjects()
  // Only an HR session sees the HR pages. The API refuses everyone else, so
  // this saves employees a click into a 403; it is not the access check.
  const { logout, isHr } = useAuth()

  // Rename state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const editInputRef = useRef<HTMLInputElement>(null)

  // New project inline creation
  const [creatingProject, setCreatingProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const newProjectInputRef = useRef<HTMLInputElement>(null)

  // Which project sections are collapsed (all open by default)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchConversations()
    fetchProjects()
  }, [fetchConversations, fetchProjects, location])

  useEffect(() => {
    if (editingId && editInputRef.current) editInputRef.current.focus()
  }, [editingId])

  useEffect(() => {
    if (creatingProject && newProjectInputRef.current) newProjectInputRef.current.focus()
  }, [creatingProject])

  // ── rename helpers ──────────────────────────────────────────────────────────
  function startEdit(conv: Conversation) {
    setEditingId(conv.session_id)
    setEditValue(conv.title)
  }
  async function commitRename() {
    if (!editingId || !editValue.trim()) return cancelEdit()
    await renameConversation(editingId, editValue.trim())
    setEditingId(null)
  }
  function cancelEdit() { setEditingId(null); setEditValue('') }

  // ── project creation helpers ────────────────────────────────────────────────
  async function commitNewProject() {
    const name = newProjectName.trim()
    if (name) await createProject(name)
    setCreatingProject(false)
    setNewProjectName('')
  }
  function cancelNewProject() { setCreatingProject(false); setNewProjectName('') }

  // ── project collapse ────────────────────────────────────────────────────────
  function toggleCollapse(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // ── delete conversation ─────────────────────────────────────────────────────
  function handleDeleteConversation(sessionId: string) {
    deleteConversation(sessionId)
    if (activeSessionId === sessionId) navigate('/chat')
  }

  // ── group by project ────────────────────────────────────────────────────────
  const byProject = conversations.reduce<Record<string, Conversation[]>>((acc, conv) => {
    const key = conv.project_id ?? '__ungrouped__'
    if (!acc[key]) acc[key] = []
    acc[key].push(conv)
    return acc
  }, {})

  const ungrouped = byProject['__ungrouped__'] ?? []

  // Shared props for ConversationItem
  const itemProps = {
    activeSessionId,
    editingId,
    editValue,
    editInputRef,
    projects,
    onNavigate: (sid: string) => navigate(`/chat?session_id=${sid}`),
    onStartEdit: startEdit,
    onEditChange: setEditValue,
    onCommitRename: commitRename,
    onCancelEdit: cancelEdit,
    onAssign: assignToProject,
    onDelete: handleDeleteConversation,
  }

  // Desktop, collapsed: a narrow rail that keeps the primary actions on
  // screen. The conversation list is one click away behind the toggle.
  if (isDesktop && !open) {
    return (
      <aside
        id="app-sidebar"
        aria-label="Navigation"
        className="flex h-svh w-15 shrink-0 flex-col items-center border-r border-rule bg-paper-2"
      >
        <div className="flex h-15 w-full shrink-0 items-center justify-center border-b border-rule">
          <BrandMark size={28} />
        </div>
        <div className="mt-2.5 flex flex-col items-center gap-1">
          <SidebarToggle kind="expand" onToggle={onToggle} />
          <button
            type="button"
            onClick={() => navigate('/chat')}
            title="New question"
            aria-label="New question"
            className={`${RAIL_BUTTON} text-ink hover:bg-paper-3`}
          >
            <Plus size={18} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => navigate('/documents')}
            title="Policy Library"
            aria-label="Policy Library"
            aria-current={onLibrary ? 'page' : undefined}
            className={`${RAIL_BUTTON} ${onLibrary ? 'bg-accent-soft text-accent' : 'text-ink-2 hover:bg-paper-3 hover:text-ink'}`}
          >
            <BookOpen size={18} aria-hidden="true" />
          </button>
          {isHr && (
            <>
              <button
                type="button"
                onClick={() => navigate('/escalations')}
                title="HR Requests"
                aria-label="HR Requests"
                aria-current={onEscalations ? 'page' : undefined}
                className={`${RAIL_BUTTON} ${onEscalations ? 'bg-accent-soft text-accent' : 'text-ink-2 hover:bg-paper-3 hover:text-ink'}`}
              >
                <ClipboardList size={18} aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => navigate('/gaps')}
                title="What People Ask"
                aria-label="What People Ask"
                aria-current={onGaps ? 'page' : undefined}
                className={`${RAIL_BUTTON} ${onGaps ? 'bg-accent-soft text-accent' : 'text-ink-2 hover:bg-paper-3 hover:text-ink'}`}
              >
                <BookDashed size={18} aria-hidden="true" />
              </button>
            </>
          )}
        </div>
        <div className="mt-auto flex flex-col items-center gap-1 pb-3">
          <ThemeToggle />
          <button
            type="button"
            onClick={logout}
            title="Sign out"
            aria-label="Sign out"
            className={`${RAIL_BUTTON} text-ink-3 hover:bg-paper-3 hover:text-ink`}
          >
            <LogOut size={18} aria-hidden="true" />
          </button>
        </div>
      </aside>
    )
  }

  // Phone: a drawer over the page that slides in; it stays mounted so the
  // slide can animate, and `inert` keeps its controls out of the tab order
  // while it is off screen.
  const layoutClass = isDesktop
    ? 'flex'
    : `fixed inset-y-0 left-0 z-40 flex transform transition-transform duration-200 motion-reduce:transition-none ${
        open ? 'translate-x-0 shadow-drawer' : '-translate-x-full'
      }`

  return (
    <aside
      id="app-sidebar"
      inert={!isDesktop && !open}
      aria-label="Conversations"
      className={`h-svh w-66 shrink-0 flex-col border-r border-rule bg-paper-2 ${layoutClass}`}
    >
      {/* Brand */}
      <div className="flex h-15 shrink-0 items-center gap-2.5 border-b border-rule pr-3 pl-4">
        <BrandMark size={28} />
        <Wordmark className="flex-1 text-[21px] leading-none" />
        <SidebarToggle kind={isDesktop ? 'collapse' : 'close'} onToggle={onToggle} className="-mr-1" />
      </div>

      {/* Primary actions */}
      <div className="flex flex-col gap-0.5 px-3 pt-3 pb-1">
        <button
          type="button"
          onClick={() => navigate('/chat')}
          className="flex h-9 w-full cursor-pointer items-center gap-2 rounded-md border border-rule-strong bg-paper-3 px-3 text-[13.5px] font-medium text-ink shadow-[0_1px_0_rgb(36_30_25/0.04)] transition-colors hover:border-ink-3"
        >
          <Plus size={15} aria-hidden="true" />
          New question
        </button>
        <button
          type="button"
          onClick={() => navigate('/documents')}
          aria-current={onLibrary ? 'page' : undefined}
          className={`${ROW} mt-1.5 h-[34px] px-2.5 ${onLibrary ? ROW_ACTIVE : ROW_IDLE}`}
        >
          <BookOpen size={15} aria-hidden="true" className={onLibrary ? 'text-accent' : 'text-ink-3'} />
          Policy Library
        </button>
        {isHr && (
          <>
            <button
              type="button"
              onClick={() => navigate('/escalations')}
              aria-current={onEscalations ? 'page' : undefined}
              className={`${ROW} h-[34px] px-2.5 ${onEscalations ? ROW_ACTIVE : ROW_IDLE}`}
            >
              <ClipboardList size={15} aria-hidden="true" className={onEscalations ? 'text-accent' : 'text-ink-3'} />
              HR Requests
            </button>
            <button
              type="button"
              onClick={() => navigate('/gaps')}
              aria-current={onGaps ? 'page' : undefined}
              className={`${ROW} h-[34px] px-2.5 ${onGaps ? ROW_ACTIVE : ROW_IDLE}`}
            >
              <BookDashed size={15} aria-hidden="true" className={onGaps ? 'text-accent' : 'text-ink-3'} />
              What People Ask
            </button>
          </>
        )}
      </div>

      {/* Scrollable middle */}
      <nav className="flex-1 overflow-y-auto px-3 py-1" aria-label="Recent questions">

        {/* ── Projects section ─────────────────────────────────────────── */}
        <div className="mt-3 flex h-7 items-center justify-between px-2.5">
          <span className="caps text-ink-3">Projects</span>
          <button
            type="button"
            onClick={() => setCreatingProject(true)}
            title="New project"
            aria-label="New project"
            className={`${ICON_BUTTON} h-6 w-6 text-ink-3 hover:text-accent`}
          >
            <FolderPlus size={14} aria-hidden="true" />
          </button>
        </div>

        <div className="flex flex-col gap-0.5">
          {/* Inline new-project input */}
          {creatingProject && (
            <div className="flex items-center gap-1.5 px-2 py-1">
              <Folder size={14} aria-hidden="true" className="shrink-0 text-ink-3" />
              <input
                ref={newProjectInputRef}
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitNewProject()
                  if (e.key === 'Escape') cancelNewProject()
                }}
                onBlur={commitNewProject}
                placeholder="Project name…"
                aria-label="Project name"
                className="h-7 min-w-0 flex-1 rounded border border-rule-strong bg-paper-3 px-2 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent"
              />
              <button type="button" onClick={commitNewProject} aria-label="Create project" className={`${ICON_BUTTON} h-6 w-6 text-accent`}><Check size={13} aria-hidden="true" /></button>
              <button type="button" onClick={cancelNewProject} aria-label="Cancel" className={`${ICON_BUTTON} h-6 w-6 text-ink-3`}><X size={13} aria-hidden="true" /></button>
            </div>
          )}

          {projects.length === 0 && !creatingProject && (
            <p className="px-2.5 py-1 text-[12.5px] text-ink-3">Group questions into a project.</p>
          )}

          {projects.map((project) => {
            const projectConvs = byProject[project.project_id] ?? []
            const isCollapsed = collapsed.has(project.project_id)

            return (
              <div key={project.project_id} className="flex flex-col gap-0.5">
                <div className={`group ${ROW} ${ROW_IDLE} h-8 pr-1.5 pl-2`}>
                  <button
                    type="button"
                    onClick={() => toggleCollapse(project.project_id)}
                    aria-expanded={!isCollapsed}
                    className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left"
                  >
                    <ChevronRight
                      size={13}
                      aria-hidden="true"
                      className={`shrink-0 text-ink-3 transition-transform duration-150 motion-reduce:transition-none ${isCollapsed ? '' : 'rotate-90'}`}
                    />
                    <Folder size={14} aria-hidden="true" className="shrink-0 text-ink-3" />
                    <span className="truncate">{project.name}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteProject(project.project_id)}
                    aria-label={`Delete project ${project.name}`}
                    className={`${ICON_BUTTON} h-6 w-6 text-ink-3 opacity-0 group-hover:opacity-100 hover:text-brick focus-visible:opacity-100`}
                  >
                    <Trash2 size={12} aria-hidden="true" />
                  </button>
                </div>

                {!isCollapsed && (
                  <div className="flex flex-col gap-0.5 pl-4">
                    {projectConvs.length === 0 ? (
                      <p className="px-2.5 py-1 text-[12.5px] text-ink-3">Empty</p>
                    ) : (
                      projectConvs.map((conv) => (
                        <ConversationItem key={conv.session_id} conv={conv} {...itemProps} />
                      ))
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* ── Recent questions ──────────────────────────────────────────── */}
        <div className="mt-3.5 flex h-7 items-center px-2.5">
          <span className="caps text-ink-3">Recent</span>
        </div>
        {ungrouped.length === 0 ? (
          <p className="px-2.5 py-1 text-[12.5px] text-ink-3">
            {conversations.length === 0 ? 'Questions you ask will be kept here.' : 'Everything is filed under a project.'}
          </p>
        ) : (
          <div className="flex flex-col gap-0.5">
            {ungrouped.map((conv) => (
              <ConversationItem key={conv.session_id} conv={conv} {...itemProps} />
            ))}
          </div>
        )}
      </nav>

      {/* Sign out, with the theme switch beside it */}
      <div className="flex items-center gap-1 border-t border-rule px-3 pt-2 pb-3">
        <button
          type="button"
          onClick={logout}
          className={`${ROW} h-[34px] px-2.5 text-ink-2 hover:bg-paper-3 hover:text-ink`}
        >
          <LogOut size={15} aria-hidden="true" className="text-ink-3" />
          Sign out
        </button>
        <ThemeToggle className="-mr-1" />
      </div>
    </aside>
  )
}

// ─── ConversationItem ─────────────────────────────────────────────────────────

interface ConversationItemProps {
  conv: Conversation
  activeSessionId: string | null
  editingId: string | null
  editValue: string
  editInputRef: React.RefObject<HTMLInputElement | null>
  projects: Project[]
  onNavigate: (sid: string) => void
  onStartEdit: (conv: Conversation) => void
  onEditChange: (v: string) => void
  onCommitRename: () => void
  onCancelEdit: () => void
  onAssign: (sessionId: string, projectId: string | null) => void
  onDelete: (sessionId: string) => void
}

function ConversationItem({
  conv, activeSessionId, editingId, editValue, editInputRef,
  projects, onNavigate, onStartEdit, onEditChange,
  onCommitRename, onCancelEdit, onAssign, onDelete,
}: ConversationItemProps) {
  const isActive = conv.session_id === activeSessionId
  const isEditing = editingId === conv.session_id

  if (isEditing) {
    return (
      <div className={`${ROW} h-[34px] px-2`}>
        <input
          ref={editInputRef}
          value={editValue}
          onChange={(e) => onEditChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onCommitRename()
            if (e.key === 'Escape') onCancelEdit()
          }}
          onBlur={onCommitRename}
          aria-label="Conversation title"
          className="h-7 min-w-0 flex-1 rounded border border-rule-strong bg-paper-3 px-2 text-[13px] text-ink outline-none focus:border-accent"
        />
        <button type="button" onClick={onCommitRename} aria-label="Save title" className={`${ICON_BUTTON} h-6 w-6 text-accent`}><Check size={13} aria-hidden="true" /></button>
        <button type="button" onClick={onCancelEdit} aria-label="Cancel" className={`${ICON_BUTTON} h-6 w-6 text-ink-3`}><X size={13} aria-hidden="true" /></button>
      </div>
    )
  }

  // The actions overlay the end of the row on hover, and stay while any of
  // them has keyboard focus, so the title keeps the full width until then.
  // They also stay while the project menu is open: the menu renders outside
  // the row, and Headless UI closes it as soon as its button is hidden.
  const actionClass = `${ICON_BUTTON} h-6 w-6 text-ink-3`
  const overlayClass = `absolute inset-y-0 right-1 hidden items-center gap-0.5 pl-5 group-hover:flex group-focus-within:flex has-data-open:flex bg-linear-to-l to-transparent ${
    isActive ? 'from-accent-soft from-70%' : 'from-paper-3 from-70%'
  }`

  return (
    <div className={`group relative ${ROW} h-[34px] pr-2 pl-2.5 ${isActive ? ROW_ACTIVE : ROW_IDLE}`}>
      <MessageCircleQuestionMark size={14} aria-hidden="true" className={`shrink-0 ${isActive ? 'text-accent' : 'text-ink-3'}`} />
      <button
        type="button"
        onClick={() => onNavigate(conv.session_id)}
        aria-current={isActive ? 'page' : undefined}
        title={conv.title}
        className="min-w-0 flex-1 cursor-pointer truncate text-left"
      >
        {conv.title}
      </button>

      <div className={overlayClass}>
        <button
          type="button"
          onClick={() => onStartEdit(conv)}
          aria-label={`Rename ${conv.title}`}
          className={`${actionClass} hover:text-ink`}
        >
          <Pencil size={12} aria-hidden="true" />
        </button>

        {projects.length > 0 && (
          <Menu as="div" className="relative flex">
            <MenuButton
              title="Move to project"
              aria-label={`Move ${conv.title} to a project`}
              className={`${actionClass} hover:text-accent data-open:opacity-100`}
            >
              <FolderOpen size={12} aria-hidden="true" />
            </MenuButton>
            <MenuItems
              anchor="bottom end"
              className="z-50 w-48 rounded-lg border border-rule-strong bg-paper-3 py-1 text-[13px] shadow-float focus:outline-none"
            >
              {conv.project_id && (
                <MenuItem>
                  <button
                    type="button"
                    onClick={() => onAssign(conv.session_id, null)}
                    className="w-full cursor-pointer px-3 py-2 text-left text-ink-2 data-focus:bg-paper-2 data-focus:text-ink"
                  >
                    Remove from project
                  </button>
                </MenuItem>
              )}
              {projects.map((p) => {
                const current = conv.project_id === p.project_id
                return (
                  <MenuItem key={p.project_id}>
                    <button
                      type="button"
                      onClick={() => onAssign(conv.session_id, p.project_id)}
                      className={`flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left data-focus:bg-paper-2 ${
                        current ? 'font-medium text-accent-ink' : 'text-ink'
                      }`}
                    >
                      <span className="flex w-3.5 shrink-0 justify-center">
                        {current && <Check size={12} aria-hidden="true" />}
                      </span>
                      <span className="truncate">{p.name}</span>
                    </button>
                  </MenuItem>
                )
              })}
            </MenuItems>
          </Menu>
        )}

        <button
          type="button"
          onClick={() => onDelete(conv.session_id)}
          aria-label={`Delete ${conv.title}`}
          className={`${actionClass} hover:text-brick`}
        >
          <Trash2 size={12} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
