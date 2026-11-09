// The review tab (חזרה): every wrong answer waits here as a card, grouped by skill. A card is answered in place: a right answer marks it done and removes
// it; a wrong one keeps it and names the mistake and its tip, never the right choice, and offers "נסו שוב". Practice only: no mastery and no grade change.
import { api } from "./api.js";
import { figures } from "./figures.js";
import { esc, fmt } from "./math.js";
import { shuffled, tabs } from "./ui.js";

const SOURCE = { practice: "תרגול", quiz: "בוחן", exercise_test: "מבחן תרגול", simulation: "מבחן סימולציה" };
const counter = n => n === 0 ? "אין שאלות שמחכות" : n === 1 ? "שאלה אחת מחכה" : `${n} שאלות מחכות`;
const cardsWord = n => n === 1 ? "כרטיס אחד" : `${n} כרטיסים`;

const card = c => `<article class="review-card" data-key="${esc(c.key)}"><p class="muted">מ${SOURCE[c.source] || "תרגול"}</p>
  <p class="ex-text" dir="auto">${fmt(c.question)}</p>${figures(c)}
  <div class="ex-choices">${shuffled(c.choices).map(x => `<button type="button" class="ex-choice" data-i="${x.index}" dir="auto">${fmt(x.text)}</button>`).join("")}</div>
  <div class="review-feedback" role="status"></div></article>`;

const group = g => `<section class="review-group" data-skill="${esc(g.skill.id)}"><h3>${fmt(g.skill.name)} <span class="tab-count review-skill-count">${cardsWord(g.cards.length)}</span></h3>
  <p class="muted review-lesson">${fmt(g.lesson.name)}</p>${g.cards.map(card).join("")}</section>`;

function draw(view, data) {
  view(`${tabs("review")}<section class="card" id="review" data-count="${data.count}"><h2>חזרה</h2><p class="muted" id="review-count" role="status">${counter(data.count)}</p>
    ${data.groups.length ? data.groups.map(group).join("") : `<p class="muted" id="review-empty">אין מה לחזור עליו. כל תשובה שגויה תופיע כאן, ותצא מהרשימה כשתענו עליה נכון.</p>`}</section>`);
  document.getElementById("review").addEventListener("click", event => {
    const choice = event.target.closest(".ex-choice");
    if (choice && !choice.disabled) answer(choice.closest(".review-card"), choice);
    const again = event.target.closest("[data-again]");
    if (again) retry(again.closest(".review-card"));
  });
}

function retry(cardEl) {
  cardEl.querySelectorAll(".ex-choice").forEach(b => { b.disabled = false; b.classList.remove("wrong"); });
  cardEl.querySelector(".review-feedback").innerHTML = "";
}

async function answer(cardEl, button) {
  const buttons = [...cardEl.querySelectorAll(".ex-choice")];
  const feedback = cardEl.querySelector(".review-feedback");
  buttons.forEach(b => { b.disabled = true; });
  let got;
  try { got = await api("/api/review/answer", { method: "POST", body: { key: cardEl.dataset.key, choice: Number(button.dataset.i) } }); }
  catch (error) { buttons.forEach(b => { b.disabled = false; }); feedback.innerHTML = `<p class="error" role="alert">${esc(error.message)}</p>`; return; }
  const page = document.getElementById("review"), groupEl = cardEl.closest(".review-group");
  page.dataset.count = got.count;
  document.getElementById("review-count").textContent = counter(got.count);
  button.classList.add(got.correct ? "right" : "wrong");          // the picked choice only: the right one is never marked
  if (got.correct) {
    cardEl.classList.add("done");
    feedback.innerHTML = `<p class="ex-note" data-result="right"><b>נכון!</b> השאלה יצאה מהרשימה.</p>`;
    groupEl.querySelector(".review-skill-count").textContent = cardsWord(got.skill_count);
    if (got.skill_count === 0) groupEl.querySelectorAll("h3, .review-lesson").forEach(el => { el.hidden = true; });      // nothing waits on this skill: its heading goes (the done cards stay until the page is left)
    if (got.count === 0) page.insertAdjacentHTML("beforeend", `<p class="muted" id="review-empty">אין מה לחזור עליו. כל הכבוד!</p>`);
    return;
  }
  const m = got.mistake;
  feedback.innerHTML = `<p class="ex-note" data-result="wrong"><b>לא נכון.</b> השאלה נשארת ברשימה.</p>${m ? `<div class="ex-mistake review-mistake"><b>${fmt(m.name)}</b><p>${fmt(m.tip)}</p>${m.back ? `<p class="muted">כדאי לתרגל: <a href="#/skill/${esc(m.back)}">${fmt(m.back_name || "")}</a></p>` : ""}</div>` : ""}
    <p><button type="button" data-again>נסו שוב</button></p>`;
}

export async function show(view) {
  draw(view, await api("/api/review"));
}
