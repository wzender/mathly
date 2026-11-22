// A class's progress for its teacher, per lesson (never per skill), and the readiness for the coming test, with the two period tabs. One class at a time; the class is chosen here when the teacher has several.
import { api, swr } from "./api.js";
import { esc, fmt } from "./math.js";
import { shortDate } from "./ui.js";

const STATE = { completed: ["✓", "הושלם", "m"], learning: ["◐", "בלמידה", "l"], not_started: ["○", "לא התחילו", "n"] };
const VIEWS = [["lessons", "לפי שיעור"], ["readiness", "מוכנות למבחן"], ["activity", "פעילות"]];
let chosen = { classId: null, period: null, view: "lessons", days: 14 };      // what the teacher last looked at

const dash = value => value === null || value === undefined ? "—" : value;
const first = email => esc(email.split("@")[0]);
const who = s => `<th scope="row" class="sticky"><span dir="ltr" title="${esc(s.email)}">${first(s.email)}</span>${s.signed_in ? "" : ` <span class="muted">(לא נכנס/ה)</span>`}</th>`;

function lessonsView(data) {
  if (!data.lessons.length) return `<p class="muted">אין שיעורים בתקופה הזו.</p>`;
  const head = data.lessons.map(l => `<th class="lesson-col">${fmt(l.name)}${l.due_date ? `<br><span class="muted">עד ${shortDate(l.due_date)}</span>` : ""}</th>`).join("");
  const rows = data.students.map(s => `<tr data-student="${esc(s.email)}">${who(s)}${data.lessons.map(l => {
    const c = s.lessons[l.id], word = (STATE[c.state] || STATE.not_started)[1];
    return `<td class="cov${c.completed ? " done" : ""}${c.behind ? " behind" : ""}" data-lesson="${esc(l.id)}" data-state="${esc(c.state)}" aria-label="${word}${c.behind ? ", בפיגור" : ""}">
      <div class="pbar"><i style="width:${c.percent}%"></i><span>${c.percent}%</span></div>
      <div class="qgrade">${dash(c.best)}${c.behind ? ` <span class="warn" data-behind aria-hidden="true">⚠</span>` : ""}</div></td>`;
  }).join("")}</tr>`).join("");
  return `<div class="tablewrap" tabindex="0" role="region" aria-label="התקדמות לפי שיעור"><table class="hm"><thead><tr><th class="sticky">תלמיד</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>
    <p class="muted legend">הסרגל: אחוז המיומנויות שנשלטו (זהב: השיעור הושלם) · המספר: הציון בבוחן · ⚠ בפיגור</p>`;
}

function readiness(data) {
  const t = data.test;
  if (!t) return `<p class="muted" id="no-test">עוד לא נקבע מבחן קרוב לכיתה הזו.</p>`;
  const rows = t.students.map(s => `<tr data-student="${esc(s.email)}">${who(s)}<td><b>${s.readiness.number}</b> · ${esc(s.readiness.label)}</td><td>${dash(s.mastery)}${s.mastery === null ? "" : "%"}</td><td>${dash(s.practice)}${s.practices ? ` <span class="muted">(${s.practices})</span>` : ""}</td><td>${dash(s.simulation)}${s.simulations ? ` <span class="muted">(${s.simulations})</span>` : ""}</td></tr>`).join("");
  return `<p>מבחן ב־${shortDate(t.date)} (${t.days_left === 0 ? "היום" : `בעוד ${t.days_left} ימים`}): ${t.lessons.map(esc).join(", ")}</p>
    <div class="tablewrap" tabindex="0" role="region" aria-label="מוכנות"><table class="hm"><thead><tr><th class="sticky">תלמיד</th><th>מוכנות</th><th>שליטה</th><th>תרגול: הטוב (כמה)</th><th>סימולציה: הטוב (כמה)</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="muted">המוכנות עולה רק ממבחני תרגול וסימולציות. השליטה במסלול מוצגת לידה ולא נכללת בה.</p>`;
}

/* ---------- each student's activity: how much and how long, in all and day by day (progress.py class_activity) ---------- */

