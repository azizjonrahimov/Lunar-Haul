// "Look inside" (F-51 part 4): the /vehicles/ viewer for one vehicle in a side panel, opened from /world/ and the
// stories when the visitor clicks a vehicle. The panel is a labelled dialog with the viewer in an iframe
// (/vehicles/?v=<id>&embed=1&view=cutaway: no site chrome, the 3D view starts by itself); Escape or Close shuts it
// and focus returns to where it was. Loaded on the first click, so pages pay nothing until then.
import './look-inside.css';

const BASE = import.meta.env.BASE_URL;
let panel = null, back = null;

export function lookInside(id, { name = id, view = 'cutaway' } = {}) {
  close();
  back = document.activeElement;
  const btn = Object.assign(document.createElement('button'), { type: 'button', className: 'ui-btn', textContent: 'Close' });
  const head = Object.assign(document.createElement('div'), { className: 'ui-inside-head' });
  const title = Object.assign(document.createElement('h2'), { className: 'ui-inside-title', textContent: `Look inside: ${name}` });
  const link = Object.assign(document.createElement('a'), { href: `${BASE}vehicles/?v=${encodeURIComponent(id)}&view=${view}`, textContent: 'Open in the vehicle viewer', className: 'small' });
  head.append(title, link, btn);
  const frame = Object.assign(document.createElement('iframe'), { src: `${BASE}vehicles/?v=${encodeURIComponent(id)}&embed=1&view=${view}`, title: `The vehicle viewer: ${name}` });
  panel = Object.assign(document.createElement('aside'), { className: 'ui-inside' });
  panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', `Look inside: ${name}`);
  panel.append(head, frame);
  btn.addEventListener('click', close);
  panel.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); close(); } });
  document.body.append(panel);
  btn.focus();
}
export function close() {
  if (!panel) return;
  panel.remove(); panel = null;   // the iframe goes with it, and its WebGL context with it
  back?.focus?.({ preventScroll: true }); back = null;
}
