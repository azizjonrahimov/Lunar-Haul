// /protocol/: the page script. The eight figures (figures.js, F-60) load when the first of them nears the screen and draw
// as each host comes close; the cutaways (Fig 1b-1d, F-68) come from the slot loader. The flags in the page text are
// upgraded at once.
import '../ui/ui.css';   // .ui-label in the page text, from the first paint
import './protocol.css';
import { upgradeFlags } from '../ui/tooltip.js';
import { mountSlots } from './anatomy-loader.js';

upgradeFlags(document.querySelector('main'));
let figs = null;
const io = new IntersectionObserver(entries => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    io.unobserve(e.target);
    (figs ||= import('./figures.js')).then(m => m.mountFigure(e.target));
  }
}, { rootMargin: '400px 0px' });
for (const host of document.querySelectorAll('.pr-host[data-fig]')) io.observe(host);
mountSlots();
