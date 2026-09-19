// Pre-account browser token: generated once and sent as a header so captures
// made before authentication can be claimed. It cannot replace login auth.

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
