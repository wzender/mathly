/* Same-account handwritten answers. Every async continuation checks its account
   and view before changing the UI. The server is authoritative for all states. */
(()=>{
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=s=>esc(s).replace(/\$([^$]+)\$/g,'<span class="m">$1</span>');
const states={waiting:"ממתינים לטלפון",confirmed:"ממתינים לטלפון",uploading:"מעלים את התשובה…",received:"התשובה התקבלה",failed:"ההעלאה נכשלה",expired:"בקשת הצילום פגה",superseded:"הבקשה הוחלפה",declined:"הבקשה נדחתה בטלפון"};
const errors={expired:"בקשת הצילום פגה. צרו בקשה חדשה ונסו שוב.",superseded:"הבקשה הוחלפה. בחרו את הבקשה העדכנית.",upload_in_progress:"העלאה כבר מתבצעת. ממתינים לעדכון…",confirmation_required:"יש לאשר את בקשת הצילום תחילה.",invalid_upload:"ההעלאה הופסקה. נסו שוב.",question_changed:"השאלה השתנתה. רעננו את העמוד ופתחו אותה מחדש.",invalid_image:"לא ניתן לקרוא את התמונה. צלמו שוב.",image_too_large:"התמונה גדולה מדי. צלמו שוב.",unsupported_image:"בחרו תמונת JPEG, PNG או WebP.",answer_storage_unavailable:"שמירת תשובות אינה זמינה כרגע. נסו שוב מאוחר יותר.",sign_in_required:"יש להיכנס לאותו חשבון בשני המכשירים."};
Object.assign(errors,{grading_unavailable:"בדיקת תשובות אינה זמינה כרגע באתר.",grading_failed:"הבדיקה נכשלה. התמונה נשמרה; אפשר לנסות שוב.",grading_interrupted:"הבדיקה הופסקה. אפשר לנסות שוב.",grading_limit:"הגעתם למכסת 20 הבדיקות היומית. נסו שוב מחר.",grading_busy:"כבר מתבצעות בדיקות בחשבון. נסו שוב בעוד רגע.",answer_required:"יש לצלם ולשלוח תשובה לפני הבדיקה."});
const verdicts={correct:"נכון! הפתרון מלא",partial:"פתרון נכון בחלקו",incorrect:"יש לתקן את הפתרון",unreadable:"לא ניתן לקרוא את התשובה",needs_review:"נדרשת הבהרה לפני מתן ציון"};
let api=null,account=null,epoch=0,question=null,inbox=false,inboxTimer=null,inboxPoll=null,capture=null,visibleRoot=null,onGraded=null,waiting=null;
const handled=new Set();   // requests this phone already answered (photographed or declined): not shown again
const live=(e)=>e===epoch&&!!account;
async function json(url,options={}){
  const r=await api(url,{cache:"no-store",...options});
  const d=await r.json().catch(()=>({}));
  if(!r.ok){if(r.status===401)reset();const error=Error(errors[d.detail]||"החיבור נקטע. נסו שוב.");error.status=r.status;error.code=d.detail;throw error;}
  return d;
}
const post=(url,body={})=>json(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
function closeQuestion(){
  if(question){clearTimeout(question.timer);if(question.image)URL.revokeObjectURL(question.image);question=null;}
}
function closeCapture(){
  if(capture){if(capture.url)URL.revokeObjectURL(capture.url);capture.node.remove();capture.returnFocus?.focus?.();capture=null;}
}
function reset(){
  epoch++;if(question)question.node.replaceChildren();closeQuestion();closeCapture();closeWait();clearTimeout(inboxTimer);inboxTimer=null;
  inbox=false;account=null;onGraded=null;
}
function configure(options){
  reset();api=options.api;account=options.enabled?options.account:null;visibleRoot=options.root;onGraded=options.onGraded;
  if(!account)return;
  // The phone (the responsive app/PWA) watches for requests from the computer and pops them up.
  if(matchMedia("(max-width: 700px)").matches||navigator.maxTouchPoints){inbox=true;pollInbox(epoch);}
}
/* The phone looks for requests every few seconds while the app is open. A new request pops up as a window with its
   4-digit code (the same code the computer shows); the student photographs the answer or declines. */
async function pollInbox(e){
  clearTimeout(inboxTimer);if(!live(e)||!inbox||inboxPoll===e)return;
  if(document.hidden){inboxTimer=setTimeout(()=>pollInbox(e),5000);return;}
  inboxPoll=e;
  let delay=3000;
  try{
    const list=await json("/api/math/answer-scans");if(!live(e)||!inbox)return;
    if(capture&&!capture.ended){
      const mine=list.find(r=>r.attempt.id===capture.result.attempt.id);
      // withdrawn on the computer (or replaced there by a new request): this window has nothing left to answer
      if(!mine||mine.scan.id!==capture.result.scan.id&&!capture.busy)capture.withdrawn?.(mine);
    }
    const ask=list.find(r=>["waiting","confirmed","failed"].includes(r.scan.state)&&!handled.has(r.scan.id));
    if(ask&&!capture)openCapture(ask);
  }catch(error){
    if(!live(e))return;
    if(error.status===401){reset();return;}
    delay=15000;
  }finally{if(inboxPoll===e)inboxPoll=null;}
  if(live(e))inboxTimer=setTimeout(()=>pollInbox(e),delay);
}
async function mountQuestion(node,id,version,fresh=false){
  closeQuestion();const e=epoch;
  if(!account){node.innerHTML='<p>כדי לסרוק תשובה בטלפון, היכנסו לאותו חשבון בשני המכשירים. שמירת תשובות צריכה להיות זמינה באתר.</p>';return;}
  const q=question={node,id,version,e,timer:null,image:null,busy:false,result:null,grading:false};
  node.innerHTML='<p role="status">טוענים את ניסיון התשובה…</p>';
  try{const r=await post("/api/math/answer-attempts",{question_id:id,question_version:version,new:fresh});if(!current(q))return;q.result=r;await renderQuestion(q);schedule(q);}
  catch(error){if(current(q)){node.innerHTML=`<p role="status">${esc(error.message)}</p><button class="mx-btn" data-reload>ניסיון נוסף</button>`;node.querySelector("button").onclick=()=>error.code==="question_changed"?location.reload():mountQuestion(node,id,version);}}
}
const current=q=>question===q&&live(q.e)&&q.node.isConnected;
function schedule(q,delay=2000){clearTimeout(q.timer);if(current(q))q.timer=setTimeout(()=>pollQuestion(q),delay);}
async function pollQuestion(q){
  if(!current(q)||q.polling)return;
  if(document.hidden){schedule(q,5000);return;}
  q.polling=true;
  try{
    const r=await json(`/api/math/answer-attempts/${q.result.attempt.id}`);if(!current(q))return;
    q.result=r;await renderQuestion(q);schedule(q);
  }catch(error){if(current(q)){q.node.querySelector("[role=status]").textContent=error.message;schedule(q,8000);}}
  finally{q.polling=false;}
}
async function renderQuestion(q){
  if(!current(q))return;
  const r=q.result,s=r.scan,state=s?.state,received=!!r.attachment,g=r.grading;
  const checking=q.grading||g?.state==="grading";
  const statusText=checking?"בודקים את התשובה…":g?.state==="completed"?verdicts[g.result.verdict]:g?.state==="failed"?errors[g.error]||errors.grading_failed:states[state]||"כתבו את הפתרון על דף וצלמו אותו בטלפון.";
  // Rebuilding controls on every poll would steal focus and race a button click.
  const signature=[state,r.attachment?.id,g?.id,g?.state,r.grading_available].join(":");
  if(q.signature!==signature){
    q.signature=signature;
    q.node.innerHTML=`<small>ניסיון ${esc(r.attempt.id.slice(0,8))}</small><p role="status" aria-live="polite">${esc(statusText)}</p>
      ${received?`<img class="mx-answer-image" alt="התשובה המצולמת שלכם" hidden>${gradingPanel(r,checking)}
        <button class="mx-btn" data-new-attempt ${checking?"disabled":""}>ניסיון חדש וצילום מחדש</button>`:`<button class="mx-btn solid mx-phone-cta" data-request><span aria-hidden="true">📱</span> ${s?["expired","superseded","declined"].includes(state)?"בקשת צילום חדשה לטלפון":waitingState(state)?"הצגת המספר לטלפון":"ניסיון נוסף בטלפון":"צילום התשובה בטלפון"}</button>`}`;
    if(!received){
      const b=q.node.querySelector("[data-request]");b.disabled=state==="uploading";
      b.onclick=async()=>{
        b.disabled=true;
        try{
          const result=waitingState(q.result.scan?.state)?q.result:await post(`/api/math/answer-attempts/${r.attempt.id}/scans`,
            {question_id:q.id,renew:["expired","superseded","failed","declined"].includes(q.result.scan?.state)});
          if(!current(q))return;q.result=result;q.signature=null;await renderQuestion(q);
          const end=await waitForPhone(result,{question_id:q.id});
          if(end&&current(q)){q.result=end;q.signature=null;await renderQuestion(q);}
          schedule(q,0);
        }
        catch(error){if(current(q)){q.node.querySelector("[role=status]").textContent=error.message;b.disabled=false;}}
      };
    }
    if(received){
      const gradeButton=q.node.querySelector("[data-grade]");
      if(gradeButton)gradeButton.onclick=()=>checkAnswer(q);
      q.node.querySelector("[data-new-attempt]").onclick=()=>mountQuestion(q.node,q.id,q.version,true);
    }
  }else q.node.querySelector("[role=status]").textContent=statusText;
  if(g?.state==="completed"&&q.notified!==g.id){q.notified=g.id;onGraded?.({questionId:q.id,grading:g});}
  if(received&&!q.image&&!q.loadingImage){
    q.loadingImage=true;
    try{
      const response=await api(`/api/math/answer-attempts/${r.attempt.id}/image`,{cache:"no-store"});
      if(!response.ok)throw Error("לא ניתן לטעון את התמונה. מנסים שוב…");
      const blob=await response.blob();if(!current(q))return;
      q.image=URL.createObjectURL(blob);const img=q.node.querySelector("img");
      img.onload=()=>{if(current(q))img.hidden=false;};img.src=q.image;
    }catch(error){if(current(q))q.node.querySelector("[role=status]").textContent=error.message;}
    finally{q.loadingImage=false;}
  }else if(q.image&&q.node.querySelector("img")){const img=q.node.querySelector("img");img.src=q.image;img.hidden=false;}
  // Resume a first check if the page closed or the server restarted just after
  // receipt. Failed checks require an explicit retry, so polling cannot spend
  // the student's daily allowance on repeated provider failures.
  if(received&&r.grading_available&&!g&&!q.autoStarted){
    q.autoStarted=true;checkAnswer(q,true);
  }
}
function gradingPanel(r,checking){
  const g=r.grading;
  if(g?.state==="completed"){
    const a=g.result;
    return `<section class="mx-grade ${a.verdict==="correct"?"mx-grade-correct":""}" aria-label="תוצאות בדיקת התשובה">
      <h4>${esc(verdicts[a.verdict])}${a.score==null?"":` · <span class="m">${esc(a.score)}/100</span>`}</h4>
      <p>${fmt(a.feedback)}</p>${a.next_step?`<p><b>הצעד הבא: </b>${fmt(a.next_step)}</p>`:""}
      ${a.transcription?`<details><summary>מה קראנו בתמונה</summary><p>${fmt(a.transcription)}</p></details>`:""}
      ${a.solution?`<details><summary>הפתרון המלא</summary><p class="mx-grade-solution">${fmt(a.solution)}</p></details>`:""}
      <small>בדיקה אוטומטית באמצעות AI. בדקו שהתמלול תואם למה שכתבתם.</small></section>`;
  }
  if(!r.grading_available&&!checking)return '<p>התמונה נשמרה כתשובה. בדיקה אוטומטית אינה זמינה כרגע באתר.</p>';
  return `<p>התשובה נשלחת לבדיקה אוטומטית באמצעות AI.</p>
    <button class="mx-btn solid" data-grade ${checking?"disabled":""}>${checking?"בודקים את התשובה…":g?.state==="failed"?"ניסיון בדיקה נוסף":"בדיקת התשובה"}</button>`;
}
async function checkAnswer(q,automatic=false){
  if(!current(q)||q.grading)return;
  q.grading=true;q.signature=null;await renderQuestion(q);schedule(q);
  try{
    const r=await post(`/api/math/answer-attempts/${q.result.attempt.id}/grade`,{automatic});
    if(!current(q))return;q.result=r;
  }catch(error){if(current(q))q.gradeError=error.message;}
  finally{
    if(current(q)){
      q.grading=false;q.signature=null;await renderQuestion(q);
      if(q.gradeError){q.node.querySelector("[role=status]").textContent=q.gradeError;q.gradeError=null;}
      schedule(q);
    }
  }
}
const waitingState=st=>st==="waiting"||st==="confirmed";
const codeHTML=code=>`<div class="mx-scan-code" dir="ltr" aria-label="מספר מזהה ${esc([...String(code||"")].join(" "))}">${[...String(code||"----")].map(d=>`<span>${esc(d)}</span>`).join("")}</div>`;
// keeps Tab inside a window
function trapTab(node,event){
  if(event.key!=="Tab")return;
  const buttons=[...node.querySelectorAll("button")].filter(b=>!b.hidden&&!b.disabled&&b.offsetParent);
  if(event.shiftKey&&document.activeElement===buttons[0]){event.preventDefault();buttons.at(-1)?.focus();}
  else if(!event.shiftKey&&document.activeElement===buttons.at(-1)){event.preventDefault();buttons[0]?.focus();}
}

/* ---------- the phone: a window for a request from the computer ---------- */
function openCapture(result){
  closeCapture();const e=epoch;
  if(!live(e))return;
  const node=document.createElement("div");node.className="mx-scan-overlay";node.setAttribute("role","alertdialog");node.setAttribute("aria-modal","true");node.setAttribute("aria-labelledby","scanTitle");
  node.innerHTML=`<div class="mx-scan-card mx-scan-ask">
    <h2 id="scanTitle"><span aria-hidden="true">📷</span> בקשת צילום מהמחשב</h2>
    <p>בדקו שזה אותו מספר שמופיע במחשב:</p>${codeHTML(result.scan.code)}
    <div class="mx-scan-q"><small>השאלה</small><p>${fmt(result.attempt.snapshot.question)}</p></div>
    <img class="mx-answer-image" data-preview alt="תצוגה מקדימה של התשובה" hidden>
    <p data-status role="status" aria-live="polite">כתבו את הפתרון על דף וצלמו אותו.</p>
    <input data-camera type="file" accept="image/*" capture="environment" hidden>
    <div class="mx-scan-actions">
      <button class="mx-btn solid" data-take>📷 צילום התשובה</button>
      <button class="mx-btn solid" data-submit hidden>שליחה למחשב</button>
      <button class="mx-btn" data-renew hidden>בקשה חדשה</button>
      <button class="mx-btn mx-btn-quiet" data-decline>סירוב</button>
      <button class="mx-btn" data-close hidden>סגירה</button>
    </div>
    <small>כשהבדיקה האוטומטית זמינה, צילום התשובה יישלח לבדיקה באמצעות AI. המשוב יופיע בשאלה במחשב.</small></div>`;
  const c=capture={node,e,result,photo:null,url:null,key:null,busy:false,ended:false,confirming:null,returnFocus:document.activeElement};visibleRoot.append(node);
  const $=sel=>node.querySelector(sel);
  const status=$("[data-status]"),camera=$("[data-camera]"),take=$("[data-take]"),send=$("[data-submit]"),preview=$("[data-preview]"),renew=$("[data-renew]"),decline=$("[data-decline]"),close=$("[data-close]");
  const valid=()=>capture===c&&live(e),say=message=>{if(valid())status.textContent=message;};
  const controls=busy=>{c.busy=busy;take.disabled=send.disabled=renew.disabled=decline.disabled=busy;};
  // the request is over: only closing is left
  const finish=message=>{c.ended=true;handled.add(c.result.scan.id);take.hidden=send.hidden=renew.hidden=decline.hidden=true;close.hidden=false;say(message);close.focus();};
  const expired=()=>{take.hidden=send.hidden=true;renew.hidden=false;say(errors.expired);};
  c.withdrawn=mine=>{ if(c.photo&&mine&&waitingState(mine.scan.state)){c.result=mine;return;} finish("הבקשה בוטלה במחשב."); };
  close.onclick=()=>{closeCapture();if(valid())pollInbox(e);};
  node.onkeydown=event=>{
    if(event.key==="Escape"){event.preventDefault();event.stopPropagation();if(c.ended)close.click();}
    trapTab(node,event);
  };
  // confirming happens in the background, so the camera opens right from the tap
  const confirmed=()=>c.confirming||=(async()=>{
    const r=await post(`/api/math/answer-scans/${c.result.scan.id}/confirm`);if(valid())c.result=r;return r;
  })().catch(error=>{c.confirming=null;throw error;});
  take.onclick=()=>{
    say("צלמו את הפתרון. אם המצלמה חסומה, אפשרו אותה בהגדרות האתר ונסו שוב.");camera.click();
    confirmed().then(r=>{if(r.attachment&&valid())success();}).catch(error=>{if(valid()){say(error.message);if(error.status===410)expired();}});
  };
  camera.addEventListener("cancel",()=>say("הצילום בוטל או שלא ניתנה הרשאה. אפשר לצלם שוב או לסרב."));
  camera.onchange=async()=>{
    const file=camera.files[0];camera.value="";if(!file||!valid())return;
    controls(true);say("מכינים את התמונה…");
    try{
      const photo=await window.MathlyPhoto.prepare(file);if(!valid())return;
      if(photo.size>5000000)throw Error(errors.image_too_large);
      if(c.url)URL.revokeObjectURL(c.url);
      c.photo=photo;c.key=null;preview.src=c.url=URL.createObjectURL(photo);preview.hidden=false;
      take.textContent="צילום מחדש";take.classList.remove("solid");send.hidden=false;say("בדקו שכל הפתרון ברור, ואז שלחו למחשב.");send.focus();
    }catch(error){say("לא ניתן להכין את התמונה. נסו לצלם שוב.");}
    finally{if(valid())controls(false);}
  };
  const success=()=>{c.photo=null;finish("✓ התשובה נשלחה למחשב.");};
  send.onclick=async()=>{
    if(!c.photo||c.busy)return;
    controls(true);say(states.uploading);
    try{
      await confirmed();if(!valid())return;
      c.key=c.key||crypto.randomUUID();
      let b=await post(`/api/math/answer-scans/${c.result.scan.id}/uploads`,{key:c.key});if(!valid())return;
      if(b.attachment){success();return;}
      const form=new FormData();form.append("photo",c.photo,"answer.jpg");
      b=await json(`/api/math/answer-scans/${c.result.scan.id}/uploads/${b.lease_id}`,{method:"POST",body:form});
      if(!valid())return;c.result=b;success();
    }catch(error){
      if(!valid())return;say(error.message+" התמונה נשמרה לתצוגה מקדימה. אפשר לנסות שוב.");
      if(error.status===410||error.code==="superseded")expired();
      // Reuse the key after an uncertain response; the server returns prior success.
    }finally{if(valid()&&!c.ended)controls(false);}
  };
  decline.onclick=async()=>{
    controls(true);
    try{await post(`/api/math/answer-scans/${c.result.scan.id}/decline`);if(!valid())return;finish("סירבתם לבקשה. המחשב קיבל הודעה.");}
    catch(error){if(!valid())return;if(error.code==="superseded"||error.status===404)finish("הבקשה כבר לא פעילה.");else say(error.message);}
    finally{if(valid()&&!c.ended)controls(false);}
  };
  renew.onclick=async()=>{
    controls(true);
    try{const r=await post(`/api/math/answer-attempts/${c.result.attempt.id}/scans`,{renew:true});if(!valid())return;
      c.result=r;c.key=null;c.confirming=null;renew.hidden=true;take.hidden=false;node.querySelector(".mx-scan-code").outerHTML=codeHTML(r.scan.code);
      say("נוצרה בקשה חדשה עם מספר חדש. אפשר לצלם.");}
    catch(error){say(error.message);}
    finally{if(valid())controls(false);}
  };
  if(result.scan.state==="expired")expired();
  if(navigator.vibrate)try{navigator.vibrate([60,40,60]);}catch{}
  take.focus();
}

/* ---------- the computer: waiting for the phone ---------- */
/* A window with the request's 4-digit code until the phone answers. Resolves with the attempt's last result (photo
   received, declined, expired or withdrawn here), or null when the account changed. `scanTo`: the body for a new
   request ({question_id} when it belongs to a question). */
function closeWait(){ if(waiting){clearTimeout(waiting.timer);waiting.node.remove();waiting.returnFocus?.focus?.({preventScroll:true});const done=waiting.done;waiting=null;done(null);} }
function waitForPhone(result,scanTo={}){
  closeWait();const e=epoch;
  if(!live(e))return Promise.resolve(null);
  return new Promise(done=>{
    const node=document.createElement("div");node.className="mx-scan-overlay mx-scan-wait";node.setAttribute("role","dialog");node.setAttribute("aria-modal","true");node.setAttribute("aria-labelledby","waitTitle");
    node.innerHTML=`<div class="mx-scan-card">
      <h2 id="waitTitle"><span aria-hidden="true">📱</span> צילום בטלפון</h2>
      <p data-say>פתחו את Mathly בטלפון, באותו חשבון. יקפוץ שם חלון עם המספר הזה:</p>
      <div data-code></div>
      <p class="mx-scan-live" data-status role="status" aria-live="polite"><span class="mx-scan-dot" aria-hidden="true"></span><span data-text>ממתינים לטלפון…</span></p>
      <div class="mx-scan-actions">
        <button class="mx-btn solid" data-again hidden>בקשה חדשה</button>
        <button class="mx-btn" data-cancel>ביטול הבקשה</button>
        <button class="mx-btn" data-done hidden>סגירה</button>
      </div></div>`;
    const w=waiting={node,timer:null,result,returnFocus:document.activeElement,done:r=>done(r)};(visibleRoot||document.body).append(node);
    const $=sel=>node.querySelector(sel);
    const valid=()=>waiting===w&&live(e);
    const end=r=>{ if(waiting!==w)return; clearTimeout(w.timer);node.remove();waiting=null;w.returnFocus?.focus?.({preventScroll:true});done(r); };
    let shown=null;
    const paint=()=>{
      const r=w.result,st=r.scan?.state,got=!!r.attachment;
      if(got){ end(r); return; }
      if(shown!==r.scan?.id){ shown=r.scan?.id; $("[data-code]").innerHTML=codeHTML(r.scan?.code); }
      const over=["declined","expired","superseded"].includes(st);
      const text={waiting:"ממתינים לטלפון…",confirmed:"הטלפון אישר. ממתינים לצילום…",uploading:"מקבלים את התמונה מהטלפון…",failed:"ההעלאה מהטלפון נכשלה. אפשר לנסות שוב בטלפון.",
        declined:"הבקשה נדחתה בטלפון.",expired:"הבקשה פגה. אפשר ליצור בקשה חדשה.",superseded:"הבקשה הוחלפה."}[st]||"ממתינים לטלפון…";
      $("[data-text]").textContent=text;
      node.classList.toggle("is-over",over);node.classList.toggle("is-declined",st==="declined");
      $("[data-say]").hidden=over;$("[data-code]").hidden=over;
      $("[data-again]").hidden=$("[data-done]").hidden=!over;$("[data-cancel]").hidden=over||st==="uploading";
    };
    const poll=async()=>{
      clearTimeout(w.timer);if(!valid())return;
      try{ const r=await json(`/api/math/answer-attempts/${w.result.attempt.id}`);if(!valid())return;w.result=r;paint(); }
      catch(error){ if(!valid())return;$("[data-text]").textContent=error.message; }
      if(valid()&&!["declined","expired","superseded"].includes(w.result.scan?.state))w.timer=setTimeout(poll,document.hidden?5000:2000);
    };
    $("[data-cancel]").onclick=async()=>{
      const b=$("[data-cancel]");b.disabled=true;
      try{ w.result=await post(`/api/math/answer-scans/${w.result.scan.id}/decline`,{});if(!valid())return; }
      catch(error){ if(!valid())return; }
      end(w.result);
    };
    $("[data-done]").onclick=()=>end(w.result);
    $("[data-again]").onclick=async()=>{
      const b=$("[data-again]");b.disabled=true;
      try{ w.result=await post(`/api/math/answer-attempts/${w.result.attempt.id}/scans`,{...scanTo,renew:true});if(!valid())return;paint();poll(); }
      catch(error){ if(valid())$("[data-text]").textContent=error.message; }
      finally{ b.disabled=false; }
    };
    node.onkeydown=event=>{ if(event.key==="Escape"){event.preventDefault();event.stopPropagation();} trapTab(node,event); };
    paint(); if(waiting===w){ $("[data-cancel]").focus(); w.timer=setTimeout(poll,1500); }
  });
}
document.addEventListener("visibilitychange",()=>{
  if(document.hidden)return;
  if(account&&inbox)pollInbox(epoch);
  if(question?.result)pollQuestion(question);
});
window.addEventListener("online",()=>{if(account&&inbox)pollInbox(epoch);if(question?.result)pollQuestion(question);});
window.MathlyAnswers={configure,mountQuestion,closeQuestion,reset,waitForPhone};
})();
