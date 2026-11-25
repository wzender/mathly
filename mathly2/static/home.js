// The student's home for a subject: one screen, like a game's level select. The stars collected and a big play button for the next lesson,
// every lesson as a small tile with its stars (a round finished, 8 of 10, every skill mastered), the nearest test in one block (the days
// left, the readiness number and the two buttons that raise it: a practice test and a simulation), and small buttons for the new
// assignments and photo help.
import { swr } from "./api.js";
import * as aiSheet from "./ai_sheet.js";
import { esc, fmt } from "./math.js";
import { backToSubjects, daysText, forSubject, shortDate, tabs } from "./ui.js";

/* ---------- the nearest test: the readiness number, and the two ways to raise it ---------- */

const SEEN = "mathly2.readiness.";
/** The number the student saw last time for this test (to count up from it), and remember the new one. */
function lastSeen(test) {
  let before = null;
  try { before = Number(localStorage.getItem(SEEN + test.id)); localStorage.setItem(SEEN + test.id, String(test.readiness.number)); } catch { /* private window */ }
  return Number.isFinite(before) && before !== null && before < test.readiness.number ? before : null;
}

/** The readiness number as a level meter: the number (counting up when it grew since the last visit), its level, the bar, and the
 *  points to the next level. */
export function readinessMeter(test) {
  const r = test.readiness, from = lastSeen(test);
  return `<div class="readiness" data-readiness data-from="${from ?? ""}" data-to="${r.number}">
    <p class="rd-top"><b class="rd-num" aria-hidden="true">${from ?? r.number}</b><span><span class="rd-label">מוכנות למבחן · <b>${esc(r.label)}</b></span>
      ${from !== null ? `<span class="rd-up" aria-hidden="true">+${r.number - from}</span>` : ""}
      <br><span class="muted rd-next">${r.next ? `עוד ${r.next.left} לרמה "${esc(r.next.name)}"` : "הגעתם לרמה הגבוהה ביותר! 🏆"}</span></span></p>
    <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}">
      <i style="width:${from ?? r.number}%"></i>${r.next ? `<s style="inset-inline-start:${r.next.at}%" aria-hidden="true"></s>` : ""}</div></div>`;
}

/* ---------- the forecast grade as a game (forecast.py): "placement" until enough answers, then a league with the next one to reach ---------- */

const FORECAST_SEEN = "mathly2.forecast.";
/** What this device showed last for the test: {grade, league (-1 while placing), done}, or null. An old plain number still reads. */
function seenOf(testId) {
  try {
    const kept = localStorage.getItem(FORECAST_SEEN + testId);
    if (kept === null) return null;
    const value = JSON.parse(kept);
    return typeof value === "number" ? { grade: value, league: null, done: null } : value;
  } catch { return null; }
}
function remember(testId, state) { try { localStorage.setItem(FORECAST_SEEN + testId, JSON.stringify(state)); } catch { /* private window */ } }

/** What to show now, and remember it: the league held through a small dip (forecast.py KEEP), whether it went up or was just revealed,
 *  and where the count-up starts (only up: a drop is shown as it is). */
function forecastState(f, testId) {
  const before = seenOf(testId);
  if (f.placement) {
    remember(testId, { grade: f.grade, league: -1, done: f.placement.done });
    const from = before?.league === -1 && before.done < f.placement.done ? before.done : null;
    return { placing: true, from };
  }
  let league = f.league;
  if (before?.league > league && f.grade >= f.leagues[before.league].at - f.keep) league = before.league;
  remember(testId, { grade: f.grade, league, done: f.answers });
  const shown = before && before.league !== null && before.league >= 0;
  return { placing: false, league, revealed: before?.league === -1, up: shown && league > before.league,
           from: shown && before.grade < f.grade ? before.grade : null };
}

/** The forecast as the student sees it. `link`/`days`: the home strip's top row is a link to the test's page with the days left; `detail`:
 *  the test's page also shows the forecast grade's range. */
