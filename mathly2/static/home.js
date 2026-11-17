// The student's home for a subject: one screen, like a game's level select. The stars collected and a big play button for the next lesson,
// every lesson as a small tile with its stars (a round finished, 8 of 10, every skill mastered), the nearest test in one block (the days
// left, the readiness number and the two buttons that raise it: a practice test and a simulation), and small buttons for the new
// assignments and photo help.
import { swr } from "./api.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { backToSubjects, daysText, forSubject, shortDate, tabs } from "./ui.js";

/* ---------- the nearest test: the readiness number, and the two ways to raise it ---------- */

const SEEN = "mathly2.readiness.";
/** The number the student saw last time for this test (to count up from it), and remember the new one. */
function lastSeen(test) {
  let before = null;
  try { before = Number(localStorage.getItem(SEEN + test.id)); localStorage.setItem(SEEN + test.id, String(test.readiness.number)); } catch { /* private window */ }
  return Number.isFinite(before) && before !== null && before < test.readiness.number ? before : null;
}

/** The readiness number as a level meter: the number (counting up when it grew since the last visit), its level, the bar, and the
 *  points to the next level. */
export function readinessMeter(test) {
  const r = test.readiness, from = lastSeen(test);
  return `<div class="readiness" data-readiness data-from="${from ?? ""}" data-to="${r.number}">
    <p class="rd-top"><b class="rd-num" aria-hidden="true">${from ?? r.number}</b><span><span class="rd-label">מוכנות למבחן · <b>${esc(r.label)}</b></span>
      ${from !== null ? `<span class="rd-up" aria-hidden="true">+${r.number - from}</span>` : ""}
      <br><span class="muted rd-next">${r.next ? `עוד ${r.next.left} לרמה "${esc(r.next.name)}"` : "הגעתם לרמה הגבוהה ביותר! 🏆"}</span></span></p>
    <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}">
      <i style="width:${from ?? r.number}%"></i>${r.next ? `<s style="inset-inline-start:${r.next.at}%" aria-hidden="true"></s>` : ""}</div></div>`;
}

/* ---------- the forecast grade: "if the test were today" (forecast.py), on home and after every activity ---------- */

const FORECAST_SEEN = "mathly2.forecast.";
/** The forecast this device showed last for the test (or null), and remember `now` as seen. */
export function forecastSeen(testId, now) {
  let before = null;
  try {
    const kept = localStorage.getItem(FORECAST_SEEN + testId);
    before = kept === null ? null : Number(kept);
    if (now !== undefined) localStorage.setItem(FORECAST_SEEN + testId, String(now));
  } catch { /* private window */ }
  return Number.isFinite(before) ? before : null;
}

/** The forecast as a meter: the grade (counting up when it grew since the last time it was seen; a drop is shown as it is), the range
 *  while it rests on few answers, and the bar with the range drawn faintly behind it. */
export function forecastMeter(f, testId, { id = "", compact = false } = {}) {
  const before = forecastSeen(testId, f.grade), from = before !== null && before < f.grade ? before : null;
  const wide = f.high - f.low >= 10;
  return `<div class="readiness forecast${compact ? " compact" : ""}"${id ? ` id="${id}"` : ""} data-from="${from ?? ""}" data-to="${f.grade}">
    <p class="rd-top"><b class="rd-num" aria-hidden="true">${from ?? f.grade}</b><span><span class="rd-label">🎯 הציון הצפוי במבחן</span>
      ${from !== null ? ` <span class="rd-up" aria-hidden="true">+${f.grade - from}</span>` : ""}
      <br><span class="muted fc-range">${wide ? `בין ${f.low} ל־${f.high} · ` : ""}${f.answers < 10 ? "עוד מעט תשובות, התחזית תתחדד עם התרגול" : "מתעדכן אחרי כל סבב, תרגול ומבחן"}</span></span></p>
    <div class="bar rd-bar fc-bar" role="progressbar" aria-label="הציון הצפוי במבחן: ${f.grade}${wide ? `, בין ${f.low} ל־${f.high}` : ""}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${f.grade}">
      ${wide ? `<u style="inset-inline-start:${f.low}%;width:${f.high - f.low}%" aria-hidden="true"></u>` : ""}<i style="width:${from ?? f.grade}%"></i></div></div>`;
}

