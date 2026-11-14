// The teacher's "בדיקת דרך" tab: the handed-in quizzes and tests of my students, each question with the student's choice and the board they
// wrote the way on. The teacher can give a question 0, half or full points for the way; the grade is recomputed on the server.
import { api } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { pictureUrl } from "./media.js";

const KINDS = { quiz: "בוחן", exercise_test: "מבחן תרגול", simulation: "סימולציה" };
const POINTS = [[null, "אוטומטי"], [0, "0"], [0.5, "½"], [1, "מלא"]];
let ctx;

/** The list: the ones not checked yet first. */
export async function show(context) {
  ctx = context;
  const items = await api("/api/teaching/work");
  ctx.draw(`${ctx.tabs("work")}<section id="boardwork"><h2>בדיקת הדרך</h2>
    <p class="muted">בכל שאלה בבוחן ובמבחן נשמר הלוח של התלמיד. אפשר לתת נקודות על הדרך: חצי או מלא גם לתשובה שגויה, או 0 לתשובה נכונה בלי דרך.</p>
    ${items.length ? `<ul class="plain work-list">${items.map(i => `<li data-attempt="${esc(i.id)}"><span class="grow"><b>${fmt(i.title)}</b><br>
        <span class="muted" dir="ltr">${esc(i.student)}</span> <span class="muted">· ${esc(i.class.name)}</span></span>
        <span class="tag">${i.grade ?? "-"}</span><span class="tag${i.checked ? " st-graded" : ""}">${i.checked ? "✓ נבדק" : "○ לבדיקה"}</span>
        <button type="button" data-open="${esc(i.id)}">פתיחה</button></li>`).join("")}</ul>`
      : `<p class="card muted" id="no-work">עוד אין בחנים או מבחנים שהוגשו.</p>`}</section>`);
  ctx.wire();
  document.querySelectorAll("[data-open]").forEach(b => b.addEventListener("click", () => open(b.dataset.open)));
}

const pointsOf = q => q.credit ?? q.auto;

function questionCard(q, i) {
  const picked = q.choices.find(c => c.index === q.picked);
  return `<article class="card work-q" data-key="${esc(q.key)}">
    <p class="muted">${i + 1}. ${fmt(q.skill_name)}</p>
    <p class="ex-text" dir="auto">${fmt(q.question)}</p>${figures(q)}
    <ul class="plain work-choices">${q.choices.map(c => `<li class="${c.correct ? "right" : ""}${c.index === q.picked ? " picked" : ""}"><span dir="auto">${fmt(c.text)}</span>
      <span>${c.correct ? "✓ נכונה" : ""}${c.index === q.picked ? " ← בחר/ה" : ""}</span></li>`).join("")}</ul>
    ${picked ? "" : `<p class="muted">לא ענה/תה על השאלה.</p>`}
    <h4>הדרך</h4>${q.ai ? `<p class="work-ai"><span class="tag">AI: ${({ correct: "✓ נכונה", partial: "◐ חלקית", wrong: "✗ שגויה", unclear: "? לא ברורה" })[q.ai.verdict] || ""}</span> ${fmt(q.ai.feedback)}</p>` : ""}${q.work ? `<img class="work-pic" data-picture="${esc(q.work)}" alt="הלוח של התלמיד בשאלה ${i + 1}" hidden>` : `<p class="muted no-work">אין לוח לשאלה הזו.</p>`}
    <div class="work-points" role="group" aria-label="נקודות לשאלה ${i + 1}"><span class="muted">נקודות:</span>${POINTS.map(([v, label]) =>
      `<button type="button" data-points="${v === null ? "auto" : v}" aria-pressed="${(q.credit ?? null) === v}">${label}${v === null ? ` (${q.auto})` : ""}</button>`).join("")}
      <b class="work-now">${pointsOf(q)}</b></div></article>`;
}

/** One attempt: every question with the choice and the board; the points buttons; save. */
async function open(id, note = "") {
  const data = await api(`/api/teaching/work/${encodeURIComponent(id)}`);
  const chosen = Object.fromEntries(data.questions.map(q => [q.key, q.credit ?? null]));
  ctx.draw(`${ctx.tabs("work")}<section id="work-check" data-attempt="${esc(data.id)}"><p><button type="button" id="work-back">‹ לרשימה</button></p>
    <h2>${fmt(data.title)}</h2><p class="muted" dir="ltr">${esc(data.student)}</p>
    <p>ציון: <b id="work-grade">${data.grade}</b>${data.checked_at ? ` <span class="muted">· נבדק</span>` : ""}</p>
    ${note ? `<p class="ex-note" role="status">${esc(note)}</p>` : ""}
    ${data.questions.map(questionCard).join("")}
    <p class="work-save"><button type="button" class="primary" id="work-save">שמירת הנקודות</button></p></section>`);
  ctx.wire();
  document.querySelectorAll("#work-check img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.replaceWith(Object.assign(document.createElement("p"), { className: "muted", textContent: "התמונה לא זמינה" })); } });
  document.getElementById("work-back").addEventListener("click", () => show(ctx));
  document.querySelectorAll(".work-q").forEach(card => card.addEventListener("click", event => {
    const b = event.target.closest("[data-points]");
    if (!b) return;
    const q = data.questions.find(x => x.key === card.dataset.key), v = b.dataset.points === "auto" ? null : Number(b.dataset.points);
    chosen[q.key] = v;
    card.querySelectorAll("[data-points]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    card.querySelector(".work-now").textContent = v ?? q.auto;
  }));
  document.getElementById("work-save").addEventListener("click", async event => {
    event.target.disabled = true;
    try {
      const saved = await api(`/api/teaching/work/${encodeURIComponent(id)}`, { method: "POST", body: { credit: chosen } });
      await open(id, `נשמר. הציון עכשיו ${saved.grade}.`);
    } catch (error) {
      event.target.disabled = false;
      event.target.insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`);
    }
  });
}

export const kindName = kind => KINDS[kind] || kind;
