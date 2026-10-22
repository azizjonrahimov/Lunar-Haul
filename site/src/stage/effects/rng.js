// Seeded random numbers for the effects, so a replay draws the same dust every time. mulberry32 gives a stream;
// hash01(seed, k, j) gives the j-th number of item k on its own, so particle k does not depend on what else was drawn
// (the wheel-dust ring buffer regenerates single slots in any order).
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hash01(seed, k, j = 0) {
  let h = (seed ^ Math.imul(k + 1, 0x9E3779B1) ^ Math.imul(j + 1, 0x85EBCA77)) >>> 0;
  h = Math.imul(h ^ (h >>> 16), 0x7FEB352D);
  h = Math.imul(h ^ (h >>> 15), 0x846CA68B);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}
