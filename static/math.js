/* The Mathly path.
   The skill graph comes from /api/math/skills (app/math_skills.py). A skill is open once every skill it needs is
   done, and the first open one is where the student goes on. A student may still open a locked skill: without a
   placement test, one who already knows the foundations should not have to answer them first.
   Each skill has one sample question, and answering it correctly marks the skill done. Progress is kept on
   this device, per account (mathly.progress.v1:<email>). */
(()=>{
const css=document.createElement("link"); css.rel="stylesheet"; css.href=document.currentScript.src.replace("math.js","math.css");
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
const save=()=>{ try{ localStorage.setItem(key(),JSON.stringify(P)); }catch{} };

let G=null, BY={}, POST={}, DEPTH={}, ORDER=[], P={done:{},tries:{}}, root=null, path=null, sheet=null, cur=null, back=null, ACTIVE_SUBJECT="";
let picker=null, PH=null;   // the photo file picker, and the photographed problem on the sheet (see photo())
let advanceTimer=null;
let phonePair=null;
function stopPhone(){
  window.MathlyAnswers?.closeQuestion();
  if(phonePair){clearTimeout(phonePair.timer);if(phonePair.qr)URL.revokeObjectURL(phonePair.qr);phonePair=null;}
}
function cancelAdvance(){ clearTimeout(advanceTimer); advanceTimer=null; }

function index(graph){
  G=graph; BY=Object.fromEntries(G.skills.map(s=>[s.id,s])); POST=Object.fromEntries(G.skills.map(s=>[s.id,[]]));
  G.skills.forEach(s=>s.prereqs.forEach(p=>POST[p].push(s.id)));
  const depth=id=>DEPTH[id]??(DEPTH[id]=BY[id].prereqs.length?1+Math.max(...BY[id].prereqs.map(depth)):0);
  G.skills.forEach(s=>depth(s.id));
  // the path's order: unit by unit, and in a unit each skill after the ones it needs
  ORDER=G.units.flatMap(u=>G.skills.filter(s=>s.unit===u.id).sort((a,b)=>DEPTH[a.id]-DEPTH[b.id]).map(s=>s.id));
}
// the units the student's class studies (its "lessons"); a teacher, or an account in no class, has every unit.
// A skill of a unit the class does not study counts as known: it does not lock the skills that need it.
const shownUnits=()=>{
  const mine=typeof MY_CLASSES==="undefined"?[]:MY_CLASS?[MY_CLASS]:MY_CLASSES, ids=new Set(mine.flatMap(c=>c.lessons||[]));
  const units=G.units.filter(u=>ids.has(u.id)); return units.length?units:G.units;
};
let SHOWN=new Set();
const status=id=>P.done[id]?"done":BY[id].prereqs.every(p=>P.done[p]||!SHOWN.has(BY[p].unit))?"open":"locked";
const next=()=>ORDER.find(id=>SHOWN.has(BY[id].unit)&&status(id)==="open")||null;

async function show(){
  document.documentElement.classList.add("math-on");
  if(!root){
    root=document.createElement("section"); root.id="mathView"; root.setAttribute("aria-label","מסלול המתמטיקה");
    path=document.createElement("div"); path.className="mx-wrap";
    sheet=document.createElement("div"); sheet.className="mx-layer"; sheet.hidden=true;
    // no capture attribute: the phone offers the camera and the gallery both
    picker=document.createElement("input"); picker.type="file"; picker.accept="image/*"; picker.hidden=true;
    picker.onchange=()=>{ const f=picker.files[0]; picker.value=""; if(f) photo(f); };
    root.append(path,sheet,picker); document.body.append(root);
    root.addEventListener("click",onClick);
    document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&cur) closeSheet(); });
  }
  root.hidden=false;
  if(!G){
    path.innerHTML='<p class="mx-note">טוענים את המסלול…</p>';
    try{ const r=await fetch("/api/math/skills"); if(!r.ok) throw new Error(`השרת ענה ${r.status}`); index(await r.json()); }
    catch(e){ path.innerHTML=`<p class="mx-note">לא הצלחנו לטעון את המסלול: ${esc(e.message)}. רעננו את העמוד ונסו שוב.</p>`; return; }
  }
  P=Object.assign({done:{},tries:{}},load()); SHOWN=new Set(shownUnits().map(u=>u.id));
  subjectOptions().length?drawSubjectPicker():selectSubject("מתמטיקה");
  window.MathlyAnswers?.configure({api,account:CFG.userId,enabled:CFG.answerScans,root,onGraded:({questionId,grading})=>{
    if(grading.result.verdict!=="correct"||P.done[questionId])return;
    P.done[questionId]=grading.finished_at||new Date().toISOString();
    P.tries[questionId]=(P.tries[questionId]||0)+1;save();draw();
  }});
}
function hide(){ cancelAdvance(); if(root) root.hidden=true; document.documentElement.classList.remove("math-on"); }

