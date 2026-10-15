"""Realistic Hydra line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow numpy):
    python tools/blender/hydra.py third_party/makehuman assets/models [--renders]
(the MakeHuman directory is not used, but the build takes the same arguments as the others).

The many-headed serpent of Lerna, after the reference sheets in refs/hydra: a heavy, low
body on four splayed legs like a giant monitor lizard, a long tapering tail, and the
necks rising from the shoulders in a fan, each with a serpent's head. Body, legs, feet
and the ridge of osteoderms are laid as ellipsoids along their lines and fused by a
voxel remesh; each neck is a tube lofted along an S-curve; each head is lofted from
sections, with its lower jaw hinged on its own bone, teeth and slit-pupilled eyes.
  L1 Marsh Hydra      about 6 m long, five necks, olive green and mud-brown scales
  L2 Lernaean Hydra   larger, seven necks, green-black scales with a bronze sheen, a ridge
                      of spines along the back and tail
  L3 Hydra Matriarch  largest, nine necks, the middle one longer and thicker with a larger
                      head (the immortal head), scarred black-green hide, pale gold eyes
One skeleton holds the body and every tier's necks; each tier's meshes are tagged L1_,
L2_ or L3_, and the gallery scales the second and third up from the first. Moves: Idle,
Walk (a lizard's trot with the body swinging), Strike (every head at once), Hit, Death.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import horse as HR
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, Mat
from peltast import bake_obj_xform

OUT = H.OUT
random.seed(41)
TIERS = {1: dict(n=5, scale=1.0), 2: dict(n=7, scale=1.12), 3: dict(n=9, scale=1.25)}


# ── Shape (metres; the hydra faces -Y, its left side at +X) ─────────────────
# Spine of the body from the root of the tail to the shoulders: (y, z of the centre,
# half-width, half-height). The belly hangs about 40 cm above the ground, as a monitor
# lizard's does on its splayed legs.
SPINE = [(1.3, .82, .42, .38), (1.0, .86, .56, .46), (.5, .9, .66, .52), (0, .92, .69, .54), (-.5, .95, .64, .52),
         (-.85, .99, .52, .46), (-1.05, 1.02, .38, .34)]
# The tail: (x, y, z, radius), curling a little to the left at its end.
TAIL = [(0, 1.3, .82, .38), (0, 1.75, .74, .31), (.04, 2.25, .62, .25), (.13, 2.75, .47, .19), (.27, 3.25, .32, .13),
        (.43, 3.7, .2, .09), (.58, 4.1, .11, .055), (.68, 4.4, .065, .03)]
# Legs (left side; the right mirrors it): joints and the limb's radius at each, the foot.
LEGS = {
    'F': dict(joints=[(.46, -.7, .84), (.97, -.78, .6), (1.02, -.9, .12)], radii=[.24, .17, .12], foot=(1.06, -1.02, .05)),
    'H': dict(joints=[(.44, .95, .8), (.99, .76, .55), (1.03, 1.05, .12)], radii=[.3, .19, .13], foot=(1.08, .92, .05)),
}

def neck_spec(tier, j):
    """The control points of neck j of a tier, its radius at the base and the head's size.
    The necks fan out across the chest: the middle ones tallest, the outer ones lower and
    further out to the sides, each rising in an S and carrying its head forward."""
    n = TIERS[tier]['n']; s = (j / (n - 1)) * 2 - 1; big = tier == 3 and j == n // 2
    B = V((.3 * s, -1.0 + .08 * s * s, 1.28 - .08 * s * s))
    Hd = V((1.45 * s, -1.4 + .3 * s * s, 3.55 - .8 * s * s + (.45 if big else 0)))
    P1 = B + V((.1 * s, -.08, .55))
    P2 = B.lerp(Hd, .55) + V((.25 * s, .38, .2))
    P3 = Hd + V((-.05 * s, .28, .02))
    k = 1.3 if big else 1.0
    return [B, P1, P2, P3, Hd], .17 * k, k

def catmull(pts, per=10):
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for k in range(per):
            t = k / per
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1].copy())
    return out

def resample(pts, n):
    """n+1 points spaced evenly by arc length along a polyline."""
    d = [0.0]
    for a, b in zip(pts, pts[1:]): d.append(d[-1] + (b - a).length)
    out = []
    for i in range(n + 1):
        t = d[-1] * i / n; k = max(0, min(len(d) - 2, next((m for m in range(len(d) - 1) if d[m + 1] >= t), len(d) - 2)))
        f = (t - d[k]) / max(1e-9, d[k + 1] - d[k]); out.append(pts[k].lerp(pts[k + 1], f))
    return out

def frames_along(pts):
    """A frame (tangent, normal, binormal) at each point, carried along without twisting."""
    T = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
    up = V((0, 0, 1)) if abs(T[0].z) < .9 else V((0, -1, 0))
    N = [(up - T[0] * up.dot(T[0])).normalized()]
    for i in range(1, len(pts)):
        n = N[-1] - T[i] * N[-1].dot(T[i]); N.append(n.normalized())
    return T, N, [t.cross(n) for t, n in zip(T, N)]

def head_axes(tier, j):
    """The head's forward and up directions: along the end of the neck, levelled out
    to point forward and a little down, turned a little outward."""
    pts, r0, k = neck_spec(tier, j); n = TIERS[tier]['n']; s = (j / (n - 1)) * 2 - 1
    f = (V((.35 * s, -1, -.18))).normalized()
    up = (V((0, 0, 1)) - f * f.z).normalized()
    return f, up, k


# ── Body ────────────────────────────────────────────────────────────────────
TOE_LEN = (.16, .21, .23, .2, .14)
def toe_dir(t, sx):
    """The direction of toe t (0 the innermost) of a foot on side sx: fanned from a little
    inward to well outward of straight ahead."""
    a = math.radians(-30 + 25 * t); return V((sx * math.sin(a), -math.cos(a), 0))

def dorsal(y):
    """(x, height of the top, half-width) of the body or tail at y."""
    if y <= SPINE[0][0]:
        rows = sorted(SPINE)
        for (y0, z0, w0, h0), (y1, z1, w1, h1) in zip(rows, rows[1:]):
            if y0 <= y <= y1: u = (y - y0) / (y1 - y0); return 0.0, z0 + h0 + (z1 + h1 - z0 - h0) * u, w0 + (w1 - w0) * u
        y0, z0, w0, h0 = rows[0]; return 0.0, z0 + h0, w0
    for (x0, y0, z0, r0), (x1, y1, z1, r1) in zip(TAIL, TAIL[1:]):
        if y0 <= y <= y1:
            u = (y - y0) / (y1 - y0); r = r0 + (r1 - r0) * u; return x0 + (x1 - x0) * u, z0 + (z1 - z0) * u + r * .92, r
    x, y1, z, r = TAIL[-1]; return x, z + r, r

def build_body(name):
    bm = bmesh.new()
    HR._chain(bm, [(0, y, z, w, h) for y, z, w, h in SPINE], step=.04)
    HR._chain(bm, [(x, y, z, r, r * .92) for x, y, z, r in TAIL], step=.035)
    for key, L in LEGS.items():
        J, R = L['joints'], L['radii']
        HR._chain(bm, [(*J[i], R[i], R[i]) for i in range(3)], step=.025, mirror=True)
        for sx in (1, -1):
            f = V(L['foot']); f.x *= sx
            HR._ellipsoid(bm, f, .14, .15, .05, Matrix.Identity(3))
            for t in range(5):   # five splayed toes, forward and out
                d = toe_dir(t, sx); ln = TOE_LEN[t]; base = f + d * .07
                HR._chain(bm, [(*(base + d * ln * u + V((0, 0, -.02 * u))), .032 - .012 * u, .024 - .009 * u) for u in (0, .5, 1)], step=.012)
    # the osteoderms: two rows of low ridged plates down the back and the tail
    for i in range(46):
        y = -.85 + 5.1 * i / 45; x, ztop, w = dorsal(y)
        spread = .16 if y < 1.3 else w * .4; size = max(.02, .06 * (1 - max(0, y - 1.3) / 3.4))
        for sx in (1, -1):
            HR._ellipsoid(bm, V((x + sx * spread, y, ztop - size * .3)), size * .8, size * 1.3, size * .9, Matrix.Identity(3))
    ob = obj_from_bm(name, bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.014); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=6, lambda_factor=.5, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.12); bake_mods(ob)
    for p in ob.data.polygons: p.use_smooth = True
    belly_attr(ob, lambda co, no: max(0.0, min(1.0, (-no.z - .15) / .5)) * (1 - max(0.0, min(1.0, (co.z - .9) / .3))))
    return ob

def belly_attr(ob, fn):
    """A 'belly' colour attribute (0 on the back, 1 underneath), for the paler belly scales."""
    me = ob.data; me.update(); attr = me.color_attributes.new('belly', 'FLOAT_COLOR', 'POINT')
    for v, a in zip(me.vertices, attr.data):
        b = fn(v.co, v.normal); a.color = (b, b, b, 1)

def claws(name, side_x=(1, -1)):
    bm = bmesh.new()
    for key, L in LEGS.items():
        for sx in side_x:
            f = V(L['foot']); f.x *= sx
            for t in range(5):
                d = toe_dir(t, sx); tip = f + d * (.07 + TOE_LEN[t]) + V((0, 0, -.02))
                bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=.013, radius2=.001, depth=.06,
                                      matrix=Matrix.Translation(tip + d * .02 + V((0, 0, -.004))) @ (d + V((0, 0, -.5))).normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4())
    return obj_from_bm(name, bm, smooth=False)

def spines(name):
    """The Lernaean hydra's ridge of spines along the back and the tail."""
    bm = bmesh.new()
    for i in range(34):
        t = i / 33; y = -.7 + 4.6 * t
        if y < 1.3:
            row = min(SPINE, key=lambda q: abs(q[0] - y)); z = row[1] + row[3]; x = 0; r = row[3]
        else:
            for (x0, y0, z0, r0), (x1, y1, z1, r1) in zip(TAIL, TAIL[1:]):
                if y0 <= y <= y1: u = (y - y0) / (y1 - y0); x = x0 + (x1 - x0) * u; z = z0 + (z1 - z0) * u; r = (r0 + (r1 - r0) * u) * .92
            z = z + r
        h = .26 * (1 - .75 * t) * (1 - .3 * abs(math.sin(i * 1.7)))
        d = V((0, .45, 1)).normalized()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=.05 * (1 - .6 * t) + .01, radius2=.002, depth=h,
                              matrix=Matrix.Translation(V((x, y, z - .02)) + d * h * .5) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4())
    return obj_from_bm(name, bm, smooth=False)


