"""A small ancient Greek horse for the cavalry lines, built in Blender.

About 13.5 hands (1.37 m at the withers), compact and deep-bodied, dark brown with black
points, a cropped upright mane, a full tail, unshod hooves, a bridle with a bronze bit, and
a sheepskin held by a braided girth and breast strap: no saddle, no stirrups.

The shape is traced from the side view of the reference sheet (OUTLINE, in its pixels)
and inflated: a Poisson solve inside the outline gives round sections across any part
of it, scaled to the widths measured on the sheet's front and back views (WIDTH_K) and
squared off where the horse is flat (SQUARE). The legs are laid joint to joint at the
sheet's joints, a few small masses add the cheeks, brows, nostrils and hocks, and a
voxel remesh fuses it all. Bones are named h_*, so a rider's skeleton can share the
armature; `hpose` places the legs by their hoof targets (a two-bone solve for the upper
leg, the cannon and pastern set by angle), and `gait` makes walk and gallop cycles from
leg phases.
"""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
import hoplite as H
import peltast as P
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, Mat, m_leather, m_bronze
from peltast import curve_mesh, Surf, m_fur


# ── Shape, traced from the reference sheet ─────────────────────────────────
# The side view of the sheet is traced in its own pixels (x forward, y down) and mapped
# onto the horse's frame: it faces -Y like the riders, z is up, the ground at z = 0.
WITHERS = 1.37
PX = WITHERS / 215           # metres per pixel: the withers stand 215 px above the ground
PX_X0, PX_GROUND = 125, 837  # the middle of the back (under the rider) and the ground line

def px(x, y, lat=0.0): return V((lat, (PX_X0 - x) * PX, (PX_GROUND - y) * PX))

# Trunk, neck and head in profile, from the root of the tail along the back: the line
# runs under the mane, the sheepskin and the tail, and across the tops of the legs.
OUTLINE = [(43, 647), (46, 643), (50, 640), (58, 637), (68, 635), (78, 633), (90, 631), (105, 629), (120, 630),
           (135, 629), (148, 626), (158, 622), (166, 617), (175, 611), (185, 604), (195, 597), (205, 591), (215, 586),
           (225, 582), (233, 579), (240, 577), (246, 577), (251, 580), (256, 586), (261, 594), (266, 602), (271, 610),
           (276, 618), (280, 625), (284, 631), (287, 637), (287, 643), (284, 648), (279, 652), (272, 653), (265, 650),
           (258, 645), (252, 639), (246, 633), (241, 629), (236, 626), (232, 627), (229, 633), (227, 642), (225, 652),
           (223, 662), (221, 672), (219, 682), (218, 692), (215, 702), (211, 711), (206, 719), (198, 724), (188, 727),
           (176, 728), (165, 727), (150, 724), (138, 721), (125, 717), (112, 712), (100, 708), (92, 709), (85, 714),
           (75, 722), (62, 726), (50, 728), (45, 728), (42, 717), (38, 704), (36, 689), (37, 675), (40, 661), (42, 652)]
# How wide the inflated profile is against how deep it is, at points of the side view (px):
# near round through the barrel, narrower over the shoulders and in the head.
WIDTH_K = [((130, 675), .9), ((95, 670), .95), ((80, 665), 1.0), ((62, 680), 1.12), ((45, 690), 1.0), ((160, 690), .9),
           ((195, 690), .92), ((212, 700), .9), ((178, 640), .78), ((205, 630), .64), ((222, 610), .6), ((234, 598), .48),
           ((245, 615), .62), ((249, 586), 1.2), ((258, 598), 1.0), ((265, 615), .8), ((275, 632), .86), ((284, 641), 1.05)]
# How square the upright sections are along the body (1 = as inflated, lower = boxier):
# the head is flat across the forehead and between the jaws.
SQUARE = [(38, .8), (50, .72), (90, .75), (150, .85), (200, .92), (228, 1.0), (240, .78), (290, .66)]
# Legs: centre (px), distance out from the midline (m), half-depth and half-width (px)
LEG_F = [(200, 696, .158, 12, 11), (193, 707, .16, 14, 12), (189, 716, .155, 15, 11.5), (187.5, 726, .15, 14.5, 11),
         (187, 740, .145, 12, 9.5), (186, 755, .14, 10, 8.5), (185.5, 765, .137, 9.5, 8), (185, 775, .135, 10, 8.5),
         (184.5, 783, .133, 8, 7), (184, 792, .13, 7, 6), (184, 802, .13, 7, 6), (184, 812, .13, 9.5, 8),
         (186.5, 819, .128, 8, 7.5), (189, 825, .127, 7.5, 7.5)]
