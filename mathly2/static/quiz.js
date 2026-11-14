// A lesson quiz, an exercise test or the simulation: multiple-choice questions (only the simulation is on a server timer), as a dialog over the path (the same sheet as the exercise screen).
// A tap saves the choice on the server; nothing says whether it is right. After the submit (or when time ends) the result shows the
// grade, the skills that lost points and the mistakes' names and tips, never the right answers.
import { api, ApiError } from "./api.js";
import { loadBoard } from "./exercise.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { pathHref, shuffled } from "./ui.js";
import { hasWork, sendWork } from "./boardwork.js";

const LIVE_AT = new Set([300, 60, 10, 0]);        // seconds left at which the timer is announced to a screen reader

let layer = null, attempt = null, at = 0, timer = null, deadline = 0, orders = {}, warned = false;

const q = selector => layer?.querySelector(selector);
export const isOpen = () => !!layer;

const clock = secs => `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;

function stopTimer() { clearInterval(timer); timer = null; }

/** Open the sheet for an attempt that the server already has (`#/quiz/<lesson>/<attempt>`). */
export async function open(attemptId) {
  const [data] = await Promise.all([api(`/api/attempts/${encodeURIComponent(attemptId)}`), loadBoard()]);
  show(data);
}

/** The student opened a lesson's quiz: the server resumes the open attempt or draws a new one; the address then names the attempt. */
export async function start(lessonId) {
  const data = await api(`/api/lessons/${encodeURIComponent(lessonId)}/quiz/start`, { method: "POST" });
  location.replace(`#/quiz/${encodeURIComponent(lessonId)}/${encodeURIComponent(data.id)}`);
}

/** An exercise test (1 or 2) of a real test, or its simulation: the same, with the attempt's id put in the address.
 *  `allSkills` (address `#/exam/<test>/<n>/all`) also draws the skills not started yet. */
export async function startExam(testId, number, allSkills = false) {
  const data = await api(`/api/tests/${encodeURIComponent(testId)}/exercise/${encodeURIComponent(number)}/start${allSkills ? "?all_skills=true" : ""}`, { method: "POST" });
  location.replace(`#/exam/${encodeURIComponent(testId)}/${encodeURIComponent(number)}/${encodeURIComponent(data.id)}`);
}

export async function startSimulation(testId) {
  const data = await api(`/api/tests/${encodeURIComponent(testId)}/simulation/start`, { method: "POST" });
  location.replace(`#/sim/${encodeURIComponent(testId)}/${encodeURIComponent(data.id)}`);
}

/** What the sheet is called, who it is about and where closing it leads, by kind. */
const names = a => a.kind === "exercise_test" ? { title: `מבחן תרגול ${a.test.number}`, again: "מבחן חוזר" }
  : a.kind === "simulation" ? { title: "מבחן סימולציה", again: "" } : { title: "בוחן", again: "בוחן חוזר" };
const chip = a => a.kind === "quiz" ? fmt(a.lesson.name) : a.test.lessons.map(fmt).join(", ");
const leaveTo = () => !attempt || attempt.kind === "quiz" ? pathHref() : `#/test/${attempt.test.id}`;

function ensureLayer() {
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "mx-layer";
    document.body.append(layer);
    layer.addEventListener("click", onClick);
  }
  layer.innerHTML = `<div class="mx-scrim" data-close></div><div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="qz-title"></div>`;
}

function show(data) {
  stopTimer();
  if (!attempt || attempt.id !== data.id) at = 0;          // a different attempt starts at its first question
  attempt = data;
  warned = false;
  ensureLayer();
  if (data.state === "open") {
    if (!(data.id in orders)) orders = { [data.id]: {} };
    at = Math.min(at, data.questions.length - 1);
    deadline = data.due_at ? performance.now() + Math.max(0, new Date(data.due_at) - new Date(data.now)) : 0;   // the server's clock, not the device's
    renderQuestion();
    if (data.due_at) { timer = setInterval(tick, 1000); tick(); }
  } else {
    renderResult();
  }
  q(".mx-x")?.focus({ preventScroll: true });
}

export function close() {
  if (!layer) return;
  stopTimer();
  window.MathlyBoard?.closeFull?.();
  layer.remove();
  layer = attempt = null;
  at = 0;
}

const left = () => Math.max(0, Math.ceil((deadline - performance.now()) / 1000));

