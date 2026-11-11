// The engine's link budget (lunarsim/atc/radio.py), ported for the /protocol/ figure 4. No DOM: tests/protocol-radio
// checks it against the per-class link numbers in results/E48_sizing.json (B-89), which radio.py produced.
export const R_MOON = 1737400, C = 299792458;
export const horizon = h => Math.sqrt(2 * R_MOON * h);                                  // radio.py horizon_m
export const fspl = (d, f) => 20 * Math.log10(4 * Math.PI * d * f / C);                 // free_space_loss_db
export const twoRay = (d, ha, hb) => 40 * Math.log10(d) - 20 * Math.log10(ha * hb);     // two_ray_loss_db
export const breakpoint = (ha, hb, f) => 4 * ha * hb * f / C;                            // breakpoint_m
export const flatLoss = (d, ha, hb, f) => d > breakpoint(ha, hb, f) ? Math.max(fspl(d, f), twoRay(d, ha, hb)) : fspl(d, f);
// radio.py snr_db and shannon_kbps: P_t + 2 G - L - N - M, then B log2(1 + SNR)
export function capacity(loss, { bw, txW = 1, gain = 3, nf = 5, margin = 10 }) {
  const snr = 10 * Math.log10(txW * 1000) + 2 * gain - loss - (-174 + 10 * Math.log10(bw) + nf) - margin;
  return { snr, kbps: bw / 1e3 * Math.log2(1 + 10 ** (snr / 10)) };
}
