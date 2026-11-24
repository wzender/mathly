// The teacher's "שיחות עם ה־AI בתרגול" (practice_tutor.py): the class's students' conversations with the AI tutor on practice questions,
// the newest first, by student and by days. Each one: the student, the skill, the question, the day, whether it was asked before answering
// (that answer did not count for mastery), and the messages.
import { api } from "./api.js";
import { esc, fmt } from "./math.js";

let days = 7, who = "";

function item(c) {
  const asked = c.messages.filter(m => m.role === "student").length;
  return `<li class="card tt-chat" data-chat-id="${esc(c.id)}"><details><summary><b dir="ltr">${esc(c.student)}</b> · ${fmt(c.skill)} · ${esc(c.day)}
      · ${asked} ${asked === 1 ? "הודעה" : "הודעות"}${c.helped ? ` · <span class="tag" title="שאל/ה לפני שענה/תה: התשובה לא נספרה לשליטה">לפני התשובה</span>` : ""}</summary>
    ${c.question ? `<p class="muted pq-preview" dir="auto">${fmt(c.question)}</p>` : ""}
    <div class="pq-chat">${c.messages.map(m => `<p class="pq-msg ${m.role === "ai" ? "ai" : "me"}" dir="auto">${m.role === "ai" ? "🤖 " : "🧑‍🎓 "}${fmt(m.text)}</p>`).join("")}</div>
  </details></li>`;
}

async function load(section) {
  let data;
  try { data = await api(`/api/teaching/tutor-chats?days=${days}`); }
  catch (e) { section.innerHTML = `<h3>שיחות עם ה־AI בתרגול</h3><p class="muted" id="tt-error">${esc(e.message)}</p>`; return; }
  const students = [...new Set(data.chats.map(c => c.student))].sort();
  if (who && !students.includes(who)) who = "";
  const shown = data.chats.filter(c => !who || c.student === who);
  section.innerHTML = `<h3>שיחות עם ה־AI בתרגול</h3>
    <p class="muted">מה התלמידים שאלו את ה־AI על שאלות התרגול, ומה הוא ענה. "לפני התשובה": התלמיד/ה שאל/ה לפני שענה/תה, והתשובה לא נספרה לשליטה.</p>
    <p class="actions"><label>תלמיד/ה <select id="tt-who"><option value="">כולם</option>${students.map(s => `<option value="${esc(s)}"${s === who ? " selected" : ""}>${esc(s)}</option>`).join("")}</select></label>
      <label>תקופה <select id="tt-days">${[[1, "היום"], [7, "שבוע"], [30, "חודש"]].map(([d, l]) => `<option value="${d}"${d === days ? " selected" : ""}>${l}</option>`).join("")}</select></label></p>
    ${shown.length ? `<ul class="plain" id="tt-list">${shown.map(item).join("")}</ul>` : `<p class="muted" id="tt-none">אין שיחות בתקופה הזו.</p>`}`;
}

export async function mount(section) {
  await load(section);
  section.addEventListener("change", event => {
    if (event.target.id === "tt-days") { days = Number(event.target.value); load(section); }
    if (event.target.id === "tt-who") { who = event.target.value; load(section); }
  });
}
