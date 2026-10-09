"""Convert a .glb into a self-contained glTF JSON (buffers embedded as base64).

Skin weights are stored as normalized bytes and UVs inside [0, 1] as normalized
shorts (both allowed by the glTF spec), which keeps the base64 file well under
the artifact size limit."""
import json, struct, base64, sys
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
magic, ver, length = struct.unpack_from('<4sII', data, 0)
assert magic == b'glTF'
off, gltf, binchunk = 12, None, b''
while off < length:
    clen, ctype = struct.unpack_from('<I4s', data, off); off += 8
    chunk = data[off:off + clen]; off += clen
    if ctype == b'JSON': gltf = json.loads(chunk)
    elif ctype == b'BIN\x00': binchunk = chunk

FLOAT, UBYTE, USHORT = 5126, 5121, 5123
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
views, accs = gltf['bufferViews'], gltf['accessors']

def read(i):
    a = accs[i]; v = views[a['bufferView']]
    dt = {FLOAT: np.float32, UBYTE: np.uint8, USHORT: np.uint16, 5125: np.uint32, 5120: np.int8, 5122: np.int16}[a['componentType']]
    n = NCOMP[a['type']]; stride = v.get('byteStride', 0)
    start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    if stride and stride != n * np.dtype(dt).itemsize:
        raw = np.frombuffer(binchunk, np.uint8, a['count'] * stride, start).reshape(a['count'], stride)
        return raw[:, :n * np.dtype(dt).itemsize].copy().view(dt).reshape(a['count'], n)
    return np.frombuffer(binchunk, dt, a['count'] * n, start).reshape(a['count'], n).copy()

def quantize(i, kind):
    a = accs[i]
    if a['componentType'] != FLOAT or a.get('sparse'): return None
    x = read(i)
    if kind == 'WEIGHTS':
        q = np.round(x * 255).astype(np.int32)
        q[np.arange(len(q)), q.argmax(1)] += 255 - q.sum(1)   # keep each row summing to exactly 1
        out, ct = q.clip(0, 255).astype(np.uint8), UBYTE
    else:
        if x.min() < 0 or x.max() > 1: return None
        out, ct = np.round(x * 65535).astype(np.uint16), USHORT
    a.update(componentType=ct, normalized=True); a.pop('min', None); a.pop('max', None)
    return out

# Rebuild the binary chunk view by view, swapping in the quantized arrays.
replace = {}
for m in gltf['meshes']:
    for p in m['primitives']:
        for k, i in p['attributes'].items():
            kind = 'WEIGHTS' if k.startswith('WEIGHTS_') else 'UV' if k.startswith('TEXCOORD_') else None
            if kind and i not in replace:
                q = quantize(i, kind)
                if q is not None: replace[i] = q
by_view = {}
for i, a in enumerate(accs):
    if 'bufferView' in a: by_view.setdefault(a['bufferView'], []).append(i)
out = bytearray()
for vi, v in enumerate(views):
    own = by_view.get(vi, [])
    if len(own) == 1 and own[0] in replace:
        blob = replace[own[0]].tobytes(); accs[own[0]]['byteOffset'] = 0; v.pop('byteStride', None)
    else:
        blob = binchunk[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']]
    while len(out) % 4: out.append(0)
    v['byteOffset'] = len(out); v['byteLength'] = len(blob); out += blob
gltf['buffers'][0]['byteLength'] = len(out)
gltf['buffers'][0]['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(bytes(out)).decode()
json.dump(gltf, open(dst, 'w'), separators=(',', ':'))
print(dst, len(open(dst).read()) // 1024, 'KB', f'({len(replace)} accessors quantized)')