function subjectOptions(){
  const bySubject=new Map();
  MY_CLASSES.forEach(row=>(row.exams||[]).forEach(exam=>{
    if(!exam?.subject||!exam?.date)return;
    const item=bySubject.get(exam.subject)||{name:exam.subject,dates:[],classes:new Set()};
    item.dates.push(exam.date);item.classes.add(row.name);bySubject.set(exam.subject,item);
  }));
  return [...bySubject.values()].map(item=>({...item,dates:item.dates.sort()})).sort((a,b)=>a.dates[0].localeCompare(b.dates[0]));
}
function drawSubjectPicker(){
  ACTIVE_SUBJECT="";
  const manage=can("management.access"), subjects=subjectOptions(), today=new Date();today.setHours(0,0,0,0);
  path.innerHTML=`<header class="mx-top"><div><h1>המקצועות שלי</h1><p class="mx-sub">בחרו מקצוע כדי לפתוח את המסלול שלו</p></div><div class="mx-acts">${manage?'<button class="mx-btn" data-act="manage">ניהול</button>':""}${AUTH_URL?'<button class="mx-btn" data-act="out">יציאה</button>':""}</div></header>
    <section class="mx-subject-grid" aria-label="מקצועות הכיתה">${subjects.map(item=>{
      const [icon,tone]=examLooks[item.name]||["●","other"],future=item.dates.find(date=>examDate(date)>=today),count=item.dates.length;
      return `<button class="mx-subject-card exam-${tone}" data-subject="${esc(item.name)}"><span class="mx-subject-icon" aria-hidden="true">${icon}</span><span><b>${esc(item.name)}</b><small>${count} מבחנים${future?` · הבא ${examDay(future)}`:" · הסתיימו"}</small></span><i aria-hidden="true">‹</i></button>`;
    }).join("")}</section>`;
}
function selectSubject(subject){
  ACTIVE_SUBJECT=subject;
  if(subject==="מתמטיקה")return draw();
  const [icon,tone]=examLooks[subject]||["●","other"];
  path.innerHTML=`<header class="mx-top"><div><h1>${esc(subject)}</h1><p class="mx-sub">המקצועות שלי</p></div><button class="mx-btn" data-act="subjects">לכל המקצועות</button></header><section class="mx-subject-empty exam-${tone}"><span aria-hidden="true">${icon}</span><h2>המסלול של ${esc(subject)} עדיין לא זמין</h2><p>לוח המבחנים של המקצוע כבר מחובר לכיתה. כשהמסלול יתווסף, הוא ייפתח מכאן.</p><button class="mx-btn solid" data-act="subjects">חזרה למקצועות</button></section>`;
}

