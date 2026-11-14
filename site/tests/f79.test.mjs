// F-79: the site follows the results corrected after the code review of 13 Nov 2026 (B-118). Each new value is checked
// against its results key: E52's stale-map hits after contact, E54's lost-link values and awards against jobs, E55's
// recent-replay trial, E56's quiet-event recalls, the verification count and G1's scope, and one robot's bid time with
// the factor range. Where a corrected value replaces a published one, the page names the earlier value once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const J = p => JSON.parse(readFileSync(join(ROOT, p), 'utf8').replace(/([:[,]\s*)-?(NaN|Infinity)\b/g, '$1null'));
const has = (...p) => p.every(x => existsSync(join(ROOT, x)));
const page = p => readFileSync(join(ROOT, 'site', p), 'utf8');
const value = html => { const m = /<span class="v">([^<]*)<\/span>/.exec(html); return m ? m[1] : null; };
const plain = html => html.replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, '').replace(/<span class="flag"[^>]*>[^<]*<\/span>/g, '').replace(/<[^>]+>/g, '');
const f = (x, d) => (+x).toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
const sup = (doc, field) => doc[Object.keys(doc).find(k => /^superseded_/.test(k) && field in doc[k])];
const once = (html, marker) => assert.equal(html.split(marker).length - 1, 1, `${marker} appears once`);

test('E52: the largest stale-map hits after contact, now and as published before, from results/E52_map.json', { skip: !has('results/E52_map.json') && 'E52 missing' }, async () => {
  const { e52 } = await import('../lib/protocol-data.mjs');
  const D = J('results/E52_map.json'), old = sup(D, 'rows'), html = page('protocol/index.html');
  assert.ok(old, 'a superseded_* block with rows');
  for (const o of ['hazards_first', 'oldest_first']) {
    const mx = rows => Math.max(...rows.filter(r => r.order === o).map(r => r.hits_after_contact_mean));
    assert.equal(value(e52(`hits_after_max_${o}`)), f(mx(D.rows), 2), o);
    assert.equal(value(e52(`was_hits_after_max_${o}`)), f(mx(old.rows), 2), `${o}, before`);
    once(html, `<!--@e52:hits_after_max_${o}-->`); once(html, `<!--@e52:was_hits_after_max_${o}-->`);
  }
  // the date reaches the page flagged, as a number does, never as typed digits
  const date = e52('superseded_on'), [y, mo, d] = old.superseded_on.split('-').map(Number);
  assert.equal(value(date), `${d} ${new Date(Date.UTC(y, mo - 1, d)).toLocaleString('en-GB', { month: 'long', timeZone: 'UTC' })} ${y}`);
  assert.match(date, /data-flag="Modelled"/); assert.match(date, /superseded_on/);
});

