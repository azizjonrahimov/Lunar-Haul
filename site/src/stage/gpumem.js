// F-40: GPU memory, measured. With ?gpumem in the URL a 3D view wraps its WebGL2 context and adds up the bytes it asks
// the GPU for: every texture level (mipmaps included, cube faces and 3D layers too), every buffer, every renderbuffer
// (multisample ones times their samples), minus what it deletes; the canvas's own drawing buffer is added from its size.
// Driver overhead and padding are not visible from WebGL, so this is a floor. Read it as window.__gpumem.report().
const TYPE_BYTES = { 0x1401: 1, 0x1400: 1, 0x1403: 2, 0x1402: 2, 0x1405: 4, 0x1404: 4, 0x1406: 4, 0x140b: 2, 0x8d61: 2, 0x8363: 2, 0x8033: 2, 0x8034: 2, 0x84fa: 4, 0x8368: 4, 0x8c3b: 4, 0x8c3e: 4, 0x8dad: 8 };
const CHANNELS = { 0x1903: 1, 0x1909: 1, 0x1906: 1, 0x190a: 2, 0x8227: 2, 0x1907: 3, 0x1908: 4, 0x8d94: 1, 0x8228: 2, 0x8d98: 3, 0x8d99: 4, 0x1902: 1, 0x84f9: 1 };
// sized internal formats -> bytes per pixel (the common ones; RGB formats are stored padded to 4 channels)
const SIZED = { 0x8229: 1, 0x822b: 2, 0x8058: 4, 0x8c43: 4, 0x8051: 4, 0x8c41: 4, 0x822d: 2, 0x822f: 4, 0x881a: 8, 0x881b: 8, 0x822e: 4, 0x8230: 8,
  0x8814: 16, 0x8815: 16, 0x8c3a: 4, 0x8c3d: 4, 0x8059: 4, 0x8d62: 2, 0x8056: 2, 0x8057: 2, 0x81a5: 2, 0x81a6: 4, 0x8cac: 4, 0x88f0: 4, 0x8cad: 8,
  0x8232: 1, 0x8234: 2, 0x8236: 4, 0x8238: 2, 0x823a: 4, 0x823c: 8, 0x8d7c: 4, 0x8d76: 8, 0x8d70: 16, 0x8d8e: 4, 0x8d88: 8, 0x8d82: 16 };

