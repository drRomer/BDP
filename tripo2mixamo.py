"""Tripo FBX (any size) -> decimated, normalized OBJ zip for Mixamo.
usage: tripo2mixamo.py in.fbx basecolor.jpg out_name [target_faces]
"""
import sys, os, zipfile, math
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbxread

src, tex, name = sys.argv[1], sys.argv[2], sys.argv[3]
target = int(sys.argv[4]) if len(sys.argv) > 4 else 40000
out = os.path.join('/home/claude/brigada/out', name)
os.makedirs(out, exist_ok=True)

ver, root = fbxread.load(src)
objs = root.first('Objects')
model = objs.first('Model')
rx, ry, rz = (fbxread.p70(model).get('Lcl Rotation') or [0, 0, 0])[-3:]
g = fbxread.geometry(root)[0]
V = g['verts']

# apply Lcl Rotation (XYZ euler, degrees) so the mesh is Y-up like the file declares
def rot(ax, a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    if ax == 0: return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if ax == 1: return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
R = rot(2, rz) @ rot(1, ry) @ rot(0, rx)
V = V @ R.T

# triangulate (fan) and build wedge UVs
polys = g['polys']; cuv = g['corner_uv']; UV = g['uvs']
tris, wuv, c = [], [], 0
for p in polys:
    n = len(p)
    for k in range(1, n - 1):
        tris.append((p[0], p[k], p[k + 1]))
        wuv.append((cuv[c], cuv[c + k], cuv[c + k + 1]))
    c += n
F = np.array(tris, dtype=np.int32)
W = UV[np.array(wuv).reshape(-1)]
print('input', len(V), 'verts', len(F), 'tris')

import pymeshlab
# load through a temp OBJ so MeshLab assigns a texture index to every wedge
tmp = '/tmp/_t2m'; os.makedirs(tmp, exist_ok=True)
Image.open(tex).convert('RGB').save(tmp + '/t.png')
open(tmp + '/m.mtl', 'w').write('newmtl m\nKd 1 1 1\nmap_Kd t.png\n')
uq, iv = np.unique(np.round(W, 7), axis=0, return_inverse=True); iv = iv.reshape(-1, 3)
with open(tmp + '/m.obj', 'w') as f:
    f.write('mtllib m.mtl\n')
    np.savetxt(f, V, fmt='v %.6f %.6f %.6f')
    np.savetxt(f, uq, fmt='vt %.7f %.7f')
    f.write('usemtl m\n')
    np.savetxt(f, np.stack([F[:, 0] + 1, iv[:, 0] + 1, F[:, 1] + 1, iv[:, 1] + 1, F[:, 2] + 1, iv[:, 2] + 1], 1), fmt='f %d/%d %d/%d %d/%d')
ms = pymeshlab.MeshSet()
ms.load_new_mesh(tmp + '/m.obj')
ms.meshing_remove_duplicate_vertices()
ms.meshing_remove_unreferenced_vertices()
ms.meshing_decimation_quadric_edge_collapse_with_texture(targetfacenum=target, qualitythr=0.5,
    preserveboundary=True, optimalplacement=True, preservenormal=True, planarquadric=True)
m = ms.current_mesh()
V2, F2 = m.vertex_matrix(), m.face_matrix()
W2 = m.wedge_tex_coord_matrix().reshape(-1, 3, 2)
print('output', len(V2), 'verts', len(F2), 'tris')

# normalize: 1.8 m tall, feet on y=0, centered on x/z
b0, b1 = V2.min(0), V2.max(0)
s = 1.8 / (b1[1] - b0[1])
ctr = (b0 + b1) / 2
V2 = (V2 - [ctr[0], b0[1], ctr[2]]) * s
print('bounds', V2.min(0).round(3), V2.max(0).round(3))

# write OBJ with per-wedge UVs (deduplicated)
uvk = np.round(W2.reshape(-1, 2), 6)
uniq, inv = np.unique(uvk, axis=0, return_inverse=True)
inv = inv.reshape(-1, 3)
tex_name = name + '_textura.jpg'
img = Image.open(tex).convert('RGB')
if max(img.size) > 2048:
    img = img.resize((2048, 2048), Image.LANCZOS)
img.save(os.path.join(out, tex_name), 'JPEG', quality=92)
with open(os.path.join(out, name + '.mtl'), 'w') as f:
    f.write('newmtl material_0\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 1\nmap_Kd %s\n' % tex_name)
with open(os.path.join(out, name + '.obj'), 'w') as f:
    f.write('mtllib %s.mtl\no %s\n' % (name, name))
    f.write(''.join('v %.6f %.6f %.6f\n' % tuple(v) for v in V2))
    f.write(''.join('vt %.6f %.6f\n' % tuple(t) for t in uniq))
    f.write('usemtl material_0\n')
    f.write(''.join('f %d/%d %d/%d %d/%d\n' % (a + 1, ta + 1, b + 1, tb + 1, c_ + 1, tc + 1)
                    for (a, b, c_), (ta, tb, tc) in zip(F2, inv)))
zp = os.path.join('/home/claude/brigada/out', name + '_para_mixamo.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(out)):
        z.write(os.path.join(out, fn), fn)
np.savez_compressed(os.path.join('/home/claude/brigada/out', name + '_mesh.npz'), V=V2, F=F2, W=W2)
print('zip', zp, os.path.getsize(zp) // 1024, 'KB')
