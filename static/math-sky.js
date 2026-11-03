/* The night sky: Mathly's rewards and the pictures behind them.
   A skill is a star and a unit is a constellation. A skill is finished (its star lit) once every question was answered
   right and the last MASTER_RUN answers were right at the first try, so a lucky guess or a remembered answer is not
   enough; GOLD_RUN first-try answers in a row (or every question, when it has fewer) turn it gold. A finished skill
   comes back for spaced review (`review`, after 1, 3, 7, 14, 30 and 60 days; a miss starts over). A finished skill not practised for
   FADE_DAYS fades until one correct answer brightens it again. GOAL correct answers make a day; days in a row make the
   streak, and one missed day does not break it. Now and then a comet crosses the screen and can be caught for the
   collection. All of it lives in the student's progress (P, see math.js): run, gold, seen, days, comets, cometDay, and the
   misconceptions met along the way (slips, see "misconception patterns").
   Pure rules first, then the drawings (owl, constellations), then the effects (sound, sparkles, overlays). */
(function(){
"use strict";
const GOAL=5, FADE_DAYS=14, DAY=86400000, LABEL_W=96, MASTER_RUN=3, GOLD_RUN=5, INTERVALS=[1,3,7,14,30,60];
const masterNeed=n=>Math.min(MASTER_RUN,Math.max(1,n)), goldNeed=n=>Math.min(GOLD_RUN,Math.max(1,n));
const SPARK="M12 1.5C13.1 9 15 10.9 22.5 12C15 13.1 13.1 15 12 22.5C10.9 15 9 13.1 1.5 12C9 10.9 10.9 9 12 1.5Z";
const spark=(cls="")=>`<svg viewBox="0 0 24 24" class="${cls}" aria-hidden="true"><path d="${SPARK}"/></svg>`;
const FLAME=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.6 1.8c.6 4.3 6.4 6.6 6.4 12.2a7 7 0 0 1-14 0c0-3 1.6-5 3-6.2-.1 2.4.9 4 2.4 4.4-.5-3.9-.1-7.6 2.2-10.4z"/></svg>`;
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* ---------- rules ---------- */
const dayKey=(d=new Date())=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const daysBack=(n,from)=>{const d=new Date(from);d.setDate(d.getDate()-n);return d};
function ensure(P){ for(const k of ["run","gold","seen","days","review","missed"]) if(!P[k]||typeof P[k]!=="object") P[k]={}; for(const k of ["comets","slips"]) if(!Array.isArray(P[k])) P[k]=[]; return P; }
function fading(P,id,now=new Date()){
  if(!P.done?.[id]) return false;
  const t=Date.parse(P.seen?.[id]||P.done[id]);
  return !isNaN(t)&&now-t>FADE_DAYS*DAY;
}
/* A correct answer in skill `id`. `first`: answered at the first try; `n`: the skill's questions; `finished`: the skill
   is done after this answer. Returns what changed: a new gold star, the day's goal just reached, a faded star revived. */
function correct(P,id,{first,n,finished,now=new Date()}){
  ensure(P);
  const revived=fading(P,id,now), k=dayKey(now), t=now.toISOString();
  P.days[k]=(P.days[k]||0)+1; P.seen[id]=t;
  P.run[id]=first?(P.run[id]||0)+1:0;
  const gold=!!finished&&!P.gold[id]&&P.run[id]>=goldNeed(n);
  if(gold) P.gold[id]=t;
  return {gold,goal:P.days[k]===GOAL,revived};
}
function wrong(P,id){ ensure(P); P.run[id]=0; }

/* ---------- spaced review ---------- */
const later=(days,now)=>dayKey(daysBack(-days,now));
// a skill just finished: first review tomorrow
function mastered(P,id,now=new Date()){ ensure(P); P.review[id]={box:0,due:later(INTERVALS[0],now)}; }
// a review answer: right moves the next review further away, wrong brings it back tomorrow
function reviewed(P,id,ok,now=new Date()){
  ensure(P); const box=ok?Math.min((P.review[id]?.box??-1)+1,INTERVALS.length-1):0;
  P.review[id]={box,due:later(INTERVALS[box],now)};
}
// is a finished skill due for review today? (one finished before reviews existed: a day after it was last seen)
function due(P,id,now=new Date()){
  if(!P.done?.[id]) return false;
  const r=P.review?.[id]; if(r?.due) return r.due<=dayKey(now);
  const t=Date.parse(P.seen?.[id]||P.done[id]); return !isNaN(t)&&now-t>=DAY;
}
/* ---------- misconception patterns ----------
   Every tagged wrong answer is kept in P.slips ({at, id: skill, q: question index, m: mistake tag, via: practice |
   review | exam}), newest last, at most SLIP_MAX. patterns() reads it: a tag is recurring when it came up at least
   twice in RECUR_DAYS and once in the last QUIET_DAYS; it has stopped when it once came up twice within RECUR_DAYS,
   but not in the last QUIET_DAYS, and less than GONE_DAYS ago. */
const SLIP_MAX=500, RECUR_DAYS=30, QUIET_DAYS=14, GONE_DAYS=60, PATTERNS_SHOWN=3;
function slip(P,id,q,m,via,now=new Date()){
  ensure(P); if(!m) return;
  P.slips.push({at:now.toISOString(),id,q,m,via});
  if(P.slips.length>SLIP_MAX) P.slips.splice(0,P.slips.length-SLIP_MAX);
}
// `mistakes`: the graph's mistakes by tag (for the skill each one sends back to)
function patterns(P,mistakes={},now=new Date()){
  const by={};
  for(const s of P.slips||[]){ const t=Date.parse(s?.at); if(s?.m&&!isNaN(t)&&t<=now) (by[s.m]||=[]).push({t,id:s.id}); }
  const recurring=[], stopped=[], age=t=>(now-t)/DAY;
  for(const [m,all] of Object.entries(by)){
    all.sort((a,b)=>a.t-b.t);
    const last=all.at(-1).t;
    if(age(last)>=GONE_DAYS) continue;
    const recent=all.filter(x=>age(x.t)<RECUR_DAYS);
    const item=list=>{
      const count={}, seen={};
      for(const x of list){ count[x.id]=(count[x.id]||0)+1; seen[x.id]=x.t; }
      const skills=Object.keys(count).sort((a,b)=>count[b]-count[a]||seen[b]-seen[a]);
      return {m,n:list.length,skills,last:new Date(last).toISOString(),practise:mistakes[m]?.back||skills[0]};
    };
    if(age(last)<QUIET_DAYS){ if(recent.length>=2) recurring.push(item(recent)); }
    else if(all.some((x,i)=>i>0&&(x.t-all[i-1].t)/DAY<=RECUR_DAYS)) stopped.push(item(all));
  }
  const rank=(a,b)=>b.skills.length-a.skills.length||b.n-a.n||b.last.localeCompare(a.last);
  return {recurring:recurring.sort(rank).slice(0,PATTERNS_SHOWN),stopped:stopped.sort(rank).slice(0,PATTERNS_SHOWN)};
}

/* a star's look: gold, lit, fading (finished), next, open, locked, off */
function star(P,id,status,isNext){
  if(status==="done") return P.gold?.[id]?"gold":fading(P,id)?"fading":"lit";
  if(status==="open") return isNext?"next":"open";
  return status;
}
const today=P=>(P.days||{})[dayKey()]||0;
function streak(P,now=new Date()){
  const days=P.days||{}, met=d=>(days[dayKey(d)]||0)>=GOAL;
  let n=0, missed=0;
  for(let i=met(now)?0:1;i<1000;i++){ if(met(daysBack(i,now))){n++;missed=0} else if(++missed>1) break; }
  return n;
}
const DAY_NAMES=["א","ב","ג","ד","ה","ו","ש"];
/* A day on the streak calendar: "met" (the goal was reached), "saved" (missed, but the streak went on over it:
   the day before was met and the day after is met, or is today and still open), "some" (practised, short of the
   goal) or "" (nothing). Today and later are "met" or "" only, since the day is not over. */
function dayState(P,d,now=new Date()){
  const days=P.days||{}, n=k=>days[dayKey(k)]||0, met=k=>n(k)>=GOAL, t=dayKey(now), key=dayKey(d);
  if(met(d)) return "met";
  if(key>=t) return "";
  const after=daysBack(-1,d);
  if(met(daysBack(1,d))&&(met(after)||dayKey(after)===t)) return "saved";
  return n(d)?"some":"";
}
// a month for the calendar, weeks from Sunday: blanks before the 1st, then {day,key,state,today,future}
function month(P,y,m,now=new Date()){
  const first=new Date(y,m,1), len=new Date(y,m+1,0).getDate(), t=dayKey(now), cells=Array(first.getDay()).fill(null);
  for(let i=1;i<=len;i++){ const d=new Date(y,m,i), key=dayKey(d); cells.push({day:i,key,state:dayState(P,d,now),today:key===t,future:key>t}); }
  return cells;
}
// the longest streak ever, by the same rule as streak(): one missed day between met days does not break it
function best(P,now=new Date()){
  const keys=Object.keys(P.days||{}).filter(k=>P.days[k]>=GOAL).sort(); if(!keys.length) return 0;
  const [y,m,d]=keys[0].split("-").map(Number);
  let top=0, run=0, missed=0;
  for(const day=new Date(y,m-1,d);dayKey(day)<=dayKey(now);day.setDate(day.getDate()+1)){
    if((P.days[dayKey(day)]||0)>=GOAL){ run++; missed=0; top=Math.max(top,run); } else if(++missed>1) run=0;
  }
  return top;
}

/* ---------- comets ---------- */
const COMETS=[
  {id:"pi",sym:"π",name:"פאי",fact:"היחס בין ההיקף של מעגל לקוטר שלו. הספרות שלו אחרי הנקודה לא נגמרות ולא חוזרות על עצמן."},
  {id:"fib",sym:"1,1,2,3,5",name:"פיבונאצ׳י",fact:"כל מספר בסדרה הוא סכום שני הקודמים. הסדרה מופיעה בספירלות של גרעיני חמנייה ובאצטרובלים."},
  {id:"phi",sym:"φ",name:"יחס הזהב",fact:"בערך 1.618. מחלקים קטע כך שהיחס בין השלם לחלק הגדול שווה ליחס בין הגדול לקטן. מופיע בפרחים, בצדפים ובאמנות."},
  {id:"inf",sym:"∞",name:"אינסוף",fact:"יש אינסוף מספרים שלמים, ויש גם אינסוף מספרים בין 0 ל־1. מתברר שהאינסוף השני גדול יותר."},
  {id:"e",sym:"e",name:"המספר e",fact:"בערך 2.718. מופיע בכל מקום שבו משהו גדל בקצב שתלוי בגודל שלו: ריבית, אוכלוסיות, חיידקים."},
  {id:"r2",sym:"√2",name:"שורש 2",fact:"האורך של אלכסון בריבוע שצלעו 1. כבר היוונים הקדמונים הוכיחו שאי אפשר לכתוב אותו כשבר."},
  {id:"zero",sym:"0",name:"אפס",fact:"במשך אלפי שנים לא היה סימן לאפס. הוא הגיע מהודו, ובזכותו אפשר לכתוב כל מספר בעשר ספרות בלבד."},
  {id:"pyth",sym:"a²+b²=c²",name:"פיתגורס",fact:"במשולש ישר זווית, סכום ריבועי הניצבים שווה לריבוע היתר. ידוע ליותר מ־370 הוכחות שונות."},
  {id:"prime",sym:"2,3,5,7",name:"מספרים ראשוניים",fact:"מספרים שמתחלקים רק ב־1 ובעצמם. יש אינסוף כאלה, ועליהם בנויה ההצפנה של האינטרנט."},
  {id:"pascal",sym:"1 2 1",name:"משולש פסקל",fact:"כל מספר הוא סכום שני המספרים שמעליו. השורות שלו נותנות את המקדמים של (a + b) בכל חזקה."},
  {id:"euler",sym:"V−E+F=2",name:"נוסחת אוילר",fact:"בכל גוף משוכלל, קודקודים פחות מקצועות ועוד פאות שווה תמיד 2. נסו על קובייה: 8 − 12 + 6."},
  {id:"mobius",sym:"∞",name:"טבעת מביוס",fact:"רצועת נייר עם חצי סיבוב: יש לה רק צד אחד ושפה אחת. נמלה שהולכת עליה תעבור בשני ה״צדדים״."}];
/* a comet comes at most once a day: surely with the first gold star of all, otherwise by chance */
function cometDue(P,{gold}){
  ensure(P);
  if(P.comets.length>=COMETS.length||P.cometDay===dayKey()) return false;
  return (gold&&!P.comets.length&&!P.cometDay)||Math.random()<.12;
}
function catchComet(P){
  ensure(P);
  const left=COMETS.filter(c=>!P.comets.includes(c.id)); if(!left.length) return null;
  const c=left[Math.floor(Math.random()*left.length)]; P.comets.push(c.id); return c;
}

/* ---------- constellations ---------- */
/* Each unit is drawn as a shape from its subject, in a box 0..1 (x to the right, y down). `corners`: the stars sit on
   the vertices first; `closed`: the outline returns to the start; `inner`: lines drawn inside once it is complete. */
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
function shape(id,n,name){
  const S=SHAPES[id]||{...FALLBACK,name};
  const w=X1-X0, h=Math.round(Math.max(w*S.aspect,n>6?(n-1)*36:0)), H=TOP+h+BOTTOM;
  const map=([x,y])=>[X0+x*w,TOP+y*h];
  const pts=S.pts.map(map);
  const stars=(S.corners&&n>=pts.length?onCorners(pts,!!S.closed,n):along(pts,!!S.closed,n));
  return {name:S.name||name,H,stars,lines:segments(pts,!!S.closed),inner:(S.inner||[]).map(l=>l.map(map))};
}
/* Where each star's name goes: below, above, or beside it, whichever stays in the box and clear of the other stars
   and names. `texts`: [{len, lines}] with len the name's characters and lines the extra lines under it. */
function labels(stars,texts,H){
  const taken=stars.map(([x,y])=>[x-15,y-15,x+15,y+15]);
  const overlap=(a,b)=>Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0]))*Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));
  return stars.map(([x,y],i)=>{
    const {len,lines=0}=texts[i], w=Math.min(LABEL_W,len*6.3+10), h=(Math.ceil(len*6.3/LABEL_W)+lines)*15+2;
    const cands=[["below",x-w/2,y+19],["above",x-w/2,y-19-h],["right",x+19,y-h/2],["left",x-19-w,y-h/2]];
    let best=null;
    for(const [side,x0,y0] of cands){
      const r=[x0,y0,x0+w,y0+h], out=(x0<0?-x0:0)+(r[2]>W?r[2]-W:0)+(y0<0?-y0:0)+(r[3]>H?r[3]-H:0);
      const score=out*60+taken.reduce((s,t,k)=>s+(k===i?0:overlap(r,t)),0);
      if(!best||score<best.score-.5) best={side,r,score};
    }
    taken.push(best.r);
    return {side:best.side,x:best.r[0],y:best.r[1],w};
  });
}

