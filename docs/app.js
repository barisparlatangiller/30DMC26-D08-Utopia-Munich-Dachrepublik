/* Die Dachrepublik · Munich centre · #30DayMapChallenge 2026 Day 8 (Utopia) */
const COL = { play: "#f0a43a", sport: "#e2603f", garden: "#8cbf3f", park: "#2f9e8a", cinema: "#8a6bc1",
  social: "#e783a7", quiet: "#4f8bd0", pv: "#27405f" };
const FREE = "#d8d1c3", BASE = "#ecebe8", PITCHED = "#8fa5bd";
const RAMP = ["#f4f1ea", "#fbe3c4", "#f8c58f", "#f1a160", "#e3793d", "#c9552a", "#a33b1d", "#7a2812"];
const $ = s => document.querySelector(s);
const fmt = n => Math.round(n).toLocaleString("en-GB");

const S = { sim: null, F: [], P: {}, share: {}, def: null, res: null, view: "roofs", pitched: true, assign: null, timer: null };

// ---------- data
async function load() {
  const [sim, buf, stats] = await Promise.all([
    fetch("data/sim.json?v=1").then(r => r.json()),
    fetch("data/pairs.bin?v=1").then(r => r.arrayBuffer()),
    fetch("data/stats.json?v=1").then(r => r.json())]);
  S.sim = sim; S.stats = stats;
  const n = buf.byteLength / 5, dv = new DataView(buf);
  S.pc = new Uint16Array(n); S.pd = new Uint8Array(n);
  for (let i = 0; i < n; i++) { S.pc[i] = dv.getUint16(i * 5 + 2, true); S.pd[i] = dv.getUint8(i * 5 + 4); }
  S.F = sim.functions.map(f => ({ ...f }));
  S.P = { ...sim.params };
  S.def = { F: JSON.parse(JSON.stringify(S.F)), P: { ...S.P } };
  for (const f of S.F) S.share[f.id] = f.share;
}

