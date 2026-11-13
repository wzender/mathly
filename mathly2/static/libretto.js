// The libretto view (ליברטו) of the developer's prompter: an opera's words one line at a time, Italian above English, on a black
// screen dim enough not to disturb the people sitting nearby. Nothing moves by itself: the reader moves on with the music.
//
// A libretto is a prompter text whose first line is "Libretto" (or "ליברטו"). After it, each line is one of:
//   Act 1 — In the garret            a heading (Act / Atto / Quadro / Scene / Scena): shown on its own, as a cue
//   RODOLFO: Italian words || English words   one cue: who sings (optional), the Italian, and after "||" the English
//   (a stage direction) || (its English)      a cue in parentheses is shown smaller, as a direction
// Empty lines and lines starting with "#" are left out.
//
// Keys: Space / → / Page Down / Enter next · ← / Page Up / Backspace back · Home first line · End last line ·
// ↑ / ↓ brighter / dimmer · + / − text size · Esc close. A tap on the screen's right two thirds is next, on the left third back
// (in this right-to-left app, the start side is right; the Italian text reads left to right, so "back" is the left edge).
// The place in each libretto, the brightness and the size are kept in this browser, so closing by mistake loses nothing.

const KEY = "mathly2.libretto";
const HEADING = /^(act|atto|quadro|scene|scena|parte|part)\b/i;

/** Is this text a libretto? */
export const isLibretto = text => /^\s*(libretto|ליברטו)\s*$/i.test(String(text || "").split("\n").find(l => l.trim()) || "");

/** The cues of a libretto: [{kind: "heading"|"line"|"direction", who, it, en}]. */
export function parse(text) {
  const lines = String(text || "").split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("#"));
  if (lines.length && isLibretto(lines[0])) lines.shift();
  return lines.map(line => {
    const [left, ...rest] = line.split("||");
    const en = rest.join("||").trim();
    let it = left.trim(), who = "";
    if (HEADING.test(it)) return { kind: "heading", who: "", it, en };
    const named = it.match(/^([^:()]{1,80}):\s*(.*)$/);
    if (named && named[1] === named[1].toUpperCase() && /\p{L}/u.test(named[1])) { who = named[1].trim(); it = named[2].trim(); }
    return { kind: /^\(.*\)$/.test(it) ? "direction" : "line", who, it, en };
  }).filter(c => c.it || c.en);
}

const CSS = `
.mxl{position:fixed;inset:0;z-index:2147483000;background:#000;color:#000;cursor:none;-webkit-user-select:none;user-select:none;touch-action:manipulation;
  display:flex;flex-direction:column;justify-content:center;align-items:center;padding:4vh 6vw;font-family:Georgia,"Times New Roman",serif;--b:.6;--s:1}
.mxl-cue{max-width:1100px;width:100%;text-align:center;direction:ltr;opacity:var(--b)}
.mxl-who{color:#a0662a;font:600 calc(15px*var(--s))/1.2 system-ui,sans-serif;letter-spacing:.12em;margin-bottom:.5em;min-height:1.2em}
.mxl-it{color:#e0952f;font-size:calc(34px*var(--s));line-height:1.3;font-weight:600}
.mxl-en{color:#b98040;font-size:calc(25px*var(--s));line-height:1.3;font-style:italic;margin-top:.45em}
.mxl-cue.heading .mxl-it{font-size:calc(24px*var(--s));letter-spacing:.08em;text-transform:uppercase;color:#c48530}
.mxl-cue.heading .mxl-en{font-size:calc(19px*var(--s))}
.mxl-cue.direction .mxl-it{font-size:calc(21px*var(--s));font-style:italic;font-weight:400;color:#b98040}
.mxl-cue.direction .mxl-en{font-size:calc(18px*var(--s))}
.mxl-next{position:absolute;inset-inline:6vw;bottom:3vh;text-align:center;direction:ltr;color:#6a4518;font-size:calc(16px*var(--s));opacity:calc(var(--b)*.6);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mxl-where{position:absolute;top:2vh;inset-inline-end:3vw;color:#6a4518;font:12px system-ui,sans-serif;direction:ltr;opacity:calc(var(--b)*.5)}
@media (prefers-reduced-motion:no-preference){.mxl-cue{animation:mxl-in .18s ease}}
@keyframes mxl-in{from{opacity:0}to{opacity:var(--b)}}
`;

