// Encounters for the /atc/ sandbox (F-54), no DOM and no three: B-78's 20 stored encounters (the parity set,
// data/atc/encounter_fixtures, staged to atc/encounters/) checked against the JS safety program, and B-83's sandbox set
// (data/atc/encounter_sandbox, staged to atc/sandbox/) replayed. Geometry follows lunarsim/atc/encounter.py: a vehicle
// is its front-bumper arc position s on a fixed polyline, its body trails along the path behind the front, two discs per
// vehicle for separation. The same file runs in the browser, in the node test and in prepare-data (the build-time
// parity summary), so the numbers on the page come from the code that runs there.
import { safetyMove, MOVING_MS } from './safety.js';

export const VEH_L = 4.0, VEH_W = 2.3, LANE_W = 3.5, CREW_R = 0.5;
const OFF = (VEH_L - VEH_W) / 2;
const inf = x => (x === null || x === undefined ? Infinity : x);

// ---------- reading a fixture (gzip JSON; a server may already have undone the gzip) ----------
export async function readFixture(bytes) {
  let u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  if (u8[0] === 0x1f && u8[1] === 0x8b) {
    const out = new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'));
    u8 = new Uint8Array(await new Response(out).arrayBuffer());
  }
  return JSON.parse(new TextDecoder().decode(u8));
}

// ---------- paths ----------
export function makePath(pts) {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const u = [];
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i][0] - pts[i - 1][0], dy = pts[i][1] - pts[i - 1][1], l = Math.hypot(dx, dy);
    u.push(l > 1e-9 ? [dx / l, dy / l] : (u[i - 2] || [1, 0]));
  }
  if (!u.length) u.push([1, 0]);
  return { pts, cum, u, length: cum[cum.length - 1] };
}
// position and unit heading at arc s (before the start: the first point; past the end: straight on along the last piece)
export function pathAt(P, s) {
  const n = P.pts.length;
  let k = 0;
  while (k < n - 2 && P.cum[k + 1] <= s) k++;
  const d = Math.max(s - P.cum[k], 0), u = P.u[k];
  return [P.pts[k][0] + u[0] * d, P.pts[k][1] + u[1] * d, u[0], u[1]];
}
// body centre, the two disc centres and the heading (lat: sideways offset, left positive)
export function body(P, s, lat = 0) {
  const at = d => { const [x, y, ux, uy] = pathAt(P, s - d); return [x - uy * lat, y + ux * lat, ux, uy]; };
  return { c: at(VEH_L / 2), f: at(VEH_L / 2 - OFF), r: at(VEH_L / 2 + OFF) };
}
// ---------- one step of the kinematics (encounter.py §physics: friction limit, no reversing) ----------
export function kinStep(s, v, a, dt, theta, mu, g) {
  const th = theta * Math.PI / 180;
  const bPhys = mu * g * Math.cos(th) - g * Math.sin(th);
  const aa = Math.max(a, -bPhys);
  const t = aa < 0 ? Math.min(dt, v / -aa) : dt;
  return [s + Math.max(v * t + 0.5 * aa * t * t, 0), Math.max(v + aa * dt, 0)];
}

const moveOf = (m, i, dt, g) => ({
  v: m.v[i], a_prop: m.a_prop[i], dt, theta: m.theta[i], mu: m.mu[i], v_class: m.v_class[i], sight: inf(m.sight[i]),
  gap_lead: inf(m.gap_lead[i]), v_lead: m.v_lead[i], d_stop: inf(m.d_stop[i]), d_crew: inf(m.d_crew[i]),
  d_crew_any: inf(m.d_crew_any[i]), must_exit: !!m.must_exit[i], a_max: 0.2, g,
});
export const gravityOf = doc => doc.constants?.G_MOON ?? 1.62;

// ---------- parity with Python on one stored encounter ----------
// a: the JS safety program on each step's stored inputs vs the stored output; s, v: one kinematic step from the
// previous stored state with the stored output vs the next stored state. A vehicle that has finished (or come to rest
// at the end of a type-1 encounter) is held at rest by the simulator: counted apart, never as a pass of the kinematics.
export function parity(doc, tol) {
  const dt = doc.dt, g = gravityOf(doc), sp = doc.spec;
  const L = sp.paths.map(p => makePath(p).length);
  const r = { file: doc.file, type: doc.type, planner: doc.planner, steps: doc.steps.length, checks: 0, maxDa: 0, maxDs: 0, maxDv: 0, held: 0, fails: 0, firstFail: null };
  let s = sp.s0.slice(), v = sp.v0.slice();
  for (const st of doc.steps) {
    const m = st.move;
    for (let i = 0; i < m.v.length; i++) {
      const out = safetyMove(moveOf(m, i, dt, g));
      const da = Math.abs(out.a - st.a[i]);
      const [s1, v1] = kinStep(s[i], v[i], st.a[i], dt, m.theta[i], m.mu[i], g);
      let ds = Math.abs(s1 - st.s[i]), dv = Math.abs(v1 - st.v[i]);
      const held = st.v[i] === 0 && Math.abs(st.s[i] - s[i]) < 1e-9 && (s[i] >= L[i] - 0.01 || v[i] <= MOVING_MS) && (ds > tol.s || dv > tol.v);
      if (held) { r.held++; ds = dv = 0; }
      r.checks++;
      r.maxDa = Math.max(r.maxDa, da); r.maxDs = Math.max(r.maxDs, ds); r.maxDv = Math.max(r.maxDv, dv);
      if (da > tol.a || ds > tol.s || dv > tol.v) { r.fails++; r.firstFail ??= { t: st.t, vehicle: i, da, ds, dv }; }
    }
    s = st.s; v = st.v;
  }
  r.pass = r.fails === 0;
  return r;
}

