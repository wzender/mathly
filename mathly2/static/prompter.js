/* Prompter (פרומפטר): a full-screen teleprompter for developers, opened from the developer screen (ported as is from mathly1).
   It stands alone, with its own styles. window.MathlyPrompter.open(text) shows it.

   Two ways to show a text:
   · Scrolling (any text): the text rolls up at a set speed.
     Keys: Space play/pause · ↑/↓ speed · +/- text size · M mirror · Home back to start · Esc close.
     A presentation clicker: Page Down / → play/pause, Page Up / ← back a few lines.
     A mouse: click play/pause · wheel changes the speed while playing (scrolls the text while paused) ·
     right-click back a few lines · middle-click or the mouse's back button to the start · forward button play/pause.
   · Slides (a text with "Slide 3 — Title" lines, the speaker notes of a slide presentation): one slide's notes at a
     time, which waits for the speaker. A "40 seconds" / "Opening · 35 seconds" line right under a slide heading is
     its time budget; "Part 1 — …" lines name the part. The top strip shows the slide, its title and a clock against
     the budget (amber near the end, red over) and how far ahead or behind the whole talk is; the bottom shows the
     next slide's title. The first tap starts the clock; then a tap or a swipe to the left is the next slide, a swipe
     to the right the one before. Keys and clickers: Space / Page Down / → / ↓ next · Page Up / ← / ↑ back ·
     Home first slide (and resets the clock) · S switches between slides and scrolling.
     In the notes, [CLICK] marks a slide click, [PAUSE] or // a pause, and *word* a stressed word; "• " lines are
     reminders (an outline, ראשי פרקים, mathly2/prompter.py) and are shown as a large list.
   The screen is kept awake while the prompter is open (where the browser allows it), and the text size is kept
   separately for scrolling and for slides in portrait and in landscape (a mini iPad turned either way). */
