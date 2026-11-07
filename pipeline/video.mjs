// ~14 s LinkedIn video (1080×1350): the camera circles Munich's centre while the Dachrepublik fills its roofs,
// one site after another, in the order the simulator places them. Rendered from the live page with Excel defaults.
//   python -m http.server -d docs 8000 &  node pipeline/video.mjs   → media/day8_dachrepublik.mp4, cover.png, thumb_full.jpg
import { chromium } from "playwright";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import http from "node:http";
import path from "node:path";

// a small static server that answers HTTP Range requests (the building tiles are a .pmtiles file read in ranges)
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".geojson": "application/geo+json" };
http.createServer((req, res) => {
  const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let f = path.join("docs", u.endsWith("/") ? u + "index.html" : u);
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  const size = fs.statSync(f).size, type = TYPES[path.extname(f)] || "application/octet-stream";
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || "");
  if (m) {
    const a = +m[1], b = m[2] ? Math.min(+m[2], size - 1) : size - 1;
    res.writeHead(206, { "Content-Type": type, "Content-Length": b - a + 1, "Content-Range": `bytes ${a}-${b}/${size}`, "Accept-Ranges": "bytes" });
    fs.createReadStream(f, { start: a, end: b }).pipe(res);
  } else {
    res.writeHead(200, { "Content-Type": type, "Content-Length": size, "Accept-Ranges": "bytes" });
    fs.createReadStream(f).pipe(res);
  }
}).listen(8000);

const URL = process.env.URL || "http://localhost:8000/";
const OUT = "media", FR = "media/frames", FPS = 15;
fs.mkdirSync(FR, { recursive: true });
for (const f of fs.readdirSync(FR)) fs.unlinkSync(`${FR}/${f}`);
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const ready = p => p.waitForFunction(() => typeof S !== "undefined" && S.res && S.map && S.map.getLayer("b3"), null, { timeout: 120000 });
const idle = p => p.evaluate(() => new Promise(r => { S.map.once("idle", r); S.map.triggerRepaint(); setTimeout(r, 1200); }));

// hub thumbnail: the page as it opens
{
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  p.on("console", m => m.type() === "error" && console.log("console:", m.text()));
  await p.goto(URL, { waitUntil: "networkidle" }); await ready(p);
  console.log("page ready", new Date().toISOString());
  await p.waitForFunction(() => S.map.loaded() && S.map.areTilesLoaded(), null, { timeout: 120000 }).catch(() => {});
  await p.waitForTimeout(3000);
  console.log("buildings rendered:", await p.evaluate(() => S.map.queryRenderedFeatures({ layers: ["b3"] }).length));
  await p.screenshot({ path: `${OUT}/thumb_full.jpg`, type: "jpeg", quality: 88 });
  await p.close();
}

const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
page.on("console", m => m.type() === "error" && console.log("console:", m.text()));
await page.goto(URL, { waitUntil: "networkidle" }); await ready(page);
await page.addStyleTag({ content: `
  .panel, .views, .legend, .maplibregl-ctrl-top-right, .maplibregl-ctrl-bottom-right { display: none !important; }
  #map { inset: 0 !important; }
  .v { position: absolute; z-index: 5; left: 44px; right: 44px; font-family: Inter; color: #1f2328; }
  .v.top { top: 40px; }
  .v .eb { font-size: 19px; letter-spacing: .14em; text-transform: uppercase; color: #8a929c; font-weight: 600; }
  .v h1 { font-size: 76px; font-weight: 800; letter-spacing: -.035em; margin: 8px 0 4px; line-height: .95; }
  .v .s { font-size: 27px; color: #5b6470; line-height: 1.3; max-width: 900px; }
  .v.bot { bottom: 44px; background: rgba(255,255,255,.94); border: 1px solid #e6e3dd; border-radius: 16px; padding: 20px 24px; box-shadow: 0 10px 30px -14px rgba(0,0,0,.3); }
  .v .now { display: flex; justify-content: space-between; align-items: baseline; }
  .v .now b { font-size: 40px; letter-spacing: -.02em; } .v .now span { font-size: 22px; color: #5b6470; }
  .v .lg { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 18px; margin-top: 14px; font-size: 19px; }
  .v .lg i { display: inline-block; width: 15px; height: 15px; border-radius: 4px; margin-right: 8px; vertical-align: -2px; }
  .v .lg .on { font-weight: 700; } .v .lg .off { opacity: .35; }
  .card { position: absolute; z-index: 6; left: 70px; right: 70px; top: 420px; background: rgba(255,255,255,.96); border-radius: 22px; padding: 38px 42px; text-align: center; box-shadow: 0 20px 50px -20px rgba(0,0,0,.35); }
  .card .big { font-size: 92px; font-weight: 800; letter-spacing: -.04em; line-height: 1; }
  .card p { font-size: 27px; line-height: 1.35; color: #3b424a; margin: 12px 0 0; }
  .card .k { display: flex; justify-content: center; gap: 34px; margin-top: 24px; font-size: 21px; color: #5b6470; }
  .card .k b { display: block; font-size: 36px; color: #1f2328; }
  .card .url { margin-top: 24px; font-size: 22px; font-weight: 600; }
  .card .att { margin-top: 8px; font-size: 15px; color: #8a929c; }
` });
const info = await page.evaluate(() => {
  document.body.insertAdjacentHTML("beforeend", `<div class="v top"><div class="eb">#30DayMapChallenge · Day 8 · Utopia · Munich</div>
    <h1>Die Dachrepublik</h1><div class="s">What if the roofs of Munich's city centre belonged to everyone?</div></div>
    <div class="v bot"><div class="now"><b id="vn">0 roofs</b><span id="vu">the roofs of the centre</span></div>
    <div class="lg">${S.F.map(f => `<span id="lg-${f.id}" class="off"><i style="background:${COL[f.id]}"></i>${f.name}</span>`).join("")}</div></div>`);
  S.map.resize(); S.map.jumpTo({ center: [11.5745, 48.1405], zoom: 14.35, pitch: 60, bearing: -40 });
  reveal(0);
  return { n: S.order.length, gained: S.res.gained, residents: S.res.residents, roofs: S.res.usedRoofs, free: S.res.freeRoofs,
    harvest: S.res.harvest, fed: S.res.people_fed, gwh: S.res.pvKwh / 1e6, fn: S.order.map(r => S.assign[r]) };
});
await page.waitForFunction(() => S.map.loaded() && S.map.areTilesLoaded(), null, { timeout: 120000 }).catch(() => {});
await page.waitForTimeout(4000);

