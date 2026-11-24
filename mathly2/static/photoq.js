// Photographed questions (שאלה מצולמת, photoq.py): photograph a question with the phone (the 4-digit code) or from this device; the AI
// reads it and suggests its skill; the student sees it like any question, may change the skill, solves it on the board (with a box for a
// plain-number answer) and hands in; the AI's grade 0-100 and its feedback on the way come back. The class's approved questions can be solved
// from here too. Addresses: #/photoq (the list and a new photo), #/photoq/<id> (a question).
import { api } from "./api.js";
import { loadBoard } from "./exercise.js";
import { esc, fmt } from "./math.js";
import { askFromComputer, stopComputer } from "./phone.js";
import { pictureUrl, prepare, sendPicture } from "./media.js";
import { hasWork, sendWork } from "./boardwork.js";
import { currentSubject, homeHref } from "./ui.js";

let layer = null, current = null, timer = null, helpOpen = new Set();      // the questions whose help panel is open
const q = selector => layer?.querySelector(selector);
const boardKey = id => `pq:${id}`;
const VERDICT = { correct: ["✓", "דרך נכונה"], partial: ["◐", "חלק מהדרך נכון"], wrong: ["✗", "הדרך לא נכונה"], unclear: ["?", "לא הצלחנו לקרוא את הלוח"] };

function ensureLayer() {
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "mx-layer pq-layer";
    document.body.append(layer);
    layer.addEventListener("click", onClick);
    layer.addEventListener("submit", event => {
      if (!event.target.closest("#pq-ask")) return;
      event.preventDefault();
      const text = q("#pq-ask-text").value.trim();
      if (text) askHelp("ask", text);
    });
  }
  layer.innerHTML = `<div class="mx-scrim" data-close></div><div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="pq-title"></div>`;
}

export function close() {
  clearTimeout(timer);
  stopComputer();
  window.MathlyBoard?.closeFull?.();
  layer?.remove();
  layer = current = null;
}

const heading = (title, board = false) => `<div class="mx-shtop"><div><span class="ex-chip">📸 שאלה מצולמת</span><h3 id="pq-title">${title}</h3></div>
  <div class="mx-shacts">${board ? window.MathlyBoard?.button() || "" : ""}<button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>`;
const sheet = html => { q(".mx-sheet").innerHTML = html; };

/** The list: a new photo, the student's questions, and the class's approved ones. */
export async function showList() {
  await loadBoard();
  ensureLayer();
  current = null;
  sheet(`${heading("צילום שאלה")}<p class="muted">טוענים…</p>`);
  let data;
  try { data = await api(`/api/photo-questions?subject=${encodeURIComponent(currentSubject())}`); }
  catch (error) { sheet(`${heading("צילום שאלה")}<p class="error" role="alert">${esc(error.message)}</p>`); return; }
  const item = (r, bank) => `<li><button type="button" class="pq-item" data-${bank ? "bank" : "open"}="${esc(r.id)}">
      <span class="grow" dir="auto">${fmt(r.question || "שאלה בקריאה…")}</span>
      <span class="muted">${r.skill ? fmt(r.skill) : "חיצוני"}${r.grade !== null && r.grade !== undefined ? ` · ציון ${r.grade}` : ""}${bank && r.solved ? " · ✓ פתרתם" : ""}</span></button></li>`;
  sheet(`${heading("צילום שאלה")}
    ${data.on ? `<p>צלמו שאלה מדף עבודה, מספר או ממבחן. נקרא אותה, תפתרו אותה בלוח, ותקבלו ציון ומשוב על הדרך.</p>
      <p><button type="button" class="primary" id="pq-new"${data.left_today ? "" : " disabled"}>📸 צילום שאלה חדשה</button>
        <span class="muted" id="pq-left">${data.left_today ? `נשארו ${data.left_today} צילומים היום` : "סיימתם את הצילומים להיום. נמשיך מחר!"}</span></p>`
      : `<p class="muted" id="pq-off">צילום שאלות לא זמין כרגע.</p>`}
    ${data.mine.length ? `<h4>השאלות שצילמתם</h4><ul class="plain pq-list" id="pq-mine">${data.mine.map(r => item(r, false)).join("")}</ul>` : ""}
    ${data.bank.length ? `<h4>שאלות מהכיתה</h4><p class="muted">שאלות שחברים צילמו והמורה אישר/ה.</p><ul class="plain pq-list" id="pq-bank">${data.bank.map(r => item(r, true)).join("")}</ul>` : ""}`);
}

