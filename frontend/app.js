/* Pantalla de supervisión de la Estación 5: dibuja las tarjetas de estación, la cinta, el historial,
 * las alertas y los indicadores a partir del estado S.
 *
 * Por ahora los datos los produce sim.js (cargado antes que este archivo). Cuando el backend tenga los
 * endpoints, los datos llegarán por api.js y sim.js quedará solo como plan B (?sim=1).
 */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
const NAMES={E1:"Recepción",E2:"Calidad visual",E3:"Tamaño",E4:"Decisión",E5:"Registro",E6:"Cinta"};
const LONG={E1:"recepción y captura",E2:"calidad visual",E3:"clasificación por tamaño",E4:"decisión comercial"};
const CAT={exportacion:["Exportación","--c-exp"],mercado_nacional:["Mercado nacional","--c-nac"],proceso:["Proceso","--c-pro"],rechazo:["Rechazo","--c-rec"],revision_manual:["Revisión manual","--c-rev"]};
const TXT={aceptada:"Aceptada",repetir:"Repetir captura",revision:"En revisión",alta:"Alta",media:"Media",baja:"Baja",defectos_visibles:"Defectos visibles",grande:"Grande",mediano:"Mediano",pequeno:"Pequeño",uniforme:"Uniforme",irregular:"Irregular",normal:"Normal",falla_mecanica:"Falla mecánica"};
const t=k=>TXT[k]||k;
const DEF={mancha_leve:"mancha leve",madurez_desigual:"madurez desigual",golpe:"golpe",antracnosis:"antracnosis",piel_danada:"piel dañada"};
const defs=l=>l.map(x=>DEF[x]||x.replace(/_/g," ")).join(", ");
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
const dec=(v,n=1)=>v.toFixed(n).replace(".",",");
const hhmmss=d=>new Date(d).toLocaleTimeString("es-CL",{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
const hhmm=d=>new Date(d).toLocaleTimeString("es-CL",{hour:"2-digit",minute:"2-digit",hour12:false});
const ago=ms=>{const s=Math.max(0,Math.round(ms/1000));return s<60?`hace ${s} s`:`hace ${Math.floor(s/60)} min`};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const S={running:true,seq:0,hist:[],alerts:[],last:{},e3cut:false,lowconf:false,e6:"normal",msgs:0,shiftStart:Date.now()-58*60e3,freshId:null,conf:[],pi:{temp:51,cpu:17,ram:1.9},
  g:null,ph:null,phT:0,lastReg:null};

const sim=E5Sim.crear(S,{clamp,dec,defs,t});
sim.seed();

/* ---------- recorrido del grupo por la cinta ----------
   Optimizado para la Raspberry Pi:
   - La animación (requestAnimationFrame) corre solo mientras el grupo se mueve. Cuando está detenido
     en una estación, saliendo a registro o con la cinta parada, basta un temporizador hasta el fin de la fase.
   - Las posiciones de las estaciones se miden una vez (al cargar, al cambiar el tamaño o la orientación),
     no en cada cuadro.
   - El color de las frutas se actualiza solo cuando llega un resultado, no en cada cuadro.
   - La textura de la cinta se desplaza con transform, que la GPU mueve sin repintar.
   El grupo entra desde fuera de la cinta por la izquierda y, tras E4, se desvanece al llegar al final:
   la fila de la cinta recorta lo que queda fuera, así el grupo nunca invade otros paneles. */
const beltrow=$("beltrow"),tex=$("tex");
let fgEl=null,fgW=0,beltShift=0,pos=null,opacidad=1;
let raf=0,timer=0,t0=0,base=0;   // t0 y base: momento y avance (s) con que empezó a correr la fase actual

function medir(){
  const br=beltrow.getBoundingClientRect();
  pos={ancho:br.width};
  for(let k=0;k<4;k++){const c=$("c-E"+(k+1)).getBoundingClientRect();pos[k]=c.left+c.width/2-br.left}
  fgW=fgEl?fgEl.offsetWidth:0}
/* Centro del grupo en cada punto del recorrido. Entrada y salida quedan justo fuera de la cinta. */
const lugar=to=>to==="start"?-fgW/2-8:to==="exit"?pos.ancho+fgW/2+8:pos[to];
const ease=x=>x<.5?2*x*x:1-Math.pow(-2*x+2,2)/2;
function dibujar(){
  const g=S.g,p=S.ph;if(!g||!p||!fgEl||!pos)return;
  let x,op=1;
  if(p.t==="move"){
    const a=lugar(g.from),b=lugar(p.to),avance=clamp(S.phT/p.d,0,1);x=a+(b-a)*ease(avance);
    if(p.to==="exit"){
      // Se desvanece desde que deja E4 hasta que su borde derecho toca el final de la cinta
      const borde=pos.ancho-fgW/2;op=borde>a?1-clamp((x-a)/(borde-a),0,1):1-avance}}
  else if(p.t==="gap")x=lugar("start");
  else if(p.t==="reg"){x=lugar("exit");op=0}
  else x=lugar(g.from);
  fgEl.style.transform=`translateX(${(x-fgW/2).toFixed(1)}px)`;
  if(op!==opacidad){opacidad=op;fgEl.style.opacity=op.toFixed(3)}}
function colorFrutas(){
  if(!fgEl)return;const g=S.g;
  fgEl.querySelectorAll(".fs i").forEach((s,i)=>{const a=g.fr[i].an;s.className=a.some(z=>z[0]==="falla")?"bad":a.length?"warn":""})}
function marks(){
  medir();beltrow.querySelectorAll(".mark").forEach(m=>m.remove());
  for(let k=0;k<4;k++){const m=document.createElement("div");m.className="mark";m.textContent="E"+(k+1);m.style.left=pos[k]+"px";beltrow.appendChild(m)}
  dibujar()}

function cancelar(){cancelAnimationFrame(raf);clearTimeout(timer);raf=timer=0}
/* Hace correr la fase actual desde S.phT: animada si es un traslado, con un temporizador si no. */
function programar(){
  cancelar();dibujar();
  if(!S.running||!S.ph)return;
  t0=performance.now();base=S.phT;
  if(S.ph.t==="move")raf=requestAnimationFrame(frame);
  else timer=setTimeout(endPhase,Math.max(0,(S.ph.d-S.phT)*1000))}
/* Congela la fase en el punto en que va (falla de cinta). */
function detener(){
  if(raf||timer)S.phT=Math.min(S.ph.d,base+(performance.now()-t0)/1000);
  cancelar();dibujar()}
function frame(now){
  raf=0;const prev=S.phT;
  S.phT=base+Math.max(0,now-t0)/1000;
  if(S.phT>=S.ph.d){endPhase();return}
  beltShift=(beltShift+(S.phT-prev)*90)%28;tex.style.transform=`translateX(${beltShift.toFixed(1)}px)`;
  dibujar();
  raf=requestAnimationFrame(frame)}

function startGroup(){
  const g=sim.newGroup(Date.now());S.g=g;g.P=sim.plan(g);g.pi=0;S.phT=0;g.from="start";
  if(fgEl)fgEl.remove();
  fgEl=document.createElement("div");fgEl.className="fg";fgEl.innerHTML=`<span class="id">${g.id}</span><span class="fs">${g.fr.map(()=>"<i></i>").join("")}</span>`;
  beltrow.appendChild(fgEl);fgW=fgEl.offsetWidth;opacidad=1;colorFrutas();enterPhase();render.all()}
function enterPhase(){
  const g=S.g,p=g.P[g.pi];S.ph=p;S.phT=0;
  if(p.t==="move"){S.moving=true;sim.e6send("normal",false)}else S.moving=false;
  programar()}
function endPhase(){
  cancelar();
  const g=S.g,p=g.P[g.pi],now=Date.now();
  if(p.t==="move")g.from=p.to;
  if(p.t==="proc"){sim.emit(g,p.k,now,true);g.done=p.k+1;colorFrutas()}
  if(p.t==="reg"){sim.finish(g,now);S.freshId=g.id;S.lastReg={g,t:now};S.msgs++}
  g.pi++;
  if(g.pi>=g.P.length){startGroup();return}
  enterPhase();render.all()}

/* ---------- render ---------- */
const EST={ok:["ok","Aprobado"],anomalia:["alerta","Con anomalía"],rechazo:["falla","Con rechazo"],proceso:["","En proceso"]};
const catCount=g=>{const c={};g.fr.forEach(f=>{const k=f.d.E4&&f.d.E4.categoria_final;if(k)c[k]=(c[k]||0)+1});return c};
const dots=g=>`<span class="dots">${g.fr.map(f=>{const k=f.d.E4&&f.d.E4.categoria_final;return `<i style="--c:var(${k?CAT[k][1]:"--off"})" title="${f.k}: ${k?CAT[k][0]:"sin dato"}"></i>`}).join("")}</span>`;
const diamMed=g=>g.fr.every(f=>f.d.E3)?Math.round(g.fr.reduce((s,f)=>s+f.d.E3.diametro_mm,0)/g.n):null;

const render={
  cards(){
    const now=Date.now(),ph=S.ph||{},g=S.g;
    const set=(st,state,pill,body,foot,light)=>{const c=$("c-"+st);c.dataset.s=state;c.querySelector(".pill").textContent=pill;if(body!=null)c.querySelector(".bd").innerHTML=body;c.querySelector(".a").textContent=foot;c.querySelector(".ft .light").className="light "+(light||"")};
    ["E1","E2","E3","E4"].forEach((st,k)=>{
      const L=S.last[st],lg=L&&L.g;let state="espera",pill="En espera";
      if(!S.running){state="detenida";pill="Detenida"}
      else if(ph.t==="proc"&&ph.k===k){state="activo";pill="Procesando "+g.id}
      if(st==="E3"&&S.e3cut){state="sinsenal";pill="Sin señal"}
      let body="";
      if(lg){
        if(st==="E1"){const d=lg.e1;body=d?`<div class="kv"><span>Imagen</span><b class="${d.validez_imagen?"":"x"}">${d.validez_imagen?"Válida":"No válida"}</b><span>Captura</span><b class="${d.estado_captura==="aceptada"?"":"w"}">${t(d.estado_captura)}</b><span>Posición</span><b class="${d.posicion_correcta?"":"w"}">${d.posicion_correcta?"Correcta":"Incorrecta"}</b><span>Frutas detectadas</span><b>${d.frutas_detectadas}</b></div>`:""}
        else{const rows=lg.fr.map(f=>{const d=f.d[st];if(!d)return `<li><span class="p"></span><span class="k">${f.k}</span><span class="v">Sin dato</span><span class="n"></span></li>`;
            const an=f.an.filter(a=>st==="E2"?/confianza|defectos|calidad/.test(a[1]):st==="E3"?/tamaño/.test(a[1]):/rechazada|revisión manual/.test(a[1]));
            const cls=an.some(a=>a[0]==="falla")?"falla":an.length?"alerta":"";
            let v,n;
            if(st==="E2"){v=t(d.calidad_visual);n=`<span class="bar" style="--v:${d.confianza_visual*100}%"></span>${dec(d.confianza_visual,2)}`}
            else if(st==="E3"){v=t(d.tamano);n=d.diametro_mm+" mm"}
            else{v=`<span style="color:var(${CAT[d.categoria_final][1]})">${CAT[d.categoria_final][0]}</span>`;n=dec(d.probabilidad,2)}
            return `<li class="${cls}"><span class="p"></span><span class="k">${f.k}</span><span class="v">${v}</span><span class="n">${n}</span></li>`}).join("");
          let sum="";
          if(st==="E3"){const p=diamMed(lg);sum=p?`<div class="sumline">Diámetro medio <b>${p} mm</b>, ${t(lg.uni||"").toLowerCase()}</div>`:""}
          if(st==="E2"){const c=lg.fr.map(f=>f.d.E2&&f.d.E2.confianza_visual).filter(x=>x!=null);sum=c.length?`<div class="sumline">Confianza media <b>${dec(c.reduce((a,b)=>a+b,0)/c.length,2)}</b></div>`:""}
          if(st==="E4"){const c=catCount(lg);sum=`<div class="sumline">${Object.entries(c).map(([k,v])=>`<b>${v}</b> ${CAT[k][0].toLowerCase()}`).join(", ")}</div>`}
          body=`<ul class="frl">${rows}</ul>${sum}`}
      }
      let foot=lg?`Último: ${lg.id}, ${ago(now-L.t)}`:"Sin datos";
      if(st==="E3"&&S.e3cut)foot="No llegan datos de E3";
      const light=state==="sinsenal"?"falla":L&&L.flag?(L.flag==="falla"&&st!=="E4"?"falla":"alerta"):"ok";
      set(st,state,pill,body,foot,light)});
    // E5
    const reg=ph.t==="reg",R=S.lastReg;
    set("E5",reg?"activo":"espera",reg?"Registrando "+g.id:"Escuchando",
      `<div class="kv"><span>Mensajes del turno</span><b>${S.msgs.toLocaleString("es-CL")}</b><span>Grupos registrados</span><b>${S.hist.length}</b><span>Frutas registradas</span><b>${S.hist.reduce((s,x)=>s+x.n,0).toLocaleString("es-CL")}</b><span>Base de datos</span><b>En línea</b></div>`,
      R?`Último registro: ${R.g.id}, ${ago(now-R.t)}`:"—","ok");
    // E6
    let st6="espera",pill6="Detenida en estación",mv="—";
    if(S.e6==="falla_mecanica"){st6="falla";pill6="Falla mecánica";mv="Detenida por falla"}
    else if(ph.t==="move"){st6="activo";pill6="En movimiento";mv=ph.to==="exit"?"Llevando a la salida":"Avanzando a E"+(ph.to+1)}
    else if(ph.t==="proc"){mv="Detenida en E"+(ph.k+1);pill6=mv}
    else if(ph.t==="reg"||ph.t==="gap"){pill6="En espera";mv="Esperando el próximo grupo"}
    set("E6",st6,pill6,`<div class="kv"><span>Estado</span><b class="${S.e6==="normal"?"":"x"}">${t(S.e6)}</b><span>Movimiento</span><b>${mv}</b><span>Falla mecánica</span><b class="${S.e6==="normal"?"":"x"}">${S.e6==="normal"?"No":"Sí"}</b></div>`,
      "Última señal "+ago(now-S.last.E6.t),S.e6==="normal"?"ok":"falla");
  },
  gnow(){const g=S.g,ph=S.ph;if(!g)return;
    $("gid").innerHTML=`<span>G-</span>${g.id.slice(-4)}`;
    let w;
    if(!S.running)w="Detenido, cinta con falla";
    else if(ph.t==="gap")w="Entrando a la línea";
    else if(ph.t==="move")w=ph.to==="exit"?"Saliendo de la línea":`Avanzando a E${ph.to+1}`;
    else if(ph.t==="proc")w=`En E${ph.k+1}, ${LONG["E"+(ph.k+1)]}`;
    else w="Registrando en E5";
    $("gwhere").textContent=w;
    const fin=g.done<4?"proceso":g.fr.some(f=>f.d.E4&&f.d.E4.categoria_final==="rechazo")?"rechazo":g.an.length?"anomalia":"ok";
    const secs=Math.round((Date.now()-g.realT0)/1000);
    $("gfacts").innerHTML=`<span><b>${g.n}</b> frutas</span><span>Entró <b>${hhmmss(g.realT0)}</b></span><span><b>${secs} s</b> en línea</span><span class="verdict ${fin==="proceso"?"":fin}">${EST[fin][1]}</span>`},
  hist(){
    $("hist").innerHTML=S.hist.slice(0,document.documentElement.classList.contains("vertical")?11:12).map(g=>{const e=EST[g.estado],p=diamMed(g);
      return `<tr class="${g.id===S.freshId?"fresh":""}"><td class="id">${g.id}</td><td>${hhmmss(g.out)}</td><td>${dots(g)} <span style="color:var(--muted)">${g.n}</span></td><td class="r">${p?p+" mm":"—"}</td><td><span class="est"><span class="light ${e[0]}"></span>${e[1]}</span></td></tr>`}).join("");
    $("histCount").textContent=`${S.hist.length} grupos, ${S.hist.reduce((s,g)=>s+g.n,0).toLocaleString("es-CL")} frutas en el turno`},
  alerts(){
    $("alerts").innerHTML=S.alerts.slice(0,8).map(a=>`<li class="${a.sev}"><span class="when">${hhmm(a.t)}</span><span class="msg">${esc(a.msg.charAt(0).toUpperCase()+a.msg.slice(1))}</span><span class="who">${a.st} (${NAMES[a.st].toLowerCase()})${a.ref?", grupo "+a.ref:""}</span></li>`).join("");
    const h=Date.now()-3600e3;$("alCount").textContent=S.alerts.filter(a=>a.sev!=="info"&&a.t>h).length+" en la última hora"},
  kpis(){
    const now=Date.now(),H=S.hist,last=H.filter(g=>g.out>now-3600e3),nfLast=last.reduce((s,g)=>s+g.n,0);
    $("kFph").innerHTML=`${nfLast.toLocaleString("es-CL")}<small>frutas</small>`;
    $("kFphS").textContent=`${last.length} grupos en los últimos 60 min`;
    const bk=new Array(12).fill(0);last.forEach(g=>{const i=11-Math.floor((now-g.out)/300e3);if(i>=0&&i<12)bk[i]+=g.n});
    const mx=Math.max(1,...bk),pts=bk.map((v,i)=>[i*240/11,48-v/mx*42]);
    const ln=pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+","+p[1].toFixed(1)).join(""),end=pts[11];
    $("spark").innerHTML=`<line x1="0" x2="240" y1="48" y2="48" stroke="var(--rule)" stroke-width="1"/><path d="${ln}L240,52L0,52Z" fill="var(--ok)" fill-opacity=".14"/><path d="${ln}" fill="none" stroke="var(--ok)" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${end[0]-3}" cy="${end[1]}" r="3" fill="var(--ok)"/>`;
    const F=H.flatMap(g=>g.fr),n=Math.max(1,F.length);
    const rej=F.filter(f=>f.d.E4&&f.d.E4.categoria_final==="rechazo").length,ano=F.filter(f=>f.an.length).length;
    $("kRej").innerHTML=`${dec(rej/n*100)}<small>%</small>`;$("kRejS").textContent=`${rej} de ${F.length.toLocaleString("es-CL")} frutas del turno`;
    $("kAno").textContent=`${Math.round(ano/n*100)} % de las frutas con alguna anomalía`;
    const cats=Object.keys(CAT).map(k=>[k,F.filter(f=>f.d.E4&&f.d.E4.categoria_final===k).length]);
    $("mix").innerHTML=cats.map(([k,v])=>v?`<i style="--c:var(${CAT[k][1]});flex:${v}" title="${CAT[k][0]}: ${v}"></i>`:"").join("");
    $("legend").innerHTML=cats.map(([k,v])=>`<span class="chip" style="--c:var(${CAT[k][1]})">${CAT[k][0]}<b>${Math.round(v/n*100)}%</b></span>`).join("");
    const cnt={E1:0,E2:0,E3:0,E4:0,E6:0};H.forEach(g=>g.an.forEach(a=>cnt[a[2]]++));S.alerts.forEach(a=>{if(a.st==="E6"&&a.sev!=="info")cnt.E6++});
    const m2=Math.max(1,...Object.values(cnt));
    $("bars").innerHTML=Object.entries(cnt).map(([k,v])=>`<span>${k} ${NAMES[k].toLowerCase()}</span><span class="bar"><i style="width:${v/m2*100}%"></i></span><b>${v}</b>`).join("");
    const ng=Math.max(1,H.length),avg=[0,1,2,3].map(i=>H.reduce((s,g)=>s+g.dur[i],0)/ng),tot=avg.reduce((a,b)=>a+b,0);
    $("seq").innerHTML=avg.map((v,i)=>`<div style="flex:${v}"><b>${dec(v)} s</b><span>E${i+1}</span></div>`).join("");
    $("seqS").textContent=`Proceso promedio por grupo: ${dec(tot)} s, sin contar el traslado en la cinta`},
  health(){
    const p=S.pi;
    const conn=S.e3cut?4:5,L=c=>`<span class="light ${c}"></span>`;
    $("health").innerHTML=[
      ["Estaciones",`${L(conn===5?"ok":"alerta")}${conn} de 5`],["Servidor :8000",`${L("ok")}En línea`],
      ["Base de datos",`${L("ok")}${S.msgs.toLocaleString("es-CL")}`],["Internet",`${L("ok")}No requerido`],
      ["Temperatura",`${L(p.temp>70?"alerta":"ok")}${p.temp.toFixed(0)} °C`],["CPU",`${p.cpu.toFixed(0)} %`],
      ["Memoria",`${dec(p.ram)}/8 GB`],["Disco","14 %"]
    ].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join("");
    const up=Date.now()-S.shiftStart;$("uptime").textContent=`Encendida hace ${Math.floor(up/3600e3)} h ${Math.floor(up%3600e3/60e3)} min`},
  top(){
    $("clock").textContent=hhmmss(Date.now());$("turno").textContent=hhmm(S.shiftStart);
    const bs=$("beltState");bs.classList.toggle("stop",!S.running);bs.querySelector("span").textContent=S.running?"Cinta en marcha":"Cinta detenida";
    const bc=$("beacon");bc.classList.toggle("on",S.e6==="falla_mecanica");bc.querySelector("span").textContent=S.e6==="falla_mecanica"?"Baliza y sirena activas":"Baliza apagada";
    const was=$("stopbar").hidden;$("stopbar").hidden=S.running;if(was!==S.running){requestAnimationFrame(marks)}},
  all(){render.cards();render.gnow();render.hist();render.alerts();render.kpis();render.top()}
};

/* ---------- controles de simulación ---------- */
function failBelt(){if(!S.running)return;const ph=S.ph;const at=ph.t==="proc"?"E"+(ph.k+1):ph.t==="move"&&ph.to!=="exit"?"E"+(ph.to+1):"E4";
  detener();sim.e6send("falla_mecanica",true);S.running=false;
  sim.addAlert("falla","E6",`Falla mecánica en el tramo de ${at}. Cinta detenida`,S.g&&S.g.id);
  $("stopmsg").textContent=`E6 detectó una falla mecánica en el tramo de ${at}. Revise la cinta y luego reanude.`;
  $("bFail").textContent="Reanudar cinta";render.all();$("resumeBtn").focus()}
function resume(){if(S.running)return;sim.e6send("normal",false);S.running=true;
  sim.addAlert("info","E6","Cinta reanudada");$("bFail").textContent="Simular falla de cinta";render.all();programar()}
$("bFail").onclick=()=>S.running?failBelt():resume();
$("resumeBtn").onclick=resume;
$("bE3").onclick=e=>{S.e3cut=!S.e3cut;e.target.setAttribute("aria-pressed",S.e3cut);e.target.textContent=S.e3cut?"Restablecer señal de E3":"Cortar señal de E3";render.all()};
$("bLow").onclick=e=>{S.lowconf=!S.lowconf;e.target.setAttribute("aria-pressed",S.lowconf);e.target.textContent=S.lowconf?"Normalizar confianza de E2":"Bajar confianza de E2"};

/* ---------- arranque ---------- */
setInterval(()=>{if(S.running&&!S.moving&&Date.now()-S.last.E6.t>20e3)sim.e6send("normal",false)},1000);
setInterval(()=>{render.cards();render.gnow();render.top();sim.pasoPi();render.health()},1000);
setInterval(()=>render.kpis(),5000);
addEventListener("resize",marks);
addEventListener("orientacion",()=>{render.hist();requestAnimationFrame(marks)});
/* Si cambia el tamaño de la fila de la cinta o de una tarjeta por otra causa, se vuelve a medir. */
if(window.ResizeObserver){const ro=new ResizeObserver(()=>marks());ro.observe(beltrow);for(let k=1;k<=4;k++)ro.observe($("c-E"+k))}
sim.pasoPi();render.all();render.health();marks();startGroup();
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(marks);
try{navigator.wakeLock&&navigator.wakeLock.request("screen").catch(()=>{})}catch(e){}
})();