# ── Necks and heads ─────────────────────────────────────────────────────────
NECK_BONES = 5

def neck_curve(tier, j):
    pts, r0, k = neck_spec(tier, j)
    return resample(catmull(pts, 14), 60), r0, k

def build_necks(tier):
    """All of a tier's necks as one mesh, each a tube lofted along its curve with its own
    UV strip. Returns the mesh and, per vertex, (neck, how far along it) for the weights."""
    n = TIERS[tier]['n']; bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); where = []
    K = 20
    for j in range(n):
        C, r0, k = neck_curve(tier, j); T, N, Bn = frames_along(C)
        f, up, _ = head_axes(tier, j)
        rings = []
        for i, (p, t, nn, b) in enumerate(zip(C, T, N, Bn)):
            u = i / (len(C) - 1); r = r0 * (1 - .5 * u ** .8) * (1 + .12 * math.exp(-((u - .08) / .06) ** 2))
            if u < .02: p = p - t * .25   # bury the base in the chest
            row = []
            for q in range(K):
                a = 2 * math.pi * q / K; d = nn * math.cos(a) + b * math.sin(a)
                row.append(bm.verts.new(p + d * r * (1.0 if abs(math.sin(a)) > .3 else .93)))   # a little flattened front and back
                where.append((j, u))
            rings.append(row)
        for i in range(len(rings) - 1):
            for q in range(K):
                fc = bm.faces.new((rings[i][q], rings[i][(q + 1) % K], rings[i + 1][(q + 1) % K], rings[i + 1][q]))
                for lp, (a, c) in zip(fc.loops, ((q, i), (q + 1, i), (q + 1, i + 1), (q, i + 1))):
                    lp[uv].uv = ((j + a / K) / n, c / (len(rings) - 1))
        bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    ob = obj_from_bm(f'L{tier}_Necks', bm)
    # the throat: the side of each neck facing the way its head looks
    heads = [head_axes(tier, j)[0] for j in range(n)]
    belly_attr(ob, lambda co, no: 0.0)
    me = ob.data; attr = me.color_attributes['belly']
    for (j, u), v, a in zip(where, me.vertices, attr.data):
        f = V((heads[j].x, heads[j].y, 0)).normalized(); b = max(0.0, min(1.0, (v.normal.dot(f) - .62) / .25)); a.color = (b, b, b, 1)
    return ob, where

