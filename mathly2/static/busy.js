// A button whose action takes time shows it. One hook for the whole app: the button (or the form's submit button) that was just pressed is
// remembered, and every request made right after that marks it busy if the answer takes longer than about a third of a second: a spinner, and
// a second press does nothing, until the request ends. Quick actions never flash it. Uploads (a file chooser's label) use `withBusy` directly.
const DELAY = 300;                 // milliseconds before the button shows it is working
const WINDOW = 600;                // a request counts as the button's when it starts within this time of the press
const SKIP = ".ex-choice, .qz-choice, .mx-board, [data-board-toggle]";      // these show their own state

let pressed = null, pressedAt = 0;
const counts = new WeakMap();

function target(event) {
  const el = event.target?.closest?.("button, .button, [type=submit]");
  return el && !el.closest(SKIP) ? el : null;
}

function mark(el) {
  counts.set(el, (counts.get(el) || 0) + 1);
  el.classList.add("busy");
  el.setAttribute("aria-busy", "true");
}

function unmark(el) {
  const left = (counts.get(el) || 1) - 1;
  counts.set(el, left);
  if (left <= 0) { el.classList.remove("busy"); el.removeAttribute("aria-busy"); }
}

document.addEventListener("click", event => {
  const el = target(event);
  if (!el) return;
  if (el.classList.contains("busy")) { event.preventDefault(); event.stopImmediatePropagation(); return; }     // a second press while it works
  pressed = el;
  pressedAt = performance.now();
}, true);

document.addEventListener("submit", event => {
  if (event.submitter?.classList.contains("busy")) { event.preventDefault(); event.stopImmediatePropagation(); return; }
  if (event.submitter && !event.submitter.closest(SKIP)) { pressed = event.submitter; pressedAt = performance.now(); }
}, true);

/** Follow a promise for a button: after a third of a second the button shows it is working. Returns the promise. */
export function withBusy(el, promise) {
  if (!el) return promise;
  const timer = setTimeout(() => { if (el.isConnected) { el.dataset.busyOn = "1"; mark(el); } }, DELAY);
  const done = () => { clearTimeout(timer); if (el.dataset.busyOn) { delete el.dataset.busyOn; unmark(el); } };
  promise.then(done, done);
  return promise;
}

/** Follow a request for the button that was just pressed (if one was pressed a moment ago). Used by `api()`. */
export function track(promise) {
  const el = performance.now() - pressedAt < WINDOW && pressed?.isConnected ? pressed : null;
  return withBusy(el, promise);
}
