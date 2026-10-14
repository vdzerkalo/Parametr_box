// Builds dist/scene.js (three.js + parts data) and index.html (HyperFrames composition) from src/steps.js. `npm run build`
import { build } from "esbuild";
import { writeFileSync, mkdirSync } from "node:fs";
import { SCENES, TOTAL } from "./src/steps.js";

mkdirSync("dist", { recursive: true });
await build({ entryPoints: ["src/scene.js"], bundle: true, format: "iife", outfile: "dist/scene.js", minify: true, loader: { ".json": "json" }, logLevel: "info" });

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const caps = SCENES.map((s, i) => `
    <section class="cap clip ${s.id === "intro" ? "title" : ""}" id="cap-${s.id}" data-start="${s.t0}" data-duration="${s.dur}" data-track-index="2">
      ${s.step ? `<div class="badge"><b>${s.step}</b><small>із 10</small></div>` : ""}
      <h2>${esc(s.title)}</h2>
      <p>${esc(s.text)}</p>
    </section>`).join("\n");
const dots = SCENES.filter((s) => s.step).map((s) => `<i id="dot-${s.id}"></i>`).join("");

const html = `<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=1920, height=1080" />
<script src="vendor/gsap.min.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:1920px;height:1080px;overflow:hidden;background:#0b1220}
  #root{position:relative;width:1920px;height:1080px;font-family:Inter,"Segoe UI",Arial,sans-serif;color:#e8eef7;
    background:radial-gradient(1200px 800px at 65% 35%,#1d2b45 0%,#0f1a2e 55%,#080d18 100%)}
  #gl{position:absolute;inset:0;width:1920px;height:1080px}
  .brand{position:absolute;left:64px;top:44px;font-size:26px;font-weight:600;letter-spacing:.02em;color:#9fb3cc}
  .brand b{color:#4fd1c5}
  .legend{position:absolute;right:64px;top:46px;font-size:22px;color:#9fb3cc;display:flex;gap:26px}
  .legend i{display:inline-block;width:16px;height:16px;border-radius:50%;margin-right:8px;vertical-align:-2px}
  .cap{position:absolute;left:64px;bottom:96px;width:900px;padding:30px 38px 32px;border-radius:26px;
    background:linear-gradient(135deg,rgba(11,18,32,.94),rgba(17,28,48,.90));border:1px solid rgba(120,160,210,.25);
    box-shadow:0 12px 30px rgba(0,0,0,.35)}
  .cap h2{font-size:52px;line-height:1.08;font-weight:700;letter-spacing:-.02em;margin-bottom:14px}
  .cap p{font-size:29px;line-height:1.38;color:#c7d4e6}
  .cap.title{left:64px;bottom:150px;width:1000px}
  .cap.title h2{font-size:70px}
  .cap.title p{font-size:34px}
  .badge{position:absolute;left:-26px;top:-34px;width:92px;height:92px;border-radius:50%;background:#ff8a3d;color:#1a1008;
    display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 10px 28px rgba(255,138,61,.45)}
  .badge b{font-size:48px;line-height:1}.badge small{font-size:15px;font-weight:600;opacity:.75}
  .cap:has(.badge) h2{padding-left:46px}
  .lbl{position:absolute;display:flex;align-items:center;gap:10px;font-size:26px;font-weight:600;padding:7px 16px 8px 12px;border-radius:999px;
    background:rgba(11,18,32,.82);border:1px solid rgba(160,190,230,.35);color:#eaf2ff;white-space:nowrap;opacity:0}
  .lbl i{width:14px;height:14px;border-radius:50%;background:#c3cdd8;display:block}
  .lbl.new i{background:#4fd1c5}
  .lbl.dimlbl{font-size:46px;padding:10px 26px;border-color:#ffd166;color:#ffd166}
  #labels{position:absolute;inset:0}
  .bar{position:absolute;left:64px;right:64px;bottom:44px;height:8px;border-radius:6px;background:rgba(160,190,230,.18)}
  .bar>div{height:100%;width:0;border-radius:6px;background:linear-gradient(90deg,#4fd1c5,#ff8a3d)}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="${TOTAL}" data-width="1920" data-height="1080">
  <canvas id="gl" width="1920" height="1080"></canvas>
  <div id="labels"></div>
  <div class="brand"><b>●</b> Розмотувач стрейч-плівки · збірка v3</div>
  <div class="legend"><span><i style="background:#4fd1c5"></i>нові деталі v3</span><span><i style="background:#c3cdd8"></i>деталі з v2</span><span><i style="background:#ff8a3d"></i>діє зараз</span></div>
${caps}
  <div class="bar"><div id="prog"></div></div>
</div>
<script src="dist/scene.js"></script>
<script>
  window.__timelines = window.__timelines || {};
  GuideScene.init(document.getElementById("gl"), 1920, 1080, document.getElementById("labels"));
  const tl = gsap.timeline({ paused: true });
  const clock = { _t: 0, set t(v) { this._t = v; GuideScene.update(v); document.getElementById("prog").style.width = (v / ${TOTAL} * 100) + "%"; }, get t() { return this._t; } };
  tl.to(clock, { t: ${TOTAL}, duration: ${TOTAL}, ease: "none" }, 0);
  const scenes = ${JSON.stringify(SCENES.map((s) => ({ id: s.id, t0: s.t0, dur: s.dur })))};
  for (const s of scenes) {
    tl.fromTo("#cap-" + s.id, { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, s.t0 + 0.2);
    if (s.id !== "done") tl.to("#cap-" + s.id, { opacity: 0, y: -20, duration: 0.5, ease: "power1.in" }, s.t0 + s.dur - 0.6);
  }
  window.__timelines["main"] = tl;
  tl.seek(0);
</script>
</body>
</html>
`;
writeFileSync("index.html", html);
console.log("wrote index.html, total", TOTAL, "s");
