const API_BASE = "http://localhost:8000/api/v1";

export async function checkSystemHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return await response.json();
  } catch (error) {
    console.error("Health check failed:", error);
    return { status: "disconnected", ollama_connected: false };
  }
}

export async function submitInquiry({ message, userPosition, confidence = 0.5, userId = "default_researcher" }) {
  const payload = {
    user_id: userId,
    message: message,
    user_position: userPosition || null,
    confidence: parseFloat(confidence)
  };

  const response = await fetch(`${API_BASE}/dialogue/inquire`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.message || "Failed to process inquiry");
  }

  return await response.json();
}