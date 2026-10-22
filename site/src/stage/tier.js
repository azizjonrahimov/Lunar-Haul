// GPU tier for the 3D pages (plan §3.6): detect-gpu with the self-hosted benchmark tables (no third-party request),
// tier 0 when WebGL2 is missing. ?tier=0..3 in the URL overrides it, for testing and for the tier switcher.
const BASE = import.meta.env.BASE_URL;

export async function detectTier() {
  const forced = new URLSearchParams(location.search).get('tier');
  if (forced !== null && /^[0-3]$/.test(forced)) return { tier: +forced, gpu: 'forced by ?tier', forced: true };
  const gl = document.createElement('canvas').getContext('webgl2');
  if (!gl) return { tier: 0, gpu: 'no WebGL2' };
  gl.getExtension('WEBGL_lose_context')?.loseContext();   // free the probe context at once
  try {
    const { getGPUTier } = await import('detect-gpu');
    const g = await getGPUTier({ benchmarksURL: BASE + 'detect-gpu/benchmarks' });
    return { tier: g.tier, gpu: g.gpu || 'unknown GPU', fps: g.fps };
  } catch (e) { return { tier: 1, gpu: `unknown (${e.message})` }; }
}

// Per-tier settings (research §1.13 table; tuned in F-40 on real hardware). particles: the landing dust budget (F-33).
export const TIERS = {
  1: { pixels: 1.8e6, ao: false, bloom: false, aa: 'fxaa', shadow: 1024, outline: false, frameMs: 33.3, particles: 2000 },
  2: { pixels: 3.3e6, ao: 'half', bloom: 'half', aa: 'fxaa', shadow: 2048, outline: true, frameMs: 16.7, particles: 10000 },
  3: { pixels: 5.2e6, ao: 'full', bloom: 'full', aa: 'smaa', shadow: 2048, outline: true, frameMs: 16.7, particles: 30000 },
};
