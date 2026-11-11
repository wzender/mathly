// Photo help for a student (STU-6): a sheet to photograph a problem and send it to the teacher, then follow the request: waiting, being
// worked on, and then the AI's hints one at a time (the steps and the answer only when asked), or the teacher's note.
import { api } from "./api.js";
import { currentSubject } from "./ui.js";
import { esc, fmt } from "./math.js";
import { isTouch, prepare, pictureUrl, sendPicture } from "./media.js";

let layer = null, timer = null, shown = { hints: 1, works: new Set(), answer: false };
let statusPromise = null, statusAt = 0;

/** {on, requests}: whether the student's classes have the AI on, and their latest requests. Remembered for a minute. */
export function status(fresh = false) {
  if (!statusPromise || fresh || Date.now() - statusAt > 60000) {
    statusAt = Date.now();
    statusPromise = api("/api/ai/status").catch(() => ({ on: false, requests: [] }));
  }
  return statusPromise;
}

const STATE = { waiting: "ממתין למורה", processing: "ה־AI עובד על זה", done: "מוכן", declined: "המורה לא שלח/ה", cancelled: "בוטל", failed: "לא הצלחנו", closed: "טופל" };
export const stateWord = state => STATE[state] || state;

const q = selector => layer?.querySelector(selector);
const reminderSeen = () => { try { return localStorage.getItem("ai-reminder") === "1"; } catch { return false; } };
const seenReminder = () => { try { localStorage.setItem("ai-reminder", "1"); } catch { /* private window */ } };