(()=>{
const CSS=`
.mxp{position:fixed;inset:0;z-index:2147483000;background:#000;color:#fff;display:flex;flex-direction:column;font-family:"Rubik","Assistant",system-ui,sans-serif;-webkit-user-select:none;user-select:none}
.mxp-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 14px;background:#111;border-bottom:1px solid #333;transition:opacity .3s}
.mxp.playing .mxp-bar{opacity:.15}.mxp.playing .mxp-bar:hover,.mxp.playing .mxp-bar:focus-within{opacity:1}
.mxp-bar button{background:#222;color:#fff;border:1px solid #444;border-radius:8px;padding:6px 12px;font:inherit;font-size:15px;cursor:pointer;min-width:40px;min-height:40px}
.mxp-bar button:hover{background:#333}.mxp-bar button[aria-pressed="true"]{background:#f5c518;color:#000;border-color:#f5c518}
.mxp-bar .mxp-play{background:#2e7d32;border-color:#2e7d32;min-width:90px}.mxp.playing .mxp-play{background:#c62828;border-color:#c62828}
.mxp-bar label{display:flex;align-items:center;gap:6px;font-size:14px;color:#bbb}
.mxp-bar input[type=range]{width:110px;accent-color:#f5c518}
.mxp-sp{flex:1}
.mxp.slides .mxp-xo,.mxp:not(.slides) .mxp-so{display:none}
.mxp-view{position:relative;flex:1;overflow:hidden}
.mxp-scroll{position:absolute;inset:0;overflow-y:scroll;scrollbar-width:none}
.mxp-scroll::-webkit-scrollbar{display:none}
.mxp-text{margin:0 auto;max-width:min(1100px,92vw);padding:45vh 0 60vh;white-space:pre-wrap;line-height:1.45;font-weight:600;text-align:start;unicode-bidi:plaintext}
.mxp-text .mxp-dir{color:#777;font-size:.45em;font-weight:500;letter-spacing:.02em}
.mxp.mirror .mxp-text,.mxp.mirror .mxp-slide{transform:scaleX(-1)}
.mxp-guide{position:absolute;inset-inline:0;top:38%;height:1.6em;pointer-events:none;border-block:2px solid rgba(245,197,24,.55);background:rgba(245,197,24,.07)}
.mxp-guide::before,.mxp-guide::after{content:"";position:absolute;top:50%;translate:0 -50%;border:12px solid transparent}
.mxp-guide::before{left:4px;border-left-color:#f5c518}.mxp-guide::after{right:4px;border-right-color:#f5c518}
.mxp-fade{position:absolute;inset-inline:0;height:22%;pointer-events:none}
.mxp-fade.top{top:0;background:linear-gradient(#000,transparent)}.mxp-fade.bot{bottom:0;background:linear-gradient(transparent,#000)}
.mxp.slides .mxp-scroll,.mxp.slides .mxp-guide,.mxp.slides .mxp-fade,.mxp:not(.slides) .mxp-slide{display:none}
.mxp-slide{position:absolute;inset:0;display:flex;flex-direction:column;touch-action:pan-y}
.mxp-shead{display:flex;align-items:center;gap:14px;padding:12px 20px;background:#0d0d0d;border-bottom:1px solid #262626;color:#bbb;font-size:18px;line-height:1.3}
.mxp-snum{flex:none;font-weight:700;color:#f5c518;font-variant-numeric:tabular-nums}
.mxp-stitle{flex:1;min-width:0;color:#eee;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext;text-align:start}
.mxp-stitle small{display:block;color:#888;font-weight:400;font-size:.78em}
.mxp-clock{flex:none;display:flex;flex-direction:column;align-items:flex-end;font-variant-numeric:tabular-nums;font-weight:700}
.mxp-timer{font-size:22px;color:#ddd}.mxp-timer.warn{color:#f5a623}.mxp-timer.over{color:#ff5252}
.mxp-timer.idle{color:#666}
.mxp-delta{font-size:14px;font-weight:600}.mxp-delta.ahead{color:#66bb6a}.mxp-delta.behind{color:#ff8a80}
.mxp-sbody{flex:1;overflow-y:auto;padding:2.5vh max(4vw,20px) 4vh;line-height:1.38;font-weight:600;scrollbar-width:none;animation:mxp-in .25s ease}
.mxp-sbody::-webkit-scrollbar{display:none}
.mxp-sbody p{margin:0 0 .4em;max-width:1100px;unicode-bidi:plaintext;text-align:start}
.mxp-sbody p.gap{height:.35em;margin:0}
.mxp-sbody p.pt{position:relative;padding-inline-start:1.1em;margin-bottom:.7em;font-size:1.25em;line-height:1.25}
.mxp-sbody p.pt::before{content:"";position:absolute;inset-inline-start:.15em;top:.45em;width:.38em;height:.38em;border-radius:50%;background:#f5c518}
.mxp-sbody em{font-style:normal;color:#f5c518}
.mxp-cue{display:inline-block;padding:0 .35em;margin:0 .15em;border-radius:.3em;font-size:.6em;vertical-align:.2em;background:#1565c0;color:#fff;font-weight:700}
.mxp-cue.pause{background:#444}
.mxp-more{position:absolute;inset-inline-end:16px;bottom:56px;padding:4px 12px;border-radius:999px;background:#f5c518;color:#000;font-size:15px;font-weight:700;pointer-events:none}
.mxp-sfoot{padding:10px 20px;border-top:1px solid #262626;color:#888;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mxp-sfoot b{color:#bbb;font-weight:600;unicode-bidi:plaintext}
@keyframes mxp-in{from{opacity:.2}to{opacity:1}}
.mxp-progress{height:3px;background:#222}.mxp-progress i{display:block;height:100%;width:0;background:#f5c518}
.mxp-hint{position:absolute;left:50%;bottom:8%;translate:-50% 0;z-index:2;display:flex;align-items:center;gap:10px;padding:12px 22px;border-radius:999px;background:rgba(20,20,20,.95);border:1px solid rgba(245,197,24,.6);color:#fff;font-size:22px;font-weight:600;white-space:nowrap;pointer-events:none;opacity:0;scale:.92;transition:opacity .25s ease,scale .25s ease}
.mxp-hint.on{opacity:1;scale:1}
.mxp-hint b{color:#f5c518;font-size:28px;line-height:1}
@media (prefers-reduced-motion:reduce){.mxp-hint{transition:opacity .15s linear;scale:1}.mxp-sbody{animation:none}}
.mxp-count{position:absolute;inset:0;display:grid;place-items:center;font-size:30vh;font-weight:700;color:#f5c518;background:rgba(0,0,0,.6);pointer-events:none}
`;
let hintTimer=0,wheel=0,keepOpen=false,root,scroller,textEl,guide,bar,raf=0,last=0,playing=false,speed=40,mirror=false,acc=0,countTimer=0,back=null;
let sizes={scroll:64,slidesP:34,slidesL:32},prefer="slides",mode="scroll",deck=null,cur=0,clock0=0,slide0=0,tickTimer=0,lock=null,touch=null,swiped=false;

function save(){try{localStorage.setItem("mathly.prompter",JSON.stringify({speed,sizes,mirror,mode:prefer}))}catch{}}
function load(){try{const s=JSON.parse(localStorage.getItem("mathly.prompter")||"{}");if(s.speed)speed=s.speed;if(s.size)sizes.scroll=s.size;if(s.sizes)Object.assign(sizes,s.sizes);mirror=!!s.mirror;if(s.mode)prefer=s.mode}catch{}}
function sizeKey(){return mode!=="slides"?"scroll":(matchMedia("(orientation: portrait)").matches?"slidesP":"slidesL");}
function size(){return sizes[sizeKey()];}

function style(){
  if(document.getElementById("mxp-css")) return;
  const el=document.createElement("style"); el.id="mxp-css"; el.textContent=CSS; document.head.appendChild(el);
}

/* ---------- reading a slide script ---------- */
const SLIDE=/^\s*(?:slide|שקף)\s*(\d+)\s*(?:[—–:.-]\s*(.*))?$/i;
const PART=/^\s*(?:part|חלק)\s*\d+\s*(?:[—–:.-]\s*.*)?$/i;
// "40 seconds", "Opening · 35 seconds", "1 minute 30 seconds", "1:30", "45 שניות"
function duration(line){
  const t=line.trim(); if(!t||t.length>48) return null;
  const m=t.match(/^(?:(.*?)\s*[·•|,–—-]\s*)?(?:(\d+):(\d\d)|(?:(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|דקות|דקה)\s*(?:and\s*)?)?(?:(\d+)\s*(?:seconds?|secs?|s|שניות))?)\s*$/i);
  if(!m) return null;
  const secs=m[2]!=null?(+m[2])*60+(+m[3]):Math.round((+(m[4]||0))*60)+(+(m[5]||0));
  return secs>0?{secs,label:(m[1]||"").trim()}:null;
}
// a list of slides, or null when the text is not a slide script; kinds[i] marks each line as "slide"/"part"/"time"/""
function parse(text){
  const lines=String(text).split(/\r?\n/), kinds=lines.map(()=>""), slides=[], pre=[];
  let s=null, part="";
  lines.forEach((line,i)=>{
    if(PART.test(line)){ kinds[i]="part"; part=line.trim(); return; }
    const m=line.match(SLIDE);
    if(m){ kinds[i]="slide"; s={num:+m[1],title:(m[2]||"").trim()||line.trim(),part,secs:0,label:"",lines:[]}; part=""; slides.push(s); return; }
    if(s&&!s.lines.some(l=>l.trim())&&!s.secs){ const d=duration(line); if(d){ kinds[i]="time"; s.secs=d.secs; s.label=d.label; return; } }
    (s?s.lines:pre).push(line);
  });
  if(slides.length<2) return {slides:null,kinds:null};
  if(pre.some(l=>l.trim())) slides.unshift({num:0,title:"פתיחה",part:"",secs:0,label:"",lines:pre});
  return {slides,kinds};
}
const BULLET=/^\s*[•\-–]\s+(.+)$/;
function esc(s){return s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function cues(line){
  return esc(line)
    .replace(/\[(?:click|קליק)\]/gi,'<span class="mxp-cue">CLICK ⏵</span>')
    .replace(/\[(?:pause|הפסקה)\]|(^|\s)\/\/(?=\s|$)/gi,(_,sp)=>(sp||"")+'<span class="mxp-cue pause">⏸</span>')
    .replace(/\*([^*\n]+)\*/g,"<em>$1</em>");
}
function fmt(sec){sec=Math.max(0,Math.round(sec));return Math.floor(sec/60)+":"+String(sec%60).padStart(2,"0");}

/* ---------- drawing ---------- */
function sync(){
  const px=size();
  textEl.style.fontSize=sizes.scroll+"px"; guide.style.height=(sizes.scroll*1.45)+"px";
  if(mode==="scroll") textEl.style.paddingTop=guide.offsetTop+"px";   // the first line starts on the reading line
  root.classList.toggle("slides",mode==="slides");
  root.classList.toggle("mirror",mirror); root.classList.toggle("playing",mode==="slides"?!!clock0:playing);
  bar.querySelector(".mxp-play").textContent=playing?"⏸ עצירה":"▶ הפעלה";
  bar.querySelector("[data-p=mirror]").setAttribute("aria-pressed",String(mirror));
  bar.querySelector(".mxp-speed").value=speed; bar.querySelector(".mxp-speed-v").textContent=speed;
  bar.querySelector(".mxp-size-v").textContent=px;
  const m=bar.querySelector("[data-p=mode]"); m.hidden=!deck; m.textContent=mode==="slides"?"☰ גלילה":"▭ שקפים";
  if(mode==="slides"&&deck) fit();
  progress();
}

function progress(){
  const bar=root.querySelector(".mxp-progress i");
  if(mode==="slides"){ bar.style.width=((cur+1)/deck.length*100)+"%"; return; }
  const max=scroller.scrollHeight-scroller.clientHeight;
  bar.style.width=(max>0?scroller.scrollTop/max*100:0)+"%";
}

function drawSlide(){
  const s=deck[cur], el=root.querySelector(".mxp-slide");
  el.querySelector(".mxp-snum").textContent=`${cur+1} / ${deck.length}`;
  const t=el.querySelector(".mxp-stitle");
  t.innerHTML=(s.part||s.label?`<small dir="auto">${esc([s.part,s.label].filter(Boolean).join(" · "))}</small>`:"")+`<span dir="auto">${esc(s.title)}</span>`;
  const body=el.querySelector(".mxp-sbody");
  const lines=s.lines.slice(); while(lines.length&&!lines[0].trim()) lines.shift(); while(lines.length&&!lines.at(-1).trim()) lines.pop();
  // "• " / "- " lines are reminders (an outline, ראשי פרקים): shown as a list, larger and with room between them
  body.innerHTML=lines.map(l=>{
    const b=l.match(BULLET);
    return b?`<p class="pt" dir="auto">${cues(b[1])}</p>`:l.trim()?`<p dir="auto">${cues(l)}</p>`:'<p class="gap"></p>';
  }).join("");
  body.scrollTop=0; body.style.animation="none"; void body.offsetWidth; body.style.animation="";
  fit();
  drawFoot(); drawClock(); progress();
}
// a long slide's notes get smaller (down to 75% of the chosen size) so they fit on one screen; what still does not
// fit scrolls with a finger, and a "more" mark shows until the end has been seen
function fit(){
  const body=root.querySelector(".mxp-sbody"), want=size(), floor=Math.max(20,Math.round(want*.75));
  let px=want; body.style.fontSize=px+"px";
  while(px>floor&&body.scrollHeight>body.clientHeight+2){ px-=2; body.style.fontSize=px+"px"; }
  more();
}
function more(){
  const body=root.querySelector(".mxp-sbody");
  root.querySelector(".mxp-more").hidden=body.scrollTop+body.clientHeight>=body.scrollHeight-4;
}
function drawFoot(){
  const next=deck[cur+1], el=root.querySelector(".mxp-sfoot");
  const what=next?`הבא: <b dir="auto">${esc(next.title)}</b>`:"<b>סוף המצגת</b>";
  el.innerHTML=(clock0?"":"הקשה על המסך מתחילה את השעון · ")+what;
}
function drawClock(){
  if(mode!=="slides"||!root) return;
  const s=deck[cur], now=performance.now(), timer=root.querySelector(".mxp-timer"), delta=root.querySelector(".mxp-delta");
  const spent=clock0?(now-slide0)/1000:0;
  timer.textContent=fmt(spent)+(s.secs?" / "+fmt(s.secs):"");
  timer.className="mxp-timer"+(!clock0?" idle":s.secs&&spent>s.secs?" over":s.secs&&spent>=s.secs*.85?" warn":"");
  // where the talk stands: when this slide began against when the plan says it should, plus any overrun of this slide
  const planned=deck.slice(0,cur).reduce((a,x)=>a+x.secs,0), known=deck.some(x=>x.secs);
  if(!clock0||!known){ delta.innerHTML=""; delta.className="mxp-delta"; return; }
  const d=Math.round((slide0-clock0)/1000-planned+Math.max(0,spent-(s.secs||spent)));
  delta.innerHTML=Math.abs(d)<5?"בזמן":(d>0?"מאחור ":"לפני הזמן ")+`<bdi dir="ltr">${d>0?"+":"−"}${fmt(Math.abs(d))}</bdi>`;
  delta.className="mxp-delta"+(Math.abs(d)<5?"":d>0?" behind":" ahead");
}

function go(i){
  if(!deck) return;
  const to=Math.max(0,Math.min(deck.length-1,i)); if(to===cur) return;
  cur=to; slide0=performance.now(); drawSlide();
}
function startClock(){ clock0=slide0=performance.now(); drawFoot(); drawClock(); sync(); }
function setMode(m){
  if(m==="slides"&&!deck) return;
  mode=m; play(false); sync();
  if(mode==="slides") drawSlide(); else requestAnimationFrame(()=>{ textEl.style.paddingTop=guide.offsetTop+"px"; progress(); });
}

/* ---------- scrolling ---------- */
function tick(now){
  if(!playing) return;
  const dt=last?(now-last)/1000:0; last=now;
  acc+=speed*dt*(sizes.scroll/64);         // speed is in "lines-ish" units, so it feels the same at any text size
  const step=Math.floor(acc); if(step){acc-=step; scroller.scrollTop+=step;}
  progress();
  if(scroller.scrollTop>=scroller.scrollHeight-scroller.clientHeight-1){playing=false;sync();return;}
  raf=requestAnimationFrame(tick);
}

function play(on){
  clearInterval(countTimer); root.querySelector(".mxp-count")?.remove();
  playing=on; last=0; acc=0; cancelAnimationFrame(raf); sync();
  if(on) raf=requestAnimationFrame(tick);
}

function countdown(){
  if(playing||root.querySelector(".mxp-count")) return play(false);   // a second press during 3-2-1 cancels it
  if(scroller.scrollTop>0) return play(true);                         // 3-2-1 only from the start; after a pause it resumes at once
  let n=3; const el=document.createElement("div"); el.className="mxp-count"; el.textContent=n; root.querySelector(".mxp-view").appendChild(el);
  countTimer=setInterval(()=>{n--; if(n>0) el.textContent=n; else play(true);},700);
}

// a short note at the bottom centre that fades in, stays a moment and fades out, so a mouse or clicker action is seen
function hint(icon,text){
  const el=root?.querySelector(".mxp-hint"); if(!el) return;
  el.innerHTML=""; const b=document.createElement("b"); b.textContent=icon; const span=document.createElement("span"); span.textContent=text;
  el.append(b,span); el.classList.add("on");
  clearTimeout(hintTimer); hintTimer=setTimeout(()=>el.classList.remove("on"),1100);
}
const HINTS={
  play:()=>playing||root.querySelector(".mxp-count")?["▶","הפעלה"]:["⏸","עצירה"],
  faster:()=>["⏩",`מהירות ${speed}`+(speed>=300?" (מקסימום)":"")], slower:()=>["⏪",`מהירות ${speed}`+(speed<=5?" (מינימום)":"")],
  bigger:()=>["A+",`גודל ${size()}`], smaller:()=>["A−",`גודל ${size()}`],
  mirror:()=>["⇋",mirror?"מראה: מופעלת":"מראה: כבויה"], top:()=>mode==="slides"?["⏮","לשקף הראשון, השעון אופס"]:["⏮","להתחלה"],
  back:()=>["↶","כמה שורות אחורה"], mode:()=>mode==="slides"?["▭","שקף אחר שקף"]:["☰","גלילה"],
};

function act(p){
  actOnly(p);
  if(root&&HINTS[p]) hint(...HINTS[p]());
}

function actOnly(p){
  const k=sizeKey();
  switch(p){
    case "play": return countdown();
    case "next": if(!clock0) return startClock(); return go(cur+1);
    case "prev": return go(cur-1);
    case "mode": prefer=mode==="slides"?"scroll":"slides"; save(); return setMode(prefer);
    case "slower": speed=Math.max(5,speed-5); break;
    case "faster": speed=Math.min(300,speed+5); break;
    case "smaller": sizes[k]=Math.max(20,sizes[k]-(k==="scroll"?6:4)); break;
    case "bigger": sizes[k]=Math.min(200,sizes[k]+(k==="scroll"?6:4)); break;
    case "mirror": mirror=!mirror; break;
    case "top":
      if(mode==="slides"){ cur=-1; clock0=0; go(0); sync(); return; }
      scroller.scrollTop=0; acc=0; progress(); break;
    case "back": scroller.scrollTop-=sizes.scroll*1.45*3; acc=0; progress(); return;
    case "full": if(document.fullscreenElement){keepOpen=true; document.exitFullscreen?.();} else root.requestFullscreen?.().catch(()=>{}); return;
    case "close": return close();
  }
  save(); sync();
}

const KEYS={" ":"play",ArrowUp:"faster",ArrowDown:"slower","+":"bigger","=":"bigger","-":"smaller",m:"mirror",M:"mirror","מ":"mirror","צ":"mirror",Home:"top",PageDown:"play",ArrowRight:"play",PageUp:"back",ArrowLeft:"back",f:"full",F:"full","כ":"full",s:"mode",S:"mode","ד":"mode",Escape:"close"};
const SLIDE_KEYS={...KEYS," ":"next",PageDown:"next",ArrowRight:"next",ArrowDown:"next",Enter:"next",PageUp:"prev",ArrowLeft:"prev",ArrowUp:"prev",Backspace:"prev"};
function onKey(e){
  if(!root) return;
  const p=(mode==="slides"?SLIDE_KEYS:KEYS)[e.key]; if(!p) return;
  if(e.target.closest?.("input")&&p!=="close") return;
  e.preventDefault(); e.stopImmediatePropagation(); act(p);
}

// in full screen the browser keeps Esc for itself (it leaves full screen and the page never sees the key), so leaving
// full screen closes the prompter too, unless it was F or the ⛶ button
function onFull(){
  if(document.fullscreenElement||!root) return;
  if(keepOpen){keepOpen=false; return;}
  close();
}

// keep the screen on (a tablet would otherwise dim and lock in the middle of a talk); the lock is lost whenever the
// page is hidden, so it is asked for again when the page comes back
async function wake(){
  if(!root||document.visibilityState!=="visible"||!navigator.wakeLock) return;
  try{ lock=await navigator.wakeLock.request("screen"); }catch{}
}
function onVisible(){ if(document.visibilityState==="visible") wake(); }
function onTurn(){ if(root){ sync(); if(mode==="scroll") textEl.style.paddingTop=guide.offsetTop+"px"; } }

function open(text){
  if(!String(text||"").trim()) return;
  close(); style(); load(); back=document.activeElement;
  const parsed=parse(text); deck=parsed.slides; cur=0; clock0=slide0=0;
  mode=deck&&prefer==="slides"?"slides":"scroll";
  root=document.createElement("div"); root.className="mxp"; root.setAttribute("role","dialog"); root.setAttribute("aria-modal","true"); root.setAttribute("aria-label","פרומפטר");
  root.innerHTML=`<div class="mxp-bar" dir="rtl">
      <button class="mxp-play mxp-xo" data-p="play"></button>
      <button class="mxp-so" data-p="prev" title="השקף הקודם (← / Page Up)" aria-label="השקף הקודם">→</button>
      <button class="mxp-so" data-p="next" title="השקף הבא (→ / Page Down / רווח)" aria-label="השקף הבא">←</button>
      <button data-p="top" title="חזרה להתחלה (Home)">⏮</button>
      <label class="mxp-xo">מהירות <input class="mxp-speed" type="range" min="5" max="300" step="5" aria-label="מהירות"><b class="mxp-speed-v"></b></label>
      <button class="mxp-xo" data-p="slower" title="לאט יותר (↓)">−</button><button class="mxp-xo" data-p="faster" title="מהר יותר (↑)">+</button>
      <label>גודל <b class="mxp-size-v"></b></label>
      <button data-p="smaller" title="קטן יותר (-)">A−</button><button data-p="bigger" title="גדול יותר (+)">A+</button>
      <button data-p="mirror" title="היפוך מראה (M)">⇋ מראה</button>
      <button data-p="mode" title="שקף אחר שקף או גלילה (S)" hidden></button>
      <span class="mxp-sp"></span>
      <button data-p="full" title="מסך מלא (F)">⛶</button>
      <button data-p="close" title="סגירה (Esc)" aria-label="סגירה">✕</button></div>
    <div class="mxp-progress"><i></i></div>
    <div class="mxp-view"><div class="mxp-scroll"><div class="mxp-text" dir="auto"></div></div>
      <div class="mxp-fade top"></div><div class="mxp-fade bot"></div><div class="mxp-guide"></div>
      <div class="mxp-slide" dir="rtl">
        <div class="mxp-shead"><span class="mxp-snum" dir="ltr"></span><span class="mxp-stitle"></span>
          <span class="mxp-clock"><span class="mxp-timer" dir="ltr"></span><span class="mxp-delta" role="status"></span></span></div>
        <div class="mxp-sbody" dir="auto" aria-live="polite"></div>
        <div class="mxp-more" hidden>▼ עוד</div>
        <div class="mxp-sfoot"></div></div>
      <div class="mxp-hint" role="status" aria-live="polite"></div></div>`;
  if(deck){ const he=/[\u0590-\u05ff\u0600-\u06ff]/.test(deck.map(d=>d.title).join(" ")); root.querySelector(".mxp-slide").dir=he?"rtl":"ltr"; }
  root.querySelector(".mxp-sbody").addEventListener("scroll",()=>root&&more(),{passive:true});
  scroller=root.querySelector(".mxp-scroll"); textEl=root.querySelector(".mxp-text"); guide=root.querySelector(".mxp-guide"); bar=root.querySelector(".mxp-bar");
  if(deck){   // scrolling a slide script: the headings and timings are shown small and grey, not read out
    const lines=String(text).split(/\r?\n/);
    textEl.replaceChildren(...lines.flatMap((l,i)=>{
      const out=[]; if(i) out.push("\n");
      if(parsed.kinds[i]){ const s=document.createElement("span"); s.className="mxp-dir"; s.textContent=l; out.push(s); } else out.push(l);
      return out;
    }));
  } else textEl.textContent=text;
  bar.addEventListener("click",e=>{const b=e.target.closest("[data-p]"); if(b) act(b.dataset.p);});
  bar.querySelector(".mxp-speed").addEventListener("input",e=>{speed=+e.target.value; save(); sync();});
  scroller.addEventListener("scroll",progress,{passive:true});
  const view=root.querySelector(".mxp-view");
  // a finger swipe across the slide: to the left the next slide, to the right the one before (up and down scroll a long slide)
  view.addEventListener("pointerdown",e=>{ touch={x:e.clientX,y:e.clientY}; swiped=false; });
  view.addEventListener("pointercancel",()=>{ touch=null; });
  view.addEventListener("pointerup",e=>{
    if(!touch||mode!=="slides") return;
    const dx=e.clientX-touch.x, dy=e.clientY-touch.y; touch=null;
    if(Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)*1.5){ swiped=true; act(dx<0?"next":"prev"); }
    else if(Math.abs(dx)>10||Math.abs(dy)>10) swiped=true;   // a drag that scrolled the notes is not a tap
  });
  view.addEventListener("click",()=>{ if(swiped){swiped=false; return;} act(mode==="slides"?"next":"play"); });
  view.addEventListener("wheel",e=>{            // while playing the wheel is a speed knob: down faster, up slower
    if(mode==="slides"||!playing){acc=0; return;}
    e.preventDefault(); wheel+=e.deltaMode?e.deltaY*40:e.deltaY;
    if(Math.abs(wheel)>=60){act(wheel>0?"faster":"slower"); wheel=0;}
  },{passive:false});
  view.addEventListener("contextmenu",e=>{e.preventDefault(); act(mode==="slides"?"prev":"back");});
  // middle and side buttons: mouseup is where the browser would scroll or go back a page, so both are stopped
  view.addEventListener("mousedown",e=>{if([1,3,4].includes(e.button)) e.preventDefault();});
  view.addEventListener("mouseup",e=>{
    const p=({1:"top",3:"top",4:mode==="slides"?"next":"play"})[e.button]; if(p){e.preventDefault(); act(p);}
  });
  document.body.appendChild(root);
  document.addEventListener("keydown",onKey,true);
  document.addEventListener("fullscreenchange",onFull);
  document.addEventListener("visibilitychange",onVisible);
  addEventListener("resize",onTurn);
  tickTimer=setInterval(drawClock,250);
  sync(); if(mode==="slides") drawSlide();
  bar.querySelector(mode==="slides"?"[data-p=next]":".mxp-play").focus();
  wake();
  // it opens full screen; this runs inside the click that opened it, which the browser requires. Where the browser
  // does not allow it (an iPhone), it simply stays as a full-page layer.
  const full=root.requestFullscreen||root.webkitRequestFullscreen;
  try{ const p=full?.call(root); p?.catch?.(()=>{}); }catch{}
}

function close(){
  if(!root) return;
  clearTimeout(hintTimer); clearInterval(tickTimer);
  play(false); document.removeEventListener("keydown",onKey,true); document.removeEventListener("fullscreenchange",onFull);
  document.removeEventListener("visibilitychange",onVisible); removeEventListener("resize",onTurn);
  lock?.release?.().catch?.(()=>{}); lock=null;
  if(document.fullscreenElement) document.exitFullscreen?.();
  root.remove(); root=null; deck=null; back?.focus?.(); back=null;
}

window.MathlyPrompter={open,close,isOpen:()=>!!root,parse};
})();
