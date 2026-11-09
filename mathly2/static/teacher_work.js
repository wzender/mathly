// The teacher's work tab: give an assignment (a file, a photo, the board, one of the bank's written quizzes, or an exercise test) and see
// how many students handed in. `ctx` is the teacher's screen: { draw(html), tabs(active), wire() }.
import { api, swr } from "./api.js";
import { loadBoard } from "./exercise.js";
import { withBusy } from "./busy.js";
import { esc, fmt } from "./math.js";
import { isTouch, pictureUrl, prepare, sendPicture } from "./media.js";
import { daysText, shortDate } from "./ui.js";

const today = () => new Date().toISOString().slice(0, 10);
const SOURCES = [["pages", "קובץ, צילום או כתיבה על הלוח"], ["quiz", "בוחן כתוב מהמאגר"], ["exercise_test", "מבחן תרגול"]];

function sourceFields(c) {
  const quizzes = c.lessons.filter(l => l.has_quiz);
  return `<div class="source" data-source="pages"><p class="muted">הוסיפו עמודים: קובץ (תמונה או PDF), צילום או כתיבה על הלוח.</p>
      <ul class="plain drafts" data-pages><li class="muted" data-pages-empty>עוד לא נוספו עמודים.</li></ul>
      <p class="actions"><label class="button file">🖼 קובץ<input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" multiple hidden data-pages-file></label>
        ${isTouch() ? `<label class="button file">📷 צילום<input type="file" accept="image/*" capture="environment" hidden data-pages-camera></label>` : ""}
        <button type="button" data-pages-board>✎ כתיבה על הלוח</button></p></div>
    <div class="source" data-source="quiz" hidden>${quizzes.length ? `<label>הבוחן הכתוב של השיעור<select name="quiz_lesson">${quizzes.map(l => `<option value="${esc(l.id)}">${fmt(l.name)}</option>`).join("")}</select></label>
      <p class="muted">ארבע שאלות כתובות, 100 נקודות.</p>` : `<p class="muted">לשיעורים של הכיתה אין בוחן כתוב במאגר.</p>`}</div>
    <div class="source" data-source="exercise_test" hidden>${c.tests.length ? `<label>המבחן<select name="test">${c.tests.map(t => `<option value="${t.id}">מבחן ב־${shortDate(t.date)}: ${t.lessons.map(fmt).join(", ")}</option>`).join("")}</select></label>
      <label>איזה מבחן תרגול<select name="exercise_number"><option value="1">מבחן תרגול 1</option><option value="2">מבחן תרגול 2</option></select></label>` : `<p class="muted">עוד לא נקבע מבחן לכיתה (בלשונית מבחנים).</p>`}</div>`;
}

function newForm(c) {
  return `<form class="assignment-form" data-class="${c.id}"><label>כותרת<input name="title" required maxlength="200"></label>
    <label>הערה לתלמידים (לא חובה)<textarea name="note" rows="2" maxlength="1000"></textarea></label>
    <label>להגיש עד<input name="due_date" type="date" required min="${today()}"></label>
    <fieldset><legend>התוכן</legend>${SOURCES.map(([v, label], i) => `<label class="check"><input type="radio" name="source" value="${v}"${i === 0 ? " checked" : ""}> ${label}</label>`).join("")}</fieldset>
    ${sourceFields(c)}<p class="error form-error" role="alert" hidden></p><p><button class="primary" type="submit">שליחה לכיתה</button></p></form>`;
}

function row(a) {
  const counts = a.kind === "exercise_test" ? `<span class="tag">${a.done} מתוך ${a.students} עשו</span>`
    : `<span class="tag counts">${a.handed_in + a.graded + a.returned} מתוך ${a.students} הגישו</span><span class="tag">${a.graded} נבדקו</span>${a.waiting ? `<span class="tag waiting">${a.waiting} מחכות לבדיקה</span>` : ""}`;
  const what = a.kind === "quiz" ? `בוחן כתוב: ${fmt(a.quiz_lesson.name)}` : a.kind === "exercise_test" ? `מבחן תרגול ${a.test.number}` : `${a.pages.length} עמודים`;
  return `<article class="card assignment-row" data-assignment="${a.id}"><div class="hrow"><h4 class="grow">${fmt(a.title)}</h4><span class="muted">עד ${shortDate(a.due_date)} (${daysText(a.days_left)})</span></div>
    <p class="muted">${what}${a.note ? ` · ${fmt(a.note)}` : ""}</p><p class="tags">${counts}</p>
    <p><button type="button" data-remove-assignment="${a.id}">הסרה</button></p></article>`;
}

