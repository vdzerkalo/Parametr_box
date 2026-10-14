// Three.js scene of the v3 assembly. Pure function of time: GuideScene.update(t) sets every transform, so HyperFrames can seek anywhere.
import * as THREE from "three";
import { unzlibSync } from "fflate";
import PARTS_DATA from "../assets/parts.json";
import L from "../assets/layout.json";
import { CAMS } from "./steps.js";

const V2 = 0xc3cdd8, V3 = 0x4fd1c5, ORANGE = 0xff8a3d;
const ADV = 15.7;                                  // spindle advance from "retracted" to "seated" (mm)
const rc = L.ring, sx = L.sx, sy = L.sy;
const ease = (x) => x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x);

// kf: [t, [dx,dy,dz], turns]  offsets from the final (assembled) position; turns = cumulative rotations about u (axis of motion)
const SPEC = {
  clamp_L:      { c: V2, name: "струбцина", kf: [[0, [0, 0, 0], 0]], hl: null },
  nut_L:        { c: V2, name: "гайка", kf: [[15, [0, 70, 0], 0], [19, [0, 0, 0], 0]] },
  screw_L:      { c: V2, name: "гвинт", u: [0, 1, 0], pivot: [68, 0, 18], kf: [[23, [0, -110, 0], 0], [28, [0, 0, 0], 3]] },
  pad_L:        { c: V2, name: "накладка", kf: [[31, [70, 0, 0], 0], [35, [0, 0, 0], 0]] },
  holder_L:     { c: V2, name: "тримач", pivot: [rc[0], rc[1], 0], kf: [[38, [0, 0, 90], 0], [41.5, [0, 0, 0], 0]],
                  swing: [[41.5, 0], [42.5, 0], [44, 30], [45.5, -30], [46, 0]] },
  pivot_knob_L: { c: V2, name: "ручка шарніра", u: [0, 0, 1], pivot: [rc[0], rc[1], 0], kf: [[47, [0, 0, -70], 0], [51, [0, 0, 0], 3]] },
  carrier_L:    { c: V3, name: "носій", kf: [[53, [0, 90, 0], 0], [57, [0, 0, 0], 0]] },
  spindle_L:    { c: V3, name: "шпиндель", u: [0, 0, 1], pivot: [sx, sy, 0],
                  kf: [[60, [0, 0, -90 - ADV], 0], [65, [0, 0, -ADV], 3], [80, [0, 0, -ADV], 3], [84, [0, 0, 0], 3 + ADV / 6]] },
  cone_L:       { c: V3, name: "конус", unit: true, kf: [[68, [0, 0, -55], 0], [72, [0, 0, 0], 0]] },
};
const ORDER = Object.keys(SPEC);
const UNIT_KF = [[67, [0, 170, 0]], [76, [0, 170, 0]], [79.5, [0, 0, 0]]];
const RIGHT_FADE = [84.5, 86.5];
const T_LABELS_ALL = [8, 13.5];

function lerpKF(kf, t) {                           // returns [offset3, turns]
  if (t <= kf[0][0]) return [kf[0][1], kf[0][2]];
  for (let i = 0; i < kf.length - 1; i++) {
    const [t0, o0, r0] = kf[i], [t1, o1, r1] = kf[i + 1];
    if (t <= t1) {
      const k = ease((t - t0) / (t1 - t0));
      return [o0.map((v, j) => v + (o1[j] - v) * k), r0 + (r1 - r0) * k];
    }
  }
  const last = kf[kf.length - 1];
  return [last[1], last[2]];
}
function lerpSeries(s, t) {
  if (t <= s[0][0]) return s[0][1];
  for (let i = 0; i < s.length - 1; i++) if (t <= s[i + 1][0]) return s[i][1] + (s[i + 1][1] - s[i][1]) * ease((t - s[i][0]) / (s[i + 1][0] - s[i][0]));
  return s[s.length - 1][1];
}
function b64(s) { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
function geometry(d) {
  const raw = unzlibSync(b64(d.data));
  const buf = raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength);
  const pos = new Float32Array(buf, 0, d.nv * 3), idx = new Uint32Array(buf, d.nv * 12, d.nf * 3);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  const ng = g.toNonIndexed();
  ng.computeVertexNormals();
  ng.computeBoundingBox();
  return ng;
}

