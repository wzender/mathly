// The lesson editor (add-subjects-and-worksheets): a worksheet's pages beside the lesson drafted from it, every part editable.
// The lesson's name; its skills (name, short name, one-line description); each skill's multiple-choice questions with their
// choices, which one is right, and for each wrong one the mistake it shows; the lesson's mistakes (name and tip). Every change is
// saved (the whole document, a moment after the last keystroke), so leaving and coming back finds the draft as it was. A question
// a person edits or adds is marked "written by a person"; the AI's own are marked so a reviewer checks them first. Nothing here
// reaches a student: publishing (with its checks) is separate.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";
import { token } from "./session.js";

const SOURCE = { sheet: "מהדף", ai: "נכתב על ידי AI", person: "נכתב על ידי אדם" };
const SAVE_AFTER = 700;

let state = null;        // {id, view, doc, pages: [object URLs], text, saving, timer, onBack, poll}

/** A page picture needs the sign-in header, so it is fetched and shown from memory. */
async function pageUrl(lessonId, index) {
  const response = await fetch(`/api/worksheets/${lessonId}/pages/${index}`, { headers: { Authorization: "Bearer " + await token() } });
  return response.ok ? URL.createObjectURL(await response.blob()) : "";
}

const at = (doc, path) => path.split(".").reduce((node, key) => node?.[/^\d+$/.test(key) ? Number(key) : key], doc);
function put(doc, path, value) {
  const keys = path.split("."), last = keys.pop();
  const parent = keys.length ? at(doc, keys.join(".")) : doc;
  if (parent) parent[/^\d+$/.test(last) ? Number(last) : last] = value;
}

function mistakeOptions(chosen) {
  const entries = Object.entries(state.doc.mistakes || {});
  return `<option value="">— בחרו טעות —</option>${entries.map(([id, m]) =>
    `<option value="${esc(id)}"${id === chosen ? " selected" : ""}>${esc(m.name || "טעות בלי שם")}</option>`).join("")}`;
}

function choiceRow(path, choice, ci, qi) {
  const name = `right-${path.replace(/\./g, "-")}`;
  return `<li class="le-choice" data-path="${path}.choices.${ci}">
    <label class="le-right"><input type="radio" name="${name}" data-act="right" ${choice.correct ? "checked" : ""}> נכונה</label>
    <input class="grow" data-f="${path}.choices.${ci}.text" value="${esc(choice.text || "")}" aria-label="תשובה ${ci + 1}" dir="auto">
    ${choice.correct ? "" : `<select data-f="${path}.choices.${ci}.mistake" aria-label="הטעות של תשובה ${ci + 1}">${mistakeOptions(choice.mistake)}</select>`}
    <button type="button" data-act="del-choice" aria-label="מחיקת תשובה ${ci + 1}">✕</button></li>`;
}

function questionCard(si, qi, q) {
  const path = `skills.${si}.questions.${qi}`;
  return `<article class="le-question" data-path="${path}">
    <div class="hrow"><b class="grow">שאלה ${qi + 1}</b><span class="le-source le-${esc(q.source || "person")}">${SOURCE[q.source] || SOURCE.person}</span>
      <button type="button" data-act="up-q" aria-label="שאלה ${qi + 1} למעלה">▲</button><button type="button" data-act="down-q" aria-label="שאלה ${qi + 1} למטה">▼</button>
      <button type="button" class="danger" data-act="del-q">מחיקה</button></div>
    <textarea data-f="${path}.question" rows="2" aria-label="נוסח שאלה ${qi + 1}" dir="auto">${esc(q.question || "")}</textarea>
    <ol class="plain le-choices">${(q.choices || []).map((c, ci) => choiceRow(path, c, ci, qi)).join("")}</ol>
    <p class="hrow"><button type="button" data-act="add-choice">+ תשובה</button></p>
    <div class="le-preview" aria-label="כך התלמידים יראו את השאלה"><p dir="auto">${fmt(q.question || "")}</p>
      <ul>${(q.choices || []).map(c => `<li dir="auto">${fmt(c.text || "")}</li>`).join("")}</ul></div></article>`;
}

function skillCard(skill, si) {
  const path = `skills.${si}`;
  return `<section class="card le-skill" data-path="${path}">
    <div class="hrow"><h4 class="grow">מיומנות ${si + 1}</h4>
      <button type="button" data-act="up-s" aria-label="מיומנות ${si + 1} למעלה">▲</button><button type="button" data-act="down-s" aria-label="מיומנות ${si + 1} למטה">▼</button>
      <button type="button" class="danger" data-act="del-s">מחיקה</button></div>
    <label>שם המיומנות<input data-f="${path}.name" maxlength="60" value="${esc(skill.name || "")}"></label>
    <label>שם קצר<input data-f="${path}.short" maxlength="25" value="${esc(skill.short || "")}"></label>
    <label>תיאור במשפט<input data-f="${path}.description" maxlength="300" value="${esc(skill.description || "")}"></label>
    ${(skill.questions || []).map((q, qi) => questionCard(si, qi, q)).join("")}
    <p><button type="button" data-act="add-q">+ שאלה</button></p></section>`;
}