function draw(){
  const UNITS=G.units.filter(u=>SHOWN.has(u.id)), mine=G.skills.filter(s=>SHOWN.has(s.unit));
  const total=mine.length, doneN=mine.filter(s=>P.done[s.id]).length, nxt=next();
  const cls=typeof MY_CLASS!=="undefined"&&MY_CLASS?` · כיתת ${esc(MY_CLASS.name)}`:"";
  const manage=can("management.access"), pct=Math.round(100*doneN/total);
  const examRows=(MY_CLASS?[MY_CLASS]:MY_CLASSES).filter(row=>(row.exams||[]).length);
  const units=UNITS.map(u=>{
    const ids=ORDER.filter(id=>BY[id].unit===u.id), d=ids.filter(id=>P.done[id]).length;
    return `<div class="mx-su u-${u.id}"><b>${esc(u.name)}</b><span class="mx-bar"><i style="width:${Math.round(100*d/ids.length)}%"></i></span><small>${d} מתוך ${ids.length}</small></div>`;
  }).join("");
  const trail=UNITS.map(u=>{
    const ids=ORDER.filter(id=>BY[id].unit===u.id);
    return `<section class="mx-unit u-${u.id}"><div class="mx-uhead"><h2>${esc(u.name)}</h2><span>${esc(u.source)}${u.when?" · "+esc(u.when):""}</span></div>
      <div class="mx-trail">${ids.map((id,i)=>{
        const s=BY[id], st=status(id), here=id===nxt;
        return `<button class="mx-node st-${st}${here?" here":""}" data-id="${id}" aria-label="${esc(plain(s.name))}, ${st==="done"?"הושלמה":st==="open"?"פתוחה":"נעולה"}">
          <span class="mx-dot">${st==="done"?"✓":i+1}</span>
          <span class="mx-lbl"><b>${fmt(s.name)}</b><small>${s.core?'<span class="mx-core">ליבה 5 יח״ל</span>':""}${here?'<span class="mx-go">ממשיכים כאן</span>':""}</small></span></button>`;
      }).join("")}</div></section>`;
  }).join("");
  path.innerHTML=`<header class="mx-top"><div><h1>המסלול שלי</h1><p class="mx-sub">אלגברה וגאומטריה כיתה ט׳ · 5 יח״ל${cls}</p></div>
      <div class="mx-acts">${subjectOptions().length?'<button class="mx-btn" data-act="subjects">מקצועות</button>':""}${manage?'<button class="mx-btn" data-act="manage">ניהול</button>':""}${AUTH_URL?'<button class="mx-btn" data-act="out">יציאה</button>':""}</div></header>
    <section class="mx-progress" aria-label="ההתקדמות שלי">
      <div class="mx-ring" style="--p:${pct}"><b>${doneN}</b><small>מתוך ${total}</small></div>
      <div class="mx-units">${units}</div></section>
    ${examRows.map(row=>examBoard(row,true)).join("")}
    ${nxt?`<button class="mx-next" data-id="${nxt}"><small>ממשיכים מכאן</small><b>${fmt(BY[nxt].name)}</b></button>`:'<p class="mx-note">סיימתם את כל המסלול. כל הכבוד!</p>'}
    <button class="mx-photo" data-act="photo"><b>צילום תרגיל</b><small>צלמו תרגיל מהמחברת או מהדף, ונעזור לכם לפתור אותו צעד אחר צעד</small></button>
    <button class="mx-photo" data-act="phone"><b>צילום בטלפון, פתרון במחשב</b><small>סרקו קוד בטלפון, צלמו תרגיל וראו את התשובה כאן אוטומטית</small></button>
    ${trail}
    <p class="mx-note">בשלב הזה יש שאלה אחת לדוגמה לכל מיומנות. ההתקדמות נשמרת במכשיר הזה.</p>`;
}

