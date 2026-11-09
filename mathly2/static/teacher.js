// The teacher's home: the classes I teach, each with its students; I add (a pasted list) and remove students of my own classes.
import { api, lastAnswer, swr } from "./api.js";
import { esc, fmt } from "./math.js";
import { daysText, shortDate } from "./ui.js";

let draw;   // the app's view() function

const tabs = active => `<div class="subtabs" id="teacher-tabs" role="group" aria-label="המורה">
  <button type="button" data-tab="classes" aria-pressed="${active === "classes"}">הכיתות שלי <span class="tab-count" data-count="classes"></span></button>
  <button type="button" data-tab="tests" aria-pressed="${active === "tests"}">מבחנים <span class="tab-count" data-count="tests"></span></button>
  <button type="button" data-tab="assignments" aria-pressed="${active === "assignments"}">משימות <span class="tab-count" data-count="assignments"></span></button>
  <button type="button" data-tab="inbox" aria-pressed="${active === "inbox"}">תיבת בדיקה <span class="tab-count" data-count="inbox"></span></button>
  <button type="button" data-tab="progress" aria-pressed="${active === "progress"}">התקדמות <span class="tab-count" data-count="progress"></span></button></div>`;

const work = () => import("./teacher_work.js");
const context = { draw: html => draw(html), tabs: active => tabs(active), wire: () => wireTabs() };

/** The number of items in each tab, from the server, filled in after the screen is drawn (and so refreshed after every action). */
async function fillCounts() {
  const show = counts => document.querySelectorAll("#teacher-tabs [data-count]").forEach(el => { el.textContent = counts[el.dataset.count]; });
  const known = lastAnswer("/api/teaching/counts");
  if (known) show(known);                                     // the last numbers at once, the fresh ones when they arrive
  try { show(await api("/api/teaching/counts")); } catch { /* the tabs work without the numbers */ }
}

function wireTabs() {
  fillCounts();
  const screens = { classes: showClasses, tests: showTests, assignments: () => work().then(m => m.showAssignments(context)), inbox: () => work().then(m => m.showInbox(context)), progress: () => import("./teacher_progress.js").then(m => m.show(context)) };
  document.querySelectorAll("#teacher-tabs [data-tab]").forEach(b => b.addEventListener("click", () => screens[b.dataset.tab]()));
}

function report(result) {
  const lines = [];
  if (result.added.length) lines.push(`נוספו ${result.added.length} תלמידים.`);
  if (result.already_here.length) lines.push(`${result.already_here.length} כבר היו בכיתה.`);
  if (result.teacher.length) lines.push(`${result.teacher.map(esc).join(", ")}: מורה הכיתה לא יכול להיות גם תלמיד בה.`);
  if (result.invalid.length) lines.push(`לא נראה כמו מייל: ${result.invalid.map(esc).join(", ")}`);
  return lines;
}

const showClasses = (notes = {}) => swr("/api/teaching", classes => drawClasses(classes, notes));

