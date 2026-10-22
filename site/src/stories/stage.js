// The 3D side of /stories/ (F-38), loaded when the visitor enters the 3D view. One stage per story, built from the
// story's scene kind: "world:<package>" uses the /world/ scene (scene packages, B-31) and "lander:<cls>/<pilot>/<pick>"
// the lander lab's scene (recorded descents, B-33). apply(step) loads the step's package or episode, picks the moment
// its modes ask for, moves the camera to its shot and plays when the step says so. Reduced motion: cuts, no playing.
// Shots: overview, pads (camera.target or the next landing's pad), base, horizon (low at the base, looking at Earth),
// descent and touchdown (lander). Modes shown: play, keepout (a keep-out window), touchdowns and ejecta (a landing at
// the pad), queues (the busiest hour at the target), earth / earth_link (Earth low over the horizon). Modes the stage
// does not draw (routes are always drawn; job_rule follows the scene; colour_by, bids, relay) leave the view as is.
import { reducedMotion } from '../ui/dom.js';
import { loadTrajectories, episodeView } from '../lander/trajectories.js';
import { loadScene } from '../world/scene-data.js';

const BASE = import.meta.env.BASE_URL, TRAJ = BASE + 'lab/policies/trajectories-v1.json';
export const SUPPORTED_MODES = ['play', 'keepout', 'touchdowns', 'ejecta', 'queues', 'earth', 'earth_link', 'routes', 'job_rule'];

export async function createStoryStage({ kind, canvas, labelsHost, tier, fetchFn = fetch, onStatus = () => {} }) {
  return kind === 'lander' ? landerStage({ canvas, labelsHost, tier, fetchFn, onStatus }) : worldStage({ canvas, labelsHost, tier, fetchFn, onStatus });
}

// ---------- world scenes ----------
async function worldStage({ canvas, labelsHost, tier, fetchFn, onStatus }) {
  const [{ createWorldScene }, traj] = await Promise.all([import('../world/v2-scene.js'), loadTrajectories(TRAJ, { fetchFn: fetchFn('landing recordings') }).catch(() => null)]);
  const sc = await createWorldScene({ canvas, labelsHost, tier, fetchFn: fetchFn('catalogue'), onStatus });
  sc.stage.director.bindKeys(canvas);
  sc.stage.director.limits({ minDistance: 20, maxDistance: 22000, maxPolar: 88 });
  const cache = new Map(), time = { t: 0, playing: false, gen: 0 };
  let cur = null;   // {id, pkg, chunks}
  async function open(id) {
    if (!cache.has(id)) cache.set(id, (async () => {
      const pkg = await loadScene(`${BASE}scenes/${id}/`, { fetchFn: fetchFn('the year') });
      const chunks = await Promise.all(pkg.index.chunks.map((_, k) => pkg.chunk(k)));
      pkg.index.landings.sort((a, b) => a.t_h - b.t_h);
      return { id, pkg, chunks };
    })());
    const P = await cache.get(id);
    if (cur?.id !== id) { cur = P; sc.setPackage(P.pkg, traj); sc.shots(); }
  }
  const hourly = t => cur.pkg.hourly(cur.chunks[cur.pkg.chunkIndex(t)], t);
  const setTime = t => { time.t = Math.max(0, Math.min(cur.pkg.index.horizon_h - 0.01, t)); sc.setTime(time.t, cur.chunks[cur.pkg.chunkIndex(time.t)]); };
  const nightAt = t => cur.pkg.index.nights.some(([a, b]) => t >= a && t < b);

  // the moment a step's modes ask for (deterministic, so Back and Next show the same view)
  function moment(step) {
    const idx = cur.pkg.index, m = step.modes || {}, target = step.camera?.target, pad = target?.startsWith('PAD') ? target : null;
    const lands = idx.landings.filter(L => L.ok && (!pad || L.pad === pad) && !nightAt(L.t_h));
    if (m.keepout) { const w = idx.keepout_windows.find(k => (!pad || k[2] === pad) && !nightAt(k[0])); if (w) return w[0] + 0.3 * (w[1] - w[0]); }
    if (m.touchdowns || m.ejecta) { const L = lands[0] || idx.landings[0]; if (L) return L.t_h - 0.03; }
    if (m.queues) {   // the busiest daylight hour at the target site (sampled every 3 h)
      const site = target || 'PAD_A'; let best = 0, bt = 0;
      for (let t = 0; t < idx.horizon_h; t += 3) { if (nightAt(t)) continue; const n = hourly(t).waiting[site]?.items || 0; if (n > best) { best = n; bt = t; } }
      if (best) return bt;
    }
    if ((m.earth || m.earth_link) && step.camera?.shot === 'horizon') {   // Earth low over the horizon, in daylight, far from the sun's bearing (lit, and the camera looks down-sun)
      let best = -1, bt = null;
      for (let t = 0; t < idx.horizon_h; t += 1) {
        const hr = hourly(t); if (nightAt(t) || !(hr.earth_el_deg > 0.5 && hr.earth_el_deg < 5)) continue;
        const sep = Math.abs(((hr.earth_bearing_deg - hr.sun_az_deg) % 360 + 540) % 360 - 180);
        if (sep > best) { best = sep; bt = t; } if (sep > 160) break;
      }
      if (bt !== null) return bt;
    }
    const L0 = lands[0] || idx.landings[0];
    return L0 ? Math.max(0, L0.t_h - 0.1) : 0;
  }
  function shot(cam, instant) {
    const name = cam?.shot || 'overview', idx = cur.pkg.index;
    if (name === 'pads') {
      const pad = cam.target?.startsWith('PAD') ? cam.target : (idx.landings.find(L => L.t_h > time.t)?.pad || 'PAD_A');
      return sc.frameAt(sc.sitePos(pad), 600, 22, 35, instant);
    }
    if (name === 'horizon') {   // low beside the base, looking out at Earth over the terrain
      const hr = hourly(time.t), a = (hr.earth_bearing_deg || 0) * Math.PI / 180, b = sc.sitePos('BASE'), dx = Math.sin(a), dz = -Math.cos(a);
      const el = Math.max(0.5, hr.earth_el_deg || 2) * Math.PI / 180, pos = { x: b.x - dx * 160, y: b.y + 14, z: b.z - dz * 160 };
      return sc.stage.director.controls.setLookAt(pos.x, pos.y, pos.z, pos.x + dx * 1000, pos.y + Math.tan(el) * 1000, pos.z + dz * 1000, !instant);
    }
    if (cam?.target && idx.sites[cam.target] && name !== 'overview') return sc.frameAt(sc.sitePos(cam.target), 700, 25, 35, instant);
    return sc.go(['overview', 'base', 'legs', 'night'].includes(name) ? name : 'overview', instant);
  }
  // playing: 6 h a second, slowed to the descent's pace while a lander comes down (a frame must not step over it)
  function play() {
    const gen = ++time.gen; time.playing = true;
    sc.stage.animate(dt => {
      if (gen !== time.gen || !time.playing) return false;
      let next = time.t + dt * (sc.activeLandings.length ? 0.012 : 6);
      if (!sc.activeLandings.length && sc.nextLandingStart) { const s0 = sc.nextLandingStart(time.t); if (s0 <= next) next = s0 + 1e-4; }
      setTime(next);
      return time.t < cur.pkg.index.horizon_h - 0.02;
    });
  }
  return {
    sc, kind: 'world',
    async apply(step, story, { instant: cut = false } = {}) {
      stop();
      await open((step.scene || story.scene).split(':')[1]);
      const instant = cut || reducedMotion();
      setTime(moment(step)); shot(step.camera, instant); setTime(time.t);   // the camera glides on its own; the first step cuts (the door is still shut)
      if ((step.modes || {}).play && !instant) play();
      return { t: time.t, night: nightAt(time.t) };
    },
    stop, dispose() { stop(); sc.dispose?.(); },
  };
  function stop() { time.playing = false; time.gen++; }
}