LEG_H = [(76, 690, .18, 20, 15), (68, 708, .175, 20, 14), (62, 725, .165, 18, 12.5), (58.5, 740, .155, 12.5, 10),
         (55, 754, .147, 8.5, 8), (50.5, 765, .14, 9, 8), (48.5, 775, .135, 7, 6.5), (48, 788, .132, 6.5, 5.5),
         (48, 800, .13, 6.5, 5.5), (48, 812, .13, 9, 7.5), (50, 819, .128, 7.5, 7), (52, 825, .127, 7.5, 7.5)]
# Smaller masses the outline cannot give: centre (px), distance out from the midline, radii
# (across, along, height) in m, and the along direction in px
MASSES = [((44, 766), .14, (.02, .022, .03), (0, 1)),      # point of the hock
          ((244, 622), .055, (.04, .07, .055), (45, 57)),  # cheeks
          ((253, 594), .074, (.03, .035, .03), (45, 57)),  # brows over the eyes
          ((282, 633), .042, (.022, .03, .025), (45, 57))] # nostrils
OUTLINE_X = (min(p[0] for p in OUTLINE), max(p[0] for p in OUTLINE))
HOOF_PX = {'F': 191, 'H': 54}
HOOF_Y = {k: (PX_X0 - v) * PX for k, v in HOOF_PX.items()}
HOOF_X = .127

# Bones: name, head, tail, parent, deform. Leg bones run joint to joint, at the sheet's joints.
def bones():
    B = [('h_root', (0, 0, 0), (0, -.4, 0), None, False),
         ('h_body', (0, .2, 1.0), (0, -.22, 1.0), 'h_root', True),
         ('h_pelvis', (0, .2, 1.02), (0, .5, 1.14), 'h_body', True),
         ('h_chest', (0, -.22, 1.02), (0, -.46, 1.08), 'h_body', True),
         ('h_saddle', (0, -.1, 1.36), (0, .1, 1.36), 'h_body', False),
         ('h_neck1', (0, -.44, 1.1), (0, -.58, 1.33), 'h_chest', True),
         ('h_neck2', (0, -.58, 1.33), (0, -.715, 1.59), 'h_neck1', True),
         ('h_head', (0, -.715, 1.59), (0, -1.02, 1.25), 'h_neck2', True),
         ('h_tail1', (0, .53, 1.2), (0, .565, 1.06), 'h_pelvis', True),
         ('h_tail2', (0, .565, 1.06), (0, .58, .9), 'h_tail1', True),
         ('h_tail3', (0, .58, .9), (0, .585, .72), 'h_tail2', True),
         ('h_tail4', (0, .585, .72), (0, .58, .52), 'h_tail3', True)]
    J = {'scap': px(165, 630, .11), 'shoulder': px(210, 688, .15), 'elbow': px(184, 720, .15), 'knee': px(185, 773, .135),
         'fetF': px(185, 812, .13), 'hoofF': px(HOOF_PX['F'], 831, HOOF_X),
         'hip': px(68, 668, .15), 'stifle': px(88, 705, .19), 'hock': px(49, 767, .137), 'fetH': px(48, 812, .13),
         'hoofH': px(HOOF_PX['H'], 831, HOOF_X)}
    for s, n in ((1, 'L'), (-1, 'R')):
        j = {k: tuple(V((v.x * s, v.y, v.z))) for k, v in J.items()}
        B += [(f'h_scap.{n}', j['scap'], j['shoulder'], 'h_chest', True),
              (f'h_humerus.{n}', j['shoulder'], j['elbow'], f'h_scap.{n}', True),
              (f'h_radius.{n}', j['elbow'], j['knee'], f'h_humerus.{n}', True),
              (f'h_cannonF.{n}', j['knee'], j['fetF'], f'h_radius.{n}', True),
              (f'h_pasternF.{n}', j['fetF'], j['hoofF'], f'h_cannonF.{n}', True),
              (f'h_femur.{n}', j['hip'], j['stifle'], 'h_pelvis', True),
              (f'h_tibia.{n}', j['stifle'], j['hock'], f'h_femur.{n}', True),
              (f'h_cannonH.{n}', j['hock'], j['fetH'], f'h_tibia.{n}', True),
              (f'h_pasternH.{n}', j['fetH'], j['hoofH'], f'h_cannonH.{n}', True)]
    return B

BONE_NAMES = [b[0] for b in bones()]
LEGS = {  # leg: (upper, lower, cannon, pastern, which way the middle joint bends)
    'LF': ('h_humerus.L', 'h_radius.L', 'h_cannonF.L', 'h_pasternF.L', V((0, 1, 0))),
    'RF': ('h_humerus.R', 'h_radius.R', 'h_cannonF.R', 'h_pasternF.R', V((0, 1, 0))),
    'LH': ('h_femur.L', 'h_tibia.L', 'h_cannonH.L', 'h_pasternH.L', V((0, -1, 0))),
    'RH': ('h_femur.R', 'h_tibia.R', 'h_cannonH.R', 'h_pasternH.R', V((0, -1, 0))),
}


