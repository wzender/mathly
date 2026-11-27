import { track } from "./busy.js";
import { onSignOut, token } from "./session.js";

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

const MESSAGES = { 503: "שירות ההתחברות לא זמין כרגע, נסו שוב בעוד רגע", 403: "אין הרשאה לפעולה הזו" };
const UPDATING = "האתר מתעדכן כרגע. נסו שוב בעוד דקה.";

// While the site is being updated (Hugging Face builds and restarts it), the host answers 502/503/504 without our JSON, or the connection
// fails: the request never reached the server, so it is sent again, also a change, a few times over about half a minute, with a note.
const RETRY_DELAYS = () => window.__retryDelays || [1000, 2000, 4000, 8000, 15000];
let waiting = 0;
function updatingNote(on) {
  waiting = Math.max(0, waiting + (on ? 1 : -1));
  let note = document.getElementById("updating-note");
  if (waiting && !note) {
    note = Object.assign(document.createElement("p"), { id: "updating-note", className: "updating-note", textContent: "⏳ האתר מתעדכן, עוד רגע…" });
    note.setAttribute("role", "status");
    document.body.append(note);
  }
  if (!waiting) note?.remove();
}
const hostAnswer = response => [502, 503, 504].includes(response.status) && !(response.headers.get("content-type") || "").includes("application/json");

async function send(path, init) {
  const delays = RETRY_DELAYS();
  for (let attempt = 0; ; attempt++) {
    let response = null;
    try { response = await fetch(path, init); } catch { response = null; }        // no connection: the server is restarting
    if (response && !hostAnswer(response)) { if (attempt) updatingNote(false); return response; }
    if (attempt >= delays.length) { if (attempt) updatingNote(false); throw new ApiError(503, UPDATING); }
    if (!attempt) updatingNote(true);
    await new Promise(done => setTimeout(done, delays[attempt]));
  }
}

const remembered = new Map();                    // GET path -> the last answer
const VIEW_KEY = "mathly2.view-class";

/** "תצוגה ככיתה": the class a developer or a teacher who is in no class sees the student screens as (kept on this device). */
export const viewClass = () => { try { return localStorage.getItem(VIEW_KEY) || ""; } catch { return ""; } };
export function setViewClass(id) {
  try { if (id) localStorage.setItem(VIEW_KEY, String(id)); else localStorage.removeItem(VIEW_KEY); } catch { /* private window */ }
  remembered.clear(); changes++;                 // every screen is now about another class
}
let changes = 0;                                 // counts changes, so an answer to a read that began before one is not kept
onSignOut(() => { remembered.clear(); changes++; });

// After an update the server answers with a new build: the page's styles and scripts are old, so the app reloads itself at the next
// change of screen (never in the middle of a question). The page's own build is in its config (main.py build_of).
const PAGE_BUILD = (() => { try { return JSON.parse(document.getElementById("config")?.textContent || "{}").build || ""; } catch { return ""; } })();
let stale = false;
function noticeBuild(build) {
  if (!build || !PAGE_BUILD || build === PAGE_BUILD || stale) return;
  stale = true;
  window.addEventListener("hashchange", () => location.reload(), { once: true });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") location.reload(); }, { once: true });
}

async function request(path, { method = "GET", body } = {}) {
  const started = changes;
  if (method !== "GET") { remembered.clear(); changes++; }      // after a change of theirs, no old answer is ever shown
  const headers = { Authorization: "Bearer " + await token() };
  if (viewClass()) headers["X-View-Class"] = viewClass();
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await send(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  noticeBuild(response.headers.get("X-Mathly-Build"));
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