export const showAssignments = ctx => swr("/api/teaching/assignments", classes => drawAssignments(ctx, classes));

async function drawAssignments(ctx, classes) {
  ctx.draw(`${ctx.tabs("assignments")}<section id="work"><h2>משימות</h2>
    ${classes.length ? classes.map(({ class: c, assignments }) => `<section class="card class-work" data-class="${c.id}"><h3>${esc(c.name)}</h3>
      ${assignments.length ? assignments.map(row).join("") : `<p class="muted">עוד לא נתנו משימה לכיתה.</p>`}
      <details class="new-assignment"><summary>משימה חדשה</summary>${newForm(c)}</details></section>`).join("")
      : `<section class="card"><p class="muted">עוד לא שייכו אותך ככיתה. מנהל הכיתות קובע מי מלמד/ת כל כיתה.</p></section>`}</section>`);
  ctx.wire();
  const root = document.getElementById("work");
  root.querySelectorAll(".assignment-form").forEach(form => wireForm(form, ctx));
  root.addEventListener("click", async event => {
    const button = event.target.closest("[data-remove-assignment]");
    if (button) {                                                                        // two steps, so a slip does not remove it
      button.outerHTML = `<span class="confirm"><button type="button" class="danger" data-confirm-remove-assignment="${button.dataset.removeAssignment}">אישור הסרה</button> <button type="button" data-cancel-remove>ביטול</button></span>`;
      return;
    }
    if (event.target.closest("[data-cancel-remove]")) return showAssignments(ctx);
    const confirm = event.target.closest("[data-confirm-remove-assignment]")?.dataset.confirmRemoveAssignment;
    if (confirm) { await api(`/api/assignments/${confirm}`, { method: "DELETE" }); await showAssignments(ctx); }
  });
}

function wireForm(form, ctx) {
  let pages = [];
  const error = form.querySelector(".form-error");
  const fail = text => { error.textContent = text; error.hidden = false; error.scrollIntoView({ block: "nearest" }); };
  const list = form.querySelector("[data-pages]");
  const drawPages = () => {
    list.innerHTML = pages.length ? pages.map(id => `<li data-page="${esc(id)}"><img data-picture="${esc(id)}" alt="עמוד של המשימה" hidden>
      <button type="button" class="remove" data-remove-page="${esc(id)}" aria-label="הסרת העמוד">✕</button></li>`).join("") : `<li class="muted" data-pages-empty>עוד לא נוספו עמודים.</li>`;
    list.querySelectorAll("img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.remove(); } });
  };
  const upload = async (blob, type) => {
    const got = await fetch("/api/assignments/pages", { method: "POST", headers: { Authorization: "Bearer " + await (await import("./session.js")).token(), "Content-Type": type || blob.type }, body: blob });
    const data = await got.json().catch(() => ({}));
    if (!got.ok) throw new Error(typeof data.detail === "string" ? data.detail : "משהו השתבש");
    pages.push(...data.pictures);
    drawPages();
  };
  const addFiles = async files => {
    error.hidden = true;
    for (const file of files) {
      try { await upload(file.type === "application/pdf" ? file : await prepare(file), file.type === "application/pdf" ? file.type : "image/jpeg"); } catch (e) { fail(e.message); }
    }
  };
  form.querySelectorAll("[data-pages-file], [data-pages-camera]").forEach(input => input.addEventListener("change", async () => { const files = [...input.files]; input.value = ""; await withBusy(input.closest("label"), addFiles(files)); }));
  list.addEventListener("click", event => { const id = event.target.closest("[data-remove-page]")?.dataset.removePage; if (id) { pages = pages.filter(p => p !== id); drawPages(); } });
  form.querySelector("[data-pages-board]").addEventListener("click", async () => {
    await loadBoard();
    if (!window.MathlyBoard?.openFull) return;
    const host = Object.assign(document.createElement("div"), { className: "mx-layer" });
    document.body.append(host);
    window.MathlyBoard.openFull({ host, key: `assignment-new:${form.dataset.class}`, title: "כתיבת משימה על הלוח", sendLabel: "הוספה למשימה",
      submit: async (page, blob) => { try { await upload(blob, "image/png"); return {}; } catch (e) { return { error: e.message }; } }, done: () => host.remove() });
  });
  form.querySelectorAll("[name=source]").forEach(radio => radio.addEventListener("change", () => {
    form.querySelectorAll(".source").forEach(box => { box.hidden = box.dataset.source !== form.querySelector("[name=source]:checked").value; });
  }));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    error.hidden = true;
    const data = new FormData(form), kind = data.get("source");
    const body = { title: data.get("title"), note: data.get("note") || "", due_date: data.get("due_date"), kind };
    if (kind === "pages") body.pages = pages;
    if (kind === "quiz") body.quiz_lesson = data.get("quiz_lesson");
    if (kind === "exercise_test") { body.test_id = Number(data.get("test")); body.exercise_number = Number(data.get("exercise_number")); }
    try {
      await api(`/api/classes/${form.dataset.class}/assignments`, { method: "POST", body });
      await showAssignments(ctx);
    } catch (e) { fail(e.message); }                                                       // the form keeps what was typed
  });
}

