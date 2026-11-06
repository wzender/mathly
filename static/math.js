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
let ME_EMAIL="", MY_CLASSES=[], MY_CLASS=null, client=null, PREVIEW=false;   // PREVIEW: a teacher looking at the app as a student
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
  each("done",earliest); each("gold",earliest); each("seen",latest); each("tries",most); each("wrongs",most); each("days",most);
  each("examples",(x,y)=>({n:most(x?.n,y?.n),last:latest(x?.last||"",y?.last||"")}));   // worked examples opened, per skill
  each("solved",(x,y)=>[...new Set([...(Array.isArray(x)?x:[]),...(Array.isArray(y)?y:[])])].sort((p,q)=>p-q));
  out.comets=[...new Set(list("comets"))];
  out.slips=joined("slips",s=>JSON.stringify([s?.at,s?.id,s?.q,s?.m])).sort((x,y)=>String(x?.at).localeCompare(String(y?.at))).slice(-500);
  if(old.quizzes||neu.quizzes) out.quizzes=joined("quizzes",q=>String(q?.at)).sort((x,y)=>String(x?.at).localeCompare(String(y?.at))).slice(-60);   // QUIZ_KEEP
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
  loadAssignments(); loadFinals();
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
      else if(e.target.matches?.("[data-focus-form]")){ e.preventDefault(); focusSave(e.target); }
      else if(e.target.matches?.("[data-ws-return]")){ e.preventDefault(); wsReturn(e.target); }
      else if(e.target.matches?.("[data-exam-form]")){ e.preventDefault(); examSave(e.target); }
      else if(e.target.matches?.("[data-exam-add]")){ e.preventDefault(); examAdd(e.target); }
      else if(e.target.matches?.("[data-final-open],[data-final-grant]")){ e.preventDefault(); finalForm(e.target); }
      else if(e.target.matches?.("[data-budget-form]")){ e.preventDefault(); const v=e.target.elements.limit.value; aqSetting(e.target.dataset.budgetForm,{ai_daily_checks:v===""?null:+v},e.target.closest("section").querySelector("[role=status]")); }
      else if(e.target.matches?.("[data-asg-form]")){ e.preventDefault(); asgSave(e.target); }
      else if(e.target.matches?.("[data-quiz-note]")){ e.preventDefault(); quizNoteSave(e.target); }
      else if(e.target.matches?.("[data-ws-check]")){ e.preventDefault(); wsCheck(e.target); }
    });
    root.addEventListener("change",e=>{ if(e.target.matches?.("[data-report-sort],[data-report-unit]")) reportControl(e.target); else if(e.target.matches?.("[data-ws-file]")) wsAddPhotos(e.target);
      else if(e.target.matches?.("[data-inbox-filter]")){ (REPORT.inboxFilter||={})[e.target.dataset.inboxFilter]=e.target.value; drawReport(); sheet.querySelector(`[data-inbox-filter="${e.target.dataset.inboxFilter}"]`)?.focus(); }
      else if(e.target.matches?.("[data-auto-send]")) aqSetting(e.target.dataset.autoSend,{auto_send_practice:e.target.checked},e.target.closest("section").querySelector("[role=status]")); });
    root.addEventListener("input",e=>{ if(WS&&e.target.matches?.("[data-ws-note]")) WS.note=e.target.value; });   // kept across redraws
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
  if(teachClasses().length) inboxCount();
  loadComments();
  loadAssignments(); loadFinals();
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
// the classes whose exams a screen shows: a student's own. A teacher sees no exam schedule at all (it is edited under ניהול)
const examClasses=()=>!PREVIEW&&(can("students.view")||teachClasses().length)?[]:MY_CLASS?[MY_CLASS]:MY_CLASSES;
const hasExams=()=>examClasses().some(row=>(row.exams||[]).some(exam=>exam?.subject&&exam?.date));
function subjectOptions(){
  const bySubject=new Map(PATH_SUBJECTS.map(name=>[name,{name,dates:[],classes:new Set()}]));
  examClasses().forEach(row=>(row.exams||[]).forEach(exam=>{
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
  path.innerHTML=`${previewBar()}<header class="mx-top"><div><h1>המקצועות שלי</h1><p class="mx-sub">בחרו מקצוע כדי לפתוח את המסלול שלו</p></div><div class="mx-acts">${window.MathlyGuide?.button()||""}${teachButton()}${manage?'<button class="mx-btn" data-act="manage">ניהול</button>':""}${window.MathlyAnswers?.pushButton?.()||""}${AUTH_URL?'<button class="mx-btn" data-act="out">יציאה</button>':""}</div></header>
    ${classesCard()}<section class="mx-subject-grid" aria-label="מקצועות הכיתה">${subjects.map(item=>subjectCard(item,today)).join("")}</section>`;
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
let VIEW="home";   // the tab shown: home (what has a date or needs action), path (self-paced learning), sky (the collection)
const SOUND_ON='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9h4l5-4v14l-5-4H3z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const SOUND_OFF='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 9h4l5-4v14l-5-4H3z"/><path d="M16 9l5 6M21 9l-5 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const TABS=[["home","בית",'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 11h2.7v9.5h5.3v-6h3v6h5.3V11h2.7Z"/></svg>'],
  ["path","מסלול",'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm12 12a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM7 11h2v2.5A2.5 2.5 0 0 0 11.5 16H14v2h-2.5A4.5 4.5 0 0 1 7 13.5Z"/></svg>'],
  ["grades","ציונים",'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V10h3.5v10H4Zm6.25 0V4h3.5v16h-3.5ZM16.5 20v-7H20v7h-3.5Z"/></svg>'],
  ["sky","האוסף",`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" opacity=".35"/><path d="${Sky.SPARK}" transform="translate(12.5 12.5) scale(.33)"/><path d="${Sky.SPARK}" transform="translate(3.5 3.5) scale(.33)"/></svg>`]];
// the names of tests, one place. A unit (lesson) has two quizzes: בוחן חיזוק (practice: retaken, its best grade
// shown, not the unit's grade) and בוחן מסכם (final: once, the unit's grade). Practice over several units is a
// מבחן תרגול; a מבחן is the school's exam on the class's exam table.
const TERMS={practice:"בוחן חיזוק",final:"בוחן מסכם",mixed:"מבחן תרגול",exam:"מבחן",unitQuizzes:"בחני היחידה"};
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
  const exams=examClasses().flatMap(row=>{ const subjects=classSubjects(row); return (row.exams||[]).filter(e=>e?.date&&subjects.includes(e.subject)); })
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
/* ---------- home ----------
   Only what has a date or needs the student: the next exam, the quizzes, work that is due and new teacher comments.
   It always ends with a button that continues the path, so it is never empty. */
function homeView(){
  if(teacherHome()) return `${topBar()}${classesCard()}`;
  const exam=examItem(), quizzes=quizCards(), due=tasksSummary()+assignmentsCard(), comments=commentsCard();
  const owed=CFG.userId&&(ASG||FIN)?myTasks().some(x=>!["handed","waiting","checked"].includes(x.state)):false;
  const empty=!exam&&!quizzes&&!owed&&!asgView()?.open.length&&!comments;
  const nxt=next();
  return `${previewBar()}${topBar()}<div class="mx-home">${exam}${examLessons()}${quizzes}${due}${comments}
    ${empty?'<p class="mx-note mx-home-empty" role="status">אין כרגע משהו להגיש או מבחן קרוב.</p>':""}
    <button type="button" class="mx-continue" data-view="path"><b>להמשיך במסלול</b><span>${nxt?`הבא בתור: ${fmt(BY[nxt].short||BY[nxt].name)}`:"כל הכוכבים פתוחים לתרגול"} ‹</span></button></div>`;
}
// the lessons (units) of the next exam: the ones still to finish stand out, and each opens on the path
function examLessons(){
  const exam=nextExam(); if(!exam) return "";
  const prep=prepExams().find(e=>e.date===exam.date&&e.subject===exam.subject); if(!prep) return "";
  const units=G.units.filter(u=>prep.units.includes(u.id)).map(u=>{ const ids=unitIds(u).filter(live), d=ids.filter(id=>P.done?.[id]).length;
    return {u,d,n:ids.length,full:ids.length>0&&d===ids.length}; });
  const left=units.filter(x=>!x.full);
  return `<section class="mx-home-lessons" aria-labelledby="mxLessons"><h3 id="mxLessons">${left.length?`להשלים לפני המבחן: ${left.length===1?"שיעור אחד":`${left.length} שיעורים`}`:"כל השיעורים של המבחן הושלמו ✓"}</h3>
    <ul>${[...left,...units.filter(x=>x.full)].map(({u,d,n,full})=>`<li class="${full?"done":"todo"}"><button type="button" class="u-${u.id}" data-view="path" data-unit="${esc(u.id)}">
      <b>${esc(u.name)}</b><span>${full?"✓ הושלם":`${d} מתוך ${n} מיומנויות`}</span><i class="mx-meter" aria-hidden="true"><i style="width:${n?Math.round(100*d/n):0}%"></i></i></button></li>`).join("")}</ul></section>`;
}
// the next exam on the class's exam table: subject, date and days left; it opens its preparation when it names units
function examItem(){
  const exam=nextExam(); if(!exam) return "";
  const prep=prepExams().find(e=>e.date===exam.date&&e.subject===exam.subject);
  const when=`${examDate(exam.date).toLocaleDateString("he-IL",{day:"numeric",month:"numeric"})} · ${exam.days?`עוד ${exam.days===1?"יום אחד":`${exam.days} ימים`}`:"היום"}`;
  return prep?`<button type="button" class="mx-examsoon mx-home-exam mx-prep-open" data-prep="${esc(prep.key)}"><b>מבחן ב${esc(exam.subject)} · ${when}</b><span>🎯 ${prepSummary(prep)} · הכנה ‹</span></button>`
    :`<div class="mx-examsoon mx-home-exam"><b>מבחן ב${esc(exam.subject)} · ${when}</b></div>`;
}
// a class's teacher (not in student preview) gets the classes, not a learning path
const teacherHome=()=>!PREVIEW&&teachClasses().length>0;
function pathView(){
  if(teacherHome()) return homeView();
  const nxt=next(), cls=MY_CLASS?` · כיתת ${esc(MY_CLASS.name)}`:"", teach=can("students.view")&&!PREVIEW, marks=asgMarks();
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
  return `${previewBar()}${topBar()}${daily()}${reviewCard()}${patternsCard()}<div class="mx-pghead"><h2>המסלול שלי</h2><p class="mx-sub">אלגברה וגאומטריה כיתה ט׳ · 5 יח״ל${cls}</p></div>
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
    ${examClasses().filter(row=>(row.exams||[]).length).map(row=>examBoard(row,true)).join("")}`;
}

function draw(){
  Sky.ensure(P);
  if(VIEW==="path"&&teacherHome()) VIEW="home";
  if(VIEW==="grades"&&(teacherHome()||!CFG.userId)) VIEW="home";   // grades: a signed-in student's
  path.innerHTML=VIEW==="sky"?collectionView():VIEW==="home"?homeView():VIEW==="grades"?gradesView():pathView();
  nav.hidden=false;
  const tabs=TABS.filter(([v])=>!(v==="path"&&teacherHome())&&!(v==="grades"&&(teacherHome()||!CFG.userId)));
  nav.innerHTML=`<div style="--tabs:${tabs.length}">${tabs.map(([v,label,icon])=>`<button data-view="${v}"${VIEW===v?' aria-current="page"':""}>${icon}<span>${label}</span></button>`).join("")}</div>`;
  decorateUnits();
}
function setView(view,unit){
  if(view==="grades") GRADES=null;   // the tab reads the server's grades again each time it is opened
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
  const rows=ASG.assignments.map(a=>({a,s:Sky.assignmentState(a,P,{sittings:ASG.sittings,submissions:ASG.submissions},now)}));
  return {open:rows.filter(x=>!x.s.finished).sort((p,q)=>p.a.due_on.localeCompare(q.a.due_on)),
    done:rows.filter(x=>x.s.finished&&x.a.due_on>=cutoff).sort((p,q)=>q.a.due_on.localeCompare(p.a.due_on))};
}
const asgDate=due=>new Date(due+"T12:00:00").toLocaleDateString("he-IL",{day:"numeric",month:"numeric"});
const asgUnit=id=>esc(G.units.find(u=>u.id===id)?.name||id);
function asgItemLabel(item){
  if(item.kind==="skill") return BY[item.id]?fmt(BY[item.id].name):esc(item.id);
  if(item.kind==="unit_quiz") return `${TERMS.practice}: ${asgUnit(item.unit)}`;
  if(item.kind==="worksheet") return `שיעורי בית: ${esc(wsTitle(item.id))}`;
  return `${TERMS.mixed}: ${(item.units||[]).map(asgUnit).join(", ")}`;
}
// the skills of unfinished assignments, with the titles, for the marker on the path
function asgMarks(){
  const marks=new Map();
  for(const {a} of asgView()?.open||[]) for(const item of a.items) if(item.kind==="skill") marks.set(item.id,[...(marks.get(item.id)||[]),a.title]);
  return marks;
}
// the time left to hand in, by Jerusalem's days; the last day counts the hours to midnight
function asgLeft(due,now=new Date()){
  const day=Sky.jerusalemDay(now), d=Math.round((Date.parse(due+"T00:00:00Z")-Date.parse(day+"T00:00:00Z"))/864e5);
  if(d<0) return {late:true,text:d===-1?"באיחור של יום":`באיחור של ${-d} ימים`};
  if(d===0){
    const hour=+new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Jerusalem",hour:"numeric",hourCycle:"h23"}).format(now), left=24-hour;
    return {late:false,soon:true,text:left<=1?"היום, נשארה פחות משעה":`היום, נשארו כ־${left} שעות`};
  }
  return {late:false,soon:d<=1,text:d===1?"מחר, נשאר יום אחד":d>60?"":`נשארו ${d} ימים`};   // far away: just the date
}
function assignmentsCard(){
  const v=asgView(); if(!v||(!v.open.length&&!v.done.length)) return "";
  const several=new Set(ASG.assignments.map(a=>a.class_id)).size>1, left=a=>asgLeft(a.due_on);
  const open=v.open.map(({a,s})=>`<article class="mx-asg${s.overdue?" late":""}">
      <div class="mx-asg-head"><b>${esc(a.title)}${a.personal?' <span class="mx-asg-personal">🎯 אישי</span>':""}</b><span class="mx-asg-due${left(a).soon?" soon":""}">${s.overdue?"באיחור · ":""}${left(a).text?`⏳ ${left(a).text} · `:""}עד ${asgDate(a.due_on)}</span></div>
      ${several?`<small class="mx-small">${esc(a.class_name)}</small>`:""}${a.note?`<p class="mx-asg-note">${esc(a.note)}</p>`:""}
      <p class="mx-asg-count"><b>${s.doneCount}</b> מתוך ${s.total} הושלמו</p>
      <ul class="mx-asg-items">${s.items.map(x=>`<li class="${x.done?"done":""}"><span aria-hidden="true">${x.done?"✓":"○"}</span> ${asgItemLabel(x.item)}${x.done?'<span class="mx-sr"> (הושלם)</span>':""}${x.known?"":" <small>(לא ניתן לבדוק כרגע)</small>"}${x.item.kind==="worksheet"?asgSheetHtml(x):""}</li>`).join("")}</ul>
      <button type="button" class="mx-btn solid" data-asg-go="${esc(a.id)}">${s.doneCount?"להמשיך":"להתחיל"}: ${asgItemLabel(s.items[s.next].item)}</button></article>`).join("");
  const done=v.done.length?`<details class="mx-asg-done"><summary>הושלמו (${v.done.length})</summary><ul>${v.done.map(({a,s})=>
    `<li>✓ ${esc(a.title)} <small>עד ${asgDate(a.due_on)}${s.late?" · הוגשה באיחור":""}</small>${s.items.filter(x=>x.item.kind==="worksheet").map(x=>`<div>${asgItemLabel(x.item)}${asgSheetHtml(x)}</div>`).join("")}</li>`).join("")}</ul></details>`:"";
  return `<section class="mx-asgs" aria-label="משימות מהמורה"><h2>משימות מהמורה</h2>${open}${done}</section>`;
}
// a worksheet item on the card: handed in or checked (with the teacher's score and comment), and the button that opens it
function asgSheetHtml(x){
  const sub=x.submission, checked=sub?.checked_at&&sub.state!=="returned";
  if(sub?.state==="returned") return ` <small class="mx-ws-badge back">↩ הוחזר לתיקון</small> <button type="button" class="mx-link" data-ws-open="${esc(x.item.id)}">תיקון והגשה מחדש</button>
    ${sub.return_comment?`<p class="mx-ws-comment"><b>המורה:</b> ${esc(sub.return_comment)}</p>`:""}`;
  const badge=checked?` <small class="mx-ws-badge checked">נבדק${sub.score!=null?` · ${sub.score}`:""}</small>`:x.done?' <small class="mx-ws-badge">הוגש</small>':"";
  return `${badge} <button type="button" class="mx-link" data-ws-open="${esc(x.item.id)}">${checked?"לצפייה":x.done?"פתיחה או החלפת ההגשה":"פתיחה והגשה"}</button>
    ${checked&&sub.comment?`<p class="mx-ws-comment"><b>המורה:</b> ${esc(sub.comment)}</p>`:""}`;
}
/* ---------- the student's task list (GET /api/math/my-tasks) ----------
   One list of what the student owes: open assignments (the class's and focus practice given to them), final quizzes
   open to them, and work the teacher returned for a fix. Each has one state (Sky.taskState), nearest due first. */
function myTasks(){
  const out=[], today=Sky.jerusalemDay(new Date()), server={sittings:ASG?.sittings,submissions:ASG?.submissions};
  for(const a of ASG?.assignments||[]){
    const t=Sky.assignmentTask(a,P,server);
    // done and nothing left to hear back about: off the list once its date has passed
    if(t.st.finished&&!["waiting","returned"].includes(t.state)&&a.due_on<today) continue;
    if(t.st.finished&&t.state==="checked") continue;
    const due=t.st.items.reduce((d,x)=>!x.done&&x.due>d?x.due:d,a.due_on);
    const back=t.st.items.find(x=>x.returned);
    out.push({key:`a:${a.id}`,title:a.title,kind:a.personal?"🎯 תרגול אישי":"משימה",due,state:t.state,label:t.label,
      sub:back?`↩ ${esc(back.submission.return_comment||"")}`:`${t.st.doneCount} מתוך ${t.st.total} הושלמו`,
      go:back?`data-ws-open="${esc(back.item.id)}"`:`data-asg-go="${esc(a.id)}"`});
  }
  for(const o of FIN?.offers||[]){
    const t=Sky.finalTask(o), unit=G.units.find(u=>u.id===o.window.unit_id);
    out.push({key:`f:${o.window.id}:${o.grant?.id||""}`,title:`${TERMS.final}: ${unit?.name||o.window.unit_id}`,kind:`📌 ${TERMS.final}`,
      due:Sky.jerusalemDay(Date.parse(o.until)),state:t.state,label:t.label,sub:`פתוח עד ${new Date(Date.parse(o.until)).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"})}`,
      go:`data-uquiz="${esc(o.window.unit_id)}"`});
  }
  return out.sort((p,q)=>(p.due||"9999").localeCompare(q.due||"9999"));
}
function tasksSummary(){
  if(!CFG.userId||!MY_CLASSES.length) return "";
  const grades="";   // the grades have their own tab
  if(!ASG&&!FIN) return grades;
  const list=myTasks(), open=list.filter(x=>!["handed","waiting","checked"].includes(x.state)), next=open[0];
  return `<button type="button" class="mx-tasks-sum${open.length?"":" quiet"}" data-act="tasks"><b>📋 המשימות שלי</b>
    <span>${open.length?`${open.length===1?"משימה אחת פתוחה":`${open.length} משימות פתוחות`} · הקרובה: ${esc(next.title)} עד ${asgDate(next.due)}`:list.length?"הכול הוגש · אפשר לראות מה מצב הבדיקה":"אין משימות פתוחות"}</span></button>${grades}`;
}
let TASKS=null;
async function openTasks(){
  if(!cur) back=document.activeElement;
  closeSheetQuietly(); cur="tasks"; TASKS={loading:true};
  drawTasks();
  try{
    const r=await api("/api/math/my-tasks",{cache:"no-store"}); const d=r.ok?await r.json():null;
    if(cur!=="tasks") return;
    if(d){ if(d.assignments) ASG=d.assignments; if(d.finals){ FIN={...(FIN||{skew:0}),offers:d.finals}; } }
    TASKS={error:!d};
  }catch{ if(cur==="tasks") TASKS={error:true}; }
  if(cur==="tasks") drawTasks();
}
function drawTasks(){
  const list=TASKS?.loading?null:myTasks();
  const rows=list?.map(x=>`<li class="mx-task" data-task="${x.state}"><div><b>${esc(x.title)}</b> <small>${x.kind}</small>
      <p class="mx-small">${x.sub}${x.due?` · ${(asgLeft(x.due).text||`עד ${asgDate(x.due)}`)}`:""}</p></div>
      <span class="mx-task-chip" data-task="${x.state}">${x.label}</span><button type="button" class="mx-btn" ${x.go}>פתיחה</button></li>`).join("");
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-tasks-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><h3 id="mxTitle">המשימות שלי</h3><small class="mx-src">מה שצריך להגיש, לפי התאריך הקרוב · <button type="button" class="mx-link" data-act="grades">הציונים שלי</button></small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${(p=>p?`<p><button type="button" class="mx-btn" data-prep="${esc(p.key)}">🎯 הכנה למבחן ב${esc(p.subject)} ${inDays(p.days)}</button></p>`:"")(prepExams()[0])}
      ${!list?'<p class="mx-small" role="status">טוענים…</p>'
        :rows?`<ul class="mx-tasks">${rows}</ul>${TASKS?.error?'<p class="mx-small">חלק מהמשימות לא נטענו עכשיו.</p>':""}`
        :`<p class="mx-note" role="status">אין מה להגיש עכשיו. 🎉</p><div class="mx-row"><button type="button" class="mx-btn solid" data-act="close">למסלול</button><button type="button" class="mx-btn" data-act="grades">לציונים שלי</button></div>`}</div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}

/* ---------- the student's grades (GET /api/math/my-grades) ----------
   Every grade the server holds, by unit: the official grade of the final quiz (once the teacher released it),
   practice quizzes (best and latest, not counting), and checked worksheets; what still waits for a check; and the
   teacher's comments not opened yet, first. Each grade opens its result. */
let GRADES=null;
// the grades tab (and every link to the grades) shows the page; it loads when it has nothing
function openGrades(){ closeSheet(); setView("grades"); }
async function loadGrades(){
  GRADES={loading:true};
  try{ const r=await api("/api/math/my-grades",{cache:"no-store"}); GRADES=r.ok?await r.json():{error:true}; }catch{ GRADES={error:true}; }
  if(VIEW==="grades"&&ACTIVE_SUBJECT==="מתמטיקה"&&root&&!root.hidden) draw();
}
function gradesView(){
  if(!GRADES) loadGrades();
  return `${previewBar()}${topBar()}<div class="mx-pghead"><h1>הציונים שלי</h1><p class="mx-sub">כל הציונים כאן מהשרת · <button type="button" class="mx-link" data-act="tasks">המשימות שלי</button></p></div>
    <div class="mx-grades-page">${gradesBody(GRADES||{loading:true})}</div>`;
}
const gradeOpen=v=>v.open===1?"ממתין לבדיקה · שאלה אחת":`ממתין לבדיקה · ${v.open} שאלות`;
const gradeDay=t=>{ const d=new Date(t); return isNaN(d)?"":d.toLocaleDateString("he-IL",{day:"numeric",month:"numeric"}); };
/* The grades as one list: what is still to hand in first (nearest date first), then everything handed in, newest
   first. Each row: when, what, the result, and what can be done now (hand in, hand in again, open). */
function gradeRows(g){
  const rows=[], unit=id=>G.units.find(u=>u.id===id)?.name||id;
  for(const o of FIN?.offers||[]) if(!o.start?.sitting_id)
    rows.push({todo:true,at:o.until,kind:TERMS.final,what:unit(o.window.unit_id),result:o.start?"בתהליך":"פתוח להגשה",
      act:`<button type="button" class="mx-btn solid" data-uquiz="${esc(o.window.unit_id)}">${o.start?"להמשיך":"הגשה"}</button>`});
  const handed=new Set((g.worksheets||[]).map(w=>w.worksheet_id));
  for(const a of ASG?.assignments||[]) for(const item of a.items) if(item.kind==="worksheet"&&!handed.has(item.id)&&!(ASG.submissions||[]).some(x=>x.worksheet_id===item.id))
    rows.push({todo:true,at:a.due_on+"T12:00:00",kind:"שיעורי בית",what:wsTitle(item.id),result:`עד ${asgDate(a.due_on)}`,
      act:`<button type="button" class="mx-btn solid" data-ws-open="${esc(item.id)}">הגשה</button>`});
  for(const u of g.units||[]) for(const v of u.sittings||[]){
    const final=v.mode==="final", mark=final&&v.id===u.official?.id?' <span class="mx-glist-mark" title="הציון של היחידה">★ ציון היחידה</span>':!final&&v.id===u.practice_best?.id&&v.grade!=null?' <span class="mx-glist-mark" title="הציון הכי טוב">הכי טוב</span>':"";
    const result=final&&v.released===false?"ממתין לפרסום":v.grade==null?gradeOpen(v):`<b>${v.grade}</b>/100`;
    const note=(g.comments||[]).some(c=>v.attempts?.includes(c.attempt_id))?' <span title="הערה חדשה מהמורה">💬</span>':"";
    rows.push({at:v.submitted_at,kind:final?TERMS.final:TERMS.practice,what:u.name,
      result:`<button type="button" class="mx-link" data-grade-sitting="${esc(v.unit_id)}:${esc(v.id)}">${result}</button>${mark}${note}`,
      act:final?"":`<button type="button" class="mx-btn" data-uquiz="${esc(v.unit_id)}">הגשה מחדש</button>`});
  }
  for(const w of g.worksheets||[]){
    const back=w.state==="returned";
    rows.push({at:w.submitted_at||w.checked_at||"",kind:"שיעורי בית",what:w.title||w.assignment,
      result:back?"↩ הוחזר לתיקון":w.checked_at?`<b>${w.score??"נבדק"}</b>${w.score!=null?"/100":""}${w.comment?' <span title="הערה מהמורה">💬</span>':""}`:"ממתין לבדיקה",
      act:`<button type="button" class="mx-btn${back?" solid":""}" data-ws-open="${esc(w.worksheet_id)}">${back?"הגשה מחדש":w.checked_at?"צפייה":"החלפת ההגשה"}</button>`});
  }
  const todo=rows.filter(r=>r.todo).sort((a,b)=>String(a.at).localeCompare(String(b.at)));
  return [...todo,...rows.filter(r=>!r.todo).sort((a,b)=>(!a.at-!b.at)||String(b.at||"").localeCompare(String(a.at||"")))];   // no date: last
}
function gradesBody(g){
  if(g?.loading) return '<p class="mx-small" role="status">טוענים…</p>';
  if(g?.error) return '<p class="mx-note" role="status">לא הצלחנו לטעון את הציונים. נסו שוב מאוחר יותר.</p>';
  const rows=gradeRows(g), official=(g.units||[]).filter(u=>u.official&&u.official.released!==false&&u.official.grade!=null);
  const comments=g.comments||[];
  return `${official.length?`<p class="mx-glist-units"><b>ציוני היחידות:</b> ${official.map(u=>`${esc(u.name)} <b>${u.official.grade}</b>`).join(" · ")}</p>`:""}
    ${comments.length?`<p class="mx-glist-new">💬 <b>${comments.length===1?"הערה חדשה מהמורה":`${comments.length} הערות חדשות מהמורה`}:</b> ${comments.map(c=>`<button type="button" class="mx-link" data-comment="${esc(c.attempt_id)}">${fmt(c.question||"תשובה")}</button>`).join(" · ")}</p>`:""}
    ${rows.length?`<ul class="mx-glist">${rows.map(r=>`<li class="mx-glist-row${r.todo?" todo":""}"><time>${esc(gradeDay(r.at))}</time>
      <span class="mx-glist-what"><small>${esc(r.kind)}</small>${esc(r.what)}</span><span class="mx-glist-res">${r.result}</span>${r.act}</li>`).join("")}</ul>`
      :'<p class="mx-note">עוד אין ציונים. כשתגישו בוחן או שיעורי בית, הם יופיעו כאן.</p>'}
    ${g.quizzes_known===false?'<p class="mx-small">חלק מהבחנים לא נטענו עכשיו.</p>':""}
    ${g.worksheets===null?'<p class="mx-small">שיעורי הבית לא נטענו עכשיו.</p>':""}`;
}
// a sitting from the grades page opens its result screen; one from another device joins this device's list first
function gradeSitting(key){
  const [uid,sid]=key.split(":"), v=(GRADES?.units||[]).flatMap(u=>u.sittings).find(x=>x.id===sid); if(!v) return;
  const st=uqState(uid); let h=st.history.findIndex(x=>x.sid===sid);
  if(h<0){ st.history.push({at:v.submitted_at,attempts:v.attempts.slice(),score:null,timeUp:v.time_up,ck:crypto.randomUUID(),sid,mode:v.mode});
    st.history.sort((p,q)=>String(p.at).localeCompare(String(q.at))); st.history=st.history.slice(-10); h=st.history.findIndex(x=>x.sid===sid); save(); }
  if(h<0) return;
  cur=null; uqResult(uid,h);
}

/* ---------- preparing for an exam (the class's exam board, with the units each exam covers) ----------
   For each upcoming exam that names units: the days left, the units, the teacher's note, how ready the student is
   (each skill's state, the mistakes that keep coming back in those units, the latest quiz grades), and a plan of
   steps. The plan is fixed when the student first opens it (P.prep[key]) and each step is checked off from progress
   made after that. */
function prepExams(){
  const today=new Date(); today.setHours(0,0,0,0);
  return examClasses().flatMap(row=>(row.exams||[]).filter(e=>e?.date&&Array.isArray(e.units)&&e.units.length&&examDate(e.date)>=today)
    .map(e=>({...e,classId:row.id,key:`${row.id}|${e.subject}|${e.date}`,days:Math.round((examDate(e.date)-today)/86400000),
      units:e.units.filter(id=>G.units.some(u=>u.id===id))})))
    .filter(e=>e.units.length).sort((a,b)=>a.date.localeCompare(b.date));
}
const prepSkills=e=>G.units.filter(u=>e.units.includes(u.id)).flatMap(u=>unitIds(u).filter(live));
function prepSummary(e){ const ids=prepSkills(e); return `${ids.filter(id=>P.done?.[id]).length} מתוך ${ids.length} מיומנויות`; }
function prepRecurring(e){
  const ids=new Set(prepSkills(e));
  return Sky.patterns(P,G.mistakes).recurring.filter(x=>G.mistakes[x.m]&&(x.skills||[]).some(id=>ids.has(id)));
}
// the plan's steps, in order: not finished, fading, to strengthen, the units' quizzes, then the three quizzes before the exam
function prepSteps(e){
  const ids=prepSkills(e), steps=[], seen=new Set();
  for(const id of ids) if(["new","practising"].includes(skillState(id))){ steps.push({k:"skill",id}); seen.add(id); }
  for(const id of ids) if(skillState(id)==="fading"){ steps.push({k:"review",id}); seen.add(id); }
  for(const x of prepRecurring(e)) if(BY[x.practise]&&!seen.has(x.practise)){ steps.push({k:"strengthen",id:x.practise}); seen.add(x.practise); }
  for(const u of G.units.filter(u=>e.units.includes(u.id)&&u.quiz)) steps.push({k:"uquiz",unit:u.id});
  for(const h of HQ) steps.push({k:"quiz",kind:h.kind});
  return steps;
}
function prepPlan(e){
  const prep=(P.prep||={}), mine=prep[e.key];
  if(mine?.steps?.some(x=>x.k==="exam")){   // a plan from before the three quizzes: its practice exam becomes them
    mine.steps=mine.steps.flatMap(x=>x.k==="exam"?HQ.map(h=>({k:"quiz",kind:h.kind})):[x]); save();
  }
  if(mine?.steps) return mine;
  prep[e.key]={opened:new Date().toISOString(),steps:prepSteps(e)}; save();
  return prep[e.key];
}
function prepDone(step,e,since){
  if(step.k==="skill") return !!P.done?.[step.id];
  if(step.k==="review") return String(P.seen?.[step.id]||"")>since&&!Sky.fading(P,step.id);
  if(step.k==="strengthen") return String(P.seen?.[step.id]||"")>since;
  if(step.k==="uquiz") return uqState(step.unit).history.some(h=>String(h.at)>since&&h.mode!=="final");
  if(step.k==="quiz") return (P.quizzes||[]).some(q=>q.kind===step.kind&&q.exam===e.key&&String(q.at)>since);
  return (P.quizzes||[]).some(q=>String(q.at)>since&&e.units.every(u=>(q.units||[]).includes(u)));
}
function prepStepHtml(step,e,done,today){
  const unit=id=>G.units.find(u=>u.id===id);
  const [label,go]=step.k==="skill"?[`ללמוד ולסיים: ${fmt(BY[step.id].short||BY[step.id].name)}`,`data-id="${esc(step.id)}"`]
    :step.k==="review"?[`לחזור על מיומנות שדועכת: ${fmt(BY[step.id].short||BY[step.id].name)}`,`data-id="${esc(step.id)}"`]
    :step.k==="strengthen"?[`לחזק (טעות שחוזרת): ${fmt(BY[step.id].short||BY[step.id].name)}`,`data-id="${esc(step.id)}"`]
    :step.k==="uquiz"?[`${TERMS.practice}: ${esc(unit(step.unit)?.name||step.unit)}`,`data-uquiz="${esc(step.unit)}"`]
    :step.k==="quiz"?[esc(HQ.find(h=>h.kind===step.kind)?.title||""),`data-hq="${esc(step.kind)}" data-hq-exam="${esc(e.key)}"`]
    :[`${TERMS.mixed} על החומר`,`data-prep-exam="${esc(e.key)}"`];
  return `<li class="mx-prep-step${done?" done":""}${today?" today":""}"><span aria-hidden="true">${done?"✓":"○"}</span>
    <span>${label}${done?'<span class="mx-sr"> (בוצע)</span>':""}${today&&!done?' <small class="mx-prep-today">היום</small>':""}</span>
    <button type="button" class="mx-btn" ${go}>${done?"שוב":"לעשות"}</button></li>`;
}
let PREP=null;
async function openPrep(key){
  const e=prepExams().find(x=>x.key===key); if(!e) return;
  if(!cur) back=document.activeElement;
  closeSheetQuietly(); cur="prep"; PREP={key,grades:null};
  prepPlan(e); drawPrep();
  try{ const r=await api("/api/math/my-grades",{cache:"no-store"}); if(cur==="prep"&&PREP?.key===key&&r.ok){ PREP.grades=await r.json(); drawPrep(); } }catch{}
}
function drawPrep(){
  const e=prepExams().find(x=>x.key===PREP?.key); if(!e) return;
  const ids=prepSkills(e), states=ids.map(id=>({id,st:skillState(id)})), finished=states.filter(x=>["gold","lit","fading"].includes(x.st)).length;
  const fadingN=states.filter(x=>x.st==="fading").length, plan=prepPlan(e);
  const steps=plan.steps.filter(x=>["exam","uquiz","quiz"].includes(x.k)?true:BY[x.id]), done=steps.map(x=>prepDone(x,e,plan.opened));
  const left=done.filter(d=>!d).length, perDay=e.days>=2&&left?Math.ceil(left/e.days):0;
  const todayIdx=new Set(); if(perDay){ for(let i=0,n=0;i<steps.length&&n<perDay;i++) if(!done[i]){ todayIdx.add(i); n++; } }
  const order=perDay?[...steps.keys()].sort((a,b)=>(todayIdx.has(b)-todayIdx.has(a))||a-b):[...steps.keys()];
  const units=G.units.filter(u=>e.units.includes(u.id)), recurring=prepRecurring(e);
  const grade=uid=>{ const u=(PREP.grades?.units||[]).find(x=>x.unit_id===uid); if(!u) return "";
    const f=u.official, p=u.practice_best||u.practice_latest;
    return `<small>${TERMS.final}: ${f?(f.released===false?"ממתין לפרסום":f.grade==null?"ממתין לבדיקה":`${f.grade}/100`):"–"} · ${TERMS.practice}, הכי טוב: ${p?(p.grade==null?"ממתין לבדיקה":`${p.grade}/100`):"–"}</small>`; };
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-prep-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${e.days===0?"היום":e.days===1?"מחר":`עוד ${e.days} ימים`}</span><h3 id="mxTitle">הכנה למבחן ב${esc(e.subject)}</h3>
        <small class="mx-src">${esc(examFullDate(e.date))}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p><b>חומר למבחן:</b> ${units.map(u=>esc(u.name)).join(", ")}${e.note?`<br><small>${esc(e.note)}</small>`:""}</p>
      <section class="mx-prep-ready"><h4>כמה אני מוכן/ה</h4><p class="mx-prep-sum"><b>${finished} מתוך ${ids.length}</b> מיומנויות הושלמו${fadingN?` · ${fadingN} דועכות`:""}</p>
        ${units.map(u=>`<div class="mx-prep-unit"><b>${esc(u.name)}</b> ${grade(u.id)}<ul class="mx-prep-skills">${unitIds(u).filter(live).map(id=>{ const st=skillState(id);
          return `<li data-state="${st}"><button type="button" class="mx-chip u-${u.id}" data-id="${esc(id)}">${fmt(BY[id].short||BY[id].name)}</button> <small>${SKILL_STATE[st]}</small></li>`; }).join("")}</ul></div>`).join("")}
        ${recurring.length?`<h5>טעויות שחוזרות בחומר</h5><ul class="mx-prep-mistakes">${recurring.map(x=>`<li><b>${fmt(G.mistakes[x.m].name)}</b>${G.mistakes[x.m].tip?`: ${fmt(G.mistakes[x.m].tip)}`:""}${BY[x.practise]?` <button type="button" class="mx-link" data-id="${esc(x.practise)}">לחזק: ${fmt(BY[x.practise].short||BY[x.practise].name)}</button>`:""}</li>`).join("")}</ul>`:""}</section>
      <section class="mx-prep-plan"><h4>תוכנית הכנה</h4>
        <p class="mx-small">${left?(perDay?`<b>${perDay} צעדים ביום</b> עד המבחן. הצעדים של היום למעלה.`:`נשארו ${left} צעדים.`):"כל הצעדים בוצעו. בהצלחה! 🎉"}</p>
        <ol class="mx-prep-steps">${order.map(i=>prepStepHtml(steps[i],e,done[i],todayIdx.has(i))).join("")}</ol></section></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}

// opens the first item of the assignment that is not done
function asgGo(id){
  const a=ASG?.assignments.find(x=>x.id===id); if(!a) return;
  const s=Sky.assignmentState(a,P,{sittings:ASG.sittings,submissions:ASG.submissions}), item=s.items[s.next]?.item; if(!item) return;
  if(item.kind==="skill") return BY[item.id]&&open(item.id);
  if(item.kind==="worksheet") return wsOpen(item.id);
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
function closeSheet(){ stopPhone(); dropResources(); dropWorksheet(); dropQueue(); dropReview(); cancelAdvance(); REV=null; stopQuizClock(); QZ=null; stopUnitQuiz(); if(sheet)sheet.hidden=true; cur=null; back?.focus?.({preventScroll:true}); back=null; }

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
      <div class="mx-shtop"><div><span class="mx-uchip">${TERMS.mixed}</span><h3 id="mxTitle">${exam?`לקראת המבחן ב${esc(exam.subject)} ${inDays(exam.days)}`:TERMS.mixed}</h3>
        <small class="mx-src">${QUIZ_SIZE} שאלות · זמן מומלץ: כ־${Math.round(QUIZ_SIZE*QUIZ_MIN_PER_Q/5)*5} דקות, בלי לחץ: השעון רק מראה.</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p>${Array.isArray(preset)?`המורה ביקש ${TERMS.mixed} על היחידות המסומנות. כדי שהמשימה תיחשב, השאירו את כולן מסומנות.`:`אילו יחידות במבחן? סימנו את מה שנלמד עד ${exam?"המבחן":"עכשיו"}. אפשר לשנות.`}</p>
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
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(QZ.title||TERMS.mixed)}</span><h3 id="mxTitle">שאלה ${i+1} מתוך ${items.length}</h3>
        <small class="mx-src">⏱ <span class="mx-quiz-clock">${mmss(Date.now()-QZ.started)}</span></small></div>
        <div class="mx-shacts">${window.MathlyBoard?.button()||""}<button class="mx-x" data-act="quiz-quit" aria-label="יציאה מהמבחן">✕</button></div></div>
      <div class="mx-quiz-dots">${items.map((x,k)=>`<button data-quiz-go="${k}" class="${x.pick!=null?"done":""}${k===i?" now":""}" aria-label="שאלה ${k+1}${x.pick!=null?", נענתה":""}">${k+1}</button>`).join("")}</div>
      <div class="mx-q"><p>${fmt(q.question)}</p>${figures(q)}
        <div class="mx-choices">${it.order.map(k=>{ const c=q.choices[k]; return `<button data-choice="${k}" data-m="${c.correct?"":esc(c.mistake)}"${c.correct?" data-right":""} aria-pressed="${it.pick===k}">${fmt(c.text)}</button>`; }).join("")}</div>
        ${QZ.conf?quizSureHtml(it):""}<div class="mx-quiz-fb" aria-live="polite"></div></div>
      <div class="mx-quiz-nav"><button class="mx-btn" data-act="quiz-prev"${i?"":" disabled"}>הקודמת</button>
        ${last?`<button class="mx-btn solid" data-act="quiz-submit">הגשה</button>`:`<button class="mx-btn solid" data-act="quiz-next">הבאה</button>`}</div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  if(QZ.feedback&&it.pick!=null) quizFeedback(it,q);   // coming back to an answered question: its feedback again
  window.MathlyBoard?.mount(sheet,`quiz:${QZ.started}:${i}`,{question:()=>sheet.querySelector(".mx-q")});   // a sketch per exam question
}
// a choice is only marked; it can be changed until the exam is handed in
function quizPick(btn){
  if(!QZ?.items) return;
  if(QZ.feedback){   // a strengthening quiz: the first pick is the answer, and the feedback comes right away
    const it=QZ.items[QZ.i]; if(it.pick!=null) return;
    it.pick=+btn.dataset.choice; sheet.querySelector(`[data-quiz-go="${QZ.i}"]`).classList.add("done");
    const ok=btn.dataset.right!=null; ok?Sky.sound.ok():Sky.sound.tap?.();
    return quizFeedback(it,QS(BY[it.id])[it.qi]);
  }
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
    if(r.pick!=null){ (P.tries||={})[r.id]=(P.tries[r.id]||0)+1; if(!r.ok) (P.wrongs||={})[r.id]=(P.wrongs[r.id]||0)+1; }   // like practice, for the chance of a right answer
  }
  const mistakes={}; res.filter(r=>r.mistake).forEach(r=>{ (mistakes[r.mistake]??={n:0,ids:new Set()}).n++; mistakes[r.mistake].ids.add(r.id); });
  const skipped=res.filter(r=>r.pick==null).map(r=>r.id);
  const top=Object.entries(mistakes).sort((a,b)=>b[1].n-a[1].n).slice(0,3);
  const weak=[...new Set([...top.flatMap(([,m])=>[...m.ids]),...skipped])];
  const def=QZ.def||null, title=QZ.title||TERMS.mixed, before=def?quizAttempts(def):[];
  const entry={at:now,n:items.length,right,ms,units:QZ.units,weak};
  if(def) Object.assign(entry,{kind:def.kind,exam:def.exam,qs:items.map(x=>`${x.id}:${x.qi}`)});
  if(QZ.conf) entry.sure=items.map(x=>x.sure??null);
  (P.quizzes=P.quizzes||[]).push(entry); P.quizzes=P.quizzes.slice(-QUIZ_KEEP);
  save(); draw();
  const perUnit=QZ.units.map(uid=>{ const u=G.units.find(x=>x.id===uid), rs=res.filter(r=>BY[r.id].unit===uid); return {u,n:rs.length,ok:rs.filter(r=>r.ok).length}; }).filter(x=>x.n);
  const plan=top.length?top.map(([k,m])=>{ const M=G.mistakes[k]; return `<li><b>${fmt(M.name)}</b>${m.n>1?` <small>(${m.n} פעמים)</small>`:""}<span>${fmt(M.tip)}</span>
      <span class="mx-chips">${[...m.ids].map(id=>`<button class="mx-btn" data-id="${id}">לתרגל: ${fmt(BY[id].short)}</button>`).join("")}</span></li>`; }).join(""):"";
  QZ={done:true};
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-quiz-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(title)}</span><h3 id="mxTitle">${right} מתוך ${items.length} נכונות</h3>
        <small class="mx-src">⏱ ${mmss(ms)}${skipped.length?` · ${skipped.length} בלי תשובה`:""}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${def?quizCompareHtml(right,items.length,before):""}
      <div class="mx-quiz-units-score">${perUnit.map(x=>`<div><span>${esc(x.u.name)}</span><b>${x.ok}/${x.n}</b><span class="mx-meter" aria-hidden="true"><i style="width:${Math.round(100*x.ok/x.n)}%"></i></span></div>`).join("")}</div>
      ${plan?`<h4>${top.length===1?"דבר אחד":top.length===2?"שני דברים":"שלושה דברים"} לחזק עד המבחן</h4><ol class="mx-quiz-plan">${plan}</ol>
        <p class="mx-small">מיומנויות שכבר סיימתם וטעיתם בהן חוזרות היום לחזרה המעורבת.</p>`
        :right===items.length?"<p>הכול נכון. ממשיכים לתרגל קצת כל יום, וזה יישאר.</p>":""}
      ${entry.sure?quizSureWrongHtml(res,entry.sure):""}
      ${def?.kind==="exam"?`<form class="mx-quiz-note" data-quiz-note="${esc(now)}"><label>משפט אחד: מה אעשה אחרת במבחן? <small>(לא חובה)</small>
        <input type="text" name="note" maxlength="${QUIZ_NOTE_MAX}" autocomplete="off"></label><button type="submit" class="mx-btn">שמירה</button><span class="mx-small" role="status"></span></form>`:""}
      <details class="mx-quiz-review"><summary>כל השאלות והתשובות</summary><ol>${res.map(r=>{ const c=r.q.choices.find(c=>c.correct), mine=r.pick==null?null:r.q.choices[r.pick];
        return `<li class="${r.ok?"ok":"bad"}"><span>${fmt(r.q.question)}</span><small>${esc(plain(BY[r.id].short))}</small>
          ${r.ok?`<span>✓ ${fmt(c.text)}</span>`:`<span>${mine?`ענית: ${fmt(mine.text)}`:"בלי תשובה"} · נכון: ${fmt(c.text)}</span>`}</li>`; }).join("")}</ol></details>
      <div class="mx-quiz-nav">${def?`<button class="mx-btn" data-hq="${esc(def.kind)}"${def.exam?` data-hq-exam="${esc(def.exam)}"`:""}>ניסיון נוסף, עם שאלות חדשות</button>`:`<button class="mx-btn" data-act="quiz">${TERMS.mixed} חדש</button>`}<button class="mx-btn solid" data-act="close">סגירה</button></div></div>`;
  sheet.querySelector(".mx-x").focus({preventScroll:true});
  if(right/items.length>=.8) Sky.sound.goal();
}
function quizQuit(){
  if(!QZ?.items) return closeSheet();
  if(QZ.items.every(x=>x.pick==null)||QZ.quitting) return closeSheet();
  QZ.quitting=true;
  sheet.querySelector(".mx-quiz-nav").insertAdjacentHTML("beforebegin",'<p class="mx-small mx-quiz-warn">לצאת? התשובות במבחן הזה לא יישמרו. לחצו שוב על ✕ כדי לצאת.</p>');
}

/* ---------- quizzes chosen for each student (openspec student-home-and-exam-quizzes) ----------
   Before an exam that names units (7 days or less): two strengthening quizzes, aiming at an expected score of about
   70% and 80% (Sky.pickQuiz), with feedback after each answer and the worked example after a wrong one, and a quiz like
   the exam: its units only, mixed, topic names hidden, feedback at the end. Without such an exam: the two strengthening
   quizzes over the units taught so far. Each can be retaken with new questions; the best grade counts. Attempts are kept
   in P.quizzes with their kind, exam and questions. */
const QUIZ_KEEP=60, QUIZ_MIN=6, QUIZ_NOTE_MAX=140;
const HQ=[
  {kind:"s1",title:"מבחן תרגול 1",target:.7,band:[4,7],say:"בעיקר נושאים שכמעט סגרתם, עם משוב אחרי כל שאלה."},
  {kind:"s2",title:"מבחן תרגול 2",target:.8,band:[3,5],say:"יותר נושאים שכבר יודעים, עם משוב אחרי כל שאלה."},
  {kind:"exam",title:"מבחן תרגול כמו במבחן",target:.75,band:[2,3],say:"מכל החומר, מעורבב ובלי שמות נושאים. המשוב בסוף."}];
function homeQuizzes(){
  if(teacherHome()) return [];
  const e=prepExams()[0];
  if(e&&e.days<=7) return quizzesFor(e);
  const units=[...quizUnits().on];
  return units.length?HQ.filter(h=>h.kind!=="exam").map(h=>({...h,exam:null,units,days:null})):[];
}
const quizzesFor=e=>HQ.map(h=>({...h,exam:e.key,units:e.units,days:e.days}));
const quizAttempts=def=>(P.quizzes||[]).filter(q=>q.kind===def.kind&&(q.exam||null)===(def.exam||null));
// the skills of the units with their multiple-choice questions; rank: taught later is higher
const quizPool=units=>units.flatMap(uid=>{ const u=G.units.find(x=>x.id===uid); return u?unitIds(u):[]; })
  .filter(id=>live(id)&&choiceSkill(id))
  .map(id=>({id,unit:BY[id].unit,rank:skillMonth(id)*1000+ORDER.indexOf(id),qs:QS(BY[id]).map((q,i)=>q.choices?i:-1).filter(i=>i>=0)}));
function buildQuiz(def){
  const pool=quizPool(def.units), seen={};
  for(const a of quizAttempts(def)) for(const k of a.qs||[]) if(!(String(seen[k]||"")>a.at)) seen[k]=a.at;
  const toLearn=pool.filter(t=>!Sky.practised(P,t.id)).map(t=>t.id);
  if(def.kind!=="exam") return {items:Sky.pickQuiz(P,pool,{target:def.target,n:QUIZ_SIZE,seen}).items,toLearn};
  // like the exam: every unit, in proportion to the topics practised in it
  const by=def.units.map(uid=>pool.filter(t=>t.unit===uid&&Sky.practised(P,t.id))).filter(x=>x.length);
  const total=by.reduce((n,x)=>n+x.length,0), items=[];
  for(const ts of by) items.push(...Sky.pickQuiz(P,ts,{target:def.target,n:Math.max(1,Math.round(QUIZ_SIZE*ts.length/total)),seen}).items);
  items.splice(QUIZ_SIZE);
  if(items.length<QUIZ_SIZE){   // rounding left room: more from all the units, none twice
    const key=x=>`${x.id}:${x.qi}`, taken=new Set(items.map(key)), more={...seen}; for(const k of taken) more[k]="9999";
    items.push(...Sky.pickQuiz(P,pool,{target:def.target,n:QUIZ_SIZE,seen:more}).items.filter(x=>!taken.has(key(x))).slice(0,QUIZ_SIZE-items.length));
  }
  return {items,toLearn};
}
const bestOf=list=>list.reduce((b,q)=>!b||q.right/q.n>b.right/b.n?q:b,null);
function quizDelta(last,prev){
  if(!last||!prev) return "";
  const d=last.right-prev.right;
  return d>0?`+${d} מהפעם הקודמת`:d<0?`${d} מהפעם הקודמת`:"כמו בפעם הקודמת";
}
function quizCards(){
  const defs=homeQuizzes(); if(!defs.length) return "";
  return `<section class="mx-hq" aria-labelledby="mxHq"><h2 id="mxHq">${defs[0].exam?"בחנים לקראת המבחן":"בחנים"}</h2>${defs.map(quizCardHtml).join("")}</section>`;
}
function quizCardHtml(def){
  const tries=quizAttempts(def), best=bestOf(tries), b=buildQuiz(def), today=def.days!=null&&def.days>=def.band[0]&&def.days<=def.band[1];
  const head=`<b>${esc(def.title)}</b>${today?' <small class="mx-hq-today">מומלץ להיום</small>':""}`;
  const days=def.days!=null?`<span class="mx-small">מומלץ ${def.band[1]}–${def.band[0]} ימים לפני המבחן</span>`:"";
  const mine=best?`<span class="mx-hq-best">הכי טוב: ${best.right}/${best.n}${tries.length>1?` · ${quizDelta(tries.at(-1),tries.at(-2))}`:""}</span>`:"";
  if(b.items.length<QUIZ_MIN) return `<div class="mx-quiz-card mx-hq-card blocked" data-hq-kind="${def.kind}">${head}
      <span>אפשר להתחיל אחרי שתתרגלו קודם את הנושאים:</span><span class="mx-chips">${b.toLearn.slice(0,5).map(id=>`<button type="button" class="mx-chip" data-id="${esc(id)}">${fmt(BY[id].short||BY[id].name)}</button>`).join("")}</span>${days}</div>`;
  return `<button type="button" class="mx-quiz-card mx-hq-card" data-hq="${def.kind}">${head}<span>${b.items.length} שאלות. ${esc(def.say)}</span>${days}${mine}<span class="mx-dgo">${tries.length?"עוד ניסיון, עם שאלות חדשות":"להתחיל"} ‹</span></button>`;
}
function startHomeQuiz(kind,examKey){
  const e=examKey?prepExams().find(x=>x.key===examKey):null;
  const def=(e?quizzesFor(e):homeQuizzes()).find(d=>d.kind===kind); if(!def) return;
  const b=buildQuiz(def); if(b.items.length<QUIZ_MIN) return;
  if(!cur) back=document.activeElement;
  stopQuizClock(); closeSheetQuietly(); cur="quiz";
  QZ={items:shuffled(b.items.map(x=>({...x,pick:null}))),i:0,started:Date.now(),units:def.units,def,title:def.title,feedback:def.kind!=="exam",conf:def.kind==="exam"};
  quizShow();
  QZ.clock=setInterval(quizTick,1000);
}
// a strengthening quiz's answer: right or wrong, the mistake's tip, and the worked example after a wrong one
function quizFeedback(it,q){
  const box=sheet.querySelector(".mx-quiz-fb"); if(!box) return;
  const c=q.choices[it.pick], ok=!!c?.correct, M=!ok&&c?.mistake?G.mistakes[c.mistake]:null, ex=!ok?BY[it.id].example:null;
  sheet.querySelectorAll("[data-choice]").forEach(btn=>{ btn.disabled=true;
    if(btn.dataset.right!=null) btn.classList.add("right"); else if(+btn.dataset.choice===it.pick) btn.classList.add("wrong"); });
  box.innerHTML=ok?`<div class="mx-ok"><b>${Sky.praise()}</b></div>`
    :`<div class="mx-bad"><b>${M?fmt(M.name):"לא בדיוק"}</b>${M?`<span>${fmt(M.tip)}</span>`:""}<span>התשובה הנכונה מסומנת.</span>
      ${ex?`<details class="mx-quiz-example"><summary>לראות דוגמה פתורה</summary>${exampleCard(ex)}</details>`:""}</div>`;
}
// how sure the student is, in the quiz like the exam (not required)
const SURE=["לא בטוח/ה","די בטוח/ה","בטוח/ה"];
const quizSureHtml=it=>`<div class="mx-quiz-sure" role="group" aria-label="כמה אתם בטוחים? (לא חובה)"><span class="mx-small">כמה בטוחים? (לא חובה)</span>
  ${SURE.map((l,k)=>`<button type="button" class="mx-chip" data-quiz-sure="${k}" aria-pressed="${it.sure===k}">${l}</button>`).join("")}</div>`;
function quizSure(k){
  const it=QZ?.items?.[QZ.i]; if(!it) return;
  it.sure=it.sure===k?null:k;
  sheet.querySelectorAll("[data-quiz-sure]").forEach(b=>b.setAttribute("aria-pressed",+b.dataset.quizSure===it.sure));
}
function quizSureWrongHtml(res,sure){
  const bad=res.map((r,i)=>({r,s:sure[i]})).filter(x=>x.s===2&&!x.r.ok);
  return bad.length?`<section class="mx-quiz-surewrong"><h4>הייתי בטוח/ה וטעיתי</h4><ol>${bad.map(x=>`<li>${fmt(x.r.q.question)}</li>`).join("")}</ol>
    <p class="mx-small">טעויות שבטוחים בהן קשה לראות לבד. כדאי לעבור עליהן עם הדוגמה הפתורה או עם המורה.</p></section>`:"";
}
function quizCompareHtml(right,n,before){
  const best=bestOf([...before,{right,n}]), prev=before.at(-1);
  return `<p class="mx-quiz-best">הכי טוב: <b>${best.right}/${best.n}</b>${prev?` · ${quizDelta({right},prev)}`:""}</p>`;
}
function quizNoteSave(form){
  const q=(P.quizzes||[]).find(x=>x.at===form.dataset.quizNote), text=form.elements.note.value.trim().slice(0,QUIZ_NOTE_MAX);
  if(!q) return;
  if(text) q.note=text; else delete q.note;
  save(); form.querySelector("[role=status]").textContent=text?"נשמר.":"";
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
const uqEnds=(u,sit)=>sit.deadline?sit.deadline-UQ_PHOTO_MIN*60000:sit.started+u.quiz.minutes*60000;   // a final sitting: the server's deadline
function quizStep(u){
  if(!u.quiz) return "";
  const st=uqState(u.id), last=st.history.at(-1), going=st.sitting&&!st.sitting.submitted;
  const tag=going?"בתהליך":finOffer(u.id)?`${TERMS.final} פתוח`:last?.score!=null?`${last.score}/100`:last?"הוגש":"";
  return `<div class="mx-step mx-uquiz-step u-${u.id}"><button class="mx-node mx-uquiz${last?" done":""}" data-uquiz="${u.id}" aria-label="${TERMS.unitQuizzes}: ${esc(u.name)}${tag?`, ${tag}`:""}">📝</button>
    <span class="mx-lbl">${TERMS.unitQuizzes}${tag?`<em>${tag}</em>`:""}</span></div>`;
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
  upload_in_progress:"העלאה כבר מתבצעת. רגע…",
  quiz_time_over:"הזמן של המבחן נגמר. המבחן הוגש עם התשובות שנשמרו.",final_open:"המבחן של היחידה פתוח לכם. אחרי שתגישו אותו אפשר לתרגל שוב.",
  final_not_open:"המבחן לא פתוח עכשיו.",final_already_handed_in:"כבר הגשתם את המבחן של היחידה.",quiz_modes_unavailable:"מבחנים אינם זמינים כרגע.",open_ended_locked:"בוחנים פתוחים סגורים כרגע באתר.",sign_in_required:"יש להיכנס לחשבון."};
function stopUnitQuiz(){ if(UQ){ clearInterval(UQ.clock); clearTimeout(UQ.poll); Object.values(UQ.images||{}).forEach(URL.revokeObjectURL); } UQ=null; }
// the intro: what the quiz is and how it works, the last results, and start / continue
function uqIntro(uid){
  const u=G.units.find(x=>x.id===uid), q=u.quiz, st=uqState(uid), offer=finOffer(uid), start=offer?.start;
  // a final sitting started on another device (or before this device lost its copy): the server's start continues it
  if(start&&!start.sitting_id&&start.attempt_ids?.length===q.questions.length&&st.sitting?.startId!==start.id&&!(st.sitting&&!st.sitting.submitted))
    st.sitting=finSitting(start);
  const sit=st.sitting, going=sit&&!sit.submitted;
  if(going) return uqOpen(uid);
  if(!cur) back=document.activeElement;
  stopUnitQuiz(); cur="uquiz"; UQ={uid};
  const ready=uqReady(u), n=q.questions.length;
  const until=offer?new Date(Date.parse(offer.until)-(FIN?.skew||0)).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"}):"";
  const final=offer?`<section class="mx-uq-final" aria-label="${TERMS.final}">
      <h4>📌 ${TERMS.final}${offer.grant?" (ניסיון נוסף מהמורה)":""}</h4>
      <p>המורה פתח/ה את הבוחן המסכם של היחידה עד <b>${esc(until)}</b>. ${offer.grant?.reason?`<small>(${esc(offer.grant.reason)})</small>`:""}</p>
      <ul class="mx-uq-rules"><li>${TERMS.final} נעשה <b>פעם אחת</b>, והציון שלו הוא הציון של היחידה.</li>
        <li>השעון נשמר בשרת: גם אם סוגרים או מרעננים, הזמן ממשיך.</li>
        <li>הציון והפתרונות יופיעו אחרי שהמורה יפרסם את התוצאות.</li></ul>
      ${ready?`<div data-uq-final-box><button class="mx-btn solid" data-act="uq-final">התחלת הבוחן המסכם</button></div>`:""}</section>`:"";
  const label=h=>h.mode==="final"?(h.score==null?"מסכם · הוגש":`מסכם · ${h.score}/100`):(h.score==null?"חיזוק · ממתין לבדיקה":`חיזוק · ${h.score}/100`);
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-uq-sheet u-${uid}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">${TERMS.unitQuizzes}</h3>
        <small class="mx-src">${n} שאלות פתוחות · ${q.minutes} דקות · 100 נקודות</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${final}
      <h4>${offer?TERMS.practice:`${TERMS.practice}: אפשר לנסות כמה פעמים שרוצים`}</h4>
      <ul class="mx-uq-rules">
        <li>כמו בוחן בכיתה: כל השאלות מופיעות יחד, והשעון סופר לאחור מרגע ההתחלה.</li>
        <li>כתבו את הפתרונות על דף, כל שאלה בנפרד, עם דרך פתרון מלאה ונימוקים.</li>
        <li>צלמו את התשובה לכל שאלה. כשהזמן נגמר יש עוד ${UQ_PHOTO_MIN} דקות לצלם ולהגיש.</li>
        <li>הבדיקה, הציון והפתרונות מגיעים רק אחרי ההגשה.</li>
        <li>בוחן חיזוק לא נכנס לציון: הציון של היחידה הוא של הבוחן המסכם.</li>
        <li>אפשר לסגור ולחזור, אבל השעון ממשיך לרוץ.</li></ul>
      ${st.history.length?`<div class="mx-uq-history"><h4>הגשות קודמות</h4>${st.history.slice().reverse().map((h,k)=>{ const i=st.history.length-1-k;
        return `<button class="mx-btn" data-uq-result="${uid}:${i}">${new Date(h.at).toLocaleDateString("he-IL")} · ${label(h)}</button>`; }).join("")}</div>`:""}
      ${!ready?`<p class="mx-note">${!CFG.userId?"הבוחן זמין אחרי כניסה לחשבון.":"בוחנים עם תשובה מצולמת ובדיקה אוטומטית אינם זמינים כרגע באתר."}</p>`
        :offer?`<p class="mx-note">בוחן החיזוק ייפתח שוב אחרי שתגישו את הבוחן המסכם.</p>`
        :`<button class="mx-btn${st.history.length?"":" solid"}" data-act="uq-start">${st.history.length?"ניסיון נוסף":"התחלת בוחן חיזוק"}</button>`}</div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
}
// starting the final asks once more: it is given once
function uqFinalAsk(){
  const box=sheet.querySelector("[data-uq-final-box]"); if(!box) return;
  box.innerHTML=`<p class="mx-note" role="alert"><b>לפני שמתחילים:</b> את הבוחן המסכם עושים פעם אחת בלבד, והשעון מתחיל מיד.</p>
    <span class="mx-chips"><button class="mx-btn solid" data-act="uq-final-go">כן, להתחיל עכשיו</button><button class="mx-btn" data-uquiz="${esc(UQ.uid)}">עוד לא</button></span>`;
  box.querySelector("[data-act=uq-final-go]").focus();
}

/* ---------- final unit quizzes (app/quiz_modes.py) ----------
   GET /api/math/quiz-windows: the final sittings open to the student now (a window of their class, or a grant from the
   teacher), each with its start when started, and the windows of their final sittings (whether results are released).
   A final sitting's clock is the server's: `skew` turns the server's times into this device's. */
let FIN=null;
async function loadFinals(){
  if(!CFG.userId||!MY_CLASSES.length) return;
  try{ const r=await api("/api/math/quiz-windows",{cache:"no-store"}); FIN=r.ok?await r.json():null; if(FIN) FIN.skew=Date.parse(FIN.now)-Date.now(); }catch{ FIN=null; }
  if(ACTIVE_SUBJECT==="מתמטיקה"&&root&&!root.hidden&&!cur) draw();
}
const finOffer=uid=>(FIN?.offers||[]).find(o=>o.window.unit_id===uid&&!o.start?.sitting_id)||null;
const finSitting=(start,skew=FIN?.skew||0)=>({started:Date.parse(start.started_at)-skew,deadline:Date.parse(start.deadline)-skew,
  attempts:start.attempt_ids.slice(),submitted:null,startId:start.id,mode:"final"});

// a new sitting: one fresh answer attempt per question
async function uqStart(final=false){
  const uid=UQ.uid, u=G.units.find(x=>x.id===uid), btn=sheet.querySelector(final?"[data-act=uq-final-go]":"[data-act=uq-start]");
  const label=btn.textContent; btn.disabled=true; btn.textContent="מכינים את הבוחן…";
  try{
    let start=null, skew=0;
    if(final){ const d=await uqPost("/api/math/quiz-sittings/start",{unit_id:uid}); start=d.start; skew=Date.parse(d.now)-Date.now(); }
    const n=u.quiz.questions.length, have=start?.attempt_ids?.length===n?start.attempt_ids:[], attempts=[];
    for(const [index,q] of u.quiz.questions.entries())
      attempts.push(have[index]||(await uqPost("/api/math/quiz-attempts",{unit:uid,index,question_version:q.question_version,new:true,
        ...(start?{start_id:start.id}:{first:index===0})})).attempt.id);
    uqState(uid).sitting=start?finSitting({...start,attempt_ids:attempts},skew):{started:Date.now(),attempts,submitted:null,mode:"practice"};
    save(); draw();
    if(final) loadFinals();
    uqOpen(uid);
  }catch(e){ btn.disabled=false; btn.textContent=label; btn.insertAdjacentHTML("afterend",`<p class="mx-small mx-quiz-warn">${esc(e.message)}</p>`); if(final) loadFinals(); }
}
// the quiz paper
function uqOpen(uid){
  const u=G.units.find(x=>x.id===uid), sit=uqState(uid).sitting;
  if(!cur) back=document.activeElement;
  stopUnitQuiz(); cur="uquiz"; UQ={uid,res:{},images:{},busy:{},msg:{}};
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-uq-sheet mx-uq-paper u-${uid}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-uq-head"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">${sit.mode==="final"?TERMS.final:TERMS.practice}</h3></div>
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
// a photo is on its way (this device's, or the phone's): handing in now would leave that answer out
const uqUploading=()=>Object.values(UQ?.busy||{}).some(Boolean)||Object.values(UQ?.res||{}).some(r=>r&&!r.attachment&&r.scan?.state==="uploading");
function uqPaintSubmit(){
  const b=sheet.querySelector('[data-act="uq-submit"]'); if(!b) return;
  const up=uqUploading(); b.disabled=up; b.textContent=up?"מעלים תמונה…":"הגשת הבוחן";
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
  uqPaintSubmit();
}
// a photo replaces an answer by a fresh attempt for that question (an attempt keeps the one photo it received)
async function uqFresh(i){
  const u=G.units.find(x=>x.id===UQ.uid), q=u.quiz.questions[i], sit=uqState(UQ.uid).sitting;
  if(!UQ.res[i]?.attachment) return sit.attempts[i];
  const r=await uqPost("/api/math/quiz-attempts",{unit:UQ.uid,index:i,question_version:q.question_version,new:true,...(sit.startId?{start_id:sit.startId}:{})});
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
  }catch(e){ if(UQ?.uid===uid) UQ.msg[i]=e.message; if(e.code==="quiz_time_over"&&UQ?.uid===uid){ UQ.busy[i]=""; return uqSubmit(true); } }
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
  if(!timeUp&&uqUploading()) return;   // the button is disabled too; this covers a key press
  const missing=sit.attempts.filter((_,i)=>!UQ.res[i]?.attachment).length;
  if(!timeUp&&missing&&!UQ.sure){
    UQ.sure=true;
    sheet.querySelector(".mx-quiz-nav").insertAdjacentHTML("beforebegin",`<p class="mx-small mx-quiz-warn">${missing===1?"לשאלה אחת":`ל־${missing} שאלות`} אין תשובה מצולמת, והן יקבלו 0 נקודות. לחצו שוב על הגשה כדי להגיש בכל זאת.</p>`);
    return;
  }
  sit.submitted=Date.now();
  const st=uqState(uid); st.history.push({at:new Date().toISOString(),attempts:sit.attempts.slice(),score:null,timeUp,ck:crypto.randomUUID(),mode:sit.mode||"practice",...(sit.startId?{startId:sit.startId}:{})}); st.history=st.history.slice(-10);
  save(); draw();
  uqResult(uid,st.history.length-1,true);
}
/* The grade of a sitting is worked out by the server from the stored checks (app/quiz_grades.py); the score kept in
   this device's progress is only a copy of it. A sitting is handed in on the server once (`sid`); the same key makes
   a retry after a lost response the same sitting. */
async function uqSend(uid,entry){
  if(entry.sid) return entry.sid;
  if(!entry.ck){ entry.ck=crypto.randomUUID(); save(); }
  const d=await uqPost("/api/math/quiz-sittings",{unit_id:uid,attempts:entry.attempts,time_up:!!entry.timeUp,client_key:entry.ck,...(entry.startId?{start_id:entry.startId}:{})});
  if(entry.startId) loadFinals();
  entry.sid=d.id; if(d.code) entry.code=d.code;
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
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(u.name)}</span><h3 id="mxTitle">${entry.mode==="final"?TERMS.final:TERMS.practice}: בודקים…</h3>
        <small class="mx-src" aria-live="polite">${CFG.aiDirect===false?"שולחים את התשובות לבדיקת המורה":check?"בודקים את התשובות, זה לוקח כחצי דקה לשאלה":"טוענים את התשובות"}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div><div class="mx-uq-report"></div></div>`;
  sheet.hidden=false; sheet.querySelector(".mx-x").focus({preventScroll:true});
  let sendError="";
  commentSeen(c=>entry.attempts.includes(c.attempt_id));
  try{ await uqSend(uid,entry); }catch(e){ sendError=e.message; }
  if(UQ?.uid!==uid) return;
  const codeTag=()=>entry.code?` · מספר הבוחן: <b dir="ltr" class="mx-uq-code">${esc(entry.code)}</b>`:"";
  if(entry.code) sheet.querySelector(".mx-src").innerHTML=(CFG.aiDirect===false?"שולחים את התשובות לבדיקת המורה":"בודקים את התשובות")+codeTag();
  const results=[];
  for(let i=0;i<n;i++){
    let r=null;
    try{
      r=await uqJson(`${UQ_BASE}/${entry.attempts[i]}`);
      if(r.attachment&&r.grading_available&&(check||CFG.aiDirect===false)&&(!r.grading||(check&&r.grading.state==="failed"))){   // a student's hand-in sends the answers to the teacher; a teacher's checks are only the ones they press
        if(UQ?.uid!==uid) return;
        sheet.querySelector(".mx-src").innerHTML=(CFG.aiDirect===false?`שולחים את שאלה ${i+1} מתוך ${n} למורה…`:`בודקים את שאלה ${i+1} מתוך ${n}…`)+codeTag();
        try{ r=await uqPost(`${UQ_BASE}/${entry.attempts[i]}/grade`,{automatic:!check}); }catch(e){ r.error=e.message; }
      }
      if(r.attachment){ const b=await api(`${UQ_BASE}/${entry.attempts[i]}/image`,{cache:"no-store"}); if(b.ok&&UQ?.uid===uid) UQ.images[i]=URL.createObjectURL(await b.blob()); }
    }catch(e){ r={error:e.message}; }
    if(UQ?.uid!==uid) return;
    results.push(r);
  }
  entry.code||=results.map(r=>r?.ai_request?.code).find(Boolean)||"";   // a hand-in from before, or another device
  sheet.querySelector(".mx-src").innerHTML=(CFG.aiDirect===false?"שולחים את התשובות לבדיקת המורה":"")+codeTag();
  // points: the server's, per question (a checked answer earns its share; a missing one 0; one not checked yet leaves the total open)
  let sitting=null;
  if(entry.sid){ try{ sitting=await uqSitting(uid,entry.sid); }catch(e){ sendError||=e.message; } }
  if(UQ?.uid!==uid) return;
  if(sitting?.mode==="final"&&!sitting.released) return uqUnreleased(uid,entry,results);
  const rows=u.quiz.questions.map((q,i)=>{
    const r=results[i], g=r?.grading, a=g?.state==="completed"?g.result:null, pts=sitting?sitting.questions[i].earned:null;
    let say="";
    if(!r?.attachment) say="לא צולמה תשובה";
    else if(sitting?.questions[i]?.state==="teacher") say="נבדק על ידי המורה";
    else if(a&&a.score!=null) say={correct:"נכון ומלא",partial:"נכון בחלקו",incorrect:"לא נכון"}[a.verdict]||"";
    else { const req=a?null:r.ai_request;
      say=req&&["pending","failed"].includes(req.state)?"ממתין לאישור המורה לבדיקה":req?.state==="sending"?"בבדיקה עכשיו":req?.state==="declined"?`המורה לא אישר את הבדיקה${req.note?`: ${req.note}`:""}`:a?.verdict==="unreadable"?"לא הצלחנו לקרוא את התמונה":a?.verdict==="needs_review"?"ממתין לבדיקה של המורה":r.error||(!r.grading_available?"הבדיקה האוטומטית אינה זמינה כרגע":"עוד לא נבדקה"); }
    return `<li class="mx-uq-q"><div class="mx-uq-qhead"><b>שאלה ${i+1}</b><span>${pts==null?"–":pts}/${q.points} נק׳</span></div>
      <p class="mx-uq-text">${fmt(q.question).replace(/\n/g,"<br>")}</p>
      ${UQ.images[i]?`<img class="mx-uq-img" alt="התשובה שלכם לשאלה ${i+1}" src="${UQ.images[i]}">`:""}
      <p class="mx-uq-verdict ${a?.verdict||"none"}">${esc(say)}</p>
      ${window.MathlyAnswers?.teacherNote?.(r||{})||""}
      ${a?.feedback?`<p>${r.teacher_review?"<b>בדיקה אוטומטית: </b>":""}${fmtLoose(a.feedback)}</p>`:""}${a?.next_step?`<p><b>הצעד הבא: </b>${fmtLoose(a.next_step)}</p>`:""}
      ${a?.solution?`<details><summary>הפתרון המלא</summary><p class="mx-grade-solution">${fmtLoose(a.solution)}</p></details>`:""}
      ${r?.attachment?window.MathlyAnswers?.reviewBox?.(entry.attempts[i],r)||"":""}
      ${r?.attachment&&!a&&r.grading_available&&!["pending","sending","failed"].includes(r.ai_request?.state)?`<button class="mx-btn" data-uq-result="${uid}:${h}:check">${CFG.aiDirect===false?"שליחה מחדש למורה":"בדיקת התשובות באמצעות AI"}</button>`:""}</li>`;
  });
  const earned=sitting?sitting.questions.reduce((sum,x)=>sum+(x.earned||0),0):0, open=sitting?sitting.open:n;
  entry.score=sitting?.grade??null; save(); draw();
  const total=!sitting?"ההגשה לא נשמרה בשרת":open?`${earned} נקודות עד עכשיו · ${open===1?"שאלה אחת לא נבדקה":`${open} שאלות לא נבדקו`}`:`${earned}/100`;
  sheet.querySelector("#mxTitle").textContent=`${sitting?.mode==="final"||entry.mode==="final"?TERMS.final:TERMS.practice}: ${total}`;
  sheet.querySelector(".mx-src").innerHTML=esc(`הוגש ${new Date(entry.at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"})}${entry.timeUp?" · הוגש כשהזמן נגמר":""}`)+codeTag();
  const final=sitting?.mode==="final", retake=final?"":uqRetakeHtml(sitting);
  sheet.querySelector(".mx-uq-report").innerHTML=`<ol class="mx-uq-qs">${rows.join("")}</ol>
    ${sendError&&!sitting?`<p class="mx-note mx-quiz-warn">${esc(sendError)} <button class="mx-btn" data-uq-result="${uid}:${h}:check">ניסיון נוסף</button></p>`:""}
    ${retake}
    <p class="mx-small">הבדיקה אוטומטית באמצעות AI: בדקו שהיא תואמת למה שכתבתם, ואם משהו נראה לא נכון, הראו למורה.</p>
    <div class="mx-quiz-nav"><button class="mx-btn" data-uquiz="${uid}">${final?"לבוחן":"ניסיון נוסף"}</button><button class="mx-btn solid" data-act="close">חזרה למסלול</button></div>`;
}

// the skills behind the points a practice sitting lost (each quiz question names its skills), to practise before a retake
const SKILL_STATE={gold:"זהב ⭐",lit:"הושלם",fading:"דועך – כדאי לחזור",practising:"בתרגול",new:"עוד לא התחיל"};
function skillState(id){
  if(P.done?.[id]) return P.gold?.[id]?"gold":Sky.fading(P,id)?"fading":"lit";
  return (P.missed?.[id]||[]).length||P.tries?.[id]||P.seen?.[id]?"practising":"new";
}
function uqLostSkills(sitting){
  if(!sitting) return [];
  return [...new Set(sitting.questions.filter(x=>x.earned!=null&&x.earned<x.points).flatMap(x=>x.skills||[]))].filter(id=>BY[id]);
}
function uqRetakeHtml(sitting){
  const lost=uqLostSkills(sitting); if(!lost.length) return "";
  return `<section class="mx-uq-retake" aria-label="לפני ניסיון נוסף"><h4>לפני ניסיון נוסף: כדאי לתרגל</h4>
    <p class="mx-small">אלה המיומנויות של השאלות שבהן הפסדתם נקודות. אפשר לתרגל אותן קודם, או לנסות שוב מיד.</p>
    <ul class="mx-uq-skills">${lost.map(id=>`<li><button class="mx-chip u-${BY[id].unit}" data-id="${id}">${fmt(BY[id].short)}</button> <small>${SKILL_STATE[skillState(id)]}</small></li>`).join("")}</ul></section>`;
}
// a final sitting before the teacher releases the results: handed in, and the photos the student sent
function uqUnreleased(uid,entry,results){
  const u=G.units.find(x=>x.id===uid);
  entry.score=null; save(); draw();
  sheet.querySelector("#mxTitle").textContent=`${TERMS.final}: הוגש`;
  sheet.querySelector(".mx-src").textContent=`הוגש ${new Date(entry.at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"})}${entry.timeUp?" · הוגש כשהזמן נגמר":""}`;
  sheet.querySelector(".mx-uq-report").innerHTML=`<p class="mx-note" role="status"><b>המבחן הוגש.</b> התוצאות יפורסמו על ידי המורה: הציון, הבדיקה והפתרונות יופיעו כאן ובדף הציונים.</p>
    <ol class="mx-uq-qs">${u.quiz.questions.map((q,i)=>`<li class="mx-uq-q"><div class="mx-uq-qhead"><b>שאלה ${i+1}</b><span>${q.points} נק׳</span></div>
      ${UQ.images[i]?`<img class="mx-uq-img" alt="התשובה שלכם לשאלה ${i+1}" src="${UQ.images[i]}">`:`<p class="mx-small">${results[i]?.attachment?"":"לא צולמה תשובה"}</p>`}</li>`).join("")}</ol>
    <div class="mx-quiz-nav"><button class="mx-btn solid" data-act="close">חזרה למסלול</button></div>`;
}

function onClick(e){
  const t=e.target.closest("button,[data-act]"); if(!t||!root.contains(t)) return;
  if(t.dataset.choice!=null) return answer(t);
  if(t.dataset.boardToggle!=null) return window.MathlyBoard?.toggle();
  if(t.dataset.quizUnit) return quizToggle(t.dataset.quizUnit);
  if(t.dataset.quizGo!=null) return quizGo(+t.dataset.quizGo);
  if(t.dataset.quizSure!=null) return quizSure(+t.dataset.quizSure);
  if(t.dataset.hq) return startHomeQuiz(t.dataset.hq,t.dataset.hqExam);
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
  if(t.dataset.gradeSitting) return gradeSitting(t.dataset.gradeSitting);
  if(t.dataset.prep) return openPrep(t.dataset.prep);
  if(t.dataset.prepExam){ const e=prepExams().find(x=>x.key===t.dataset.prepExam); if(e){ stopQuizClock(); QZ=null; cur=null; return quizSetup(e.units); } }
  if(t.dataset.asgNew!=null){ REPORT.form={id:null}; drawReport(); return sheet.querySelector(".mx-asg-form input[name=title]")?.focus(); }
  if(t.dataset.asgEdit){ REPORT.form={id:t.dataset.asgEdit,focus:t.dataset.asgFocus!=null}; drawReport(); return sheet.querySelector(".mx-asg-form input[name=title]")?.focus(); }
  if(t.dataset.asgFocusNew!=null) return focusOpen();
  if(t.dataset.finalClose||t.dataset.finalRelease) return finalAct(t);
  if(t.dataset.batch) return aqBatch(t);
  if(t.dataset.examDel) return examDelete(t.dataset.examDel);
  if(t.dataset.inboxOpen) return inboxOpen(t.dataset.inboxOpen);
  if(t.dataset.wsAiFill){ const s=REPORT?.data.students.flatMap(x=>x.worksheet_submissions||[]).find(x=>x.id===t.dataset.wsAiFill), f=sheet.querySelector("[data-ws-check]");
    if(s?.ai&&f){ if(s.ai.score!=null) f.elements.score.value=s.ai.score; f.elements.comment.value=s.ai.comment||""; f.elements.comment.focus(); } return; }
  if(t.dataset.focusGive) return focusOpen([t.dataset.focusGive],t.dataset.focusTo.split(",").filter(Boolean));
  if(t.dataset.asgCancel!=null){ wsCancel(); REPORT.form=null; return drawReport(); }
  if(t.dataset.asgDel) return asgDelete(t.dataset.asgDel);
  if(t.dataset.wsOpen) return wsOpen(t.dataset.wsOpen);
  if(t.dataset.wsUpload!=null) return wsUpload(t);
  if(t.dataset.wsRemove) return wsRemove(t.dataset.wsRemove);
  if(t.dataset.wsSub) return wsSubOpen(t.dataset.wsSub);
  if(t.dataset.wsSubBack!=null){ wsSubClose(); if(REPORT) REPORT.inbox=null; drawReport(); return sheet.querySelector(`[data-report-tab="${REPORT.tab}"]`)?.focus(); }
  if(t.dataset.wsAi!=null) return wsAiCheck(t);
  if(t.dataset.wsPick!=null) return sheet.querySelector("[data-ws-file]")?.click();
  if(t.dataset.wsSend!=null) return wsSend();
  if(t.dataset.wsBoard!=null) return wsBoard();
  if(t.dataset.wsPhone!=null) return wsPhone();
  if(t.dataset.wsCancel!=null) return wsPhoneCancel();
  if(t.dataset.wsUp) return wsMove(+t.dataset.wsUp,false);
  if(t.dataset.wsDrop) return wsMove(+t.dataset.wsDrop,true);
  if(t.dataset.wsDownload!=null) return wsDownload(t);
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
  if(t.dataset.reportTab||t.dataset.heatUnit||t.dataset.heatGroup||t.dataset.heatAll) return reportControl(t);
  if(t.dataset.aqSend) return aqSend(t.dataset.aqSend);
  if(t.dataset.aqDecline) return aqDecline(t.dataset.aqDecline);
  switch(t.dataset.act){
    case "help-close": return helpClose();
    case "manage": return manageClasses();
    case "class-report": return classReport(t.dataset.classId);
    case "ai-queue": return aiQueue();
    case "aq-all": return aqAll();
    case "photo-cancel": return photoCancel();
    case "manage-refresh": return loadManagedClasses(true);
    case "manage-lab": return showManageMode("lab");
    case "manage-prompter": return showManageMode("prompter");
    case "prompter-go": return window.MathlyPrompter?.open(sheet.querySelector("#mxPrompterText")?.value);
    case "manage-practice": return closeSheet();
    case "preview-on": return setPreview(true);
    case "preview-off": return setPreview(false);
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
    case "tasks": return openTasks();
    case "grades": return openGrades();
    case "uq-start": return uqStart();
    case "uq-final": return uqFinalAsk();
    case "uq-final-go": return uqStart(true);
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
        <button class="mx-btn" data-act="manage-prompter">פרומפטר</button>
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
  if(mode==="prompter"){
    // a developer tool: the text is kept only in this browser, so it is still there the next time
    let saved=""; try{saved=localStorage.getItem("mathly.prompterText")||"";}catch{}
    box.innerHTML=`<div class="mx-manage-title"><h4>פרומפטר</h4><span>טקסט לקריאה מול המצלמה</span></div>
      <textarea id="mxPrompterText" class="mx-prompter-text" dir="auto" rows="12" placeholder="הדביקו או כתבו כאן את הטקסט…" aria-label="טקסט לפרומפטר">${esc(saved)}</textarea>
      <p class="mx-note">רווח: הפעלה/עצירה · ↑/↓: מהירות · +/−: גודל · M: מראה · F: מסך מלא · Esc: יציאה</p>
      <button class="mx-btn solid" data-act="prompter-go">הצגה בפרומפטר</button>`;
    const area=box.querySelector("#mxPrompterText");
    area.addEventListener("input",()=>{try{localStorage.setItem("mathly.prompterText",area.value);}catch{}});
    area.focus(); return;
  }
  box.innerHTML='<div class="mx-manage-title"><h4>מעבדה</h4><span>כלים לבדיקה ופיתוח</span></div><p class="mx-note">כלי המעבדה למתמטיקה יתווספו כאן. אפשר לחזור לכל אזור ניהול מהכרטיסיות למעלה.</p>';
}

/* Monitoring (ניטור): a snapshot of the system, open-answer activity, and the server's latest warnings.
   Each source loads and fails on its own, so a slow Supabase does not hold up the rest. */
const MON_RANGES={day:["יום","24 השעות האחרונות","15 דקות"],week:["שבוע","7 הימים האחרונים","שעה"],month:["חודש","30 הימים האחרונים","יום"]};
const MON_ACTIONS={visit:["👋","נכנס/ה לאפליקציה"],photo:["📷","צילם/ה תרגיל לעזרה"],answer_upload:["📝","שלח/ה תשובה פתוחה"],answer_graded:["✔️","תשובה נבדקה"],class_saved:["🏫","שמר/ה כיתה"],class_deleted:["🗑️","מחק/ה כיתה"],resource_added:["🖼️","הוסיף/ה תמונה למשאבי שיעור"],
  worksheet_added:["📄","העלה/תה שיעורי בית"],worksheet_submitted:["📬","הגיש/ה שיעורי בית"],worksheet_checked:["✅","בדק/ה שיעורי בית"],worksheet_ai_checked:["🤖","בדק/ה שיעורי בית עם AI"],
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
      <label>מורה הכיתה<small>כתובת דוא״ל אחת, לא מרשימת התלמידים: מורה אינו תלמיד בכיתה. המורה רואה את ההתקדמות, הקשיים והציונים של כל התלמידים בכיתה.</small><input type="text" name="teacher" dir="ltr" spellcheck="false" autocomplete="off" placeholder="teacher@example.com" value="${esc((row?.teachers||[])[0]||"")}"></label>
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
  const lines=name=>form.elements[name].value.split(/[\n,;]+/).map(value=>value.trim().toLowerCase()).filter(Boolean);
  const pickTeacher=form.elements.teacher;
  form.querySelector('input[name="name"]').focus();
  form.onsubmit=async event=>{
    event.preventDefault();
    const lessons=[...form.querySelectorAll('input[name="unit"]:checked')].map(input=>input.value);
    if(!lessons.length){message.textContent="בחרו לפחות מקצוע אחד.";return;}
    const teacher=pickTeacher.value.trim().toLowerCase(), students=lines("emails");
    if(teacher&&!teacher.includes("@")){message.textContent="כתבו כתובת דוא״ל תקינה למורה.";return;}
    if(students.includes(teacher)){message.textContent="מורה לא יכול להיות גם תלמיד בכיתה. הסירו אותו מרשימת התלמידים.";return;}
    const body={name:form.elements.name.value.trim(),emails:students,teachers:teacher?[teacher]:[],lessons};
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
// "view as student": the teacher sees the home screen the way a student of the class does, until they switch back
const previewBar=()=>PREVIEW?`<div class="mx-preview" role="status"><span>מצב תצוגה כתלמיד</span><button class="mx-btn" data-act="preview-off">חזרה למצב מורה</button></div>`:"";
function setPreview(on){ PREVIEW=on; closeSheet(); if(hasExams()) drawSubjectPicker(); else selectSubject("מתמטיקה"); window.scrollTo?.(0,0); }
const teachButton=()=>CFG.aiReview?`<button class="mx-btn" data-act="ai-queue">${aqLabel()}</button>`:"";
// the teacher's classes, at the top of the home screen: each opens its report (students, progress, assignments)
function classesCard(){
  const mine=PREVIEW?[]:teachClasses(); if(!mine.length) return "";
  return `<section class="mx-classes" aria-labelledby="mxClasses"><h2 id="mxClasses">הכיתות שלי</h2>
    <div class="mx-classes-grid">${mine.map(row=>`<button type="button" class="mx-myclass" data-act="class-report" data-class-id="${esc(row.id)}">
      <b>${esc(row.name)}</b><small>${row.students!=null?`${row.students} תלמידים`:"תלמידים, התקדמות ומשימות"}${INBOX_COUNT?.[row.id]?` · <span class="mx-inbox-count">📥 ${INBOX_COUNT[row.id]} לבדיקה</span>`:""}</small><i aria-hidden="true">‹</i></button>`).join("")}</div>
    ${CFG.aiLeft!=null?`<p class="mx-small mx-ai-left">${CFG.aiLeft?`נשארו לכם היום ${CFG.aiLeft===1?"בקשת AI אחת":`${CFG.aiLeft} בקשות AI`} מתוך 3.`:"השתמשתם היום בכל 3 בקשות ה-AI. אפשר שוב מחר."}</p>`:""}</section>`;
}
const aiUsed=()=>{ if(CFG.aiLeft!=null) CFG.aiLeft=Math.max(0,CFG.aiLeft-1); };
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
    // the official grade is the latest final sitting's (app/quiz_modes.py); practice sittings never make it
    const official=mine.filter(x=>x.mode==="final").at(-1)||null, practice=mine.filter(x=>x.mode!=="final").at(-1)||null;
    return {u,st,last:mine.at(-1)||null,official,practice,count:mine.length,unverified:st.history.filter(h=>!h.sid||!known.has(h.sid)).length};
  });
  const officials=quizzes.map(x=>x.official?.grade).filter(g=>g!=null);
  const scores=officials.length?officials:quizzes.map(x=>x.last?.grade).filter(g=>g!=null);
  const exams=(p.quizzes||[]).slice().reverse();
  const days=Object.keys(p.days||{}).sort(), last=[p.updated?new Date(+p.updated):null,days.length?new Date(days.at(-1)):null].filter(d=>d&&!isNaN(d)).sort((a,b)=>b-a)[0];
  // worked examples the student opened in the last two weeks, in the class's skills (the device reports them)
  const classSkills=new Set(units.flatMap(u=>unitIds(u).filter(live))), since=Date.now()-14*864e5;
  const helped=Object.entries(p.examples||{}).filter(([id,e])=>classSkills.has(id)&&BY[id]&&Date.parse(e?.last)>=since)
    .map(([id,e])=>({id,n:+e.n||1,last:e.last})).sort((a,b)=>b.last.localeCompare(a.last));
  return {perUnit,n,done,helped,week:Sky.weekly(p),recurring:recurring.filter(x=>G.mistakes[x.m]),quizzes,quizzesKnown:sittings!=null,quizAvg:scores.length?Math.round(scores.reduce((a,b)=>a+b,0)/scores.length):null,quizAvgOfficial:officials.length>0,exams,last};
}
async function classReport(id){
  const mine=teachClasses(), classId=id??REPORT?.id??mine[0]?.id; if(classId==null) return;
  if(!cur) back=document.activeElement;
  closeSheetQuietly(); cur="report"; REPORT={id:classId,data:null,form:null,tab:repGet("tab","list"),sort:repGet("sort","attention"),unit:"overview",open:repGet("mapMonths",null)};
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
// the teacher's choices in the report (which tab, the order) are kept on this device
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
// a unit's share of finished skills as a heat level: 0 not started, 1 under a third, 2 under two thirds, 3 under all, 4 all
const heatLevel=(done,n,started)=>!n||(!done&&!started)?0:done>=n?4:done*3<n?1:done*3<2*n?2:3;
// the map's open months: the teacher's choice, kept on this device; until they choose, the current month is open
const heatOpen=()=>REPORT.open==null?new Set([new Date().toLocaleDateString("he-IL",{month:"long",timeZone:"Asia/Jerusalem"})])
  :new Set(REPORT.open.split("|").filter(Boolean));
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
  // a student's state at a glance: stuck on something, active this week, or quiet; and the last 14 days as small bars
  const dayKey=d=>d.toLocaleDateString("en-CA",{timeZone:"Asia/Jerusalem"});
  const status=r=>{ const week=Date.now()-7*864e5;
    return r.perUnit.some(x=>x.stuck.length)?['low',"תקוע","יש לתלמיד לפחות מיומנות אחת שלא הושלמה ושיש בה שאלות שנענו לא נכון ועדיין לא נפתרו. זה לא ציון: אין סף, ומספיק שאלה אחת. נתוני המכשיר של התלמיד, והשרת לא בודק אותם."]:r.last&&r.last.getTime()>=week?['good',"פעיל"]:['mid',"לא פעיל"]; };
  const spark=s=>{ const days=s.progress?.days||{}, now=Date.now();
    const bars=Array.from({length:14},(_,k)=>days[dayKey(new Date(now-(13-k)*864e5))]||0), top=Math.max(5,...bars);
    return `<span class="mx-spark" role="img" aria-label="${bars.reduce((a,b)=>a+b,0)} תשובות נכונות ב־14 הימים האחרונים" title="14 הימים האחרונים">${bars.map(n=>`<i style="height:${n?Math.max(15,Math.round(n/top*100)):6}%"${n?"":' class="off"'}></i>`).join("")}</span>`; };
  const card=({s,r,att},i)=>{
    if(!r) return `<details class="mx-report-student" id="rs-${i}"><summary><b dir="ltr">${esc(name(s.email))}</b><span class="mx-small">${s.signed_in?"עוד לא התחיל לתרגל":"עוד לא נכנס לחשבון"}</span></summary><p class="mx-small" dir="ltr">${esc(s.email)}</p>${focusOf(s,units).length?focusCardHtml(s,{recurring:[]},units):""}</details>`;
    const exam=r.exams[0];
    const [stTone,stText,stHint]=status(r);
    return `<details class="mx-report-student" id="rs-${i}"><summary><b dir="ltr">${esc(name(s.email))}</b><span class="mx-report-chip ${stTone}"${stHint?` title="${esc(stHint)}"`:""}>${stText}</span>
        <span class="mx-report-prog"><span class="mx-meter" aria-hidden="true"><i style="width:${pct(r.done,r.n)}%"></i></span><small>${r.done}/${r.n} מיומנויות</small></span>${spark(s)}
        <span class="mx-report-chip${tone(r.quizAvg)}" title="${r.quizAvgOfficial?"ממוצע המבחנים":"ממוצע הבחנים האחרונים (אין עדיין מבחן)"}">${r.quizAvgOfficial?"מבחן":"בוחן"} ${grade(r.quizAvg)}</span>
        <span class="mx-report-chip${tone(exam?pct(exam.right,exam.n):null)}" title="מבחן התרגול האחרון (נתוני מכשיר)">מבחן תרגול ${exam?`${exam.right}/${exam.n}`:"–"}</span>
        ${r.recurring.length?`<span class="mx-report-chip low">${r.recurring.length} קשיים</span>`:""}
        ${(s.review_requests||[]).length?`<span class="mx-report-chip low">ביקש בדיקה חוזרת</span>`:""}</summary>
      <div class="mx-report-body">
        <p class="mx-small"><span dir="ltr">${esc(s.email)}</span>${r.last?` · פעילות אחרונה ${r.last.toLocaleDateString("he-IL")}`:""}</p>
        ${focusCardHtml(s,r,units)}
        ${(s.review_requests||[]).length?`<section class="mx-tr-request"><h5>ביקש שתסתכלו שוב</h5>${s.review_requests.map(q=>`<p>${fmt(q.question||"")}${q.message?`: ${esc(q.message)}`:""}
          <button type="button" class="mx-btn" data-review-answer="${esc(q.attempt_id)}" data-review-from="report">פתיחת התשובה</button></p>`).join("")}</section>`:""}
        ${r.helped.length?`<section><h5>דוגמאות פתורות שנפתחו בשבועיים האחרונים${DEVICE_NOTE}</h5><ul class="mx-report-list">${r.helped.map(x=>
          `<li><b>${fmt(BY[x.id].name)}</b> <small>${x.n===1?"פעם אחת":`${x.n} פעמים`}, לאחרונה ${shortDate(x.last)}</small></li>`).join("")}</ul></section>`:""}
        <p class="mx-report-week"><b>${r.week.thisWeek}</b> תשובות נכונות השבוע · <b>${r.week.lastWeek}</b> בשבוע שעבר</p>
        ${focusOfHtml(s)}
        <section><h5>התקדמות ביחידות${DEVICE_NOTE}</h5><div class="mx-quiz-units-score">${r.perUnit.filter(x=>x.done||x.gold||x.stuck.length).map(x=>`<div><span>${esc(x.u.name)}${x.gold?` <small>· ${x.gold} זהב</small>`:""}</span><b>${x.done}/${x.n}</b><span class="mx-meter" aria-hidden="true"><i style="width:${pct(x.done,x.n)}%"></i></span></div>`).join("")||'<p class="mx-small">עוד אין פעילות ביחידות.</p>'}</div>${r.perUnit.some(x=>!x.done&&!x.gold&&!x.stuck.length)?`<p class="mx-small">עוד ${r.perUnit.filter(x=>!x.done&&!x.gold&&!x.stuck.length).length} יחידות בלי פעילות</p>`:""}</section>
        <section><h5>קשיים${DEVICE_NOTE}</h5>${r.recurring.length?`<div class="mx-chips">${r.recurring.map(x=>`<span class="mx-report-chip low" title="${x.n} פעמים ב־${x.skills.length} מיומנויות, לאחרונה ${shortDate(x.last)}">${fmt(G.mistakes[x.m].name)} <em>×${x.n}</em></span>`).join("")}</div>
      <p class="mx-small">${r.recurring.map(x=>`<b>${fmt(G.mistakes[x.m].name)}</b>: ${x.n} פעמים ב־${x.skills.length} מיומנויות, לאחרונה ${shortDate(x.last)}${BY[x.practise]?`. לחזק: ${fmt(BY[x.practise].name)}`:""}`).join("<br>")}</p>`:'<p class="mx-small">אין טעויות שחוזרות לאחרונה.</p>'}
          ${r.perUnit.some(x=>x.stuck.length)?`<p class="mx-small">מיומנויות עם שאלות שעוד לא נפתרו: ${r.perUnit.flatMap(x=>x.stuck).slice(0,8).map(sk=>fmt(sk.name)).join(" · ")}</p>`:""}</section>
        <section><h5>${TERMS.unitQuizzes}</h5>${quizUnits.length?`<table class="mx-report-table"><thead><tr><th>יחידה</th><th>ציון היחידה (בוחן מסכם)</th><th>בוחן אחרון</th><th>הגשות</th><th>תאריך</th><th>תשובות</th></tr></thead><tbody>${r.quizzes.map(({u,st,last,official,practice,count,unverified})=>{
            const g=x=>x?(x.grade==null?"ממתין לבדיקה":`${x.grade}/100`):"–";
            const cell=!r.quizzesKnown?"לא זמין":g(official);
            const prac=st.going?"בתהליך":!r.quizzesKnown?"לא זמין":practice?g(practice):unverified?"לא מאומת":"–";
            const subs=`${count||(unverified?"":"–")}${unverified&&r.quizzesKnown?`${count?" ":""}<small>(${unverified} לא מאומתות)</small>`:""}`;
            return `<tr><td>${esc(u.name)}</td><td class="mx-report-grade${tone(official?.grade)}">${cell}</td><td class="mx-report-grade${tone(practice?.grade)}">${prac}</td><td>${subs}</td><td>${last?shortDate(last.submitted_at):"–"}</td><td>${last?`<button type="button" class="mx-btn${last.grade==null?" solid":""}" data-answers="${i}:${esc(u.id)}">פתיחה</button>`:""}</td></tr>`; }).join("")}</tbody></table>`:'<p class="mx-small">ליחידות של הכיתה אין בוחן מסכם.</p>'}</section>
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

  // the map: a row per student; a column per unit, or (one unit chosen) per skill. The colour says how far the student is,
  // the red mark says they are stuck on something there. It is the device's data, as the rest of the progress
  const mapUnit=units.find(u=>u.id===REPORT.unit);
  const started=all.filter(x=>x.r).length;
  let map;
  if(!students.length) map='<p class="mx-note">אין עדיין תלמידים בכיתה.</p>';
  else if(!mapUnit){
    // two levels: the units are grouped by the month the syllabus teaches them in; a month's column opens into its units
    const monthOf=u=>(u.when||"ללא מועד").split(/[–-]/)[0].trim();
    const groups=[]; units.forEach((u,k)=>{ const key=monthOf(u); let g=groups.find(x=>x.key===key); if(!g) groups.push(g={key,ks:[]}); g.ks.push(k); });
    const openG=heatOpen(), isOpen=g=>openG.has(g.key), rows=groups.some(isOpen)?2:1;
    const stuckIn=ks=>order.filter(({r})=>r&&ks.some(k=>r.perUnit[k].stuck.length)).length;
    const hard=ks=>stuckIn(ks)>0&&stuckIn(ks)*3>=Math.max(started,1);
    const cell=(s,r,ks,title)=>{
      if(!r) return `<td><span class="mx-heat-cell h0" role="img" aria-label="${s.signed_in?"עוד לא התחיל לתרגל":"עוד לא נכנס לחשבון"}"></span></td>`;
      const done=ks.reduce((t,k)=>t+r.perUnit[k].done,0), n=ks.reduce((t,k)=>t+r.perUnit[k].n,0), stuck=ks.reduce((t,k)=>t+r.perUnit[k].stuck.length,0);
      const label=`${title}: ${done} מתוך ${n} מיומנויות${stuck?`, תקוע ב־${stuck}`:""}`;
      return `<td><span class="mx-heat-cell h${heatLevel(done,n,0)}${stuck?" stuck":""}" role="img" aria-label="${esc(label)}" title="${esc(label)}">${done?`${pct(done,n)}%`:""}</span></td>`; };
    const head1=groups.map(g=>isOpen(g)
      ?`<th scope="colgroup" colspan="${g.ks.length}" class="mx-heat-gopen"><button type="button" class="mx-heat-group" data-heat-group="${esc(g.key)}" aria-expanded="true" title="קיפול ${esc(g.key)}">◂ ${esc(g.key)}</button></th>`
      :`<th scope="col" rowspan="${rows}" class="mx-heat-gcol${hard(g.ks)?" hard":""}"><button type="button" class="mx-heat-group" data-heat-group="${esc(g.key)}" aria-expanded="false" title="פתיחת ${esc(g.key)}: ${g.ks.length} יחידות">${esc(g.key)}<small>${g.ks.length} יחידות ▸</small></button></th>`).join("");
    const head2=rows===2?`<tr>${groups.filter(isOpen).flatMap(g=>g.ks).map(k=>
      `<th scope="col" class="mx-heat-col${hard([k])?" hard":""}"><button type="button" class="mx-heat-unit" data-heat-unit="${esc(units[k].id)}" title="${esc(units[k].name)}: פתיחה לפי מיומנויות">${esc(units[k].name)}</button></th>`).join("")}</tr>`:"";
    map=`<table class="mx-heat"><thead><tr><th class="mx-grid-name" scope="col" rowspan="${rows}">תלמיד</th>${head1}</tr>${head2}</thead><tbody>${
      order.map(({s,r})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th>${groups.map(g=>isOpen(g)?g.ks.map(k=>cell(s,r,[k],units[k].name)).join(""):cell(s,r,g.ks,g.key)).join("")}</tr>`).join("")}</tbody></table>
      <p class="mx-small">לחיצה על חודש פותחת אותו ליחידות שלו, ולחיצה על שם יחידה פותחת אותה לפי מיומנויות. נקודה אדומה: התלמיד תקוע בלפחות מיומנות אחת.</p>`;
  }else{
    const skills=unitIds(mapUnit).filter(live);
    const count=skills.map(id=>{ const st=all.map(x=>cellState(x.s.progress,id));
      const trying=st.filter(t=>t==="trying").length; return {id,done:st.filter(t=>["gold","lit","fading"].includes(t)).length,trying,hard:trying>0&&trying>=started*HARD_SHARE}; });
    map=`<table class="mx-grid"><thead><tr><th class="mx-grid-name" scope="col">תלמיד</th>${count.map(c=>
      `<th scope="col" class="mx-grid-skill${c.hard?" hard":""}"${c.hard?' aria-label="קושי כיתתי"':""}><span title="${esc(BY[c.id].name)}">${c.hard?"⚠ ":""}${fmt(BY[c.id].short||BY[c.id].name)}</span></th>`).join("")}</tr></thead><tbody>${
      order.map(({s})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th>${skills.map(id=>{ const st=cellState(s.progress,id);
        return `<td><span class="mx-cell ${st}" role="img" aria-label="${CELL_TEXT[st]}" title="${CELL_TEXT[st]}"></span></td>`; }).join("")}</tr>`).join("")}</tbody><tfoot>
      <tr><th scope="row" class="mx-grid-name">סיימו</th>${count.map(c=>`<td class="mx-grid-sum">${c.done}/${started}</td>`).join("")}</tr>
      <tr><th scope="row" class="mx-grid-name">מתקשים</th>${count.map(c=>`<td class="mx-grid-sum${c.hard?" hard":""}">${c.trying||""}</td>`).join("")}</tr></tfoot></table>
      <p class="mx-small">⚠ מיומנות שלפחות שליש מהתלמידים מתרגלים ועוד לא סיימו.</p>`;
  }
  const mapLegend=mapUnit?"":`<div class="mx-heat-legend" aria-hidden="true"><span><i class="h0"></i>לא התחיל</span><span><i class="h1"></i>עד שליש</span><span><i class="h2"></i>עד שני שלישים</span><span><i class="h3"></i>כמעט הכול</span><span><i class="h4"></i>סיים</span></div>`;
  const view=["map","tasks","subs","exams","focus","finals","inbox"].includes(REPORT.tab)?REPORT.tab:"list";
  const bar=`<div class="mx-report-bar"><div class="mx-report-views" role="group" aria-label="תצוגה">
      <button type="button" class="mx-btn" data-report-tab="list" aria-pressed="${view==="list"}">רשימה</button>
      <button type="button" class="mx-btn" data-report-tab="map" aria-pressed="${view==="map"}">מפת כיתה</button>
      <button type="button" class="mx-btn" data-report-tab="tasks" aria-pressed="${view==="tasks"}">${asgFull()?"משימות":"שיעורי בית"}</button>
      <button type="button" class="mx-btn" data-report-tab="subs" aria-pressed="${view==="subs"}">הגשות</button>
      <button type="button" class="mx-btn" data-report-tab="inbox" aria-pressed="${view==="inbox"}">📥 לבדיקה${INBOX_COUNT?.[REPORT.id]?` <span class="mx-aq-badge">${INBOX_COUNT[REPORT.id]}</span>`:""}</button>
      <button type="button" class="mx-btn" data-report-tab="focus" aria-pressed="${view==="focus"}">על מה לעבוד</button>
      <button type="button" class="mx-btn" data-report-tab="finals" aria-pressed="${view==="finals"}">בחנים מסכמים</button>
      <button type="button" class="mx-btn" data-report-tab="exams" aria-pressed="${view==="exams"}">מבחנים</button>
      <button type="button" class="mx-btn" data-act="preview-on" title="לראות את האפליקציה כמו שתלמיד בכיתה רואה אותה">הצגה כתלמיד</button></div>
    <label class="mx-small">מיון <select data-report-sort>${Object.entries(REPORT_SORTS).map(([k,v])=>`<option value="${k}"${k===sort?" selected":""}>${v}</option>`).join("")}</select></label>
    ${view==="map"&&!mapUnit?`<button type="button" class="mx-btn" data-heat-all="open">פתיחת הכול</button><button type="button" class="mx-btn" data-heat-all="close">קיפול הכול</button>`:""}
    ${view==="map"?`<label class="mx-small">יחידה <select data-report-unit><option value="overview">כל היחידות</option>${units.map(u=>`<option value="${esc(u.id)}"${u.id===REPORT.unit?" selected":""}>${esc(u.name)}</option>`).join("")}</select></label>`:""}</div>`;
  sheet.querySelector(".mx-report").innerHTML=bar+(view==="map"?`${mapLegend}<div class="mx-grid-wrap${mapUnit?"":" mx-heat-wrap"}" tabindex="0" role="region" aria-label="מפת הכיתה">${map}</div>`:view==="tasks"||view==="subs"?(REPORT.sub?wsSubHtml(name):view==="subs"?subsTabHtml(order,name):REPORT.form?(REPORT.form.focus?focusFormHtml(units,name):asgFormHtml(units)):asgTasksHtml(order,name))
    :view==="inbox"?(REPORT.sub?wsSubHtml(name):inboxHtml(name))
    :view==="exams"?examsTabHtml(units,all,name):view==="focus"?classFocusHtml(units,all,name):view==="finals"?finalsTabHtml(units,name):list);
  if((view==="tasks"||view==="subs"||view==="inbox")&&REPORT.sub) wsSubImages();
  if(REPORT.flash) sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",`<p class="mx-small mx-flash" role="status">${esc(REPORT.flash)}</p>`);   // until the next tab
}

/* ---------- the teacher's inbox (GET /api/teacher/inbox) ----------
   Everything of this class that waits for the teacher, oldest first: worksheets to check, quiz answers that need the
   teacher, requests to look again. Filters by kind, state and assignment or quiz; saving a check opens the next one. */
let INBOX_COUNT=null;
async function inboxCount(){
  try{ const r=await api("/api/teacher/inbox",{cache:"no-store"}); if(!r.ok) return; const d=await r.json();
    INBOX_COUNT={}; for(const e of d.entries) INBOX_COUNT[e.class_id]=(INBOX_COUNT[e.class_id]||0)+1; }catch{ return; }
  if(ACTIVE_SUBJECT==="מתמטיקה"&&root&&!root.hidden&&!cur) draw();
}
const INBOX_KIND={worksheet:"שיעורי בית",quiz:"תשובה בבוחן",request:"בקשה לבדיקה חוזרת"};
const INBOX_STATE={submitted:"ממתין לבדיקה",waiting:"עוד לא נבדק",unreadable:"ה־AI לא הצליח לקרוא",needs_review:"ה־AI ביקש מורה",ai_to_confirm:"ציון AI לאישור",request:"התלמיד/ה ביקש/ה"};
const inboxKey=e=>`${e.kind}:${e.submission_id||e.attempt_id}`;
const inboxItem=e=>e.assignment_id?`a:${e.assignment_id}`:e.window_id?`w:${e.window_id}`:e.unit_id?`u:${e.unit_id}`:"";
async function inboxLoad(){
  const id=REPORT.id;
  try{ const r=await api(`/api/teacher/inbox?class_id=${encodeURIComponent(id)}`,{cache:"no-store"}); const d=await r.json().catch(()=>({}));
    if(REPORT?.id!==id) return; REPORT.inboxData=r.ok?d:{error:true,entries:[]}; (INBOX_COUNT||={})[id]=r.ok?d.entries.length:0; }
  catch{ if(REPORT?.id===id) REPORT.inboxData={error:true,entries:[]}; }
  if(cur==="report"&&REPORT.tab==="inbox") drawReport();
}
function inboxList(){
  const f=REPORT.inboxFilter||={}, done=REPORT.inboxDone||=new Set();
  return (REPORT.inboxData?.entries||[]).filter(e=>!done.has(inboxKey(e))&&(!f.kind||e.kind===f.kind)&&(!f.state||e.state===f.state)&&(!f.item||inboxItem(e)===f.item));
}
function inboxHtml(name){
  if(!REPORT.inboxData){ inboxLoad(); return '<p class="mx-small" role="status">טוענים…</p>'; }
  if(REPORT.inboxData.error) return '<p class="mx-note">לא הצלחנו לטעון את מה שממתין לבדיקה.</p>';
  const all=REPORT.inboxData.entries, list=inboxList(), f=REPORT.inboxFilter;
  const items=new Map(all.filter(inboxItem).map(e=>[inboxItem(e),e.assignment||e.title.replace(/\s*·\s*שאלה\s*\d+$/,"")]));
  const opt=(key,value,label)=>`<option value="${esc(value)}"${f[key]===value?" selected":""}>${esc(label)}</option>`;
  return `<div class="mx-row mx-inbox-filters">
      <label class="mx-small">סוג <select data-inbox-filter="kind">${opt("kind","","הכול")}${Object.entries(INBOX_KIND).map(([k,v])=>opt("kind",k,v)).join("")}</select></label>
      <label class="mx-small">מצב <select data-inbox-filter="state">${opt("state","","הכול")}${Object.entries(INBOX_STATE).map(([k,v])=>opt("state",k,v)).join("")}</select></label>
      <label class="mx-small">משימה או בוחן <select data-inbox-filter="item">${opt("item","","הכול")}${[...items].map(([k,v])=>opt("item",k,v)).join("")}</select></label></div>
    ${REPORT.inboxData.unavailable?.length?'<p class="mx-small">חלק מהרשימה לא נטען עכשיו.</p>':""}
    ${list.length?`<p class="mx-small"><b>${list.length}</b> ממתינים לכם, הישן ביותר קודם. שמירה עוברת לבא בתור.</p><ol class="mx-inbox">${list.map(e=>`<li class="mx-inbox-row">
      <div><b dir="ltr">${esc(name(e.student_email))}</b> · ${esc(INBOX_KIND[e.kind])} <small>${fmt(e.title||"")}${e.assignment?` (${esc(e.assignment)})`:""}${e.version>1?" · מתוקן":""}</small>
        <p class="mx-small">${esc(shortDate(e.submitted_at))}${e.late?" · באיחור":""} · ${esc(INBOX_STATE[e.state]||e.state)}${e.note?` · "${esc(e.note)}"`:""}${e.message?` · "${esc(e.message)}"`:""}</p></div>
      <button type="button" class="mx-btn" data-inbox-open="${esc(inboxKey(e))}">פתיחה</button></li>`).join("")}</ol>`
      :`<p class="mx-note" role="status">${all.length?"אין מה לבדוק בסינון הזה.":"אין מה לבדוק. 🎉"}</p>`}`;
}
function inboxOpen(key){
  const e=(REPORT.inboxData?.entries||[]).find(x=>inboxKey(x)===key); if(!e) return;
  REPORT.inbox={key};
  if(e.kind==="worksheet"){ REPORT.sub={wid:e.worksheet_id,email:e.student_email,urls:[]}; drawReport(); return sheet.querySelector(".mx-ws-review [data-ws-sub-back]")?.focus(); }
  const id=REPORT.id;
  trOpenAnswer(e.attempt_id,"inbox");
  if(TR) TR.inbox={key,classId:id};
}
// the report's frame again, around the data it already has (back from a sheet opened over it)
function drawReportShell(){
  const mine=teachClasses(), classId=REPORT.id;
  const tabs=mine.length>1?`<div class="mx-report-tabs">${mine.map(row=>`<button class="mx-btn" data-report-class="${esc(row.id)}" aria-pressed="${String(row.id)===String(classId)}">${esc(row.name)}</button>`).join("")}</div>`:"";
  cur="report";
  sheet.innerHTML=`<div class="mx-scrim"></div>
    <div class="mx-sheet mx-manage-sheet mx-report-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-manage-head"><h3 id="mxTitle">הכיתה שלי</h3><span class="mx-manage-spacer"></span>
        <button class="mx-btn" data-report-class="${esc(classId)}">רענון</button><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      ${tabs}<p class="mx-manage-state" aria-live="polite"></p><div class="mx-report"></div></div>`;
  sheet.hidden=false;
}
// back from a quiz answer to the class's inbox (the report, kept as it was); `saved`: on to the next one
function inboxBack(saved=false){
  const kept=REPORT; dropReview();
  if(!kept) return closeSheet();
  REPORT=kept; REPORT.tab="inbox"; cur=null; drawReportShell();
  if(saved) return inboxAfterSave();
  REPORT.inbox=null; drawReport();
}
// after a save: this one is done, and the next one of the same filter opens (or the list, when none is left)
function inboxAfterSave(){
  const key=REPORT.inbox?.key; if(key) REPORT.inboxDone.add(key);
  const next=inboxList()[0];
  wsSubClose(); REPORT.inbox=null;
  if(INBOX_COUNT&&REPORT.id in INBOX_COUNT) INBOX_COUNT[REPORT.id]=Math.max(0,INBOX_COUNT[REPORT.id]-1);
  if(next) return inboxOpen(inboxKey(next));
  drawReport(); sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",'<p class="mx-small" role="status">סיימתם את כל מה שממתין בסינון הזה. 🎉</p>');
}

/* ---------- final unit quizzes, in the report (app/quiz_modes.py) ----------
   The class teacher opens a final quiz of a unit for a time, closes it early, gives one student another sitting, and
   releases the results. How far each window is comes from the students' sittings in the report (their window_id). */
const localInput=d=>{ const z=new Date(d.getTime()-d.getTimezoneOffset()*60000); return z.toISOString().slice(0,16); };
const whenShort=t=>new Date(t).toLocaleString("he-IL",{day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"});
async function finalsLoad(){
  const id=REPORT.id;
  try{ const r=await api(`/api/classes/${encodeURIComponent(id)}/quiz-windows`,{cache:"no-store"}); const d=await r.json().catch(()=>({}));
    if(REPORT?.id!==id) return; REPORT.finals=r.ok?d:{error:d.detail||"error"}; }
  catch{ if(REPORT?.id===id) REPORT.finals={error:"error"}; }
  if(cur==="report"&&REPORT.tab==="finals") drawReport();
}
function finalStats(w){
  const sittings=REPORT.data.students.flatMap(s=>(s.quiz_sittings||[]).filter(x=>x.window_id===w.id).map(x=>({s,x})));
  const started=(REPORT.finals?.starts||[]).filter(x=>x.window_id===w.id).length;
  return {started,handed:sittings.length,checked:sittings.filter(({x})=>x.grade!=null).length,sittings};
}
function finalsTabHtml(units,name){
  if(!REPORT.finals){ finalsLoad(); return '<p class="mx-small" role="status">טוענים…</p>'; }
  if(REPORT.finals.error) return `<p class="mx-note">${REPORT.finals.error==="quiz_modes_unavailable"?"מבחנים אינם זמינים עדיין באתר.":"לא הצלחנו לטעון את המבחנים."}</p>`;
  const quizUnits=units.filter(u=>u.quiz), now=Date.now(), start=new Date(Math.ceil(now/300000)*300000);
  const windows=(REPORT.finals.windows||[]).slice().sort((a,b)=>b.opens_at.localeCompare(a.opens_at));
  const students=REPORT.data.students;
  const card=w=>{ const u=G.units.find(x=>x.id===w.unit_id), st=finalStats(w), opens=Date.parse(w.opens_at), closes=Date.parse(w.closes_at);
    const state=now<opens?"מתוזמן":now<closes?"פתוח":"נסגר", grants=(REPORT.finals.grants||[]).filter(g=>g.window_id===w.id);
    return `<article class="mx-final-t" data-window="${esc(w.id)}"><h4>${esc(u?.name||w.unit_id)} · <span class="mx-report-chip${state==="פתוח"?" good":""}">${state}</span></h4>
      <p class="mx-small">${esc(whenShort(w.opens_at))} עד ${esc(whenShort(w.closes_at))} · התחילו <b>${st.started}</b> · הגישו <b>${st.handed}</b> מתוך ${students.length} · נבדקו במלואם <b>${st.checked}</b>
        ${w.released_at?` · <b>התוצאות פורסמו</b> ${esc(whenShort(w.released_at))}`:""}</p>
      <div class="mx-row">${state!=="נסגר"?`<button type="button" class="mx-btn" data-final-close="${esc(w.id)}">סגירה עכשיו</button>`:""}
        ${w.released_at?"":`<button type="button" class="mx-btn solid" data-final-release="${esc(w.id)}">פרסום תוצאות</button>`}
        ${st.handed?`<button type="button" class="mx-btn" data-batch="${esc(REPORT.id)}|window:${esc(w.id)}">שליחת כל הבוחן לבדיקה</button>`:""}</div>
      <p class="mx-small" role="status" aria-live="polite"></p>
      ${grants.length?`<p class="mx-small">ניסיון נוסף: ${grants.map(g=>`<span dir="ltr">${esc(name(g.student_email))}</span> עד ${esc(whenShort(g.until))}${g.reason?` (${esc(g.reason)})`:""}`).join(" · ")}</p>`:""}
      <details><summary>ניסיון נוסף לתלמיד/ה</summary><form class="mx-asg-form" data-final-grant="${esc(w.id)}" novalidate>
        <label>תלמיד/ה<select name="student">${students.map(s=>`<option value="${esc(s.email)}">${esc(name(s.email))}</option>`).join("")}</select></label>
        <label>עד<input type="datetime-local" name="until" value="${localInput(new Date(now+3*864e5))}"></label>
        <label>סיבה <small>(לא חובה)</small><input name="reason" maxlength="200" placeholder="למשל: נעדר/ה"></label>
        <div class="mx-row"><button type="submit" class="mx-btn">מתן ניסיון נוסף</button><span class="mx-small" role="status" aria-live="polite"></span></div></form></details></article>`; };
  return `<p class="mx-small">בוחן מסכם נעשה פעם אחת, והציון שלו הוא הציון של היחידה. בחני חיזוק לא משנים אותו.</p>
    ${quizUnits.length?`<form class="mx-asg-form" data-final-open novalidate><h4>פתיחת בוחן מסכם</h4>
      <label>יחידה<select name="unit">${quizUnits.map(u=>`<option value="${esc(u.id)}">${esc(u.name)} (${u.quiz.minutes} דק׳)</option>`).join("")}</select></label>
      <label>נפתח<input type="datetime-local" name="opens" value="${localInput(start)}"></label>
      <label>נסגר<input type="datetime-local" name="closes" value="${localInput(new Date(start.getTime()+90*60000))}"></label>
      <div class="mx-row"><button type="submit" class="mx-btn solid">פתיחה</button><span class="mx-small" role="status" aria-live="polite"></span></div></form>`:'<p class="mx-note">ליחידות של הכיתה אין בוחן מסכם.</p>'}
    ${windows.map(card).join("")||'<p class="mx-small">עוד לא נפתחו מבחנים.</p>'}`;
}
const FINAL_ERR={window_already_open:"כבר יש בוחן מסכם פתוח ליחידה הזאת.",quiz_modes_unavailable:"בחנים מסכמים אינם זמינים עדיין באתר."};
async function finalPost(path,body,status){
  const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/quiz-windows${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});
  const d=await r.json().catch(()=>({}));
  if(!r.ok) throw Error(FINAL_ERR[d.detail]||(typeof d.detail==="string"&&r.status===400?"בדקו את הפרטים: "+d.detail:"הפעולה נכשלה. נסו שוב."));
  return d;
}
async function finalAct(t){
  try{
    if(t.dataset.finalClose) await finalPost(`/${encodeURIComponent(t.dataset.finalClose)}/close`);
    else if(t.dataset.finalRelease){
      const w=(REPORT.finals.windows||[]).find(x=>x.id===t.dataset.finalRelease), st=finalStats(w), open=st.handed-st.checked;
      if(open&&!confirm(`${open===1?"בוחן אחד עוד לא נבדק":`${open} בחנים עוד לא נבדקו`} במלואו. לפרסם בכל זאת? התלמידים האלה יראו את הציון כשהבדיקה תסתיים.`)) return;
      await finalPost(`/${encodeURIComponent(w.id)}/release`);
    }
    REPORT.finals=null; drawReport();
  }catch(e){ alert(e.message); }
}
async function finalForm(form){
  const status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const iso=v=>v?new Date(v).toISOString():null;
  button.disabled=true; status.textContent="שומרים…";
  try{
    if(form.dataset.finalGrant) await finalPost(`/${encodeURIComponent(form.dataset.finalGrant)}/grants`,
      {student_email:form.elements.student.value,until:iso(form.elements.until.value),reason:form.elements.reason.value});
    else await finalPost("",{unit_id:form.elements.unit.value,opens_at:iso(form.elements.opens.value),closes_at:iso(form.elements.closes.value)});
    REPORT.finals=null; drawReport();
  }catch(e){ button.disabled=false; status.textContent=e.message; }
}

/* ---------- the class's exams, in the report: what each covers, and how ready the class is ----------
   The class teacher names an exam's units and a note (PUT /api/classes/{id}/exams/topics); the students' preparation
   view is built on them. For an exam with units: how many students finished each of its skills, and who is furthest. */
function examsTabHtml(units,all,name){
  const exams=(REPORT.data.class.exams||[]).filter(e=>e?.date&&e?.subject).slice().sort((a,b)=>a.date.localeCompare(b.date));
  const today=new Date(); today.setHours(0,0,0,0);
  const upcoming=exams.filter(e=>examDate(e.date)>=today), past=exams.filter(e=>examDate(e.date)<today);
  const n=all.length, done=(s,id)=>!!s.progress?.done?.[id];
  const subjects=[...new Set(["מתמטיקה",...exams.map(e=>e.subject)])];
  const add=`<form class="mx-asg-form mx-exam-add" data-exam-add novalidate><h4>הוספת מבחן ללוח המבחנים</h4>
      <div class="mx-row"><label>מקצוע<input name="subject" list="mx-exam-subjects" maxlength="40" value="מתמטיקה" required></label>
        <datalist id="mx-exam-subjects">${subjects.map(x=>`<option value="${esc(x)}">`).join("")}</datalist>
        <label>תאריך<input type="date" name="date" required></label></div>
      <fieldset><legend>החומר למבחן <small>(לא חובה)</small></legend><div class="mx-asg-checks">${units.map(u=>`<label><input type="checkbox" name="unit" value="${esc(u.id)}"> ${esc(u.name)}</label>`).join("")}</div></fieldset>
      <label>הערה לתלמידים <small>(לא חובה)</small><input name="note" maxlength="300"></label>
      <div class="mx-row"><button type="submit" class="mx-btn solid">הוספה</button><span class="mx-small" role="status" aria-live="polite"></span></div></form>`;
  const card=e=>{
    const chosen=new Set(e.units||[]), ids=units.filter(u=>chosen.has(u.id)).flatMap(u=>unitIds(u).filter(live));
    const days=Math.round((examDate(e.date)-today)/864e5);
    const ready=ids.length?`<details><summary>כמה הכיתה מוכנה</summary><table class="mx-report-table"><thead><tr><th>מיומנות</th><th>סיימו</th></tr></thead><tbody>${ids.map(id=>{
        const k=all.filter(x=>done(x.s,id)).length; return `<tr><td>${fmt(BY[id].short||BY[id].name)}</td><td class="mx-report-grade${k<n/2?" low":k<n?" mid":" good"}">${k}/${n}</td></tr>`; }).join("")}</tbody></table>
      <p class="mx-small"><b>הכי רחוקים מהחומר:</b> ${all.map(x=>({s:x.s,k:ids.filter(id=>done(x.s,id)).length})).sort((a,b)=>a.k-b.k).slice(0,5)
        .map(x=>`<span dir="ltr">${esc(name(x.s.email))}</span> (${x.k}/${ids.length})`).join(" · ")}</p></details>`
      :'<p class="mx-small">בחרו את היחידות של המבחן כדי לראות כמה הכיתה מוכנה, וכדי שהתלמידים יקבלו תוכנית הכנה.</p>';
    return `<article class="mx-exam-t"><div class="mx-row"><h4>${esc(e.subject)} · ${esc(examFullDate(e.date))} <small>${days===0?"היום":days===1?"מחר":`בעוד ${days} ימים`}</small></h4>
        <span class="mx-manage-spacer"></span><button type="button" class="mx-link" data-exam-del="${esc(e.subject)}|${esc(e.date)}">מחיקה</button></div>
      <form class="mx-asg-form" data-exam-form="${esc(e.subject)}|${esc(e.date)}" novalidate>
        <fieldset><legend>החומר למבחן</legend><div class="mx-asg-checks">${units.map(u=>`<label><input type="checkbox" name="unit" value="${esc(u.id)}"${chosen.has(u.id)?" checked":""}> ${esc(u.name)}</label>`).join("")}</div></fieldset>
        <label>הערה לתלמידים <small>(לא חובה, למשל "פרק 3 עד עמוד 80")</small><input name="note" maxlength="300" value="${esc(e.note||"")}"></label>
        <div class="mx-row"><button type="submit" class="mx-btn">שמירה</button><span class="mx-small" role="status" aria-live="polite"></span></div></form>
      ${ready}</article>`;
  };
  return `<p class="mx-small">לוח המבחנים של הכיתה: מה שהתלמידים רואים במסך המקצועות. מבחן הוא המבחן בבית הספר; לפניו התלמידים מקבלים תוכנית הכנה ומבחני תרגול.</p>
    ${upcoming.map(card).join("")||'<p class="mx-note">אין מבחנים קרובים בלוח.</p>'}
    ${add}
    ${past.length?`<details class="mx-exam-past"><summary>מבחנים שעברו (${past.length})</summary><ul class="mx-report-list">${past.slice().reverse().map(e=>`<li>${esc(e.subject)} · ${esc(examDay(e.date))}${(e.units||[]).length?` <small>(${e.units.map(id=>esc(G.units.find(u=>u.id===id)?.name||id)).join(", ")})</small>`:""}</li>`).join("")}</ul></details>`:""}`;
}
async function examAdd(form){
  const status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const body={subject:form.elements.subject.value,date:form.elements.date.value,units:[...form.querySelectorAll("[name=unit]:checked")].map(c=>c.value),note:form.elements.note.value};
  if(!body.subject.trim()){ status.textContent="כתבו מקצוע."; return form.elements.subject.focus(); }
  if(!body.date){ status.textContent="בחרו תאריך."; return form.elements.date.focus(); }
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/exams`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(r.status===409?"המבחן הזה כבר בלוח.":r.status===403?"רק מורה הכיתה יכול להוסיף מבחנים.":"ההוספה נכשלה. בדקו את הפרטים ונסו שוב.");
    REPORT.data.class.exams=[...(REPORT.data.class.exams||[]),d];
    REPORT.flash=`המבחן ב${d.subject} נוסף ללוח. התלמידים רואים אותו.`; drawReport();
  }catch(e){ button.disabled=false; status.textContent=e.message; }
}
async function examDelete(key){
  const [subject,date]=key.split("|");
  if(!confirm(`למחוק את המבחן ב${subject} (${examDay(date)}) מלוח המבחנים?`)) return;
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/exams?${new URLSearchParams({subject,date})}`,{method:"DELETE"});
    if(!r.ok) throw Error("המחיקה נכשלה.");
    REPORT.data.class.exams=(REPORT.data.class.exams||[]).filter(e=>!(e.subject===subject&&e.date===date));
    REPORT.flash="המבחן נמחק מהלוח."; drawReport();
  }catch(e){ alert(e.message); }
}
async function examSave(form){
  const [subject,date]=form.dataset.examForm.split("|"), status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const body={subject,date,units:[...form.querySelectorAll("[name=unit]:checked")].map(c=>c.value),note:form.elements.note.value};
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/exams/topics`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(r.status===403?"רק מורה הכיתה יכול לקבוע את החומר.":"השמירה נכשלה. נסו שוב.");
    REPORT.data.class.exams=(REPORT.data.class.exams||[]).map(e=>e.subject===subject&&e.date===date?d:e);
    drawReport(); sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",'<p class="mx-small" role="status">החומר למבחן נשמר. התלמידים רואים תוכנית הכנה.</p>');
  }catch(e){ button.disabled=false; status.textContent=e.message; }
}

