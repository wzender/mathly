// The student's home for a subject: one screen, like a game's level select. The stars collected and a big play button for the next lesson,
// every lesson as a small tile with its stars (a round finished, 8 of 10, every skill mastered), then the nearest test in one strip (the days
// left, the readiness number, today's task) and small buttons for a required simulation, the new assignments and photo help.
import { swr } from "./api.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { backToSubjects, daysText, forSubject, pathHref, shortDate, tabs } from "./ui.js";

/** One part of the readiness number as a row in plain Hebrew: its name, what the number is, and its value ("—" when there is none yet). */
const part = (id, name, what, value, unit = "") => `<li class="rd-part" data-part="${id}"><span class="grow"><b>${name}</b> <span class="muted">${what}</span></span><b class="rd-val">${value === null ? "—" : value + unit}</b></li>`;

/** The readiness number as a level bar with its three parts under it; before the simulation it says the bar is capped. */
const HOW = ["המדד מורכב משליטה (50%), מבחני תרגול (20%) וסימולציה (30%).", "חלק שעוד אין לו ציון לא נספר.", "בלי סימולציה המדד לא עובר 80."];

/** The info button beside the readiness number and its tooltip: hover, focus or tap opens it; a second tap, a tap elsewhere or Escape closes it. */
const howTip = () => `<span class="info-tip"><button type="button" class="info" data-info aria-label="איך המדד מחושב" aria-expanded="false">ⓘ</button>
  <span class="tip" role="tooltip" hidden>${HOW.map(l => `<span>${l}</span>`).join("")}</span></span>`;

const closeTips = except => document.querySelectorAll(".info-tip.open").forEach(t => {
  if (t === except) return;
  t.classList.remove("open");
  t.querySelector("[data-info]").setAttribute("aria-expanded", "false");
  t.querySelector(".tip").hidden = true;
});
document.addEventListener("click", event => {
  const tip = event.target.closest(".info-tip");
  closeTips(tip);
  if (!tip || !event.target.closest("[data-info]")) return;
  const open = !tip.classList.contains("open");
  tip.classList.toggle("open", open);
  tip.querySelector("[data-info]").setAttribute("aria-expanded", String(open));
  tip.querySelector(".tip").hidden = !open;
});
document.addEventListener("keydown", event => { if (event.key === "Escape") { closeTips(null); document.activeElement?.closest?.(".info-tip") && document.activeElement.blur(); } });

export function readinessBar(r) {
  return `<div class="readiness" data-readiness>
    <p class="rd-top"><b class="rd-num" aria-hidden="true">${r.number}</b><span class="rd-label">${esc(r.label)}</span>${howTip()}</p>
    <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}"><i style="width:${r.number}%"></i></div>
    <ul class="plain rd-parts">${part("M", "שליטה", "אחוז המיומנויות שנשלטו", r.parts.M, "%")}${part("E", "מבחני תרגול", "ממוצע הציונים הטובים ביותר", r.parts.E)}${part("S", "סימולציה", "הציון במבחן הסימולציה", r.parts.S)}</ul>
    ${r.waiting_for_simulation ? `<p class="rd-note">עוד לא עשיתם מבחן סימולציה, ולכן המדד לא עובר את ${80}.</p>` : ""}</div>`;
}

/** Today's task as {label, href}. */
function taskLink(task, test, next) {
  const skill = id => `#/skill/${encodeURIComponent(id)}`;
  switch (task.kind) {
    case "path": return { label: task.skill ? `לסיים את המסלול: ${task.skill_name}` : "לסיים את המסלול", href: task.skill ? skill(task.skill) : pathHref() };
    case "ex1": case "ex2": return { label: `מבחן תרגול ${task.kind === "ex1" ? 1 : 2}`, href: `#/exam/${test.id}/${task.kind === "ex1" ? 1 : 2}` };
    case "sim": return { label: "מבחן סימולציה", href: `#/sim/${test.id}` };
    case "review": return { label: `חזרה על ${task.skill_name}`, href: skill(task.skill) };
    case "mixed_review": return task.skill ? { label: `חזרה קלה: ${task.skill_name}`, href: skill(task.skill) } : { label: "חזרה קלה במסלול", href: pathHref() };
    default: return next ? { label: `להמשיך במסלול: ${next.name}`, href: skill(next.id) } : { label: "למסלול", href: pathHref() };
  }
}

/** The nearest test, in one short strip: the days left and the readiness number (it opens the test's card, which has the bar, the plan and
 *  the practice tests), and today's one task as a button. */
function testStrip(test, task, next) {
  const t = taskLink(task, test, next);
  return `<section class="strip test-strip" id="nearest-test" data-test="${test.id}">
    <a class="strip-main" href="#/test/${test.id}"><h2>📅 מבחן ${daysText(test.days_left)}</h2><span class="muted">מוכנות <b>${test.readiness.number}</b> ‹</span></a>
    <a class="today-btn" id="today-task" href="${esc(t.href)}"><small>היום:</small> ${esc(t.label)}</a></section>`;
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
function quest(map) {
  const next = map.lessons.find(l => l.id === map.next);
  const play = next ? `<a class="play" id="play" href="${roundHref(next.id)}"><span class="play-icon" aria-hidden="true">▶</span>
      <span class="grow"><small>${next.round_open ? "להמשיך את הסבב" : next.behind ? "להשלים" : next.stars ? "לעוד כוכב" : "השיעור הבא"}</small><b>${fmt(next.name)}</b></span>
      <span class="lstars" aria-label="${starsLabel(next.stars)}">${starsText(next.stars)}</span></a>`
    : `<p class="all-perfect" id="play">👑 כל השיעורים מושלמים! אפשר להעמיק בלשונית העמקה.</p>`;
  const t = map.today;
  return `<section class="quest" id="quest" aria-label="המסע שלי">
    <p class="quest-stats"><span id="stars-count">⭐ ${map.stars} מתוך ${map.max_stars}</span><span id="perfect-count">👑 ${map.perfect}</span>
      ${map.streak ? `<span>🔥 ${map.streak}</span>` : ""}<span id="goal" class="goal-chip${t.reached ? " done" : ""}" title="יעד יומי">🎯 ${Math.min(t.done, t.goal)}/${t.goal}${t.reached ? " ✓" : ""}</span></p>
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
  const required = data.tests.filter(t => t.simulation.required);
  const chips = required.map(t => `<a class="hchip required" href="#/sim/${t.id}" data-required="${t.id}"><b>חובה</b> סימולציה</a>`).join("") + assignmentsChip(assignments) + aiChips(ai);
  view(`${tabs("home")}${backToSubjects()}
    ${quest(data.map)}
    ${first ? testStrip(first, data.task, data.next_skill) : ""}
    ${chips ? `<div class="hchips" id="home-actions">${chips}</div>` : ""}
    ${board(data.map)}`);
  document.getElementById("ai-new")?.addEventListener("click", () => aiSheet.open());
  document.querySelectorAll("[data-ai-open]").forEach(b => b.addEventListener("click", () => aiSheet.open({ id: b.dataset.aiOpen })));
}
