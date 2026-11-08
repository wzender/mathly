// What the student achieved: each completed lesson as a constellation, each mastered skill as a star (faded ones dimmed), and the comets.
import { api } from "./api.js";
import { esc } from "./math.js";
import { showCard } from "./comets.js";
import { constellationSvg } from "./sky.js";
import { tabs } from "./ui.js";

export async function show(view) {
  const [{ skills, lessons }, { comets, caught, total }] = await Promise.all([api("/api/collection"), api("/api/comets")]);
  view(`${tabs("collection")}<section class="card" id="collection"><h2>האוסף שלי</h2>
    <h3>קבוצות כוכבים (${lessons.length})</h3>
    ${lessons.length ? `<div class="cons" id="done-lessons">${lessons.map(l => `<figure class="con-card" data-lesson="${esc(l.id)}">
        ${constellationSvg(l.id, l.name, l.skills)}<figcaption>${esc(l.name)}<small class="muted">${l.skills} כוכבים</small></figcaption></figure>`).join("")}</div>`
      : `<p class="muted">עוד אין. קבוצת כוכבים מופיעה כשכל המיומנויות של שיעור נשלטות.</p>`}
    <h3>מיומנויות שנשלטו (${skills.length})</h3>
    ${skills.length ? `<ul class="plain" id="done-skills">${skills.map(s => `<li${s.faded ? ' class="faded"' : ""}><a href="#/skill/${esc(s.id)}">✓ ${esc(s.name)}${s.faded ? " · ◌ דועך" : ""}</a><span class="muted">${esc(s.lesson_name)}</span></li>`).join("")}</ul>`
      : `<p class="muted">עוד אין. מיומנות נשלטת אחרי 3 תשובות נכונות ברצף, בלי עזרה, בשני ימים שונים.</p>`}
    <h3>שביטים נדירים <span class="muted">(${caught} מתוך ${total})</span></h3>
    <div class="comets" id="comets">${comets.map(c => c.caught
      ? `<button type="button" class="comet-tile have" data-comet="${esc(c.id)}"><span class="sym" dir="ltr">${esc(c.sym)}</span><small>${esc(c.name)}</small></button>`
      : `<button type="button" class="comet-tile" data-comet="${esc(c.id)}" aria-label="שביט שעוד לא נתפס"><span class="sym">?</span><small>עוד לא נתפס</small></button>`).join("")}</div></section>`);
  document.getElementById("comets").addEventListener("click", event => {
    const tile = event.target.closest("[data-comet]");
    if (tile) showCard(comets.find(c => c.id === tile.dataset.comet), { heading: "שביט נדיר" });
  });
}
