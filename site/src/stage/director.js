// Camera director on camera-controls (MIT): named shots, smooth moves (SmoothDamp), orbit limits, instant cuts under
// prefers-reduced-motion, keyboard orbit/zoom on the canvas, and button-friendly nudge()/zoom() so nothing needs a
// drag (WCAG 2.5.7). update(dt) returns true while the camera moves, which keeps the render loop awake.
import CameraControls from 'camera-controls';
import { Vector2, Vector3, Vector4, Quaternion, Matrix4, Spherical, Box3, Sphere, Raycaster } from 'three';
import { reducedMotion } from '../ui/dom.js';

CameraControls.install({ THREE: { Vector2, Vector3, Vector4, Quaternion, Matrix4, Spherical, Box3, Sphere, Raycaster } });
const DEG = Math.PI / 180;

export function createDirector(camera, dom, { onWake = () => {} } = {}) {
  const controls = new CameraControls(camera, dom);
  controls.smoothTime = 0.45; controls.draggingSmoothTime = 0.12; controls.restThreshold = 0.002;
  const shots = new Map();
  let auto = 0, paused = false;
  for (const ev of ['controlstart', 'control', 'update', 'transitionstart']) controls.addEventListener(ev, onWake);

  const api = {
    controls, shots,
    // shot(name, {position: [x,y,z], target: [x,y,z]}) or shot(name, box3, {padding}) to frame a box
    shot(name, spec) { shots.set(name, spec); return api; },
    async go(name, { instant = false } = {}) {
      const s = shots.get(name); if (!s) throw new Error(`director: no shot ${name}`);
      const smooth = !instant && !reducedMotion();
      controls.normalizeRotations();
      onWake();
      if (s.box) return controls.fitToBox(s.box, smooth, s.padding || {});
      return controls.setLookAt(...s.position, ...s.target, smooth);
    },
    limits({ minDistance, maxDistance, minPolar, maxPolar, boundary } = {}) {
      if (minDistance !== undefined) controls.minDistance = minDistance;
      if (maxDistance !== undefined) controls.maxDistance = maxDistance;
      if (minPolar !== undefined) controls.minPolarAngle = minPolar * DEG;
      if (maxPolar !== undefined) controls.maxPolarAngle = maxPolar * DEG;
      if (boundary) controls.setBoundary(boundary);
    },
    nudge(azimuthDeg, polarDeg = 0) { onWake(); controls.rotate(azimuthDeg * DEG, polarDeg * DEG, !reducedMotion()); },
    zoom(factor) { onWake(); controls.dolly(controls.distance * (1 - 1 / factor), !reducedMotion()); },
    autoRotate(degPerSecond) { auto = degPerSecond; if (auto) onWake(); },
    get autoRotating() { return !!auto && !paused && !reducedMotion(); },
    pause(v) { paused = v; if (v) controls.stop?.(); },
    update(dt) {
      if (auto && !paused && !reducedMotion()) controls.azimuthAngle += auto * DEG * dt;
      return controls.update(dt);
    },
    // arrow keys orbit, +/- zoom, Home goes to the 'home' shot; only while the canvas has focus
    bindKeys(el) {
      el.addEventListener('keydown', e => {
        const k = e.key, step = e.shiftKey ? 30 : 10;
        const act = { ArrowLeft: () => api.nudge(-step), ArrowRight: () => api.nudge(step), ArrowUp: () => api.nudge(0, -step / 2),
          ArrowDown: () => api.nudge(0, step / 2), '+': () => api.zoom(1.25), '=': () => api.zoom(1.25), '-': () => api.zoom(0.8),
          Home: () => shots.has('home') && api.go('home') }[k];
        if (act) { e.preventDefault(); act(); }
      });
    },
    dispose() { controls.dispose(); },
  };
  return api;
}