function mount() {
  if (layer) return;
  layer = document.createElement("div");
  layer.className = "ai-window";
  layer.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="ai-title"></div>`;
  document.body.append(layer);
  layer.addEventListener("click", event => { if (event.target === layer || event.target.closest("[data-ai-close]")) close(); });
}

export function close() {
  clearTimeout(timer);
  timer = null;
  layer?.remove();
  layer = null;
}

const body = html => { q(".sheet").innerHTML = `<div class="ai-top"><h3 id="ai-title">עזרה מתמונה</h3><button type="button" class="mx-x" data-ai-close aria-label="סגירה">✕</button></div>${html}`; };

/** The first step: the reminder, and choosing or taking the photo. `context`: { skillId, classId } of where it was opened. */
export async function openNew(context = {}) {
  mount();
  body(`<p class="ex-note" role="note">המורה רואה את התמונה לפני שהיא נשלחת ל־AI, ולכן התשובה לא מגיעה מיד.</p>
    <p class="muted">אל תכתבו שם או פרטים אישיים בתמונה.</p>
    <p class="actions">${isTouch() ? `<label class="button file primary">📷 צילום<input type="file" accept="image/*" capture="environment" hidden data-ai-file></label>` : ""}
      <label class="button file">🖼 בחירת תמונה<input type="file" accept="image/jpeg,image/png,image/webp" hidden data-ai-file></label></p>
    <div id="ai-preview"></div><p class="error" id="ai-error" role="alert" hidden></p>`);
  let chosen = null;
  layer.querySelectorAll("[data-ai-file]").forEach(input => input.addEventListener("change", async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    chosen = await prepare(file);
    q("#ai-preview").innerHTML = `<img id="ai-img" alt="התמונה שבחרתם" src="${URL.createObjectURL(chosen)}"><p><button type="button" class="primary" id="ai-send">שליחה למורה</button></p>`;
    q("#ai-send").addEventListener("click", async () => {
      const button = q("#ai-send");
      button.disabled = true;
      try {
        seenReminder();
        const params = new URLSearchParams(Object.entries({ skill_id: context.skillId, class_id: context.classId,
          subject: context.skillId ? "" : currentSubject() }).filter(([, v]) => v));          // from home: the subject whose home it is
        const made = await sendPicture(`/api/ai/photo${params.size ? `?${params}` : ""}`, chosen);
        status(true);
        follow(made.id);
      } catch (error) {
        button.disabled = false;
        q("#ai-error").textContent = error.message;
        q("#ai-error").hidden = false;
      }
    });
  }));
}

/** Follow a request: draw its state and look again every few seconds while it is waiting or being worked on. */
export async function follow(id) {
  mount();
  clearTimeout(timer);
  let request;
  try { request = await api(`/api/ai/requests/${encodeURIComponent(id)}`); } catch (error) { body(`<p class="error" role="alert">${esc(error.message)}</p>`); return; }
  if (!layer) return;
  draw(request);
  if (["waiting", "processing"].includes(request.state)) timer = setTimeout(() => layer && follow(id), 4000);
}

function draw(request) {
  const photo = request.picture ? `<p><img id="ai-photo" alt="התמונה ששלחתם" hidden></p>` : "";
  let content = `<p id="ai-state" role="status"><span class="tag st-${esc(request.state)}">${esc(stateWord(request.state))}</span></p>${photo}`;
  if (request.state === "waiting") content += `<p class="muted">המורה רואה את התמונה ומחליט/ה אם לשלוח אותה. אפשר לסגור, והבקשה תחכה.</p><p><button type="button" id="ai-cancel">ביטול הבקשה</button></p>`;
  if (request.state === "processing") content += `<p class="muted">המורה שלח/ה את התמונה. עוד רגע התשובה כאן.</p>`;
  if (request.state === "declined") content += `<p id="ai-note"><b>המורה:</b> ${request.teacher_note ? fmt(request.teacher_note) : "לא נשלח. אפשר לשאול את המורה."}</p>`;
  if (request.state === "failed") content += `<p class="error" role="alert" id="ai-failed">${esc(request.failure?.message || "לא הצלחנו כרגע. נסו שוב מאוחר יותר.")}</p>`;
  if (request.state === "done") content += result(request);
  body(content);
  if (request.picture) pictureUrl(request.picture.id).then(url => { const img = q("#ai-photo"); if (img) { img.src = url; img.hidden = false; } }).catch(() => {});
  q("#ai-cancel")?.addEventListener("click", async () => { await api(`/api/ai/requests/${request.id}/cancel`, { method: "POST" }); status(true); follow(request.id); });
  layer.querySelectorAll("[data-more]").forEach(b => b.addEventListener("click", () => { reveal(request, b.dataset.more, Number(b.dataset.i)); }));
}

function result(request) {
  const r = request.result;
  if (!r.readable) return `<p id="ai-unreadable" role="status">${fmt(r.note || "לא הצלחנו לקרוא את התמונה. צלמו שוב.")}</p>`;
  const steps = r.steps || [];
  const hints = steps.slice(0, shown.hints).map((s, i) => `<li data-step="${i}"><p class="ai-hint">💡 ${fmt(s.hint)}</p>
    ${shown.works.has(i) ? `<p class="ai-work">${fmt(s.work)}</p>` : `<button type="button" data-more="work" data-i="${i}">הצגת הצעד</button>`}</li>`).join("");
  const nextHint = shown.hints < steps.length ? `<button type="button" data-more="hint" data-i="0" id="ai-next-hint">רמז נוסף</button>` : "";
  const answer = shown.answer ? `<p id="ai-answer"><b>התשובה:</b> ${fmt(r.answer)}</p>` : `<button type="button" data-more="answer" data-i="0" id="ai-show-answer">הצגת התשובה</button>`;
  const skill = r.skill ? `<p class="muted">המיומנות במסלול: <a href="#/skill/${esc(r.skill.id)}" data-ai-close>${fmt(r.skill.name)}</a></p>` : "";
  return `<p class="muted">כך קראנו את התרגיל: ${fmt(r.problem)}</p>${r.note ? `<p class="ex-note">${fmt(r.note)}</p>` : ""}<ol class="plain ai-steps" id="ai-steps">${hints}</ol>
    <p class="actions">${nextHint}</p><p>${answer}</p>${skill}`;
}

function reveal(request, what, i) {
  if (what === "hint") shown.hints += 1;
  if (what === "work") shown.works.add(i);
  if (what === "answer") shown.answer = true;
  draw(request);
}

/** Open the sheet for a request (a new photo when `id` is not given); the hints start closed each time. */
export function open({ id = null, skillId = null, classId = null } = {}) {
  shown = { hints: 1, works: new Set(), answer: false };
  return id ? follow(id) : openNew({ skillId, classId });
}

export const isOpen = () => !!layer;
