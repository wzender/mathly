// Teacher screens: my classes, and one class with its students.
import { api } from "./api.js";
import { esc } from "./math.js";

let draw;   // the app's view() function

const note = (text, kind = "muted") => text ? `<p class="${kind}" role="${kind === "error" ? "alert" : "status"}">${text}</p>` : "";

async function showClasses(message = "", error = "") {
  const classes = await api("/api/classes");
  draw(`<section class="card"><h2>הכיתות שלי</h2>
    ${classes.length ? `<ul class="plain" id="classes">${classes.map(c =>
      `<li><a href="#class/${c.id}">${esc(c.name)}</a><span class="muted">${c.students} תלמידים</span></li>`).join("")}</ul>`
      : `<p class="muted">עוד אין כיתות. אפשר ליצור את הראשונה כאן.</p>`}</section>
    <section class="card"><h2>כיתה חדשה</h2>${note(esc(error), "error")}${note(esc(message))}
    <form id="new-class"><label for="class-name">שם הכיתה</label>
    <input id="class-name" required maxlength="60" autocomplete="off">
    <p><button class="primary" type="submit">יצירת כיתה</button></p></form></section>`);
  document.getElementById("new-class").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const created = await api("/api/classes", { method: "POST", body: { name: document.getElementById("class-name").value } });
      await showClasses(`הכיתה "${created.name}" נוצרה`);
    } catch (e) { await showClasses("", e.message); }
  });
}

function report(result) {
  const lines = [];
  if (result.added.length) lines.push(`נוספו ${result.added.length} תלמידים.`);
  if (result.already_here.length) lines.push(`${result.already_here.length} כבר היו בכיתה.`);
  for (const x of result.elsewhere)
    lines.push(`${esc(x.email)} כבר שייך/ת לכיתה "${esc(x.class_name)}" ולא נוסף/ה. תלמיד יכול להיות רק בכיתה אחת.`);
  if (result.invalid.length) lines.push(`לא נראה כמו מייל: ${result.invalid.map(esc).join(", ")}`);
  return lines;
}

async function showClass(id, lines = [], error = "") {
  const cls = await api(`/api/classes/${id}`);
  draw(`<p><a href="#">← הכיתות שלי</a></p>
    <section class="card"><h2>${esc(cls.name)}</h2>
    ${cls.students.length ? `<ul class="plain" id="students">${cls.students.map(s =>
      `<li><span dir="ltr">${esc(s.email)}</span><span class="muted">${s.signed_in ? "נכנס/ה" : "עוד לא נכנס/ה"}</span>
       <button type="button" data-remove="${esc(s.email)}" aria-label="הסרת ${esc(s.email)}">הסרה</button></li>`).join("")}</ul>`
      : `<p class="muted">עוד אין תלמידים בכיתה.</p>`}</section>
    <section class="card"><h2>הוספת תלמידים</h2>${note(esc(error), "error")}
    <div id="report">${lines.map(l => `<p role="status">${l}</p>`).join("")}</div>
    <form id="add"><label for="emails">כתובות מייל (אפשר להדביק רשימה)</label>
    <textarea id="emails" dir="ltr" required></textarea>
    <p><button class="primary" type="submit">הוספה</button></p></form></section>`);
  document.getElementById("add").addEventListener("submit", async event => {
    event.preventDefault();
    try {
      const result = await api(`/api/classes/${id}/students`, { method: "POST", body: { emails: document.getElementById("emails").value } });
      await showClass(id, report(result));
    } catch (e) { await showClass(id, [], e.message); }
  });
  document.getElementById("students")?.addEventListener("click", async event => {
    const email = event.target.closest("[data-remove]")?.dataset.remove;
    if (!email) return;
    try {
      await api(`/api/classes/${id}/students/${encodeURIComponent(email)}`, { method: "DELETE" });
      await showClass(id, [`${esc(email)} הוסר/ה מהכיתה.`]);
    } catch (e) { await showClass(id, [], e.message); }
  });
}

async function route() {
  const match = location.hash.match(/^#class\/(\d+)$/);
  try { await (match ? showClass(Number(match[1])) : showClasses()); }
  catch (e) { draw(`<section class="card"><p class="error" role="alert">${esc(e.message)}</p><p><a href="#">← הכיתות שלי</a></p></section>`); }
}

export async function show(me, view) {
  draw = view;
  addEventListener("hashchange", route);
  await route();
}
