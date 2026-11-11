// The manager's "מקצועות" tab (add-subjects-and-worksheets): every subject with its lessons. A manager or a developer creates a
// subject, renames it, changes its icon, deletes an empty one and orders its lessons. Math is fixed: it holds the content file's
// lessons, which keep their order; lessons added to math come after them.
import { api } from "./api.js";
import { esc } from "./math.js";

const STATE = { published: "פורסם", draft: "טיוטה", drafting: "בהכנה", failed: "נכשל" };
const stateOf = l => l.status === "drafting" ? "drafting" : l.status === "failed" ? "failed" : l.published ? "published" : "draft";

const icons = (list, chosen, name) => `<div class="sb-icons" role="radiogroup" aria-label="סמל">${list.map((icon, i) =>
  `<label class="sb-icon"><input type="radio" name="${name}" value="${esc(icon)}" ${icon === chosen || (!chosen && i === 0) ? "checked" : ""}>
    <span aria-hidden="true">${esc(icon)}</span><span class="mx-sr">סמל ${i + 1}</span></label>`).join("")}</div>`;

function lessonList(subject) {
  const fixed = subject.fixed ? `<li class="muted">${subject.file_lessons.length} שיעורים מקובץ התוכן (הסדר שלהם קבוע)</li>` : "";
  const rows = subject.lessons.map((l, i) => `<li data-lesson="${l.id}"><span class="grow"><b>${esc(l.name || "שיעור בלי שם")}</b>
      <span class="sb-state sb-${stateOf(l)}">${STATE[stateOf(l)]}</span> <span class="muted">${l.skills} מיומנויות</span></span>
      <button type="button" data-open-lesson="${l.id}">עריכה</button>
      <button type="button" data-move="-1" aria-label="להזיז למעלה את ${esc(l.name)}" ${i === 0 ? "disabled" : ""}>▲</button>
      <button type="button" data-move="1" aria-label="להזיז למטה את ${esc(l.name)}" ${i === subject.lessons.length - 1 ? "disabled" : ""}>▼</button></li>`).join("");
  return `<ul class="plain sb-lessons">${fixed}${rows || (subject.fixed ? "" : `<li class="muted">עוד אין שיעורים במקצוע.</li>`)}</ul>`;
}

const UPLOAD_TYPES = ".pdf,application/pdf,image/jpeg,image/png,image/webp,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function uploadForm(data) {
  return `<form class="card" id="worksheet-form"><h3>דף עבודה חדש</h3>
    <p class="muted">PDF אחד (עד 20 עמודים), עד 10 תמונות, או מסמך Word אחד, עד 15MB. ה־AI מכין ממנו טיוטה של שיעור, ואתם בודקים ומתקנים לפני הפרסום.</p>
    <label for="ws-subject">המקצוע</label><select id="ws-subject">${data.subjects.map(s => `<option value="${esc(s.id)}">${esc(s.icon)} ${esc(s.name)}</option>`).join("")}
      <option value="new">+ מקצוע חדש</option></select>
    <div id="ws-new" hidden><label for="ws-new-name">שם המקצוע החדש</label><input id="ws-new-name" maxlength="60" autocomplete="off">${icons(data.icons, null, "ws-icon")}</div>
    <label for="ws-files">הקובץ או התמונות</label><input id="ws-files" type="file" multiple accept="${UPLOAD_TYPES}" required>
    <p class="error" id="ws-error" role="alert" hidden></p><p class="muted" id="ws-progress" role="status"></p>
    <p><button class="primary" type="submit" id="ws-go">העלאה והכנת טיוטה</button></p></form>`;
}

export async function view() {
  const data = await api("/api/subjects");
  const warning = data.content_error ? `<p class="error" role="alert">לא הצלחנו לקרוא את המקצועות ממסד הנתונים, ולכן רק שיעורי המתמטיקה מקובץ התוכן מוצגים לתלמידים. בדקו שהמיגרציה <span dir="ltr">20261117090000_m2_subjects.sql</span> הוחלה.</p>` : "";
  return `${warning}${uploadForm(data)}<form class="card" id="new-subject"><h3>מקצוע חדש</h3>
      <label for="sb-name">שם המקצוע</label><input id="sb-name" required maxlength="60" autocomplete="off">
      ${icons(data.icons, null, "sb-new-icon")}
      <p><button class="primary" type="submit" id="sb-create">יצירת המקצוע</button></p></form>
    <div class="cards" id="subjects">${data.subjects.map(s => `<article class="card" data-subject="${esc(s.id)}">
      <div class="hrow"><h3 class="grow"><span aria-hidden="true">${esc(s.icon)}</span> ${esc(s.name)}</h3>
        ${s.fixed ? "" : `<button type="button" data-rename>עריכה</button><button type="button" class="danger" data-delete>מחיקה</button>`}</div>
      ${s.fixed ? "" : `<form class="sb-rename" hidden><label for="rn-${esc(s.id)}">שם</label><input id="rn-${esc(s.id)}" maxlength="60" value="${esc(s.name)}">
        ${icons(data.icons, s.icon, `icon-${s.id}`)}<p class="hrow"><button class="primary" type="submit">שמירה</button><button type="button" data-cancel>ביטול</button></p></form>`}
      ${lessonList(s)}</article>`).join("")}</div>`;
}

