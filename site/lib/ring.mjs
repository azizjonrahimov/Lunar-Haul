// F-75: P2's ring (encounter type 5) by exit rule: counted from the part files and written into /atc/ at build
// (vite.config.js, <!--@ring:E44--> and <!--@ring:E47-->), so the numbers are the files' and the lazy chunk stays small.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { gunzipSync } from 'node:zlib';
import { num } from '../src/components/num.js';
import { ROOT as SITE_ROOT } from './pages.mjs';

// F-75: type 5 (the ring) by the exit rule drawn for each encounter, counted as P2 counts it (paper/p2/build_p2.py,
// ring_parts and ring_facts): the driven encounters of results/<body>_parts/T05_b*.csv.gz split by params.keep_free (false is
// R3 as written, true the keep-one-slot-free variant); deadlock is judged only where no random planner runs. The two
// rules must account for every driven encounter and every deadlock in the bounds file, or the build stops.
export function ringByRule(ROOT, body, bounds) {
  const dir = join(ROOT, 'results', `${body}_parts`);
  const fs = existsSync(dir) ? readdirSync(dir).filter(f => /^T05_b\d+\.csv\.gz$/.test(f)).sort() : [];
  if (!fs.length) return null;
  const split = l => {   // one CSV line; only params is quoted, with "" for a quote
    const f = []; let cur = '', q = false;
    for (let i = 0; i < l.length; i++) {
      const ch = l[i];
      if (q) { if (ch === '"' && l[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
      else if (ch === '"') q = true; else if (ch === ',') { f.push(cur); cur = ''; } else cur += ch;
    }
    return [...f, cur];
  };
  const out = { as_written: { driven: 0, judged: 0, deadlock: 0 }, variant: { driven: 0, judged: 0, deadlock: 0 } };
  for (const f of fs) {
    const [head, ...rows] = gunzipSync(readFileSync(join(dir, f))).toString('utf8').trim().split(/\r?\n/), H = split(head), ix = k => H.indexOf(k);
    for (const l of rows) {
      const r = split(l);
      if (+r[ix('drivable')] !== 1) continue;
      const c = out[JSON.parse(r[ix('params')]).keep_free ? 'variant' : 'as_written'], judged = +r[ix('n_random')] === 0;
      c.driven++; if (judged) { c.judged++; if (+r[ix('deadlock')] > 0) c.deadlock++; }
    }
  }
  const t = bounds.types['5'], a = out.as_written, v = out.variant;
  if (a.driven + v.driven !== t.n_driven || a.deadlock + v.deadlock !== t.outcomes.deadlock)
    throw new Error(`ring: results/${body}_parts type 5 gives ${a.driven + v.driven} driven and ${a.deadlock + v.deadlock} deadlocks, the bounds file ${t.n_driven} and ${t.outcomes.deadlock}`);
  return { source: `results/${body}_parts/T05_b*.csv.gz (type 5 per encounter; keep_free false = R3 as written, true = the variant; judged = no random planner)`, ...out };
}

// the sentence after the type-5 finding, as P2's conclusion gives it (13 of 1,892 as written, 373 of 1,963 with the variant)
export function ringSentence(body) {
  const bounds = JSON.parse(readFileSync(join(SITE_ROOT, 'results', `${body}_bounds.json`), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null'));
  const R = ringByRule(SITE_ROOT, body, bounds);
  if (!R) throw new Error(`ring: results/${body}_parts has no type-5 files; /atc/ states the ring by exit rule`);
  const m = (value, unit, digits, source) => num({ value, unit, digits, flag: 'Modelled', source });
  const f = k => { const x = R[k], q = `${R.source}: ${k}.`; return `${m(x.deadlock, '', 0, q + 'deadlock')} of ${m(x.judged, '', 0, q + 'judged')} (${m(100 * x.deadlock / x.judged, ' %', 1, q + 'deadlock / judged')})`; };
  return `Where a deadlock is judged (no random planner)${body === 'E47' ? ' on Mars' : ''}, the ring locked up in ${f('as_written')} under the rule as written and in ${f('variant')} with a variant keeping one bay slot free; the Deadlocks column adds both.`;
}