test('E54: the lost-link values, the Earth ledger and awards against jobs, now and as published before', { skip: !has('results/E54_dtn.json', 'results/E54_ledger.json') && 'E54 missing' }, async () => {
  const { e54, compactE54 } = await import('../lib/protocol-data.mjs');
  // F-81: E54 keeps two blocks (b118, the code review; b120_b, the end of the window), so each "before" key names its block
  const D = J('results/E54_dtn.json'), html = page('protocol/index.html');
  const block = task => { const ks = Object.keys(D).filter(x => /^superseded_/.test(x) && x.endsWith(`_${task}`)); assert.equal(ks.length, 1, task); return D[ks[0]]; };
  const row = (doc, p, l) => doc.rows.find(r => r.protocol === p && r.loss === l);
  const sec = v => (v < 90 ? `${f(v, 1)}` : v < 5400 ? f(v / 60, 1) : f(v / 3600, 1));
  const keys = [...new Set([...html.matchAll(/<!--@e54:([\w:@.]+)-->/g)].map(m => m[1]))];
  assert.ok(keys.length >= 15, `${keys.length} E54 keys on /protocol/`);
  for (const k of keys) {
    const w = /^was_(\w+?):(.+)$/.exec(k), was = !!w, kk = was ? w[2] : k, doc = was ? block(w[1]) : D, out = e54(k);
    assert.ok(!k.startsWith('was:'), `${k}: a bare was: cannot say which block`);
    let m;
    if ((m = /^(\w+):(\w+)@([\d.]+)$/.exec(kk))) {
      const v = row(doc, m[1], +m[3])[m[2]];
      assert.equal(value(out), /_s$/.test(m[2]) ? sec(v) : f(v, 0), k);
    } else if (kk === 'returns') assert.equal(value(out), f(doc.lost_link_returns_per_seed, 1), k);
    else if (kk === 'jobs') assert.equal(value(out), f(D.awards_and_jobs.jobs_per_seed, 1));
    else if (kk === 'awards') assert.equal(value(out), f(D.awards_and_jobs.awards_per_seed, 2));
    else if (kk === 'team_jobs') assert.equal(value(out), f(D.awards_and_jobs.team_jobs_per_seed, 2));
    else if ((m = /^loss@([\d.]+)$/.exec(kk))) assert.equal(out, `${f(100 * m[1], 0)} %`);
    else { const s = /^superseded_on_(\w+)$/.exec(kk); assert.ok(s, k); const [y, mo, d] = block(s[1]).superseded_on.split('-').map(Number);
      assert.match(out, new RegExp(`>${d} ${new Date(Date.UTC(y, mo - 1, d)).toLocaleString('en-GB', { month: 'long', timeZone: 'UTC' })} ${y}<`), k); }
    if (was) once(html, `<!--@e54:${k}-->`);   // each earlier value named once on the page
  }
  // the values LEAD listed, read here from the file: age of information and reports with the rule, returns, the ledger
  for (const k of ['sf_ll:aoi_mean_s@0.25', 'sf_ll:aoi_worst_vehicle_s@0.25', 'sf_ll:task_state_delay_mean_s@0.25', 'sf_ll:grant_lost@0.25', 'sf:ledger_earth_lost@0.25', 'sf:ledger_earth_censored@0.25', 'returns', 'awards', 'jobs', 'team_jobs']) assert.ok(keys.includes(k), k);
  // awards = jobs + the extra vehicle of each two-vehicle team job
  const AJ = D.awards_and_jobs;
  assert.ok(Math.abs(AJ.jobs_per_seed + AJ.team_jobs_per_seed * (AJ.vehicles_per_job_max - 1) - AJ.awards_per_seed) < 0.01);
  const C = compactE54(D, J('results/E54_ledger.json'));
  assert.deepEqual(C.awards_and_jobs, { jobs_per_seed: AJ.jobs_per_seed, awards_per_seed: AJ.awards_per_seed, team_jobs_per_seed: AJ.team_jobs_per_seed });
  assert.equal(C.returns_per_seed, D.lost_link_returns_per_seed);
  assert.throws(() => compactE54({ ...D, awards_and_jobs: undefined }, J('results/E54_ledger.json')), /awards_and_jobs\.jobs_per_seed/);
  assert.throws(() => e54('was_b118:jobs'), /unknown key/);
  assert.throws(() => e54('was:returns'), /2 superseded_\* blocks/, 'a bare was: with two blocks stops the build');
  assert.throws(() => e54('was_b999:returns'), /0 superseded_\* blocks end in _b999/);
  assert.throws(() => e54('was_b120_b:returns'), /no superseded_2026-11-14_b120_b\.lost_link_returns_per_seed/, 'the second block holds no returns');
  // F-81 (B-120 B): the ledger split now and before the end-of-window fix, each from the file
  for (const [k, doc] of [['sf:ledger_earth_lost@0.25', D], ['sf:ledger_earth_censored@0.25', D], ['was_b120_b:sf:ledger_earth_lost@0.25', block('b120_b')], ['was_b120_b:sf:ledger_earth_censored@0.25', block('b120_b')]]) {
    const f2 = k.replace(/^was_\w+?:/, '').split(':')[1].split('@')[0];
    assert.equal(value(e54(k)), f(row(doc, 'sf', 0.25)[f2], 0), k); assert.ok(keys.includes(k), k);
  }
  assert.equal(row(D, 'sf', 0.25).ledger_earth_lost + row(D, 'sf', 0.25).ledger_earth_censored, row(block('b120_b'), 'sf', 0.25).ledger_earth_lost + row(block('b120_b'), 'sf', 0.25).ledger_earth_censored, 'the fix moves bundles between expired and censored, none appear or vanish');
  assert.throws(() => e54('sf_ll:aoi_mean_s@0.33'), /no rows aoi_mean_s for sf_ll at loss 0.33/);
  // H14's second clause: the figure says what the file says (holds by rule) and shows the rule's count as not measured
  const fig = readFileSync(join(ROOT, 'site/src/protocol/figures.js'), 'utf8');
  if (D.h14.clause_2_basis) { assert.match(fig, /holds by rule, not by measurement/); assert.match(fig, /blocked, by rule \(not measured\)/); }
  assert.doesNotMatch(fig, /'not counted yet'/);
});

