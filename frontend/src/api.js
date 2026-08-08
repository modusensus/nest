const STORAGE_KEY = 'wb-server-url'

export function getBaseUrl() {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored || ''
}

export function setBaseUrl(url) {
  const trimmed = (url || '').replace(/\/+$/, '')
  if (trimmed) {
    localStorage.setItem(STORAGE_KEY, trimmed)
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export async function api(path, options) {
  const base = getBaseUrl()
  const response = await fetch(`${base}/api${path}`, options)
  if (!response.ok) {
    let message = response.statusText
    try { message = (await response.json()).detail || message } catch { /* 忽略非 JSON 响应 */ }
    throw new Error(message)
  }
  return response.json()
}

export function post(path, body = {}, method = 'POST') {
  return api(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}