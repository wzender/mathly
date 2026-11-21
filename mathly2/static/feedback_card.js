// The developer's "הצעות ומשוב" card (feedback.py): what people sent, the open ones first, each with who, when and from which screen,
// and a button that marks it handled (or opens it again).
import { api } from "./api.js";
import { esc } from "./math.js";

const KIND = { idea: "💡 רעיון", bug: "🐞 תקלה", other: "💬 אחר" };
const ROLE = { student: "תלמיד", teacher: "מורה", manager: "מנהל כיתות", admin: "מנהל הרשאות", developer: "מפתח" };
const when = iso => new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jerusalem" }).format(new Date(iso));

function item(f) {
  return `<li class="${f.handled_at ? "handled" : ""}" data-feedback="${f.id}">
    <span class="fb-head"><span class="tag">${KIND[f.kind] || f.kind}</span><span dir="ltr">${esc(f.email)}</span>
      <span class="muted">${f.roles.map(r => ROLE[r] || r).join(", ")} · ${esc(when(f.created_at))}${f.page ? ` · <span dir="ltr">${esc(f.page)}</span>` : ""}</span></span>
    <p class="fb-text" dir="auto">${esc(f.body)}</p>
    <p><button type="button" data-handled="${f.id}" data-to="${f.handled_at ? "false" : "true"}">${f.handled_at ? "↩ לפתוח שוב" : "✓ טופל"}</button></p></li>`;
}

function draw(section, list) {
  const open = list.filter(f => !f.handled_at), done = list.filter(f => f.handled_at);
  section.innerHTML = `<h2>הצעות ומשוב <span class="tag" id="fb-open-count">${open.length} פתוחות</span></h2>
    ${open.length ? `<ul class="plain fb-list" id="fb-open">${open.map(item).join("")}</ul>` : `<p class="muted" id="fb-none">אין הצעות פתוחות.</p>`}
    ${done.length ? `<details><summary>טופלו (${done.length})</summary><ul class="plain fb-list" id="fb-done">${done.map(item).join("")}</ul></details>` : ""}`;
}

export async function mount(section) {
  section.innerHTML = `<h2>הצעות ומשוב</h2><p class="muted">טוענים…</p>`;
  let list;
  try { list = await api("/api/feedback"); }
  catch (e) { section.innerHTML = `<h2>הצעות ומשוב</h2><p class="error" role="alert">לא הצלחנו לקרוא את ההצעות: ${esc(e.message)}</p>`; return; }
  draw(section, list);
  section.addEventListener("click", async event => {
    const button = event.target.closest("[data-handled]");
    if (!button) return;
    button.disabled = true;
    try {
      const saved = await api(`/api/feedback/${button.dataset.handled}/handled`, { method: "POST", body: { handled: button.dataset.to === "true" } });
      list = list.map(f => f.id === saved.id ? saved : f);
      draw(section, list);
    } catch (e) { button.disabled = false; button.insertAdjacentHTML("afterend", ` <span class="error">${esc(e.message)}</span>`); }
  });
}
