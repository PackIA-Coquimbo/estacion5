/* Pantalla de supervisión de la Estación 5: dibuja las tarjetas de estación, la cinta, el historial,
 * las alertas y los indicadores a partir del estado S.
 *
 * La cinta lleva una mandarina a la vez (contratos v3): cada tarjeta muestra la lectura de la última
 * mandarina que pasó por esa estación y el historial tiene una fila por mandarina.
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
const TXT={aceptada:"Aceptada",repetir:"Repetir captura",revision:"En revisión",alta:"Alta",media:"Media",baja:"Baja",defectos_visibles:"Defectos visibles",grande:"Grande",mediano:"Mediano",pequeno:"Pequeño",normal:"Normal",falla_mecanica:"Falla mecánica"};
const t=k=>TXT[k]||k;
const DEF={mancha_leve:"mancha leve",color_irregular:"color irregular",golpe:"golpe",podredumbre:"podredumbre",piel_danada:"piel dañada"};
const defs=l=>l.map(x=>DEF[x]||x.replace(/_/g," ")).join(", ");
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
const dec=(v,n=1)=>v.toFixed(n).replace(".",",");
const hhmmss=d=>new Date(d).toLocaleTimeString("es-CL",{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
const hhmm=d=>new Date(d).toLocaleTimeString("es-CL",{hour:"2-digit",minute:"2-digit",hour12:false});
const ago=ms=>{const s=Math.max(0,Math.round(ms/1000));return s<60?`hace ${s} s`:`hace ${Math.floor(s/60)} min`};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const num=n=>n.toLocaleString("es-CL");

const S={running:true,seq:0,hist:[],alerts:[],last:{},e3cut:false,lowconf:false,e6:"normal",msgs:0,shiftStart:Date.now()-58*60e3,freshId:null,conf:[],pi:{temp:51,cpu:17,ram:1.9},
  m:null,ph:null,phT:0,lastReg:null};

const sim=E5Sim.crear(S,{clamp,dec,defs,t});
sim.seed();

/* ---------- recorrido de la mandarina por la cinta ----------
   Optimizado para la Raspberry Pi:
   - La animación (requestAnimationFrame) corre solo mientras la mandarina se mueve. Cuando está detenida
     en una estación, saliendo a registro o con la cinta parada, basta un temporizador hasta el fin de la fase.
   - Las posiciones de las estaciones se miden una vez (al cargar, al cambiar el tamaño o la orientación),
     no en cada cuadro.
   - El color de la mandarina se actualiza solo cuando llega un resultado, no en cada cuadro.
   - La textura de la cinta se desplaza con transform, que la GPU mueve sin repintar.
   La mandarina entra desde fuera de la cinta por la izquierda y, tras E4, se desvanece al llegar al final:
   la fila de la cinta recorta lo que queda fuera, así nunca invade otros paneles. */
const beltrow=$("beltrow"),tex=$("tex");
let fgEl=null,fgW=0,beltShift=0,pos=null,opacidad=1;
let raf=0,timer=0,t0=0,base=0;   // t0 y base: momento y avance (s) con que empezó a correr la fase actual

function medir(){
  const br=beltrow.getBoundingClientRect();
  pos={ancho:br.width};
  for(let k=0;k<4;k++){const c=$("c-E"+(k+1)).getBoundingClientRect();pos[k]=c.left+c.width/2-br.left}
  fgW=fgEl?fgEl.offsetWidth:0}
/* Centro de la mandarina en cada punto del recorrido. Entrada y salida quedan justo fuera de la cinta. */
const lugar=to=>to==="start"?-fgW/2-8:to==="exit"?pos.ancho+fgW/2+8:pos[to];
const ease=x=>x<.5?2*x*x:1-Math.pow(-2*x+2,2)/2;
function dibujar(){
  const m=S.m,p=S.ph;if(!m||!p||!fgEl||!pos)return;
  let x,op=1;
  if(p.t==="move"){
    const a=lugar(m.from),b=lugar(p.to),avance=clamp(S.phT/p.d,0,1);x=a+(b-a)*ease(avance);
    if(p.to==="exit"){
      // Se desvanece desde que deja E4 hasta que su borde derecho toca el final de la cinta
      const borde=pos.ancho-fgW/2;op=borde>a?1-clamp((x-a)/(borde-a),0,1):1-avance}}
  else if(p.t==="gap")x=lugar("start");
  else if(p.t==="reg"){x=lugar("exit");op=0}
  else x=lugar(m.from);
  fgEl.style.transform=`translateX(${(x-fgW/2).toFixed(1)}px)`;
  if(op!==opacidad){opacidad=op;fgEl.style.opacity=op.toFixed(3)}}
