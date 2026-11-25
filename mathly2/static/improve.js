// "📈 איך מעלים את הציון?" (home.js): a sheet with the ways to raise the nearest test's estimated grade, each with what it does and a
// link straight to it: keep the grade with today's mission, the rounds that add the most (forecast.boost, with their points), closing
// the gaps, a practice test and the simulation (their answers count double), and quick practice.
import { esc, fmt } from "./math.js";

let layer = null;

export function close() {
  layer?.remove();
  layer = null;
  document.removeEventListener("keydown", onKey);
}

function onKey(event) { if (event.key === "Escape") close(); }

const item = (href, icon, title, why, chip = "", extra = "") => `<li><a class="imp-item${extra}" href="${esc(href)}">
    <span class="imp-icon" aria-hidden="true">${icon}</span><span class="grow"><b>${title}</b><small>${why}</small></span>
    ${chip ? `<span class="imp-chip">${chip}</span>` : ""}</a></li>`;

/** `test`: the home's nearest test card (with forecast.held and forecast.boost); `data`: the home (behind lessons, quick practice). */
export function open(test, data) {
  close();
  const f = test.forecast, h = f.held || { grade: f.grade, need: 0, done: 0, safe: true }, boost = f.boost || { rounds: [] };
  const names = Object.fromEntries([...(test.lessons || []), ...(data.map?.lessons || [])].map(l => [l.id, l.name]));
  const byLesson = new Map();
  for (const r of boost.rounds || []) byLesson.set(r.lesson, (byLesson.get(r.lesson) || 0) + r.gain);
  const best = [...byLesson.keys()][0] || data.map?.current || data.map?.next;
  const total = [...byLesson.values()].reduce((a, b) => a + b, 0);
  const keep = test.days_left <= 0 ? "" : item(best ? `#/round/${encodeURIComponent(best)}` : "#/onthego", h.safe ? "✅" : "🎯",
    h.safe ? "המשימה של היום הושלמה" : "המשימה של היום",
    h.safe ? "הציון נשמר להיום. כל סבב נוסף רק מעלה." : `${Math.min(h.done, h.need)}/${h.need} תשובות. בלעדיה הציון יורד מחר ל־${h.tomorrow}.`,
    h.safe ? "✓" : `${h.need - Math.min(h.done, h.need)} נשארו`, h.safe ? " done" : " urgent");
  const rounds = [...byLesson].map(([lesson, gain]) => item(`#/round/${encodeURIComponent(lesson)}`, "▶", `סבב ב${fmt(names[lesson] || "שיעור")}`,
    "10 שאלות בנושא שהכי מעלה את הציון", `<bdi dir="ltr">+${gain}</bdi>`)).join("");
  const behind = data.behind || [];
  layer = document.createElement("div");
  layer.className = "mx-layer fb-layer imp-layer";
  layer.innerHTML = `<div class="mx-scrim" data-close></div>
    <div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="imp-title">
      <div class="mx-shtop"><h3 id="imp-title">📈 איך מעלים את הציון?</h3><div class="mx-shacts"><button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>
      <p class="imp-now">עכשיו <b>${h.grade}</b>${total ? ` · עם הסבבים כאן אפשר להגיע ל־<b class="imp-up">${Math.min(100, h.grade + total)}</b>` : ""}</p>
      <ul class="plain imp-list" id="imp-list">
        ${keep}
        ${rounds ? `<li class="imp-head">הכי משתלם עכשיו</li>${rounds}` : ""}
        ${behind.length ? item("#/gaps", "🧩", "השלמת פערים", `${behind.length === 1 ? "שיעור אחד בפיגור" : `${behind.length} שיעורים בפיגור`}: מעל 90 והשיעור נסגר`, `${5 * behind.length} שאלות`) : ""}
        <li class="imp-head">כמו במבחן</li>
        ${item(`#/test/${test.id}/practice`, "📝", "מבחן תרגול", "התשובות במבחן תרגול נספרות כפול בציון המשוער")}
        ${item(`#/sim/${test.id}${test.simulation?.open ? `/${esc(test.simulation.open)}` : ""}`, "⏱", "מבחן סימולציה", "הכי קרוב למבחן האמיתי: זמן, אורך ורמת קושי")}
        ${data.onthego >= 10 ? `<li class="imp-head">גם כשאין זמן</li>${item("#/onthego", "⚡", "תרגול מהיר", "10 שאלות בלי לוח, נספרות למשימה היומית")}` : ""}
      </ul></div>`;
  document.body.append(layer);
  layer.addEventListener("click", event => { if (event.target.closest("[data-close]") || event.target.closest("a[href]")) close(); });
  document.addEventListener("keydown", onKey);
  layer.querySelector(".imp-item")?.focus({ preventScroll: true });
}
