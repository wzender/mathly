// The student's home for a subject: the nearest test with its readiness and one task for today, the required simulation,
// the other tests, and a button that continues the path.
import { swr } from "./api.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { PATH, backToSubjects, daysText, shortDate, tabs } from "./ui.js";

const part = (label, name, value) => `<span class="rd-part"><b>${label}</b> ${name} ${value === null ? "—" : value}</span>`;

/** The readiness number as a level bar with its three parts under it; before the simulation it says the bar is capped. */
export function readinessBar(r) {
  return `<div class="readiness" data-readiness>
    <p class="rd-top"><b class="rd-num" aria-hidden="true">${r.number}</b><span class="rd-label">${esc(r.label)}</span></p>
    <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}"><i style="width:${r.number}%"></i></div>
    <p class="rd-parts muted">${part("M", "שליטה", r.parts.M)} ${part("E", "מבחני תרגול", r.parts.E)} ${part("S", "סימולציה", r.parts.S)}</p>
    ${r.waiting_for_simulation ? `<p class="rd-note">עוד לא עשיתם מבחן סימולציה, ולכן המדד לא עובר את ${80}.</p>` : ""}</div>`;
}

/** Today's task as {label, href}. */
function taskLink(task, test, next) {
  const skill = id => `#/skill/${encodeURIComponent(id)}`;
  switch (task.kind) {
    case "path": return { label: task.skill ? `לסיים את המסלול: ${task.skill_name}` : "לסיים את המסלול", href: task.skill ? skill(task.skill) : PATH };
    case "ex1": case "ex2": return { label: `מבחן תרגול ${task.kind === "ex1" ? 1 : 2}`, href: `#/exam/${test.id}/${task.kind === "ex1" ? 1 : 2}` };
    case "sim": return { label: "מבחן סימולציה", href: `#/sim/${test.id}` };
    case "review": return { label: `חזרה על ${task.skill_name}`, href: skill(task.skill) };
    case "mixed_review": return task.skill ? { label: `חזרה קלה: ${task.skill_name}`, href: skill(task.skill) } : { label: "חזרה קלה במסלול", href: PATH };
    default: return next ? { label: `להמשיך במסלול: ${next.name}`, href: skill(next.id) } : { label: "למסלול", href: PATH };
  }
}

const lessonsOf = test => test.lessons.map(l => fmt(l.name)).join(", ");

function nearest(test, task, next) {
  const t = taskLink(task, test, next);
  return `<section class="card test-card" id="nearest-test" data-test="${test.id}">
    <h2>המבחן הבא: ${shortDate(test.date)} <span class="muted">(${daysText(test.days_left)})</span></h2>
    <p class="muted">${lessonsOf(test)}${test.note ? ` · ${esc(test.note)}` : ""}</p>
    ${readinessBar(test.readiness)}
    <p class="today"><span class="muted">המשימה להיום</span><a class="big-task" id="today-task" href="${esc(t.href)}">${esc(t.label)} <span aria-hidden="true">‹</span></a></p>
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

/** Every lesson behind the curriculum, short: its name, its date and one link to its quiz (at least 13 of 15 completes the lesson, PTH-10). */
function behindCard(lessons) {
  if (!lessons?.length) return "";
  return `<section class="card" id="behind-card"><h2>שיעורים בפיגור</h2>
    <ul class="plain behind-list">${lessons.map(l => `<li data-lesson="${esc(l.id)}"><p><b>${fmt(l.name)}</b> <span class="late">⚠ עד ${shortDate(l.due_date)}</span></p>
      <p class="actions"><a class="button" data-way="quiz" href="#/quiz/${encodeURIComponent(l.id)}">${l.quiz.open ? "להמשיך את הבוחן" : "לבוחן"}: לפחות ${l.quiz.pass_right} מתוך ${l.quiz.size}</a>
        <span class="muted" data-best>${l.quiz.best === null ? "עוד לא נעשה" : `הציון הטוב ביותר: ${l.quiz.best}`}</span></p></li>`).join("")}</ul></section>`;
}

/** The practice tests of upcoming tests that were taken and are below 87 (13 of 15): to take again. */
function weakTestsCard(tests) {
  if (!tests?.length) return "";
  return `<section class="card" id="weak-tests"><h2>מבחני תרגול להשלמה</h2>
    <ul class="plain behind-list">${tests.map(t => `<li data-test="${t.test_id}" data-number="${t.number}"><p><b>מבחן תרגול ${t.number}</b> <span class="muted">למבחן ב־${shortDate(t.date)}</span></p>
      <p class="actions"><a class="button" data-way="retake" href="#/exam/${t.test_id}/${t.number}">${t.open ? "להמשיך" : "לנסות שוב"}</a>
        <span class="muted" data-best>הציון הטוב ביותר: ${t.best} · צריך 87 לפחות (13 מתוך 15)</span></p></li>`).join("")}</ul></section>`;
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

export const show = view => swr(["/api/home", "/api/assignments", "/api/ai/status"], ([data, assignments, ai]) => draw(view, data, assignments, ai));

function draw(view, data, assignments, ai) {
  const [first] = data.tests;
  const required = data.tests.filter(t => t.simulation.required);
  view(`${tabs("home")}${backToSubjects()}
    ${first ? nearest(first, data.task, data.next_skill) : `<section class="card" id="no-test"><h2>הבית</h2>
      <p class="muted">המורה עוד לא קבע מבחן. בינתיים אפשר להמשיך במסלול.</p></section>`}
    ${behindCard(data.behind)}${weakTestsCard(data.weak_tests)}${assignmentsCard(assignments)}${aiCard(ai)}
    ${required.map(t => `<a class="required" href="#/sim/${t.id}" data-required="${t.id}"><b>חובה</b> מבחן סימולציה למבחן ב־${shortDate(t.date)}<span aria-hidden="true">‹</span></a>`).join("")}
    <p>${data.next_skill ? `<a class="primary-link" id="continue-path" href="#/skill/${encodeURIComponent(data.next_skill.id)}">להמשיך במסלול: ${fmt(data.next_skill.name)} <span aria-hidden="true">‹</span></a>`
      : `<a class="primary-link" id="continue-path" href="${PATH}">למסלול: כל הכוכבים פתוחים לתרגול <span aria-hidden="true">‹</span></a>`}</p>`);
  document.getElementById("ai-new")?.addEventListener("click", () => aiSheet.open());
  document.querySelectorAll("[data-ai-open]").forEach(b => b.addEventListener("click", () => aiSheet.open({ id: b.dataset.aiOpen })));
}
