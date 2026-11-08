// The developer's home. Every permission is already there (the other roles' chips open their screens); the tools come later.
import { esc } from "./math.js";

export async function show(me, view) {
  view(`<section class="card" id="developer"><h2>מפתח</h2>
    <p>יש לך את כל ההרשאות: אפשר לפתוח את המסכים של כל התפקידים מהכפתורים למעלה.</p>
    <p class="muted">כלי המפתח (פרומפטר, מעבדה, עלות ה־AI) יתווספו בשלבים הבאים.</p>
    <p class="muted" dir="ltr">${esc(me.email)}</p></section>`);
}
