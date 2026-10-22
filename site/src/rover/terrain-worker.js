// F-40: builds the rover lab's terrain off the main thread (decoding the 3200 x 3200 16-bit height PNG and the 20 m
// roughness grid took ~1.5 s of the page's main thread at load) and hands the arrays back without copying them.
import { RoverTerrain } from './terrain.js';

self.onmessage = async e => {
  try {
    const t = await RoverTerrain.load(e.data.base, m => self.postMessage({ type: 'progress', message: m }));
    const rough = t.roughness20(), f = t.fields();
    self.postMessage({ type: 'done', fields: f, rough }, [f.z5.buffer, f.z20.buffer, f.slope20.buffer, rough.buffer]);
  } catch (err) { self.postMessage({ type: 'error', message: err.message }); }
};
