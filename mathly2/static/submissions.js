// "הגשות": every assignment from the student's teachers, grouped by state, and (on a phone) the switch for notifications.
import { swr } from "./api.js";
import { assignmentHref, assignmentState } from "./home.js";
import { esc, fmt } from "./math.js";
import * as notifications from "./notifications.js";
import { shortDate, tabs } from "./ui.js";

/** The groups, in the order a student needs them: what to do first, then what waits, then what is done. */
const GROUPS = [
  { id: "new", title: "חדשות: עוד לא הוגשו", states: ["not_handed", "not_done"] },
  { id: "returned", title: "הוחזרו לתיקון", states: ["returned"] },
  { id: "waiting", title: "הוגשו וממתינות לבדיקה", states: ["handed_in"] },
  { id: "checked", title: "נבדקו", states: ["graded", "done"] },
];

function item(a) {
  const s = assignmentState(a);
  const note = a.teacher_note ? `<span class="muted gr-note">הערת המורה: ${fmt(a.teacher_note)}</span>` : "";
  return `<li data-assignment="${a.id}" data-state="${esc(a.state)}"><a href="${assignmentHref(a)}"><b>${fmt(a.title)}</b></a>
    <span class="muted">${esc(a.class.name)} · עד ${shortDate(a.due_date)}</span><span class="tag st-${esc(a.state)}"><span aria-hidden="true">${s.symbol}</span> ${s.word}</span>${note}</li>`;
}

export const show = view => swr("/api/assignments", list => draw(view, list));

function draw(view, list) {
  const groups = GROUPS.map(g => ({ ...g, items: list.filter(a => g.states.includes(a.state)) })).filter(g => g.items.length);
  view(`${tabs("submissions")}<section class="card" id="submissions"><h2>הגשות</h2>
    ${groups.length ? groups.map(g => `<section class="group" id="group-${g.id}" data-group="${g.id}"><h3>${g.title} <span class="tab-count">${g.items.length}</span></h3>
      <ul class="plain assignments">${g.items.map(item).join("")}</ul></section>`).join("")
      : `<p class="muted" id="no-assignments">המורים עוד לא נתנו משימות.</p>`}</section>
    <section class="card" id="notifications" hidden></section>`);
  notifications.setup(document.getElementById("notifications"));
}