# ── Mesh ────────────────────────────────────────────────────────────────────
def _frame(d):
    """An orthonormal frame with Y along d and X as close to the world's X as allowed."""
    y = d.normalized(); x = V((1, 0, 0)); x = (x - y * x.dot(y))
    x = x.normalized() if x.length > 1e-6 else V((0, 0, 1)).cross(y).normalized()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()

def _ellipsoid(bm, c, rx, ry, rz, R):
    M = Matrix.Translation(c) @ R.to_4x4() @ Matrix.Diagonal((rx, ry, rz, 1))
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1, matrix=M)

def _chain(bm, pts, step=.012, mirror=False):
    """Ellipsoids laid densely along a line through pts (x, y, z, half-width, half-height)."""
    for sx in ((1, -1) if mirror else (1,)):
        P_ = [(V((x * sx, y, z)), rw, rh) for x, y, z, rw, rh in pts]
        for (a, wa, ha), (b, wb, hb) in zip(P_, P_[1:]):
            d = b - a; n = max(1, int(d.length / step))
            R = _frame(d)
            for i in range(n + (1 if (b, wb, hb) == P_[-1] else 0)):
                t = i / n; c = a.lerp(b, t); rw = wa + (wb - wa) * t; rh = ha + (hb - ha) * t
                _ellipsoid(bm, c, rw, max(rw, rh) * .9, rh, R)

def _hits(o, d):
    """Distances along the ray o + t d (sheet pixels) at which it crosses the outline."""
    out = []
    for (ax, ay), (bx, by) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        ex, ey = bx - ax, by - ay; den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12: continue
        t = ((ax - o[0]) * ey - (ay - o[1]) * ex) / den; u = ((ax - o[0]) * d[1] - (ay - o[1]) * d[0]) / den
        if t > 1e-9 and 0 <= u <= 1: out.append(t)
    return sorted(out)

def _inside(X, Y):
    """Even-odd test of grid points against the outline."""
    ins = np.zeros(X.shape, bool)
    for (ax, ay), (bx, by) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        c = ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / ((by - ay) or 1e-9) + ax)
        ins ^= c
    return ins

def _inflate(x0=30, x1=296, y0=570, y1=736):
    """Half-widths (px) of the inflated profile on a 1 px grid: solve lap(h) = -1 inside the
    outline with h = 0 on it, so sqrt(2h) is a round section across any strip, then scale
    by WIDTH_K. Solved coarse to fine."""
    h = None
    for res in (4, 2, 1):
        xs, ys = np.arange(x0, x1, res, dtype=float), np.arange(y0, y1, res, dtype=float)
        X, Y = np.meshgrid(xs, ys); ins = _inside(X, Y)
        if h is None: h = np.zeros(X.shape)
        else: h = np.kron(h, np.ones((2, 2)))[:X.shape[0], :X.shape[1]]
        h = np.pad(h, ((0, X.shape[0] - h.shape[0]), (0, X.shape[1] - h.shape[1])))
        red = (np.add.outer(np.arange(X.shape[0]), np.arange(X.shape[1])) % 2) == 0
        for _ in range(400 if res == 4 else 250):   # red-black over-relaxation
            for cells in (ins & red, ins & ~red):
                hn = (np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1) + res * res) / 4
                h = np.where(cells, h + 1.85 * (hn - h), h)
        h = np.where(ins, h, 0.0)
    wsum = np.zeros(X.shape); ksum = np.zeros(X.shape)
    for (cx, cy), k in WIDTH_K:
        g = np.exp(-((X - cx) ** 2 + (Y - cy) ** 2) / (2 * 16.0 ** 2)); wsum += g; ksum += g * k
    return xs, ys, (ksum / np.maximum(wsum, 1e-9)) * np.sqrt(2 * np.maximum(h, 0))

def _lerp(table, x):
    for (x0, v0), (x1, v1) in zip(table, table[1:]):
        if x <= x1: return v0 + (v1 - v0) * max(0.0, (x - x0) / (x1 - x0))
    return table[-1][1]

def _sample(grid, x, y):
    xs, ys, W = grid; step = xs[1] - xs[0]
    i = min(max((x - xs[0]) / step, 0), len(xs) - 1.001); j = min(max((y - ys[0]) / step, 0), len(ys) - 1.001)
    i0, j0 = int(i), int(j); fi, fj = i - i0, j - j0
    return (W[j0, i0] * (1 - fi) * (1 - fj) + W[j0, i0 + 1] * fi * (1 - fj) + W[j0 + 1, i0] * (1 - fi) * fj + W[j0 + 1, i0 + 1] * fi * fj)