export function forecastMeter(f, testId, { id = "", compact = false, link = "", days = "", detail = false } = {}) {
  const st = forecastState(f, testId);
  const top = (inner) => link ? `<a class="strip-main" href="${link}">${inner}<span class="strip-more" aria-hidden="true">‹</span></a>` : `<div class="fc-top">${inner}</div>`;
  const when = days ? `📅 <span class="days">מבחן ${days}</span>` : "";
  if (st.placing) {
    const p = f.placement, left = p.need - p.done;
    return `<div class="readiness forecast placing${compact ? " compact" : ""}"${id ? ` id="${id}"` : ""} data-from="${st.from ?? ""}" data-to="${p.done}" data-min="0" data-max="${p.need}">
      ${top(`<span class="fc-icon" aria-hidden="true">🔍</span><span class="grow"><span class="rd-label">מגלים את הליגה שלך</span>
        <small class="muted">${when}${when ? " · " : ""}עוד ${left} ${left === 1 ? "תשובה" : "תשובות"}</small></span>
        <span class="fc-count"><b class="rd-num">${st.from ?? p.done}</b>/${p.need}</span>`)}
      <div class="bar rd-bar fc-bar" role="progressbar" aria-label="מגלים את הליגה: ${p.done} מתוך ${p.need} תשובות" aria-valuemin="0" aria-valuemax="${p.need}" aria-valuenow="${p.done}"><i style="width:${100 * (st.from ?? p.done) / p.need}%"></i></div></div>`;
  }
  const L = f.leagues, now = L[st.league], next = L[st.league + 1];
  const min = now.at, max = next ? next.at : 100, pct = v => Math.max(0, Math.min(100, 100 * (v - min) / (max - min)));
  const cheer = st.revealed ? `🎉 נחשפה הליגה שלך: ${now.icon} ${now.name}!` : st.up ? `🎉 עליתם לליגת ${now.icon} ${now.name}!` : "";
  const toNext = next ? (f.grade >= next.at ? `כמעט בליגת ${next.icon} ${next.name}` : `עוד ${next.at - f.grade} לליגת ${next.icon} ${next.name}`) : "🏆 הליגה הגבוהה ביותר";
  return `<div class="readiness forecast league-${st.league}${compact ? " compact" : ""}"${id ? ` id="${id}"` : ""} data-league="${st.league}"
      data-from="${st.from ?? ""}" data-to="${f.grade}" data-min="${min}" data-max="${max}">
    ${cheer ? `<p class="fc-cheer" role="status">${cheer}</p>` : ""}
    ${top(`<span class="fc-icon" aria-hidden="true">${now.icon}</span><span class="grow"><span class="rd-label">ליגת ${now.name}${st.from !== null ? ` <span class="rd-up" aria-hidden="true">+${f.grade - st.from}</span>` : ""}</span>
      <small class="muted">${when}${when ? " · " : ""}${toNext}</small></span>`)}
    <div class="bar rd-bar fc-bar" role="progressbar" aria-label="ליגת ${now.name}${next ? `, ${toNext}` : ""}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(pct(f.grade))}"><i style="width:${pct(st.from ?? f.grade)}%"></i></div>
    ${detail ? `<p class="muted fc-detail">הליגה מתעדכנת אחרי כל סבב, תרגול ומבחן בחומר של המבחן: כל תשובה נכונה מקרבת לליגה הבאה.</p>` : ""}</div>`;
}

/** Count the number up from the last visit's and grow the bar with it. */
function countUp(root = document) {
  root.querySelectorAll(".readiness[data-from]:not([data-from=''])").forEach(meter => {
    const from = Number(meter.dataset.from), to = Number(meter.dataset.to), num = meter.querySelector(".rd-num"), bar = meter.querySelector(".rd-bar i");
    const min = Number(meter.dataset.min || 0), max = Number(meter.dataset.max || 100);                // a league's bar spans its own points
    const width = v => `${Math.max(0, Math.min(100, 100 * (v - min) / (max - min)))}%`;
    meter.dataset.from = "";
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { if (num) num.textContent = to; bar.style.width = width(to); return; }
    const start = performance.now(), time = 900;
    const frame = now => {
      const k = Math.min(1, (now - start) / time), v = Math.round(from + (to - from) * (1 - (1 - k) ** 3));
      if (num) num.textContent = v;
      bar.style.width = width(v);
      if (k < 1) requestAnimationFrame(frame); else meter.classList.add("grew");
    };
    requestAnimationFrame(frame);
  });
}
export { countUp };

/** The nearest test in one compact block (the home is one screen): the readiness number with its level and the days left (a link to the
 *  test's page, with all its tests and grades), the bar, and the two buttons that raise it, each with the most it can add now. */
