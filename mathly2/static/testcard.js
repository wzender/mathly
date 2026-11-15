// One real test: the readiness number and what moves it, a simulation on request (all the material, timed, no choice), a practice test on
// request in one of three modes (balanced, focused on the skills that were hard, or skills picked by hand), and the trail of the tests
// handed in with what each one added.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";
import { countUp, readinessMeter } from "./home.js";
import { daysText, forSubject, homeHref, setSubject, shortDate, tabs } from "./ui.js";

const MODES = [
  ["balanced", "⚖️ מאוזן", "שאלות מכל החומר של המבחן, באופן שווה."],
  ["focus", "🎯 ממוקד", "15 שאלות רק מהמיומנויות שהתקשיתם בהן במבחנים."],
  ["manual", "✋ בחירה ידנית", "אתם בוחרים את המיומנויות."],
];
const STATE = { mastered: "👑", learning: "◐", not_started: "○" };

/** How the number moves, in plain words, with what deepening gives now. */
const how = r => `<details class="rd-how" id="rd-how"><summary>איך מעלים את המוכנות?</summary><ul>
  <li id="rd-deepening">העמקה נספרת: כל מיומנות מהחומר של המבחן שמגיעים בה לשליטה (👑) מעלה את נקודת ההתחלה, עד 20 נקודות כשכל החומר בשליטה.
    ${r.mastered_share ? `<b>עכשיו: ${Math.round(r.mastered_share * 100)}% מהמיומנויות בשליטה, ${r.deepening} נקודות.</b>` : ""}</li>
  <li>כל מבחן שהציון בו גבוה מהמוכנות מעלה אותה: מבחן תרגול סוגר 30% מהפער, <b>מבחן סימולציה סוגר 60%</b>, ומבחן בבחירה ידנית 15%.</li>
  <li>ציון נמוך מהמוכנות לא מוריד אותה.</li></ul></details>`;

function simulationCard(test) {
  const s = test.simulation, gain = test.readiness.can_add.simulation;
  return `<section class="card test-action" id="simulation"><h3>⏱ מבחן סימולציה</h3>
    <p class="muted">כמו המבחן האמיתי: ${test.questions} שאלות מכל החומר, ${test.minutes} דקות. את השאלות בוחרת האפליקציה.</p>
    <p><a class="button primary big-btn" id="sim-start" href="#/sim/${test.id}${s.open ? `/${esc(s.open)}` : ""}">${s.open ? "להמשיך את הסימולציה" : "בקשת מבחן סימולציה"}
      ${s.open || !gain ? "" : `<small class="gain-hint">עד +${gain} מוכנות</small>`}</a></p>
    ${s.taken ? `<p class="muted" id="sim-done">עשיתם ${s.taken === 1 ? "סימולציה אחת" : `${s.taken} סימולציות`} · הציון הטוב: <b id="sim-best">${s.best}</b></p>` : ""}</section>`;
}

function practiceCard(test) {
  const p = test.practice, gain = test.readiness.can_add;
  const lessons = [...new Set(p.manual.skills.map(s => s.lesson))];
  const radio = ([mode, title, what]) => {
    const off = mode === "focus" && !p.focus.skills.length;
    return `<label class="mode${off ? " off" : ""}" data-mode="${mode}"><input type="radio" name="mode" value="${mode}"${mode === "balanced" ? " checked" : ""}${off ? " disabled" : ""}>
      <span><b>${title}</b>${p[mode].open ? ` <span class="tag">באמצע</span>` : ""}<br><span class="muted">${off ? "יופיע אחרי מבחן שבו היו טעויות." : what}</span></span></label>`;
  };
  return `<section class="card test-action" id="practice"><h3>📝 מבחן תרגול</h3>
    <p class="muted">אתם בוחרים על מה להתאמן. בלי שעון.</p>
    <div class="modes" role="radiogroup" aria-label="סוג מבחן התרגול">${MODES.map(radio).join("")}</div>
    <div id="focus-skills" class="chips" hidden>${p.focus.skills.map(s => `<span class="ex-chip">${fmt(s.name)}</span>`).join(" ")}</div>
    <fieldset id="manual-skills" hidden><legend>בחרו מיומנויות</legend>${lessons.map(lesson => `<p class="muted pick-lesson">${fmt(lesson)}</p>
      ${p.manual.skills.filter(s => s.lesson === lesson).map(s => `<label class="pick"><input type="checkbox" value="${esc(s.id)}"> <span aria-hidden="true">${STATE[s.state] || ""}</span> ${fmt(s.name)}</label>`).join("")}`).join("")}</fieldset>
    <p><button type="button" class="primary big-btn" id="practice-start">בקשת מבחן תרגול <small class="gain-hint">עד +${gain.practice} מוכנות</small></button></p>
    <p class="error" id="practice-error" role="alert" hidden></p></section>`;
}

