// One assignment: its material (pages or the bank's written quiz), the student's answer as pictures (from the board, the camera, a file or
// the phone) and handing it in; afterwards its state, and the grade and note or the request to correct.
import { api } from "./api.js";
import { stateWord } from "./ai_sheet.js";
import { loadBoard } from "./exercise.js";
import { figures } from "./figures.js";
import { assignmentState } from "./home.js";
import { withBusy } from "./busy.js";
import { esc, fmt } from "./math.js";
import { isTouch, pictureUrl, prepare, sendPicture } from "./media.js";
import * as phone from "./phone.js";
import { shortDate, tabs } from "./ui.js";

let draw = null, current = null, draft = [], message = "";

const draftKey = id => `assignment-draft:${id}`;
const saveDraft = () => { try { sessionStorage.setItem(draftKey(current.id), JSON.stringify(draft)); } catch { /* private window */ } };
const loadDraft = id => { try { return JSON.parse(sessionStorage.getItem(draftKey(id)) || "null"); } catch { return null; } };
const q = selector => document.querySelector(selector);
const editable = a => ["not_handed", "handed_in", "returned"].includes(a.state);

/** Fill an <img> with a private picture (fetched with the sign-in). */
async function fill(img, id) {
  try { img.src = await pictureUrl(id); img.hidden = false; } catch (error) { img.replaceWith(Object.assign(document.createElement("span"), { className: "muted", textContent: error.message })); }
}

function material(a) {
  if (a.kind === "exercise_test") return `<p><a class="button primary" href="#/exam/${a.test.id}/${a.test.number}">למבחן התרגול</a></p>`;
  if (a.kind === "quiz" && a.quiz) {
    return `<h3>הבוחן הכתוב <span class="muted">(${a.quiz.minutes} דקות · ${a.quiz.points} נקודות)</span></h3><ol class="qz-written" id="written-quiz">${a.quiz.questions.map(x =>
      `<li><p class="ex-text" dir="auto">${fmt(x.question)}</p>${figures(x)}<span class="muted">${x.points} נק׳</span></li>`).join("")}</ol>`;
  }
  return a.pages.length ? `<h3>הדף</h3><div class="pages" id="pages">${a.pages.map((id, i) => `<img data-picture="${esc(id)}" alt="עמוד ${i + 1}" hidden>`).join("")}</div>` : "";
}

function stateBox(a) {
  const s = assignmentState(a);
  const note = a.teacher_note ? `<p class="teacher-note" id="teacher-note"><b>הערת המורה:</b> ${fmt(a.teacher_note)}</p>` : "";
  const head = `<p id="state" role="status"><span class="tag st-${esc(a.state)}"><span aria-hidden="true">${s.symbol}</span> ${s.word}</span></p>`;
  if (a.state === "returned") return `${head}<div class="returned" id="returned"><b>המורה החזיר/ה את המשימה לתיקון.</b>${note}<p>תקנו והגישו שוב.</p></div>`;
  if (a.state === "graded") return `${head}<p class="grade-big" id="grade">הציון: <b>${a.grade}</b></p>${note}`;
  return head;
}

/** What the student can do about a handed-in answer: ask for an AI check (it waits for the teacher), see its result as a suggestion, or ask
 *  the teacher to look again. */
