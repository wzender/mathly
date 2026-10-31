/* Same-account handwritten answers. Every async continuation checks its account
   and view before changing the UI. The server is authoritative for all states. */
(()=>{
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=s=>esc(s).replace(/\$([^$]+)\$/g,'<span class="m">$1</span>');
const states={waiting:"ממתינים לטלפון",confirmed:"ממתינים לטלפון",uploading:"מעלים את התשובה…",received:"התשובה התקבלה",failed:"ההעלאה נכשלה",expired:"בקשת הצילום פגה",superseded:"הבקשה הוחלפה"};
const errors={expired:"בקשת הצילום פגה. צרו בקשה חדשה ונסו שוב.",superseded:"הבקשה הוחלפה. בחרו את הבקשה העדכנית.",upload_in_progress:"העלאה כבר מתבצעת. ממתינים לעדכון…",confirmation_required:"יש לאשר את בקשת הצילום תחילה.",invalid_upload:"ההעלאה הופסקה. נסו שוב.",question_changed:"השאלה השתנתה. רעננו את העמוד ופתחו אותה מחדש.",invalid_image:"לא ניתן לקרוא את התמונה. צלמו שוב.",image_too_large:"התמונה גדולה מדי. צלמו שוב.",unsupported_image:"בחרו תמונת JPEG, PNG או WebP.",answer_storage_unavailable:"שמירת תשובות אינה זמינה כרגע. נסו שוב מאוחר יותר.",sign_in_required:"יש להיכנס לאותו חשבון בשני המכשירים."};
let api=null,account=null,epoch=0,question=null,inbox=null,inboxTimer=null,inboxPoll=null,capture=null,visibleRoot=null;
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
  epoch++;if(question)question.node.replaceChildren();closeQuestion();closeCapture();clearTimeout(inboxTimer);inboxTimer=null;
  inbox?.remove();inbox=null;account=null;
}
function configure(options){
  reset();api=options.api;account=options.enabled?options.account:null;visibleRoot=options.root;
  if(!account)return;
  // Foreground discovery is available in the responsive phone app/PWA.
  if(matchMedia("(max-width: 700px)").matches||navigator.maxTouchPoints){
    inbox=document.createElement("section");inbox.className="mx-scan-inbox mx-wrap";
    inbox.setAttribute("aria-label","בקשות לצילום תשובה");visibleRoot.prepend(inbox);pollInbox(epoch);
  }
}
async function pollInbox(e){
  clearTimeout(inboxTimer);if(!live(e)||!inbox||inboxPoll===e)return;
  if(document.hidden){inboxTimer=setTimeout(()=>pollInbox(e),5000);return;}
  inboxPoll=e;
  let delay=5000;
  try{
    const list=await json("/api/math/answer-scans");if(!live(e)||!inbox)return;
    const signature=JSON.stringify(list.map(r=>[r.scan.id,r.scan.state]));
    if(inbox.dataset.signature!==signature){
      inbox.dataset.signature=signature;
      inbox.innerHTML=list.length?`<h2>בקשות לצילום תשובה</h2>${list.map((r,i)=>`<button class="mx-btn" data-scan-index="${i}"><b>${fmt(r.attempt.snapshot.question)}</b><small>ניסיון ${esc(r.attempt.id.slice(0,8))} · ${esc(states[r.scan.state])}</small></button>`).join("")}`:"";
      inbox.querySelectorAll("[data-scan-index]").forEach(button=>button.onclick=()=>openCapture(list[Number(button.dataset.scanIndex)]));
    }
  }catch(error){
    if(!live(e))return;
    if(error.status===401){reset();return;}
    if(inbox){inbox.textContent="לא ניתן לבדוק בקשות צילום כרגע. מנסים שוב…";delete inbox.dataset.signature;}delay=15000;
  }finally{if(inboxPoll===e)inboxPoll=null;}
  if(live(e))inboxTimer=setTimeout(()=>pollInbox(e),delay);
}
async function mountQuestion(node,id,version){
  closeQuestion();const e=epoch;
  if(!account){node.innerHTML='<p>כדי לסרוק תשובה בטלפון, היכנסו לאותו חשבון בשני המכשירים. שמירת תשובות צריכה להיות זמינה באתר.</p>';return;}
  const q=question={node,id,e,timer:null,image:null,busy:false,result:null};
  node.innerHTML='<p role="status">טוענים את ניסיון התשובה…</p>';
  try{const r=await post("/api/math/answer-attempts",{question_id:id,question_version:version});if(!current(q))return;q.result=r;await renderQuestion(q);schedule(q);}
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
  const r=q.result,s=r.scan,state=s?.state,received=!!r.attachment;
  // Rebuilding controls on every poll would steal focus and race a button click.
  const signature=[state,r.attachment?.id].join(":");
  if(q.signature!==signature){
    q.signature=signature;
    q.node.innerHTML=`<small>ניסיון ${esc(r.attempt.id.slice(0,8))}</small><p role="status" aria-live="polite">${esc(states[state]||"כתבו את הפתרון על דף וצלמו אותו בטלפון.")}</p>
      ${received?'<p>התמונה נשמרה כתשובה. היא עדיין לא נבדקה.</p><img class="mx-answer-image" alt="התשובה המצולמת שלכם" hidden>':`<button class="mx-btn solid" data-request>${s?["expired","superseded"].includes(state)?"יצירת בקשת צילום חדשה":state==="failed"?"ניסיון נוסף":"פתחו את Mathly בטלפון באותו חשבון":"סריקת התשובה שלי בטלפון"}</button>`}`;
    if(!received){
      const b=q.node.querySelector("[data-request]");b.disabled=["uploading","waiting","confirmed"].includes(state);
      b.onclick=async()=>{
        b.disabled=true;
        try{const result=await post(`/api/math/answer-attempts/${r.attempt.id}/scans`,{question_id:q.id,renew:["expired","superseded","failed"].includes(state)});
          if(!current(q))return;q.result=result;q.signature=null;await renderQuestion(q);schedule(q);}
        catch(error){if(current(q)){q.node.querySelector("[role=status]").textContent=error.message;b.disabled=false;}}
      };
    }
  }else q.node.querySelector("[role=status]").textContent=states[state]||"כתבו את הפתרון על דף וצלמו אותו בטלפון.";
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
  }else if(q.image&&q.node.querySelector("img"))q.node.querySelector("img").src=q.image;
}
function openCapture(result){
  closeCapture();const e=epoch;
  if(!live(e))return;
  const node=document.createElement("div");node.className="mx-scan-overlay";node.setAttribute("role","dialog");node.setAttribute("aria-modal","true");node.setAttribute("aria-labelledby","scanTitle");
  node.innerHTML=`<div class="mx-scan-card"><button class="mx-btn" data-close>סגירה</button><h2 id="scanTitle">צילום תשובה</h2>
    <p>${fmt(result.attempt.snapshot.question)}</p><small>ניסיון ${esc(result.attempt.id.slice(0,8))}</small>
    <p data-status role="status" aria-live="polite">האם לצלם תשובה לשאלה הזו?</p>
    <button class="mx-btn solid" data-confirm>כן, אני רוצה לצלם תשובה</button>
    <button class="mx-btn" data-renew hidden>יצירת בקשת צילום חדשה</button>
    <input data-camera type="file" accept="image/*" capture="environment" hidden>
    <button class="mx-btn" data-take hidden>צילום התשובה</button>
    <img class="mx-answer-image" data-preview alt="תצוגה מקדימה של התשובה" hidden>
    <button class="mx-btn solid" data-submit hidden>שליחת התשובה למחשב</button></div>`;
  const c=capture={node,e,result,photo:null,url:null,key:null,busy:false,returnFocus:document.activeElement};visibleRoot.append(node);
  const status=node.querySelector("[data-status]"),camera=node.querySelector("[data-camera]"),take=node.querySelector("[data-take]"),send=node.querySelector("[data-submit]"),preview=node.querySelector("[data-preview]"),confirm=node.querySelector("[data-confirm]"),renew=node.querySelector("[data-renew]");
  const valid=()=>capture===c&&live(e),say=message=>{if(valid())status.textContent=message;};
  const controls=busy=>{c.busy=busy;take.disabled=send.disabled=confirm.disabled=renew.disabled=busy;};
  const expired=()=>{confirm.hidden=true;take.hidden=true;send.hidden=true;renew.hidden=false;say(errors.expired);};
  node.querySelector("[data-close]").onclick=closeCapture;
  node.onkeydown=event=>{
    if(event.key==="Escape"&&!c.busy){event.preventDefault();event.stopPropagation();closeCapture();}
    if(event.key==="Tab"){
      const buttons=[...node.querySelectorAll("button")].filter(b=>!b.hidden&&!b.disabled);
      if(event.shiftKey&&document.activeElement===buttons[0]){event.preventDefault();buttons.at(-1)?.focus();}
      else if(!event.shiftKey&&document.activeElement===buttons.at(-1)){event.preventDefault();buttons[0]?.focus();}
    }
  };
  confirm.onclick=async()=>{
    controls(true);
    try{const r=await post(`/api/math/answer-scans/${c.result.scan.id}/confirm`);if(!valid())return;c.result=r;
      if(r.attachment){success();return;}
      confirm.hidden=true;take.hidden=false;say("בחרו צילום. אם תתבקשו, אפשרו גישה למצלמה.");take.focus();}
    catch(error){if(valid()){say(error.message);if(error.status===410)expired();}}
    finally{if(valid())controls(false);}
  };
  take.onclick=()=>{say("צלמו את הפתרון. אם המצלמה חסומה, אפשרו אותה בהגדרות האתר ונסו שוב.");camera.click();};
  camera.addEventListener("cancel",()=>say("הצילום בוטל או שלא ניתנה הרשאה. אפשר לנסות שוב בכפתור הצילום."));
  camera.onchange=async()=>{
    const file=camera.files[0];camera.value="";if(!file||!valid())return;
    controls(true);say("מכינים את התמונה…");
    try{
      const photo=await window.MathlyPhoto.prepare(file);if(!valid())return;
      if(photo.size>5000000)throw Error(errors.image_too_large);
      if(c.url)URL.revokeObjectURL(c.url);
      c.photo=photo;c.key=null;preview.src=c.url=URL.createObjectURL(photo);preview.hidden=false;
      take.textContent="צילום מחדש";send.hidden=false;say("בדקו שכל הפתרון ברור, ואז שלחו את התשובה.");
    }catch(error){say("לא ניתן להכין את התמונה. נסו לצלם שוב.");}
    finally{if(valid())controls(false);}
  };
  const success=()=>{say("התשובה הועלתה בהצלחה ומצורפת לשאלה במחשב.");take.hidden=send.hidden=confirm.hidden=renew.hidden=true;c.photo=null;if(valid())pollInbox(e);};
  send.onclick=async()=>{
    if(!c.photo||c.busy)return;
    controls(true);say(states.uploading);
    try{
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
    }finally{if(valid())controls(false);}
  };
  renew.onclick=async()=>{
    controls(true);
    try{const r=await post(`/api/math/answer-attempts/${c.result.attempt.id}/scans`,{renew:true});if(!valid())return;
      c.result=r;c.key=null;renew.hidden=true;confirm.hidden=false;say("נוצרה בקשה חדשה. האם לצלם תשובה לשאלה הזו?");}
    catch(error){say(error.message);}
    finally{if(valid())controls(false);}
  };
  if(result.scan.state==="expired")expired();
  node.querySelector("[data-close]").focus();
}
document.addEventListener("visibilitychange",()=>{
  if(document.hidden)return;
  if(account&&inbox)pollInbox(epoch);
  if(question?.result)pollQuestion(question);
});
window.addEventListener("online",()=>{if(account&&inbox)pollInbox(epoch);if(question?.result)pollQuestion(question);});
window.MathlyAnswers={configure,mountQuestion,closeQuestion,reset};
})();