/** Count the number up from the last visit's and grow the bar with it. */
function countUp(root = document) {
  root.querySelectorAll(".readiness[data-from]:not([data-from=''])").forEach(meter => {
    const from = Number(meter.dataset.from), to = Number(meter.dataset.to), num = meter.querySelector(".rd-num"), bar = meter.querySelector(".rd-bar i");
    meter.dataset.from = "";
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { num.textContent = to; bar.style.width = `${to}%`; return; }
    const start = performance.now(), time = 900;
    const frame = now => {
      const k = Math.min(1, (now - start) / time), v = Math.round(from + (to - from) * (1 - (1 - k) ** 3));
      num.textContent = v;
      bar.style.width = `${v}%`;
      if (k < 1) requestAnimationFrame(frame); else meter.classList.add("grew");
    };
    requestAnimationFrame(frame);
  });
}
export { countUp };

/** The nearest test in one compact block (the home is one screen): the readiness number with its level and the days left (a link to the
 *  test's page, with all its tests and grades), the bar, and the two buttons that raise it, each with the most it can add now. */
function testStrip(test) {
  if (test.forecast) return forecastStrip(test);
  const r = test.readiness, add = r.can_add, sim = test.simulation.open, from = lastSeen(test);
  return `<section class="strip test-strip" id="nearest-test" data-test="${test.id}">
    <div class="readiness" data-readiness data-from="${from ?? ""}" data-to="${r.number}">
      <a class="strip-main" href="#/test/${test.id}"><b class="rd-num" aria-hidden="true">${from ?? r.number}</b>
        <span class="grow"><span class="rd-label">מוכנות למבחן · <b>${esc(r.label)}</b>${from !== null ? ` <span class="rd-up" aria-hidden="true">+${r.number - from}</span>` : ""}</span>
          <small class="muted">📅 <span class="days">מבחן ${daysText(test.days_left)}</span>${r.next ? ` · עוד ${r.next.left} לרמה "${esc(r.next.name)}"` : " · 🏆"}</small></span>
        <span class="strip-more" aria-hidden="true">‹</span></a>
      <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}"><i style="width:${from ?? r.number}%"></i></div></div>
    <div class="test-btns"><a class="test-btn" id="home-practice" href="#/test/${test.id}/practice">📝 מבחן תרגול${add.practice ? ` <small>+${add.practice}</small>` : ""}</a>
      <a class="test-btn sim" id="home-sim" href="#/sim/${test.id}${sim ? `/${esc(sim)}` : ""}">⏱ ${sim ? "להמשיך סימולציה" : "מבחן סימולציה"}${add.simulation && !sim ? ` <small>+${add.simulation}</small>` : ""}</a></div></section>`;
}

/** The nearest test with its forecast grade, in the strip's one-screen layout: the grade (counting up from the last time it was seen),
 *  the days left and the range (a link to the test's page, where the readiness number is), the bar, and the practice test and the
 *  simulation. */
function forecastStrip(test) {
  const f = test.forecast, sim = test.simulation.open, before = forecastSeen(test.id, f.grade);
  const from = before !== null && before < f.grade ? before : null, wide = f.high - f.low >= 10;
  return `<section class="strip test-strip" id="nearest-test" data-test="${test.id}">
    <div class="readiness forecast" id="home-forecast" data-from="${from ?? ""}" data-to="${f.grade}">
      <a class="strip-main" href="#/test/${test.id}"><b class="rd-num" aria-hidden="true">${from ?? f.grade}</b>
        <span class="grow"><span class="rd-label">🎯 הציון הצפוי במבחן${from !== null ? ` <span class="rd-up" aria-hidden="true">+${f.grade - from}</span>` : ""}</span>
          <small class="muted">📅 <span class="days">מבחן ${daysText(test.days_left)}</span>${wide ? ` · בין ${f.low} ל־${f.high}` : ""}</small></span>
        <span class="strip-more" aria-hidden="true">‹</span></a>
      <div class="bar rd-bar fc-bar" role="progressbar" aria-label="הציון הצפוי במבחן: ${f.grade}${wide ? `, בין ${f.low} ל־${f.high}` : ""}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${f.grade}">
        ${wide ? `<u style="inset-inline-start:${f.low}%;width:${f.high - f.low}%" aria-hidden="true"></u>` : ""}<i style="width:${from ?? f.grade}%"></i></div></div>
    <div class="test-btns"><a class="test-btn" id="home-practice" href="#/test/${test.id}/practice">📝 מבחן תרגול</a>
      <a class="test-btn sim" id="home-sim" href="#/sim/${test.id}${sim ? `/${esc(sim)}` : ""}">⏱ ${sim ? "להמשיך סימולציה" : "מבחן סימולציה"}</a></div></section>`;
}