test('E55: the recent-replay trial, from results/E55_integrity.json replay_recent', { skip: !has('results/E55_integrity.json') && 'E55 missing' }, async () => {
  const { e55, compactE55 } = await import('../lib/protocol-data.mjs');
  const D = J('results/E55_integrity.json'), L = D.replay_recent.loss, html = page('protocol/index.html');
  for (const [l, v] of Object.entries(L)) {
    for (const k of ['replays', 'replays_accepted', 'accepted_missed_original_inside_window', 'accepted_other']) assert.equal(value(e55(`replay_${k}@${l}`)), f(v[k], 0), `${k} at ${l}`);
    assert.equal(v.accepted_missed_original_inside_window + v.accepted_other, v.replays_accepted, `loss ${l} adds up`);
    assert.equal(e55(`replay_loss@${l}`), `${f(100 * l, 0)} %`);
  }
  assert.deepEqual(Object.keys(compactE55(D).replay_recent).sort(), Object.keys(L).sort());
  for (const k of ['replay_replays_accepted@0.25', 'replay_replays@0.25', 'replay_accepted_missed_original_inside_window@0.25', 'replay_accepted_other@0.25']) assert.ok(html.includes(`<!--@e55:${k}-->`), k);
  // the answer no longer says every replay is rejected while the trial accepts some
  if (Object.values(L).some(v => v.replays_accepted > 0)) assert.doesNotMatch(html, /forged and replayed messages are\s+rejected/);
  const bad = JSON.parse(JSON.stringify(D)); bad.replay_recent.loss['0.25'].accepted_other = 1;
  assert.throws(() => compactE55(bad), /accepted replays do not add up/);
});

test('E56: the quiet-event recalls on /network/, from onset_context_and_fa_interval_b118', { skip: !has('results/E56_integrity.json', 'results/table_E56.csv') && 'E56 missing' }, async () => {
  const { nw } = await import('../lib/network.mjs');
  const B = J('results/E56_integrity.json').onset_context_and_fa_interval_b118.sets, html = page('network/index.html');
  for (const d of ['cusum', 'chi2_step', 'net']) {
    const ev = B.ood[d].day.events.all;
    assert.equal(value(nw(`ood_before_${d}`)), f(100 * ev.share_alarm_in_60s_before, 1), d);
    assert.equal(value(nw(`ood_quiet_${d}`)), f(ev.recall_quiet_60s_before, 2), d);
    assert.equal(value(nw(`ood_all_${d}`)), f(ev.recall, 2), `${d}: the block's recall is the table's`);
    for (const k of [`ood_before_${d}`, `ood_quiet_${d}`, `ood_all_${d}`]) assert.ok(html.includes(`<!--@nw:${k}-->`), k);
  }
  const tmax = Math.max(...Object.values(B.test).map(x => x.day.events.all.share_alarm_in_60s_before));
  assert.equal(value(nw('test_before_max')), f(100 * tmax, 1));
});

