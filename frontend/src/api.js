export async function api(path, options) {
  const response = await fetch(`/api${path}`, options)
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
