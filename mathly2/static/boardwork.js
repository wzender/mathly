// The work on the board (הדרך): after an answer, a picture of the question's board goes to the server, so the teacher can grade the way and
// not only the final answer. A picture is sent again only when the board changed; an empty board sends nothing.
import { sendPicture } from "./media.js";

const sent = new Map();          // board key -> the sketch's signature when it was last sent

/** Is there anything but the question's copy on this board? */
export const hasWork = boardKey => !!window.MathlyBoard?.hasWork?.(boardKey);

/** Send the board's picture as the work for one answer: `ref` is the attempt's id or "practice". Resolves to true when the server has it. */
export async function sendWork(boardKey, ref, questionKey) {
  const board = window.MathlyBoard;
  if (!board?.hasWork?.(boardKey)) return false;
  const sig = board.workSig(boardKey);
  if (sent.get(boardKey) === sig) return true;
  const blob = await board.pictureOf(boardKey);
  if (!blob) return false;
  await sendPicture(`/api/work?ref=${encodeURIComponent(ref)}&key=${encodeURIComponent(questionKey)}`, blob);
  sent.set(boardKey, sig);
  return true;
}

/** The same, never failing the caller (practice and rounds go on whatever happens to the picture). */
export const sendWorkQuietly = (...args) => sendWork(...args).catch(() => false);
