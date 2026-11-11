// F-62/F-68: Fig 1b, the rover's navigation stack as a physical object (anatomy kit, vendor/anatomy, MIT): a deck section on
// a bench with the camera mast, star tracker, sun sensor, IMU, clock module, navigation computer and the ranging radio with
// its antenna, cabled together. "Open" lifts the lids and moves the computer's and the clock's side panels away (each moving
// group carries its screen offset in data-move). Labels with leader lines carry each part's key number. Sizes are
// schematic; every number comes from note 01 (src/protocol/params.js) or results/E48_sizing.json.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { k, W, project, tools, labels, partList, plate, still } from './anatomy-common.mjs';
import { num, esc, fmt } from '../src/components/num.js';
import { P as PRM } from '../src/protocol/params.js';
import { ROOT } from './pages.mjs';

const H = 470;
const DECK = { x: -150, y: -80, w: 300, d: 160, r: 8 }, DECK_H = 10, FOOT_H = 6;
const MAST = [-110, -45], MAST_TOP = 132;
const STAR = [55, -48], SUN = [112, -52], IMU = { x: -40, y: -60, w: 38, d: 38, r: 3 };
const CPU = { x: -30, y: 0, w: 85, d: 60, r: 2 }, CPU_H = 48;
const CLK = { x: -82, y: 24, w: 40, d: 30, r: 2 }, CLK_H = 18;
const RAD = { x: 92, y: 26, w: 30, d: 28, r: 2.5 }, RAD_H = 22, ANT = [RAD.x + 6, RAD.y - 9], ANT_TOP = 128;

const P = project([...k.boxCorners(DECK, -DECK_H - FOOT_H, 0), [MAST[0], MAST[1], MAST_TOP + 20], [ANT[0], ANT[1], ANT_TOP + 4], [CPU.x + 42, CPU.y + 30, CPU_H + 50]], H, { pad: 18, azimuth: 45 });
const { at, S, L, D, depth, byDepth, move, faceCircle } = tools(P);
// a group that moves by world vector v when the figure opens; baked open for the still
const mv = (v, body, open, fade = null) => `<g data-move="${move(v)}"${fade !== null ? ` data-fade="${fade}"` : ''}${open ? ` transform="translate(${move(v)})"${fade !== null ? ` opacity="${fade}"` : ''}` : ''}>${body}</g>`;
// the near panels of an opened box slide out a little and fade to a trace (a ghosted panel), so the inside reads

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
  const strip = { x: -138, y: DECK.y + DECK.d - 14, w: 120, d: 7, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: 'lo', crease: 'none' }));
  const t = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.6], P);
  out.push(L(t.minor, { tone: 'lo' }), L(t.major, { tone: 'mid' }));
  out.push(D([at([strip.x + 2, strip.y + 3.5, 0.6]), at([strip.x + strip.w - 2, strip.y + 3.5, 0.6])], { size: 0.45 }));
  const lp = { x: 22, y: DECK.y + DECK.d - 16, w: 52, d: 10, r: 1 };
  out.push(S(k.slabOf(lp, 0, 0.8, P, 4), { tone: 'lo' }), L(k.planOutline(k.insetPlan(lp, 1.6), 0.8, P), { tone: 'faint' }));
  out.push(k.faceTextSvg(k.topMatrix([lp.x + 4, lp.y + 6.2], 0.8, P, 'x'), 'NAV STACK', { size: 3, tone: 'mid' }));
  out.push(D([at([lp.x + lp.w - 3, lp.y + 2.5, 0.8]), at([lp.x + lp.w - 3, lp.y + lp.d - 2.5, 0.8])], { size: 0.4 }));
  return out.join('');
}

