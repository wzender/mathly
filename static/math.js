/* The Mathly path.
   The skill graph comes from /api/math/skills (app/math_skills.py). Every skill is open; the path walks them in
   order, and the first one not done yet is where the student goes on.
   A skill has one sample question or a list of questions. It is done once every one of its questions has been
   answered correctly and the last few answers (Sky.masterNeed) were right at the first try; after each answer the
   student moves to the next unsolved question, so a missed question comes back after the others. The choices are
   shuffled each time a question is shown, and a wrong answer does not reveal the right one, so a question that comes
   back is solved again, not remembered. Finished skills come back in a mixed review (see "spaced review" below). Progress is kept on the device per account (mathly.progress.v1:<email>), and for a signed-in student also on
   the server so it follows them to other devices (see "progress across devices"): `done` per
   skill, and `solved` (indexes answered correctly), `at` (the question to show) and `set` (the round's questions, see round())
   for skills with a list. Every tagged wrong answer is also kept in `slips` (see "misconception patterns" and math-sky.js),
   so the mistakes that keep coming back across skills can be shown with what to practise. */
(()=>{
const css=document.createElement("link"); css.rel="stylesheet"; css.href=document.currentScript.src.replace("math.js","math.css");
const cssReady=new Promise(done=>{ css.onload=css.onerror=done; });   // until then #mathView is not yet the scrolling box
document.head.append(css);

const CFG=window.MATHLY||{}, AUTH_URL=CFG.supabaseUrl||"";
let ME_EMAIL="", MY_CLASSES=[], MY_CLASS=null, client=null;
const can=permission=>(CFG.permissions||[]).includes("*")||(CFG.permissions||[]).includes(permission);
const api=(url,options={})=>fetch(url,{...options,headers:{...(options.headers||{}),...(CFG.token?{Authorization:`Bearer ${CFG.token}`}:{})}});

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=s=>esc(s).replace(/\$([^$]+)\$/g,'<span class="m">$1</span>');   // $…$ is math: set left to right
const plain=s=>String(s).replace(/\$/g,"");
// the model's text: as fmt, and a signed number it left outside $…$ is set left to right too, or its minus lands after it
const fmtLoose=s=>String(s??"").split("$").map((part,i)=>i%2?`<span class="m">${esc(part)}</span>`
  :esc(part).replace(/(^|[\s(־])([−-]\d+(?:[.,]\d+)?)/g,'$1<span class="m">$2</span>')).join("");
const key=()=>"mathly.progress.v1:"+(ME_EMAIL||"guest");
const load=()=>{ try{ return JSON.parse(localStorage.getItem(key())||"{}"); }catch{ return {}; } };
const save=()=>{ P.updated=Date.now(); try{ localStorage.setItem(key(),JSON.stringify(P)); }catch{} queuePush(); };

/* Progress across devices: a signed-in student's progress is also kept on the server (app/progress.py). On sign-in the
   server's copy is merged into this device's; after each save the merged copy is sent back, and coming back to the tab
   merges again. mergeProgress keeps the work of both copies: finished skills, gold stars, solved questions, comets,
   mistakes and exams are joined; counts keep the higher one; where a student is now (the round, the question, a
   sitting, the run of first tries, spaced review) comes from the copy saved last (`updated`). */
const isObj=v=>!!v&&typeof v==="object"&&!Array.isArray(v);
function mergeProgress(a,b){
  a=isObj(a)?a:{}; b=isObj(b)?b:{};
  const [old,neu]=(+a.updated||0)>(+b.updated||0)?[b,a]:[a,b], out={...old,...neu};
  const each=(k,pick)=>{ const o=isObj(old[k])?old[k]:{}, n=isObj(neu[k])?neu[k]:{}, r={...o,...n};
    if(pick) for(const id in o) if(id in n) r[id]=pick(o[id],n[id]);
    out[k]=r; };
  const earliest=(x,y)=>String(x)<String(y)?x:y, latest=(x,y)=>String(x)>String(y)?x:y, most=(x,y)=>Math.max(+x||0,+y||0);
  const list=k=>[...(Array.isArray(old[k])?old[k]:[]),...(Array.isArray(neu[k])?neu[k]:[])];
  const joined=(k,id)=>{ const by=new Map(); for(const x of list(k)) by.set(id(x),x); return [...by.values()]; };
  for(const k of new Set([...Object.keys(old),...Object.keys(neu)])) if(isObj(old[k])&&isObj(neu[k])) each(k);   // newer per key
  each("done",earliest); each("gold",earliest); each("seen",latest); each("tries",most); each("days",most);
  each("examples",(x,y)=>({n:most(x?.n,y?.n),last:latest(x?.last||"",y?.last||"")}));   // worked examples opened, per skill
  each("solved",(x,y)=>[...new Set([...(Array.isArray(x)?x:[]),...(Array.isArray(y)?y:[])])].sort((p,q)=>p-q));
  out.comets=[...new Set(list("comets"))];
  out.slips=joined("slips",s=>JSON.stringify([s?.at,s?.id,s?.q,s?.m])).sort((x,y)=>String(x?.at).localeCompare(String(y?.at))).slice(-500);
  if(old.quizzes||neu.quizzes) out.quizzes=joined("quizzes",q=>String(q?.at)).sort((x,y)=>String(x?.at).localeCompare(String(y?.at))).slice(-20);
  if(old.cometDay||neu.cometDay) out.cometDay=latest(old.cometDay||"",neu.cometDay||"");
  out.updated=Math.max(+a.updated||0,+b.updated||0);
  return out;
}
const synced=()=>!!(AUTH_URL&&CFG.token);
let pushTimer=null;
async function pullProgress(){
  if(!synced()) return null;
  try{ const r=await api("/api/math/progress"); return r.ok?(await r.json()).progress||{}:null; }catch{ return null; }
}
async function pushProgress(){
  clearTimeout(pushTimer); pushTimer=null;
  const remote=await pullProgress(); if(remote===null) return;
  try{ await api("/api/math/progress",{method:"PUT",keepalive:true,headers:{"Content-Type":"application/json"},
    body:JSON.stringify({progress:mergeProgress(remote,P)})}); }catch{}
}
function queuePush(){ if(!synced()) return; clearTimeout(pushTimer); pushTimer=setTimeout(pushProgress,1500); }
document.addEventListener("visibilitychange",async()=>{
  if(!synced()||!G) return;
  if(document.visibilityState==="hidden"){ if(pushTimer) pushProgress(); return; }
  if(cur) return;   // a question or exam is open: take the other device's work next time
  loadComments();   // the teacher may have reviewed an answer meanwhile
  loadAssignments();
  const remote=await pullProgress(); if(!remote||cur) return;
  P=Sky.ensure(mergeProgress(P,remote)); try{ localStorage.setItem(key(),JSON.stringify(P)); }catch{}
  if(ACTIVE_SUBJECT==="מתמטיקה"&&!root?.hidden) draw();
});

let G=null, BY={}, POST={}, ORDER=[], P={done:{},tries:{},solved:{},at:{}}, root=null, curQ=0, path=null, sheet=null, cur=null, back=null, ACTIVE_SUBJECT="";
const ROUND_WRONG={};   // wrong answers per skill in its current round: from the second the worked example is offered
let nav=null, FIRST=true, COMBO=0, REV=null, QZ=null, UQ=null;   // UQ: the unit quiz on the sheet (see unit quiz below)   // QZ: the practice exam in progress (see quiz below)   // the tab bar; whether the shown question is still at its first try; first-try answers in a row
let picker=null, PH=null, resPicker=null, RES=null;   // RES: the open lesson-resources sheet (see openResources())   // the photo file picker, and the photographed problem on the sheet (see photo())
let advanceTimer=null;
function stopPhone(){
  window.MathlyAnswers?.closeQuestion();
}
function cancelAdvance(){ clearTimeout(advanceTimer); advanceTimer=null; }

function index(graph){
  G=graph; BY=Object.fromEntries(G.skills.map(s=>[s.id,s])); POST=Object.fromEntries(G.skills.map(s=>[s.id,[]]));
  G.skills.forEach(s=>s.prereqs.forEach(p=>POST[p].push(s.id)));
  // the path's order: unit by unit, and in a unit the order of the file (the teaching schedule's),
  // except that a skill waits until the skills it needs in its unit are placed
  ORDER=G.units.flatMap(u=>{
    const left=G.skills.filter(s=>s.unit===u.id), placed=new Set(), out=[];
    while(left.length){
      const i=left.findIndex(s=>s.prereqs.every(p=>placed.has(p)||BY[p].unit!==u.id));
      const [s]=left.splice(i,1); placed.add(s.id); out.push(s.id);
    }
    return out;
  });
}
// the units the student's class studies (its "lessons"); a teacher, or an account in no class, has every unit.
// A skill of a unit the class does not study counts as known: it does not lock the skills that need it.
const shownUnits=()=>{
  const mine=typeof MY_CLASSES==="undefined"?[]:MY_CLASS?[MY_CLASS]:MY_CLASSES, ids=new Set(mine.flatMap(c=>c.lessons||[]));
  const units=G.units.filter(u=>ids.has(u.id)); return units.length?units:G.units;
};
let SHOWN=new Set();
// a skill the server locked (an open-ended question while AI grading is off) is "off": shown, never asked, never blocking
const status=id=>P.done[id]?"done":BY[id].locked?"off":"open";
const next=()=>ORDER.find(id=>SHOWN.has(BY[id].unit)&&status(id)==="open")||null;
const QS=s=>s.questions||[s.sample];
const solvedOf=id=>new Set(P.solved[id]||[]);
const shuffled=a=>{ const out=a.slice(); for(let i=out.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [out[i],out[j]]=[out[j],out[i]]; } return out; };
// a multiple-choice question's buttons, in a new order each time it is shown
const choiceButtons=q=>`<div class="mx-choices">${shuffled(q.choices||[]).map((c,i)=>`<button data-choice="${i}" data-m="${c.correct?"":esc(c.mistake)}"${c.correct?" data-right":""}>${fmt(c.text)}</button>`).join("")}</div>`;
const figures=q=>`${q.graph?plot(q.graph):""}${q.diagram?geometryDiagram(q.diagram):""}${q.figure?figure(q.figure):""}`;
/* A round: a skill with more than ROUND questions asks a random ROUND of them (indexes into its list), the ones not
   solved yet first. A round in progress keeps its questions (P.set); a finished skill gets a new one each time it is
   opened. Progress from before rounds existed was on the first ROUND questions, so it stays there. */
const ROUND=10;
function round(id){
  const n=QS(BY[id]).length; if(n<=ROUND) return [...Array(n).keys()];
  let r=P.set[id];
  if(!Array.isArray(r)||r.length!==ROUND||r.some(i=>!(Number.isInteger(i)&&i>=0&&i<n))){
    if(!P.done[id]&&(P.solved[id]?.length||P.at[id]!=null))   // progress from before rounds: keep what was solved
      r=[...new Set([...(P.solved[id]||[]),P.at[id],...Array(n).keys()].filter(i=>Number.isInteger(i)&&i>=0&&i<n))].slice(0,ROUND);
    else { const got=solvedOf(id), all=shuffled([...Array(n).keys()]); r=[...all.filter(i=>!got.has(i)),...all.filter(i=>got.has(i))].slice(0,ROUND); }
    P.set[id]=r;
  }
  return r;
}
const solvedIn=id=>{ const got=solvedOf(id); return round(id).filter(i=>got.has(i)).length; };
// the round's question after `from` that is not solved yet; once all are solved, simply the next one
const nextQ=(id,from)=>{ const r=round(id), got=solvedOf(id), at=r.indexOf(from), n=r.length;
  for(let k=1;k<=n;k++){ const j=r[(at+k)%n]; if(!got.has(j)) return j; } return r[(at+1)%n]; };

async function show(){
  document.documentElement.classList.add("math-on");
  if(!root){
    root=document.createElement("section"); root.id="mathView"; root.setAttribute("aria-label","מסלול המתמטיקה");
    path=document.createElement("div"); path.className="mx-wrap";
    sheet=document.createElement("div"); sheet.className="mx-layer"; sheet.hidden=true;
    // no capture attribute: the phone offers the camera and the gallery both
    picker=document.createElement("input"); picker.type="file"; picker.accept="image/*"; picker.hidden=true;
    picker.onchange=()=>{ const f=picker.files[0]; picker.value=""; if(f) photo(f); };
    resPicker=document.createElement("input"); resPicker.type="file"; resPicker.accept="image/*"; resPicker.hidden=true;
    resPicker.setAttribute("capture","environment");   // a lesson resource is photographed: the phone opens its camera
    resPicker.onchange=()=>{ const f=resPicker.files[0]; resPicker.value=""; if(f) resourcePhoto(f); };
    nav=document.createElement("nav"); nav.className="mx-nav"; nav.setAttribute("aria-label","ניווט"); nav.hidden=true;
    root.append(path,sheet,picker,resPicker,nav); document.body.append(root); window.MathlySky.mount(root);
    root.addEventListener("click",onClick);
    root.addEventListener("submit",e=>{
      if(e.target.matches?.("[data-review-form]")){ e.preventDefault(); reviewSave(e.target); }
      else if(e.target.matches?.("[data-asg-form]")){ e.preventDefault(); asgSave(e.target); }
    });
    root.addEventListener("change",e=>{ if(e.target.matches?.("[data-report-sort],[data-report-unit]")) reportControl(e.target); });
    document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&helpOpen()) return helpClose(); if(e.key==="Escape"&&cur) QZ?.items?quizQuit():closeSheet(); });   // an exam asks before it is left
  }
  root.hidden=false;
  if(!G){
    path.innerHTML='<p class="mx-note">טוענים את המסלול…</p>';
    try{ const r=await fetch("/api/math/skills"); if(!r.ok) throw new Error(`השרת ענה ${r.status}`); index(await r.json()); }
    catch(e){ path.innerHTML=`<p class="mx-note">לא הצלחנו לטעון את המסלול: ${esc(e.message)}. רעננו את העמוד ונסו שוב.</p>`; return; }
  }
  const remote=await pullProgress();
  P=window.MathlySky.ensure(Object.assign({done:{},tries:{},solved:{},at:{},set:{}},remote?mergeProgress(load(),remote):load()));
  if(remote){ try{ localStorage.setItem(key(),JSON.stringify(P)); }catch{} queuePush(); }   // this device's own work goes up too
  if(!P.set||typeof P.set!=="object") P.set={}; SHOWN=new Set(shownUnits().map(u=>u.id));
  hasExams()?drawSubjectPicker():selectSubject("מתמטיקה");   // no exams yet: straight to math, science is a tap away
  if(CFG.aiReview) aqCount();
  loadComments();
  loadAssignments();
  window.MathlyAnswers?.configure({api,account:CFG.userId,enabled:CFG.answerScans,root,queued:CFG.aiDirect===false,onGraded:({questionId,grading})=>{
    if(grading.result.verdict!=="correct"||P.done[questionId])return;
    const unitWas=unitDone(unitOf(questionId));
    P.done[questionId]=grading.finished_at||new Date().toISOString(); Sky.mastered(P,questionId);
    P.tries[questionId]=(P.tries[questionId]||0)+1;
    const r=Sky.correct(P,questionId,{first:true,n:QS(BY[questionId]).length,finished:true});
    save();draw();rewards(questionId,{r,lit:true,unitWas});
  }});
}
function hide(){ cancelAdvance(); if(root) root.hidden=true; document.documentElement.classList.remove("math-on"); }

// subjects with a path of their own: always offered, even before the class has an exam in them
const PATH_SUBJECTS=["מתמטיקה","מדעים"];
const hasExams=()=>MY_CLASSES.some(row=>(row.exams||[]).some(exam=>exam?.subject&&exam?.date));
function subjectOptions(){
  const bySubject=new Map(PATH_SUBJECTS.map(name=>[name,{name,dates:[],classes:new Set()}]));
  MY_CLASSES.forEach(row=>(row.exams||[]).forEach(exam=>{
    if(!exam?.subject||!exam?.date)return;
    const item=bySubject.get(exam.subject)||{name:exam.subject,dates:[],classes:new Set()};
    item.dates.push(exam.date);item.classes.add(row.name);bySubject.set(exam.subject,item);
  }));
  const today=new Date();today.setHours(0,0,0,0);
  // first the subjects with an exam ahead (nearest first), then those with no exams yet, then those whose exams are over
  return [...bySubject.values()].map(item=>{
    const dates=item.dates.sort(), left=dates.filter(date=>examDate(date)>=today);
    return {...item,dates,left,rank:left.length?0:dates.length?2:1};
  }).sort((a,b)=>a.rank-b.rank||String(a.left[0]||"").localeCompare(String(b.left[0]||"")));
}
// the stars lit in a subject's units out of all its skills; null when the subject has no practice path here
function subjectSkills(name){
  const ids=mineUnits().filter(u=>u.subject===name).flatMap(u=>unitIds(u).filter(live));
  return ids.length?{lit:ids.filter(id=>P.done[id]).length,total:ids.length}:null;
}
function subjectCard(item,today){
  const [icon,tone]=examLooks[item.name]||["●","other"], count=item.dates.length, left=item.left.length, over=count>0&&!left;
  const days=left?Math.round((examDate(item.left[0])-today)/86400000):null, skills=subjectSkills(item.name);
  const dots=count&&count<=12?`<span class="mx-subject-dots" aria-hidden="true">${item.dates.map(date=>`<span${examDate(date)<today?' class="past"':""}></span>`).join("")}</span>`:"";
  const exams=count?(over?"כל המבחנים הסתיימו":`נשארו ${left} מתוך ${count} מבחנים`):item.name==="מדעים"?"חידות בהצבעה כיתתית":"מסלול תרגול";
  const bar=skills?`<span class="mx-subject-bar" role="progressbar" aria-label="מיומנויות שהושלמו" aria-valuemin="0" aria-valuemax="${skills.total}" aria-valuenow="${skills.lit}"><span style="width:${Math.round(100*skills.lit/skills.total)}%"></span></span><small>${skills.lit} מתוך ${skills.total} מיומנויות</small>`:"";
  const when=days===null?"":`<span class="mx-subject-count${days<3?" urgent":days<7?" soon":""}" title="${esc(examFullDate(item.left[0]))}">${days===0?"<b>היום</b>":days===1?"<b>מחר</b>":`<small>בעוד</small><b>${days}</b><small>ימים</small>`}</span>`;
  return `<button class="mx-subject-card exam-${tone}${over?" is-over":""}" data-subject="${esc(item.name)}"><span class="mx-subject-icon" aria-hidden="true">${icon}</span><span><b>${esc(item.name)}</b><small class="mx-subject-left">${dots}${exams}</small>${bar}</span>${when}<i aria-hidden="true">‹</i></button>`;
}
function drawSubjectPicker(){
  ACTIVE_SUBJECT=""; nav.hidden=true;
  const manage=can("management.access"), subjects=subjectOptions(), today=new Date();today.setHours(0,0,0,0);
  path.innerHTML=`<header class="mx-top"><div><h1>המקצועות שלי</h1><p class="mx-sub">בחרו מקצוע כדי לפתוח את המסלול שלו</p></div><div class="mx-acts">${window.MathlyGuide?.button()||""}${teachButton()}${manage?'<button class="mx-btn" data-act="manage">ניהול</button>':""}${window.MathlyAnswers?.pushButton?.()||""}${AUTH_URL?'<button class="mx-btn" data-act="out">יציאה</button>':""}</div></header>
    <section class="mx-subject-grid" aria-label="מקצועות הכיתה">${subjects.map(item=>subjectCard(item,today)).join("")}</section>`;
}
function selectSubject(subject){
  ACTIVE_SUBJECT=subject;
  if(subject==="מתמטיקה")return setView(VIEW);
  nav.hidden=true;
  if(subject==="מדעים"&&window.MathlyScience)return window.MathlyScience.show(path);
  const [icon,tone]=examLooks[subject]||["●","other"];
  path.innerHTML=`<header class="mx-top"><div><h1>${esc(subject)}</h1><p class="mx-sub">המקצועות שלי</p></div><button class="mx-btn" data-act="subjects">לכל המקצועות</button></header><section class="mx-subject-empty exam-${tone}"><span aria-hidden="true">${icon}</span><h2>המסלול של ${esc(subject)} עדיין לא זמין</h2><p>לוח המבחנים של המקצוע כבר מחובר לכיתה. כשהמסלול יתווסף, הוא ייפתח מכאן.</p><button class="mx-btn solid" data-act="subjects">חזרה למקצועות</button></section>`;
}

/* The math screens: home (what you gathered and your streak on top, the path below it) and the collection.
   The rules of the stars, the streak and the comets, and their pictures, are in math-sky.js. */
const Sky=window.MathlySky;
let VIEW="path";
const SOUND_ON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9h4l5-4v14l-5-4H3z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const SOUND_OFF='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9h4l5-4v14l-5-4H3z"/><path d="M16 9l5 6M21 9l-5 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const TABS=[["path","בית",'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 11h2.7v9.5h5.3v-6h3v6h5.3V11h2.7Z"/></svg>'],
  ["sky","האוסף",`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" opacity=".35"/><path d="${Sky.SPARK}" transform="translate(12.5 12.5) scale(.33)"/><path d="${Sky.SPARK}" transform="translate(3.5 3.5) scale(.33)"/></svg>`]];
const STATE_NAME={gold:"כוכב זהב",lit:"הושלמה",fading:"הושלמה, הכוכב דועך",next:"הכוכב הבא",open:"פתוחה",off:"סגורה כרגע"};
const mineUnits=()=>G.units.filter(u=>SHOWN.has(u.id));
const unitOf=id=>G.units.find(u=>u.id===BY[id].unit);
const unitIds=u=>ORDER.filter(id=>BY[id].unit===u.id);
const live=id=>!BY[id].locked;
const seenAt=id=>Date.parse(P.seen?.[id]||P.done[id]||0)||0;
const goldNeed=id=>Sky.goldNeed(Math.min(ROUND,QS(BY[id]).length));
const inDays=d=>d===0?"היום":d===1?"מחר":`בעוד ${d} ימים`;
function unitDone(u){ const ids=unitIds(u).filter(live); return ids.length>0&&ids.every(id=>P.done[id]); }
function skyStats(){
  let lit=0, gold=0, total=0, cons=0;
  const units=mineUnits();
  for(const u of units){
    const ids=unitIds(u).filter(live); total+=ids.length;
    for(const id of ids) if(P.done[id]){ lit++; if(P.gold[id]) gold++; }
    if(unitDone(u)) cons++;
  }
  const fading=ORDER.filter(id=>SHOWN.has(BY[id].unit)&&Sky.fading(P,id)).sort((a,b)=>seenAt(a)-seenAt(b));
  return {lit,gold,total,cons,units:units.length,fading};
}
// the class's next exam in a subject of its units
function nextExam(){
  const today=new Date(); today.setHours(0,0,0,0);
  const exams=(MY_CLASS?[MY_CLASS]:MY_CLASSES).flatMap(row=>{ const subjects=classSubjects(row); return (row.exams||[]).filter(e=>e?.date&&subjects.includes(e.subject)); })
    .filter(e=>examDate(e.date)>=today).sort((a,b)=>a.date.localeCompare(b.date));
  return exams.length?{...exams[0],days:Math.round((examDate(exams[0].date)-today)/86400000)}:null;
}

function topBar(){
  const st=skyStats(), hot=Sky.today(P)>=Sky.GOAL, manage=can("management.access"), on=Sky.soundOn(), streak=Sky.streak(P);
  return `<header class="mx-top"><div class="mx-brand">${Sky.spark()}<span>מתמטיקה</span></div>
    <div class="mx-acts"><button class="mx-btn" data-act="subjects">מקצועות</button>${window.MathlyGuide?.button()||""}${teachButton()}${manage?'<button class="mx-btn" data-act="manage">ניהול</button>':""}${window.MathlyAnswers?.pushButton?.()||""}${AUTH_URL?'<button class="mx-btn" data-act="out">יציאה</button>':""}</div></header>
    <div class="mx-hud"><div class="mx-stats">
      <button class="sky-chip flame${hot?"":" cold"}" data-act="streak" title="${streak} ימים ברצף">${Sky.FLAME}<b>${streak}</b><span class="mx-sr">ימים ברצף</span></button>
      <span class="sky-chip stars" title="${st.lit} כוכבים">${Sky.spark()}<b>${st.lit}</b><span class="mx-sr">כוכבים</span></span>
      <span class="sky-chip golds" title="${st.gold} כוכבי זהב">${Sky.spark()}<b>${st.gold}</b><span class="mx-sr">כוכבי זהב</span></span>
      <span class="sky-chip comets" title="${P.comets.length} שביטים"><i aria-hidden="true">☄</i><b>${P.comets.length}</b><span class="mx-sr">שביטים</span></span>
      <button class="sky-chip snd" data-act="sound" aria-pressed="${on}" aria-label="צלילים">${on?SOUND_ON:SOUND_OFF}</button></div></div>`;
}
function counts(st){
  return `<div class="mx-counts"><div><b>${st.lit}</b><small>מתוך ${st.total} כוכבים</small></div><div class="g"><b>${st.gold}</b><small>כוכבי זהב</small></div>
    <div class="k"><b>${st.cons}</b><small>קבוצות כוכבים</small></div><div class="c"><b>${P.comets.length}</b><small>שביטים</small></div></div>`;
}
/* a unit's constellation as one picture: its outline (whole once the unit is done) and its stars */
function conSvg(u,animate=false){
  const ids=unitIds(u), shp=Sky.shape(u.id,ids.length,u.name), nxt=next(), full=unitDone(u);
  const lines=[...shp.lines,...(full?shp.inner:[])].map(([a,b],k)=>`<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" class="${full?"on":"ghost"}${animate?" draw":""}"${animate?` style="animation-delay:${(k*.1).toFixed(2)}s"`:""}/>`).join("");
  const stars=ids.map((id,i)=>{ const st=Sky.star(P,id,status(id),id===nxt), [x,y]=shp.stars[i], r=st==="gold"?18:["lit","fading","next"].includes(st)?13:7;
    return `<path d="${Sky.SPARK}" transform="translate(${(x-r).toFixed(1)} ${(y-r).toFixed(1)}) scale(${(r/12).toFixed(3)})" class="c-${st}"/>`; }).join("");
  return `<svg class="mx-con" viewBox="34 22 292 ${shp.H-56}" aria-hidden="true">${lines}${stars}</svg>`;
}
const pips=(u,fresh)=>`<div class="sky-pips" aria-hidden="true">${unitIds(u).filter(live).map(id=>Sky.spark(`${P.gold[id]?"g":P.done[id]?"l":""}${id===fresh?" new":""}`)).join("")}</div>`;

// today's goal: right answers so far; opens the streak calendar
function daily(){
  const n=Sky.today(P), goal=Sky.GOAL, done=n>=goal, streak=Sky.streak(P);
  return `<button class="mx-daily${done?" done":""}" data-act="streak"><span class="mx-dline">${Sky.FLAME}
      <b>${done?"היעד היומי הושלם":`היעד היומי: ${Math.min(n,goal)}/${goal} תשובות נכונות`}</b><span class="mx-dgo">לוח הרצף ‹</span></span>
    <span class="mx-meter" aria-hidden="true"><i style="width:${Math.min(100,Math.round(100*n/goal))}%"></i></span>
    <small>${done?`${streak===1?"יום אחד":`${streak} ימים`} ברצף. נתראה מחר!`:`עוד ${goal-n} והרצף ${streak?"ממשיך":"מתחיל"}.`}</small></button>`;
}
/* The streak calendar, a month at a time: days whose goal was met are joined in one band, a forgiven day sits
   in the band in ice, practice short of the goal is a small dot. */
