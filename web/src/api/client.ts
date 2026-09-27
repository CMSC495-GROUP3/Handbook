/**
 * Axios client configured for the FastAPI backend.
 *
 * The request interceptor runs before every API call and automatically
 * attaches the JWT from localStorage as a Bearer token header.
 * This way no individual API function has to think about auth.
 *
 * The response interceptor handles 401s globally — if the token expires
 * mid-session, the user gets sent back to the login page automatically.
 * Login POSTs are excluded: a wrong password is also a 401, and the form
 * must show "Incorrect password." instead of being navigated away.
 */
import axios from 'axios'
import { HR_CRED, MANAGER_CRED, TOKEN_KEY } from '../config'

export { TOKEN_KEY }

const LOGIN_PATH = '/api/auth/login'

const client = axios.create({
  // In dev, Vite proxies /api → localhost:8000 (see vite.config.ts).
  // In production, Nginx handles the same routing — so this baseURL works in both environments.
  baseURL: '/',
})

/** Clear the stored JWT and return to the sign-in page. */
export function signOut(): void {
  localStorage.removeItem(TOKEN_KEY)
  window.location.href = '/'
}

/**
 * The payload of a JWT, decoded but not verified, or null if it will not parse.
 * The browser has no signing key; the server checks every token it is sent.
 */
function readClaims(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = (4 - (b64.length % 4)) % 4
    const claims: unknown = JSON.parse(atob(b64 + '='.repeat(pad)))
    return claims && typeof claims === 'object' ? (claims as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/**
 * True when `token` is expired, malformed, or missing an `exp` claim.
 */
export function isTokenExpired(token: string): boolean {
  const exp = readClaims(token)?.exp
  if (typeof exp !== 'number') return true
  return exp * 1000 <= Date.now()
}

/**
 * True when the stored token was issued for the HR password. This only decides
 * which links to show: the server answers 403 to any other token on the HR
 * routes, whatever the client shows.
 */
export function isHrSession(): boolean {
  return storedCred() === HR_CRED
}

/**
 * True when the stored token was issued for the manager password. Like
 * isHrSession, this only decides which links to show.
 */
export function isManagerSession(): boolean {
  return storedCred() === MANAGER_CRED
}

function storedCred(): unknown {
  const token = localStorage.getItem(TOKEN_KEY)
  return token === null ? undefined : readClaims(token)?.cred
}

function isLoginRequest(url: string | undefined): boolean {
  if (!url) return false
  // Match /api/auth/login with optional query string; avoid prefix false-positives.
  try {
    const path = url.includes('://') ? new URL(url).pathname : url.split('?')[0]
    return path === LOGIN_PATH || path.endsWith(LOGIN_PATH)
  } catch {
    return url.includes(LOGIN_PATH)
  }
}

// Attach JWT to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On 401, clear the stored token and reload to the login page —
// except for the login route itself (wrong password is also a 401).
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !isLoginRequest(error.config?.url)
    ) {
      signOut()
    }
    return Promise.reject(error)
  }
)

export default client
