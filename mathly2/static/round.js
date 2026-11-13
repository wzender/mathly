// A lesson round (סבב שיעור), opened from the home's map: a short round of the lesson's skills, one question at a time, with instant feedback
// like the exercise screen. A wrong answer names the mistake and never marks the right choice. The last answer shows the lesson's stars.
import { api, ApiError } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { loadBoard } from "./exercise.js";
import { homeHref, shuffled } from "./ui.js";

const COUNTDOWN = 2;   // seconds before the next question after a right answer
let layer = null, round = null, timer = null, streak = 0;

const q = selector => layer?.querySelector(selector);
const stop = () => { clearTimeout(timer); timer = null; };
const starsText = n => "★".repeat(n) + "☆".repeat(3 - n);
const CHEERS = ["נכון!", "יופי!", "מצוין!", "בדיוק!", "אלופים!"];

export const isOpen = () => !!layer;

/** Start the lesson's round (or resume the open one). Returns the round, so the router knows its subject. */
export const start = lesson => api(`/api/lessons/${encodeURIComponent(lesson)}/round/start`, { method: "POST" });

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

const heading = () => `<div class="mx-shtop"><div><span class="ex-chip">סבב שיעור</span><h3 id="rd-title">${fmt(round.lesson.name)}</h3></div>
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
  return `<div class="mx-q" id="ex-q" data-key="${esc(question.key)}"><p class="muted rd-skill">${fmt(question.skill_name)}</p>
    <p class="ex-text" dir="auto">${fmt(question.question)}</p>${figures(question)}
    <div class="ex-choices" id="ex-choices">${shuffled(question.choices).map(c =>
      `<button type="button" class="ex-choice" data-i="${c.index}" dir="auto">${fmt(c.text)}</button>`).join("")}</div>
    <div class="ex-fb" id="ex-fb" role="status" aria-live="polite"></div></div>`;
}

/** The round's result: the stars big, the score, what was mastered, what is one good day away, and the mistakes (never the right answers). */
function resultHtml() {
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
    <p class="ex-actions"><button type="button" class="primary" id="rd-again">סבב נוסף</button> <button type="button" data-close>חזרה למפה</button></p></section>`;
}

function mountBoard() {
  const key = round.question ? `round:${round.id}:${round.question.key}` : `round:${round.id}:done`;
  window.MathlyBoard?.mount(layer, key, { question: () => q("#ex-q") });
}

function render(notice = "") {
  q(".mx-sheet").innerHTML = `${heading()}${notice ? `<p class="ex-note" role="status">${esc(notice)}</p>` : ""}${progress()}
    ${round.state === "done" ? resultHtml() : questionHtml()}`;
  mountBoard();
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
    round = await start(round.lesson.id);
    streak = 0;
    render();
  } catch (error) {
    button.disabled = false;
    button.insertAdjacentHTML("afterend", `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`);
  }
}

function onClick(event) {
  const target = event.target;
  if (target.closest("[data-close]")) { location.hash = homeHref(); return; }
  if (target.closest("[data-board-toggle]")) { window.MathlyBoard?.toggle(); return; }
  if (target.closest("#rd-again")) { again(); return; }
  const choice = target.closest(".ex-choice");
  if (choice && !choice.disabled) answer(choice);
}

window.addEventListener("mathly:leave", close);

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && layer && !document.querySelector(".mx-board.full")) location.hash = homeHref();
});
