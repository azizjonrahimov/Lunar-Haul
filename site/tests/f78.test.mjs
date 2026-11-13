// F-78 (code review of Phase 6, sections W and T): the site's readers stop the build on a missing row or key, with the
// file and key named, instead of printing a dash or "0 of 0"; the /protocol/ data budget counts the file the page reads.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const J = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null'));
const has = (...p) => p.every(x => existsSync(join(ROOT, x)));
const value = html => { const m = /<span class="v">([^<]*)<\/span>/.exec(html); return m ? m[1] : null; };

test('/network/: every key the page uses gives a flagged number; an unknown key throws', { skip: !has('results/table_E56.csv', 'results/E56_integrity.json') && 'E56 missing' }, async () => {
  const { nw } = await import('../lib/network.mjs');
  const page = readFileSync(join(ROOT, 'site/network/index.html'), 'utf8');
  const keys = [...new Set([...page.matchAll(/<!--@nw:(\w+)-->/g)].map(m => m[1]))];
  assert.ok(keys.length >= 20, `only ${keys.length} keys on the page`);
  for (const k of keys) {
    const html = nw(k), v = value(html);
    assert.ok(v && /\d/.test(v) && v !== '–', `${k}: ${v}`);
    assert.match(html, /data-flag="Modelled"/, k);
    assert.match(html, /Source: (results\/table_E56\.csv|results\/E56_integrity\.json|data\/atc\/protocol\/b96_landscape\.json)/, k);
  }
  assert.throws(() => nw('no_such_key'), /network: no number no_such_key/);
});

test('/network/: the parameter count is labelled with the file it was read from', { skip: !has('results/E56_integrity.json') && 'E56 missing' }, async () => {
  const { nw } = await import('../lib/network.mjs');
  const E = J('results/E56_integrity.json'), html = nw('params');
  assert.match(html, typeof E.model?.n_params === 'number' ? /results\/E56_integrity\.json: model\.n_params/ : /b96_landscape\.json: landscape\.model\.n_params/);
});

test('/results/ family table: a decision on a hypothesis or clause the file does not have stops the build', { skip: !has('results/phase6_family.json') && 'family missing' }, async () => {
  const { familyRows, DECISIONS } = await import('../lib/phase6.mjs');
  const F = J('results/phase6_family.json');
  assert.ok(familyRows(F).length > 0);
  assert.throws(() => familyRows(F, { ...DECISIONS, H9: { ...DECISIONS.H9, clauses: { 'a clause the file does not have': 'reading' } } }), /H9 has no clause “a clause the file does not have”/);
  assert.throws(() => familyRows(F, { ...DECISIONS, H99: { label: 'H99' } }), /no hypothesis H99/);
});

test('/verification/: the Phase 6 count comes from the rows\' passed flags and must agree with the summary', { skip: !has('results/vv_phase6.json') && 'vv_phase6 missing' }, async () => {
  const { vv6 } = await import('../lib/phase6.mjs');
  const D = J('results/vv_phase6.json'), n = D.rows.filter(r => r.passed).length;
  assert.ok(vv6('lead', D).startsWith(`${n.toLocaleString('en-GB')} of ${D.rows.length.toLocaleString('en-GB')} recorded checks pass`));
  const alt = f => { const X = structuredClone(D); f(X); return X; };
  assert.throws(() => vv6('lead', alt(X => { delete X.summary.passed; })), /summary\.rows or summary\.passed missing/);
  assert.throws(() => vv6('lead', alt(X => { X.summary.passed -= 1; })), /the rows give .* the summary/);
  assert.throws(() => vv6('lead', alt(X => { X.rows.find(r => r.id === 'G1').passed = false; X.summary.passed -= 1; })), /G1 does not pass/);
  assert.throws(() => vv6('lead', alt(X => { delete X.rows[0].passed; })), /without a boolean passed/);
});

test('/protocol/ figure 3: the constants it reads are required', { skip: !has('results/E51_clocks.json') && 'E51 missing' }, async () => {
  const { compactE51 } = await import('../lib/protocol-data.mjs');
  const D = J('results/E51_clocks.json');
  const out = compactE51(D);
  for (const k of ['guard_s', 'uwb_sigma_m', 'contact_share']) assert.equal(typeof out[k], 'number', k);
  const X = structuredClone(D); delete X.design.uwb_sigma_m;
  assert.throws(() => compactE51(X), /no number at design\.uwb_sigma_m/);
});

test('/protocol/ data budget counts the file the bit-rate figure reads; the build-only B-99 file is not staged', async () => {
  const B = JSON.parse(readFileSync(join(ROOT, 'tools/ci/budgets.json'), 'utf8'));
  const all = JSON.stringify(B);
  assert.ok(all.includes('"protocol/e53-v02.json"'));
  assert.ok(!all.includes('protocol/b99/e53_bitrate.json'));
  const { B99_BUILD_ONLY } = await import('../lib/protocol-data.mjs');
  assert.ok(B99_BUILD_ONLY.has('e53_bitrate.json'));
  const fig = readFileSync(join(ROOT, 'site/src/protocol/figures.js'), 'utf8');
  assert.ok(!/fetch\([^)]*b99\/e53_bitrate\.json/.test(fig), 'no page fetches the build-only file');
});