function colorFruta(){
  if(!fgEl)return;const a=S.m.an;
  fgEl.querySelector(".fs i").className=a.some(z=>z[0]==="falla")?"bad":a.length?"warn":""}
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

function startFruit(){
  const m=sim.newFruit(Date.now());S.m=m;m.P=sim.plan(m);m.pi=0;S.phT=0;m.from="start";
  if(fgEl)fgEl.remove();
  fgEl=document.createElement("div");fgEl.className="fg";fgEl.innerHTML=`<span class="id">${m.id}</span><span class="fs"><i></i></span>`;
  beltrow.appendChild(fgEl);fgW=fgEl.offsetWidth;opacidad=1;colorFruta();enterPhase();render.all()}
function enterPhase(){
  const m=S.m,p=m.P[m.pi];S.ph=p;S.phT=0;
  if(p.t==="move"){S.moving=true;sim.e6send("normal",false)}else S.moving=false;
  programar()}
function endPhase(){
  cancelar();
  const m=S.m,p=m.P[m.pi],now=Date.now();
  if(p.t==="move")m.from=p.to;
  if(p.t==="proc"){sim.emit(m,p.k,now,true);m.done=p.k+1;colorFruta()}
  if(p.t==="reg"){sim.finish(m,now);S.freshId=m.id;S.lastReg={m,t:now};S.msgs++}
  m.pi++;
  if(m.pi>=m.P.length){startFruit();return}
  enterPhase();render.all()}

/* ---------- render ---------- */
const EST={ok:["ok","Aprobada"],anomalia:["alerta","Con anomalía"],rechazo:["falla","Rechazada"],proceso:["","En proceso"]};
const catChip=k=>k?`<span class="chip" style="--c:var(${CAT[k][1]})">${CAT[k][0]}</span>`:`<span style="color:var(--faint)">—</span>`;
/* Clase de aviso de un valor según las anomalías que dejó la estación en la mandarina. */
const marca=(m,st)=>{const a=m.an.filter(z=>z[2]===st);return a.some(z=>z[0]==="falla")?"x":a.length?"w":""};