let CAL=null;   // the month shown: {y,m}
const MONTH=new Intl.DateTimeFormat("he-IL",{month:"long",year:"numeric"});
function showStreak(step=0){
  const now=new Date();
  if(!step||!CAL) CAL={y:now.getFullYear(),m:now.getMonth()};
  else{ const d=new Date(CAL.y,CAL.m+step,1); CAL={y:d.getFullYear(),m:d.getMonth()}; }
  const keys=Object.keys(P.days||{}).sort(), first=keys[0]?keys[0].slice(0,7):Sky.dayKey(now).slice(0,7);
  const ym=`${CAL.y}-${String(CAL.m+1).padStart(2,"0")}`, atStart=ym<=first, atNow=ym>=Sky.dayKey(now).slice(0,7);
  const streak=Sky.streak(P), best=Math.max(Sky.best(P),streak), n=Sky.today(P), goal=Sky.GOAL;
  const cells=Sky.month(P,CAL.y,CAL.m,now), on=c=>c&&(c.state==="met"||c.state==="saved");
  const metHere=cells.filter(c=>c?.state==="met").length;
  const grid=cells.map((c,i)=>{
    if(!c) return '<span class="mx-cday blank"></span>';
    const col=i%7, prev=col>0&&on(cells[i-1]), nxt=col<6&&on(cells[i+1]);
    const cls=["mx-cday",c.state&&`s-${c.state}`,on(c)&&prev&&"jp",on(c)&&nxt&&"jn",c.today&&"today",c.future&&"future"].filter(Boolean).join(" ");
    const say=c.state==="met"?"היעד הושלם":c.state==="saved"?"יום שנסלח":c.state==="some"?"תרגול בלי יעד":"";
    return `<span class="${cls}"${say?` title="${say}"`:""}><b>${c.day}</b>${say?`<span class="mx-sr">${say}</span>`:""}</span>`;
  }).join("");
  if(!cur) back=document.activeElement;
  cur="streak";
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div><div class="mx-sheet mx-streak-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
    <div class="mx-shtop"><h3 id="mxTitle">הרצף שלי</h3><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
    <div class="mx-shero${n>=goal?"":" cold"}">${Sky.FLAME}<div><b>${streak}</b><span>${streak===1?"יום ברצף":"ימים ברצף"}</span></div></div>
    <p class="mx-ssay">${n>=goal?"היעד של היום הושלם. הרצף נשמר!":`עוד ${goal-n} תשובות נכונות היום כדי ${streak?"להמשיך":"להתחיל"} את הרצף.`}</p>
    <div class="mx-sstats"><div><b>${best}</b><small>הרצף הארוך ביותר</small></div><div><b>${metHere}</b><small>ימי יעד בחודש</small></div></div>
    <div class="mx-cal"><div class="mx-calhead"><button class="mx-calnav" data-act="cal-prev" aria-label="החודש הקודם"${atStart?" disabled":""}>›</button>
        <b aria-live="polite">${MONTH.format(new Date(CAL.y,CAL.m,1))}</b>
        <button class="mx-calnav" data-act="cal-next" aria-label="החודש הבא"${atNow?" disabled":""}>‹</button></div>
      <div class="mx-calgrid">${["א","ב","ג","ד","ה","ו","ש"].map(d=>`<span class="mx-cdow">${d}</span>`).join("")}${grid}</div>
      <div class="mx-calkey"><span><i class="k-met"></i>יעד הושלם</span><span><i class="k-saved"></i>יום שנסלח</span><span><i class="k-some"></i>תרגול בלי יעד</span></div></div>
    <p class="mx-note">יום נספר ברצף כשעונים בו נכון על ${goal} שאלות. יום אחד שמפספסים לא שובר את הרצף, ושניים ברצף כן.</p></div>`;
  sheet.hidden=false; sheet.querySelector(step>0?"[data-act=cal-next]":step<0?"[data-act=cal-prev]":".mx-x").focus({preventScroll:true});
}
// a short line about the class's next exam, when it is two weeks away or less
function examSoon(){
  const exam=nextExam();
  return exam&&exam.days<=14?`<button class="mx-examsoon" data-view="sky"><b>המבחן ב${esc(exam.subject)} ${inDays(exam.days)}</b><span>ללוח המבחנים ‹</span></button>`:"";
}

/* The path: unit after unit, top to bottom. Each unit is a hub in the middle with its skills orbiting it in order:
   skill 1 sits at the top and the rest follow clockwise, each numbered, with arrows on the ring between them. A stretch
   of the ring is lit once the skill it leaves from is done, so the lit ring leads to where to go next. The unit quiz follows the orbit. */
const ORBIT_R=34;   // the ring's radius, in % of the orbit's width
const isOn=st=>st==="lit"||st==="gold"||st==="fading";
function orbitRing(sts){
  const n=sts.length, a=i=>(-90+360*i/n)*Math.PI/180, pt=(t,r=ORBIT_R)=>[50+r*Math.cos(t),50+r*Math.sin(t)], f=v=>v.toFixed(2);
  const gap=n>1?Math.min(.32,Math.PI/n*.55):0;   // room left around each node (radians)
  const arcs=sts.slice(0,-1).map((st,k)=>{
    const t0=a(k)+gap, t1=a(k+1)-gap, [x0,y0]=pt(t0), [x1,y1]=pt(t1), tm=(a(k)+a(k+1))/2, [mx,my]=pt(tm), deg=tm*180/Math.PI+90;
    return `<path class="${isOn(st)?"on":""}" d="M${f(x0)} ${f(y0)}A${ORBIT_R} ${ORBIT_R} 0 0 1 ${f(x1)} ${f(y1)}"/>
      <path class="mx-arrow${isOn(st)?" on":""}" d="M-1.6 -1.9 1.6 0 -1.6 1.9" transform="translate(${f(mx)} ${f(my)}) rotate(${f(deg)})"/>`; }).join("");
  // the closing stretch, from the last skill back to the first, stays faint: the orbit has a start and an end
  const back=n>2?(()=>{ const [x0,y0]=pt(a(n-1)+gap), [x1,y1]=pt(a(n)-gap); return `<path class="mx-back" d="M${f(x0)} ${f(y0)}A${ORBIT_R} ${ORBIT_R} 0 0 1 ${f(x1)} ${f(y1)}"/>`; })():"";
  return `<svg class="mx-ring" viewBox="0 0 100 100" aria-hidden="true">${back}${arcs}</svg>`;
}
function pathView(){
  const nxt=next(), cls=MY_CLASS?` · כיתת ${esc(MY_CLASS.name)}`:"", teach=can("students.view"), marks=asgMarks();
  const fix=new Set(myPatterns().recurring.map(x=>x.practise));   // skills that a recurring mistake sends back to
  const units=mineUnits().map(u=>{
    const ids=unitIds(u), act=ids.filter(live), lit=act.filter(id=>P.done[id]).length, n=ids.length, full=unitDone(u);
    const sts=ids.map(id=>Sky.star(P,id,status(id),id===nxt));
    const steps=ids.map((id,i)=>{ const st=sts[i], tag=st==="next"?"ממשיכים כאן":fix.has(id)?"לחזק":st==="fading"?"דועך":"", given=marks.get(id);
      const t=(-90+360*i/n)*Math.PI/180, dx=Math.cos(t), dy=Math.sin(t), up=dy<-.3;
      return `<div class="mx-step mx-orb u-${u.id}${up?" up":""}" style="--dx:${dx.toFixed(3)};--dy:${dy.toFixed(3)}">
        <button class="mx-node mx-star st-${st}${fix.has(id)?" fix":""}" data-id="${id}" aria-label="${i+1}. ${esc(plain(BY[id].name))}: ${STATE_NAME[st]}${fix.has(id)?", כדאי לחזק":""}${given?`, משימה מהמורה: ${esc(given.join(", "))}`:""}">${Sky.spark()}<span class="mx-num" aria-hidden="true">${i+1}</span>${given?'<span class="mx-asg-pin" aria-hidden="true">📌</span>':""}${st==="next"?`<span class="mx-perch">${Sky.owl(34)}</span>`:""}</button>
        <span class="mx-lbl l-${st}${fix.has(id)?" l-fix":""}">${fmt(BY[id].short)}${tag?`<em>${tag}</em>`:""}</span></div>`; }).join("");
    const res=teach?` data-act="resources" data-unit="${u.id}"`:"";   // a teacher opens the lesson's resources from its title
    const pct=act.length?Math.round(100*lit/act.length):0;
    return `<section class="mx-unit mx-orbit u-${u.id}${full?" full":""}" id="mx-unit-${u.id}">
      <div class="mx-stage">${orbitRing(sts)}
        <div class="mx-uhead mx-hub${teach?" is-teach":""}"${res} style="--p:${pct}">
          <h2>${esc(u.name)}</h2><span class="mx-pill">${lit}/${act.length}</span>${u.when?`<span class="mx-usub">${esc(u.when)}</span>`:""}</div>
        ${steps}</div>
      ${teach?`<button class="mx-res-open"${res} aria-label="משאבי השיעור ${esc(u.name)}">📷 משאבים</button>`:""}</section>${quizStep(u)}`;
  }).join("");
  return `${topBar()}${commentsCard()}${assignmentsCard()}${daily()}${reviewCard()}${patternsCard()}${examSoon()}${quizCard()}<div class="mx-pghead"><h2>המסלול שלי</h2><p class="mx-sub">אלגברה וגאומטריה כיתה ט׳ · 5 יח״ל${cls}</p></div>
    <div class="mx-trail">
      <div class="mx-start"><span class="mx-flag">${Sky.owl(40)}</span><b>התחלה</b></div>${units}
      <div class="mx-finish" aria-hidden="true">${Sky.spark()}<b>סוף המסלול</b></div></div>
    <p class="mx-note">כל השיעורים פתוחים. בכל יחידה המיומנויות מסודרות סביבה לפי הסדר, מ־1 למעלה ועם כיוון השעון. כוכב נדלק כשעונים נכון על כל השאלות של המיומנות, והופך לזהב אחרי ${3} תשובות נכונות ברצף (או כל השאלות, כשיש פחות). כוכב שלא תרגלו ${Sky.FADE_DAYS} יום דועך, ותשובה נכונה אחת מחזירה לו את האור. ההתקדמות נשמרת במכשיר הזה.</p>`;
}

function collectionView(){
  const st=skyStats();
  return `${topBar()}<div class="mx-pghead"><h1>האוסף שלי</h1><p class="mx-sub">כל מיומנות היא כוכב. כל יחידה שמסיימים מציירת קבוצת כוכבים.</p></div>
    ${counts(st)}
    <div class="mx-sh"><h2>קבוצות כוכבים</h2><span>${st.cons} מתוך ${st.units}</span></div>
    <div class="mx-cons">${mineUnits().map(u=>{ const ids=unitIds(u).filter(live), lit=ids.filter(id=>P.done[id]).length, full=unitDone(u);
      return `<button class="mx-con-card u-${u.id}${full?" full":lit?"":" unknown"}" data-view="path" data-unit="${u.id}">${conSvg(u)}
        <b>${lit?esc(Sky.shape(u.id,1,u.name).name):"?"}</b><small>${esc(u.name)} · ${full?"הושלמה":`${lit}/${ids.length}`}</small></button>`; }).join("")}</div>
    <div class="mx-sh"><h2>שביטים נדירים</h2><span>${P.comets.length} מתוך ${Sky.COMETS.length}</span></div>
    <p class="mx-note">שביטים חולפים לפעמים על המסך בזמן תרגול. מי שלוחץ עליהם בזמן תופס אותם.</p>
    <div class="mx-comets">${Sky.COMETS.map(c=>{ const have=P.comets.includes(c.id);
      return `<button class="mx-comet${have?" have":""}" data-comet="${c.id}" aria-label="${have?esc(c.name):"שביט שעוד לא נתפס"}"><span class="sym">${have?esc(c.sym):"?"}</span><small>${have?esc(c.name):"עוד לא נתפס"}</small></button>`; }).join("")}</div>
    ${(MY_CLASS?[MY_CLASS]:MY_CLASSES).filter(row=>(row.exams||[]).length).map(row=>examBoard(row,true)).join("")}`;
}

function draw(){
  Sky.ensure(P);
  path.innerHTML=VIEW==="sky"?collectionView():pathView();
  nav.hidden=false;
  nav.innerHTML=`<div>${TABS.map(([v,label,icon])=>`<button data-view="${v}"${VIEW===v?' aria-current="page"':""}>${icon}<span>${label}</span></button>`).join("")}</div>`;
  decorateUnits();
}
function setView(view,unit){
  VIEW=view; draw(); root.scrollTop=0;
  const target=view!=="path"?null:unit?root.querySelector(`#mx-unit-${CSS.escape(unit)}`):root.querySelector(".mx-star.st-next")||root.querySelector(".mx-star.st-open");
  if(!target) return;
  target.scrollIntoView({block:unit?"start":"center"});
  cssReady.then(()=>{ if(VIEW===view&&target.isConnected) target.scrollIntoView({block:unit?"start":"center"}); });
}
function showComet(cid){
  const c=Sky.COMETS.find(x=>x.id===cid), have=P.comets.includes(cid);
  if(!c) return;
  if(!cur) back=document.activeElement;
  cur="comet";
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div><div class="mx-sheet mx-comet-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
    <div class="mx-shtop"><h3 id="mxTitle">${have?esc(c.name):"שביט שעוד לא נתפס"}</h3><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
    ${have?`${Sky.cometCard(c)}<p>${esc(c.fact)}</p>`:"<p>שביטים חולפים לפעמים על המסך בזמן תרגול. מי שלוחץ עליהם בזמן תופס אותם, והם נשמרים כאן.</p>"}</div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}
function launchComet(){
  Sky.comet(()=>{
    cancelAdvance();
    const c=Sky.catchComet(P); save(); draw();
    if(c) Sky.celebrate({kind:"gold",title:"תפסתם שביט נדיר!",sub:esc(c.fact),art:Sky.cometCard(c)});
  });
}
/* After a correct answer in `id`: the celebrations it earned, one after another, then a comet perhaps.
   `r`: what Sky.correct changed; `lit`: the skill was finished just now; `unitWas`: its unit was complete before.
   Resolves when the student has seen them all (at once when there was nothing to celebrate). */
function rewards(id,{r,lit,unitWas}){
  const u=unitOf(id), steps=[], name=Sky.shape(u.id,1,u.name).name;
  if(r.gold) steps.push(()=>Sky.celebrate({kind:"gold",title:"כוכב זהב!",sub:`${fmt(BY[id].short)} · ${goldNeed(id)===1?"נכון בניסיון הראשון":`${goldNeed(id)} נכונות ברצף`}`,extra:pips(u,id)}));
  else if(lit) steps.push(()=>Sky.celebrate({kind:"lit",title:"כוכב חדש!",sub:fmt(BY[id].short),extra:pips(u,id)}));
  if(unitDone(u)&&!unitWas) steps.push(()=>Sky.celebrate({kind:"con",title:`קבוצת ${name} הושלמה!`,sub:`כל הכוכבים של ${esc(u.name)} דולקים.`,art:conSvg(u,true)}));
  if(r.revived&&!steps.length) Sky.toast(`<b>${fmt(BY[id].short)}</b> זורח שוב`);
  if(r.goal) steps.push(async()=>{ Sky.sound.goal(); Sky.toast(`יעד יומי הושלם · <b>${Sky.streak(P)} ימים ברצף</b>`); });
  if(Sky.cometDue(P,{gold:r.gold})){ P.cometDay=Sky.dayKey(); save(); steps.push(()=>new Promise(res=>setTimeout(()=>{ launchComet(); res(); },600))); }
  return steps.reduce((p,step)=>p.then(step),Promise.resolve()).then(()=>{ if(steps.length) draw(); });
}

function chips(ids){
  return ids.length?ids.map(id=>`<button class="mx-chip u-${BY[id].unit}${P.done[id]?" is-done":""}" data-id="${id}">${P.done[id]?"✓ ":""}${fmt(BY[id].short)}</button>`).join(""):'<em>אין</em>';
}
/* ---------- the teacher's assignments (app/assignments.py) ----------
   GET /api/math/assignments gives the student's classes' assignments and when they handed in each unit quiz. Whether an
   item is done is worked out on the page (Sky.assignmentState) from the progress and those sittings, so the card and the
   teacher's report always agree. A card on the home screen lists the open ones, and the done ones for two weeks. */
let ASG=null;
async function loadAssignments(){
  if(!CFG.userId||!MY_CLASSES.length) return;
  try{ const r=await api("/api/math/assignments",{cache:"no-store"}); ASG=r.ok?await r.json():null; }catch{ ASG=null; }
  if(ACTIVE_SUBJECT==="מתמטיקה"&&root&&!root.hidden&&!cur) draw();   // not over the subject picker
}
function asgView(){
  if(!ASG?.assignments?.length) return null;
  const now=new Date(), cutoff=Sky.jerusalemDay(now-14*864e5);
  const rows=ASG.assignments.map(a=>({a,s:Sky.assignmentState(a,P,ASG.sittings,now)}));
  return {open:rows.filter(x=>!x.s.finished).sort((p,q)=>p.a.due_on.localeCompare(q.a.due_on)),
    done:rows.filter(x=>x.s.finished&&x.a.due_on>=cutoff).sort((p,q)=>q.a.due_on.localeCompare(p.a.due_on))};
}
const asgDate=due=>new Date(due+"T12:00:00").toLocaleDateString("he-IL",{day:"numeric",month:"numeric"});
const asgUnit=id=>esc(G.units.find(u=>u.id===id)?.name||id);
function asgItemLabel(item){
  if(item.kind==="skill") return BY[item.id]?fmt(BY[item.id].name):esc(item.id);
  if(item.kind==="unit_quiz") return `בוחן מסכם: ${asgUnit(item.unit)}`;
  return `מבחן תרגול: ${(item.units||[]).map(asgUnit).join(", ")}`;
}
// the skills of unfinished assignments, with the titles, for the marker on the path
function asgMarks(){
  const marks=new Map();
  for(const {a} of asgView()?.open||[]) for(const item of a.items) if(item.kind==="skill") marks.set(item.id,[...(marks.get(item.id)||[]),a.title]);
  return marks;
}
function assignmentsCard(){
  const v=asgView(); if(!v||(!v.open.length&&!v.done.length)) return "";
  const several=new Set(ASG.assignments.map(a=>a.class_id)).size>1;
  const open=v.open.map(({a,s})=>`<article class="mx-asg${s.overdue?" late":""}">
      <div class="mx-asg-head"><b>${esc(a.title)}</b><span class="mx-asg-due">${s.overdue?"באיחור · ":""}עד ${asgDate(a.due_on)}</span></div>
      ${several?`<small class="mx-small">${esc(a.class_name)}</small>`:""}${a.note?`<p class="mx-asg-note">${esc(a.note)}</p>`:""}
      <p class="mx-asg-count"><b>${s.doneCount}</b> מתוך ${s.total} הושלמו</p>
      <ul class="mx-asg-items">${s.items.map(x=>`<li class="${x.done?"done":""}"><span aria-hidden="true">${x.done?"✓":"○"}</span> ${asgItemLabel(x.item)}${x.done?'<span class="mx-sr"> (הושלם)</span>':""}${x.known?"":" <small>(לא ניתן לבדוק כרגע)</small>"}</li>`).join("")}</ul>
      <button type="button" class="mx-btn solid" data-asg-go="${esc(a.id)}">${s.doneCount?"להמשיך":"להתחיל"}: ${asgItemLabel(s.items[s.next].item)}</button></article>`).join("");
  const done=v.done.length?`<details class="mx-asg-done"><summary>הושלמו (${v.done.length})</summary><ul>${v.done.map(({a,s})=>
    `<li>✓ ${esc(a.title)} <small>עד ${asgDate(a.due_on)}${s.late?" · הוגשה באיחור":""}</small></li>`).join("")}</ul></details>`:"";
  return `<section class="mx-asgs" aria-label="משימות מהמורה"><h2>משימות מהמורה</h2>${open}${done}</section>`;
}
// opens the first item of the assignment that is not done
function asgGo(id){
  const a=ASG?.assignments.find(x=>x.id===id); if(!a) return;
  const s=Sky.assignmentState(a,P,ASG.sittings), item=s.items[s.next]?.item; if(!item) return;
  if(item.kind==="skill") return BY[item.id]&&open(item.id);
  if(item.kind==="unit_quiz") return uqIntro(item.unit);
  stopQuizClock(); QZ=null; return quizSetup(item.units);
}

/* Answers the teacher has reviewed that the student has not opened since (GET /api/math/teacher-comments): a card on
   the home screen opens the first one. Opening an answer tells the server it was seen, and drops it from the list. */
let TC=[];
async function loadComments(){
  if(!CFG.userId||!CFG.answerScans) return;
  try{ const r=await api("/api/math/teacher-comments",{cache:"no-store"}); TC=r.ok?(await r.json()).comments||[]:[]; }catch{ TC=[]; }
  if(ACTIVE_SUBJECT==="מתמטיקה"&&root&&!root.hidden&&!cur) draw();   // not over the subject picker
}
const commentSeen=pred=>{ const n=TC.length; TC=TC.filter(c=>!pred(c)); return TC.length!==n; };
function commentsCard(){
  if(!TC.length) return "";
  const c=TC[0], more=TC.length-1;
  return `<button type="button" class="mx-teacher-comment" data-comment="${esc(c.attempt_id)}"><b>המורה הגיב על תשובה שלכם</b>
    <span>${fmt(c.question||"")}${c.score==null?"":` · ${c.score}/100`}${more?` · ועוד ${more}`:""}</span></button>`;
}
function openComment(attemptId){
  const c=TC.find(x=>x.attempt_id===attemptId); if(!c) return;
  const [kind,uid]=String(c.question_id).split(":");
  if(kind==="quiz"){
    const h=(uqState(uid).history||[]).findIndex(e=>(e.attempts||[]).includes(attemptId));
    return h>=0?uqResult(uid,h):uqIntro(uid);   // this device does not have that sitting: the quiz page lists the past ones
  }
  if(BY[c.question_id]) open(c.question_id);
}
/* ---------- help while practising a skill ----------
   The "?" in a skill's sheet opens a panel on top of the question: the skill's description, its worked example (a
   question of its own, solved one step at a time with the reason for each) and the teacher's explanations of it. The
   question underneath is not touched, so closing the panel returns to it as it was. The worked example is also offered
   after the second mistake in a round. Opening the example is kept (P.examples) for the teacher's report; it changes
   nothing about finishing or gold, which still need clean first-try answers. */
let helpBack=null;
const helpOpen=()=>!!sheet?.querySelector(".mx-help-wrap");
function helpClose(){ const el=sheet?.querySelector(".mx-help-wrap"); if(!el) return; el.remove(); helpBack?.focus?.({preventScroll:true}); helpBack=null; }
function exampleCard(ex){
  return `<section class="mx-example"><h4>דוגמה פתורה</h4><p class="mx-example-q">${fmt(ex.question)}</p>
    <ol class="mx-example-steps">${ex.steps.map((st,i)=>`<li${i?" hidden":""}><b>${fmt(st.do)}</b><span>${fmt(st.why)}</span></li>`).join("")}</ol>
    <p class="mx-example-answer" hidden><b>התשובה: </b>${fmt(ex.answer)}</p>
    <button type="button" class="mx-btn" data-example-next>${ex.steps.length>1?"הצעד הבא":"הצגת התשובה"}</button></section>`;
}
// one more step, then the answer
function exampleNext(btn){
  const box=btn.closest(".mx-example"), next=box.querySelector(".mx-example-steps li[hidden]");
  if(next){ next.hidden=false; if(!box.querySelector(".mx-example-steps li[hidden]")) btn.textContent="הצגת התשובה"; next.scrollIntoView({block:"nearest"}); return; }
  box.querySelector(".mx-example-answer").hidden=false; btn.hidden=true;
}
function showHelp(id){
  const s=BY[id]; if(!s||!sheet||sheet.hidden) return;
  if(s.example){ const e=((P.examples||={})[id]||={n:0,last:""}); e.n++; e.last=new Date().toISOString(); save(); }
  if(!helpOpen()) helpBack=document.activeElement;
  sheet.querySelector(".mx-help-wrap")?.remove();
  const el=document.createElement("div"); el.className="mx-help-wrap";
  el.innerHTML=`<div class="mx-scrim" data-act="help-close"></div>
    <div class="mx-sheet mx-help u-${s.unit}" role="dialog" aria-modal="true" aria-labelledby="mxHelpTitle">
      <div class="mx-shtop"><h3 id="mxHelpTitle">עזרה: ${fmt(s.name)}</h3><div class="mx-shacts"><button class="mx-x" data-act="help-close" aria-label="חזרה לשאלה">✕</button></div></div>
      <p>${fmt(s.description)}</p>
      ${s.example?exampleCard(s.example):'<p class="mx-note">לכישור הזה עוד אין דוגמה פתורה.</p>'}
      <div class="mx-help-resources" data-help-resources="${esc(id)}"></div>
      <button type="button" class="mx-btn solid" data-act="help-close">חזרה לשאלה</button></div>`;
  sheet.append(el); el.querySelector(".mx-x").focus({preventScroll:true});
  fillExplanations(el.querySelector("[data-help-resources]"),s.unit,r=>r.skill_id===id);
}
function open(id){
  commentSeen(c=>c.question_id===id);
  stopPhone();
  cancelAdvance();
  const s=BY[id], st=status(id), unit=G.units.find(u=>u.id===s.unit), all=QS(s);
  if(P.done[id]&&cur!==id) delete P.set[id];   // a finished skill opened again: a new round
  const r=round(id), n=r.length;
  curQ=r.includes(P.at[id])?P.at[id]:r[0];
  const q=all[curQ], openEnded=q.type==="open-ended", got=solvedOf(id), gotN=r.filter(i=>got.has(i)).length;
  if(!cur) back=document.activeElement;
  cur=id; FIRST=true; REV=null; stopQuizClock(); QZ=null; stopUnitQuiz();
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet u-${s.unit}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(unit.name)}</span>${s.core?' <span class="mx-core">ליבה 5 יח״ל</span>':""}
        <h3 id="mxTitle">${fmt(s.name)}</h3><small class="mx-src">${s.month?`בפריסה: ${esc(s.month)}`:esc(unit.source)}${st==="done"?" · הושלמה ✓":""}</small></div>
        <div class="mx-shacts">${window.MathlyBoard?.button()||""}<button class="mx-helpbtn" data-help="${id}" aria-label="עזרה: ההסבר והדוגמה הפתורה" title="עזרה">?</button><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div></div>
      <p>${fmt(s.description)}</p>
      <div class="mx-q">${n>1?`<div class="mx-qprog"><span>שאלה ${r.indexOf(curQ)+1} מתוך ${n}</span><span class="mx-qdots" aria-label="נפתרו ${gotN} מתוך ${n}">${r.map(i=>`<i class="${got.has(i)?"ok":""}${i===curQ?" now":""}"></i>`).join("")}</span></div>`:""}
        <p>${fmt(q.question)}</p>${figures(q)}
        ${st==="off"?'<p class="mx-note mx-off">השאלה הזו סגורה כרגע לתשובות. היא לא נדרשת כדי להתקדם במסלול.</p>':openEnded?'<div class="mx-answer"></div>':choiceButtons(q)}
        <div class="mx-fb" aria-live="polite"></div></div>
      <div class="mx-sec mx-skill-res" data-skill-res hidden></div>
      <div class="mx-sec"><h4>דורשת</h4><div class="mx-chips">${chips(s.prereqs)}</div></div>
      <div class="mx-sec"><h4>פותחת</h4><div class="mx-chips">${chips(POST[id])}</div></div>
    </div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  window.MathlyBoard?.mount(sheet,`${id}:${curQ}`,{question:()=>sheet.querySelector(".mx-q")});   // the sketch board beside the exercise, when the student has it on
  sheet.querySelector(".mx-x").focus({preventScroll:true});
  if(openEnded&&st!=="off")window.MathlyAnswers?.mountQuestion(sheet.querySelector(".mx-answer"),id,s.question_version);
  fillExplanations(sheet.querySelector("[data-skill-res]"),s.unit,r=>r.skill_id===id);
}
function closeSheet(){ stopPhone(); dropResources(); dropQueue(); dropReview(); cancelAdvance(); REV=null; stopQuizClock(); QZ=null; stopUnitQuiz(); if(sheet)sheet.hidden=true; cur=null; back?.focus?.({preventScroll:true}); back=null; }

// counts down, then opens `target` (a skill id); stops if the student moved on in the meantime
function autoAdvance(id,target){
  let seconds=3;
  const countdown=sheet.querySelector(".mx-countdown");
  const tick=()=>{
    if(cur!==id||sheet.hidden||root.hidden) return cancelAdvance();
    if(seconds===0) return open(target);
    countdown.textContent=target===id?`השאלה הבאה בעוד ${seconds}…`:`התרגיל הבא בעוד ${seconds}…`;
    seconds--;
    advanceTimer=setTimeout(tick,1000);
  };
  tick();
}

function answer(btn){
  if(btn.disabled) return;
  if(QZ) return quizPick(btn);
  if(REV) return reviewAnswer(btn);
  const id=cur, m=btn.dataset.m, fb=sheet.querySelector(".mx-fb"), n=round(id).length, qi=curQ;
  const buttons=sheet.querySelectorAll("[data-choice]");
  buttons.forEach(b=>b.classList.remove("right","wrong"));
  btn.classList.add(m?"wrong":"right");
  P.tries[id]=(P.tries[id]||0)+1;
  if(n>1) P.at[id]=nextQ(id,qi);
  if(!m){
    const all=solvedOf(id); all.add(qi); P.solved[id]=[...all].sort((a,b)=>a-b);
    const gotN=solvedIn(id);   // solved in this round
    const missed=new Set(P.missed[id]||[]), recovered=missed.delete(qi); P.missed[id]=[...missed];
    // done once every question is solved and the last answers were right at the first try
    const run=FIRST?(P.run[id]||0)+1:0, need=Sky.masterNeed(n);
    const first=!P.done[id]&&gotN>=n&&run>=need, unitWas=unitDone(unitOf(id));
    if(first){ P.done[id]=new Date().toISOString(); Sky.mastered(P,id); delete ROUND_WRONG[id]; }
    COMBO=FIRST?COMBO+1:0;
    const persisted=!FIRST;
    const r=Sky.correct(P,id,{first:FIRST,n,finished:!!P.done[id]}); FIRST=false;
    save(); draw();
    buttons.forEach(b=>b.disabled=true);
    COMBO>=2?Sky.sound.combo(COMBO):Sky.sound.ok(); Sky.buzz(25); Sky.burstAt(btn,14);
    const ok=`<b>${Sky.praise({recovered,persisted,combo:COMBO})}</b>${COMBO>=2?`<span class="mx-combo">${Sky.FLAME}${COMBO} ברצף</span>`:""}`;
    const after=rewards(id,{r,lit:first,unitWas}), then=go=>after.then(()=>{ if(cur===id&&!sheet.hidden&&fb.isConnected) go(); });   // not once another question is shown
    if(!P.done[id]){
      const left=need-run, say=gotN<n?`פתרתם ${gotN} מתוך ${n} שאלות במיומנות הזו.`
        :n===1?"כדי לסיים צריך לענות נכון בניסיון הראשון. נסו את השאלה שוב, הפעם בסדר אחר."
        :`כל השאלות נפתרו. עוד ${left===1?"תשובה נכונה אחת":`${left} תשובות נכונות`} ברצף, בניסיון הראשון, כדי לסיים.`;
      fb.innerHTML=`<div class="mx-ok">${ok}<span>${say}</span>
        <span class="mx-countdown"></span><button class="mx-btn solid" data-id="${id}">${n===1?"לנסות שוב":"לשאלה הבאה"}</button></div>`;
      return n===1?then(()=>{}):then(()=>autoAdvance(id,id));
    }
    const nxt=next();
    fb.innerHTML=`<div class="mx-ok">${ok}${first?`<span>${n>1?`פתרתם את כל ${n} השאלות. `:""}המיומנות סומנה כהושלמה.</span>`:""}
      ${nxt&&nxt!==id?`<span class="mx-countdown"></span><button class="mx-btn solid" data-id="${nxt}">המשך עכשיו: ${fmt(BY[nxt].short)}</button>`
        :nxt?"":"<span>סיימתם את כל המסלול. כל הכבוד!</span>"}
      ${n>1?`<button class="mx-btn" data-id="${id}">עוד שאלה במיומנות הזו</button>`:""}</div>`;
    if(nxt&&nxt!==id) then(()=>autoAdvance(id,nxt));
    return;
  }
  // a mistake is quiet: no sound, no vibration, and words about the mistake, not about the student
  Sky.wrong(P,id); Sky.slip(P,id,qi,m,"practice"); FIRST=false; COMBO=0;
  const missed=new Set(P.missed[id]||[]); missed.add(qi); P.missed[id]=[...missed];
  save();
  const M=G.mistakes[m], to=M.back&&M.back!==id?M.back:null;
  // with a list of questions, a missed question comes back later, shuffled; the right answer is not shown,
  // so solving it then shows understanding, not memory
  if(n>1) buttons.forEach(b=>b.disabled=true); else btn.disabled=true;
  // from the second mistake in the round the worked example is offered (the first is often a slip, and the tip covers it)
  ROUND_WRONG[id]=(ROUND_WRONG[id]||0)+1;
  const offer=ROUND_WRONG[id]>=2&&BY[id].example?`<button type="button" class="mx-btn" data-example="${id}">איך פותרים? דוגמה פתורה</button>`:"";
  fb.innerHTML=`<div class="mx-bad"><small class="mx-small">טעות נפוצה, וטוב שהיא עולה עכשיו</small><b>${fmt(M.name)}</b><span>${fmt(M.tip)}</span>
    ${offer}
    ${n>1?`<span class="mx-small">השאלה תחזור אחרי שאר השאלות, ותוכלו לנסות אותה שוב.</span><button class="mx-btn solid" data-id="${id}">לשאלה הבאה</button>`:""}
    ${to?`<button class="mx-btn" data-id="${to}">לחזק קודם את: ${fmt(BY[to].short)}</button>`:n>1?"":"<span class=\"mx-small\">אפשר לבחור תשובה אחרת.</span>"}
    ${patternNote(m,[id,to])}</div>`;
}

