// Named speeds and their wording for the shared time scale (F-50; the control is timescale.js). No DOM, so Node tests
// can use it. Speeds are simulated seconds per real second (x).
// the named speeds; pages pick a subset or add their own multipliers (the labs' 2×, 5×, 10×)
export const SPEEDS = { real: 1, '1min': 60, '5min': 300, '15min': 900, '1h': 3600, '6h': 21600, '1d': 86400, '3d': 259200 };
export const NAMED = Object.values(SPEEDS);

// 300 -> "5 min", 3600 -> "1 h", 86400 -> "1 day", 2 -> "2 s"
export function simSpan(sec) {
  const r = v => +v.toFixed(v < 10 && v % 1 ? 1 : 0);
  if (sec >= 86400) { const d = r(sec / 86400); return `${d} day${d === 1 ? '' : 's'}`; }
  if (sec >= 3600) return `${r(sec / 3600)} h`;
  if (sec >= 60) return `${r(sec / 60)} min`;
  return `${r(sec)} s`;
}
// the option name: "real time", "5 min/s", "1 day/s", or "2×" below a minute a second
export const speedName = x => x === 0 ? 'instant' : x === 1 ? 'real time' : x < 60 ? `${x}×` : `${simSpan(x)}/s`;
// the label under the control
export const speedText = x => x === 0 ? 'Instant: jumps to the end' : x === 1 ? 'Real time: 1 s on screen = 1 s on the Moon' : `1 s on screen = ${simSpan(x)} on the Moon`;
// a skipped stretch of simulated hours: "6 h 20 min", "2 days 3 h", "40 min"
export function hoursText(h) {
  const m = Math.round(h * 60), d = Math.floor(m / 1440), hh = Math.floor((m % 1440) / 60), mm = m % 60;
  if (d) return `${d} day${d === 1 ? '' : 's'}${hh ? ` ${hh} h` : ''}`;
  return hh ? `${hh} h${mm ? ` ${mm} min` : ''}` : `${mm} min`;
}
// ?speed= value -> x, or null: a name (5min, 1h, 1d, 3d, real), a multiplier (60x, 300) or a span per second (15m, 6h)
export function parseSpeed(s) {
  if (!s) return null;
  s = String(s).trim().toLowerCase().replace(/\s+/g, '').replace(/\/s$/, '');
  if (s === 'real' || s === 'realtime' || s === '1x') return 1;
  const m = /^(\d+(?:\.\d+)?)(x|s|sec|m|min|h|d|day|days)?$/.exec(s); if (!m) return null;
  const v = +m[1], u = m[2] || 'x', k = { x: 1, s: 1, sec: 1, m: 60, min: 60, h: 3600, d: 86400, day: 86400, days: 86400 }[u];
  return v > 0 ? v * k : null;
}
// the available speed nearest to x (by ratio)
export const nearest = (speeds, x) => speeds.filter(v => v > 0).reduce((a, b) => Math.abs(Math.log(b / x)) < Math.abs(Math.log(a / x)) ? b : a);

// Landings, the same on every page (LEAD, 27 Oct): a descent plays at 10 s a second, its last 60 s (from about 150 m
// up to touchdown, the burn and the dust) at real time; never faster than the page's own speed x.
export const LANDING_SLOW_X = 10, LANDING_REAL_S = 60;
export const landingX = (toTouchdownS, x = Infinity) => Math.min(x, toTouchdownS <= LANDING_REAL_S ? 1 : LANDING_SLOW_X);
// the label prefix for the override: which part of the descent is playing
export const landingPrefix = toTouchdownS => toTouchdownS <= LANDING_REAL_S ? `Landing, last ${LANDING_REAL_S} s` : 'Landing';
