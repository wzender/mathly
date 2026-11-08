// Comets on screen: the crossing comet (or, with reduced motion, one still button), the catch, and the card with the fact.
import { api } from "./api.js";
import { esc } from "./math.js";
import { cometCard, cometSvg } from "./sky.js";

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** A small dialog with a comet's card and fact (or a hint for one not caught yet). Closed by its button or Escape; focus returns. */
export function showCard(comet, { heading = "שביט" } = {}) {
  const back = document.activeElement;
  const box = document.createElement("div");
  box.className = "comet-dialog";
  box.innerHTML = `<div class="scrim" data-close></div><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="comet-h">
    <h2 id="comet-h">${esc(heading)}</h2>
    ${comet.caught === false ? `<div class="comet-card"><span class="sym">?</span><b>עוד לא נתפס</b></div>
      <p>שביטים חולפים לפעמים על המסך בזמן תרגול. מי שלוחץ עליהם בזמן תופס אותם.</p>`
      : `${cometCard(comet)}<p>${esc(comet.fact)}</p>`}
    <p><button type="button" class="primary" data-close>סגירה</button></p></div>`;
  document.body.append(box);
  const close = () => { box.remove(); document.removeEventListener("keydown", onKey); back?.focus?.(); };
  const onKey = event => { if (event.key === "Escape") close(); };
  box.addEventListener("click", event => { if (event.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", onKey);
  box.querySelector("button").focus();
  return close;
}

/** A comet is due: it crosses `host` for about 4 seconds, or, with reduced motion, one still button stays until the next question.
 *  A tap catches it (the server picks which one) and shows the card. `onDone` runs when it is caught or gone. */
export function cross({ feedback, onDone = () => {} } = {}) {
  document.getElementById("comet")?.remove();
  const button = document.createElement("button");
  button.type = "button";
  button.id = "comet";
  const still = reducedMotion();
  button.className = still ? "comet still" : "comet";
  button.setAttribute("aria-label", "שביט! לחצו כדי לתפוס אותו");
  button.innerHTML = still ? "☄ שביט!" : cometSvg();
  (still ? feedback : document.body).append(button);            // a still button sits under the feedback; a moving comet crosses the whole screen
  const gone = () => { if (button.isConnected) { button.remove(); onDone(false); } };
  button.addEventListener("animationend", gone);
  button.addEventListener("click", async () => {
    button.remove();
    try {
      const { comet } = await api("/api/comets/catch", { method: "POST" });
      showCard({ ...comet, caught: true }, { heading: "תפסתם שביט נדיר!" });
      onDone(true);
    } catch { onDone(false); }
  });
  return button;
}

/** Take a crossing comet away (the sheet closed or the person left). */
export const clear = () => document.getElementById("comet")?.remove();