/* ---------- spaced review ----------
   Finished skills come back after growing gaps (Sky.mastered/reviewed/due). A review is a few questions from different
   units, mixed, and the skill's name is shown only after the answer: choosing the method is part of the question. */
const REVIEW_SIZE=3;
const choiceSkill=id=>QS(BY[id]).some(q=>q.choices);
const dueReviews=()=>ORDER.filter(id=>SHOWN.has(BY[id].unit)&&live(id)&&choiceSkill(id)&&Sky.due(P,id))
  .sort((a,b)=>(P.review[a]?.due||"").localeCompare(P.review[b]?.due||"")||seenAt(a)-seenAt(b));
function reviewCard(){
  const n=dueReviews().length; if(!n) return "";
  return `<button class="mx-review" data-act="review"><b>חזרה מעורבת</b>
    <span>${n===1?"מיומנות אחת מחכה":`${n} מיומנויות מחכות`} לחזרה. ${Math.min(n,REVIEW_SIZE)} שאלות מנושאים שונים, מעורבבות, כדי שמה שלמדתם יישאר.</span>
    <span class="mx-dgo">להתחיל ‹</span></button>`;
}
/* ---------- misconception patterns ----------
   The mistakes that keep coming back, across skills (Sky.patterns over P.slips): a card on home, and a sheet with what
   to practise for each. The words are about the mistake, never about the student; a pattern that stopped is a win. */
function myPatterns(){
  const known=x=>G.mistakes[x.m]&&BY[x.practise], {recurring,stopped}=Sky.patterns(P,G.mistakes);
  return {recurring:recurring.filter(known),stopped:stopped.filter(known)};
}
// after a mistake: a line when this mistake is now a recurring one, with its skill to strengthen (unless offered already)
function patternNote(m,offered=[]){
  const x=myPatterns().recurring.find(x=>x.m===m); if(!x) return "";
  return `<span class="mx-pattern-note">הטעות הזו חזרה ${timesWord(x.n)} ${inSkills(x.skills.length)} בחודש האחרון. כדאי לחזק את הבסיס שלה, והיא תיעלם גם בשאר הנושאים.</span>
    ${offered.includes(x.practise)?"":`<button class="mx-btn" data-id="${x.practise}">לחזק: ${fmt(BY[x.practise].short)}</button>`}`;
}
const inSkills=k=>k===1?"במיומנות אחת":`ב־${k} מיומנויות`;
const timesWord=n=>n===1?"פעם אחת":`${n} פעמים`;
const daysAgo=iso=>{ const d=Math.round((Date.parse(Sky.dayKey())-Date.parse(Sky.dayKey(new Date(iso))))/86400000); return d<=0?"היום":d===1?"אתמול":`לפני ${d} ימים`; };
function patternsCard(){
  const {recurring,stopped}=myPatterns(), top=recurring[0];
  if(!top&&!stopped.length) return "";
  const say=top?`${fmt(G.mistakes[top.m].name)}: חזר ${timesWord(top.n)} ${inSkills(top.skills.length)} לאחרונה. כדאי לחזק.`
    :`${fmt(G.mistakes[stopped[0].m].name)}: הדפוס הזה כבר לא חוזר. התיקון עבד!`;
  return `<button class="mx-patterns" data-act="patterns"><b>דפוסים שחוזרים</b><span>${say}</span>
    <span class="mx-dgo">${top?"מה לחזק ‹":"לראות ‹"}</span></button>`;
}
function showPatterns(){
  const {recurring,stopped}=myPatterns();
  const row=x=>{ const M=G.mistakes[x.m];
    return `<li><b>${fmt(M.name)}</b><span>${fmt(M.tip)}</span>
      <small class="mx-small">${timesWord(x.n)} ${inSkills(x.skills.length)} · לאחרונה ${daysAgo(x.last)}</small>
      <button class="mx-btn solid" data-id="${x.practise}">לחזק: ${fmt(BY[x.practise].short)}</button></li>`; };
  if(!cur) back=document.activeElement;
  cur="patterns";
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div><div class="mx-sheet mx-patterns-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
    <div class="mx-shtop"><div><h3 id="mxTitle">דפוסים שחוזרים</h3><small class="mx-src">טעויות שחזרו בחודש האחרון, גם בנושאים שונים.</small></div>
      <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
    ${recurring.length?`<ol class="mx-pattern-list">${recurring.map(row).join("")}</ol>
      <p class="mx-small">טעות שחוזרת היא רמז למה שכדאי לחזק. כשמתרגלים את הבסיס שלה, היא נעלמת גם בשאר הנושאים.</p>`
      :"<p>כרגע אין טעות שחוזרת. כל הכבוד!</p>"}
    ${stopped.length?`<h4>דפוסים שנעלמו</h4><ul class="mx-pattern-list gone">${stopped.map(x=>`<li><b>${fmt(G.mistakes[x.m].name)}</b>
      <small class="mx-small">לא חזר כבר ${daysAgo(x.last).replace("לפני ","")}. התיקון עבד!</small></li>`).join("")}</ul>`:""}</div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  sheet.querySelector(".mx-x").focus({preventScroll:true});
}
// the oldest due skills, one per unit first, in a mixed order; a random multiple-choice question of each
function startReview(){
  const due=dueReviews(), pick=[], units=new Set();
  for(const id of due) if(pick.length<REVIEW_SIZE&&!units.has(BY[id].unit)){ pick.push(id); units.add(BY[id].unit); }
  for(const id of due) if(pick.length<REVIEW_SIZE&&!pick.includes(id)) pick.push(id);
  if(!pick.length) return;
  const items=shuffled(pick).map(id=>{ const qs=QS(BY[id]).map((q,i)=>i).filter(i=>QS(BY[id])[i].choices); return {id,qi:qs[Math.floor(Math.random()*qs.length)]}; });
  if(!cur) back=document.activeElement;
  stopQuizClock(); QZ=null; REV={items,i:0,right:0}; openReview();
}
function openReview(){
  cancelAdvance();
  const {items,i}=REV, it=items[i], q=QS(BY[it.id])[it.qi];
  cur="review"; FIRST=true;
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-review-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">חזרה מעורבת</span><h3 id="mxTitle">שאלה ${i+1} מתוך ${items.length}</h3>
        <small class="mx-src">מאיזה נושא השאלה? זה חלק מהתרגול.</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <div class="mx-q"><p>${fmt(q.question)}</p>${figures(q)}${choiceButtons(q)}<div class="mx-fb" aria-live="polite"></div></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  sheet.querySelector(".mx-x").focus({preventScroll:true});
}
const inDaysWord=d=>d===1?"מחר":`בעוד ${d} ימים`;
function reviewAnswer(btn){
  const it=REV.items[REV.i], id=it.id, m=btn.dataset.m, ok=!m, fb=sheet.querySelector(".mx-fb"), s=BY[id];
  sheet.querySelectorAll("[data-choice]").forEach(b=>b.disabled=true);
  btn.classList.add(ok?"right":"wrong");
  P.tries[id]=(P.tries[id]||0)+1;
  Sky.reviewed(P,id,ok);
  const gap=Math.round((Date.parse(P.review[id].due)-Date.parse(Sky.dayKey()))/86400000);
  const last=REV.i+1>=REV.items.length, go=`<button class="mx-btn solid" data-act="review-next">${last?"לסיכום":"לשאלה הבאה"}</button>`;
  if(ok){
    REV.right++;
    const r=Sky.correct(P,id,{first:true,n:QS(s).length,finished:true});
    save(); draw(); Sky.sound.ok(); Sky.burstAt(btn,14);
    fb.innerHTML=`<div class="mx-ok"><b>${Sky.praise()}</b><span>הנושא: ${fmt(s.name)}. החזרה הבאה עליו ${inDaysWord(gap)}.</span>${go}</div>`;
    rewards(id,{r,lit:false,unitWas:true});
    return;
  }
  Sky.wrong(P,id); Sky.slip(P,id,it.qi,m,"review"); save(); draw();
  const M=G.mistakes[m];
  fb.innerHTML=`<div class="mx-bad"><small class="mx-small">הנושא: ${fmt(s.name)}</small><b>${fmt(M.name)}</b><span>${fmt(M.tip)}</span>
    <span class="mx-small">שכחה היא חלק מהלמידה. הנושא יחזור מחר.</span>${go}
    <button class="mx-btn" data-id="${id}">לתרגל את ${fmt(s.short)}</button>${patternNote(m,[id])}</div>`;
}
function reviewNext(){
  if(REV.i+1<REV.items.length){ REV.i++; return openReview(); }
  const {right,items}=REV, more=dueReviews().length;
  sheet.querySelector(".mx-q").innerHTML=`<div class="mx-ok"><b>החזרה הסתיימה</b>
    <span>${right} מתוך ${items.length} נכונות. ${right===items.length?"הכול נשמר בזיכרון.":"מה שלא הצליח יחזור מחר, וזה בדיוק מה שמחזק אותו."}</span>
    ${more?`<button class="mx-btn solid" data-act="review">עוד חזרה (${more})</button>`:""}<button class="mx-btn" data-act="close">חזרה למסלול</button></div>`;
  REV=null;
}

/* ---------- practice exam ----------
   Like the real thing: questions from several units, mixed, the skill's name hidden, no feedback until it is handed in.
   It covers what the schedule taught before the class's next exam (or before this month, without one); the student can
   change the units. The report counts the answers per unit, names the three mistakes to work on with their skills, and
   brings the finished skills that went wrong back to today's review. Nothing on the path is locked by it.
   The results are kept in P.quizzes (newest last). */
const QUIZ_SIZE=12, QUIZ_MIN_PER_Q=3.5;   // a relaxed pace: minutes per question, shown, never enforced
const SCHOOL_MONTHS=["ספטמבר","אוקטובר","נובמבר","דצמבר","ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט"];
const schoolMonth=d=>(d.getMonth()+4)%12;   // September is 0
const skillMonth=id=>{ const m=String(BY[id].month||"").split("–")[0].trim(); const i=SCHOOL_MONTHS.indexOf(m); return i<0?99:i; };
// the exam the practice prepares for: the class's next one within a month, if any
const quizExam=()=>{ const e=typeof nextExam==="function"?nextExam():null; return e&&e.days<=30?e:null; };
function quizUnits(){
  const exam=quizExam(), until=exam?schoolMonth(examDate(exam.date)):schoolMonth(new Date());
  const units=mineUnits().map(u=>({u,ids:unitIds(u).filter(id=>live(id)&&choiceSkill(id))})).filter(x=>x.ids.length);
  let on=units.filter(x=>x.ids.some(id=>skillMonth(id)<until));
  if(!on.length) on=units.filter(x=>x.ids.some(id=>skillMonth(id)<=until));   // the first month of the year
  const offered=units.filter(x=>x.ids.some(id=>skillMonth(id)<=until));   // taught by then; the exam's own month may be added
  return {exam,offered,on:new Set(on.map(x=>x.u.id))};
}
function quizCard(){
  const {exam,on}=quizUnits(); if(!on.size) return "";
  const last=(P.quizzes||[]).at(-1);
  return `<button class="mx-quiz-card" data-act="quiz"><b>מבחן תרגול${exam?` לקראת המבחן ${inDays(exam.days)}`:""}</b>
    <span>${QUIZ_SIZE} שאלות מ־${on.size} יחידות, מעורבבות, כמו במבחן. המשוב מגיע בסוף, עם תוכנית: מה לחזק עד המבחן.</span>
    ${last?`<span>בפעם הקודמת: ${last.right} מתוך ${last.n}</span>`:""}<span class="mx-dgo">להתחיל ‹</span></button>`;
}
function quizSetup(preset){
  let {exam,offered,on}=quizUnits();
  if(Array.isArray(preset)){   // an assignment asks for these units: they are offered whatever the schedule says, and chosen
    const all=mineUnits().map(u=>({u,ids:unitIds(u).filter(id=>live(id)&&choiceSkill(id))})).filter(x=>x.ids.length);
    offered=[...offered,...all.filter(x=>preset.includes(x.u.id)&&!offered.some(o=>o.u.id===x.u.id))];
    on=new Set(preset.filter(id=>offered.some(o=>o.u.id===id)));
  }
  if(!cur) back=document.activeElement;
  cur="quiz"; QZ={setup:true,on,offered};
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-quiz-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">מבחן תרגול</span><h3 id="mxTitle">${exam?`לקראת המבחן ב${esc(exam.subject)} ${inDays(exam.days)}`:"מבחן תרגול"}</h3>
        <small class="mx-src">${QUIZ_SIZE} שאלות · זמן מומלץ: כ־${Math.round(QUIZ_SIZE*QUIZ_MIN_PER_Q/5)*5} דקות, בלי לחץ: השעון רק מראה.</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p>${Array.isArray(preset)?"המורה ביקש מבחן תרגול על היחידות המסומנות. כדי שהמשימה תיחשב, השאירו את כולן מסומנות.":`אילו יחידות במבחן? סימנו את מה שנלמד עד ${exam?"המבחן":"עכשיו"}. אפשר לשנות.`}</p>
      <div class="mx-quiz-units">${offered.map(({u})=>`<button class="mx-btn" data-quiz-unit="${u.id}" aria-pressed="${on.has(u.id)}">${esc(u.name)}</button>`).join("")}</div>
      <p class="mx-small">השאלות מעורבבות ושם הנושא לא מופיע: לזהות איזו דרך מתאימה זה חלק מהמבחן. אין משוב באמצע, כמו במבחן אמיתי.</p>
      <button class="mx-btn solid" data-act="quiz-start"${on.size?"":" disabled"}>להתחיל</button></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}
function quizToggle(uid){
  if(!QZ?.setup) return;
  QZ.on.has(uid)?QZ.on.delete(uid):QZ.on.add(uid);
  sheet.querySelector(`[data-quiz-unit="${CSS.escape(uid)}"]`).setAttribute("aria-pressed",QZ.on.has(uid));
  sheet.querySelector("[data-act=quiz-start]").disabled=!QZ.on.size;
}
// questions from the chosen units in proportion to their skills: the units take turns, each turn a skill not used yet
function quizStart(){
  const units=QZ.offered.filter(x=>QZ.on.has(x.u.id)).map(x=>({u:x.u,ids:shuffled(x.ids)}));
  const total=units.reduce((n,x)=>n+x.ids.length,0), items=[], used=new Set();
  const share=units.map(x=>({...x,want:Math.max(1,Math.round(QUIZ_SIZE*x.ids.length/total)),k:0}));
  for(let turn=0;items.length<QUIZ_SIZE&&turn<QUIZ_SIZE*4;turn++){
    for(const x of share){
      if(items.length>=QUIZ_SIZE||x.k>=x.want) continue;
      const id=x.ids[x.k%x.ids.length], qs=QS(BY[id]).map((q,i)=>i).filter(i=>QS(BY[id])[i].choices&&!used.has(`${id}:${i}`));
      if(!qs.length){ x.k++; continue; }
      const qi=qs[Math.floor(Math.random()*qs.length)]; used.add(`${id}:${qi}`); items.push({id,qi,pick:null}); x.k++;
    }
    if(share.every(x=>x.k>=x.want)) share.forEach(x=>x.want++);   // rounding left room: one more for each, in turn
  }
  QZ={items:shuffled(items),i:0,started:Date.now(),units:units.map(x=>x.u.id)};
  quizShow();
  QZ.clock=setInterval(quizTick,1000);
}
function stopQuizClock(){ if(QZ?.clock) clearInterval(QZ.clock); }
const mmss=ms=>{ const s=Math.floor(ms/1000); return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`; };
function quizTick(){ const el=sheet.querySelector(".mx-quiz-clock"); if(el&&QZ?.started) el.textContent=mmss(Date.now()-QZ.started); }
function quizShow(){
  const {items,i}=QZ, it=items[i], q=QS(BY[it.id])[it.qi], last=i===items.length-1;
  if(!it.order) it.order=shuffled(q.choices.map((_,k)=>k));   // the same order when coming back to a question
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-quiz-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">מבחן תרגול</span><h3 id="mxTitle">שאלה ${i+1} מתוך ${items.length}</h3>
        <small class="mx-src">⏱ <span class="mx-quiz-clock">${mmss(Date.now()-QZ.started)}</span></small></div>
        <div class="mx-shacts">${window.MathlyBoard?.button()||""}<button class="mx-x" data-act="quiz-quit" aria-label="יציאה מהמבחן">✕</button></div></div>
      <div class="mx-quiz-dots">${items.map((x,k)=>`<button data-quiz-go="${k}" class="${x.pick!=null?"done":""}${k===i?" now":""}" aria-label="שאלה ${k+1}${x.pick!=null?", נענתה":""}">${k+1}</button>`).join("")}</div>
      <div class="mx-q"><p>${fmt(q.question)}</p>${figures(q)}
        <div class="mx-choices">${it.order.map(k=>{ const c=q.choices[k]; return `<button data-choice="${k}" data-m="${c.correct?"":esc(c.mistake)}"${c.correct?" data-right":""} aria-pressed="${it.pick===k}">${fmt(c.text)}</button>`; }).join("")}</div></div>
      <div class="mx-quiz-nav"><button class="mx-btn" data-act="quiz-prev"${i?"":" disabled"}>הקודמת</button>
        ${last?`<button class="mx-btn solid" data-act="quiz-submit">הגשה</button>`:`<button class="mx-btn solid" data-act="quiz-next">הבאה</button>`}</div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  window.MathlyBoard?.mount(sheet,`quiz:${QZ.started}:${i}`,{question:()=>sheet.querySelector(".mx-q")});   // a sketch per exam question
}
// a choice is only marked; it can be changed until the exam is handed in
function quizPick(btn){
  if(!QZ?.items) return;
  const it=QZ.items[QZ.i]; it.pick=+btn.dataset.choice;
  sheet.querySelectorAll("[data-choice]").forEach(b=>b.setAttribute("aria-pressed",b===btn));
  sheet.querySelector(`[data-quiz-go="${QZ.i}"]`).classList.add("done");
  Sky.sound.tap();
}
function quizGo(k){ if(!QZ?.items) return; QZ.i=Math.max(0,Math.min(QZ.items.length-1,k)); quizShow(); }
function quizSubmit(){
  const left=QZ.items.filter(x=>x.pick==null).length;
  if(left&&!QZ.sure){
    QZ.sure=true;
    const nav=sheet.querySelector(".mx-quiz-nav");
    nav.insertAdjacentHTML("beforebegin",`<p class="mx-small mx-quiz-warn">${left===1?"שאלה אחת לא נענתה":`${left} שאלות לא נענו`}. אפשר לחזור אליהן במספרים למעלה, או ללחוץ שוב על הגשה.</p>`);
    return;
  }
  stopQuizClock();
  const items=QZ.items, ms=Date.now()-QZ.started, now=new Date().toISOString();
  const res=items.map(x=>{ const q=QS(BY[x.id])[x.qi], c=x.pick==null?null:q.choices[x.pick]; return {...x,q,ok:!!c?.correct,mistake:c&&!c.correct?c.mistake:null}; });
  const right=res.filter(r=>r.ok).length;
  // answering counts like practice: right answers go to today's goal, and a finished skill that went wrong is reviewed today
  for(const r of res){
    if(r.ok){ Sky.ensure(P); const k=Sky.dayKey(); P.days[k]=(P.days[k]||0)+1; }
    else if(P.done[r.id]){ Sky.ensure(P); P.review[r.id]={box:0,due:Sky.dayKey()}; }
    if(r.mistake) Sky.slip(P,r.id,r.qi,r.mistake,"exam",new Date(now));
  }
  const mistakes={}; res.filter(r=>r.mistake).forEach(r=>{ (mistakes[r.mistake]??={n:0,ids:new Set()}).n++; mistakes[r.mistake].ids.add(r.id); });
  const skipped=res.filter(r=>r.pick==null).map(r=>r.id);
  const top=Object.entries(mistakes).sort((a,b)=>b[1].n-a[1].n).slice(0,3);
  const weak=[...new Set([...top.flatMap(([,m])=>[...m.ids]),...skipped])];
  (P.quizzes=P.quizzes||[]).push({at:now,n:items.length,right,ms,units:QZ.units,weak}); P.quizzes=P.quizzes.slice(-20);
  save(); draw();
  const perUnit=QZ.units.map(uid=>{ const u=G.units.find(x=>x.id===uid), rs=res.filter(r=>BY[r.id].unit===uid); return {u,n:rs.length,ok:rs.filter(r=>r.ok).length}; }).filter(x=>x.n);
  const plan=top.length?top.map(([k,m])=>{ const M=G.mistakes[k]; return `<li><b>${fmt(M.name)}</b>${m.n>1?` <small>(${m.n} פעמים)</small>`:""}<span>${fmt(M.tip)}</span>
      <span class="mx-chips">${[...m.ids].map(id=>`<button class="mx-btn" data-id="${id}">לתרגל: ${fmt(BY[id].short)}</button>`).join("")}</span></li>`; }).join(""):"";
  QZ={done:true};
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-quiz-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">מבחן תרגול</span><h3 id="mxTitle">${right} מתוך ${items.length} נכונות</h3>
        <small class="mx-src">⏱ ${mmss(ms)}${skipped.length?` · ${skipped.length} בלי תשובה`:""}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <div class="mx-quiz-units-score">${perUnit.map(x=>`<div><span>${esc(x.u.name)}</span><b>${x.ok}/${x.n}</b><span class="mx-meter" aria-hidden="true"><i style="width:${Math.round(100*x.ok/x.n)}%"></i></span></div>`).join("")}</div>
      ${plan?`<h4>${top.length===1?"דבר אחד":top.length===2?"שני דברים":"שלושה דברים"} לחזק עד המבחן</h4><ol class="mx-quiz-plan">${plan}</ol>
        <p class="mx-small">מיומנויות שכבר סיימתם וטעיתם בהן חוזרות היום לחזרה המעורבת.</p>`
        :right===items.length?"<p>הכול נכון. ממשיכים לתרגל קצת כל יום, וזה יישאר.</p>":""}
      <details class="mx-quiz-review"><summary>כל השאלות והתשובות</summary><ol>${res.map(r=>{ const c=r.q.choices.find(c=>c.correct), mine=r.pick==null?null:r.q.choices[r.pick];
        return `<li class="${r.ok?"ok":"bad"}"><span>${fmt(r.q.question)}</span><small>${esc(plain(BY[r.id].short))}</small>
          ${r.ok?`<span>✓ ${fmt(c.text)}</span>`:`<span>${mine?`ענית: ${fmt(mine.text)}`:"בלי תשובה"} · נכון: ${fmt(c.text)}</span>`}</li>`; }).join("")}</ol></details>
      <div class="mx-quiz-nav"><button class="mx-btn" data-act="quiz">מבחן תרגול חדש</button><button class="mx-btn solid" data-act="close">חזרה למסלול</button></div></div>`;
  sheet.querySelector(".mx-x").focus({preventScroll:true});
  if(right/items.length>=.8) Sky.sound.goal();
}
function quizQuit(){
  if(!QZ?.items) return closeSheet();
  if(QZ.items.every(x=>x.pick==null)||QZ.quitting) return closeSheet();
  QZ.quitting=true;
  sheet.querySelector(".mx-quiz-nav").insertAdjacentHTML("beforebegin",'<p class="mx-small mx-quiz-warn">לצאת? התשובות במבחן הזה לא יישמרו. לחצו שוב על ✕ כדי לצאת.</p>');
}

/* ---------- unit quiz ----------
   A unit can end with a summarizing quiz (unit.quiz, app/math_skills.py): open-ended questions with points, and a time
   limit. It is shown like a paper quiz: all the questions at once, a clock counting down, nothing checked until it is
   handed in. The student writes on paper and photographs each answer (on this device, or from the phone on the same
   account); when the time is up there are UQ_PHOTO_MIN more minutes to photograph, then it is handed in by itself.
   After handing in, each answer is checked (the server does not check quiz answers on upload), and the report shows
   the points per question with feedback and a solution. The sitting is kept in P.uq[unit]: {sitting:{started,
   attempts, submitted}, history:[{at, score, graded}]} so a reload continues it with the clock still running.
   The time limit is kept by this page; the server keeps the answers and their checks. */