async function drawClasses(classes, notes) {
  draw(`${tabs("classes")}<section id="teaching"><h2>הכיתות שלי</h2>
    ${classes.length ? `<div class="cards">${classes.map(c => `<article class="card class-card" data-id="${c.id}">
      <div class="hrow"><h3 class="grow">${esc(c.name)}</h3><span class="tag">${c.students.length} תלמידים</span><button type="button" data-progress="${c.id}">התקדמות</button></div>
      <p class="muted" style="margin:0 0 8px">${c.ai_enabled ? "AI פועל" : "AI כבוי: מנהל הכיתות מפעיל"}</p>
      ${c.students.length ? `<ul class="plain students">${c.students.map(s => `<li><span dir="ltr">${esc(s.email)}</span>
        <span class="muted">${s.signed_in ? "נכנס/ה" : "עוד לא נכנס/ה"}</span>
        <button type="button" data-remove="${esc(s.email)}" aria-label="הסרת ${esc(s.email)}">הסרה</button>
        <button type="button" data-wipe="${esc(s.email)}" aria-label="מחיקת התמונות של ${esc(s.email)}">מחיקת תמונות</button></li>`).join("")}</ul>`
        : `<p class="muted">עוד אין תלמידים בכיתה.</p>`}
      <form class="add-students"><label for="emails-${c.id}">הוספת תלמידים (כתובת בכל שורה)</label>
        <textarea id="emails-${c.id}" class="emails" dir="ltr" required></textarea>
        <div class="report" role="status">${(notes[c.id]?.lines || []).map(l => `<p>${l}</p>`).join("")}</div>
        ${notes[c.id]?.error ? `<p class="error" role="alert">${esc(notes[c.id].error)}</p>` : ""}
        <p><button class="primary" type="submit">הוספה</button></p></form></article>`).join("")}</div>`
      : `<section class="card"><p class="muted">עוד לא שייכו אותך ככיתה. מנהל הכיתות קובע מי מלמד/ת כל כיתה.</p></section>`}</section>`);
  wireTabs();
  document.querySelectorAll("[data-progress]").forEach(b => b.addEventListener("click", () => import("./teacher_progress.js").then(m => m.show(context, Number(b.dataset.progress)))));
  document.querySelectorAll(".class-card").forEach(card => {
    const id = Number(card.dataset.id);
    card.querySelector("form").addEventListener("submit", async event => {
      event.preventDefault();
      try {
        const result = await api(`/api/classes/${id}/students`, { method: "POST", body: { emails: card.querySelector(".emails").value } });
        await showClasses({ [id]: { lines: report(result) } });
      } catch (e) { await showClasses({ [id]: { error: e.message } }); }
    });
    card.addEventListener("click", async event => {
      const wipe = event.target.closest("[data-wipe]");
      if (wipe) {                                                           // the student's answer pictures, on request: two steps (the grades stay)
        wipe.outerHTML = `<span class="confirm"><button type="button" class="danger" data-confirm-wipe="${wipe.dataset.wipe}">אישור מחיקת התמונות</button> <button type="button" data-cancel-wipe>ביטול</button></span>`;
        return;
      }
      if (event.target.closest("[data-cancel-wipe]")) { await showClasses(); return; }
      const sure = event.target.closest("[data-confirm-wipe]")?.dataset.confirmWipe;
      if (sure) {
        try {
          const done = await api(`/api/classes/${id}/pictures/${encodeURIComponent(sure)}`, { method: "DELETE" });
          await showClasses({ [id]: { lines: [`נמחקו ${done.deleted} תמונות של ${esc(sure)}. הציונים וההערות נשארו.`] } });
        } catch (e) { await showClasses({ [id]: { error: e.message } }); }
        return;
      }
      const email = event.target.closest("[data-remove]")?.dataset.remove;
      if (!email) return;
      try {
        await api(`/api/classes/${id}/students/${encodeURIComponent(email)}`, { method: "DELETE" });
        await showClasses({ [id]: { lines: [`${esc(email)} הוסר/ה מהכיתה.`] } });
      } catch (e) { await showClasses({ [id]: { error: e.message } }); }
    });
  });
}

// ---- the tests tab: set a test for a class, change or remove it, see who took the simulation ----

const today = () => new Date().toISOString().slice(0, 10);

function testForm(c, test = null) {
  const id = test ? `edit-${test.id}` : `new-${c.id}`;
  const chosen = new Set(test ? test.lessons.map(l => l.id) : c.lessons.map(l => l.id));
  return `<form class="test-form" data-class="${c.id}"${test ? ` data-test="${test.id}"` : ""} id="form-${id}">
    <label for="date-${id}">תאריך המבחן</label><input id="date-${id}" name="date" type="date" required min="${today()}" value="${test ? test.date : ""}">
    <fieldset><legend>השיעורים שהמבחן כולל</legend>${c.lessons.map(l => `<label class="check"><input type="checkbox" name="lessons" value="${esc(l.id)}"${chosen.has(l.id) ? " checked" : ""}> ${fmt(l.name)}</label>`).join("")}</fieldset>
    <label for="note-${id}">הערה (לא חובה)</label><input id="note-${id}" name="note" maxlength="500" value="${test ? esc(test.note) : ""}">
    <div class="two"><span><label for="q-${id}">מספר שאלות</label><input id="q-${id}" name="questions" type="number" min="1" max="40" value="${test ? test.questions : 12}"></span>
      <span><label for="m-${id}">דקות</label><input id="m-${id}" name="minutes" type="number" min="5" max="180" value="${test ? test.minutes : 45}"></span></div>
    <p class="error form-error" role="alert" hidden></p>
    <p><button class="primary" type="submit">${test ? "שמירת השינויים" : "קביעת המבחן"}</button>${test ? ` <button type="button" data-cancel>ביטול</button>` : ""}</p></form>`;
}

