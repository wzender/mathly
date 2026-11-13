// The manager's screens: every class (make, change, delete), every student, the curriculum and the subjects. A manager sees no learning data.
import { api } from "./api.js";
import { esc } from "./math.js";
import * as subjectsTab from "./subjects_tab.js";

let draw, tab = "classes", editing = null, draft = null, flash = { message: "", error: "" }, lessonId = null;
// draft: what was typed in the editor when a save was refused, so the form keeps it and the person can fix one thing

const note = () => `${flash.error && tab !== "edit" ? `<p class="error" role="alert">${esc(flash.error)}</p>` : ""}${flash.message ? `<p role="status" id="msg">${esc(flash.message)}</p>` : ""}`;
const tabs = () => `<div class="subtabs" id="mgr-tabs" role="group" aria-label="מנהל כיתות">
  ${[["classes", "כיתות"], ["edit", editing ? "עריכת כיתה" : "כיתה חדשה"], ["students", "תלמידים"], ["curriculum", "תכנית לימודים"], ["subjects", "מקצועות"]].map(([id, label]) =>
    `<button type="button" data-tab="${id}" aria-pressed="${tab === id || (tab === "lesson" && id === "subjects")}">${label}</button>`).join("")}</div>`;

async function render() {
  let body, failed = false;
  try {   // a tab whose data cannot be read says so, instead of the click doing nothing
    if (tab === "edit") subjects = (await api("/api/subjects")).subjects;
    body = tab === "classes" ? await classesView() : tab === "students" ? await studentsView() : tab === "curriculum" ? await curriculumView()
      : tab === "subjects" ? await subjectsTab.view() : tab === "lesson" ? `<div id="lesson-slot"></div>` : editorView();
  } catch (e) {
    failed = true;
    body = `<p class="error" role="alert" id="tab-error">לא הצלחנו לפתוח את הלשונית: ${esc(e.message)}</p>`;
  }
  draw(`<section id="mgr"><h2>מנהל כיתות</h2>${tabs()}${note()}${body}</section>`);
  document.getElementById("mgr-tabs").addEventListener("click", event => {
    const next = event.target.closest("[data-tab]")?.dataset.tab;
    if (!next) return;
    if (next === "edit" && tab !== "edit") editing = null;
    draft = null;
    go(next);
  });
  if (failed) { flash = { message: "", error: "" }; return; }
  if (tab === "classes") wireClasses();
  if (tab === "curriculum") wireCurriculum();
  const openLesson = id => { lessonId = id; go("lesson"); };
  if (tab === "subjects") subjectsTab.wire(go, (message, error) => { flash = { message, error }; }, openLesson);
  if (tab === "lesson") (await import("./lesson_editor.js")).open(document.getElementById("lesson-slot"), lessonId, () => go("subjects"));
  if (tab === "edit") wireEditor();
  if (tab === "edit" && flash.error) {   // the form is long: bring the reason into view, next to the buttons that were pressed
    const reason = document.getElementById("form-error");
    reason.scrollIntoView({ block: "center" });
    reason.focus();
  }
  flash = { message: "", error: "" };
}

/** The curriculum: the date by which each lesson should be completed, one for the whole school. */
async function curriculumView() {
  const lessons = await api("/api/curriculum");
  return `<form class="card" id="curriculum-form"><h3>תכנית לימודים</h3>
    <p class="muted">התאריך שעד אליו כל שיעור אמור להסתיים. תלמיד שלא סיים שיעור אחרי התאריך רואה אותו מסומן בפיגור. אפשר להשאיר תאריך ריק.</p>
    ${[...new Set(lessons.map(l => l.subject?.id || "math"))].map(sid => {
      const mine = lessons.filter(l => (l.subject?.id || "math") === sid);
      return `<section class="curriculum-subject" data-subject="${esc(sid)}"><h4>${esc(mine[0].subject?.name || "מתמטיקה")}</h4>
      <ul class="plain curriculum">${mine.map(l => `<li><label for="due-${esc(l.id)}">${esc(l.name)} <span class="muted">${esc(l.month)}</span></label>
      <input id="due-${esc(l.id)}" type="date" data-lesson="${esc(l.id)}" value="${esc(l.due_date || "")}"></li>`).join("")}</ul></section>`;
    }).join("")}
    <p><button class="primary" type="submit" id="save-curriculum">שמירה</button></p></form>`;
}

function wireCurriculum() {
  document.getElementById("curriculum-form").addEventListener("submit", async event => {
    event.preventDefault();
    const dates = Object.fromEntries([...document.querySelectorAll("#curriculum-form [data-lesson]")].map(i => [i.dataset.lesson, i.value || null]));
    try { await api("/api/curriculum", { method: "PUT", body: { dates } }); flash = { message: "התכנית נשמרה.", error: "" }; }
    catch (e) { flash = { message: "", error: e.message }; }
    go("curriculum");
  });
}

const go = next => { tab = next; return render(); };

async function classesView() {
  const classes = await api("/api/classes");
  return `<div class="hrow" style="margin-bottom:10px"><button class="primary" type="button" id="new-class">+ כיתה חדשה</button>
    <span class="muted">${classes.length} כיתות</span></div>
    ${classes.length ? `<div class="cards" id="classes">${classes.map(c => `<article class="card" data-id="${c.id}">
      <div class="hrow"><h3 class="grow">${esc(c.name)}</h3><button type="button" data-edit="${c.id}">עריכה</button><button type="button" class="danger" data-delete="${c.id}">מחיקה</button></div>
      <p style="margin:0;font-size:14px">מורה: <span dir="ltr">${esc(c.teacher_email || "עוד לא נבחר")}</span><br>
      ${c.students} תלמידים · AI: <b>${c.ai_enabled ? "פועל" : "כבוי"}</b> · ${c.ai_daily_checks} בדיקות ביום</p></article>`).join("")}</div>`
      : `<section class="card"><p class="muted">עוד אין כיתות. פתחו כיתה ראשונה והוסיפו את התלמידים.</p></section>`}`;
}