function testStrip(test) {
  if (test.forecast) return forecastStrip(test);
  const r = test.readiness, add = r.can_add, sim = test.simulation.open, from = lastSeen(test);
  return `<section class="strip test-strip" id="nearest-test" data-test="${test.id}">
    <div class="readiness" data-readiness data-from="${from ?? ""}" data-to="${r.number}">
      <a class="strip-main" href="#/test/${test.id}"><b class="rd-num" aria-hidden="true">${from ?? r.number}</b>
        <span class="grow"><span class="rd-label">מוכנות למבחן · <b>${esc(r.label)}</b>${from !== null ? ` <span class="rd-up" aria-hidden="true">+${r.number - from}</span>` : ""}</span>
          <small class="muted">📅 <span class="days">מבחן ${daysText(test.days_left)}</span>${r.next ? ` · עוד ${r.next.left} לרמה "${esc(r.next.name)}"` : " · 🏆"}</small></span>
        <span class="strip-more" aria-hidden="true">‹</span></a>
      <div class="bar rd-bar" role="progressbar" aria-label="מוכנות למבחן: ${r.number} מתוך 100, ${esc(r.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${r.number}"><i style="width:${from ?? r.number}%"></i></div></div>
    <div class="test-btns"><a class="test-btn" id="home-practice" href="#/test/${test.id}/practice">📝 מבחן תרגול${add.practice ? ` <small>+${add.practice}</small>` : ""}</a>
      <a class="test-btn sim" id="home-sim" href="#/sim/${test.id}${sim ? `/${esc(sim)}` : ""}">⏱ ${sim ? "להמשיך סימולציה" : "מבחן סימולציה"}${add.simulation && !sim ? ` <small>+${add.simulation}</small>` : ""}</a></div></section>`;
}

/* ---------- the nearest test: the forecast grade and the days left, as big as the screen allows ---------- */

/** How close the test is, for the pressure: the words, the icon and how many rounds today's mission asks for. */
export function phaseOf(days) {
  if (days <= 0) return { id: "today", icon: "💪", text: "המבחן היום! בהצלחה", rounds: 0 };
  if (days <= 3) return { id: "sprint", icon: "🚀", text: "ספרינט אחרון!", rounds: 3 };
  if (days <= 7) return { id: "hot", icon: "🔥", text: "שבוע אחרון", rounds: 2 };
  if (days <= 14) return { id: "warm", icon: "⏳", text: "שבועיים אחרונים", rounds: 1 };
  return { id: "calm", icon: "📅", text: "יש זמן להתכונן", rounds: 1 };
}

const GRADE_SEEN = "mathly2.grade.";
/** The grade this device showed last for the test; only a rise is shown ("▲ +3"): a dip is not announced. */
function gradeRise(testId, grade) {
  let before = null;
  try { before = JSON.parse(localStorage.getItem(GRADE_SEEN + testId) || "null"); localStorage.setItem(GRADE_SEEN + testId, JSON.stringify(grade)); } catch { /* private window */ }
  return typeof before === "number" && grade > before ? grade - before : 0;
}

/** The nearest test as the home's hero: the days left and the held grade big (forecast.held: it starts 25 above the forecast, the
 *  daily mission keeps it, a day without it loses a quarter of the lead, and it meets the forecast by the test). Beside it, what today
 *  decides: "✓ נשמר" once today's mission is done, else the grade tomorrow without it. The closer the test, the stronger the colours
 *  and the bigger the mission. The practice test and the simulation under it. */
