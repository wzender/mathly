// 💬 The AI tutor's chat on a practice question (practice_tutor.py), shared by the skill's sheet (exercise.js) and the rounds (round.js).
// One conversation per question on screen: it starts again with the next question. Before the answer the tutor guides (and that answer
// does not count for mastery); after it, it explains. The teacher reads the conversations.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";

export class TutorChat {
  /** `url`: () => the address to post a message to (/api/skills/<id>/tutor or /api/rounds/<id>/tutor). */
  constructor(url) { this.url = url; this.key = null; this.log = []; this.open = false; }

  html(key, answered) {
    if (key !== this.key) { this.key = key; this.log = []; }
    return `<section class="ex-chat" id="ex-chat" aria-label="שיחה עם ה־AI"${this.open ? "" : " hidden"}>
    <h4>💬 שאלו את ה־AI</h4>
    <p class="muted" id="ex-chat-note">${answered ? "אפשר לשאול למה התשובה נכונה או איפה הטעות." : "ה־AI יעזור לחשוב, בלי לגלות את התשובה. שאלה לפני שעונים: התשובה לא תיספר לשליטה."} המורה רואה את השיחות.</p>
    <ol class="pq-chat" id="ex-chat-log">${this.log.map(m => `<li class="pq-msg ${m.role === "ai" ? "ai" : "me"}" dir="auto">${m.role === "ai" ? "🤖 " : ""}${fmt(m.text)}</li>`).join("")}</ol>
    <form id="ex-chat-form" class="pq-ask"><input id="ex-chat-text" maxlength="500" autocomplete="off" dir="auto" aria-label="השאלה שלכם ל־AI" placeholder="למשל: איך מתחילים?">
      <button type="submit" class="primary">שליחה</button></form>
    <p id="ex-chat-msg" role="status"></p></section>`;
  }

  /** Draw (or redraw) the panel inside `root`, after `anchor` when it is not there yet; "" (no question) removes it. */
  draw(root, key, answered, anchor) {
    const old = root.querySelector("#ex-chat"), html = key ? this.html(key, answered) : "";
    if (old) old.outerHTML = html;
    else if (html && anchor) anchor.insertAdjacentHTML("afterend", html);
    root.querySelector("[data-chat]")?.setAttribute("aria-expanded", String(this.open));
  }

  /** Send a message; redraws the panel with the reply. Returns the server's answer ({reply, helped, left}) or null. */
  async send(root, text, answered) {
    const key = this.key, msg = root.querySelector("#ex-chat-msg"), button = root.querySelector("#ex-chat-form button");
    button.disabled = true;
    msg.textContent = "🤖 חושב…";
    try {
      const got = await api(this.url(), { method: "POST", body: { question_key: key, message: text, history: this.log.slice(-12) } });
      if (this.key !== key) return null;
      this.log.push({ role: "student", text }, { role: "ai", text: got.reply });
      this.draw(root, key, answered());
      root.querySelector("#ex-chat-msg").textContent = got.left <= 5 ? `נשארו ${got.left} שאלות ל־AI היום` : "";
      root.querySelector("#ex-chat-log")?.lastElementChild?.scrollIntoView({ block: "nearest" });
      root.querySelector("#ex-chat-text")?.focus({ preventScroll: true });
      return got;
    } catch (error) {
      button.disabled = false;
      msg.innerHTML = `<span class="error">${esc(error.message || "ה־AI לא ענה")}</span>`;
      return null;
    }
  }

  reset() { this.key = null; this.log = []; this.open = false; }
}

export const button = open => `<button type="button" class="ex-help ex-tutor" data-chat aria-label="שאלו את ה־AI על השאלה" title="שאלו את ה־AI" aria-expanded="${open}">💬</button>`;
