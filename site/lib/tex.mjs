// Equations rendered at build time (KaTeX 0.18, MathML output: the browser draws them natively, so no KaTeX CSS,
// fonts or script reach the page). <!--@tex:name--> in page HTML becomes the block below; numbers match
// site/src/lander/env.js (reward v2/v3 weights) and classes.js.
import katex from 'katex';

const T = String.raw;
const BLOCKS = {
  // the lander lab's chalkboard (F-34)
  lander: [
    ['The engine against gravity', T`m\,\dot{\mathbf v} = T\,\hat{\mathbf u} - m\,g\,\hat{\mathbf z},\qquad g = 1.62\ \mathrm{m\,s^{-2}},\qquad \dot m = -\frac{T}{I_{sp}\,g_0}`],
    ['Score per 0.2 s step', T`r_t = \alpha\,\Big(1 + 3\max\big(0,\,1-\tfrac{z}{30}\big)\Big)\,\lVert \mathbf v - \mathbf v^{*} \rVert + \beta\,\frac{T}{T_{\max}} + \eta`],
    ['Score for the landing', T`R = \sum_t r_t + 50\Big(\tfrac12 + \tfrac12\,e^{-d/10}\Big)\ \text{in the box},\qquad \alpha = \beta = -0.05,\ \ \eta = +0.01`],
    ['The hover hack (first reward rules)', T`\eta = +0.3:\quad 750\ \text{steps} \times 0.3 = +225 \;\gg\; 10\ \text{for landing}`],
  ],
};

export function tex(name) {
  const block = BLOCKS[name];
  if (!block) throw new Error(`tex: no block ${name}`);
  return block.map(([label, src]) => `<div class="tex-row"><p class="ui-label">${label}</p>${katex.renderToString(src, { output: 'mathml', displayMode: true, throwOnError: true })}</div>`).join('\n');
}