test('/verification/: the count and G1\'s scope (one scenario, one seed, the days, the values) from results/vv_phase6.json', { skip: !has('results/vv_phase6.json') && 'no vv_phase6' }, async () => {
  const { vv6 } = await import('../lib/phase6.mjs');
  const D = J('results/vv_phase6.json'), t = vv6('lead'), g = D.rows.find(r => r.id === 'G1' && r.sub === 'options off');
  assert.ok(t.startsWith(`${f(D.rows.filter(r => r.passed).length, 0)} of ${f(D.rows.length, 0)} recorded checks pass`));
  const b = /^(.+), (\d+) days, seed (\d+): (\d+) summary values against \S+ \(commit (\w+)\)$/.exec(g.basis);
  assert.ok(b, g.basis);
  assert.ok(t.includes(`one scenario (${b[1]}), one seed (seed ${b[3]}) and ${b[2]} days, ${b[4]} values`), t);
  assert.ok(t.includes(`commit ${b[5]}`));
  const on = D.rows.find(r => r.id === 'G1' && r.sub === 'option on changes the run');
  if (on) assert.ok(t.includes(`${/(\d+) of \d+ summary values differ/.exec(on.basis)[1]} of them differ, so the check can fail`));
  const alt = fn => { const X = JSON.parse(JSON.stringify(D)); fn(X); return X; };
  assert.throws(() => vv6('lead', alt(X => { X.rows.find(r => r.id === 'G1' && r.sub === 'options off').basis = 'some other text'; })), /options-off basis/);
});

test('one robot\'s bid: under the decision at the central factor, the top of the factor range, and the earlier values once a page', { skip: !has('results/E48_sizing.json') && 'E48 missing' }, async () => {
  const { robotRound } = await import('../src/atc/e48-robot.js');
  const { atcResults } = await import('../lib/results-atc.mjs');
  const S = J('results/E48_sizing.json'), RR = robotRound(S), TP = S.per_robot_round.timing_passes.by_multiple;
  const bid = plain(RR.bid), xs = Object.keys(TP);
  const top = xs.filter(x => S.per_robot_round.laptop_ms_by_multiple[x].flight_p99_ms <= 1000 && TP[x].flight_p99_ms_over_passes_and_factor_range[1] > 1000);
  assert.equal(RR.top, top.length > 0);
  for (const x of top) assert.ok(bid.includes(`${f(TP[x].flight_p99_ms_over_passes_and_factor_range[1] / 1e3, 2)} s`), `top of the range at ${x}`);
  if (!RR.above) {
    assert.ok(xs.every(x => TP[x].against_1s_at_central_factor === 'inside'), 'the file says inside at the central factor');
    assert.match(bid, /over three timing passes, under the one-second decision at the central factor in all three passes/);
  }
  if (RR.top) assert.match(bid, /over it only at the top of the factor range/);
  const old = sup(S, 'per_robot_round').per_robot_round.laptop_ms_by_multiple, was = plain(RR.was);
  for (const x of xs) assert.ok(was.includes(`${f(old[x].flight_p99_ms / 1e3, 2)} s`), `earlier value at ${x}`);
  // the /results/ P3 card names it once; /atc/ section 3 appends it once and no longer says the bidding never fits
  assert.equal(plain(atcResults()).split(was).length - 1, 1, 'P3 card');
  // F-81: on the rendered section 3 text (src/atc/sizing-note.js), not on the source of sizing.js
  const { sizingHtml } = await import('../src/atc/sizing-note.js');
  const sec3 = plain(sizingHtml(S));
  assert.equal(sec3.split(was).length - 1, 1, '/atc/ section 3 names the earlier values once');
  assert.ok(sec3.includes(bid), '/atc/ section 3 gives the bid time');
  if (!RR.above) assert.doesNotMatch(sec3, /does not fit at every fleet size/, 'section 3 does not say the bidding never fits');
  assert.match(sec3, RR.above ? /The bidding does not fit at every fleet size/ : RR.top ? /The bidding fits at the central factor but not across the whole factor range/ : /The bidding fits at every fleet size/);
});
