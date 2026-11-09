// A class's progress for its teacher, per lesson (never per skill), and the readiness for the coming test, with the two period tabs. One class at a time; the class is chosen here when the teacher has several.
import { api, swr } from "./api.js";
import { esc, fmt } from "./math.js";
import { shortDate } from "./ui.js";

const STATE = { completed: ["✓", "הושלם", "m"], learning: ["◐", "בלמידה", "l"], not_started: ["○", "לא התחילו", "n"] };
const VIEWS = [["lessons", "לפי שיעור"], ["readiness", "מוכנות למבחן"]];
let chosen = { classId: null, period: null, view: "lessons" };      // what the teacher last looked at

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
  const rows = t.students.map(s => `<tr data-student="${esc(s.email)}">${who(s)}<td><b>${s.readiness.number}</b> · ${esc(s.readiness.label)}</td><td>${dash(s.mastery)}${s.mastery === null ? "" : "%"}</td><td>${dash(s.practice)}</td><td>${dash(s.simulation)}</td></tr>`).join("");
  return `<p>מבחן ב־${shortDate(t.date)} (${t.days_left === 0 ? "היום" : `בעוד ${t.days_left} ימים`}): ${t.lessons.map(esc).join(", ")}</p>
    <div class="tablewrap" tabindex="0" role="region" aria-label="מוכנות"><table class="hm"><thead><tr><th class="sticky">תלמיד</th><th>מוכנות</th><th>שליטה</th><th>תרגול</th><th>סימולציה</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function page(ctx, classes, data) {
  const periodTabs = chosen.view === "readiness" ? "" : `<div class="subtabs" id="period-tabs" role="group" aria-label="תקופה">${data.periods.map(p =>
    `<button type="button" data-period="${p.id}" aria-pressed="${p.id === data.period}">${p.label}${p.current ? " (עכשיו)" : ""}</button>`).join("")}</div>`;
  const body = chosen.view === "readiness" ? readiness(data) : lessonsView(data);
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
