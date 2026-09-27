import { beforeEach, describe, expect, it } from 'vitest'
import { browserId } from './client'
import { CLIENT_ID_KEY } from '../config'

describe('browserId', () => {
  beforeEach(() => localStorage.clear())

  it('makes a 32-digit hex id once and keeps returning it', () => {
    const first = browserId()
    expect(first).toMatch(/^[0-9a-f]{32}$/)
    expect(browserId()).toBe(first)
    expect(localStorage.getItem(CLIENT_ID_KEY)).toBe(first)
  })

  it('replaces a stored value the server would reject', () => {
    localStorage.setItem(CLIENT_ID_KEY, 'not-an-id')
    const id = browserId()
    expect(id).toMatch(/^[0-9a-f]{32}$/)
    expect(localStorage.getItem(CLIENT_ID_KEY)).toBe(id)
  })
})
