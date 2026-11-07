// App shell: sign-in, then the screen for the signed-in person's role.
import { api, ApiError } from "./api.js";
import { esc } from "./math.js";
import * as session from "./session.js";

const CFG = JSON.parse(document.getElementById("config").textContent);
const app = document.getElementById("app");
const nav = document.getElementById("nav");

export const view = html => { app.innerHTML = html; };

function showSignIn(message = "") {
  nav.innerHTML = "";
  view(`<section class="card" id="signin"><h2>כניסה</h2>
    ${message ? `<p class="error" role="alert">${esc(message)}</p>` : ""}
    ${CFG.devSignIn
      ? `<p class="muted">כניסת פיתוח (dev only): ללא Supabase, כל כתובת מייל מתקבלת.</p>
         <form id="dev"><label for="email">מייל</label><input id="email" type="email" required autocomplete="email" dir="ltr">
         <p><button class="primary" type="submit">כניסה</button></p></form>`
      : `<p><button class="primary" id="google" type="button">כניסה עם Google</button></p>`}</section>`);
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

function header(me) {
  nav.innerHTML = `<span class="muted" dir="ltr">${esc(me.email)}</span> <button type="button" id="out">יציאה</button>`;
  document.getElementById("out").addEventListener("click", () => signOutAndShow());
}

async function boot() {
  view(`<section class="card"><p class="muted">טוען…</p></section>`);
  try {
    await session.init(CFG);
  } catch {
    return showSignIn("לא הצלחנו לטעון את שירות ההתחברות. בדקו את החיבור לרשת ונסו שוב.");
  }
  if (!await session.token()) return showSignIn();
  try {
    const me = await api("/api/me");
    header(me);
    const screen = await import(me.role === "teacher" ? "./teacher.js" : "./student.js");
    await screen.show(me, view);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return signOutAndShow("ההתחברות פגה, יש להיכנס שוב");
    view(`<section class="card"><p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p></section>`);
  }
}

boot();