def head_sections(k):
    """(t along the head from the back of the skull to the snout, half-width, top, bottom)
    of the upper head, in units of its length."""
    return [(0, .21, .1, -.04), (.12, .25, .15, -.03), (.3, .25, .17, -.02), (.5, .21, .15, -.015),
            (.7, .16, .12, -.012), (.85, .12, .095, -.01), (.96, .08, .07, -.008), (1.0, .03, .045, -.006)]

def loft_sections(bm, secs, L, frame, K=24):
    """Loft elliptic sections (t, half-width, top, bottom) along a head of length L, in a
    frame (origin, forward, up): above the middle line the section reaches top, below it
    bottom (negative), both in units of L."""
    o, f, up = frame; side = f.cross(up)
    rings = []
    for t, w, top, bot in secs:
        c = o + f * (t * L); row = []
        for q in range(K):
            a = 2 * math.pi * q / K; x = math.cos(a); y = math.sin(a)
            hgt = (top if y > 0 else -bot) * L
            row.append(bm.verts.new(c + side * x * w * L + up * (y * hgt)))
        rings.append(row)
    for i in range(len(rings) - 1):
        for q in range(K): bm.faces.new((rings[i][q], rings[i][(q + 1) % K], rings[i + 1][(q + 1) % K], rings[i + 1][q]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

HEAD_L = .42

def build_heads(tier):
    """Upper heads, lower jaws, teeth and eyes of a tier's necks, each set as one mesh.
    Returns the meshes and per-vertex neck indices for the rigid weights."""
    n = TIERS[tier]['n']; parts = {}
    for kind in ('Heads', 'Jaws', 'Teeth', 'Eyes', 'Pupils'):
        bm = bmesh.new(); parts[kind] = (bm, bm.verts.layers.int.new('neck'))
    def add_part(kind, j, fn):
        """Build part of a head and mark its new vertices with the neck they belong to (+1):
        the bmesh operators reuse freed vertex slots, so the order cannot tell."""
        bm, lay = parts[kind]; fn(bm)
        for v in bm.verts:
            if v[lay] == 0: v[lay] = j + 1
    for j in range(n):
        C, r0, k = neck_curve(tier, j); f, up, _ = head_axes(tier, j); L = HEAD_L * k; o = C[-1] - f * .05 * k; side = f.cross(up)
        add_part('Heads', j, lambda bm: loft_sections(bm, head_sections(k), L, (o, f, up)))
        jaw = [(.04, .2, .02, -.075), (.2, .22, .02, -.07), (.45, .18, .02, -.055), (.7, .13, .018, -.04), (.9, .08, .015, -.03), (.98, .04, .012, -.02)]
        add_part('Jaws', j, lambda bm: loft_sections(bm, jaw, L, (o - up * .012 * k, f, up)))
        def teeth(bm):
            for s in (1, -1):
                for i in range(8):
                    t = .25 + .65 * i / 7; w = (.25 - .14 * (t - .25) / .65) * .92
                    p = o + f * (t * L) + side * (s * w * L) + up * (-.006 * L)
                    ln = (.07 if i == 6 else .035) * L
                    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=.009 * k * (1.6 if i == 6 else 1), radius2=.0008, depth=ln,
                                          matrix=Matrix.Translation(p - up * ln * .5) @ (-up).to_track_quat('Z', 'Y').to_matrix().to_4x4())
        add_part('Teeth', j, teeth)
        for s in (1, -1):
            e = o + f * (.36 * L) + side * (s * .2 * L) + up * (.09 * L)
            add_part('Eyes', j, lambda bm, e=e: bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=.028 * k, matrix=Matrix.Translation(e)))
            n_out = (side * s * .9 + f * .2 + up * .3).normalized()
            M = Matrix.Translation(e + n_out * .025 * k) @ n_out.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Diagonal((.004 * k, .016 * k, .006 * k, 1))
            add_part('Pupils', j, lambda bm, M=M: bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1, matrix=M))
    out = {}
    for kind, (bm, lay) in parts.items():
        ob = obj_from_bm(f'L{tier}_{kind}', bm, smooth=kind not in ('Teeth',))
        out[kind] = (ob, [a.value - 1 for a in ob.data.attributes['neck'].data])
    belly_attr(out['Heads'][0], lambda co, no: max(0.0, min(1.0, (-no.z - .1) / .5)))
    belly_attr(out['Jaws'][0], lambda co, no: max(0.0, min(1.0, (-no.z + .3) / .5)))
    return out


