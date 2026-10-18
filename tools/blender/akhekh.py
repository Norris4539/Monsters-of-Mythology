"""Realistic Akhekh Griffin line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow numpy):
    python tools/blender/akhekh.py third_party/makehuman assets/models [--renders]
(the MakeHuman directory is not used, but the build takes the same arguments as the others).

Akhekh, the falcon-headed griffin of the Beni Hasan tomb paintings, after the views in
refs/akhekh/sources: a pale sandy lion's body 3 m from chest to rump with a long tufted tail,
the head of a lanner falcon made twice the size a griffin's would be (half as long as the body
and as wide as the chest) on a thick cream feathered neck, and falcon wings spanning about 9 m.
The lion is traced from the side view and inflated as the horse is (horse.py): a Poisson
solve inside the outline gives round sections, sized to widths measured on the front and back
views, and the legs are laid joint to joint at the sheet's joints, with paws, toes and muscle
masses, all fused by a voxel remesh together with the falcon head, which is lofted from
sections traced from the side view and sized to the front view. The hooked beak and lower
mandible are lofted along their curves; the eyes are large and dark. The head's markings (the
rufous crown and nape, the dark moustache stripe and the dark skin round the eye) are painted
from the side view and baked with the fur and the feathering of the neck. Each wing is a chain
of three bones (humerus, forearm, hand) under layered feather cards: ten primaries, twelve
secondaries and three tertials, each on its own bone, the primary, greater and median coverts
riding on them, and rows of lesser coverts, scapulars and the alula on the arm, all drawn in one
barred feather atlas. Folding turns every bone to its place in the closed wing (FOLD), which
lies over the flank and back with the primaries reaching past the root of the tail.
  L1 Akhekh Griffin           pale sandy lion, cream falcon head and neck, barred sandy wings
  L2 Veteran Akhekh Griffin   a wide plain band of hammered gold round the base of the neck
  L3 Elite Akhekh Griffin     a fitted cover of gilded bronze plates inlaid with lapis lazuli
                              over the shoulders, back and hips, a broad collar of gold and lapis
                              across the chest, the gold neck band, gilded claws and gold cuffs
                              at the wrists and hocks; the wings stay bare feathers
One skeleton holds the line. The untagged meshes are the griffin every tier shares; L12_ are the
bare claws, L23_ the neck band and L3_ the armour, collar, cuffs and gilded claws. Moves: Idle
(wings folded), Walk, Fly (hovering on beating wings), Strike (a leaping pounce: the wings
open, the fore claws rake down and the beak stabs), Hit and Death (it sinks onto its belly,
the head drops and the wings fall open on the ground).
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import horse as HR
import peltast as PT
from hoplite import obj_from_bm, bake_mods, mod, smart_uv, srgb, Mat
from hydra import catmull, resample, smooth, skin
from scorpion import Poser, m_gold

OUT = H.OUT
random.seed(31)
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', '..', 'refs', 'akhekh')


# ── Shape, traced from the side view (refs/akhekh/sources/side.png, 1344 x 768) ─
# Pixels (x forward, y down) map onto the griffin's frame: it faces -Y, its left side at +X,
# the ground at z = 0. The 537 px from the rump to the breast are 3 m.
S = .0056
X0, GY = 650, 715            # the middle of the body and the ground line
SIDES = (('L', 1), ('R', -1))
Z_ = V((0, 0, 1))

def px(x, y, lat=0.0): return V((lat * S, (X0 - x) * S, (GY - y) * S))

# Trunk and neck in profile, from the root of the tail along the back (under the folded wing),
# up the back of the neck into the head, down the throat and breast, along the belly and round
# the haunch; the head is lofted over its top end.
OUTLINE = [(400, 447), (425, 428), (470, 416), (530, 410), (600, 405), (670, 399), (730, 390), (775, 378), (795, 350),
           (805, 305), (822, 280), (840, 250), (858, 222), (880, 200), (930, 190), (990, 205), (1030, 235), (1036, 300),
           (1030, 330), (1018, 350), (1002, 380), (980, 420), (960, 460), (937, 500), (915, 522), (885, 540), (850, 550),
           (800, 553), (760, 556), (720, 553), (680, 545), (640, 533), (600, 522), (560, 517), (525, 520), (495, 535),
           (470, 552), (445, 563), (415, 563), (400, 548), (393, 520), (392, 490), (395, 465)]
# Half-widths (px) at points of the side view, measured on the front and back views (front.png
# is drawn 1.05 times larger): the neck as wide as the head, the chest broadest at the shoulders.
WIDTHS = [(405, 500, 58), (430, 495, 72), (470, 485, 78), (520, 466, 72), (580, 461, 70), (640, 467, 74), (700, 470, 82),
          (760, 470, 90), (830, 420, 96), (880, 470, 98), (900, 360, 94), (960, 330, 95), (1000, 290, 84), (1022, 280, 66),
          (870, 260, 86), (930, 230, 88)]
SQUARE = [(390, .8), (520, .85), (760, .9), (850, 1.0), (1100, 1.0)]
# Legs (left): centre (px), distance out from the midline (px), half-depth and half-width (px)
LEG_F = [(848, 470, 70, 42, 38), (835, 500, 68, 40, 36), (815, 530, 64, 36, 33), (812, 560, 62, 35, 32), (815, 600, 60, 32, 30),
         (818, 630, 58, 29, 28), (820, 655, 56, 26, 27), (824, 672, 55, 25, 28), (830, 686, 54, 24, 30)]
LEG_H = [(455, 478, 55, 46, 35), (460, 515, 56, 42, 34), (458, 543, 54, 33, 29), (440, 567, 52, 28, 25), (422, 585, 50, 25, 22),
         (408, 602, 48, 21, 20), (410, 625, 48, 17, 18), (413, 650, 48, 16, 18), (416, 672, 48, 17, 19), (420, 688, 48, 18, 21)]
# Masses the outline cannot give: centre (px), out from the midline (px), radii (across, along,
# up; px) and the along direction (px: forward, down)
MASSES = [((832, 478), 78, (24, 44, 46), (1, 0)),     # shoulder over the upper arm
          ((812, 522), 66, (24, 26, 34), (0, 1)),     # triceps behind the elbow
          ((445, 495), 74, (22, 55, 48), (1, 0)),     # haunch
          ((797, 335), 55, (40, 48, 32), (1, 0)),     # the roots of the wings on the shoulders
          ((1027, 173), 47, (13, 30, 9), (1, -.2)),   # brows over the eyes
          ((852, 697), 54, (31, 42, 18), (1, 0)),     # fore paw
          ((434, 699), 48, (28, 37, 16), (1, 0))]     # hind paw
TOES = {'F': ((878, 702), 54, (-22, -7, 7, 22), (11, 14, 13)), 'H': ((458, 703), 48, (-19, -6, 6, 19), (10, 13, 12))}
# The falcon head: sections (x, top, bottom, height of the widest line, half-width), px
HEAD = [(855, 225, 330, 290, 86), (875, 192, 325, 270, 92), (900, 168, 318, 255, 96), (930, 152, 312, 245, 97),
        (960, 143, 305, 238, 95), (990, 142, 296, 232, 88), (1010, 146, 286, 226, 78), (1030, 154, 270, 220, 64),
        (1050, 164, 250, 212, 48), (1065, 172, 240, 208, 38), (1080, 180, 233, 206, 30), (1094, 189, 228, 206, 23)]
# The beak along its middle line (x, y), with half-height and half-width (px) at each point
BEAK = [(1078, 207, 26, 26), (1095, 208, 25, 22), (1110, 211, 23, 18), (1123, 217, 20, 14), (1133, 226, 16, 11), (1139, 238, 12, 9),
        (1140, 250, 9, 7), (1138, 260, 6, 5), (1135, 268, 2, 1.5)]
JAW = [(1046, 237, 9, 30), (1070, 240, 9, 25), (1090, 242, 6, 15), (1104, 243, 2, 6)]
EYE = ((1032, 187), 17)      # centre and radius, px
TAIL = [(405, 452), (398, 480), (392, 505), (378, 535), (358, 563), (332, 585), (300, 600), (265, 604), (235, 598), (212, 583),
        (198, 562), (192, 545)]
TUFT = ((193, 552), (168, 490))
OUTLINE_X = (min(p[0] for p in OUTLINE), max(p[0] for p in OUTLINE))


# ── Inflating the outline (after horse.py, for any outline) ────────────────
def _hits(o, d):
    out = []
    for (ax, ay), (bx, by) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        ex, ey = bx - ax, by - ay; den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12: continue
        t = ((ax - o[0]) * ey - (ay - o[1]) * ex) / den; u = ((ax - o[0]) * d[1] - (ay - o[1]) * d[0]) / den
        if t > 1e-9 and 0 <= u <= 1: out.append(t)
    return sorted(out)

def _inside(X, Y):
    ins = np.zeros(X.shape, bool)
    for (ax, ay), (bx, by) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        ins ^= ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / ((by - ay) or 1e-9) + ax)
    return ins

def _inflate(x0=380, x1=1050, y0=180, y1=575):
    """Half-widths (px) of the inflated profile: lap(h) = -1 inside the outline, sqrt(2h) a round
    section across any strip, scaled so it passes through WIDTHS (the scale blended between them)."""
    h = None
    for res in (4, 2, 1):
        xs, ys = np.arange(x0, x1, res, dtype=float), np.arange(y0, y1, res, dtype=float)
        X, Y = np.meshgrid(xs, ys); ins = _inside(X, Y)
        if h is None: h = np.zeros(X.shape)
        else: h = np.kron(h, np.ones((2, 2)))[:X.shape[0], :X.shape[1]]
        h = np.pad(h, ((0, X.shape[0] - h.shape[0]), (0, X.shape[1] - h.shape[1])))
        red = (np.add.outer(np.arange(X.shape[0]), np.arange(X.shape[1])) % 2) == 0
        for _ in range(400 if res == 4 else 250):
            for cells in (ins & red, ins & ~red):
                hn = (np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1) + res * res) / 4
                h = np.where(cells, h + 1.85 * (hn - h), h)
        h = np.where(ins, h, 0.0)
    R = np.sqrt(2 * np.maximum(h, 0)); grid = (xs, ys, R)
    wsum = np.zeros(X.shape); ksum = np.zeros(X.shape)
    for x, y, w in WIDTHS:
        k = w / max(1.0, HR._sample(grid, x, y))
        g = np.exp(-((X - x) ** 2 + (Y - y) ** 2) / (2 * 30.0 ** 2)); wsum += g; ksum += g * k
    return xs, ys, (ksum / np.maximum(wsum, 1e-9)) * R

def _body_loft(bm, grid, step=1.5, K=24):
    """The inflated trunk and neck as one loft of upright sections from the tail to the throat."""
    rings = []; x = OUTLINE_X[0] + .3
    while x < OUTLINE_X[1] - .2:
        hh = _hits((x, 0), (0, 1))
        if len(hh) >= 2:
            top, bot = hh[0], hh[-1]
            zs = [top + (bot - top) * (1 - math.cos(math.pi * i / K)) / 2 for i in range(K + 1)]
            side = [(HR._sample(grid, x, z), z) for z in zs]
            wmax = max(w for w, z in side) or 1; g = HR._lerp(SQUARE, x)
            side = [(wmax * (w / wmax) ** g, z) for w, z in side]
            pts = side + [(-w, z) for w, z in side[-2:0:-1]]
            rings.append([bm.verts.new(px(x, z, w)) for w, z in pts])
        x += step
    for a, b in zip(rings, rings[1:]):
        k = len(a)
        for i in range(k): bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

def sec_ring(c, side, up, w, top, bot, K, nt=2.3, nb=2.3):
    """A superellipse section centred at c: half-width w along side, top above and bot below (m)."""
    out = []
    for q in range(K):
        a = 2 * math.pi * q / K; ca, sa = math.cos(a), math.sin(a); n = nt if sa >= 0 else nb; h = top if sa >= 0 else bot
        out.append(c + side * (math.copysign(abs(ca) ** (2 / n), ca) * w) + up * (math.copysign(abs(sa) ** (2 / n), sa) * h))
    return out

def loft(bm, rings, caps=True):
    R = [[bm.verts.new(p) for p in r] for r in rings]; n = len(R[0])
    for a, b in zip(R, R[1:]):
        for k in range(n): bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    if caps: bm.faces.new(R[0][::-1]); bm.faces.new(R[-1])
    return R

def head_rings(K=40):
    """The falcon head's sections, front view widths on the side view's heights."""
    rows = []
    for x0 in np.arange(HEAD[0][0], HEAD[-1][0] + .1, 4.0):
        x = float(x0); vals = [float(np.interp(x, [h[0] for h in HEAD], [h[j] for h in HEAD])) for j in range(1, 5)]
        top, bot, zc, w = vals
        rows.append(sec_ring(px(x, zc), V((1, 0, 0)), Z_, w * S, (zc - top) * S, (bot - zc) * S, K, 2.2, 2.6))
    return rows

def path_loft(bm, pts, hh, hw, K=20, nt=2.2, nb=3.0, n=60):
    """A tube along a curve in the side view's plane, its sections upright to the curve."""
    C = resample(catmull([px(x, y) for x, y in pts], 12), n)
    arc = [0.0]
    for a, b in zip(C, C[1:]): arc.append(arc[-1] + (b - a).length)
    u = [i / (len(pts) - 1) for i in range(len(pts))]
    rings, tone = [], []
    for i, c in enumerate(C):
        t = (C[min(i + 1, n)] - C[max(i - 1, 0)]).normalized(); up = V((0, t.z, -t.y)).normalized()
        f = arc[i] / arc[-1]
        rings.append(sec_ring(c, V((1, 0, 0)), up, np.interp(f, u, hw) * S, np.interp(f, u, hh) * S, np.interp(f, u, hh) * S, K, nt, nb))
        tone.append(f)
    return loft(bm, rings), tone