/** Taking the photo: the code for the phone, or a picture from this device. */
function showCapture() {
  sheet(`${heading("צילום שאלה")}
    <div id="pq-phone"></div>
    <p class="muted">או מהמכשיר הזה: <label class="button" for="pq-file">📷 בחירת תמונה</label><input type="file" id="pq-file" accept="image/*" capture="environment" hidden></p>
    <p id="pq-msg" role="status"></p>`);
  askFromComputer(null, pictureId => start(pictureId), q("#pq-phone"));
  q("#pq-file").addEventListener("change", async event => {
    const file = event.target.files?.[0];
    if (!file) return;
    stopComputer();
    q("#pq-msg").textContent = "מעלים את התמונה…";
    try { const made = await sendPicture("/api/pictures", await prepare(file)); await start(made.id); }
    catch (error) { q("#pq-msg").innerHTML = `<span class="error">${esc(error.message || "ההעלאה נכשלה")}</span>`; }
  });
}

async function start(pictureId) {
  try {
    const made = await api("/api/photo-questions", { method: "POST", body: { picture_id: pictureId, subject: currentSubject() } });
    location.hash = `#/photoq/${made.id}`;
  } catch (error) {
    const msg = q("#pq-msg") || q("#pq-phone");
    if (msg) msg.innerHTML = `<p class="error" role="alert">${esc(error.message)}</p>`;
  }
}

/** A question: being read, ready for the board, being checked, or checked. */
export async function open(id) {
  await loadBoard();
  if (!layer) ensureLayer();
  clearTimeout(timer);
  let data;
  try { data = await api(`/api/photo-questions/${encodeURIComponent(id)}`); }
  catch (error) { sheet(`${heading("שאלה מצולמת")}<p class="error" role="alert">${esc(error.message)}</p>`); return; }
  current = data;
  draw();
  if (data.state === "reading" || data.state === "checking") timer = setTimeout(() => layer && current?.id === id && open(id), 2000);
}

function photo(data) {
  if (!data.picture_id) return "";
  pictureUrl(data.picture_id).then(url => { const img = q("#pq-photo"); if (img) { img.src = url; img.hidden = false; } }).catch(() => {});
  return `<details class="pq-photo" open><summary>התמונה שצילמתם</summary>
    <button type="button" class="pq-photo-btn" id="pq-photo-btn" aria-label="הגדלת התמונה"><img id="pq-photo" alt="התמונה של השאלה" hidden></button></details>`;
}

function skillPick(data, locked) {
  const options = [...data.skills.map(s => `<option value="${esc(s.id)}"${data.skill?.id === s.id ? " selected" : ""}>${esc(s.name)}${s.id === data.suggested_skill ? " (הצעה)" : ""}</option>`),
    `<option value=""${data.skill ? "" : " selected"}>חיצוני (לא מהחומר שלנו)${data.suggested_skill ? "" : " (הצעה)"}</option>`];
  return `<p class="pq-skill"><label for="pq-skill">סיווג:</label> <select id="pq-skill"${locked ? " disabled" : ""}>${options.join("")}</select></p>`;
}

/** Help (עזרה): the conversation with the AI tutor, the ladder of hints with what each costs, and a box for any question. */
function helpHtml(d) {
  const h = d.help;
  if (!h) return "";
  const open = helpOpen.has(d.id) || h.chat.length > 0;
  const rung = (kind, label, cap) => cap === null || cap === undefined ? ""
    : `<button type="button" data-help="${kind}">${label} <small>(מקסימום ${cap})</small></button>`;
  const before = d.state === "ready";
  return `<section class="pq-help" id="pq-help">
    ${open ? `${before ? `<p class="pq-cap" id="pq-cap">🎯 הציון שאפשר להגיע אליו בשאלה הזו: <b>${h.max_grade}</b></p>` : ""}
      ${h.chat.length ? `<div class="pq-chat" id="pq-chat" aria-live="polite">${h.chat.map(m => `<p class="pq-msg ${m.role === "ai" ? "ai" : "me"}" dir="auto">${m.role === "ai" ? "🤖 " : ""}${fmt(m.text).replace(/\n/g, "<br>")}</p>`).join("")}</div>` : ""}
      ${before ? `<p class="pq-rungs" id="pq-rungs">${rung("direction", "🧭 איך מתחילים?", h.rungs.direction)}${rung("step", "👣 הצעד הבא", h.rungs.step)}${rung("full", "📖 הפתרון המלא", h.rungs.full)}</p>` : ""}
      ${h.can_ask ? `<form class="pq-ask" id="pq-ask"><label for="pq-ask-text" class="mx-sr">שאלה ל־AI</label>
        <input id="pq-ask-text" maxlength="500" dir="auto" placeholder="${before ? "מה לא ברור? למשל: מה זה שוקיים?" : "למשל: למה קיבלתי את הציון הזה?"}" autocomplete="off">
        <button type="submit">שליחה</button></form>
        <p class="muted pq-note">נשארו ${h.left} הודעות בשאלה הזו · המורה יכול/ה לראות את השיחה</p>` : `<p class="muted">הגעתם למספר ההודעות בשאלה הזו.</p>`}
      <p id="pq-help-msg" role="status"></p>`
    : `<p><button type="button" id="pq-help-open">💬 עזרה</button> <span class="muted">${before ? "רמזים בהדרגה, או שאלה חופשית ל־AI" : "לא הבנתם את הבדיקה? שאלו"}</span></p>`}</section>`;
}