// ---------- the simulator
function insert(h, it) {                                       // h sorted by gain, descending
  let lo = 0, hi = h.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (h[mid][0] >= it[0]) lo = mid + 1; else hi = mid; }
  h.splice(lo, 0, it);
}
function simulate() {
  const sim = S.sim, C = sim.cells, R = sim.roofs, nC = C.pop.length, nR = R.net.length;
  const totNet = R.net.reduce((a, b) => a + b, 0), residents = C.pop.reduce((a, b) => a + b, 0);
  const assign = new Int8Array(nR).fill(-1);                    // function index per candidate roof
  const order = [];                                             // placement order (for the video)
  const covB = {}, covA = {}, out = {};
  const pub = S.F.filter(f => f.id !== "pv");
  // state per public function
  const st = pub.map((f, fi) => {
    const w = f.group === "kids" ? C.kids : C.pop;
    const before = new Uint8Array(nC), after = new Uint8Array(nC);
    for (let c = 0; c < nC; c++) { before[c] = after[c] = C.base[f.id][c] * 10 <= f.target ? 1 : 0; }
    const need = f.per > 0 ? Math.max(0, Math.ceil(Math.ceil(residents / f.per) * (1 - f.have / 100))) : 0;
    const budget = totNet * (S.share[f.id] || 0) / 100;
    const lim = Math.round(f.target / 10);
    // initial upper bounds (gain before any placement)
    const heap = [];
    for (let r = 0; r < nR; r++) {
      if (R.net[r] < f.min_m2) continue;
      let g = 0;
      for (let k = R.start[r]; k < R.start[r + 1]; k++) if (S.pd[k] <= lim && !before[S.pc[k]]) g += w[S.pc[k]];
      if (g > 0) heap.push([g, r]);
    }
    heap.sort((a, b) => b[0] - a[0]);
    return { f, fi: S.F.indexOf(f), w, before, after, need, budget, used: 0, placed: 0, lim, heap, done: !need || !budget, gainPeople: 0 };
  });
  const gainOf = (s, r) => { let g = 0; for (let k = S.sim.roofs.start[r]; k < S.sim.roofs.start[r + 1]; k++) if (S.pd[k] <= s.lim && !s.after[S.pc[k]]) g += s.w[S.pc[k]]; return g; };
  // round-robin lazy greedy: each use in turn takes the roof that gives most people new access
  let active = st.filter(s => !s.done);
  while (active.length) {
    for (const s of active) {
      let pick = -1;
      while (s.heap.length) {
        const [ub, r] = s.heap[0];
        if (assign[r] >= 0 || s.used + R.net[r] > s.budget * 1.0001) { s.heap.shift(); continue; }
        const g = gainOf(s, r);
        if (g <= 0) { s.heap.shift(); continue; }
        if (s.heap.length < 2 || g >= s.heap[1][0]) { pick = r; s.heap.shift(); break; }
        s.heap.shift(); insert(s.heap, [g, r]);                   // re-insert with its true gain
      }
      if (pick < 0) { s.done = true; continue; }
      assign[pick] = s.fi; s.used += R.net[pick]; s.placed++; order.push(pick);
      for (let k = R.start[pick]; k < R.start[pick + 1]; k++) if (S.pd[k] <= s.lim) s.after[S.pc[k]] = 1;
      if (s.placed >= s.need) s.done = true;
    }
    active = active.filter(s => !s.done);
  }
  // PV: pitched faces first (if on), then free flat roofs, largest first, until the kWh target or the PV share is reached
  const P = S.P, fpv = S.F.find(f => f.id === "pv"), pvi = S.F.indexOf(fpv);
  const kwh = m2 => m2 * P.pv_fill * P.kwp_m2 * P.kwh_kwp;
  const target = residents * P.pv_target_kwh;
  let pvKwh = S.pitched ? kwh(sim.totals.pitched_pv_m2) : 0, pvFlat = 0, pvRoofs = 0;
  const pvBudget = totNet * (S.share.pv || 0) / 100;
  const pvOrder = [...Array(nR).keys()].filter(r => assign[r] < 0 && R.net[r] >= fpv.min_m2).sort((a, b) => R.net[b] - R.net[a]);
  for (const r of pvOrder) {
    if (pvKwh >= target || pvFlat + R.net[r] > pvBudget) continue;
    assign[r] = pvi; pvFlat += R.net[r]; pvRoofs++; pvKwh += kwh(R.net[r]); order.push(r);
  }
  // results, people counted once
  let gained = 0, gapB = 0, gapA = 0;
  const missB = new Uint8Array(nC), missA = new Uint8Array(nC);
  for (let c = 0; c < nC; c++) {
    let g = false;
    for (const s of st) { if (!s.before[c]) missB[c]++; if (!s.after[c]) missA[c]++; if (s.after[c] && !s.before[c]) g = true; }
    if (g) gained += C.pop[c];
  }
  const rows = st.map(s => {
    let pb = 0, pa = 0, tot = 0;
    for (let c = 0; c < nC; c++) { tot += s.w[c]; if (s.before[c]) pb += s.w[c]; if (s.after[c]) pa += s.w[c]; }
    return { id: s.f.id, name: s.f.name, need: s.need, placed: s.placed, m2: s.used, budget: s.budget, before: pb / tot, after: pa / tot };
  });
  const garden = rows.find(r => r.id === "garden");
  const harvest = (garden ? garden.m2 : 0) * P.grow_share * P.yield_kg_m2;
  const usedRoofs = [...assign].filter(a => a >= 0).length;
  const usedM2 = rows.reduce((a, r) => a + r.m2, 0) + pvFlat;
  S.assign = assign; S.missB = missB; S.missA = missA; S.order = order;
  S.res = { rows, gained, residents, harvest, people_fed: harvest / P.veg_need_kg, pvKwh, target, pvFlat, pvRoofs,
    usedRoofs, freeRoofs: nR - usedRoofs, usedM2, freeM2: totNet - usedM2, totNet, nR };
  return S.res;
}

