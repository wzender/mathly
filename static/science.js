/* The science path (app/science.py): the unit חידות and its riddle skills, solved by the class together.
   The host opens a vote and shows its code on the board; students join with the code on their own devices and vote.
   Every screen asks the server for the room about once a second and a half. Votes stay hidden until the host checks;
   then the rocket is launched with the majority's fuel: it flies, falls back (too little fuel) or stays on the pad
   (too heavy). math.js opens this from the subject picker: MathlyScience.show(container, {back}). */
(()=>{
const css=document.createElement("link"); css.rel="stylesheet"; css.href=document.currentScript.src.replace("science.js","science.css");
document.head.append(css);

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=s=>esc(s).replace(/\$([^$]+)\$/g,'<span class="m" dir="ltr">$1</span>');   // $…$: math, set left to right
const store={get:(k,s=localStorage)=>{ try{ return s.getItem(k); }catch{ return null; } },
  set:(k,v,s=localStorage)=>{ try{ s.setItem(k,v); }catch{} }};
// one vote per device: a random id kept on it
const VOTER=(()=>{ let id=store.get("mathly.voter"); if(!id||id.length<8){ id=(crypto.randomUUID?.()||String(Math.random()).slice(2)+Date.now()).replace(/-/g,""); store.set("mathly.voter",id); } return id; })();
const hostKey=code=>store.get(`mathly.science.host:${code}`,sessionStorage)||"";
const POLL=1500;

let box=null, PATH=null, ROOM=null, SHOWN="", timer=null, launched=new Set(), busy=false, msg="";

async function call(url,options={}){
  const code=ROOM?.code;
  const r=await fetch(url,{...options,headers:{"Content-Type":"application/json",...(code?{"X-Host":hostKey(code)}:{})}});
  const body=await r.json().catch(()=>({}));
  if(!r.ok){ const e=new Error(body.detail||`השרת ענה ${r.status}`); e.status=r.status; throw e; }
  return body;
}
const SAY={"no vote with this code":"אין הצבעה פתוחה עם הקוד הזה. בדקו את הקוד ונסו שוב.","no votes yet":"עוד אף אחד לא הצביע.",
  "this riddle is no longer open for votes":"ההצבעה על החידה הזאת כבר נסגרה.","this vote is full":"ההצבעה מלאה.",
  "too many votes are open right now":"יש עכשיו יותר מדי הצבעות פתוחות. נסו שוב בעוד כמה דקות."};
const say=e=>SAY[e.message]||e.message||"משהו השתבש. נסו שוב.";

function stop(){ clearTimeout(timer); timer=null; }
const alive=()=>box&&box.isConnected&&box.querySelector(".sci");
function draw(html){ box.innerHTML=`<div class="sci">${html}</div>`; }
const header=(title,sub,act='<button class="mx-btn" data-act="subjects">לכל המקצועות</button>')=>
  `<header class="mx-top"><div><h1>${esc(title)}</h1><p class="mx-sub">${esc(sub)}</p></div>${act}</header>`;

async function show(container,opts={}){
  if(box!==container){ container.addEventListener("click",onClick); }
  box=container; stop(); ROOM=null; msg="";
  draw(`${header("מדעים","המקצועות שלי")}<p class="mx-note">טוענים את המסלול…</p>`);
  if(!PATH){
    try{ PATH=await call("/api/science"); }
    catch(e){ return draw(`${header("מדעים","המקצועות שלי")}<p class="mx-note">לא הצלחנו לטעון את המסלול: ${esc(say(e))}</p>`); }
  }
  drawPath();
}
function drawPath(){
  stop(); ROOM=null;
  draw(`${header(PATH.subject,"המקצועות שלי")}${PATH.units.map(u=>`<section class="sci-unit">
    <div class="sci-unit-head"><span aria-hidden="true">🧩</span><div><h2>${esc(u.name)}</h2><p>${esc(u.description||"")}</p></div></div>
    ${PATH.skills.filter(s=>s.unit===u.id).map(s=>`<button class="sci-skill" data-sci="lobby" data-skill="${esc(s.id)}">
      <span class="sci-skill-icon" aria-hidden="true">🚀</span><span><b>${esc(s.name)}</b><small>${esc(s.description||"")}</small><small>${s.riddles} חידות · הצבעה כיתתית</small></span><i aria-hidden="true">‹</i></button>`).join("")}
  </section>`).join("")}`);
}
function drawLobby(skillId){
  stop(); ROOM=null;
  const s=PATH.skills.find(x=>x.id===skillId);
  draw(`${header(s.name,"חידות · מדעים",'<button class="mx-btn" data-sci="path">חזרה</button>')}
    <section class="sci-card"><h2>פתיחת הצבעה</h2><p>למורה או למי שמציג על הלוח: פותחים הצבעה, ומקבלים קוד שהכיתה מצטרפת איתו.</p>
      <button class="mx-btn solid" data-sci="open" data-skill="${esc(s.id)}"${busy?" disabled":""}>פתיחת הצבעה לכיתה</button></section>
    <section class="sci-card"><h2>הצטרפות להצבעה</h2><p>הקלידו את הקוד שמופיע על הלוח.</p>
      <form class="sci-join" data-sci-join><input name="code" inputmode="numeric" autocomplete="off" maxlength="4" pattern="[0-9]{4}" placeholder="קוד בן 4 ספרות" aria-label="קוד ההצבעה" required>
      <button class="mx-btn solid"${busy?" disabled":""}>הצטרפות</button></form></section>
    ${msg?`<p class="sci-msg" role="alert">${esc(msg)}</p>`:""}`);
  box.querySelector("[data-sci-join]").onsubmit=e=>{ e.preventDefault(); join(e.target.code.value.trim(),s.id); };
}

async function openRoom(skillId){
  busy=true; msg=""; drawLobby(skillId);
  try{ const st=await call("/api/science/rooms",{method:"POST",body:JSON.stringify({skill:skillId})});
    store.set(`mathly.science.host:${st.code}`,st.host_key,sessionStorage); ROOM={code:st.code,skill:skillId}; busy=false; render(st); poll(); }
  catch(e){ busy=false; msg=say(e); drawLobby(skillId); }
}
async function join(code,skillId){
  if(!/^\d{4}$/.test(code)){ msg="הקוד הוא 4 ספרות."; return drawLobby(skillId); }
  busy=true; msg=""; ROOM={code,skill:skillId};
  try{ const st=await call(`/api/science/rooms/${code}?voter=${VOTER}`); busy=false; render(st); poll(); }
  catch(e){ busy=false; ROOM=null; msg=say(e); drawLobby(skillId); }
}
function poll(){
  stop();
  timer=setTimeout(async()=>{
    if(!ROOM||!alive()) return stop();
    try{ render(await call(`/api/science/rooms/${ROOM.code}?voter=${VOTER}`)); }
    catch(e){ if(e.status===404){ msg="ההצבעה הסתיימה."; return drawLobby(ROOM.skill); } }
    poll();
  },POLL);
}
async function act(url,body){
  try{ const st=await call(url,{method:"POST",...(body?{body:JSON.stringify(body)}:{})}); ROOM.err=""; render(st,true); }
  catch(e){ ROOM.err=say(e); render(ROOM.last,true); }
}

const OUT={flies:["הטיל המריא! 🚀","flies"],falls:["הדלק נגמר באמצע הדרך, והטיל נפל בחזרה","falls"],stuck:["הטיל כבד מדי ולא זז מכן השיגור","stuck"]};
function rocket(st){
  const key=`${st.code}:${st.n}`, now=st.phase==="checked"&&!launched.has(key);
  if(now) launched.add(key);
  const cls=st.phase!=="checked"?"":`${now?"go":"end"}-${st.outcome}`;
  return `<div class="sci-stage ${cls}" aria-hidden="true"><div class="sci-sky"></div>
    <svg class="sci-rocket" viewBox="0 0 60 140"><g class="sci-flame"><path d="M20 112 Q30 150 40 112Z" fill="#FF8B5C"/><path d="M25 112 Q30 136 35 112Z" fill="#F7C948"/></g>
      <path d="M30 6 C44 22 46 50 46 80 V108 H14 V80 C14 50 16 22 30 6Z" fill="#EAF0FF"/><path d="M30 6 C38 15 42 26 44 36 H16 C18 26 22 15 30 6Z" fill="#F08A96"/>
      <circle cx="30" cy="56" r="8" fill="#6FB3D2" stroke="#27335F" stroke-width="3"/><path d="M14 84 L2 110 H14Z M46 84 L58 110 H46Z" fill="#F08A96"/><rect x="18" y="106" width="24" height="6" rx="2" fill="#5B6694"/></svg>
    <div class="sci-smoke"><i></i><i></i><i></i></div><div class="sci-pad"></div></div>`;
}
function render(st,force=false){
  if(!ROOM||!st) return;
  const sig=JSON.stringify(st)+(ROOM.err||"");
  if(!force&&sig===SHOWN&&alive()) return;
  SHOWN=sig; ROOM.last=st;
  const done=st.phase==="checked", total=st.votes, counts=st.counts||[];
  const choices=st.choices.map((text,i)=>{
    const pct=done&&total?Math.round(100*counts[i]/total):0;
    const cls=["sci-choice",st.mine===i&&"mine",done&&i===st.picked&&"picked",done&&i===st.right&&"right",st.tie.includes(i)&&"tied"].filter(Boolean).join(" ");
    return `<button class="${cls}" data-sci="vote" data-choice-i="${i}"${done?" disabled":""} aria-pressed="${st.mine===i}">
      ${done?`<span class="sci-bar" style="width:${pct}%"></span>`:""}<b>⛽ ${esc(text)}</b>${done?`<small>${counts[i]===1?"קול אחד":`${counts[i]} קולות`}</small>`:st.mine===i?"<small>ההצבעה שלך</small>":""}</button>`;
  }).join("");
  const tie=st.tie.length&&!done?`<p class="sci-msg">תיקו בין ${st.tie.map(i=>esc(st.choices[i])).join(" ובין ")}. אפשר לשנות הצבעה ולבדוק שוב.</p>`:"";
  const result=done?`<section class="sci-result ${OUT[st.outcome][1]}" role="status"><h3>${OUT[st.outcome][0]}</h3>
      <p>הרוב בחר <b>${esc(st.choices[st.picked])}</b> (${counts[st.picked]} מתוך ${total}).</p><p>${fmt(st.why)}</p>
      ${st.picked!==st.right?`<p>התשובה שהייתה מצליחה: <b>${esc(st.choices[st.right])}</b></p>`:""}</section>`:"";
  const host=st.host?`<div class="sci-host">${done
      ?(st.n<st.of?'<button class="mx-btn solid" data-sci="next">לחידה הבאה</button>':'<button class="mx-btn solid" data-sci="path">סיום</button>')
      :`<button class="mx-btn solid" data-sci="check"${total?"":" disabled"}>בדיקה: שיגור עם תשובת הרוב</button>`}</div>`:"";
  draw(`${header(st.name,`חידה ${st.n} מתוך ${st.of}`,'<button class="mx-btn" data-sci="leave">יציאה מההצבעה</button>')}
    <div class="sci-code${st.host?" big":""}"><span>${st.host?"הקוד להצטרפות":"קוד ההצבעה"}</span><b dir="ltr">${esc(st.code)}</b></div>
    <section class="sci-card sci-riddle"><h2>${esc(st.title)}</h2><p>${fmt(st.story)}</p><p class="sci-q">${esc(st.question)}</p></section>
    ${rocket(st)}${result}
    <div class="sci-choices">${choices}</div>
    <p class="sci-count" aria-live="polite">${done?`${total} הצביעו`:`${total} ${total===1?"הצביע":"הצביעו"} עד עכשיו · התוצאות ייחשפו בבדיקה`}</p>
    ${tie}${ROOM.err?`<p class="sci-msg" role="alert">${esc(ROOM.err)}</p>`:""}${host}`);
}

function onClick(e){
  const t=e.target.closest("[data-sci]"); if(!t||!box.contains(t)) return;
  switch(t.dataset.sci){
    case "path": return drawPath();
    case "lobby": msg=""; return drawLobby(t.dataset.skill);
    case "open": return openRoom(t.dataset.skill);
    case "leave": { const s=ROOM?.skill; stop(); ROOM=null; msg=""; return drawLobby(s); }
    case "vote": return act(`/api/science/rooms/${ROOM.code}/vote`,{voter:VOTER,choice:+t.dataset.choiceI,n:ROOM.last.n});
    case "check": return act(`/api/science/rooms/${ROOM.code}/check?voter=${VOTER}`);
    case "next": return act(`/api/science/rooms/${ROOM.code}/next?voter=${VOTER}`);
  }
}

window.MathlyScience={show,stop};
})();