def _frame(d): return HR._frame(d)

def _ellipsoid(bm, c, rx, ry, rz, R, nu=12, nv=8):
    """horse._ellipsoid, built vertex by vertex: bmesh's sphere operator slows as the mesh grows."""
    M = R @ Matrix.Diagonal((rx, ry, rz))
    top = bm.verts.new(c + M @ V((0, 0, 1))); bot = bm.verts.new(c + M @ V((0, 0, -1))); rings = []
    for j in range(1, nv):
        th = math.pi * j / nv
        rings.append([bm.verts.new(c + M @ V((math.sin(th) * math.cos(2 * math.pi * i / nu), math.sin(th) * math.sin(2 * math.pi * i / nu), math.cos(th))))
                      for i in range(nu)])
    for i in range(nu):
        i2 = (i + 1) % nu; bm.faces.new((top, rings[0][i], rings[0][i2])); bm.faces.new((bot, rings[-1][i2], rings[-1][i]))
        for a, b in zip(rings, rings[1:]): bm.faces.new((a[i], b[i], b[i2], a[i2]))

def _chain(bm, pts, step=.012):
    """horse._chain (mirrored), with the ellipsoids above."""
    for sx in (1, -1):
        P_ = [(V((x * sx, y, z)), rw, rh) for x, y, z, rw, rh in pts]
        for k, ((a, wa, ha), (b, wb, hb)) in enumerate(zip(P_, P_[1:])):
            d = b - a; n = max(1, int(d.length / step)); R = _frame(d)
            for i in range(n + (1 if k == len(P_) - 2 else 0)):
                t = i / n; rw = wa + (wb - wa) * t; rh = ha + (hb - ha) * t
                _ellipsoid(bm, a.lerp(b, t), rw, max(rw, rh) * .9, rh, R)

def build_body():
    """The skin: the traced trunk and neck inflated, the falcon head lofted onto the neck, legs
    laid joint to joint, paws, toes and muscle masses, fused by a voxel remesh."""
    bm = bmesh.new()
    _body_loft(bm, _inflate())
    loft(bm, head_rings())
    for leg in (LEG_F, LEG_H):
        _chain(bm, [(lat * S, (X0 - x) * S, (GY - y) * S, w * S, d * S) for x, y, lat, d, w in leg])
    for (cx, cy), lat, (rx, ry, rz), (dx, dy) in MASSES:
        for sx in (1, -1):
            _ellipsoid(bm, px(cx, cy, lat * sx), rx * S, ry * S, rz * S, _frame(V((0, -dx, -dy))))
    for k, ((cx, cy), lat, offs, (rx, ry, rz)) in TOES.items():
        for sx in (1, -1):
            for o in offs:
                back = 6 if abs(o) > 15 else 0
                _ellipsoid(bm, px(cx - back, cy, (lat + o) * sx), rx * S, ry * S, rz * S, _frame(V((0, -1, 0))))
    ob = obj_from_bm('Body', bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.011); bake_mods(ob)
    mod(ob, 'SMOOTH', factor=.6, iterations=4); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.16); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=4, lambda_factor=.4, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    ob.data.validate(clean_customdata=False)
    for p in ob.data.polygons: p.use_smooth = True
    print('body', len(ob.data.vertices), 'vertices')
    return ob


# ── Head parts, tail and claws ──────────────────────────────────────────────
def build_beak():
    """The hooked upper mandible and the lower one, each with a 'tone' from base to tip."""
    out = []
    for name, pts in (('Beak', BEAK), ('Jaw', JAW)):
        bm = bmesh.new(); lay = bm.verts.layers.float.new('tone')
        R, tone = path_loft(bm, [p[:2] for p in pts], [p[2] for p in pts], [p[3] for p in pts], 20, 2.2, 3.0 if name == 'Beak' else 2.4)
        for row, t in zip(R, tone):
            for v in row: v[lay] = t if name == 'Beak' else .3 + .5 * t
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = obj_from_bm(name, bm); mod(ob, 'SUBSURF', levels=1); bake_mods(ob); out.append(ob)
    return out

def build_eyes(bvh):
    """Large dark eyes set into the face, each in a ring of pale bare skin."""
    parts = []
    (ex, ey), r = EYE
    for s, sx in SIDES:
        h = bvh.ray_cast(px(ex, ey, sx * 200), V((-sx, 0, 0)), 3)
        n = (h[1] + V((0, -.55, 0)) + V((sx * .2, 0, 0))).normalized()   # it looks forward as well as out
        c = h[0] - h[1] * (r * S * .2)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r * S, segments=32, ring_count=16, location=c)
        e = bpy.context.object; e.name = f'Eye{s}'; parts.append(e)
        prof = [(r * S * .98 + .011 * math.cos(2 * math.pi * k / 10), .011 * math.sin(2 * math.pi * k / 10)) for k in range(11)]
        ring = H.lathe(f'EyeRing{s}', prof, 40)
        ring.matrix_world = Matrix.Translation(c + n * r * S * .35) @ Z_.rotation_difference(n).to_matrix().to_4x4()
        PT.bake_obj_xform(ring); parts.append(ring)
    return parts

def build_nostrils(beak):
    """A small dark nostril on each side of the cere."""
    bv = BVHTree.FromObject(beak, bpy.context.evaluated_depsgraph_get()); out = []
    for s, sx in SIDES:
        h = bv.ray_cast(px(1096, 196, sx * 120), V((-sx, 0, 0)), 2)
        if h[0]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.016, segments=12, ring_count=8, location=h[0] - h[1] * .006)
            o = bpy.context.object; o.name = f'Nostril{s}'; o.scale = (.7, 1, 1); PT.bake_obj_xform(o); out.append(o)
    return out

def build_tail():
    bm = bmesh.new(); C = resample(catmull([px(x, y) for x, y in TAIL], 10), 50)
    rings = []
    for i, c in enumerate(C):
        t = (C[min(i + 1, 50)] - C[max(i - 1, 0)]).normalized(); r = (13 - 6 * i / 50) * S
        up = V((0, t.z, -t.y)).normalized(); rings.append(sec_ring(c, V((1, 0, 0)), up, r, r, r, 14, 2, 2))
    loft(bm, rings); tail = obj_from_bm('Tail', bm)
    bm = bmesh.new(); a, b = px(*TUFT[0]), px(*TUFT[1]); d = (b - a).normalized(); up = V((0, d.z, -d.y)); rnd = random.Random(4)
    rings = []
    for i in range(17):
        f = i / 16; r = 15 * S * math.sin(math.pi * min(1, .1 + f * .95)) ** .7 + .004
        ring = sec_ring(a + (b - a) * f, V((1, 0, 0)), up, r * .9, r, r, 16, 2, 2)
        rings.append([p + V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * r * .12 for p in ring])
    loft(bm, rings); tuft = obj_from_bm('TailTuft', bm)
    return tail, tuft

def claw(bm, base, d, length, r0, curve=.9, seg=10):
    """A curved, tapering claw from base along d, hooking down."""
    p = base.copy(); dd = d.normalized(); rows = []
    for i in range(8):
        t = i / 7; r = r0 * (1 - t) ** .8 + .0015
        sd = dd.cross(Z_).normalized() if abs(dd.z) < .95 else V((1, 0, 0)); up = sd.cross(dd)
        rows.append([p + (sd * math.cos(2 * math.pi * q / seg) + up * math.sin(2 * math.pi * q / seg) * 1.3) * r for q in range(seg)])
        dd = (dd + V((0, 0, -curve / 7))).normalized(); p = p + dd * (length / 7)
    loft(bm, rows)

def claw_specs():
    """(toe bone, base, direction) for every claw: one at the front of each toe."""
    out = []
    for k, ((cx, cy), lat, offs, (rx, ry, rz)) in TOES.items():
        for s, sx in SIDES:
            for o in offs:
                back = 6 if abs(o) > 15 else 0
                out.append((f'{"f" if k == "F" else "h"}_toe.{s}', px(cx - back + ry * .8, cy - 3, (lat + o) * sx), V((0, -1, -.35))))
    return out

