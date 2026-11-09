// The review tab (חזרה): every wrong answer waits here. One question at a time, the oldest first. A right answer removes it; a wrong one keeps it and
// names the mistake and its tip, never the right choice. Practice only: it changes no mastery and no grade (it counts toward the daily goal).
import { api } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { shuffled, tabs } from "./ui.js";

const SOURCE = { practice: "תרגול", quiz: "בוחן", exercise_test: "מבחן תרגול", simulation: "מבחן סימולציה" };
let view = null;

const counter = n => n === 0 ? "אין שאלות שמחכות" : n === 1 ? "שאלה אחת מחכה" : `${n} שאלות מחכות`;

function frame(count, inner) {
  view(`${tabs("review")}<section class="card" id="review" data-count="${count}"><h2>חזרה</h2><p class="muted" id="review-count" role="status">${counter(count)}</p>${inner}</section>`);
}

function questionCard(q) {
  return `<div id="review-q" data-key="${esc(q.key)}"><p><span class="ex-chip">${fmt(q.lesson.name)}</span> <span class="muted">${fmt(q.skill.name)} · מ${SOURCE[q.source] || "תרגול"}</span></p>
    <p class="ex-text" dir="auto">${fmt(q.question)}</p>${figures(q)}
    <div class="ex-choices" id="review-choices">${shuffled(q.choices).map(c => `<button type="button" class="ex-choice" data-i="${c.index}" dir="auto">${fmt(c.text)}</button>`).join("")}</div>
    <div id="review-feedback" role="status"></div></div>`;
}

function draw(data) {
  if (!data.question) {
    frame(data.count, `<p class="muted" id="review-empty">אין מה לחזור עליו. כל תשובה שגויה תופיע כאן, ותצא מהרשימה כשתענו עליה נכון.</p>`);
    return;
  }
  frame(data.count, questionCard(data.question));
  document.getElementById("review-choices").addEventListener("click", event => {
    const button = event.target.closest(".ex-choice");
    if (button && !button.disabled) answer(data, button);
  });
}

async function answer(data, button) {
  const buttons = [...document.querySelectorAll("#review-choices .ex-choice")];
  buttons.forEach(b => { b.disabled = true; });
  let got;
  try { got = await api("/api/review/answer", { method: "POST", body: { key: data.question.key, choice: Number(button.dataset.i) } }); }
  catch (error) { buttons.forEach(b => { b.disabled = false; }); document.getElementById("review-feedback").innerHTML = `<p class="error" role="alert">${esc(error.message)}</p>`; return; }
  document.getElementById("review-count").textContent = counter(got.count);
  document.getElementById("review").dataset.count = got.count;
  button.classList.add(got.correct ? "right" : "wrong");        // the picked choice only: the right one is never marked
  const m = got.mistake;
  const why = got.correct ? `<p class="ex-note" data-result="right"><b>נכון!</b> השאלה יצאה מהרשימה.</p>`
    : `<p class="ex-note" data-result="wrong"><b>לא נכון.</b> השאלה נשארת ברשימה.</p>${m ? `<div class="ex-mistake" id="review-mistake"><b>${fmt(m.name)}</b><p>${fmt(m.tip)}</p>${m.back ? `<p class="muted">כדאי לתרגל: <a href="#/skill/${esc(m.back)}">${fmt(m.back_name || "")}</a></p>` : ""}</div>` : ""}`;
  document.getElementById("review-feedback").innerHTML = `${why}${got.next ? `<p><button type="button" class="primary" id="review-next">הבאה</button></p>` : `<p class="muted">זו הייתה האחרונה.</p>`}`;
  document.getElementById("review-next")?.addEventListener("click", () => draw({ count: got.count, question: got.next }));
}

export async function show(v) {
  view = v;
  draw(await api("/api/review"));
}
