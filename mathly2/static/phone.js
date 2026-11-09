// The photo request, both ends. The computer asks for a photo of an answer: it shows a 4-digit code and the request's state in words.
// The student's phone (any other device signed in to the same account) shows a window with the same code and a camera button.
import { api, ApiError } from "./api.js";
import { withBusy } from "./busy.js";
import { esc, fmt } from "./math.js";
import { deviceId, prepare, sendPicture } from "./media.js";

export const WORDS = { waiting: "ממתינים לטלפון", uploading: "מעלים את התשובה…", received: "התשובה התקבלה", failed: "ההעלאה נכשלה", expired: "הבקשה פגה. אפשר לבקש שוב.",
  superseded: "הוחלפה בבקשה חדשה" };
const DONE = new Set(["received", "failed", "expired", "superseded"]);
const everyComputer = () => window.__photoPollComputer ?? 2000;       // the computer looks for the phone's answer this often (milliseconds)
const everyPhone = () => window.__photoPollPhone ?? 5000;             // the phone looks for new requests this often

// ---------- the computer ----------

let runs = 0;       // a newer request (or leaving the page) stops the older one's looking

/** Ask the student's phone for a photo of this assignment's answer. `onPicture(id)` is called when the picture arrives. */
export async function askFromComputer(assignment, onPicture, panel) {
  const mine = ++runs;
  const old = [...panel.querySelectorAll(".photo-request[data-code]")].map(el => `<li data-state="superseded">קוד ${esc(el.dataset.code)}: ${WORDS.superseded}</li>`).join("")
    + (panel.querySelector(".old-requests")?.innerHTML || "");
  let request;
  try {
    request = await api("/api/photo-requests", { method: "POST", body: { assignment_id: assignment.id, device: deviceId() } });
  } catch (error) {
    panel.innerHTML = `<p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>`;
    return;
  }
  const draw = state => {
    panel.innerHTML = `<div class="photo-request" id="photo-request" data-code="${esc(request.code)}" data-state="${esc(state)}">
      <p>הקוד של הבקשה: <b class="code" id="request-code" dir="ltr">${esc(request.code)}</b></p>
      <p class="muted">פתחו את האפליקציה בטלפון. אם הקוד שם זהה, צלמו את התשובה.</p>
      <p class="status" id="request-state" role="status"><b>${WORDS[state] || state}</b></p></div>${old ? `<ul class="plain old-requests">${old}</ul>` : ""}`;
  };
  draw(request.state);
  while (mine === runs && !DONE.has(request.state)) {
    await new Promise(done => setTimeout(done, everyComputer()));
    if (mine !== runs) return;
    try { request = await api(`/api/photo-requests/${request.id}`); } catch { return; }
    draw(request.state);
  }
  if (mine === runs && request.state === "received" && request.picture_id) onPicture(request.picture_id);
}

/** Stop looking for an answer (the page was left). */
export const stopComputer = () => { runs += 1; };

// ---------- the phone ----------

let watching = null, handled = new Set(), shown = null;

function closeWindow() {
  document.getElementById("photo-window")?.remove();
  shown = null;
}

function windowHtml(request) {
  return `<div class="photo-window" id="photo-window" role="dialog" aria-modal="true" aria-labelledby="pw-title" data-request="${esc(request.id)}">
    <div class="sheet"><h3 id="pw-title">📷 בקשת צילום מהמחשב</h3>
      <p>הקוד שבמחשב: <b class="code" id="phone-code" dir="ltr">${esc(request.code)}</b></p>
      <p class="muted">אם הקוד זהה למה שרואים במחשב, צלמו את התשובה: ${fmt(request.assignment.title)}</p>
      <p class="status" id="phone-state" role="status"></p>
      <p><label class="button primary file" id="phone-camera">📷 צילום<input type="file" accept="image/*" capture="environment" hidden data-photo></label>
        <button type="button" id="phone-later">לא עכשיו</button></p></div></div>`;
}

async function takePhoto(request, file) {
  const status = document.getElementById("phone-state");
  status.textContent = "מעלים את התשובה…";
  try {
    await api(`/api/photo-requests/${request.id}/start`, { method: "POST" });
    await sendPicture(`/api/photo-requests/${request.id}/picture`, await prepare(file));
    handled.add(request.id);
    status.textContent = "התמונה נשלחה למחשב ✓";
    setTimeout(closeWindow, 1500);
  } catch (error) {
    status.textContent = (error instanceof ApiError && error.message) || "ההעלאה נכשלה. נסו שוב.";
  }
}

async function look() {
  let open;
  try { open = await api(`/api/photo-requests/open?device=${encodeURIComponent(deviceId())}`); } catch { return; }
  const wanted = open.find(r => !handled.has(r.id));
  if (!wanted) { if (shown && !document.getElementById("phone-state")?.textContent.includes("נשלחה")) closeWindow(); return; }
  if (shown === wanted.id) return;
  closeWindow();
  shown = wanted.id;
  document.body.insertAdjacentHTML("beforeend", windowHtml(wanted));
  const box = document.getElementById("photo-window");
  box.querySelector("[data-photo]").addEventListener("change", event => { const file = event.target.files[0]; event.target.value = ""; if (file) withBusy(box.querySelector("#phone-camera"), takePhoto(wanted, file)); });
  box.querySelector("#phone-later").addEventListener("click", () => { handled.add(wanted.id); closeWindow(); });
  box.querySelector("#phone-camera").focus?.();
}

/** Start looking for photo requests made by the student's other devices: now, on a timer, when the page comes back, and when a notification was tapped. */
export function startWatching() {
  if (watching) return;
  handled = new Set();
  const again = () => { look(); };
  const timer = () => { watching = setTimeout(async () => { await look(); if (watching) timer(); }, everyPhone()); };
  look();
  timer();
  const visible = () => { if (document.visibilityState === "visible") again(); };
  const message = event => { if (event.data?.type === "notified") again(); };
  document.addEventListener("visibilitychange", visible);
  navigator.serviceWorker?.addEventListener("message", message);
  startWatching.stop = () => {
    clearTimeout(watching); watching = null; closeWindow();
    document.removeEventListener("visibilitychange", visible);
    navigator.serviceWorker?.removeEventListener("message", message);
  };
}

export const stopWatching = () => { startWatching.stop?.(); };
window.addEventListener("mathly:leave", () => { stopComputer(); stopWatching(); });