function aiBox(a) {
  const ai = a.ai;
  if (!ai || (!ai.can_check && !ai.can_look_again && !ai.asked_again && !ai.checks.length)) return "";
  const checks = ai.checks.map(c => {
    const r = c.result;
    const body = c.state === "done"
      ? (r.score === null || r.score === undefined ? `<p>ה־AI לא הצליח לקרוא את התשובה. המורה יבדוק/תבדוק.</p>` : `<p>הציון המוצע: <b>${r.score}</b> (המורה קובע/ת את הציון)</p>`) + `<p>${fmt(r.feedback || "")}</p>${r.next_step ? `<p class="muted">${fmt(r.next_step)}</p>` : ""}`
      : c.state === "declined" ? `<p>${c.teacher_note ? fmt(c.teacher_note) : "המורה לא שלח/ה את הבקשה."}</p>`
      : c.state === "failed" ? `<p class="error">${esc(c.failure?.message || "לא הצלחנו כרגע. נסו שוב מאוחר יותר.")}</p>` : "";
    return `<div class="ai-check" data-check="${esc(c.id)}" data-state="${esc(c.state)}"><p><span class="tag st-${esc(c.state)}">${esc(stateWord(c.state))}</span></p>${body}</div>`;
  }).join("");
  return `<section class="card" id="ai-box"><h3>בדיקה נוספת</h3>
    ${ai.can_check ? `<p><button type="button" id="ask-check">בקשת בדיקה של AI</button> <span class="muted">המורה יראה/תראה את הבקשה קודם.</span></p>` : ""}
    ${ai.can_look_again ? `<p><button type="button" id="ask-again">בקשה מהמורה לבדוק שוב</button></p>` : ""}
    ${ai.asked_again ? `<p class="muted" id="again-asked">ביקשתם מהמורה לבדוק שוב.</p>` : ""}${checks}</section>`;
}

function draftHtml() {
  return draft.length ? draft.map(id => `<li data-picture-id="${esc(id)}"><img data-picture="${esc(id)}" alt="תמונה של התשובה" hidden>
    <button type="button" class="remove" data-remove="${esc(id)}" aria-label="הסרת התמונה">✕</button></li>`).join("") : `<li class="muted" id="draft-empty">עוד לא הוספתם תמונה.</li>`;
}

function renderDraft() {
  q("#draft").innerHTML = draftHtml();
  q("#draft").querySelectorAll("img[data-picture]").forEach(img => fill(img, img.dataset.picture));
  q("#hand-in").disabled = !draft.length;
  saveDraft();
}

function answerBox(a) {
  if (a.kind === "exercise_test") return "";
  if (!editable(a)) {
    return a.pictures.length ? `<section class="card" id="answer"><h3>התשובה שהגשתי</h3><div class="pages" id="submitted">${a.pictures.map(p => p.deleted
      ? `<p class="muted" data-deleted>התמונות נמחקו</p>` : `<img data-picture="${esc(p.id)}" alt="התשובה שהגשתי" hidden>`).join("")}</div></section>` : "";
  }
  return `<section class="card" id="answer"><h3>${a.state === "handed_in" ? "התשובה שהגשתי (אפשר להחליף עד שהמורה בודק/ת)" : "התשובה שלי"}</h3>
    <ul class="plain drafts" id="draft">${draftHtml()}</ul>
    <p class="actions" id="add-actions"><button type="button" id="board-btn">✎ כתיבה על הלוח</button>
      ${isTouch() ? `<label class="button file">📷 צילום<input type="file" accept="image/*" capture="environment" hidden data-file="camera"></label>` : ""}
      <label class="button file">🖼 העלאת תמונה<input type="file" accept="image/jpeg,image/png,image/webp" multiple hidden data-file="upload"></label>
      ${!isTouch() ? `<button type="button" id="ask-phone">📱 בקשת צילום מהטלפון</button>` : ""}</p>
    <div id="phone-panel"></div>
    <p class="error" id="add-error" role="alert" hidden></p>
    <p><button type="button" class="primary" id="hand-in" disabled>${a.state === "handed_in" ? "החלפת ההגשה" : "הגשה"}</button></p>
    <p id="hand-msg" role="status" class="muted">${esc(message)}</p></section>`;
}

function add(id) {
  if (!q("#draft")) return;                                         // the page was left while a photo was on its way
  if (!draft.includes(id)) draft.push(id);
  renderDraft();
}

async function addFiles(files) {
  const error = q("#add-error");
  error.hidden = true;
  for (const file of files) {
    if (draft.length >= 10) { error.textContent = "אפשר להגיש עד 10 תמונות"; error.hidden = false; break; }
    try {
      add((await sendPicture("/api/pictures", await prepare(file))).id);
    } catch (e) { error.textContent = e.message; error.hidden = false; }
  }
}