function mistakesCard() {
  return `<section class="card le-mistakes"><h4>טעויות</h4><p class="muted">כל תשובה שגויה מראה לתלמיד טעות: שם קצר וטיפ איך לא לטעות שוב.</p>
    <ul class="plain">${Object.entries(state.doc.mistakes || {}).map(([id, m]) => `<li class="le-mistake" data-mistake="${esc(id)}">
      <input data-f="mistakes.${esc(id)}.name" maxlength="80" placeholder="שם הטעות" value="${esc(m.name || "")}" aria-label="שם הטעות">
      <input class="grow" data-f="mistakes.${esc(id)}.tip" maxlength="600" placeholder="טיפ" value="${esc(m.tip || "")}" aria-label="טיפ"></li>`).join("")}</ul>
    <p><button type="button" data-act="add-mistake">+ טעות</button></p></section>`;
}

function statusPanel() {
  const v = state.view;
  if (v.status === "drafting") return `<p class="le-status" id="le-status" role="status">מכינים טיוטה מדף העבודה. זה יכול לקחת דקה או שתיים…</p>`;
  if (v.status === "failed" && v.failure) return `<div class="error le-status" id="le-status" role="alert"><b>${esc(v.failure.what)}</b>
      ${v.failure.note ? `<p>${esc(v.failure.note)}</p>` : ""}<p>${esc(v.failure.todo)}</p>
      <button type="button" class="primary" id="le-retry">נסו שוב</button></div>`;
  return "";
}

function pagesColumn() {
  const pages = state.pages.map((url, i) => url ? `<img src="${url}" alt="עמוד ${i + 1} של דף העבודה" loading="lazy">` : "").join("");
  return `<aside class="le-sheet" aria-label="דף העבודה">${pages}${state.text ? `<pre class="le-text" dir="auto">${esc(state.text)}</pre>` : ""}
    ${!pages && !state.text ? `<p class="muted">אין דף עבודה לשיעור הזה.</p>` : ""}</aside>`;
}

function html() {
  const doc = state.doc;
  return `<section id="lesson-editor" data-lesson="${state.id}">
    <p><button type="button" id="le-back">‹ חזרה למקצועות</button> <span class="muted" id="le-saved" role="status" aria-live="polite"></span></p>
    ${statusPanel()}
    <div class="le-layout">${pagesColumn()}
      <div class="le-draft">${doc ? `<section class="card"><label for="le-name">שם השיעור</label><input id="le-name" data-f="name" maxlength="80" value="${esc(doc.name || "")}">
        ${doc.note ? `<p class="muted">הערת ה־AI: ${esc(doc.note)}</p>` : ""}</section>
        ${(doc.skills || []).map(skillCard).join("")}
        <p><button type="button" data-act="add-s">+ מיומנות</button></p>
        ${mistakesCard()}` : ""}</div></div></section>`;
}

function draw() {
  const root = document.getElementById("lesson-editor-root");
  if (!root) return;
  const focused = document.activeElement?.dataset?.f, caret = document.activeElement?.selectionStart;
  root.innerHTML = html();
  if (focused) {
    const again = root.querySelector(`[data-f="${CSS.escape(focused)}"]`);
    again?.focus();
    if (again && caret != null && again.setSelectionRange) try { again.setSelectionRange(caret, caret); } catch { /* not a text field */ }
  }
}

function said(text) { const el = document.getElementById("le-saved"); if (el) el.textContent = text; }

async function saveNow() {
  clearTimeout(state.timer);
  state.timer = null;
  said("שומרים…");
  try {
    const saved = await api(`/api/subjects/lessons/${state.id}/draft`, { method: "PUT", body: { lesson: state.doc } });
    const fresh = saved.draft;
    const renamed = JSON.stringify(Object.keys(fresh.mistakes || {})) !== JSON.stringify(Object.keys(state.doc.mistakes || {}))
      || (fresh.skills || []).some((s, i) => s.id !== state.doc.skills[i]?.id);
    state.doc = fresh;
    if (renamed) draw();                            // new skills or mistakes got their ids: the selects must name them
    said("נשמר");
  } catch (e) { said(""); const el = document.getElementById("le-saved"); if (el) { el.textContent = `לא נשמר: ${e.message}`; el.classList.add("error"); } }
}

function changed({ redraw = false } = {}) {
  if (redraw) draw();
  said("");
  clearTimeout(state.timer);
  state.timer = setTimeout(saveNow, SAVE_AFTER);
}

const asPerson = question => { if (question) question.source = "person"; };
const move = (list, from, to) => { if (to < 0 || to >= list.length) return; const [item] = list.splice(from, 1); list.splice(to, 0, item); };
const newMistake = () => { const id = `new-${Date.now()}`; state.doc.mistakes = { ...(state.doc.mistakes || {}), [id]: { name: "", tip: "" } }; return id; };