# ── Materials ───────────────────────────────────────────────────────────────
HIDES = {
    1: dict(dark='#2c2a17', base='#535231', light='#77703f', belly='#857b54', edge='#1c1a0e', metal=0.0, scars=0.0, eye='#d9b23a'),
    2: dict(dark='#0e130d', base='#1d2617', light='#38402a', belly='#4a4733', edge='#070906', metal=.35, scars=0.0, eye='#e0902a'),
    3: dict(dark='#0b0d0a', base='#172014', light='#2b3624', belly='#3b3a2c', edge='#050604', metal=.15, scars=.8, eye='#e8d38a'),
}

def m_scales(name, tier, scale=20.0, res=1024, scutes=None):
    """Scales: each cell its own shade between dark and light, dark seams between them,
    domed in the bump; the belly attribute blends to paler scales, laid in transverse
    plates where scutes gives their spacing (along the UV V, or object Y)."""
    c = HIDES[tier]; m = Mat(name, metal=c['metal'], res=res)
    vor = m.node('ShaderNodeTexVoronoi', Scale=scale); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    edge = m.node('ShaderNodeTexVoronoi', Scale=scale, feature='DISTANCE_TO_EDGE'); m.L.new(m.coord.outputs['Object'], edge.inputs['Vector'])
    shade = m.ramp(vor.outputs['Color'], [(.0, srgb(c['dark'])), (.45, srgb(c['base'])), (1.0, srgb(c['light']))])
    big = m.ramp(m.noise(2.5, 3, .5).outputs['Fac'], [(.35, (.8, .8, .8)), (.65, (1.15, 1.15, 1.15))])
    col = m.mix(shade.outputs['Color'], big.outputs['Color'], 1.0, 'MULTIPLY')
    seam = m.ramp(edge.outputs['Distance'], [(.0, (1, 1, 1)), (.06, (0, 0, 0))])
    col = m.mix(col, srgb(c['edge']), seam.outputs['Color'])
    attr = m.node('ShaderNodeAttribute', attribute_name='belly')
    bel = srgb(c['belly'])
    if scutes:
        src, freq = scutes
        sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs[src], sep.inputs['Vector'])
        mul = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(sep.outputs['Y'], mul.inputs[0]); mul.inputs[1].default_value = freq
        fr = m.node('ShaderNodeMath', operation='FRACT'); m.L.new(mul.outputs[0], fr.inputs[0])
        plate = m.ramp(fr.outputs[0], [(.0, tuple(x * .55 for x in bel)), (.12, bel), (.9, tuple(x * .85 for x in bel))])
        bel_col = plate.outputs['Color']
    else:
        bel_col = m.mix(bel, tuple(x * .7 for x in bel), seam.outputs['Color'])
    col = m.mix(col, bel_col, attr.outputs['Fac'])
    if c['scars']:   # pale old wounds raked across the hide
        mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Rotation'].default_value = (.3, .7, .2)
        w = m.node('ShaderNodeTexWave', wave_type='BANDS', Scale=3.0, Distortion=4.0, Detail=2.0); m.L.new(mp.outputs['Vector'], w.inputs['Vector'])
        lines = m.ramp(w.outputs['Fac'], [(.0, (0, 0, 0)), (.47, (0, 0, 0)), (.5, (1, 1, 1)), (.53, (0, 0, 0))])
        few = m.ramp(m.noise(3, 2, .5).outputs['Fac'], [(.55, (0, 0, 0)), (.62, (1, 1, 1))])
        sc = m.mix(lines.outputs['Color'], few.outputs['Color'], 1.0, 'MULTIPLY')
        col = m.mix(col, srgb('#7a6f62'), m.mix((0, 0, 0), sc, c['scars']))
    dome = m.ramp(edge.outputs['Distance'], [(.0, (0, 0, 0)), (.25, (1, 1, 1))])
    m.set(col, .5 if not c['metal'] else .38, dome.outputs['Color'], .5, .003)
    return m