async function tick() {
  if (!layer || attempt?.state !== "open" || !attempt.due_at) return;
  const secs = left();
  const label = q("#qz-timer");
  if (label) label.textContent = clock(secs);
  if (LIVE_AT.has(secs) && q("#qz-live")) q("#qz-live").textContent = secs === 0 ? "הזמן נגמר" : `נשארו ${secs >= 60 ? `${secs / 60} דקות` : `${secs} שניות`}`;
  if (secs === 0) {
    stopTimer();
    await finish(false);
  }
}

/** Ask the server for the attempt: past the deadline it has been settled already, before it a submit settles it. */
async function finish(submit) {
  const id = attempt.id;
  try {
    if (submit) { await saving; await sendAllWork(); }                                         // the boards go with the hand-in
    const data = submit ? await api(`/api/attempts/${id}/submit`, { method: "POST" }) : await api(`/api/attempts/${id}`);
    if (data.state === "open") { setTimeout(() => layer && finish(false), 1000); return; }      // a hair early on the device: ask again
    show(data);
  } catch (error) {
    if (q("#qz-fb")) q("#qz-fb").innerHTML = `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`;
  }
}

const heading = (title) => `<div class="mx-shtop"><div><span class="ex-chip">${chip(attempt)}</span><h3 id="qz-title">${title}</h3></div>
  <div class="mx-shacts">${attempt.state === "open" ? (window.MathlyBoard?.button() || "") : ""}
    <button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>`;

function choicesOf(question) {
  const order = (orders[attempt.id] ||= {});
  order[question.key] ||= shuffled(question.choices).map(c => c.index);
  return order[question.key].map(i => question.choices.find(c => c.index === i));
}

function renderQuestion() {
  const total = attempt.questions.length, question = attempt.questions[at], saved = attempt.answers[question.key];
  const answered = Object.keys(attempt.answers).length;
  q(".mx-sheet").innerHTML = `${heading(names(attempt).title)}
    <div class="qz-bar">${attempt.due_at ? `<span class="qz-timer" id="qz-timer" aria-label="הזמן שנשאר">${clock(left())}</span>` : ""}
      <span id="qz-count">שאלה ${at + 1} מתוך ${total}</span></div>
    <span class="mx-sr" id="qz-live" role="status" aria-live="polite"></span>
    <div class="qz-dots" role="group" aria-label="נענו ${answered} מתוך ${total}">${attempt.questions.map((x, i) =>
      `<button type="button" class="qz-dot${attempt.answers[x.key] !== undefined ? " done" : ""}${i === at ? " cur" : ""}" data-go="${i}" aria-label="שאלה ${i + 1}${attempt.answers[x.key] !== undefined ? ", נענתה" : ", לא נענתה"}"${i === at ? ' aria-current="step"' : ""}></button>`).join("")}</div>
    <div class="mx-q" id="qz-q" data-key="${esc(question.key)}"><p class="ex-text" dir="auto">${fmt(question.question)}</p>${figures(question)}
      <div class="ex-choices" id="qz-choices">${choicesOf(question).map(c =>
        `<button type="button" class="ex-choice qz-choice${saved === c.index ? " picked" : ""}" data-i="${c.index}" aria-pressed="${saved === c.index}" dir="auto">${fmt(c.text)}</button>`).join("")}</div>
      <div id="qz-fb" role="status" aria-live="polite"></div></div>
    <div class="qz-nav"><button type="button" data-go="${at - 1}"${at === 0 ? " disabled" : ""}>הקודמת</button>
      <button type="button" data-go="${at + 1}"${at === total - 1 ? " disabled" : ""}>הבאה</button>
      <button type="button" class="primary" id="qz-submit">הגשה</button></div>
    <div id="qz-warn"></div>`;
  window.MathlyBoard?.mount(layer, `quiz:${attempt.id}:${question.key}`, { question: () => q("#qz-q") });
}

let saving = Promise.resolve();   // the answer saves still on their way to the server

const boardKey = key => `quiz:${attempt.id}:${key}`;

/** In a quiz or a test the way counts: a choice needs something written on the board for this question (or a board already saved). */
function needsWork(question) {
  if (!attempt.work_required || hasWork(boardKey(question.key)) || (attempt.work || []).includes(question.key)) return false;
  q("#qz-fb").innerHTML = `<div class="ex-note qz-need-work" id="qz-need-work" role="alert"><p><b>✏️ קודם כותבים את הדרך בלוח</b></p>
    <p>המורה בודק גם את הדרך, לא רק את התשובה. פתרו בלוח ואז בחרו תשובה.</p>
    <p><button type="button" class="primary" id="qz-open-board">פתיחת הלוח</button></p></div>`;
  return true;
}