function forecastStrip(test) {
  const f = test.forecast, sim = test.simulation.open, phase = phaseOf(test.days_left);
  const h = f.held || { grade: f.grade, need: 0, done: 0, safe: true, tomorrow: f.grade };
  const rise = gradeRise(test.id, h.grade), loss = h.grade - h.tomorrow;
  const rounds = phase.rounds === 1 ? "סבב אחד" : `${phase.rounds} סבבים`;
  const mission = phase.id === "today" ? "נשמו עמוק, אתם מוכנים יותר ממה שנדמה."
    : h.safe ? "המשימה של היום הושלמה 💪" : `היום: ${rounds} · ${Math.min(h.done, h.need)}/${h.need} תשובות`;
  const side = phase.id === "today" ? ""
    : h.safe ? `<span class="fc-way fc-safe" id="home-way"><small>היום</small><b>✓</b><small>הציון נשמר</small></span>`
    : loss > 0 ? `<span class="fc-way fc-risk" id="home-way"><small>בלי המשימה</small><b>${h.tomorrow}</b><small>מחר, ${loss} פחות</small></span>` : "";
  const days = test.days_left <= 0 ? "היום" : test.days_left === 1 ? "מחר" : test.days_left;
  const label = `המבחן ${daysText(test.days_left)}. ציון משוער ${h.grade}. ${h.safe ? "הציון נשמר היום." : loss > 0 ? `בלי המשימה של היום הוא יירד מחר ל־${h.tomorrow}.` : ""}`;
  return `<section class="strip test-strip fc-hero-strip phase-${phase.id}${!h.safe && loss > 0 ? " at-risk" : ""}" id="nearest-test" data-test="${test.id}" data-phase="${phase.id}">
    <a class="strip-main fc-hero" href="#/test/${test.id}" aria-label="${esc(label)}">
      <span class="fc-days" id="home-days"><b>${days}</b><small>${typeof days === "number" ? "ימים למבחן" : "המבחן"}</small></span>
      <span class="fc-grade" id="home-forecast" data-grade="${h.grade}"><small>ציון משוער</small><b class="fc-num">${h.grade}</b>${rise ? `<small class="fc-rise">▲ +${rise}</small>` : ""}</span>
      ${side}</a>
    <p class="fc-mission" id="home-mission"><span aria-hidden="true">${phase.icon}</span> <b>${phase.text}</b> · ${mission}</p>
    ${phase.id === "today" ? "" : `<button type="button" class="fc-improve" id="home-improve">📈 איך מעלים את הציון?${(f.boost?.gains || []).length ? ` <span class="imp-chip">עד <bdi dir="ltr">+${f.boost.gains.reduce((a, b) => a + b, 0)}</bdi></span>` : ""}</button>`}
    <div class="test-btns"><a class="test-btn" id="home-practice" href="#/test/${test.id}/practice">📝 מבחן תרגול</a>
      <a class="test-btn sim" id="home-sim" href="#/sim/${test.id}${sim ? `/${esc(sim)}` : ""}">⏱ ${sim ? "להמשיך סימולציה" : "מבחן סימולציה"}</a></div></section>`;
}

/** An assignment's state in a symbol and a word (never colour alone). */
export function assignmentState(a) {
  if (a.kind === "exercise_test") return a.state === "done" ? { symbol: "✓", word: `ציון ${a.grade}` } : a.overdue ? { symbol: "⚠", word: "באיחור" } : { symbol: "○", word: "עוד לא נעשה" };
  switch (a.state) {
    case "handed_in": return { symbol: "◐", word: a.late ? "הוגש באיחור" : "הוגש" };
    case "graded": return { symbol: "✓", word: `ציון ${a.grade}` };
    case "returned": return { symbol: "↩", word: "הוחזר לתיקון" };
    default: return a.overdue ? { symbol: "⚠", word: "באיחור" } : { symbol: "○", word: "לא הוגש" };
  }
}
export const assignmentHref = a => a.kind === "exercise_test" ? `#/exam/${a.test.id}/${a.test.number}` : `#/assignment/${a.id}`;

/** Home shows only the new assignments: those not handed in yet (or an exercise test not taken). The rest are in the "הגשות" tab. */
const isNew = a => a.state === "not_handed" || a.state === "not_done";

/** The new assignments as one button to the "הגשות" tab, with how many there are. */
function assignmentsChip(all) {
  const list = all.filter(isNew);
  if (!list.length) return "";
  const late = list.some(a => a.overdue);
  return `<a class="hchip${late ? " late" : ""}" id="assignments" data-count="${list.length}" href="#/submissions">📝 ${list.length === 1 ? "משימה חדשה" : `${list.length} משימות חדשות`}${late ? " ⚠" : ""}</a>`;
}

/** Photo help (STU-6), only for a class with the AI on: one button, and the latest request with its state when there is one. */
function aiChips(ai) {
  if (!ai?.on) return "";
  const last = ai.requests[0];
  return `<span class="hchips-ai" id="ai-card"><button type="button" class="hchip" id="ai-new">📷 עזרה מתמונה</button>${last ? `<button type="button" class="hchip" data-ai-open="${esc(last.id)}"
    data-request="${esc(last.id)}">${esc(aiSheet.stateWord(last.state))}</button>` : ""}</span>`;
}