async function askHelp(kind, text = "") {
  const msg = q("#pq-help-msg");
  layer.querySelectorAll("#pq-help button").forEach(b => { b.disabled = true; });
  if (msg) msg.textContent = kind === "ask" || kind === "direction" ? "🤖 חושב…" : "";
  try {
    current = await api(`/api/photo-questions/${current.id}/help`, { method: "POST", body: { kind, text } });
    helpOpen.add(current.id);
    draw();
    q("#pq-chat")?.lastElementChild?.scrollIntoView({ block: "nearest" });
  } catch (error) {
    layer.querySelectorAll("#pq-help button").forEach(b => { b.disabled = false; });
    if (q("#pq-help-msg")) q("#pq-help-msg").innerHTML = `<span class="error">${esc(error.message)}</span>`;
  }
}

function draw() {
  const d = current;
  if (d.state === "reading") return sheet(`${heading("שאלה מצולמת")}<p class="pq-wait" role="status">🔎 קוראים את השאלה…</p>${photo(d)}`);
  if (d.state === "unreadable" || d.state === "failed") {
    return sheet(`${heading("שאלה מצולמת")}<p class="error" role="alert" id="pq-reason">${esc(d.reason || "לא הצלחנו לקרוא את השאלה")}</p>${photo(d)}
      <p><button type="button" class="primary" id="pq-again">📸 לצלם שוב</button> <button type="button" data-list>לרשימה</button></p>`);
  }
  const checked = d.state === "checked", checking = d.state === "checking";
  const box = checked ? "" : boxes(d);
  const result = checked ? `<section class="pq-result" id="pq-result"><p class="qz-grade" aria-label="הציון ${d.grade}"><b>${d.grade}</b><span>מתוך 100</span></p>
      ${d.review ? `<p><span class="tag"><span aria-hidden="true">${VERDICT[d.review.verdict]?.[0] || ""}</span> ${VERDICT[d.review.verdict]?.[1] || ""}</span></p>
        <p>${fmt(d.review.feedback)}</p>${partsHtml(d.review.parts)}${d.review.tip ? `<p class="muted">💡 ${fmt(d.review.tip)}</p>` : ""}` : ""}
      <details><summary>הפתרון המלא</summary><ol>${(d.steps || []).map(s => `<li dir="auto">${fmt(s)}</li>`).join("")}</ol><p>תשובה: <b dir="auto" class="pq-lines">${fmt(d.answer || "")}</b></p></details>
      ${d.bank === "pending" ? `<p class="muted">📬 השאלה נשלחה למורה. אם יאשר/תאשר, היא תיכנס לשאלות של הכיתה.</p>` : d.bank === "approved" ? `<p class="muted">✓ השאלה נמצאת בשאלות של הכיתה.</p>` : ""}</section>` : "";
  sheet(`${heading(d.from_bank ? "שאלה מהכיתה" : "שאלה מצולמת", !checked)}
    ${photo(d)}
    <div class="mx-q" id="pq-q"><p class="ex-text pq-lines" dir="auto">${fmt(d.question)}</p>${skillPick(d, checked || checking)}
      ${checked ? "" : `<p class="muted">✏️ פתרו בלוח, כמו במבחן. הבודק רואה את הדרך, לא רק את התשובה.</p>`}${box}</div>
    ${checking ? "" : helpHtml(d)}
    ${checking ? `<p class="pq-wait" role="status">🧐 בודקים את הפתרון…</p>` : ""}
    ${result}
    <p id="pq-msg" role="status">${d.reason && d.state === "ready" ? `<span class="error">${esc(d.reason)}</span>` : ""}</p>
    <p class="ex-actions">${!checked && !checking ? `<button type="button" class="primary" id="pq-submit">הגשה</button>` : ""}
      ${checked && d.checks_left ? `<button type="button" id="pq-retry">לנסות שוב (${d.checks_left})</button>` : ""}
      <button type="button" data-list>לרשימה</button></p>`);
  if (!checked && !checking) window.MathlyBoard?.mount(layer, boardKey(d.id), { question: () => q("#pq-q") });
}

