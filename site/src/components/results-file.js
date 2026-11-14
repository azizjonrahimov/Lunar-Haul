// F-81: two readers of a results file that the build and the pages share (pure, no Node).
//
// supersededBlock(doc, file, has): a results file keeps the values it published before a correction under
// superseded_<date>_<task>. A page that prints a "before" sentence takes the one block that holds what it reads (has(block)
// is true). None, or more than one (a second supersession, where "before" would no longer say which), stops the build,
// naming the file and the keys; with key given, that block and no other.
export function supersededBlock(doc, file, has, key = null) {
  const keys = Object.keys(doc || {}).filter(k => /^superseded_/.test(k));
  const hit = (key ? keys.filter(k => k === key) : keys).filter(k => doc[k] && typeof doc[k] === 'object' && has(doc[k]));
  if (hit.length === 1) return { key: hit[0], doc: doc[hit[0]] };
  if (hit.length > 1) throw new Error(`${file}: ${hit.length} superseded_* blocks hold the values a "before" sentence reads (${hit.join(', ')}); the page names one, so pass its key`);
  throw new Error(`${file}: no superseded_* block${key ? ` ${key}` : ''} holds the values a "before" sentence reads${keys.length ? ` (the file has ${keys.join(', ')})` : ' (the file has none)'}`);
}

// readingVerdict(x): one reading of "near the base" in one cell (results/E50_near_base.json sets.<set>.<reading>):
// 'not judged' when no seed has steps inside the reading (the Python side's "not judged", B-118 N19), else 'holds' (every
// seed with steps inside the budget), 'fails' (none) or 'mixed'
export function readingVerdict(x) {
  if (!x || typeof x.seeds_with_steps !== 'number' || typeof x.seeds_inside_budget !== 'number') throw new Error('near base: a reading without seeds_with_steps or seeds_inside_budget');
  if (x.seeds_with_steps === 0) return 'not judged';
  return x.seeds_inside_budget === 0 ? 'fails' : x.seeds_inside_budget === x.seeds_with_steps ? 'holds' : 'mixed';
}
