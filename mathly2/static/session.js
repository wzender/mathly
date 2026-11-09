// Sign-in state. With Supabase settings: Google sign-in through supabase-js. Without them (local development only):
// a "dev only" sign-in that takes an email address; the server trusts "dev:<email>" tokens only in that mode.
const DEV_KEY = "mathly2.dev-email";
let client = null;

const load = src => new Promise((ok, fail) => {
  const s = document.createElement("script");
  s.src = src; s.onload = ok; s.onerror = () => fail(new Error("script " + src));
  document.head.append(s);
});

export async function init(cfg) {
  if (!cfg.supabaseUrl) return;
  await load("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js");
  client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseKey);
}

export async function token() {
  if (client) {
    const { data } = await client.auth.getSession();   // supabase-js refreshes an expired token here
    return data.session?.access_token || "";
  }
  try { const email = localStorage.getItem(DEV_KEY); return email ? "dev:" + email : ""; } catch { return ""; }
}

export const signInWithGoogle = () =>
  client.auth.signInWithOAuth({ provider: "google", options: { redirectTo: location.origin + location.pathname } });

export function signInDev(email) {
  try { localStorage.setItem(DEV_KEY, email.trim().toLowerCase()); } catch { /* private window: stays signed out */ }
}

const outListeners = [];
/** Calls `fn` when the person signs out (so nothing remembered about them is shown to the next one). */
export const onSignOut = fn => outListeners.push(fn);

export async function signOut() {
  outListeners.forEach(fn => fn());
  if (client) await client.auth.signOut();
  try { localStorage.removeItem(DEV_KEY); } catch { /* nothing stored */ }
}
