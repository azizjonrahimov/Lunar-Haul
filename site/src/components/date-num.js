// F-79: kept out of num.js so the pages that share num.js's chunk do not carry it (research/earth-sky's JS budget)
import { FLAGS, esc } from './num.js';

/* F-79: a date read from a results file (e.g. superseded_on, "2026-11-13"), shown as "13 November 2026" in the same
   flagged markup as a number, so no date reaches a page as typed digits. dateNum({iso, flag, source}) -> HTML. */
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export function dateNum({ iso, flag = 'Modelled', source = '' }) {
  if (!FLAGS[flag]) throw new Error(`dateNum: flag must be one of ${Object.keys(FLAGS).join(', ')} (got ${flag})`);
  // F-81: a real calendar day (2026-02-31 stops the build too)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso)), mo = m ? +m[2] : 0, d = m ? +m[3] : 0;
  if (!m || mo < 1 || mo > 12 || d < 1 || new Date(Date.UTC(+m[1], mo - 1, d)).getUTCDate() !== d) throw new Error(`dateNum: ${iso} is not a date (YYYY-MM-DD)${source ? `, ${source}` : ''}`);
  const tip = `${FLAGS[flag]}.${source ? ' Source: ' + source : ''}`;
  return `<span class="num"><span class="v">${d} ${MONTHS[mo - 1]} ${m[1]}</span><span class="flag" data-flag="${flag}" title="${esc(tip)}">${flag}</span>` +
    `<span class="visually-hidden"> (${esc(tip)})</span></span>`;
}