function testCard(c, t) {
  const open = t.days_left > 0;
  return `<article class="card test-row" data-test="${t.id}"><div class="hrow"><h4 class="grow">מבחן ב־${shortDate(t.date)} <span class="muted">(${daysText(t.days_left)})</span></h4>
      <span class="tag sim-count">${t.simulation.taken} מתוך ${t.simulation.total} עשו סימולציה</span></div>
    <p class="muted">${t.lessons.map(l => fmt(l.name)).join(", ")}${t.note ? ` · ${esc(t.note)}` : ""} · ${t.questions} שאלות · ${t.minutes} דקות</p>
    ${t.simulation.missing.length ? `<p class="sim-missing"><b>עוד לא עשו סימולציה:</b> ${t.simulation.missing.map(e => `<span dir="ltr">${esc(e)}</span>`).join(", ")}</p>`
      : t.simulation.total ? `<p class="sim-missing">כולם עשו את מבחן הסימולציה.</p>` : ""}
    ${t.students.length ? `<div class="tablewrap"><table class="data readiness-table"><thead><tr><th>תלמיד</th><th>מוכנות</th><th>שליטה</th><th>תרגול</th><th>סימולציה</th></tr></thead>
      <tbody>${t.students.map(s => `<tr><td dir="ltr">${esc(s.email)}</td><td>${s.readiness.number} · ${esc(s.readiness.label)}</td>
        <td>${s.readiness.parts.M === null ? "—" : s.readiness.parts.M + "%"}</td><td>${s.readiness.parts.E ?? "—"}</td><td>${s.readiness.parts.S ?? "—"}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <p class="test-actions">${open ? `<button type="button" data-edit="${t.id}">שינוי</button> ` : ""}<button type="button" data-remove-test="${t.id}">הסרה</button></p>
    <div class="edit-slot" data-slot="${t.id}"></div></article>`;
}

const showTests = () => swr("/api/teaching/tests", drawTests);

async function drawTests(classes) {
  draw(`${tabs("tests")}<section id="tests"><h2>מבחנים</h2>
    ${classes.length ? classes.map(({ class: c, tests }) => `<section class="card class-tests" data-class="${c.id}"><h3>${esc(c.name)}</h3>
      ${tests.length ? tests.map(t => testCard(c, t)).join("") : `<p class="muted">עוד לא נקבע מבחן לכיתה.</p>`}
      <details class="set-test"><summary>קביעת מבחן</summary>${testForm(c)}</details></section>`).join("")
      : `<section class="card"><p class="muted">עוד לא שייכו אותך ככיתה. מנהל הכיתות קובע מי מלמד/ת כל כיתה.</p></section>`}</section>`);
  wireTabs();
  const byId = new Map(classes.flatMap(({ class: c, tests }) => tests.map(t => [t.id, { c, t }])));
  const root = document.getElementById("tests");
  root.addEventListener("submit", async event => {
    const form = event.target.closest(".test-form");
    if (!form) return;
    event.preventDefault();
    const data = new FormData(form), error = form.querySelector(".form-error");
    const body = { date: data.get("date"), lessons: data.getAll("lessons"), note: data.get("note") || "", questions: Number(data.get("questions")), minutes: Number(data.get("minutes")) };
    error.hidden = true;
    try {
      if (form.dataset.test) await api(`/api/tests/${form.dataset.test}`, { method: "PUT", body });
      else await api(`/api/classes/${form.dataset.class}/tests`, { method: "POST", body });
      await showTests();
    } catch (e) {
      error.textContent = e.message;
      error.hidden = false;
      error.scrollIntoView({ block: "nearest" });                                    // the form keeps what was typed
    }
  });
  root.addEventListener("click", async event => {
    const edit = event.target.closest("[data-edit]")?.dataset.edit;
    if (edit) {
      const { c, t } = byId.get(Number(edit));
      root.querySelector(`[data-slot="${edit}"]`).innerHTML = testForm(c, t);
      return;
    }
    if (event.target.closest("[data-cancel]")) { event.target.closest(".edit-slot").innerHTML = ""; return; }
    const remove = event.target.closest("[data-remove-test]");
    if (remove) {                                                                    // two steps, so a slip does not remove a test
      remove.outerHTML = `<span class="confirm"><button type="button" class="danger" data-confirm-remove="${remove.dataset.removeTest}">אישור הסרה</button> <button type="button" data-cancel-remove>ביטול</button></span>`;
      return;
    }
    if (event.target.closest("[data-cancel-remove]")) { await showTests(); return; }
    const confirm = event.target.closest("[data-confirm-remove]")?.dataset.confirmRemove;
    if (confirm) { await api(`/api/tests/${confirm}`, { method: "DELETE" }); await showTests(); }
  });
}

export async function show(me, view) {
  draw = view;
  await showClasses();
}