/** An assignment's state in a symbol and a word (never colour alone). */
export function assignmentState(a) {
  if (a.kind === "exercise_test") return a.state === "done" ? { symbol: "✓", word: `ציון ${a.grade}` } : a.overdue ? { symbol: "⚠", word: "באיחור" } : { symbol: "○", word: "עוד לא נעשה" };
  switch (a.state) {
    case "handed_in": return { symbol: "◐", word: a.late ? "הוגש באיחור" : "הוגש" };
    case "graded": return { symbol: "✓", word: `ציון ${a.grade}` };
    case "returned": return { symbol: "↩", word: "הוחזר לתיקון" };
    default: return a.overdue ? { symbol: "⚠", word: "באיחור" } : { symbol: "○", word: "לא הוגש" };
  }
}
export const assignmentHref = a => a.kind === "exercise_test" ? `#/exam/${a.test.id}/${a.test.number}` : `#/assignment/${a.id}`;

/** Home shows only the new assignments: those not handed in yet (or an exercise test not taken). The rest are in the "הגשות" tab. */
const isNew = a => a.state === "not_handed" || a.state === "not_done";

/** The new assignments as one button to the "הגשות" tab, with how many there are. */
function assignmentsChip(all) {
  const list = all.filter(isNew);
  if (!list.length) return "";
  const late = list.some(a => a.overdue);
  return `<a class="hchip${late ? " late" : ""}" id="assignments" data-count="${list.length}" href="#/submissions">📝 ${list.length === 1 ? "משימה חדשה" : `${list.length} משימות חדשות`}${late ? " ⚠" : ""}</a>`;
}

/** Photo help (STU-6), only for a class with the AI on: one button, and the latest request with its state when there is one. */
function aiChips(ai) {
  if (!ai?.on) return "";
  const last = ai.requests[0];
  return `<span class="hchips-ai" id="ai-card"><button type="button" class="hchip" id="ai-new">📷 עזרה מתמונה</button>${last ? `<button type="button" class="hchip" data-ai-open="${esc(last.id)}"
    data-request="${esc(last.id)}">${esc(aiSheet.stateWord(last.state))}</button>` : ""}</span>`;
}

/* ---------- the lessons board: every lesson on one screen ---------- */

const starsText = n => "★".repeat(n) + "☆".repeat(3 - n);
const starsLabel = n => n === 3 ? "שלושה כוכבים, מושלם" : n === 0 ? "אין עדיין כוכבים" : n === 1 ? "כוכב אחד" : "שני כוכבים";
const plainText = text => String(text ?? "").replace(/\$/g, "");
export const roundHref = id => `#/round/${encodeURIComponent(id)}`;

function tile(l, next) {
  const isNext = l.id === next, perfect = l.stars === 3;
  const label = `שיעור ${l.number}: ${plainText(l.name)}. ${starsLabel(l.stars)}${l.behind ? `. בפיגור, היה אמור להסתיים ב־${shortDate(l.due_date)}` : ""}${l.round_open ? ". באמצע סבב" : ""}${isNext ? ". ממשיכים כאן" : ""}`;
  return `<a class="lnode s${l.stars}${perfect ? " perfect" : ""}${isNext ? " next" : ""}${l.behind ? " behind" : ""}" href="${roundHref(l.id)}" data-lesson="${esc(l.id)}" data-stars="${l.stars}"
      aria-label="${esc(label)}" title="${esc(plainText(l.name))}">
    <span class="disc" aria-hidden="true">${perfect ? "👑" : l.number}${l.behind ? `<i class="badge late">⏰</i>` : l.round_open ? `<i class="badge open">◐</i>` : ""}</span>
    <span class="lstars" aria-hidden="true">${starsText(l.stars)}</span><span class="lname" aria-hidden="true">${fmt(l.name)}</span></a>`;
}