console.log("video page ready", new Date().toISOString(), JSON.stringify({ n: info.n, gained: info.gained }));
let n = 0, bearing = -40;
const shot = async () => { await page.screenshot({ path: `${FR}/f${String(n).padStart(4, "0")}.png` }); n++; };
const step = async (k, label) => {
  bearing += 0.55;
  await page.evaluate(({ k, bearing, label }) => {
    S.map.jumpTo({ bearing }); reveal(k);
    document.querySelector("#vn").textContent = `${k.toLocaleString("en-GB")} roofs`;
    const cur = k ? S.F[S.assign[S.order[k - 1]]] : null;
    document.querySelector("#vu").textContent = label || (cur ? `now: ${cur.name.toLowerCase()}` : "the roofs of the centre");
    for (const f of S.F) { const el = document.querySelector(`#lg-${f.id}`); const seen = S.order.slice(0, k).some(r => S.F[S.assign[r]].id === f.id);
      el.className = cur && cur.id === f.id ? "on" : seen ? "" : "off"; }
  }, { k, bearing, label });
  await idle(page);
  await shot();
  if (n % 20 === 0) console.log("frame", n, new Date().toISOString());
};
for (let i = 0; i < 12; i++) await step(0);                                   // 0.8 s: grey roofs
const FILL = 130;                                                             // ≈ 8.7 s of filling
for (let i = 1; i <= FILL; i++) await step(Math.round(info.n * Math.pow(i / FILL, 1.15)));
for (let i = 0; i < 8; i++) await step(info.n, "need met, the rest stays free");
await page.evaluate(i => {
  document.querySelector(".v.bot").style.display = "none";
  const f = x => Math.round(x).toLocaleString("en-GB");
  document.body.insertAdjacentHTML("beforeend", `<div class="card"><div class="big">${f(i.gained)}</div>
    <p>residents of Munich's centre would gain a free public roof within walking distance: a playground, a garden, a park, a terrace…</p>
    <div class="k"><span><b>${f(i.roofs)}</b>roofs used</span><span><b>${f(i.free)}</b>stay free</span><span><b>${f(i.harvest / 1000)} t</b>harvest</span><span><b>${i.gwh.toFixed(0)} GWh</b>solar</span></div>
    <div class="url">Try your own Dachrepublik · barisparlatangiller.github.io</div>
    <div class="att">LoD2 © Bayerische Vermessungsverwaltung (CC BY 4.0) · Zensus 2022 © Destatis · © OpenStreetMap contributors</div></div>`);
}, info);
for (let i = 0; i < 42; i++) { bearing += 0.3; await page.evaluate(b => S.map.jumpTo({ bearing: b }), bearing); await idle(page); await shot(); }
fs.copyFileSync(`${FR}/f${String(n - 1).padStart(4, "0")}.png`, `${OUT}/cover.png`);
await browser.close();
execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", `${FR}/f%04d.png`,
  "-vf", "minterpolate=fps=30:mi_mode=blend", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
  "-movflags", "+faststart", `${OUT}/day8_dachrepublik.mp4`]);
console.log(`${n} frames, ${(n / FPS).toFixed(1)} s, ${(fs.statSync(`${OUT}/day8_dachrepublik.mp4`).size / 1e6).toFixed(2)} MB`, JSON.stringify({ ...info, fn: undefined }));
fs.rmSync(FR, { recursive: true });
process.exit(0);