def m_eye(tier):
    m = Mat(f'Eye{tier}', res=0); m.set(srgb(HIDES[tier]['eye']), .1); return m


# ── Rig ─────────────────────────────────────────────────────────────────────
BODY_BONES = ['hips', 'chest'] + [f'tail{i}' for i in range(6)] + [f'{p}{k}.{s}' for k in 'FH' for s in 'LR' for p in ('upper', 'lower', 'foot')]

def bones():
    B = [('root', (0, 0, 0), (0, -.5, 0), None, False),
         ('hips', (0, 1.05, .85), (0, 0, .9), 'root', True),
         ('chest', (0, 0, .9), (0, -1.0, 1.02), 'hips', True)]
    tail = resample(catmull([V((x, y, z)) for x, y, z, r in TAIL], 10), 6)
    prev = 'hips'
    for i in range(6):
        B.append((f'tail{i}', tuple(tail[i]), tuple(tail[i + 1]), prev, True)); prev = f'tail{i}'
    for k, L in LEGS.items():
        for sx, s in ((1, 'L'), (-1, 'R')):
            J = [V((x * sx, y, z)) for x, y, z in L['joints']]; ft = V(L['foot']); ft.x *= sx; toe = ft + V((0, -.2, -.02))
            par = 'chest' if k == 'F' else 'hips'
            B += [(f'upper{k}.{s}', tuple(J[0]), tuple(J[1]), par, True), (f'lower{k}.{s}', tuple(J[1]), tuple(J[2]), f'upper{k}.{s}', True),
                  (f'foot{k}.{s}', tuple(J[2]), tuple(toe), f'lower{k}.{s}', True)]
    for tier, T in TIERS.items():
        for j in range(T['n']):
            C, r0, kk = neck_curve(tier, j); P = resample(C, NECK_BONES); prev = 'chest'
            for b in range(NECK_BONES):
                nm = f'n{tier}_{j}_{b}'; B.append((nm, tuple(P[b]), tuple(P[b + 1]), prev, True)); prev = nm
            f, up, _ = head_axes(tier, j); L = HEAD_L * kk; o = C[-1] - f * .05 * kk
            B.append((f'h{tier}_{j}', tuple(o), tuple(o + f * L * .9), prev, True))
            hinge = o + f * .02 * kk - up * .015 * kk
            B.append((f'j{tier}_{j}', tuple(hinge), tuple(hinge + (f - up * .12).normalized() * L * .9), f'h{tier}_{j}', True))
    return B

