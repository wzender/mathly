// The student's home for a subject: the nearest test with its readiness and one task for today, the required simulation,
// the other tests, and a button that continues the path.
import { api } from "./api.js";
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

export async function show(view) {
  const data = await api("/api/home");
  const [first, ...others] = data.tests;
  const required = data.tests.filter(t => t.simulation.required);
  view(`${tabs("home")}${backToSubjects()}
    ${first ? nearest(first, data.task, data.next_skill) : `<section class="card" id="no-test"><h2>הבית</h2>
      <p class="muted">המורה עוד לא קבע מבחן. בינתיים אפשר להמשיך במסלול.</p></section>`}
    ${required.map(t => `<a class="required" href="#/sim/${t.id}" data-required="${t.id}"><b>חובה</b> מבחן סימולציה למבחן ב־${shortDate(t.date)}<span aria-hidden="true">‹</span></a>`).join("")}
    <p>${data.next_skill ? `<a class="primary-link" id="continue-path" href="#/skill/${encodeURIComponent(data.next_skill.id)}">להמשיך במסלול: ${fmt(data.next_skill.name)} <span aria-hidden="true">‹</span></a>`
      : `<a class="primary-link" id="continue-path" href="${PATH}">למסלול: כל הכוכבים פתוחים לתרגול <span aria-hidden="true">‹</span></a>`}</p>
    ${others.length ? `<h3>מבחנים נוספים</h3><ul class="plain" id="other-tests">${others.map(t => `<li><a href="#/test/${t.id}">${shortDate(t.date)} · ${lessonsOf(t)}</a>
      <span class="muted">${daysText(t.days_left)} · מוכנות ${t.readiness.number}</span></li>`).join("")}</ul>` : ""}`);
}
