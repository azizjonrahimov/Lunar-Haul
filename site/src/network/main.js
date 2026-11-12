// F-61: /network/. The text and its numbers are built into the HTML (<!--@nw:key-->, lib/network.mjs); the three figures
// load their data and code when their section nears the screen; the "where it runs" deck comes from the cutaway loader.
import './network.css';
import { mountSlots } from '../protocol/anatomy-loader.js';
import { upgradeFlags } from '../ui/tooltip.js';

const BASE = import.meta.env.BASE_URL;
const json = f => fetch(`${BASE}network/${f}`).then(r => { if (!r.ok) throw new Error(`${f}: ${r.status}`); return r.json(); });
const loaders = {
  'nw-landscape': host => Promise.all([fetch(`${BASE}protocol/b99/b96_landscape.json`).then(r => { if (!r.ok) throw new Error(`b96_landscape.json: ${r.status}`); return r.json(); }), import('./landscape.js')]).then(([D, m]) => { if (D.format !== 'lunarsim-protocol-data' || !D.landscape) throw new Error('b96_landscape.json: no landscape'); return m.mountLandscape(host, D.landscape); }),   // F-65: B-99's copy
  'nw-inside': host => Promise.all([json('integrity_net_v1.json'), json('integrity_net_v1.check.json'), import('./inside.js')]).then(([p, c, m]) => m.mountInside(host, p, c)),
  'nw-bars': host => Promise.all([json('e56.json'), import('./bars.js')]).then(([E, m]) => m.mountBars(host, E)),
};
const io = new IntersectionObserver(entries => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    io.unobserve(e.target);
    const host = e.target;
    loaders[host.id](host).then(() => host.querySelector(':scope > p.small.muted')?.remove())
      .catch(err => { host.innerHTML = `<p class="stub">This figure could not load (${err.message}).</p>`; });
  }
}, { rootMargin: '300px 0px' });
for (const id of Object.keys(loaders)) { const el = document.getElementById(id); if (el) io.observe(el); }
mountSlots();
upgradeFlags(document.querySelector('main'));