// ---------- the inbox: everything that waits for the teacher, oldest first ----------

const when = iso => new Date(iso).toLocaleString("he-IL", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });

export const showInbox = (ctx, notice = "") => swr("/api/teaching/inbox", items => drawInbox(ctx, items, notice));

async function drawInbox(ctx, items, notice) {
  ctx.draw(`${ctx.tabs("inbox")}<section id="inbox"><h2>תיבת בדיקה</h2>${notice ? `<p class="ex-note" role="status" id="inbox-notice">${esc(notice)}</p>` : ""}
    ${items.length ? `<ul class="plain inbox-list" id="inbox-list">${items.map(i => `<li data-submission="${i.id}" data-kind="${esc(i.kind)}"><button type="button" class="open-submission" data-open="${i.id}">
      <b>${esc(i.student || "תלמיד/ה")}</b> · ${fmt(i.assignment.title)}<br><span class="muted">${esc(i.assignment.class.name)} · ${i.kind === "again" ? `ביקש/ה בדיקה חוזרת ${when(i.asked_at)}` : `הוגש ${when(i.handed_at)}${i.late ? " · באיחור" : ""}`}</span></button></li>`).join("")}</ul>`
      : `<p class="muted" id="inbox-empty">אין מה לבדוק. כל ההגשות נבדקו.</p>`}</section>`);
  ctx.wire();
  document.getElementById("inbox").addEventListener("click", event => {
    const id = event.target.closest("[data-open]")?.dataset.open;
    if (id) openSubmission(ctx, id);
  });
}

/** The AI's check of the answer, as a suggestion: the teacher's grade is what counts. */
function aiSuggestion(s) {
  const a = s.ai;
  if (a && a.state === "done" && !s.ai_open) {
    const r = a.result || {};
    const score = r.score === null || r.score === undefined ? `<p>ה־AI לא נתן ציון (${r.verdict === "unreadable" ? "התמונה לא קריאה" : "לא היה בטוח"}). כדאי לבדוק בעצמכם.</p>` : `<p>הציון המוצע: <b id="ai-score">${r.score}</b></p>`;
    return `<section class="ai-check" id="ai-suggestion"><h4>הצעה של AI (הציון שלכם קובע)</h4>${score}<p>${fmt(r.feedback || "")}</p>
      <details><summary>מה ה־AI קרא ומה הפתרון</summary><p class="muted">${fmt(r.transcription || "")}</p><p>${fmt(r.solution || "")}</p></details></section>`;
  }
  if (s.ai_open) return `<p class="muted" id="ai-pending" role="status">בדיקת ה־AI בדרך…</p>`;
  const f = s.ai_failed;
  const failed = f ? `<p class="error" id="ai-failed">בדיקת ה־AI נכשלה: ${esc(f.failure?.label || "")}. ${esc(f.failure?.todo || "")} <span class="muted" dir="ltr">${esc(f.failure?.detail || "")}</span></p>` : "";
  return `${failed}${s.ai_enabled ? `<p><button type="button" id="teacher-ai-check">${f ? "ניסיון חוזר: בדיקת AI" : "בדיקת AI"}</button></p>` : ""}`;
}

