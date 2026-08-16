// All HTTP calls to the backend live here. The frontend never
// computes an answer, ranks anything, or makes a decision -- it only
// sends requests and renders whatever the backend already decided
// (§7 hard rule). Every request now carries the API key (§27).

const BASE_URL = "http://127.0.0.1:8000"
// Must match API_KEY in the backend's .env file.
const API_KEY = "change-me-local-dev-key"
const AUTH_HEADERS = { "X-API-Key": API_KEY }

async function handleResponse(response) {
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }
  return response.json()
}

export const api = {
  chat: (query, sessionId, useWebSearch = false, traceId = null) =>
    fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...AUTH_HEADERS,
        ...(traceId ? { "X-Trace-Id": traceId } : {}),
      },
      body: JSON.stringify({ query, session_id: sessionId, use_web_search: useWebSearch }),
    }).then(handleResponse),

  getTrace: (traceId) =>
    fetch(`${BASE_URL}/trace/${traceId}`, { headers: AUTH_HEADERS }).then(handleResponse),

  chatStream: async (query, onToken, onDone) => {
    const response = await fetch(`${BASE_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
      body: JSON.stringify({ query }),
    })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split("\n\n")
      buffer = events.pop()
      for (const chunk of events) {
        if (chunk.startsWith("event: done")) {
          onDone()
        } else if (chunk.startsWith("data:")) {
          onToken(chunk.slice(5))
        }
      }
    }
  },

  search: (q, topK = 5) =>
    fetch(`${BASE_URL}/search?q=${encodeURIComponent(q)}&top_k=${topK}`, { headers: AUTH_HEADERS }).then(handleResponse),

  research: (question, topK = 5, useWebSearch = false) =>
    fetch(`${BASE_URL}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
      body: JSON.stringify({ question, top_k: topK, use_web_search: useWebSearch }),
    }).then(handleResponse),

  listDocuments: () => fetch(`${BASE_URL}/documents`, { headers: AUTH_HEADERS }).then(handleResponse),
  uploadDocument: (file) => {
    const formData = new FormData()
    formData.append("file", file)
    return fetch(`${BASE_URL}/documents`, { method: "POST", headers: AUTH_HEADERS, body: formData }).then(handleResponse)
  },

  listConcepts: () => fetch(`${BASE_URL}/concepts`, { headers: AUTH_HEADERS }).then(handleResponse),

  listProjects: () => fetch(`${BASE_URL}/projects`, { headers: AUTH_HEADERS }).then(handleResponse),
  createProject: (name, description) =>
    fetch(`${BASE_URL}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
      body: JSON.stringify({ name, description }),
    }).then(handleResponse),

  getSessionHistory: (id) => fetch(`${BASE_URL}/sessions/${id}/history`, { headers: AUTH_HEADERS }).then(handleResponse),

  getSetting: (key) => fetch(`${BASE_URL}/settings/${key}`, { headers: AUTH_HEADERS }).then(handleResponse),
  setSetting: (key, value) =>
    fetch(`${BASE_URL}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
      body: JSON.stringify({ key, value }),
    }).then(handleResponse),
}