let renderer, scene, camera, W = 1920, H = 1080, unit, right, tableMesh, filmMesh, coreMesh, dim, labelsEl;
const nodes = {};                                  // name -> {group, mesh, mat, rGroup, rMat, center}
const labels = {};

function mkMat(c) { return new THREE.MeshStandardMaterial({ color: c, roughness: 0.5, metalness: 0.08, flatShading: true, transparent: true }); }

function init(canvas, w = 1920, h = 1080, labelLayer = null) {
  W = w; H = h; labelsEl = labelLayer;
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(W, H, false); renderer.setClearColor(0x000000, 0);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(32, W / H, 5, 6000);
  
  scene.add(new THREE.HemisphereLight(0xe8f1ff, 0x1b2433, 1.15));
  const d1 = new THREE.DirectionalLight(0xffffff, 1.6); d1.position.set(400, 700, -500); scene.add(d1);
  const d2 = new THREE.DirectionalLight(0x9fd8ff, 0.7); d2.position.set(-500, 200, 400); scene.add(d2);

  unit = new THREE.Group(); scene.add(unit);
  right = new THREE.Group(); right.position.z = 2 * L.z_mid; right.scale.z = -1; scene.add(right);
  const rightUnit = new THREE.Group(); right.add(rightUnit);

  for (const n of ORDER) {
    const s = SPEC[n], geo = geometry(PARTS_DATA[n]);
    const piv = s.pivot || [0, 0, 0];
    const mat = mkMat(s.c);
    const mesh = new THREE.Mesh(geo, mat); mesh.position.set(-piv[0], -piv[1], -piv[2]);
    const grp = new THREE.Group(); grp.add(mesh);
    (s.unit ? unit : scene).add(grp);
    const rMat = mkMat(s.c);
    const rMesh = new THREE.Mesh(geo, rMat); rMesh.position.copy(mesh.position);
    const rGrp = new THREE.Group(); rGrp.add(rMesh);
    right.add(rGrp);
    const c = new THREE.Vector3(); geo.boundingBox.getCenter(c);
    nodes[n] = { grp, mat, rGrp, rMat, center: c, piv, s };
    if (labelsEl) {
      const el = document.createElement("div"); el.className = "lbl" + (s.c === V3 ? " new" : "");
      el.innerHTML = `<i></i><span>${s.name}</span>`; labelsEl.appendChild(el); labels[n] = el;
    }
  }
  // roll: core + film (inside `unit`), left cone already lives in `unit`; right cone is a mirrored clone placed in `right`
  const zc = L.z_re + L.W / 2;
  const cyl = (r, len, op, color, open = true, side = THREE.DoubleSide) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 72, 1, open), new THREE.MeshStandardMaterial({ color, roughness: 0.9, transparent: true, opacity: op, side, depthWrite: false }));
    m.rotation.x = Math.PI / 2; m.position.set(sx, sy, zc); return m;
  };
  coreMesh = cyl(L.ID / 2 + L.core_wall, L.W, 0.5, 0xb08968); unit.add(coreMesh);
  const coreIn = cyl(L.ID / 2, L.W, 0.5, 0x8b6b4f); unit.add(coreIn);
  filmMesh = cyl(L.film_od / 2, L.W, 0.16, 0xdff3ff); unit.add(filmMesh);
  for (const z of [L.z_re, L.z_re + L.W]) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(L.ID / 2 + L.core_wall, L.film_od / 2, 72), new THREE.MeshBasicMaterial({ color: 0xdff3ff, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false }));
    ring.position.set(sx, sy, z); unit.add(ring);
  }
  // right cone sits in the unit (mirrored about z_mid)
  const rc2 = new THREE.Mesh(nodes.cone_L.grp.children[0].geometry, nodes.cone_L.mat.clone());
  rc2.position.copy(nodes.cone_L.grp.children[0].position); const rcg = new THREE.Group(); rcg.add(rc2);
  rcg.position.z = 2 * L.z_mid; rcg.scale.z = -1; unit.add(rcg); nodes.cone_R = { rGrp: rcg, rMat: rc2.material };
  // right side must not duplicate the cone (it is in the unit)
  nodes.cone_L.rGrp.visible = false;
  // table
  tableMesh = new THREE.Mesh(new THREE.BoxGeometry(110, L.table_t, 820), new THREE.MeshStandardMaterial({ color: 0xb39b78, roughness: 0.8, transparent: true, opacity: 0.22 }));
  tableMesh.position.set(30 + 55, L.arm_lo + L.jaw_gap - L.table_t / 2, 350); scene.add(tableMesh);
  // dimension between holder plate mid-planes
  dim = new THREE.Group();
  const lm = new THREE.LineBasicMaterial({ color: 0xffd166 });
  const seg = (a, b) => new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]), lm);
  const y0 = sy + 95, zA = L.z_pm, zB = L.z_pm + L.S;
  dim.add(seg([sx, y0, zA], [sx, y0, zB]), seg([sx, y0 - 140, zA], [sx, y0 + 20, zA]), seg([sx, y0 - 140, zB], [sx, y0 + 20, zB]));
  scene.add(dim);
  if (labelsEl) {
    const el = document.createElement("div"); el.className = "lbl dimlbl"; el.innerHTML = `<span>630 мм</span>`; labelsEl.appendChild(el); labels.__dim = el;
    for (const k of ["roll_core"]) { }
  }
  update(0);
}

