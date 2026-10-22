// The vehicle and site catalogue (B-30, lunarsim/catalog-v1.json, staged by prepare-data.mjs): the one source of
// every vehicle number and 3D dimension on screen. Each number is a quantity {value, unit, flag, source}; q() turns
// one into the spec that components/num.js and the stat chips take.
const BASE = import.meta.env.BASE_URL;
let cached = null;

// fetchFn: e.g. a loading door's fetch, so the bytes count towards its progress bar
export async function loadCatalog(url = BASE + 'catalog/catalog-v1.json', { fetchFn = fetch } = {}) {
  if (cached) return cached;
  const r = await fetchFn(url);
  if (!r.ok) throw new Error(`vehicle catalogue: HTTP ${r.status}`);
  const doc = await r.json();
  if (doc.format !== 'lunarsim-catalog' || doc.version !== 1) throw new Error('vehicle catalogue: unexpected format');
  const byId = Object.fromEntries(doc.entries.map(e => [e.id, e]));
  const entry = id => { if (!byId[id]) throw new Error(`vehicle catalogue: no entry ${id}`); return byId[id]; };
  // q('MK1', 'gate.t_max_n', {scale: 1e-3, unit: 'kN', digits: 0}) -> {value, unit, flag, source, digits}
  const q = (id, path, { scale = 1, unit, digits = 1 } = {}) => {
    const v = path.split('.').reduce((o, k) => o?.[k], entry(id));
    if (!v || typeof v.value !== 'number') throw new Error(`vehicle catalogue: ${id}.${path} is not a quantity`);
    return { value: v.value * scale, unit: unit ?? v.unit, flag: v.flag, source: v.source, digits };
  };
  cached = { doc, entries: doc.entries, entry, q };
  return cached;
}
