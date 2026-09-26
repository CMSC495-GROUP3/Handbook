import { isHrSession, signOut } from '../api/client'

export function useAuth() {
  function logout() {
    signOut()
  }

  // Read on every render rather than kept in state: signing in or out swaps
  // the stored token and re-renders or reloads the app anyway.
  return { logout, isHr: isHrSession() }
}
