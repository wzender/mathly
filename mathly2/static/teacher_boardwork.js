// The teacher's "בדיקת דרך" tab: the handed-in quizzes and tests of my students, each question with the student's choice and the board they
// wrote the way on. The teacher can give a question 0, half or full points for the way; the grade is recomputed on the server.
import { api } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { pictureUrl } from "./media.js";
import { stepsHtml } from "./reviewsteps.js";

const KINDS = { quiz: "בוחן", exercise_test: "מבחן תרגול", simulation: "סימולציה" };
const POINTS = [[null, "אוטומטי"], [0, "0"], [0.5, "½"], [1, "מלא"]];
let ctx, poll = null;

const REASONS = {
  api_key_invalid: "המפתח של Gemini לא תקין. בדקו את GEMINI_API_KEY בשרת.",
  permission: "למפתח של Gemini אין הרשאה למודל הזה.",
  model_not_found: "המודל לא נמצא, ולא נמצא מודל Flash אחר למפתח הזה. בדקו את GEMINI_MODEL בשרת (או מחקו אותו).",
  rate_limited: "נגמרה המכסה החינמית של Gemini לעכשיו. נסו שוב מאוחר יותר.",
  no_connection: "השרת לא הצליח להתחבר ל־Gemini.",
  database: "לא ניתן לשמור את הבדיקה: חסרה במסד הנתונים העמודה review (המיגרציה 20261121090000_m2_board_review.sql).",
  bad_request: "Gemini דחה את הבקשה.", incomplete: "התשובה של Gemini נקטעה.", bad_output: "Gemini החזיר תשובה לא תקינה.",
};

/** The AI panel: whether it can run, its state, why it failed, and the button that starts it (again). */
function aiPanel(data) {
  const ai = data.ai || {};
  if (!ai.available) return `<div class="card work-ai-panel" id="work-ai"><p class="muted">🤖 בדיקה עם AI לא מוגדרת בשרת: חסר GEMINI_API_KEY.</p></div>`;
  const button = label => `<button type="button" id="work-ai-run">${label}</button>`;
  const body = ai.state === "pending" ? `<p><b>🤖 בדיקה עם AI</b></p>${stepsHtml(ai)}`
    : ai.state === "failed" ? `<p class="error" role="alert">🤖 הבדיקה עם AI נכשלה. ${esc(REASONS[ai.reason] || "")}${ai.model ? ` <span dir="ltr">(${esc(ai.model)})</span>` : ""}</p>${button("לנסות שוב")}`
    : ai.state === "done" ? `<p>🤖 <b>סיכום ה־AI:</b> ${ai.summary ? fmt(ai.summary) : "אין סיכום."}</p>
      ${ai.missing ? `<p class="error">${ai.missing === 1 ? "שאלה אחת לא נבדקה" : `${ai.missing} שאלות לא נבדקו`}. ${esc(REASONS[ai.reason] || "")} אפשר לבדוק כל שאלה בכפתור שלה.</p>` : ""}
      <p class="muted">הצעה בלבד: הנקודות שלכם קובעות.</p>${button("לבדוק שוב את כל המבחן")}`
    : `<p class="muted">🤖 עוד לא נבדק עם AI. ה־AI בודק כל שאלה בנפרד.</p>${button("בדיקה עם AI של כל השאלות")}`;
  return `<div class="card work-ai-panel" id="work-ai" data-state="${esc(ai.state || "none")}">${body}</div>`;
}

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
const VERDICT = { correct: "✓ נכונה", partial: "◐ חלקית", wrong: "✗ שגויה", unclear: "? לא ברורה" };
let aiNow = {};                                            // the attempt's AI state, for the per-question buttons

/** One question's AI line, and its own button (check it alone, or again). */
function aiSlot(q) {
  const line = q.ai ? `<p class="work-ai"><span class="tag">AI: ${VERDICT[q.ai.verdict] || ""}</span> ${fmt(q.ai.feedback)}${q.ai.tip ? `<br><span class="muted">💡 ${fmt(q.ai.tip)}</span>` : ""}</p>` : "";
  const busy = aiNow.state === "pending";
  const button = aiNow.available && q.work ? `<button type="button" class="work-ai-run" data-ai-key="${esc(q.key)}"${busy ? " disabled" : ""}>🤖 ${q.ai ? "לבדוק שוב את השאלה" : "בדיקה עם AI של השאלה"}</button>` : "";
  return `<div class="work-ai-slot">${line}${button}</div>`;
}

