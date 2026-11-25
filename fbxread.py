"""Minimal binary FBX (7.x) reader: geometry, UVs, model transforms, global settings."""
import struct, zlib, sys
import numpy as np

ARR = {b'f': ('<f4', 4), b'd': ('<f8', 8), b'l': ('<i8', 8), b'i': ('<i4', 4), b'b': ('u1', 1)}


class Node:
    __slots__ = ('name', 'props', 'kids')

    def __init__(self, name, props, kids):
        self.name, self.props, self.kids = name, props, kids

    def find(self, name):
        return [k for k in self.kids if k.name == name]

    def first(self, name):
        r = self.find(name)
        return r[0] if r else None


def _props(d, p, n):
    out = []
    for _ in range(n):
        t = d[p:p + 1]; p += 1
        if t == b'Y': out.append(struct.unpack_from('<h', d, p)[0]); p += 2
        elif t == b'C': out.append(bool(d[p])); p += 1
        elif t == b'I': out.append(struct.unpack_from('<i', d, p)[0]); p += 4
        elif t == b'F': out.append(struct.unpack_from('<f', d, p)[0]); p += 4
        elif t == b'D': out.append(struct.unpack_from('<d', d, p)[0]); p += 8
        elif t == b'L': out.append(struct.unpack_from('<q', d, p)[0]); p += 8
        elif t in ARR:
            ln, enc, clen = struct.unpack_from('<III', d, p); p += 12
            raw = d[p:p + clen]; p += clen
            if enc == 1: raw = zlib.decompress(raw)
            dt, _sz = ARR[t]
            out.append(np.frombuffer(raw, dtype=dt, count=ln))
        elif t in (b'S', b'R'):
            ln = struct.unpack_from('<I', d, p)[0]; p += 4
            v = d[p:p + ln]; p += ln
            out.append(v.decode('utf-8', 'replace') if t == b'S' else v)
        else:
            raise ValueError('prop type %r at %d' % (t, p))
    return out, p


def _node(d, p, wide):
    if wide:
        end, nprops, plen = struct.unpack_from('<QQQ', d, p); p += 24
    else:
        end, nprops, plen = struct.unpack_from('<III', d, p); p += 12
    nl = d[p]; p += 1
    if end == 0:
        return None, p
    name = d[p:p + nl].decode('ascii', 'replace'); p += nl
    props, p2 = _props(d, p, nprops)
    p = p + plen
    kids = []
    sentinel = 25 if wide else 13
    while p < end - sentinel or (p < end and d[p:p + sentinel] != b'\0' * sentinel):
        k, p = _node(d, p, wide)
        if k is None:
            break
        kids.append(k)
    return Node(name, props, kids), end


def load(path):
    d = open(path, 'rb').read()
    assert d[:20] == b'Kaydara FBX Binary  ', 'not binary FBX'
    ver = struct.unpack_from('<I', d, 23)[0]
    wide = ver >= 7500
    p, top = 27, []
    while p < len(d):
        n, p = _node(d, p, wide)
        if n is None:
            break
        top.append(n)
    return ver, Node('root', [], top)


def p70(node):
    out = {}
    pp = node.first('Properties70') if node else None
    if pp:
        for k in pp.find('P'):
            out[k.props[0]] = k.props[4:]
    return out


def geometry(root):
    """Return list of dicts: verts (N,3), polys (list of index lists), uv (M,2) and per-corner uv index."""
    objs = root.first('Objects')
    res = []
    for g in objs.find('Geometry'):
        V = g.first('Vertices').props[0].reshape(-1, 3).astype(np.float64)
        pvi = g.first('PolygonVertexIndex').props[0].astype(np.int64)
        polys, cur = [], []
        for i in pvi:
            if i < 0:
                cur.append(-i - 1); polys.append(cur); cur = []
            else:
                cur.append(int(i))
        corner_uv = None
        uvs = None
        le = g.first('LayerElementUV')
        if le is not None:
            uvs = le.first('UV').props[0].reshape(-1, 2).astype(np.float64)
            mapping = le.first('MappingInformationType').props[0]
            ref = le.first('ReferenceInformationType').props[0]
            idx = le.first('UVIndex').props[0].astype(np.int64) if le.first('UVIndex') else None
            nc = len(pvi)
            if mapping == 'ByPolygonVertex':
                corner_uv = idx if ref.startswith('IndexToDirect') else np.arange(nc)
            elif mapping in ('ByVertice', 'ByVertex'):
                vi = np.array([i if i >= 0 else -i - 1 for i in pvi])
                corner_uv = idx[vi] if ref.startswith('IndexToDirect') else vi
        res.append(dict(id=g.props[0], name=g.props[1], verts=V, polys=polys, uvs=uvs, corner_uv=corner_uv))
    return res


if __name__ == '__main__':
    ver, root = load(sys.argv[1])
    print('FBX', ver)
    gs = p70(root.first('GlobalSettings'))
    for k in ('UpAxis', 'UpAxisSign', 'FrontAxis', 'FrontAxisSign', 'CoordAxis', 'UnitScaleFactor', 'OriginalUnitScaleFactor'):
        print(' ', k, gs.get(k))
    objs = root.first('Objects')
    for m in objs.find('Model'):
        pr = p70(m)
        print(' Model', m.props[1], m.props[2], {k: pr[k][-3:] for k in pr if k.startswith('Lcl') or k in ('PreRotation', 'GeometricTranslation', 'GeometricRotation', 'GeometricScaling')})
    for g in geometry(root):
        V = g['verts']
        tri = sum(len(p) - 2 for p in g['polys'])
        print(' Geometry', g['name'], 'verts', len(V), 'polys', len(g['polys']), 'tris', tri,
              'uvs', None if g['uvs'] is None else len(g['uvs']), 'bounds', V.min(0).round(3), V.max(0).round(3))
