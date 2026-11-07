import { api } from "./api.js";
import { esc } from "./math.js";

export async function show(me, view) {
  if (!me.class) {
    view(`<section class="card" id="no-class"><h2>עוד לא בכיתה</h2>
      <p>המורה עוד לא הוסיפה אותך לכיתה. בקשו מהמורה להוסיף את כתובת המייל שבה נכנסתם:</p>
      <p dir="ltr"><b>${esc(me.email)}</b></p></section>`);
    return;
  }
  const lessons = await api("/api/lessons");
  view(`<section class="card"><h2>שלום</h2><p class="muted">הכיתה: ${esc(me.class.name)}. השיעורים (${lessons.length}) יפתחו כאן בהמשך.</p>
    <ul class="plain">${lessons.map(l => `<li><span>${esc(l.name)}</span><span class="muted">${l.skills.length} מיומנויות</span></li>`).join("")}</ul></section>`);
}