async function openBoard() {
  await loadBoard();
  if (!window.MathlyBoard?.openFull) return;
  const host = Object.assign(document.createElement("div"), { className: "mx-layer" });
  document.body.append(host);
  window.MathlyBoard.openFull({
    host, key: `assignment:${current.id}`, title: "כתיבה על הלוח", sendLabel: "הוספה להגשה",
    submit: async (page, blob) => {
      if (draft.length >= 10) return { error: "אפשר להגיש עד 10 תמונות" };
      try { add((await sendPicture("/api/pictures", blob)).id); return {}; } catch (e) { return { error: e.message }; }
    },
    done: () => host.remove(),
  });
}

async function handIn() {
  const button = q("#hand-in");
  button.disabled = true;
  q("#hand-msg").textContent = "שולחים…";
  try {
    await api(`/api/assignments/${current.id}/submission`, { method: "POST", body: { pictures: draft } });
    try { sessionStorage.removeItem(draftKey(current.id)); } catch { /* nothing */ }
    message = "ההגשה נשלחה. המורה יבדוק/תבדוק.";
    await show(draw, current.id);
  } catch (error) {
    button.disabled = false;
    q("#hand-msg").textContent = "";
    q("#add-error").textContent = error.message || "משהו השתבש";
    q("#add-error").hidden = false;
  }
}

let pollTimer = null;
function wireAi(id) {
  clearTimeout(pollTimer);
  const ask = async path => { try { await api(path, { method: "POST" }); } catch (e) { message = e.message; } await show(draw, id); };
  q("#ask-check")?.addEventListener("click", e => withBusy(e.currentTarget, ask(`/api/assignments/${current.id}/ai-check`)));
  q("#ask-again")?.addEventListener("click", e => withBusy(e.currentTarget, ask(`/api/assignments/${current.id}/look-again`)));
  if ((current.ai?.checks || []).some(c => ["waiting", "processing"].includes(c.state)) && q("#assignment")) {      // look again while a check is on its way
    pollTimer = setTimeout(() => { if (q("#assignment")?.dataset.id === String(current.id)) show(draw, id); }, 5000);
  }
}

export async function show(view, id) {
  draw = view;
  current = await api(`/api/assignments/${encodeURIComponent(id)}`);
  const saved = loadDraft(current.id);
  draft = editable(current) ? (saved ?? current.pictures.filter(p => !p.deleted).map(p => p.id)) : [];
  view(`${tabs("submissions")}<p><a class="back" href="#/submissions">‹ ההגשות</a></p>
    <section class="card" id="assignment" data-id="${current.id}" data-state="${esc(current.state)}"><h2>${fmt(current.title)}</h2>
      <p class="muted">${esc(current.class.name)} · עד ${shortDate(current.due_date)}${current.overdue ? " · באיחור" : ""}</p>
      ${current.note ? `<p id="assignment-note">${fmt(current.note)}</p>` : ""}${stateBox(current)}</section>
    <section class="card" id="material">${material(current)}</section>${answerBox(current)}${aiBox(current)}`);
  wireAi(id);
  document.querySelectorAll("img[data-picture]:not(#draft img)").forEach(img => fill(img, img.dataset.picture));
  if (!editable(current) || current.kind === "exercise_test") return;
  renderDraft();
  q("#board-btn").addEventListener("click", openBoard);
  q("#hand-in").addEventListener("click", handIn);
  q("#draft").addEventListener("click", event => {
    const id = event.target.closest("[data-remove]")?.dataset.remove;
    if (id) { draft = draft.filter(x => x !== id); renderDraft(); }
  });
  document.querySelectorAll("[data-file]").forEach(input => input.addEventListener("change", async () => { const files = [...input.files]; input.value = ""; await withBusy(input.closest("label"), addFiles(files)); }));
  q("#ask-phone")?.addEventListener("click", () => phone.askFromComputer(current, id => add(id), q("#phone-panel")));
}
