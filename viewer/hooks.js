// Prop attachment helpers; evaluated in the page after bake.html is ready.
(() => {
  const T = B.THREE, st = B.st;
  const V = () => new T.Vector3(), Q = () => new T.Quaternion();
  B.att = {};
  function basisMatrix(pos, yAxis, zAxis, scale) {
    const y = yAxis.clone().normalize();
    const z = zAxis.clone().sub(y.clone().multiplyScalar(zAxis.dot(y))).normalize();
    const x = new T.Vector3().crossVectors(y, z).normalize();
    const m = new T.Matrix4().makeBasis(x.multiplyScalar(scale), y.multiplyScalar(scale), z.multiplyScalar(scale));
    m.setPosition(pos);
    return m;
  }
  function place(g, m) { g.matrixAutoUpdate = false; g.matrix.copy(m); g.updateMatrixWorld(true); }
  // Rifle: grip at right hand, barrel toward left hand
  B.setupRifle = (scale, gripOff) => {
    const i = B.addProp('rifle', {len: 0.85}); const g = st.props[i];
    B.att.rifle = {g, scale, gripOff: gripOff || [0, 0, 0]};
  };
  // Hammer carried along the forearm, bent toward the body's forward direction by `bend` degrees
  B.setupHammer = (hand, fore, len) => {
    const i = B.addProp('hammer', {len: 1}); const g = st.props[i];
    const hips = st.bones['Hips']; const q0 = Q(); hips.getWorldQuaternion(q0);
    const lfwd = new T.Vector3(0, 0, 1).applyQuaternion(q0.clone().invert());
    B.att.hammer = {g, hand, fore, len, bend: 45, lfwd, grip: 0, grav: 0, side: 0};
  };
  // Hammer from a GLB (handle along +Y, head long axis along X): wrapped so grip=origin, head center=(0,1,0), faces along +Z
  B.setupHammerGLB = async (url, hand, fore, len, thick) => {
    const {GLTFLoader} = await import('three/addons/loaders/GLTFLoader.js');
    const gl = await new Promise((res, rej) => new GLTFLoader().load(url, res, undefined, rej));
    const m = gl.scene; m.traverse(o => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
    const box = new T.Box3().setFromObject(m); const mn = box.min, mx = box.max, h = mx.y - mn.y;
    const gy = mn.y + 0.2 * h, hy = mn.y + 0.86 * h, sc = 1 / (hy - gy);
    const cx = (mn.x + mx.x) / 2, cz = (mn.z + mx.z) / 2;
    const inner = new T.Group(); inner.add(m); m.position.set(-cx, -gy, -cz);
    const tk = thick || 1; inner.scale.set(sc * tk, sc, sc * tk); inner.rotation.y = Math.PI / 2;   // head long axis X -> Z; tk engrosa mango y cabeza sin alargar
    const g = new T.Group(); g.add(inner); B.scene.add(g); st.props.push(g);
    g.userData.head = new T.Vector3(0, 1, 0); g.userData.face = new T.Vector3(0, 1, 0.42);
    const hips = st.bones['Hips']; const q0 = Q(); hips.getWorldQuaternion(q0);
    const lfwd = new T.Vector3(0, 0, 1).applyQuaternion(q0.clone().invert());
    B.att.hammer = {g, hand, fore, len, bend: 45, lfwd, grip: 0, grav: 0, side: 0};
    return [h, sc];
  };
  // martillo como arma en un "socket" de la mano: sigue la rotación de la muñeca (eje local 'ax' = mango, 'up' = cara)
  B.setupHammerSocket = async (url, hand, len, thick, ax, up, grip) => {
    const r = await B.setupHammerGLB(url, hand, hand, len, thick);
    const a = B.att.hammer; a.sock = {ax: new T.Vector3().fromArray(ax), up: new T.Vector3().fromArray(up), grip: grip || 0};
    return r;
  };
  B.setSock = (ax, up, grip) => { const a = B.att.hammer; a.sock = {ax: new T.Vector3().fromArray(ax), up: new T.Vector3().fromArray(up), grip: grip || 0}; };
  // agarre a dos manos: el mango pasa por los dos puños ('back' en el extremo, 'front' hacia la cabeza); vel = dirección del golpe
  B.setTwo = (back, front) => { const a = B.att.hammer; a.two = back ? {back, front} : null; a.sock = null; };
  B.setVel = (v) => { B.att.hammer.vel = v ? new T.Vector3().fromArray(v) : null; };
  B.palm = (name) => { const h = st.bones[name], m = st.bones[name.replace('Hand', 'HandMiddle1')], p = V(), q = V(); h.getWorldPosition(p); if (m) m.getWorldPosition(q); else q.copy(p); return p.lerp(q, 0.55).toArray(); };
  B.setBend = (deg) => { B.att.hammer.bend = deg; };
  B.setGrip = (u) => { B.att.hammer.grip = u; };
  B.setGrav = (g) => { B.att.hammer.grav = g; };
  B.setSide = (s) => { B.att.hammer.side = s; };
  B.hammerHead = () => { const a = B.att.hammer; const v = a.g.userData.head.clone().applyMatrix4(a.g.matrixWorld); return v.toArray(); };
  B.hammerFace = () => { const a = B.att.hammer; const v = a.g.userData.face.clone().applyMatrix4(a.g.matrixWorld); return v.toArray(); };
  B.muzzle = () => { const a = B.att.rifle; const v = a.g.userData.muzzle.clone().applyMatrix4(a.g.matrixWorld); return v.toArray(); };
  B.hook = () => {
    if (B.att.rifle) {
      const a = B.att.rifle, rh = st.bones['RightHand'], lh = st.bones['LeftHand'];
      const pr = V(), pl = V(); rh.getWorldPosition(pr); lh.getWorldPosition(pl);
      const fwd = pl.clone().sub(pr).normalize();
      const up = new T.Vector3(0, 1, 0);
      const pos = pr.clone().add(new T.Vector3().fromArray(a.gripOff));
      // rifle local: +Z barrel, +Y up -> basis(y=up', z=fwd)
      const m = basisMatrix(pos, up.clone().sub(fwd.clone().multiplyScalar(up.dot(fwd))), fwd, a.scale);
      // basisMatrix builds x = y cross z ; for rifle we want z = fwd exactly
      const y = up.clone().sub(fwd.clone().multiplyScalar(up.dot(fwd))).normalize();
      const x = new T.Vector3().crossVectors(y, fwd).normalize();
      const mm = new T.Matrix4().makeBasis(x.multiplyScalar(a.scale), y.multiplyScalar(a.scale), fwd.clone().multiplyScalar(a.scale)); mm.setPosition(pos);
      place(a.g, mm);
    }
    if (B.att.hammer) {
      const a = B.att.hammer, hb = st.bones[a.hand], fb = st.bones[a.fore];
      const ph = V(), pf = V(); hb.getWorldPosition(ph); fb.getWorldPosition(pf);
      if (a.two) {
        const PB = new T.Vector3().fromArray(B.palm(a.two.back)), PF = new T.Vector3().fromArray(B.palm(a.two.front));
        const d = PF.clone().sub(PB).normalize();
        const qh0 = Q(); st.bones['Hips'].getWorldQuaternion(qh0); const fw = a.lfwd.clone().applyQuaternion(qh0);
        // mezcla suave entre el frente del cuerpo (quieto) y la dirección del golpe (rápido) para que la cabeza no gire de golpe
        const w = a.vel ? Math.min(1, a.vel.length() / (a.len * 0.18)) : 0;
        let n = fw.clone().multiplyScalar(1 - w); if (w > 0) n.add(a.vel.clone().normalize().multiplyScalar(w));
        n.sub(d.clone().multiplyScalar(n.dot(d)));
        if (n.length() < 1e-3) n = fw.clone().sub(d.clone().multiplyScalar(fw.dot(d)));
        n.normalize();
        a.cur = {d: d.toArray(), n: n.toArray(), hand: PB.toArray()};
        place(a.g, basisMatrix(PB, d, n, a.len));
        return;
      }
      if (a.sock) {
        const qh = Q(); hb.getWorldQuaternion(qh);
        const mid = st.bones[a.hand.replace('Hand', 'HandMiddle1')]; const pm = V(); if (mid) mid.getWorldPosition(pm); else pm.copy(ph);
        const palm = ph.clone().lerp(pm, 0.55);
        const d = a.sock.ax.clone().applyQuaternion(qh).normalize();
        let n = a.sock.up.clone().applyQuaternion(qh); n.sub(d.clone().multiplyScalar(n.dot(d))).normalize();
        const pos = palm.clone().sub(d.clone().multiplyScalar(a.sock.grip * a.len));
        a.cur = {d: d.toArray(), n: n.toArray(), hand: ph.toArray()};
        place(a.g, basisMatrix(pos, d, n, a.len));
        return;
      }
      let d = ph.clone().sub(pf).normalize();
      if (a.grav > 0) d = d.multiplyScalar(1 - a.grav).add(new T.Vector3(0, -a.grav, 0)).normalize();
      const qh = Q(); st.bones['Hips'].getWorldQuaternion(qh);
      const fwd = a.lfwd.clone().applyQuaternion(qh); fwd.y = 0; fwd.normalize();
      const out = new T.Vector3().crossVectors(fwd, new T.Vector3(0, 1, 0)).normalize();
      const sr = a.side * Math.PI / 180, dirB = fwd.clone().multiplyScalar(Math.cos(sr)).add(out.multiplyScalar(Math.sin(sr)));
      let n = dirB.clone().sub(d.clone().multiplyScalar(dirB.dot(d)));
      if (n.length() < 1e-3) n = new T.Vector3(0, 1, 0).sub(d.clone().multiplyScalar(d.y));
      n.normalize();
      const r = a.bend * Math.PI / 180;
      const d2 = d.clone().multiplyScalar(Math.cos(r)).add(n.clone().multiplyScalar(Math.sin(r))).normalize();
      const n2 = n.clone().multiplyScalar(Math.cos(r)).sub(d.clone().multiplyScalar(Math.sin(r))).normalize();
      const pos = ph.clone().add(d.clone().multiplyScalar(a.grip));
      // keep the head above the ground: lift the handle toward horizontal if needed
      const minY = (a.minY || 0.2) * a.len, need = (minY - pos.y) / a.len;
      if (d2.y < need) {
        const hz = new T.Vector3(d2.x, 0, d2.z); if (hz.length() < 1e-4) hz.copy(n2).setY(0); hz.normalize();
        const yy = Math.min(0.95, need), k = Math.sqrt(Math.max(0, 1 - yy * yy));
        d2.set(hz.x * k, yy, hz.z * k);
        n2.sub(d2.clone().multiplyScalar(n2.dot(d2))).normalize();
      }
      a.cur = {d: d2.toArray(), n: n2.toArray(), hand: ph.toArray()};
      place(a.g, basisMatrix(pos, d2, n2, a.len));
    }
  };
  return true;
})();