// The final-answer boxes: one for a plain question, one per sub-part whose answer is a number. The typed answers go as "א=30;ב=12".
function typedOf(d) {
  const text = d.typed || "", out = {};
  for (const piece of text.split(";")) { const [k, ...v] = piece.split("="); if (v.length && /^[א-ט]$/.test(k)) out[k] = v.join("="); }
  return Object.keys(out).length ? out : { "": text };
}

function boxes(d) {
  const list = d.finals || [], typed = typedOf(d);
  if (!list.length) return "";
  const many = list.some(f => f.part);
  return `<div class="qz-final pq-finals"><p><b>${many ? "התשובות הסופיות:" : "התשובה הסופית:"}</b></p>${list.map((f, i) => `<p class="qz-final-row" dir="ltr">
      ${f.part ? `<span class="tag" dir="rtl">סעיף ${esc(f.part)}</span>` : ""}${f.label ? `<span>${esc(f.label)}</span>` : ""}
      <input data-final="${esc(f.part)}" id="${i ? `pq-final-${i}` : "pq-final"}" aria-label="${f.part ? `התשובה של סעיף ${esc(f.part)}` : "התשובה הסופית"}" inputmode="decimal"
        maxlength="${many ? 10 : 40}" autocomplete="off" value="${esc(typed[f.part] || "")}">${f.unit ? `<span>${esc(f.unit)}</span>` : ""}</p>`).join("")}</div>`;
}

function typedNow() {
  const inputs = [...(layer?.querySelectorAll("[data-final]") || [])];
  if (inputs.length === 1 && !inputs[0].dataset.final) return inputs[0].value.trim();
  return inputs.filter(i => i.value.trim()).map(i => `${i.dataset.final}=${i.value.trim().replace(/[;=]/g, "")}`).join(";").slice(0, 40);
}

function partsHtml(parts) {
  if (!parts?.length) return "";
  return `<ul class="pq-parts">${parts.map(p => `<li><span class="tag">סעיף ${esc(p.label)} <span aria-hidden="true">${VERDICT[p.verdict]?.[0] || ""}</span></span> ${fmt(p.feedback)}</li>`).join("")}</ul>`;
}

async function submit() {
  const d = current, button = q("#pq-submit"), msg = q("#pq-msg");
  if (!hasWork(boardKey(d.id))) { msg.innerHTML = `<span class="error">✏️ קודם כותבים את הפתרון בלוח</span>`; window.MathlyBoard?.show?.(0); return; }
  button.disabled = true;
  msg.textContent = "שולחים את הלוח…";
  try {
    if (!await sendWork(boardKey(d.id), `pq:${d.id}`, "q")) throw new Error("הלוח לא נשלח, נסו שוב");
    await api(`/api/photo-questions/${d.id}/submit`, { method: "POST", body: { skill_id: q("#pq-skill")?.value || "", typed: typedNow() } });
    open(d.id);
  } catch (error) { button.disabled = false; msg.innerHTML = `<span class="error">${esc(error.message || "ההגשה נכשלה")}</span>`; }
}

async function fromBank(id) {
  try { const made = await api(`/api/photo-questions/from-bank/${encodeURIComponent(id)}`, { method: "POST" }); location.hash = `#/photoq/${made.id}`; }
  catch (error) { alert(error.message); }
}

function onClick(event) {
  const t = event.target;
  if (t.closest("[data-close]")) { location.hash = homeHref(); return; }
  if (t.closest("[data-board-toggle]")) { window.MathlyBoard?.toggle(); return; }
  if (t.closest("[data-list]")) { location.hash = "#/photoq"; showList(); return; }
  if (t.closest("#pq-new") || t.closest("#pq-again")) { showCapture(); return; }
  if (t.closest("#pq-submit")) { submit(); return; }
  const zoom = t.closest("#pq-photo-btn");
  if (zoom) { const big = zoom.classList.toggle("big"); zoom.setAttribute("aria-label", big ? "הקטנת התמונה" : "הגדלת התמונה"); return; }
  if (t.closest("#pq-help-open")) { helpOpen.add(current.id); draw(); q("#pq-ask-text")?.focus(); return; }
  const rung = t.closest("[data-help]")?.dataset.help;
  if (rung) { askHelp(rung); return; }
  if (t.closest("#pq-retry")) { current = { ...current, state: "ready" }; draw(); return; }
  const mine = t.closest("[data-open]")?.dataset.open;
  if (mine) { location.hash = `#/photoq/${mine}`; return; }
  const bank = t.closest("[data-bank]")?.dataset.bank;
  if (bank) fromBank(bank);
}

let availability = null;
/** Is photographing questions on (the AI is set up)? Asked once a page load. */
export function available() {
  availability ||= api(`/api/photo-questions?subject=${encodeURIComponent(currentSubject())}`).then(d => !!d.on).catch(() => false);
  return availability;
}

window.addEventListener("mathly:leave", close);
