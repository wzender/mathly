// The student's grades: each lesson's best quiz grade, and each real test's exercise tests and simulation (best grade, tries, last date).
// Assignments will add their rows later.
import { swr } from "./api.js";
import { esc, fmt } from "./math.js";
import { shortDate, tabs } from "./ui.js";

const day = iso => iso ? new Date(iso).toLocaleDateString("he-IL", { day: "numeric", month: "numeric" }) : "";
const tries = n => `${n} ${n === 1 ? "ניסיון" : "ניסיונות"}`;

function row({ attrs, href, title, best, attempts, last }) {
  return `<li ${attrs}><a href="${href}"><b>${title}</b></a>
    <span class="gr-num" aria-label="הציון הטוב ביותר ${best}">${best}</span>
    <span class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${best}"><i style="width:${best}%"></i></span>
    <span class="muted">${tries(attempts)}${last ? ` · האחרון ב־${day(last)}` : ""}</span></li>`;
}

const testTitle = (t, suffix) => `מבחן ב־${shortDate(t.date)}: ${suffix}${t.removed ? " (הוסר)" : ""}`;

export const show = view => swr("/api/grades", data => draw(view, data));

function draw(view, { quizzes, exercise_tests: exercises = [], simulations = [], assignments = [] }) {
  const none = !quizzes.length && !exercises.length && !simulations.length && !assignments.length;
  view(`${tabs("grades")}<section class="card" id="grades"><h2>הציונים שלי</h2>
    ${none ? `<p class="muted" id="no-grades">עוד אין ציונים. הבוחן של כל שיעור מחכה בסוף השיעור במסלול.</p>` : ""}
    ${quizzes.length ? `<h3>בחנים</h3><ul class="plain grades" id="quiz-grades">${quizzes.map(g => row({ attrs: `data-lesson="${esc(g.lesson.id)}"`, href: `#/quiz/${esc(g.lesson.id)}`,
      title: fmt(g.lesson.name), best: g.best, attempts: g.attempts, last: g.last })).join("")}</ul>` : ""}
    ${exercises.length ? `<h3>מבחני תרגול</h3><ul class="plain grades" id="exercise-grades">${exercises.map(g => row({ attrs: `data-test="${g.test.id}" data-number="${g.number}"`,
      href: `#/test/${g.test.id}`, title: testTitle(g.test, `מבחן תרגול ${g.number}`), best: g.best, attempts: g.attempts, last: g.last })).join("")}</ul>` : ""}
    ${assignments.length ? `<h3>משימות</h3><ul class="plain grades" id="assignment-grades">${assignments.map(g => `<li data-assignment="${g.assignment.id}">
        <a href="#/assignment/${g.assignment.id}"><b>${fmt(g.assignment.title)}</b>${g.assignment.removed ? " (הוסרה)" : ""}</a>
        <span class="gr-num" aria-label="הציון ${g.grade}">${g.grade}</span>
        <span class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${g.grade}"><i style="width:${g.grade}%"></i></span>
        ${g.note ? `<span class="muted gr-note">הערת המורה: ${fmt(g.note)}</span>` : `<span class="muted">${g.assignment.kind === "exercise_test" ? "מבחן תרגול" : "משימה"}</span>`}</li>`).join("")}</ul>` : ""}
    ${simulations.length ? `<h3>מבחני סימולציה</h3><ul class="plain grades" id="simulation-grades">${simulations.map(g => row({ attrs: `data-test="${g.test.id}"`,
      href: `#/test/${g.test.id}`, title: testTitle(g.test, "מבחן סימולציה"), best: g.best, attempts: g.attempts, last: g.last })).join("")}</ul>` : ""}</section>`);
}