def weight_necks(ob, where, tier):
    """Each neck's vertices to the two nearest bones of its chain by how far along it they
    lie, handing over to the chest at the base and to the head at the top."""
    names = [f'n{tier}_{j}_{b}' for j in range(TIERS[tier]['n']) for b in range(NECK_BONES)] + [f'h{tier}_{j}' for j in range(TIERS[tier]['n'])] + ['chest']
    for nm in names: ob.vertex_groups.new(name=nm)
    for v, (j, u) in zip(ob.data.vertices, where):
        x = u * NECK_BONES - .5; b0 = max(0, min(NECK_BONES - 1, math.floor(x))); f = max(0.0, min(1.0, x - b0))
        if x < 0: ws = {'chest': min(1, -x * 2), f'n{tier}_{j}_0': 1 - min(1, -x * 2)}
        elif b0 == NECK_BONES - 1: ws = {f'n{tier}_{j}_{b0}': 1 - f, f'h{tier}_{j}': f}
        else: ws = {f'n{tier}_{j}_{b0}': 1 - f, f'n{tier}_{j}_{b0 + 1}': f}
        for nm, w in ws.items():
            if w > .001: ob.vertex_groups[nm].add([v.index], w, 'REPLACE')

def weight_rigid(ob, idx, bone_of):
    for j in set(idx): ob.vertex_groups.new(name=bone_of(j))
    for v, j in zip(ob.data.vertices, idx): ob.vertex_groups[bone_of(j)].add([v.index], 1.0, 'REPLACE')

def skin(ob, rig):
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig


# ── Moves ───────────────────────────────────────────────────────────────────
REST = {}
def q(bone, axis, ang):
    """A pose rotation of a bone by ang about an axis given in the rest pose's space."""
    a = REST[bone].inverted() @ V(axis); return Quaternion(a.normalized(), ang)

def bend_axis(tier, j):
    """The axis that tips neck j forward and down, towards where its head looks."""
    f, up, k = head_axes(tier, j); h = V((f.x, f.y, 0)).normalized()
    return V((0, 0, 1)).cross(h)

def pose_hydra(rig, P):
    """P: {bone: quaternion} and 'root_loc'. Unlisted bones return to rest."""
    for pb in rig.pose.bones:
        pb.rotation_quaternion = P.get(pb.name, Quaternion()); pb.location = (0, 0, 0)
    rig.pose.bones['root'].location = REST['root'].inverted() @ V(P.get('root_loc', (0, 0, 0)))

def action(rig, name, length, fn, step=2):
    rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
    frames = sorted(set(list(range(1, length + 1, step)) + [length]))
    for f in frames:
        pose_hydra(rig, fn(f)); H._upd()
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_quaternion', frame=f); pb.keyframe_insert('location', frame=f)
    return act

def smooth(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a))); return x * x * (3 - 2 * x)

def necks(P, fn):
    """Apply fn(tier, j, b, axis) -> angle (b = 0..4 neck bones, 5 the head, 6 the jaw)."""
    for tier, T in TIERS.items():
        for j in range(T['n']):
            ax = bend_axis(tier, j); f, up, _ = head_axes(tier, j); hx = V((0, 0, 1)).cross(f)
            for b in range(NECK_BONES + 2):
                nm = f'n{tier}_{j}_{b}' if b < NECK_BONES else (f'h{tier}_{j}' if b == NECK_BONES else f'j{tier}_{j}')
                r = fn(tier, j, b, ax if b < NECK_BONES else hx)
                if isinstance(r, tuple):   # (pitch, yaw)
                    qq = q(nm, ax if b < NECK_BONES else hx, r[0]) @ q(nm, (0, 0, 1), r[1])
                else: qq = q(nm, ax if b < NECK_BONES else hx, r)
                P[nm] = P.get(nm, Quaternion()) @ qq

