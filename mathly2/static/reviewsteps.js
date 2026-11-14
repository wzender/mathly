// The steps of an AI review while it runs (board-review): what the server has done so far, as a short list that grows, and the time since
// it started. Shown on the student's result and on the teacher's "בדיקת דרך" screen; both ask the server again every few seconds.
import { esc } from "./math.js";

const boards = n => n === 1 ? "לוח אחד" : `${n} לוחות`;

/** The lines: the boards found, how many questions are checked, the one being checked now (or the AI busy), the summary. */
function lines(review) {
  const events = (review.events || []).filter(e => e.step !== "resumed");
  if (!events.length) return [["now", "⏳", "מתחילים…"]];
  const out = [], last = events[events.length - 1];
  const boardsEv = events.find(e => e.step === "boards");
  if (boardsEv) out.push(["done", "📋", `נמצאו ${boards(boardsEv.count)} עם דרך (מתוך ${boardsEv.total} שאלות)`]);
  const current = [...events].reverse().find(e => e.step === "question");
  if (current) {
    const done = current.i - 1, all = current.of;
    if (done) out.push(["done", "🔍", `נבדקו ${done} מתוך ${all}`]);
    const writing = events.some(e => e.step === "summary");
    if (!writing) out.push(["now", "🔍", `בודקים את שאלה ${current.n} (${current.i} מתוך ${all})…`]);
    else out.push(["done", "🔍", `נבדקו כל ${all} השאלות`]);
  }
  if (last.step === "busy") out.push(["now", "☕", `ה־AI עמוס כרגע. ממשיכים בעוד ${last.seconds} שניות`]);
  if (events.some(e => e.step === "summary")) out.push([last.step === "busy" ? "done" : "now", "✍️", "כותבים סיכום קצר…"]);
  if (last.step === "busy" && out.length > 1) {                                       // while waiting, the step before it is not "now"
    const prev = out[out.length - 2];
    if (prev[0] === "now") prev[0] = "wait";
  }
  return out;
}

/** How far along: the questions checked out of all of them (0..1), or null before the first. */
function share(review) {
  const current = [...(review.events || [])].reverse().find(e => e.step === "question");
  if (!current) return null;
  return (review.events.some(e => e.step === "summary") ? current.of : current.i - 1) / current.of;
}

const since = at => Math.max(0, Math.round((Date.now() - new Date(at)) / 1000));
const elapsed = secs => secs < 60 ? `${secs} שניות` : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")} דקות`;

/** The steps as HTML: a list, then "running for … (usually under a minute)". */
export function stepsHtml(review) {
  const at = review.at, part = share(review);
  return `${part === null ? "" : `<div class="rv-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(part * 100)}"><i style="width:${Math.round(part * 100)}%"></i></div>`}
    <ol class="plain rv-steps" aria-live="polite">${lines(review).map(([state, icon, text]) =>
    `<li class="rv-${state}"><span aria-hidden="true">${state === "now" ? `<span class="spin"></span>` : state === "wait" ? "⏸" : icon}</span> ${text}${state === "done" ? ' <span class="rv-ok" aria-hidden="true">✓</span>' : ""}</li>`).join("")}</ol>
    ${at ? `<p class="muted rv-time">כבר <span class="rv-elapsed" data-since="${esc(at)}">${elapsed(since(at))}</span> · בדרך כלל פחות מדקה</p>` : ""}`;
}

setInterval(() => document.querySelectorAll(".rv-elapsed[data-since]").forEach(el => { el.textContent = elapsed(since(el.dataset.since)); }), 1000);
