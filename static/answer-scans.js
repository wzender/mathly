/* Same-account handwritten answers. Every async continuation checks its account
   and view before changing the UI. The server is authoritative for all states. */
(()=>{
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=s=>esc(s).replace(/\$([^$]+)\$/g,'<span class="m">$1</span>');
const states={waiting:"ממתינים לטלפון",confirmed:"ממתינים לטלפון",uploading:"מעלים את התשובה…",received:"התשובה התקבלה",failed:"ההעלאה נכשלה",expired:"בקשת הצילום פגה",superseded:"הבקשה הוחלפה",declined:"הבקשה נדחתה בטלפון"};
const errors={expired:"בקשת הצילום פגה. צרו בקשה חדשה ונסו שוב.",superseded:"הבקשה הוחלפה. בחרו את הבקשה העדכנית.",upload_in_progress:"העלאה כבר מתבצעת. ממתינים לעדכון…",confirmation_required:"יש לאשר את בקשת הצילום תחילה.",invalid_upload:"ההעלאה הופסקה. נסו שוב.",question_changed:"השאלה השתנתה. רעננו את העמוד ופתחו אותה מחדש.",invalid_image:"לא ניתן לקרוא את התמונה. צלמו שוב.",image_too_large:"התמונה גדולה מדי. צלמו שוב.",unsupported_image:"בחרו תמונת JPEG, PNG או WebP.",answer_storage_unavailable:"שמירת תשובות אינה זמינה כרגע. נסו שוב מאוחר יותר.",sign_in_required:"יש להיכנס לאותו חשבון בשני המכשירים.",review_limit:"יש כבר 5 בקשות פתוחות למורה. אפשר לבקש שוב אחרי שהמורה יענה.",message_too_long:"ההודעה ארוכה מדי (עד 300 תווים).",invalid_message:"ההודעה אינה תקינה.",answer_required:"צריך לצלם את התשובה קודם.",review_unavailable:"הבקשה למורה אינה זמינה כרגע. נסו שוב מאוחר יותר."};
Object.assign(errors,{grading_unavailable:"בדיקת תשובות אינה זמינה כרגע באתר.",grading_failed:"הבדיקה נכשלה. התמונה נשמרה; אפשר לנסות שוב.",grading_interrupted:"הבדיקה הופסקה. אפשר לנסות שוב.",grading_limit:"הגעתם למכסת 20 הבדיקות היומית. נסו שוב מחר.",grading_busy:"כבר מתבצעות בדיקות בחשבון. נסו שוב בעוד רגע.",answer_required:"יש לצלם ולשלוח תשובה לפני הבדיקה.",queue_unavailable:"שליחת תשובות לבדיקת המורה אינה זמינה כרגע.",request_taken:"המורה כבר טיפל בבקשה. רעננו את העמוד."});
/* Why an AI check failed (the server's `reason`, app/math_photo.py: failure_reason), for the people who can fix it:
   a teacher sending from the AI queue, or checking their own answer. Each is what happened and what to do. */
const reasons={
  missing_key:["חסר מפתח API בשרת","משתנה הסביבה ANTHROPIC_API_KEY לא מוגדר בשרת. הוסיפו אותו להגדרות השרת (Secrets או קובץ .env) והפעילו את השרת מחדש."],
  api_key_invalid:["מפתח ה-API לא תקין","Anthropic דחתה את המפתח (401). בדקו שהערך של ANTHROPIC_API_KEY הועתק במלואו, ושהמפתח לא בוטל ב-Anthropic Console."],
  permission:["אין הרשאה","למפתח ה-API אין הרשאה למודל או לפעולה הזו (403). בדקו את הרשאות המפתח וה-Workspace ב-Anthropic Console."],
  model_not_found:["המודל לא נמצא","המודל שמוגדר בשרת (MATH_MODEL) לא קיים או לא זמין למפתח הזה (404). בדקו את שם המודל, או מחקו את MATH_MODEL כדי לחזור לברירת המחדל."],
  no_credit:["נגמר הקרדיט","אין מספיק קרדיט בחשבון Anthropic. הוסיפו קרדיט ב-Anthropic Console, בעמוד Billing."],
  rate_limited:["יותר מדי בקשות","הגעתם למגבלת הקצב של ה-API (429). חכו דקה ונסו שוב."],
  overloaded:["שירות ה-AI עמוס","השרתים של Anthropic עמוסים כרגע. נסו שוב בעוד כמה דקות."],
  no_connection:["אין חיבור ל-AI","השרת לא הצליח להתחבר ל-API של Anthropic (רשת או זמן המתנה ארוך מדי). בדקו את החיבור של השרת ונסו שוב."],
  bad_request:["ה-API דחה את הבקשה","Anthropic החזירה שגיאה 400. הפרטים הטכניים למטה מסבירים למה."],
  refused:["ה-AI סירב לבדוק","המודל סירב לענות על הבקשה הזו. אפשר לנסות שוב או לבקש מהתלמיד לצלם מחדש."],
  incomplete:["הבדיקה נקטעה","ה-AI הפסיק לפני שסיים את הבדיקה. נסו שוב."],
  bad_output:["תשובה לא תקינה מה-AI","ה-AI החזיר תשובה שלא עברה את בדיקות השרת, ולכן לא ניתן ציון. נסו שוב."],
  provider_error:["שגיאה בשירות ה-AI","Anthropic החזירה שגיאה לא צפויה. נסו שוב, ואם זה חוזר, ראו את הפרטים הטכניים."],
  server_error:["שגיאה בשרת שלנו","משהו נכשל בשרת של Mathly. הפרטים הטכניים למטה, וגם ביומן השגיאות בלשונית ניטור."],
  answer_storage_unavailable:["האחסון לא זמין","לא הצלחנו לקרוא את התמונה השמורה. בדקו את Supabase או את MATHLY_ANSWER_BUCKET ו-HF_TOKEN."],
  open_ended_locked:["שאלות פתוחות נעולות","בשרת מוגדר MATHLY_OPEN_ENDED_LOCKED=1. שנו ל-0 והפעילו מחדש כדי לאפשר בדיקה."]};
// a "פירוט השגיאה" button that opens what happened, what to do, and the technical line; "" without a reason
function errorDetails(reason,detail){
  if(!reason&&!detail)return "";
  const [title,say]=reasons[reason]||["שגיאה לא מוכרת","לא זיהינו את סוג השגיאה. הפרטים הטכניים למטה."];
  return `<details class="mx-error-details"><summary>פירוט השגיאה</summary><p><b>${esc(title)}</b></p><p>${esc(say)}</p>${detail?`<code dir="ltr">${esc(detail)}</code>`:""}</details>`;
}
const verdicts={correct:"נכון! הפתרון מלא",partial:"פתרון נכון בחלקו",incorrect:"יש לתקן את הפתרון",unreadable:"לא ניתן לקרוא את התשובה",needs_review:"נדרשת הבהרה לפני מתן ציון"};
let queued=false;   // a student: an answer is checked only after their teacher sends it to the AI (app/ai_queue.py)
let api=null,account=null,epoch=0,question=null,inbox=false,inboxTimer=null,inboxPoll=null,capture=null,visibleRoot=null,onGraded=null;
const handled=new Set();   // requests this phone already answered (photographed or declined): not shown again
const live=(e)=>e===epoch&&!!account;
async function json(url,options={}){
  const r=await api(url,{cache:"no-store",...options});
  const d=await r.json().catch(()=>({}));
  if(!r.ok){if(r.status===401)reset();const error=Error(errors[d.detail]||"החיבור נקטע. נסו שוב.");error.status=r.status;error.code=d.detail;error.reason=d.reason||"";error.detail=d.error_detail||"";throw error;}
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
  inbox=false;account=null;onGraded=null;PUSH_MODE="hidden";paintPush();document.querySelector(".mx-push-ask")?.remove();
}
function configure(options){
  reset();api=options.api;account=options.enabled?options.account:null;visibleRoot=options.root;onGraded=options.onGraded;queued=!!options.queued;
  if(!account)return;
  // The phone (the responsive app/PWA) watches for requests from the computer and pops them up.
  if(matchMedia("(max-width: 700px)").matches||navigator.maxTouchPoints){inbox=true;pollInbox(epoch);pushSync(epoch);}
}
/* ---------- the phone: a notification when the computer asks for a photo (app/push.py) ----------
   Only the phone subscribes, so the computer that made the request is not notified. The notification just brings the
   student here; the look for requests above shows the request itself. On an iPhone only the app added to the home
   screen may get notifications. A tap while the app is open comes as a message from the service worker. */
const PUSH_IOS=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
const PUSH_STANDALONE=matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;
const PUSH_CAN="serviceWorker" in navigator&&"PushManager" in window&&"Notification" in window;
const PUSH_OFF="mathly.pushOff";   // turned off here: not turned on again by itself
const pushOptOut=v=>{try{if(v===undefined)return localStorage.getItem(PUSH_OFF)==="1";v?localStorage.setItem(PUSH_OFF,"1"):localStorage.removeItem(PUSH_OFF);}catch{return false;}};
let pushKey=null,pushReg=null;
function pushWorker(){
  if(!("serviceWorker" in navigator))return Promise.resolve(null);
  return pushReg||=navigator.serviceWorker.register("/service-worker.js").then(()=>navigator.serviceWorker.ready).catch(()=>null);
}
async function pushState(){   // {key, sub}: key is empty when the server sends no notifications
  if(!PUSH_CAN||!account)return {key:"",sub:null};
  if(pushKey===null)pushKey=await json("/api/push").then(d=>d.key||"").catch(()=>"");
  const reg=await pushWorker();
  const sub=reg?await reg.pushManager.getSubscription().catch(()=>null):null;
  return {key:pushKey,sub};
}
const subscribeBody=sub=>({method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(sub.toJSON())});
async function pushOn(key){   // asks the permission (call it from a tap) and subscribes; the subscription, or null
  if(await Notification.requestPermission()!=="granted")return null;
  const reg=await pushWorker();if(!reg)throw Error("no worker");
  const raw=atob(key.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-key.length%4)%4));
  const sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:Uint8Array.from(raw,c=>c.charCodeAt(0))});
  const r=await api("/api/push/subscribe",subscribeBody(sub)).catch(()=>null);
  if(!r?.ok){await sub.unsubscribe().catch(()=>{});const e=Error("not kept");e.server=r?r.status:0;throw e;}
  pushOptOut(false);return sub;
}
async function pushOff(sub){
  await api("/api/push/unsubscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({endpoint:sub.endpoint})}).catch(()=>{});
  await sub.unsubscribe().catch(()=>{});
}
/* A phone's subscription belongs to the account signed in on it: on sign-in it moves to that account (or, notifications
   being allowed already, is made again after a sign-out), unless it was turned off here. */
async function pushSync(e){
  if(!PUSH_CAN){pushMode(PUSH_IOS&&!PUSH_STANDALONE?"ios":"hidden");return;}
  try{
    const st=await pushState();if(!live(e))return;
    if(!st.key){pushMode("hidden");return;}
    let sub=st.sub;
    if(sub)await api("/api/push/subscribe",subscribeBody(sub));
    else if(Notification.permission==="granted"&&!pushOptOut())sub=await pushOn(st.key);
    if(!live(e))return;
    pushMode(sub?"on":Notification.permission==="denied"?"blocked":"off");
    if(!sub&&Notification.permission==="default"&&!pushOptOut()&&!pushAsked())askPush(e);
  }catch{if(live(e))pushMode(Notification.permission==="denied"?"blocked":"off");}
}
/* The 🔔 in the top bar (phones only): its state is kept here and painted into every .mx-push-btn, so the page can
   draw it in its templates (pushButton) and it changes in place when the state does. */
let PUSH_MODE="hidden";   // hidden | on | off | blocked | ios
const PUSH_LOOK={on:["🔔","התראות פעילות. לחצו לכיבוי"],off:["🔕","התראות כבויות. לחצו להפעלה"],
  blocked:["🔕","ההתראות חסומות בדפדפן"],ios:["🔕","התראות באייפון: מהאפליקציה שעל מסך הבית"]};
function pushMode(m){PUSH_MODE=account&&inbox?m:"hidden";paintPush();}
function pushButton(){   // drawn as it is now; paintPush changes it in place later
  const look=PUSH_LOOK[PUSH_MODE];
  return look?`<button class="mx-btn mx-push-btn" data-act="push" type="button" title="${look[1]}" aria-label="${look[1]}" aria-pressed="${PUSH_MODE==="on"}">${look[0]}</button>`
    :'<button class="mx-btn mx-push-btn" data-act="push" type="button" hidden></button>';
}
function paintPush(){
  for(const b of document.querySelectorAll(".mx-push-btn")){
    const look=PUSH_LOOK[PUSH_MODE];b.hidden=!look;if(!look)continue;
    b.textContent=look[0];b.title=look[1];b.setAttribute("aria-label",look[1]);b.setAttribute("aria-pressed",String(PUSH_MODE==="on"));
  }
}
const pushAsked=()=>{try{return localStorage.getItem("mathly.pushAsked")==="1";}catch{return true;}};
function pushNote(title,html,buttons){   // a small window on the phone: the question, or how to unblock
  document.querySelector(".mx-push-ask")?.remove();
  const node=document.createElement("div");node.className="mx-scan-overlay mx-push-ask";node.setAttribute("role","dialog");node.setAttribute("aria-modal","true");node.setAttribute("aria-labelledby","pushTitle");
  node.innerHTML=`<div class="mx-scan-card"><h2 id="pushTitle">${title}</h2><p>${html}</p><p data-status role="status" aria-live="polite"></p><div class="mx-scan-actions"></div></div>`;
  const row=node.querySelector(".mx-scan-actions"),close=()=>node.remove();
  for(const [label,solid,act] of buttons){
    const b=document.createElement("button");b.type="button";b.className="mx-btn"+(solid?" solid":" mx-btn-quiet");b.textContent=label;
    b.onclick=async()=>{for(const x of row.children)x.disabled=true;try{if(await act?.(node)!==false)close();}finally{for(const x of row.children)x.disabled=false;}};row.append(b);
  }
  node.addEventListener("keydown",ev=>{if(ev.key==="Escape")close();});
  (visibleRoot||document.body).append(node);row.firstChild?.focus();
}
async function enablePush(node){   // "אישור": the browser's own question follows; false keeps the window open with why
  const say=t=>{const s=node?.querySelector("[data-status]");if(s)s.textContent=t;};
  try{
    const st=await pushState();const sub=st.key?await pushOn(st.key):null;
    pushMode(sub?"on":Notification.permission==="denied"?"blocked":"off");
    if(!sub){say(Notification.permission==="denied"?"ההתראות נחסמו. אפשר לאשר אותן בהגדרות האתר בדפדפן.":"ההתראות לא אושרו.");return false;}
  }catch(error){
    // the server could not keep the subscription (503: not set up there yet), or the phone's push service refused
    say(error.server===503?"ההתראות עוד לא מוכנות בשרת. נסו שוב מאוחר יותר."
      :error.server===0?"אין חיבור לשרת. בדקו את האינטרנט ונסו שוב."
      :error.server?"השרת לא שמר את ההרשמה. נסו שוב מאוחר יותר."
      :"הטלפון לא הצליח להירשם להתראות. בדקו שהתראות הדפדפן מותרות בהגדרות הטלפון ונסו שוב.");
    return false;
  }
}
function askPush(e){   // once per phone, after sign-in; "לא, תודה" is final (the 🔔 still turns them on)
  if(capture||document.querySelector(".mx-push-ask"))return;
  const done=()=>{try{localStorage.setItem("mathly.pushAsked","1");}catch{}};
  pushNote("🔔 התראות מהמחשב","כשהמחשב מבקש לצלם תשובה, הטלפון יקבל התראה, גם כשהאפליקציה סגורה.",[
    ["אישור",true,async node=>{done();if(!live(e))return;return enablePush(node);}],
    ["לא, תודה",false,()=>{done();pushOptOut(true);pushMode("off");}]]);
}
async function togglePush(){   // the 🔔
  if(PUSH_MODE==="ios")return pushNote("📱 התראות באייפון","באייפון ההתראות מגיעות רק מהאפליקציה שעל מסך הבית: לחצו על <b>שיתוף</b> ⬆️ ← <b>„הוספה למסך הבית”</b>, ופתחו את האפליקציה משם.",[["הבנתי",true]]);
  if(PUSH_MODE==="blocked")return pushNote("🔕 ההתראות חסומות","הדפדפן חוסם התראות מהאתר. כדי לאשר: בכרום לחצו על הסמל שליד הכתובת ← <b>הרשאות</b> ← <b>התראות</b> ← <b>אישור</b>. באייפון: <b>הגדרות</b> ← <b>עדכונים</b> ← <b>לומדים בכיף</b>.",[["הבנתי",true]]);
  if(PUSH_MODE==="on")return pushNote("🔔 לכבות התראות?","הטלפון לא יקבל התראה כשהמחשב מבקש צילום. אפשר להפעיל שוב מכאן.",[
    ["כיבוי",true,async()=>{const st=await pushState().catch(()=>({}));if(st.sub)await pushOff(st.sub);pushOptOut(true);pushMode("off");}],["ביטול",false]]);
  if(PUSH_MODE==="off")return pushNote("🔔 להפעיל התראות?","כשהמחשב מבקש לצלם תשובה, הטלפון יקבל התראה, גם כשהאפליקציה סגורה.",[["אישור",true,enablePush],["ביטול",false]]);
}
async function forgetPush(){   // signing out: the next account on this phone does not get this one's requests
  try{const st=await pushState();if(st.sub)await pushOff(st.sub);}catch{}
}
async function clearScanNotices(){   // the app is open and shows requests itself: the tray's ones are old news
  try{const reg=await navigator.serviceWorker?.getRegistration();for(const n of await reg?.getNotifications()||[])if(String(n.tag).startsWith("scan-"))n.close();}catch{}
}
/* The offer, at the end of a request on the phone: "next time, tell me". Nothing is shown when notifications cannot
   work here or are blocked; an iPhone's browser gets the home-screen hint instead. */
function pushOffer(node,e){
  const box=document.createElement("div");box.className="mx-push-offer";box.hidden=true;node.append(box);
  const draw=(text,button,act)=>{
    box.replaceChildren();const p=document.createElement("small");p.textContent=text;box.append(p);
    if(button){const b=document.createElement("button");b.className="mx-btn";b.type="button";b.textContent=button;b.onclick=async()=>{
      b.disabled=true;try{await act();}catch{p.textContent="לא הצלחנו להפעיל התראות. נסו שוב מאוחר יותר.";}finally{b.disabled=false;}};box.append(b);}
    box.hidden=false;
  };
  if(!PUSH_CAN){
    if(PUSH_IOS&&!PUSH_STANDALONE)draw("📱 רוצים שהטלפון יצלצל כשהמחשב מבקש צילום? באייפון זה עובד רק מהאפליקציה שעל מסך הבית: שיתוף ← „הוספה למסך הבית”.");
    return;
  }
  pushState().then(st=>{
    if(!live(e)||!st.key||Notification.permission==="denied")return;
    const show=sub=>sub
      ?draw("🔔 התראה תגיע לטלפון כשהמחשב מבקש צילום.","כיבוי ההתראות",async()=>{await pushOff(sub);pushOptOut(true);pushMode("off");show(null);})
      :draw("רוצים שהטלפון יודיע לכם בפעם הבאה שהמחשב מבקש צילום, גם כשהאפליקציה סגורה?","🔔 כן, להודיע לי",async()=>{const s=await pushOn(st.key);if(live(e)){pushMode(s?"on":Notification.permission==="denied"?"blocked":"off");show(s);}});
    show(st.sub);
  });
}
if("serviceWorker" in navigator){
  navigator.serviceWorker.addEventListener("message",ev=>{
    if(ev.data?.type!=="notified"||!account||!inbox)return;
    clearScanNotices();pollInbox(epoch);
  });
}
if(new URLSearchParams(location.search).get("from")==="push-scan")history.replaceState(null,"",location.pathname);
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
    if(ask&&!capture){openCapture(ask);clearScanNotices();}
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
  const checking=q.grading||g?.state==="grading", req=r.ai_request;
  const waiting=!checking&&g?.state!=="completed"&&waitingTeacher(req);
  // while the phone has the request, its code and progress are in the phone box itself (phoneLive)
  const statusText=checking?(q.grading&&queued?"שולחים למורה…":"בודקים את התשובה…"):waiting?"התשובה מחכה למורה":g?.state==="completed"?verdicts[g.result.verdict]:g?.state==="failed"?errors[g.error]||errors.grading_failed:!received&&phonePending(state)?"":states[state]||"כתבו את הפתרון על דף וצלמו אותו בטלפון.";
  // Rebuilding controls on every poll would steal focus and race a button click.
  const signature=[state,s?.id,r.attachment?.id,g?.id,g?.state,r.grading_available,req?.id,req?.state,r.teacher_review?.created_at,r.review_request?.id,r.review_request?.state].join(":");
  if(q.signature!==signature){
    q.signature=signature;
    q.node.innerHTML=`<small>ניסיון ${esc(r.attempt.id.slice(0,8))}</small><p role="status" aria-live="polite">${esc(statusText)}</p>
      ${received?`<img class="mx-answer-image" alt="התשובה המצולמת שלכם" hidden>${teacherNote(r)}${gradingPanel(r,checking)}${reviewBox(r.attempt.id,r)}
        <button class="mx-btn" data-new-attempt ${checking?"disabled":""}>ניסיון חדש וצילום מחדש</button>`:phoneLive(s,`data-request`,`data-cancel-scan`,!s?"צילום התשובה בטלפון":"בקשת צילום חדשה לטלפון")}`;
    if(!received){
      const say=t=>{const el=q.node.querySelector("[role=status]");if(el)el.textContent=t;};
      const b=q.node.querySelector("[data-request]");
      if(b)b.onclick=async()=>{
        b.disabled=true;
        try{
          const result=await post(`/api/math/answer-attempts/${r.attempt.id}/scans`,
            {question_id:q.id,renew:["expired","superseded","failed","declined"].includes(q.result.scan?.state)});
          if(!current(q))return;q.result=result;await renderQuestion(q);schedule(q,1500);
        }
        catch(error){if(current(q)){say(error.message);b.disabled=false;}}
      };
      const cancel=q.node.querySelector("[data-cancel-scan]");
      if(cancel)cancel.onclick=async()=>{
        cancel.disabled=true;
        try{const result=await post(`/api/math/answer-scans/${q.result.scan.id}/decline`,{});if(!current(q))return;q.result=result;await renderQuestion(q);}
        catch(error){if(current(q)){say(error.message);cancel.disabled=false;}}
      };
    }
    if(received){
      const gradeButton=q.node.querySelector("[data-grade]");
      if(gradeButton)gradeButton.onclick=()=>checkAnswer(q);
      q.node.querySelector("[data-new-attempt]").onclick=()=>mountQuestion(q.node,q.id,q.version,true);
      const ask=q.node.querySelector("[data-ask-review]");
      if(ask)ask.onclick=async()=>{const sent=await askReview(ask);if(sent&&current(q)){q.result={...q.result,review_request:sent};q.signature=[q.signature,"asked"].join(":");}};
    }
  }else q.node.querySelector("[role=status]").textContent=statusText;
  if(g?.state==="completed"&&q.notified!==g.id){q.notified=g.id;onGraded?.({questionId:q.id,grading:g});}
  const t=r.teacher_review;   // the teacher's 100 counts like a correct check
  if(t?.score===100&&q.notifiedTeacher!==t.created_at){q.notifiedTeacher=t.created_at;onGraded?.({questionId:q.id,grading:{id:"teacher:"+t.created_at,finished_at:t.created_at,result:{verdict:"correct",score:100}}});}
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
/* The teacher's review of the answer (its own score and comment), shown above the automatic check, and the student's
   request to look again. Used by the answer panel here and by the unit quiz's result in math.js. */
function teacherNote(r){
  const t=r.teacher_review; if(!t)return "";
  return `<section class="mx-teacher-note" aria-label="הערת המורה"><h4>הערת המורה${t.score==null?"":` · <span class="m">${esc(t.score)}/100</span>`}</h4>${t.comment?`<p>${esc(t.comment).replace(/\n/g,"<br>")}</p>`:""}</section>`;
}
function reviewBox(attemptId,r){
  if(r.review_request?.state==="open")return '<p class="mx-small mx-ask-wait">ביקשתם מהמורה לבדוק שוב. הבקשה ממתינה.</p>';
  if(r.grading?.state!=="completed")return "";   // only a checked answer can be questioned
  return `<details class="mx-ask"><summary>לבקש מהמורה לבדוק שוב</summary>
    <textarea maxlength="300" rows="2" data-ask-msg aria-label="הודעה למורה (לא חובה)" placeholder="מה לא נראה לכם בבדיקה? (לא חובה)"></textarea>
    <button type="button" class="mx-btn" data-ask-review="${esc(attemptId)}">שליחה למורה</button></details>`;
}
// sends the request in the box the button is in; the box then says it waits
async function askReview(button){
  const box=button.closest(".mx-ask"),message=box.querySelector("[data-ask-msg]").value;
  button.disabled=true;box.querySelector(".mx-ask-error")?.remove();
  try{
    const sent=await post(`/api/math/answer-attempts/${button.dataset.askReview}/review-request`,{message});
    box.outerHTML='<p class="mx-small mx-ask-wait" role="status">ביקשתם מהמורה לבדוק שוב. הבקשה ממתינה.</p>';
    return sent.review_request;
  }catch(error){
    button.disabled=false;box.insertAdjacentHTML("beforeend",`<p class="mx-small mx-ask-error" role="alert">${esc(error.message)}</p>`);
    return null;
  }
}
function gradingPanel(r,checking){
  const g=r.grading;
  if(g?.state==="completed"){
    const a=g.result;
    return `<section class="mx-grade ${a.verdict==="correct"?"mx-grade-correct":""}" aria-label="תוצאות בדיקת התשובה">
      <h4>${r.teacher_review?"בדיקה אוטומטית: ":""}${esc(verdicts[a.verdict])}${a.score==null?"":` · <span class="m">${esc(a.score)}/100</span>`}</h4>
      <p>${fmt(a.feedback)}</p>${a.next_step?`<p><b>הצעד הבא: </b>${fmt(a.next_step)}</p>`:""}
      ${a.transcription?`<details><summary>מה קראנו בתמונה</summary><p>${fmt(a.transcription)}</p></details>`:""}
      ${a.solution?`<details><summary>הפתרון המלא</summary><p class="mx-grade-solution">${fmt(a.solution)}</p></details>`:""}
      <small>בדיקה אוטומטית באמצעות AI. בדקו שהתמלול תואם למה שכתבתם.</small></section>`;
  }
  if(!r.grading_available&&!checking)return '<p>התמונה נשמרה כתשובה. בדיקה אוטומטית אינה זמינה כרגע באתר.</p>';
  if(queued&&!checking){
    const req=r.ai_request;
    if(waitingTeacher(req))return '<p>התשובה נשלחה למורה. אחרי שהמורה יאשר את הבדיקה, התוצאה תופיע כאן.</p>';
    if(req?.state==="declined")return `<p>המורה לא אישר את הבדיקה.${req.note?` <b>הערת המורה:</b> ${esc(req.note)}`:""}</p>
      <button class="mx-btn" data-grade>שליחה מחדש למורה</button>`;
    return `<p>${g?.state==="failed"||req?.state==="failed"?"הבדיקה נכשלה. אפשר לשלוח שוב למורה.":"שלחו את התשובה למורה, והמורה יעביר אותה לבדיקה."}</p>
      <button class="mx-btn solid" data-grade>שליחה לבדיקת המורה</button>`;
  }
  return `<p>התשובה נשלחת לבדיקה אוטומטית באמצעות AI.</p>
    <button class="mx-btn solid" data-grade ${checking?"disabled":""}>${checking?"בודקים את התשובה…":g?.state==="failed"?"ניסיון בדיקה נוסף":"בדיקת התשובה"}</button>`;
}
// the answer's request is in the teacher's queue (a failed send stays there for the teacher to try again)
const waitingTeacher=req=>!!req&&["pending","sending","failed"].includes(req.state);
async function checkAnswer(q,automatic=false){
  if(!current(q)||q.grading)return;
  q.grading=true;q.signature=null;await renderQuestion(q);schedule(q);
  try{
    const r=await post(`/api/math/answer-attempts/${q.result.attempt.id}/grade`,{automatic});
    if(!current(q))return;q.result=r;
  }catch(error){if(current(q))q.gradeError=error;}
  finally{
    if(current(q)){
      q.grading=false;q.signature=null;await renderQuestion(q);
      if(q.gradeError){
        const status=q.node.querySelector("[role=status]");status.textContent=q.gradeError.message;
        status.insertAdjacentHTML("afterend",errorDetails(q.gradeError.reason,q.gradeError.detail));q.gradeError=null;
      }
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
  closeCapture();document.querySelector(".mx-push-ask")?.remove();const e=epoch;   // the request comes first
  if(!live(e))return;
  const node=document.createElement("div");node.className="mx-scan-overlay";node.setAttribute("role","alertdialog");node.setAttribute("aria-modal","true");node.setAttribute("aria-labelledby","scanTitle");
  node.innerHTML=`<div class="mx-scan-card mx-scan-ask">
    <h2 id="scanTitle"><span aria-hidden="true">📷</span> בקשת צילום מהמחשב</h2>
    <p>בדקו שזה אותו מספר שמופיע במחשב:</p>${codeHTML(result.scan.code)}
    <div class="mx-scan-q"><small>השאלה</small><p>${fmt(result.attempt.snapshot.question)}</p></div>
    <img class="mx-answer-image" data-preview alt="תצוגה מקדימה של התשובה" hidden>
    <p data-status role="status" aria-live="polite">${window.MathlyBoard?"כתבו את הפתרון על דף וצלמו אותו, או כתבו אותו כאן בלוח.":"כתבו את הפתרון על דף וצלמו אותו."}</p>
    <input data-camera type="file" accept="image/*" capture="environment" hidden>
    <div class="mx-scan-actions">
      <button class="mx-btn solid" data-take>📷 צילום התשובה</button>
      ${window.MathlyBoard?'<button class="mx-btn solid" data-draw>✏️ כתיבה בלוח</button>':""}
      <button class="mx-btn solid" data-submit hidden>שליחה למחשב</button>
      <button class="mx-btn" data-renew hidden>בקשה חדשה</button>
      <button class="mx-btn mx-btn-quiet" data-decline>סירוב</button>
      <button class="mx-btn" data-close hidden>סגירה</button>
    </div>
    <small>כשהבדיקה האוטומטית זמינה, צילום התשובה יישלח לבדיקה באמצעות AI. המשוב יופיע בשאלה במחשב.</small></div>`;
  const c=capture={node,e,result,photo:null,url:null,key:null,busy:false,ended:false,confirming:null,returnFocus:document.activeElement};visibleRoot.append(node);
  const $=sel=>node.querySelector(sel);
  const status=$("[data-status]"),camera=$("[data-camera]"),take=$("[data-take]"),draw=$("[data-draw]"),send=$("[data-submit]"),preview=$("[data-preview]"),renew=$("[data-renew]"),decline=$("[data-decline]"),close=$("[data-close]");
  const valid=()=>capture===c&&live(e),say=message=>{if(valid())status.textContent=message;};
  const controls=busy=>{c.busy=busy;take.disabled=send.disabled=renew.disabled=decline.disabled=busy;if(draw)draw.disabled=busy;};
  // the request is over: only closing is left
  const finish=(message,offer=false)=>{c.ended=true;handled.add(c.result.scan.id);take.hidden=send.hidden=renew.hidden=decline.hidden=true;if(draw)draw.hidden=true;close.hidden=false;say(message);if(offer)pushOffer($(".mx-scan-actions"),e);close.focus();};
  const expired=()=>{take.hidden=send.hidden=true;if(draw)draw.hidden=true;renew.hidden=false;say(errors.expired);};
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
  const confirmNow=()=>confirmed().then(r=>{if(r.attachment&&valid())success();}).catch(error=>{if(valid()){say(error.message);if(error.status===410)expired();}});
  take.onclick=()=>{
    say("צלמו את הפתרון. אם המצלמה חסומה, אפשרו אותה בהגדרות האתר ונסו שוב.");camera.click();
    confirmNow();
  };
  // the board instead of paper: full screen; its hand-in becomes this answer's picture and is sent like a photo
  if(draw)draw.onclick=()=>{
    confirmNow();
    window.MathlyBoard.openFull({host:visibleRoot,key:`scan:${c.result.attempt.id}`,title:"התשובה למחשב",sendLabel:"שליחה למחשב",
      question:()=>node.querySelector(".mx-scan-q"),done:()=>{if(valid())(c.ended?close:draw).focus();},
      submit:async(_,picture)=>{
        if(!valid()||c.ended)return {error:"הבקשה כבר לא פעילה"};
        try{setPhoto(await window.MathlyPhoto.prepare(picture));}catch{return {error:"לא ניתן להכין את התמונה"};}
        await upload();
        return c.ended?{close:true}:{error:status.textContent};
      }});
  };
  camera.addEventListener("cancel",()=>say("הצילום בוטל או שלא ניתנה הרשאה. אפשר לצלם שוב או לסרב."));
  camera.onchange=async()=>{
    const file=camera.files[0];camera.value="";if(!file||!valid())return;
    controls(true);say("מכינים את התמונה…");
    try{
      const photo=await window.MathlyPhoto.prepare(file);if(!valid())return;
      setPhoto(photo);say("בדקו שכל הפתרון ברור, ואז שלחו למחשב.");send.focus();
    }catch(error){say("לא ניתן להכין את התמונה. נסו לצלם שוב.");}
    finally{if(valid())controls(false);}
  };
  // a picture to send: the camera's, or the board's
  function setPhoto(photo){
    if(photo.size>5000000)throw Error(errors.image_too_large);
    if(c.url)URL.revokeObjectURL(c.url);
    c.photo=photo;c.key=null;preview.src=c.url=URL.createObjectURL(photo);preview.hidden=false;
    take.textContent="צילום מחדש";take.classList.remove("solid");send.hidden=false;
  }
  const success=()=>{c.photo=null;finish("✓ התשובה נשלחה למחשב.",true);};
  const upload=async()=>{
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
  send.onclick=upload;
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

/* ---------- the computer: the phone box ---------- */
/* No window over the question: the photo button itself becomes the request's box while the phone has it, with the
   4-digit code, how far the phone got, and a way to withdraw the request. The page's own look at the attempt (every
   couple of seconds) keeps it up to date; when the photo arrives the answer replaces it. `scan`: the attempt's last
   scan; `ask`/`cancel`: the attributes of its two buttons; `idle`: the button's words when there is no open request. */
const phonePending=st=>["waiting","confirmed","uploading","failed"].includes(st);
const PHONE_STEPS={waiting:"ממתינים לטלפון… פתחו את האפליקציה באותו חשבון",confirmed:"הטלפון אישר. ממתינים לצילום…",
  uploading:"מקבלים את התמונה מהטלפון…",failed:"ההעלאה נכשלה. נסו שוב בטלפון"};
function phoneLive(scan,ask,cancel,idle,disabled=false){
  const st=scan?.state;
  if(!phonePending(st))return `<button class="mx-btn solid mx-phone-cta" ${ask}${disabled?" disabled":""}><span aria-hidden="true">📱</span> ${esc(idle)}</button>`;
  return `<div class="mx-phone-live is-${esc(st)}" role="group" aria-label="צילום בטלפון">
    <div class="mx-phone-live-head"><span class="mx-scan-dot" aria-hidden="true"></span><span aria-live="polite">${esc(PHONE_STEPS[st])}</span></div>
    <div class="mx-phone-live-code"><small>המספר בטלפון:</small>${codeHTML(scan.code)}</div>
    ${st==="uploading"?"":`<button class="mx-link" ${cancel}>ביטול הבקשה</button>`}</div>`;
}
document.addEventListener("visibilitychange",()=>{
  if(document.hidden)return;
  if(account&&inbox){clearScanNotices();pollInbox(epoch);}
  if(question?.result)pollQuestion(question);
});
window.addEventListener("online",()=>{if(account&&inbox)pollInbox(epoch);if(question?.result)pollQuestion(question);});
window.MathlyAnswers={errorDetails,teacherNote,reviewBox,askReview,configure,mountQuestion,closeQuestion,reset,phoneLive,forgetPush,pushButton,paintPush,togglePush};
})();
