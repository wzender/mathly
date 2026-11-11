// The path: a trail of lessons. Each lesson is a hub with its skills as numbered stars in a ring around it; the owl perches on the
// suggested next skill. Every star is a link to its exercise screen (#/skill/<id>) and says its state in a symbol and a word.
import { api, swr } from "./api.js";
import { esc, fmt } from "./math.js";
import { owl, ringSvg, spark } from "./sky.js";
import { backToSubjects, forSubject, goalBar, shortDate, tabs } from "./ui.js";

export const STATES = {
  not_started: { symbol: "○", word: "לא התחלת" },
  learning: { symbol: "◐", word: "בלמידה" },
  mastered: { symbol: "✓", word: "נשלטה" },
};
const NEXT = "ממשיכים כאן";
const FADING = "דועך";
const plain = text => String(text ?? "").replace(/\$/g, "");

function star(skill, i, n, isNext) {
  const t = (-90 + 360 * i / n) * Math.PI / 180, base = STATES[skill.state] || STATES.not_started;
  const symbol = skill.faded ? `${base.symbol} ◌` : base.symbol, word = skill.faded ? `${base.word}, ${FADING}` : base.word;
  return `<a class="star st-${esc(skill.state)}${skill.faded ? " faded" : ""}${isNext ? " next" : ""}" href="#/skill/${esc(skill.id)}" data-skill="${esc(skill.id)}"
      style="--dx:${Math.cos(t).toFixed(3)};--dy:${Math.sin(t).toFixed(3)}"
      aria-label="${i + 1}. ${esc(plain(skill.name))}: ${word}${isNext ? ", " + NEXT : ""}">
    <span class="node">${spark()}<span class="num" aria-hidden="true">${i + 1}</span>${isNext ? `<span class="perch">${owl(30)}</span>` : ""}</span>
    <span class="lbl">${fmt(skill.short)}<em><span aria-hidden="true">${symbol}</span> ${word}${isNext ? " · " + NEXT : ""}</em></span></a>`;
}

/** The lesson's quiz, a node on the trail after its ring: always open, its state in words. */
function quizNode(l) {
  const { best, open } = l.quiz || {};
  const state = [best !== null && best !== undefined ? `✓ הציון: ${best}` : "○ עוד לא נעשה", open ? "◐ בוחן פתוח" : ""].filter(Boolean).join(" · ");
  return `<a class="quiz-node${best !== null && best !== undefined ? " graded" : ""}${open ? " open" : ""}" href="#/quiz/${esc(l.id)}" data-quiz="${esc(l.id)}"
      aria-label="בוחן ${esc(plain(l.name))}: ${state}"><span class="qz-icon" aria-hidden="true">${spark()}</span><span><b>בוחן</b><em>${state}</em></span></a>`;
}

/** "הושלם", or, for a lesson whose date has passed without it being completed, the marker with the date in words. */
function lessonStatus(l) {
  if (l.completed) return `<p class="lesson-status done" data-status="completed"><span aria-hidden="true">✓</span> הושלם${l.passed ? " (עברת את הבוחן)" : ""}</p>`;
  if (l.behind) return `<p class="lesson-status late" data-status="behind"><span aria-hidden="true">⚠</span> היה אמור להסתיים ב־${shortDate(l.due_date)}</p>`;
  return "";
}

const behindNote = n => n ? `<p class="behind-note" id="behind-note" role="status"><span aria-hidden="true">⚠</span> ${n === 1 ? "שיעור אחד בפיגור" : `${n} שיעורים בפיגור`} לפי התכנית</p>` : "";

function lesson(l, next) {
  const n = l.skills.length;
  return `<section class="orbit${l.completed ? " completed" : ""}${l.behind ? " behind" : ""}" id="lesson-${esc(l.id)}" aria-label="${esc(plain(l.name))}">
    <div class="stage">${ringSvg(l.skills.map(s => s.state))}
      <div class="hub"><h3>${fmt(l.name)}</h3><span class="count">${l.mastered} מתוך ${n} נשלטו${l.completed ? " ✓" : ""}</span></div>
      ${l.skills.map((s, i) => star(s, i, n, s.id === next)).join("")}</div>${lessonStatus(l)}</section>${quizNode(l)}`;
}

export function pathHtml(path) {
  return `${tabs("path")}${backToSubjects()}
    <section class="card path-top" id="path"><h2>המסלול שלי</h2>
    <p class="muted">כל השיעורים פתוחים, בכל סדר. הינשוף מציע איפה להמשיך, אבל אפשר ללחוץ על כל כוכב.</p>${goalBar(path.today, path.streak)}${behindNote(path.behind)}</section>
    <div class="trail">
      <div class="mark start">${owl(44)}<b>התחלה</b></div>
      ${path.lessons.map(l => lesson(l, path.next)).join("")}
      <div class="mark end"><span aria-hidden="true" style="font-size:26px">✦</span><b>סוף המסלול</b></div></div>`;
}

/** Draw the path. `scroll`: bring the next skill to the middle of the screen (when the path opens); a refresh keeps the place. */
export const show = (view, { scroll = true } = {}) => {
  let first = true;                                  // a refresh of the same screen keeps the place
  return swr(forSubject("/api/path"), path => { const result = drawPath(view, path, scroll && first); first = false; return result; });
};

function drawPath(view, path, scroll) {
  const place = window.scrollY;
  view(pathHtml(path));
  if (scroll) document.querySelector(".star.next")?.scrollIntoView({ block: "center" });
  else window.scrollTo(0, place);
  return path;
}

/** Math's card keeps the course's full name; other subjects show their own name. */
const cardName = s => s.id === "math" ? "מתמטיקה כיתה ט - מצוינות" : s.name;

/** The first screen: a card per subject of the student's classes, math first; each bar counts that subject's mastered skills. */
export async function showSubjects(view) {
  const subjects = await api("/api/my-subjects");
  view(`<section class="subjects" aria-label="מקצועות">
    <h2>מה נתרגל היום?</h2>
    ${subjects.map(s => `<a class="subject-card" href="#/subject/${encodeURIComponent(s.id)}" data-subject="${esc(s.id)}"><span class="subject-icon" aria-hidden="true">${esc(s.icon)}</span>
      <span class="grow"><b>${esc(cardName(s))}</b>
        <span class="bar" role="progressbar" aria-label="מיומנויות שהושלמו" aria-valuemin="0" aria-valuemax="${s.total}" aria-valuenow="${s.mastered}"><i style="width:${s.total ? Math.round(100 * s.mastered / s.total) : 0}%"></i></span>
        <small>${s.mastered} מתוך ${s.total} מיומנויות</small></span><i aria-hidden="true">‹</i></a>`).join("")}</section>`);
  return subjects;
}