/** Send the board of every answered question that changed since it was last sent (before handing in). */
function sendAllWork() {
  const id = attempt.id;
  return Promise.allSettled(attempt.questions.filter(x => attempt.answers[x.key] !== undefined)
    .map(x => sendWork(`quiz:${id}:${x.key}`, id, x.key).then(ok => { if (ok && attempt?.id === id) (attempt.work ||= []).push(x.key); })));
}

async function choose(button) {
  const question = attempt.questions[at], index = Number(button.dataset.i), before = attempt.answers[question.key];
  if (needsWork(question)) return;
  attempt.answers[question.key] = index;
  layer.querySelectorAll(".qz-choice").forEach(b => { const on = Number(b.dataset.i) === index; b.classList.toggle("picked", on); b.setAttribute("aria-pressed", String(on)); });
  q(`.qz-dot[data-go="${at}"]`)?.classList.add("done");
  const id = attempt.id, save = saving.then(() => api(`/api/attempts/${id}/answers`, { method: "PUT", body: { key: question.key, choice: index } }));
  saving = save.catch(() => {});      // one save at a time, and a submit waits for the last one (else it is graded without it)
  try {
    await save;
    sendWork(boardKey(question.key), id, question.key).then(ok => { if (ok && attempt?.id === id) (attempt.work ||= []).push(question.key); }).catch(() => {});
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) return finish(false);                // time ran out: the server already submitted
    if (before === undefined) delete attempt.answers[question.key]; else attempt.answers[question.key] = before;
    renderQuestion();
    q("#qz-fb").innerHTML = `<p class="error" role="alert">${esc(error.message || "התשובה לא נשמרה, נסו שוב")}</p>`;
  }
}

function submit() {
  const missing = attempt.questions.filter(x => attempt.answers[x.key] === undefined).length;
  if (missing && !warned) {
    warned = true;
    q("#qz-warn").innerHTML = `<div class="ex-note" role="alert"><p>יש ${missing} ${missing === 1 ? "שאלה" : "שאלות"} בלי תשובה. הן ייחשבו שגויות.</p>
      <p><button type="button" class="primary" id="qz-yes">הגשה בכל זאת</button> <button type="button" id="qz-back">חזרה לבוחן</button></p></div>`;
    q("#qz-back").focus();
    return;
  }
  finish(true);
}

const VERDICT = { correct: ["✓", "דרך נכונה"], partial: ["◐", "חלק מהדרך נכון"], wrong: ["✗", "הדרך לא נכונה"], unclear: ["?", "לא הצלחנו לקרוא"] };

/** The AI's review of the way (a practice test, the simulation): waiting, failed, or per question with a board its verdict, feedback and tip. */
function reviewHtml(r) {
  const review = r.review;
  if (!review) return "";
  if (review.state === "pending") return `<section class="qz-review" id="qz-review" data-state="pending"><h4>משוב על הדרך</h4>
    <p class="muted"><span class="spin" aria-hidden="true"></span> בודקים את הדרך שכתבתם בלוח… זה לוקח כדקה.</p></section>`;
  if (review.state === "failed") return `<section class="qz-review" id="qz-review" data-state="failed"><h4>משוב על הדרך</h4><p class="muted">לא הצלחנו לבדוק את הדרך הפעם. המורה יראו את הלוחות.</p></section>`;
  const rows = (r.keys || []).map((key, i) => [i + 1, review.questions[key]]).filter(([, q]) => q);
  return `<section class="qz-review" id="qz-review" data-state="done"><h4>משוב על הדרך</h4>
    ${review.summary ? `<p class="qz-review-sum">${fmt(review.summary)}</p>` : ""}
    ${rows.length ? `<ol class="plain qz-review-list">${rows.map(([n, q]) => `<li class="v-${esc(q.verdict)}" data-n="${n}"><p><b>שאלה ${n}</b>
      <span class="tag"><span aria-hidden="true">${VERDICT[q.verdict][0]}</span> ${VERDICT[q.verdict][1]}</span></p>
      <p>${fmt(q.feedback)}</p>${q.tip ? `<p class="muted">💡 ${fmt(q.tip)}</p>` : ""}</li>`).join("")}</ol>`
      : `<p class="muted">לא נשמרה דרך בלוח באף שאלה.</p>`}
    <p class="muted qz-review-note">משוב אוטומטי. המורה בודקים את הדרך ונותנים את הנקודות.</p></section>`;
}