function wireClasses() {
  document.getElementById("new-class").addEventListener("click", () => { editing = null; draft = null; go("edit"); });
  document.getElementById("classes")?.addEventListener("click", async event => {
    const edit = event.target.closest("[data-edit]")?.dataset.edit, del = event.target.closest("[data-delete]")?.dataset.delete;
    if (edit) { editing = await api(`/api/classes/${edit}`); draft = null; return go("edit"); }
    if (del) {
      const card = event.target.closest("article");
      if (!confirm(`למחוק את הכיתה "${card.querySelector("h3").textContent}"? ההתקדמות של התלמידים נשמרת.`)) return;
      try { await api(`/api/classes/${del}`, { method: "DELETE" }); flash.message = "הכיתה נמחקה."; }
      catch (e) { flash.error = e.message; }
      go("classes");
    }
  });
}

let subjects = [];   // every subject, for the class editor's choice (loaded when the editor opens)

function editorView() {
  const c = editing, d = draft;   // a refused save keeps what was typed
  const value = (typed, saved, fallback = "") => d ? (typed ?? fallback) : (saved ?? fallback);
  const studies = d ? d.subjects : (c?.subjects || ["math"]);
  return `<form class="card" id="class-form"><h3>${c ? `עריכת ${esc(c.name)}` : "כיתה חדשה"}</h3>
    <label for="c-name">שם הכיתה</label><input id="c-name" required maxlength="80" autocomplete="off" value="${esc(value(d?.name, c?.name))}">
    <label for="c-teacher">מורה הכיתה (כתובת אחת; לא אחד התלמידים של הכיתה)</label>
    <input id="c-teacher" type="text" dir="ltr" autocomplete="off" value="${esc(value(d?.teacher_email, c?.teacher_email))}">
    <label for="c-students">תלמידים (כתובת בכל שורה; תלמיד יכול להיות בכמה כיתות)</label>
    <textarea id="c-students" dir="ltr" spellcheck="false">${esc(d ? d.students : (c?.student_emails || []).join("\n"))}</textarea>
    <div class="hrow" style="margin-top:12px"><label class="switch"><input id="c-ai" type="checkbox" ${value(d?.ai_enabled, c?.ai_enabled, false) ? "checked" : ""}> AI לכיתה</label>
      <label for="c-budget" style="margin:0">בדיקות AI ביום</label><input id="c-budget" type="number" min="0" max="10000" style="width:110px" value="${value(d?.ai_daily_checks, c?.ai_daily_checks, 150)}"></div>
    <p class="muted">ה־AI כבוי עד שבית הספר מאשר שהמשפחות מסכימות. רק אחרי זה מפעילים אותו.</p>
    <fieldset class="c-subjects" id="c-subjects"><legend>מקצועות שהכיתה לומדת</legend>
      ${subjects.map(s => `<label class="switch"><input type="checkbox" value="${esc(s.id)}" ${studies.includes(s.id) ? "checked" : ""}> <span aria-hidden="true">${esc(s.icon)}</span> ${esc(s.name)}</label>`).join("")}
      <p class="muted">הכיתה לומדת את כל השיעורים שפורסמו במקצועות שנבחרו. הסרת מקצוע לא מוחקת את ההתקדמות של התלמידים.</p></fieldset>
    ${flash.error ? `<p class="error" role="alert" id="form-error" tabindex="-1"><b>לא נשמר:</b> ${esc(flash.error)}</p>` : ""}
    <div class="hrow"><button class="primary" type="submit" id="c-save">${c ? "שמירת השינויים" : "פתיחת הכיתה"}</button><button type="button" id="c-cancel">ביטול</button></div></form>`;
}

function wireEditor() {
  document.getElementById("c-cancel").addEventListener("click", () => { editing = null; draft = null; go("classes"); });
  document.getElementById("class-form").addEventListener("submit", async event => {
    event.preventDefault();
    const body = {
      name: document.getElementById("c-name").value,
      teacher_email: document.getElementById("c-teacher").value.trim() || null,
      students: document.getElementById("c-students").value,
      ai_enabled: document.getElementById("c-ai").checked,
      ai_daily_checks: Number(document.getElementById("c-budget").value),
      subjects: [...document.querySelectorAll("#c-subjects input:checked")].map(i => i.value),
    };
    try {
      const saved = editing ? await api(`/api/classes/${editing.id}`, { method: "PUT", body }) : await api("/api/classes", { method: "POST", body });
      flash.message = `${editing ? "השינויים נשמרו" : "הכיתה נפתחה"}: ${saved.name}.${saved.invalid?.length ? ` לא נראה כמו מייל: ${saved.invalid.join(", ")}` : ""}`;
      editing = null; draft = null;
      go("classes");
    } catch (e) { draft = body; flash.error = e.message; go("edit"); }
  });
}

async function studentsView() {
  const students = await api("/api/students");
  return `<div class="tablewrap" id="students-list"><table class="data"><thead><tr><th>תלמיד</th><th>כיתות</th></tr></thead>
    <tbody>${students.length ? students.map(s => `<tr><td dir="ltr">${esc(s.email)}</td><td>${s.classes.map(esc).join(" · ")}</td></tr>`).join("")
      : `<tr><td colspan="2" class="muted">עדיין לא נוספו תלמידים לכיתות.</td></tr>`}</tbody></table></div>`;
}

export async function show(me, view) {
  draw = view;
  tab = "classes"; editing = null;
  await render();
}
