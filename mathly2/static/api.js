import { token } from "./session.js";

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

const MESSAGES = { 503: "שירות ההתחברות לא זמין כרגע, נסו שוב בעוד רגע", 403: "אין הרשאה לפעולה הזו" };

export async function api(path, { method = "GET", body } = {}) {
  const headers = { Authorization: "Bearer " + await token() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (response.ok) return response.status === 204 ? null : response.json();
  let detail = "";
  try { detail = (await response.json()).detail; } catch { /* no body */ }
  throw new ApiError(response.status, typeof detail === "string" && detail ? detail : (MESSAGES[response.status] || "משהו השתבש, נסו שוב"));
}
