// The teacher's "שאלות מצולמות" (photoq.py): the questions the class's students photographed and solved, waiting for a decision. For each:
// the photo, the question as the AI read it and its answer (both can be fixed), the student's board, grade and feedback, and the skill;
// "אישור למאגר" puts it in the class's bank (the other students can solve it), "דחייה" keeps it out.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";
import { pictureUrl } from "./media.js";

const FILTERS = [["pending", "ממתינות"], ["approved", "אושרו"], ["rejected", "נדחו"]];
let filter = "pending";

function item(r) {
  const options = [...r.skills.map(s => `<option value="${esc(s.id)}"${r.skill?.id === s.id ? " selected" : ""}>${esc(s.name)}${s.id === r.suggested_skill ? " (הצעת ה־AI)" : ""}</option>`),
    `<option value=""${r.skill ? "" : " selected"}>חיצוני</option>`];
  return `<li class="card pq-t" data-pq="${esc(r.id)}">
    <p class="muted"><span dir="ltr">${esc(r.student)}</span>${r.grade !== null ? ` · ציון ${r.grade}` : ""}${r.review?.verdict ? ` · ${esc(r.review.verdict)}` : ""}</p>
    <div class="pq-pics">${r.picture_id ? `<figure><img data-picture="${esc(r.picture_id)}" alt="התמונה שצולמה" hidden><figcaption>התמונה</figcaption></figure>` : ""}
      ${r.board_id ? `<figure><img data-picture="${esc(r.board_id)}" alt="הלוח של התלמיד" hidden><figcaption>הלוח</figcaption></figure>` : ""}</div>
    <label>השאלה (אפשר לתקן)</label><textarea data-field="question" rows="3" dir="auto">${esc(r.question)}</textarea>
    <p class="muted pq-preview" dir="auto">${fmt(r.question)}</p>
    <label>התשובה (אפשר לתקן)</label><input data-field="answer" value="${esc(r.answer)}" dir="auto">
    ${r.steps?.length ? `<details><summary>הפתרון של ה־AI</summary><ol>${r.steps.map(s => `<li dir="auto">${fmt(s)}</li>`).join("")}</ol></details>` : ""}
    ${r.review?.feedback ? `<p class="muted">משוב לתלמיד: ${fmt(r.review.feedback)}</p>` : ""}
    <label>סיווג</label><select data-field="skill">${options.join("")}</select>
    <p class="actions">${r.bank !== "approved" ? `<button type="button" class="primary" data-decide="approve">✓ אישור למאגר הכיתה</button>` : ""}
      ${r.bank !== "rejected" ? `<button type="button" data-decide="reject">דחייה</button>` : ""}
      ${r.bank !== "pending" ? `<button type="button" data-decide="pending">החזרה להמתנה</button>` : ""}</p></li>`;
}

async function load(section) {
  let rows;
  try { rows = await api(`/api/teaching/photo-questions?bank=${filter}`); }
  catch (e) { section.innerHTML = `<h3>שאלות מצולמות</h3><p class="error">${esc(e.message)}</p>`; return; }
  section.innerHTML = `<h3>שאלות מצולמות</h3>
    <p class="muted">תלמידים צילמו את השאלות האלה ופתרו אותן. שאלה שתאשרו תיכנס לשאלות של הכיתה, ושאר התלמידים יוכלו לפתור אותה.</p>
    <div class="subtabs" id="pq-filter" role="group" aria-label="סינון">${FILTERS.map(([id, label]) => `<button type="button" data-filter="${id}" aria-pressed="${id === filter}">${label}</button>`).join("")}</div>
    ${rows.length ? `<ul class="plain" id="pq-teacher-list">${rows.map(item).join("")}</ul>` : `<p class="muted" id="pq-none">אין שאלות כאן.</p>`}`;
  section.querySelectorAll("img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.remove(); } });
}

export async function mount(section) {
  await load(section);
  section.addEventListener("click", async event => {
    const f = event.target.closest("[data-filter]")?.dataset.filter;
    if (f) { filter = f; return load(section); }
    const button = event.target.closest("[data-decide]");
    if (!button) return;
    const li = button.closest("[data-pq]");
    button.disabled = true;
    try {
      await api(`/api/teaching/photo-questions/${li.dataset.pq}`, { method: "POST", body: { action: button.dataset.decide,
        skill_id: li.querySelector("[data-field=skill]").value, question: li.querySelector("[data-field=question]").value,
        answer: li.querySelector("[data-field=answer]").value } });
      await load(section);
    } catch (e) { button.disabled = false; button.insertAdjacentHTML("afterend", ` <span class="error">${esc(e.message)}</span>`); }
  });
}
