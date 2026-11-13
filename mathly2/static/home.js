// The student's home for a subject: a game board. The stars collected and a big play button for the next lesson, the map of the lessons
// (each with its stars: a round finished, 8 of 10, every skill mastered), then the nearest test with its readiness and today's task, the new
// assignments, the required simulation, and a link to the path for going deeper.
import { swr } from "./api.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { owl } from "./sky.js";
import { backToSubjects, daysText, forSubject, goalBar, pathHref, shortDate, tabs } from "./ui.js";

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

const lessonsOf = test => test.lessons.map(l => fmt(l.name)).join(", ");

function nearest(test, task, next, weak = []) {
  const t = taskLink(task, test, next);
  return `<section class="card test-card" id="nearest-test" data-test="${test.id}">
    <h2>המבחן הבא: ${shortDate(test.date)} <span class="muted">(${daysText(test.days_left)})</span></h2>
    <p class="muted">${lessonsOf(test)}${test.note ? ` · ${esc(test.note)}` : ""}</p>
    ${readinessBar(test.readiness)}
    <p class="today"><span class="muted">המשימה להיום</span><a class="big-task" id="today-task" href="${esc(t.href)}">${esc(t.label)} <span aria-hidden="true">‹</span></a></p>
    ${weakTests(weak)}
    <p><a href="#/test/${test.id}">כל התוכנית והמבחנים</a></p></section>`;
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

function assignmentsCard(all) {
  const list = all.filter(isNew);
  if (!list.length) return "";
  return `<section class="card" id="assignments"><h3>המשימות שלי</h3><ul class="plain assignments">${list.map(a => {
    const s = assignmentState(a);
    return `<li data-assignment="${a.id}" data-state="${esc(a.state)}"><a href="${assignmentHref(a)}"><b>${fmt(a.title)}</b></a>
      <span class="muted">עד ${shortDate(a.due_date)}</span><span class="tag st-${esc(a.state)}"><span aria-hidden="true">${s.symbol}</span> ${s.word}</span></li>`;
  }).join("")}</ul></section>`;
}

/** A grade as a chip inside the link it belongs to: the bare number, or "-" when there is none. */
const chip = grade => `<span class="grade-chip${grade === null || grade === undefined ? " none" : ""}" data-best>${grade === null || grade === undefined ? "-" : grade}</span>`;

/** The nearest test's practice tests that were taken and are below 87 (13 of 15): to take again, inside the test's own card. */
function weakTests(tests) {
  if (!tests?.length) return "";
  return `<div class="weak-tests" id="weak-tests"><p class="muted">מבחני תרגול להשלמה</p>
    <ul class="plain behind-list">${tests.map(t => `<li class="behind-row" data-test="${t.test_id}" data-number="${t.number}"><span class="grow"><b>מבחן תרגול ${t.number}</b></span>
      <a class="button with-chip" data-way="retake" href="#/exam/${t.test_id}/${t.number}">${t.open ? "להמשיך" : "לנסות שוב"} ${chip(t.best)}</a></li>`).join("")}</ul></div>`;
}

/** The photo help card (STU-6): only for a class with the AI on; it also lists the student's latest requests with their state. */
function aiCard(ai) {
  if (!ai?.on) return "";
  return `<section class="card ai-card" id="ai-card"><h2>תקועים על תרגיל? צלמו אותו</h2>
    <p class="muted">המורה רואה את התמונה לפני שהיא נשלחת ל־AI.</p>
    <p><button type="button" class="primary" id="ai-new">📷 עזרה מתמונה</button></p>
    ${ai.requests.length ? `<ul class="plain" id="ai-requests">${ai.requests.map(r => `<li data-request="${esc(r.id)}"><button type="button" data-ai-open="${esc(r.id)}">
      <span class="tag st-${esc(r.state)}">${esc(aiSheet.stateWord(r.state))}</span> ${r.skill ? fmt(r.skill.name) : "תרגיל מצולם"}</button></li>`).join("")}</ul>` : ""}</section>`;
}

/* ---------- the lessons map: the home's game board ---------- */

const ROW = 128;                                  // px between two lessons on the map
const XS = [50, 76, 50, 24];                      // each lesson's place across the map, in %: a winding trail
const starsText = n => "★".repeat(n) + "☆".repeat(3 - n);
const starsLabel = n => n === 3 ? "שלושה כוכבים, מושלם" : n === 0 ? "אין עדיין כוכבים" : n === 1 ? "כוכב אחד" : "שני כוכבים";
export const roundHref = id => `#/round/${encodeURIComponent(id)}`;

/** The trail that joins the lessons: one curve per pair, gold after a perfect lesson, blue after a lesson with stars, faint otherwise. */
function trailSvg(lessons) {
  const h = lessons.length * ROW;
  const pt = i => [XS[i % XS.length], i * ROW + 40];
  const parts = lessons.slice(0, -1).map((l, i) => {
    const [x0, y0] = pt(i), [x1, y1] = pt(i + 1), m = (y0 + y1) / 2;
    return `<path class="${l.stars === 3 ? "gold" : l.stars ? "on" : ""}" d="M${x0} ${y0}C${x0} ${m} ${x1} ${m} ${x1} ${y1}"/>`;
  }).join("");
  return `<svg class="map-trail" viewBox="0 0 100 ${h}" preserveAspectRatio="none" aria-hidden="true">${parts}</svg>`;
}

function lessonNode(l, i, next) {
  const isNext = l.id === next, perfect = l.stars === 3;
  const marks = [l.behind ? `<span class="lmark late">⏰ עד ${shortDate(l.due_date)}</span>` : "", l.round_open ? `<span class="lmark open">◐ באמצע סבב</span>` : ""].join("");
  const label = `שיעור ${l.number}: ${plainText(l.name)}. ${starsLabel(l.stars)}${l.behind ? `. בפיגור, היה אמור להסתיים ב־${shortDate(l.due_date)}` : ""}${l.round_open ? ". באמצע סבב" : ""}${isNext ? ". ממשיכים כאן" : ""}`;
  return `<a class="lnode s${l.stars}${perfect ? " perfect" : ""}${isNext ? " next" : ""}${l.behind ? " behind" : ""}" href="${roundHref(l.id)}" data-lesson="${esc(l.id)}" data-stars="${l.stars}"
      style="left:${XS[i % XS.length]}%;top:${i * ROW}px" aria-label="${esc(label)}">
    <span class="disc" aria-hidden="true">${perfect ? "👑" : l.number}${isNext ? `<span class="perch">${owl(34)}</span>` : ""}</span>
    <span class="lstars" aria-hidden="true">${starsText(l.stars)}</span>
    <span class="lname">${fmt(l.name)}</span>${marks}</a>`;
}

const plainText = text => String(text ?? "").replace(/\$/g, "");

/** The header and the play button: the stars collected, the lessons perfected, the daily goal and the streak. */
function quest(map) {
  const next = map.lessons.find(l => l.id === map.next);
  const play = next ? `<a class="play" id="play" href="${roundHref(next.id)}"><span class="play-icon" aria-hidden="true">▶</span>
      <span class="grow"><small>${next.round_open ? "להמשיך את הסבב" : next.behind ? "להשלים" : next.stars ? "לעוד כוכב" : "השיעור הבא"}</small><b>${fmt(next.name)}</b></span>
      <span class="lstars" aria-label="${starsLabel(next.stars)}">${starsText(next.stars)}</span></a>`
    : `<p class="all-perfect" id="play">👑 כל השיעורים מושלמים! אפשר להעמיק במסלול.</p>`;
  return `<section class="quest" id="quest" aria-label="המסע שלי">
    <div class="quest-top">${owl(56)}<div class="grow"><h2>המסע שלי</h2>
      <p class="quest-stats"><span id="stars-count">⭐ ${map.stars} מתוך ${map.max_stars}</span><span id="perfect-count">👑 ${map.perfect} מושלמים</span>${map.streak ? `<span>🔥 ${map.streak}</span>` : ""}</p></div></div>
    ${goalBar(map.today)}${play}</section>`;
}

function lessonMap(map) {
  if (!map.lessons.length) return "";
  return `<section class="lesson-map" id="lesson-map" aria-label="מפת השיעורים" style="height:${map.lessons.length * ROW}px">${trailSvg(map.lessons)}
    ${map.lessons.map((l, i) => lessonNode(l, i, map.next)).join("")}</section>
    <p class="map-key muted">★ סבב הושלם · ★★ 8 מתוך 10 · ★★★ כל המיומנויות נשלטו (שני ימים טובים)</p>`;
}

export const show = view => swr([forSubject("/api/home"), "/api/assignments", "/api/ai/status"], ([data, assignments, ai]) => draw(view, data, assignments, ai));

let scrolled = false;

function draw(view, data, assignments, ai) {
  const [first] = data.tests;
  const required = data.tests.filter(t => t.simulation.required);
  view(`${tabs("home")}${backToSubjects()}
    ${required.map(t => `<a class="required" href="#/sim/${t.id}" data-required="${t.id}"><b>חובה</b> מבחן סימולציה למבחן ב־${shortDate(t.date)}<span aria-hidden="true">‹</span></a>`).join("")}
    ${quest(data.map)}${assignmentsCard(assignments)}${lessonMap(data.map)}
    ${first ? nearest(first, data.task, data.next_skill, data.weak_tests) : ""}
    ${aiCard(ai)}
    <p><a class="primary-link" id="continue-path" href="${pathHref()}">להעמקה: כל המיומנויות, אחת־אחת <span aria-hidden="true">‹</span></a></p>`);
  if (!scrolled) { scrolled = true; document.querySelector(".lnode.next")?.scrollIntoView?.({ block: "nearest" }); }
  document.getElementById("ai-new")?.addEventListener("click", () => aiSheet.open());
  document.querySelectorAll("[data-ai-open]").forEach(b => b.addEventListener("click", () => aiSheet.open({ id: b.dataset.aiOpen })));
}