// ---------- the replay (B-83's sandbox set) ----------
// Each encounter of data/atc/encounter_sandbox holds two runs recorded by the simulator from the same start: shield_on
// (every move through the safety program) and shield_off (each proposal applied as made). Steps are stored at 10 Hz,
// thinned in long runs (the stride is in the file; the first intervention steps are always kept), so frames are not
// evenly spaced. Separation here is per shown frame; the whole run's record (closest approach, violations, outcome) is
// the simulator's own, read from the file.
export const PLANNERS = ['nominal', 'random', 'adversarial'];

export function replayTrace(doc, which = 'shield_on') {
  const sp = doc.spec, V = sp.paths.length, run = doc[which];
  const P = sp.paths.map(makePath);
  const [leadV, leadT] = sp.lead_brake || [-1, Infinity], [faultV, faultT] = sp.fault_stop || [-1, Infinity];
  const done = sp.s0.map((x, i) => x >= P[i].length - 0.01), tDone = new Array(V).fill(Infinity);
  const frames = [{ t: 0, s: sp.s0.slice(), v: sp.v0.slice(), done: done.slice(), fault: new Array(V).fill(false),
    bodies: sp.s0.map((x, i) => body(P[i], x, 0)), crew: (sp.crew || []).map(() => null), verdicts: null, applied: null }];
  for (const st of run.steps) {
    const t = st.t, s = st.s, v = st.v;
    // finished: the end of its path, or (type 1) at rest once the braking leader has stopped. The simulator drops a
    // finished vehicle from the encounter (no leader for others, no separation), so the scene removes it too
    const leadStopped = sp.stop_is_goal && leadV >= 0 && t > leadT && v[leadV] <= MOVING_MS;
    for (let i = 0; i < V; i++) if (!done[i] && (s[i] >= P[i].length - 0.01 || (leadStopped && v[i] <= MOVING_MS))) { done[i] = true; tDone[i] = t; }
    // sideways offset (a drifting vehicle) from the stored body centre
    const bodies = s.map((x, i) => {
      const [px, py, ux, uy] = pathAt(P[i], x - VEH_L / 2), [cx, cy] = st.xy[i];
      return body(P[i], x, (cy - py) * ux - (cx - px) * uy);
    });
    frames.push({ t, s, v, done: done.slice(), fault: s.map((_, i) => i === faultV && t >= faultT), bodies, crew: st.crew || [],
      verdicts: s.map((_, i) => ({ prop: st.a_prop[i], a: st.a[i], rule: st.rule[i], modified: st.modified[i] })), applied: st.a });
  }
  let minSep = Infinity, contactAt = null, n = 0;
  for (const f of frames) {
    // nearest two live vehicles at this frame (two discs each, minus the width) and the nearest crew
    f.sep = Infinity; f.crewGap = Infinity;
    for (let i = 0; i < V; i++) {
      if (f.done[i]) continue;
      for (let j = i + 1; j < V; j++) if (!f.done[j]) for (const a of ['f', 'r']) for (const b of ['f', 'r']) f.sep = Math.min(f.sep, Math.hypot(f.bodies[i][a][0] - f.bodies[j][b][0], f.bodies[i][a][1] - f.bodies[j][b][1]) - VEH_W);
      for (const c of f.crew) if (c) for (const a of ['f', 'r']) f.crewGap = Math.min(f.crewGap, Math.hypot(f.bodies[i][a][0] - c[0], f.bodies[i][a][1] - c[1]) - (VEH_W / 2 + CREW_R));
    }
    minSep = Math.min(minSep, f.sep); f.minSep = minSep;
    if (f.sep < 0 && contactAt === null) contactAt = f.t;
    if (f.verdicts) n += f.verdicts.filter((x, i) => x.modified && !f.done[i]).length;
    f.n = n;
  }
  return { which, mode: which === 'shield_on' ? 'on' : 'off', outcome: run.outcome, frames, paths: P, contactAt, tDone };
}

// the JS safety program on the stored inputs ('move', every 20th step) against the stored output; the sandbox set
// stores values to 4 decimals, so agreement is to 1e-3 m/s2 (the 20 fixtures above hold the full-precision parity)
export function checkMoves(doc, which = 'shield_on', tol = 1e-3) {
  const g = gravityOf(doc), r = { n: 0, agree: 0, maxDa: 0 };
  for (const st of doc[which].steps) {
    if (!st.move) continue;
    for (let i = 0; i < st.a.length; i++) {
      const out = safetyMove(moveOf(st.move, i, doc.dt, g));
      const want = which === 'shield_on' ? st.a[i] : null;
      if (want === null) continue;
      const d = Math.abs(out.a - want); r.n++; r.maxDa = Math.max(r.maxDa, d); if (d <= tol) r.agree++;
    }
  }
  return r;
}

// time lost against driving at the class speed from the start: t - (s - s0) / v_class (at the finish this is
// encounter.py's delay, t_done - t_free)
export function delayAt(doc, frame, i, tDone = Infinity) {
  const sp = doc.spec, t = Math.min(frame.t, tDone);
  return t - (Math.min(frame.s[i], makePath(sp.paths[i]).length) - sp.s0[i]) / sp.v_class[i];
}