// ---------- panel
function sliders() {
  $("#sliders").innerHTML = S.F.map(f => `<li style="--c:${COL[f.id]}"><span class="sw"></span><span class="nm">${f.name}</span>
    <span class="pc" id="pc-${f.id}"></span><input type="range" min="0" max="60" step="1" data-id="${f.id}" aria-label="${f.name} share">
    <span class="info" id="in-${f.id}"></span></li>`).join("");
  $("#sliders").querySelectorAll("input").forEach(el => el.oninput = e => setShare(e.target.dataset.id, +e.target.value));
  syncSliders();
}
function setShare(id, v) {
  // keep the total at 100 %: the other uses give or take in proportion to their current share
  const others = S.F.filter(f => f.id !== id), rest = others.reduce((a, f) => a + S.share[f.id], 0);
  v = Math.max(0, Math.min(100, v)); const left = 100 - v;
  for (const f of others) S.share[f.id] = rest > 0 ? S.share[f.id] * left / rest : left / others.length;
  S.share[id] = v;
  syncSliders(); schedule();
}
function syncSliders() {
  for (const f of S.F) {
    const el = document.querySelector(`#sliders input[data-id="${f.id}"]`); if (el) el.value = S.share[f.id];
    $(`#pc-${f.id}`).textContent = `${S.share[f.id].toFixed(0)} %`;
  }
  const sum = Object.values(S.share).reduce((a, b) => a + b, 0);
  $("#sumNote").textContent = `total ${sum.toFixed(0)} %`;
}
function schedule() { clearTimeout(S.timer); S.timer = setTimeout(run, 60); }

function run() {
  const r = simulate();
  const pct = x => `${Math.round(x * 100)} %`;
  $("#kpis").innerHTML = `
    <div class="kpi wide"><b>${fmt(r.gained)}</b><span>residents gain walking access to at least one new public roof use<br>of ${fmt(r.residents)} living in the centre (each person counted once)</span></div>
    <div class="kpi"><b>${fmt(r.usedRoofs)}</b><span>roofs used, ${fmt(r.usedM2 / 1000)}k m²</span></div>
    <div class="kpi"><b>${fmt(r.freeRoofs)}</b><span>flat roofs stay free: need already met (${pct(r.freeM2 / r.totNet)} of the area)</span></div>
    <div class="kpi"><b>${fmt(r.harvest / 1000)} t</b><span>vegetables & fruit a season, enough for ${fmt(r.people_fed)} people</span></div>
    <div class="kpi"><b>${fmt(r.pvKwh / 1e6)} GWh</b><span>solar a year, ${pct(Math.min(1, r.pvKwh / r.target))} of the ${S.P.pv_target_kwh} kWh/resident target</span></div>`;
  for (const row of r.rows) $(`#in-${row.id}`).textContent = `${row.placed} of ${row.need} sites needed · ${fmt(row.m2)} m² of ${fmt(row.budget)} m²`;
  $("#in-pv").textContent = `${r.pvRoofs} flat roofs, ${fmt(r.pvFlat)} m²${S.pitched ? " + pitched roofs" : ""}`;
  $("#matrix").innerHTML = `<tr><th>Use</th><th>sites / needed</th><th>within walk: today</th><th>after</th></tr>` + r.rows.map(x =>
    `<tr style="--c:${COL[x.id]}"><td><i></i>${x.name}</td><td>${x.placed} / ${x.need}</td><td>${pct(x.before)}</td>
     <td>${pct(x.after)} <span class="bar"><b style="width:${(x.after * 100).toFixed(0)}%"></b></span></td></tr>`).join("");
  paint();
}