/* ---------- the owl ---------- */
const owl=(w=80,cls="")=>`<svg class="sky-owl ${cls}" width="${w}" height="${Math.round(w*1.04)}" viewBox="0 0 100 104" aria-hidden="true">
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
/* Praise names what the student did, never what they are: fixing an earlier mistake is praised most. */
const PRAISE=["נכון. עבודה מדויקת.","נכון. חישוב זהיר.","נכון, שלב אחרי שלב.","נכון. בדקתם עד הסוף."];
const pick=a=>a[Math.floor(Math.random()*a.length)];
function praise({recovered=false,persisted=false,combo=0}={}){
  if(recovered) return pick(["תיקנתם שאלה שטעיתם בה קודם. ככה לומדים!","הפעם זה יצא נכון. הטעות מקודם עזרה."]);
  if(persisted) return "נכון. ההתמדה השתלמה.";
  if(combo>=3) return "נכון, ובעקביות.";
  return pick(PRAISE);
}

/* ---------- effects ---------- */
const RM=()=>matchMedia("(prefers-reduced-motion: reduce)").matches;
let host=null, fx=null, fc=null, parts=[], running=false, AC=null;
const soundOn=()=>{ try{ return localStorage.getItem("mathly.sound")!=="off"; }catch{ return true; } };
function setSound(on){ try{ localStorage.setItem("mathly.sound",on?"on":"off"); }catch{} }
function tone(fs,dur=.12,type="sine",gap=.07,vol=.15){
  if(!soundOn()) return;
  try{
    AC=AC||new (window.AudioContext||window.webkitAudioContext)(); const t0=AC.currentTime+.01;
    fs.forEach((f,i)=>{ const o=AC.createOscillator(), g=AC.createGain(), t=t0+i*gap; o.type=type; o.frequency.value=f;
      g.gain.setValueAtTime(0,t); g.gain.linearRampToValueAtTime(vol,t+.012); g.gain.exponentialRampToValueAtTime(.0008,t+dur+.25);
      o.connect(g).connect(AC.destination); o.start(t); o.stop(t+dur+.3); });
  }catch{}
}
const sound={
  ok:()=>tone([784,1175],.1,"sine",.08), combo:n=>tone([784,988,1175,1568].slice(0,Math.min(4,n+1)),.09,"sine",.06),
  bad:()=>tone([196,165],.12,"triangle",.09,.08), win:()=>tone([523,659,784,1047,1319,1568],.2,"sine",.09),
  goal:()=>tone([659,784,1047],.16,"sine",.1), comet:()=>tone([1568,2093,1760,2349],.12,"triangle",.07,.09), tap:()=>tone([1200],.03,"sine",0,.05)};
const buzz=p=>{ try{ navigator.vibrate&&navigator.vibrate(p); }catch{} };

function sizeFx(){ const d=devicePixelRatio||1; fx.width=innerWidth*d; fx.height=innerHeight*d; fc.setTransform(d,0,0,d,0,0); }
function sparkle(c,x,y,r){ c.beginPath(); c.moveTo(x,y-r); c.quadraticCurveTo(x+r*.15,y-r*.15,x+r,y); c.quadraticCurveTo(x+r*.15,y+r*.15,x,y+r);
  c.quadraticCurveTo(x-r*.15,y+r*.15,x-r,y); c.quadraticCurveTo(x-r*.15,y-r*.15,x,y-r); c.fill(); }
/* sparks out of a point: a few for a correct answer, a shower for a star */
function burst(x,y,n=14,gold=false){
  if(!fx||RM()) return;
  const cols=gold?["#F7C948","#FFE7A3","#FFFFFF","#FF8B5C"]:["#7EE3C8","#EAF0FF","#C3A6F5","#74C3E6"];
  for(let i=0;i<n;i++){ const a=Math.random()*Math.PI*2, v=2+Math.random()*(gold?9:5);
    parts.push({x,y,vx:Math.cos(a)*v,vy:Math.sin(a)*v-(gold?3:1),r:2+Math.random()*(gold?6:4),c:cols[i%cols.length],life:1,d:.008+Math.random()*.014}); }
  if(!running){ running=true; requestAnimationFrame(tick); }
}
const burstAt=(el,n,gold)=>{ if(!el) return; const r=el.getBoundingClientRect(); burst(r.left+r.width/2,r.top+r.height/2,n,gold); };
function tick(){
  fc.clearRect(0,0,innerWidth,innerHeight);
  for(const p of parts){ p.x+=p.vx; p.y+=p.vy; p.vy+=.14; p.vx*=.985; p.life-=p.d; fc.globalAlpha=Math.max(0,p.life); fc.fillStyle=p.c; sparkle(fc,p.x,p.y,p.r); }
  parts=parts.filter(p=>p.life>0&&p.y<innerHeight+20); fc.globalAlpha=1;
  if(parts.length) requestAnimationFrame(tick); else { running=false; fc.clearRect(0,0,innerWidth,innerHeight); }
}

/* the twinkling sky behind the screens */
function starfield(canvas){
  const c=canvas.getContext("2d"); let stars=[];
  const size=()=>{ const d=devicePixelRatio||1; canvas.width=innerWidth*d; canvas.height=innerHeight*d; c.setTransform(d,0,0,d,0,0);
    stars=Array.from({length:Math.round(innerWidth*innerHeight/2600)},()=>({x:Math.random()*innerWidth,y:Math.random()*innerHeight,r:Math.random()*1.3+.2,p:Math.random()*6.28,s:.4+Math.random()*1.4})); paint(0); };
  const paint=t=>{ c.clearRect(0,0,innerWidth,innerHeight); c.fillStyle="#DDE4FF";
    for(const s of stars){ c.globalAlpha=Math.max(.08,.35+.45*Math.sin(s.p+t*.001*s.s)); c.beginPath(); c.arc(s.x,s.y,s.r,0,6.28); c.fill(); } c.globalAlpha=1; };
  const loop=t=>{ if(!canvas.isConnected) return; if(host&&!host.hidden) paint(t); requestAnimationFrame(loop); };
  addEventListener("resize",size); size(); if(!RM()) requestAnimationFrame(loop);
}

function mount(root){
  host=root;
  const bg=document.createElement("canvas"); bg.className="sky-bg"; bg.setAttribute("aria-hidden","true");
  fx=document.createElement("canvas"); fx.className="sky-fx"; fx.setAttribute("aria-hidden","true"); fc=fx.getContext("2d");
  root.prepend(bg); root.append(fx); starfield(bg); sizeFx(); addEventListener("resize",sizeFx);
}

function toast(html,ms=3400){
  const t=document.createElement("div"); t.className="sky-toast"; t.setAttribute("role","status"); t.innerHTML=html;
  (host||document.body).append(t); setTimeout(()=>t.remove(),ms);
}
/* A full-screen moment. `kind`: "gold", "lit" or "con"; `art` replaces the big star (a constellation, a comet card).
   Resolves when the student goes on. */
function celebrate({kind="lit",title,sub="",extra="",art=""}){
  return new Promise(done=>{
    const c=document.createElement("div"); c.className=`sky-cele k-${kind}`; c.setAttribute("role","dialog"); c.setAttribute("aria-modal","true"); c.setAttribute("aria-label",title);
    c.innerHTML=`<div class="in"><div class="rays"></div><div class="big">${art||spark()}</div><h2>${esc(title)}</h2>${sub?`<p>${sub}</p>`:""}${extra}
      <button class="sky-btn${kind==="lit"?"":" gold"}" data-sky="go">להמשיך</button></div>`;
    (host||document.body).append(c);
    kind==="lit"?sound.ok():sound.win(); buzz(kind==="lit"?[40,40,60]:[40,60,40,60,120]);
    setTimeout(()=>burstAt(c.querySelector(".big"),kind==="lit"?45:90,kind!=="lit"),250);
    const btn=c.querySelector("[data-sky=go]"); btn.focus({preventScroll:true});
    const close=()=>{ c.remove(); removeEventListener("keydown",key,true); done(); };
    const key=e=>{ if(e.key==="Escape"){ e.stopPropagation(); close(); } };
    addEventListener("keydown",key,true); btn.onclick=close;
  });
}
/* A comet flies across; `onCatch` runs when it is tapped in time. */
function comet(onCatch){
  const b=document.createElement("button"); b.className="sky-comet"; b.setAttribute("aria-label","שביט! לחצו כדי לתפוס אותו");
  b.innerHTML=`<svg viewBox="0 0 120 56" aria-hidden="true"><defs><linearGradient id="skyTail" x1="0" x2="1"><stop offset="0" stop-color="#F7C948" stop-opacity="0"/><stop offset="1" stop-color="#F7C948"/></linearGradient></defs>
    <path d="M2 28 98 20 98 36Z" fill="url(#skyTail)"/><path d="${SPARK}" transform="translate(84 10) scale(1.5)" fill="#EAF0FF"/></svg>`;
  (host||document.body).append(b); sound.comet(); toast("<b>שביט!</b> תפסו אותו לפני שהוא חולף",2600);
  const gone=()=>{ if(b.isConnected){ b.remove(); toast("השביט חלף. שביטים חוזרים מדי פעם בזמן תרגול."); } };
  b.onclick=()=>{ const r=b.getBoundingClientRect(); b.remove(); burst(r.left+r.width-20,r.top+r.height/2,60,true); buzz([30,30,80]); onCatch(); };
  b.addEventListener("animationend",gone);
  if(RM()) setTimeout(gone,9000);
}
const cometCard=c=>`<div class="sky-card"><span class="sym">${esc(c.sym)}</span><b>${esc(c.name)}</b></div>`;

window.MathlySky={GOAL,slip,patterns,FADE_DAYS,MASTER_RUN,GOLD_RUN,masterNeed,goldNeed,mastered,reviewed,due,COMETS,SPARK,spark,FLAME,owl,praise,dayKey,ensure,correct,wrong,fading,star,today,streak,dayState,month,best,
  cometDue,catchComet,shape,labels,mount,burst,burstAt,sound,buzz,soundOn,setSound,toast,celebrate,comet,cometCard};
})();