function onInput(event) {
  const field = event.target.closest("[data-f]");
  if (!field || !state?.doc) return;
  const path = field.dataset.f;
  put(state.doc, path, field.value);
  const question = path.match(/^skills\.\d+\.questions\.\d+/);
  if (question) asPerson(at(state.doc, question[0]));
  const preview = field.closest(".le-question");
  if (preview) {                                    // the question's preview follows the typing, without redrawing the field
    const q = at(state.doc, preview.dataset.path);
    preview.querySelector(".le-preview").innerHTML = `<p dir="auto">${fmt(q.question || "")}</p><ul>${(q.choices || []).map(c => `<li dir="auto">${fmt(c.text || "")}</li>`).join("")}</ul>`;
    const badge = preview.querySelector(".le-source");
    badge.className = "le-source le-person"; badge.textContent = SOURCE.person;
  }
  changed({ redraw: event.type === "change" && field.tagName === "SELECT" });
}

function onClick(event) {
  const button = event.target.closest("[data-act]");
  if (event.target.closest("#le-back")) { leave(); return; }
  if (event.target.closest("#le-retry")) { retry(); return; }
  if (!button || !state?.doc) return;
  const doc = state.doc, act = button.dataset.act;
  const skillPath = button.closest(".le-skill")?.dataset.path, qPath = button.closest(".le-question")?.dataset.path;
  const skills = doc.skills = doc.skills || [];
  const si = skillPath ? Number(skillPath.split(".")[1]) : -1, qi = qPath ? Number(qPath.split(".")[3]) : -1;
  const questions = si >= 0 ? (skills[si].questions = skills[si].questions || []) : [];
  if (act === "right") {
    const choices = at(doc, qPath).choices, ci = Number(button.closest(".le-choice").dataset.path.split(".").pop());
    choices.forEach((c, i) => { if (i === ci) { c.correct = true; delete c.mistake; } else if (c.correct) { delete c.correct; c.mistake = ""; } });
    asPerson(at(doc, qPath));
  } else if (act === "del-choice") {
    at(doc, qPath).choices.splice(Number(button.closest(".le-choice").dataset.path.split(".").pop()), 1); asPerson(at(doc, qPath));
  } else if (act === "add-choice") { at(doc, qPath).choices = [...(at(doc, qPath).choices || []), { text: "", mistake: "" }]; asPerson(at(doc, qPath)); }
  else if (act === "add-q") questions.push({ question: "", source: "person", choices: [{ text: "", correct: true }, { text: "", mistake: "" }] });
  else if (act === "del-q") { if (!confirm("למחוק את השאלה?")) return; questions.splice(qi, 1); }
  else if (act === "up-q" || act === "down-q") move(questions, qi, qi + (act === "up-q" ? -1 : 1));
  else if (act === "add-s") skills.push({ name: "", short: "", description: "", questions: [] });
  else if (act === "del-s") { if (!confirm("למחוק את המיומנות ואת השאלות שלה?")) return; skills.splice(si, 1); }
  else if (act === "up-s" || act === "down-s") move(skills, si, si + (act === "up-s" ? -1 : 1));
  else if (act === "add-mistake") newMistake();
  else return;
  changed({ redraw: true });
}

async function refresh() {
  const v = await api(`/api/worksheets/${state.id}`).catch(() => null);
  if (!v || !state) return;
  const was = state.view.status;
  state.view = v;
  if (v.status !== "drafting") {
    clearInterval(state.poll); state.poll = null;
    if (was === "drafting") { state.doc = (await api(`/api/subjects/lessons/${state.id}`)).draft; draw(); }
  }
}

async function retry() {
  try { state.view = await api(`/api/worksheets/${state.id}/draft`, { method: "POST" }); draw(); watch(); }
  catch (e) { said(e.message); }
}

function watch() {
  clearInterval(state.poll);
  if (state.view.status === "drafting") state.poll = setInterval(refresh, 2000);
}

function leave() {
  const back = state.onBack;
  if (state.timer) saveNow();
  clearInterval(state.poll);
  state.pages.forEach(url => url && URL.revokeObjectURL(url));
  state = null;
  back();
}

/** Open the editor for a lesson inside `root` (an element the caller drew). `onBack` returns to where the person came from. */
export async function open(root, lessonId, onBack) {
  root.id = "lesson-editor-root";
  const lesson = await api(`/api/subjects/lessons/${lessonId}`);
  const view = lesson.source === "worksheet" ? await api(`/api/worksheets/${lessonId}`) : { status: "ready", pages: [], has_text: false };
  state = { id: lessonId, view, doc: view.status === "ready" ? lesson.draft : null, pages: [], text: "", timer: null, poll: null, onBack };
  if (state.doc && !Object.keys(state.doc).length) state.doc = { name: "", skills: [], mistakes: {} };
  state.pages = await Promise.all(view.pages.map(i => pageUrl(lessonId, i)));
  if (view.has_text) state.text = (await api(`/api/worksheets/${lessonId}/text`)).text;
  draw();
  root.addEventListener("input", onInput);
  root.addEventListener("change", onInput);
  root.addEventListener("click", onClick);
  watch();
}