export function trackGpuMemory(gl, canvas) {
  const tex = new Map(), buf = new Map(), rb = new Map(), dims = new Map();   // dims: texture -> 'w×h' of its largest level   // object -> bytes (textures: Map level/face -> bytes)
  const unitTex = new Map(); let unit = gl.TEXTURE0, curBuf = new Map(), curRb = null;
  const bpp = (internal, format, type) => SIZED[internal] || (CHANNELS[format] || CHANNELS[internal] || 4) * (TYPE_BYTES[type] || 1);
  const bound = target => unitTex.get(unit + ':' + (target >= 0x8515 && target <= 0x851a ? gl.TEXTURE_CUBE_MAP : target));
  const setLevel = (target, level, bytes, w, h) => {
    const t = bound(target); if (!t) return;
    if (w && (level === 0 || level === 'storage')) dims.set(t, `${w}×${h}`);
    if (!tex.has(t)) tex.set(t, new Map());
    tex.get(t).set(`${target}:${level}`, bytes);
  };
  const wrap = (name, after) => { const f = gl[name].bind(gl); gl[name] = (...a) => { const r = f(...a); after(a, r); return r; }; };
  wrap('activeTexture', ([u]) => { unit = u; });
  wrap('bindTexture', ([target, t]) => { unitTex.set(unit + ':' + target, t); });
  wrap('texImage2D', a => {   // (target, level, internal, w, h, border, format, type, src) or (target, level, internal, format, type, source)
    if (a.length >= 8) setLevel(a[0], a[1], a[3] * a[4] * bpp(a[2], a[6], a[7]), a[3], a[4]);
    else { const s = a[5]; const w = s.videoWidth || s.naturalWidth || s.width, h = s.videoHeight || s.naturalHeight || s.height; setLevel(a[0], a[1], w * h * bpp(a[2], a[3], a[4]), w, h); }
  });
  wrap('texImage3D', a => setLevel(a[0], a[1], a[3] * a[4] * a[5] * bpp(a[2], a[7], a[8])));
  wrap('texStorage2D', ([target, levels, internal, w, h]) => {
    let s = 0; for (let l = 0; l < levels; l++) s += Math.max(1, w >> l) * Math.max(1, h >> l) * bpp(internal);
    const faces = target === gl.TEXTURE_CUBE_MAP ? 6 : 1; setLevel(target, 'storage', s * faces, w, h);
  });
  wrap('texStorage3D', ([target, levels, internal, w, h, d]) => {
    let s = 0; for (let l = 0; l < levels; l++) s += Math.max(1, w >> l) * Math.max(1, h >> l) * (target === gl.TEXTURE_3D ? Math.max(1, d >> l) : d) * bpp(internal);
    setLevel(target, 'storage', s);
  });
  wrap('compressedTexImage2D', a => setLevel(a[0], a[1], a[6]?.byteLength || 0));
  wrap('generateMipmap', ([target]) => {   // levels 1.. of a full chain: a third of level 0 more
    const t = bound(target), m = t && tex.get(t); if (!m) return;
    const base = [...m].filter(([k]) => k.endsWith(':0')).reduce((s, [, v]) => s + v, 0);
    m.set(`${target}:mips`, Math.round(base / 3));
  });
  wrap('deleteTexture', ([t]) => { tex.delete(t); dims.delete(t); });
  wrap('bindBuffer', ([target, b]) => { curBuf.set(target, b); });
  wrap('bufferData', ([target, data]) => { const b = curBuf.get(target); if (b) buf.set(b, typeof data === 'number' ? data : data.byteLength); });
  wrap('deleteBuffer', ([b]) => { buf.delete(b); });
  wrap('bindRenderbuffer', ([, r]) => { curRb = r; });
  wrap('renderbufferStorage', ([, internal, w, h]) => { if (curRb) rb.set(curRb, w * h * (SIZED[internal] || 4)); });
  wrap('renderbufferStorageMultisample', ([, samples, internal, w, h]) => { if (curRb) rb.set(curRb, w * h * (SIZED[internal] || 4) * Math.max(1, samples)); });
  wrap('deleteRenderbuffer', ([r]) => { rb.delete(r); });
  const MB = b => Math.round(b / 1048576 * 10) / 10;
  const api = {
    report() {
      const t = [...tex.values()].reduce((s, m) => s + [...m.values()].reduce((a, b) => a + b, 0), 0);
      const b = [...buf.values()].reduce((s, v) => s + v, 0), r = [...rb.values()].reduce((s, v) => s + v, 0);
      const aa = gl.getContextAttributes()?.antialias ? Math.max(1, gl.getParameter(gl.SAMPLES)) : 1, px = gl.drawingBufferWidth * gl.drawingBufferHeight;
      const d = px * (4 + 4) * aa + (aa > 1 ? px * 4 : 0);   // the canvas: colour + depth/stencil per sample, plus the resolved image when multisampled
      const top = [...tex].map(([k, m]) => ({ dims: dims.get(k) || '?', mb: MB([...m.values()].reduce((a, b) => a + b, 0)) })).sort((a, b) => b.mb - a.mb).slice(0, 5);
      return { top_textures: top, textures_mb: MB(t), buffers_mb: MB(b), renderbuffers_mb: MB(r), canvas_mb: MB(d), total_mb: MB(t + b + r + d), n_textures: tex.size, n_buffers: buf.size,
        drawing_buffer: [gl.drawingBufferWidth, gl.drawingBufferHeight], canvas: [canvas.width, canvas.height] };
    },
  };
  return api;
}