def _body_loft(bm, grid, step=1.5, K=24):
    """The inflated trunk, neck and head as one loft of upright sections from tail to nose."""
    rings = []; x = OUTLINE_X[0] + .3
    while x < OUTLINE_X[1] - .2:
        h = _hits((x, 400), (0, 1))
        if len(h) >= 2:
            top, bot = 400 + h[0], 400 + h[-1]
            zs = [top + (bot - top) * (1 - math.cos(math.pi * i / K)) / 2 for i in range(K + 1)]
            side = [(_sample(grid, x, z), z) for z in zs]
            wmax = max(w for w, z in side) or 1; g = _lerp(SQUARE, x)
            u = min(1.0, max(0.0, (x - 38) / 24)); taper = .72 + .28 * u * u * (3 - 2 * u)   # a rounder rump
            side = [(taper * wmax * (w / wmax) ** g, z) for w, z in side]
            pts = side + [(-w, z) for w, z in side[-2:0:-1]]
            rings.append([bm.verts.new(px(x, z, w * PX)) for w, z in pts])
        x += step
    for a, b in zip(rings, rings[1:]):
        k = len(a)
        for i in range(k): bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

def build_body(name='Horse'):
    """The horse's skin: the traced profile inflated into trunk, neck and head, legs laid
    joint to joint and muscle masses, fused by a voxel remesh and smoothed."""
    bm = bmesh.new()
    _body_loft(bm, _inflate())
    for leg in (LEG_F, LEG_H):
        _chain(bm, [(lat, (PX_X0 - x) * PX, (PX_GROUND - y) * PX, w * PX, d * PX) for x, y, lat, d, w in leg], step=.008, mirror=True)
    for (cx, cy), lat, (rx, ry, rz), (dx, dy) in MASSES:
        for sx in ((1, -1) if lat else (1,)):
            _ellipsoid(bm, px(cx, cy, lat * sx), rx, ry, rz, _frame(V((0, -dx, -dy))))
    ob = obj_from_bm(name, bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.0065); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=10, lambda_factor=.6, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.11); bake_mods(ob)
    ob.data.validate(clean_customdata=False)
    for p in ob.data.polygons: p.use_smooth = True
    return ob


# ── Materials ───────────────────────────────────────────────────────────────
def m_coat(name='Coat', base='#3d2c1f', belly='#4a3727', points='#171513', res=1024):
    """The sheet's brown: a muted, greyish brown body, paler belly, near-black legs from
    above the knee and hock, a dark grey muzzle."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    def mr(src, a, b):   # 0 at a, 1 at b, smooth
        n = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP'); m.L.new(src, n.inputs['Value'])
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b; return n.outputs['Result']
    body = m.ramp(m.noise(7, 4, .55).outputs['Fac'], [(.3, tuple(x * .82 for x in srgb(base))), (.7, srgb(base))])
    col = m.mix(body.outputs['Color'], srgb(belly), mr(sep.outputs['Z'], 1.0, .78))       # paler underneath
    legs = mr(sep.outputs['Z'], .58, .46)                                                  # dark points
    muzzle = mr(sep.outputs['Y'], -.93, -.99)
    dark = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(legs, dark.inputs[0]); m.L.new(muzzle, dark.inputs[1])
    col = m.mix(col, srgb(points), dark.outputs[0])
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=260.0, Distortion=3.0, Detail=2.0)
    m.L.new(m.coord.outputs['Object'], hair.inputs['Vector'])
    rough = m.ramp(m.noise(40, 3).outputs['Fac'], [(.3, (.78, .78, .78)), (.7, (.9, .9, .9))])   # a short coat's soft sheen, not a gloss
    m.set(col, rough.outputs['Color'], hair.outputs['Fac'], .12, .001)
    return m

def m_flat(name, hexcol, rough=.5, metal=0.0): return H.m_flat(name, hexcol, rough, metal)


# ── Head and hair ───────────────────────────────────────────────────────────
HEAD_AXIS = (px(241, 577), px(288, 641))   # poll top to muzzle tip

def head_loop(bvh, s, a0=0.0, a1=2 * math.pi, n=24, off=.004):
    """Points round the head at fraction s from poll to muzzle, between angles a0..a1
    (0 = the horse's left side, pi/2 = the top), laid on the skin."""
    p0, p1 = HEAD_AXIS; u = (p1 - p0).normalized(); c = p0.lerp(p1, s)
    nrm = V((1, 0, 0)).cross(u).normalized()
    if nrm.z < 0: nrm = -nrm
    pts = []
    for i in range(n):
        a = a0 + (a1 - a0) * i / max(1, n - 1); d = (V((1, 0, 0)) * math.cos(a) + nrm * math.sin(a)).normalized()
        h = bvh.ray_cast(c + d * .4, -d, .5)
        if h[0]: pts.append(h[0] + h[1] * off)
    return pts

def strands(name, roots, length, droop, spread, seed, radius=.004, n=7, taper=.6, scale=None):
    """Hair as thin tapered tubes from roots (point, direction); scale sets each one's length."""
    rnd = random.Random(seed); lines = []
    for j, (base, d) in enumerate(roots):
        ln = length * rnd.uniform(.85, 1.1) * (scale[j] if scale else 1); p = base.copy(); pts = [tuple(p)]
        dd = (d + V((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), 0))).normalized()
        for k in range(n):
            dd = (dd + V((0, 0, -droop * (k + 1) / n))).normalized()
            p = p + dd * ln / n; pts.append(tuple(p))
        lines.append(pts)
    return curve_mesh(name, lines, radius, radii=lambda t: 1 - taper * t, res=0)

