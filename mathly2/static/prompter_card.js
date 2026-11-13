// The developer's "פרומפטר" card (add-prompter): the saved texts (the account's own, on every device), an editor for the title, the
// text and its outline (ראשי פרקים), the AI's outline on request, and the full-screen prompter (prompter.js, ported from mathly1).
// What is typed is also kept in this browser until it is saved, so nothing is lost before a save.
import { api } from "./api.js";
import { esc } from "./math.js";

const DRAFT_KEY = "mathly2.prompter-draft";
let texts = [], current = null;          // current: {id|null, title, body, outline}

const keep = () => { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(current)); } catch { /* private window: not kept */ } };
const kept = () => { try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); } catch { return null; } };
const forget = () => { try { localStorage.removeItem(DRAFT_KEY); } catch { /* nothing kept */ } };
const when = iso => iso ? new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jerusalem" }).format(new Date(iso)) : "";
const saved = () => current?.id ? texts.find(t => t.id === current.id) : null;
const dirty = () => { const s = saved(); return !!current && (!s || s.title !== current.title || s.body !== current.body || (s.outline || "") !== (current.outline || "")); };

function say(text, error = false) {
  const el = document.getElementById("pr-msg");
  if (el) { el.textContent = text; el.classList.toggle("error", error); }
}

function list() {
  return texts.length ? `<ul class="plain pr-list" id="pr-list">${texts.map(t => `<li data-text="${esc(t.id)}"${current?.id === t.id ? ' aria-current="true"' : ""}>
      <button type="button" class="pr-pick grow" data-pick="${esc(t.id)}"><b dir="auto">${esc(t.title)}</b> <span class="muted">${esc(when(t.updated_at))}${t.outline ? " · יש ראשי פרקים" : ""}</span></button></li>`).join("")}</ul>`
    : `<p class="muted">עוד אין טקסטים שמורים. כתבו או הדביקו טקסט, ושמרו אותו.</p>`;
}

function editor() {
  const c = current || { id: null, title: "", body: "", outline: "" };
  return `<form id="pr-form" class="pr-form">
    <label for="pr-title">כותרת (לא חובה)</label><input id="pr-title" maxlength="120" value="${esc(c.title || "")}" dir="auto">
    <label for="pr-body">הטקסט</label><textarea id="pr-body" rows="10" dir="auto" placeholder="אפשר לכתוב Slide 1 — כותרת בתחילת כל שקף, כדי להציג שקף אחר שקף">${esc(c.body || "")}</textarea>
    <details ${c.outline ? "open" : ""}><summary>ראשי פרקים</summary>
      <textarea id="pr-outline" rows="6" dir="auto" placeholder="שורות שמתחילות ב־• מוצגות כתזכורות">${esc(c.outline || "")}</textarea></details>
    <p class="hrow pr-actions">
      <button type="submit" class="primary" id="pr-save">שמירה</button>
      <button type="button" id="pr-show" data-show="body">הצגה בפרומפטר</button>
      <button type="button" id="pr-show-outline" data-show="outline" ${c.outline ? "" : "disabled"}>הצגת ראשי הפרקים</button>
      <button type="button" id="pr-make-outline" ${c.id ? "" : "disabled"} title="${c.id ? "" : "קודם שומרים את הטקסט"}">ראשי פרקים עם AI</button>
      <button type="button" id="pr-new">טקסט חדש</button>
      ${c.id ? `<button type="button" class="danger" id="pr-delete">מחיקה</button>` : ""}</p>
    <p id="pr-msg" role="status" aria-live="polite"></p></form>`;
}

function draw() {
  const box = document.getElementById("pr-body-box");
  if (box) box.innerHTML = `<div class="pr-layout"><div>${list()}</div><div>${editor()}</div></div>`;
}

function read() {
  current = { id: current?.id || null, title: document.getElementById("pr-title").value, body: document.getElementById("pr-body").value,
              outline: document.getElementById("pr-outline").value };
}

async function show(which) {
  read();
  const text = which === "outline" ? current.outline : current.body;
  if (!text.trim()) { say(which === "outline" ? "אין ראשי פרקים להצגה" : "אין טקסט להצגה", true); return; }
  if (!window.MathlyPrompter) await import("./prompter.js");
  window.MathlyPrompter.open(text);
}

async function save() {
  read();
  const body = { title: current.title, body: current.body, outline: current.outline };
  const made = current.id ? await api(`/api/prompter/texts/${current.id}`, { method: "PUT", body }) : await api("/api/prompter/texts", { method: "POST", body });
  current = { ...made.text };
  texts = [made.text, ...texts.filter(t => t.id !== made.text.id)];
  forget();
  draw();
  say("נשמר");
}

async function onClick(event) {
  const target = event.target;
  try {
    const pick = target.closest("[data-pick]")?.dataset.pick;
    if (pick) {
      if (dirty() && !confirm("יש שינויים שלא נשמרו. לעבור לטקסט אחר בלי לשמור?")) return;
      current = { ...texts.find(t => t.id === pick) }; forget(); draw(); return;
    }
    if (target.closest("[data-show]")) return await show(target.closest("[data-show]").dataset.show);
    if (target.closest("#pr-new")) {
      if (dirty() && !confirm("יש שינויים שלא נשמרו. להתחיל טקסט חדש בלי לשמור?")) return;
      current = { id: null, title: "", body: "", outline: "" }; forget(); draw(); document.getElementById("pr-body").focus(); return;
    }
    if (target.closest("#pr-delete")) {
      if (!confirm("למחוק את הטקסט?")) return;
      await api(`/api/prompter/texts/${current.id}`, { method: "DELETE" });
      texts = texts.filter(t => t.id !== current.id); current = null; forget(); draw(); say("נמחק"); return;
    }
    if (target.closest("#pr-make-outline")) {
      read();
      if (dirty()) await save();                                // the outline is written from the saved text
      say("ה־AI כותב ראשי פרקים…");
      const made = await api(`/api/prompter/texts/${current.id}/outline`, { method: "POST" });
      current = { ...made.text }; texts = texts.map(t => t.id === made.text.id ? made.text : t);
      draw(); say("ראשי הפרקים מוכנים");
    }
  } catch (e) { say(e.message, true); }
}

/** Draw the card's content into its section and wire it. */
export async function mount(section) {
  section.innerHTML = `<h2>פרומפטר</h2><div id="pr-body-box"><p class="muted">טוענים…</p></div>`;
  try { texts = (await api("/api/prompter/texts")).texts; }
  catch (e) { section.querySelector("#pr-body-box").innerHTML = `<p class="error" role="alert">לא הצלחנו לקרוא את הטקסטים: ${esc(e.message)}</p>`; return; }
  current = kept() || (texts[0] ? { ...texts[0] } : { id: null, title: "", body: "", outline: "" });
  draw();
  if (kept()) say("הטקסט שהתחלתם לכתוב חזר. הוא עוד לא נשמר.");
  section.addEventListener("click", onClick);
  section.addEventListener("submit", event => { event.preventDefault(); save().catch(e => say(e.message, true)); });
  section.addEventListener("input", event => { if (event.target.closest("#pr-form")) { read(); keep(); } });
}