const minutes = m => m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} שע׳` : `${m} דק׳`;
const percent = (right, all) => all ? `${Math.round(100 * right / all)}%` : "—";

/** The days of the range as small bars (the class's busiest day is full height), with each day's numbers on hover. */
function bars(daily, top) {
  return `<span class="act-bars" aria-hidden="true">${daily.map(d => `<i style="height:${top ? Math.max(d.answers || d.tests ? 8 : 0, Math.round(100 * d.answers / top)) : 0}%"
    title="${shortDate(d.day)}: ${d.answers} תרגילים, ${minutes(d.minutes)}${d.tests ? `, ${d.tests} בחנים/מבחנים` : ""}"></i>`).join("")}</span>`;
}

function activityTable(data) {
  if (!data.students.length) return `<p class="muted">אין עדיין תלמידים בכיתה.</p>`;
  const top = Math.max(1, ...data.students.flatMap(s => s.daily.map(d => d.answers)));
  const row = (s, i) => `<tr data-student="${i}">${who(s)}
      <td><button type="button" class="act-open" data-open-student="${i}" aria-expanded="false" aria-label="פירוט יומי של ${esc(s.email)}">${bars(s.daily, top)}</button></td>
      <td>${s.recent.answers}</td><td>${minutes(s.recent.minutes)}</td><td>${s.recent.days}</td><td>${percent(s.recent.correct, s.recent.answers)}</td>
      <td>${s.total.answers}</td><td>${minutes(s.total.minutes)}</td><td>${s.last_day ? shortDate(s.last_day) : "—"}</td></tr>
    <tr class="act-days" data-days="${i}" hidden><td colspan="9"><div class="act-days-box">${dayTable(s)}</div></td></tr>`;
  return `<div class="tablewrap"><table class="data act-table" id="activity-table"><thead>
      <tr><th rowspan="2" class="sticky">תלמיד</th><th rowspan="2">יום אחר יום</th><th colspan="4">ב־${data.days} הימים האחרונים</th><th colspan="2">מתחילת השנה</th><th rowspan="2">פעילות אחרונה</th></tr>
      <tr><th>תרגילים</th><th>זמן</th><th>ימים</th><th>נכונות</th><th>תרגילים</th><th>זמן</th></tr></thead>
    <tbody>${data.students.map(row).join("")}</tbody></table></div>`;
}

function dayTable(s) {
  const days = s.daily.filter(d => d.answers || d.tests).reverse();
  if (!days.length) return `<p class="muted">לא היה תרגול בימים האלה.</p>`;
  return `<table class="data act-day-table"><thead><tr><th>יום</th><th>תרגילים</th><th>נכונות</th><th>זמן</th><th title="בחנים ומבחנים שהוגשו">מבחנים</th></tr></thead><tbody>${days.map(d =>
    `<tr><td>${shortDate(d.day)}</td><td>${d.answers}</td><td>${percent(d.correct, d.answers)}</td><td>${minutes(d.minutes)}</td><td>${d.tests || "—"}</td></tr>`).join("")}</tbody></table>`;
}

async function showActivity(classId) {
  const slot = document.getElementById("activity-view");
  if (!slot) return;
  await swr(`/api/classes/${classId}/activity?days=${chosen.days}`, data => {
    const here = document.getElementById("activity-view");
    if (!here || chosen.view !== "activity") return;
    here.innerHTML = `<div class="subtabs" id="act-range" role="group" aria-label="טווח">${[7, 14, 30].map(n =>
        `<button type="button" data-days="${n}" aria-pressed="${n === data.days}">${n} ימים</button>`).join("")}</div>
      <p class="muted act-note">תרגילים: כל תשובה בתרגול, בסבבים ובחזרה. הזמן הוא הערכה לפי הפערים בין התשובות (עד 3 דקות לתשובה, הפסקה של יותר מ־5 דקות לא נספרת), ובבחנים ובמבחנים מההתחלה ועד ההגשה.</p>
      ${activityTable(data)}`;
    here.querySelector("#act-range").addEventListener("click", e => {
      const n = Number(e.target.closest("[data-days]")?.dataset.days);
      if (n && n !== chosen.days) { chosen.days = n; showActivity(classId); }
    });
    here.querySelectorAll("[data-open-student]").forEach(b => b.addEventListener("click", () => {
      const rowEl = here.querySelector(`[data-days="${b.dataset.openStudent}"]`), open = rowEl.hidden;
      rowEl.hidden = !open;
      b.setAttribute("aria-expanded", String(open));
    }));
  });
}

function page(ctx, classes, data) {
  const periodTabs = chosen.view !== "lessons" ? "" : `<div class="subtabs" id="period-tabs" role="group" aria-label="תקופה">${data.periods.map(p =>
    `<button type="button" data-period="${p.id}" aria-pressed="${p.id === data.period}">${p.label}${p.current ? " (עכשיו)" : ""}</button>`).join("")}</div>`;
  const body = chosen.view === "readiness" ? readiness(data) : chosen.view === "activity" ? `<div id="activity-view"><p class="muted">טוענים…</p></div>` : lessonsView(data);
  ctx.draw(`${ctx.tabs("progress")}<section id="progress"><h2>התקדמות</h2>
    ${classes.length > 1 ? `<label for="class-pick">כיתה</label><select id="class-pick">${classes.map(c => `<option value="${c.id}"${c.id === data.class.id ? " selected" : ""}>${esc(c.name)}</option>`).join("")}</select>` : `<p class="muted">${esc(data.class.name)}</p>`}
    <div class="subtabs" id="view-tabs" role="group" aria-label="תצוגה">${VIEWS.map(([id, label]) => `<button type="button" data-view="${id}" aria-pressed="${id === chosen.view}">${label}</button>`).join("")}</div>
    ${periodTabs}${body}</section>`);
  ctx.wire();
  document.getElementById("class-pick")?.addEventListener("change", e => show(ctx, Number(e.target.value), null));
  document.getElementById("view-tabs").addEventListener("click", e => {
    const view = e.target.closest("[data-view]")?.dataset.view;
    if (view) { chosen.view = view; page(ctx, classes, data); }                       // the same data, another view
  });
  if (chosen.view === "activity") showActivity(data.class.id);
  document.getElementById("period-tabs")?.addEventListener("click", e => {
    const period = Number(e.target.closest("[data-period]")?.dataset.period);
    if (period) show(ctx, data.class.id, period);
  });
}

/** Open the progress tab for `classId` (the one last looked at, or the first, when not given). */
export async function show(ctx, classId = null, period = null) {
  const classes = await api("/api/teaching");
  if (!classes.length) {
    ctx.draw(`${ctx.tabs("progress")}<section id="progress"><h2>התקדמות</h2><section class="card"><p class="muted">עוד לא שייכו אותך ככיתה. מנהל הכיתות קובע מי מלמד/ת כל כיתה.</p></section></section>`);
    return ctx.wire();
  }
  const id = classes.some(c => c.id === (classId ?? chosen.classId)) ? (classId ?? chosen.classId) : classes[0].id;
  if (id !== chosen.classId || (classId !== null && period === null)) chosen.period = null;
  chosen = { ...chosen, classId: id, period: period ?? chosen.period };
  await swr(`/api/classes/${id}/progress${chosen.period ? `?period=${chosen.period}` : ""}`, data => page(ctx, classes, data));
}