function questionCard(q, i) {
  const picked = q.choices.find(c => c.index === q.picked);
  return `<article class="card work-q" data-key="${esc(q.key)}">
    <p class="muted">${i + 1}. ${fmt(q.skill_name)}</p>
    <p class="ex-text" dir="auto">${fmt(q.question)}</p>${figures(q)}
    <ul class="plain work-choices">${q.choices.map(c => `<li class="${c.correct ? "right" : ""}${c.index === q.picked ? " picked" : ""}"><span dir="auto">${fmt(c.text)}</span>
      <span>${c.correct ? "✓ נכונה" : ""}${c.index === q.picked ? " ← בחר/ה" : ""}</span></li>`).join("")}</ul>
    ${picked ? "" : `<p class="muted">לא ענה/תה על השאלה.</p>`}
    <h4>הדרך</h4>${aiSlot(q)}${q.work ? `<img class="work-pic" data-picture="${esc(q.work)}" alt="הלוח של התלמיד בשאלה ${i + 1}" hidden>` : `<p class="muted no-work">אין לוח לשאלה הזו.</p>`}
    <div class="work-points" role="group" aria-label="נקודות לשאלה ${i + 1}"><span class="muted">נקודות:</span>${POINTS.map(([v, label]) =>
      `<button type="button" data-points="${v === null ? "auto" : v}" aria-pressed="${(q.credit ?? null) === v}">${label}${v === null ? ` (${q.auto})` : ""}</button>`).join("")}
      <b class="work-now">${pointsOf(q)}</b></div></article>`;
}

/** One attempt: every question with the choice and the board; the points buttons; save. */
async function open(id, note = "", given = null, keep = null) {
  clearTimeout(poll);
  const data = given || await api(`/api/teaching/work/${encodeURIComponent(id)}`);
  if (keep) data.questions.forEach(q => { if (q.key in keep) q.credit = keep[q.key]; });       // points picked but not saved yet stay picked
  const chosen = Object.fromEntries(data.questions.map(q => [q.key, q.credit ?? null]));
  aiNow = data.ai || {};
  ctx.draw(`${ctx.tabs("work")}<section id="work-check" data-attempt="${esc(data.id)}"><p><button type="button" id="work-back">‹ לרשימה</button></p>
    <h2>${fmt(data.title)}</h2><p class="muted" dir="ltr">${esc(data.student)}</p>
    <p>ציון: <b id="work-grade">${data.grade}</b>${data.checked_at ? ` <span class="muted">· נבדק</span>` : ""}</p>
    ${note ? `<p class="ex-note" role="status">${esc(note)}</p>` : ""}
    ${aiPanel(data)}
    ${data.questions.map(questionCard).join("")}
    <p class="work-save"><button type="button" class="primary" id="work-save">שמירת הנקודות</button></p></section>`);
  ctx.wire();
  document.querySelectorAll("#work-check img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.replaceWith(Object.assign(document.createElement("p"), { className: "muted", textContent: "התמונה לא זמינה" })); } });
  document.getElementById("work-back").addEventListener("click", () => { clearTimeout(poll); show(ctx); });
  const runAi = async (button, key) => {
    button.disabled = true;
    try { await open(id, "", await api(`/api/teaching/work/${encodeURIComponent(id)}/review${key ? `?key=${encodeURIComponent(key)}` : ""}`, { method: "POST" }), chosen); }
    catch (error) { button.disabled = false; button.insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`); }
  };
  document.getElementById("work-ai-run")?.addEventListener("click", event => runAi(event.target, null));
  document.querySelectorAll("[data-ai-key]").forEach(b => b.addEventListener("click", event => { event.stopPropagation(); runAi(b, b.dataset.aiKey); }));
  if (data.ai?.state === "pending") {                                   // ask again until the AI is done, then redraw with the picks kept
    const wait = () => { poll = setTimeout(async () => {
      if (document.getElementById("work-check")?.dataset.attempt !== data.id) return;
      let now;
      try { now = await api(`/api/teaching/work/${encodeURIComponent(id)}`); } catch { return wait(); }
      if (document.getElementById("work-check")?.dataset.attempt !== data.id) return;
      if (now.ai?.state === "pending") {                                 // the new steps in the box, and each question's line as it is checked
        document.getElementById("work-ai")?.replaceWith(Object.assign(document.createElement("div"), { innerHTML: aiPanel(now) }).firstElementChild);
        aiNow = now.ai;
        now.questions.forEach(q => {
          const slot = document.querySelector(`.work-q[data-key="${CSS.escape(q.key)}"] .work-ai-slot`);
          if (slot && q.ai) slot.outerHTML = aiSlot(q);
        });
        return wait();
      }
      open(id, "", now, chosen);
    }, 4000); };
    wait();
  }
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