function cables() {
  const Wr = pts => k.wireSvg(at(pts[0]), at(pts[pts.length - 1]), { via: pts.slice(1, -1).map(at), tone: 'mid', size: 1 });
  const z = 0.6;
  return [
    Wr([[MAST[0], MAST[1] + 19, z], [MAST[0], 18, z], [CPU.x - 0.5, 18, z]]),
    Wr([[IMU.x + 19, IMU.y + IMU.d + 5, z], [IMU.x + 19, CPU.y - 0.5, z]]),
    Wr([[STAR[0], STAR[1] + 21, z], [STAR[0], -12, z], [38, -12, z], [38, CPU.y - 0.5, z]]),
    Wr([[SUN[0], SUN[1] + 13, z], [SUN[0], -5, z], [50, -5, z], [50, CPU.y - 0.5, z]]),
    Wr([[CLK.x + CLK.w + 4, 38, z], [CPU.x - 0.5, 38, z]]),
    Wr([[RAD.x + 15, RAD.y + RAD.d + 4, z], [RAD.x + 15, 72, z], [42, 72, z], [42, CPU.y + CPU.d + 5, z]]),
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
const plug = (x, y) => S(k.slabOf({ x: x - 2.2, y: y - 2.5, w: 4.4, d: 5, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' });

function mast() {
  const [x, y] = MAST, out = [];
  out.push(plug(x, y + 16));
  out.push(S(k.cylinder(x, y, 11, 0, 3, P, 32, 0.6), { tone: 'mid' }));
  out.push(D(byDepth([[x + 8, y], [x - 8, y], [x, y + 8], [x, y - 8]]).map(p => at([...p, 3])), { size: 0.45 }));
  out.push(S(k.cylinder(x, y, 4, 3, MAST_TOP - 3, P, 28), { tone: 'mid', crease: 'none' }));
  out.push(L([40, 80].map(zz => k.sideArc(x, y, 4, zz, P, 16)).join(''), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y, 6, MAST_TOP, 5, P, 28), { tone: 'mid' }));
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

function imu(open) {
  const b = IMU, out = [], c = [b.x + b.w / 2, b.y + b.d / 2];
  out.push(plug(c[0], b.y + b.d + 3));
  out.push(S(k.slabOf(k.insetPlan(b, -4), 0, 3, P, 4, 0.5), { tone: 'mid' }));
  out.push(D(k.corners(k.insetPlan(b, -4), 2.2).map(([x, y]) => at([x, y, 3])), { size: 0.45 }));
  out.push(S(k.slabOf(b, 3, 30, P, 4, 1.2), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(b, 26, P, 4), { tone: 'faint' }) }));
  for (const [dx, dy] of [[-8, -6], [6, -6], [-1, 7]]) out.push(S(k.cylinder(c[0] + dx, c[1] + dy, 4.2, 33, 4, P, 24, 0.4), { tone: 'mid' }));
  const lid = S(k.slabOf(b, 33, 4.5, P, 4, 0.8), { tone: 'hi', crease: 'lo' }) + L(k.planOutline(k.insetPlan(b, 4), 37.5, P, 3), { tone: 'faint' }) + D(k.corners(b, 3.4).map(([x, y]) => at([x, y, 37.5])), { size: 0.45 });
  out.push(mv([0, 0, 40], lid, open));
  return out.join('');
}

function star(open) {
  const [x, y] = STAR, out = [];
  out.push(plug(x, y + 18));
  out.push(S(k.slabOf({ x: x - 15, y: y - 15, w: 30, d: 30, r: 2 }, 0, 6, P, 4, 0.6), { tone: 'mid' }));
  out.push(D(k.corners({ x: x - 15, y: y - 15, w: 30, d: 30 }, 3).map(([a, b]) => at([a, b, 6])), { size: 0.45 }));
  out.push(S(k.cylinder(x, y, 11, 6, 22, P, 40, 0.6), { tone: 'hi', crease: 'lo' }));
  out.push(L(k.sideArc(x, y, 11, 20, P, 24), { tone: 'faint' }));
  out.push(S(k.cylinder(x, y, 12.5, 28, 4, P, 40, 0.4), { tone: 'mid' }));
  out.push(L(k.ring(x, y, 7, 32, P, 32), { tone: 'hi' }));
  const baffle = S(k.cylinder(x, y, 15, 32, 20, P, 44, 0.6), { tone: 'hi', crease: 'lo' }) + L(k.sideArc(x, y, 15, 42, P, 28), { tone: 'faint' })
    + [12.5, 9.5].map(r => L(k.ring(x, y, r, 52, P, 40), { tone: 'lo' })).join('');
  out.push(mv([0, 0, 30], baffle, open));
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

// a box with a lid and two removable panels (the near +x and +y sides); opening lifts the lid and moves the panels out
function box(b, h, inside, open, { lift = 30, out: away = 22, rise = 8 } = {}) {   // panels rise clear of what is inside
  const t = 2.4, o = [];
  o.push(S(k.slabOf(b, 0, 3, P, 4, 0.4), { tone: 'lo' }));
  o.push(S(k.slabOf({ x: b.x, y: b.y, w: b.w, d: t, r: 0.6 }, 3, h, P, 2, 0.3), { tone: 'mid' }));
  o.push(S(k.slabOf({ x: b.x, y: b.y + t, w: t, d: b.d - t, r: 0.6 }, 3, h, P, 2, 0.3), { tone: 'mid' }));
  o.push(inside);
  const right = { x: b.x + b.w - t, y: b.y + t, w: t, d: b.d - 2 * t, r: 0.6 }, front = { x: b.x, y: b.y + b.d - t, w: b.w, d: t, r: 0.6 };
  o.push(mv([away, 0, rise], S(k.slabOf(right, 3, h, P, 2, 0.3), { tone: 'mid' }) + D([at([right.x + 1.2, right.y + 6, 3 + h]), at([right.x + 1.2, right.y + right.d - 6, 3 + h])], { size: 0.4 }), open, 0.14));
  o.push(mv([0, away, rise], S(k.slabOf(front, 3, h, P, 2, 0.3), { tone: 'mid' }) + D([at([front.x + 8, front.y + 1.2, 3 + h]), at([front.x + front.w - 8, front.y + 1.2, 3 + h])], { size: 0.4 }), open, 0.14));
  const lid = S(k.slabOf(b, 3 + h, 2.4, P, 4, 0.5), { tone: 'hi', crease: 'lo' }) + L(k.planOutline(k.insetPlan(b, 4), 5.4 + h, P, 3), { tone: 'faint' }) + D(k.corners(b, 3).map(([x, y]) => at([x, y, 5.4 + h])), { size: 0.45 });
  o.push(mv([0, 0, lift], lid, open));
  return o.join('');
}

function clock(open) {
  const b = CLK, inner = [];
  inner.push(S(k.slabOf({ x: b.x + 4, y: b.y + 4, w: b.w - 8, d: b.d - 8, r: 0.8 }, 3, 1.6, P, 3), { tone: 'lo' }));
  const csac = S(k.slabOf({ x: b.x + 7, y: b.y + 7, w: 16, d: 13, r: 1.2 }, 4.6, 5, P, 3, 0.5), { tone: 'hi', crease: 'lo' }) + D(k.corners({ x: b.x + 7, y: b.y + 7, w: 16, d: 13 }, 1.6).map(([x, y]) => at([x, y, 9.6])), { size: 0.35 });
  inner.push(mv([0, 0, 14], csac, open));
  inner.push(S(k.cylinder(b.x + 30, b.y + 13, 3, 4.6, 2.6, P, 20, 0.3), { tone: 'hi', crease: 'lo' }));
  return S(k.slabOf({ x: b.x + b.w + 1, y: 35.5, w: 5, d: 5, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' }) + box(b, CLK_H, inner.join(''), open, { lift: 62, out: 12, rise: 0 });
}

function computer(open) {
  const b = CPU, inner = [];
  inner.push(L(Array.from({ length: 5 }, (_, i) => k.lineOnTop([b.x + 12 + 13 * i, b.y + 4], [b.x + 12 + 13 * i, b.y + b.d - 4], 3, P)).join(''), { tone: 'faint' }));
  const boards = [];
  for (let i = 0; i < 5; i++) {
    const bx = b.x + 11 + 13 * i, board = { x: bx, y: b.y + 5, w: 2.2, d: b.d - 10, r: 0.4 };
    boards.push(S(k.slabOf(board, 3, 38, P, 2), { tone: i === 2 ? 'hi' : 'mid', crease: 'lo' }));
    boards.push(S(k.slabOf({ x: bx + 2.2, y: b.y + 18, w: 1.4, d: 14, r: 0.3 }, 16, 12, P, 2), { tone: 'mid' }));
    boards.push(S(k.slabOf({ x: bx - 0.6, y: b.y + b.d - 9, w: 3.4, d: 4, r: 0.6 }, 41, 3, P, 2, 0.3), { tone: 'mid' }));
    if (i === 2) for (let f = 0; f < 4; f++) boards.push(S(k.slabOf({ x: bx + 3.6 + f * 1.8, y: b.y + 19, w: 0.9, d: 12, r: 0.2 }, 17, 10, P, 2), { tone: 'lo', crease: 'none' }));
  }
  inner.push(mv([0, 0, 16], boards.join(''), open));
  const front = S(k.slabOf({ x: 39.8, y: b.y + b.d, w: 4.4, d: 5, r: 0.8 }, 0, 3.2, P, 2, 0.3), { tone: 'mid' });
  return box(b, CPU_H, inner.join(''), open, { lift: 120, out: 16, rise: 0 }) + front;
}

function radio(open) {
  const b = RAD, out = [], c = [b.x + b.w / 2, b.y + b.d / 2];
  out.push(plug(c[0], b.y + b.d + 2.5));
  out.push(S(k.slabOf({ x: ANT[0] - 5, y: ANT[1] - 5, w: 10, d: 10, r: 1.5 }, 0, 4, P, 3, 0.4), { tone: 'mid' }));
  out.push(S(k.cylinder(ANT[0], ANT[1], 3.4, 4, 4, P, 24, 0.3), { tone: 'mid' }));
  out.push(S(k.cylinder(ANT[0], ANT[1], 1.1, 8, ANT_TOP - 10, P, 16), { tone: 'hi', crease: 'none' }));
  out.push(S(k.cylinder(ANT[0], ANT[1], 1.8, 62, 3, P, 20, 0.3), { tone: 'mid' }));
  out.push(S(k.cylinder(ANT[0], ANT[1], 2, ANT_TOP - 2, 2.4, P, 20, 0.4), { tone: 'hi', crease: 'lo' }));
  out.push(S(k.slabOf(b, 0, RAD_H - 2.5, P, 4, 0.8), { tone: 'hi', crease: 'lo', inner: L(k.sideSeam(b, 6, P, 4), { tone: 'faint' }) }));
  const z = RAD_H - 2.5;
  out.push(S(k.slabOf(k.insetPlan(b, 3), z, 1, P, 3), { tone: 'lo' }));
  out.push(S(k.slabOf({ x: b.x + 6, y: b.y + 6, w: 6, d: 6, r: 0.6 }, z + 1, 2, P, 2), { tone: 'mid' }), S(k.slabOf({ x: b.x + 15, y: b.y + 6, w: 6, d: 6, r: 0.6 }, z + 1, 2, P, 2), { tone: 'mid' }));
  out.push(S(k.slabOf({ x: b.x + 6, y: b.y + 15, w: 17, d: 8, r: 0.8 }, z + 1, 3, P, 3, 0.3), { tone: 'hi', crease: 'lo' }));
  const lid = S(k.slabOf(b, z, 2.5, P, 4, 0.5), { tone: 'hi', crease: 'lo' }) + L(k.planOutline(k.insetPlan(b, 3), z + 2.5, P, 3), { tone: 'faint' })
    + D(k.corners(b, 2.6).map(([x, y]) => at([x, y, z + 2.5])), { size: 0.45 })
    + S(k.slabOf({ x: b.x + 4, y: b.y + 4, w: 10, d: 10, r: 1 }, z + 2.5, 1.4, P, 3), { tone: 'mid' });
  out.push(mv([0, 0, 38], lid, open));
  return out.join('');
}

// ---------- numbers ----------
const E48 = () => { const p = join(ROOT, 'results', 'E48_sizing.json'); return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8').replace(/\bNaN\b/g, 'null')) : null; };
const n = key => num(PRM[key]);
const t = key => `${fmt(PRM[key].value, PRM[key].digits)}${PRM[key].unit}`;   // plain text for the drawing
function rows() {
  const S48 = E48(), SZ = 'results/E48_sizing.json', sm = S48?.classes?.SMALL, F = S48?.flight;
  const e = (value, unit, digits, flag, src) => num({ value, unit, digits, flag, source: `${SZ}: ${src}` });
  const check = sm && F ? sm.cpu_safety_check_us.p99 * F.factor / 1000 : null;
  return {
    check, sm, F,
    list: [
      ['cameras', 'Stereo cameras on the mast', 'Visual odometry: track the ground between frames.', `Drift ${n('dr_vo')}; ${n('vo_fail')} of updates fail`, 'published'],
      ['star', 'Star tracker', 'Absolute heading from the stars, so the gyros cannot drift.', `Heading to ${n('star_hdg')}, bounded`, 'our design'],
      ['sun', 'Sun sensor', 'Heading from the Sun when it is up; a backup to the star tracker.', `Heading to ${n('sun_hdg')}, sunlit only`, 'published'],
      ['imu', 'IMU: three gyros and accelerometers', 'Turn rate and acceleration between camera frames.', `Heading drift ${n('gyro')} on gyros alone`, 'published'],
      ['radio', 'Ranging radio (UWB)', 'Two-way radio ranges to the base beacons and to other rovers.', `Range error ${n('uwb')} up to ${n('uwb_range')}`, 'published'],
      ['antenna', 'Antenna (1 m) of the coordination radio', 'Carries position reports and the job market.',
        sm ? `${e(sm.link.longest_hop_kbps, ' kbit/s', 1, 'Modelled', 'classes.SMALL.link.longest_hop_kbps')} at the ${e(sm.link.mutual_horizon_m / 1000, ' km', 1, 'Modelled', 'classes.SMALL.link.mutual_horizon_m')} horizon, ${e(sm.link.tx_power_w, ' W', 2, 'Assumed', 'classes.SMALL.link.tx_power_w')}` : 'E48 not available', 'our design'],
      ['clock', 'Clock module', 'A chip-scale atomic clock beside a crystal: time stamps and resyncs.', `Drift: atomic ${n('csac')}, crystal ${n('tcxo')}`, 'published'],
      ['computer', 'Navigation computer', `The flight board (${esc(F?.processor || 'GR740')}) runs our safety program and planner.`,
        sm && F ? `${num({ value: F.memory_mb, unit: ' MB', digits: 0, flag: 'Spec', source: `${SZ}: flight.memory_mb (${F.processor})` })} on board; our program peaks at ${e(sm.peak_memory_mb, ' MB', 2, 'Modelled', 'classes.SMALL.peak_memory_mb')} and one safety check takes ${e(check, ' ms', 0, 'Modelled', 'classes.SMALL.cpu_safety_check_us.p99 × flight.factor')} on the flight core` : 'E48 not available', 'published board, our software'],
    ],
  };
}

function drawing(open) {
  const parts = { cameras: mast(), star: star(open), sun: sun(), imu: imu(open), radio: radio(open), clock: clock(open), computer: computer(open) };
  const sys = { cameras: 'nav', star: 'nav', sun: 'nav', imu: 'nav', radio: 'radio', clock: 'clock', computer: 'cpu' };
  const centre = { cameras: [...MAST, 0], star: [...STAR, 0], sun: [...SUN, 0], imu: [IMU.x + 19, IMU.y + 19, 0], clock: [CLK.x + 20, CLK.y + 15, 0], computer: [CPU.x + 42, CPU.y + 30, 0], radio: [RAD.x + 15, RAD.y + 14, 0] };
  const order = Object.keys(parts).sort((a, b) => depth(centre[a]) - depth(centre[b]));
  const R = rows();
  const lab = labels(P, [
    { id: 'cameras', anchor: [MAST[0] - 30, MAST[1], MAST_TOP + 15], title: 'Stereo cameras', value: `drift ${t('dr_vo')}` },
    { id: 'star', anchor: [STAR[0] + 11, STAR[1], 16], title: 'Star tracker', value: `heading ${t('star_hdg')}` },
    { id: 'sun', anchor: [SUN[0] + 6, SUN[1], 8], title: 'Sun sensor', value: `heading ${t('sun_hdg')}` },
    { id: 'imu', anchor: [IMU.x, IMU.y + 19, 18], title: 'IMU gyros', value: `drift ${t('gyro')}` },
    { id: 'radio', anchor: [RAD.x + RAD.w, RAD.y + 14, 10], title: 'UWB ranging', value: `${t('uwb')} to ${t('uwb_range')}` },
    { id: 'antenna', anchor: [ANT[0], ANT[1], 122], title: 'Antenna, 1 m', value: R.sm ? `${fmt(R.sm.link.longest_hop_kbps, 1)} kbit/s at ${fmt(R.sm.link.mutual_horizon_m / 1000, 1)} km` : '–' },
    { id: 'clock', anchor: [CLK.x + 3, CLK.y + CLK.d, 1.5], title: 'Atomic clock', value: t('csac').replace(' a day', '/day') },
    { id: 'computer', anchor: [CPU.x + 3, CPU.y + CPU.d, 1.5], title: 'Computer', value: R.check ? `${fmt(R.check, 0)} ms per safety check` : '–' },
  ], H);
  const body = [base(), cables(), clips(), ...order.map(id => `<g class="nv-part" data-part="${id}" data-sys="${sys[id]}"${id === 'radio' ? ' data-also="antenna"' : ''}>${parts[id]}</g>`), lab].join('');
  return { body, R };
}

const LABEL = 'A rover navigation deck on a bench: a mast with two cameras at the back left, a star tracker and a small sun sensor at the back right, the IMU in the middle, a clock module and the navigation computer at the front, and the ranging radio with its antenna at the front right, all cabled to the computer. Opening the figure lifts the lids and moves the side panels away. Labels give each part\'s key number.';

export function navStackFigure() {
  const { body, R } = drawing(false);
  const svg = k.figureSvg({ width: W, height: H, label: LABEL, body });
  return plate({ kind: 'nav', fig: 'Fig 1b', title: 'Navigation stack', hint: 'Pick a part · open it', readout: R.list[0][1],
    keys: [{ mark: 'lit', label: 'The part picked' }, { mark: 'raised', label: 'Sizes are schematic; the numbers are not' }],
    caption: '"Published" means the number is the maker\'s or a measured test; "our design" means we chose or assumed it.',
    svg, controls: `<button type="button" class="ui-btn an-open" aria-pressed="false">Open the boxes</button>`, list: partList(R.list, 'Parts of the navigation stack') });
}
export const navStackStill = () => still(drawing(true).body, W, H, LABEL);
