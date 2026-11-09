// Pictures in the browser: reading a private picture through the server (a plain <img src> cannot send the sign-in), shrinking a photo before
// it is sent, uploading it, and telling a phone from a computer.
import { token } from "./session.js";
import { ApiError } from "./api.js";

const cache = new Map();

/** A picture's bytes as a blob URL, fetched with the sign-in (the server is the only door to pictures). Rejects with ApiError (410: deleted). */
export function pictureUrl(id) {
  if (!cache.has(id)) {
    cache.set(id, (async () => {
      const response = await fetch(`/api/pictures/${encodeURIComponent(id)}`, { headers: { Authorization: "Bearer " + await token() } });
      if (!response.ok) { cache.delete(id); throw new ApiError(response.status, response.status === 410 ? "התמונה נמחקה" : "לא הצלחנו לפתוח את התמונה"); }
      return URL.createObjectURL(await response.blob());
    })());
  }
  return cache.get(id);
}

/** A photo shrunk to at most `side` pixels and re-encoded as JPEG (this also drops its metadata). Falls back to the file itself when the browser
 *  cannot decode it, and the server then decides. */
export async function prepare(file, side = 2000) {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, side / Math.max(bitmap.width, bitmap.height));
    const canvas = Object.assign(document.createElement("canvas"), { width: Math.round(bitmap.width * scale), height: Math.round(bitmap.height * scale) });
    const context = canvas.getContext("2d");
    context.fillStyle = "#fff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(done => canvas.toBlob(done, "image/jpeg", 0.88));
    return blob || file;
  } catch { return file; }
}

/** Send picture bytes (a Blob or File) to `url`; resolves to the JSON answer. */
export async function sendPicture(url, blob) {
  const response = await fetch(url, { method: "POST", headers: { Authorization: "Bearer " + await token(), "Content-Type": blob.type || "image/jpeg" }, body: blob });
  let data = null;
  try { data = await response.json(); } catch { /* no body */ }
  if (!response.ok) throw new ApiError(response.status, (data && typeof data.detail === "string" && data.detail) || "משהו השתבש, נסו שוב");
  return data;
}

/** A phone or tablet (a touch screen): where the camera opens directly and notifications are offered. */
export const isTouch = () => !!window.matchMedia?.("(pointer: coarse)").matches;

/** This browser's own id, so a photo request knows which device asked and the phone does not ask itself. */
export function deviceId() {
  try {
    let id = localStorage.getItem("mathly2.device");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("mathly2.device", id); }
    return id;
  } catch { return "device-" + Math.random().toString(36).slice(2); }
}