function assumptions() {
  $("#fnParams").innerHTML = `<tr><th></th><th>min m²</th><th>walk m</th><th>people / site</th><th>covered %</th></tr>` +
    S.F.filter(f => f.id !== "pv").map(f => `<tr><td>${f.name}</td>${["min_m2", "target", "per", "have"].map(k =>
      `<td><input type="number" data-f="${f.id}" data-k="${k}" value="${f[k]}"></td>`).join("")}</tr>`).join("");
  const L = { usable_net: "Usable share of a flat roof", grow_share: "Planted share of a garden roof", yield_kg_m2: "Yield, kg/m² a season",
    veg_need_kg: "Vegetables & fruit, kg/person/year", pv_fill: "Panel cover of a PV roof", kwp_m2: "kWp per m² of panel",
    kwh_kwp: "kWh per kWp a year", pv_target_kwh: "PV target, kWh/resident/year" };
  $("#params").innerHTML = Object.keys(L).map(k => `<label for="p-${k}">${L[k]}</label><input id="p-${k}" type="number" step="any" data-p="${k}" value="${S.P[k]}">`).join("");
  document.querySelectorAll("#fnParams input").forEach(el => el.onchange = e => { S.F.find(f => f.id === e.target.dataset.f)[e.target.dataset.k] = +e.target.value; schedule(); });
  document.querySelectorAll("#params input").forEach(el => el.onchange = e => { S.P[e.target.dataset.p] = +e.target.value; schedule(); });
  $("#params").insertAdjacentHTML("beforeend", `<span class="fine" style="grid-column:1/-1">The usable share was applied when the roofs were prepared (75 %); changing it here does not re-cut the roofs.</span>`);
}

// ---------- map
function legend() {
  const el = $("#legend");
  if (S.view === "roofs") {
    el.innerHTML = S.F.map(f => `<span class="it"><i style="background:${COL[f.id]}"></i>${f.name}</span>`).join("") +
      `<span class="it"><i style="background:${FREE}"></i>flat roof, stays free</span>` +
      (S.pitched ? `<span class="it"><i style="background:${PITCHED}"></i>PV on pitched roof</span>` : "");
  } else {
    el.innerHTML = `<b>${S.view === "need" ? "Today" : "After the Dachrepublik"}</b>: how many of the 7 public uses are <i>not</i> within walking distance
      <div class="ramp">${RAMP.map(c => `<b style="background:${c}"></b>`).join("")}</div><div class="ends"><span>0</span><span>all 7 missing</span></div>`;
  }
}
function paint() {
  const m = S.map; if (!m || !m.getLayer("b3")) return;
  const R = S.sim.roofs;
  for (let r = 0; r < R.bid.length; r++) m.setFeatureState({ source: "b", sourceLayer: "b", id: R.bid[r] }, { f: S.assign[r] });
  for (let c = 0; c < S.missB.length; c++) m.setFeatureState({ source: "cells", id: c }, { b: S.missB[c], a: S.missA[c] });
  m.setPaintProperty("b3", "fill-extrusion-color", roofColor());
  legend();
}
// show only the first k placements (used by the video renderer)
function reveal(k) {
  const m = S.map, R = S.sim.roofs, on = new Set(S.order.slice(0, k));
  for (let r = 0; r < R.bid.length; r++) m.setFeatureState({ source: "b", sourceLayer: "b", id: R.bid[r] }, { f: on.has(r) ? S.assign[r] : -1 });
}
function roofColor() {
  const ids = S.F.map(f => f.id);
  return ["case",
    [">=", ["coalesce", ["feature-state", "f"], -1], 0], ["match", ["feature-state", "f"], ...ids.flatMap((id, i) => [i, COL[id]]), FREE],
    ["all", S.pitched, [">", ["get", "p"], 20]], PITCHED,
    [">=", ["get", "c"], 0], FREE, BASE];
}
function setView(v) {
  S.view = v;
  document.querySelectorAll(".views button").forEach(b => b.classList.toggle("on", b.dataset.v === v));
  const m = S.map;
  m.setLayoutProperty("cells", "visibility", v === "roofs" ? "none" : "visible");
  m.setPaintProperty("cells", "fill-color", ["interpolate", ["linear"], ["coalesce", ["feature-state", v === "need" ? "b" : "a"], 0], ...RAMP.flatMap((c, i) => [i, c])]);
  m.setPaintProperty("b3", "fill-extrusion-opacity", v === "roofs" ? 0.96 : 0.55);
  legend();
}

