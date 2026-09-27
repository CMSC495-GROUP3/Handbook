import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { AxiosResponse } from 'axios'
import client, { TOKEN_KEY } from '../../api/client'
import Sidebar from './Sidebar'

/** An unsigned JWT with the given claims. The client only reads, never verifies. */
function tokenWith(claims: Record<string, unknown>): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const exp = Math.floor(Date.now() / 1000) + 3600
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: 'user', exp, ...claims })}.sig`
}

const HR_LINKS = ['HR Requests', 'What People Ask']

function renderSidebar(isDesktop: boolean, open: boolean) {
  return render(
    <MemoryRouter initialEntries={['/chat']}>
      <Sidebar open={open} isDesktop={isDesktop} onToggle={() => {}} />
    </MemoryRouter>,
  )
}

// The expanded desktop sidebar, the collapsed rail, and the phone drawer.
const LAYOUTS = [
  { name: 'sidebar', isDesktop: true, open: true },
  { name: 'rail', isDesktop: true, open: false },
  { name: 'drawer', isDesktop: false, open: true },
]

describe('Sidebar HR and manager entries', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(client, 'get').mockResolvedValue({ data: [] } as unknown as AxiosResponse)
  })

  it.each(LAYOUTS)('shows them in the $name to an HR session', async ({ isDesktop, open }) => {
    localStorage.setItem(TOKEN_KEY, tokenWith({ cred: 'HR_PASSWORD_HASH' }))
    renderSidebar(isDesktop, open)

    for (const name of HR_LINKS) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: 'Policy Library' })).toBeInTheDocument()
    await waitFor(() => expect(client.get).toHaveBeenCalled())
  })

  it.each(LAYOUTS)('hides them in the $name from an employee session', async ({ isDesktop, open }) => {
    localStorage.setItem(TOKEN_KEY, tokenWith({ cred: 'APP_PASSWORD_HASH' }))
    renderSidebar(isDesktop, open)

    for (const name of HR_LINKS) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: 'Policy Library' })).toBeInTheDocument()
    await waitFor(() => expect(client.get).toHaveBeenCalled())
  })

  it.each(LAYOUTS)('shows a manager session only What People Ask in the $name', async ({ isDesktop, open }) => {
    localStorage.setItem(TOKEN_KEY, tokenWith({ cred: 'MANAGER_PASSWORD_HASH' }))
    renderSidebar(isDesktop, open)

    expect(screen.getByRole('button', { name: 'What People Ask' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'HR Requests' })).not.toBeInTheDocument()
    await waitFor(() => expect(client.get).toHaveBeenCalled())
  })

  it.each([
    ['the reviewer password', tokenWith({ cred: 'APP_PASSWORD_HASH_2' })],
    ['no cred claim', tokenWith({})],
    ['a token that is not a JWT', 'not-a-jwt'],
  ])('hides them for %s', async (_label, token) => {
    localStorage.setItem(TOKEN_KEY, token)
    renderSidebar(true, true)

    for (const name of HR_LINKS) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
    await waitFor(() => expect(client.get).toHaveBeenCalled())
  })
})
