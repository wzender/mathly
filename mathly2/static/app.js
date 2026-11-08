// App shell: the sign-in page, then the home of the role the person chose. A person with several roles gets a chip for each.
import { api, ApiError } from "./api.js";
import { esc } from "./math.js";
import { ROLE_NAMES, visibleRoles } from "./roles.js";
import { clearRoute, leaveScreen } from "./router.js";
import * as session from "./session.js";
import { owl } from "./sky.js";

const CFG = JSON.parse(document.getElementById("config").textContent);
const app = document.getElementById("app");
const nav = document.getElementById("nav");
const ROLE_KEY = "mathly2.role";
const SCREENS = { student: "./student.js", teacher: "./teacher.js", manager: "./manager.js", admin: "./admin.js", developer: "./developer.js" };

export const view = html => { app.innerHTML = html; };

const remembered = () => { try { return localStorage.getItem(ROLE_KEY) || ""; } catch { return ""; } };
const remember = role => { try { localStorage.setItem(ROLE_KEY, role); } catch { /* private window */ } };

function showSignIn(message = "", canRetry = false) {
  leaveScreen();
  nav.innerHTML = "";
  view(`<section class="signin" id="signin"><img class="logo" src="/static/logo.svg" alt="לומדים בכיף" width="489" height="225">${owl(72)}
    <p class="status ${message ? "error" : ""}" ${message ? 'role="alert"' : ""}>${esc(message || "יש להיכנס כדי לפתוח את מסלול המתמטיקה.")}</p>
    ${canRetry ? `<p><button type="button" class="primary" id="retry">נסו שוב</button></p>` : ""}
    ${CFG.devSignIn
      ? `<p class="hint">כניסת פיתוח (dev only): ללא Supabase, כל כתובת מייל מתקבלת.</p>
         <form id="dev"><label for="email">מייל</label><input id="email" type="email" required autocomplete="email" dir="ltr">
         <p><button class="pill" type="submit">כניסה</button></p></form>`
      : canRetry ? "" : `<p><button class="pill" id="google" type="button">כניסה עם Google</button></p>`}</section>`);
  document.getElementById("retry")?.addEventListener("click", () => boot());
  document.getElementById("google")?.addEventListener("click", () => session.signInWithGoogle());
  document.getElementById("dev")?.addEventListener("submit", event => {
    event.preventDefault();
    session.signInDev(document.getElementById("email").value);
    boot();
  });
}

async function signOutAndShow(message) {
  await session.signOut();
  showSignIn(message);
}

function header(me, current) {
  const roles = visibleRoles(me.roles);
  nav.innerHTML = `<span class="muted" dir="ltr">${esc(me.email)}</span>
    ${roles.length > 1 ? `<span class="roles" role="group" aria-label="תפקיד">${roles.map(role =>
      `<button type="button" data-role="${role}" aria-pressed="${role === current}">${ROLE_NAMES[role]}</button>`).join("")}</span>` : ""}
    <button type="button" id="access">ההרשאות שלי</button> <button type="button" id="out">יציאה</button>`;
  document.getElementById("out").addEventListener("click", () => signOutAndShow());
  document.getElementById("access").addEventListener("click", async () => {
    clearRoute();
    nav.querySelectorAll("[data-role]").forEach(b => b.setAttribute("aria-pressed", "false"));
    await (await import("./access.js")).show(me, view);
  });
  nav.querySelectorAll("[data-role]").forEach(button => button.addEventListener("click", () => open(me, button.dataset.role)));
}

async function open(me, role, { keepAddress = false } = {}) {
  remember(role);
  clearRoute({ keepAddress });
  header(me, role);
  view(`<section class="card"><p class="muted">טוען…</p></section>`);
  try {
    await (await import(SCREENS[role])).show(me, view);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return signOutAndShow("ההתחברות פגה, יש להיכנס שוב");
    view(`<section class="card"><p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p></section>`);
  }
}

async function boot() {
  view(`<section class="card"><p class="muted">טוען…</p></section>`);
  try {
    await session.init(CFG);
  } catch {
    return showSignIn("לא הצלחנו להתחבר לשירות ההתחברות. בדקו את החיבור לרשת ונסו שוב.", true);
  }
  if (!await session.token()) return showSignIn();
  try {
    const me = await api("/api/me");
    const roles = visibleRoles(me.roles);
    await open(me, roles.includes(remembered()) ? remembered() : roles[0], { keepAddress: true });   // the first screen honours a link
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return signOutAndShow("ההתחברות פגה, יש להיכנס שוב");
    if (error instanceof ApiError && error.status === 503) return showSignIn("שירות ההתחברות לא זמין כרגע.", true);
    view(`<section class="card"><p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p></section>`);
  }
}

boot();
