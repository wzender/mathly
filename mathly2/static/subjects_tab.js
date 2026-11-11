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
      <button type="button" data-move="-1" aria-label="להזיז למעלה את ${esc(l.name)}" ${i === 0 ? "disabled" : ""}>▲</button>
      <button type="button" data-move="1" aria-label="להזיז למטה את ${esc(l.name)}" ${i === subject.lessons.length - 1 ? "disabled" : ""}>▼</button></li>`).join("");
  return `<ul class="plain sb-lessons">${fixed}${rows || (subject.fixed ? "" : `<li class="muted">עוד אין שיעורים במקצוע.</li>`)}</ul>`;
}

export async function view() {
  const data = await api("/api/subjects");
  const warning = data.content_error ? `<p class="error" role="alert">לא הצלחנו לקרוא את המקצועות ממסד הנתונים, ולכן רק שיעורי המתמטיקה מקובץ התוכן מוצגים לתלמידים. בדקו שהמיגרציה <span dir="ltr">20261117090000_m2_subjects.sql</span> הוחלה.</p>` : "";
  return `${warning}<form class="card" id="new-subject"><h3>מקצוע חדש</h3>
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

export function wire(go, say) {
  const done = (message, error = "") => { say(message, error); go("subjects"); };
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
