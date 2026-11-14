// The exercise screen: one skill, one question at a time, as a dialog over the path (mathly1's sheet).
// Tap a choice and the server grades it; a wrong answer names the mistake and never marks the right choice.
import { api, ApiError } from "./api.js";
import { figures } from "./figures.js";
import { clear as clearComet, cross as crossComet } from "./comets.js";
import { esc, fmt } from "./math.js";
import * as aiSheet from "./ai_sheet.js";
import { pathHref, shuffled } from "./ui.js";
import { sendWorkQuietly } from "./boardwork.js";


const COUNTDOWN = 3;   // seconds before the next question after a right answer
let layer = null, skill = null, timer = null, helped = false, boardReady = null, aiOn = false;

const script = src => new Promise((ok, no) => {
  const s = document.createElement("script");
  s.src = src; s.onload = ok; s.onerror = no;
  document.head.append(s);
});

/** The board and its styles load the first time a sheet opens, not with the app. If they cannot load, the sheet works without it. */
export function loadBoard() {
  return boardReady ||= new Promise(done => {
    const link = Object.assign(document.createElement("link"), { rel: "stylesheet", href: "/static/board.css" });
    link.onload = () => script("/static/board-math.js").then(() => script("/static/math-board.js")).then(done, done);
    link.onerror = () => done();
    document.head.append(link);
  });
}

const q = selector => layer?.querySelector(selector);
const stop = () => { clearTimeout(timer); timer = null; };

export const isOpen = () => !!layer;

/** Open (or switch to) a skill's sheet. */
export async function open(id) {
  stop();
  const [data, , ai] = await Promise.all([api(`/api/skills/${encodeURIComponent(id)}`), loadBoard(), aiSheet.status()]);
  skill = data;
  aiOn = !!ai.on;                                                     // photo help only for a class with the AI on (AI-10)
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "mx-layer";
    document.body.append(layer);
    layer.addEventListener("click", onClick);
  }
  layer.innerHTML = `<div class="mx-scrim" data-close></div><div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="ex-title"></div>`;
  render();
  q(".mx-x")?.focus({ preventScroll: true });
}

/** Close the sheet: stop timers, bring the board back from full screen, and remove everything. */
export function close() {
  if (!layer) return;
  aiSheet.close();
  stop();
  clearComet();
  window.MathlyBoard?.closeFull?.();
  layer.remove();
  layer = skill = null;
}

const heading = () => `<div class="mx-shtop"><div><span class="ex-chip">${fmt(skill.lesson.name)}</span>
    <h3 id="ex-title">${fmt(skill.name)}${skill.state === "mastered" ? ' <span class="ex-done" title="נשלטה">✓ נשלטה</span>' : ""}</h3></div>
  <div class="mx-shacts">${window.MathlyBoard?.button() || ""}
    ${aiOn ? `<button type="button" class="ex-help ex-ai" data-ai aria-label="עזרה מתמונה: צלמו תרגיל ושלחו למורה" title="עזרה מתמונה">📷</button>` : ""}
    <button type="button" class="ex-help" data-help aria-label="עזרה: ההסבר והדוגמה הפתורה" title="עזרה" aria-expanded="false">?</button>
    <button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>`;

/** Where the student is in the round: "question n of N" and a dot per question (filled for right, marked ✗ for wrong, empty when not answered). */
const dots = round => Array.from({ length: round.total }, (_, i) => {
  const result = round.results[i];
  return `<i class="${result === true ? "ok" : result === false ? "bad" : ""}">${result === false ? "✗" : ""}</i>`;
}).join("");
const countText = round => round.done ? "הסבב הסתיים" : `שאלה ${Math.min(round.answered + 1, round.total)} מתוך ${round.total}`;
const dotsLabel = round => `נענו ${round.answered} מתוך ${round.total}, ${round.results.filter(Boolean).length} נכונות`;
const progress = () => {
  const round = skill.round;
  return round.total ? `<div class="ex-progress"><span id="ex-count">${countText(round)}</span>
    <span class="ex-dots" id="ex-dots" role="img" aria-label="${dotsLabel(round)}">${dots(round)}</span></div>` : "";
};

/** The round's result: how it went and the mistakes, never the right answers. */
function roundResult() {
  const { result } = skill.round;
  return `<section class="ex-round" id="ex-round"><h4>סיכום הסבב</h4>
    <p class="ex-score" id="ex-score"><b>${result.right}</b> מתוך ${result.total}</p>
    ${skill.state === "mastered" ? `<p id="ex-mastered-now">🎉 המיומנות נשלטה!</p>` : ""}
    ${result.missed.length ? `<h4>מה כדאי לחזק</h4><ol class="ex-missed" id="ex-missed">${result.missed.map(m => `<li><p class="ex-text" dir="auto">${fmt(m.question)}</p>
      ${m.mistake ? `<p><b>${esc(m.mistake.name)}</b>${m.mistake.tip ? `<br>${fmt(m.mistake.tip)}` : ""}</p>` : ""}
      ${m.back ? `<p><a href="#/skill/${esc(m.back.id)}">כדאי לחזור אל: ${fmt(m.back.name)}</a></p>` : ""}</li>`).join("")}</ol>`
      : `<p id="ex-perfect">כל התשובות נכונות. כל הכבוד!</p>`}
    <p class="ex-actions"><button type="button" class="primary" id="ex-newround">סבב חדש</button> <button type="button" data-close>חזרה למסלול</button></p></section>`;
}

