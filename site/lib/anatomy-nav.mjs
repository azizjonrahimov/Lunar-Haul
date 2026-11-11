// F-62: the rover's navigation stack as a physical object, drawn with the anatomy kit (vendor/anatomy, MIT) at build
// time: a deck section on a bench with the camera mast, star tracker, sun sensor, IMU, a cut-open clock module, the
// cut-open navigation computer and the ranging radio with its antenna, cabled together. Static SVG; the page script
// (src/protocol/nav-stack.js) lights one part at a time. Sizes are schematic (no maker's drawings are used); every
// number in the part list comes from note 01 (src/protocol/params.js) or results/E48_sizing.json.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import * as k from '../vendor/anatomy/iso-kit.mjs';
import { num, esc } from '../src/components/num.js';
import { P as PRM } from '../src/protocol/params.js';
import { ROOT } from './pages.mjs';

const WIDTH = 640, HEIGHT = 400;
const DECK = { x: -150, y: -80, w: 300, d: 160, r: 8 }, DECK_H = 10, FOOT_H = 6;
const MAST = [-110, -45], MAST_TOP = 132;
const STAR = [55, -48], SUN = [112, -52], IMU = { x: -40, y: -60, w: 38, d: 38, r: 3 };
const CPU = { x: -30, y: 0, w: 85, d: 60, r: 2 }, CPU_H = 48, CPU_CUT = 14;
const CLK = { x: -82, y: 24, w: 40, d: 30, r: 2 }, CLK_H = 18, CLK_CUT = 6;
const RAD = { x: 92, y: 26, w: 30, d: 28, r: 2.5 }, RAD_H = 22, ANT_TOP = 128;

const P = k.fitProjection([...k.boxCorners(DECK, -DECK_H - FOOT_H, 0), [MAST[0], MAST[1], MAST_TOP + 16], [RAD.x + 15, RAD.y + 14, ANT_TOP + 4]], WIDTH, HEIGHT, { pad: 26, azimuth: 45 });
const at = p => k.iso(p, P);
const S = (paths, o) => k.solidSvg(paths, o);
const L = (d, o) => k.lineSvg(d, o);
const D = (pts, o) => k.dotsSvg(pts, o);
const depth = ([x, y, z = 0]) => k.depthOf([x, y, z], P);
const byDepth = pts => [...pts].sort((a, b) => depth(a) - depth(b));
// a circle in a vertical plane facing +y (a lens on a front face)
const faceCircle = (cx, y, cz, r, n = 28) => k.pathOf(Array.from({ length: n }, (_, i) => { const t = 2 * Math.PI * i / n; return at([cx + r * Math.cos(t), y, cz + r * Math.sin(t)]); }), true);

