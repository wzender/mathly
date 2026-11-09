// The teacher's AI tab (TCH-5): the requests of my students waiting for me (a photographed problem, or a check of a handed-in answer), which I send
// to the AI or decline with a note; a batch sends many at once; what is being worked on, what failed and why; and my own photo help.
import { api } from "./api.js";
import { withBusy } from "./busy.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { pictureUrl, prepare, sendPicture } from "./media.js";

let timer = null;
const KIND = { photo: "תמונה של תרגיל", check: "בדיקת תשובה" };
const who = email => esc((email || "").split("@")[0] || "תלמיד/ה");

function waitingItem(i) {
  const what = i.kind === "photo" ? `${KIND.photo}${i.skill ? ` · ${fmt(i.skill.name)}` : ""}` : `${KIND.check} · ${fmt(i.assignment.title)}`;
  return `<li class="card ai-item" data-request="${esc(i.id)}" data-kind="${esc(i.kind)}"><p><b>${who(i.student)}</b> · ${what}<br><span class="muted">${esc(i.class?.name || "")}</span></p>
    ${i.picture ? `<img data-picture="${esc(i.picture.id)}" alt="התמונה שהתלמיד/ה שלח/ה" hidden>` : ""}
    <p class="actions"><button type="button" class="primary" data-send="${esc(i.id)}">שליחה ל־AI</button>
      <button type="button" data-decline-open="${esc(i.id)}">דחייה</button></p>
    <div class="decline" data-decline="${esc(i.id)}" hidden><label>הערה לתלמיד/ה (לא חובה)<input maxlength="500" data-note></label>
      <button type="button" data-decline-confirm="${esc(i.id)}">אישור הדחייה</button></div></li>`;
}

function otherItem(i) {
  const head = `<b>${who(i.student)}</b> · ${i.kind === "photo" ? KIND.photo : `${KIND.check} · ${fmt(i.assignment.title)}`}`;
  if (i.state === "processing") return `<li data-request="${esc(i.id)}" data-state="processing">${head} · <span class="tag st-processing">ה־AI עובד…</span></li>`;
  if (i.state === "failed") return `<li data-request="${esc(i.id)}" data-state="failed" class="ai-failed">${head} · <span class="tag st-failed">נכשל</span>
    <br>${esc(i.failure.label)}. ${esc(i.failure.todo)} <span class="muted" dir="ltr">${esc(i.failure.detail || "")}</span>
    <br><button type="button" data-send="${esc(i.id)}">ניסיון חוזר</button> <button type="button" data-decline-now="${esc(i.id)}">דחייה</button></li>`;
  return `<li data-request="${esc(i.id)}" data-state="done">${head} · <span class="tag st-done">הושלם</span></li>`;
}

function html(ctx, data) {
  const waiting = data.items.filter(i => i.state === "waiting");
  const rest = data.items.filter(i => i.state !== "waiting");
  const photos = waiting.filter(i => i.kind === "photo").length;
  const byAssignment = new Map();
  waiting.filter(i => i.kind === "check").forEach(i => byAssignment.set(i.assignment.id, [i.assignment.title, (byAssignment.get(i.assignment.id)?.[1] || 0) + 1]));
  const budgets = data.classes.map(c => c.ai_enabled
    ? `<li data-class="${c.id}">${esc(c.name)}: נשארו ${Math.max(c.daily - c.used, 0)} מתוך ${c.daily} בדיקות היום</li>` : `<li data-class="${c.id}" class="muted">${esc(c.name)}: ה־AI כבוי (מנהל הכיתות מפעיל)</li>`).join("");
  return `${ctx.tabs("ai")}<section id="ai-queue"><h2>בינה מלאכותית</h2>
    <p class="muted">תלמידים לא פונים ל־AI בעצמם: כל בקשה מחכה לכם. אתם רואים את התמונה ומחליטים אם לשלוח.</p>
    <ul class="plain" id="ai-budgets">${budgets}</ul>
    <p id="ai-message" role="status" class="ex-note" hidden></p>
    ${waiting.length ? `<p class="actions" id="ai-batches">${photos ? `<button type="button" data-batch="photos">שליחת כל התמונות (${photos})</button>` : ""}
      ${[...byAssignment].map(([id, [title, n]]) => `<button type="button" data-batch="assignment" data-assignment="${id}">שליחת כל הבדיקות: ${fmt(title)} (${n})</button>`).join("")}</p>
      <ul class="plain" id="ai-waiting">${waiting.map(waitingItem).join("")}</ul>` : `<p class="muted" id="ai-empty">אין בקשות שמחכות.</p>`}
    ${rest.length ? `<h3>בטיפול, נכשלו והושלמו היום</h3><ul class="plain" id="ai-rest">${rest.map(otherItem).join("")}</ul>` : ""}
    <section class="card"><h3>עזרה מתמונה לעצמי</h3>
      <p class="muted">${data.own ? `נשארו ${Math.max(data.own.allowance - data.own.used, 0)} מתוך ${data.own.allowance} בקשות אישיות היום.` : "למפתחים אין הגבלה."}</p>
      <label class="button file">📷 צילום או בחירת תמונה<input type="file" accept="image/jpeg,image/png,image/webp" hidden id="ai-own-file"></label></section></section>`;
}

export async function show(ctx, notice = "") {
  clearTimeout(timer);
  const data = await api("/api/ai/queue");
  ctx.draw(html(ctx, data));
  ctx.wire();
  const root = document.getElementById("ai-queue");
  if (notice) { const m = root.querySelector("#ai-message"); m.textContent = notice; m.hidden = false; }
  root.querySelectorAll("img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.remove(); } });
  const again = text => show(ctx, text);
  const run = (button, promise, done) => withBusy(button, promise.then(r => again(done ? done(r) : "")).catch(e => again(e.message)));
  root.addEventListener("click", event => {
    const t = event.target.closest("button");
    if (!t) return;
    if (t.dataset.send) return run(t, api(`/api/ai/requests/${t.dataset.send}/send`, { method: "POST" }));
    if (t.dataset.declineOpen) { root.querySelector(`[data-decline="${t.dataset.declineOpen}"]`).hidden = false; return; }
    if (t.dataset.declineConfirm) {
      const note = root.querySelector(`[data-decline="${t.dataset.declineConfirm}"] [data-note]`).value;
      return run(t, api(`/api/ai/requests/${t.dataset.declineConfirm}/decline`, { method: "POST", body: { note } }), () => "הבקשה נדחתה.");
    }
    if (t.dataset.declineNow) return run(t, api(`/api/ai/requests/${t.dataset.declineNow}/decline`, { method: "POST", body: { note: "" } }), () => "הבקשה נדחתה.");
    if (t.dataset.batch) {
      const body = t.dataset.batch === "photos" ? { scope: "photos" } : { scope: "assignment", assignment_id: Number(t.dataset.assignment) };
      return run(t, api("/api/ai/batch", { method: "POST", body }), r => `נשלחו ${r.sent}. ${r.message}`.trim());
    }
  });
  root.querySelector("#ai-own-file").addEventListener("change", async event => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    try {
      const made = await withBusy(event.target.closest("label"), prepare(file).then(blob => sendPicture("/api/ai/photo", blob)));
      aiSheet.open({ id: made.id });
    } catch (e) { again(e.message); }
  });
  if (data.items.some(i => i.state === "processing")) {                                    // look again while something is being worked on
    timer = setTimeout(() => { if (document.getElementById("ai-queue") && !document.activeElement?.matches?.("input, textarea")) show(ctx); }, 4000);
  }
}
