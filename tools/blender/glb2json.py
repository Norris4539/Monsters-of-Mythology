"""Convert a .glb into a self-contained glTF JSON (buffers embedded as base64)."""
import json, struct, base64, sys
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
gltf['buffers'][0]['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(binchunk).decode()
json.dump(gltf, open(dst, 'w'), separators=(',', ':'))
print(dst, len(open(dst).read()) // 1024, 'KB')