def build_horse(add):
    """The horse and its tack. add(ob, material, bind) as in the unit builds;
    bind is 'horse' (skin to the horse body), a bone name, or 'tail'."""
    body = build_body()
    add(body, m_coat(), 'body')
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(body, dg)
    dark_hair = m_flat('HorseHair', '#1d1612', .55)
    # eyes on the sides of the head, ears at the poll
    for sx, n in ((1, 'L'), (-1, 'R')):
        e0 = px(253, 595, sx * .5); h = bvh.ray_cast(e0, V((-sx, 0, 0)), 1)
        if h[0]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.021, segments=20, ring_count=12, location=h[0] - h[1] * .006)
            e = bpy.context.object; e.name = f'HorseEye{n}'; add(e, m_flat('HorseEye', '#0e0a08', .12), 'h_head')
        ear = lathe(f'HorseEar{n}', [(.0, 0), (.031, .015), (.034, .056), (.023, .098), (.006, .128), (0, .134)], 16)
        ear.scale = (1, .5, 1)
        a0 = px(242, 560, sx * .052); h = bvh.ray_cast(V((a0.x, a0.y, 2.2)), V((0, 0, -1)), 1)
        base = (h[0] - V((0, 0, .018))) if h[0] else px(242, 580, sx * .052)
        ear.rotation_euler = (math.radians(-12), math.radians(sx * 14), math.radians(sx * -12)); ear.location = base
        P.bake_obj_xform(ear); add(ear, m_coat('EarCoat', '#36271b', '#36271b', '#1c1612', 256), 'h_head')
    # hooves: unshod, a little flared at the ground
    hoof_m = m_flat('Hoof', '#3d362f', .62)
    for key in ('F', 'H'):
        for sx, n in ((1, 'L'), (-1, 'R')):
            hf = lathe(f'Hoof{key}{n}', [(0, 0), (.064, 0), (.063, .015), (.057, .045), (.05, .068), (0, .072)], 28)
            for v in hf.data.vertices: v.co.y = v.co.y * 1.1 + .32 * v.co.z   # longer than wide; the wall slopes back from the toe
            hf.location = (sx * HOOF_X, HOOF_Y[key] - .012, 0); P.bake_obj_xform(hf)
            add(hf, hoof_m, f'h_pastern{key}.{n}')
    # the cropped mane stands upright along the crest; a short forelock between the ears
    roots = []
    y0, y1 = px(238, 0).y, px(160, 0).y   # poll to withers
    lens = []
    for i in range(120):
        t = i / 119; y = y0 + (y1 - y0) * t
        h = bvh.ray_cast(V((0, y, 2.4)), V((0, 0, -1)), 2)
        if not h[0] or h[0].z < 1.2: continue
        for sx in (-1.5, -.5, .5, 1.5):
            roots.append((h[0] + V((sx * .008, 0, -.01)), (h[1] * .4 + V((0, .08 * t - .06, .8))).normalized()))
            lens.append(.65 + .45 * math.sin(math.pi * min(1, t * 1.15)))
    mane = strands('HorseMane', roots, .125, .0, .12, 3, .0044, 4, .3, scale=lens)
    add(mane, dark_hair, 'horse')
    fl = [(px(244, 578, (i % 5 - 2) * .006) + V((0, (i // 5) * .006, -.01)), V((0, -.4, 1))) for i in range(25)]
    add(strands('HorseForelock', fl, .08, .05, .2, 4, .0032, 5), dark_hair, 'h_head')
    # the tail: long and full, falling from the dock nearly to the hocks' height
    roots = []
    for i in range(48):
        t = i / 47; z = px(0, 649).z - .16 * t
        h = bvh.ray_cast(V((0, 1.5, z)), V((0, -1, 0)), 1)
        if not h[0]: continue
        for k in range(7):
            roots.append((h[0] + V(((k - 3) * .0075, -.006, 0)), V(((k - 3) * .09, .34, -.35)).normalized()))
    tail = strands('HorseTail', roots, .64, 1.3, .1, 5, .005, 7, .38)
    add(tail, dark_hair, 'tail')

    # the sheepskin saddle cloth, draped over the back, and a girth over it
    bm = bmesh.new(); nx, ny = 30, 20
    def back(y): h = bvh.ray_cast(V((0, y, 3)), V((0, 0, -1)), 4); return h[0].z if h[0] else 1.33
    g = []
    for j in range(ny + 1):
        y = .04 + (j / ny - .5) * .56; zb = back(y) + .016
        g.append([bm.verts.new(((i / nx - .5) * 1.0, y, zb - max(0, abs(i / nx - .5) - .07) * .25)) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx): bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
    cloth = obj_from_bm('SaddleCloth', bm)
    H.drape('SaddleCloth', cloth, lambda c: abs(c.x) < .06, body, 90, .35, 0)
    rnd = random.Random(8); edge = []
    bmc = bmesh.new(); bmc.from_mesh(cloth.data); bmc.verts.ensure_lookup_table()
    for v in bmc.verts:
        if not v.is_boundary: continue
        out = sum(((v.co - e.other_vert(v).co) for e in v.link_edges if not e.is_boundary), V()).normalized()
        for k in range(3):
            j = V((rnd.uniform(-.01, .01), rnd.uniform(-.01, .01), 0))
            edge.append((v.co + j, (out + V((0, 0, -.6)) + j * 20).normalized()))
    bmc.free()
    fur = m_fur('Sheepskin', '#4a3828', '#7a6248')
    mod(cloth, 'SOLIDIFY', thickness=.012, offset=1); bake_mods(cloth)
    add(cloth, fur, 'horse-trunk')
    add(strands('SheepskinFringe', edge, .045, .3, .35, 9, .004, 3, .5), fur, 'horse-trunk')
    sf = Surf([body, cloth]); pts = []
    for i in range(41):
        a = i / 40 * 2 * math.pi; d = V((math.cos(a), 0, math.sin(a))); o = V((0, -.2, 1.0))
        h = sf.hit(o, d, .8)
        if h: pts.append((h[0] + h[1] * .006, h[1]))
    braid = P.m_rope('Braid', '#5e4128')
    add(curve_mesh('Girth', [[tuple(p) for p, n in pts]], .011, cyclic=True), braid, 'horse-trunk')
    # a braided breast strap round the front of the chest, from the cloth's front corners
    pts = []
    for i in range(33):
        a = math.radians(-84 + 168 * i / 32); u = abs(a) / math.radians(84)
        h = sf.hit(V((0, -.2, .98 + .2 * u * u)), V((math.sin(a), -math.cos(a), 0)), .9)
        if h: pts.append(h[0] + h[1] * .008)
    add(curve_mesh('BreastStrap', [[tuple(p) for p in pts]], .01), braid, 'horse-trunk')

    # the bridle: crownpiece and throatlatch, browband, noseband, cheekpieces, bronze bit rings
    strap = m_leather('Bridle', '#3e2818', 256); bronze = m_bronze('BitBronze', .2, 256)
    lines = [head_loop(bvh, .04, 0, 2 * math.pi, 28), head_loop(bvh, .14, .35, math.pi - .35, 12), head_loop(bvh, .63, 0, 2 * math.pi, 28)]
    lines[0].append(lines[0][0]); lines[2].append(lines[2][0])
    for a in (0, math.pi):   # cheekpieces, dropping toward the mouth corners
        side = -1 if a == 0 else 1; pts = []
        for k in range(12):
            s = .04 + (.88 - .04) * k / 11; aa = a + side * .35 * max(0, s - .6) / .28
            p = head_loop(bvh, s, aa, aa, 1)
            if p: pts.append(p[0])
        if len(pts) > 2: lines.append(pts)
    add(curve_mesh('Bridle', [[tuple(p) for p in L] for L in lines if len(L) > 1], .0045, res=1), strap, 'h_head')
    rings = []
    for a in (0, math.pi):
        p = head_loop(bvh, .9, a + (-.35 if a == 0 else .35), a + (-.35 if a == 0 else .35), 1, .008)
        if not p: continue
        r = lathe('BitRing', [(.019, -.004), (.024, 0), (.019, .004)], 20)
        r.rotation_euler = (0, math.pi / 2, 0); r.location = p[0]; P.bake_obj_xform(r)
        rings.append(r); add(r, bronze, 'h_head')
    for i, r in enumerate(rings): r.name = f'BitRing{"LR"[i]}'
    return body, bvh


# ── Posing ──────────────────────────────────────────────────────────────────
def rest_hoof(rig, leg):
    b = rig.data.bones[LEGS[leg][3]]; return b.tail_local.copy()

def rest_angles(rig, leg):
    """The cannon's and pastern's rest angles from vertical (cannon + = hoof behind, pastern + = toe forward)."""
    c, p = (rig.data.bones[n] for n in LEGS[leg][2:4])
    dc, dp = c.tail_local - c.head_local, p.tail_local - p.head_local
    return math.atan2(dc.y, -dc.z), math.atan2(-dp.y, -dp.z)

def hpose(rig, HP):
    """Pose the horse. HP: body {'loc', 'rot', 'pivot'}, chest/neck1/neck2/head/tail1..4 {'rot'},
    legs {leg: {'off': hoof offset from rest (in the ground frame, or the body frame with
    'body': True), 'cannon': angle from vertical (+ = hoof behind), 'pastern': angle (+ = toe forward)}}."""
    PB = rig.pose.bones
    for n in BONE_NAMES:
        PB[n].rotation_quaternion = (1, 0, 0, 0); PB[n].location = (0, 0, 0)
    b = HP.get('body', {})
    rot = Euler(b.get('rot', (0, 0, 0))).to_matrix()
    pivot = V(b.get('pivot', rig.data.bones['h_body'].head_local))
    head0 = rig.data.bones['h_body'].head_local
    shift = pivot + rot @ (head0 - pivot) - head0     # rotate about the pivot rather than the bone's head
    PB['h_body'].location = rig.data.bones['h_body'].matrix_local.to_3x3().inverted() @ (V(b.get('loc', (0, 0, 0))) + shift)
    PB['h_body'].rotation_quaternion = (rig.data.bones['h_body'].matrix_local.to_3x3().inverted() @ rot @ rig.data.bones['h_body'].matrix_local.to_3x3()).to_quaternion()
    for n in ('h_pelvis', 'h_chest', 'h_neck1', 'h_neck2', 'h_head', 'h_tail1', 'h_tail2', 'h_tail3', 'h_tail4'):
        if n in HP: PB[n].rotation_quaternion = Euler(HP[n].get('rot', (0, 0, 0))).to_quaternion()
    H._upd()
    body_m = PB['h_body'].matrix @ rig.data.bones['h_body'].matrix_local.inverted()
    for leg, (b1, b2, b3, b4, bend) in LEGS.items():
        spec = HP.get('legs', {}).get(leg, {})
        off = V(spec.get('off', (0, 0, 0)))
        T = rest_hoof(rig, leg) + off
        if spec.get('body'): T = body_m @ T
        ac0, ap0 = rest_angles(rig, leg)
        ac, ap = spec.get('cannon', ac0), spec.get('pastern', ap0)
        l1, l2, l3, l4 = (rig.data.bones[n].length for n in (b1, b2, b3, b4))
        dirp = V((0, -math.sin(ap), -math.cos(ap))); dirc = V((0, math.sin(ac), -math.cos(ac)))
        if spec.get('body'): dirp = body_m.to_3x3() @ dirp; dirc = body_m.to_3x3() @ dirc
        P3 = T - dirp * l4; P2 = P3 - dirc * l3
        S = PB[b1].head.copy()
        E = H.two_bone(S, P2, l1, l2, body_m.to_3x3() @ bend)
        H.swing(rig, b1, E - S); H.swing(rig, b2, P2 - PB[b2].head)
        H.swing(rig, b3, P3 - PB[b3].head); H.swing(rig, b4, T - PB[b4].head)

def leg_cycle(phase, stance, stride, lift, front, ac0, ap0):
    """Hoof offset and joint angles for one leg at a point in its cycle: on the ground
    sliding back during the stance, folded and swung forward in the air after it."""
    if phase < stance:
        t = phase / stance
        return {'off': (0, -stride / 2 + stride * t, 0), 'cannon': ac0 - .12 + .32 * t, 'pastern': ap0 + .25 * math.sin(math.pi * t)}
    u = (phase - stance) / (1 - stance); e = .5 - .5 * math.cos(math.pi * u)
    fold = math.sin(math.pi * min(1, u * 1.15))
    if front: ac, ap = ac0 + .2 + 1.35 * fold - .32 * u, ap0 - 1.9 * fold
    else: ac, ap = ac0 + .2 - .6 * fold - .32 * u, ap0 - 1.0 * fold
    return {'off': (0, stride / 2 - stride * e, lift * math.sin(math.pi * u)), 'cannon': ac, 'pastern': ap}

GAITS = {   # frames per cycle, leg phases, stance fraction, stride, hoof lift (front, hind), body bob, pitch
    'walk':   dict(frames=28, phase={'LH': 0, 'LF': .25, 'RH': .5, 'RF': .75}, stance=.64, stride=.62, lift=(.16, .1), bob=.012, pitch=.015),
    'gallop': dict(frames=16, phase={'LH': 0, 'RH': .12, 'LF': .42, 'RF': .54}, stance=.32, stride=1.05, lift=(.38, .24), bob=.05, pitch=.08),
}

def gait(rig, name, f, extra=None):
    """The horse's pose at frame f of a gait cycle."""
    G = GAITS[name]; c = (f % G['frames']) / G['frames']
    legs = {}
    for k, p in G['phase'].items():
        front = k[1] == 'F'; ac0, ap0 = rest_angles(rig, k)
        legs[k] = leg_cycle((c - p) % 1, G['stance'], G['stride'], G['lift'][0 if front else 1], front, ac0, ap0)
    w = 2 * math.pi * c * (2 if name == 'walk' else 1)
    HP = {'body': {'loc': (0, 0, G['bob'] * math.sin(w)), 'rot': (G['pitch'] * math.sin(w + .8), 0, 0)},
          'h_neck1': {'rot': (-G['pitch'] * 1.2 * math.sin(w + .4), 0, 0)}, 'h_head': {'rot': (G['pitch'] * .6 * math.sin(w), 0, 0)},
          'h_tail2': {'rot': (.15 * math.sin(w) * (2 if name == 'gallop' else 1), 0, 0)}, 'legs': legs}
    if name == 'gallop': HP['h_tail1'] = {'rot': (-.5, 0, 0)}
    for k, v in (extra or {}).items(): HP[k] = v
    return HP


def build_rig(name='HorseRig', B=None):
    """An armature from a bone list (name, head, tail, parent, deform)."""
    arm = bpy.data.armatures.new(name); ob = link(bpy.data.objects.new(name, arm))
    H.activate(ob); bpy.ops.object.mode_set(mode='EDIT')
    for n, h, t, parent, deform in (B or bones()):
        b = arm.edit_bones.new(n); b.head = h; b.tail = t; b.roll = 0; b.use_deform = deform
        if parent: b.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones: pb.rotation_mode = 'QUATERNION'
    return ob

def weight_to_chain(ob, rig, names):
    """Skin a strand mesh (the tail) along a chain of bones: each vertex goes to the
    nearest two bones, weighted by distance, so the hair bends with the dock."""
    segs = [(n, rig.data.bones[n].head_local, rig.data.bones[n].tail_local) for n in names]
    for n in names:
        if n not in ob.vertex_groups: ob.vertex_groups.new(name=n)
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co; ds = []
        for n, a, b in segs:
            u = b - a; t = max(0.0, min(1.0, (p - a).dot(u) / u.length_squared)); ds.append(((p - (a + u * t)).length, n))
        ds.sort(); (d1, n1), (d2, n2) = ds[0], ds[1]
        w1 = (d2 + 1e-4) / (d1 + d2 + 2e-4)
        ob.vertex_groups[n1].add([v.index], w1, 'REPLACE'); ob.vertex_groups[n2].add([v.index], 1 - w1, 'REPLACE')
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig

TAIL_BONES = ['h_tail1', 'h_tail2', 'h_tail3', 'h_tail4']

LEG_BONE = ('scap', 'humerus', 'radius', 'cannon', 'pastern', 'femur', 'tibia')

def trunk_only(ob):
    """Drop leg-bone weights from tack skinned to the horse (girth, saddle cloth), so it
    rides on the trunk instead of following a leg that passes near it."""
    legs = [g for g in ob.vertex_groups if any(k in g.name for k in LEG_BONE)]
    keep = [g for g in ob.vertex_groups if g not in legs]
    body = ob.vertex_groups.get('h_body') or ob.vertex_groups.new(name='h_body')
    for v in ob.data.vertices:
        ws = {g.group: g.weight for g in v.groups}
        tot = sum(w for gi, w in ws.items() if ob.vertex_groups[gi] in keep)
        for g in legs: g.remove([v.index])
        if tot < 1e-4: body.add([v.index], 1.0, 'REPLACE')
        else:
            for gi, w in ws.items():
                if ob.vertex_groups[gi] in keep: ob.vertex_groups[gi].add([v.index], w / tot, 'REPLACE')
