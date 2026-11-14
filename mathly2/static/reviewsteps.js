// The steps of an AI review while it runs (board-review): what the server has done so far, as a short list that grows, and the time since
// it started. Shown on the student's result and on the teacher's "בדיקת דרך" screen; both ask the server again every few seconds.
import { esc } from "./math.js";

const boards = n => n === 1 ? "לוח אחד" : `${n} לוחות`;

/** One line per step; the last one is the one happening now. */
function lines(review) {
  const events = review.events || [];
  if (!events.length) return [["now", "⏳", "מתחילים…"]];
  return events.map((e, i) => {
    const last = i === events.length - 1;
    if (e.step === "boards") return ["done", "📋", `נמצאו ${boards(e.count)} עם דרך (מתוך ${e.total} שאלות)`];
    if (e.step === "busy") return [last ? "now" : "done", "☕", last ? `ה־AI עמוס כרגע. מנסים שוב בעוד ${e.seconds} שניות` : "ה־AI היה עמוס, ניסינו שוב"];
    if (e.step === "sent") return [last ? "now" : "done", last ? "🔍" : "📤", last ? "ה־AI קורא את הלוחות ובודק את הדרך, שאלה אחרי שאלה…" : "נשלח ל־AI"];
    return ["done", "•", esc(e.step)];
  });
}

const since = at => Math.max(0, Math.round((Date.now() - new Date(at)) / 1000));
const elapsed = secs => secs < 60 ? `${secs} שניות` : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")} דקות`;

/** The steps as HTML: a list, then "running for … (usually under a minute)". */
export function stepsHtml(review) {
  const at = review.at;
  return `<ol class="plain rv-steps" aria-live="polite">${lines(review).map(([state, icon, text]) =>
    `<li class="rv-${state}"><span aria-hidden="true">${state === "now" ? `<span class="spin"></span>` : icon}</span> ${text}${state === "done" ? ' <span class="rv-ok" aria-hidden="true">✓</span>' : ""}</li>`).join("")}</ol>
    ${at ? `<p class="muted rv-time">כבר <span class="rv-elapsed" data-since="${esc(at)}">${elapsed(since(at))}</span> · בדרך כלל פחות מדקה</p>` : ""}`;
}

setInterval(() => document.querySelectorAll(".rv-elapsed[data-since]").forEach(el => { el.textContent = elapsed(since(el.dataset.since)); }), 1000);