function base() {
  const out = [`<path class="iso-halo" d="${k.haloOf(DECK, -DECK_H - FOOT_H, DECK_H, P)}"/>`];
  for (const [x, y] of byDepth(k.corners(DECK, 24))) {
    out.push(S(k.cylinder(x, y, 8, -DECK_H - FOOT_H, 1.8, P, 28), { tone: 'lo' }));
    out.push(S(k.cylinder(x, y, 6, -DECK_H - FOOT_H + 1.8, FOOT_H - 1.8, P, 28), { tone: 'mid' }));
  }
  out.push(S(k.slabOf(DECK, -DECK_H, DECK_H, P, 8, 1.6), { tone: 'mid' }));
  out.push(L(k.planOutline(k.insetPlan(DECK, 5), 0, P), { tone: 'lo' }));
  const screws = k.corners(DECK, 11);
  out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.4, 0, P, 16)).join(''), { tone: 'lo' }), D(screws.map(([x, y]) => at([x, y, 0])), { size: 0.5 }));
  const g = k.insetPlan(DECK, 5), riv = [];
  for (let x = g.x + 30; x <= g.x + g.w - 30; x += 20) riv.push([x, g.y + g.d - 2.5]);
  for (let y = g.y + 30; y <= g.y + g.d - 30; y += 20) riv.push([g.x + g.w - 2.5, y]);
  out.push(D(riv.map(([x, y]) => at([x, y, 0])), { size: 0.4, tone: 'lo' }));
  // ruler strip along the front-left edge (ticks every 5 units, a major every 25)
  const strip = { x: -138, y: DECK.y + DECK.d - 14, w: 120, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: 'lo', crease: 'none' }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.6], P);
  out.push(L(t.minor, { tone: 'lo' }), L(t.major, { tone: 'mid' }));
  out.push(D([at([strip.x + 2, strip.y + 3.5, 0.6]), at([strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  // label plate with its rule lines (printed text) and the one engraved label
  const lp = { x: 22, y: DECK.y + DECK.d - 16, w: 52, d: 10, r: 1 };
  out.push(S(k.slabOf(lp, 0, 0.8, P, 4), { tone: 'lo' }), L(k.planOutline(k.insetPlan(lp, 1.6), 0.8, P), { tone: 'faint' }));
  out.push(k.faceTextSvg(k.topMatrix([lp.x + 4, lp.y + 6.2], 0.8, P, 'x'), 'NAV STACK', { size: 3, tone: 'mid' }));
  out.push(D([at([lp.x + lp.w - 3, lp.y + 2.5, 0.8]), at([lp.x + lp.w - 3, lp.y + lp.d - 2.5, 0.8])], { size: 0.4 }));
  return out.join('');
}

// cables on the deck: drawn after the base and before every part, so a part standing on a cable's route hides it;
// each run ends on a plug block (drawn with its part) or under the computer's back faces
function cables() {
  const W = (pts) => k.wireSvg(at(pts[0]), at(pts[pts.length - 1]), { via: pts.slice(1, -1).map(at), tone: 'lo', size: 1 });
  const z = 0.6;
  return [
    W([[MAST[0], MAST[1] + 19, z], [MAST[0], 18, z], [CPU.x - 0.5, 18, z]]),                                    // cameras -> computer, left face
    W([[IMU.x + 19, IMU.y + IMU.d + 5, z], [IMU.x + 19, CPU.y - 0.5, z]]),                                      // IMU -> computer, back face
    W([[STAR[0], STAR[1] + 21, z], [STAR[0], -12, z], [38, -12, z], [38, CPU.y - 0.5, z]]),                      // star tracker
    W([[SUN[0], SUN[1] + 13, z], [SUN[0], -5, z], [50, -5, z], [50, CPU.y - 0.5, z]]),                          // sun sensor
    W([[CLK.x + CLK.w + 4, 38, z], [CPU.x - 0.5, 38, z]]),                                                       // clock module -> computer
    W([[RAD.x + 15, RAD.y + RAD.d + 4, z], [RAD.x + 15, 72, z], [42, 72, z], [42, CPU.y + CPU.d + 5, z]]),      // radio -> computer front plug
  ].join('');
}
function clips() {
  const out = [], clip = (x, y, along) => {
    const plan = along === 'y' ? { x: x - 4.5, y: y - 1.6, w: 9, d: 3.2, r: 0.8 } : { x: x - 1.6, y: y - 4.5, w: 3.2, d: 9, r: 0.8 };
    out.push(S(k.slabOf(plan, 0, 1.8, P, 2, 0.3), { tone: 'mid' }));
    out.push(D((along === 'y' ? [[x - 3.2, y], [x + 3.2, y]] : [[x, y - 3.2], [x, y + 3.2]]).map(([a, b]) => at([a, b, 1.8])), { size: 0.4 }));
  };
  clip(MAST[0], -8, 'y'); clip(-70, 18, 'x'); clip(STAR[0], -20, 'y'); clip(SUN[0], -22, 'y'); clip(84, -5, 'x'); clip(72, 72, 'x'); clip(RAD.x + 15, 64, 'y');
  return out.join('');
}
const plug = (x, y, along = 'y') => S(k.slabOf(along === 'y' ? { x: x - 2.2, y: y - 2.5, w: 4.4, d: 5, r: 0.8 } : { x: x - 2.5, y: y - 2.2, w: 5, d: 4.4, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' });

function mast() {
  const [x, y] = MAST, out = [];
  out.push(plug(x, y + 16));
  out.push(S(k.cylinder(x, y, 11, 0, 3, P, 32, 0.6), { tone: 'mid' }));
  out.push(D(byDepth([[x + 8, y], [x - 8, y], [x, y + 8], [x, y - 8]]).map(p => at([...p, 3])), { size: 0.45 }));
  out.push(S(k.cylinder(x, y, 4, 3, MAST_TOP - 3, P, 28), { tone: 'mid', crease: 'none' }));
  out.push(L([40, 80].map(zz => k.sideArc(x, y, 4, zz, P, 16)).join(''), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y, 6, MAST_TOP, 5, P, 28), { tone: 'mid' }));
  // pan-tilt yoke and the stereo camera bar, lenses facing the front (+y)
  out.push(S(k.slabOf({ x: x - 7, y: y - 5, w: 14, d: 10, r: 1.5 }, MAST_TOP + 5, 4, P, 3, 0.4), { tone: 'mid' }));
  const bar = { x: x - 30, y: y - 6, w: 60, d: 12, r: 2 }, bz = MAST_TOP + 9;
  out.push(S(k.slabOf(bar, bz, 12, P, 4, 0.6), { tone: 'hi', crease: 'lo' }));
  for (const cx of [x - 21, x + 21]) {
    const hood = { x: cx - 6, y: bar.y + bar.d, w: 12, d: 4, r: 1 };
    out.push(S(k.slabOf(hood, bz + 0.5, 11, P, 3, 0.3), { tone: 'hi', crease: 'lo' }));
    out.push(L(faceCircle(cx, hood.y + hood.d, bz + 6, 3.6), { tone: 'mid' }), L(faceCircle(cx, hood.y + hood.d, bz + 6, 1.8), { tone: 'hi' }));
  }
  out.push(D([at([x, bar.y + bar.d, bz + 9])], { size: 0.5, tone: 'hi' }));
  return out.join('');
}

function imu() {
  const b = IMU, out = [], c = [b.x + b.w / 2, b.y + b.d / 2];
  out.push(plug(c[0], b.y + b.d + 3));
  out.push(S(k.slabOf(k.insetPlan(b, -4), 0, 3, P, 4, 0.5), { tone: 'mid' }));
  out.push(D(k.corners(k.insetPlan(b, -4), 2.2).map(([x, y]) => at([x, y, 3])), { size: 0.45 }));
  out.push(S(k.slabOf(b, 3, 32, P, 4, 1.2), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(b, 30, P, 4), { tone: 'faint' }) }));
  out.push(L(k.planOutline(k.insetPlan(b, 4), 35, P, 3), { tone: 'faint' }));
  out.push(D(k.corners(b, 3.4).map(([x, y]) => at([x, y, 35])), { size: 0.45 }));
  // three gyro caps on the lid: one per axis
  for (const [dx, dy] of [[-8, -6], [6, -6], [-1, 7]]) out.push(S(k.cylinder(c[0] + dx, c[1] + dy, 4, 35, 3, P, 24, 0.4), { tone: 'mid' }));
  return out.join('');
}

function star() {
  const [x, y] = STAR, out = [];
  out.push(plug(x, y + 18));
  out.push(S(k.slabOf({ x: x - 15, y: y - 15, w: 30, d: 30, r: 2 }, 0, 6, P, 4, 0.6), { tone: 'mid' }));
  out.push(D(k.corners({ x: x - 15, y: y - 15, w: 30, d: 30 }, 3).map(([a, b]) => at([a, b, 6])), { size: 0.45 }));
  out.push(S(k.cylinder(x, y, 11, 6, 22, P, 40, 0.6), { tone: 'hi', crease: 'lo' }));
  out.push(L(k.sideArc(x, y, 11, 20, P, 24), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y, 12.5, 28, 4, P, 40, 0.4), { tone: 'mid' }));
  out.push(S(k.cylinder(x, y, 15, 32, 20, P, 44, 0.6), { tone: 'hi', crease: 'lo' }));
  out.push(L(k.sideArc(x, y, 15, 42, P, 28), { tone: 'faint' }));
  for (const r of [12.5, 9.5, 6]) out.push(L(k.ring(x, y, r, 52, P, 40), { tone: r === 6 ? 'hi' : 'lo' }));
  return out.join('');
}

function sun() {
  const [x, y] = SUN, out = [];
  out.push(plug(x, y + 10));
  out.push(S(k.slabOf({ x: x - 8, y: y - 8, w: 16, d: 16, r: 1.5 }, 0, 4, P, 3, 0.4), { tone: 'mid' }));
  out.push(S(k.cylinder(x, y, 6, 4, 7, P, 28, 0.4), { tone: 'hi', crease: 'lo' }));
  out.push(S(k.cylinder(x, y, 3.6, 11, 1.6, P, 24, 0.3), { tone: 'mid' }));
  out.push(L(k.ring(x, y, 4.8, 11, P, 24), { tone: 'lo' }), D([at([x, y, 12.6])], { size: 0.55, tone: 'hi' }));
  return out.join('');
}

// open box cut down at the front and right, the contents drawn between the back and the front walls
function openBox(b, h, cut, inside) {
  const t = 2.4, out = [];
  out.push(S(k.slabOf(b, 0, 3, P, 4, 0.4), { tone: 'lo' }));
  out.push(S(k.slabOf({ x: b.x, y: b.y, w: b.w, d: t, r: 0.6 }, 3, h, P, 2, 0.3), { tone: 'mid' }));
  out.push(S(k.slabOf({ x: b.x, y: b.y + t, w: t, d: b.d - t, r: 0.6 }, 3, h, P, 2, 0.3), { tone: 'mid' }));
  out.push(inside);
  out.push(S(k.slabOf({ x: b.x + b.w - t, y: b.y + t, w: t, d: b.d - t, r: 0.6 }, 3, cut, P, 2, 0.3), { tone: 'mid' }));
  out.push(S(k.slabOf({ x: b.x, y: b.y + b.d - t, w: b.w, d: t, r: 0.6 }, 3, cut, P, 2, 0.3), { tone: 'mid' }));
  return out.join('');
}

function clock() {
  const b = CLK, inner = [];
  inner.push(S(k.slabOf({ x: b.x + 4, y: b.y + 4, w: b.w - 8, d: b.d - 8, r: 0.8 }, 3, 1.6, P, 3), { tone: 'lo' }));
  // chip-scale atomic clock (the larger can) and the crystal oscillator (the small one)
  inner.push(S(k.slabOf({ x: b.x + 7, y: b.y + 7, w: 16, d: 13, r: 1.2 }, 4.6, 5, P, 3, 0.5), { tone: 'hi', crease: 'lo' }));
  inner.push(D(k.corners({ x: b.x + 7, y: b.y + 7, w: 16, d: 13 }, 1.6).map(([x, y]) => at([x, y, 9.6])), { size: 0.35 }));
  inner.push(S(k.cylinder(b.x + 30, b.y + 13, 3, 4.6, 2.6, P, 20, 0.3), { tone: 'hi', crease: 'lo' }));
  return S(k.slabOf({ x: b.x + b.w + 1, y: 35.5, w: 5, d: 5, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' }) + openBox(b, CLK_H, CLK_CUT, inner.join(''));
}

function computer() {
  const b = CPU, inner = [];
  // card guides on the floor, then five boards (thin in x), far to near; the GR740 board carries a finned heat sink
  inner.push(L(Array.from({ length: 5 }, (_, i) => k.lineOnTop([b.x + 12 + 13 * i, b.y + 4], [b.x + 12 + 13 * i, b.y + b.d - 4], 3, P)).join(''), { tone: 'faint' }));
  for (let i = 0; i < 5; i++) {
    const bx = b.x + 11 + 13 * i, board = { x: bx, y: b.y + 5, w: 2.2, d: b.d - 10, r: 0.4 };
    inner.push(S(k.slabOf(board, 3, 38, P, 2), { tone: i === 2 ? 'hi' : 'mid', crease: 'lo' }));
    inner.push(S(k.slabOf({ x: bx + 2.2, y: b.y + 18, w: 1.4, d: 14, r: 0.3 }, 16, 12, P, 2), { tone: 'mid' }));
    inner.push(S(k.slabOf({ x: bx - 0.6, y: b.y + b.d - 9, w: 3.4, d: 4, r: 0.6 }, 41, 3, P, 2, 0.3), { tone: 'mid' }));
    if (i === 2) for (let f = 0; f < 4; f++) inner.push(S(k.slabOf({ x: bx + 3.6 + f * 1.8, y: b.y + 19, w: 0.9, d: 12, r: 0.2 }, 17, 10, P, 2), { tone: 'lo', crease: 'none' }));
  }
  const front = S(k.slabOf({ x: 39.8, y: b.y + b.d, w: 4.4, d: 5, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' });
  const wallScrews = D([[b.x + 10, b.y + b.d - 1.2], [b.x + b.w - 10, b.y + b.d - 1.2], [b.x + b.w - 1.2, b.y + 12], [b.x + b.w - 1.2, b.y + b.d - 12]].map(([x, y]) => at([x, y, 3 + CPU_CUT])), { size: 0.4 });
  return openBox(b, CPU_H, CPU_CUT, inner.join('')) + wallScrews + front;
}

function radio() {
  const b = RAD, out = [], c = [b.x + b.w / 2, b.y + b.d / 2];
  out.push(plug(c[0], b.y + b.d + 2.5));
  out.push(S(k.slabOf(b, 0, RAD_H, P, 4, 0.8), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(b, 6, P, 4), { tone: 'faint' }) }));
  out.push(L(k.planOutline(k.insetPlan(b, 3), RAD_H, P, 3), { tone: 'faint' }));
  out.push(D(k.corners(b, 2.6).map(([x, y]) => at([x, y, RAD_H])), { size: 0.45 }));
  // the ranging antenna (a flat patch) and the whip of the coordination radio
  out.push(S(k.slabOf({ x: b.x + 4, y: b.y + 4, w: 10, d: 10, r: 1 }, RAD_H, 1.4, P, 3), { tone: 'mid' }));
  out.push(S(k.cylinder(c[0] + 6, c[1] + 6, 3.4, RAD_H, 4, P, 24, 0.3), { tone: 'mid' }));
  out.push(S(k.cylinder(c[0] + 6, c[1] + 6, 1.1, RAD_H + 4, ANT_TOP - RAD_H - 6, P, 16), { tone: 'hi', crease: 'none' }));
  out.push(S(k.cylinder(c[0] + 6, c[1] + 6, 1.8, 62, 3, P, 20, 0.3), { tone: 'mid' }));
  out.push(S(k.cylinder(c[0] + 6, c[1] + 6, 2, ANT_TOP - 2, 2.4, P, 20, 0.4), { tone: 'hi', crease: 'lo' }));
  return out.join('');
}

// ---------- the part list: number, flag, source, and whose number it is ----------
const E48 = () => { const p = join(ROOT, 'results', 'E48_sizing.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')) : null; };
const n = key => num(PRM[key]);
function partList() {
  const S48 = E48(), SZ = 'results/E48_sizing.json';
  const e = (value, unit, digits, flag, src) => num({ value, unit, digits, flag, source: `${SZ}: ${src}` });
  const sm = S48?.classes?.SMALL, F = S48?.flight;
  return [
    ['cameras', 'Stereo cameras on the mast', 'Visual odometry: track the ground between frames.', `Drift ${n('dr_vo')}; ${n('vo_fail')} of updates fail`, 'published'],
    ['star', 'Star tracker', 'Absolute heading from the stars, so the gyros cannot drift.', `Heading to ${n('star_hdg')}, bounded`, 'our design'],
    ['sun', 'Sun sensor', 'Heading from the Sun when it is up; a backup to the star tracker.', `Heading to ${n('sun_hdg')}, sunlit only`, 'published'],
    ['imu', 'IMU: three gyros and accelerometers', 'Turn rate and acceleration between camera frames.', `Heading drift ${n('gyro')} on gyros alone`, 'published'],
    ['radio', 'Ranging radio (UWB)', 'Two-way radio ranges to the base beacons and to other rovers.', `Range error ${n('uwb')} up to ${n('uwb_range')}`, 'published'],
    ['antenna', 'Antenna (1 m) of the coordination radio', 'Carries position reports and the job market.',
      sm ? `${e(sm.link.longest_hop_kbps, ' kbit/s', 1, 'Modelled', 'classes.SMALL.link.longest_hop_kbps')} at the ${e(sm.link.mutual_horizon_m / 1000, ' km', 1, 'Modelled', 'classes.SMALL.link.mutual_horizon_m')} horizon, ${e(sm.link.tx_power_w, ' W', 2, 'Assumed', 'classes.SMALL.link.tx_power_w')}` : 'E48 not available', 'our design'],
    ['clock', 'Clock module, cut open', 'A chip-scale atomic clock beside a crystal: time stamps and resyncs.', `Drift: atomic ${n('csac')}, crystal ${n('tcxo')}`, 'published'],
    ['computer', 'Navigation computer, cut open', `The flight board (${esc(F?.processor || 'GR740')}) runs our safety program and planner.`,
      sm && F ? `${num({ value: F.memory_mb, unit: ' MB', digits: 0, flag: 'Spec', source: `${SZ}: flight.memory_mb (${F.processor})` })} on board; our program peaks at ${e(sm.peak_memory_mb, ' MB', 2, 'Modelled', 'classes.SMALL.peak_memory_mb')} and one safety check takes ${e(sm.cpu_safety_check_us.p99 * F.factor / 1000, ' ms', 0, 'Modelled', 'classes.SMALL.cpu_safety_check_us.p99 × flight.factor')} on the flight core` : 'E48 not available', 'published board, our software'],
  ];
}

export function navStackFigure() {
  const parts = { cameras: mast(), star: star(), sun: sun(), imu: imu(), radio: radio(), clock: clock(), computer: computer() };
  // painter's order for the parts on the deck: far before near (antenna rides with the radio)
  const centre = { cameras: [...MAST, 0], star: [...STAR, 0], sun: [...SUN, 0], imu: [IMU.x + 19, IMU.y + 19, 0], clock: [CLK.x + 20, CLK.y + 15, 0], computer: [CPU.x + 42, CPU.y + 30, 0], radio: [RAD.x + 15, RAD.y + 14, 0] };
  const order = Object.keys(parts).sort((a, b) => depth(centre[a]) - depth(centre[b]));
  const group = id => `<g class="nv-part" data-part="${id}"${id === 'radio' ? ' data-also="antenna"' : ''}>${parts[id]}</g>`;
  const svg = k.figureSvg({ width: WIDTH, height: HEIGHT,
    label: 'A rover navigation deck on a bench, cut open: a mast with two cameras at the back left, a star tracker with its light baffle and a small sun sensor at the back right, the IMU in the middle, a clock module and the navigation computer with their walls cut down at the front, and the ranging radio with its antenna at the front right, all cabled to the computer.',
    body: [base(), cables(), clips(), ...order.map(group)] });
  const list = partList();
  const items = list.map(([id, name, what, numbers, whose]) => `<li><button type="button" class="nv-item" data-part="${id}" aria-pressed="false"><span class="nv-name">${esc(name)}</span> <span class="nv-whose" data-whose="${whose.startsWith('our') ? 'ours' : whose.startsWith('published board') ? 'mixed' : 'published'}">${esc(whose)}</span></button><span class="nv-what">${esc(what)} ${numbers}.</span></li>`).join('');
  const plate = k.plateHtml({ fig: 'Fig 1b', title: 'Navigation stack', hint: 'Pick a part', readout: `${list[0][1]}`,
    keys: [{ mark: 'lit', label: 'The part picked in the list' }, { mark: 'raised', label: 'Sizes are schematic; the numbers are not' }],
    caption: '"Published" means the number is the maker\'s or a measured test; "our design" means we chose or assumed it.',
    body: `<div class="iso-stage nv-stage">${svg}</div>` });
  return `<div class="iso nv">${plate}<ol class="nv-list" aria-label="Parts of the navigation stack">${items}</ol></div>`;
}
