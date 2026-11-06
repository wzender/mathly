/* Prompter (פרומפטר): a full-screen teleprompter for developers, opened from ניהול.
   It stands alone, with its own styles. window.MathlyPrompter.open(text) shows it.
   Keys: Space play/pause · ↑/↓ speed · +/- text size · M mirror · Home back to start · Esc close.
   A presentation clicker: Page Down / → play/pause, Page Up / ← back a few lines.
   A mouse: click play/pause · wheel changes the speed while playing (scrolls the text while paused) ·
   right-click back a few lines · middle-click or the mouse's back button to the start · forward button play/pause. */
(()=>{
const CSS=`
.mxp{position:fixed;inset:0;z-index:2147483000;background:#000;color:#fff;display:flex;flex-direction:column;font-family:"Rubik","Assistant",system-ui,sans-serif}
.mxp-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:10px 14px;background:#111;border-bottom:1px solid #333;transition:opacity .3s}
.mxp.playing .mxp-bar{opacity:.15}.mxp.playing .mxp-bar:hover,.mxp.playing .mxp-bar:focus-within{opacity:1}
.mxp-bar button{background:#222;color:#fff;border:1px solid #444;border-radius:8px;padding:6px 12px;font:inherit;font-size:15px;cursor:pointer;min-width:40px}
.mxp-bar button:hover{background:#333}.mxp-bar button[aria-pressed="true"]{background:#f5c518;color:#000;border-color:#f5c518}
.mxp-bar .mxp-play{background:#2e7d32;border-color:#2e7d32;min-width:90px}.mxp.playing .mxp-play{background:#c62828;border-color:#c62828}
.mxp-bar label{display:flex;align-items:center;gap:6px;font-size:14px;color:#bbb}
.mxp-bar input[type=range]{width:110px;accent-color:#f5c518}
.mxp-sp{flex:1}
.mxp-view{position:relative;flex:1;overflow:hidden}
.mxp-scroll{position:absolute;inset:0;overflow-y:scroll;scrollbar-width:none}
.mxp-scroll::-webkit-scrollbar{display:none}
.mxp-text{margin:0 auto;max-width:min(1100px,92vw);padding:45vh 0 60vh;white-space:pre-wrap;line-height:1.45;font-weight:600;text-align:center;unicode-bidi:plaintext}
.mxp.mirror .mxp-text{transform:scaleX(-1)}
.mxp-guide{position:absolute;inset-inline:0;top:38%;height:1.6em;pointer-events:none;border-block:2px solid rgba(245,197,24,.55);background:rgba(245,197,24,.07)}
.mxp-guide::before,.mxp-guide::after{content:"";position:absolute;top:50%;translate:0 -50%;border:12px solid transparent}
.mxp-guide::before{left:4px;border-left-color:#f5c518}.mxp-guide::after{right:4px;border-right-color:#f5c518}
.mxp-fade{position:absolute;inset-inline:0;height:22%;pointer-events:none}
.mxp-fade.top{top:0;background:linear-gradient(#000,transparent)}.mxp-fade.bot{bottom:0;background:linear-gradient(transparent,#000)}
.mxp-progress{height:3px;background:#222}.mxp-progress i{display:block;height:100%;width:0;background:#f5c518}
.mxp-count{position:absolute;inset:0;display:grid;place-items:center;font-size:30vh;font-weight:700;color:#f5c518;background:rgba(0,0,0,.6);pointer-events:none}
`;
let wheel=0,keepOpen=false,root,scroller,textEl,guide,bar,raf=0,last=0,playing=false,speed=40,size=64,mirror=false,acc=0,countTimer=0,back=null;

function save(){try{localStorage.setItem("mathly.prompter",JSON.stringify({speed,size,mirror}))}catch{}}
function load(){try{const s=JSON.parse(localStorage.getItem("mathly.prompter")||"{}");if(s.speed)speed=s.speed;if(s.size)size=s.size;mirror=!!s.mirror}catch{}}

function style(){
  if(document.getElementById("mxp-css")) return;
  const el=document.createElement("style"); el.id="mxp-css"; el.textContent=CSS; document.head.appendChild(el);
}

function sync(){
  textEl.style.fontSize=size+"px"; guide.style.height=(size*1.45)+"px";
  root.classList.toggle("mirror",mirror); root.classList.toggle("playing",playing);
  bar.querySelector(".mxp-play").textContent=playing?"⏸ עצירה":"▶ הפעלה";
  bar.querySelector("[data-p=mirror]").setAttribute("aria-pressed",String(mirror));
  bar.querySelector(".mxp-speed").value=speed; bar.querySelector(".mxp-speed-v").textContent=speed;
  bar.querySelector(".mxp-size-v").textContent=size;
}

function progress(){
  const max=scroller.scrollHeight-scroller.clientHeight;
  root.querySelector(".mxp-progress i").style.width=(max>0?scroller.scrollTop/max*100:0)+"%";
}

function tick(now){
  if(!playing) return;
  const dt=last?(now-last)/1000:0; last=now;
  acc+=speed*dt*(size/64);                 // speed is in "lines-ish" units, so it feels the same at any text size
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

function act(p){
  switch(p){
    case "play": return countdown();
    case "slower": speed=Math.max(5,speed-5); break;
    case "faster": speed=Math.min(300,speed+5); break;
    case "smaller": size=Math.max(24,size-6); break;
    case "bigger": size=Math.min(200,size+6); break;
    case "mirror": mirror=!mirror; break;
    case "top": scroller.scrollTop=0; acc=0; progress(); break;
    case "back": scroller.scrollTop-=size*1.45*3; acc=0; progress(); return;
    case "full": if(document.fullscreenElement){keepOpen=true; document.exitFullscreen?.();} else root.requestFullscreen?.().catch(()=>{}); return;
    case "close": return close();
  }
  save(); sync();
}

function onKey(e){
  if(!root) return;
  const map={" ":"play",ArrowUp:"faster",ArrowDown:"slower","+":"bigger","=":"bigger","-":"smaller",m:"mirror",M:"mirror","מ":"mirror",Home:"top",PageDown:"play",ArrowRight:"play",PageUp:"back",ArrowLeft:"back",f:"full",F:"full",Escape:"close"};
  const p=map[e.key]; if(!p) return;
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

function open(text){
  if(!String(text||"").trim()) return;
  close(); style(); load(); back=document.activeElement;
  root=document.createElement("div"); root.className="mxp"; root.setAttribute("role","dialog"); root.setAttribute("aria-modal","true"); root.setAttribute("aria-label","פרומפטר");
  root.innerHTML=`<div class="mxp-bar" dir="rtl">
      <button class="mxp-play" data-p="play"></button>
      <button data-p="top" title="חזרה להתחלה (Home)">⏮</button>
      <label>מהירות <input class="mxp-speed" type="range" min="5" max="300" step="5" aria-label="מהירות"><b class="mxp-speed-v"></b></label>
      <button data-p="slower" title="לאט יותר (↓)">−</button><button data-p="faster" title="מהר יותר (↑)">+</button>
      <label>גודל <b class="mxp-size-v"></b></label>
      <button data-p="smaller" title="קטן יותר (-)">A−</button><button data-p="bigger" title="גדול יותר (+)">A+</button>
      <button data-p="mirror" title="היפוך מראה (M)">⇋ מראה</button>
      <span class="mxp-sp"></span>
      <button data-p="full" title="מסך מלא (F)">⛶</button>
      <button data-p="close" title="סגירה (Esc)" aria-label="סגירה">✕</button></div>
    <div class="mxp-progress"><i></i></div>
    <div class="mxp-view"><div class="mxp-scroll"><div class="mxp-text" dir="auto"></div></div>
      <div class="mxp-fade top"></div><div class="mxp-fade bot"></div><div class="mxp-guide"></div></div>`;
  scroller=root.querySelector(".mxp-scroll"); textEl=root.querySelector(".mxp-text"); guide=root.querySelector(".mxp-guide"); bar=root.querySelector(".mxp-bar");
  textEl.textContent=text;
  bar.addEventListener("click",e=>{const b=e.target.closest("[data-p]"); if(b) act(b.dataset.p);});
  bar.querySelector(".mxp-speed").addEventListener("input",e=>{speed=+e.target.value; save(); sync();});
  scroller.addEventListener("scroll",progress,{passive:true});
  const view=root.querySelector(".mxp-view");
  view.addEventListener("click",()=>countdown());
  view.addEventListener("wheel",e=>{            // while playing the wheel is a speed knob: down faster, up slower
    if(!playing){acc=0; return;}
    e.preventDefault(); wheel+=e.deltaMode?e.deltaY*40:e.deltaY;
    if(Math.abs(wheel)>=60){act(wheel>0?"faster":"slower"); wheel=0;}
  },{passive:false});
  view.addEventListener("contextmenu",e=>{e.preventDefault(); act("back");});
  // middle and side buttons: mouseup is where the browser would scroll or go back a page, so both are stopped
  const extra={1:"top",3:"top",4:"play"};
  view.addEventListener("mousedown",e=>{if(extra[e.button]) e.preventDefault();});
  view.addEventListener("mouseup",e=>{const p=extra[e.button]; if(p){e.preventDefault(); act(p);}});
  document.body.appendChild(root);
  document.addEventListener("keydown",onKey,true);
  document.addEventListener("fullscreenchange",onFull);
  sync(); bar.querySelector(".mxp-play").focus();
  // it opens full screen; this runs inside the click that opened it, which the browser requires. Where the browser
  // does not allow it (an iPhone), it simply stays as a full-page layer.
  const full=root.requestFullscreen||root.webkitRequestFullscreen;
  try{ const p=full?.call(root); p?.catch?.(()=>{}); }catch{}
}

function close(){
  if(!root) return;
  play(false); document.removeEventListener("keydown",onKey,true); document.removeEventListener("fullscreenchange",onFull);
  if(document.fullscreenElement) document.exitFullscreen?.();
  root.remove(); root=null; back?.focus?.(); back=null;
}

window.MathlyPrompter={open,close,isOpen:()=>!!root};
})();