function camAt(t) {
  let i = 0; while (i < CAMS.length - 2 && t > CAMS[i + 1][0]) i++;
  const [t0, p0, g0] = CAMS[i], [t1, p1, g1] = CAMS[i + 1];
  const k = ease((t - t0) / (t1 - t0));
  return [p0.map((v, j) => v + (p1[j] - v) * k), g0.map((v, j) => v + (g1[j] - v) * k)];
}

const tmpV = new THREE.Vector3(), up = new THREE.Vector3();
const LOFF = { clamp_L: [70, 70], nut_L: [14, -30], pad_L: [14, 20] };
function labelAt(el, wpos, show, dx = 12, dy = -34) {
  if (!el) return;
  if (!show) { el.style.opacity = 0; return; }
  tmpV.copy(wpos).project(camera);
  el.style.opacity = 1;
  el.style.left = ((tmpV.x * 0.5 + 0.5) * W + dx) + "px";
  el.style.top = ((-tmpV.y * 0.5 + 0.5) * H + dy) + "px";
}

function update(t) {
  const [cp, cg] = camAt(t);
  // gentle orbit during the intro so it never looks static
  const orb = t < 14 ? Math.sin(t * 0.35) * 0.25 : 0;
  const px = cp[0], pz = cp[2], gx = cg[0], gz = cg[2];
  const dxp = px - gx, dzp = pz - gz, ca = Math.cos(orb), sa = Math.sin(orb);
  camera.position.set(gx + dxp * ca - dzp * sa, cp[1], gz + dxp * sa + dzp * ca);
  camera.lookAt(cg[0], cg[1], cg[2]);
  const vo = ease((t - 78) / 4);
  camera.setViewOffset(W, H, -340 + 200 * vo, 0 - 20 * vo, W, H);   // subject to the right of the caption panel; centred for the full-machine shots
  camera.updateMatrixWorld();

  const unitOff = lerpKF(UNIT_KF.map(([a, o]) => [a, o, 0]), t)[0];
  unit.position.set(...unitOff);
  const unitVisible = ease((t - 66.5) / 1.0);
  const rightVis = ease((t - RIGHT_FADE[0]) / (RIGHT_FADE[1] - RIGHT_FADE[0]));
  const partVis = ease((t - 0.2) / 1.0);

  for (const n of ORDER) {
    const nd = nodes[n], s = nd.s;
    const [off, turns] = lerpKF(s.kf, t);
    const [o0, ] = [s.kf[0][1]];
    let u = s.u ? new THREE.Vector3(...s.u) : null;
    nd.grp.position.set(nd.piv[0] + off[0], nd.piv[1] + off[1], nd.piv[2] + off[2]);
    nd.grp.quaternion.identity();
    if (u && turns) nd.grp.quaternion.setFromAxisAngle(u, turns * Math.PI * 2);
    if (s.swing) {
      const a = lerpSeries(s.swing, t) * Math.PI / 180;
      nd.grp.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), a));
    }
    // active highlight window
    const ta = s.kf[0][0] - 0.8, tb = s.kf[s.kf.length - 1][0] + (n === "spindle_L" ? 0 : 1.2);
    const lit = s.hl === null ? 0 : (n === "spindle_L" ? Math.max(ease((t - ta) / 0.5) * (1 - ease((t - 66.5) / 0.8)), ease((t - 80) / 0.4) * (1 - ease((t - 85.5) / 0.8))) : ease((t - ta) / 0.5) * (1 - ease((t - tb) / 0.8)));
    nd.mat.emissive = new THREE.Color(ORANGE).multiplyScalar(lit * 0.55);
    nd.mat.opacity = n === "clamp_L" ? 1 : (s.unit ? unitVisible : partVis);
    nd.grp.visible = nd.mat.opacity > 0.01;
    if (n === "clamp_L") nd.grp.visible = true;
    // right side copy: assembled
    nd.rGrp.position.set(nd.piv[0], nd.piv[1], nd.piv[2]);
    nd.rMat.opacity = rightVis; nd.rGrp.visible = rightVis > 0.01 && !s.unit;
    if (n === "spindle_L") { nd.rGrp.position.z = nd.piv[2] + lerpKF(s.kf, t)[0][2]; nd.rGrp.visible = rightVis > 0.01; nd.rGrp.quaternion.setFromAxisAngle(new THREE.Vector3(0, 0, 1), turns * Math.PI * 2); }
  }
  nodes.cone_R.rMat.opacity = unitVisible;
  nodes.cone_R.rGrp.visible = unitVisible > 0.01;
  // roll pieces fade (core visible with the unit, film only from the "roll" step)
  coreMesh.parent.children.forEach((c) => { if (c.material && c !== nodes.cone_L.grp) { } });
  const filmK = ease((t - 76) / 2);
  filmMesh.material.opacity = 0.16 * filmK; filmMesh.visible = filmK > 0.01;
  unit.children.forEach((c) => { if (c.isMesh && c !== filmMesh && c.geometry.type !== "RingGeometry") c.material.opacity = 0.5 * unitVisible; if (c.geometry && c.geometry.type === "RingGeometry") c.visible = false; });
  coreMesh.visible = unitVisible > 0.01; unit.children.forEach((c) => { if (c.isMesh && c.geometry.type === "CylinderGeometry" && c !== filmMesh) c.visible = unitVisible > 0.01; });
  right.visible = rightVis > 0.01;
  tableMesh.material.opacity = 0.22 * ease((t - 13) / 1.0) * (1 - ease((t - 86) / 1.0) * 0);
  tableMesh.visible = tableMesh.material.opacity > 0.01;
  const dimK = ease((t - 86.5) / 0.8) * (1 - ease((t - 94.2) / 0.8));
  dim.visible = dimK > 0.01;

  renderer.render(scene, camera);

  // labels
  if (labelsEl) {
    const inAll = t >= T_LABELS_ALL[0] && t <= T_LABELS_ALL[1];
    for (const n of ORDER) {
      const nd = nodes[n], s = nd.s;
      const ta = s.kf[0][0], tb = s.kf[s.kf.length - 1][0];
      const own = s.hl !== null && t >= ta - 0.6 && t <= Math.min(tb + 0.6, n === "spindle_L" ? 66.5 : 999) && t > 13.9;
      const show = (inAll || own) && (nd.grp.visible);
      const w = new THREE.Vector3(); w.copy(nd.center).add(new THREE.Vector3(...lerpKF(s.kf, t)[0]));
      if (s.unit) w.add(unit.position);
      const lo = LOFF[n] || [12, -34]; labelAt(labels[n], w, show, lo[0], lo[1]);
      if (labels[n]) labels[n].style.opacity = show ? Math.min(1, ease((t - (inAll ? T_LABELS_ALL[0] : ta - 0.6)) / 0.5)) : 0;
    }
    const mid = new THREE.Vector3(sx, sy + 95, L.z_pm + L.S / 2);
    labelAt(labels.__dim, mid, dimK > 0.05, -40, -46);
    if (labels.__dim) labels.__dim.style.opacity = dimK;
  }
}

window.GuideScene = { init, update, nodes };