def build_claws(name, k=1.0):
    bm = bmesh.new(); bones_ = []
    for bone, base, d in claw_specs():
        n0 = len(bm.verts); claw(bm, base, d, .085 * k, .019 * k); bones_ += [bone] * (len(bm.verts) - n0)
    ob = obj_from_bm(name, bm); assign(ob, [{b: 1.0} for b in bones_]); return ob

def assign(ob, weights):
    """Vertex groups from a list of {bone: weight}, one per vertex in order."""
    for i, w in enumerate(weights):
        for b, x in w.items():
            g = ob.vertex_groups.get(b) or ob.vertex_groups.new(name=b); g.add([i], x, 'REPLACE')


# ── Wings ───────────────────────────────────────────────────────────────────
# Each wing is laid out spread flat at rest, in (out, aft) metres from the shoulder J0, with
# heights above it to stack the feathers. Primaries: place along the hand (0 at the wrist),
# angle from straight out towards aft (deg), length and half-width (m).
J0 = px(800, 318, 79)
ARM = [(0.0, 0.0), (.55, .10), (1.38, 0.0), (1.83, .03)]     # shoulder, elbow, wrist, tip
ARM_BONES = ('w_hum', 'w_fore', 'w_hand')
TUBE = [(.12, .16), (.085, .12), (.06, .085), (.025, .04)]   # the arm's half-height and half-width there
TUBE_Z = .07
PRIM = [(.0, 78, 1.40, .13), (.11, 69, 1.48, .13), (.22, 59, 1.58, .135), (.33, 49, 1.72, .135), (.44, 39, 1.9, .14),
        (.55, 30, 2.1, .14), (.66, 22, 2.3, .135), (.76, 15, 2.45, .13), (.86, 9, 2.52, .12), (.96, 4, 2.28, .11)]
# The closed wing lies in a plane tilted out from upright by alpha, through the shoulder; angles
# within it run from straight aft (0) towards up-and-in (+90). The forearm sits a little outside
# the humerus and the hand inside it, so the feathers stack: primaries under secondaries under
# tertials, the coverts on top.
FOLD = dict(alpha=18, hum=-20, fore=168, hand=-18, prim=(-10, -26), sec=(-36, -2), tert=(-3, 3), off=(0, .03, -.03), inward=(5, 2, 0))
# (the elbow closes by less than a half turn and the wrist opens by less, so that partly folded
# wings, turned part of the way, bend the right way; inward tips the primaries and secondaries
# in towards the body, deg)

def wpt(a, b, sx, z=0.0): return V((sx * (J0.x + a), J0.y + b, J0.z + z))
def wdir(ang): return V((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))

def feather_specs():
    """Every feather card of the left wing: the bone it has (or None), the bone it rides on, its
    tile in the atlas, base (out, aft), angle, length, half-width, outer vane's share, height, tip."""
    F = []
    (Ea, Eb), (Wa, Wb), (Ta, Tb) = ARM[1], ARM[2], ARM[3]
    def add(bone, ride, tile, a, b, ang, L, w, out, z, tip, back=0.0):
        d = wdir(ang); F.append(dict(bone=bone, ride=ride, tile=tile, a=a - d.x * back, b=b - d.y * back, ang=ang, L=L, w=w, out=out, z=z, tip=tip))
    for i, (t, ang, L, w) in enumerate(PRIM):
        a, b = Wa + (Ta - Wa) * t, Wb + (Tb - Wb) * t + .03; n = f'f_p{i + 1:02d}'; z = .045 - .005 * i
        add(n, n, 'prim', a, b, ang, L, w, .7 if i < 5 else .7 - .08 * (i - 4), z, 'point')
        add(None, n, 'pcov', a, b, ang, .52, .085, .8, z + .06, 'round', .04)
    for i in range(12):
        t = .02 + .96 * i / 11; a, b = Wa + (Ea - Wa) * t, Wb + (Eb - Wb) * t + .03
        n = f'f_s{i + 1:02d}'; ang = 84 + 16 * t; z = .05 + .005 * i
        add(n, n, 'sec', a, b, ang, 1.25 - .1 * t, .11, .8, z, 'round')
        add(None, n, 'gcov', a, b, ang, .52, .09, .8, z + .05, 'round', .06)
        if i % 2 == 0: add(None, n, 'mcov', a, b, ang, .3, .075, .8, z + .08, 'round', .17)
    for i, (t, ang, L) in enumerate(((.1, 106, 1.05), (.3, 114, .95), (.5, 124, .82))):
        n = f'f_t{i + 1}'; add(n, n, 'tert', Ea * (1 - t), Eb * (1 - t) + .03, ang, L, .11, .8, .115 + .005 * i, 'round')
    for i, (ang, L) in enumerate(((-4, .22), (0, .26), (4, .3))):
        add(None, 'w_hand', 'alula', Wa + .03 * i, Wb - .06, ang, L, .045, .5, .2 + .004 * i, 'point')
    for j, bone in ((1, 'w_fore'),):   # lesser coverts in two rows on the forearm, riding on the nearest secondary
        (a0, b0), (a1, b1) = ARM[j], ARM[j + 1]; seg = V((a1 - a0, b1 - b0, 0)); ang = math.degrees(math.atan2(seg.y, seg.x)) + 90
        n = max(3, int(seg.length / .055))
        def near(t): return f'f_s{min(12, max(1, round(12.5 - 11 * t))):02d}'
        for row in (0, 1):
            for k in range(n - row):
                t = (k + .5 + .5 * row) / n; ht, wd = tube_at(j + t)
                d = wdir(ang); a = a0 + seg.x * t - d.x * (wd * .3 - .08 * row); b = b0 + seg.y * t - d.y * (wd * .3 - .08 * row)
                add(None, near(t), 'lcov', a, b, ang, .22 + .04 * row, .055, .8, TUBE_Z + ht + .012 - .006 * row, 'round')
    return F

def tube_at(u):
    """The arm's half-height and half-width at u (0 shoulder, 1 elbow, 2 wrist, 3 tip)."""
    i = min(2, int(u)); f = u - i
    return tuple(TUBE[i][k] + (TUBE[i + 1][k] - TUBE[i][k]) * f for k in (0, 1))

FEATHERS = None
def feather_bones():
    return [f for f in FEATHERS if f['bone']]

def parent_of(bone): return {'p': 'w_hand', 's': 'w_fore', 't': 'w_hum'}[bone[2]]

def vane(r, tip):
    """The feather's width (of its widest) at fraction r from quill to tip."""
    if r < .06: return .18 + .6 * r / .06
    if r < .15: return .78 + .22 * (r - .06) / .09
    k = .72 if tip == 'point' else .6
    if r <= k: return 1.0 - (.08 * (r - .15) / (k - .15) if tip == 'point' else 0)
    q = (r - k) / (1 - k); return (.92 if tip == 'point' else 1.0) * math.sqrt(max(0.0, 1 - q * q))

TILES = {'prim': (0, 0, 256, 2048), 'sec': (256, 0, 256, 2048), 'tert': (512, 0, 256, 2048), 'scap': (768, 0, 256, 2048),
         'gcov': (1024, 0, 256, 1024), 'pcov': (1024, 1024, 256, 1024), 'mcov': (1280, 0, 256, 1024), 'alula': (1280, 1024, 256, 1024),
         'lcov': (1536, 0, 256, 1024), 'arm': (1792, 0, 256, 2048)}
ATLAS = 2048

def build_feathers():
    """All the feather cards of both wings as one mesh, each card rigid on its bone."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); W = []
    for s, sx in SIDES:
        for f in FEATHERS:
            d = wdir(f['ang']); so = V((d.y, -d.x, 0))   # towards the leading edge or the wing tip
            tx, ty, tw, th = TILES[f['tile']]; n = 9 if f['L'] > .7 else 5
            ride = f['ride'] + '.' + s
            rows = []
            for j in range(n + 1):
                r = (j / n) ** .85; wv = vane(min(r, .999), f['tip']) * f['w']; row = []
                if j == n: row = [None]
                else:
                    for c in (-1, -.5, 0, .5, 1):
                        lat = (-c * f['out'] if c < 0 else -c) * wv
                        z = f['z'] + .004 * (1 - abs(c)) * f['w'] / .1 * vane(r, f['tip'])
                        p2 = V((f['a'], f['b'], 0)) + d * (r * f['L']) + so * lat
                        row.append((wpt(p2.x, p2.y, sx, z), ((c + 1) / 2, r)))
                rows.append(row)
            tip2 = V((f['a'], f['b'], 0)) + d * f['L']; tipv = (wpt(tip2.x, tip2.y, sx, f['z']), (.5, 1.0))
            VV = []
            for row in rows:
                vr = []
                for item in (row if row[0] else [tipv]):
                    v = bm.verts.new(item[0]); W.append({ride: 1.0}); vr.append((v, item[1]))
                VV.append(vr)
            def uv(t): return ((tx + t[0] * tw) / ATLAS, (ty + t[1] * th) / ATLAS)
            for a_, b_ in zip(VV, VV[1:]):
                quads = [(a_[k], a_[k + 1], b_[k + 1], b_[k]) for k in range(4)] if len(b_) > 1 else [(a_[k], a_[k + 1], b_[0]) for k in range(4)]
                for q in quads:
                    q = q if sx > 0 else q[::-1]
                    face = bm.faces.new([v for v, t in q])
                    for lp, (v, t) in zip(face.loops, q): lp[uvl].uv = uv(t)
    ob = obj_from_bm('Feathers', bm); assign(ob, W); return ob

def build_arms():
    """The arm under the coverts: a flattened tube from the shoulder to the tip of the hand,
    thick along its leading edge, bending at the elbow and wrist."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); W = []
    pts2 = [V((a, b, 0)) for a, b in ARM]
    arc_j = [0.0]
    for a, b in zip(pts2, pts2[1:]): arc_j.append(arc_j[-1] + (b - a).length)
    tx, ty, tw, th = TILES['arm']; K = 16; n = 48
    for s, sx in SIDES:
        rows = []
        for i in range(n + 1):
            u = 3 * i / n; j = min(2, int(u)); f = u - j; p = pts2[j].lerp(pts2[j + 1], f)
            t2 = (pts2[j + 1] - pts2[j]).normalized(); side = V((t2.y, -t2.x, 0))   # towards the leading edge
            ht, wd = tube_at(u); arc = arc_j[j] + (arc_j[j + 1] - arc_j[j]) * f
            ring = []
            for q in range(K):
                a = 2 * math.pi * q / K; c2 = p + side * (wd * (math.cos(a) + .25)) * (1 if math.cos(a) > 0 else .7)
                ring.append((wpt(c2.x, c2.y, sx, TUBE_Z + ht * math.sin(a)), q / K, arc / arc_j[-1]))
            # weights: each bone, blended over the joints
            w = {}
            for jj, b in enumerate(ARM_BONES):
                x = (1.0 if jj == 0 else min(1.0, max(0.0, (arc - arc_j[jj] + .06) / .12))) * \
                    (1.0 if jj == 2 else min(1.0, max(0.0, (arc_j[jj + 1] + .06 - arc) / .12)))
                if x > 0: w[f'{b}.{s}'] = x
            tot = sum(w.values()); rows.append((ring, {k: v / tot for k, v in w.items()}))
        VV = []
        for ring, w in rows:
            vr = []
            for p, uu, vv in ring: vr.append((bm.verts.new(p), (uu, vv))); W.append(w)
            VV.append(vr)
        for a_, b_ in zip(VV, VV[1:]):
            for k in range(K):
                q = (a_[k], a_[(k + 1) % K], b_[(k + 1) % K], b_[k]); q = q if sx > 0 else q[::-1]
                face = bm.faces.new([v for v, t in q])
                for lp, (v, t), kk in zip(face.loops, q, (k, k + 1, k + 1, k)):
                    lp[uvl].uv = ((tx + kk / K * tw) / ATLAS, (ty + t[1] * th) / ATLAS)
        for row in (VV[0], VV[-1]):
            face = bm.faces.new([v for v, t in (row if (row is VV[-1]) == (sx > 0) else row[::-1])])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm('WingArms', bm); assign(ob, W); return ob