function trailCard(test) {
  if (!test.trail.length) return "";
  return `<section class="card" id="trail"><h3>המבחנים שעשיתם</h3><ol class="plain trail">${test.trail.map(t => `<li data-kind="${t.kind}">
      <a href="${t.kind === "simulation" ? `#/sim/${test.id}/${esc(t.attempt)}` : `#/exam/${test.id}/${t.number}/${esc(t.attempt)}`}"><span class="grow"><b>${esc(t.title)}</b>
      <span class="muted"> · ${shortDate(t.at.slice(0, 10))}</span></span><span class="tag">ציון ${t.grade}</span>
      <span class="gain${t.gain ? "" : " zero"}">${t.gain ? `+${t.gain}` : "±0"}</span></a></li>`).join("")}</ol></section>`;
}

/** The mode's extra part (the hard skills, the skills to pick) and what the button says; the button asks for the test. */
function wire(test) {
  const card = document.getElementById("practice");
  const mode = () => card.querySelector("input[name=mode]:checked").value;
  const sync = () => {
    const m = mode(), resume = m !== "manual" && test.practice[m].open;
    card.querySelector("#focus-skills").hidden = m !== "focus";
    card.querySelector("#manual-skills").hidden = m !== "manual";
    card.querySelectorAll(".mode").forEach(l => l.classList.toggle("on", l.dataset.mode === m));
    const gain = test.readiness.can_add[m === "manual" ? "manual" : "practice"];
    document.getElementById("practice-start").innerHTML = resume ? "להמשיך את המבחן"
      : `בקשת מבחן תרגול${gain ? ` <small class="gain-hint">עד +${gain} מוכנות</small>` : ""}`;
  };
  card.addEventListener("change", sync);
  sync();
  document.getElementById("practice-start").addEventListener("click", async event => {
    const button = event.currentTarget, error = document.getElementById("practice-error"), m = mode();
    const skills = [...card.querySelectorAll("#manual-skills input:checked")].map(i => i.value);
    if (m === "manual" && !skills.length) { error.textContent = "בחרו לפחות מיומנות אחת."; error.hidden = false; return; }
    button.disabled = true;
    error.hidden = true;
    try {
      const data = await api(`/api/tests/${test.id}/practice/start`, { method: "POST", body: { mode: m, skills } });
      location.hash = `#/exam/${test.id}/${data.test.number}/${encodeURIComponent(data.id)}`;
    } catch (e) {
      button.disabled = false;
      error.textContent = e.message || "משהו השתבש";
      error.hidden = false;
    }
  });
}

/** `focus`: a section to scroll to ("practice" from the home's button). */
export async function show(view, id, focus = "") {
  const test = await api(`/api/tests/${encodeURIComponent(id)}`);
  setSubject(test.subject_id);                                         // a test belongs to one subject: its home and tab bar follow it
  const home = await api(forSubject("/api/home"));
  const others = home.tests.filter(t => t.id !== test.id);
  view(`${tabs("home")}<p><a class="back" href="${homeHref()}">‹ הבית</a></p>
    <section class="card" id="test-card" data-test="${test.id}"><h2>מבחן ב־${shortDate(test.date)} <span class="muted">(${daysText(test.days_left)})</span></h2>
      <p class="muted">${test.lessons.map(l => fmt(l.name)).join(", ")}${test.note ? ` · ${esc(test.note)}` : ""}</p>
      ${readinessMeter(test)}${how(test.readiness)}</section>
    ${simulationCard(test)}
    ${practiceCard(test)}
    ${trailCard(test)}
    ${others.length ? `<section class="card"><h3>מבחנים נוספים</h3><ul class="plain" id="other-tests">${others.map(t => `<li><a href="#/test/${t.id}">${shortDate(t.date)} · ${t.lessons.map(l => fmt(l.name)).join(", ")}</a>
      <span class="muted">${daysText(t.days_left)} · מוכנות ${t.readiness.number}</span></li>`).join("")}</ul></section>` : ""}`);
  wire(test);
  countUp();
  if (focus) document.getElementById(focus)?.scrollIntoView({ block: "start" });
}
