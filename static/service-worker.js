/* Mathly's service worker: push notifications only (app/push.py). It has no fetch handler and keeps no cache.
   An older version served /static/ from its own cache forever; activating this one deletes those caches. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil((async () => {
  await Promise.all((await caches.keys()).map(key => caches.delete(key)));
  await self.clients.claim();
})()));

// a photo request from the computer (or any later message): shown even when the app is closed
self.addEventListener("push", event => {
  let msg = {};
  try { msg = event.data ? event.data.json() : {}; } catch { msg = { body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(msg.title || "לומדים בכיף", {
    body: msg.body || "", tag: msg.tag || "mathly", renotify: true, requireInteraction: false,
    lang: "he", dir: "rtl",
    icon: "/static/icons/icon-192.png", badge: "/static/icons/icon-192.png",
    data: { url: msg.url || "/" }
  }));
});

// a tap: the app already open is brought forward and told to look for requests now; otherwise it is opened
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(wins => {
    const app = wins.find(w => new URL(w.url).origin === self.location.origin && !new URL(w.url).pathname.startsWith("/static/"));
    if (app) { app.postMessage({ type: "notified", url }); return app.focus(); }
    return self.clients.openWindow(url);
  }));
});
