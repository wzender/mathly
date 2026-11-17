// A lesson round (סבב שיעור), opened from the home's map: a short round of the lesson's skills, one question at a time, with instant feedback
// like the exercise screen. A wrong answer names the mistake and never marks the right choice. The last answer shows the lesson's stars.
// The same sheet plays a mistakes round (חזרה על הטעויות): the questions a handed-in quiz, exercise test or simulation got wrong, with no stars.
import { api, ApiError } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { loadBoard } from "./exercise.js";
import { forSubject, homeHref, pathHref, shuffled } from "./ui.js";
import { countUp, forecastMeter } from "./home.js";
import { sendWorkQuietly } from "./boardwork.js";

const COUNTDOWN = 2;   // seconds before the next question after a right answer
let layer = null, round = null, timer = null, streak = 0;

const q = selector => layer?.querySelector(selector);
const stop = () => { clearTimeout(timer); timer = null; };
const starsText = n => "★".repeat(n) + "☆".repeat(3 - n);
const CHEERS = ["נכון!", "יופי!", "מצוין!", "בדיוק!", "אלופים!"];

export const isOpen = () => !!layer;

/** Start the lesson's round (or resume the open one). Returns the round, so the router knows its subject. */
export const start = lesson => api(`/api/lessons/${encodeURIComponent(lesson)}/round/start`, { method: "POST" });

/** Start (or resume) the mistakes round of a handed-in attempt. */
export const startRetry = attemptId => api(`/api/attempts/${encodeURIComponent(attemptId)}/retry/start`, { method: "POST" });

const isRetry = () => !!round?.source;
/** Where closing leads: the home's map, or for a mistakes round its test's card (a quiz: the path). */
const leaveTo = () => round?.source ? (round.source.test_id ? `#/test/${round.source.test_id}` : pathHref()) : homeHref();

/** Show a round from `start` as a sheet over the home. */
export async function show(data) {
  stop();
  await loadBoard();
  round = data;
  streak = 0;
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "mx-layer round-layer";
    document.body.append(layer);
    layer.addEventListener("click", onClick);
  }
  layer.innerHTML = `<div class="mx-scrim" data-close></div><div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="rd-title"></div>`;
  render();
  q(".mx-x")?.focus({ preventScroll: true });
}

export function close() {
  if (!layer) return;
  stop();
  window.MathlyBoard?.closeFull?.();
  layer.remove();
  layer = round = null;
}

const heading = () => `<div class="mx-shtop"><div><span class="ex-chip">${isRetry() ? "חזרה על הטעויות" : "סבב שיעור"}</span><h3 id="rd-title">${fmt(round.lesson.name)}</h3></div>
  <div class="mx-shacts">${window.MathlyBoard?.button() || ""}<button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>`;

const dots = () => Array.from({ length: round.total }, (_, i) => {
  const r = round.results[i];
  return `<i class="${r === true ? "ok" : r === false ? "bad" : ""}">${r === false ? "✗" : ""}</i>`;
}).join("");
const countText = () => round.state === "done" ? "הסבב הסתיים" : `שאלה ${Math.min(round.results.length + 1, round.total)} מתוך ${round.total}`;
const progress = () => `<div class="ex-progress"><span id="rd-count">${countText()}</span>
  <span class="ex-dots" id="rd-dots" role="img" aria-label="נענו ${round.results.length} מתוך ${round.total}, ${round.results.filter(Boolean).length} נכונות">${dots()}</span></div>`;

function questionHtml() {
  const question = round.question;
  const ctx = question.context;
  const from = ctx ? `<div class="rd-context" id="rd-context"><span class="ex-chip">📝 ${ctx.n ? `שאלה ${ctx.n}${ctx.of ? ` מתוך ${ctx.of}` : ""} ב${fmt(ctx.title)}` : fmt(ctx.title)}</span>
    <p class="muted">${ctx.picked ? `במבחן בחרתם: <span dir="auto">${fmt(ctx.picked)}</span>` : "במבחן לא עניתם על השאלה הזו."} נסו שוב.</p></div>` : "";
  return `<div class="mx-q" id="ex-q" data-key="${esc(question.key)}">${from}<p class="muted rd-skill">${fmt(question.skill_name)}</p>
    <p class="ex-text" dir="auto">${fmt(question.question)}</p>${figures(question)}
    <div class="ex-choices" id="ex-choices">${shuffled(question.choices).map(c =>
      `<button type="button" class="ex-choice" data-i="${c.index}" dir="auto">${fmt(c.text)}</button>`).join("")}</div>
    <div class="ex-fb" id="ex-fb" role="status" aria-live="polite"></div></div>`;
}

