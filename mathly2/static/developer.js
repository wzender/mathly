// The developer's home: a status card (is each part working, which version runs, when it was last updated), an activity chart
// (how many people used the app on each of the last 7 or 30 days) and every permission (the other roles' chips open their screens).
// The other tools (prompter, lab, AI cost) come later.
import { api } from "./api.js";
import { esc } from "./math.js";

const STATES = { ok: { icon: "✓", word: "תקין" }, warn: { icon: "!", word: "שימו לב" }, error: { icon: "✕", word: "תקלה" }, off: { icon: "–", word: "כבוי" } };
const OVERALL = { ok: "המערכת תקינה", warn: "המערכת עובדת, עם הערות", error: "יש תקלה במערכת" };

const when = iso => iso ? new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jerusalem" }).format(new Date(iso)) : "לא ידוע";

function since(seconds) {
  const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600), m = Math.floor(seconds % 3600 / 60);
  return d ? `לפני ${d} ימים ו־${h} שעות` : h ? `לפני ${h} שעות ו־${m} דקות` : m ? `לפני ${m} דקות` : "לפני פחות מדקה";
}

function card(s) {
  const v = s.version;
  return `<div class="st-head st-${esc(s.overall)}" id="st-overall" data-state="${esc(s.overall)}">
      <span class="st-dot" aria-hidden="true">${STATES[s.overall].icon}</span><b>${OVERALL[s.overall]}</b></div>
    <dl class="st-facts">
      <div><dt>גרסה</dt><dd id="st-version" dir="ltr">${v.short ? `<span title="${esc(v.commit)}">${esc(v.short)}</span>` : "לא ידועה"}</dd></div>
      <div><dt>עדכון אחרון</dt><dd id="st-updated">${esc(when(v.date))}</dd></div>
      <div><dt>השרת עלה</dt><dd id="st-started">${esc(when(s.started_at))} <span class="muted">(${since(s.uptime_seconds)})</span></dd></div>
    </dl>
    <ul class="plain st-checks" id="st-checks">${s.checks.map(c => `<li data-key="${esc(c.key)}" data-state="${esc(c.state)}">
      <span><span class="st-dot st-${esc(c.state)}" aria-hidden="true">${STATES[c.state].icon}</span> <b>${esc(c.name)}</b>
        <span class="muted">${esc(c.detail)}</span></span><span class="st-word st-${esc(c.state)}">${STATES[c.state].word}</span></li>`).join("")}</ul>
    <p class="muted st-foot">נבדק ב־${esc(when(s.now))} · Python ${esc(s.python)}</p>`;
}

let asked = 0;                                     // only the latest check is drawn, if two overlap

async function load() {
  const mine = ++asked;
  let html;
  try {
    html = card(await api("/api/dev/status"));
  } catch (error) {
    html = `<p class="error" role="alert">לא הצלחנו לקרוא את מצב המערכת: ${esc(error.message || "")}</p>`;
  }
  const box = document.getElementById("st-body");
  if (box && mine === asked) box.innerHTML = html;
}

// ---- activity: one column per Israel day, oldest on the left; the height is how many different people were active ----

const DAY = new Intl.DateTimeFormat("he-IL", { weekday: "short", timeZone: "UTC" });
const DATE = new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "numeric", timeZone: "UTC" });
const LONG = new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
const at = iso => new Date(`${iso}T00:00:00Z`);                      // a calendar day, drawn as that day whatever the device's zone
const people = n => n === 1 ? "משתמש אחד" : `${n.toLocaleString("he-IL")} משתמשים`;

/** A clean top for the axis (1, 2 or 5 times a power of ten) and its step, about four gridlines. */
function scale(max) {
  if (max <= 4) return { top: Math.max(max, 1), step: 1 };
  const rough = max / 4, power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map(m => m * power).find(s => s >= rough);
  return { top: Math.ceil(max / step) * step, step };
}

