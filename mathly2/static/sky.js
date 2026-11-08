import { esc } from "./math.js";
// The sky look's pictures. The owl is mathly1's (static/math-sky.js), coloured by the --sky-owl* tokens in app.css.
export const owl = (width = 80, cls = "") => `<svg class="sky-owl ${cls}" width="${width}" height="${Math.round(width * 1.04)}" viewBox="0 0 100 104" aria-hidden="true">
  <path d="M20 34 26 6l17 18q7-3 14 0L74 6l6 28q12 22 4 44-9 24-34 24T16 78q-8-22 4-44Z" class="o-b"/>
  <path d="M16 62q-8 14 2 28 4-10 4-22Z M84 62q8 14-2 28-4-10-4-22Z" class="o-b" opacity=".75"/>
  <ellipse cx="50" cy="74" rx="22" ry="23" class="o-belly"/>
  <path d="M40 70q3 3 6 0M54 70q3 3 6 0M44 80q3 3 6 0M50 80q3 3 6 0" class="o-feather"/>
  <circle cx="35" cy="44" r="13" class="o-eye"/><circle cx="65" cy="44" r="13" class="o-eye"/>
  <circle cx="37" cy="45" r="6.5" class="o-pupil"/><circle cx="63" cy="45" r="6.5" class="o-pupil"/>
  <circle cx="39" cy="42.5" r="2" class="o-glint"/><circle cx="65" cy="42.5" r="2" class="o-glint"/>
  <ellipse class="o-lid" cx="35" cy="44" rx="13.5" ry="13.5"/><ellipse class="o-lid" cx="65" cy="44" rx="13.5" ry="13.5"/>
  <circle cx="35" cy="44" r="15.5" class="o-glass"/><circle cx="65" cy="44" r="15.5" class="o-glass"/>
  <path d="M48 42q2-2 4 0" class="o-glass"/>
  <path d="M45 56h10l-5 9Z" class="o-beak"/>
  <path d="M38 99l-3 4M44 100v4M56 100v4M62 99l3 4" class="o-feet"/></svg>`;

/** The four-pointed star every skill is (mathly1's spark). Its colour and fill come from CSS (state classes). */
export const spark = (cls = "") => `<svg viewBox="0 0 24 24" class="${cls}" aria-hidden="true"><path d="M12 1.5C13.1 9 15 10.9 22.5 12C15 13.1 13.1 15 12 22.5C10.9 15 9 13.1 1.5 12C9 10.9 10.9 9 12 1.5Z"/></svg>`;

/** The arcs that join a lesson's stars in a ring (from mathly1's orbitRing). One path per neighbouring pair, clockwise from the top;
 *  an arc is "on" once the star it leaves has been started. The closing arc from the last star back to the first stays faint:
 *  the ring has a start and an end. Drawn in a 100x100 box that is stretched to the ring's size, so strokes do not scale. */
export function ringSvg(states) {
  const n = states.length;
  if (n < 2) return "";
  const angle = i => (-90 + 360 * i / n) * Math.PI / 180;
  const gap = Math.min(0.32, Math.PI / n * 0.55);          // room left around each star (radians)
  const point = t => [50 + 50 * Math.cos(t), 50 + 50 * Math.sin(t)];
  const f = v => v.toFixed(2);
  const arc = (from, to, cls) => {
    const [x0, y0] = point(from), [x1, y1] = point(to);
    return `<path class="${cls}" d="M${f(x0)} ${f(y0)}A50 50 0 0 1 ${f(x1)} ${f(y1)}"/>`;
  };
  const arcs = states.slice(0, -1).map((state, k) => arc(angle(k) + gap, angle(k + 1) - gap, state === "not_started" ? "" : "on")).join("");
  const back = n > 2 ? arc(angle(n - 1) + gap, angle(n) - gap, "back") : "";
  return `<svg class="ring" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${back}${arcs}</svg>`;
}

