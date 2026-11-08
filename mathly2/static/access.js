// "My access": the signed-in account's own roles and what each allows (open to every account).
import { esc } from "./math.js";
import { ROLE_ALLOWS, ROLE_NAMES, visibleRoles } from "./roles.js";

export async function show(me, view) {
  const held = visibleRoles(me.roles).filter(role => me.roles.includes(role));
  view(`<section class="card" id="my-access"><h2>ההרשאות שלי</h2>
    <p class="muted" dir="ltr">${esc(me.email)}</p>
    <ul class="plain">${held.map(role => `<li><b>${ROLE_NAMES[role]}</b><span>${ROLE_ALLOWS[role]}</span></li>`).join("")}</ul>
    ${me.roles.includes("developer") ? "" : `<p class="muted">תפקיד חדש נותן מנהל ההרשאות.</p>`}</section>`);
}