const render={
  cards(){
    const now=Date.now(),ph=S.ph||{},m=S.m;
    const set=(st,state,pill,body,foot,light)=>{const c=$("c-"+st);c.dataset.s=state;c.querySelector(".pill").textContent=pill;if(body!=null)c.querySelector(".bd").innerHTML=body;c.querySelector(".a").textContent=foot;c.querySelector(".ft .light").className="light "+(light||"")};
    ["E1","E2","E3","E4"].forEach((st,k)=>{
      const L=S.last[st],lm=L&&L.m;let state="espera",pill="En espera";
      if(!S.running){state="detenida";pill="Detenida"}
      else if(ph.t==="proc"&&ph.k===k){state="activo";pill="Procesando "+m.id}
      if(st==="E3"&&S.e3cut){state="sinsenal";pill="Sin señal"}
      let body="";
      if(lm){
        const d=lm.d[st],w=marca(lm,st);
        if(!d)body=`<div class="kv"><span>Lectura</span><b class="w">Sin datos</b></div>`;
        else if(st==="E1")body=`<div class="kv"><span>Imagen</span><b class="${d.validez_imagen?"":"x"}">${d.validez_imagen?"Válida":"No válida"}</b><span>Captura</span><b class="${d.estado_captura==="aceptada"?"":"w"}">${t(d.estado_captura)}</b><span>Posición</span><b class="${d.posicion_correcta?"":"w"}">${d.posicion_correcta?"Correcta":"Incorrecta"}</b></div>`;
        else if(st==="E2")body=`<div class="kv"><span>Calidad</span><b class="${/defectos|revision/.test(d.calidad_visual)?"w":""}">${t(d.calidad_visual)}</b><span>Confianza</span><b class="${d.confianza_visual<.7?"w":""}"><span class="bar" style="--v:${d.confianza_visual*100}%"></span>${dec(d.confianza_visual,2)}</b><span>Defectos</span><b class="${d.defectos_detectados.length?w:""}">${d.defectos_detectados.length?esc(defs(d.defectos_detectados)):"Ninguno"}</b></div>`;
        else if(st==="E3")body=`<div class="kv"><span>Diámetro</span><b class="${w}">${d.diametro_mm} mm</b><span>Tamaño</span><b>${t(d.tamano)}</b></div>`;
        else body=`<div class="kv"><span>Categoría</span><b style="color:var(${CAT[d.categoria_final][1]})">${CAT[d.categoria_final][0]}</b><span>Probabilidad</span><b>${dec(d.probabilidad,2)}</b><span>Revisión manual</span><b class="${d.requiere_revision_manual?"w":""}">${d.requiere_revision_manual?"Sí":"No"}</b></div>`;
      }
      let foot=lm?`Último: ${lm.id}, ${ago(now-L.t)}`:"Sin datos";
      if(st==="E3"&&S.e3cut)foot="No llegan datos de E3";
      const light=state==="sinsenal"?"falla":L&&L.flag?(L.flag==="falla"&&st!=="E4"?"falla":"alerta"):"ok";
      set(st,state,pill,body,foot,light)});
    // E5
    const reg=ph.t==="reg",R=S.lastReg;
    set("E5",reg?"activo":"espera",reg?"Registrando "+m.id:"Escuchando",
      `<div class="kv"><span>Mensajes del turno</span><b>${num(S.msgs)}</b><span>Mandarinas registradas</span><b>${num(S.hist.length)}</b><span>Base de datos</span><b>En línea</b></div>`,
      R?`Último registro: ${R.m.id}, ${ago(now-R.t)}`:"—","ok");
    // E6
    let st6="espera",pill6="Detenida en estación",mv="—";
    if(S.e6==="falla_mecanica"){st6="falla";pill6="Falla mecánica";mv="Detenida por falla"}
    else if(ph.t==="move"){st6="activo";pill6="En movimiento";mv=ph.to==="exit"?"Llevando a la salida":"Avanzando a E"+(ph.to+1)}
    else if(ph.t==="proc"){mv="Detenida en E"+(ph.k+1);pill6=mv}
    else if(ph.t==="reg"||ph.t==="gap"){pill6="En espera";mv="Esperando la próxima mandarina"}
    set("E6",st6,pill6,`<div class="kv"><span>Estado</span><b class="${S.e6==="normal"?"":"x"}">${t(S.e6)}</b><span>Movimiento</span><b>${mv}</b><span>Falla mecánica</span><b class="${S.e6==="normal"?"":"x"}">${S.e6==="normal"?"No":"Sí"}</b></div>`,
      "Última señal "+ago(now-S.last.E6.t),S.e6==="normal"?"ok":"falla");
  },
  gnow(){const m=S.m,ph=S.ph;if(!m)return;
    $("gid").innerHTML=`<span>M-</span>${m.id.slice(-4)}`;
    let w;
    if(!S.running)w="Detenida, cinta con falla";
    else if(ph.t==="gap")w="Entrando a la línea";
    else if(ph.t==="move")w=ph.to==="exit"?"Saliendo de la línea":`Avanzando a E${ph.to+1}`;
    else if(ph.t==="proc")w=`En E${ph.k+1}, ${LONG["E"+(ph.k+1)]}`;
    else w="Registrando en E5";
    $("gwhere").textContent=w;
    const fin=m.done<4?"proceso":m.d.E4&&m.d.E4.categoria_final==="rechazo"?"rechazo":m.an.length?"anomalia":"ok";
    const secs=Math.round((Date.now()-m.realT0)/1000);
    $("gfacts").innerHTML=`<span>Entró <b>${hhmmss(m.realT0)}</b></span><span><b>${secs} s</b> en línea</span>${m.d.E3?`<span><b>${m.d.E3.diametro_mm} mm</b></span>`:""}<span class="verdict ${fin==="proceso"?"":fin}">${EST[fin][1]}</span>`},
  hist(){
    $("hist").innerHTML=S.hist.slice(0,document.documentElement.classList.contains("vertical")?11:12).map(m=>{const e=EST[m.estado],d=m.d;
      return `<tr class="${m.id===S.freshId?"fresh":""}"><td class="id">${m.id}</td><td>${hhmmss(m.out)}</td><td class="r">${d.E3?d.E3.diametro_mm+" mm":"—"}</td><td>${catChip(d.E4&&d.E4.categoria_final)}</td><td><span class="est"><span class="light ${e[0]}"></span>${e[1]}</span></td></tr>`}).join("");
    $("histCount").textContent=`${num(S.hist.length)} mandarinas en el turno`},
  alerts(){
    $("alerts").innerHTML=S.alerts.slice(0,8).map(a=>`<li class="${a.sev}"><span class="when">${hhmm(a.t)}</span><span class="msg">${esc(a.msg.charAt(0).toUpperCase()+a.msg.slice(1))}</span><span class="who">${a.st} (${NAMES[a.st].toLowerCase()})${a.ref?", "+a.ref:""}</span></li>`).join("");
    const h=Date.now()-3600e3;$("alCount").textContent=S.alerts.filter(a=>a.sev!=="info"&&a.t>h).length+" en la última hora"},
  kpis(){
    const now=Date.now(),H=S.hist,last=H.filter(m=>m.out>now-3600e3);
    $("kFph").innerHTML=`${num(last.length)}<small>mandarinas</small>`;
    $("kFphS").textContent=last.length>1?`Una cada ${Math.round(3600/last.length)} s en promedio`:"En los últimos 60 min";
    const bk=new Array(12).fill(0);last.forEach(m=>{const i=11-Math.floor((now-m.out)/300e3);if(i>=0&&i<12)bk[i]++});
    const mx=Math.max(1,...bk),pts=bk.map((v,i)=>[i*240/11,48-v/mx*42]);
    const ln=pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+","+p[1].toFixed(1)).join(""),end=pts[11];
    $("spark").innerHTML=`<line x1="0" x2="240" y1="48" y2="48" stroke="var(--rule)" stroke-width="1"/><path d="${ln}L240,52L0,52Z" fill="var(--ok)" fill-opacity=".14"/><path d="${ln}" fill="none" stroke="var(--ok)" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${end[0]-3}" cy="${end[1]}" r="3" fill="var(--ok)"/>`;
    const n=Math.max(1,H.length);
    const rej=H.filter(m=>m.d.E4&&m.d.E4.categoria_final==="rechazo").length,ano=H.filter(m=>m.an.length).length;
    $("kRej").innerHTML=`${dec(rej/n*100)}<small>%</small>`;$("kRejS").textContent=`${rej} de ${num(H.length)} mandarinas del turno`;
    $("kAno").textContent=`${Math.round(ano/n*100)} % de las mandarinas con alguna anomalía`;
    const cats=Object.keys(CAT).map(k=>[k,H.filter(m=>m.d.E4&&m.d.E4.categoria_final===k).length]);
    $("mix").innerHTML=cats.map(([k,v])=>v?`<i style="--c:var(${CAT[k][1]});flex:${v}" title="${CAT[k][0]}: ${v}"></i>`:"").join("");
    $("legend").innerHTML=cats.map(([k,v])=>`<span class="chip" style="--c:var(${CAT[k][1]})">${CAT[k][0]}<b>${Math.round(v/n*100)}%</b></span>`).join("");
    const cnt={E1:0,E2:0,E3:0,E4:0,E6:0};H.forEach(m=>m.an.forEach(a=>cnt[a[2]]++));S.alerts.forEach(a=>{if(a.st==="E6"&&a.sev!=="info")cnt.E6++});
    const m2=Math.max(1,...Object.values(cnt));
    $("bars").innerHTML=Object.entries(cnt).map(([k,v])=>`<span>${k} ${NAMES[k].toLowerCase()}</span><span class="bar"><i style="width:${v/m2*100}%"></i></span><b>${v}</b>`).join("");
    const avg=[0,1,2,3].map(i=>H.reduce((s,m)=>s+m.dur[i],0)/n),tot=avg.reduce((a,b)=>a+b,0);
    $("seq").innerHTML=avg.map((v,i)=>`<div style="flex:${v}"><b>${dec(v)} s</b><span>E${i+1}</span></div>`).join("");
    $("seqS").textContent=`Proceso promedio por mandarina: ${dec(tot)} s, sin contar el traslado en la cinta`},
  health(){
    const p=S.pi;
    const conn=S.e3cut?4:5,L=c=>`<span class="light ${c}"></span>`;
    $("health").innerHTML=[
      ["Estaciones",`${L(conn===5?"ok":"alerta")}${conn} de 5`],["Servidor :8000",`${L("ok")}En línea`],
      ["Base de datos",`${L("ok")}${num(S.msgs)}`],["Internet",`${L("ok")}No requerido`],
      ["Temperatura",`${L(p.temp>70?"alerta":"ok")}${p.temp.toFixed(0)} °C`],["CPU",`${p.cpu.toFixed(0)} %`],
      ["Memoria",`${dec(p.ram)}/4 GB`],["Disco","14 %"]
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
  sim.addAlert("falla","E6",`Falla mecánica en el tramo de ${at}. Cinta detenida`,S.m&&S.m.id);
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
sim.pasoPi();render.all();render.health();marks();startFruit();
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(marks);
try{navigator.wakeLock&&navigator.wakeLock.request("screen").catch(()=>{})}catch(e){}
})();
