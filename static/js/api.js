// One helper for every call: a timeout, a non-JSON error page or a network failure becomes a
// Retry card, never a crash (plan section 10). A typed server error keeps its friendly message.

const STEP_FAILED = Object.freeze({
  error: "step_failed",
  message: "This step could not finish. Your earlier work is kept.",
});

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function isTypedError(data) {
  return data !== null && typeof data === "object" && typeof data.error === "string";
}

export async function callApi(url, body) {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await readJson(response);
    if (isTypedError(data)) return data;
    if (!response.ok || data === null) return STEP_FAILED;
    return data;
  } catch {
    return STEP_FAILED;
  }
}

export async function getJson(url) {
  try {
    const response = await fetch(url);
    return response.ok ? await readJson(response) : null;
  } catch {
    return null;
  }
}
