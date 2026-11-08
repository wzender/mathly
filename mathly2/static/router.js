// One address-bar router for the active screen: whichever role screen is open sets its handler, so screens never stack listeners.
let handler = null;
window.addEventListener("hashchange", () => { if (handler) handler(); });
/** Make `fn` the screen that reacts to the address after "#". */
export const route = fn => { handler = fn; };
/** Tell whatever is open over the screens (a sheet) that the person is leaving. */
export const leaveScreen = () => window.dispatchEvent(new Event("mathly:leave"));

/** Forget the open screen. The address after "#" is cleared too, unless `keepAddress`: a link or a reload must land where it points. */
export const clearRoute = ({ keepAddress = false } = {}) => {
  leaveScreen();
  handler = null;
  if (!keepAddress) history.replaceState(null, "", location.pathname + location.search);
};
