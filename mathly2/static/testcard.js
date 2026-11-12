// One real test: its plan with the recommended days, the readiness bar, the two exercise tests, the simulation and what to practise first.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";
import { readinessBar } from "./home.js";
import { daysText, forSubject, homeHref, setSubject, shortDate, tabs } from "./ui.js";

const STEP_NAMES = { path: "לסיים את המסלול של השיעורים", ex1: "מבחן תרגול 1", ex2: "מבחן תרגול 2", sim: "מבחן סימולציה", review: "חזרה על מה שנפל בסימולציה" };

function planList(test) {
  return `<ol class="plan" id="plan">${test.plan.map(step => {
    const when = step.id === "path" ? `עד ${step.until} ימים לפני` : step.id === "review" ? `${step.day} ימים לפני ועד המבחן` : `בערך ${step.day} ימים לפני`;
    return `<li class="${step.done ? "done" : ""}" data-step="${step.id}"><span class="mark" aria-hidden="true">${step.done ? "✓" : "○"}</span>
      <span><b>${STEP_NAMES[step.id]}</b><br><span class="muted">${when} · ${step.done ? "בוצע" : "עוד לא"}</span></span></li>`;
  }).join("")}</ol><p class="muted">הימים הם המלצה: אפשר להתחיל כל שלב קודם או אחר כך.</p>`;
}

function exercises(test) {
  return `<ul class="plain" id="exercises">${test.exercise_tests.map(e => `<li data-exercise="${e.number}">
    <span><b>מבחן תרגול ${e.number}</b><br><span class="muted">${e.best === null ? "עוד לא נעשה" : `הציון הטוב: ${e.best} · ${e.attempts} ${e.attempts === 1 ? "ניסיון" : "ניסיונות"}`}</span></span>
    <a class="button" href="#/exam/${test.id}/${e.number}">${e.open ? "להמשיך" : e.attempts ? "שוב" : "התחלה"}</a></li>`).join("")}</ul>`;
}

function simulation(test) {
  const s = test.simulation;
  const lead = s.taken ? `<p>הציון: <b id="sim-grade">${s.grade}</b></p>${s.review.length ? `<p>מיומנויות לחזרה:</p><ul class="plain" id="sim-review">${s.review.map(r =>
        `<li><a href="#/skill/${esc(r.id)}">${fmt(r.name)}</a></li>`).join("")}</ul>` : `<p class="muted">אין מיומנויות לחזרה. כל הכבוד!</p>`}
      <p><a class="button" href="#/sim/${test.id}">לתוצאה</a></p>`
    : s.open_now ? `<p><b class="req">חובה</b> המבחן פתוח עד יום המבחן. אפשר לעשות אותו פעם אחת.</p>
      <p><a class="button primary" id="sim-start" href="#/sim/${test.id}">${s.in_progress ? "להמשיך" : "התחלה"}</a></p>`
    : `<p id="sim-closed">מבחן הסימולציה ייפתח ב־${shortDate(s.opens_on)} (בעוד ${s.opens_in_days} ימים). אפשר לעשות אותו פעם אחת.</p>`;
  return `<div id="simulation" data-taken="${s.taken}">${lead}</div>`;
}

export async function show(view, id) {
  const test = await api(`/api/tests/${encodeURIComponent(id)}`);
  setSubject(test.subject_id);                                         // a test belongs to one subject: its home and tab bar follow it
  const home = await api(forSubject("/api/home"));
  const others = home.tests.filter(t => t.id !== test.id);
  view(`${tabs("home")}<p><a class="back" href="${homeHref()}">‹ הבית</a></p>
    <section class="card" id="test-card" data-test="${test.id}"><h2>מבחן ב־${shortDate(test.date)} <span class="muted">(${daysText(test.days_left)})</span></h2>
      <p class="muted">${test.lessons.map(l => fmt(l.name)).join(", ")}${test.note ? ` · ${esc(test.note)}` : ""}<br>${test.questions} שאלות · ${test.minutes} דקות</p>
      ${readinessBar(test.readiness)}</section>
    <section class="card"><h3>התוכנית</h3>${planList(test)}</section>
    <section class="card"><h3>מבחני תרגול</h3>${exercises(test)}
      ${test.practice_first.length ? `<p id="practice-first"><b>כדאי לתרגל קודם:</b> ${test.practice_first.map(s => `<a class="ex-chip link" href="#/skill/${esc(s.id)}">${fmt(s.name)}</a>`).join(" ")}</p>
        <p class="muted">אלה מיומנויות שעוד לא התחלתם, ולכן אין להן שאלות במבחני התרגול.</p>` : ""}</section>
    <section class="card"><h3>מבחן סימולציה</h3>${simulation(test)}</section>
    ${others.length ? `<section class="card"><h3>מבחנים נוספים</h3><ul class="plain" id="other-tests">${others.map(t => `<li><a href="#/test/${t.id}">${shortDate(t.date)} · ${t.lessons.map(l => fmt(l.name)).join(", ")}</a>
      <span class="muted">${daysText(t.days_left)} · מוכנות ${t.readiness.number}</span></li>`).join("")}</ul></section>` : ""}`);
}
