// On-screen camera buttons for a 3D view (F-40, WCAG 2.5.7): every move the canvas offers by dragging, without a drag:
// orbit left, right, up and down and zoom, as the arrow and +/- keys do on the focused canvas. Takes anything with
// nudge(azimuthDeg, polarDeg) and zoom(factor), e.g. the stage director. The look of the vehicles page's camera group;
// laid out as zoom over an arrow cluster, in reading order (+ ↑ − / ← ↓ →) so the tab order matches what is seen.
import { h } from './dom.js';

export function viewPad(cam, { label = 'Camera', place = '' } = {}) {
  const b = (text, aria, fn) => h('button', { class: 'ui-iconbtn', type: 'button', 'aria-label': aria, title: aria, onclick: fn }, text);
  return h('div', { class: `ui-viewpad ui-glass ${place}`.trim(), role: 'group', 'aria-label': label },
    b('+', 'Zoom in', () => cam.zoom(1.25)), b('↑', 'Orbit up', () => cam.nudge(0, -10)), b('−', 'Zoom out', () => cam.zoom(0.8)),
    b('←', 'Orbit left', () => cam.nudge(-20)), b('↓', 'Orbit down', () => cam.nudge(0, 10)), b('→', 'Orbit right', () => cam.nudge(20)));
}