/** The round's result: the stars big, the score, what was mastered, what is one good day away, and the mistakes (never the right answers). */
function retryResultHtml() {
  const r = round.result, all = r.right === r.total;
  return `<section class="rd-result" id="rd-result" data-kind="retry">
    <p class="rd-bigstars" aria-hidden="true">${all ? "🎉" : "💪"}</p>
    <h4 class="rd-title">${all ? "כל הטעויות תוקנו!" : "סיימתם לחזור על הטעויות"}</h4>
    <p class="ex-score" id="rd-score"><b>${r.right}</b> מתוך ${r.total} נכונות הפעם</p>
    ${r.mastered.length ? `<p class="rd-mastered" id="rd-mastered">🎉 נשלטו: ${r.mastered.map(s => fmt(s.name)).join(", ")}</p>` : ""}
    ${r.missed.length ? `<h4>עדיין כדאי לחזק</h4><ol class="ex-missed" id="rd-missed">${r.missed.map(m => `<li><p class="muted">${m.n ? `שאלה ${m.n} · ` : ""}${fmt(m.skill_name)}</p><p class="ex-text" dir="auto">${fmt(m.question)}</p>
      ${m.mistake ? `<p><b>${esc(m.mistake.name)}</b>${m.mistake.tip ? `<br>${fmt(m.mistake.tip)}` : ""}</p>` : ""}</li>`).join("")}</ol>` : ""}
    <p class="muted">הציון במבחן לא משתנה. התרגול נספר לשליטה במיומנויות.</p>
    <p class="ex-actions">${all ? "" : `<button type="button" class="primary" id="rd-again">שוב על הטעויות</button> `}<button type="button" data-close>${round.source.test_id ? "חזרה למבחן" : "חזרה למסלול"}</button></p></section>`;
}

function resultHtml() {
  if (isRetry()) return retryResultHtml();
  const r = round.result;
  const names = list => list.map(s => fmt(s.name)).join(", ");
  const title = r.stars === 3 ? "👑 השיעור מושלם!" : r.right === r.total ? "מושלם! כל התשובות נכונות" : r.right * 10 >= r.total * 8 ? "כל הכבוד!" : "סיימתם סבב!";
  return `<section class="rd-result" id="rd-result">
    <p class="rd-bigstars" aria-label="${r.stars} מתוך 3 כוכבים">${[0, 1, 2].map(i => `<span class="${i < r.stars ? "on" : ""}" style="--i:${i}">${i < r.stars ? "★" : "☆"}</span>`).join("")}</p>
    <h4 class="rd-title">${title}</h4>
    <p class="ex-score" id="rd-score"><b>${r.right}</b> מתוך ${r.total}</p>
    ${r.mastered.length ? `<p class="rd-mastered" id="rd-mastered">🎉 נשלטו: ${names(r.mastered)}</p>` : ""}
    ${r.almost.length ? `<p class="rd-almost" id="rd-almost">🔜 עוד סבב טוב ביום אחר ונשלטות: ${names(r.almost)}</p>` : ""}
    ${r.stars < 3 ? `<p class="muted rd-next">${r.stars < 2 ? "8 מתוך 10 נותנים כוכב שני." : "הכוכב השלישי: כל המיומנויות נשלטו. חוזרים מחר לעוד סבב."}</p>` : ""}
    ${r.missed.length ? `<h4>מה כדאי לחזק</h4><ol class="ex-missed" id="rd-missed">${r.missed.map(m => `<li><p class="muted">${fmt(m.skill_name)}</p><p class="ex-text" dir="auto">${fmt(m.question)}</p>
      ${m.mistake ? `<p><b>${esc(m.mistake.name)}</b>${m.mistake.tip ? `<br>${fmt(m.mistake.tip)}` : ""}</p>` : ""}</li>`).join("")}</ol>` : ""}
    <div id="rd-forecast" aria-live="polite"></div>
    <p class="ex-actions"><button type="button" class="primary" id="rd-again">סבב נוסף</button> <button type="button" data-close>חזרה למפה</button></p></section>`;
}

/** After a round: the nearest test's forecast grade, growing from what was seen last (a round moves it, forecast.py). */
async function showForecast(id) {
  try {
    const got = await api(forSubject("/api/forecast"));
    const slot = q("#rd-forecast");
    if (!got.forecast || !slot || round?.id !== id) return;
    slot.innerHTML = forecastMeter(got.forecast, got.test.id, { compact: true });
    countUp(slot);
  } catch { /* the result stands without it */ }
}

function mountBoard() {
  const key = round.question ? `round:${round.id}:${round.question.key}` : `round:${round.id}:done`;
  window.MathlyBoard?.mount(layer, key, { question: () => q("#ex-q") });
}

