// Small pieces shared by the student screens.
import { esc } from "./math.js";

const STATES = { mastered: ["✓", "נשלטה"], learning: ["◐", "בלמידה"], not_started: ["○", "לא התחלת"] };

/** A skill's state as a symbol and a word, so it never depends on colour alone. */
export const stateTag = state => {
  const [symbol, word] = STATES[state] || STATES.not_started;
  return `<span class="tag st-${esc(state)}"><span aria-hidden="true">${symbol}</span> ${word}</span>`;
};

/** The subject's home and its path: the card on the subjects screen opens the home; the tab bar leads to the rest. */
export const HOME = "#/subject/math";
export const PATH = "#/subject/math/path";

/** The student's tab bar, fixed at the bottom of the screen (the CSS places it): home, path, grades, collection. */
export const tabs = active => `<nav class="tabs" aria-label="תפריט התלמיד">
  <a href="${HOME}" ${active === "home" ? 'aria-current="page"' : ""}>בית</a>
  <a href="${PATH}" ${active === "path" ? 'aria-current="page"' : ""}>מסלול</a>
  <a href="#/submissions" ${active === "submissions" ? 'aria-current="page"' : ""}>הגשות</a>
  <a href="#/grades" ${active === "grades" ? 'aria-current="page"' : ""}>ציונים</a>
  <a href="#/collection" ${active === "collection" ? 'aria-current="page"' : ""}>האוסף</a></nav>`;

export const shortDate = iso => { const [, m, d] = iso.split("-"); return `${Number(d)}.${Number(m)}`; };
export const daysText = n => n === 0 ? "היום" : n === 1 ? "מחר" : `בעוד ${n} ימים`;

/** The way back from a subject's screens to the subjects. */
export const backToSubjects = () => `<p><a class="back" id="to-subjects" href="#/">‹ המקצועות</a></p>`;

export const goalBar = (today, streak) => `<div class="goal" id="goal">
  <div class="grow"><span id="goal-text">יעד יומי: ${today.done} מתוך ${today.goal}${today.reached ? " ✓" : ""}</span>
    <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="${today.goal}" aria-valuenow="${Math.min(today.done, today.goal)}">
      <i style="width:${Math.min(100, Math.round(today.done / today.goal * 100))}%"></i></div></div>
  ${streak === undefined ? "" : `<div id="streak">🔥 רצף: ${streak} ${streak === 1 ? "יום" : "ימים"}</div>`}</div>`;

/** A copy in random order; the items keep their own `index`, so the server still grades by the bank's position. */
export const shuffled = items => {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
};
