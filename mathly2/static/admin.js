// The admin's screen: the accounts the app knows, with their roles; give a role to any email (even one that never signed in) or take it away.
import { api } from "./api.js";
import { esc } from "./math.js";
import { ROLE_NAMES } from "./roles.js";

const GRANTABLE = ["student", "teacher", "manager", "admin"];
let draw;

async function showAccounts(message = "", error = "") {
  const accounts = await api("/api/accounts");
  draw(`<section id="accounts"><h2>תפקידים</h2>
    <section class="card"><h3>מתן תפקיד</h3>
      <p class="muted">אפשר להקליד גם כתובת שעוד לא נכנסה לאפליקציה: התפקיד יחול מהכניסה הראשונה שלה. שינוי תפקיד נקלט תוך כחצי דקה.</p>
      <form id="give"><label for="g-email">מייל</label><input id="g-email" type="email" dir="ltr" required autocomplete="off">
        <label for="g-role">תפקיד</label><select id="g-role">${GRANTABLE.map(r => `<option value="${r}">${ROLE_NAMES[r]}</option>`).join("")}</select>
        ${error ? `<p class="error" role="alert">${esc(error)}</p>` : ""}${message ? `<p role="status">${esc(message)}</p>` : ""}
        <p><button class="primary" type="submit">מתן התפקיד</button></p></form></section>
    <div class="tablewrap"><table class="data"><thead><tr><th>חשבון</th><th>תפקידים שניתנו</th><th>מההגדרות</th></tr></thead>
      <tbody>${accounts.map(a => `<tr data-email="${esc(a.email)}"><td dir="ltr">${esc(a.email)}</td>
        <td>${a.roles.map(r => `<span class="tag">${ROLE_NAMES[r]} <button type="button" data-take="${r}" aria-label="הסרת התפקיד ${ROLE_NAMES[r]} מ־${esc(a.email)}">✕</button></span>`).join(" ") || '<span class="muted">—</span>'}</td>
        <td>${a.from_settings.map(r => `<span class="tag">${ROLE_NAMES[r]}</span>`).join(" ") || '<span class="muted">—</span>'}</td></tr>`).join("")}</tbody></table></div></section>`);
  document.getElementById("give").addEventListener("submit", async event => {
    event.preventDefault();
    const email = document.getElementById("g-email").value.trim(), role = document.getElementById("g-role").value;
    try {
      await api(`/api/accounts/${encodeURIComponent(email)}/roles/${role}`, { method: "POST" });
      await showAccounts(`${email}: ניתן התפקיד ${ROLE_NAMES[role]}.`);
    } catch (e) { await showAccounts("", e.message); }
  });
  document.querySelector("#accounts tbody").addEventListener("click", async event => {
    const role = event.target.closest("[data-take]")?.dataset.take;
    if (!role) return;
    const email = event.target.closest("tr").dataset.email;
    try {
      await api(`/api/accounts/${encodeURIComponent(email)}/roles/${role}`, { method: "DELETE" });
      await showAccounts(`${email}: התפקיד ${ROLE_NAMES[role]} הוסר.`);
    } catch (e) { await showAccounts("", e.message); }
  });
}

export async function show(me, view) {
  draw = view;
  await showAccounts();
}
