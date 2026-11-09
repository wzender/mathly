// Notifications for photo requests, on a phone only: a switch on home. The service worker shows the notification when the app is closed and, on a
// tap, tells the open app to look for requests. Without a push key on the server the switch is not offered.
import { api } from "./api.js";
import { isTouch } from "./media.js";

const bytes = base64 => Uint8Array.from(atob(base64.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - base64.length % 4) % 4)), c => c.charCodeAt(0));

/** Draw the switch into `box` (nothing at all on a computer, without notification support, or when the server has no key). */
export async function setup(box) {
  if (!isTouch() || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;
  let server;
  try { server = await api("/api/push/key"); } catch { return; }
  if (!server.enabled) return;
  let registration;
  try { registration = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" }); } catch { return; }
  let subscription = await registration.pushManager.getSubscription();
  const draw = (note = "") => {
    box.hidden = false;
    box.innerHTML = `<h3>התראות</h3><p class="muted">כשהמחשב מבקש תמונה של תשובה, הטלפון יקבל התראה גם כשהאפליקציה סגורה. באייפון זה עובד רק מהאפליקציה שהוספתם למסך הבית.</p>
      <p>${subscription ? `<span class="tag" id="notif-state"><span aria-hidden="true">✓</span> התראות פועלות</span> <button type="button" id="notif-off">כיבוי</button>`
        : `<button type="button" class="primary" id="notif-on">הפעלת התראות</button>`}</p><p class="muted" id="notif-note" role="status">${note}</p>`;
    box.querySelector("#notif-on")?.addEventListener("click", enable);
    box.querySelector("#notif-off")?.addEventListener("click", disable);
  };
  async function enable() {
    try {
      if (await Notification.requestPermission() !== "granted") return draw("ההתראות חסומות בדפדפן. אפשר לאשר אותן בהגדרות.");
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes(server.key) });
      await api("/api/push/subscribe", { method: "POST", body: subscription.toJSON() });
      draw();
    } catch (error) { subscription = null; draw(error.message || "לא הצלחנו להפעיל התראות."); }
  }
  async function disable() {
    const endpoint = subscription?.endpoint;
    try { await subscription?.unsubscribe(); if (endpoint) await api("/api/push/unsubscribe", { method: "POST", body: { endpoint } }); } catch { /* it is off here either way */ }
    subscription = null;
    draw();
  }
  draw();
}