def legs(P, fn):
    """fn(key, side) -> (swing forward, lift, elbow bend) for each leg."""
    for k in 'FH':
        for s, sx in (('L', 1), ('R', -1)):
            sw, lift, bend = fn(k, s)
            P[f'upper{k}.{s}'] = q(f'upper{k}.{s}', (0, 0, 1), -sx * sw) @ q(f'upper{k}.{s}', (0, 1, 0), -sx * lift)
            P[f'lower{k}.{s}'] = q(f'lower{k}.{s}', (0, 1, 0), sx * bend)
            P[f'foot{k}.{s}'] = q(f'foot{k}.{s}', (0, 1, 0), sx * (lift - bend) * .6)

def tail(P, fn):
    for i in range(6):
        yaw, pitch = fn(i); P[f'tail{i}'] = q(f'tail{i}', (0, 0, 1), yaw) @ q(f'tail{i}', (1, 0, 0), pitch)

def actions(rig):
    for b in rig.data.bones: REST[b.name] = b.matrix_local.to_3x3()
    A = []
    def idle(f):
        P = {}; w = 2 * math.pi * f / 96
        necks(P, lambda t, j, b, ax: (.035 * math.sin(w + j * 1.3 + b * .5), .05 * math.sin(w * 2 + j * 2.1 + b * .3)) if b < 5 else
              ((.06 * math.sin(w * 2 + j), .1 * math.sin(w + j * 1.7)) if b == 5 else max(0, .25 * math.sin(w * 3 + j * 2.3) - .15)))
        tail(P, lambda i: (.03 * math.sin(w - i * .5), 0)); P['chest'] = q('chest', (1, 0, 0), .01 * math.sin(w * 2))
        return P
    A.append(action(rig, 'Idle', 96, idle, 3))
    def walk(f):
        P = {}; w = 2 * math.pi * (f - 1) / 40
        def leg(k, s):
            ph = w + (0 if (k, s) in (('F', 'L'), ('H', 'R')) else math.pi)
            return .34 * math.sin(ph), .3 * max(0, math.cos(ph)), .25 * max(0, math.cos(ph))
        legs(P, leg)
        P['hips'] = q('hips', (0, 0, 1), -.07 * math.sin(w)); P['chest'] = q('chest', (0, 0, 1), .14 * math.sin(w))
        P['root_loc'] = (0, 0, .02 * math.cos(2 * w))
        tail(P, lambda i: (.06 * math.sin(w - .7 - i * .55) * (1 + i * .2), 0))
        necks(P, lambda t, j, b, ax: (.03 * math.sin(2 * w + b * .6), -.06 * math.sin(w) if b == 0 else 0) if b < 5 else (.05 * math.sin(2 * w + .5) if b == 5 else 0))
        return P
    A.append(action(rig, 'Walk', 40, walk))
    def strike(f):
        P = {}
        def neck(t, j, b, ax):
            d = j % 3   # the heads strike a frame or two apart
            back, hit, rec = smooth(1, 11 + d, f), smooth(12 + d, 17 + d, f), smooth(24 + d, 40, f)
            if b < 5: return (-.12 * back + (.3 if b == 0 else .16) * hit) * (1 - rec)
            if b == 5: return (-.25 * back + .55 * hit) * (1 - rec)
            return (.15 * back + .55 * smooth(9 + d, 14 + d, f) - .7 * smooth(15 + d, 17 + d, f)) * (1 - rec) + .0
        necks(P, neck)
        lunge = smooth(11, 17, f) * (1 - smooth(26, 40, f))
        P['chest'] = q('chest', (1, 0, 0), .1 * lunge - .05 * smooth(1, 11, f) * (1 - smooth(12, 16, f)))
        P['root_loc'] = (0, -.15 * lunge, 0)
        legs(P, lambda k, s: (.12 * lunge if k == 'H' else -.08 * lunge, 0, 0))
        tail(P, lambda i: (0, .04 * lunge))
        return P
    A.append(action(rig, 'Strike', 40, strike))
    def hit(f):
        P = {}; e = smooth(1, 4, f) * (1 - smooth(6, 20, f))
        necks(P, lambda t, j, b, ax: (-.14 * e * (1 + .3 * math.sin(j * 2.1)), .08 * e * math.sin(j * 1.7)) if b < 5 else (-.4 * e if b == 5 else .5 * e))
        P['chest'] = q('chest', (1, 0, 0), -.06 * e) @ q('chest', (0, 0, 1), .05 * e); P['root_loc'] = (0, .12 * e, 0)
        tail(P, lambda i: (.1 * e * math.sin(i), 0))
        return P
    A.append(action(rig, 'Hit', 20, hit))
    def death(f):
        P = {}; sink = smooth(8, 30, f); flop = lambda j: smooth(12 + 3 * (j % 4), 36 + 3 * (j % 4), f)
        def neck(t, j, b, ax):
            s = flop(j); n = TIERS[t]['n']; side = (j / (n - 1)) * 2 - 1
            # toppled at the root, the S of the neck straightened so it lies out flat
            if b < 5: return ((1.25, .05, -.3, -.42, -.3)[b] * s - .12 * smooth(1, 6, f) * (1 - s), .3 * side * s if b == 0 else 0)
            return (-.15 * s if b == 5 else .35 * s)
        necks(P, neck)
        P['root_loc'] = (0, 0, -.5 * sink)
        legs(P, lambda k, s: (0, .85 * sink, -.4 * sink))
        P['chest'] = q('chest', (1, 0, 0), .06 * sink); tail(P, lambda i: (.05 * sink * i, .06 * sink if i < 2 else -.03 * sink))
        return P
    A.append(action(rig, 'Death', 60, death))
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    items = {}
    def add(ob, mt, bind, extra=None): items[ob.name] = (ob, mt, bind, extra); return ob
    body = build_body('L1_Body'); bodies = {1: body}
    for t in (2, 3):
        b = link(body.copy()); b.data = body.data.copy(); b.name = f'L{t}_Body'; bodies[t] = b
    claw = H.m_flat('Claw', '#1a1612', .45)
    for t in (1, 2, 3):
        add(bodies[t], m_scales(f'Hide{t}', t, 20.0, 2048, scutes=('Object', 6.0)), 'body')
        add(claws(f'L{t}_Claws'), claw, 'body-near')
        nk, where = build_necks(t); add(nk, m_scales(f'NeckHide{t}', t, 26.0, 2048, scutes=('UV', 70.0)), 'necks', where)
        hd = build_heads(t)
        add(hd['Heads'][0], m_scales(f'HeadHide{t}', t, 45.0, 1024), 'heads', hd['Heads'][1])
        add(hd['Jaws'][0], m_scales(f'JawHide{t}', t, 45.0, 512), 'jaws', hd['Jaws'][1])
        add(hd['Teeth'][0], H.m_flat('Teeth', '#e2d9c0', .35), 'heads', hd['Teeth'][1])
        add(hd['Eyes'][0], m_eye(t), 'heads', hd['Eyes'][1])
        add(hd['Pupils'][0], H.m_flat('Pupil', '#050403', .1), 'heads', hd['Pupils'][1])
    add(spines('L2_Spines'), H.m_bronze('SpineHorn', .1, 512), 'body-near')
    H.bake_textures({k: v[:3] for k, v in items.items()})
    rig = HR.build_rig('HydraRig', bones())
    rig.data.pose_position = 'REST'; H._upd()
    body_def = set(BODY_BONES)
    for b in rig.data.bones: b.use_deform = b.name in body_def
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for b in rig.data.bones: b.use_deform = b.name != 'root'
    import talos as T
    for t in (2, 3):
        T.copy_weights(body, bodies[t]); skin(bodies[t], rig)
    for name, (ob, mt, bind, extra) in items.items():
        if ob in bodies.values(): continue
        t = int(name[1])
        if bind == 'body-near': H.bind_skin(ob, rig, body)
        elif bind == 'necks': weight_necks(ob, extra, t); skin(ob, rig)
        elif bind == 'heads': weight_rigid(ob, extra, lambda j, t=t: f'h{t}_{j}'); skin(ob, rig)
        elif bind == 'jaws': weight_rigid(ob, extra, lambda j, t=t: f'j{t}_{j}'); skin(ob, rig)
    rig.data.pose_position = 'POSE'; H._upd()
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.validate(): print('repaired', ob.name)   # the glTF exporter checks this too
    return rig, actions(rig)

def renders(rig):
    from PIL import Image
    shots = []
    for t in (1, 2, 3):
        k = TIERS[t]['scale']; rig.scale = (k, k, k)
        p = os.path.join(OUT, f'hydra_L{t}.png')
        H.render(rig, p, 'Idle', 1, t, cam=((6.2, -9.0, 3.6), (80, 0, 35)), res=(620, 640), samples=24); shots.append(p)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'hydra_lineup.png'))
    rig.scale = (1, 1, 1)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'hydra.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'hydra.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