let root = null, cues = [], at = 0, id = "", lock = null, prefs = { b: .6, s: 1, at: {} };

function loadPrefs() { try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch { /* nothing kept */ } }
function savePrefs() { try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* private window */ } }
function hash(text) { let h = 0; for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0; return String(h); }
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function draw() {
  const c = cues[at], n = cues[at + 1];
  root.style.setProperty("--b", prefs.b);
  root.style.setProperty("--s", prefs.s);
  root.innerHTML = `<div class="mxl-where">${at + 1} / ${cues.length}</div>
    <div class="mxl-cue ${c.kind}" lang="it"><div class="mxl-who">${esc(c.who)}</div><div class="mxl-it">${esc(c.it)}</div>
      ${c.en ? `<div class="mxl-en" lang="en">${esc(c.en)}</div>` : ""}</div>
    <div class="mxl-next" lang="it">${n ? esc((n.who ? n.who + ": " : "") + n.it) : ""}</div>`;
  prefs.at[id] = at; savePrefs();
}

const go = to => { const next = Math.max(0, Math.min(cues.length - 1, to)); if (next !== at) { at = next; draw(); } };
const brighter = d => { prefs.b = Math.round(Math.max(.1, Math.min(1, prefs.b + d)) * 100) / 100; draw(); };
const bigger = d => { prefs.s = Math.round(Math.max(.6, Math.min(2.5, prefs.s + d)) * 100) / 100; draw(); };

function onKey(e) {
  const k = e.key;
  if ([" ", "ArrowRight", "PageDown", "Enter"].includes(k)) go(at + 1);
  else if (["ArrowLeft", "PageUp", "Backspace"].includes(k)) go(at - 1);
  else if (k === "Home") go(0);
  else if (k === "End") go(cues.length - 1);
  else if (k === "ArrowUp") brighter(.05);
  else if (k === "ArrowDown") brighter(-.05);
  else if (k === "+" || k === "=") bigger(.1);
  else if (k === "-") bigger(-.1);
  else if (k === "Escape") close();
  else return;
  e.preventDefault(); e.stopPropagation();
}

function onTap(e) { go(e.clientX < innerWidth / 3 ? at - 1 : at + 1); }

async function awake() { try { lock = await navigator.wakeLock?.request("screen"); } catch { lock = null; } }
const onVisible = () => { if (root && document.visibilityState === "visible") awake(); };

/** Show a libretto text. Returns false when it has no cues. */
export function open(text) {
  cues = parse(text);
  if (!cues.length) return false;
  close();
  loadPrefs();
  id = hash(text);
  at = Math.min(prefs.at[id] || 0, cues.length - 1);
  if (!document.getElementById("mxl-css")) {
    const el = document.createElement("style"); el.id = "mxl-css"; el.textContent = CSS; document.head.appendChild(el);
  }
  root = document.createElement("div");
  root.className = "mxl"; root.setAttribute("role", "dialog"); root.setAttribute("aria-modal", "true"); root.setAttribute("aria-label", "ליברטו");
  root.tabIndex = -1;
  document.body.appendChild(root);
  draw();
  root.focus();
  document.addEventListener("keydown", onKey, true);
  root.addEventListener("click", onTap);
  document.addEventListener("visibilitychange", onVisible);
  root.requestFullscreen?.().catch(() => { /* not allowed here: the black page still covers the screen */ });
  awake();
  return true;
}

export function close() {
  if (!root) return;
  document.removeEventListener("keydown", onKey, true);
  document.removeEventListener("visibilitychange", onVisible);
  root.remove(); root = null;
  lock?.release?.().catch(() => {}); lock = null;
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
}

export const isOpen = () => !!root;