const helpBox = () => {
  const ex = skill.help.solved_example;
  return `<div class="ex-helpbox" id="ex-helpbox" hidden><h4>הסבר</h4><p>${fmt(skill.help.explanation)}</p>
    ${ex ? `<h4>דוגמה פתורה</h4><p class="ex-eq">${fmt(ex.question)}</p><ol class="ex-steps">${ex.steps.map(s =>
      `<li>${fmt(s.do)}<br><span class="muted">${fmt(s.why)}</span></li>`).join("")}</ol><p><b>תשובה:</b> ${fmt(ex.answer)}</p>` : ""}
    ${skill.question ? `<p class="muted" id="ex-helpnote">פתחתם עזרה: התשובה לשאלה הזו לא תיספר לשליטה.</p>` : ""}
    ${aiOn ? `<p><button type="button" data-ai id="ex-stuck">עדיין תקועים? צלמו</button></p>` : ""}</div>`;
};

const related = () => {
  const chips = (title, items) => items.length ? `<p class="ex-related"><span class="muted">${title}</span> ${items.map(s =>
    `<a class="ex-chip link" href="#/skill/${esc(s.id)}">${fmt(s.name)}</a>`).join(" ")}</p>` : "";
  return chips("דורשת:", skill.requires) + chips("פותחת:", skill.opens);
};

function questionHtml() {
  const question = skill.question;
  if (!question && skill.round.done) return roundResult();
  if (!question) return `<p class="muted" id="no-practice">אין עדיין שאלות תרגול למיומנות הזו.</p>`;
  return `<div class="mx-q" id="ex-q" data-key="${esc(question.key)}"><p class="ex-text" dir="auto">${fmt(question.question)}</p>${figures(question)}
    <div class="ex-choices" id="ex-choices">${shuffled(question.choices).map(c =>
      `<button type="button" class="ex-choice" data-i="${c.index}" dir="auto">${fmt(c.text)}</button>`).join("")}</div>
    <div class="ex-fb" id="ex-fb" role="status" aria-live="polite"></div></div>`;
}

/** Mount the board for the question on screen: each question keeps its own sketch. */
function mountBoard() {
  const key = skill.question ? `${skill.id}:${skill.question.key}` : `${skill.id}:none`;
  window.MathlyBoard?.mount(layer, key, { question: () => q("#ex-q") });
}

function render(notice = "") {
  q(".mx-sheet").innerHTML = `${heading()}<p class="ex-explain">${fmt(skill.description)}</p>${notice ? `<p class="ex-note" role="status">${esc(notice)}</p>` : ""}
    ${helpBox()}${progress()}${questionHtml()}${related()}`;
  helped = false;
  mountBoard();
}

function showNextQuestion(question) {
  stop();
  skill.question = question;
  q("#ex-q")?.remove();
  q("#no-practice")?.remove();
  const holder = document.createElement("div");
  holder.innerHTML = questionHtml();
  (q("#ex-dots")?.parentElement || q(".ex-explain")).after(holder.firstElementChild);
  q("#ex-helpbox").hidden = true;
  q("[data-help]")?.setAttribute("aria-expanded", "false");
  helped = false;
  mountBoard();
}

function updateProgress() {
  const round = skill.round;
  q("#ex-count").textContent = countText(round);
  const row = q("#ex-dots");
  row.setAttribute("aria-label", dotsLabel(round));
  row.innerHTML = dots(round);
  if (skill.state === "mastered" && !q(".ex-done")) q("#ex-title").insertAdjacentHTML("beforeend", ' <span class="ex-done" title="נשלטה">✓ נשלטה</span>');
}

/** The round is over: show its result in place of the question. */
function showResult() {
  stop();
  skill.question = null;
  render();
}