const UQ_PHOTO_MIN=10, UQ_BASE="/api/math/answer-attempts";
const uqState=uid=>((P.uq||={})[uid]||={history:[]});
const uqReady=u=>!!(u.quiz&&!u.quiz.locked&&CFG.answerScans&&CFG.userId);
const uqEnds=(u,sit)=>sit.started+u.quiz.minutes*60000;
function quizStep(u){
  if(!u.quiz) return "";
  const st=uqState(u.id), last=st.history.at(-1), going=st.sitting&&!st.sitting.submitted;
  const tag=going?"בתהליך":last?.score!=null?`${last.score}/100`:last?"הוגש":"";
  return `<div class="mx-step mx-uquiz-step u-${u.id}"><button class="mx-node mx-uquiz${last?" done":""}" data-uquiz="${u.id}" aria-label="בוחן מסכם: ${esc(u.name)}${tag?`, ${tag}`:""}">📝</button>
    <span class="mx-lbl">בוחן מסכם${tag?`<em>${tag}</em>`:""}</span></div>`;
}
async function uqJson(url,options={}){
  const r=await api(url,{cache:"no-store",...options}), d=await r.json().catch(()=>({}));
  if(!r.ok){ const e=Error(UQ_ERRORS[d.detail]||"החיבור נקטע. נסו שוב."); e.code=d.detail; e.status=r.status; throw e; }
  return d;
}
const uqPost=(url,body={})=>uqJson(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
const UQ_ERRORS={quiz_sittings_unavailable:"שמירת ההגשה אינה זמינה כרגע. נסו שוב מאוחר יותר.",invalid_sitting:"ההגשה לא תואמת לתשובות השמורות. פתחו את הבוחן מחדש.",question_changed:"הבוחן עודכן. רעננו את העמוד והתחילו מחדש.",image_too_large:"התמונה גדולה מדי. צלמו שוב.",invalid_image:"לא ניתן לקרוא את התמונה. צלמו שוב.",
  unsupported_image:"בחרו תמונת JPEG, PNG או WebP.",answer_storage_unavailable:"שמירת תשובות אינה זמינה כרגע.",grading_unavailable:"הבדיקה האוטומטית אינה זמינה כרגע.",
  grading_failed:"הבדיקה נכשלה. התמונה נשמרה; אפשר לנסות שוב.",grading_limit:"הגעתם למכסת הבדיקות היומית. נסו שוב מחר.",grading_busy:"כבר מתבצעות בדיקות. נסו שוב בעוד רגע.",
  upload_in_progress:"העלאה כבר מתבצעת. רגע…",open_ended_locked:"בוחנים פתוחים סגורים כרגע באתר.",sign_in_required:"יש להיכנס לחשבון."};
function stopUnitQuiz(){ if(UQ){ clearInterval(UQ.clock); clearTimeout(UQ.poll); Object.values(UQ.images||{}).forEach(URL.revokeObjectURL); } UQ=null; }
// the intro: what the quiz is and how it works, the last results, and start / continue
function uqIntro(uid){
  const u=G.units.find(x=>x.id===uid), q=u.quiz, st=uqState(uid), sit=st.sitting, going=sit&&!sit.submitted;
  if(going) return uqOpen(uid);
  if(!cur) back=document.activeElement;
  stopUnitQuiz(); cur="uquiz"; UQ={uid};
  const ready=uqReady(u), n=q.questions.length;
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-uq-sheet u-${uid}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">בוחן מסכם</h3>
        <small class="mx-src">${n} שאלות פתוחות · ${q.minutes} דקות · 100 נקודות</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <ul class="mx-uq-rules">
        <li>כמו בוחן בכיתה: כל השאלות מופיעות יחד, והשעון סופר לאחור מרגע ההתחלה.</li>
        <li>כתבו את הפתרונות על דף, כל שאלה בנפרד, עם דרך פתרון מלאה ונימוקים.</li>
        <li>צלמו את התשובה לכל שאלה. כשהזמן נגמר יש עוד ${UQ_PHOTO_MIN} דקות לצלם ולהגיש.</li>
        <li>הבדיקה, הציון והפתרונות מגיעים רק אחרי ההגשה.</li>
        <li>אפשר לסגור ולחזור, אבל השעון ממשיך לרוץ.</li></ul>
      ${st.history.length?`<div class="mx-uq-history"><h4>הגשות קודמות</h4>${st.history.slice().reverse().map((h,k)=>{ const i=st.history.length-1-k;
        return `<button class="mx-btn" data-uq-result="${uid}:${i}">${new Date(h.at).toLocaleDateString("he-IL")} · ${h.score==null?"ממתין לבדיקה":`${h.score}/100`}</button>`; }).join("")}</div>`:""}
      ${ready?`<button class="mx-btn solid" data-act="uq-start">התחלת הבוחן</button>`
        :`<p class="mx-note">${!CFG.userId?"הבוחן זמין אחרי כניסה לחשבון.":"בוחנים עם תשובה מצולמת ובדיקה אוטומטית אינם זמינים כרגע באתר."}</p>`}</div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}
// a new sitting: one fresh answer attempt per question
async function uqStart(){
  const uid=UQ.uid, u=G.units.find(x=>x.id===uid), btn=sheet.querySelector("[data-act=uq-start]");
  btn.disabled=true; btn.textContent="מכינים את הבוחן…";
  try{
    const attempts=[];
    for(const [index,q] of u.quiz.questions.entries())
      attempts.push((await uqPost("/api/math/quiz-attempts",{unit:uid,index,question_version:q.question_version,new:true})).attempt.id);
    uqState(uid).sitting={started:Date.now(),attempts,submitted:null}; save(); draw();
    uqOpen(uid);
  }catch(e){ btn.disabled=false; btn.textContent="התחלת הבוחן"; btn.insertAdjacentHTML("afterend",`<p class="mx-small mx-quiz-warn">${esc(e.message)}</p>`); }
}
// the quiz paper
function uqOpen(uid){
  const u=G.units.find(x=>x.id===uid), sit=uqState(uid).sitting;
  if(!cur) back=document.activeElement;
  stopUnitQuiz(); cur="uquiz"; UQ={uid,res:{},images:{},busy:{},msg:{}};
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-uq-sheet mx-uq-paper u-${uid}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-uq-head"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">בוחן מסכם</h3></div>
        <div class="mx-uq-clock" role="timer" aria-live="off"></div>
        <div class="mx-shacts">${window.MathlyBoard?.button()||""}<button class="mx-x" data-act="close" aria-label="יציאה (השעון ממשיך)">✕</button></div></div>
      <p class="mx-uq-banner" aria-live="polite"></p>
      <ol class="mx-uq-qs">${u.quiz.questions.map((q,i)=>`<li class="mx-uq-q" id="uq-q${i}">
        <div class="mx-uq-qhead"><b>שאלה ${i+1}</b><span>${q.points} נק׳</span></div>
        <p class="mx-uq-text">${fmt(q.question).replace(/\n/g,"<br>")}</p>${figures(q)}
        <div class="mx-uq-answer" data-uq-i="${i}"></div></li>`).join("")}</ol>
      <div class="mx-quiz-nav"><span class="mx-small" data-uq-count></span><button class="mx-btn solid" data-act="uq-submit">הגשת הבוחן</button></div>
      <input type="file" accept="image/*" capture="environment" hidden data-uq-file></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  // all the questions on one paper: the board has a page per question, and hands in that page as the question's answer
  window.MathlyBoard?.mount(sheet,`uq:${uid}:${sit.started}`,{pages:u.quiz.questions.length,question:i=>sheet.querySelector(`#uq-q${i}`),
    submit:async(i,picture)=>{
      if(UQ?.uid!==uid||uqState(uid).sitting?.submitted) return {error:"הבוחן כבר הוגש"};
      await uqUpload(i,picture); return UQ?.msg[i]?{error:UQ.msg[i]}:{};
    },
    turned:i=>sheet.querySelector(`#uq-q${i}`)?.scrollIntoView({block:"start",behavior:"smooth"})});
  sheet.querySelector("[data-uq-file]").onchange=e=>{ const f=e.target.files[0]; e.target.value=""; if(f&&UQ?.pick!=null) uqUpload(UQ.pick,f); };
  uqTick(); UQ.clock=setInterval(uqTick,1000);
  sit.attempts.forEach((_,i)=>uqRefresh(i));
}
function uqTick(){
  if(!UQ?.uid) return;
  const u=G.units.find(x=>x.id===UQ.uid), sit=uqState(UQ.uid).sitting; if(!sit||sit.submitted) return;
  const left=uqEnds(u,sit)-Date.now(), photo=left+UQ_PHOTO_MIN*60000;
  const clock=sheet.querySelector(".mx-uq-clock"), banner=sheet.querySelector(".mx-uq-banner"); if(!clock) return;
  if(photo<=0) return uqSubmit(true);
  clock.textContent=left>0?mmss(left):mmss(photo);
  clock.classList.toggle("low",left>0&&left<5*60000); clock.classList.toggle("over",left<=0);
  const say=left>0?(left<5*60000?"נשארו פחות מ־5 דקות. זה זמן טוב לבדוק ולצלם.":""):`הזמן לכתיבה נגמר. נשארו ${mmss(photo)} לצילום ולהגשה, בלי להוסיף לפתרונות.`;
  if(banner.textContent!==say) banner.textContent=say;
}
// one question's answer box: the photo if there is one, and the ways to add or replace it
async function uqRefresh(i){
  const sit=uqState(UQ.uid).sitting, aid=sit.attempts[i], uid=UQ.uid;
  try{
    const r=await uqJson(`${UQ_BASE}/${aid}`); if(UQ?.uid!==uid) return;
    UQ.res[i]=r;
    if(r.attachment&&!UQ.images[i]){ const b=await api(`${UQ_BASE}/${aid}/image`,{cache:"no-store"}); if(b.ok&&UQ?.uid===uid) UQ.images[i]=URL.createObjectURL(await b.blob()); }
  }catch(e){ if(UQ?.uid===uid) UQ.msg[i]=e.message; }
  if(UQ?.uid===uid) uqDrawAnswer(i);
  // waiting for the phone: look again soon
  if(UQ?.uid===uid&&!UQ.res[i]?.attachment&&["waiting","confirmed","uploading","failed"].includes(UQ.res[i]?.scan?.state)){ clearTimeout(UQ.poll); UQ.poll=setTimeout(()=>sit.attempts.forEach((_,k)=>uqRefresh(k)),2000); }
}
function uqDrawAnswer(i){
  const box=sheet.querySelector(`[data-uq-i="${i}"]`); if(!box) return;
  const r=UQ.res[i], has=!!r?.attachment, busy=UQ.busy[i], st=r?.scan?.state, phone=["waiting","confirmed","uploading","failed"].includes(st)&&!has;
  const touch=matchMedia("(max-width: 700px)").matches||navigator.maxTouchPoints>0;
  // on a computer the phone comes first: it is how most answers on paper get here. While the phone has the request,
  // the button is the request's box (its code and progress), not a window over the quiz.
  const phoneBtn=touch?"":window.MathlyAnswers.phoneLive(has?null:r?.scan,`data-uq-phone="${i}"`,`data-uq-cancel="${i}"`,has?"צילום מחדש בטלפון":"צילום בטלפון",!!busy);
  box.innerHTML=`${has?`<img class="mx-uq-img" alt="התשובה המצולמת לשאלה ${i+1}" src="${UQ.images[i]||""}">`:""}
    <p class="mx-small" role="status">${busy?esc(busy):UQ.msg[i]?esc(UQ.msg[i]):has?"✓ התשובה נשמרה":phone?"":st==="declined"?"הבקשה נדחתה בטלפון":st==="expired"?"בקשת הצילום פגה":"עוד לא צולמה תשובה"}</p>
    <span class="mx-chips">${window.MathlyBoard?`<button class="mx-btn mx-board-only" data-uq-board="${i}"${busy?" disabled":""}>✏️ פתרון בלוח</button>`:""}${phoneBtn}<button class="mx-btn${has||!touch?"":" solid"}" data-uq-photo="${i}"${busy?" disabled":""}>${has&&touch?"צילום מחדש":touch?"צילום התשובה":"העלאת תמונה מהמחשב"}</button></span>`;
  const done=Object.values(UQ.res).filter(x=>x?.attachment).length, n=uqState(UQ.uid).sitting.attempts.length;
  const c=sheet.querySelector("[data-uq-count]"); if(c) c.textContent=`צולמו ${done} מתוך ${n} תשובות`;
}
// a photo replaces an answer by a fresh attempt for that question (an attempt keeps the one photo it received)
async function uqFresh(i){
  const u=G.units.find(x=>x.id===UQ.uid), q=u.quiz.questions[i], sit=uqState(UQ.uid).sitting;
  if(!UQ.res[i]?.attachment) return sit.attempts[i];
  const r=await uqPost("/api/math/quiz-attempts",{unit:UQ.uid,index:i,question_version:q.question_version,new:true});
  sit.attempts[i]=r.attempt.id; save();
  if(UQ.images[i]){ URL.revokeObjectURL(UQ.images[i]); delete UQ.images[i]; }
  UQ.res[i]=r; return r.attempt.id;
}
// this device: request, confirm, lease and upload in a row (the same steps the phone takes)
async function uqUpload(i,file){
  const uid=UQ.uid; UQ.busy[i]="מעלים את התמונה…"; UQ.msg[i]=""; uqDrawAnswer(i);
  try{
    const photo=await window.MathlyPhoto.prepare(file);
    if(photo.size>5000000) throw Error(UQ_ERRORS.image_too_large);
    const aid=await uqFresh(i);
    const scan=(await uqPost(`${UQ_BASE}/${aid}/scans`,{renew:true,direct:true})).scan;   // this device's own upload: no phone is asked
    await uqPost(`/api/math/answer-scans/${scan.id}/confirm`);
    const lease=await uqPost(`/api/math/answer-scans/${scan.id}/uploads`,{key:crypto.randomUUID()});
    if(!lease.attachment){ const form=new FormData(); form.append("photo",photo,"answer.jpg");
      await uqJson(`/api/math/answer-scans/${scan.id}/uploads/${lease.lease_id}`,{method:"POST",body:form}); }
  }catch(e){ if(UQ?.uid===uid) UQ.msg[i]=e.message; }
  if(UQ?.uid!==uid) return;
  UQ.busy[i]=""; uqRefresh(i);
}
// the phone: a request with a 4-digit code, shown in the answer's own box until the phone sends the photo or declines
async function uqPhone(i){
  const uid=UQ.uid;
  UQ.busy[i]="יוצרים בקשת צילום…"; UQ.msg[i]=""; uqDrawAnswer(i);
  try{ const aid=await uqFresh(i); UQ.res[i]=await uqPost(`${UQ_BASE}/${aid}/scans`,{renew:true}); }
  catch(e){ if(UQ?.uid===uid) UQ.msg[i]=e.message; }
  if(UQ?.uid!==uid) return;
  UQ.busy[i]=""; uqRefresh(i);
}
async function uqCancel(i){   // the computer withdraws the request
  const uid=UQ.uid, sid=UQ.res[i]?.scan?.id; if(!sid) return;
  try{ UQ.res[i]=await uqPost(`/api/math/answer-scans/${sid}/decline`); }catch(e){ if(UQ?.uid===uid) UQ.msg[i]=e.message; }
  if(UQ?.uid===uid) uqRefresh(i);
}
function uqSubmit(timeUp=false){
  const uid=UQ.uid, sit=uqState(uid).sitting; if(!sit||sit.submitted) return;
  const missing=sit.attempts.filter((_,i)=>!UQ.res[i]?.attachment).length;
  if(!timeUp&&missing&&!UQ.sure){
    UQ.sure=true;
    sheet.querySelector(".mx-quiz-nav").insertAdjacentHTML("beforebegin",`<p class="mx-small mx-quiz-warn">${missing===1?"לשאלה אחת":`ל־${missing} שאלות`} אין תשובה מצולמת, והן יקבלו 0 נקודות. לחצו שוב על הגשה כדי להגיש בכל זאת.</p>`);
    return;
  }
  sit.submitted=Date.now();
  const st=uqState(uid); st.history.push({at:new Date().toISOString(),attempts:sit.attempts.slice(),score:null,timeUp,ck:crypto.randomUUID()}); st.history=st.history.slice(-10);
  save(); draw();
  uqResult(uid,st.history.length-1,true);
}
/* The grade of a sitting is worked out by the server from the stored checks (app/quiz_grades.py); the score kept in
   this device's progress is only a copy of it. A sitting is handed in on the server once (`sid`); the same key makes
   a retry after a lost response the same sitting. */
async function uqSend(uid,entry){
  if(entry.sid) return entry.sid;
  if(!entry.ck){ entry.ck=crypto.randomUUID(); save(); }
  entry.sid=(await uqPost("/api/math/quiz-sittings",{unit_id:uid,attempts:entry.attempts,time_up:!!entry.timeUp,client_key:entry.ck})).id;
  save(); return entry.sid;
}
async function uqSitting(uid,sid){ return (await uqJson(`/api/math/quiz-sittings?unit_id=${encodeURIComponent(uid)}`)).sittings.find(x=>x.id===sid)||null; }
// the report: each answer is checked now (once), then points per question, feedback and the solution
async function uqResult(uid,h,check=false){
  const u=G.units.find(x=>x.id===uid), st=uqState(uid), entry=st.history[h];
  if(!cur) back=document.activeElement;
  stopUnitQuiz(); cur="uquiz"; UQ={uid,res:{},images:{}};
  const n=entry.attempts.length;
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-uq-sheet u-${uid}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">בוחן מסכם: בודקים…</h3>
        <small class="mx-src" aria-live="polite">${CFG.aiDirect===false?"שולחים את התשובות לבדיקת המורה":"בודקים את התשובות, זה לוקח כחצי דקה לשאלה"}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div><div class="mx-uq-report"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
  let sendError="";
  commentSeen(c=>entry.attempts.includes(c.attempt_id));
  try{ await uqSend(uid,entry); }catch(e){ sendError=e.message; }
  if(UQ?.uid!==uid) return;
  const results=[];
  for(let i=0;i<n;i++){
    let r=null;
    try{
      r=await uqJson(`${UQ_BASE}/${entry.attempts[i]}`);
      if(r.attachment&&r.grading_available&&(!r.grading||(check&&r.grading.state==="failed"))){
        if(UQ?.uid!==uid) return;
        sheet.querySelector(".mx-src").textContent=CFG.aiDirect===false?`שולחים את שאלה ${i+1} מתוך ${n} למורה…`:`בודקים את שאלה ${i+1} מתוך ${n}…`;
        try{ r=await uqPost(`${UQ_BASE}/${entry.attempts[i]}/grade`,{automatic:!check}); }catch(e){ r.error=e.message; }
      }
      if(r.attachment){ const b=await api(`${UQ_BASE}/${entry.attempts[i]}/image`,{cache:"no-store"}); if(b.ok&&UQ?.uid===uid) UQ.images[i]=URL.createObjectURL(await b.blob()); }
    }catch(e){ r={error:e.message}; }
    if(UQ?.uid!==uid) return;
    results.push(r);
  }
  // points: the server's, per question (a checked answer earns its share; a missing one 0; one not checked yet leaves the total open)
  let sitting=null;
  if(entry.sid){ try{ sitting=await uqSitting(uid,entry.sid); }catch(e){ sendError||=e.message; } }
  if(UQ?.uid!==uid) return;
  const rows=u.quiz.questions.map((q,i)=>{
    const r=results[i], g=r?.grading, a=g?.state==="completed"?g.result:null, pts=sitting?sitting.questions[i].earned:null;
    let say="";
    if(!r?.attachment) say="לא צולמה תשובה";
    else if(sitting?.questions[i]?.state==="teacher") say="נבדק על ידי המורה";
    else if(a&&a.score!=null) say={correct:"נכון ומלא",partial:"נכון בחלקו",incorrect:"לא נכון"}[a.verdict]||"";
    else { const req=a?null:r.ai_request;
      say=req&&["pending","sending","failed"].includes(req.state)?"מחכה למורה שיאשר את הבדיקה":req?.state==="declined"?`המורה לא אישר את הבדיקה${req.note?`: ${req.note}`:""}`:a?.verdict==="unreadable"?"לא הצלחנו לקרוא את התמונה":a?.verdict==="needs_review"?"נדרשת בדיקה של מורה":r.error||(!r.grading_available?"הבדיקה האוטומטית אינה זמינה כרגע":"עוד לא נבדקה"); }
    return `<li class="mx-uq-q"><div class="mx-uq-qhead"><b>שאלה ${i+1}</b><span>${pts==null?"–":pts}/${q.points} נק׳</span></div>
      <p class="mx-uq-text">${fmt(q.question).replace(/\n/g,"<br>")}</p>
      ${UQ.images[i]?`<img class="mx-uq-img" alt="התשובה שלכם לשאלה ${i+1}" src="${UQ.images[i]}">`:""}
      <p class="mx-uq-verdict ${a?.verdict||"none"}">${esc(say)}</p>
      ${window.MathlyAnswers?.teacherNote?.(r||{})||""}
      ${a?.feedback?`<p>${r.teacher_review?"<b>בדיקה אוטומטית: </b>":""}${fmtLoose(a.feedback)}</p>`:""}${a?.next_step?`<p><b>הצעד הבא: </b>${fmtLoose(a.next_step)}</p>`:""}
      ${a?.solution?`<details><summary>הפתרון המלא</summary><p class="mx-grade-solution">${fmtLoose(a.solution)}</p></details>`:""}
      ${r?.attachment?window.MathlyAnswers?.reviewBox?.(entry.attempts[i],r)||"":""}
      ${r?.attachment&&!a&&r.grading_available&&!["pending","sending","failed"].includes(r.ai_request?.state)?`<button class="mx-btn" data-uq-result="${uid}:${h}:check">${CFG.aiDirect===false?"שליחה מחדש למורה":"בדיקה נוספת"}</button>`:""}</li>`;
  });
  const earned=sitting?sitting.questions.reduce((sum,x)=>sum+(x.earned||0),0):0, open=sitting?sitting.open:n;
  entry.score=sitting?.grade??null; save(); draw();
  const total=!sitting?"ההגשה לא נשמרה בשרת":open?`${earned} נקודות עד עכשיו · ${open===1?"שאלה אחת לא נבדקה":`${open} שאלות לא נבדקו`}`:`${earned}/100`;
  sheet.querySelector("#mxTitle").textContent=`בוחן מסכם: ${total}`;
  sheet.querySelector(".mx-src").textContent=`הוגש ${new Date(entry.at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"})}${entry.timeUp?" · הוגש כשהזמן נגמר":""}`;
  const weak=u.quiz.questions.map((q,i)=>i).filter(i=>{ const a=results[i]?.grading?.result; return !results[i]?.attachment||(a&&a.score!=null&&a.score<70); });
  sheet.querySelector(".mx-uq-report").innerHTML=`<ol class="mx-uq-qs">${rows.join("")}</ol>
    ${sendError&&!sitting?`<p class="mx-note mx-quiz-warn">${esc(sendError)} <button class="mx-btn" data-uq-result="${uid}:${h}:check">ניסיון נוסף</button></p>`:""}
    ${weak.length&&!open?`<p class="mx-note">כדאי לחזור על ${weak.map(i=>`שאלה ${i+1}`).join(", ")} ולתרגל את המיומנויות של היחידה במסלול לפני הבוחן הבא.</p>`:""}
    <p class="mx-small">הבדיקה אוטומטית באמצעות AI: בדקו שהיא תואמת למה שכתבתם, ואם משהו נראה לא נכון, הראו למורה.</p>
    <div class="mx-quiz-nav"><button class="mx-btn" data-uquiz="${uid}">לבוחן</button><button class="mx-btn solid" data-act="close">חזרה למסלול</button></div>`;
}

function onClick(e){
  const t=e.target.closest("button,[data-act]"); if(!t||!root.contains(t)) return;
  if(t.dataset.choice!=null) return answer(t);
  if(t.dataset.boardToggle!=null) return window.MathlyBoard?.toggle();
  if(t.dataset.quizUnit) return quizToggle(t.dataset.quizUnit);
  if(t.dataset.quizGo!=null) return quizGo(+t.dataset.quizGo);
  if(t.dataset.uquiz) return uqIntro(t.dataset.uquiz);   // a sitting in progress opens straight on its paper
  if(t.dataset.sres) return t.closest(".mx-sres-item").classList.toggle("zoom");
  if(t.dataset.help) return showHelp(t.dataset.help);
  if(t.dataset.example) return showHelp(t.dataset.example);
  if(t.dataset.exampleNext!=null) return exampleNext(t);
  if(t.dataset.aqTab) return aqTab(t.dataset.aqTab);
  if(t.dataset.reviewAnswer) return trOpenAnswer(t.dataset.reviewAnswer,t.dataset.reviewFrom);
  if(t.dataset.reviewBack!=null) return TR?.back?.();
  if(t.dataset.answers) return reviewSitting(...t.dataset.answers.split(":"));
  if(t.dataset.askReview!=null) return window.MathlyAnswers.askReview(t);
  if(t.dataset.comment) return openComment(t.dataset.comment);
  if(t.dataset.asgGo) return asgGo(t.dataset.asgGo);
  if(t.dataset.asgNew!=null){ REPORT.form={id:null}; drawReport(); return sheet.querySelector(".mx-asg-form input[name=title]")?.focus(); }
  if(t.dataset.asgEdit){ REPORT.form={id:t.dataset.asgEdit}; drawReport(); return sheet.querySelector(".mx-asg-form input[name=title]")?.focus(); }
  if(t.dataset.asgCancel!=null){ REPORT.form=null; return drawReport(); }
  if(t.dataset.asgDel) return asgDelete(t.dataset.asgDel);
  if(t.dataset.uqResult){ const [uid,h,check]=t.dataset.uqResult.split(":"); return uqResult(uid,+h,check==="check"); }
  if(t.dataset.uqPhoto!=null){ UQ.pick=+t.dataset.uqPhoto; return sheet.querySelector("[data-uq-file]").click(); }
  if(t.dataset.uqPhone!=null) return uqPhone(+t.dataset.uqPhone);
  if(t.dataset.uqCancel!=null) return uqCancel(+t.dataset.uqCancel);
  if(t.dataset.uqBoard!=null) return window.MathlyBoard?.show(+t.dataset.uqBoard);
  if(t.dataset.subject) return selectSubject(t.dataset.subject);
  if(t.dataset.view){ closeSheet(); return setView(t.dataset.view,t.dataset.unit); }
  if(t.dataset.comet) return showComet(t.dataset.comet);
  if(t.dataset.id) return open(t.dataset.id);
  if(t.dataset.manageMode) return showManageMode(t.dataset.manageMode);
  if(t.dataset.classAction) return manageClassAction(t.dataset.classAction,t.dataset.classId);
  if(t.dataset.reportClass!=null) return classReport(t.dataset.reportClass);
  if(t.dataset.reportStudent!=null) return reportOpenStudent(t.dataset.reportStudent);
  if(t.dataset.reportTab) return reportControl(t);
  if(t.dataset.aqSend) return aqSend(t.dataset.aqSend);
  if(t.dataset.aqDecline) return aqDecline(t.dataset.aqDecline);
  switch(t.dataset.act){
    case "help-close": return helpClose();
    case "manage": return manageClasses();
    case "class-report": return classReport();
    case "ai-queue": return aiQueue();
    case "aq-all": return aqAll();
    case "photo-cancel": return photoCancel();
    case "manage-refresh": return loadManagedClasses(true);
    case "manage-lab": return showManageMode("lab");
    case "manage-practice": return closeSheet();
    case "subjects": return drawSubjectPicker();
    case "streak": return showStreak();
    case "review": return startReview();
    case "patterns": return showPatterns();
    case "quiz": stopQuizClock(); QZ=null; return quizSetup();
    case "quiz-start": return quizStart();
    case "quiz-next": return quizGo(QZ.i+1);
    case "quiz-prev": return quizGo(QZ.i-1);
    case "quiz-submit": return quizSubmit();
    case "quiz-quit": return quizQuit();
    case "uq-start": return uqStart();
    case "uq-submit": return uqSubmit();
    case "review-next": return REV&&reviewNext();
    case "cal-prev": return showStreak(-1);
    case "cal-next": return showStreak(1);
    case "push": return window.MathlyAnswers?.togglePush?.();
    case "sound": Sky.setSound(!Sky.soundOn()); Sky.sound.tap(); return draw();
    case "resources": return openResources(t.dataset.unit);
    case "res-take": case "res-retake": return resPicker.click();
    case "res-cancel": RES.photo=null; RES.msg=""; return drawResources();
    case "res-visible": return setResourceVisible(t.dataset.res,t.dataset.visible==="1");
    case "unit-explanations": return openExplanations(t.dataset.unit);
    case "res-delete": return deleteResource(t.dataset.res);
    case "photo": case "retake": return picker.click();
    case "hint": PH.shown++; return drawPhoto();
    case "work": PH.works.add(+t.dataset.i); return drawPhoto();
    case "all": PH.all=true; return drawPhoto();
    case "close": return closeSheet();
    case "out": return Promise.resolve(window.MathlyAnswers?.forgetPush?.()).finally(()=>{window.MathlyAnswers?.reset();closeSheet();hide();return client?.auth.signOut().then(()=>location.reload());});
  }
}

let MANAGED_CLASSES=[], MANAGE_MODE="classes", MANAGE_BUSY=false;
const manageTabs=[
  ["classes","כיתות","פתיחה, עריכה ומחיקה"],
  ["students","תלמידים","רשימה ומסנן כיתות"],
  ["content","תוכן","מקצועות, יחידות ותת־נושאים"],
  ["flags","ניטור","מצב המערכת ופעילות"],
  ["access","הרשאות","תפקידים וגישה"]
];

const examLooks={
  "גיאוגרפיה":["🌍","geo"],"אזרחות":["🏛️","civics"],"מבוא מדעי":["🧪","intro"],
  "מתמטיקה":["∑","math"],"לשון":["✍️","language"],"חינוך פיננסי":["₪","finance"],
  "מדעים":["🔬","science"],"אנגלית":["A","english"],"ספרות":["📚","literature"],
  "היסטוריה":["⌛","history"],"תנ״ך":["📜","bible"]
};
const examDate=value=>{const [y,m,d]=String(value).split("-").map(Number);return new Date(y,m-1,d)};
const examDay=value=>{const date=examDate(value);return `${String(date.getDate()).padStart(2,"0")}.${String(date.getMonth()+1).padStart(2,"0")}.${date.getFullYear()}`};
const examFullDate=value=>new Intl.DateTimeFormat("he-IL",{weekday:"long",day:"numeric",month:"long",year:"numeric"}).format(examDate(value));
const examMonth=value=>new Intl.DateTimeFormat("he-IL",{month:"long",year:"numeric"}).format(examDate(value));
const classSubjects=row=>[...new Set(G.units.filter(unit=>(row.lessons||[]).includes(unit.id)).map(unit=>unit.subject).filter(Boolean))];
function examCards(exams,nextDate){
  return exams.map(exam=>{
    const [icon,tone]=examLooks[exam.subject]||["●","other"], next=exam.date===nextDate;
    return `<article class="mx-exam-card exam-${tone}${next?" is-next":""}"><span class="mx-exam-icon" aria-hidden="true">${icon}</span><div><b>${esc(exam.subject)}</b><small>${examDay(exam.date)}${next?" · המבחן הבא":""}</small></div></article>`;
  }).join("");
}
function examBoard(row,compact=false){
  const all=[...(row.exams||[])].filter(exam=>exam?.date&&exam?.subject).sort((a,b)=>a.date.localeCompare(b.date));
  const subjects=classSubjects(row), exams=compact?all.filter(exam=>subjects.includes(exam.subject)):all;
  if(!exams.length)return "";
  const today=new Date();today.setHours(0,0,0,0);
  const upcoming=exams.filter(exam=>examDate(exam.date)>=today), nextDate=upcoming[0]?.date||"";
  const groups=[];exams.forEach(exam=>{const month=examMonth(exam.date),last=groups[groups.length-1];if(last?.month===month)last.exams.push(exam);else groups.push({month,exams:[exam]});});
  const full=`<div class="mx-exam-months">${groups.map(group=>`<section><h5>${esc(group.month)}</h5><div class="mx-exam-grid">${examCards(group.exams,nextDate)}</div></section>`).join("")}</div>`;
  const title=esc(compact?`מבחני ${subjects.join(" ו")}`:row.exam_title||`לוח מבחנים – ${row.name}`),note=esc(row.exam_note||"");
  if(!compact)return `<section class="mx-exam-board"><div class="mx-exam-head"><div><h4>${title}</h4><small>${exams.length} מבחנים</small></div></div>${full}${note?`<p class="mx-exam-note">${note}</p>`:""}</section>`;
  const next=upcoming[0], days=next?Math.max(0,Math.ceil((examDate(next.date)-today)/86400000)):null;
  const countdown=next?`<div class="mx-exam-countdown exam-${(examLooks[next.subject]||["","other"])[1]}"><span><b>${days===0?"היום":days===1?"מחר":days}</b><small>${days>1?"ימים למבחן":""}</small></span><div><small>המבחן הקרוב</small><strong>${esc(next.subject)}</strong><time datetime="${esc(next.date)}"><span>מועד המבחן</span>${esc(examFullDate(next.date))}<small>${examDay(next.date)}</small></time></div></div>`:"";
  return `<section class="mx-exam-board compact"><div class="mx-exam-head"><div><h2>${title}</h2><small>${upcoming.length?`${upcoming.length} מבחנים בהמשך השנה`:"לוח המבחנים הסתיים"}</small></div></div>${countdown}${upcoming.length?`<div class="mx-exam-grid">${examCards(upcoming,nextDate)}</div>`:""}${note?`<p class="mx-exam-note">${note}</p>`:""}</section>`;
}

async function manageClasses(){
  if(!can("management.access")) return;
  closeSheet(); back=document.activeElement; cur="management";
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-manage-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-manage-head"><h3 id="mxTitle">ניהול</h3><span class="mx-manage-spacer"></span>
        <button class="mx-btn" data-act="manage-refresh">רענון</button>
        <button class="mx-btn" data-act="manage-lab">מעבדה</button>
        <button class="mx-btn solid" data-act="manage-practice">לתרגול</button>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p class="mx-manage-state" aria-live="polite"></p>
      <div class="mx-manage-modes" role="tablist" aria-label="ניהול">${manageTabs.map(([mode,title,sub])=>`<button role="tab" data-manage-mode="${mode}">${title}<small>${sub}</small></button>`).join("")}</div>
      <div class="mx-management"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus();
  MANAGE_MODE="classes";
  await loadManagedClasses();
}

async function loadManagedClasses(refresh=false){
  if(MANAGE_BUSY||cur!=="management") return;
  const state=sheet.querySelector(".mx-manage-state");
  MANAGE_BUSY=true; state.textContent=refresh?"מרעננים את נתוני הניהול…":"טוענים את הכיתות…";
  try{
    const response=await api("/api/classes");
    if(!response.ok) throw new Error("לא הצלחנו לטעון את הכיתות. נסו שוב.");
    const {classes}=await response.json();
    if(cur!=="management") return;
    MANAGED_CLASSES=classes||[]; state.textContent=refresh?"הנתונים עודכנו.":""; showManageMode(MANAGE_MODE);
  }catch(error){state.textContent=error.message;sheet.querySelector(".mx-management").innerHTML=`<p class="mx-note">${esc(error.message)}</p>`;}
  finally{MANAGE_BUSY=false;}
}

function showManageMode(mode){
  if(cur!=="management") return;
  MANAGE_MODE=mode;
  sheet.querySelectorAll("[data-manage-mode]").forEach(button=>button.setAttribute("aria-selected",String(button.dataset.manageMode===mode)));
  const box=sheet.querySelector(".mx-management");
  if(mode==="classes") return drawManagedClasses(box);
  if(mode==="students"){
    const students=new Map();
    MANAGED_CLASSES.forEach(row=>(row.emails||[]).forEach(email=>students.set(email,[...(students.get(email)||[]),row.name])));
    box.innerHTML=`<div class="mx-manage-title"><h4>תלמידים</h4><span>${students.size} תלמידים · ${MANAGED_CLASSES.length} כיתות</span></div>${students.size?`<div class="mx-manage-list">${[...students].map(([email,classes])=>`<article><b dir="ltr">${esc(email)}</b><small>${esc(classes.join(" · "))}</small></article>`).join("")}</div>`:'<p class="mx-note">עדיין לא נוספו תלמידים לכיתות.</p>'}`;
    return;
  }
  if(mode==="content") return drawContent(box);
  if(mode==="flags") return drawMonitoring(box);
  if(mode==="access"){
    const roles=CFG.roles||[], permissions=CFG.permissions||[];
    box.innerHTML=`<div class="mx-manage-title"><h4>הרשאות</h4><span>תפקידים וגישה</span></div><div class="mx-access-card"><small>התפקידים שלך</small><div class="mx-tag-row">${roles.length?roles.map(role=>`<span>${esc(role)}</span>`).join(""):'<span>מנהל/ת</span>'}</div><small>הרשאות פעילות</small><div class="mx-tag-row">${permissions.map(permission=>`<span dir="ltr">${esc(permission)}</span>`).join("")}</div></div>`;
    return;
  }
  box.innerHTML='<div class="mx-manage-title"><h4>מעבדה</h4><span>כלים לבדיקה ופיתוח</span></div><p class="mx-note">כלי המעבדה למתמטיקה יתווספו כאן. אפשר לחזור לכל אזור ניהול מהכרטיסיות למעלה.</p>';
}

/* Monitoring (ניטור): a snapshot of the system, open-answer activity, and the server's latest warnings.
   Each source loads and fails on its own, so a slow Supabase does not hold up the rest. */
const MON_RANGES={day:["יום","24 השעות האחרונות","15 דקות"],week:["שבוע","7 הימים האחרונים","שעה"],month:["חודש","30 הימים האחרונים","יום"]};
const MON_ACTIONS={visit:["👋","נכנס/ה לאפליקציה"],photo:["📷","צילם/ה תרגיל לעזרה"],answer_upload:["📝","שלח/ה תשובה פתוחה"],answer_graded:["✔️","תשובה נבדקה"],class_saved:["🏫","שמר/ה כיתה"],class_deleted:["🗑️","מחק/ה כיתה"],resource_added:["🖼️","הוסיף/ה תמונה למשאבי שיעור"],
  ai_request:["🙋","ביקש/ה בדיקת AI מהמורה"],ai_sent:["🤖","שלח/ה בקשה של תלמיד ל-AI"],ai_failed:["⚠️","שליחה ל-AI נכשלה"],ai_declined:["✋","דחה/תה בקשת AI"]};
const VERDICTS={correct:"נכונות",partial:"נכונות חלקית",incorrect:"שגויות",unreadable:"לא קריאות",needs_review:"דורשות בדיקה",grading:"בבדיקה",failed:"הבדיקה נכשלה"};
let MON={}, MON_RANGE=(()=>{try{return localStorage.getItem("mathly.monRange")}catch{return null}})();
if(!MON_RANGES[MON_RANGE]) MON_RANGE="week";
const monRel=new Intl.RelativeTimeFormat("he",{numeric:"auto"});
function monAgo(stamp){
  const when=new Date(stamp), seconds=Math.max(0,(Date.now()-when.getTime())/1000);
  if(!stamp||Number.isNaN(when.getTime())) return "";
  const [value,unit]=seconds<60?[Math.max(1,Math.floor(seconds)),"second"]:seconds<3600?[Math.floor(seconds/60),"minute"]:seconds<86400?[Math.floor(seconds/3600),"hour"]:seconds<2592000?[Math.floor(seconds/86400),"day"]:[Math.floor(seconds/2592000),"month"];
  return `<time datetime="${esc(when.toISOString())}" title="${esc(when.toLocaleString("he-IL",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Jerusalem"}))}">${esc(monRel.format(-value,unit))}</time>`;
}
async function monGet(url){
  try{ const res=await api(url), data=await res.json().catch(()=>({})); if(!res.ok) throw new Error(data.detail||res.status); return data; }
  catch(err){ return {error:err.message||"לא זמין"}; }
}
function drawMonitoring(box){
  box.innerHTML=`<div class="mx-manage-title"><h4>ניטור</h4><span>מצב המערכת ופעילות · מתעדכן פעם בדקה</span></div>
    <section class="mx-mon-card mx-mon-summary"></section><section class="mx-mon-card mx-mon-activity"></section>`;
  drawMonSummary(); drawMonActivity(); loadMonitoring();
}
function loadMonitoring(){
  const redraw=draw=>{ if(cur==="management"&&MANAGE_MODE==="flags") draw(); };
  monGet("/api/monitor/summary").then(data=>{ MON.summary=data; redraw(drawMonSummary); });
  monGet("/api/monitor/supabase").then(data=>{ MON.supabase=data; redraw(drawMonSummary); });
  monGet("/api/monitor/ai-usage").then(data=>{ MON.ai=data; redraw(drawMonSummary); });
  loadMonActivity().then(()=>{ redraw(drawMonActivity); redraw(drawMonSummary); });
}
async function loadMonActivity(){ const range=MON_RANGE, data=await monGet(`/api/monitor/activity?period=${range}`); if(range===MON_RANGE) MON.activity=data; }
setInterval(()=>{ if(cur==="management"&&MANAGE_MODE==="flags"&&!document.hidden) loadMonitoring(); },60000);

function drawMonSummary(){
  const box=sheet.querySelector(".mx-mon-summary"); if(!box) return;
  const sum=MON.summary, sb=MON.supabase, loading=!sum, err=sum?.error;
  const tile=(value,label,sub,tone="",cls="")=>`<article class="mx-mon-tile ${tone} ${cls}"><b>${value}</b><small>${esc(label)}</small>${sub?`<span>${sub}</span>`:""}</article>`;
  const tiles=[];
  { const seen=sum?.seen, n=seen?.last_5m;
    tiles.push(tile(loading?"…":err?"–":n?`${n} ${n===1?"משתמש/ת":"משתמשים"}`:"אין משתמשים","נכנסו ב־5 הדקות האחרונות",
      loading?"טוען…":err?esc(err):`${seen.last_hour} בשעה האחרונה · ${seen.last_24h} ב־24 שעות · ${n?"כדאי לחכות עם פריסה":"אפשר לפרוס גרסה חדשה"}`,
      loading||err?"":n?"busy":"ready","mx-mon-live")); }
  { const b=sum?.build||{};
    tiles.push(tile(loading?"…":monAgo(b.updated_at)||"–","עדכון אחרון",err?esc(err):esc([b.version,b.commit_message].filter(Boolean).join(" · ")))); }
  { const ph=sum?.photos;
    tiles.push(tile(loading||err?"–":String(ph.today),"תרגילים מצולמים היום",loading?"":err?esc(err):!sum.photo_help?"עזרה בצילום אינה מוגדרת":
      `${ph.students} תלמידים · ${ph.at_limit} הגיעו למכסה (${ph.daily_limit} ליום)`,!loading&&!err&&ph.at_limit?"warn":"")); }
  { const e=sum?.errors||{}, tone=loading||err?"":e.last_hour?"bad":e.last_24h?"warn":"ready";
    tiles.push(tile(loading||err?"–":String(e.last_24h??0),"שגיאות בלוג ב־24 השעות האחרונות",loading?"":err?esc(err):
      `${e.since_start??0} מאז הפעלת השרת${e.last_at?` · אחרונה ${monAgo(new Date(e.last_at*1000).toISOString())}`:""}`,tone)); }
  { const parts=sb&&!sb.error?[["התחברות",sb.auth||{}],["מסד נתונים",sb.db||{}]]:[];
    const down=parts.some(([,x])=>!x.ok), slow=parts.some(([,x])=>x.ok&&x.ms>2000);
    const sub=!sb?"בודק…":sb.error?esc(sb.error):parts.map(([name,x])=>x.ok?`${name} ${(x.ms/1000).toFixed(1)} ש׳`:`${name}: ${esc(x.error||"לא עונה")}`).join(" · ");
    tiles.push(tile(!sb?"…":sb.error?"–":down?"לא זמין":slow?"איטי":"תקין","Supabase",sub,!sb||sb.error?"":down?"bad":slow?"warn":"ready")); }
  { const ai=MON.ai, t=ai?.total, f=ai?.by_feature||{};
    const usd=x=>`$${(x||0).toFixed(x>=10?0:2)}`, tok=n=>n>=1e6?`${(n/1e6).toFixed(1)}M`:n>=1e3?`${Math.round(n/1e3)}K`:String(n||0);
    tiles.push(tile(!ai?"…":t?usd(t.cost_usd):"–",`עלות Claude ב־${ai?.days||30} יום (הערכה)`,
      !ai?"טוען…":ai.error?esc(ai.error):ai.unavailable?esc(ai.unavailable):
      `${t.calls} קריאות · ${tok(t.input_tokens)} אסימוני קלט · ${tok(t.output_tokens)} פלט · היום ${usd(ai.today.cost_usd)}`+
      ` · צילום ${usd(f.photo?.cost_usd)} · בדיקה ${usd(f.grading?.cost_usd)}`)); }

  // open answers: what is switched on, and how this period's photo checks came out
  const ans=sum?.answers, act=MON.activity, verdicts=act?.summary?.verdicts||{};
  let answers;
  if(loading) answers='<p class="mx-note">טוען…</p>';
  else if(err) answers=`<p class="mx-note">לא ניתן לטעון: ${esc(err)}</p>`;
  else{
    const flag=(on,yes,no)=>`<li class="${on?"on":"off"}">${on?yes:no}</li>`;
    answers=`<ul class="mx-mon-flags">${flag(ans.storage,"שמירת תשובות מצולמות פעילה","שמירת תשובות מצולמות כבויה")}${flag(!ans.open_ended_locked,"שאלות פתוחות פתוחות לתלמידים","שאלות פתוחות נעולות")}${flag(ans.grading,"בדיקה אוטומטית של תשובות פעילה","בדיקה אוטומטית כבויה")}</ul>`;
    const total=Object.values(verdicts).reduce((a,b)=>a+b,0);
    if(act&&!act.error&&!act.unavailable) answers+=total?`<p class="mx-note">${total} בדיקות ב־${MON_RANGES[MON_RANGE][1]}:</p><ul class="mx-mon-verdicts">${Object.entries(verdicts).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`<li><span>${esc(VERDICTS[k]||k)}</span><b>${n}</b></li>`).join("")}</ul>`:`<p class="mx-note">אין בדיקות תשובות ב־${MON_RANGES[MON_RANGE][1]}.</p>`;
  }
  // the last WARNING-or-worse log lines of this server process
  const lines=sum?.errors?.recent;
  const logs=loading?'<p class="mx-note">טוען…</p>':err?`<p class="mx-note">לא ניתן לטעון: ${esc(err)}</p>`:!lines?.length?'<p class="mx-note">אין אזהרות או שגיאות מאז הפעלת השרת.</p>':
    lines.map(line=>`<div class="mx-mon-log"><div><span class="mx-mon-level ${(line.level||"").toLowerCase()==="warning"?"warn":"bad"}">${esc(line.level)}</span><code dir="ltr">${esc(line.logger)}</code>${monAgo(new Date(line.at*1000).toISOString())}</div><code class="mx-mon-msg" dir="ltr">${esc(line.message)}</code></div>`).join("");
  // the latest actions: what, who, when (kept in server memory since its last start)
  const acts=sum?.actions;
  const actions=loading?'<p class="mx-note">טוען…</p>':err?`<p class="mx-note">לא ניתן לטעון: ${esc(err)}</p>`:!acts?.length?'<p class="mx-note">עדיין לא נרשמו פעולות מאז הפעלת השרת.</p>':
    acts.slice(0,10).map(a=>{ const [icon,what]=MON_ACTIONS[a.kind]||["•",a.kind]; return `<div class="mx-mon-action"><i aria-hidden="true">${icon}</i><div><b>${esc(what)}</b><small><span dir="ltr">${esc(a.email||"משתמש לא ידוע")}</span>${a.label?` · ${esc(a.label)}`:""}</small></div>${monAgo(new Date(a.at*1000).toISOString())}</div>`; }).join("");
  box.innerHTML=`<h5>תמונת מצב</h5><div class="mx-mon-tiles">${tiles.join("")}</div>
    <div class="mx-mon-lower"><div class="mx-mon-panel"><h6>פעולות אחרונות</h6>${actions}</div><div class="mx-mon-panel"><h6>תשובות פתוחות</h6>${answers}</div><div class="mx-mon-panel mx-mon-logs"><h6>5 שורות הלוג האחרונות (אזהרה ומעלה)</h6>${logs}</div></div>`;
}

function drawMonActivity(){
  const box=sheet.querySelector(".mx-mon-activity"); if(!box) return;
  const [,title,bucket]=MON_RANGES[MON_RANGE], data=MON.activity;
  const ranges=Object.entries(MON_RANGES).map(([key,[label]])=>`<button type="button" data-mon-range="${key}" aria-pressed="${key===MON_RANGE}">${label}</button>`).join("");
  let body;
  if(!data) body='<p class="mx-note">טוען את נתוני הפעילות…</p>';
  else if(data.error) body=`<p class="mx-note">גרף הפעילות אינו זמין: ${esc(data.error)}</p>`;
  else if(data.unavailable) body=`<p class="mx-note">גרף הפעילות אינו זמין (${esc(data.unavailable)}).</p>`;
  else{
    const rows=data.buckets||[], s=data.summary||{}, avg=s.active_students?Math.round(s.attempts/s.active_students*10)/10:"–";
    const stats=[[s.active_students,"תלמידים פעילים"],[s.attempts,"תשובות פתוחות"],[avg,"תשובות לתלמיד/ה"],[s.returning_students,"חזרו ביום נוסף"],[s.active_days,"ימים עם פעילות"]]
      .map(([n,label])=>`<article><b>${n??"–"}</b><small>${label}</small></article>`).join("");
    const W=720,H=190,left=32,top=10,width=678,height=145, max=Math.max(1,...rows.map(r=>r.attempts)), maxA=Math.max(1,...rows.map(r=>r.active_students)), bw=width/Math.max(1,rows.length);
    const days=MON_RANGE==="month", when=t=>new Date(t).toLocaleString("he-IL",days?{day:"numeric",month:"numeric",timeZone:"Asia/Jerusalem"}:MON_RANGE==="week"?{weekday:"short",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Jerusalem"}:{hour:"2-digit",minute:"2-digit",timeZone:"Asia/Jerusalem"});
    const tick=(m,f,attrs)=>Number.isInteger(m*f)?`<text ${attrs}>${m*f}</text>`:"";   // whole counts only
    const grid=[0,.5,1].map(f=>{ const y=top+height*(1-f); return `<line class="grid" x1="${left}" x2="${left+width}" y1="${y}" y2="${y}"/>${tick(max,f,`x="0" y="${y+4}"`)}${tick(maxA,f,`class="active-axis" x="${W-2}" y="${y+4}" text-anchor="end"`)}`; }).join("");
    const points=[], bars=rows.map((r,i)=>{ const x=left+i*bw, h=r.attempts/max*height; points.push(`${x+bw/2},${top+height-r.active_students/maxA*height}`);
      return r.attempts?`<rect class="bar" x="${x+bw*.08}" y="${top+height-h}" width="${Math.max(.5,bw*.84)}" height="${h}"><title>${esc(when(r.bucket))}: ${r.attempts} תשובות, ${r.active_students} תלמידים</title></rect>`:""; }).join("");
    const labels=rows.length?[[0,"start"],[Math.floor((rows.length-1)/2),"middle"],[rows.length-1,"end"]].map(([i,a])=>`<text x="${left+width*(i/(Math.max(1,rows.length-1)))}" y="${H-10}" text-anchor="${a}">${esc(when(rows[i].bucket))}</text>`).join(""):"";
    body=`<div class="mx-mon-stats">${stats}</div><div class="mx-mon-legend"><span><i></i>תשובות פתוחות</span><span class="students"><i></i>תלמידים פעילים</span></div>
      <svg class="mx-mon-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="גרף פעילות: ${s.attempts||0} תשובות פתוחות ב־${title}">${grid}${bars}<path class="active-line" d="${points.length?"M"+points.join("L"):""}"/>${labels}</svg>
      ${s.attempts?"":'<p class="mx-note">עוד לא נשלחו תשובות פתוחות בטווח הזה.</p>'}`;
  }
  box.innerHTML=`<div class="mx-mon-head"><div><h5>פעילות ב־${title}</h5><p>תשובות פתוחות שנשלחו · כל עמודה מייצגת ${bucket}. התרגול עצמו נשמר במכשיר של כל תלמיד/ה ולא נספר כאן.</p></div><div class="mx-mon-ranges">${ranges}</div></div>${body}`;
  box.querySelectorAll("[data-mon-range]").forEach(button=>button.onclick=async()=>{
    MON_RANGE=button.dataset.monRange; try{localStorage.setItem("mathly.monRange",MON_RANGE)}catch{}
    MON.activity=null; drawMonActivity(); await loadMonActivity(); drawMonActivity(); drawMonSummary();
  });
}

// every subject a class meets: those with units, then those that so far only have exams
const contentSubjects=()=>[...new Set([...G.units.map(unit=>unit.subject),
  ...MANAGED_CLASSES.flatMap(row=>(row.exams||[]).map(exam=>exam.subject))].filter(Boolean))];
const unitSkills=id=>ORDER.filter(sid=>BY[sid].unit===id).map(sid=>BY[sid]);
const questionCount=skills=>skills.reduce((sum,skill)=>sum+QS(skill).length,0);
function drawContent(box){
  const subjects=contentSubjects();
  box.innerHTML=`<div class="mx-manage-title"><h4>תוכן לימודי</h4><span>${subjects.length} מקצועות · ${G.units.length} יחידות · ${G.skills.length} תת־נושאים · ${questionCount(G.skills)} שאלות</span></div>
    ${subjects.map(subject=>{
      const units=G.units.filter(unit=>unit.subject===subject), [icon,tone]=examLooks[subject]||["●","other"];
      return `<section class="mx-content-subject exam-${tone}"><h5><span aria-hidden="true">${icon}</span>${esc(subject)}<small>${units.length?`${units.length} יחידות`:"עוד אין יחידות במסלול"}</small></h5>
        ${units.map(unit=>{
          const skills=unitSkills(unit.id), classes=MANAGED_CLASSES.filter(row=>(row.lessons||[]).includes(unit.id)).length;
          return `<details class="mx-content-unit u-${unit.id}"><summary><b>${esc(unit.name)}</b>
            <small>${unit.when?`${esc(unit.when)} · `:""}${skills.length} תת־נושאים · ${questionCount(skills)} שאלות · פעיל ב־${classes} כיתות</small></summary>
            <ol>${skills.map(skill=>`<li><span>${fmt(skill.name)}</span><small>${esc(skill.subject||subject)} › ${esc(unit.name)}${skill.month?` · ${esc(skill.month)}`:""} · ${QS(skill).length===1?"שאלה אחת":`${QS(skill).length} שאלות`}</small></li>`).join("")}</ol></details>`;
        }).join("")}</section>`;
    }).join("")}`;
}

function drawManagedClasses(box){
  const classes=MANAGED_CLASSES;
  box.innerHTML=`<div class="mx-manage-title"><h4>כיתות</h4><span>פתיחה, עריכה ומחיקה</span></div>
    <div class="mx-class-toolbar"><button class="mx-btn solid" data-class-action="new">+ כיתה חדשה</button><span>${classes.length} כיתות</span></div>
    ${classes.length?`<div class="mx-class-cards">${classes.map(row=>{
      const units=G.units.filter(unit=>(row.lessons||[]).includes(unit.id));
      const subjects=classSubjects(row);
      const unitLine=units.length===G.units.length?`כל היחידות (${G.units.length})`:units.map(unit=>unit.name).join(" · ")||"לא נבחרו";
      const students=row.emails||[], teachers=row.teachers||[];
      return `<article class="mx-class-card"><div class="mx-class-card-head"><h5>${esc(row.name)}</h5><div class="mx-class-actions"><button class="mx-btn" data-class-action="report" data-class-id="${esc(row.id)}">מעקב</button><button class="mx-btn" data-class-action="edit" data-class-id="${esc(row.id)}">עריכה</button><button class="mx-btn danger" data-class-action="delete" data-class-id="${esc(row.id)}">מחיקה</button></div></div>
        <dl><dt>יחידות</dt><dd>${esc(unitLine)}</dd><dt>מקצועות היחידות</dt><dd>${esc(subjects.join(" · ")||"לא הוגדרו")}</dd><dt>תלמידים</dt><dd>${students.length?`${students.length}: ${esc(students.join(" · "))}`:"עוד אין"}</dd><dt>מורה הכיתה</dt><dd dir="auto">${teachers.length?esc(teachers.join(" · ")):"עוד לא נבחר"}</dd></dl>${examBoard(row)}</article>`;
    }).join("")}</div>`:'<div class="mx-empty-class"><h5>עוד אין כיתות</h5><p>פתחו כיתה ראשונה, בחרו את יחידות הלימוד והוסיפו את כתובות התלמידים.</p></div>'}`;
}

function manageClassAction(action,id){
  if(action==="new") return openClassEditor(null);
  if(action==="cancel") return drawManagedClasses(sheet.querySelector(".mx-management"));
  const row=MANAGED_CLASSES.find(item=>String(item.id)===String(id));
  if(!row) return;
  if(action==="edit") return openClassEditor(row);
  if(action==="delete") return deleteManagedClass(row);
  if(action==="report") return classReport(row.id);
}

function openClassEditor(row){
  const box=sheet.querySelector(".mx-management"), creating=!row;
  const selected=new Set(row?.lessons||[]);   // a new class starts with no subject chosen
  const subjects=[...new Set(G.units.map(unit=>unit.subject))], subjectUnits=subject=>G.units.filter(unit=>unit.subject===subject);
  box.innerHTML=`<div class="mx-manage-title"><h4>${creating?"כיתה חדשה":`עריכת ${esc(row.name)}`}</h4><button class="mx-btn" type="button" data-class-action="cancel">חזרה לכיתות</button></div>
    <form class="mx-class-form"><label>שם הכיתה<input name="name" required maxlength="80" autocomplete="off" placeholder="למשל: ט׳ 1" value="${esc(row?.name||"")}"></label>
      <fieldset><legend>מקצועות<small>בחרו את המקצועות שהכיתה לומדת. בחירת מקצוע מסמנת את כל יחידות הלימוד שלו, ואפשר לבטל יחידות שהכיתה לא לומדת.</small></legend>
        <div class="mx-subject-picks">${subjects.map(subject=>{const [icon,tone]=examLooks[subject]||["●","other"], units=subjectUnits(subject);
          return `<label class="exam-${tone}"><input type="checkbox" name="subject" value="${esc(subject)}"><span aria-hidden="true" class="mx-subject-icon">${icon}</span><span>${esc(subject)}<small>${units.length} יחידות</small></span></label>`}).join("")}</div></fieldset>
      <fieldset class="mx-unit-fieldset"><legend>יחידות הלימוד<small>התלמידים יראו במסלול רק את המיומנויות של היחידות שסומנו. מקצוע היחידה קובע אילו מבחנים יוצגו במסלול.</small></legend>
        <p class="mx-note mx-no-subject">בחרו מקצוע כדי לראות את יחידות הלימוד שלו.</p>
        ${subjects.map(subject=>`<section class="mx-subject-units" data-subject-units="${esc(subject)}"><h6 class="mx-pick-subject">${esc(subject)}</h6><div class="mx-unit-picks">${subjectUnits(subject).map(unit=>{const skills=unitSkills(unit.id);return `<label class="u-${unit.id}"><input type="checkbox" name="unit" value="${esc(unit.id)}" data-subject="${esc(subject)}"${selected.has(unit.id)?" checked":""}><span>${esc(unit.name)}<small>${skills.length} תת־נושאים · ${questionCount(skills)} שאלות</small></span></label>`}).join("")}</div></section>`).join("")}</fieldset>
      <label>התלמידים<small>כתובת דוא״ל אחת בכל שורה. תלמיד יכול להשתייך ליותר מכיתה אחת.</small><textarea name="emails" dir="ltr" spellcheck="false" placeholder="student@example.com">${esc((row?.emails||[]).join("\n"))}</textarea></label>
      <label>מורה הכיתה<small>אחד מתלמידי הכיתה. המורה רואה את ההתקדמות, הקשיים והציונים של כל התלמידים בכיתה.</small><select name="teacher" dir="ltr"></select></label>
      <div class="mx-class-form-actions"><button class="mx-btn solid" type="submit">${creating?"פתיחת הכיתה":"שמירת השינויים"}</button><button class="mx-btn" type="button" data-class-action="cancel">ביטול</button><span role="status" aria-live="polite"></span></div></form>`;
  const form=box.querySelector("form"), message=form.querySelector('[role="status"]');
  const unitBoxes=subject=>[...form.querySelectorAll('input[name="unit"]')].filter(input=>input.dataset.subject===subject);
  // a subject is chosen while any of its units is; a subject's units stay in view from choosing it until it is cleared
  const open=new Set(subjects.filter(subject=>subjectUnits(subject).some(unit=>selected.has(unit.id))));
  const syncSubjects=()=>{
    form.querySelectorAll('input[name="subject"]').forEach(input=>{
      const boxes=unitBoxes(input.value), on=boxes.filter(box=>box.checked).length;
      input.checked=on>0; input.indeterminate=on>0&&on<boxes.length;
      form.querySelector(`[data-subject-units="${CSS.escape(input.value)}"]`).hidden=!open.has(input.value);
    });
    form.querySelector(".mx-no-subject").hidden=open.size>0;
  };
  form.addEventListener("change",event=>{
    const input=event.target;
    if(input.name==="subject"){
      unitBoxes(input.value).forEach(box=>box.checked=input.checked);
      if(input.checked) open.add(input.value); else open.delete(input.value);
    }
    if(input.name==="subject"||input.name==="unit") syncSubjects();
  });
  syncSubjects();
  // the teacher is picked from the students: the list follows the students box as it is edited
  const lines=name=>form.elements[name].value.split(/[\n,;]+/).map(value=>value.trim().toLowerCase()).filter(Boolean);
  const pickTeacher=form.elements.teacher;
  const syncTeacher=()=>{
    const chosen=pickTeacher.options.length?pickTeacher.value:(row?.teachers||[])[0]||"", students=[...new Set(lines("emails"))];
    pickTeacher.innerHTML=`<option value="">ללא מורה</option>${students.map(email=>`<option value="${esc(email)}"${email===chosen?" selected":""}>${esc(email)}</option>`).join("")}`;
  };
  form.elements.emails.addEventListener("input",syncTeacher); syncTeacher();
  form.querySelector('input[name="name"]').focus();
  form.onsubmit=async event=>{
    event.preventDefault();
    const lessons=[...form.querySelectorAll('input[name="unit"]:checked')].map(input=>input.value);
    if(!lessons.length){message.textContent="בחרו לפחות מקצוע אחד.";return;}
    const body={name:form.elements.name.value.trim(),emails:lines("emails"),teachers:pickTeacher.value?[pickTeacher.value]:[],lessons};
    const buttons=form.querySelectorAll("button"); buttons.forEach(button=>button.disabled=true); message.textContent=creating?"פותחים את הכיתה…":"שומרים…";
    try{
      const response=await api(creating?"/api/classes":`/api/classes/${encodeURIComponent(row.id)}`,{method:creating?"POST":"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      if(!response.ok){const detail=(await response.json().catch(()=>({}))).detail;throw new Error(detail||"לא הצלחנו לשמור את הכיתה. נסו שוב.");}
      if(!creating){
        Object.assign(row,body); MY_CLASSES.forEach(item=>{if(String(item.id)===String(row.id))Object.assign(item,body,{teacher:body.teachers.includes(ME_EMAIL.toLowerCase())});});
        if(String(MY_CLASS?.id)===String(row.id))Object.assign(MY_CLASS,body);
        SHOWN=new Set(shownUnits().map(unit=>unit.id)); draw();
      }
      await loadManagedClasses(true);
    }catch(error){message.textContent=error.message;buttons.forEach(button=>button.disabled=false);}
  };
}

async function deleteManagedClass(row){
  if(!confirm(`למחוק את הכיתה ${row.name}? התלמידים שלה לא יוכלו להיכנס עוד.`)) return;
  const state=sheet.querySelector(".mx-manage-state"); state.textContent=`מוחקים את ${row.name}…`;
  try{
    const response=await api(`/api/classes/${encodeURIComponent(row.id)}`,{method:"DELETE"});
    if(!response.ok){const detail=(await response.json().catch(()=>({}))).detail;throw new Error(detail||"לא הצלחנו למחוק את הכיתה.");}
    MANAGED_CLASSES=MANAGED_CLASSES.filter(item=>String(item.id)!==String(row.id));
    MY_CLASSES=MY_CLASSES.filter(item=>String(item.id)!==String(row.id));
    if(String(MY_CLASS?.id)===String(row.id)) MY_CLASS=MY_CLASSES.length===1?MY_CLASSES[0]:null;
    SHOWN=new Set(shownUnits().map(unit=>unit.id)); draw(); state.textContent="הכיתה נמחקה."; drawManagedClasses(sheet.querySelector(".mx-management"));
  }catch(error){state.textContent=error.message;}
}

/* ---------- the class teacher's report ----------
   A class's teacher is one of its students, chosen in the class editor. That account (and a manager, from the class's
   card) opens the class's report (/api/classes/{id}/report, app/class_report.py): each student's saved progress, read
   the same way the student's own page reads it. It shows, per student, the skills finished in the class's units,
   the mistakes that keep coming back (Sky.patterns), the summarizing quizzes' grades and the practice exams' results,
   and above them the mistakes most common in the class. */
const teachClasses=()=>MY_CLASSES.filter(row=>row.teacher);
const teachButton=()=>(teachClasses().length?'<button class="mx-btn" data-act="class-report">הכיתה שלי</button>':"")
  +(CFG.aiReview?`<button class="mx-btn" data-act="ai-queue">${aqLabel()}</button>`:"");
let REPORT=null;
const shortDate=at=>{ const d=new Date(at); return isNaN(d)?"":d.toLocaleDateString("he-IL",{day:"numeric",month:"numeric"}); };
const pct=(a,b)=>b?Math.round(100*a/b):0;
// one student's numbers, from their saved progress (null: nothing saved yet)
function reportOf(student,units){
  const p=student.progress; if(!p) return null;
  const perUnit=units.map(u=>{ const ids=unitIds(u).filter(live); return {u,n:ids.length,done:ids.filter(id=>p.done?.[id]).length,
    gold:ids.filter(id=>p.gold?.[id]).length,stuck:ids.filter(id=>!p.done?.[id]&&(p.missed?.[id]||[]).length).map(id=>BY[id])}; });
  const n=perUnit.reduce((s,x)=>s+x.n,0), done=perUnit.reduce((s,x)=>s+x.done,0);
  const {recurring}=Sky.patterns(p,G.mistakes);
  // the unit quizzes' grades are the server's (student.quiz_sittings, oldest first; null: they could not be read); the
  // device's own history only says which submissions the server has not seen ("unverified")
  const sittings=student.quiz_sittings;
  const quizzes=units.filter(u=>u.quiz).map(u=>{
    const st=p.uq?.[u.id]||{history:[]}, mine=(sittings||[]).filter(x=>x.unit_id===u.id), known=new Set(mine.map(x=>x.id));
    return {u,st,last:mine.at(-1)||null,count:mine.length,unverified:st.history.filter(h=>!h.sid||!known.has(h.sid)).length};
  });
  const scores=quizzes.map(x=>x.last?.grade).filter(g=>g!=null);
  const exams=(p.quizzes||[]).slice().reverse();
  const days=Object.keys(p.days||{}).sort(), last=[p.updated?new Date(+p.updated):null,days.length?new Date(days.at(-1)):null].filter(d=>d&&!isNaN(d)).sort((a,b)=>b-a)[0];
  // worked examples the student opened in the last two weeks, in the class's skills (the device reports them)
  const classSkills=new Set(units.flatMap(u=>unitIds(u).filter(live))), since=Date.now()-14*864e5;
  const helped=Object.entries(p.examples||{}).filter(([id,e])=>classSkills.has(id)&&BY[id]&&Date.parse(e?.last)>=since)
    .map(([id,e])=>({id,n:+e.n||1,last:e.last})).sort((a,b)=>b.last.localeCompare(a.last));
  return {perUnit,n,done,helped,week:Sky.weekly(p),recurring:recurring.filter(x=>G.mistakes[x.m]),quizzes,quizzesKnown:sittings!=null,quizAvg:scores.length?Math.round(scores.reduce((a,b)=>a+b,0)/scores.length):null,exams,last};
}
async function classReport(id){
  const mine=teachClasses(), classId=id??REPORT?.id??mine[0]?.id; if(classId==null) return;
  if(!cur) back=document.activeElement;
  closeSheetQuietly(); cur="report"; REPORT={id:classId,data:null,form:null,tab:repGet("tab","list"),sort:repGet("sort","attention"),unit:repGet("unit","overview")};
  const tabs=mine.length>1?`<div class="mx-report-tabs">${mine.map(row=>`<button class="mx-btn" data-report-class="${esc(row.id)}" aria-pressed="${String(row.id)===String(classId)}">${esc(row.name)}</button>`).join("")}</div>`:"";
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-manage-sheet mx-report-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-manage-head"><h3 id="mxTitle">הכיתה שלי</h3><span class="mx-manage-spacer"></span>
        <button class="mx-btn" data-report-class="${esc(classId)}">רענון</button><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${tabs}<p class="mx-manage-state" aria-live="polite">טוענים את נתוני הכיתה…</p><div class="mx-report"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/report`,{cache:"no-store"});
    if(!r.ok) throw Error(r.status===403?"רק מורה הכיתה יכול לראות את הנתונים שלה.":"לא הצלחנו לטעון את נתוני הכיתה. נסו שוב.");
    const data=await r.json(); if(cur!=="report"||REPORT?.id!==classId) return;
    REPORT.data=data; drawReport();
  }catch(e){ if(cur==="report") sheet.querySelector(".mx-manage-state").textContent=e.message; }
}
// a student named in the attention list: their card opens and scrolls into view
function reportOpenStudent(i){
  const card=sheet.querySelector(`#rs-${+i}`); if(!card) return;
  card.open=true; card.scrollIntoView({block:"nearest"}); card.querySelector("summary").focus({preventScroll:true});
}
function closeSheetQuietly(){ const b=back; closeSheet(); back=b; }
// the teacher's choices in the report (list or grid, which unit, the order) are kept on this device
const repGet=(k,def)=>{ try{ return localStorage.getItem("mathly.report."+k)||def; }catch{ return def; } };
const repSet=(k,v)=>{ try{ localStorage.setItem("mathly.report."+k,v); }catch{} };
const REPORT_SORTS={attention:"דורשים תשומת לב קודם",name:"שם",progress:"התקדמות",activity:"פעילות אחרונה (הישנה קודם)"};
// how a skill stands for a student, as on their own path: gold, lit, fading (finished), trying (practised, not finished), none
function cellState(p,id){
  if(!p) return "none";
  if(p.done?.[id]) return Sky.star(p,id,"done",false);
  return p.tries?.[id]>0||(p.missed?.[id]||[]).length?"trying":"none";
}
const CELL_TEXT={gold:"כוכב זהב",lit:"הושלמה",fading:"הושלמה, הכוכב דועך",trying:"מתרגל, עוד לא סיים",none:"לא התחיל"};
const HARD_SHARE=1/3;   // a skill is a class-wide difficulty when this share of the students are on it without finishing
function drawReport(){
  const {class:row,students}=REPORT.data, ids=new Set(row.lessons||[]);
  const units=G.units.filter(u=>ids.has(u.id)&&unitIds(u).some(live));
  const skillNames={}; units.forEach(u=>unitIds(u).filter(live).forEach(id=>{ skillNames[id]=BY[id].name; }));
  const ctx={skills:skillNames,units:units.filter(u=>u.quiz).map(u=>({id:u.id,name:u.name})),assignments:REPORT.data.assignments||[]};
  const all=students.map(s=>({s,r:reportOf(s,units),att:Sky.attention(s,ctx)}));
  sheet.querySelector("#mxTitle").textContent=`הכיתה שלי: ${row.name}`;
  sheet.querySelector(".mx-manage-state").textContent=`${students.length} תלמידים · ${all.filter(x=>x.r).length} התחילו לתרגל`;
  // the mistakes that keep coming back for the most students
  const common={}; all.forEach(({s,r})=>r?.recurring.forEach(x=>(common[x.m]||=[]).push(s.email)));
  const top=Object.entries(common).sort((a,b)=>b[1].length-a[1].length).slice(0,5);
  // a student is shown by the class's nickname, else their Google name, else the start of their email
  const name=email=>students.find(x=>x.email===email)?.name||email.split("@")[0];
  const quizUnits=units.filter(u=>u.quiz);
  const DEVICE_NOTE=' <small class="mx-device" title="המכשיר של התלמיד מדווח את הנתונים האלה, והשרת לא בודק אותם">· נתוני תרגול מהמכשיר</small>';
  const grade=score=>score==null?"–":`${score}`;
  const tone=score=>score==null?"":score>=80?" good":score>=55?" mid":" low";
  const card=({s,r},i)=>{
    if(!r) return `<details class="mx-report-student" id="rs-${i}"><summary><b dir="ltr">${esc(name(s.email))}</b><span class="mx-small">${s.signed_in?"עוד לא התחיל לתרגל":"עוד לא נכנס לחשבון"}</span></summary><p class="mx-small" dir="ltr">${esc(s.email)}</p></details>`;
    const exam=r.exams[0];
    return `<details class="mx-report-student" id="rs-${i}"><summary><b dir="ltr">${esc(name(s.email))}</b>
        <span class="mx-report-prog"><span class="mx-meter" aria-hidden="true"><i style="width:${pct(r.done,r.n)}%"></i></span><small>${r.done}/${r.n} מיומנויות</small></span>
        <span class="mx-report-chip${tone(r.quizAvg)}" title="ממוצע בחנים מסכמים שנבדקו">בוחן ${grade(r.quizAvg)}</span>
        <span class="mx-report-chip${tone(exam?pct(exam.right,exam.n):null)}" title="מבחן התרגול האחרון (נתוני מכשיר)">תרגול ${exam?`${exam.right}/${exam.n}`:"–"}</span>
        ${r.recurring.length?`<span class="mx-report-chip low">${r.recurring.length} קשיים</span>`:""}
        ${(s.review_requests||[]).length?`<span class="mx-report-chip low">ביקש בדיקה חוזרת</span>`:""}</summary>
      <div class="mx-report-body">
        <p class="mx-small"><span dir="ltr">${esc(s.email)}</span>${r.last?` · פעילות אחרונה ${r.last.toLocaleDateString("he-IL")}`:""}</p>
        ${(s.review_requests||[]).length?`<section class="mx-tr-request"><h5>ביקש שתסתכלו שוב</h5>${s.review_requests.map(q=>`<p>${fmt(q.question||"")}${q.message?`: ${esc(q.message)}`:""}
          <button type="button" class="mx-btn" data-review-answer="${esc(q.attempt_id)}" data-review-from="report">פתיחת התשובה</button></p>`).join("")}</section>`:""}
        ${r.helped.length?`<section><h5>דוגמאות פתורות שנפתחו בשבועיים האחרונים${DEVICE_NOTE}</h5><ul class="mx-report-list">${r.helped.map(x=>
          `<li><b>${fmt(BY[x.id].name)}</b> <small>${x.n===1?"פעם אחת":`${x.n} פעמים`}, לאחרונה ${shortDate(x.last)}</small></li>`).join("")}</ul></section>`:""}
        <p class="mx-report-week"><b>${r.week.thisWeek}</b> תשובות נכונות השבוע · <b>${r.week.lastWeek}</b> בשבוע שעבר</p>
        <section><h5>התקדמות ביחידות${DEVICE_NOTE}</h5><div class="mx-quiz-units-score">${r.perUnit.map(x=>`<div><span>${esc(x.u.name)}${x.gold?` <small>· ${x.gold} זהב</small>`:""}</span><b>${x.done}/${x.n}</b><span class="mx-meter" aria-hidden="true"><i style="width:${pct(x.done,x.n)}%"></i></span></div>`).join("")}</div></section>
        <section><h5>קשיים${DEVICE_NOTE}</h5>${r.recurring.length?`<ul class="mx-report-list">${r.recurring.map(x=>`<li><b>${fmt(G.mistakes[x.m].name)}</b> <small>${x.n} פעמים ב־${x.skills.length} מיומנויות, לאחרונה ${shortDate(x.last)}</small>${BY[x.practise]?`<small>לחזק: ${fmt(BY[x.practise].name)}</small>`:""}</li>`).join("")}</ul>`:'<p class="mx-small">אין טעויות שחוזרות לאחרונה.</p>'}
          ${r.perUnit.some(x=>x.stuck.length)?`<p class="mx-small">מיומנויות עם שאלות שעוד לא נפתרו: ${r.perUnit.flatMap(x=>x.stuck).slice(0,8).map(sk=>fmt(sk.name)).join(" · ")}</p>`:""}</section>
        <section><h5>בוחן מסכם</h5>${quizUnits.length?`<table class="mx-report-table"><thead><tr><th>יחידה</th><th>ציון אחרון</th><th>הגשות</th><th>תאריך</th><th>תשובות</th></tr></thead><tbody>${r.quizzes.map(({u,st,last,count,unverified})=>{
            const cell=st.going?"בתהליך":!r.quizzesKnown?"לא זמין":last?(last.grade==null?"ממתין לבדיקה":`${last.grade}/100`):unverified?"לא מאומת":"–";
            const subs=`${count||(unverified?"":"–")}${unverified&&r.quizzesKnown?`${count?" ":""}<small>(${unverified} לא מאומתות)</small>`:""}`;
            return `<tr><td>${esc(u.name)}</td><td class="mx-report-grade${tone(last?.grade)}">${cell}</td><td>${subs}</td><td>${last?shortDate(last.submitted_at):"–"}</td><td>${last?`<button type="button" class="mx-btn" data-answers="${i}:${esc(u.id)}">פתיחה</button>`:""}</td></tr>`; }).join("")}</tbody></table>`:'<p class="mx-small">ליחידות של הכיתה אין בוחן מסכם.</p>'}</section>
        <section><h5>מבחני תרגול${DEVICE_NOTE}</h5>${r.exams.length?`<table class="mx-report-table"><thead><tr><th>תאריך</th><th>ציון</th><th>תשובות נכונות</th><th>זמן</th></tr></thead><tbody>${r.exams.slice(0,10).map(q=>`<tr><td>${shortDate(q.at)}</td><td class="mx-report-grade${tone(pct(q.right,q.n))}">${pct(q.right,q.n)}</td><td>${q.right}/${q.n}</td><td>${q.ms?`${Math.round(q.ms/60000)} דק׳`:"–"}</td></tr>`).join("")}</tbody></table>`:'<p class="mx-small">עוד לא נעשו מבחני תרגול.</p>'}</section>
      </div></details>`;
  };
  // the order the teacher chose; ties keep the class list's order. `i` is the student's place in the class list (their card's id)
  const rank={attention:(a,b)=>b.att.length-a.att.length,
    name:(a,b)=>name(a.s.email).localeCompare(name(b.s.email),"he"),
    progress:(a,b)=>(b.r?b.r.done:-1)-(a.r?a.r.done:-1),
    activity:(a,b)=>(a.r?.last?.getTime()??0)-(b.r?.last?.getTime()??0)};
  const sort=rank[REPORT.sort]?REPORT.sort:"attention";
  const order=all.map((x,i)=>({...x,i})).sort(rank[sort]);
  const needy=order.filter(x=>x.att.length);
  const attn=`<section class="mx-report-attn"><h4>דורשים תשומת לב</h4>${needy.length?`<ul class="mx-report-list">${needy.map(({s,att,i})=>
    `<li><button type="button" class="mx-report-open" data-report-student="${i}"><b dir="ltr">${esc(name(s.email))}</b></button><small>${att.map(x=>fmt(x.text)).join(" · ")}</small></li>`).join("")}</ul>`
    :'<p class="mx-note">אף תלמיד לא דורש תשומת לב כרגע.</p>'}</section>`;
  const list=`${attn}
    ${top.length?`<section class="mx-report-common"><h4>קשיים נפוצים בכיתה</h4><ul class="mx-report-list">${top.map(([m,who])=>`<li><b>${fmt(G.mistakes[m].name)}</b> <small>${who.length} תלמידים: ${who.map(e=>esc(name(e))).join(", ")}</small></li>`).join("")}</ul></section>`:""}
    <h4>תלמידים</h4>${students.length?order.map(x=>card(x,x.i)).join(""):'<p class="mx-note">אין עדיין תלמידים בכיתה.</p>'}`;

  // the grid: a row per student; a column per skill of one unit, or per unit in the overview
  const started=all.filter(x=>x.r).length;
  const gridUnit=units.find(u=>u.id===REPORT.unit);
  let grid;
  if(!students.length) grid='<p class="mx-note">אין עדיין תלמידים בכיתה.</p>';
  else if(!gridUnit){
    grid=`<table class="mx-grid"><thead><tr><th class="mx-grid-name" scope="col">תלמיד</th>${units.map(u=>`<th scope="col" class="mx-grid-unit">${esc(u.name)}</th>`).join("")}</tr></thead><tbody>${
      order.map(({s,r})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th>${units.map((u,k)=>{ const x=r?.perUnit[k];
        return x?`<td class="mx-grid-num${tone(pct(x.done,x.n))}">${x.done}/${x.n}</td>`:'<td class="mx-grid-num">–</td>'; }).join("")}</tr>`).join("")}</tbody></table>`;
  }else{
    const skills=unitIds(gridUnit).filter(live);
    const count=skills.map(id=>{ const st=all.map(x=>cellState(x.s.progress,id));
      const trying=st.filter(t=>t==="trying").length; return {id,done:st.filter(t=>["gold","lit","fading"].includes(t)).length,trying,hard:trying>0&&trying>=started*HARD_SHARE}; });
    grid=`<table class="mx-grid"><thead><tr><th class="mx-grid-name" scope="col">תלמיד</th>${count.map(c=>
      `<th scope="col" class="mx-grid-skill${c.hard?" hard":""}"${c.hard?' aria-label="קושי כיתתי"':""}><span title="${esc(BY[c.id].name)}">${c.hard?"⚠ ":""}${fmt(BY[c.id].short)}</span></th>`).join("")}</tr></thead><tbody>${
      order.map(({s})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th>${skills.map(id=>{ const st=cellState(s.progress,id);
        return `<td><span class="mx-cell ${st}" role="img" aria-label="${CELL_TEXT[st]}" title="${CELL_TEXT[st]}"></span></td>`; }).join("")}</tr>`).join("")}</tbody><tfoot>
      <tr><th scope="row" class="mx-grid-name">סיימו</th>${count.map(c=>`<td class="mx-grid-sum">${c.done}/${started}</td>`).join("")}</tr>
      <tr><th scope="row" class="mx-grid-name">מתקשים</th>${count.map(c=>`<td class="mx-grid-sum${c.hard?" hard":""}">${c.trying||""}</td>`).join("")}</tr></tfoot></table>
      <p class="mx-small">⚠ מיומנות שלפחות שליש מהתלמידים מתרגלים ועוד לא סיימו.</p>`;
  }
  const view=["grid","tasks"].includes(REPORT.tab)?REPORT.tab:"list";
  const bar=`<div class="mx-report-bar"><div class="mx-report-views" role="group" aria-label="תצוגה">
      <button type="button" class="mx-btn" data-report-tab="list" aria-pressed="${view==="list"}">רשימה</button>
      <button type="button" class="mx-btn" data-report-tab="grid" aria-pressed="${view==="grid"}">טבלת מיומנויות</button>
      <button type="button" class="mx-btn" data-report-tab="tasks" aria-pressed="${view==="tasks"}">משימות</button></div>
    <label class="mx-small">מיון <select data-report-sort>${Object.entries(REPORT_SORTS).map(([k,v])=>`<option value="${k}"${k===sort?" selected":""}>${v}</option>`).join("")}</select></label>
    ${view==="grid"?`<label class="mx-small">יחידה <select data-report-unit><option value="overview">כל היחידות</option>${units.map(u=>`<option value="${esc(u.id)}"${u.id===REPORT.unit?" selected":""}>${esc(u.name)}</option>`).join("")}</select></label>`:""}</div>`;
  sheet.querySelector(".mx-report").innerHTML=bar+(view==="grid"?`<div class="mx-grid-wrap" tabindex="0" role="region" aria-label="טבלת מיומנויות של הכיתה">${grid}</div>`
    :view==="tasks"?(REPORT.form?asgFormHtml(units):asgTasksHtml(order,name)):list);
}

/* ---------- the class's assignments, in the report (app/assignments.py) ----------
   The tab lists the class's assignments, how many students finished each and, for each student, which items are done
   (worked out by Sky.assignmentState from the progress and the server's quiz sittings, as on the student's own screen),
   and gives the teacher the form to make, change or delete one. */
const ASG_ERR={400:"אחד הפריטים אינו שייך ליחידות של הכיתה, או שהתאריך אינו תקין.",403:"רק מורה הכיתה יכול לתת לה משימות.",404:"הכיתה או המשימה לא נמצאו.",
  503:"המשימות אינן זמינות כרגע. נסו שוב מאוחר יותר."};
const asgStates=(a,order)=>order.map(({s})=>({s,st:Sky.assignmentState(a,s.progress,s.quiz_sittings)}));
function asgTasksHtml(order,name){
  const list=REPORT.data.assignments;
  if(list===null) return '<p class="mx-note">המשימות אינן זמינות כרגע באתר.</p>';
  const today=Sky.jerusalemDay(new Date());
  const cards=list.slice().sort((p,q)=>q.due_on.localeCompare(p.due_on)).map(a=>{
    const rows=asgStates(a,order), finished=rows.filter(x=>x.st.finished).length, past=today>a.due_on;
    return `<article class="mx-asg-t${past?" past":""}"><div class="mx-asg-head"><b>${esc(a.title)}</b><span class="mx-asg-due">${past?"המועד עבר · ":""}עד ${asgDate(a.due_on)}</span></div>
      ${a.note?`<p class="mx-asg-note">${esc(a.note)}</p>`:""}
      <p class="mx-asg-count"><b>${finished}</b> מתוך ${rows.length} תלמידים סיימו</p>
      <ul class="mx-asg-items">${a.items.map(i=>`<li>${asgItemLabel(i)}</li>`).join("")}</ul>
      ${rows.length?`<details class="mx-asg-who"><summary>מי עשה מה</summary><div class="mx-grid-wrap" tabindex="0" role="region" aria-label="מצב התלמידים במשימה"><table class="mx-grid">
        <thead><tr><th class="mx-grid-name" scope="col">תלמיד</th>${a.items.map(i=>`<th scope="col" class="mx-grid-unit">${asgItemLabel(i)}</th>`).join("")}</tr></thead><tbody>
        ${rows.map(({s,st})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th>${st.items.map(x=>
          `<td class="mx-asg-cell ${x.done?(x.late?"late":"ok"):x.known?"none":"unknown"}">${x.done?(x.late?"✓ באיחור":"✓"):x.known?"–":"?"}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div></details>`:""}
      <div class="mx-row"><button type="button" class="mx-btn" data-asg-edit="${esc(a.id)}">עריכה</button>
        <button type="button" class="mx-btn" data-asg-del="${esc(a.id)}">מחיקה</button></div></article>`;
  }).join("");
  return `<div class="mx-row"><button type="button" class="mx-btn solid" data-asg-new>משימה חדשה</button></div>
    ${cards||'<p class="mx-note">עוד לא נתתם משימות לכיתה. משימה היא מיומנויות לסיים, בוחן מסכם להגיש או מבחן תרגול, עד תאריך.</p>'}`;
}
function asgFormHtml(units){
  const old=REPORT.data.assignments.find(x=>x.id===REPORT.form.id);
  const a=old||{title:"",note:"",due_on:new Date(Date.now()+7*864e5).toLocaleDateString("en-CA",{timeZone:"Asia/Jerusalem"}),items:[]};
  const skills=new Set(a.items.filter(i=>i.kind==="skill").map(i=>i.id)), quizzes=new Set(a.items.filter(i=>i.kind==="unit_quiz").map(i=>i.unit));
  const exam=new Set(a.items.find(i=>i.kind==="exam")?.units||[]);
  const box=(name,value,on,label)=>`<label><input type="checkbox" name="${name}" value="${esc(value)}"${on?" checked":""}> ${label}</label>`;
  return `<form class="mx-asg-form" data-asg-form="${esc(old?.id||"")}" novalidate><h4>${old?"עריכת משימה":"משימה חדשה"}</h4>
    <label>כותרת<input name="title" maxlength="80" value="${esc(a.title)}" required></label>
    <label>הערה לתלמידים <small>(לא חובה)</small><textarea name="note" rows="2" maxlength="500">${esc(a.note)}</textarea></label>
    <label>להגיש עד<input type="date" name="due_on" value="${esc(a.due_on)}" required></label>
    <fieldset><legend>מיומנויות לסיים</legend>${units.map(u=>{ const ids=unitIds(u).filter(live);
      return `<details${ids.some(id=>skills.has(id))?" open":""}><summary>${esc(u.name)}</summary><div class="mx-asg-checks">${ids.map(id=>box("skill",id,skills.has(id),fmt(BY[id].short||BY[id].name))).join("")}</div></details>`; }).join("")}</fieldset>
    <fieldset><legend>בוחן מסכם להגשה</legend><div class="mx-asg-checks">${units.filter(u=>u.quiz).map(u=>box("quiz",u.id,quizzes.has(u.id),esc(u.name))).join("")||"<small>ליחידות של הכיתה אין בוחן מסכם.</small>"}</div></fieldset>
    <fieldset><legend>מבחן תרגול על היחידות</legend><div class="mx-asg-checks">${units.map(u=>box("exam",u.id,exam.has(u.id),esc(u.name))).join("")}</div>
      <small>מי שיסמן כמה יחידות יבקש מבחן תרגול שכולל את כולן.</small></fieldset>
    <div class="mx-row"><button type="submit" class="mx-btn solid">שמירה</button><button type="button" class="mx-btn" data-asg-cancel>ביטול</button>
      <span class="mx-small" role="status" aria-live="polite"></span></div></form>`;
}
async function asgSave(form){
  const id=form.dataset.asgForm, status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]"), classId=REPORT.id;
  const picked=name=>[...form.querySelectorAll(`[name=${name}]:checked`)].map(c=>c.value);
  const items=[...picked("skill").map(v=>({kind:"skill",id:v})),...picked("quiz").map(v=>({kind:"unit_quiz",unit:v}))];
  if(picked("exam").length) items.push({kind:"exam",units:picked("exam")});
  const body={title:form.elements.title.value,note:form.elements.note.value,due_on:form.elements.due_on.value,items};
  if(!body.title.trim()){ status.textContent="כתבו כותרת למשימה."; form.elements.title.focus(); return; }
  if(!body.due_on){ status.textContent="בחרו תאריך להגשה."; return; }
  if(!items.length){ status.textContent="בחרו לפחות פריט אחד: מיומנות, בוחן מסכם או מבחן תרגול."; return; }
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/assignments${id?`/${encodeURIComponent(id)}`:""}`,
      {method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(ASG_ERR[r.status]||"השמירה נכשלה. נסו שוב.");
    if(cur!=="report"||REPORT?.id!==classId) return;
    const list=REPORT.data.assignments||[];
    REPORT.data.assignments=id?list.map(x=>x.id===id?d:x):[d,...list];
    REPORT.form=null; drawReport();
    sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",`<p class="mx-small" role="status">${id?"המשימה עודכנה.":"המשימה נשמרה. התלמידים רואים אותה בבית."}</p>`);
  }catch(e){ if(cur==="report"){ button.disabled=false; status.textContent=e.message; } }
}
async function asgDelete(id){
  const a=REPORT.data.assignments.find(x=>x.id===id); if(!a) return;
  const started=REPORT.data.students.filter(s=>Sky.assignmentState(a,s.progress,s.quiz_sittings).doneCount>0).length;
  if(!confirm(`למחוק את המשימה "${a.title}"? התלמידים לא יראו אותה יותר.${started?` ${started} תלמידים כבר השלימו לפחות פריט אחד ממנה.`:""}`)) return;
  const classId=REPORT.id;
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/assignments/${encodeURIComponent(id)}`,{method:"DELETE"});
    if(!r.ok) throw Error(ASG_ERR[r.status]||"המחיקה נכשלה. נסו שוב.");
    if(cur!=="report"||REPORT?.id!==classId) return;
    REPORT.data.assignments=REPORT.data.assignments.filter(x=>x.id!==id); drawReport();
  }catch(e){ if(cur==="report") sheet.querySelector(".mx-manage-state").textContent=e.message; }
}
// the report's own controls: the view, the order and the unit of the grid
function reportControl(t){
  if(t.dataset.reportTab){ REPORT.tab=t.dataset.reportTab; repSet("tab",REPORT.tab); drawReport(); sheet.querySelector(`[data-report-tab="${REPORT.tab}"]`)?.focus(); }
  else if(t.matches("[data-report-sort]")){ REPORT.sort=t.value; repSet("sort",t.value); drawReport(); sheet.querySelector("[data-report-sort]")?.focus(); }
  else if(t.matches("[data-report-unit]")){ REPORT.unit=t.value; repSet("unit",t.value); drawReport(); sheet.querySelector("[data-report-unit]")?.focus(); }
}

/* ---------- the teacher's review of a student's answer (app/teacher_review.py) ----------
   The class teacher opens an open answer of one of their students (from a unit-quiz row of the report, or a handled
   request of the AI queue): the question, the photo, the automatic check, and a form for a score of their own and a
   comment. The teacher's score counts instead of the AI's wherever the answer is graded. */
let TR=null;   // the answer on the sheet: {attemptId, back (how to return), data, url}
const TR_ERR={invalid_score:"הציון חייב להיות מספר שלם בין 0 ל־100.",comment_too_long:"ההערה ארוכה מדי (עד 1000 תווים).",empty_review:"כתבו ציון או הערה.",
  invalid_comment:"ההערה אינה תקינה.",forbidden:"אין לכם הרשאה לתשובה הזו.",teacher_required:"אין לכם הרשאה לתשובה הזו.",not_found:"התשובה לא נמצאה.",
  answer_required:"לתשובה הזו אין תמונה שמורה.",review_unavailable:"הבדיקה אינה זמינה כרגע. נסו שוב מאוחר יותר.",answer_storage_unavailable:"שמירת תשובות אינה זמינה כרגע."};
function dropReview(){ if(TR?.url) URL.revokeObjectURL(TR.url); TR=null; }
const trName=email=>String(email||"").split("@")[0];
function trShell(title,backLabel){
  if(cur!=="review"){ if(!cur) back=document.activeElement; closeSheetQuietly(); cur="review"; }
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-manage-sheet mx-tr-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-manage-head"><h3 id="mxTitle">${esc(title)}</h3><span class="mx-manage-spacer"></span>
        <button class="mx-btn" data-review-back>${esc(backLabel)}</button><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p class="mx-manage-state" aria-live="polite"></p><div class="mx-tr"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}
// the answers of one unit-quiz sitting of a student, to open one of them
function reviewSitting(index,unitId){
  const student=REPORT?.data?.students[index], unit=G.units.find(u=>u.id===unitId);
  const sitting=(student?.quiz_sittings||[]).filter(x=>x.unit_id===unitId).at(-1);
  if(!sitting) return;
  trShell(`תשובות בבוחן: ${unit.name}`,"חזרה לדוח");   // opening the sheet closes the one before it, and its answer
  dropReview(); TR={back:()=>classReport(REPORT.id)};
  const STATE={missing:"לא צולמה תשובה",waiting:"ממתינה לבדיקה",unreadable:"לא קריאה",needs_review:"דורשת בדיקה שלכם",teacher:"נבדקה על ידכם",checked:"נבדקה"};
  sheet.querySelector(".mx-manage-state").textContent=`${trName(student.email)} · ${sitting.grade==null?"עוד אין ציון":`ציון ${sitting.grade}/100`}`;
  sheet.querySelector(".mx-tr").innerHTML=`<ol class="mx-uq-qs">${sitting.questions.map((q,k)=>`<li class="mx-uq-q"><div class="mx-uq-qhead"><b>שאלה ${k+1}</b>
      <span>${q.earned==null?"–":q.earned}/${q.points} נק׳</span></div><p class="mx-small">${STATE[q.state]||esc(q.state)}</p>
      ${q.state==="missing"?"":`<button class="mx-btn" data-review-answer="${esc(sitting.attempts[k])}" data-review-from="sitting:${index}:${esc(unitId)}">פתיחת התשובה</button>`}</li>`).join("")}</ol>`;
}
async function trOpenAnswer(attemptId,from){
  const [kind,a,b]=String(from||"").split(":");
  const backTo=kind==="sitting"?()=>reviewSitting(+a,b):kind==="queue"?()=>aiQueue():kind==="report"?()=>classReport(REPORT?.id):()=>closeSheet();
  trShell("תשובה של תלמיד",kind==="queue"?"חזרה לתור":"חזרה");
  dropReview(); const mine=TR={attemptId,back:backTo,data:null,url:null};
  sheet.querySelector(".mx-manage-state").textContent="טוענים את התשובה…";
  try{
    const r=await api(`/api/teacher/answers/${encodeURIComponent(attemptId)}`,{cache:"no-store"});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(TR_ERR[d.detail]||"לא הצלחנו לטעון את התשובה. נסו שוב.");
    if(TR!==mine) return;
    mine.data=d; drawReview();
    const img=await api(`/api/teacher/answers/${encodeURIComponent(attemptId)}/image`,{cache:"no-store"});
    if(img.ok){ const url=URL.createObjectURL(await img.blob()); if(TR!==mine) return URL.revokeObjectURL(url); mine.url=url; const el=sheet.querySelector(".mx-tr-img"); if(el){ el.src=url; el.hidden=false; } }
  }catch(e){ if(TR===mine) sheet.querySelector(".mx-manage-state").textContent=e.message; }
}
function drawReview(note=""){
  const d=TR.data, a=d.grading?.state==="completed"?d.grading.result:null, rv=d.review, rq=d.request;
  const isQuiz=String(d.attempt.question_id).startsWith("quiz:"), when=at=>new Date(at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"});
  sheet.querySelector(".mx-manage-state").textContent=`${trName(d.student.email)} · ${d.student.email}`;
  sheet.querySelector(".mx-tr").innerHTML=`
    <p class="mx-small">${fmt(d.attempt.snapshot.name||"")}</p>
    <p class="mx-aq-q">${fmtLoose(d.attempt.snapshot.question||"").replace(/\n/g,"<br>")}</p>
    <img class="mx-aq-img mx-tr-img" alt="התשובה שצילם התלמיד" ${TR.url?`src="${TR.url}"`:"hidden"}>
    ${rq?.state==="open"?`<div class="mx-tr-request" role="note"><b>התלמיד ביקש שתסתכלו שוב</b>${rq.message?`<p>${esc(rq.message)}</p>`:""}<small>${when(rq.created_at)}</small></div>`:""}
    <section class="mx-tr-ai"><h5>בדיקה אוטומטית (AI)</h5>${a?`<p><b>${esc(AQ_VERDICT[a.verdict]||"")}</b>${a.score==null?"":` · ${esc(a.score)}/100`}</p>
      ${a.feedback?`<p>${fmtLoose(a.feedback)}</p>`:""}
      ${a.transcription?`<details><summary>מה ה-AI קרא בתמונה</summary><p>${fmtLoose(a.transcription)}</p></details>`:""}
      ${a.solution?`<details><summary>הפתרון המלא</summary><p class="mx-grade-solution">${fmtLoose(a.solution)}</p></details>`:""}`:'<p class="mx-small">התשובה עוד לא נבדקה בבדיקה אוטומטית.</p>'}</section>
    ${rv?`<section><h5>הבדיקה שלכם</h5><p>${rv.score==null?"בלי ציון":`${esc(rv.score)}/100`} · <small>${when(rv.created_at)}</small></p>${rv.comment?`<p>${esc(rv.comment).replace(/\n/g,"<br>")}</p>`:""}</section>`:""}
    <form class="mx-tr-form" data-review-form>
      <h5>${rv?"עדכון הבדיקה שלכם":"הבדיקה שלכם"}</h5>
      <label>ציון (0 עד 100)<input type="number" name="score" min="0" max="100" step="1" inputmode="numeric" value="${rv?.score??""}"></label>
      <label>הערה לתלמיד<textarea name="comment" rows="3" maxlength="1000">${esc(rv?.comment||"")}</textarea></label>
      <p class="mx-small">${isQuiz?"הציון שלכם מחליף את הציון האוטומטי בחישוב ציון הבוחן.":"הציון שלכם מחליף את הציון האוטומטי. ציון 100 מסמן את המיומנות כהושלמה אצל התלמיד."}</p>
      <div class="mx-row"><button type="submit" class="mx-btn solid">שמירה</button><span class="mx-small" role="status" aria-live="polite">${esc(note)}</span></div></form>`;
}
async function reviewSave(form){
  const mine=TR, status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const raw=form.elements.score.value.trim(), body={comment:form.elements.comment.value};
  if(raw!=="") body.score=Number(raw);
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/teacher/answers/${encodeURIComponent(mine.attemptId)}/review`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(TR_ERR[d.detail]||"השמירה נכשלה. נסו שוב.");
    if(TR!==mine) return;
    mine.data.review=d.review; mine.data.request=d.request; mine.data.effective_score=d.review?.score??mine.data.effective_score;
    mine.changed=true; drawReview("נשמר. התלמיד יראה את הבדיקה שלכם.");
  }catch(e){ if(TR===mine){ button.disabled=false; status.textContent=e.message; } }
}

/* ---------- the teacher's AI queue (app/ai_queue.py) ----------
   A student does not call the AI. Their answer to check (or a photographed problem) waits here for their class's
   teacher, who looks at the photo and sends it to the AI or declines it with a note. The student's page shows the
   result. A manager sees every class's requests. */
let AQ=null, AQ_OPEN=null, RQ_OPEN=0, AQ_TAB="queue";   // AQ: the queue on the sheet; AQ_OPEN: how many requests wait (for the header button)
const AQ_KIND={photo:"📷 תרגיל לעזרה",grading:"📝 בדיקת תשובה"};
const AQ_STATE={pending:"ממתינה",sending:"נשלחת…",done:"נשלחה ל-AI",failed:"השליחה נכשלה",declined:"נדחתה",cancelled:"בוטלה"};
const AQ_ERR={grading_failed:"הבדיקה נכשלה. אפשר לנסות שוב.",grading_unavailable:"בדיקה אוטומטית אינה זמינה כרגע באתר.",open_ended_locked:"שאלות פתוחות נעולות כרגע.",
  grading_limit:"התלמיד הגיע למכסת הבדיקות היומית.",grading_busy:"כבר מתבצעות בדיקות לתלמיד הזה. נסו שוב בעוד רגע.",grading_interrupted:"הבדיקה הופסקה. אפשר לנסות שוב.",
  request_taken:"הבקשה כבר טופלה (אולי ממכשיר אחר). רעננו את התור.",queue_unavailable:"התור אינו זמין כרגע.",
  answer_storage_unavailable:"לא הצלחנו לקרוא את התמונה השמורה.",photo_failed:"פתרון התמונה נכשל. אפשר לנסות שוב."};
// a failed send's error is "code|reason|technical detail" (app/ai_queue.py)
function aqError(error){
  const [code,reason="",...rest]=String(error||"").split("|"), detail=rest.join("|");
  return `<p class="mx-aq-error">${esc(AQ_ERR[code]||code||"השליחה נכשלה.")}</p>${window.MathlyAnswers?.errorDetails?.(reason,detail)||""}`;
}
const AQ_VERDICT={correct:"נכונה",partial:"נכונה חלקית",incorrect:"שגויה",unreadable:"לא קריאה",needs_review:"דורשת בדיקה שלכם"};
const aqWaiting=r=>["pending","sending","failed"].includes(r.state);
const aqLabel=()=>`תור AI${(AQ_OPEN||0)+RQ_OPEN?` <span class="mx-aq-badge">${(AQ_OPEN||0)+RQ_OPEN}</span>`:""}`;   // waiting requests, and students asking to look again
function aqPaintBadge(){ document.querySelectorAll('[data-act="ai-queue"]').forEach(b=>{ if(!b.closest(".mx-sheet")) b.innerHTML=aqLabel(); }); }
function aqBadge(rows){ AQ_OPEN=rows.filter(r=>r.state==="pending").length; aqPaintBadge(); }
function rqBadge(rows){ RQ_OPEN=rows.length; aqPaintBadge(); }
async function aqCount(){
  try{ const r=await api("/api/ai-queue",{cache:"no-store"}); if(r.ok) aqBadge((await r.json()).requests||[]); }catch{}
  try{ const r=await api("/api/teacher/review-requests",{cache:"no-store"}); if(r.ok) rqBadge((await r.json()).requests||[]); }catch{}
}
function dropQueue(){ if(AQ) Object.values(AQ.urls).forEach(u=>u&&URL.revokeObjectURL(u)); AQ=null; }
async function aiQueue(){
  if(cur!=="aiqueue"){ if(!cur) back=document.activeElement; closeSheetQuietly(); cur="aiqueue"; AQ={rows:null,reqs:null,tab:AQ_TAB,urls:{},busy:new Set()}; }
  const mine=AQ;
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-manage-sheet mx-aq-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-manage-head"><h3 id="mxTitle">תור AI</h3><span class="mx-manage-spacer"></span>
        <button class="mx-btn" data-act="aq-all" hidden>שליחת כל הממתינות</button><button class="mx-btn" data-act="ai-queue">רענון</button><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <div class="mx-report-views" data-aq-tabs role="group" aria-label="תצוגה"></div>
      <p class="mx-small" data-aq-help>בקשות התלמידים מחכות כאן. הסתכלו בתמונה, ואז שלחו אותה ל-AI או דחו אותה. התלמיד רואה את התוצאה בעמוד שלו.</p>
      <p class="mx-manage-state" aria-live="polite">טוענים את הבקשות…</p><div class="mx-aq"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
  try{
    const r=await api("/api/ai-queue",{cache:"no-store"});
    if(!r.ok) throw Error(r.status===403?"רק מורה של כיתה יכול לראות את התור.":"לא הצלחנו לטעון את התור. נסו שוב.");
    const d=await r.json(); if(AQ!==mine) return;
    mine.rows=d.requests||[]; drawQueue();
  }catch(e){ if(AQ===mine) sheet.querySelector(".mx-manage-state").textContent=e.message; }
  try{   // the students asking the teacher to look again at a checked answer
    const r=await api("/api/teacher/review-requests",{cache:"no-store"});
    mine.reqs=r.ok?(await r.json()).requests||[]:[];
  }catch{ mine.reqs=[]; }
  if(AQ===mine){ rqBadge(mine.reqs); drawQueue(); }
}
function aqTab(tab){ if(!AQ) return; AQ.tab=AQ_TAB=tab; drawQueue(); sheet.querySelector(`[data-aq-tab="${tab}"]`)?.focus(); }
function aqResult(r){
  const x=r.result||{};
  if(r.kind==="photo") return x.readable===false?"ה-AI לא הצליח לקרוא את התרגיל.":`התשובה שה-AI מצא: ${fmtLoose(x.answer||"")}`;
  return `תוצאה: ${esc(AQ_VERDICT[x.verdict]||"")}${x.score==null?"":` · ${esc(x.score)}/100`}`;
}
function drawQueue(){
  const box=sheet.querySelector(".mx-aq"); if(!box) return;
  const tabs=sheet.querySelector("[data-aq-tabs]"), asks=AQ?.reqs;
  if(tabs) tabs.innerHTML=`<button type="button" class="mx-btn" data-aq-tab="queue" aria-pressed="${AQ.tab!=="requests"}">בקשות לבדיקה</button>
    <button type="button" class="mx-btn" data-aq-tab="requests" aria-pressed="${AQ.tab==="requests"}">בקשות לבדיקה חוזרת${asks?.length?` <span class="mx-aq-badge">${asks.length}</span>`:""}</button>`;
  if(AQ?.tab==="requests") return drawRequests();
  sheet.querySelector('[data-act="aq-all"]').hidden=true;
  sheet.querySelector("[data-aq-help]").hidden=false;
  if(!AQ?.rows) return;
  const open=AQ.rows.filter(aqWaiting), rest=AQ.rows.filter(r=>!aqWaiting(r));
  aqBadge(AQ.rows);
  sheet.querySelector(".mx-manage-state").textContent=open.length?(open.length===1?"בקשה אחת ממתינה":`${open.length} בקשות ממתינות`):"אין בקשות ממתינות.";
  sheet.querySelector('[data-act="aq-all"]').hidden=open.filter(r=>r.state==="pending").length<2;
  const when=at=>new Date(at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"});
  const card=r=>{
    const busy=AQ.busy.has(r.id), act=r.state==="pending"||r.state==="failed";
    return `<article class="mx-aq-card ${esc(r.state)}"><div class="mx-aq-head"><b dir="ltr">${esc(String(r.email).split("@")[0])}</b><span>${AQ_KIND[r.kind]||""}</span>
        <small>${when(r.created_at)}</small><span class="mx-aq-state">${busy?"שולחים ל-AI…":AQ_STATE[r.state]||esc(r.state)}</span></div>
      ${r.label?`<p class="mx-aq-label">${fmt(r.label)}</p>`:""}${r.question?`<p class="mx-aq-q">${fmtLoose(r.question).replace(/\n/g,"<br>")}</p>`:""}
      ${aqWaiting(r)?`<img class="mx-aq-img" alt="התמונה ששלח התלמיד" data-aq-img="${esc(r.id)}" hidden>`:""}
      ${r.state==="failed"&&r.error?aqError(r.error):""}
      ${r.state==="declined"&&r.note?`<p class="mx-small">ההערה שלכם: ${esc(r.note)}</p>`:""}
      ${r.state==="done"?`<p class="mx-small">${aqResult(r)}</p>`:""}
      ${r.kind==="grading"&&r.attempt_id&&!aqWaiting(r)?`<button type="button" class="mx-btn" data-review-answer="${esc(r.attempt_id)}" data-review-from="queue">פתיחת התשובה</button>`:""}
      ${act?`<div class="mx-row"><button class="mx-btn solid" data-aq-send="${esc(r.id)}"${busy?" disabled":""}>${r.state==="failed"?"שליחה חוזרת ל-AI":"שליחה ל-AI"}</button>
        <button class="mx-btn" data-aq-decline="${esc(r.id)}"${busy?" disabled":""}>דחייה</button></div>`:""}</article>`;
  };
  box.innerHTML=`${open.map(card).join("")}${rest.length?`<h4 class="mx-aq-done">טופלו ביממה האחרונה</h4>${rest.map(card).join("")}`:""}`;
  open.forEach(r=>aqImage(r.id));
}
// students who asked the teacher to look again at a checked answer
function drawRequests(){
  const box=sheet.querySelector(".mx-aq"), rows=AQ.reqs;
  sheet.querySelector('[data-act="aq-all"]').hidden=true;
  sheet.querySelector("[data-aq-help]").hidden=true;
  const state=sheet.querySelector(".mx-manage-state");
  if(!rows){ state.textContent="טוענים את הבקשות…"; box.innerHTML=""; return; }
  state.textContent=rows.length?(rows.length===1?"בקשה אחת לבדיקה חוזרת":`${rows.length} בקשות לבדיקה חוזרת`):"אין בקשות לבדיקה חוזרת.";
  const when=at=>new Date(at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"});
  box.innerHTML=rows.map(r=>`<article class="mx-aq-card pending"><div class="mx-aq-head"><b dir="ltr">${esc(String(r.student).split("@")[0])}</b><span>🔁 בקשה לבדיקה חוזרת</span><small>${when(r.created_at)}</small></div>
    ${r.question?`<p class="mx-aq-label">${fmt(r.question)}</p>`:""}
    ${r.message?`<p class="mx-aq-q">${esc(r.message)}</p>`:'<p class="mx-small">בלי הודעה.</p>'}
    <div class="mx-row"><button type="button" class="mx-btn solid" data-review-answer="${esc(r.attempt_id)}" data-review-from="queue">פתיחת התשובה</button></div></article>`).join("");
}
async function aqImage(id){
  const mine=AQ, show=url=>{ const img=sheet.querySelector(`[data-aq-img="${CSS.escape(id)}"]`); if(img){ img.src=url; img.hidden=false; } };
  if(mine.urls[id]) return show(mine.urls[id]);
  if(id in mine.urls) return;   // loading
  mine.urls[id]=null;
  try{
    const r=await api(`/api/ai-queue/${encodeURIComponent(id)}/image`,{cache:"no-store"}); if(!r.ok) throw Error();
    const url=URL.createObjectURL(await r.blob());
    if(AQ!==mine) return URL.revokeObjectURL(url);
    mine.urls[id]=url; show(url);
  }catch{ if(AQ===mine) delete mine.urls[id]; }
}
async function aqPost(id,what,body){
  const mine=AQ; if(!mine||mine.busy.has(id)) return;
  mine.busy.add(id); drawQueue();
  let row=null, err="";
  try{
    const r=await api(`/api/ai-queue/${encodeURIComponent(id)}/${what}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(AQ_ERR[d.detail]||"הפעולה נכשלה. נסו שוב.");
    row=d;
  }catch(e){ err=e.message; }
  mine.busy.delete(id); if(AQ!==mine) return;
  if(row){ const i=mine.rows.findIndex(x=>x.id===id); if(i>=0) mine.rows[i]=row; }
  drawQueue(); if(err) sheet.querySelector(".mx-manage-state").textContent=err;
}
const aqSend=id=>aqPost(id,"send");
function aqDecline(id){
  const note=prompt("הערה לתלמיד (לא חובה), למשל: צלמו שוב, התמונה לא ברורה");
  if(note!==null) return aqPost(id,"decline",{note});
}
async function aqAll(){ for(const r of (AQ?.rows||[]).filter(x=>x.state==="pending")){ if(!AQ) return; await aqSend(r.id); } }

/* A photographed problem (/api/math/photo, app/math_photo.py): hints first. The sheet shows the problem as it was
   read (a wrong reading is the student's cue to photograph again), then one hint; each further hint, each step and
   the whole solution with its answer come only when the student asks for them. */
async function shrink(file){ return window.MathlyPhoto.prepare(file); }
async function photo(file){
  stopPhone();
  cancelAdvance();
  let blob; try{ blob=await shrink(file); }catch{ blob=file; }   // a format the browser cannot draw goes as it is
  if(PH?.url) URL.revokeObjectURL(PH.url);
  if(cur!=="photo"){ if(!cur) back=document.activeElement; cur="photo"; }
  const mine=PH={url:URL.createObjectURL(blob),data:null,error:"",busy:true,shown:1,works:new Set(),all:false,fresh:true};
  drawPhoto();
  try{
    const form=new FormData(); form.append("photo",blob,"problem.jpg");
    const res=await api("/api/math/photo",{method:"POST",body:form}), data=await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(typeof data.detail==="string"?data.detail:`השרת ענה ${res.status}`);
    if(data.queued){ mine.req=data.request; mine.left=data.left; } else mine.data=data;
  }catch(e){ mine.error=e.message; }
  mine.busy=false;
  if(PH===mine&&cur==="photo") drawPhoto();   // a newer photo, or a closed sheet, keeps its own
  if(mine.req) photoWait(mine);
}
// a student's photo waits for their teacher (app/ai_queue.py): the sheet looks for the answer while it is open
const photoWaiting=req=>!!req&&["pending","sending","failed"].includes(req.state);
async function photoWait(mine){
  while(PH===mine&&cur==="photo"&&photoWaiting(mine.req)){
    await new Promise(done=>setTimeout(done,8000));
    if(PH!==mine||cur!=="photo") return;
    try{
      const r=await api("/api/math/ai-requests",{cache:"no-store"}); if(!r.ok) continue;
      const row=((await r.json()).requests||[]).find(x=>x.id===mine.req.id); if(!row) continue;
      mine.req=row; if(row.state==="done"&&row.result) mine.data={...row.result,left:mine.left};
    }catch{ continue; }
    if(!photoWaiting(mine.req)&&PH===mine&&cur==="photo") drawPhoto();
  }
}
async function photoCancel(){
  const mine=PH; if(!mine?.req) return;
  try{ const r=await api(`/api/math/ai-requests/${encodeURIComponent(mine.req.id)}/cancel`,{method:"POST"}); if(r.ok) mine.req=await r.json(); }catch{}
  if(PH===mine&&cur==="photo") drawPhoto();
}
function drawPhoto(){
  const d=PH.data;
  let body;
  if(PH.busy) body='<div class="mx-wait"><span class="mx-spin" aria-hidden="true"></span><b>קוראים את התרגיל ופותרים…</b><small>זה לוקח כמה שניות.</small></div>';
  else if(PH.error) body=`<div class="mx-bad"><b>לא הצלחנו</b><span>${esc(PH.error)}</span><button class="mx-btn" data-act="retake">צילום מחדש</button></div>`;
  else if(!d&&photoWaiting(PH.req)) body=`<div class="mx-wait"><b>התמונה נשלחה למורה</b><small>אחרי שהמורה יאשר, הרמזים והפתרון יופיעו כאן.</small><button class="mx-btn" data-act="photo-cancel">ביטול הבקשה</button></div>`;
  else if(!d) body=`<div class="mx-bad"><b>${PH.req?.state==="cancelled"?"הבקשה בוטלה":"המורה לא אישר את הבקשה"}</b>${PH.req?.note?`<span>הערת המורה: ${esc(PH.req.note)}</span>`:""}<button class="mx-btn" data-act="retake">צילום חדש</button></div>`;
  else if(!d.readable) body=`<div class="mx-bad"><b>לא הצלחנו לקרוא את התרגיל</b><span>${fmtLoose(d.note||"צלמו שוב, קרוב יותר ובאור טוב.")}</span><button class="mx-btn" data-act="retake">צילום מחדש</button></div>`;
  else{
    const n=d.steps.length, shown=PH.all?n:Math.min(PH.shown,n);
    body=`<div class="mx-read"><small>זה התרגיל שקראנו:</small><p>${fmtLoose(d.problem)}</p><button class="mx-link" data-act="retake">לא נכון? צלמו שוב</button></div>
      ${d.note?`<p class="mx-small">${fmtLoose(d.note)}</p>`:""}
      <ol class="mx-steps">${d.steps.slice(0,shown).map((s,i)=>`<li><span>${fmtLoose(s.hint)}</span>
        ${PH.all||PH.works.has(i)?`<div class="mx-work">${fmtLoose(s.work)}</div>`:`<button class="mx-link" data-act="work" data-i="${i}">הראו את הצעד</button>`}</li>`).join("")}</ol>
      ${PH.all?`<div class="mx-ok"><b>התשובה</b><span>${fmtLoose(d.answer)}</span></div>`:`<div class="mx-row">
        ${shown<n?'<button class="mx-btn solid" data-act="hint">רמז הבא</button>':""}<button class="mx-btn" data-act="all">הפתרון המלא</button></div>`}
      ${d.skill&&BY[d.skill]?`<div class="mx-sec"><h4>המיומנות שהתרגיל מתרגל</h4><div class="mx-chips">${chips([d.skill])}</div></div>`:""}
      ${d.left!=null?`<p class="mx-small">נשארו לכם היום ${d.left} צילומים.</p>`:""}`;
  }
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><h3 id="mxTitle">פתרון מתמונה</h3><small class="mx-src">קודם רמזים, והפתרון המלא כשתבקשו.</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${PH.url?`<img class="mx-thumb" src="${PH.url}" alt="התמונה ששלחתם">`:""}
      <div class="mx-pbody" aria-live="polite">${body}</div></div>`;
  sheet.hidden=false;
  if(PH.fresh){ PH.fresh=false; sheet.querySelector(".mx-x").focus({preventScroll:true}); }
}

/* The teacher's explanations, for students (GET /api/math/units/.../student-resources): the resources a teacher marked
   visible. Those tagged with a skill appear in that skill's sheet and in its help panel; the rest of the unit's are
   on a list opened from the unit on the path. Images come with the student's sign-in, so each is a blob URL. */
const SRES={};   // unit id → {rows, p (the request), at, urls}
const SRES_TTL=300000;
function sresLoad(unitId){
  const c=SRES[unitId]||=({rows:null,p:null,at:0,urls:{}});
  if(!c.p||Date.now()-c.at>SRES_TTL){
    c.at=Date.now();
    c.p=(async()=>{ try{ const r=await api(`/api/math/units/${encodeURIComponent(unitId)}/student-resources`,{cache:"no-store"}); c.rows=r.ok?(await r.json()).resources||[]:[]; }catch{ c.rows=c.rows||[]; } return c.rows; })();
  }
  return c.p;
}
async function sresImage(unitId,id){
  const c=SRES[unitId]; if(c.urls[id]) return c.urls[id];
  try{ const r=await api(`/api/math/student-resources/${encodeURIComponent(id)}/image`); if(r.ok) return c.urls[id]=URL.createObjectURL(await r.blob()); }catch{}
  return "";
}
const sresList=rows=>`<div class="mx-sres">${rows.map(r=>`<figure class="mx-sres-item"><button type="button" class="mx-sres-img" data-sres="${esc(r.id)}" aria-label="הגדלה או הקטנה של התמונה">
  <img data-sres-img="${esc(r.id)}" alt="${esc(r.kind==="other"?r.note:RES_KINDS[r.kind]||"")}"></button>
  <figcaption><b>${esc(RES_KINDS[r.kind]||"")}</b>${r.note?` · ${esc(r.note)}`:""}</figcaption></figure>`).join("")}</div>`;
function sresPaint(node,unitId,rows){
  node.insertAdjacentHTML("beforeend",sresList(rows));
  for(const r of rows) sresImage(unitId,r.id).then(url=>{ const img=node.querySelector(`[data-sres-img="${CSS.escape(r.id)}"]`); if(img&&url) img.src=url; });
}
// fills a box with the unit's explanations that `pick` chooses (a skill's own); the box stays hidden when there are none
async function fillExplanations(node,unitId,pick){
  if(!node||!CFG.userId) return;
  const rows=(await sresLoad(unitId)).filter(pick);
  if(!rows.length||!node.isConnected) return;
  node.innerHTML="<h4>הסברים מהמורה</h4>"; node.hidden=false; sresPaint(node,unitId,rows);
}
// the unit's explanations that belong to no skill: a button under the unit, once they are known to exist
function decorateUnits(){
  if(!CFG.userId||can("students.view")||VIEW==="sky"||!path) return;
  for(const u of mineUnits()){
    const c=SRES[u.id];
    if(!c?.rows){ if(!c?.p) sresLoad(u.id).then(()=>{ if(root&&!root.hidden&&!cur) decorateUnits(); }); continue; }
    const general=c.rows.filter(r=>!r.skill_id), section=path.querySelector(`#mx-unit-${u.id}`);
    if(general.length&&section&&!section.querySelector(".mx-sres-open"))
      section.insertAdjacentHTML("beforeend",`<button type="button" class="mx-sres-open" data-act="unit-explanations" data-unit="${esc(u.id)}">📷 הסברים מהמורה (${general.length})</button>`);
  }
}
async function openExplanations(unitId){
  const unit=G.units.find(u=>u.id===unitId); if(!unit) return;
  stopPhone(); cancelAdvance(); if(!cur) back=document.activeElement; closeSheetQuietly(); cur="explanations";
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-res u-${unit.id}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(unit.name)}</span><h3 id="mxTitle">הסברים מהמורה</h3>
        <small class="mx-src">תמונות שהמורה שמר לשיעור הזה</small></div><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <div class="mx-skill-res" data-unit-res><p class="mx-note">טוענים…</p></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
  const rows=(await sresLoad(unitId)).filter(r=>!r.skill_id), node=sheet.querySelector("[data-unit-res]");
  if(!node||cur!=="explanations") return;
  node.innerHTML=rows.length?"":'<p class="mx-note">אין כרגע הסברים לשיעור הזה.</p>';
  if(rows.length) sresPaint(node,unitId,rows);
}

/* Lesson resources (app/unit_resources.py). A teacher taps a unit's title on the path, photographs an exercise or an
   explanation, says what it shows (a new exercise, a theory explanation, or other words) and, if they like, which of
   the unit's topics it belongs to. Images come through the API with the teacher's sign-in, so each is a blob URL. */
const RES_KINDS={exercise:"תרגיל חדש",theory:"הסבר תיאורטי",other:"אחר"};
const resError=(status,fallback)=>({401:"צריך להיכנס מחדש.",403:"רק מורים יכולים לראות ולהוסיף משאבים.",404:"השיעור או התמונה לא נמצאו.",
  413:"התמונה גדולה מדי. נסו לצלם שוב.",415:"לא הצלחנו לקרוא את התמונה. צלמו שוב או בחרו JPEG, PNG או WebP.",
  503:"שמירת משאבים עדיין לא זמינה בשרת. נסו שוב מאוחר יותר."}[status]||fallback);
function dropResources(){
  if(!RES) return;
  Object.values(RES.urls).forEach(url=>URL.revokeObjectURL(url));
  if(RES.preview) URL.revokeObjectURL(RES.preview);
  RES=null;
}
function openResources(unitId){
  const unit=G.units.find(u=>u.id===unitId);
  if(!unit||!can("students.view")) return;
  stopPhone(); cancelAdvance(); dropResources();
  if(!cur) back=document.activeElement;
  cur="resources";
  RES={unit,items:null,error:"",urls:{},photo:null,preview:null,busy:false,msg:"",fresh:true};
  drawResources();
  loadResources(RES);
}
async function loadResources(mine){
  try{
    const res=await api(`/api/math/units/${encodeURIComponent(mine.unit.id)}/resources`,{cache:"no-store"}), data=await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(resError(res.status,"לא הצלחנו לטעון את המשאבים."));
    mine.items=data.resources||[]; mine.error="";
  }catch(e){ mine.items=mine.items||[]; mine.error=e.message; }
  if(RES===mine&&cur==="resources") drawResources();
}
function resourceForm(){
  const skills=unitSkills(RES.unit.id);
  return `<form class="mx-res-form" novalidate>
    <img class="mx-thumb" src="${RES.preview}" alt="התמונה שצילמתם">
    <fieldset><legend>מה בתמונה?</legend><div class="mx-res-kinds">
      ${Object.entries(RES_KINDS).map(([k,label])=>`<label><input type="radio" name="kind" value="${k}"><span>${label}</span></label>`).join("")}</div>
      <input name="note" maxlength="200" autocomplete="off" placeholder="כתבו מה יש בתמונה" aria-label="תיאור חופשי של התמונה" hidden></fieldset>
    <label>נושא <small>(לא חובה)</small><select name="skill"><option value="">ללא נושא מסוים</option>
      ${skills.map(s=>`<option value="${esc(s.id)}">${esc(plain(s.name))}</option>`).join("")}</select></label>
    <label class="mx-res-visible"><input type="checkbox" name="visible"><span>גלוי לתלמידים</span></label>
    <small class="mx-small">הסבר תיאורטי מוצג לתלמידים כברירת מחדל. תרגיל והערה נשארים מוסתרים עד שתסמנו.</small>
    <div class="mx-row"><button type="submit" class="mx-btn solid"${RES.busy?" disabled":""}>${RES.busy?"שומרים…":"שמירה במשאבים"}</button>
      <button type="button" class="mx-btn" data-act="res-retake"${RES.busy?" disabled":""}>צילום מחדש</button>
      <button type="button" class="mx-btn" data-act="res-cancel"${RES.busy?" disabled":""}>ביטול</button></div></form>`;
}
function resourceItem(r){
  const skill=r.skill_id&&BY[r.skill_id], mine=r.created_by===CFG.userId||can("management.access");
  const when=new Date(r.created_at), date=Number.isNaN(when.getTime())?"":when.toLocaleDateString("he-IL",{day:"numeric",month:"short",year:"numeric"});
  return `<article class="mx-res-item"><a class="mx-res-img" data-res-link="${esc(r.id)}" target="_blank" rel="noopener" aria-label="פתיחת התמונה בגודל מלא">
      <img data-res-img="${esc(r.id)}" alt="${esc(r.kind==="other"?r.note:RES_KINDS[r.kind]||"")}"${RES.urls[r.id]?` src="${RES.urls[r.id]}"`:""}></a>
    <div><b>${esc(RES_KINDS[r.kind]||r.kind)}</b>${r.kind==="other"&&r.note?`<p>${esc(r.note)}</p>`:""}
      <small>${skill?`${fmt(skill.short||skill.name)} · `:""}${esc(date)}${r.created_email?` · <span dir="ltr">${esc(r.created_email)}</span>`:""}</small>
      <span class="mx-res-vis${r.visible?" on":""}">${r.visible?"👁 גלוי לתלמידים":"🔒 מוסתר מהתלמידים"}</span></div>
    ${mine?`<div class="mx-res-acts"><button class="mx-link" data-act="res-visible" data-res="${esc(r.id)}" data-visible="${r.visible?0:1}">${r.visible?"הסתרה מהתלמידים":"הצגה לתלמידים"}</button>
      <button class="mx-link" data-act="res-delete" data-res="${esc(r.id)}">מחיקה</button></div>`:""}</article>`;
}
function drawResources(){
  const items=RES.items, was=sheet.querySelector(".mx-res-form");   // a redraw keeps what was filled in
  const filled=was&&{kind:was.elements.kind.value,note:was.elements.note.value,skill:was.elements.skill.value,
    visible:was.elements.visible.checked,touched:!!was.elements.visible.dataset.touched};
  const list=items===null?'<p class="mx-note">טוענים את המשאבים…</p>':items.length?`<div class="mx-res-list">${items.map(resourceItem).join("")}</div>`
    :'<p class="mx-note">עוד אין משאבים לשיעור הזה. צלמו תרגיל או הסבר כדי להוסיף.</p>';
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-res u-${RES.unit.id}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(RES.unit.name)}</span><h3 id="mxTitle">משאבי השיעור</h3>
        <small class="mx-src">תמונות של תרגילים והסברים לשיעור הזה</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${RES.photo?resourceForm():'<button class="mx-btn solid mx-res-take" data-act="res-take">📷 צילום תמונה</button>'}
      <p class="mx-res-msg" role="status" aria-live="polite">${esc(RES.msg)}</p>
      ${RES.error?`<p class="mx-bad">${esc(RES.error)}</p>`:""}
      <div class="mx-sec"><h4>משאבים${items?.length?` (${items.length})`:""}</h4>${list}</div></div>`;
  sheet.hidden=false;
  if(RES.fresh){ RES.fresh=false; sheet.querySelector(".mx-x").focus({preventScroll:true}); }
  const form=sheet.querySelector(".mx-res-form");
  if(form){
    const note=form.elements.note;
    const visible=form.elements.visible;   // shown to students: a theory explanation by default, until the teacher decides
    if(filled){ form.querySelectorAll('[name="kind"]').forEach(r=>r.checked=r.value===filled.kind); note.value=filled.note; form.elements.skill.value=filled.skill; note.hidden=filled.kind!=="other";
      visible.checked=filled.visible; if(filled.touched) visible.dataset.touched="1"; }
    form.addEventListener("change",event=>{
      if(event.target===visible){ visible.dataset.touched="1"; return; }
      note.hidden=form.elements.kind.value!=="other"; if(!note.hidden) note.focus();
      if(!visible.dataset.touched) visible.checked=form.elements.kind.value==="theory";
    });
    form.onsubmit=event=>{ event.preventDefault(); saveResource(form); };
  }
  (items||[]).forEach(r=>{ if(r.id in RES.urls) showResourceImage(r.id); else loadResourceImage(RES,r.id); });
}
function showResourceImage(id){
  const url=RES.urls[id], img=sheet.querySelector(`[data-res-img="${CSS.escape(id)}"]`), link=sheet.querySelector(`[data-res-link="${CSS.escape(id)}"]`);
  if(!url) return;
  if(img) img.src=url;
  if(link) link.href=url;
}
async function loadResourceImage(mine,id){
  mine.urls[id]=null;   // asked for once
  try{
    const res=await api(`/api/math/resources/${encodeURIComponent(id)}/image`);
    if(!res.ok) return;
    const url=URL.createObjectURL(await res.blob());
    if(RES!==mine){ URL.revokeObjectURL(url); return; }
    mine.urls[id]=url; showResourceImage(id);
  }catch{}
}
async function resourcePhoto(file){
  if(!RES||cur!=="resources") return;
  const mine=RES;
  mine.msg="מכינים את התמונה…"; drawResources();
  let blob=null;
  try{ blob=await window.MathlyPhoto.prepare(file); }catch{}
  if(!blob&&["image/jpeg","image/png","image/webp"].includes(file.type)) blob=file;
  if(RES!==mine) return;
  if(!blob||blob.size>5000000){ mine.msg="לא הצלחנו להכין את התמונה. צלמו שוב."; return drawResources(); }
  if(mine.preview) URL.revokeObjectURL(mine.preview);
  mine.photo=blob; mine.preview=URL.createObjectURL(blob); mine.msg="בחרו מה יש בתמונה, ואם תרצו גם את הנושא.";
  drawResources();
  sheet.querySelector(".mx-res-form")?.scrollIntoView({block:"start"});
}
async function saveResource(form){
  const mine=RES, kind=form.elements.kind.value, note=form.elements.note.value.trim(), skill=form.elements.skill.value;
  const status=sheet.querySelector(".mx-res-msg");
  if(!kind){ status.textContent="בחרו מה יש בתמונה: תרגיל חדש, הסבר תיאורטי או אחר."; return; }
  if(kind==="other"&&!note){ status.textContent="כתבו בכמה מילים מה יש בתמונה."; form.elements.note.focus(); return; }
  mine.busy=true; form.querySelectorAll("button").forEach(b=>b.disabled=true); status.textContent="שומרים…";
  try{
    const body=new FormData(); body.append("photo",mine.photo,"resource.jpg"); body.append("kind",kind); body.append("note",kind==="other"?note:""); body.append("skill",skill); body.append("visible",form.elements.visible.checked?"1":"0");
    const res=await api(`/api/math/units/${encodeURIComponent(mine.unit.id)}/resources`,{method:"POST",body}), data=await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(resError(res.status,"לא הצלחנו לשמור. נסו שוב."));
    mine.urls[data.id]=URL.createObjectURL(mine.photo);   // the saved photo, without downloading it again
    mine.items=[data,...(mine.items||[])];
    URL.revokeObjectURL(mine.preview); mine.photo=mine.preview=null; mine.msg="התמונה נשמרה במשאבי השיעור.";
  }catch(e){ mine.msg=e.message; }
  mine.busy=false;
  if(RES===mine&&cur==="resources") drawResources();
}
async function setResourceVisible(id,visible){
  const mine=RES; if(!mine) return;
  try{
    const res=await api(`/api/math/resources/${encodeURIComponent(id)}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({visible})}), data=await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(resError(res.status,"לא הצלחנו לשנות. נסו שוב."));
    const i=mine.items.findIndex(r=>r.id===id); if(i>=0) mine.items[i]={...mine.items[i],visible:data.visible};
    mine.msg=data.visible?"התמונה גלויה עכשיו לתלמידים.":"התמונה מוסתרת מהתלמידים.";
  }catch(e){ mine.msg=e.message; }
  if(RES===mine&&cur==="resources") drawResources();
}
async function deleteResource(id){
  const mine=RES; if(!mine||!confirm("למחוק את התמונה ממשאבי השיעור?")) return;
  try{
    const res=await api(`/api/math/resources/${encodeURIComponent(id)}`,{method:"DELETE"});
    if(!res.ok) throw new Error(resError(res.status,"לא הצלחנו למחוק. נסו שוב."));
    mine.items=mine.items.filter(r=>r.id!==id);
    if(mine.urls[id]) URL.revokeObjectURL(mine.urls[id]);
    delete mine.urls[id]; mine.msg="התמונה נמחקה.";
  }catch(e){ mine.msg=e.message; }
  if(RES===mine&&cur==="resources") drawResources();
}

function geometryDiagram(diagram){
  const triangle=diagram.type==="triangle";
  return `<div class="mx-geometry"><svg viewBox="0 0 320 210" role="img" aria-label="${esc(diagram.alt)}">
    <path d="${triangle?"M60 165 L260 165 L60 35 Z":"M60 50 H260 V165 H60 Z"}"/>
    ${triangle?'<path class="mx-angle" d="M60 147 H78 V165"/>':""}
    <text x="160" y="192" text-anchor="middle">${esc(diagram.base)}</text>
    <text x="38" y="110" text-anchor="middle">${esc(diagram.height)}</text>
    ${triangle?`<text x="180" y="90" text-anchor="middle">${esc(diagram.side||"")}</text>`:""}
    </svg><small>השרטוט להמחשה ואינו בקנה מידה</small></div>`;
}

/* A geometry question's figure (`figure` in app/math_algebra9.json, checked by app/math_skills.py), one statement per ";":
   A=x,y[@dir] a point (y up; "_P" is not named, @n/s/e/w/ne/nw/se/sw places its name) · poly A B C · line A B · dash A B
   dot A · len A B text (lenx: on the other side) · ang P V Q text (ang2/ang3: two or three arcs) · right P V Q
   tick A B n (equal sides) · par A B n (parallel arrows) · text x,y words · note words (a line under the figure)
   grid (a coordinate plane) */
function figure(src){
  const P={}, ops=[]; let grid=false;
  for(const st of src.split(";").map(s=>s.trim()).filter(Boolean)){
    const m=st.match(/^([A-Za-z_][\w']*)=(-?[\d.]+),(-?[\d.]+)(?:@(\w+))?$/);
    if(m){ P[m[1]]={x:+m[2],y:+m[3],dir:m[4]}; continue; }
    if(st==="grid"){ grid=true; continue; }
    const [op,...a]=st.split(/\s+/); ops.push([op,a]);
  }
  const under=ops.filter(([op])=>op==="note").map(([,a])=>`<p>${esc(a.join(" "))}</p>`).join("");
  const notes=ops.filter(([op])=>op==="text").map(([,a])=>{const [x,y]=a[0].split(",").map(Number);return {x,y,words:a.slice(1).join(" ")}});
  const all=[...Object.values(P),...notes], xs=all.map(p=>p.x), ys=all.map(p=>p.y);
  let x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
  if(grid){ x0=Math.floor(Math.min(x0,0))-1; x1=Math.ceil(Math.max(x1,0))+1; y0=Math.floor(Math.min(y0,0))-1; y1=Math.ceil(Math.max(y1,0))+1; }
  const W=320, PAD=grid?14:30, dx=Math.max(x1-x0,1e-6), dy=Math.max(y1-y0,1e-6), s=Math.min((W-2*PAD)/dx,(250-2*PAD)/dy);
  const H=Math.round(dy*s+2*PAD), ox=(W-dx*s)/2;
  const X=x=>ox+(x-x0)*s, Y=y=>H-PAD-(y-y0)*s, at=n=>[X(P[n].x),Y(P[n].y)];
  const f=v=>v.toFixed(1), unit=([x,y])=>{const l=Math.hypot(x,y)||1;return [x/l,y/l]};
  const named=Object.keys(P).filter(n=>!n.startsWith("_"));
  const pts=Object.keys(P), cx=pts.reduce((t,n)=>t+at(n)[0],0)/pts.length, cy=pts.reduce((t,n)=>t+at(n)[1],0)/pts.length;
  const txt=(x,y,words,cls="",anchor="")=>`<text${cls?` class="${cls}"`:""}${anchor?` text-anchor="${anchor}"`:""} x="${f(x)}" y="${f(y+5)}">${esc(words)}</text>`;
  // a label beside a point: one beside a side grows away from it, so a long label never covers the side
  const beside=(x,y,[nx,ny],gap,words,cls)=>Math.abs(nx)>0.8?txt(x+nx*(gap-6),y+ny*gap,words,cls,nx>0?"start":"end"):txt(x+nx*gap,y+ny*gap,words,cls);
  let back="", shapes="", marks="", words="";
  if(grid){
    for(let x=x0;x<=x1;x++){ back+=`<line class="g" x1="${f(X(x))}" x2="${f(X(x))}" y1="${f(Y(y0))}" y2="${f(Y(y1))}"/>`;
      if(x&&x>x0&&x<x1) words+=txt(X(x),Y(0)+8,String(x).replace("-","−"),"n"); }
    for(let y=y0;y<=y1;y++){ back+=`<line class="g" x1="${f(X(x0))}" x2="${f(X(x1))}" y1="${f(Y(y))}" y2="${f(Y(y))}"/>`;
      if(y&&y>y0&&y<y1) words+=txt(X(0)-8,Y(y),String(y).replace("-","−"),"n"); }
    back+=`<line class="ax" x1="${f(X(x0))}" x2="${f(X(x1))}" y1="${f(Y(0))}" y2="${f(Y(0))}"/><line class="ax" x1="${f(X(0))}" x2="${f(X(0))}" y1="${f(Y(y0))}" y2="${f(Y(y1))}"/>`;
  }
  const side=(a,b,flip)=>{const [ax,ay]=at(a),[bx,by]=at(b),u=unit([bx-ax,by-ay]),mx=(ax+bx)/2,my=(ay+by)/2;
    let n=[-u[1],u[0]]; if((n[0]*(mx-cx)+n[1]*(my-cy)<0)!==!!flip) n=[-n[0],-n[1]]; return {u,n,mx,my};};
  for(const [op,a] of ops){
    if(op==="poly") shapes+=`<path class="s" d="M${a.map(n=>at(n).map(f).join(",")).join("L")}Z"/>`;
    else if(op==="line"||op==="dash"){ const [p,q]=[at(a[0]),at(a[1])]; shapes+=`<line class="${op==="line"?"s":"d"}" x1="${f(p[0])}" y1="${f(p[1])}" x2="${f(q[0])}" y2="${f(q[1])}"/>`; }
    else if(op==="len"||op==="lenx"){ const {n,mx,my}=side(a[0],a[1],op==="lenx"); words+=beside(mx,my,n,14,a.slice(2).join(" "),"q"); }
    else if(/^ang[23]?$/.test(op)){
      const v=at(a[1]), u1=unit([at(a[0])[0]-v[0],at(a[0])[1]-v[1]]), u2=unit([at(a[2])[0]-v[0],at(a[2])[1]-v[1]]);
      let d=Math.atan2(u2[1],u2[0])-Math.atan2(u1[1],u1[0]); while(d>Math.PI)d-=2*Math.PI; while(d<=-Math.PI)d+=2*Math.PI;
      const arcs=+(op[3]||1), deg=Math.abs(d)*180/Math.PI;
      for(let i=0;i<arcs;i++){ const r=16+i*4; marks+=`<path class="m" d="M${f(v[0]+r*u1[0])},${f(v[1]+r*u1[1])}A${r},${r} 0 0 ${d>0?1:0} ${f(v[0]+r*u2[0])},${f(v[1]+r*u2[1])}"/>`; }
      const b=unit([u1[0]+u2[0],u1[1]+u2[1]]), r=16+(arcs-1)*4+13+Math.max(0,(45-deg)*0.45);
      if(a.length>3) words+=txt(v[0]+b[0]*r,v[1]+b[1]*r,a.slice(3).join(" "),"q");
    }
    else if(op==="right"){ const v=at(a[1]), u1=unit([at(a[0])[0]-v[0],at(a[0])[1]-v[1]]), u2=unit([at(a[2])[0]-v[0],at(a[2])[1]-v[1]]), k=10;
      marks+=`<path class="m" d="M${f(v[0]+k*u1[0])},${f(v[1]+k*u1[1])}L${f(v[0]+k*(u1[0]+u2[0]))},${f(v[1]+k*(u1[1]+u2[1]))}L${f(v[0]+k*u2[0])},${f(v[1]+k*u2[1])}"/>`; }
    else if(op==="tick"||op==="par"){ const {u,n,mx,my}=side(a[0],a[1]), k=+(a[2]||1);
      // arrows step aside from the equal-side marks of the same side
      const shift=op==="par"&&ops.some(([o,b])=>o==="tick"&&[b[0],b[1]].sort().join()===[a[0],a[1]].sort().join())?14:0;
      for(let i=0;i<k;i++){ const o=(i-(k-1)/2)*(op==="tick"?5:7)+shift, c=[mx+u[0]*o,my+u[1]*o];
        marks+=op==="tick"?`<path class="m" d="M${f(c[0]-n[0]*6)},${f(c[1]-n[1]*6)}L${f(c[0]+n[0]*6)},${f(c[1]+n[1]*6)}"/>`
          :`<path class="m" d="M${f(c[0]-u[0]*6-n[0]*5)},${f(c[1]-u[1]*6-n[1]*5)}L${f(c[0])},${f(c[1])}L${f(c[0]-u[0]*6+n[0]*5)},${f(c[1]-u[1]*6+n[1]*5)}"/>`; } }
    else if(op==="dot") a.forEach(n=>{const [x,y]=at(n);shapes+=`<circle cx="${f(x)}" cy="${f(y)}" r="3"/>`;});
  }
  const dirs={n:[0,-1],s:[0,1],e:[1,0],w:[-1,0],ne:[1,-1],nw:[-1,-1],se:[1,1],sw:[-1,1]};
  for(const n of named){ const [x,y]=at(n), d=unit(dirs[P[n].dir]||(Math.hypot(x-cx,y-cy)<1?[1,-1]:[x-cx,y-cy])); words+=txt(x+d[0]*14,y+d[1]*14,n,"v"); }
  notes.forEach(t=>{words+=txt(X(t.x),Y(t.y),t.words,"t");});
  return `<div class="mx-figure"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="שרטוט לשאלה">${back}${shapes}${marks}${words}</svg>${under}<small>השרטוט להמחשה ואינו בקנה מידה</small></div>`;
}

// a function's graph through the given points: monotone cubic (Fritsch-Carlson), so it never passes the marked extrema
function plot(g){
  const W=320, H=210, PAD=24, [x0,x1]=g.x, [y0,y1]=g.y;
  const sx=x=>PAD+(x-x0)/(x1-x0)*(W-2*PAD), sy=y=>H-PAD-(y-y0)/(y1-y0)*(H-2*PAD);
  const xs=g.points.map(p=>p[0]), ys=g.points.map(p=>p[1]), k=xs.length;
  const d=xs.slice(0,-1).map((x,i)=>(ys[i+1]-ys[i])/(xs[i+1]-x));
  const m=xs.map((_,i)=>i===0?d[0]:i===k-1?d[k-2]:d[i-1]*d[i]<=0?0:(d[i-1]+d[i])/2);
  d.forEach((di,i)=>{ if(di===0){ m[i]=m[i+1]=0; return; } const a=m[i]/di, b=m[i+1]/di, s=a*a+b*b;
    if(s>9){ const t=3/Math.sqrt(s); m[i]=t*a*di; m[i+1]=t*b*di; } });
  let line="";
  for(let i=0;i<k-1;i++){ const h=xs[i+1]-xs[i];
    for(let j=0;j<=20;j++){ const t=j/20, t2=t*t, t3=t2*t;
      const y=(2*t3-3*t2+1)*ys[i]+(t3-2*t2+t)*h*m[i]+(-2*t3+3*t2)*ys[i+1]+(t3-t2)*h*m[i+1];
      line+=`${line?"L":"M"}${sx(xs[i]+t*h).toFixed(1)},${sy(y).toFixed(1)}`; } }
  let grid="", ticks="";
  for(let x=Math.ceil(x0);x<=x1;x++){ grid+=`<line class="g" x1="${sx(x)}" x2="${sx(x)}" y1="${sy(y0)}" y2="${sy(y1)}"/>`;
    if(x) ticks+=`<text x="${sx(x)}" y="${Math.min(sy(0)+13,H-4)}" text-anchor="middle">${x}</text>`; }
  for(let y=Math.ceil(y0);y<=y1;y++){ grid+=`<line class="g" x1="${sx(x0)}" x2="${sx(x1)}" y1="${sy(y)}" y2="${sy(y)}"/>`;
    if(y) ticks+=`<text x="${Math.max(sx(0)-5,10)}" y="${sy(y)+4}" text-anchor="end">${y}</text>`; }
  const dots=g.points.map(([x,y])=>`<circle cx="${sx(x)}" cy="${sy(y)}" r="3.5"/>`).join("");
  return `<div class="mx-plot"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="גרף הפונקציה">${grid}
    <line class="a" x1="${sx(x0)}" x2="${sx(x1)}" y1="${sy(0)}" y2="${sy(0)}"/><line class="a" x1="${sx(0)}" x2="${sx(0)}" y1="${sy(y0)}" y2="${sy(y1)}"/>
    ${ticks}<path class="c" d="${line}"/>${dots}</svg></div>`;
}

async function boot(){
  const state=document.getElementById("bootState"), login=document.getElementById("loginBtn");
  if(AUTH_URL){
    if(!window.supabase){ state.className="error"; state.textContent="לא ניתן לטעון את שירות הכניסה."; return; }
    client=window.supabase.createClient(AUTH_URL,CFG.supabaseKey);
    client.auth.onAuthStateChange((event,session)=>{
      CFG.token=session?.access_token||"";
      if(event==="SIGNED_OUT"||(CFG.userId&&session?.user?.id&&session.user.id!==CFG.userId)){
        window.MathlyAnswers?.reset();closeSheet();hide();location.reload();
      }
    });
    const {data}=await client.auth.getSession(), session=data.session;
    if(!session){
      state.textContent="יש להיכנס כדי לפתוח את מסלול המתמטיקה."; login.hidden=false;
      login.onclick=()=>client.auth.signInWithOAuth({provider:"google",options:{redirectTo:location.origin+location.pathname}});
      return;
    }
    CFG.token=session.access_token;
    const meta=session.user?.user_metadata||{}; CFG.name=meta.given_name||String(meta.full_name||meta.name||"").trim().split(/\s+/)[0]||"";
    const response=await api("/api/me");
    if(!response.ok){ state.className="error"; state.textContent=response.status===403?"החשבון אינו משויך לכיתת מתמטיקה.":"לא ניתן להשלים את הכניסה."; return; }
    const me=await response.json();CFG.userId=me.user_id;CFG.answerScans=me.answer_scans; ME_EMAIL=me.email||""; MY_CLASSES=me.classes||[]; MY_CLASS=MY_CLASSES.length===1?MY_CLASSES[0]:null;
    CFG.permissions=me.permissions||[]; CFG.roles=me.roles||[]; CFG.aiDirect=me.ai_direct!==false; CFG.aiReview=!!me.ai_review;
  }
  document.getElementById("boot").hidden=true;
  show();
}
boot().catch(error=>{ const state=document.getElementById("bootState"); state.className="error"; state.textContent=`לא הצלחנו לפתוח את המסלול: ${error.message}`; });
})();
