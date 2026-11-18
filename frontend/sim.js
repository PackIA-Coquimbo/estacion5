/* Simulación de datos del dashboard de la Estación 5.
 *
 * Genera grupos de frutas, lecturas de E1 a E4 y E6, y aplica las reglas de anomalías.
 * En el sistema real esos datos llegan de las estaciones y las reglas las aplica el backend;
 * mientras la pantalla no lea la API, los datos salen de aquí. Después quedará como plan B de la demo (?sim=1).
 *
 * app.js lo usa así: const sim = E5Sim.crear(S, util), donde S es el estado de la pantalla
 * y util trae las funciones de formato que necesitan los mensajes de alerta.
 * Supuesto de los contratos v2: E1 informa por grupo; E2, E3 y E4 informan por fruta.
 */
(function () {
"use strict";

const DUR = [3.4, 5.2, 4.5, 2.8];            // segundos promedio de proceso en E1..E4
const MOVE = 1.5, EXIT = 1.8, REG = 1.4, GAP = .8; // traslado entre estaciones, salida, registro y espera (s)

function crear(S, util) {
  const { clamp, dec, defs, t } = util;
  const rnd = Math.random;
  const pick = w => { let s = 0, r = rnd() * w.reduce((a, b) => a + b[1], 0); for (const [v, p] of w) { s += p; if (r < s) return v } return w[0][0] };
  const gauss = (m, s) => m + s * Math.sqrt(-2 * Math.log(rnd() || 1e-9)) * Math.cos(2 * Math.PI * rnd());
  const pad = n => String(n).padStart(4, "0");

  /* ---------- generadores de lecturas ---------- */
  const gen = {
    E1(g) { const v = rnd() > .03; return { validez_imagen: v, estado_captura: v ? pick([["aceptada", 94], ["repetir", 4], ["revision", 2]]) : "repetir", posicion_correcta: rnd() > .04, frutas_detectadas: g.n } },
    E2() {
      const calidad = pick([["alta", 56], ["media", 27], ["baja", 7], ["defectos_visibles", 7], ["revision", 3]]);
      let c = clamp(gauss(.88, .06), .5, .99); if (S.lowconf || rnd() < .05) c = clamp(gauss(.6, .06), .4, .69);
      const d = calidad === "alta" ? (rnd() < .15 ? ["mancha_leve"] : []) : calidad === "media" ? [pick([["mancha_leve", 3], ["madurez_desigual", 2]])] : calidad === "revision" ? [] : [pick([["golpe", 2], ["antracnosis", 1], ["piel_danada", 2]])];
      return { calidad_visual: calidad, confianza_visual: +c.toFixed(2), defectos_detectados: d }
    },
    E3() { const d = Math.round(clamp(gauss(102, 11), 70, 135)); return { diametro_mm: d, tamano: d >= 112 ? "grande" : d >= 92 ? "mediano" : "pequeno" } },
    E4(f) {
      const e2 = f.d.E2, e3 = f.d.E3; let cat;
      if (!e2 || !e3) cat = "revision_manual";
      else if (e2.calidad_visual === "defectos_visibles") cat = rnd() < .55 ? "rechazo" : "proceso";
      else if (e2.calidad_visual === "revision") cat = "revision_manual";
      else if (e2.calidad_visual === "baja") cat = rnd() < .3 ? "rechazo" : "proceso";
      else if (e2.calidad_visual === "media" || e3.tamano === "pequeno") cat = "mercado_nacional";
      else cat = "exportacion";
      const p = +clamp(gauss(cat === "revision_manual" ? .62 : .87, .06), .45, .99).toFixed(2);
      return { categoria_final: cat, probabilidad: p, requiere_revision_manual: cat === "revision_manual" || p < .7 }
    }
  };

  /* ---------- reglas de anomalías por fruta (en el sistema real las aplica el backend) ---------- */
  function rulesFruit(st, d) {
    const a = [];
    if (st === "E2") { if (d.confianza_visual < .7) a.push(["alerta", `confianza baja (${dec(d.confianza_visual, 2)})`]); if (d.calidad_visual === "defectos_visibles") a.push(["alerta", "defectos visibles: " + defs(d.defectos_detectados)]); if (d.calidad_visual === "revision") a.push(["alerta", "calidad visual en revisión"]) }
    if (st === "E3") { if (d.diametro_mm < 80) a.push(["alerta", `bajo el tamaño mínimo (${d.diametro_mm} mm)`]) }
    if (st === "E4") { if (d.categoria_final === "rechazo") a.push(["falla", "rechazada"]); else if (d.requiere_revision_manual) a.push(["alerta", "requiere revisión manual"]) }
    return a
  }

  function newGroup(realT0) {
    S.seq++; const n = pick([[3, 45], [4, 40], [2, 8], [5, 7]]);
    return { id: "G-" + pad(S.seq), n, realT0, dur: DUR.map(d => +(d + (rnd() - .5) * .4).toFixed(2)), e1: null, uni: null, fr: Array.from({ length: n }, (_, i) => ({ k: "F" + (i + 1), d: {}, an: [] })), an: [], done: 0, estado: "proceso" }
  }
  function addAlert(sev, st, msg, ref, when) { S.alerts.unshift({ sev, st, msg, ref, t: when || Date.now() }); S.alerts.length = Math.min(S.alerts.length, 40) }
  function flag(g, sev, st, msg, live, when, fk) { g.an.push([sev, msg, st, fk || null]); if (live) addAlert(sev, st, (fk ? fk + ": " : "") + msg, g.id, when) }

  /* Genera la lectura de la estación k (0 = E1 … 3 = E4) para el grupo g y aplica las reglas. */
  function emit(g, k, when, live) {
    const st = "E" + (k + 1); let worst = null;
    if (live && st === "E3" && S.e3cut) { flag(g, "alerta", st, "Sin datos de E3 para el grupo", live, when); return }
    if (st === "E1") {
      const d = gen.E1(g); g.e1 = d; S.msgs++;
      if (!d.validez_imagen) { flag(g, "falla", st, "Imagen no válida", live, when); worst = "falla" }
      else if (d.estado_captura !== "aceptada") { flag(g, "alerta", st, "Captura: " + t(d.estado_captura).toLowerCase(), live, when); worst = "alerta" }
      if (!d.posicion_correcta) { flag(g, "alerta", st, "Frutas mal posicionadas", live, when); worst = worst || "alerta" }
      if (live) S.last.E1 = { t: when, g, flag: worst }; return
    }
    for (const f of g.fr) {
      const d = gen[st](f); f.d[st] = d; S.msgs++;
      rulesFruit(st, d).forEach(x => { f.an.push(x); flag(g, x[0], st, x[1], live, when, f.k); worst = worst === "falla" ? "falla" : x[0] })
    }
    if (st === "E3") { const w = g.fr.map(f => f.d.E3.diametro_mm), sp = Math.max(...w) - Math.min(...w); g.uni = sp > 28 ? "irregular" : "uniforme"; if (g.uni === "irregular") { flag(g, "alerta", st, `Tamaños irregulares en el grupo (${sp} mm de diferencia)`, live, when); worst = worst || "alerta" } }
    if (live) S.last[st] = { t: when, g, flag: worst };
    if (st === "E2") {
      g.fr.forEach(f => S.conf.push(f.d.E2.confianza_visual)); while (S.conf.length > 12) S.conf.shift();
      const low = S.conf.filter(c => c < .7).length;
      if (live && low >= 3 && !S.trendOn) { S.trendOn = true; addAlert("alerta", "E2", `Baja confianza frecuente: ${low} de las últimas 12 frutas`, null, when) }
      if (low < 2) S.trendOn = false
    }
  }
  function finish(g, when) {
    const rej = g.fr.some(f => f.d.E4 && f.d.E4.categoria_final === "rechazo");
    g.estado = rej ? "rechazo" : g.an.length ? "anomalia" : "ok"; g.out = when;
    S.hist.unshift(g); if (S.hist.length > 600) S.hist.pop()
  }

  /* ---------- turno precargado: llena el historial desde el inicio del turno hasta ahora ---------- */
  function seed() {
    let tt = S.shiftStart; const end = Date.now() - 25e3;
    while (tt < end) {
      const g = newGroup(tt); let acc = tt;
      for (let k = 0; k < 4; k++) { acc += (g.dur[k] + MOVE) * 1000; emit(g, k, acc, false); g.done = k + 1 }
      finish(g, acc + (EXIT + REG) * 1000); tt += gauss(24, 4) * 1000
    }
    const lg = S.hist[0]; ["E1", "E2", "E3", "E4"].forEach((st, i) => S.last[st] = { t: Date.now() - (25 - i * 4) * 1000, g: lg, flag: null });
    S.lastReg = { g: lg, t: Date.now() - 20e3 };
    S.last.E6 = { t: Date.now() - 3e3 };
    addAlert("info", "E6", "Cinta en marcha. Inicio de turno", null, S.shiftStart);
    S.hist.slice(0, 30).reverse().forEach(g => g.an.slice(0, 1).forEach(a => addAlert(a[0], a[2], (a[3] ? a[3] + ": " : "") + a[1], g.id, g.out)));
  }

  /* Recorrido de un grupo: avanza, se detiene en cada estación, sale y se registra.
     En el sistema real, cada paso lo marca un mensaje: la cinta (E6) avisa que se mueve
     y cada estación avisa cuando entrega su resultado. Aquí se simula ese orden. */
  function plan(g) {
    const P = [{ t: "gap", d: GAP }];
    for (let k = 0; k < 4; k++) { P.push({ t: "move", to: k, d: MOVE }); P.push({ t: "proc", k, d: g.dur[k] }) }
    P.push({ t: "move", to: "exit", d: EXIT }); P.push({ t: "reg", d: REG });
    return P
  }

  function e6send(estado, falla) { S.e6 = estado; S.last.E6 = { t: Date.now(), d: { estado_cinta: estado, falla_mecanica_detectada: falla } }; S.msgs++ }

  /* Métricas simuladas de la Raspberry Pi (en el sistema real vendrán de GET /api/v1/sistema). */
  function pasoPi() { const p = S.pi; p.temp = clamp(p.temp + (rnd() - .5) * .6, 46, 62); p.cpu = clamp(p.cpu + (rnd() - .5) * 4, 8, 40); p.ram = clamp(p.ram + (rnd() - .5) * .05, 1.6, 2.4) }

  return { newGroup, addAlert, emit, finish, seed, plan, e6send, pasoPi };
}

window.E5Sim = { crear };
})();