/** The top: the stars collected, the lessons perfected, the streak and the daily goal, then the big play button for the next lesson. */
function quest(map, chips = "") {
  const next = map.lessons.find(l => l.id === map.next);
  const play = next ? `<a class="play" id="play" href="${roundHref(next.id)}"><span class="play-icon" aria-hidden="true">▶</span>
      <span class="grow"><small>${next.round_open ? "להמשיך את הסבב" : next.behind ? "להשלים" : next.stars ? "לעוד כוכב" : "השיעור הבא"}</small><b>${fmt(next.name)}</b></span>
      <span class="lstars" aria-label="${starsLabel(next.stars)}">${starsText(next.stars)}</span></a>`
    : `<p class="all-perfect" id="play">👑 כל השיעורים מושלמים! אפשר להעמיק בלשונית העמקה.</p>`;
  const t = map.today;
  return `<section class="quest" id="quest" aria-label="המסע שלי">
    <p class="quest-stats"><span id="stars-count" aria-label="${map.stars} כוכבים מתוך ${map.max_stars}">⭐ ${map.stars}/${map.max_stars}</span><span id="perfect-count">👑 ${map.perfect}</span>
      ${map.streak ? `<span>🔥 ${map.streak}</span>` : ""}<span id="goal" class="goal-chip${t.reached ? " done" : ""}" title="יעד יומי">🎯 ${Math.min(t.done, t.goal)}/${t.goal}${t.reached ? " ✓" : ""}</span>
      ${chips ? `<span class="hchips" id="home-actions">${chips}</span>` : ""}</p>
    ${play}</section>`;
}

/** The lessons. With dates in the curriculum: the current lesson (the first whose date is today or later) on its own, and the lessons
 *  whose date has passed and the coming ones folded under it, each with how many there are (and how many are behind). Without dates:
 *  every lesson as a tile. */
function board(map) {
  if (!map.lessons.length) return "";
  const tiles = list => `<div class="lesson-board">${list.map(l => tile(l, map.next)).join("")}</div>`;
  if (!map.lessons.some(l => l.when)) return `<section class="lesson-board" id="lesson-map" aria-label="השיעורים">${map.lessons.map(l => tile(l, map.next)).join("")}</section>`;
  const past = map.lessons.filter(l => l.when === "past"), later = map.lessons.filter(l => l.when === "later");
  const now = map.lessons.find(l => l.when === "current");
  const behind = past.filter(l => l.behind).length;
  const fold = (id, title, list, extra = "") => list.length ? `<details class="lfold" id="${id}"><summary><span class="grow">${title} (${list.length})</span>${extra}</summary>${tiles(list)}</details>` : "";
  return `<section class="lesson-groups" id="lesson-map" aria-label="השיעורים">
    ${now ? `<div class="lnow" id="lesson-now"><h2 class="lnow-title">השיעור הנוכחי <span class="muted">עד ${esc(shortDate(now.due_date))}</span></h2>${tile(now, map.next)}</div>`
          : `<p class="muted" id="lesson-now">כל התאריכים בתוכנית כבר עברו.</p>`}
    ${fold("lessons-past", "שיעורים שעברו", past, behind ? `<span class="lfold-late">⏰ ${behind} בפיגור</span>` : "")}
    ${fold("lessons-later", "השיעורים הבאים", later)}</section>`;
}

export const show = view => swr([forSubject("/api/home"), "/api/assignments", "/api/ai/status"], ([data, assignments, ai]) => draw(view, data, assignments, ai));

function draw(view, data, assignments, ai) {
  const [first] = data.tests;
  const chips = assignmentsChip(assignments) + aiChips(ai);
  view(`${tabs("home")}${backToSubjects()}
    ${quest(data.map, chips)}
    ${first ? testStrip(first) : ""}
    ${board(data.map)}`);
  countUp();
  document.getElementById("ai-new")?.addEventListener("click", () => aiSheet.open());
  document.querySelectorAll("[data-ai-open]").forEach(b => b.addEventListener("click", () => aiSheet.open({ id: b.dataset.aiOpen })));
}