async function newRound() {
  const button = q("#ex-newround");
  button.disabled = true;
  try {
    await api(`/api/skills/${encodeURIComponent(skill.id)}/round`, { method: "POST" });
    skill = await api(`/api/skills/${encodeURIComponent(skill.id)}`);
    render();
  } catch (error) {
    button.disabled = false;
    button.insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`);
  }
}

async function reloadCurrent() {
  skill = await api(`/api/skills/${encodeURIComponent(skill.id)}`);
  stop();
  render("השאלה התחלפה בחלון אחר. זו השאלה שעל המסך עכשיו.");
}

function countdown(next) {
  let left = COUNTDOWN;
  const label = q("#ex-countdown");
  const tick = () => {
    if (!layer || !label?.isConnected) return;
    if (left === 0) return next();
    label.textContent = `השאלה הבאה בעוד ${left}…`;
    left -= 1;
    timer = setTimeout(tick, 1000);
  };
  tick();
}

async function answer(button) {
  const question = skill.question;
  const buttons = [...layer.querySelectorAll(".ex-choice")];
  buttons.forEach(b => { b.disabled = true; b.classList.toggle("dim", b !== button); });
  button.classList.add("pending");                                                       // the thinking indicator: the server is checking
  button.setAttribute("aria-busy", "true");
  q("#ex-fb").innerHTML = `<p class="ex-thinking" id="ex-thinking">בודקים…</p>`;       // a live region: a screen reader hears it too
  let result;
  try {
    result = await api(`/api/skills/${encodeURIComponent(skill.id)}/answer`, { method: "POST", body: { question_key: question.key, choice: Number(button.dataset.i) } });
  } catch (error) {
    buttons.forEach(b => b.classList.remove("pending", "dim"));
    button.removeAttribute("aria-busy");
    if (error instanceof ApiError && error.status === 409) return reloadCurrent();
    buttons.forEach(b => { b.disabled = false; });
    q("#ex-fb").innerHTML = `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`;
    return;
  }
  buttons.forEach(b => b.classList.remove("pending", "dim"));
  button.removeAttribute("aria-busy");
  sendWorkQuietly(`${skill.id}:${question.key}`, "practice", question.key);              // the board of this answer, for the teacher
  Object.assign(skill, { round: result.round, state: result.state, correct_in_row: result.correct_in_row, today: result.today });
  updateProgress();
  const feedback = q("#ex-fb");
  const next = () => (result.next_question ? showNextQuestion(result.next_question) : showResult());
  if (result.correct) {
    button.classList.add("right");
    button.insertAdjacentHTML("beforeend", '<span class="burst" aria-hidden="true">✦ ✦ ✦</span>');
    navigator.vibrate?.(25);
    feedback.innerHTML = `<div class="ex-ok"><b>נכון ✓</b> <span>${result.correct_in_row} ${result.correct_in_row === 1 ? "תשובה נכונה" : "תשובות נכונות"} ברצף (מתוך 3)</span>
      ${result.mastered_now ? `<p id="ex-mastered">🎉 המיומנות נשלטה!</p>` : ""}
      ${result.next_question ? `<div class="ex-actions"><span id="ex-countdown"></span><button type="button" id="ex-skip">לשאלה הבאה</button><button type="button" id="ex-pause">עצירה</button></div>`
        : `<p>סיימתם את הסבב.</p><div class="ex-actions"><button type="button" class="primary" id="ex-results">לתוצאות הסבב</button></div>`}</div>`;
    q("#ex-results")?.addEventListener("click", next);
    if (result.comet) crossComet({ feedback });
    if (result.next_question) {
      q("#ex-skip").addEventListener("click", next);
      q("#ex-pause").addEventListener("click", () => { stop(); q("#ex-countdown").textContent = ""; q("#ex-pause").remove(); });
      countdown(next);
    }
  } else {
    button.classList.add("wrong");               // only the chosen one is marked, with a symbol and a word (not colour alone); the right choice is never shown
    button.insertAdjacentHTML("beforeend", '<span class="verdict"><span aria-hidden="true">✗</span> לא נכון</span>');
    const m = result.mistake;
    feedback.innerHTML = `<div class="ex-bad"><b>${esc(m?.name || "תשובה לא נכונה")}</b>${m?.tip ? `<p>${fmt(m.tip)}</p>` : ""}
      ${m?.back && m.back_name ? `<p><a href="#/skill/${esc(m.back)}">כדאי לחזור אל: ${fmt(m.back_name)}</a></p>` : ""}
      <div class="ex-actions"><button type="button" id="ex-other">${result.next_question ? "לשאלה הבאה" : "לתוצאות הסבב"}</button></div></div>`;   // a wrong question does not come back in the round
    q("#ex-other").addEventListener("click", next);
  }
}

async function openHelp() {
  const box = q("#ex-helpbox"), button = q("[data-help]");
  const opening = box.hidden;
  box.hidden = !opening;
  button.setAttribute("aria-expanded", String(opening));
  if (opening && skill.question && !helped && !q("#ex-fb").children.length) {      // help before answering: this answer will not count
    helped = true;
    try { await api(`/api/skills/${encodeURIComponent(skill.id)}/help`, { method: "POST" }); } catch { helped = false; }
  }
}

function onClick(event) {
  const target = event.target;
  if (target.closest("[data-close]")) { location.hash = pathHref(); return; }
  if (target.closest("[data-board-toggle]")) { window.MathlyBoard?.toggle(); return; }
  if (target.closest("[data-ai]")) { aiSheet.open({ skillId: skill.id }); return; }
  if (target.closest("[data-help]")) { openHelp(); return; }
  if (target.closest("#ex-newround")) { newRound(); return; }
  const choice = target.closest(".ex-choice");
  if (choice && !choice.disabled) answer(choice);
}

window.addEventListener("mathly:leave", close);     // another role's screen opened, or the person signed out

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && layer && !document.querySelector(".mx-board.full")) location.hash = pathHref();
});