async function init() {
  await load();
  const protocol = new pmtiles.Protocol(); maplibregl.addProtocol("pmtiles", protocol.tile);
  const map = (S.map = new maplibregl.Map({ container: "map", style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    center: [11.5735, 48.1420], zoom: 14.15, pitch: 58, bearing: -18, antialias: true, attributionControl: false, maxPitch: 75 }));
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "LoD2 © Bayerische Vermessungsverwaltung (CC BY 4.0) · Zensus 2022 © Destatis" }), "bottom-right");
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  const setup = () => {
    if (map.getLayer("b3")) return true;
    try {
      const sym = map.getStyle().layers.find(l => l.type === "symbol")?.id;
      map.addSource("bd", { type: "geojson", data: "data/boundary.geojson" });
      map.addLayer({ id: "bd", type: "line", source: "bd", paint: { "line-color": "#1f2328", "line-width": 1.6, "line-dasharray": [3, 2], "line-opacity": .55 } }, sym);
      map.addSource("cells", { type: "geojson", data: "data/cells.geojson?v=1", promoteId: "i" });
      map.addLayer({ id: "cells", type: "fill", source: "cells", layout: { visibility: "none" }, paint: { "fill-color": RAMP[0], "fill-opacity": 0.75 } }, sym);
      map.addSource("b", { type: "vector", url: `pmtiles://${location.href.replace(/[^/]*$/, "")}data/buildings.pmtiles?v=${S.stats.build}`, promoteId: "bid" });
      map.addLayer({ id: "b3", type: "fill-extrusion", source: "b", "source-layer": "b", minzoom: 12, paint: {
        "fill-extrusion-color": roofColor(), "fill-extrusion-height": ["get", "h"], "fill-extrusion-base": 0,
        "fill-extrusion-opacity": 0.96, "fill-extrusion-vertical-gradient": true } });
      for (const l of map.getStyle().layers) if (/building/.test(l.id) && l.id !== "b3") map.setLayoutProperty(l.id, "visibility", "none");
      map.on("sourcedata", e => { if (e.sourceId === "b" && e.isSourceLoaded) paint(); });
      map.on("click", "b3", e => {
        const p = e.features[0].properties, st = e.features[0].state || {};
        const f = st.f >= 0 ? S.F[st.f] : null;
        new maplibregl.Popup({ offset: 6 }).setLngLat(e.lngLat).setHTML(`<b>${f ? f.name : p.c >= 0 ? "Flat roof, stays free" : "Building"}</b><br>
          ${fmt(p.fl)} m² flat roof · ${p.h} m high${p.p > 20 ? ` · ${fmt(p.p)} m² pitched roof facing E/S/W` : ""}`).addTo(map);
      });
      return true;
    } catch (e) { console.warn(e.message); return false; }
  };
  map.on("load", () => { setup(); run(); });
  const poll = setInterval(() => { if (map.style && map.style._loaded && setup()) { clearInterval(poll); run(); } }, 300);
  sliders(); assumptions(); legend();
  document.querySelectorAll(".views button").forEach(b => b.onclick = () => setView(b.dataset.v));
  $("#pitched").onchange = e => { S.pitched = e.target.checked; schedule(); };
  $("#reset").onclick = () => { S.F = JSON.parse(JSON.stringify(S.def.F)); S.P = { ...S.def.P }; for (const f of S.F) S.share[f.id] = f.share; syncSliders(); assumptions(); schedule(); };
  run();
}
init();
