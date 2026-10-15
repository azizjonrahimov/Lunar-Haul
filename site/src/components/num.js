// Num: one number with its unit, its provenance flag and its source. Isomorphic (build time in Node, run time in
// the browser): returns an HTML string. Every number on the site goes through here so none appears unflagged.
export const FLAGS = {
  Measured: 'Measured: observed on flown hardware or in a published test',
  Spec: 'Spec: a published specification or requirement',
  Modelled: 'Modelled: produced by the LunarSim simulation',
  Assumed: 'Assumed: a modelling assumption, varied in sensitivity runs',
};

export const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

export function fmt(value, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(+value)) return '–';
  return (+value).toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/* num({value, unit, flag, source, digits, pm}) -> HTML. pm: ± half-width shown after the value (same unit). */
export function num({ value, unit = '', flag, source = '', digits = 1, pm = null }) {
  if (!FLAGS[flag]) throw new Error(`num: flag must be one of ${Object.keys(FLAGS).join(', ')} (got ${flag})`);
  const v = fmt(value, digits), u = unit ? `<span class="u">${esc(unit)}</span>` : '';
  const pmTxt = pm === null ? '' : `<span class="u"> ± ${fmt(pm, digits)}</span>`;
  const tip = `${FLAGS[flag]}.${source ? ' Source: ' + source : ''}`;
  return `<span class="num"><span class="v">${v}</span>${pmTxt}${u}<span class="flag" data-flag="${flag}" title="${esc(tip)}">${flag}</span>` +
    `<span class="visually-hidden"> (${esc(tip)})</span></span>`;
}
