// Follow mode: the kit's flow paths (propellant feed lines, power cables, the cargo load path) drawn as glowing tubes
// with dashes moving along them, seen through the hull (no depth test) so the route reads in any view. Colours: cool
// cyan for propellant, warm amber for power (plan §3), Tol green for cargo. Under reduced motion or pause the dashes
// stand still.
import * as THREE from 'three';

export const FLOW_COLOURS = { propellant: '#74d5f5', power: '#ffb054', cargo: '#34a447' };

export function createFlows(scene) {
  const group = new THREE.Group(); group.name = 'flows'; group.renderOrder = 2000;
  scene.add(group);
  const uniforms = { time: { value: 0 } };
  let meshes = [];
  return {
    group,
    show(curves, kind, size) {
      this.clear();
      if (!curves?.length) return 0;
      const r = Math.max(0.025, size * 0.01), col = new THREE.Color(FLOW_COLOURS[kind]).multiplyScalar(2.2);   // > 1: bloom catches it on tier 2-3
      for (const c of curves) {
        const g = new THREE.TubeGeometry(c, 64, r, 8, false);
        const m = new THREE.ShaderMaterial({
          uniforms: { ...uniforms, color: { value: col }, len: { value: c.getLength() } },
          transparent: true, depthTest: false, depthWrite: false,
          vertexShader: 'varying float vU; void main() { vU = uv.x; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
          fragmentShader: `uniform float time; uniform float len; uniform vec3 color; varying float vU;
            void main() { float d = fract(vU * len / 0.6 - time * 1.2); float a = 0.35 + 0.65 * smoothstep(0.0, 0.15, d) * (1.0 - smoothstep(0.45, 0.6, d)); gl_FragColor = vec4(color, a); }`,
        });
        const mesh = new THREE.Mesh(g, m); mesh.renderOrder = 2000; mesh.userData.noPick = true;
        group.add(mesh); meshes.push(mesh);
      }
      return meshes.length;
    },
    tick(dt) { uniforms.time.value += dt; return meshes.length > 0; },
    clear() { for (const m of meshes) { m.geometry.dispose(); m.material.dispose(); group.remove(m); } meshes = []; },
    dispose() { this.clear(); scene.remove(group); },
  };
}