/* ---------- the lessons board: every lesson on one screen ---------- */

const starsText = n => "★".repeat(n) + "☆".repeat(3 - n);
const starsLabel = n => n === 3 ? "שלושה כוכבים, מושלם" : n === 0 ? "אין עדיין כוכבים" : n === 1 ? "כוכב אחד" : "שני כוכבים";
const plainText = text => String(text ?? "").replace(/\$/g, "");
export const roundHref = id => `#/round/${encodeURIComponent(id)}`;

function tile(l, next, kicker = "") {
  const isNext = l.id === next, perfect = l.stars === 3;
  const label = `שיעור ${l.number}: ${plainText(l.name)}. ${starsLabel(l.stars)}${l.behind ? `. בפיגור, היה אמור להסתיים ב־${shortDate(l.due_date)}` : ""}${l.round_open ? ". באמצע סבב" : ""}${isNext ? ". ממשיכים כאן" : ""}`;
  return `<a class="lnode s${l.stars}${perfect ? " perfect" : ""}${isNext ? " next" : ""}${l.behind ? " behind" : ""}" href="${roundHref(l.id)}" data-lesson="${esc(l.id)}" data-stars="${l.stars}"
      aria-label="${esc(label)}" title="${esc(plainText(l.name))}">
    <span class="disc" aria-hidden="true">${perfect ? "👑" : l.number}${l.behind ? `<i class="badge late">⏰</i>` : l.round_open ? `<i class="badge open">◐</i>` : ""}</span>
    <span class="lstars" aria-hidden="true">${starsText(l.stars)}</span><span class="lname" aria-hidden="true">${kicker ? `<small class="lkick">${kicker}</small><span class="ltext">${fmt(l.name)}</span>` : fmt(l.name)}</span></a>`;
}

/** The top: the stars collected, the lessons perfected, the streak and the daily goal, then the big play button for the next lesson. */
/** The status line (stars, crowns, streak, today's goal and the small buttons), then the big buttons: the current lesson (or the round left
 *  open), closing the gaps when lessons are behind (5 questions each; above 90 closes a lesson's gap), and quick practice and a
 *  photographed question side by side. */
function quest(map, chips = "", data = {}) {
  const open = map.lessons.find(l => l.round_open);
  const lesson = open || map.lessons.find(l => l.id === map.current) || map.lessons.find(l => l.id === map.next);
  const t = map.today, behind = data.behind || [];
  const play = lesson ? `<a class="play act-lesson" id="play" href="${roundHref(lesson.id)}"><span class="play-icon" aria-hidden="true">▶</span>
      <span class="grow"><small>${open ? "להמשיך את הסבב" : lesson.id === map.current ? `השיעור הנוכחי${lesson.due_date ? ` · עד ${esc(shortDate(lesson.due_date))}` : ""}` : lesson.stars ? "לעוד כוכב" : "השיעור הבא"}</small><b>${fmt(lesson.name)}</b></span>
      <span class="lstars" aria-label="${starsLabel(lesson.stars)}">${starsText(lesson.stars)}</span></a>`
    : `<p class="all-perfect" id="play">👑 כל השיעורים מושלמים! אפשר להעמיק בלשונית העמקה.</p>`;
  const gaps = behind.length ? `<a class="play act-gaps" id="home-gaps" href="#/gaps"><span class="play-icon" aria-hidden="true">🧩</span>
      <span class="grow"><small>השלמת פערים</small><b>${behind.length === 1 ? "שיעור אחד בפיגור" : `${behind.length} שיעורים בפיגור`}</b></span>
      <span class="ns-side"><span class="ns-chip">${5 * behind.length} שאלות</span><span class="ns-cost">מעל 90 = נסגר</span></span></a>` : "";
  const quick = data.onthego >= 10 ? `<a class="act" id="home-onthego" href="#/onthego"><span aria-hidden="true">⚡</span><b>תרגול מהיר</b><small>בלי לוח</small></a>` : "";
  const photo = data.photoq ? `<a class="act" id="home-photoq" href="#/photoq"><span aria-hidden="true">📸</span><b>צילום שאלה</b><small>ציון ומשוב</small></a>` : "";
  return `<section class="quest" id="quest" aria-label="המסע שלי">
    <p class="quest-stats"><span id="stars-count" aria-label="${map.stars} כוכבים מתוך ${map.max_stars}">⭐ ${map.stars}/${map.max_stars}</span><span id="perfect-count">👑 ${map.perfect}</span>
      ${map.streak ? `<span>🔥 ${map.streak}</span>` : ""}<span id="goal" class="goal-chip${t.reached ? " done" : ""}" title="יעד יומי">🎯 ${Math.min(t.done, t.goal)}/${t.goal}${t.reached ? " ✓" : ""}</span>
      ${chips ? `<span class="hchips" id="home-actions">${chips}</span>` : ""}</p>
    ${play}${gaps}${quick || photo ? `<div class="act-row${quick && photo ? "" : " one"}" id="home-quick">${quick}${photo}</div>` : ""}</section>`;
}

