/* The user guide: how to use the app, for students and for teachers.
   A "?" button on the start screen (before and after sign-in) opens it as a dialog with a tab for each.
   It stands alone, with its own styles, so it also works on the sign-in screen before math.css is loaded.
   Other screens add the same button with MathlyGuide.button(). */
(()=>{
const STUDENT=[
  ["🚪","כניסה ובחירת מקצוע",`<p>נכנסים עם חשבון Google של בית הספר. כדאי להיכנס תמיד עם <b>אותו חשבון</b> בכל מכשיר: ההתקדמות נשמרת בחשבון ועוברת בין המחשב לטלפון.</p>
    <p>במסך <b>המקצועות שלי</b> בוחרים מקצוע כדי לפתוח את המסלול שלו. לכל מקצוע מופיעים גם המבחנים הקרובים של הכיתה.</p>`],
  ["⭐","המסלול",`<p>כל יחידה היא קבוצת כוכבים, וכל כוכב הוא מיומנות. כל השיעורים פתוחים, והינשוף מסמן איפה <b>ממשיכים</b>.</p>
    <ul><li>לוחצים על כוכב כדי לפתוח את המיומנות ולענות על השאלות שלה.</li>
    <li>הכוכב נדלק כשעונים נכון על כל השאלות, והופך ל<b>זהב</b> אחרי כמה תשובות נכונות ברצף בניסיון הראשון.</li>
    <li>כוכב שלא תרגלו שבועיים <b>דועך</b>. תשובה נכונה אחת מחזירה לו את האור.</li>
    <li>תשובה שגויה לא מגלה את התשובה הנכונה. השאלה תחזור אחרי האחרות, ואפשר לנסות שוב.</li></ul>`],
  ["🔥","היעד היומי והרצף",`<p>היעד היומי הוא 5 תשובות נכונות. מי שמגיע אליו כל יום בונה <b>רצף</b>. לוחצים על הלהבה כדי לראות את לוח הרצף של החודש.</p>`],
  ["🔁","חזרה מעורבת ודפוסים שחוזרים",`<p><b>חזרה מעורבת</b> מופיעה בבית כשמיומנויות שכבר סיימתם צריכות חזרה: כמה שאלות מנושאים שונים, כדי שמה שלמדתם יישאר.</p>
    <p><b>דפוסים שחוזרים</b> מראה טעות שחוזרת אצלכם בכמה נושאים, ואיזו מיומנות כדאי לחזק כדי שהיא תיעלם.</p>`],
  ["📝","מבחן תרגול",`<p>12 שאלות מעורבבות מכמה יחידות, כמו במבחן אמיתי: שם הנושא לא מופיע ואין משוב באמצע. בוחרים אילו יחידות ייכנסו, ובסוף מקבלים ציון ותוכנית: מה לחזק עד המבחן. השעון רק מראה את הזמן, בלי לחץ.</p>`],
  ["🧾","בוחן מסכם ליחידה",`<p>בסוף כל יחידה יש בוחן עם שאלות פתוחות ושעון שסופר לאחור.</p>
    <ul><li>כותבים את הפתרונות על דף, כל שאלה בנפרד, עם דרך פתרון מלאה.</li>
    <li>מצלמים את התשובה לכל שאלה: מהטלפון, מהמחשב (<b>צילום בטלפון</b> נותן קוד, ופותחים את האפליקציה בטלפון עם אותו חשבון), או פותרים ב<b>לוח</b> ומגישים ממנו.</li>
    <li>כשהזמן לכתיבה נגמר יש עוד 10 דקות לצלם ולהגיש.</li>
    <li>אחרי ההגשה התשובות נשלחות למורה. כשהמורה מאשר את הבדיקה מגיעים הציון והפתרונות (ראו <b>בדיקה דרך המורה</b>).</li></ul>`],
  ["🙋","בדיקה דרך המורה",`<p>תשובה פתוחה שצילמתם (או תרגיל שצילמתם לעזרה) לא נבדקת מיד: היא נשלחת ל<b>מורה הכיתה</b>, והמורה מעביר אותה לבדיקה אוטומטית.</p>
    <ul><li>בזמן ההמתנה כתוב <b>התשובה מחכה למורה</b>. אפשר להמשיך לתרגל, והתוצאה תופיע במקום כשהיא מוכנה.</li>
    <li>אם המורה לא אישר, מופיעה ההערה שלו. אפשר לתקן ולשלוח שוב (<b>שליחה מחדש למורה</b>).</li>
    <li>בקשה לעזרה בתרגיל מצולם אפשר לבטל ב<b>ביטול הבקשה</b>.</li>
    <li>אפשר לחכות לכל היותר ל־5 בקשות בבת אחת.</li>
    <li>הבדיקה האוטומטית יכולה לטעות: בדקו שהתמלול שמוצג תואם למה שכתבתם, ואם לא, הראו למורה.</li></ul>`],
  ["✏️","לוח טיוטה",`<p>הכפתור <b>לוח</b> בכל שאלה פותח דף לכתיבה: עט, קו ישר, עיגול, נוסחה מוקלדת ומחק. בטלפון הלוח נפתח במסך מלא, ו<b>חזרה לשאלה</b> מחזיר. גוללים עם שתי אצבעות או עם כלי ההזזה (כף היד). כפתור הלוח עם הדף (<b>השאלה</b>) מעתיק את השאלה לראש הדף.</p>`],
  ["🔔","התראות בטלפון",`<p>כשהמחשב מבקש צילום של תשובה, הטלפון יכול לקבל התראה גם כשהאפליקציה סגורה. מפעילים אותה בכפתור הפעמון. באייפון זה עובד רק מהאפליקציה שהוספה למסך הבית.</p>`],
  ["☄️","האוסף ושביטים",`<p>בלשונית <b>האוסף</b> רואים את כל הכוכבים וקבוצות הכוכבים שאספתם. לפעמים חולף על המסך שביט בזמן תרגול: מי שלוחץ עליו בזמן תופס אותו.</p>`],
  ["🚀","מדעים: חידות בהצבעה",`<p>המורה פותח הצבעה ומציג על הלוח <b>קוד בן 4 ספרות</b>. נכנסים לחידה, מקלידים את הקוד ב<b>הצטרפות להצבעה</b> ומצביעים. אפשר לשנות הצבעה עד שהמורה בודק.</p>`],
];
const TEACHER=[
  ["👩‍🏫","להיות מורה הכיתה",`<p>לכל כיתה יש מורה אחד. מנהל בוחר אותו ב<b>ניהול ← כיתות ← עריכה ← מורה הכיתה</b>, מתוך החשבונות של הכיתה. אחרי הבחירה מופיעים למורה הכפתורים <b>הכיתה שלי</b> ו<b>תור AI</b>.</p>`],
  ["🤖","תור AI",`<p>תלמידים לא שולחים ל-AI בעצמם. כל תשובה פתוחה, בוחן מסכם או תרגיל מצולם של תלמיד מחכה ב<b>תור AI</b> של מורה הכיתה. המספר על הכפתור הוא מספר הבקשות שממתינות.</p>
    <ul><li>בכל בקשה רואים את התלמיד, השאלה והתמונה ששלח.</li>
    <li><b>שליחה ל-AI</b> מעביר את הבקשה לבדיקה, והתלמיד רואה את הציון והמשוב בעמוד שלו.</li>
    <li><b>דחייה</b> סוגרת את הבקשה, ואפשר לצרף הערה לתלמיד (למשל "התמונה מטושטשת, צלמו שוב").</li>
    <li>כשממתינות כמה בקשות, <b>שליחת כל הממתינות</b> שולח את כולן יחד. שליחה שנכשלה אפשר לנסות שוב.</li>
    <li>בקשות שטופלו נשארות ברשימה יממה. <b>רענון</b> טוען בקשות חדשות.</li></ul>
    <p>מורים ומנהלים שולחים את התשובות שלהם ישר ל-AI, בלי תור. מנהל רואה את הבקשות של כל הכיתות.</p>`],
  ["📊","דוח הכיתה",`<p><b>הכיתה שלי</b> פותח דוח על כל תלמיד:</p>
    <ul><li>המיומנויות שסיים ביחידות של הכיתה.</li>
    <li>הטעויות שחוזרות אצלו.</li>
    <li>הציון ב<b>בוחן המסכם</b> של כל יחידה, ותוצאות <b>מבחני התרגול</b>.</li></ul>
    <p>בראש הדוח מופיעות הטעויות הנפוצות בכל הכיתה, כדי לדעת מה כדאי לחזור עליו בשיעור. הנתונים של תלמיד מופיעים אחרי שנכנס לחשבון ותרגל.</p>`],
  ["📷","משאבי שיעור",`<p>במסלול המתמטיקה, לוחצים על שם יחידה (או על <b>📷 משאבים</b> מתחתיה) כדי לפתוח את המשאבים של השיעור.</p>
    <ul><li><b>📷 צילום תמונה</b>: מצלמים תרגיל או הסבר מהלוח או מהספר.</li>
    <li>מסמנים את הסוג: <b>תרגיל חדש</b>, <b>הסבר תיאורטי</b> או <b>אחר</b>, ואפשר לכתוב לאיזה נושא הוא שייך.</li>
    <li>רק מי שהוסיף תמונה (או מנהל) יכול למחוק אותה.</li></ul>
    <p>בשלב זה המשאבים גלויים למורים בלבד.</p>`],
  ["🚀","הצבעה כיתתית במדעים",`<p>במקצוע <b>מדעים</b> בוחרים חידה ולוחצים <b>פתיחת הצבעה לכיתה</b>. על המסך מופיע קוד בן 4 ספרות: מציגים אותו על הלוח והתלמידים מצטרפים איתו מהמכשירים שלהם.</p>
    <ul><li>ההצבעות מוסתרות עד שלוחצים <b>בדיקה</b>. הטיל משוגר עם התשובה שרוב הכיתה בחרה.</li>
    <li>בתיקו הטיל לא משוגר: התלמידים יכולים לשנות הצבעה, ובודקים שוב.</li>
    <li><b>לחידה הבאה</b> ממשיך באותה הצבעה.</li></ul>`],
  ["🗓️","מבחנים ותרגול לקראתם",`<p>לוח המבחנים של הכיתה מופיע לתלמידים במסך המקצועות ובמסלול. כשמבחן מתקרב, <b>מבחן התרגול</b> מכוון אליו ומציע את היחידות שנלמדו עד אז. כדאי להזכיר לתלמידים לעשות אותו בשבוע שלפני המבחן.</p>`],
  ["⚙️","ניהול (למנהלים)",`<p>הכפתור <b>ניהול</b> מופיע למי שיש לו הרשאה. שם יוצרים כיתות, מוסיפים תלמידים לפי כתובת דוא״ל (שורה לכל תלמיד), בוחרים יחידות ומקצועות, מגדירים לוח מבחנים ובוחרים את מורה הכיתה. כל כיתה פותחת לתלמידים שלה רק את היחידות שנבחרו לה. בלשונית המעקב רואים פעילות ושימוש.</p>`],
];

const css=`
.mg-help{position:absolute;top:max(14px,env(safe-area-inset-top,0px));left:16px;width:44px;height:44px;border-radius:50%;
  border:1px solid #7EE3C8;background:transparent;color:#7EE3C8;font:700 20px/1 system-ui,sans-serif;cursor:pointer;display:grid;place-items:center}
.mg-help:hover,.mg-help:focus-visible{background:#163A36}
.mg-help.inline{position:static;width:36px;height:36px;font-size:17px}
.mg-scrim{position:fixed;inset:0;z-index:1100;background:rgb(3 5 14 / .78);display:flex;align-items:flex-end;justify-content:center}
.mg-scrim[hidden]{display:none}
.mg-box{direction:rtl;width:min(720px,100%);max-height:90vh;display:flex;flex-direction:column;background:#121B3B;color:#F2EFFF;
  border:1px solid #27335F;border-radius:20px 20px 0 0;font:400 16px/1.6 "Rubik",system-ui,-apple-system,"Segoe UI",sans-serif;
  padding-bottom:env(safe-area-inset-bottom,0px)}
@media (min-width:760px){.mg-scrim{align-items:center}.mg-box{border-radius:20px;max-height:86vh}}
.mg-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 20px 10px}
.mg-head h2{margin:0;font:400 24px/1.2 "Secular One","Rubik",system-ui,sans-serif}
.mg-x{border:1px solid #27335F;background:none;color:#9BA5CD;width:38px;height:38px;border-radius:50%;font-size:16px;cursor:pointer;flex:none}
.mg-tabs{display:flex;gap:8px;padding:0 20px 12px;border-bottom:1px solid #27335F}
.mg-tabs button{flex:1;border:1px solid #7EE3C8;background:transparent;color:#7EE3C8;font:700 15px/1 "Rubik",system-ui,sans-serif;padding:11px 12px;border-radius:999px;cursor:pointer}
.mg-tabs button[aria-selected="true"]{background:#7EE3C8;color:#05231B}
.mg-body{overflow:auto;padding:14px 20px 22px;overscroll-behavior:contain}
.mg-body[hidden]{display:none}
.mg-body details{border:1px solid #27335F;border-radius:14px;background:#18234A;margin-bottom:10px}
.mg-body summary{display:flex;align-items:center;gap:10px;padding:13px 14px;cursor:pointer;font-weight:700;list-style:none}
.mg-body summary::-webkit-details-marker{display:none}
.mg-body summary::after{content:"‹";margin-inline-start:auto;color:#9BA5CD;transition:transform .15s}
.mg-body details[open] summary::after{transform:rotate(-90deg)}
.mg-body summary i{font-style:normal;font-size:20px;width:26px;text-align:center}
.mg-body .mg-txt{padding:0 14px 12px 14px;color:#D9DDF2}
.mg-body p{margin:0 0 8px}.mg-body ul{margin:0 0 8px;padding-inline-start:20px}.mg-body li{margin-bottom:4px}
.mg-body b{color:#F2EFFF}
.mg-intro{color:#9BA5CD;margin:0 0 12px}
@media (max-width:420px){.mg-head,.mg-tabs,.mg-body{padding-inline:16px}}
`;

let scrim=null, back=null;
const section=([icon,title,body],i)=>`<details${i===0?" open":""}><summary><i aria-hidden="true">${icon}</i><span>${title}</span></summary><div class="mg-txt">${body}</div></details>`;
const style=document.createElement("style"); style.textContent=css; document.head.append(style);
function build(){
  scrim=document.createElement("div"); scrim.className="mg-scrim"; scrim.hidden=true;
  scrim.innerHTML=`<div class="mg-box" role="dialog" aria-modal="true" aria-labelledby="mgTitle">
    <div class="mg-head"><h2 id="mgTitle">איך משתמשים באפליקציה</h2><button class="mg-x" data-mg="close" aria-label="סגירת המדריך">✕</button></div>
    <div class="mg-tabs" role="tablist">
      <button role="tab" id="mgTabS" aria-controls="mgS" aria-selected="true" data-mg-tab="S">לתלמידים</button>
      <button role="tab" id="mgTabT" aria-controls="mgT" aria-selected="false" data-mg-tab="T" tabindex="-1">למורים</button></div>
    <div class="mg-body" id="mgS" role="tabpanel" aria-labelledby="mgTabS"><p class="mg-intro">מתרגלים במסלול, אוספים כוכבים ומתכוננים למבחנים. לחצו על נושא כדי לפתוח אותו.</p>${STUDENT.map(section).join("")}</div>
    <div class="mg-body" id="mgT" role="tabpanel" aria-labelledby="mgTabT" hidden><p class="mg-intro">רואים איך הכיתה מתקדמת, שומרים חומרים לשיעור ומפעילים את הכיתה. לחצו על נושא כדי לפתוח אותו.</p>${TEACHER.map(section).join("")}</div></div>`;
  document.body.append(scrim);
  scrim.addEventListener("click",e=>{
    if(e.target===scrim||e.target.closest("[data-mg=close]")) return close();
    const tab=e.target.closest("[data-mg-tab]"); if(tab) pick(tab.dataset.mgTab);
  });
  scrim.addEventListener("keydown",e=>{
    if(e.key==="Escape"){ e.stopPropagation(); return close(); }
    if(e.target.matches("[data-mg-tab]")&&["ArrowLeft","ArrowRight"].includes(e.key)){
      const to=e.target.dataset.mgTab==="S"?"T":"S"; pick(to); scrim.querySelector(`[data-mg-tab=${to}]`).focus();
    }
  });
}
function pick(which){
  scrim.querySelectorAll("[data-mg-tab]").forEach(b=>{ const on=b.dataset.mgTab===which; b.setAttribute("aria-selected",on); b.tabIndex=on?0:-1; });
  scrim.querySelector("#mgS").hidden=which!=="S"; scrim.querySelector("#mgT").hidden=which!=="T";
}
function open(which="S"){
  if(!scrim) build();
  back=document.activeElement; pick(which); scrim.hidden=false;
  scrim.querySelector(".mg-x").focus({preventScroll:true});
}
function close(){ if(!scrim||scrim.hidden) return; scrim.hidden=true; back?.focus?.({preventScroll:true}); }

const button=(cls="inline")=>`<button type="button" class="mg-help ${cls}" data-guide-open aria-label="מדריך שימוש" title="מדריך שימוש">?</button>`;
// one listener for every "?" button, wherever a screen draws it (capture: before a screen's own handlers)
document.addEventListener("click",e=>{ if(e.target.closest?.("[data-guide-open]")){ e.preventDefault(); open(); } },true);

// the sign-in screen's button
const boot=document.getElementById("boot");
if(boot){ boot.style.position="relative"; boot.insertAdjacentHTML("afterbegin",button("")); }

window.MathlyGuide={open,close,button};
})();
