// Anonymous session token: generated once, stored locally, sent as a header.
// No account needed; "Delete my data" wipes server-side data and regenerates.

const KEY = 'lifeclip.session'

export function getSessionToken(): string {
  let token = localStorage.getItem(KEY)
  if (!token || !/^[A-Za-z0-9_-]{16,128}$/.test(token)) {
    token = (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, '').slice(0, 48)
    localStorage.setItem(KEY, token)
  }
  return token
}

export function resetSessionToken(): void {
  localStorage.removeItem(KEY)
}
