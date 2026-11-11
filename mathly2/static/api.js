import { track } from "./busy.js";
import { onSignOut, token } from "./session.js";

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

const MESSAGES = { 503: "שירות ההתחברות לא זמין כרגע, נסו שוב בעוד רגע", 403: "אין הרשאה לפעולה הזו" };

const remembered = new Map();                    // GET path -> the last answer
let changes = 0;                                 // counts changes, so an answer to a read that began before one is not kept
onSignOut(() => { remembered.clear(); changes++; });

async function request(path, { method = "GET", body } = {}) {
  const started = changes;
  if (method !== "GET") { remembered.clear(); changes++; }      // after a change of theirs, no old answer is ever shown
  const headers = { Authorization: "Bearer " + await token() };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (response.ok) {
    const data = response.status === 204 ? null : await response.json();
    if (method === "GET") { if (started === changes) remembered.set(path, data); }
    else { remembered.clear(); changes++; }
    return data;
  }
  let detail = "";
  try { detail = (await response.json()).detail; } catch { /* no body */ }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {        // {message, problems}: a refusal with its list
    const error = new ApiError(response.status, detail.message);
    error.problems = Array.isArray(detail.problems) ? detail.problems : [];
    throw error;
  }
  throw new ApiError(response.status, typeof detail === "string" && detail ? detail : (MESSAGES[response.status] || "משהו השתבש, נסו שוב"));
}

/** A request to the server. The button that was just pressed shows it is working if the answer takes a moment (busy.js). */
export const api = (path, options) => track(request(path, options));

/** The last answer for this GET path, or undefined (nothing yet, or something was changed since). */
export const lastAnswer = path => remembered.get(path);

let screen = 0;
const busyNow = () => {
  const here = document.activeElement;
  return !!(here && here.matches?.("input, textarea, select, [contenteditable]")) || !!document.querySelector("main details[open], .sheet, dialog[open]");
};

/** Shows a screen: draws `render(data)` at once from the last answer if there is one, then draws again when the fresh answer
 *  differs, unless the person has moved on, is typing, or has something open. Without a last answer it waits, as before.
 *  `path` may be a list: then `render` gets the answers as a list. */
export async function swr(path, render) {
  const paths = Array.isArray(path) ? path : [path], one = !Array.isArray(path);
  const give = list => render(one ? list[0] : list);
  const mine = ++screen, hash = location.hash, before = paths.map(p => remembered.get(p));
  if (before.some(x => x === undefined)) return give(await Promise.all(paths.map(p => api(p))));
  give(before);
  Promise.all(paths.map(p => api(p))).then(fresh => {
    if (mine === screen && hash === location.hash && JSON.stringify(fresh) !== JSON.stringify(before) && !busyNow()) give(fresh);
  }).catch(() => { /* the screen already shows what it knew */ });
}