/* ---------- the class's assignments, in the report (app/assignments.py) ----------
   The tab lists the class's assignments, how many students finished each and, for each student, which items are done
   (worked out by Sky.assignmentState from the progress and the server's quiz sittings, as on the student's own screen),
   and gives the teacher the form to make, change or delete one. */
const ASG_ERR={400:"אחד הפריטים אינו שייך ליחידות של הכיתה, או שהתאריך אינו תקין.",403:"רק מורה הכיתה יכול לתת לה משימות.",404:"הכיתה או המשימה לא נמצאו.",
  503:"המשימות אינן זמינות כרגע. נסו שוב מאוחר יותר."};
// focus practice counts only its chosen students (app/assignments.py); a class-wide assignment counts everyone
const asgFor=(a,s)=>!a.student_emails?.length||a.student_emails.includes(s.email);
const asgStates=(a,order)=>order.filter(({s})=>asgFor(a,s)).map(({s})=>({s,st:Sky.assignmentState(a,s.progress,wsServer(s))}));
function asgTasksHtml(order,name){
  const list=REPORT.data.assignments;
  if(list===null) return '<p class="mx-note">המשימות אינן זמינות כרגע באתר.</p>';
  const today=Sky.jerusalemDay(new Date());
  const cards=list.slice().sort((p,q)=>q.due_on.localeCompare(p.due_on)).map(a=>{
    const rows=asgStates(a,order), finished=rows.filter(x=>x.st.finished).length, past=today>a.due_on;
    const focus=a.student_emails?.length?`<p class="mx-small"><span class="mx-report-chip mid">אישי</span> תרגול ממוקד ל: ${a.student_emails.map(e=>`<span dir="ltr">${esc(name(e))}</span>`).join(", ")}</p>`:"";
    return `<article class="mx-asg-t${past?" past":""}"><div class="mx-asg-head"><b>${esc(a.title)}</b><span class="mx-asg-due">${past?"המועד עבר · ":""}עד ${asgDate(a.due_on)}</span></div>
      ${focus}${a.note?`<p class="mx-asg-note">${esc(a.note)}</p>`:""}
      <p class="mx-asg-count"><b>${finished}</b> מתוך ${rows.length} תלמידים סיימו</p>
      <ul class="mx-asg-items">${a.items.map(i=>`<li>${asgItemLabel(i)}</li>`).join("")}</ul>${wsSummaryHtml(a,order)}
      ${rows.length?`<details class="mx-asg-who"${rows.some(({st})=>st.items.some(x=>wsWaiting(x.submission)))?" open":""}><summary>מי עשה מה</summary><div class="mx-grid-wrap" tabindex="0" role="region" aria-label="מצב התלמידים במשימה"><table class="mx-grid">
        <thead><tr><th class="mx-grid-name" scope="col">תלמיד</th><th scope="col">מצב</th>${a.items.map(i=>`<th scope="col" class="mx-grid-unit">${asgItemLabel(i)}</th>`).join("")}</tr></thead><tbody>
        ${rows.map(({s,st})=>`<tr><th scope="row" class="mx-grid-name" dir="ltr">${esc(name(s.email))}</th><td class="mx-task-state" data-task="${Sky.assignmentTask(a,s.progress,wsServer(s)).state}">${Sky.assignmentTask(a,s.progress,wsServer(s)).label}</td>${st.items.map(x=>wsCellHtml(x,a,s)||
          `<td class="mx-asg-cell ${x.done?(x.late?"late":"ok"):x.known?"none":"unknown"}">${x.done?(x.late?"✓ באיחור":"✓"):x.known?"–":"?"}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div></details>`:""}
      <div class="mx-row"><button type="button" class="mx-btn" data-asg-edit="${esc(a.id)}"${a.student_emails?.length?" data-asg-focus":""}>עריכה</button>
        <button type="button" class="mx-btn" data-asg-del="${esc(a.id)}">מחיקה</button></div></article>`;
  }).join("");
  return `<div class="mx-row"><button type="button" class="mx-btn solid" data-asg-new>${asgFull()?"משימה חדשה":"שיעורי בית חדשים"}</button>
    <button type="button" class="mx-btn" data-asg-focus-new>🎯 תרגול ממוקד לתלמידים</button></div>
    ${cards||`<p class="mx-note">${asgFull()?"עוד לא נתתם משימות לכיתה. ":"עוד לא נתתם שיעורי בית לכיתה. "}${asgFull()?"משימה היא מיומנויות לסיים, בוחן מסכם להגיש, מבחן תרגול או שיעורי בית, עד תאריך.":"שיעורי בית הם PDF או תמונות שהתלמידים פותרים ומגישים עד תאריך יעד."}</p>`}`;
}
// a teacher gives worksheets only; the full picker (skills, unit quizzes, practice exams) is for developers
const asgFull=()=>can("management.access");
function asgFormHtml(units){
  const old=REPORT.data.assignments.find(x=>x.id===REPORT.form.id);
  const a=old||{title:"",note:"",due_on:new Date(Date.now()+7*864e5).toLocaleDateString("en-CA",{timeZone:"Asia/Jerusalem"}),items:[]};
  const skills=new Set(a.items.filter(i=>i.kind==="skill").map(i=>i.id)), quizzes=new Set(a.items.filter(i=>i.kind==="unit_quiz").map(i=>i.unit));
  const exam=new Set(a.items.find(i=>i.kind==="exam")?.units||[]);
  const box=(name,value,on,label)=>`<label><input type="checkbox" name="${name}" value="${esc(value)}"${on?" checked":""}> ${label}</label>`;
  return `<form class="mx-asg-form" data-asg-form="${esc(old?.id||"")}" novalidate><h4>${asgFull()?(old?"עריכת משימה":"משימה חדשה"):(old?"עריכת שיעורי בית":"שיעורי בית חדשים")}</h4>
    <label>כותרת<input name="title" maxlength="80" value="${esc(a.title)}" required></label>
    <label>הערה לתלמידים <small>(לא חובה)</small><textarea name="note" rows="2" maxlength="500">${esc(a.note)}</textarea></label>
    <label>תאריך יעד<input type="date" name="due_on" value="${esc(a.due_on)}" required></label>
    ${asgFull()?`<fieldset><legend>מיומנויות לסיים</legend>${units.map(u=>{ const ids=unitIds(u).filter(live);
      return `<details${ids.some(id=>skills.has(id))?" open":""}><summary>${esc(u.name)}</summary><div class="mx-asg-checks">${ids.map(id=>box("skill",id,skills.has(id),fmt(BY[id].short||BY[id].name))).join("")}</div></details>`; }).join("")}</fieldset>
    <fieldset><legend>בוחן חיזוק להגשה</legend><div class="mx-asg-checks">${units.filter(u=>u.quiz).map(u=>box("quiz",u.id,quizzes.has(u.id),esc(u.name))).join("")||"<small>ליחידות של הכיתה אין בוחן מסכם.</small>"}</div></fieldset>
    <fieldset><legend>${TERMS.mixed} על היחידות</legend><div class="mx-asg-checks">${units.map(u=>box("exam",u.id,exam.has(u.id),esc(u.name))).join("")}</div>
      <small>מי שיסמן כמה יחידות יבקש ${TERMS.mixed} שכולל את כולן.</small></fieldset>`:""}
    ${wsFieldHtml(old)||(asgFull()?"":'<p class="mx-note">שיעורי הבית אינם זמינים כרגע, ולכן אי אפשר לשמור אותם.</p>')}
    <div class="mx-row"><button type="submit" class="mx-btn solid">שמירה</button><button type="button" class="mx-btn" data-asg-cancel>ביטול</button>
      <span class="mx-small" role="status" aria-live="polite"></span></div></form>`;
}
/* Focus practice (app/assignments.py): a class teacher gives 1 to 5 skills to chosen students. Opened empty, or with
   skills and students already chosen (from a student's or the class's focus areas). */
const FOCUS_MAX=5;
/* ---------- focus areas (Sky.focus): where each student, and the class, most need work ----------
   Each skill comes with its evidence in words, and each piece of evidence says where it comes from: unit-quiz points
   are checked by the server; practice answers, misconceptions and fading are what the student's device reports. */
const DEVICE_TAG='<small class="mx-device">· מהמכשיר</small>';
const classSkillIds=units=>units.flatMap(u=>unitIds(u).filter(live));
// quiz points lost are the server's evidence: they count even for a student whose device has reported nothing yet
const focusOf=(s,units)=>Sky.focus(s.progress||{},s.quiz_sittings,classSkillIds(units)).slice(0,Sky.FOCUS.TOP);
function focusEvidence(f){
  const quiz=f.lost?[`איבד ${Math.round(f.lost)} נק׳ בבחנים`]:[];
  const device=[f.wrong?`${f.wrong} טעויות ב־14 ימים`:"",f.unfinished?"לא הושלם":"",f.fading?"דועך":""].filter(Boolean);
  return [quiz.join(""),device.length?`${device.join(" · ")} ${DEVICE_TAG}`:""].filter(Boolean).join(" · ");
}
function focusCardHtml(s,r,units){
  const top=focusOf(s,units), rec=r.recurring||[];
  if(!top.length&&!rec.length) return `<section class="mx-focus"><h5>🎯 על מה לעבוד</h5><p class="mx-small">אין כרגע מיומנות שצריך לחזק.</p></section>`;
  return `<section class="mx-focus"><h5>🎯 על מה לעבוד</h5>
    ${top.length?`<ol class="mx-focus-list">${top.map(f=>`<li><b>${fmt(BY[f.id].short||BY[f.id].name)}</b> <small>${focusEvidence(f)}</small>
      <button type="button" class="mx-link" data-focus-give="${esc(f.id)}" data-focus-to="${esc(s.email)}">לתת תרגול</button></li>`).join("")}</ol>`:""}
    ${rec.length?`<p class="mx-small"><b>טעויות שחוזרות</b> ${DEVICE_TAG}</p><ul class="mx-focus-list">${rec.map(x=>`<li>${fmt(G.mistakes[x.m].name)} · ${x.n} פעמים ב־${x.skills.length} מיומנויות${BY[x.practise]?` · לחזק: ${fmt(BY[x.practise].short||BY[x.practise].name)} <button type="button" class="mx-link" data-focus-give="${esc(x.practise)}" data-focus-to="${esc(s.email)}">לתת תרגול</button>`:""}</li>`).join("")}</ul>`:""}</section>`;
}
// the class: the skills most students list among their focus areas, and the misconceptions recurring in most students
function classFocusHtml(units,all,name){
  const bySkill={}, byMistake={};
  for(const {s,r} of all){
    for(const f of focusOf(s,units)) (bySkill[f.id]||=[]).push(s.email);
    for(const x of r?.recurring||[]) (byMistake[x.m]||=[]).push(s.email);
  }
  const skills=Object.entries(bySkill).sort((a,b)=>b[1].length-a[1].length).slice(0,5);
  const mistakes=Object.entries(byMistake).filter(([m])=>G.mistakes[m]).sort((a,b)=>b[1].length-a[1].length).slice(0,3);
  const who=list=>`<details><summary>${list.length===1?"תלמיד/ה אחד/ת":`${list.length} תלמידים`}</summary><p class="mx-small">${list.map(e=>`<span dir="ltr">${esc(name(e))}</span>`).join(" · ")}</p></details>`;
  if(!skills.length&&!mistakes.length) return '<p class="mx-note">אין כרגע מיומנות או טעות שחוזרת אצל כמה תלמידים.</p>';
  return `<p class="mx-small">מה הכיתה צריכה לחזק: המיומנויות שהכי הרבה תלמידים צריכים לעבוד עליהן (לפי ניקוד הבחנים מהשרת ונתוני התרגול מהמכשיר), והטעויות שחוזרות אצל הכי הרבה תלמידים.</p>
    ${skills.length?`<section class="mx-focus"><h5>מיומנויות לחזק</h5><ol class="mx-focus-list">${skills.map(([id,list])=>`<li><b>${fmt(BY[id].short||BY[id].name)}</b> · ${list.length} תלמידים
      <button type="button" class="mx-btn" data-focus-give="${esc(id)}" data-focus-to="${esc(list.join(","))}">לתת תרגול</button>${who(list)}</li>`).join("")}</ol></section>`:""}
    ${mistakes.length?`<section class="mx-focus"><h5>טעויות שחוזרות ${DEVICE_TAG}</h5><ol class="mx-focus-list">${mistakes.map(([m,list])=>`<li><b>${fmt(G.mistakes[m].name)}</b> · ${list.length} תלמידים
      ${BY[G.mistakes[m].back]?`<button type="button" class="mx-btn" data-focus-give="${esc(G.mistakes[m].back)}" data-focus-to="${esc(list.join(","))}">לתת תרגול: ${fmt(BY[G.mistakes[m].back].short||BY[G.mistakes[m].back].name)}</button>`:""}${who(list)}</li>`).join("")}</ol></section>`:""}`;
}
// on a student's card: the focus practice given to them, and how far they are
function focusOfHtml(s){
  const mine=(REPORT.data.assignments||[]).filter(a=>a.student_emails?.includes(s.email)); if(!mine.length) return "";
  return `<section><h5>🎯 תרגול ממוקד</h5><ul class="mx-report-list">${mine.map(a=>{ const st=Sky.assignmentState(a,s.progress,wsServer(s));
    return `<li><b>${esc(a.title)}</b> <small>עד ${asgDate(a.due_on)} · ${st.finished?(st.late?"הושלם באיחור":"הושלם"):st.overdue?"באיחור":`${st.doneCount} מתוך ${st.total}`}</small></li>`; }).join("")}</ul></section>`;
}
function focusOpen(skills=[],emails=[]){
  REPORT.tab="tasks"; REPORT.sub=null; REPORT.form={id:null,focus:true,skills,emails};
  drawReport(); sheet.querySelector(".mx-asg-form input[name=title]")?.focus();
}
function focusFormHtml(units,name){
  const old=(REPORT.data.assignments||[]).find(x=>x.id===REPORT.form.id);
  const skills=new Set(old?old.items.filter(i=>i.kind==="skill").map(i=>i.id):REPORT.form.skills||[]);
  const chosen=new Set(old?old.student_emails||[]:REPORT.form.emails||[]);
  const due=old?.due_on||new Date(Date.now()+7*864e5).toLocaleDateString("en-CA",{timeZone:"Asia/Jerusalem"});
  const title=old?.title??(skills.size===1?`חיזוק: ${BY[[...skills][0]]?.short||BY[[...skills][0]]?.name||""}`:"תרגול ממוקד");
  return `<form class="mx-asg-form" data-focus-form="${esc(old?.id||"")}" novalidate><h4>${old?"עריכת תרגול ממוקד":"תרגול ממוקד לתלמידים"}</h4>
    <p class="mx-small">רק התלמידים שתבחרו יראו את המשימה, והדוח סופר רק אותם. אפשר לבחור עד ${FOCUS_MAX} מיומנויות.</p>
    <label>כותרת<input name="title" maxlength="80" value="${esc(title)}" required></label>
    <label>הערה לתלמידים <small>(לא חובה)</small><textarea name="note" rows="2" maxlength="500">${esc(old?.note||"")}</textarea></label>
    <label>תאריך יעד<input type="date" name="due_on" value="${esc(due)}" required></label>
    <fieldset><legend>תלמידים</legend><div class="mx-asg-checks">${REPORT.data.students.map(s=>`<label><input type="checkbox" name="student" value="${esc(s.email)}"${chosen.has(s.email)?" checked":""}> <span dir="ltr">${esc(name(s.email))}</span></label>`).join("")}</div></fieldset>
    <fieldset><legend>מיומנויות לתרגל</legend>${units.map(u=>{ const ids=unitIds(u).filter(live);
      return `<details${ids.some(id=>skills.has(id))?" open":""}><summary>${esc(u.name)}</summary><div class="mx-asg-checks">${ids.map(id=>`<label><input type="checkbox" name="skill" value="${esc(id)}"${skills.has(id)?" checked":""}> ${fmt(BY[id].short||BY[id].name)}</label>`).join("")}</div></details>`; }).join("")}</fieldset>
    <div class="mx-row"><button type="submit" class="mx-btn solid">שמירה</button><button type="button" class="mx-btn" data-asg-cancel>ביטול</button>
      <span class="mx-small" role="status" aria-live="polite"></span></div></form>`;
}
async function focusSave(form){
  const id=form.dataset.focusForm, status=form.querySelector(":scope>.mx-row>[role=status]"), button=form.querySelector("[type=submit]"), classId=REPORT.id;
  const picked=n=>[...form.querySelectorAll(`[name=${n}]:checked`)].map(c=>c.value);
  const body={title:form.elements.title.value,note:form.elements.note.value,due_on:form.elements.due_on.value,
    items:picked("skill").map(v=>({kind:"skill",id:v})),student_emails:picked("student")};
  if(!body.title.trim()){ status.textContent="כתבו כותרת."; return form.elements.title.focus(); }
  if(!body.student_emails.length){ status.textContent="בחרו לפחות תלמיד אחד."; return; }
  if(!body.items.length||body.items.length>FOCUS_MAX){ status.textContent=`בחרו בין מיומנות אחת ל־${FOCUS_MAX} מיומנויות.`; return; }
  if(!body.due_on){ status.textContent="בחרו תאריך יעד."; return; }
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/assignments${id?`/${encodeURIComponent(id)}`:""}`,
      {method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(d.detail==="audience_unavailable"?"תרגול ממוקד אינו זמין עדיין באתר.":typeof d.detail==="string"&&r.status===400?"לא הצלחנו לשמור: בדקו את התלמידים והמיומנויות.":ASG_ERR[r.status]||"השמירה נכשלה. נסו שוב.");
    if(cur!=="report"||REPORT?.id!==classId) return;
    const list=REPORT.data.assignments||[];
    REPORT.data.assignments=id?list.map(x=>x.id===id?d:x):[d,...list];
    REPORT.form=null; drawReport();
    sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",`<p class="mx-small" role="status">התרגול הממוקד נשמר. ${d.student_emails.length===1?"התלמיד/ה רואה":"התלמידים שבחרתם רואים"} אותו בבית.</p>`);
  }catch(e){ if(cur==="report"){ button.disabled=false; status.textContent=e.message; } }
}
async function asgSave(form){
  const id=form.dataset.asgForm, status=form.querySelector(":scope>.mx-row>[role=status]"), button=form.querySelector("[type=submit]"), classId=REPORT.id;   // the save's own line, not the worksheet upload's
  const picked=name=>[...form.querySelectorAll(`[name=${name}]:checked`)].map(c=>c.value);
  const items=[...picked("skill").map(v=>({kind:"skill",id:v})),...picked("quiz").map(v=>({kind:"unit_quiz",unit:v}))];
  if(picked("exam").length) items.push({kind:"exam",units:picked("exam")});
  if(!asgFull()) items.push(...(REPORT.data.assignments.find(x=>x.id===id)?.items||[]).filter(i=>i.kind!=="worksheet"));   // kept as they were
  const before=(REPORT.data.assignments.find(x=>x.id===id)?.items||[]).filter(i=>i.kind==="worksheet").map(i=>i.id);
  // without the worksheet list (not available), the assignment keeps the worksheets it had
  for(const w of REPORT.form?.sheets||before.map(wid=>({id:wid}))) items.push({kind:"worksheet",id:w.id});
  const body={title:form.elements.title.value,note:form.elements.note.value,due_on:form.elements.due_on.value,items};
  if(!body.title.trim()){ status.textContent="כתבו כותרת למשימה."; form.elements.title.focus(); return; }
  if(!body.due_on){ status.textContent="בחרו תאריך להגשה."; return; }
  if(!items.length){ status.textContent=asgFull()?"בחרו לפחות פריט אחד: מיומנות, בוחן חיזוק, ${TERMS.mixed} או שיעורי בית.":"העלו שיעורי בית אחד לפחות."; return; }
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/assignments${id?`/${encodeURIComponent(id)}`:""}`,
      {method:id?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(d.detail==="teachers_give_worksheets_only"?"מורה נותן שיעורי בית בלבד.":ASG_ERR[r.status]||"השמירה נכשלה. נסו שוב.");
    if(cur!=="report"||REPORT?.id!==classId) return;
    const list=REPORT.data.assignments||[];
    REPORT.data.assignments=id?list.map(x=>x.id===id?d:x):[d,...list];
    wsAfterSave(before,d.items.filter(i=>i.kind==="worksheet").map(i=>i.id));
    REPORT.form=null; drawReport();
    sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",`<p class="mx-small" role="status">${id?"המשימה עודכנה.":"המשימה נשמרה. התלמידים רואים אותה בבית."}</p>`);
  }catch(e){ if(cur==="report"){ button.disabled=false; status.textContent=e.message; } }
}
async function asgDelete(id){
  const a=REPORT.data.assignments.find(x=>x.id===id); if(!a) return;
  const started=REPORT.data.students.filter(s=>Sky.assignmentState(a,s.progress,wsServer(s)).doneCount>0).length;
  const sheets=a.items.filter(i=>i.kind==="worksheet").map(i=>i.id), handed=REPORT.data.students.filter(s=>(s.worksheet_submissions||[]).some(x=>sheets.includes(x.worksheet_id))).length;
  if(!confirm(`למחוק את המשימה "${a.title}"? התלמידים לא יראו אותה יותר.${started?` ${started} תלמידים כבר השלימו לפחות פריט אחד ממנה.`:""}${handed?` ${handed} תלמידים הגישו דפי עבודה, וההגשות יימחקו.`:""}`)) return;
  const classId=REPORT.id;
  try{
    const r=await api(`/api/classes/${encodeURIComponent(classId)}/assignments/${encodeURIComponent(id)}`,{method:"DELETE"});
    if(!r.ok) throw Error(ASG_ERR[r.status]||"המחיקה נכשלה. נסו שוב.");
    if(cur!=="report"||REPORT?.id!==classId) return;
    REPORT.data.assignments=REPORT.data.assignments.filter(x=>x.id!==id); wsAfterSave(sheets,[]); drawReport();
  }catch(e){ if(cur==="report") sheet.querySelector(".mx-manage-state").textContent=e.message; }
}
/* ---------- worksheets on assignments (app/worksheets.py) ----------
   The teacher uploads a PDF or photos from the assignment form; it becomes a {kind:"worksheet", id} item when the
   assignment is saved. Students open its pages (rendered on the server) from the card, and hand in photos of their
   solution, which they can replace until the teacher checks. The teacher checks each submission from the report's
   "משימות" tab: a score and a comment, both optional. */
const WS_ERR={too_many_pages:"אפשר עד 10 עמודים.",pdf_too_large:"הקובץ גדול מדי (עד 10MB).",file_too_large:"הקובץ גדול מדי.",
  image_too_large:"תמונה גדולה מדי (עד 5MB).",not_a_pdf:"הקובץ אינו PDF תקין.",unreadable_pdf:"לא הצלחנו לקרוא את ה־PDF. אם הוא מוגן בסיסמה, שמרו עותק בלי סיסמה.",
  pdf_too_slow:"ה־PDF כבד מדי לעיבוד. נסו לשמור אותו מחדש, או להעלות צילומים.",unsupported_image:"אפשר להעלות PDF או תמונות (JPEG, PNG, WebP).",
  empty_image:"הקובץ ריק.",one_pdf_or_photos:"העלו PDF אחד, או תמונות, לא את שניהם יחד.",no_files:"בחרו קובץ.",
  worksheets_unavailable:"שיעורי הבית אינם זמינים כרגע. נסו שוב מאוחר יותר.",already_checked:"המורה כבר בדק/ה את ההגשה, ולכן אי אפשר להחליף אותה.",
  worksheet_in_use:"שיעורי הבית כבר נשמרו במשימה.",
  open_ended_locked:"בדיקת AI נעולה כרגע.",grading_unavailable:"בדיקה אוטומטית אינה זמינה כרגע באתר.",
  teacher_ai_limit:"הגעתם למכסה של 3 בקשות AI ביום. אפשר לבדוק ידנית, או לנסות שוב מחר."};
const wsError=(r,fallback)=>WS_ERR[typeof r.data?.detail==="string"?r.data.detail:""]||(r.status===0?"אין חיבור לשרת. בדקו את החיבור ונסו שוב.":r.status===403?"אין לכם הרשאה לפעולה הזו.":r.status===404?"שיעורי הבית לא נמצאו.":fallback);
// a form sent with upload progress (fetch has none)
function sendForm(url,method,body,onProgress){
  return new Promise(resolve=>{
    const x=new XMLHttpRequest(); x.open(method,url);
    if(CFG.token) x.setRequestHeader("Authorization",`Bearer ${CFG.token}`);
    x.upload.onprogress=e=>{ if(e.lengthComputable) onProgress?.(e.loaded/e.total); };
    x.onload=()=>{ let data={}; try{ data=JSON.parse(x.responseText); }catch{} resolve({ok:x.status>=200&&x.status<300,status:x.status,data}); };
    x.onerror=x.ontimeout=()=>resolve({ok:false,status:0,data:{}});
    x.send(body);
  });
}
// a photo made smaller on the phone before it is sent; the file itself when that fails and it is an image we take
async function wsPrepare(file){
  let blob=null;
  try{ blob=await window.MathlyPhoto.prepare(file); }catch{}
  if(!blob&&["image/jpeg","image/png","image/webp"].includes(file.type)) blob=file;
  return blob&&blob.size<=5000000?blob:null;
}
const wsAll=()=>[...(REPORT?.data?.worksheets||[]),...(REPORT?.form?.sheets||[]),...(ASG?.worksheets||[])];
const wsInfo=id=>wsAll().find(w=>w.id===id)||null;
const wsTitle=id=>wsInfo(id)?.title||"שיעורי בית";
const wsWhen=t=>new Date(t).toLocaleString("he-IL",{day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit",timeZone:"Asia/Jerusalem"});
// a submission waits for the teacher while it is handed in and neither checked nor returned
const wsWaiting=x=>!!x&&(x.state||(x.checked_at?"checked":"submitted"))==="submitted";
const wsDue=(sub,a)=>{ const back=sub?.state==="returned"?sub.return_due_on:(sub?.earlier||[]).find(e=>e.return_due_on)?.return_due_on; return back&&back>a.due_on?back:a.due_on; };
const wsLate=(sub,a)=>!!sub&&sub.state!=="returned"&&Sky.jerusalemDay(sub.submitted_at)>wsDue(sub,a);
const wsWhenShort=t=>new Date(t).toLocaleString("he-IL",{day:"numeric",month:"numeric",hour:"2-digit",minute:"2-digit"});
// earlier versions of a hand-in (returned for a fix): what was handed in and what the teacher wrote
function wsEarlierHtml(sub){
  const list=sub?.earlier||[]; if(!list.length) return "";
  return `<details class="mx-ws-earlier"><summary>הגשות קודמות (${list.length})</summary><ul>${list.map(e=>`<li>גרסה ${e.version} · הוגש ${esc(wsWhenShort(e.submitted_at))} · ${e.pages} עמ׳
    ${e.note?`<br><small>ההערה שלך: ${esc(e.note)}</small>`:""}${e.return_comment?`<br><b>הוחזר לתיקון:</b> ${esc(e.return_comment)}`:""}</li>`).join("")}</ul></details>`;
}
const wsServer=s=>({sittings:s.quiz_sittings,submissions:s.worksheet_submissions});
const wsHanded=id=>(REPORT?.data?.students||[]).filter(s=>(s.worksheet_submissions||[]).some(x=>x.worksheet_id===id)).length;
async function wsBlob(url){ try{ const r=await api(url); return r.ok?URL.createObjectURL(await r.blob()):null; }catch{ return null; } }

// ---- the teacher: in the assignment form
function wsListHtml(){
  const list=REPORT.form?.sheets||[];
  return list.map(w=>`<li><span>📄 <b>${esc(w.title)}</b> <small>${w.pages} עמ׳ · ${w.source==="pdf"?"PDF":"תמונות"}</small></span>
    <button type="button" class="mx-link" data-ws-remove="${esc(w.id)}">הסרה</button></li>`).join("");
}
function wsFieldHtml(old){
  if(!Array.isArray(REPORT.data.worksheets)) return "";   // the worksheet tables are not there: no worksheets
  if(!REPORT.form.sheets) REPORT.form.sheets=(old?.items||[]).filter(i=>i.kind==="worksheet").map(i=>wsInfo(i.id)||{id:i.id,title:"שיעורי בית",pages:"?",source:""});
  return `<fieldset class="mx-ws-field"><legend>שיעורי בית</legend>
    <ul class="mx-ws-list" data-ws-list>${wsListHtml()}</ul>
    <div class="mx-ws-add"><label>שם שיעורי הבית<input name="ws_title" maxlength="80" autocomplete="off" placeholder="למשל: שיעורי בית – פיתגורס"></label>
      <label>קובץ<input type="file" name="ws_files" accept="application/pdf,.pdf,image/jpeg,image/png,image/webp" multiple></label>
      <div class="mx-row"><button type="button" class="mx-btn" data-ws-upload>העלאה</button>
        <progress max="1" value="0" hidden data-ws-progress></progress><span class="mx-small" data-ws-status role="status" aria-live="polite"></span></div></div>
    <small>PDF אחד של עד 10 עמודים, או עד 10 תמונות. אפשר להוסיף כמה שיעורי בית שרוצים. התלמידים פותחים אותם, מצלמים את הפתרון ומגישים עד תאריך היעד, ואתם בודקים בלשונית שיעורי בית או הגשות.</small></fieldset>`;
}
async function wsUpload(button){
  const form=button.closest("form"), status=form.querySelector("[data-ws-status]"), bar=form.querySelector("[data-ws-progress]");
  const title=form.elements.ws_title.value.trim(), files=[...form.elements.ws_files.files], classId=REPORT.id, mine=REPORT.form;
  const pdfs=files.filter(f=>f.type==="application/pdf"||/\.pdf$/i.test(f.name));
  if(!title){ status.textContent="כתבו שם לשיעורי הבית."; return form.elements.ws_title.focus(); }
  if(!files.length){ status.textContent="בחרו PDF או תמונות."; return form.elements.ws_files.focus(); }
  if(pdfs.length&&files.length>1){ status.textContent=WS_ERR.one_pdf_or_photos; return; }
  if(files.length>10){ status.textContent="אפשר עד 10 תמונות."; return; }
  button.disabled=true; status.textContent="מכינים…";
  const body=new FormData(); body.append("title",title);
  if(pdfs.length) body.append("files",files[0],files[0].name||"worksheet.pdf");
  else for(const [i,f] of files.entries()){
    const blob=await wsPrepare(f);
    if(!blob){ button.disabled=false; status.textContent=`לא הצלחנו להכין את התמונה ${i+1}. נסו תמונה אחרת.`; return; }
    body.append("files",blob,`page${i+1}.jpg`);
  }
  status.textContent="מעלים…"; bar.hidden=false; bar.value=0;
  const r=await sendForm(`/api/classes/${encodeURIComponent(classId)}/worksheets`,"POST",body,p=>bar.value=p);
  if(cur!=="report"||REPORT?.form!==mine) return;
  button.disabled=false; bar.hidden=true;
  if(!r.ok){ status.textContent=wsError(r,"ההעלאה נכשלה. נסו שוב."); return; }
  mine.sheets=[...(mine.sheets||[]),r.data];
  form.querySelector("[data-ws-list]").innerHTML=wsListHtml();
  form.elements.ws_title.value=""; form.elements.ws_files.value="";
  status.textContent=`"${r.data.title}" הועלו (${r.data.pages} עמ׳). התלמידים יראו אותם כשתשמרו.`;
}
function wsRemove(id){
  const mine=REPORT.form, old=REPORT.data.assignments.find(x=>x.id===mine.id), saved=(old?.items||[]).some(i=>i.kind==="worksheet"&&i.id===id);
  const n=saved?wsHanded(id):0;
  if(n&&!confirm(`להסיר את "${wsTitle(id)}"? ${n} תלמידים כבר הגישו אותו, וההגשות שלהם יימחקו כשתשמרו את המשימה.`)) return;
  mine.sheets=(mine.sheets||[]).filter(w=>w.id!==id);
  const list=sheet.querySelector("[data-ws-list]"); if(list) list.innerHTML=wsListHtml();
  if(!saved) api(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(id)}`,{method:"DELETE"}).catch(()=>{});   // not saved yet: gone now
}
// the form closed without saving: worksheets uploaded in it, and not in the assignment, go now (else the hourly cleanup)
function wsCancel(){
  const old=REPORT.data.assignments.find(x=>x.id===REPORT.form?.id), kept=new Set((old?.items||[]).filter(i=>i.kind==="worksheet").map(i=>i.id));
  for(const w of REPORT.form?.sheets||[]) if(!kept.has(w.id))
    api(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(w.id)}`,{method:"DELETE"}).catch(()=>{});
}
// after a save: the report knows the assignment's worksheets, and forgets those it lost
function wsAfterSave(before,after){
  const gone=new Set(before.filter(id=>!after.includes(id)));
  const known=(REPORT.data.worksheets||[]).filter(w=>!gone.has(w.id));
  for(const w of REPORT.form?.sheets||[]) if(after.includes(w.id)&&!known.some(k=>k.id===w.id)) known.push(w);
  if(Array.isArray(REPORT.data.worksheets)) REPORT.data.worksheets=known;
  for(const s of REPORT.data.students) if(s.worksheet_submissions) s.worksheet_submissions=s.worksheet_submissions.filter(x=>!gone.has(x.worksheet_id));
}

// ---- the teacher: in the report's assignments tab
function wsSummaryHtml(a,order){
  return a.items.filter(i=>i.kind==="worksheet").map(i=>{
    if(order.some(({s})=>s.worksheet_submissions==null)) return `<p class="mx-ws-sum">📄 ${esc(wsTitle(i.id))}: ההגשות אינן זמינות כרגע.</p>`;
    const subs=order.map(({s})=>s.worksheet_submissions.find(x=>x.worksheet_id===i.id)).filter(Boolean);
    const late=subs.filter(x=>wsLate(x,a)).length, waiting=subs.filter(wsWaiting).length, back=subs.filter(x=>x.state==="returned").length;
    return `<p class="mx-ws-sum">📄 <b>${esc(wsTitle(i.id))}</b>: הגישו <b>${subs.length}</b> מתוך ${order.length}${late?` (${late} באיחור)`:""} · ${order.length-subs.length} לא הגישו · <span class="${waiting?"mx-ws-wait":""}">${waiting} ממתינים לבדיקה</span>${back?` · ${back} הוחזרו לתיקון`:""}</p>`;
  }).join("");
}
function wsCellHtml(x,a,s){
  const sub=x.submission;
  if(!sub) return null;
  const label=sub.state==="returned"?"↩ הוחזר":sub.checked_at?(sub.score!=null?`✔ ${sub.score}`:"✔ נבדק"):sub.version>1?"לבדיקה (מתוקן)":"לבדיקה";
  return `<td class="mx-asg-cell ${x.late?"late":"ok"}"><button type="button" class="mx-link mx-ws-cell${wsWaiting(sub)?" wait":""}" data-ws-sub="${esc(sub.worksheet_id)}|${esc(s.email)}">${x.late?"באיחור · ":""}${label}</button></td>`;
}
function wsSubOpen(key){
  const [wid,email]=key.split("|");
  REPORT.sub={wid,email,urls:[]}; drawReport();
  sheet.querySelector(".mx-ws-review [data-ws-sub-back]")?.focus();
}
function wsSubClose(){ for(const u of REPORT?.sub?.urls||[]) if(u) URL.revokeObjectURL(u); if(REPORT) REPORT.sub=null; }
function wsSubHtml(name){
  const {wid,email}=REPORT.sub, s=REPORT.data.students.find(x=>x.email===email);
  const sub=(s?.worksheet_submissions||[]).find(x=>x.worksheet_id===wid);
  const a=REPORT.data.assignments.find(x=>x.items.some(i=>i.kind==="worksheet"&&i.id===wid));
  if(!s||!sub) return `<div class="mx-ws-review"><button type="button" class="mx-btn" data-ws-sub-back>חזרה למשימות</button><p class="mx-note">ההגשה לא נמצאה.</p></div>`;
  return `<div class="mx-ws-review"><div class="mx-row"><button type="button" class="mx-btn" data-ws-sub-back>חזרה למשימות</button></div>
    <h4>${esc(wsTitle(wid))} · <span dir="ltr">${esc(name(email))}</span></h4>
    <p class="mx-small">הוגש ${esc(wsWhen(sub.submitted_at))}${a&&wsLate(sub,a)?' · <b class="mx-ws-late">באיחור</b>':""} · ${sub.pages} עמ׳${sub.version>1?` · גרסה ${sub.version} (אחרי תיקון)`:""}${sub.checked_at&&sub.state!=="returned"?` · נבדק ${esc(wsWhen(sub.checked_at))}`:""}${sub.state==="returned"?" · <b>הוחזר לתיקון</b>":""}</p>
    ${sub.note?`<p class="mx-ws-note-shown"><b>הערה מהתלמיד/ה:</b> ${esc(sub.note)}</p>`:""}
    ${wsEarlierHtml(sub)}
    <div class="mx-ws-pages">${Array.from({length:sub.pages},(_,i)=>`<a class="mx-ws-page" data-ws-sublink="${i}" target="_blank" rel="noopener" aria-label="עמוד ${i+1} בגודל מלא"><img data-ws-subimg="${i}" alt="עמוד ${i+1} של ההגשה"></a>`).join("")}</div>
    <div class="mx-row"><button type="button" class="mx-btn" data-ws-ai="${esc(sub.id)}">🤖 בדיקה עם AI</button>
      <span class="mx-small" data-ws-ai-status role="status" aria-live="polite">${CFG.aiLeft!=null?`נשארו לכם היום ${CFG.aiLeft} מתוך 3 בקשות AI. `:""}ה־AI מציע ציון והערה, ואתם מאשרים או מתקנים.</span></div>
    ${sub.ai?`<p class="mx-ws-ai">🤖 <b>הצעת ה־AI${sub.ai.readable===false?" (לא הצליח לקרוא)":""}:</b> ${sub.ai.score!=null?`${sub.ai.score} · `:""}${esc(sub.ai.comment||"")}
      <button type="button" class="mx-link" data-ws-ai-fill="${esc(sub.id)}">להכניס לטופס</button> <small>(התלמיד/ה לא רואה אותה עד שתשמרו)</small></p>`:""}
    <form class="mx-ws-check" data-ws-check="${esc(sub.id)}" novalidate>
      <label>ציון <small>(0–100, לא חובה)</small><input type="number" name="score" min="0" max="100" step="1" inputmode="numeric" value="${sub.score??""}"></label>
      <label>הערה לתלמיד <small>(לא חובה)</small><textarea name="comment" rows="3" maxlength="1000">${esc(sub.comment||"")}</textarea></label>
      <div class="mx-row"><button type="submit" class="mx-btn solid">${sub.checked_at&&sub.state!=="returned"?"עדכון הבדיקה":"סימון כנבדק"}</button><span class="mx-small" role="status" aria-live="polite"></span></div></form>
    ${sub.state==="returned"?`<p class="mx-small">הוחזר לתיקון${sub.return_comment?`: ${esc(sub.return_comment)}`:""}. כשהתלמיד/ה יגיש/תגיש שוב, ההגשה תחזור לבדיקה.</p>`
      :`<details class="mx-ws-return-box"><summary>↩ החזרה לתיקון</summary><form class="mx-ws-check" data-ws-return="${esc(sub.id)}" novalidate>
      <label>מה לתקן <small>(חובה)</small><textarea name="comment" rows="2" maxlength="1000"></textarea></label>
      <label>תאריך יעד חדש <small>(לא חובה)</small><input type="date" name="due_on"></label>
      <div class="mx-row"><button type="submit" class="mx-btn">החזרה לתלמיד/ה</button><span class="mx-small" role="status" aria-live="polite"></span></div></form></details>`}</div>`;
}
async function wsSubImages(){
  const mine=REPORT?.sub; if(!mine) return;
  const s=REPORT.data.students.find(x=>x.email===mine.email), sub=(s?.worksheet_submissions||[]).find(x=>x.worksheet_id===mine.wid);
  if(!sub) return;
  for(let i=0;i<sub.pages;i++){
    if(!(i in mine.urls)){ mine.urls[i]=null; mine.urls[i]=await wsBlob(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(mine.wid)}/submissions/${encodeURIComponent(sub.id)}/pages/${i+1}`); }
    if(REPORT?.sub!==mine){ if(mine.urls[i]) URL.revokeObjectURL(mine.urls[i]); return; }
    const url=mine.urls[i]; if(!url) continue;
    const img=sheet.querySelector(`[data-ws-subimg="${i}"]`), link=sheet.querySelector(`[data-ws-sublink="${i}"]`);
    if(img) img.src=url; if(link) link.href=url;
  }
}
async function wsCheck(form){
  const mine=REPORT.sub, status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const raw=form.elements.score.value.trim(), score=raw===""?null:Number(raw), comment=form.elements.comment.value;
  if(score!==null&&!(Number.isInteger(score)&&score>=0&&score<=100)){ status.textContent="הציון הוא מספר שלם בין 0 ל־100, או ריק."; return form.elements.score.focus(); }
  button.disabled=true; status.textContent="שומרים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(mine.wid)}/submissions/${encodeURIComponent(form.dataset.wsCheck)}`,
      {method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({score,comment})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(wsError({status:r.status,data:d},"השמירה נכשלה. נסו שוב."));
    if(REPORT?.sub!==mine) return;
    const s=REPORT.data.students.find(x=>x.email===mine.email);
    s.worksheet_submissions=s.worksheet_submissions.map(x=>x.id===d.id?{...x,...d,earlier:x.earlier}:x);
    if(REPORT.inbox) return inboxAfterSave();
    wsSubClose(); drawReport();
    sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",'<p class="mx-small" role="status">הבדיקה נשמרה. התלמיד/ה רואה אותה בכרטיס המשימה.</p>');
  }catch(e){ if(REPORT?.sub===mine){ button.disabled=false; status.textContent=e.message; } }
}

// back to the student for a fix: a comment (required) and maybe a new due date; the next hand-in is a new version
async function wsReturn(form){
  const mine=REPORT.sub, status=form.querySelector("[role=status]"), button=form.querySelector("[type=submit]");
  const comment=form.elements.comment.value.trim(), due_on=form.elements.due_on.value||null;
  if(!comment){ status.textContent="כתבו מה לתקן."; return form.elements.comment.focus(); }
  button.disabled=true; status.textContent="מחזירים…";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(mine.wid)}/submissions/${encodeURIComponent(form.dataset.wsReturn)}/return`,
      {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({comment,due_on})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw Error(d.detail==="returns_unavailable"?"החזרה לתיקון אינה זמינה עדיין באתר.":d.detail==="not_the_current_version"?"התלמיד/ה כבר הגיש/ה גרסה חדשה. רעננו את הדוח.":wsError({status:r.status,data:d},"ההחזרה נכשלה. נסו שוב."));
    if(REPORT?.sub!==mine) return;
    const s=REPORT.data.students.find(x=>x.email===mine.email);
    s.worksheet_submissions=s.worksheet_submissions.map(x=>x.id===d.id?{...x,...d,earlier:x.earlier}:x);
    if(REPORT.inbox) return inboxAfterSave();
    wsSubClose(); drawReport();
    sheet.querySelector(".mx-report").insertAdjacentHTML("afterbegin",'<p class="mx-small" role="status">ההגשה הוחזרה לתיקון. התלמיד/ה רואה את ההערה בכרטיס המשימה.</p>');
  }catch(e){ if(REPORT?.sub===mine){ button.disabled=false; status.textContent=e.message; } }
}

// the AI's suggestion for this submission fills the form; the teacher decides what is saved
async function wsAiCheck(button){
  const mine=REPORT?.sub, status=sheet.querySelector("[data-ws-ai-status]"), form=sheet.querySelector("[data-ws-check]");
  if(!mine||!form) return;
  button.disabled=true; status.textContent="ה־AI בודק… זה לוקח כחצי דקה.";
  try{
    const r=await api(`/api/classes/${encodeURIComponent(REPORT.id)}/worksheets/${encodeURIComponent(mine.wid)}/submissions/${encodeURIComponent(form.dataset.wsCheck)}/ai-check`,{method:"POST"});
    const d=await r.json().catch(()=>({}));
    if(REPORT?.sub!==mine) return;
    if(!r.ok){
      if(d.detail==="teacher_ai_limit") CFG.aiLeft=0;
      throw Error(String(d.detail||"").startsWith("ai_check_failed")?"הבדיקה של ה־AI נכשלה. אפשר לנסות שוב או לבדוק ידנית.":wsError({status:r.status,data:d},"הבדיקה של ה־AI נכשלה. אפשר לבדוק ידנית."));
    }
    if(typeof d.left==="number"&&!d.class_budget) CFG.aiLeft=d.left;
    if(d.score!=null) form.elements.score.value=d.score;
    form.elements.comment.value=d.comment||"";
    status.textContent=d.readable?"הצעת ה־AI הוכנסה לטופס. בדקו, תקנו אם צריך, ולחצו על הכפתור כדי לשמור.":"ה־AI לא הצליח לקרוא את הפתרון (לא נספר מהמכסה). ההערה שלו בטופס, ואפשר לבדוק ידנית.";
    form.elements.comment.focus({preventScroll:true});
  }catch(e){ if(REPORT?.sub===mine) status.textContent=e.message; }
  finally{ button.disabled=false; }
}

// ---- the report's "הגשות" tab: everything the students handed in, by student and by kind
function subsTabHtml(order,name){
  const students=REPORT.data.students, noteDevice=' <small class="mx-device">· מהמכשיר</small>';
  const hwRows=s=>(s.worksheet_submissions||[]).slice().sort((p,q)=>String(q.submitted_at).localeCompare(String(p.submitted_at)));
  const cards=order.map(({s,i})=>{
    const exams=(s.progress?.quizzes||[]).slice().reverse();
    const sit=s.quiz_sittings, latest=new Map((sit||[]).map(x=>[x.unit_id,x.id]));
    const quizzes=(sit||[]).slice().reverse(), homework=hwRows(s);
    const waiting=homework.filter(wsWaiting).length+quizzes.filter(x=>x.grade==null).length;
    const total=exams.length+quizzes.length+homework.length;
    const group=(title,rows,empty)=>`<section><h5>${title}</h5>${rows.length?`<ul class="mx-report-list mx-subs">${rows.join("")}</ul>`:`<p class="mx-small">${empty}</p>`}</section>`;
    const examRows=exams.map(q=>`<li><b>${(q.units||[]).map(asgUnit).join(", ")||TERMS.mixed}</b> <small>${esc(shortDate(q.at))} · ${q.right}/${q.n} נכונות (${pct(q.right,q.n)}%)</small></li>`);
    const quizRows=sit==null?[]:quizzes.map(x=>`<li><b>${asgUnit(x.unit_id)}</b> <span class="mx-report-chip${x.mode==="final"?" mid":""}">${x.mode==="final"?"מסכם":"חיזוק"}</span> <small>${esc(shortDate(x.submitted_at))} · ${x.grade==null?'<span class="mx-ws-wait">ממתין לבדיקה</span>':`ציון ${x.grade}/100`}</small>
      ${latest.get(x.unit_id)===x.id?`<button type="button" class="mx-btn" data-answers="${i}:${esc(x.unit_id)}">פתיחה ובדיקה</button>`:""}</li>`);
    const hwList=homework.map(x=>{ const a=REPORT.data.assignments?.find(y=>y.items.some(it=>it.kind==="worksheet"&&it.id===x.worksheet_id)), late=a&&wsLate(x,a);
      return `<li><b>${esc(wsTitle(x.worksheet_id))}</b> <small>${esc(wsWhen(x.submitted_at))}${late?" · באיחור":""} · ${x.state==="returned"?"הוחזר לתיקון":x.checked_at?(x.score!=null?`נבדק, ציון ${x.score}`:"נבדק"):`<span class="mx-ws-wait">ממתין לבדיקה${x.version>1?" (מתוקן)":""}</span>`}</small>
        <button type="button" class="mx-btn" data-ws-sub="${esc(x.worksheet_id)}|${esc(s.email)}">${wsWaiting(x)?"בדיקה":"צפייה ועדכון"}</button></li>`; });
    return `<details class="mx-report-student"${waiting?" open":""}><summary><b dir="ltr">${esc(name(s.email))}</b>
        <span class="mx-small">${total} הגשות</span>${waiting?`<span class="mx-report-chip low">${waiting} ממתינות לבדיקה</span>`:""}</summary>
      <div class="mx-report-body">
        ${group(`שיעורי בית`,hwList,"עוד לא הוגשו שיעורי בית.")}
        ${group(`בחנים`,quizRows,sit==null?"הבחנים אינם זמינים כרגע.":"עוד לא הוגש בוחן.")}
        ${group(`מבחני תרגול${noteDevice}`,examRows,"עוד לא נעשה מבחן תרגול.")}
      </div></details>`;
  }).join("");
  const waitingAll=order.reduce((n,{s})=>n+hwRows(s).filter(wsWaiting).length+(s.quiz_sittings||[]).filter(x=>x.grade==null).length,0);
  return `<p class="mx-small">${waitingAll?`<b>${waitingAll}</b> הגשות ממתינות לבדיקה. `:"אין הגשות שממתינות לבדיקה. "}שיעורי בית אפשר לבדוק ידנית או עם AI בפתיחת ההגשה. בחנים מסכמים נבדקים בפתיחה, וה־AI בודק אותם דרך תור ה־AI.${CFG.aiReview?' <button type="button" class="mx-link" data-act="ai-queue">לתור ה־AI</button>':""}</p>
    ${cards||'<p class="mx-note">עוד אין תלמידים בכיתה.</p>'}`;
}

// ---- the student: the worksheet and the hand-in
let WS=null;   // {id, urls (pages), files (chosen photos, prepared), previews, msg, busy, progress}
function dropWorksheet(){
  if(WS){
    clearTimeout(WS.timer); const sid=WS.phone?.res?.scan?.id;
    if(sid) uqPost(`/api/math/answer-scans/${sid}/decline`).catch(()=>{});   // a request for the phone that nobody waits for
    window.MathlyBoard?.closeFull();
    for(const u of [...WS.urls,...WS.previews]) if(u) URL.revokeObjectURL(u); WS=null;
  }
  wsSubClose();
}
const wsAssignment=id=>ASG?.assignments.find(a=>a.items.some(i=>i.kind==="worksheet"&&i.id===id));
const wsMine=id=>(ASG?.submissions||[]).find(x=>x.worksheet_id===id)||null;
function wsOpen(id){
  if(!cur) back=document.activeElement;
  closeSheetQuietly(); cur="worksheet";
  WS={id,urls:[],files:[],previews:[],msg:"",busy:false,progress:0,fresh:true};
  drawWorksheet(); wsPages(WS);
}
function wsHandHtml(w,a){
  const sub=wsMine(w.id);
  if(ASG.submissions===null) return '<p class="mx-note">אי אפשר לבדוק כרגע אם הגשתם. נסו שוב מאוחר יותר.</p>';
  const returned=sub?.state==="returned";
  if(sub?.checked_at&&!returned) return `<p class="mx-ws-checked">✔ המורה בדק/ה${sub.score!=null?` · ציון <b>${sub.score}</b>`:""}</p>
    ${sub.comment?`<p class="mx-ws-comment">${esc(sub.comment)}</p>`:""}<p class="mx-small">הוגש ${esc(wsWhen(sub.submitted_at))}${wsLate(sub,a)?" · באיחור":""} · ${sub.pages} עמ׳${sub.version>1?` · גרסה ${sub.version}`:""}</p>${wsEarlierHtml(sub)}`;
  const chosen=WS.files.length?`<ol class="mx-ws-chosen">${WS.files.map((_,i)=>`<li><img src="${WS.previews[i]}" alt="תמונה ${i+1}">
      <span>עמוד ${i+1}</span><span class="mx-ws-acts">${i?`<button type="button" class="mx-link" data-ws-up="${i}" aria-label="להזיז את עמוד ${i+1} למעלה">↑</button>`:""}
      <button type="button" class="mx-link" data-ws-drop="${i}" aria-label="להסיר את עמוד ${i+1}">✕</button></span></li>`).join("")}</ol>`:"";
  const due=wsDue(sub,a);
  return `${returned?`<div class="mx-ws-returned" role="status"><b>↩ הוחזר לתיקון</b>${sub.return_comment?`<p class="mx-ws-comment"><b>המורה:</b> ${esc(sub.return_comment)}</p>`:""}
        <p class="mx-small">צלמו את הפתרון המתוקן והגישו שוב${sub.return_due_on?` עד ${asgDate(sub.return_due_on)}`:""}. ההגשה הקודמת נשמרת.</p></div>`
      :sub?`<p class="mx-ws-done" role="status">✓ הוגש ${esc(wsWhen(sub.submitted_at))}${wsLate(sub,a)?" · באיחור":""} · ${sub.pages} עמ׳${sub.version>1?` · גרסה ${sub.version}`:""} · <b>ממתין לבדיקה</b>. אפשר להחליף את ההגשה עד שהמורה יבדוק.</p>${sub.note?`<p class="mx-small">ההערה שלך למורה: ${esc(sub.note)}</p>`:""}`
      :`<p class="mx-small">פתרתם? צלמו את הדפים של הפתרון (עד 10) והגישו למורה.${Sky.jerusalemDay(new Date())>due?" תאריך היעד עבר, ואפשר עדיין להגיש. ההגשה תסומן באיחור.":""}</p>`}
    ${wsEarlierHtml(sub)}
    ${chosen}
    ${WS.files.length?`<label class="mx-ws-note">הערה למורה <small>(לא חובה, עד 300 תווים)</small><textarea data-ws-note rows="2" maxlength="300">${esc(WS.note||"")}</textarea></label>`:""}
    <input type="file" accept="image/*" multiple hidden data-ws-file>
    <div class="mx-row"><button type="button" class="mx-btn" data-ws-pick${WS.busy||WS.files.length>=10?" disabled":""}>📷 ${WS.files.length?"עוד עמוד":"צילום או העלאת תמונה"}</button>
      ${window.MathlyBoard?`<button type="button" class="mx-btn" data-ws-board${WS.busy||WS.files.length>=10?" disabled":""}>✏️ כתיבה בלוח</button>`:""}
      ${wsPhoneHtml()}
      ${WS.files.length?`<button type="button" class="mx-btn solid" data-ws-send${WS.busy?" disabled":""}>${WS.busy?"שולחים…":returned?"הגשה מתוקנת":sub?"החלפת ההגשה":"הגשה"} (${WS.files.length} עמ׳)</button>`:""}</div>
    ${WS.busy?`<progress max="1" value="${WS.progress}" aria-label="התקדמות השליחה"></progress>`:""}`;
}
// on a computer the phone is asked to photograph a page: its code and progress show in the box (like an exercise's answer)
function wsPhoneHtml(){
  const touch=matchMedia("(max-width: 700px)").matches||navigator.maxTouchPoints>0;
  if(touch||!window.MathlyAnswers||!CFG.answerScans||!CFG.userId) return "";
  return window.MathlyAnswers.phoneLive(WS.phone?.res?.scan,"data-ws-phone","data-ws-cancel","צילום בטלפון",WS.busy||WS.files.length>=10||!!WS.phone?.starting);
}
function drawWorksheet(){
  const top=sheet.querySelector(".mx-sheet")?.scrollTop||0;
  const w=ASG?.worksheets?.find(x=>x.id===WS.id), a=wsAssignment(WS.id);
  const body=!w||!a?'<p class="mx-note">שיעורי הבית אינם זמינים כרגע.</p>':`
    <div class="mx-row">${w.source==="pdf"?'<button type="button" class="mx-btn" data-ws-download>⬇ הורדת ה־PDF להדפסה</button>':'<small class="mx-small">אפשר לפתוח כל עמוד בגודל מלא ולשמור אותו.</small>'}</div>
    <div class="mx-ws-pages">${Array.from({length:w.pages},(_,i)=>`<a class="mx-ws-page" data-ws-link="${i}" target="_blank" rel="noopener" download="${esc(w.title)}-${i+1}.jpg" aria-label="עמוד ${i+1} בגודל מלא"><img data-ws-img="${i}" alt="עמוד ${i+1} מתוך ${w.pages}"${WS.urls[i]?` src="${WS.urls[i]}"`:""}></a>`).join("")}</div>
    <section class="mx-sec mx-ws-hand" aria-labelledby="wsHand"><h4 id="wsHand">ההגשה שלי</h4>${wsHandHtml(w,a)}
      <p class="mx-res-msg" role="status" aria-live="polite">${esc(WS.msg)}</p></section>`;
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet mx-ws-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">שיעורי בית</span><h3 id="mxTitle">${esc(w?.title||"שיעורי בית")}</h3>
        ${a?`<small class="mx-src">${esc(a.title)} · עד ${asgDate(a.due_on)}</small>`:""}</div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>${body}</div>`;
  sheet.hidden=false;
  if(WS.fresh){ WS.fresh=false; sheet.querySelector(".mx-x").focus({preventScroll:true}); }
  else sheet.querySelector(".mx-sheet").scrollTop=top;
  // a computer: the board beside the worksheet when the student turned it on (as in quizzes)
  if(w&&a&&window.MathlyBoard?.desk()) window.MathlyBoard.mount(sheet,`ws:${WS.id}`,{sendLabel:"הוספה להגשה",
    question:()=>sheet.querySelector(".mx-ws-pages"),submit:wsBoardSubmit(WS,false)});
}
// a page written on the board joins the hand-in like a photo
// On a computer the board opens beside the worksheet, so its pages stay in view; on a phone, full screen
function wsBoard(){
  const mine=WS; if(!mine||mine.busy||!window.MathlyBoard) return;
  if(window.MathlyBoard.desk()) return window.MathlyBoard.show(0);
  window.MathlyBoard.openFull({host:document.body,key:`ws:${mine.id}`,title:"פתרון בלוח",sendLabel:"הוספה להגשה",
    submit:wsBoardSubmit(mine,true),done:()=>WS===mine&&mine.files.length&&wsShowHandIn()});
}
// a page from the board joins the photos of the hand-in; it is sent to the teacher with the hand-in's own button
function wsBoardSubmit(mine,close){
  return async(_,picture)=>{
    if(WS!==mine) return {error:"החלון נסגר"};
    if(mine.files.length>=10) return {error:"אפשר עד 10 עמודים."};
    const blob=await wsPrepare(picture); if(WS!==mine) return {error:"החלון נסגר"};
    if(!blob) return {error:"לא ניתן להכין את התמונה"};
    mine.files.push(blob); mine.previews.push(URL.createObjectURL(blob));
    mine.msg=`העמוד מהלוח נוסף (${mine.files.length} עמ׳). כדי לשלוח למורה לחצו על "הגשה".`;
    drawWorksheet(); if(!close) wsShowHandIn();
    return close?{close:true}:{};
  };
}
// the hand-in after a page was added: in view, its send button marked and focused
function wsShowHandIn(){
  const hand=sheet.querySelector(".mx-ws-hand"), send=sheet.querySelector("[data-ws-send]"); if(!hand) return;
  hand.scrollIntoView({block:"center",behavior:"smooth"});
  if(send){ send.classList.add("mx-attn"); send.focus({preventScroll:true}); }
}
async function wsPhone(){
  const mine=WS; if(!mine||mine.busy||mine.phone) return;
  mine.phone={starting:true}; mine.msg=""; drawWorksheet();
  try{
    const r=await uqPost("/api/math/worksheet-attempts",{worksheet_id:mine.id,new:true});
    const res=await uqPost(`${UQ_BASE}/${r.attempt.id}/scans`,{renew:true});
    if(WS!==mine) return;
    mine.phone={aid:r.attempt.id,res,state:res.scan?.state};
  }catch(e){ if(WS!==mine) return; mine.phone=null; mine.msg=e.message; }
  drawWorksheet(); wsPhoneWatch(mine);
}
async function wsPhoneCancel(){
  const mine=WS, sid=mine?.phone?.res?.scan?.id; if(!sid) return;
  clearTimeout(mine.timer); mine.phone=null;
  try{ await uqPost(`/api/math/answer-scans/${sid}/decline`); }catch{}
  if(WS===mine){ mine.msg="הבקשה בוטלה."; drawWorksheet(); }
}
// looks every 2 seconds until the phone has sent the photo (it joins the hand-in) or the request ends
function wsPhoneWatch(mine){
  clearTimeout(mine.timer);
  const p=mine.phone; if(!p?.aid) return;
  mine.timer=setTimeout(async()=>{
    if(WS!==mine||mine.phone!==p) return;
    try{
      const r=await uqJson(`${UQ_BASE}/${p.aid}`);
      if(WS!==mine||mine.phone!==p) return;
      p.res=r;
      if(r.attachment){
        const b=await api(`${UQ_BASE}/${p.aid}/image`,{cache:"no-store"});
        if(WS!==mine||mine.phone!==p) return;
        if(!b.ok) throw Error("לא הצלחנו לקבל את התמונה מהטלפון. נסו שוב.");
        const blob=await b.blob(); if(WS!==mine||mine.phone!==p) return;
        mine.phone=null;
        if(mine.files.length>=10) mine.msg="אפשר עד 10 עמודים.";
        else{ mine.files.push(blob); mine.previews.push(URL.createObjectURL(blob)); mine.msg="התמונה מהטלפון נוספה להגשה."; }
        return drawWorksheet();
      }
      const st=r.scan?.state;
      if(["waiting","confirmed","uploading","failed"].includes(st)){
        if(st!==p.state){ p.state=st; drawWorksheet(); }   // redraw only when the phone moved on
        return wsPhoneWatch(mine);
      }
      mine.phone=null; mine.msg=st==="declined"?"הבקשה נדחתה בטלפון.":st==="expired"?"בקשת הצילום פגה. אפשר לבקש שוב.":"הבקשה הסתיימה.";
    }catch(e){ if(WS!==mine||mine.phone!==p) return; mine.phone=null; mine.msg=e.message; }
    drawWorksheet();
  },2000);
}
async function wsPages(mine){
  const w=ASG?.worksheets?.find(x=>x.id===mine.id); if(!w) return;
  for(let i=0;i<w.pages;i++){
    const url=await wsBlob(`/api/math/worksheets/${encodeURIComponent(w.id)}/pages/${i+1}`);
    if(WS!==mine){ if(url) URL.revokeObjectURL(url); return; }
    mine.urls[i]=url; if(!url) continue;
    const img=sheet.querySelector(`[data-ws-img="${i}"]`), link=sheet.querySelector(`[data-ws-link="${i}"]`);
    if(img) img.src=url; if(link) link.href=url;
  }
}
async function wsDownload(button){
  const mine=WS, w=ASG?.worksheets?.find(x=>x.id===mine.id); if(!w) return;
  button.disabled=true;
  const url=await wsBlob(`/api/math/worksheets/${encodeURIComponent(w.id)}/original`);
  if(WS!==mine) return url&&URL.revokeObjectURL(url);
  button.disabled=false;
  if(!url){ mine.msg="ההורדה נכשלה. נסו שוב."; return drawWorksheet(); }
  const link=document.createElement("a"); link.href=url; link.download=`${w.title}.pdf`; document.body.append(link); link.click(); link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
}
async function wsAddPhotos(input){
  const mine=WS, files=[...input.files]; input.value="";
  if(!mine||!files.length) return;
  mine.msg="מכינים את התמונות…"; drawWorksheet();
  let failed=0;
  for(const f of files){
    if(mine.files.length>=10){ mine.msg="אפשר עד 10 עמודים."; break; }
    const blob=await wsPrepare(f);
    if(WS!==mine) return;
    if(!blob){ failed++; continue; }
    mine.files.push(blob); mine.previews.push(URL.createObjectURL(blob));
  }
  if(mine.files.length<10||failed) mine.msg=failed?`לא הצלחנו להכין ${failed===1?"תמונה אחת":`${failed} תמונות`}. צלמו שוב.`:"";
  drawWorksheet();
}
function wsMove(i,drop){
  if(!WS||WS.busy) return;
  if(drop){ URL.revokeObjectURL(WS.previews[i]); WS.files.splice(i,1); WS.previews.splice(i,1); }
  else if(i>0){ for(const k of ["files","previews"]) [WS[k][i-1],WS[k][i]]=[WS[k][i],WS[k][i-1]]; }
  WS.msg=""; drawWorksheet();
}
async function wsSend(){
  const mine=WS; if(!mine||mine.busy||!mine.files.length) return;
  mine.busy=true; mine.progress=0; mine.msg="שולחים…"; drawWorksheet();
  const body=new FormData(); mine.files.forEach((f,i)=>body.append("files",f,`page${i+1}.jpg`));
  if((mine.note||"").trim()) body.append("note",mine.note.trim());
  const r=await sendForm(`/api/math/worksheets/${encodeURIComponent(mine.id)}/submission`,"PUT",body,p=>{
    mine.progress=p; const bar=WS===mine&&sheet.querySelector(".mx-ws-hand progress"); if(bar) bar.value=p; });
  if(WS!==mine) return;
  mine.busy=false;
  if(!r.ok){
    mine.msg=wsError(r,"השליחה נכשלה. התמונות נשמרו כאן: נסו לשלוח שוב.");   // the chosen photos stay
    if(r.data?.detail==="already_checked") loadAssignments();
    return drawWorksheet();
  }
  ASG.submissions=[...(ASG.submissions||[]).filter(x=>x.worksheet_id!==mine.id),r.data];
  for(const u of mine.previews) URL.revokeObjectURL(u);
  mine.files=[]; mine.previews=[]; mine.note="";
  mine.msg=`ההגשה נשלחה למורה. 🎉 קבלה: ${r.data.pages} עמ׳, ${wsWhenShort(r.data.submitted_at)}${wsLate(r.data,wsAssignment(mine.id)||{due_on:"9999-12-31"})?", באיחור":", בזמן"}.`;
  drawWorksheet(); draw();   // the card on the home screen behind the sheet
}

// the report's own controls: the view and the order
function reportControl(t){
  if(t.dataset.reportTab){ wsSubClose(); REPORT.flash=null; REPORT.tab=t.dataset.reportTab; repSet("tab",REPORT.tab); drawReport(); sheet.querySelector(`[data-report-tab="${REPORT.tab}"]`)?.focus(); }
  else if(t.matches("[data-report-unit]")){ REPORT.unit=t.value; drawReport(); sheet.querySelector("[data-report-unit]")?.focus(); }
  else if(t.dataset.heatGroup||t.dataset.heatAll){
    const open=heatOpen(), key=t.dataset.heatGroup;
    if(key) open.has(key)?open.delete(key):open.add(key);
    else if(t.dataset.heatAll==="close") open.clear();
    else [...sheet.querySelectorAll("[data-heat-group]")].forEach(b=>open.add(b.dataset.heatGroup));
    REPORT.open="|"+[...open].join("|"); repSet("mapMonths",REPORT.open); drawReport();
    sheet.querySelector(key?`[data-heat-group="${CSS.escape(key)}"]`:`[data-heat-all="${t.dataset.heatAll}"]`)?.focus(); }
  else if(t.dataset.heatUnit){ REPORT.unit=t.dataset.heatUnit; drawReport(); sheet.querySelector("[data-report-unit]")?.focus(); }
  else if(t.matches("[data-report-sort]")){ REPORT.sort=t.value; repSet("sort",t.value); drawReport(); sheet.querySelector("[data-report-sort]")?.focus(); }
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
  const backTo=kind==="sitting"?()=>reviewSitting(+a,b):kind==="queue"?()=>aiQueue():kind==="report"?()=>classReport(REPORT?.id)
    :kind==="inbox"?()=>inboxBack():()=>closeSheet();
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
    mine.changed=true;
    if(mine.inbox) return inboxBack(true);
    drawReview("נשמר. התלמיד יראה את הבדיקה שלכם.");
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
  answer_storage_unavailable:"לא הצלחנו לקרוא את התמונה השמורה.",photo_failed:"פתרון התמונה נכשל. אפשר לנסות שוב.",
  teacher_ai_limit:"הגעתם למכסה של 3 בקשות AI ביום. אפשר לשלוח שוב מחר."};
// a failed send's error is "code|reason|technical detail" (app/ai_queue.py)
function aqError(error){
  const [code,reason="",...rest]=String(error||"").split("|"), detail=rest.join("|");
  return `<p class="mx-aq-error">${esc(AQ_ERR[code]||code||"השליחה נכשלה.")}</p>${window.MathlyAnswers?.errorDetails?.(reason,detail)||""}`;
}
const AQ_VERDICT={correct:"נכונה",partial:"נכונה חלקית",incorrect:"שגויה",unreadable:"לא קריאה",needs_review:"דורשת בדיקה שלכם"};
const aqCode=list=>{ const c=list.map(r=>r.code).find(Boolean); return c?`<span class="mx-aq-code" dir="ltr" title="מספר הבוחן">#${esc(c)}</span>`:""; };
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
  if(cur!=="aiqueue"){ if(!cur) back=document.activeElement; closeSheetQuietly(); cur="aiqueue"; AQ={rows:null,reqs:null,tab:AQ_TAB,urls:{},busy:new Set(),openGroups:new Set()}; }
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
  await aqBudgetLoad(mine);
}
/* ---------- the class's daily AI budget and batches (app/ai_batches.py) ----------
   Checks of students' work come from each class's daily budget, not the teacher's own 3 requests. A batch sends every
   pending check of one scope (a final quiz, a unit's practice quizzes, a worksheet) in one action, after showing how
   many it holds and how many the class has left today. */
async function aqBudgetLoad(mine=AQ){
  try{ const r=await api("/api/ai-queue/budget",{cache:"no-store"}); mine.budget=r.ok?await r.json():null; }catch{ mine.budget=null; }
  if(AQ===mine) drawQueue();
}
function aqBudgetHtml(){
  const b=AQ?.budget; if(!b?.classes?.length) return "";
  if(b.available===false) return '<p class="mx-small">תקציב ה־AI הכיתתי עוד לא מוגדר באתר: כל שליחה נספרת מ־3 הבקשות היומיות שלכם.</p>';
  return b.classes.map(c=>`<section class="mx-aq-budget" data-budget-class="${c.class_id}"><h4>${esc(c.name)}: בדיקות AI</h4>
    <p class="mx-small"><b>נוצלו ${c.used_today} מתוך ${c.limit} היום</b> · ב־7 הימים האחרונים: ${c.used_7d}</p>
    <label class="mx-small"><input type="checkbox" data-auto-send="${c.class_id}"${c.auto_send_practice?" checked":""}> לשלוח לבדיקה מיד את הבחנים של הכיתה (מבחן ושיעורי בית תמיד מחכים לכם)</label>
    ${b.manager?`<form class="mx-row" data-budget-form="${c.class_id}" novalidate><label class="mx-small">תקציב יומי <input type="number" name="limit" min="0" max="5000" value="${c.limit}" style="width:6em"></label><button type="submit" class="mx-btn">שמירה</button></form>`:""}
    ${c.scopes.length?`<ul class="mx-aq-scopes">${c.scopes.map(x=>`<li>${esc(x.label)}: <b>${x.pending}</b> ממתינות
      <button type="button" class="mx-btn" data-batch="${c.class_id}|${esc(x.key)}">שליחה של כולן לבדיקה</button></li>`).join("")}</ul>`:'<p class="mx-small">אין בדיקות שממתינות לשליחה.</p>'}
    <p class="mx-small" role="status" aria-live="polite"></p></section>`).join("");
}
// a batch: first how many, then the teacher confirms
async function aqBatch(button){
  const [cid,scope]=button.dataset.batch.split("|"), status=button.closest("section,article")?.querySelector("[role=status]");
  const post=confirm=>api("/api/ai-queue/batches",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({class_id:+cid,scope,confirm})}).then(async r=>{ const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail==="budget_unavailable"?"תקציב ה־AI הכיתתי עוד לא מוגדר באתר.":"השליחה נכשלה. נסו שוב."); return d; });
  button.disabled=true;
  try{
    const p=await post(false);
    if(!p.total){ if(status) status.textContent="אין מה לשלוח."; return; }
    if(!confirm(`${p.label||"שליחה לבדיקה"}: ${p.total} בדיקות · נשארו ${p.left} היום.${p.total>p.left?` יישלחו ${p.left} עכשיו, והשאר מחר.`:""} לשלוח?`)) return;
    const d=await post(true), say=`נשלחו ${d.sent} בדיקות.${d.later?` ${d.later} יישלחו מחר.`:""}`;
    if(status) status.textContent=say;
    if(cur==="aiqueue") setTimeout(()=>aiQueue(),400);
    else if(cur==="report"){ REPORT.finals=null; REPORT.inboxData=null; REPORT.flash=say; drawReport(); }
  }catch(e){ if(status) status.textContent=e.message; }
  finally{ button.disabled=false; }
}
async function aqSetting(cid,body,status){
  try{
    const r=await api(`/api/classes/${encodeURIComponent(cid)}/ai-settings`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!r.ok) throw Error(r.status===403?"רק מנהל יכול לשנות את התקציב.":"השמירה נכשלה.");
    if(status) status.textContent="נשמר.";
    aqBudgetLoad();
  }catch(e){ if(status) status.textContent=e.message; }
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
  if(tabs) tabs.innerHTML=`<button type="button" class="mx-btn" data-aq-tab="queue" aria-pressed="${AQ.tab!=="requests"&&AQ.tab!=="done"}">בקשות לבדיקה</button>
    <button type="button" class="mx-btn" data-aq-tab="done" aria-pressed="${AQ.tab==="done"}">טופלו${AQ.rows?.some(r=>!aqWaiting(r))?` <span class="mx-aq-badge done">${AQ.rows.filter(r=>!aqWaiting(r)).length}</span>`:""}</button>
    <button type="button" class="mx-btn" data-aq-tab="requests" aria-pressed="${AQ.tab==="requests"}">בקשות לבדיקה חוזרת${asks?.length?` <span class="mx-aq-badge">${asks.length}</span>`:""}</button>`;
  if(AQ?.tab==="requests") return drawRequests();
  sheet.querySelector('[data-act="aq-all"]').hidden=true;
  sheet.querySelector("[data-aq-help]").hidden=false;
  if(!AQ?.rows) return;
  const open=AQ.rows.filter(aqWaiting), rest=AQ.rows.filter(r=>!aqWaiting(r));
  aqBadge(AQ.rows);
  const done=AQ.tab==="done";
  sheet.querySelector(".mx-manage-state").textContent=(done?(rest.length?`${rest.length} בקשות שטופלו ביממה האחרונה`:"אין בקשות שטופלו ביממה האחרונה."):open.length?(open.length===1?"בקשה אחת ממתינה":`${open.length} בקשות ממתינות`):"אין בקשות ממתינות.")+(CFG.aiLeft!=null?` · נשארו לכם היום ${CFG.aiLeft} מתוך 3 בקשות AI`:"");
  sheet.querySelector('[data-act="aq-all"]').hidden=done||open.filter(r=>r.state==="pending").length<2;
  const when=at=>new Date(at).toLocaleString("he-IL",{dateStyle:"short",timeStyle:"short"});
  const card=r=>{
    const busy=AQ.busy.has(r.id), act=r.state==="pending"||r.state==="failed";
    return `<article class="mx-aq-card ${esc(r.state)}"><div class="mx-aq-head"><span>${AQ_KIND[r.kind]||""}</span>${aqCode([r])}
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
  // by student, then by subject (the same quiz: its label without the " · שאלה N"); newest first within each
  const subjectOf=r=>String(r.label||"").replace(/\s*·\s*שאלה\s*\d+\s*$/,"").trim()||(r.kind==="photo"?"תרגילים מצולמים":"ללא נושא");
  const grouped=rows=>{
    const students=new Map(), last=new Map();
    // a request before the codes existed has none: the requests of one hand-in were made within moments of each other
    const clusterKey=r=>{
      const id=`${r.email}|${subjectOf(r)}`, t=Date.parse(r.created_at), prev=last.get(id);
      if(!prev||Math.abs(prev.t-t)>120000) last.set(id,{t,n:(prev?.n||0)+1}); else prev.t=t;
      return `${subjectOf(r)}@${last.get(id).n}`;
    };
    rows.forEach(r=>{ const s=students.get(r.email)||students.set(r.email,new Map()).get(r.email), k=r.code?`${subjectOf(r)}#${r.code}`:/·\s*שאלה\s*\d+\s*$/.test(r.label||"")?clusterKey(r):subjectOf(r); (s.get(k)||s.set(k,[]).get(k)).push(r); });   // one hand-in (its code) is one group: two sittings of the same quiz stay apart
    return [...students].map(([email,subjects])=>`<section class="mx-aq-student"><h4 class="mx-aq-who" dir="ltr">${esc(String(email).split("@")[0])}</h4>
      ${[...subjects].map(([key0,list])=>{ const name=subjectOf(list[0]);
        if(list.length===1) return `<div class="mx-aq-subject">${card(list[0])}</div>`;   // one request: a plain card (its card shows the hand-in number)
        // a collection (a quiz): one request that opens into a card per question, each handled on its own
        const key=email+"|"+key0, waiting=list.filter(aqWaiting).length;
        return `<details class="mx-aq-subject mx-aq-group" data-aq-group="${esc(key)}"${AQ.openGroups.has(key)?" open":""}><summary><b>${fmtLoose(name)}</b>
          <span class="mx-aq-badge">${list.length}</span>${aqCode(list)}<small>${waiting?`${waiting} ממתינות`:"טופלו"}</small></summary>${list.map(card).join("")}</details>`;
      }).join("")}</section>`).join("");
  };
  box.innerHTML=(done?"":aqBudgetHtml())+grouped(done?rest:open);
  box.querySelectorAll("[data-aq-group]").forEach(d=>d.addEventListener("toggle",()=>{ const k=d.dataset.aqGroup; d.open?AQ.openGroups.add(k):AQ.openGroups.delete(k); }));
  (done?[]:open).forEach(r=>aqImage(r.id));
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
    if(d.detail==="teacher_ai_limit") CFG.aiLeft=0;
    if(!r.ok) throw Error(AQ_ERR[d.detail]||"הפעולה נכשלה. נסו שוב.");
    row=d; if(what==="send"&&d.state==="done") aiUsed();
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
async function aqAll(){ for(const r of (AQ?.rows||[]).filter(x=>x.state==="pending")){ if(!AQ||CFG.aiLeft===0) return; await aqSend(r.id); } }

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
    if(data.queued){ mine.req=data.request; mine.left=data.left; } else { mine.data=data; if(data.readable) aiUsed(); }
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
  if(!CFG.userId||can("students.view")||VIEW!=="path"||!path) return;
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
    CFG.aiLeft=typeof me.ai_left==="number"?me.ai_left:null;   // a teacher's AI requests left today (app/teacher_ai.py)
  }
  document.getElementById("boot").hidden=true;
  show();
}
boot().catch(error=>{ const state=document.getElementById("bootState"); state.className="error"; state.textContent=`לא הצלחנו לפתוח את המסלול: ${error.message}`; });
})();