function chips(ids){
  return ids.length?ids.map(id=>`<button class="mx-chip u-${BY[id].unit}${P.done[id]?" is-done":""}" data-id="${id}">${P.done[id]?"✓ ":""}${esc(BY[id].short)}</button>`).join(""):'<em>אין</em>';
}
function open(id){
  stopPhone();
  cancelAdvance();
  const s=BY[id], st=status(id), unit=G.units.find(u=>u.id===s.unit), openEnded=s.sample.type==="open-ended";
  const options=s.sample.choices||[],rot=options.length?ORDER.indexOf(id)%options.length:0;
  const choices=options.slice(rot).concat(options.slice(0,rot)), missing=s.prereqs.filter(p=>!P.done[p]&&SHOWN.has(BY[p].unit));
  if(!cur) back=document.activeElement;
  cur=id;
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div>
    <div class="mx-sheet u-${s.unit}" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
      <div class="mx-shtop"><div><span class="mx-uchip">${esc(unit.name)}</span>${s.core?' <span class="mx-core">ליבה 5 יח״ל</span>':""}
        <h3 id="mxTitle">${fmt(s.name)}</h3><small class="mx-src">${s.month?`בפריסה: ${esc(s.month)}`:esc(unit.source)}${st==="done"?" · הושלמה ✓":""}</small></div>
        <button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
      <p>${fmt(s.description)}</p>
      ${st==="locked"?`<div class="mx-hint">מומלץ לעבור קודם על: <span class="mx-chips">${chips(missing)}</span></div>`:""}
      <div class="mx-q"><p>${fmt(s.sample.question)}</p>${s.sample.graph?plot(s.sample.graph):""}${s.sample.diagram?geometryDiagram(s.sample.diagram):""}
        ${openEnded?'<div class="mx-answer"></div>':`<div class="mx-choices">${choices.map((c,i)=>`<button data-choice="${i}" data-m="${c.correct?"":esc(c.mistake)}">${fmt(c.text)}</button>`).join("")}</div>`}
        <div class="mx-fb" aria-live="polite"></div></div>
      <div class="mx-sec"><h4>דורשת</h4><div class="mx-chips">${chips(s.prereqs)}</div></div>
      <div class="mx-sec"><h4>פותחת</h4><div class="mx-chips">${chips(POST[id])}</div></div>
    </div>`;
  sheet.hidden=false; sheet.querySelector(".mx-sheet").scrollTop=0;
  sheet.querySelector(".mx-x").focus({preventScroll:true});
  if(openEnded)window.MathlyAnswers?.mountQuestion(sheet.querySelector(".mx-answer"),id,s.question_version);
}
function closeSheet(){ stopPhone(); cancelAdvance(); if(sheet)sheet.hidden=true; cur=null; back?.focus?.({preventScroll:true}); back=null; }

function answer(btn){
  if(btn.disabled) return;
  const id=cur, m=btn.dataset.m, fb=sheet.querySelector(".mx-fb");
  sheet.querySelectorAll("[data-choice]").forEach(b=>b.classList.remove("right","wrong"));
  btn.classList.add(m?"wrong":"right");
  P.tries[id]=(P.tries[id]||0)+1;
  if(!m){
    const first=!P.done[id]; P.done[id]=P.done[id]||new Date().toISOString(); save(); draw();
    const nxt=next();
    sheet.querySelectorAll("[data-choice]").forEach(b=>b.disabled=true);
    fb.innerHTML=`<div class="mx-ok"><b>נכון!</b>${first?"<span>המיומנות סומנה כהושלמה.</span>":""}
      ${nxt&&nxt!==id?`<span class="mx-countdown"></span><button class="mx-btn solid" data-id="${nxt}">המשך עכשיו: ${esc(BY[nxt].short)}</button>`:"<span>סיימתם את כל המסלול. כל הכבוד!</span>"}</div>`;
    if(nxt&&nxt!==id){
      let seconds=3;
      const countdown=fb.querySelector(".mx-countdown");
      const tick=()=>{
        if(cur!==id||sheet.hidden||root.hidden) return cancelAdvance();
        if(seconds===0) return open(nxt);
        countdown.textContent=`התרגיל הבא בעוד ${seconds}…`;
        seconds--;
        advanceTimer=setTimeout(tick,1000);
      };
      tick();
    }
    return;
  }
  save();
  const M=G.mistakes[m], to=M.back&&M.back!==id?M.back:null;
  fb.innerHTML=`<div class="mx-bad"><b>${fmt(M.name)}</b><span>${fmt(M.tip)}</span>
    ${to?`<button class="mx-btn" data-id="${to}">חזרה אל: ${esc(BY[to].short)}</button>`:"<span class=\"mx-small\">אפשר לבחור תשובה אחרת.</span>"}</div>`;
}

function onClick(e){
  const t=e.target.closest("button,[data-act]"); if(!t||!root.contains(t)) return;
  if(t.dataset.choice!=null) return answer(t);
  if(t.dataset.subject) return selectSubject(t.dataset.subject);
  if(t.dataset.id) return open(t.dataset.id);
  if(t.dataset.manageMode) return showManageMode(t.dataset.manageMode);
  if(t.dataset.classAction) return manageClassAction(t.dataset.classAction,t.dataset.classId);
  switch(t.dataset.act){
    case "manage": return manageClasses();
    case "manage-refresh": return loadManagedClasses(true);
    case "manage-lab": return showManageMode("lab");
    case "manage-practice": return closeSheet();
    case "subjects": return drawSubjectPicker();
    case "phone": return pairPhone();
    case "copy-phone": return copyPhone(t);
    case "photo": case "retake": return picker.click();
    case "hint": PH.shown++; return drawPhoto();
    case "work": PH.works.add(+t.dataset.i); return drawPhoto();
    case "all": PH.all=true; return drawPhoto();
    case "close": return closeSheet();
    case "out": window.MathlyAnswers?.reset();closeSheet();hide();return client?.auth.signOut().then(()=>location.reload());
  }
}

let MANAGED_CLASSES=[], MANAGE_MODE="classes", MANAGE_BUSY=false;
const manageTabs=[
  ["classes","כיתות","פתיחה, עריכה ומחיקה"],
  ["students","תלמידים","רשימה ומסנן כיתות"],
  ["content","תוכן","נושאים, סרטונים וטקסטים"],
  ["flags","ניטור","פעילות ודיווחי ציונים"],
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
  if(mode==="content"){
    box.innerHTML=`<div class="mx-manage-title"><h4>תוכן לימודי</h4><span>${G.units.length} נושאים במסלול</span></div><div class="mx-manage-list">${G.units.map(unit=>{const skills=G.skills.filter(skill=>skill.unit===unit.id);const count=MANAGED_CLASSES.filter(row=>(row.lessons||[]).includes(unit.id)).length;return `<article class="u-${unit.id}"><b>${esc(unit.name)}</b><small>${skills.length} מיומנויות · פעיל ב־${count} כיתות</small></article>`}).join("")}</div>`;
    return;
  }
  if(mode==="flags"){
    const done=Object.keys(P.done||{}).length, tries=Object.values(P.tries||{}).reduce((sum,n)=>sum+(+n||0),0);
    box.innerHTML=`<div class="mx-manage-title"><h4>ניטור</h4><span>פעילות ודיווחי ציונים</span></div><div class="mx-manage-stats"><article><b>${MANAGED_CLASSES.length}</b><small>כיתות פעילות</small></article><article><b>${done}</b><small>מיומנויות שהושלמו במכשיר זה</small></article><article><b>${tries}</b><small>ניסיונות במכשיר זה</small></article></div><p class="mx-note">נתוני התקדמות כיתתיים יופיעו כאן כאשר שירות דיווחי הציונים יחובר.</p>`;
    return;
  }
  if(mode==="access"){
    const roles=CFG.roles||[], permissions=CFG.permissions||[];
    box.innerHTML=`<div class="mx-manage-title"><h4>הרשאות</h4><span>תפקידים וגישה</span></div><div class="mx-access-card"><small>התפקידים שלך</small><div class="mx-tag-row">${roles.length?roles.map(role=>`<span>${esc(role)}</span>`).join(""):'<span>מנהל/ת</span>'}</div><small>הרשאות פעילות</small><div class="mx-tag-row">${permissions.map(permission=>`<span dir="ltr">${esc(permission)}</span>`).join("")}</div></div>`;
    return;
  }
  box.innerHTML='<div class="mx-manage-title"><h4>מעבדה</h4><span>כלים לבדיקה ופיתוח</span></div><p class="mx-note">כלי המעבדה למתמטיקה יתווספו כאן. אפשר לחזור לכל אזור ניהול מהכרטיסיות למעלה.</p>';
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
      return `<article class="mx-class-card"><div class="mx-class-card-head"><h5>${esc(row.name)}</h5><div class="mx-class-actions"><button class="mx-btn" data-class-action="edit" data-class-id="${esc(row.id)}">עריכה</button><button class="mx-btn danger" data-class-action="delete" data-class-id="${esc(row.id)}">מחיקה</button></div></div>
        <dl><dt>יחידות</dt><dd>${esc(unitLine)}</dd><dt>מקצועות היחידות</dt><dd>${esc(subjects.join(" · ")||"לא הוגדרו")}</dd><dt>תלמידים</dt><dd>${students.length?`${students.length}: ${esc(students.join(" · "))}`:"עוד אין"}</dd><dt>מורים</dt><dd>${teachers.length?esc(teachers.join(" · ")):"עוד לא נבחרו"}</dd></dl>${examBoard(row)}</article>`;
    }).join("")}</div>`:'<div class="mx-empty-class"><h5>עוד אין כיתות</h5><p>פתחו כיתה ראשונה, בחרו את יחידות הלימוד והוסיפו את כתובות התלמידים.</p></div>'}`;
}

function manageClassAction(action,id){
  if(action==="new") return openClassEditor(null);
  if(action==="cancel") return drawManagedClasses(sheet.querySelector(".mx-management"));
  const row=MANAGED_CLASSES.find(item=>String(item.id)===String(id));
  if(!row) return;
  if(action==="edit") return openClassEditor(row);
  if(action==="delete") return deleteManagedClass(row);
}

function openClassEditor(row){
  const box=sheet.querySelector(".mx-management"), creating=!row;
  const selected=new Set(row?.lessons||G.units.map(unit=>unit.id));
  box.innerHTML=`<div class="mx-manage-title"><h4>${creating?"כיתה חדשה":`עריכת ${esc(row.name)}`}</h4><button class="mx-btn" type="button" data-class-action="cancel">חזרה לכיתות</button></div>
    <form class="mx-class-form"><label>שם הכיתה<input name="name" required maxlength="80" autocomplete="off" placeholder="למשל: ט׳ 1" value="${esc(row?.name||"")}"></label>
      <fieldset><legend>יחידות הלימוד<small>התלמידים יראו במסלול רק את המיומנויות של היחידות שסומנו. מקצוע היחידה קובע אילו מבחנים יוצגו במסלול.</small></legend><div class="mx-unit-picks">${G.units.map(unit=>`<label class="u-${unit.id}"><input type="checkbox" name="unit" value="${esc(unit.id)}"${selected.has(unit.id)?" checked":""}><span>${esc(unit.name)}<small>${esc(unit.subject)} · ${G.skills.filter(skill=>skill.unit===unit.id).length} מיומנויות</small></span></label>`).join("")}</div></fieldset>
      <label>התלמידים<small>כתובת דוא״ל אחת בכל שורה. תלמיד יכול להשתייך ליותר מכיתה אחת.</small><textarea name="emails" dir="ltr" spellcheck="false" placeholder="student@example.com">${esc((row?.emails||[]).join("\n"))}</textarea></label>
      <label>מורי הכיתה<small>כתובת דוא״ל אחת בכל שורה. למורים תהיה גישה לכיתה הזו.</small><textarea name="teachers" dir="ltr" spellcheck="false" placeholder="teacher@example.com">${esc((row?.teachers||[]).join("\n"))}</textarea></label>
      <div class="mx-class-form-actions"><button class="mx-btn solid" type="submit">${creating?"פתיחת הכיתה":"שמירת השינויים"}</button><button class="mx-btn" type="button" data-class-action="cancel">ביטול</button><span role="status" aria-live="polite"></span></div></form>`;
  const form=box.querySelector("form"), message=form.querySelector('[role="status"]');
  form.querySelector('input[name="name"]').focus();
  form.onsubmit=async event=>{
    event.preventDefault();
    const lessons=[...form.querySelectorAll('input[name="unit"]:checked')].map(input=>input.value);
    if(!lessons.length){message.textContent="בחרו לפחות יחידת לימוד אחת.";return;}
    const lines=name=>form.elements[name].value.split(/[\n,;]+/).map(value=>value.trim().toLowerCase()).filter(Boolean);
    const body={name:form.elements.name.value.trim(),emails:lines("emails"),teachers:lines("teachers"),lessons};
    const buttons=form.querySelectorAll("button"); buttons.forEach(button=>button.disabled=true); message.textContent=creating?"פותחים את הכיתה…":"שומרים…";
    try{
      const response=await api(creating?"/api/classes":`/api/classes/${encodeURIComponent(row.id)}`,{method:creating?"POST":"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      if(!response.ok){const detail=(await response.json().catch(()=>({}))).detail;throw new Error(detail||"לא הצלחנו לשמור את הכיתה. נסו שוב.");}
      if(!creating){
        Object.assign(row,body); MY_CLASSES.forEach(item=>{if(String(item.id)===String(row.id))Object.assign(item,body);});
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
    mine.data=data;
  }catch(e){ mine.error=e.message; }
  mine.busy=false;
  if(PH===mine&&cur==="photo") drawPhoto();   // a newer photo, or a closed sheet, keeps its own
}
function drawPhoto(){
  const d=PH.data;
  let body;
  if(PH.busy) body='<div class="mx-wait"><span class="mx-spin" aria-hidden="true"></span><b>קוראים את התרגיל ופותרים…</b><small>זה לוקח כמה שניות.</small></div>';
  else if(PH.error) body=`<div class="mx-bad"><b>לא הצלחנו</b><span>${esc(PH.error)}</span><button class="mx-btn" data-act="retake">צילום מחדש</button></div>`;
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

async function copyPhone(button){
  try{
    await navigator.clipboard.writeText(phonePair?.url||"");
    button.textContent="הקישור הועתק";
  }catch{
    const input=sheet.querySelector(".mx-phone-url");
    input?.focus();input?.select();
    button.textContent="בחרו והעתיקו את הקישור";
  }
}

async function pairPhone(){
  cancelAdvance();stopPhone();
  if(!cur)back=document.activeElement;
  cur="phone";
  const pair=phonePair={timer:null,qr:null,url:""};
  sheet.innerHTML=`<div class="mx-scrim" data-act="close"></div><div class="mx-sheet" role="dialog" aria-modal="true" aria-labelledby="mxTitle">
    <div class="mx-shtop"><h3 id="mxTitle">צילום בטלפון, פתרון במחשב</h3><button class="mx-x" data-act="close" aria-label="סגירה">✕</button></div>
    <div class="mx-pair-content"></div><p class="mx-pair-status" role="status" aria-live="polite">מכינים קישור לטלפון…</p></div>`;
  sheet.hidden=false;sheet.querySelector(".mx-x").focus({preventScroll:true});
  const content=sheet.querySelector(".mx-pair-content"),message=sheet.querySelector(".mx-pair-status");
  try{
    const response=await api("/api/math/photo-sessions",{method:"POST"}),data=await response.json();
    if(!response.ok)throw Error(data.detail||"לא הצלחנו ליצור קישור.");
    if(phonePair!==pair)return;
    pair.url=`${location.origin}/phone#${data.token}`;
    content.innerHTML=`<p>סרקו בטלפון וצלמו את התרגיל. התשובה והפתרון יופיעו כאן. הקישור תקף ל־15 דקות ולתרגיל אחד.</p>
      <div class="mx-qr-slot"></div><label>אפשר גם לפתוח בטלפון את הקישור:<input class="mx-phone-url" readonly dir="ltr" value="${esc(pair.url)}" aria-label="קישור לצילום בטלפון"></label>
      <button class="mx-btn" data-act="copy-phone">העתקת קישור</button>
      ${["localhost","127.0.0.1","[::1]"].includes(location.hostname)?'<p class="mx-bad">כדי שהטלפון יתחבר, פתחו במחשב את האתר בכתובת רשת שנגישה גם מהטלפון, ואז צרו קישור חדש.</p>':""}`;
    message.textContent="ממתינים לתמונה מהטלפון…";
    // Start polling independently so a QR failure still leaves a working link.
    const poll=async()=>{
      if(phonePair!==pair)return;
      try{
        const res=await api(`/api/math/photo-sessions/${data.token}`,{cache:"no-store"}),result=await res.json();
        if(phonePair!==pair)return;
        if(!res.ok){
          if(res.status>=400&&res.status<500){
            message.textContent=result.detail||"החיבור הופסק. פתחו קישור חדש.";
            stopPhone();return;
          }
          throw Error(result.detail||"החיבור נקטע לרגע. מנסים שוב…");
        }
        if(result.state==="done"){
          stopPhone();cur="photo";
          if(PH?.url)URL.revokeObjectURL(PH.url);
          PH={url:null,data:result.result,error:"",busy:false,shown:1,works:new Set(),all:true,fresh:true};
          drawPhoto();return;
        }
        message.textContent=result.state==="solving"?"התמונה התקבלה! קוראים ופותרים…":result.state==="error"?result.error+" אפשר לנסות שוב בטלפון.":"ממתינים לתמונה מהטלפון…";
      }catch(error){
        if(phonePair!==pair)return;
        message.textContent="החיבור נקטע לרגע. מנסים שוב…";
      }
      pair.timer=setTimeout(poll,2000);
    };
    poll();
    try{
      const qr=await api("/api/math/photo-qr",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:pair.url})});
      if(!qr.ok)throw Error("qr");
      const blob=await qr.blob();if(phonePair!==pair)return;
      pair.qr=URL.createObjectURL(blob);
      content.querySelector(".mx-qr-slot").innerHTML=`<img class="mx-phone-qr" src="${pair.qr}" alt="סרקו בטלפון כדי לצלם תרגיל">`;
    }catch{if(phonePair===pair)content.querySelector(".mx-qr-slot").textContent="הקוד לא נטען. אפשר להעתיק את הקישור לטלפון.";}
  }catch(error){if(phonePair===pair)message.textContent=error.message;}
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
    const response=await api("/api/me");
    if(!response.ok){ state.className="error"; state.textContent=response.status===403?"החשבון אינו משויך לכיתת מתמטיקה.":"לא ניתן להשלים את הכניסה."; return; }
    const me=await response.json();CFG.userId=me.user_id;CFG.answerScans=me.answer_scans; ME_EMAIL=me.email||""; MY_CLASSES=me.classes||[]; MY_CLASS=MY_CLASSES.length===1?MY_CLASSES[0]:null;
    CFG.permissions=me.permissions||[]; CFG.roles=me.roles||[];
  }
  document.getElementById("boot").hidden=true;
  show();
}
boot().catch(error=>{ const state=document.getElementById("bootState"); state.className="error"; state.textContent=`לא הצלחנו לפתוח את המסלול: ${error.message}`; });
})();