/* ---------- constellations and comets (ported from mathly1) ---------- */
const SPARK = "M12 1.5C13.1 9 15 10.9 22.5 12C15 13.1 13.1 15 12 22.5C10.9 15 9 13.1 1.5 12C9 10.9 10.9 9 12 1.5Z";
const curve=(f,n=48)=>Array.from({length:n+1},(_,i)=>f(i/n));
const SHAPES={
  t:{name:"הקערה",aspect:.9,pts:curve(s=>[1-s,1-(2*s-1)**2])},
  t2:{name:"המדרגות",aspect:.75,corners:1,pts:[[1,1],[1,.5],[.5,.5],[.5,0],[0,0]]},
  k:{name:"הדלתון",aspect:1.15,closed:1,corners:1,pts:[[.5,0],[1,.36],[.5,1],[0,.36]],inner:[[[.5,0],[.5,1]],[[0,.36],[1,.36]]]},
  i:{name:"המשולש",aspect:.9,closed:1,corners:1,pts:[[.5,0],[1,1],[0,1]],inner:[[[.5,0],[.5,1]]]},
  q:{name:"הקשת",aspect:.75,pts:curve(s=>[1-s,(2*s-1)**2])},
  q2:{name:"הפרבולה",aspect:.85,pts:curve(s=>[1-s,1-(2*s-1)**2]),inner:[[[.5,0],[.5,1]]]},
  a:{name:"הזווית",aspect:.7,closed:1,corners:1,pts:[[1,0],[1,1],[0,1]]},
  l:{name:"המשולש הישר",aspect:.75,closed:1,corners:1,pts:[[1,0],[1,1],[0,1]]},
  z:{name:"הטרפז",aspect:.6,closed:1,corners:1,pts:[[.72,0],[1,1],[0,1],[.28,0]]},
  z2:{name:"הטרפז הישר",aspect:.6,closed:1,corners:1,pts:[[.6,0],[1,1],[0,1],[0,0]]},
  e:{name:"הגבעה",aspect:.55,pts:curve(s=>[1-s,1-Math.sin(Math.PI*s)])},
  v:{name:"החץ",aspect:.8,corners:1,pts:[[0,0],[1,.5],[0,1]]},
  g:{name:"המקבילית",aspect:.6,closed:1,corners:1,pts:[[1,0],[.72,1],[0,1],[.28,0]]},
  r:{name:"ההיפרבולה",aspect:.9,pts:curve(s=>{const x=.06+.94*(1-s);return [x,Math.min(1,.06/x)]})},
  m:{name:"המלבן",aspect:.62,closed:1,corners:1,pts:[[1,0],[1,1],[0,1],[0,0]],inner:[[[1,0],[0,1]]]},
  h:{name:"הקובייה",aspect:1.1,closed:1,corners:1,pts:[[.5,0],[1,.25],[1,.75],[.5,1],[0,.75],[0,.25]],inner:[[[.5,.5],[.5,1]],[[.5,.5],[0,.25]],[[.5,.5],[1,.25]]]},
  s:{name:"המפגש",aspect:.75,pts:curve(s=>[1-s,(2*s-1)**2]),inner:[[[1,.12],[0,.88]]]},
  n:{name:"הגל",aspect:.5,pts:curve(s=>[1-s,.5-.5*Math.sin(2*Math.PI*s)])},
  b:{name:"המעוין",aspect:1.25,closed:1,corners:1,pts:[[.5,0],[1,.5],[.5,1],[0,.5]],inner:[[[.5,0],[.5,1]],[[0,.5],[1,.5]]]},
  c:{name:"הריבוע",aspect:1,closed:1,corners:1,pts:[[1,0],[1,1],[0,1],[0,0]],inner:[[[1,0],[0,1]],[[0,0],[1,1]]]},
  o:{name:"התיכון",aspect:.8,closed:1,corners:1,pts:[[1,0],[1,1],[0,1]],inner:[[[1,1],[.5,.5]]]},
  p:{name:"הרקטה",aspect:1,pts:curve(s=>{const x=1-s;return [x,1-(Math.pow(40,x)-1)/39]})},
  w:{name:"הברק",aspect:.6,corners:1,pts:[[1,1],[.75,0],[.5,.75],[.25,0],[0,1]]},
  d:{name:"המשולשים הדומים",aspect:.9,closed:1,corners:1,pts:[[.5,0],[1,1],[0,1]],inner:[[[.25,.5],[.75,.5]]]},
};
const FALLBACK={aspect:.7,corners:1,pts:[[1,.15],[.68,.85],[.36,.1],[0,.75]]};
const W=360, X0=60, X1=300, TOP=52, BOTTOM=64;
const lerp=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
const dist=(a,b)=>Math.hypot(b[0]-a[0],b[1]-a[1]);
function segments(pts,closed){ const out=[]; for(let i=0;i<pts.length-1;i++) out.push([pts[i],pts[i+1]]); if(closed) out.push([pts[pts.length-1],pts[0]]); return out; }
function along(pts,closed,n){
  const segs=segments(pts,closed), L=segs.reduce((s,[a,b])=>s+dist(a,b),0);
  const at=d=>{ for(const [a,b] of segs){ const l=dist(a,b); if(d<=l+1e-9) return lerp(a,b,l?d/l:0); d-=l; } return segs[segs.length-1][1]; };
  if(n<=0) return [];
  if(closed) return Array.from({length:n},(_,i)=>at(L*i/n));
  if(n===1) return [at(L/2)];
  return Array.from({length:n},(_,i)=>at(L*i/(n-1)));
}
function onCorners(pts,closed,n){
  const segs=segments(pts,closed), extra=segs.map(()=>0);
  for(let k=0;k<n-pts.length;k++){ let best=0; segs.forEach(([a,b],i)=>{ if(dist(a,b)/(extra[i]+1)>dist(...segs[best])/(extra[best]+1)) best=i; }); extra[best]++; }
  const out=[];
  segs.forEach(([a,b],i)=>{ out.push(a); for(let j=1;j<=extra[i];j++) out.push(lerp(a,b,j/(extra[i]+1))); });
  if(!closed) out.push(pts[pts.length-1]);
  return out;
}
/* The drawing of unit `id` with `n` stars, in a box W wide and H high: the stars in the path's order, the outline's
   segments, and the inner lines. A unit with many stars is drawn taller so that they keep apart. */