def feather_atlas():
    """Colour and normal maps for the feather cards (TILES): each tile one feather from quill
    (bottom) to tip and from its outer to inner edge, barred with darker brown, a pale fringe,
    the shaft and the barbs; 'arm' is the small scalloped feathering of the arm."""
    from PIL import Image
    A = ATLAS; col = np.zeros((A, A, 3), np.float32); hgt = np.zeros((A, A), np.float32); rng = np.random.default_rng(7)
    def hexc(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    def noise(shape, cell):
        g = rng.random((max(2, shape[0] // cell), max(2, shape[1] // cell))).astype(np.float32)
        return np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((shape[1], shape[0]), Image.BICUBIC), np.float32) / 255
    def sst(a, b, x): t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
    LOOK = {   # base, bars, fringe, number of bars, dark tip, barbs, strength of the bars, darker centre
        'prim': ('#9a8068', '#5c4434', '#cdb89c', 9, .22, 260, .6, 0), 'sec': ('#a8896a', '#6c5240', '#d6c2a4', 7, .1, 200, .55, .1),
        'tert': ('#b39272', '#78593f', '#dcc6a6', 6, .06, 170, .45, .15), 'scap': ('#b89676', '#80604a', '#dcc6a8', 4, 0, 150, .35, .2),
        'gcov': ('#bc9a76', '#86664c', '#dcc6a8', 2, 0, 110, .3, .25), 'pcov': ('#a88a6c', '#715540', '#d4bfa2', 2, .05, 110, .35, .2),
        'mcov': ('#c29f7b', '#8c6c52', '#e0caac', 1, 0, 80, .25, .25), 'alula': ('#9a7e64', '#62493a', '#cdb79c', 3, .1, 90, .45, .1),
        'lcov': ('#c6a480', '#8f6f54', '#e2ceb0', 1, 0, 60, .15, .3)}
    for name, (x, y, w, h) in TILES.items():
        U, Vv = np.meshgrid((np.arange(w) + .5) / w, (np.arange(h) + .5) / h)
        n1, n2 = noise((h, w), 24), noise((h, w), 6)
        if name == 'arm':   # rows of small overlapping feathers along the arm
            rows, cols = 46, 12; ry = Vv * rows; cx = U * cols + .5 * (np.floor(ry) % 2); fx, fy = cx % 1, ry % 1
            edge = (.95 - 1.6 * (fx - .5) ** 2) - fy
            sh = sst(0, .2, edge)
            c = hexc('#bf9b75')[None, None] * (.92 + .16 * n1[..., None])
            c = c * (.55 + .45 * sh[..., None]) + hexc('#e6d6be')[None, None] * (.25 * sst(.15, 0, np.abs(edge - .05)))[..., None]
            col[y:y + h, x:x + w] = c; hgt[y:y + h, x:x + w] = sh * .6 + .1 * n2
            continue
        base, dark, pale, nb, tipd, barbs, bk, ctr = LOOK[name]
        a = np.abs(U - .5) * 2
        bar = sst(.45, .8, .5 + .5 * np.sin(2 * np.pi * (nb * Vv + .22 * a + .25 * n1))) * (Vv > .12) * (.75 + .25 * (U > .5))
        c = hexc(base)[None, None] * (.94 + .12 * n2[..., None])
        c = c * (1 - ctr * (1 - a) ** 1.5)[..., None]   # a darker streak along the shaft
        c = c + (hexc(dark) - hexc(base))[None, None] * (bar * bk)[..., None]
        if tipd: c = c + (hexc(dark) * .85 - c) * (sst(1 - tipd, 1 - tipd * .35, Vv) * .75)[..., None]
        c = c + (hexc(pale) - c) * (sst(.8, 1.0, a) * .45)[..., None]
        rach = np.exp(-((U - .5) / .012) ** 2) * (Vv < .97)
        c = c + (hexc('#ece0cb') - c) * (rach * .75)[..., None]
        c = c + (hexc('#e2d6c2') - c) * (np.clip(1 - Vv / .08, 0, 1) * .6)[..., None]
        barb = .5 + .5 * np.sin(2 * np.pi * (Vv * barbs - a * barbs * .08))
        c = c * (.96 + .05 * barb[..., None])
        col[y:y + h, x:x + w] = c; hgt[y:y + h, x:x + w] = .25 * barb + rach - .15 * bar
    gy, gx = np.gradient(hgt); k = 3.0
    nrm = np.dstack([-gx * k, -gy * k, np.ones_like(hgt)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    imgs = []
    os.makedirs(os.path.join(OUT, '_tex'), exist_ok=True)
    for arr, nm, cs in ((col, 'feathers_col', 'sRGB'), (nrm * .5 + .5, 'feathers_nrm', 'Non-Color')):
        p = os.path.join(OUT, '_tex', nm + '.png')
        Image.fromarray((np.clip(arr[::-1], 0, 1) * 255).astype(np.uint8)).save(p)   # rows from the top, as images are stored
        img = bpy.data.images.load(p); img.colorspace_settings.name = cs; img.pack(); imgs.append(img)
    return imgs

def m_feathers():
    col, nrm = feather_atlas()
    m = bpy.data.materials.new('Feathers'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    bsdf = N['Principled BSDF']; bsdf.inputs['Roughness'].default_value = .8
    tc = N.new('ShaderNodeTexImage'); tc.image = col; L.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
    tn = N.new('ShaderNodeTexImage'); tn.image = nrm; nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = .8
    L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


# ── Kit ─────────────────────────────────────────────────────────────────────
NECK_C = px(905, 345)
NECK_A = V((0, -45 * S, 82 * S)).normalized()                       # up the neck
NECK_F = (V((0, -1, 0)) - NECK_A * NECK_A.dot(V((0, -1, 0)))).normalized()   # forward, across it

def ring_band(name, bvh, c, axis, width, off, far=1.4, n=64, rows=6, lip=.009, thick=.012):
    """A plain band round a limb or the neck: rings cast onto the skin across the band's width,
    smoothed, lifted by off and rolled a little at both edges."""
    e1 = axis.orthogonal().normalized(); e2 = axis.cross(e1)
    bm = bmesh.new(); R = []
    for j in range(rows):
        sj = (j / (rows - 1) - .5) * width; cc = c + axis * sj; rad = []
        for i in range(n):
            a = 2 * math.pi * i / n; d = e1 * math.cos(a) + e2 * math.sin(a)
            h = bvh.ray_cast(cc + d * far, -d, far)
            rad.append((h[0] - cc).length if h[0] else (rad[-1] if rad else .2))
        rad = [sum(rad[(i + k) % n] for k in range(-3, 4)) / 7 for i in range(n)]
        R.append((cc, rad, abs(j / (rows - 1) - .5) * 2))
    big = [max(r[1][i] for r in R) for i in range(n)]
    rows_v = []
    for cc, rad, edge in R:
        rr = [max(rad[i], big[i] - .03) + off + lip * math.cos(edge * math.pi / 2) ** .5 * (1 if edge > .8 else 0) for i in range(n)]
        rows_v.append([bm.verts.new(cc + (e1 * math.cos(2 * math.pi * i / n) + e2 * math.sin(2 * math.pi * i / n)) * rr[i]) for i in range(n)])
    for a, b in zip(rows_v, rows_v[1:]):
        for i in range(n): bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=thick, offset=-1); bake_mods(ob)
    return ob

def field_shell(name, body, f, offset, thick, pattern):
    """The part of the body's skin where f(p) > 0, cut cleanly along f = 0, lifted by offset and
    given a thickness. 'rim' holds each vertex's distance from the cut; pattern(p) gives the UV
    the inlay is drawn in (UV map 'Pattern')."""
    bm = bmesh.new(); bm.from_mesh(body.data); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    for lay in list(bm.loops.layers.uv.values()): bm.loops.layers.uv.remove(lay)
    val = {v: f(v.co) for v in bm.verts}
    bmesh.ops.delete(bm, geom=[fa for fa in bm.faces if not any(val[v] > 0 for v in fa.verts)], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    moves = {}
    for v in bm.verts:
        if val[v] > 0: continue
        pts = [v.co.lerp(e.other_vert(v).co, val[v] / (val[v] - val[e.other_vert(v)])) for e in v.link_edges if val[e.other_vert(v)] > 0]
        if pts: moves[v] = sum(pts, V()) / len(pts)
    for v, c in moves.items(): v.co = c
    bmesh.ops.dissolve_degenerate(bm, dist=.004, edges=bm.edges[:])
    bm.normal_update()
    for v in bm.verts: v.co += v.normal * offset
    edge = [v.co.copy() for v in bm.verts if v.is_boundary]
    kd = KDTree(len(edge))
    for i, c in enumerate(edge): kd.insert(c, i)
    kd.balance()
    rim = bm.verts.layers.float.new('rim'); uvl = bm.loops.layers.uv.new('Pattern')
    for v in bm.verts: v[rim] = kd.find(v.co)[2] if edge else 1.0
    for fa in bm.faces:
        for lp in fa.loops: lp[uvl].uv = pattern(lp.vert.co)
    ob = obj_from_bm(name, bm); PT.relax_rim(ob, 4)
    mod(ob, 'SOLIDIFY', thickness=thick, offset=1); bake_mods(ob)
    return ob

def side_px(p): return X0 - p.y / S, GY - p.z / S

ARMOUR_EDGE = [(390, 520), (430, 538), (480, 532), (520, 492), (580, 474), (700, 476), (760, 484), (800, 512), (840, 520), (880, 505), (905, 470)]

def armour_field(p):
    x, y = side_px(p); s = (p - NECK_C).dot(NECK_A); fwd = (p - NECK_C).dot(NECK_F)
    low = float(np.interp(x, [e[0] for e in ARMOUR_EDGE], [e[1] for e in ARMOUR_EDGE]))
    return min((low - y) * S, (x - 404) * S, (895 - x) * S, -.33 - s, max(-(fwd + .02), -(s + .66)))

def collar_field(p):
    s = (p - NECK_C).dot(NECK_A); fwd = (p - NECK_C).dot(NECK_F)
    return min(-.14 - s, s + .64, fwd + .02, .62 - abs(p.x))

def armour_uv(p):
    th = math.atan2(p.z - 1.55, p.x); return (p.y / .9, th * .62 / .9)

def collar_uv(p):
    q = p - NECK_C; s = q.dot(NECK_A); e1 = V((1, 0, 0)); e2 = NECK_A.cross(e1)
    return (math.atan2(q.dot(e2), q.dot(e1)) * .45 / .9, s / .9)

def build_kit(body, bvh):
    """The tiers' gold and armour, fitted to the skin."""
    kit = {}
    kit['L23_NeckBand'] = ring_band('L23_NeckBand', bvh, NECK_C, NECK_A, .26, .018)
    kit['L3_Collar'] = field_shell('L3_Collar', body, collar_field, .028, .014, collar_uv)
    kit['L3_Armour'] = field_shell('L3_Armour', body, armour_field, .024, .014, armour_uv)
    cuffs = []
    for leg, (x, y, lat) in (('F', (819, 640, 57)), ('H', (409, 618, 48))):
        for s, sx in SIDES:
            a = (px(x + (2 if leg == 'F' else -1), y - 20) - px(x, y + 20)).normalized()
            cuffs.append(ring_band(f'Cuff{leg}{s}', bvh, px(x, y, lat * sx), a, .11, .012, far=.35, n=40, rows=5, lip=.007, thick=.01))
    for o in cuffs[1:]: o.select_set(False)
    H.activate(cuffs[0])
    for o in cuffs[1:]: o.select_set(True)
    bpy.ops.object.join(); kit['L3_Cuffs'] = bpy.context.object; kit['L3_Cuffs'].name = 'L3_Cuffs'
    return kit


# ── Materials ───────────────────────────────────────────────────────────────
def marking_mask():
    """The head's and neck's markings painted in the side view's pixels: red the cream feathered
    neck, breast and head, green the rufous crown and nape, blue the dark moustache stripe and
    the dark skin round the eye."""
    from PIL import Image, ImageDraw, ImageFilter
    W, Hh = 1344, 768; chans = []
    cream = [(782, 372), (786, 320), (800, 262), (830, 205), (880, 100), (1300, 100), (1300, 640), (940, 590), (870, 556), (880, 537),
             (892, 512), (898, 472), (893, 428), (876, 400), (856, 381), (820, 373)]
    rufous = [(838, 272), (845, 240), (858, 212), (880, 185), (910, 160), (950, 60), (1075, 60), (1062, 166), (1048, 169), (1020, 173),
              (990, 171), (950, 177), (915, 188), (890, 202), (868, 225), (855, 252), (850, 274)]
    malar = [(1010, 203), (1052, 211), (1046, 226), (1032, 241), (1023, 259), (1016, 281), (1008, 302), (996, 308), (991, 294),
             (995, 268), (1001, 240), (1003, 220)]
    for polys, ell in (([cream], None), ([rufous], None), ([malar], (1036, 191, 27, 19))):
        im = Image.new('L', (W, Hh), 0); d = ImageDraw.Draw(im)
        for pg in polys: d.polygon(pg, fill=255)
        if ell: d.ellipse((ell[0] - ell[2], ell[1] - ell[3], ell[0] + ell[2], ell[1] + ell[3]), fill=255)
        chans.append(im.filter(ImageFilter.GaussianBlur(2.0)))
    p = os.path.join(OUT, '_tex', 'markings.png'); os.makedirs(os.path.dirname(p), exist_ok=True)
    Image.merge('RGB', chans).save(p)
    img = bpy.data.images.load(p); img.colorspace_settings.name = 'Non-Color'; return img, (W, Hh)

def m_griffin(res=2048):
    """Pale sandy fur, paler below and darker along the back, and the cream feathered neck, breast
    and head with the rufous crown and dark moustache stripe, read from the painted markings in
    the side view's projection with a ragged edge; fur streaks and feather scallops in the bump."""
    m = Mat('Griffin', res=res); L = m.L
    img, (W, Hh) = marking_mask()
    sep = m.node('ShaderNodeSeparateXYZ'); L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    def madd(a, k, c):
        n = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); L.new(a, n.inputs[0]); n.inputs[1].default_value = k; n.inputs[2].default_value = c
        return n.outputs[0]
    uv = m.node('ShaderNodeCombineXYZ')
    L.new(madd(sep.outputs['Y'], -1 / (S * W), X0 / W), uv.inputs['X']); L.new(madd(sep.outputs['Z'], 1 / (S * Hh), 1 - GY / Hh), uv.inputs['Y'])
    jit = m.noise(22, 3, .6)
    vm = m.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD'); L.new(jit.outputs['Color'], vm.inputs[0])
    vm.inputs[1].default_value = (.007, .007, 0); L.new(uv.outputs['Vector'], vm.inputs[2])
    vs = m.node('ShaderNodeVectorMath', operation='SUBTRACT'); L.new(vm.outputs['Vector'], vs.inputs[0]); vs.inputs[1].default_value = (.0035, .0035, 0)
    tex = m.node('ShaderNodeTexImage'); tex.image = img; tex.extension = 'EXTEND'; L.new(vs.outputs['Vector'], tex.inputs['Vector'])
    ch = m.node('ShaderNodeSeparateColor'); L.new(tex.outputs['Color'], ch.inputs['Color'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); L.new(sep.outputs['X'], ax.inputs[0])
    def mr(src, a, b):
        n = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP'); L.new(src, n.inputs['Value'])
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b; return n.outputs['Result']
    def mul(a, b):
        n = m.node('ShaderNodeMath', operation='MULTIPLY'); L.new(a, n.inputs[0]); L.new(b, n.inputs[1]); return n.outputs[0]
    nz = m.node('ShaderNodeSeparateXYZ'); L.new(m.coord.outputs['Normal'], nz.inputs['Vector'])
    fur = m.ramp(m.noise(4, 4, .55).outputs['Fac'], [(.3, srgb('#a57744')), (.7, srgb('#bf915b'))])
    col = m.mix(fur.outputs['Color'], srgb('#d2b386'), mr(nz.outputs['Z'], -.15, -.75))      # paler underneath
    col = m.mix(col, srgb('#956a3c'), mul(mr(nz.outputs['Z'], .45, .95), mr(sep.outputs['Z'], 1.4, 1.9)))   # darker along the back
    cr = m.ramp(m.noise(9, 3, .5).outputs['Fac'], [(.3, srgb('#d6c8aa')), (.7, srgb('#e4d9c1'))])
    col = m.mix(col, cr.outputs['Color'], ch.outputs['Red'])
    ru = m.ramp(m.noise(30, 3, .6).outputs['Fac'], [(.3, srgb('#87452a')), (.7, srgb('#a05a34'))])
    col = m.mix(col, ru.outputs['Color'], ch.outputs['Green'])
    col = m.mix(col, srgb('#2a1d14'), mul(ch.outputs['Blue'], mr(ax.outputs[0], .1, .17)))
    hair = m.node('ShaderNodeMapping'); L.new(m.coord.outputs['Object'], hair.inputs['Vector']); hair.inputs['Scale'].default_value = (420, 140, 420)
    hn = m.node('ShaderNodeTexNoise', Scale=1.0, Detail=3.0, Roughness=.6); L.new(hair.outputs['Vector'], hn.inputs['Vector'])
    fm = m.node('ShaderNodeMapping'); L.new(m.coord.outputs['Object'], fm.inputs['Vector']); fm.inputs['Scale'].default_value = (17, 17, 11)
    vor = m.node('ShaderNodeTexVoronoi'); L.new(fm.outputs['Vector'], vor.inputs['Vector'])
    scal = m.ramp(vor.outputs['Distance'], [(0, (1, 1, 1)), (.85, (0, 0, 0))])
    bump = m.mix(hn.outputs['Fac'], scal.outputs['Color'], ch.outputs['Red'])
    m.set(col, .84, bump, .3, .004)
    return m

def m_tail():
    """The tail's short sandy fur, streaked along it."""
    m = Mat('TailFur', res=512)
    fur = m.ramp(m.noise(8, 4, .55).outputs['Fac'], [(.3, srgb('#a27343')), (.7, srgb('#ba8c57'))])
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=240.0, Distortion=4.0, Detail=2.0)
    m.L.new(m.coord.outputs['Object'], hair.inputs['Vector'])
    m.set(fur.outputs['Color'], .85, hair.outputs['Fac'], .2, .002); return m

def m_beak():
    m = Mat('Beak', res=512)
    t = m.node('ShaderNodeAttribute', attribute_name='tone')
    col = m.ramp(t.outputs['Fac'], [(0, srgb('#cbbf86')), (.18, srgb('#c4b67c')), (.3, srgb('#7f8792')), (.7, srgb('#5c646f')), (.95, srgb('#23262a'))])
    m.set(col.outputs['Color'], .3, m.noise(400, 3, .6).outputs['Fac'], .08, .001); return m

def m_inlay(name, res=1024, brick=(.17, .075)):
    """Gilded bronze set with lapis lazuli in rows of cells (a brick pattern in the 'Pattern' UV),
    a plain gold border along the cut edge ('rim'); roughness and metal baked together."""
    m = Mat(name, res=res); L = m.L
    uvn = m.node('ShaderNodeUVMap'); uvn.uv_map = 'Pattern'
    br = m.node('ShaderNodeTexBrick'); L.new(uvn.outputs['UV'], br.inputs['Vector'])
    for k, v in (('Color1', (1, 1, 1, 1)), ('Color2', (1, 1, 1, 1)), ('Mortar', (0, 0, 0, 1)), ('Scale', 1.0), ('Mortar Size', .012),
                 ('Mortar Smooth', .2), ('Brick Width', brick[0]), ('Row Height', brick[1])):
        br.inputs[k].default_value = v
    rim = m.node('ShaderNodeAttribute', attribute_name='rim')
    rr = m.node('ShaderNodeMapRange'); L.new(rim.outputs['Fac'], rr.inputs['Value']); rr.inputs['From Min'].default_value = .035; rr.inputs['From Max'].default_value = .042
    sepc = m.node('ShaderNodeSeparateColor'); L.new(br.outputs['Color'], sepc.inputs['Color'])
    sv = m.node('ShaderNodeSeparateXYZ'); L.new(uvn.outputs['UV'], sv.inputs['Vector'])   # lapis in every other row, gold bands between
    sn = m.node('ShaderNodeMath', operation='SINE'); mv = m.node('ShaderNodeMath', operation='MULTIPLY'); L.new(sv.outputs['Y'], mv.inputs[0])
    mv.inputs[1].default_value = math.pi / brick[1]; L.new(mv.outputs[0], sn.inputs[0])
    row = m.node('ShaderNodeMath', operation='GREATER_THAN'); L.new(sn.outputs[0], row.inputs[0]); row.inputs[1].default_value = 0.0
    inl0 = m.node('ShaderNodeMath', operation='MULTIPLY'); L.new(sepc.outputs['Red'], inl0.inputs[0]); L.new(row.outputs[0], inl0.inputs[1])
    inl = m.node('ShaderNodeMath', operation='MULTIPLY'); L.new(inl0.outputs[0], inl.inputs[0]); L.new(rr.outputs['Result'], inl.inputs[1])
    gold = m.ramp(m.noise(6, 4, .55).outputs['Fac'], [(.3, srgb('#b07f2e')), (.55, srgb('#d3a646')), (.8, srgb('#ebc767'))])
    lap = m.ramp(m.noise(14, 5, .65).outputs['Fac'], [(.25, srgb('#13286e')), (.6, srgb('#1f3d96')), (.85, srgb('#3557b0'))])
    speck = m.ramp(m.noise(260, 2, .5).outputs['Fac'], [(.66, (0, 0, 0)), (.7, (1, 1, 1))])
    lap_c = m.mix(lap.outputs['Color'], srgb('#d8b45a'), speck.outputs['Color'])
    col = m.mix(gold.outputs['Color'], lap_c, inl.outputs[0])
    rough = m.node('ShaderNodeMapRange'); L.new(inl.outputs[0], rough.inputs['Value']); rough.inputs['To Min'].default_value = .27; rough.inputs['To Max'].default_value = .4
    metal = m.node('ShaderNodeMath', operation='SUBTRACT'); metal.inputs[0].default_value = 1.0; L.new(inl.outputs[0], metal.inputs[1])
    dim = m.node('ShaderNodeTexVoronoi', Scale=60.0); L.new(m.coord.outputs['Object'], dim.inputs['Vector'])
    bump = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); L.new(metal.outputs[0], bump.inputs[0]); bump.inputs[1].default_value = .8
    L.new(dim.outputs['Distance'], bump.inputs[2])
    m.set(col, None, bump.outputs[0], .5, .003)
    m.mr = (rough.outputs['Result'], metal.outputs[0])
    return m

def bake(items):
    """scorpion.bake with the normal map at the colour's resolution, and for inlaid metal a
    roughness-metal map (green, blue) as glTF packs them."""
    SC = H.SC; SC.cycles.samples = 4; SC.render.bake.use_selected_to_active = False; SC.render.bake.margin = 6
    for name, (ob, mt) in items.items():
        if mt.res == 0: ob.data.materials.clear(); ob.data.materials.append(mt.m); continue
        me = ob.data
        if 'UV' not in me.uv_layers:
            lay = me.uv_layers.new(name='UV'); me.uv_layers.active = lay; smart_uv(ob, .006)
        me.uv_layers['UV'].active = True; me.uv_layers['UV'].active_render = True
        imgs = {}
        kinds = ['color', 'normal'] + (['mr'] if hasattr(mt, 'mr') else ['rough'] if mt.bsdf.inputs['Roughness'].links else [])
        for kind in kinds:
            r = mt.res if kind in ('color', 'normal') else max(128, mt.res // 2)
            img = bpy.data.images.new(f'{ob.name}_{kind}', r, r, alpha=False)
            img.colorspace_settings.name = 'sRGB' if kind == 'color' else 'Non-Color'; imgs[kind] = img
        m = mt.m.copy(); m.name = f'{mt.m.name}_{ob.name}'; me.materials.clear(); me.materials.append(m)
        nt = m.node_tree; N = nt.nodes; Lk = nt.links; bsdf = N['Principled BSDF']; outn = N['Material Output']
        tex = N.new('ShaderNodeTexImage'); H.activate(ob)
        for kind, img in imgs.items():
            tex.image = img; N.active = tex
            if kind == 'normal':
                Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface']); bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
            else:
                em = N.new('ShaderNodeEmission')
                if kind == 'mr':
                    cc = N.new('ShaderNodeCombineColor')
                    for (src, ch) in zip(mt.mr, ('Green', 'Blue')):
                        Lk.new(next(o for o in N[src.node.name].outputs if o.identifier == src.identifier), cc.inputs[ch])   # the copy's socket
                    Lk.new(cc.outputs['Color'], em.inputs['Color'])
                else:
                    src = bsdf.inputs['Base Color' if kind == 'color' else 'Roughness']
                    if src.links: Lk.new(src.links[0].from_socket, em.inputs['Color'])
                    else: v = src.default_value; em.inputs['Color'].default_value = tuple(v) if kind == 'color' else (v, v, v, 1)
                Lk.new(em.outputs['Emission'], outn.inputs['Surface']); bpy.ops.object.bake(type='EMIT'); N.remove(em)
            img.pack()
        for n in list(N):
            if n not in (bsdf, outn): N.remove(n)
        Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface'])
        for kind, img in imgs.items():
            t = N.new('ShaderNodeTexImage'); t.image = img
            if kind == 'color': Lk.new(t.outputs['Color'], bsdf.inputs['Base Color'])
            elif kind == 'rough': Lk.new(t.outputs['Color'], bsdf.inputs['Roughness'])
            elif kind == 'mr':
                sp = N.new('ShaderNodeSeparateColor'); Lk.new(t.outputs['Color'], sp.inputs['Color'])
                Lk.new(sp.outputs['Green'], bsdf.inputs['Roughness']); Lk.new(sp.outputs['Blue'], bsdf.inputs['Metallic'])
            else:
                nm = N.new('ShaderNodeNormalMap'); Lk.new(t.outputs['Color'], nm.inputs['Color']); Lk.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        for a in ('rim', 'tone'):
            if a in me.attributes: me.attributes.remove(me.attributes[a])
        if 'Pattern' in me.uv_layers: me.uv_layers.remove(me.uv_layers['Pattern'])
        print('baked', ob.name, list(imgs))


# ── Skeleton ────────────────────────────────────────────────────────────────
TAIL_BONES = [f'tail{i + 1}' for i in range(6)]

def tail_joints():
    C = resample(catmull([px(x, y) for x, y in TAIL], 10), 60); return [C[i * 10] for i in range(7)]

LEG_J = {'F': [(832, 410, 62), (848, 478, 66), (806, 540, 62), (820, 655, 56), (838, 697, 54), (880, 708, 54)],
         'H': [(452, 476, 56), (458, 543, 54), (406, 602, 48), (420, 694, 48), (458, 709, 48)]}

def bones():
    B = [('root', (0, 0, 0), (0, -.4, 0), None, False),
         ('spine', px(520, 462), px(700, 452), 'root', True),
         ('chest', px(700, 452), px(830, 432), 'spine', True),
         ('pelvis', px(520, 462), px(415, 478), 'spine', True),
         ('neck1', px(830, 432), px(885, 335), 'chest', True),
         ('neck2', px(885, 335), px(918, 252), 'neck1', True),
         ('head', px(918, 252), px(1080, 210), 'neck2', True),
         ('jaw', px(1046, 237), px(1110, 245), 'head', False)]
    TJ = tail_joints(); prev = 'pelvis'
    for i, n in enumerate(TAIL_BONES): B.append((n, TJ[i], TJ[i + 1], prev, True)); prev = n
    for s, sx in SIDES:
        F = [px(x, y, l * sx) for x, y, l in LEG_J['F']]; Hj = [px(x, y, l * sx) for x, y, l in LEG_J['H']]
        B += [(f'f_scap.{s}', F[0], F[1], 'chest', True), (f'f_hum.{s}', F[1], F[2], f'f_scap.{s}', True),
              (f'f_rad.{s}', F[2], F[3], f'f_hum.{s}', True), (f'f_meta.{s}', F[3], F[4], f'f_rad.{s}', True),
              (f'f_toe.{s}', F[4], F[5], f'f_meta.{s}', True),
              (f'h_fem.{s}', Hj[0], Hj[1], 'pelvis', True), (f'h_tib.{s}', Hj[1], Hj[2], f'h_fem.{s}', True),
              (f'h_meta.{s}', Hj[2], Hj[3], f'h_tib.{s}', True), (f'h_toe.{s}', Hj[3], Hj[4], f'h_meta.{s}', True)]
        P = [wpt(a, b, sx) for a, b in ARM]
        B += [(f'w_hum.{s}', P[0], P[1], 'chest', True), (f'w_fore.{s}', P[1], P[2], f'w_hum.{s}', True),
              (f'w_hand.{s}', P[2], P[3], f'w_fore.{s}', True)]
        for f in feather_bones():
            d = wdir(f['ang'])
            B.append((f"{f['bone']}.{s}", wpt(f['a'], f['b'], sx, f['z']), wpt(f['a'] + d.x * f['L'] * .5, f['b'] + d.y * f['L'] * .5, sx, f['z']),
                      f"{parent_of(f['bone'])}.{s}", True))
    return B

def is_wing(n): return n.startswith(('w_', 'f_p', 'f_s', 'f_t'))


# ── Moves ───────────────────────────────────────────────────────────────────
def frame(d, n):
    x = d.normalized(); z = (n - x * n.dot(x)).normalized(); return Matrix((x, z.cross(x), z)).transposed()

def orient(po, n, Rw):
    """Turn bone n so that, in armature space, it is turned by Rw from its rest."""
    B = po.base(n).to_3x3(); po.q[n] = (B.inverted() @ Rw @ po.rest[n].to_3x3()).to_quaternion(); po.M = {}

QF = {}
def solve_fold(po):
    """The closed wing: every wing bone's turn from the spread rest, as local rotations (QF)."""
    po.clear(); al = math.radians(FOLD['alpha'])
    for s, sx in SIDES:
        n = V((sx * math.cos(al), 0, math.sin(al))); u = V((-sx * math.sin(al), 0, math.cos(al)))
        dirf = lambda deg: (V((0, 1, 0)) * math.cos(math.radians(deg)) + u * math.sin(math.radians(deg))).normalized()
        L = [(V(ARM[i + 1]) - V(ARM[i])).length for i in range(3)]
        J = wpt(0, 0, sx); E = J + dirf(FOLD['hum']) * L[0]; Wr = E + dirf(FOLD['fore']) * L[1]; T = Wr + dirf(FOLD['hand']) * L[2]
        o = FOLD['off']; pts = [J, E + n * o[1], Wr + n * o[1], T + n * o[2]]
        rest = [wpt(a, b, sx) for a, b in ARM]
        for i, b in enumerate(ARM_BONES):
            orient(po, f'{b}.{s}', frame(pts[i + 1] - pts[i], n) @ frame(rest[i + 1] - rest[i], Z_).transposed())
        for f in feather_bones():
            k = f['bone'][2]; i = int(f['bone'][3:]) - 1
            lo, hi = FOLD[{'p': 'prim', 's': 'sec', 't': 'tert'}[k]]; cnt = {'p': 9, 's': 11, 't': 2}[k]
            phi = lo + (hi - lo) * i / cnt; tilt = Matrix.Rotation(math.radians(FOLD['inward']['pst'.index(k)] * sx), 3, u)
            d0 = wdir(f['ang']); d0 = V((d0.x * sx, d0.y, 0))
            orient(po, f"{f['bone']}.{s}", tilt @ frame(dirf(phi), n) @ frame(d0, Z_).transposed())
    for nme in po.q:
        if is_wing(nme):
            q = po.q[nme].copy()
            if q.w < 0: q.negate()
            QF[nme] = q

def wing(po, s, fold=1.0, flap=0.0, sweep=0.0, twist=0.0, hand=None, feath=None):
    """Wing s: closed by fold (0 spread, 1 folded), the hand and the flight feathers by their own
    amounts if given, then raised by flap, swept forward by sweep and its leading edge turned up
    by twist, all about the shoulder."""
    sx = 1 if s == 'L' else -1; h = f'w_hum.{s}'
    po.q[h] = Quaternion(); po.M = {}
    po.bend(h, (0, -sx, 0), flap); po.bend(h, (0, 0, -sx), sweep); po.bend(h, (sx, 0, 0), twist)
    po.q[h] = po.q[h] @ Quaternion().slerp(QF[h], fold); po.M = {}
    for n in QF:
        if not n.endswith('.' + s) or n == h: continue
        f = fold
        if hand is not None and n.startswith(('w_hand', 'f_p')): f = hand
        if feath is not None and n.startswith('f_'): f = feath
        po.q[n] = Quaternion().slerp(QF[n], f)
    po.M = {}

LREST = {}
def leg_rest(rig):
    for s, sx in SIDES:
        for k, names in (('F', ('f_hum', 'f_rad', 'f_meta', 'f_toe')), ('H', ('h_fem', 'h_tib', 'h_meta', 'h_toe'))):
            bs = [rig.data.bones[f'{n}.{s}'] for n in names]
            dm = bs[2].tail_local - bs[2].head_local; dt = bs[3].tail_local - bs[3].head_local
            LREST[k + s] = dict(names=[f'{n}.{s}' for n in names], ball=bs[2].tail_local.copy(), L=[b.length for b in bs],
                                g0=math.atan2(-dm.y, -dm.z), t0=math.atan2(-dt.z, -dt.y), bend=V((0, 1, 0)) if k == 'F' else V((0, -1, 0)))

def place_leg(po, leg, ball, g=None, t=None, R=None):
    """Leg (LF, RF, LH, RH) with its ball at an armature-space point, the metapodial at angle g
    from upright (+ = forward and down), the toes at t below level, in frame R (the world's if None)."""
    r = LREST[leg]; R = R or Matrix.Identity(3); up, lo, me, to = r['names']; l1, l2, l3, l4 = r['L']
    g = r['g0'] if g is None else g; t = r['t0'] if t is None else t
    dm = R @ V((0, -math.sin(g), -math.cos(g))); dt = R @ V((0, -math.cos(t), -math.sin(t)))
    Wp = ball - dm * l3; Sp = po.mat(up).translation
    E = H.two_bone(Sp, Wp, l1, l2, R @ r['bend'])
    po.aim(up, E - Sp); po.aim(lo, Wp - E); po.aim(me, ball - Wp); po.aim(to, dt)

def root_R(po): return po.skin('root').to_3x3()

def body_leg(po, leg, off=(0, 0, 0), g=None, t=None):
    """A leg placed in the body's frame: its ball moved by off from rest, carried with the body."""
    Mb = po.skin('root'); r = LREST[leg]
    place_leg(po, leg, Mb @ (r['ball'] + V(off)), g, t, Mb.to_3x3())

def stand(po, offs=None):
    for leg, r in LREST.items():
        o = (offs or {}).get(leg, {}); place_leg(po, leg, r['ball'] + V(o.get('off', (0, 0, 0))), o.get('g'), o.get('t'))

def tail(po, pitch, yaw=None):
    for i, n in enumerate(TAIL_BONES):
        po.bend(n, (1, 0, 0), pitch[i])
        if yaw: po.bend(n, (0, 0, 1), yaw[i])

def look(po, pitch=0.0, yaw=0.0, roll=0.0, neck=(0.0, 0.0)):
    """The neck bent by neck (pitch, yaw) and the head turned on it (+ pitch = down, + yaw = left)."""
    po.bend('neck1', (1, 0, 0), neck[0] * .6); po.bend('neck2', (1, 0, 0), neck[0] * .4)
    po.bend('neck1', (0, 0, 1), neck[1] * .4); po.bend('neck2', (0, 0, 1), neck[1] * .6)
    po.bend('head', (1, 0, 0), pitch); po.bend('head', (0, 0, 1), yaw)
    if roll: po.bend('head', (0, 1, 0), roll)

SAMPLES = {}
def lowest(po, names):
    z = 9.0
    for n in names:
        M = po.skin(n)
        for p in SAMPLES.get(n, ()): z = min(z, (M @ p).z)
    return z

def actions(rig):
    po = Poser(rig); A = []; leg_rest(rig); solve_fold(po)
    piv = px(640, 470)
    def clip(name, length, fn, step=1):
        rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
        po.prev = {}
        for fr in sorted(set(range(1, length + 1, step)) | {length}): po.clear(); fn(fr); po.key(fr)
        A.append(act)
    X = (1, 0, 0)
    def idle(f):
        w = 2 * math.pi * (f - 1) / 96   # frame 97 is frame 1 again
        po.place(Matrix.Rotation(.006 * math.sin(w), 3, 'X'), (0, 0, .006 * math.sin(2 * w)), piv)
        po.bend('chest', X, -.008 * math.sin(2 * w))
        turn = .42 * (smooth(22, 26, f) - smooth(46, 50, f)) - .3 * (smooth(54, 57, f) - smooth(78, 82, f))
        look(po, .05 * math.sin(w) - .1 * (smooth(54, 57, f) - smooth(78, 82, f)), turn * .6, .12 * (smooth(26, 30, f) - smooth(44, 48, f)), (.02 * math.sin(w + 1), turn * .4))
        tail(po, [.03 * math.sin(w + .5 * i) for i in range(6)], [.06 * math.sin(w - .6 * i) + .12 * math.exp(-((f - 66 + 2 * i) / 4) ** 2) for i in range(6)])
        rf = .06 * math.sin(math.pi * smooth(60, 72, f)) ** 2
        for s in ('L', 'R'): wing(po, s, 1 - rf, rf * .6)
        stand(po)
    clip('Idle', 97, idle, 2)
    WALK = dict(frames=36, phase={'HL': 0, 'FL': .25, 'HR': .5, 'FR': .75}, stance=.62, stride=1.3, lift=(.24, .18))
    def walk(f):
        c = ((f - 1) % WALK['frames']) / WALK['frames']; w = 2 * math.pi * c
        po.place(Matrix.Rotation(.012 * math.sin(2 * w + .8), 3, 'X') @ Matrix.Rotation(.02 * math.sin(w), 3, 'Z'), (0, 0, .025 * math.sin(2 * w)), piv)
        look(po, -.015 * math.sin(2 * w), -.03 * math.sin(w), 0, (.02 * math.sin(2 * w + .4), -.02 * math.sin(w)))
        tail(po, [.04 + .03 * math.sin(2 * w - .5 * i) for i in range(6)], [.1 * math.sin(w - .6 * i) for i in range(6)])
        for s in ('L', 'R'): wing(po, s, 1.0, .015 * math.sin(2 * w))
        offs = {}
        for leg, ph in WALK['phase'].items():
            p = (c - ph) % 1; r = LREST[leg]; front = leg[0] == 'F'; st = WALK['stance']; L_ = WALK['stride']
            if p < st:
                t = p / st; offs[leg] = {'off': (0, -L_ / 2 + L_ * t, 0), 'g': r['g0'] - .2 + .65 * t}
            else:
                u = (p - st) / (1 - st); e = .5 - .5 * math.cos(math.pi * u); fold = math.sin(math.pi * min(1, u * 1.1))
                g = r['g0'] + .45 - (1.9 if front else .9) * fold - .6 * u * (1 - fold)
                offs[leg] = {'off': (0, L_ / 2 - L_ * e, WALK['lift'][0 if front else 1] * math.sin(math.pi * u)), 'g': g,
                             't': r['t0'] - (.9 if front else .5) * fold}
        stand(po, offs)
    clip('Walk', WALK['frames'] + 1, walk)
    def fly(f):
        c = ((f - 1) % 28) / 28; w = 2 * math.pi * c
        flap = .2 + .78 * math.cos(w); fold = .04 + .42 * max(0.0, -math.sin(w)) ** 1.2
        R = Matrix.Rotation(-.3 + .03 * math.sin(w), 3, 'X')
        po.place(R, (0, .1, 1.75 + .12 * math.sin(w - .9)), piv)
        look(po, .3 + .04 * math.sin(w - 1), 0, 0, (.15 - .05 * math.sin(w - .6), 0))
        tail(po, [.18 - .06 * i + .08 * math.sin(w - .7 * i) for i in range(6)], [.03 * math.sin(w * .5 - .5 * i) for i in range(6)])
        for s in ('L', 'R'): wing(po, s, fold, flap, .22 * math.sin(w), .12 * math.cos(w), hand=fold * 1.3, feath=fold * .8)
        for s in ('L', 'R'):
            body_leg(po, 'F' + s, (0, -.3, .32 + .03 * math.sin(w)), LREST['F' + s]['g0'] - .8, LREST['F' + s]['t0'] - .5)
            body_leg(po, 'H' + s, (0, .42, .22 + .04 * math.sin(w)), LREST['H' + s]['g0'] - .6, LREST['H' + s]['t0'] - .6)
    clip('Fly', 29, fly)
    def strike(f):
        a = smooth(1, 8, f); b = smooth(8, 15, f); c = smooth(15, 21, f); r = smooth(24, 40, f)
        up = b * (1 - c); dn = c * (1 - r)
        pitch = .06 * a * (1 - b) - .5 * up + .14 * dn
        po.place(Matrix.Rotation(pitch, 3, 'X'), (0, -.45 * b * (1 - r) - .4 * dn, -.16 * a * (1 - b) + .55 * up + .02 * dn), px(560, 520))
        look(po, -.25 * up + .35 * dn - .1 * a * (1 - b), 0, 0, (-.35 * (a * (1 - b) + up) + .55 * dn, 0))
        po.bend('jaw', X, .55 * smooth(17, 20, f) * (1 - smooth(21, 23, f)) + .3 * up)
        tail(po, [(-.25 * up + .1 * dn) * (1 - .1 * i) for i in range(6)], [.1 * math.sin(f * .4 - i) * (up + dn) for i in range(6)])
        fold = 1 - .6 * a - .4 * b + 1.0 * r; flap = .3 * a + .45 * up - .55 * dn; fold = min(1.0, max(0.0, fold))
        for s in ('L', 'R'): wing(po, s, fold, flap * (1 - r), .25 * up - .1 * dn, .1 * up)
        hop = smooth(9, 17, f) * (1 - smooth(27, 37, f)); lift = .22 * math.sin(math.pi * smooth(9, 17, f)) + .15 * math.sin(math.pi * smooth(27, 37, f))
        offs = {}
        for s in ('L', 'R'):
            rb = LREST['F' + s]; ahead = rb['ball'] + V((0, -1.0, 0))
            reach = po.skin('root') @ (rb['ball'] + V((0, -.45, .75)))
            if f < 15: tgt = rb['ball'].lerp(reach, b); g = rb['g0'] - 1.2 * b; t = rb['t0'] - .4 * b
            elif f < 24: tgt = reach.lerp(ahead, c); g = rb['g0'] - 1.2 * (1 - c) + .2 * c; t = rb['t0'] - .4 * (1 - c)
            else:
                tgt = ahead.lerp(rb['ball'], r) + V((0, 0, .18 * math.sin(math.pi * r))); g = rb['g0'] + .2 * (1 - r) - .6 * math.sin(math.pi * r); t = rb['t0']
            place_leg(po, 'F' + s, tgt, g, t)
            rh = LREST['H' + s]; offs['H' + s] = {'off': (0, -.55 * hop, lift), 'g': rh['g0'] + .4 * up}
        for leg, o in offs.items(): place_leg(po, leg, LREST[leg]['ball'] + V(o['off']), o['g'])
    clip('Strike', 40, strike)
    def hit(f):
        e = smooth(1, 4, f) * (1 - smooth(6, 20, f))
        po.place(Matrix.Rotation(-.09 * e, 3, 'X') @ Matrix.Rotation(.05 * e, 3, 'Y'), (0, .16 * e, .03 * e), piv)
        look(po, -.25 * e, .2 * e, .15 * e, (-.3 * e, -.15 * e))
        tail(po, [-.12 * e] * 6, [.15 * e * math.sin(i) for i in range(6)])
        for s in ('L', 'R'): wing(po, s, 1 - .14 * e, .2 * e, 0, 0)
        stand(po)
    clip('Hit', 20, hit)
    def death(f):
        s1 = smooth(1, 10, f); s2 = smooth(8, 30, f); s3 = smooth(22, 46, f); jerk = math.sin(math.pi * smooth(1, 9, f))
        R = Matrix.Rotation(.05 * jerk + .04 * s2, 3, 'X') @ Matrix.Rotation(.08 * s1 * (1 - s2) + .22 * s2, 3, 'Y')
        po.place(R, (0, 0, -.95 * s2 + .02 * jerk), piv)
        if f > 20:   # it lies on the ground, not in it
            z = lowest(po, ('spine', 'chest', 'pelvis')); po.place(R, (0, 0, -.95 * s2 + .02 * jerk - min(0.0, z) * smooth(20, 30, f)), piv)
        k = 1.0
        for _ in range(12):   # the head comes to rest on the ground
            look(po, .3 * s3 - .2 * jerk, .5 * s3, .9 * s3, (-.25 * jerk + 1.05 * s3 * k, .5 * s3))
            if f < 20 or lowest(po, ('head',)) > .02: break
            for n in ('neck1', 'neck2', 'head'): po.q[n] = Quaternion()
            po.M = {}; k -= .06
        po.bend('jaw', X, .3 * s3)
        tail(po, [.15 * s3 - .05 * i * s3 for i in range(6)], [.25 * s3 * math.sin(.5 * i + 1) for i in range(6)])
        for s, sx in SIDES:
            fl = .08 * s1 * (1 - s2) - .05 * s3
            wing(po, s, 1 - .15 * s1 - .4 * s3, fl, 0, 0, hand=1 - .1 * s1 - .5 * s3)
            if f > 20:   # the wings rest on the ground
                for _ in range(20):
                    if lowest(po, [n for n in SAMPLES if n.endswith('.' + s) and is_wing(n)]) > .02: break
                    fl += .03; wing(po, s, 1 - .15 * s1 - .4 * s3, fl, 0, 0, hand=1 - .1 * s1 - .5 * s3)
        for s in ('L', 'R'):
            rf, rh = LREST['F' + s], LREST['H' + s]
            ff = rf['ball'] + V((0, -.85 * s2, 0)); place_leg(po, 'F' + s, ff, rf['g0'] + 1.45 * s2, rf['t0'])
            hh = rh['ball'] + V((0, -.25 * s2, 0)); place_leg(po, 'H' + s, hh, rh['g0'] + 1.5 * s2, rh['t0'])
    clip('Death', 60, death)
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    global FEATHERS
    FEATHERS = feather_specs()
    body = build_body()
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(body, dg)
    beak, jaw = build_beak()
    eyes = build_eyes(bvh); nostrils = build_nostrils(beak)
    tailm, tuft = build_tail()
    feathers = build_feathers(); arms = build_arms()
    claws = build_claws('L12_Claws'); gclaws = build_claws('L3_Claws', 1.25)
    kit = build_kit(body, bvh)
    fm = m_feathers()
    for o in (feathers, arms): o.data.materials.append(fm)
    eye_m = H.m_flat('Eye', '#120c09', .04); ring_m = H.m_flat('EyeRing', '#a99a6e', .55); nos_m = H.m_flat('Nostril', '#1a1715', .5)
    for o in eyes: o.data.materials.append((ring_m if 'Ring' in o.name else eye_m).m)
    for o in nostrils: o.data.materials.append(nos_m.m)
    claws.data.materials.append(H.m_flat('Claw', '#2b2420', .38).m)
    items = {'Body': (body, m_griffin()), 'Tail': (tailm, m_tail()), 'TailTuft': (tuft, PT.m_fur('Tuft', '#4c3122', '#6e4c33', 256)),
             'Beak': (beak, m_beak()), 'Jaw': (jaw, m_beak()), 'L3_Claws': (gclaws, m_gold('GoldClaws', 256)),
             'L23_NeckBand': (kit['L23_NeckBand'], m_gold('NeckBand', 1024)), 'L3_Cuffs': (kit['L3_Cuffs'], m_gold('Cuffs', 512)),
             'L3_Armour': (kit['L3_Armour'], m_inlay('Armour', 1024, (.14, .06))), 'L3_Collar': (kit['L3_Collar'], m_inlay('Collar', 1024, (.12, .06)))}
    bake(items)
    rig = HR.build_rig('AkhekhRig', bones())
    # the skin by heat from the body's bones only
    off = [b for b in rig.data.bones if is_wing(b.name) or b.name == 'jaw']
    for b in off: b.use_deform = False
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for b in off: b.use_deform = True
    for o in (feathers, arms): skin(o, rig)
    HR.weight_to_chain(tailm, rig, TAIL_BONES); HR.weight_to_chain(tuft, rig, TAIL_BONES[-2:])
    for o in eyes + nostrils + [beak]: H.bind_rigid(o, rig, 'head')
    H.bind_rigid(jaw, rig, 'jaw')
    for o in (claws, gclaws): skin(o, rig)
    for o in kit.values(): H.bind_skin(o, rig, body)
    rig.data.pose_position = 'POSE'; H._upd()
    for ob in (feathers, body):   # sample points per bone, to keep the wings, trunk and head off the ground
        gi = {g.index: g.name for g in ob.vertex_groups}
        for v in list(ob.data.vertices)[::7]:
            g = max(v.groups, key=lambda e: e.weight, default=None)
            if g and g.weight > .9: SAMPLES.setdefault(gi[g.group], []).append(v.co.copy())
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.validate(): print('repaired', ob.name)
    return rig, actions(rig)

def renders(rig):
    """A lineup of the three tiers, key frames of the moves, and each tier beside the sheet."""
    from PIL import Image
    shots = []
    for t in (1, 2, 3):
        p = os.path.join(OUT, f'akhekh_L{t}.png')
        H.render(rig, p, 'Idle', 1, t, cam=((6.5, -8.0, 3.4), (78, 0, 39)), res=(560, 520), samples=24); shots.append(p)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'akhekh_lineup.png'))
    for clip, fr in (('Fly', 1), ('Fly', 8), ('Fly', 15), ('Fly', 22), ('Strike', 13), ('Strike', 20), ('Walk', 10), ('Death', 60), ('Hit', 5)):
        H.render(rig, os.path.join(OUT, f'akhekh_{clip}{fr}.png'), clip, fr, 3, cam=((10.5, -12.5, 5.5), (78, 0, 40)), res=(480, 400), samples=16)
    for t in (1, 3): compare(rig, t)

def compare(rig, t, size=720, samples=16):
    """Orthographic side (Idle), front and back (Fly at the top of the beat) views of tier t at
    the side view's scale, under the reference views."""
    from PIL import Image
    H.render(rig, os.path.join(OUT, '_warmup.png'), 'Idle', 1, t, res=(32, 32), samples=1)
    cam = bpy.data.objects['Cam']; cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1344 * S
    g = bpy.data.objects.get('Ground'); Wc = H.SC.world.node_tree.nodes['Background'].inputs['Color']
    Wc.default_value = (.62, .62, .64, 1); g.hide_render = True
    cols = []
    for view, (act, fr, src) in (('side', ('Idle', 1, 'side')), ('front', ('Fly', 1, 'front')), ('back', ('Fly', 1, 'back'))):
        rig.animation_data.action = bpy.data.actions[act]; H.SC.frame_set(fr)
        zc = (GY - 384) * S + (1.75 if act == 'Fly' else 0)
        if view == 'side': cam.location = (-12, (X0 - 672) * S, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
        elif view == 'front': cam.location = (0, -12, zc); cam.rotation_euler = (math.radians(90), 0, 0)
        else: cam.location = (0, 12, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
        p = os.path.join(OUT, f'akhekh_L{t}_{view}.png')
        H.SC.cycles.samples = samples; H.SC.render.resolution_x = size; H.SC.render.resolution_y = int(size * 768 / 1344); H.SC.render.filepath = p
        bpy.ops.render.render(write_still=True)
        ref = Image.open(os.path.join(REF, 'sources', f'{src}.png')).convert('RGB').resize((size, int(size * 768 / 1344)))
        both = Image.new('RGB', (size, ref.height * 2)); both.paste(ref, (0, 0)); both.paste(Image.open(p).convert('RGB'), (0, ref.height)); cols.append(both)
    out = Image.new('RGB', (size * 3, cols[0].height)); [out.paste(c, (i * size, 0)) for i, c in enumerate(cols)]
    out.save(os.path.join(OUT, f'akhekh_compare_L{t}.png'))
    cam.data.type = 'PERSP'; g.hide_render = False; Wc.default_value = (.36, .42, .5, 1)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'akhekh.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'akhekh.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