/** While the review is being written, ask again every few seconds and redraw only its section. */
function waitForReview(id) {
  setTimeout(async () => {
    if (!layer || attempt?.id !== id || attempt.review?.state !== "pending") return;
    try {
      const fresh = await api(`/api/attempts/${encodeURIComponent(id)}`);
      if (!layer || attempt?.id !== id) return;
      attempt.review = fresh.review;
      q("#qz-review")?.replaceWith(Object.assign(document.createElement("div"), { innerHTML: reviewHtml(fresh) }).firstElementChild || "");
    } catch { /* try again */ }
    waitForReview(id);
  }, 4000);
}

function renderResult() {
  const r = attempt;
  stopTimer();
  q(".mx-sheet").innerHTML = `${heading(`תוצאת ${names(r).title}`)}
    <div class="qz-result"><p class="qz-grade" id="qz-grade" aria-label="הציון ${r.grade}"><b>${r.grade}</b><span>מתוך 100</span></p>
      <p>${r.right === 1 ? "תשובה נכונה אחת" : `${r.right} תשובות נכונות`} מתוך ${r.total}${r.timed_out ? ". הזמן נגמר והבוחן הוגש כמו שהוא." : ""}</p>
      <p class="muted" id="qz-best"></p>${r.kind === "simulation" ? `<p class="muted">מבחן סימולציה אפשר לעשות פעם אחת.</p>` : ""}</div>
    ${r.lost_skills.length ? `<h4>איפה אפשר להשתפר</h4><ul class="plain" id="qz-lost">${r.lost_skills.map(s =>
      `<li><a href="#/skill/${esc(s.id)}">${fmt(s.name)}</a><span class="muted">${s.missed} ${s.missed === 1 ? "שאלה שגויה" : "שאלות שגויות"}</span></li>`).join("")}</ul>
      <p class="muted">אפשר לתרגל את המיומנות ואז לנסות שוב.</p>` : `<p id="qz-perfect">כל התשובות נכונות. כל הכבוד!</p>`}
    ${r.missed.length ? `<h4>הטעויות</h4><ol class="qz-missed" id="qz-missed">${r.missed.map(m => `<li><p class="ex-text" dir="auto">${fmt(m.question)}</p>
      ${m.picked ? `<p class="muted">בחרתם: <span dir="auto">${fmt(m.picked)}</span></p>` : `<p class="muted">לא ענו על השאלה.</p>`}
      ${m.mistake ? `<p><b>${esc(m.mistake.name)}</b>${m.mistake.tip ? `<br>${fmt(m.mistake.tip)}` : ""}</p>` : ""}</li>`).join("")}</ol>` : ""}
    ${reviewHtml(r)}
    <p class="qz-actions">${names(r).again ? `<button type="button" class="primary" id="qz-retake">${names(r).again}</button> ` : ""}<button type="button" data-close>${r.kind === "quiz" ? "חזרה למסלול" : "חזרה למבחן"}</button></p>`;
  if (r.review?.state === "pending") waitForReview(r.id);
  const best = r.kind === "quiz" ? api(`/api/lessons/${encodeURIComponent(r.lesson.id)}/quiz`).then(f => f.best === null ? "" : `הציון של השיעור: ${f.best}`)
    : r.kind === "exercise_test" ? api(`/api/tests/${encodeURIComponent(r.test.id)}`).then(t => `הציון הטוב במבחן התרגול: ${t.exercise_tests[r.test.number - 1].best ?? ""}`) : Promise.resolve("");
  best.then(text => { if (text && q("#qz-best")) q("#qz-best").textContent = text; }).catch(() => {});
}

function onClick(event) {
  const target = event.target;
  if (target.closest("[data-close]")) { location.hash = leaveTo(); return; }
  if (target.closest("[data-board-toggle]")) { window.MathlyBoard?.toggle(); return; }
  if (attempt?.state === "open") {
    const go = target.closest("[data-go]");
    if (go && !go.disabled) { at = Number(go.dataset.go); warned = false; renderQuestion(); return; }
    const choice = target.closest(".qz-choice");
    if (choice) { choose(choice); return; }
    if (target.closest("#qz-submit")) { submit(); return; }
    if (target.closest("#qz-open-board")) { window.MathlyBoard?.show?.(0); return; }
    if (target.closest("#qz-yes")) { finish(true); return; }
    if (target.closest("#qz-back")) { q("#qz-warn").innerHTML = ""; warned = false; return; }
  } else if (target.closest("#qz-retake")) {
    at = 0;
    const again = attempt.kind === "quiz" ? start(attempt.lesson.id) : startExam(attempt.test.id, attempt.test.number);
    again.catch(error => { q(".qz-actions").insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message)}</p>`); });
  }
}

window.addEventListener("mathly:leave", close);

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && layer && !document.querySelector(".mx-board.full")) location.hash = leaveTo();
});
