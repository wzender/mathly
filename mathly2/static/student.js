// The student's screens, switched by the address after "#": "/" the subjects, "/subject/<id>" a subject's home, "/subject/<id>/path"
// its path, "/skill/<id>" a skill's sheet over its subject's path, "/collection". The subject of a skill, a quiz or a test opened by a
// link is asked from the server, so a reload lands on the right subject's path.
import { api } from "./api.js";
import { esc } from "./math.js";
import { setSubject } from "./ui.js";
import * as exercise from "./exercise.js";
import * as home from "./home.js";
import * as phone from "./phone.js";
import * as path from "./path.js";
import * as quiz from "./quiz.js";
import * as lessonRound from "./round.js";
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
    if (!where.startsWith("/round/")) lessonRound.close();
    try {
      if (where.startsWith("/round/")) {                                     // a lesson's round over the home (a link or a reload: the home first)
        exercise.close(); quiz.close();
        const data = await lessonRound.start(decodeURIComponent(where.slice(7)));
        setSubject(data.subject_id);
        if (!document.getElementById("lesson-map")) await home.show(view);
        await lessonRound.show(data);
      } else if (where.startsWith("/skill/")) {
        quiz.close();
        lastSkill = decodeURIComponent(where.slice(7));
        if (!document.getElementById("path")) {                            // a link or a reload: the skill's subject's path first, then the sheet
          setSubject((await api(`/api/skills/${encodeURIComponent(lastSkill)}`)).subject_id);
          await path.show(view);
        }
        await exercise.open(lastSkill);
      } else if (where.startsWith("/quiz/")) {
        exercise.close();
        const [lesson, attempt] = where.slice(6).split("/").map(decodeURIComponent);
        if (!document.getElementById("path")) {                                       // a link or a reload: the lesson's subject's path first
          setSubject((await api(`/api/lessons/${encodeURIComponent(lesson)}/quiz`)).subject_id);
          await path.show(view);
        }
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
        const allSkills = kind === "exam" ? third === "all" : second === "all";      // "/exam/<test>/<n>/all", "/sim/<test>/all": not an attempt id
        const attempt = allSkills ? undefined : kind === "exam" ? third : second;
        if (!document.getElementById("path") && !document.getElementById("test-card")) await (await import("./testcard.js")).show(view, test);   // a link or a reload: the test's card first
        if (attempt) await quiz.open(attempt);
        else if (kind === "exam") await quiz.startExam(test, second, allSkills);
        else await quiz.startSimulation(test, allSkills);
      } else if (where.startsWith("/test/")) {
        exercise.close(); quiz.close();
        await (await import("./testcard.js")).show(view, decodeURIComponent(where.slice(6)));
      } else if (where === "/review") {
        exercise.close(); quiz.close();
        await (await import("./review.js")).show(view);
      } else if (where === "/grades") {
        exercise.close(); quiz.close();
        await (await import("./grades.js")).show(view);
      } else if (where === "/") {
        exercise.close(); quiz.close();
        await path.showSubjects(view);
      } else if (/^\/subject\/[^/]+$/.test(where)) {
        exercise.close(); quiz.close();
        setSubject(decodeURIComponent(where.slice(9)));
        await home.show(view);
      } else if (where === "/collection") {
        exercise.close(); quiz.close();
        await (await import("./collection.js")).show(view);
      } else {                                                              // "/subject/<id>/path", and any unknown address
        const named = where.match(/^\/subject\/([^/]+)\/path$/);
        if (named) setSubject(decodeURIComponent(named[1]));
        const wasOpen = exercise.isOpen() || quiz.isOpen();
        exercise.close(); quiz.close();
        await path.show(view, { scroll: !wasOpen });                       // closing a sheet refreshes the stars and keeps the place
        if (wasOpen && lastSkill) document.querySelector(`.star[data-skill="${CSS.escape(lastSkill)}"]`)?.focus({ preventScroll: true });
      }
    } catch (error) {
      if (error.status === 401) throw error;
      const sim = where.match(/^\/sim\/([^/]+)$/);                         // the simulation with nothing started yet: a bypass on all the material
      const bypass = sim && error.status === 409 && /עוד לא התחלתם/.test(error.message || "")
        ? `<p><a class="button primary" id="sim-bypass" href="#/sim/${sim[1]}/all">להתחיל בכל זאת, על כל החומר</a></p>
           <p class="muted">מבחן סימולציה עושים פעם אחת, והציון נשמר.</p>` : "";
      view(`<section class="card"><p class="error" role="alert">${esc(error.message || "משהו השתבש")}</p>${bypass}</section>`);
    }
    if (!where.startsWith("/skill/") && !exercise.isOpen()) { /* the path scrolls itself */ }
  }
  onRoute(route);
  phone.startWatching();                                       // a photo request from the student's computer shows here when this is the phone
  await route();
}
