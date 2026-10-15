// State of the base at sim time t (hours), derived from a trace only. Pure and DOM-free (tested in Node).
// Every quantity is either read from the trace or a direct count over it; nothing is invented. Fields a v1 trace
// cannot supply (energy, interventions, sheltering) come back null and the UI shows them as unavailable.

const LANDED_SHOW_H = 72;          // a lander stays on its pad in the view for 72 h, as the 2D map does
export const DESCENT_S = 30;       // synthetic vertical approach when the trace has no descent profile
export const DESCENT_FROM_M = 500;

const upper = (arr, x) => { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] <= x) lo = m + 1; else hi = m; } return lo; };

export function indexTrace(tr) {
  const byVeh = new Map(tr.vehicles.map(v => [v.id, []]));
  for (const j of tr.jobs) for (const id of j.team) byVeh.get(id).push(j);   // jobs are sorted by t0
  const start = new Map();
  for (const [id, js] of byVeh) start.set(id, js.length && js[0].segments.length ? js[0].segments[0][0] : 'DEPOT');
  const delivered = tr.cargo.filter(c => c.tDelivered !== null).sort((a, b) => a.tDelivered - b.tDelivered);
  const delT = delivered.map(c => c.tDelivered), delKg = []; let acc = 0; for (const c of delivered) { acc += c.mass; delKg.push(acc); }
  const jobT0 = tr.jobs.map(j => j.t0), landT = tr.landings.map(l => l.t);
  const hasEnergy = tr.jobs.some(j => j.energy !== null), hasInterv = tr.jobs.some(j => j.interventions !== null);
  const nightOps = new Map(tr.vehicles.map(v => [v.id, v.nightOps]));
  return { byVeh, start, delT, delKg, jobT0, landT, hasEnergy, hasInterv, nightOps };
}

/* descent duration in hours: the trace's profile (descent[] times in seconds), else the synthetic 30 s approach */
export const descentH = l => l.descent ? Math.max(1, l.descent[l.descent.length - 1][0] - l.descent[0][0]) / 3600 : DESCENT_S / 3600;

export const isNight =(tr, t) => tr.nights.some(([a, b]) => t >= a && t < b);

/* vehicle state at t: {id, at|from,to,f, status, loadKg, job} ; status: driving | handling | idle | parked-night | stranded-night */
export function vehicleState(tr, ix, v, t, night) {
  const js = ix.byVeh.get(v.id); let lo = 0, hi = js.length;
  while (lo < hi) { const m = (lo + hi) >> 1; if (js[m].t0 <= t) lo = m + 1; else hi = m; }
  const last = lo - 1, job = last >= 0 ? js[last] : null;
  if (job && t < job.t1) {
    for (const s of job.segments) {
      if (t >= s[2] && t <= s[3]) {
        const moving = s[0] !== s[1], f = moving ? (t - s[2]) / Math.max(1e-9, s[3] - s[2]) : 0;
        const status = moving ? (night && !v.nightOps ? 'stranded-night' : 'driving') : 'handling';
        return { id: v.id, from: s[0], to: s[1], f, status, loadKg: s[4], job };
      }
    }
    const seg = job.segments.filter(s => s[2] <= t).pop() || job.segments[0];
    return { id: v.id, from: seg ? seg[1] : ix.start.get(v.id), to: seg ? seg[1] : ix.start.get(v.id), f: 0, status: 'handling', loadKg: 0, job };
  }
  // between jobs: at the end of the last finished job
  let at = ix.start.get(v.id);
  for (let k = last; k >= 0; k--) { const sg = js[k].segments; if (sg.length && js[k].t1 <= t) { at = sg[sg.length - 1][1]; break; } }
  return { id: v.id, from: at, to: at, f: 0, status: night && !v.nightOps ? 'parked-night' : 'idle', loadKg: 0, job: null };
}

export function snapshot(tr, ix, t) {
  const night = isNight(tr, t);
  const vehicles = tr.vehicles.map(v => vehicleState(tr, ix, v, t, night));
  const waiting = {}; let waitKg = 0, waitN = 0;
  for (const c of tr.cargo) if (c.tReady <= t && (c.tPicked === null || c.tPicked > t) && !c.stranded) {
    const w = waiting[c.origin] || (waiting[c.origin] = { n: 0, kg: 0 }); w.n++; w.kg += c.mass; waitKg += c.mass; waitN++;
  }
  const nDel = upper(ix.delT, t), delKg = nDel ? ix.delKg[nDel - 1] : 0;
  let energy = null, interv = null;
  if (ix.hasEnergy || ix.hasInterv) {
    energy = ix.hasEnergy ? 0 : null; interv = ix.hasInterv ? 0 : null;
    for (const j of tr.jobs) { if (j.t0 > t) break; const f = Math.min(1, (t - j.t0) / Math.max(1e-9, j.t1 - j.t0));
      if (energy !== null && j.energy !== null) energy += j.energy * f; if (interv !== null && j.interventions !== null) interv += j.interventions * (j.t1 <= t ? 1 : 0); }
  }
  const plume = tr.plumeWindows.filter(p => t >= p.t0 && t < p.t1);
  const shelterSet = new Set(tr.shelters.map(s => (typeof s === 'string' ? s : s.site || s.id)));
  const sheltering = tr.meta.version >= 2 && plume.length ? vehicles.filter(s => s.status !== 'driving' && shelterSet.has(s.to)).length : null;
  const landers = [];
  for (const l of tr.landings) {
    const dh = descentH(l);
    if (t >= l.t - dh && t < l.t + LANDED_SHOW_H) landers.push({ landing: l, phase: t < l.t ? 'descent' : 'landed', fDescent: t < l.t ? 1 - (l.t - t) / dh : 1, secToTouchdown: (l.t - t) * 3600 });
  }
  const fleetCost = tr.summary && Number.isFinite(tr.summary.fleet_cost_musd) ? tr.summary.fleet_cost_musd * Math.min(1, t / tr.horizon) : null;
  return {
    t, night, vehicles, waiting, waitKg, waitN, deliveredN: nDel, deliveredKg: delKg,
    tripsStarted: upper(ix.jobT0, t), landingsSoFar: upper(ix.landT, t), landingsTotal: tr.landings.length,
    busy: vehicles.filter(s => s.status === 'driving' || s.status === 'handling' || s.status === 'stranded-night').length,
    parkedNight: vehicles.filter(s => s.status === 'parked-night').length, strandedNight: vehicles.filter(s => s.status === 'stranded-night').length,
    sheltering, energyKwh: energy, interventions: interv, fleetCostMusd: fleetCost, plume, landers,
  };
}

/* the step list: first landing, first night, first stand-down (null when the trace has none) */
export function steps(tr) {
  const first = tr.landings[0], night = tr.nights[0], plume = tr.plumeWindows[0];
  return [
    { id: 'landing', label: 'First landing', t: first ? Math.max(0, first.t - (first.descent ? 0.6 : 0.67) * descentH(first)) : null, focus: first ? first.pad : null },
    { id: 'night', label: 'First night', t: night ? night[0] + 0.5 : null, focus: 'BASE' },
    { id: 'standdown', label: 'First stand-down', t: plume ? plume.t0 + 0.25 : null, focus: plume ? plume.pad : null },
  ];
}