/** Send one file as the request body (the server takes a PDF, an image or a Word document by its content type). */
async function sendFile(lessonId, file) {
  const { token } = await import("./session.js");
  const kind = file.type || (file.name.toLowerCase().endsWith(".docx") ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : "");
  const response = await fetch(`/api/worksheets/${lessonId}/files`, { method: "POST", body: file, headers: { Authorization: "Bearer " + await token(), "Content-Type": kind } });
  if (!response.ok) {
    let detail = ""; try { detail = (await response.json()).detail; } catch { /* no body */ }
    throw new Error(typeof detail === "string" && detail ? detail : "ההעלאה נכשלה");
  }
}

function wireUpload(openLesson) {
  const form = document.getElementById("worksheet-form"), pick = document.getElementById("ws-subject");
  pick.addEventListener("change", () => { document.getElementById("ws-new").hidden = pick.value !== "new"; });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const error = document.getElementById("ws-error"), progress = document.getElementById("ws-progress"), files = [...document.getElementById("ws-files").files];
    error.hidden = true;
    const body = pick.value === "new"
      ? { new_subject: document.getElementById("ws-new-name").value, icon: form.querySelector("input[name=ws-icon]:checked")?.value }
      : { subject_id: pick.value };
    try {
      progress.textContent = "מתחילים…";
      const lesson = await api("/api/worksheets", { method: "POST", body });
      for (const [i, file] of files.entries()) { progress.textContent = `מעלים ${i + 1} מתוך ${files.length}…`; await sendFile(lesson.id, file); }
      progress.textContent = "מבקשים טיוטה…";
      await api(`/api/worksheets/${lesson.id}/draft`, { method: "POST" });
      openLesson(lesson.id);
    } catch (e) { progress.textContent = ""; error.textContent = e.message; error.hidden = false; }
  });
}

export function wire(go, say, openLesson) {
  const done = (message, error = "") => { say(message, error); go("subjects"); };
  wireUpload(openLesson);
  document.getElementById("new-subject").addEventListener("submit", async event => {
    event.preventDefault();
    const icon = document.querySelector("#new-subject input[name=sb-new-icon]:checked")?.value;
    try { const made = await api("/api/subjects", { method: "POST", body: { name: document.getElementById("sb-name").value, icon } }); done(`המקצוע "${made.name}" נוצר.`); }
    catch (e) { done("", e.message); }
  });
  document.getElementById("subjects").addEventListener("click", async event => {
    const card = event.target.closest("[data-subject]");
    if (!card) return;
    const id = card.dataset.subject, form = card.querySelector(".sb-rename");
    const edit = event.target.closest("[data-open-lesson]")?.dataset.openLesson;
    if (edit) { openLesson(Number(edit)); return; }
    if (event.target.closest("[data-rename]")) { form.hidden = false; form.querySelector("input").focus(); return; }
    if (event.target.closest("[data-cancel]")) { form.hidden = true; return; }
    if (event.target.closest("[data-delete]")) {
      if (!confirm(`למחוק את המקצוע "${card.querySelector("h3").textContent.trim()}"?`)) return;
      try { await api(`/api/subjects/${encodeURIComponent(id)}`, { method: "DELETE" }); done("המקצוע נמחק."); } catch (e) { done("", e.message); }
      return;
    }
    const move = event.target.closest("[data-move]");
    if (move) {
      const order = [...card.querySelectorAll("[data-lesson]")].map(li => Number(li.dataset.lesson));
      const from = order.indexOf(Number(move.closest("[data-lesson]").dataset.lesson)), to = from + Number(move.dataset.move);
      [order[from], order[to]] = [order[to], order[from]];
      try { await api(`/api/subjects/${encodeURIComponent(id)}/order`, { method: "PUT", body: { lessons: order } }); done("הסדר נשמר."); }
      catch (e) { done("", e.message); }
    }
  });
  document.querySelectorAll("#subjects .sb-rename").forEach(form => form.addEventListener("submit", async event => {
    event.preventDefault();
    const id = form.closest("[data-subject]").dataset.subject;
    const body = { name: form.querySelector("input[type=text], input:not([type])").value, icon: form.querySelector("input[type=radio]:checked")?.value };
    try { await api(`/api/subjects/${encodeURIComponent(id)}`, { method: "PUT", body }); done("המקצוע עודכן."); } catch (e) { done("", e.message); }
  }));
}
