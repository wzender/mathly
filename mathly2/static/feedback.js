// Suggestions and feedback (משוב, feedback.py): a small sheet from the header for anyone signed in. The screen they were on goes with it.
import { api } from "./api.js";
import { esc } from "./math.js";

let layer = null;
const KINDS = [["idea", "💡 רעיון"], ["bug", "🐞 משהו לא עובד"], ["other", "💬 אחר"]];

export function close() {
  layer?.remove();
  layer = null;
  document.removeEventListener("keydown", onKey);
}

function onKey(event) { if (event.key === "Escape") close(); }

export function open() {
  close();
  const page = (location.hash || "#/").slice(0, 200);
  layer = document.createElement("div");
  layer.className = "mx-layer fb-layer";
  layer.innerHTML = `<div class="mx-scrim" data-close></div>
    <div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="fb-title"><form class="fb-sheet" id="fb-form">
      <div class="mx-shtop"><h3 id="fb-title">הצעה או משוב</h3><div class="mx-shacts"><button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>
      <p class="muted">מה היה עוזר לכם? משהו לא עובד? כל הצעה נקראת.</p>
      <fieldset class="fb-kinds"><legend class="mx-sr">סוג</legend>${KINDS.map(([v, label], i) =>
        `<label class="fb-kind"><input type="radio" name="kind" value="${v}"${i === 0 ? " checked" : ""}> ${label}</label>`).join("")}</fieldset>
      <label for="fb-body" class="mx-sr">ההצעה</label>
      <textarea id="fb-body" name="body" rows="5" maxlength="2000" required dir="auto" placeholder="כתבו כאן…"></textarea>
      <p class="fb-msg" id="fb-msg" role="status" aria-live="polite"></p>
      <p><button type="submit" class="primary" id="fb-send">שליחה</button> <button type="button" data-close>ביטול</button></p>
    </form></div>`;
  document.body.append(layer);
  layer.addEventListener("click", event => { if (event.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", onKey);
  const form = layer.querySelector("#fb-form"), msg = layer.querySelector("#fb-msg");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const body = form.body.value.trim();
    if (!body) { msg.textContent = "כתבו מה תרצו לספר לנו"; return; }
    const send = form.querySelector("#fb-send");
    send.disabled = true;
    try {
      await api("/api/feedback", { method: "POST", body: { kind: form.kind.value, body, page } });
      form.innerHTML = `<div class="mx-shtop"><h3 id="fb-title">תודה! 🙏</h3><div class="mx-shacts"><button type="button" class="mx-x" data-close aria-label="סגירה">✕</button></div></div>
        <p id="fb-thanks">קיבלנו את ההצעה שלכם. ככה האפליקציה משתפרת.</p><p><button type="button" class="primary" data-close>סגירה</button></p>`;
      form.querySelector("[data-close].primary").focus();
    } catch (error) {
      send.disabled = false;
      msg.innerHTML = `<span class="error">${esc(error.message || "ההצעה לא נשלחה, נסו שוב")}</span>`;
    }
  });
  layer.querySelector("#fb-body").focus();
}