export function shape(id,n,name){
  const S=SHAPES[id]||{...FALLBACK,name};
  const w=X1-X0, h=Math.round(Math.max(w*S.aspect,n>6?(n-1)*36:0)), H=TOP+h+BOTTOM;
  const map=([x,y])=>[X0+x*w,TOP+y*h];
  const pts=S.pts.map(map);
  const stars=(S.corners&&n>=pts.length?onCorners(pts,!!S.closed,n):along(pts,!!S.closed,n));
  return {name:S.name||name,H,stars,lines:segments(pts,!!S.closed),inner:(S.inner||[]).map(l=>l.map(map))};
}

/** A completed lesson's constellation: its outline and inner lines, and its stars as small gold sparks, in the shape its lesson id gives
 *  (a zig-zag when none is defined). Stars are numbered in the lesson's order for the screen reader only. */
export function constellationSvg(lessonId, name, count) {
  const shp = shape(lessonId, count, name);
  const line = ([a, b]) => `<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}"/>`;
  const stars = shp.stars.map(([x, y]) => `<path d="${SPARK}" transform="translate(${(x - 20).toFixed(1)} ${(y - 20).toFixed(1)}) scale(${(20 / 12).toFixed(3)})"/>`).join("");
  return `<svg class="con" viewBox="34 22 292 ${shp.H - 56}" role="img" aria-label="קבוצת הכוכבים ${name}: ${count} כוכבים">${[...shp.lines, ...shp.inner].map(line).join("")}${stars}</svg>`;
}

/** The comet that crosses the screen: a gold tail and a spark. */
export const cometSvg = () => `<svg viewBox="0 0 120 56" aria-hidden="true"><defs><linearGradient id="cometTail" x1="0" x2="1"><stop offset="0" stop-color="#F7C948" stop-opacity="0"/><stop offset="1" stop-color="#F7C948"/></linearGradient></defs>
  <path d="M2 28 98 20 98 36Z" fill="url(#cometTail)"/><path d="${SPARK}" transform="translate(84 10) scale(1.5)" fill="#EAF0FF"/></svg>`;

/** A caught comet's card: its symbol and name (the fact is written under it by the screen). */
export const cometCard = c => `<div class="comet-card"><span class="sym" dir="ltr">${esc(c.sym)}</span><b>${esc(c.name)}</b></div>`;
