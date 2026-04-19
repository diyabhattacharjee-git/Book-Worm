// In dev, vite proxies /api → localhost:5000
// In production, set VITE_API_URL env variable to your backend URL
const API_BASE = import.meta.env.VITE_API_URL || "/api";

/**
 * Send a chat message to the backend.
 * Returns the full response object: { response, stores, recommendations,
 * recommendations_with_links, agent_insights, comparison }
 */
export async function sendMessage(message, session_id) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id }),
  });

  if (!res.ok) {
    throw new Error(`Server error: ${res.status}`);
  }

  const data = await res.json();
  return data;
}

/**
 * Reset current chat session on the backend.
 */
export async function resetChat(session_id) {
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id }),
  });
}

/**
 * Health-check endpoint.
 */
export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
