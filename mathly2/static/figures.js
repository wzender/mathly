// Drawing for exercise-bank questions that have a `figure` (geometry) or a `graph` (a function's points).
// Ported from the current app's static/math.js (figure() and plot()), unchanged except that the marks use class
// "mk" (the new app already uses "m" for formulas). The syntax of `figure` is described below.
import { esc } from "./math.js";

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
      for(let i=0;i<arcs;i++){ const r=16+i*4; marks+=`<path class="mk" d="M${f(v[0]+r*u1[0])},${f(v[1]+r*u1[1])}A${r},${r} 0 0 ${d>0?1:0} ${f(v[0]+r*u2[0])},${f(v[1]+r*u2[1])}"/>`; }
      const b=unit([u1[0]+u2[0],u1[1]+u2[1]]), r=16+(arcs-1)*4+13+Math.max(0,(45-deg)*0.45);
      if(a.length>3) words+=txt(v[0]+b[0]*r,v[1]+b[1]*r,a.slice(3).join(" "),"q");
    }
    else if(op==="right"){ const v=at(a[1]), u1=unit([at(a[0])[0]-v[0],at(a[0])[1]-v[1]]), u2=unit([at(a[2])[0]-v[0],at(a[2])[1]-v[1]]), k=10;
      marks+=`<path class="mk" d="M${f(v[0]+k*u1[0])},${f(v[1]+k*u1[1])}L${f(v[0]+k*(u1[0]+u2[0]))},${f(v[1]+k*(u1[1]+u2[1]))}L${f(v[0]+k*u2[0])},${f(v[1]+k*u2[1])}"/>`; }
    else if(op==="tick"||op==="par"){ const {u,n,mx,my}=side(a[0],a[1]), k=+(a[2]||1);
      // arrows step aside from the equal-side marks of the same side
      const shift=op==="par"&&ops.some(([o,b])=>o==="tick"&&[b[0],b[1]].sort().join()===[a[0],a[1]].sort().join())?14:0;
      for(let i=0;i<k;i++){ const o=(i-(k-1)/2)*(op==="tick"?5:7)+shift, c=[mx+u[0]*o,my+u[1]*o];
        marks+=op==="tick"?`<path class="mk" d="M${f(c[0]-n[0]*6)},${f(c[1]-n[1]*6)}L${f(c[0]+n[0]*6)},${f(c[1]+n[1]*6)}"/>`
          :`<path class="mk" d="M${f(c[0]-u[0]*6-n[0]*5)},${f(c[1]-u[1]*6-n[1]*5)}L${f(c[0])},${f(c[1])}L${f(c[0]-u[0]*6+n[0]*5)},${f(c[1]-u[1]*6+n[1]*5)}"/>`; } }
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

/** The drawings a bank question needs, as HTML: its graph and/or its figure; empty for a plain question. */
export const figures = q => `${q.graph ? plot(q.graph) : ""}${q.figure ? figure(q.figure) : ""}`;