function render(notice = "") {
  q(".mx-sheet").innerHTML = `${heading()}${notice ? `<p class="ex-note" role="status">${esc(notice)}</p>` : ""}${progress()}
    ${round.state === "done" ? resultHtml() : questionHtml()}`;
  mountBoard();
  if (round.state === "done" && !isRetry()) showForecast(round.id);
}

function updateProgress() {
  q("#rd-count").textContent = countText();
  q("#rd-dots").innerHTML = dots();
}

function countdown(next) {
  let left = COUNTDOWN;
  const label = q("#ex-countdown");
  const tick = () => {
    if (!layer || !label?.isConnected) return;
    if (left === 0) return next();
    label.textContent = `הבאה בעוד ${left}…`;
    left -= 1;
    timer = setTimeout(tick, 1000);
  };
  tick();
}

async function answer(button) {
  const buttons = [...layer.querySelectorAll(".ex-choice")];
  buttons.forEach(b => { b.disabled = true; b.classList.toggle("dim", b !== button); });
  button.classList.add("pending");
  button.setAttribute("aria-busy", "true");
  q("#ex-fb").innerHTML = `<p class="ex-thinking">בודקים…</p>`;
  let result;
  try {
    result = await api(`/api/rounds/${encodeURIComponent(round.id)}/answer`, { method: "POST", body: { key: round.question.key, choice: Number(button.dataset.i) } });
  } catch (error) {
    buttons.forEach(b => b.classList.remove("pending", "dim"));
    button.removeAttribute("aria-busy");
    if (error instanceof ApiError && error.status === 409) {                    // answered in another tab: show where the round is now
      round = await api(`/api/rounds/${encodeURIComponent(round.id)}`);
      return render("הסבב התקדם בחלון אחר. זו השאלה שעל המסך עכשיו.");
    }
    buttons.forEach(b => { b.disabled = false; });
    q("#ex-fb").innerHTML = `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`;
    return;
  }
  buttons.forEach(b => b.classList.remove("pending", "dim"));
  button.removeAttribute("aria-busy");
  sendWorkQuietly(`round:${round.id}:${round.question.key}`, round.id, round.question.key);   // the board of this answer, for the teacher
  const following = result.round;
  round = { ...round, results: following.results, state: following.state };
  updateProgress();
  const next = () => { stop(); round = following; render(); };
  const last = following.state === "done";
  const feedback = q("#ex-fb");
  const mastered = result.mastered_now ? `<p class="rd-mastered">🎉 ${fmt(result.mastered_now.name)}: נשלטה!</p>` : "";
  if (result.correct) {
    streak += 1;
    button.classList.add("right");
    button.insertAdjacentHTML("beforeend", '<span class="burst" aria-hidden="true">✦ ✦ ✦</span>');
    navigator.vibrate?.(25);
    feedback.innerHTML = `<div class="ex-ok"><b>${CHEERS[(streak - 1) % CHEERS.length]} ✓</b>${streak >= 3 ? ` <span>🔥 ${streak} ברצף</span>` : ""}${mastered}
      <div class="ex-actions">${last ? `<button type="button" class="primary" id="rd-next">לתוצאות ✨</button>`
        : `<span id="ex-countdown"></span><button type="button" id="rd-next">לשאלה הבאה</button>`}</div></div>`;
    if (!last) countdown(next);
  } else {
    streak = 0;
    button.classList.add("wrong");
    button.insertAdjacentHTML("beforeend", '<span class="verdict"><span aria-hidden="true">✗</span> לא נכון</span>');
    const m = result.mistake;
    feedback.innerHTML = `<div class="ex-bad"><b>${esc(m?.name || "תשובה לא נכונה")}</b>${m?.tip ? `<p>${fmt(m.tip)}</p>` : ""}
      <div class="ex-actions"><button type="button" id="rd-next">${last ? "לתוצאות" : "לשאלה הבאה"}</button></div></div>`;
  }
  q("#rd-next").addEventListener("click", next);
}

async function again() {
  const button = q("#rd-again");
  button.disabled = true;
  try {
    round = await (isRetry() ? startRetry(round.source.id) : start(round.lesson.id));
    streak = 0;
    render();
  } catch (error) {
    button.disabled = false;
    button.insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`);
  }
}

function onClick(event) {
  const target = event.target;
  if (target.closest("[data-close]")) { location.hash = leaveTo(); return; }
  if (target.closest("[data-board-toggle]")) { window.MathlyBoard?.toggle(); return; }
  if (target.closest("#rd-again")) { again(); return; }
  const choice = target.closest(".ex-choice");
  if (choice && !choice.disabled) answer(choice);
}

window.addEventListener("mathly:leave", close);

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && layer && !document.querySelector(".mx-board.full")) location.hash = leaveTo();
});
