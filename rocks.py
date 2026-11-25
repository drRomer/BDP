"""Rock chunk sprites (lava rock from the Titán texture, concrete from the sidewalk texture): 4 shapes x 8 rotations."""
import asyncio, sys, os, json, math
sys.path.insert(0, '/home/claude/brigada')
from bk import Baker, img_of, tex_for
from PIL import Image
OUT = '/home/claude/brigada/out/fx'; os.makedirs(OUT, exist_ok=True)
JS = r"""
async ([texUrl, k, seed, rough, emissive, colr]) => {
  const T = B.THREE, st = B.st;
  if (st.root && st.root.parent) st.root.parent.remove(st.root);
  const tex = await new Promise(r => new T.TextureLoader().load(texUrl, t => { t.colorSpace = T.SRGBColorSpace; t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(1.6, 1.6); r(t); }));
  const g = new T.IcosahedronGeometry(1, 2);
  const P = g.attributes.position, v = new T.Vector3();
  const h = (x, y, z) => { const s = Math.sin(x * 12.9898 + y * 78.233 + z * 37.719 + seed * 4.1) * 43758.5453; return s - Math.floor(s); };
  const sx = 0.8 + h(1, 2, 3) * 0.6, sy = 0.6 + h(4, 5, 6) * 0.5, sz = 0.75 + h(7, 8, 9) * 0.5;
  for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i); const q = v.clone().normalize();
    const n = 0.78 + 0.32 * h(Math.round(q.x * 7), Math.round(q.y * 7), Math.round(q.z * 7)) + 0.12 * h(Math.round(q.x * 3), Math.round(q.y * 3), Math.round(q.z * 3));
    v.copy(q).multiplyScalar(n); v.x *= sx; v.y *= sy; v.z *= sz; P.setXYZ(i, v.x, v.y, v.z); }
  g.computeVertexNormals();
  const m = new T.MeshStandardMaterial({color: new T.Color(colr || 0xffffff), map: tex, roughness: rough, metalness: 0.05, flatShading: true, emissive: new T.Color(emissive || 0x000000), emissiveIntensity: emissive ? 0.35 : 0, emissiveMap: emissive ? tex : null});
  const mesh = new T.Mesh(g, m); mesh.castShadow = false;
  const grp = new T.Group(); grp.add(mesh); B.st.root = grp; B.st.meshes = [mesh]; B.scene.add(grp);
  return true;
}
"""
async def main():
    async with Baker() as b:
        meta = {}
        sets = [('rockL', tex_for('t_55648842')['base'], 0.85, 0x552200), ('rockC', '/mnt-dl/Gemini_Generated_Image_5oqo2b5oqo2b5oqo.jpg', 0.95, 0)]
        os.makedirs('/home/claude/brigada/in/tex', exist_ok=True)
        import shutil
        shutil.copy('/mnt/user-data/uploads/Downloads/Gemini_Generated_Image_5oqo2b5oqo2b5oqo.jpg', '/home/claude/brigada/in/tex/sidewalk.jpg')
        sets[1] = ('rockC', '/in/tex/sidewalk.jpg', 0.95, 0)
        for key, tex, rough, em in sets:
            frames = []
            for k in range(4):
                await b.js(JS, [tex, k, k * 3.7 + (1 if key == 'rockL' else 9), rough, em, 0xffffff if key == 'rockL' else 0x86817b])
                await b.js('(y)=>B.view(y,33.7)', 0)
                for r in range(8):
                    a = r / 8 * math.pi * 2
                    await b.js('(a)=>{const g=B.st.root;g.rotation.set(a*0.7,a,a*0.35);g.updateMatrixWorld(true);}', a)
                    d = await b.js('()=>B.frameRock(96)')
                    frames.append(img_of(d))
            S = 96; im = Image.new('RGBA', (8 * S, 4 * S), (0, 0, 0, 0))
            for i, f in enumerate(frames): im.paste(f, ((i % 8) * S, (i // 8) * S))
            im.save(os.path.join(OUT, key + '.png')); meta[key] = {'fw': 96, 'fh': 96, 'n': 32, 'cols': 8}
        print('errs', [e for e in b.errs if '404' not in e][:3])
        old = json.load(open(os.path.join(OUT, 'fx.json'))); old.update(meta); json.dump(old, open(os.path.join(OUT, 'fx.json'), 'w'))

asyncio.run(main())
