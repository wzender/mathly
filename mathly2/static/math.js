// Shared text helpers. The bank writes math as plain text between $…$ (for example "$x² − 2x − 15$").
// fmt() escapes the text and wraps each $…$ in <span class="m">, which math-tex.js draws as a formula.
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const fmt = s => esc(s).replace(/\$([^$]+)\$/g, '<span class="m">$1</span>');