async function openSubmission(ctx, id) {
  const s = await api(`/api/submissions/${id}`);
  const material = s.quiz ? `<h4>הבוחן הכתוב</h4><ol class="qz-written">${s.quiz.questions.map(x => `<li><p class="ex-text" dir="auto">${fmt(x.question)}</p><span class="muted">${x.points} נק׳</span></li>`).join("")}</ol>`
    : s.pages.length ? `<h4>הדף שניתן</h4><div class="pages">${s.pages.map(p => `<img data-picture="${esc(p)}" alt="עמוד של המשימה" hidden>`).join("")}</div>` : "";
  ctx.draw(`${ctx.tabs("inbox")}<section id="check" class="card" data-submission="${s.id}"><p><button type="button" id="back-to-inbox">‹ חזרה לתיבה</button></p>
    <h2>${esc(s.student)}: ${fmt(s.assignment.title)}</h2><p class="muted">${esc(s.assignment.class.name)} · הוגש ${when(s.handed_at)}${s.late ? " · באיחור" : ""}</p>
    ${s.look_again ? `<p class="ex-note" id="look-again-note" role="status">התלמיד/ה ביקש/ה שתבדקו שוב.</p>` : ""}
    <h4>התשובה</h4><div class="pages" id="answer-pictures">${s.pictures.map(p => p.deleted ? `<p class="muted">התמונה נמחקה</p>` : `<img data-picture="${esc(p.id)}" alt="תמונה של התשובה" hidden>`).join("")}</div>
    ${aiSuggestion(s)}
    <details><summary>מה ביקשנו</summary>${material || `<p class="muted">אין תוכן להצגה.</p>`}</details>
    <form id="check-form"><label>ציון (0 עד 100)<input name="grade" type="number" min="0" max="100" step="1" inputmode="numeric"></label>
      <label>הערה לתלמיד/ה<textarea name="note" rows="3" maxlength="2000"></textarea></label>
      <p class="error" id="check-error" role="alert" hidden></p>
      <p><button type="submit" class="primary" id="give-grade">שמירת הציון</button> <button type="button" id="send-back">החזרה לתיקון</button></p></form></section>`);
  ctx.wire();
  document.querySelectorAll("#check img[data-picture]").forEach(async img => { try { img.src = await pictureUrl(img.dataset.picture); img.hidden = false; } catch { img.remove(); } });
  const form = document.getElementById("check-form"), error = document.getElementById("check-error");
  document.getElementById("teacher-ai-check")?.addEventListener("click", async event => {
    try { await withBusy(event.currentTarget, api(`/api/submissions/${id}/ai-check`, { method: "POST" })); } catch (e) { error.textContent = e.message; error.hidden = false; return; }
    openSubmission(ctx, id);
  });
  if (s.ai_open) setTimeout(() => { if (document.getElementById("check")?.dataset.submission === String(id)) openSubmission(ctx, id); }, 5000);   // the check is on its way
  const fail = text => { error.textContent = text; error.hidden = false; };
  document.getElementById("back-to-inbox").addEventListener("click", () => showInbox(ctx));
  const send = async (path, body, done) => {
    error.hidden = true;
    try { await api(`/api/submissions/${id}/${path}`, { method: "POST", body: { ...body, seen: s.seen } }); await showInbox(ctx, done); }
    catch (e) { fail(e.status === 409 ? `${e.message} ` : e.message); if (e.status === 409) error.insertAdjacentHTML("beforeend", `<button type="button" id="reopen">פתיחה מחדש</button>`); document.getElementById("reopen")?.addEventListener("click", () => showInbox(ctx)); }
  };
  form.addEventListener("submit", event => {
    event.preventDefault();
    const grade = form.elements.grade.value;
    if (grade === "" || !Number.isInteger(Number(grade)) || Number(grade) < 0 || Number(grade) > 100) return fail("הציון הוא מספר שלם בין 0 ל־100.");
    send("grade", { grade: Number(grade), note: form.elements.note.value }, "הציון נשמר.");
  });
  document.getElementById("send-back").addEventListener("click", () => {
    if (!form.elements.note.value.trim()) return fail("צריך לכתוב מה לתקן.");
    send("return", { note: form.elements.note.value }, "המשימה הוחזרה לתלמיד/ה לתיקון.");
  });
}