/** The lessons. With dates in the curriculum: the current lesson (the first whose date is today or later) on its own, and the lessons
 *  whose date has passed and the coming ones folded under it, each with how many there are (and how many are behind). Without dates:
 *  every lesson as a tile. */
function board(map) {
  const played = map.lessons.find(l => l.round_open)?.id || map.current || map.next;      // the big button above already shows this one
  if (!map.lessons.length) return "";
  const tiles = list => `<div class="lesson-board">${list.map(l => tile(l, map.next)).join("")}</div>`;
  if (!map.lessons.some(l => l.when)) {                     // no dates: the row of six around the next lesson, the rest folded (one screen)
    const at = Math.max(0, map.lessons.findIndex(l => l.id === map.next)), from = Math.floor(at / 6) * 6;
    const row = map.lessons.slice(from, from + 6), rest = map.lessons.filter(l => !row.includes(l));
    return `<section class="lesson-groups" id="lesson-map" aria-label="השיעורים">${tiles(row)}
      ${rest.length ? `<details class="lfold" id="lessons-rest"><summary><span class="grow">שאר השיעורים (${rest.length})</span></summary>${tiles(rest)}</details>` : ""}</section>`;
  }
  const past = map.lessons.filter(l => l.when === "past"), later = map.lessons.filter(l => l.when === "later");
  const now = map.lessons.find(l => l.when === "current");
  const behind = past.filter(l => l.behind).length;
  const fold = (id, title, list, extra = "") => list.length ? `<details class="lfold" id="${id}"><summary><span class="grow">${title} (${list.length})</span>${extra}</summary>${tiles(list)}</details>` : "";
  return `<section class="lesson-groups" id="lesson-map" aria-label="השיעורים">
    ${now && now.id === played ? "" : now ? `<div class="lnow" id="lesson-now"><h2 class="lnow-title mx-sr">השיעור הנוכחי</h2>${tile(now, map.next, `השיעור הנוכחי · עד ${esc(shortDate(now.due_date))}`)}</div>`
          : `<p class="muted" id="lesson-now">כל התאריכים בתוכנית כבר עברו.</p>`}
    ${fold("lessons-past", "שיעורים שעברו", past, behind ? `<span class="lfold-late">⏰ ${behind} בפיגור</span>` : "")}
    ${fold("lessons-later", "השיעורים הבאים", later)}</section>`;
}

export const show = view => swr([forSubject("/api/home"), "/api/assignments", "/api/ai/status"], ([data, assignments, ai]) => draw(view, data, assignments, ai));

function draw(view, data, assignments, ai) {
  const [first] = data.tests;
  const chips = assignmentsChip(assignments) + (data.photoq ? "" : aiChips(ai));   // photo help is the photographed question now
  view(`${tabs("home")}${backToSubjects()}
    ${quest(data.map, chips, data)}
    ${first ? testStrip(first) : ""}
    ${board(data.map)}`);
  countUp();
  document.getElementById("home-improve")?.addEventListener("click", () => import("./improve.js").then(m => m.open(first, data)));
  document.getElementById("ai-new")?.addEventListener("click", () => aiSheet.open());
  document.querySelectorAll("[data-ai-open]").forEach(b => b.addEventListener("click", () => aiSheet.open({ id: b.dataset.aiOpen })));
}