function chart(a) {
  const days = a.days, n = days.length, { top, step } = scale(Math.max(...days.map(d => d.users)));
  const peak = days.reduce((best, d, i) => d.users > days[best].users ? i : best, 0);
  const every = n <= 7 ? 1 : 5;                                         // which days get a label under the axis
  const ticks = []; for (let v = 0; v <= top; v += step) ticks.push(v);
  return `<div class="ac-plot" dir="ltr" style="--n:${n}">
      <div class="ac-grid" aria-hidden="true">${ticks.map(v => `<div class="ac-tick" style="bottom:${v / top * 100}%"><span>${v}</span></div>`).join("")}</div>
      <ol class="ac-cols" aria-label="משתמשים פעילים בכל יום">${days.map((d, i) => {
        const label = `${LONG.format(at(d.day))}: ${people(d.users)}, ${d.answers} תשובות בתרגול, ${d.attempts} בחנים ומבחנים`;
        const shown = d.users > 0 && (i === n - 1 || i === peak);          // label the latest day and the busiest, not every column
        return `<li class="ac-col" tabindex="0" data-day="${d.day}" data-users="${d.users}" aria-label="${esc(label)}">
          <span class="ac-bar" style="height:${d.users / top * 100}%">${shown ? `<b class="ac-val">${d.users}</b>` : ""}</span>
          <span class="ac-tip" role="tooltip"><b>${esc(LONG.format(at(d.day)))}</b><br>${people(d.users)}<br>${d.answers} תשובות בתרגול<br>${d.attempts} בחנים ומבחנים</span>
          <span class="ac-x" aria-hidden="true">${i % every === (n - 1) % every ? (n <= 7 ? `${esc(DAY.format(at(d.day)))}<br>${esc(DATE.format(at(d.day)))}` : esc(DATE.format(at(d.day)))) : ""}</span>
        </li>`;
      }).join("")}</ol></div>`;
}

function activityCard(a) {
  const today = a.days[a.days.length - 1], n = a.days.length;
  return `<dl class="st-facts ac-tiles">
      <div><dt>היום</dt><dd id="ac-today">${people(today.users)}</dd></div>
      <div><dt>ב־${n} הימים האחרונים</dt><dd id="ac-range">${people(a.users)}</dd></div>
      <div><dt>תשובות בתרגול</dt><dd>${a.answers.toLocaleString("he-IL")}</dd></div>
      <div><dt>בחנים ומבחנים שהתחילו</dt><dd>${a.attempts.toLocaleString("he-IL")}</dd></div>
    </dl>${chart(a)}
    <details class="ac-table"><summary>הנתונים בטבלה</summary><table><thead><tr><th>יום</th><th>משתמשים</th><th>תשובות</th><th>בחנים ומבחנים</th></tr></thead>
      <tbody>${a.days.slice().reverse().map(d => `<tr><td>${esc(LONG.format(at(d.day)))}</td><td>${d.users}</td><td>${d.answers}</td><td>${d.attempts}</td></tr>`).join("")}</tbody></table></details>
    <p class="muted st-foot">משתמש פעיל: ענה על שאלה בתרגול או התחיל בוחן או מבחן באותו יום (לפי שעון ישראל).</p>`;
}

let range = 7, askedActivity = 0;

async function loadActivity() {
  const mine = ++askedActivity;
  let html;
  try {
    html = activityCard(await api(`/api/dev/activity?days=${range}`));
  } catch (error) {
    html = `<p class="error" role="alert">לא הצלחנו לקרוא את הפעילות: ${esc(error.message || "")}</p>`;
  }
  const box = document.getElementById("ac-body");
  if (box && mine === askedActivity) box.innerHTML = html;
}

export async function show(me, view) {
  view(`<section class="card" id="status" aria-labelledby="st-title">
      <div class="st-top"><h2 id="st-title">מצב המערכת</h2><button type="button" id="st-refresh">בדיקה מחדש</button></div>
      <div id="st-body" aria-live="polite"><p class="muted">בודקים…</p></div></section>
    <section class="card" id="activity" aria-labelledby="ac-title">
      <div class="st-top"><h2 id="ac-title">פעילות</h2>
        <div class="ac-range" role="group" aria-label="טווח">${[7, 30].map(d =>
          `<button type="button" data-range="${d}" aria-pressed="${d === range}">${d} ימים</button>`).join("")}</div></div>
      <div id="ac-body" aria-live="polite"><p class="muted">טוענים…</p></div></section>
    <section class="card" id="developer"><h2>מפתח</h2>
      <p>יש לך את כל ההרשאות: אפשר לפתוח את המסכים של כל התפקידים מהכפתורים למעלה.</p>
      <p class="muted">כלי המפתח (פרומפטר, מעבדה, עלות ה־AI) יתווספו בשלבים הבאים.</p>
      <p class="muted" dir="ltr">${esc(me.email)}</p></section>`);
  document.getElementById("st-refresh").addEventListener("click", () => { load(); loadActivity(); });
  document.querySelector("#activity .ac-range").addEventListener("click", event => {
    const button = event.target.closest("[data-range]");
    if (!button) return;
    range = Number(button.dataset.range);
    document.querySelectorAll("#activity [data-range]").forEach(b => b.setAttribute("aria-pressed", String(b === button)));
    loadActivity();
  });
  await Promise.all([load(), loadActivity()]);
}
