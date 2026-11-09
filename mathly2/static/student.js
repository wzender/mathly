// The student's screens, switched by the address after "#": "/" the subjects, "/subject/math" the home, "/subject/math/path" the path, "/skill/<id>" a skill's sheet over the path, "/collection".
import { esc } from "./math.js";
import * as exercise from "./exercise.js";
import * as home from "./home.js";
import * as phone from "./phone.js";
import * as path from "./path.js";
import * as quiz from "./quiz.js";
import { route as onRoute } from "./router.js";

export async function show(me, view) {
  if (!me.classes.length && me.roles.every(r => r === "student")) {
    view(`<section class="card" id="no-class"><h2>עוד לא בכיתה</h2>
      <p>עוד לא הוסיפו אותך לכיתה. בקשו מהמורה או ממנהל הכיתות להוסיף את כתובת המייל שבה נכנסתם:</p>
      <p dir="ltr"><b>${esc(me.email)}</b></p></section>`);
    return;
  }
  let lastSkill = "";
  async function route() {
    phone.stopComputer();                                      // a page that was waiting for the phone's photo is left
    const raw = location.hash.replace(/^#/, "");
    const where = raw.startsWith("/") ? raw : "/";          // no address, or the sign-in service's "#access_token=…": the first screen
    try {
      if (where.startsWith("/skill/")) {
        quiz.close();
        lastSkill = decodeURIComponent(where.slice(7));
        if (!document.getElementById("path")) await path.show(view);       // a link or a reload: the path first, then the sheet over it
        await exercise.open(lastSkill);
      } else if (where.startsWith("/quiz/")) {
        exercise.close();
        const [lesson, attempt] = where.slice(6).split("/").map(decodeURIComponent);
        if (!document.getElementById("path")) await path.show(view);                  // a link or a reload: the path first, then the sheet
        if (attempt) await quiz.open(attempt); else await quiz.start(lesson);       // the node starts or resumes; the address then names the attempt
      } else if (where === "/submissions") {
        exercise.close(); quiz.close();
        await (await import("./submissions.js")).show(view);
      } else if (where.startsWith("/assignment/")) {
        exercise.close(); quiz.close();
        await (await import("./assignment.js")).show(view, decodeURIComponent(where.slice(12)));
      } else if (where.startsWith("/exam/") || where.startsWith("/sim/")) {
        exercise.close();
        const [kind, ...rest] = where.slice(1).split("/").map(decodeURIComponent);
        const [test, second, third] = rest;
        const attempt = kind === "exam" ? third : second;
        if (!document.getElementById("path") && !document.getElementById("test-card")) await (await import("./testcard.js")).show(view, test);   // a link or a reload: the test's card first
        if (attempt) await quiz.open(attempt);
        else if (kind === "exam") await quiz.startExam(test, second);
        else await quiz.startSimulation(test);
      } else if (where.startsWith("/test/")) {
        exercise.close(); quiz.close();
        await (await import("./testcard.js")).show(view, decodeURIComponent(where.slice(6)));
      } else if (where === "/grades") {
        exercise.close(); quiz.close();
        await (await import("./grades.js")).show(view);
      } else if (where === "/") {
        exercise.close(); quiz.close();
        await path.showSubjects(view);
      } else if (where === "/subject/math") {
        exercise.close(); quiz.close();
        await home.show(view);
      } else if (where === "/collection") {
        exercise.close(); quiz.close();
        await (await import("./collection.js")).show(view);
      } else {                                                              // "/subject/math/path", and any unknown address
        const wasOpen = exercise.isOpen() || quiz.isOpen();
        exercise.close(); quiz.close();
        await path.show(view, { scroll: !wasOpen });                       // closing a sheet refreshes the stars and keeps the place
        if (wasOpen && lastSkill) document.querySelector(`.star[data-skill="${CSS.escape(lastSkill)}"]`)?.focus({ preventScroll: true });
      }
    } catch (error) {
      if (error.status === 401) throw error;
      view(`<section class="card"><p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p></section>`);
    }
    if (!where.startsWith("/skill/") && !exercise.isOpen()) { /* the path scrolls itself */ }
  }
  onRoute(route);
  phone.startWatching();                                       // a photo request from the student's computer shows here when this is the phone
  await route();
}
