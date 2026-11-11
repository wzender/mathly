// The developer's home: a status card (is each part working, which version runs, when it was last updated) and every permission
// (the other roles' chips open their screens). The other tools (prompter, lab, AI cost) come later.
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

export async function show(me, view) {
  view(`<section class="card" id="status" aria-labelledby="st-title">
      <div class="st-top"><h2 id="st-title">מצב המערכת</h2><button type="button" id="st-refresh">בדיקה מחדש</button></div>
      <div id="st-body" aria-live="polite"><p class="muted">בודקים…</p></div></section>
    <section class="card" id="developer"><h2>מפתח</h2>
      <p>יש לך את כל ההרשאות: אפשר לפתוח את המסכים של כל התפקידים מהכפתורים למעלה.</p>
      <p class="muted">כלי המפתח (פרומפטר, מעבדה, עלות ה־AI) יתווספו בשלבים הבאים.</p>
      <p class="muted" dir="ltr">${esc(me.email)}</p></section>`);
  document.getElementById("st-refresh").addEventListener("click", load);
  await load();
}
