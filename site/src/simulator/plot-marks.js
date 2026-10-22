// The Observable Plot marks the simulator draws with, re-exported so the page can load them lazily and still get a
// tree-shaken chunk (a dynamic import of '@observablehq/plot' itself would pull in the whole library, d3 included).
export { plot, barY, ruleX, text, dot, rectX } from '@observablehq/plot';
