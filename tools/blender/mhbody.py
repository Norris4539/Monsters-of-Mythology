"""Load the MakeHuman base mesh (CC0), apply shape targets, report joints."""
import os, math
from mathutils import Vector

def load_mh(obj_path, targets=()):
    """Returns verts (Blender Z-up metres), body faces with UVs, joint centres, eye vertex sets."""
    vs, vts, groups, cur = [], [], {}, None
    with open(obj_path) as f:
        for line in f:
            if line.startswith('v '):
                x, y, z = map(float, line.split()[1:4]); vs.append([x, y, z])
            elif line.startswith('vt '):
                u, v = map(float, line.split()[1:3]); vts.append((u, v))
            elif line.startswith('g '):
                cur = line.split()[1]; groups.setdefault(cur, [])
            elif line.startswith('f '):
                face = []
                for tok in line.split()[1:]:
                    p = tok.split('/'); face.append((int(p[0]) - 1, int(p[1]) - 1 if len(p) > 1 and p[1] else None))
                groups[cur].append(face)
    for path, w in targets:
        with open(path) as f:
            for line in f:
                if line.startswith('#') or not line.strip(): continue
                i, dx, dy, dz = line.split(); i = int(i)
                vs[i][0] += float(dx) * w; vs[i][1] += float(dy) * w; vs[i][2] += float(dz) * w
    # MakeHuman: Y up, decimetres, facing +Z. Blender: Z up, metres, facing -Y.
    conv = [Vector((x * .1, -z * .1, y * .1)) for x, y, z in vs]
    joints = {}
    for g, faces in groups.items():
        if g.startswith('joint-'):
            idx = {i for fc in faces for i, _ in fc}
            joints[g[6:]] = sum((conv[i] for i in idx), Vector()) / len(idx)
    return conv, vts, groups, joints