// ---------- the lander lab's recorded descents ----------
async function landerStage({ canvas, labelsHost, tier, fetchFn, onStatus }) {
  const [mod, doc] = await Promise.all([import('../lander/lab3d-scene.js'), loadTrajectories(TRAJ, { fetchFn: fetchFn('descent recordings') })]);
  const sc = await mod.createLanderScene({ canvas, labelsHost, tier, fetchFn: fetchFn('catalogue'), onStatus });
  sc.stage.director.bindKeys(canvas);
  sc.stage.director.limits({ minDistance: 3, maxDistance: 2500, maxPolar: 95 });
  const time = { t: 0, gen: 0 };
  let key = '', view = null;
  function stop() { time.gen++; }
  return {
    sc, kind: 'lander',
    async apply(step, story) {
      stop();
      const [cls, pilot, pick] = (step.scene || story.scene).split(':')[1].split('/');
      const p = doc.pilots.find(q => q.cls === cls && q.pilot === pilot);
      if (!p) throw new Error(`no recorded pilot ${pilot} for ${cls}`);
      const ep = p.episodes.find(e => e.pick === pick) || p.episodes[0];
      if (`${cls}/${pilot}/${ep.pick}` !== key) { key = `${cls}/${pilot}/${ep.pick}`; view = episodeView(ep); sc.setEpisode({ cls, view, seed: 1 }); sc.setShow({ guidance: false, thrust: false, sensors: false }); sc.lightForSide(); }
      const touch = step.camera?.shot === 'touchdown', instant = reducedMotion();
      time.t = touch ? Math.max(0, view.tEnd - 3) : 0;
      sc.setTime(time.t); sc.setView('side', true); sc.setTime(time.t);   // touchdown: the side view at the end of the descent (the pad camera looks into the glare)
      if (!instant) {   // the descent is the content: it plays at real time, then holds on the ground
        const gen = ++time.gen;
        sc.stage.animate(dt => { if (gen !== time.gen) return false; time.t = Math.min(view.tEnd + 3, time.t + dt); sc.setTime(time.t); return time.t < view.tEnd + 3; });
      }
      return { t: time.t, outcome: view.outcome, tEnd: view.tEnd };
    },
    stop, dispose() { stop(); sc.dispose?.(); },
  };
}
