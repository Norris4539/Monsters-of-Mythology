"""Realistic Serket Scorpion line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow numpy):
    python tools/blender/scorpion.py third_party/makehuman assets/models [--renders]
(the MakeHuman directory is not used, but the build takes the same arguments as the others).

The giant black fat-tailed scorpion (Androctonus) sacred to Serket, after the reference sheets
in refs/scorpion: about 2.5 m from the chelicerae to the sting along the body and the arched
tail, standing high on four pairs of legs, its small heavy pincers held forward. The
exoskeleton is built as the animal's own rigid plates, lofted from sections traced from the
side view of the sheet and sized to its front and back views: the carapace with its median
and lateral eyes over the coxae, the seven overlapping tergites and five sternites of the
abdomen on the folded pleural membrane, the pectines, five swollen keeled tail segments, the
bulbous telson and its curved sting, the pedipalps with their chelae, and the legs segment
by segment. Every plate is skinned rigidly to its own bone, and dark brown membranes bend
between them at the joints.
  L1 Serket Scorpion          glossy black granular chitin, the telson dark red-brown
  L2 Veteran Serket Scorpion  larger, a band of hammered gold round the second tail segment
  L3 Elite Serket Scorpion    largest, fitted armour of gilded bronze inlaid with lapis
                              lazuli (lotus fans and feathers) on the carapace, tergites,
                              sternites, tail segments and pincers, gilded fingers, a
                              gold-sheathed sting and the band of the second tier; black legs
One skeleton holds the line. The untagged meshes are the scorpion every tier shares; L12_
are the bare fingers and telson, L23_ the gold band and L3_ the armour, the gilded fingers
and the gold telson. The gallery scales the second and third tiers up. Moves: Idle, Walk
(the alternating tetrapod gait, body level), Strike (the tail lashes forward over the head
and stabs), Pinch (both chelae lunge and snap shut), Hit and Death (it rolls onto its back
and curls its legs).
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector, Matrix, Quaternion
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import horse as HR
from hoplite import link, obj_from_bm, smart_uv, srgb, Mat
from hydra import catmull, resample, smooth, skin

OUT = H.OUT
random.seed(23)
TIERS = {1: dict(scale=1.0), 2: dict(scale=1.12), 3: dict(scale=1.25)}


# ── Shape (sheet pixels mapped to metres; the scorpion faces -Y, its left side at +X) ──
# Traced from the side view of refs/scorpion/scorpion-1.png: X runs forward along the sheet and
# Z is the height above its ground line (y = 645); half-widths (lat) come from the front and
# back views. The 865 px from the chelicerae to the sting along the body and tail are 2.5 m.
S = 2.5 / 865
X0 = 306                     # the middle of the side view, at y = 0
SIDES = (('L', 1), ('R', -1))
SIDE, UP = V((1, 0, 0)), V((0, 0, 1))

def P(X, lat=0.0, Z=0.0): return V((lat * S, (X0 - X) * S, Z * S))

# Cross-sections (X, half-width, top, bottom). The body rises towards the tail, so the front
# view of the sheet looks onto its tergites and the back view onto its sternites.
PROSOMA = [(314, 30, 146, 108), (318, 45, 158, 102), (322, 51, 165, 100), (340, 52, 166, 99), (365, 52, 165, 98),
           (390, 51, 161, 97), (405, 50, 156, 97), (413, 47, 149, 98), (418, 42, 140, 100), (421, 33, 131, 103),
           (423, 20, 124, 106), (424, 6, 120, 108)]
MESO = [(334, 46, 158, 103), (322, 52, 164, 101), (305, 56, 167, 101), (285, 59, 171, 102), (260, 61, 176, 104),
        (235, 63, 182, 107), (210, 63, 189, 112), (185, 62, 198, 119), (160, 59, 208, 128), (138, 53, 219, 141),
        (118, 44, 234, 159), (104, 33, 245, 179), (96, 27, 251, 199), (91, 20, 252, 216), (88, 10, 250, 229)]
TERGITES = [(328, 300), (303, 274), (277, 247), (250, 218), (221, 187), (190, 151), (154, 90)]
STERNITES = [(316, 270), (273, 222), (225, 168), (171, 124), (127, 92)]
# The tail's midline (X, Z) from the end of the abdomen, rising behind it and arching forward,
# and its five segments, each longer than the last, with their half-width and half-height.
TAIL_PATH = [(92, 242), (82, 272), (76, 320), (79, 357), (91, 400), (113, 435), (150, 462), (195, 471), (240, 456),
             (274, 427), (296, 400), (310, 380)]
SEG_LEN = (70, 78, 84, 90, 100)
SEG_R = ((25, 24.5), (25, 24), (26.5, 25), (27, 25.5), (27, 25))
TELSON = dict(fold=110, length=58, w=22, h=21, sting=46, curl=72)
# Pedipalp (left): trochanter, elbow (femur-patella), wrist, and the hand's axis to the
# base of the fingers; each finger as points (forward, out, up) from the hand's base.
PALP = dict(C=(412, 32, 104), E=(374, 88, 142), W=(428, 112, 112), H0=(428, 118, 124), H1=(498, 128, 125), w=24, h=33)
FIXED = [(58, 0, 5), (78, -1, 4), (96, -2, 3), (112, -4, 1), (126, -5, -1), (134, -6, -5)]
MOVABLE = [(58, 0, -21), (76, 0, -25), (94, -2, -30), (110, -4, -36), (124, -5, -40), (133, -6, -38)]
# Legs (left): femur head at the coxa, knee, ankle (tibia to basitarsus) and the tip of the
# tarsus. The femurs climb out and back from the coxae under the carapace, so the knees stand
# beside the body as on the sheet, and the feet splay from beside the pincers to under the tail.
LEGS = {1: ((398, 30, 100), (350, 86, 152), (380, 122, 56), (402, 134, 4)),
        2: ((378, 37, 98), (296, 100, 162), (310, 147, 56), (326, 160, 4)),
        3: ((356, 42, 98), (226, 106, 167), (208, 152, 56), (210, 168, 4)),
        4: ((336, 45, 100), (148, 102, 164), (104, 140, 56), (72, 150, 4))}
LEG_R = {1: 1.0, 2: 1.0, 3: 1.05, 4: 1.08}

def table(rows, sigma=3.0):
    """A smooth function X -> (half-width, top, bottom) through a table of sections."""
    rows = sorted(rows); X = np.array([r[0] for r in rows], float); Y = np.array([r[1:] for r in rows], float)
    xs = np.arange(X[0], X[-1] + .25, .5)
    ys = np.stack([np.interp(xs, X, Y[:, j]) for j in range(Y.shape[1])], 1)
    k = np.exp(-.5 * (np.arange(-4 * sigma, 4 * sigma + .25, .5) / sigma) ** 2); k /= k.sum(); pad = len(k) // 2
    yp = np.pad(ys, ((pad, pad), (0, 0)), mode='edge')
    ys = np.stack([np.convolve(yp[:, j], k, mode='valid') for j in range(ys.shape[1])], 1)
    return lambda x: tuple(float(np.interp(x, xs, ys[:, j])) for j in range(ys.shape[1]))

PRO, MES = table(PROSOMA), table(MESO)

def tail_joints():
    """The joints of the tail: points along its midline at the segments' lengths."""
    path = resample(catmull([P(x, 0, z) for x, z in TAIL_PATH], 16), 800)
    arc = [0.0]
    for a, b in zip(path, path[1:]): arc.append(arc[-1] + (b - a).length)
    J, acc = [path[0].copy()], 0.0
    for L in SEG_LEN:
        acc += L * S; J.append(path[next((k for k in range(len(arc)) if arc[k] >= acc), len(arc) - 1)].copy())
    return J
TJ = tail_joints()

def dorsal(d): return V((0, -d.z, d.y))   # the back of the tail, for a direction d along it

def telson_axes():
    """The telson's axis and back: folded from the last segment over its back, so the vesicle
    hangs under the arch with the sting curving down."""
    d5 = (TJ[5] - TJ[4]).normalized(); R = Matrix.Rotation(math.radians(TELSON['fold']), 3, 'X')
    return R @ d5, R @ dorsal(d5)

def palp_pts(sx):
    return {k: P(*PALP[k][:1], sx * PALP[k][1], PALP[k][2]) for k in ('C', 'E', 'W', 'H0', 'H1')}

def hand_frame(sx):
    p = palp_pts(sx); f = (p['H1'] - p['H0']).normalized(); up = (UP - f * UP.dot(f)).normalized()
    out = up.cross(f) * sx   # outward from the body on either side
    return p['H0'], f, out, up

def finger_pts(sx, pts):
    o, f, out, up = hand_frame(sx)
    return [o + f * (a * S) + out * (b * S) + up * (c * S) for a, b, c in pts]

def leg_pts(k, sx): return [P(x, sx * l, z) for x, l, z in LEGS[k]]


# ── Mesh building ───────────────────────────────────────────────────────────
def bones():
    B = [('root', (0, 0, 0), (0, -.3, 0), None, False),
         ('prosoma', P(330, 0, 132), P(420, 0, 132), 'root', True),
         ('meso1', P(326, 0, 134), P(215, 0, 150), 'prosoma', True),
         ('meso2', P(215, 0, 150), TJ[0], 'meso1', True)]
    prev = 'meso2'
    for i in range(5): B.append((f'tail{i + 1}', TJ[i], TJ[i + 1], prev, True)); prev = f'tail{i + 1}'
    dt, nt = telson_axes(); B.append(('telson', TJ[5], TJ[5] + dt * (TELSON['length'] * S), prev, True))
    for s, sx in SIDES:
        p = palp_pts(sx); mv = finger_pts(sx, MOVABLE)
        B += [(f'palp_fem.{s}', p['C'], p['E'], 'prosoma', True), (f'palp_pat.{s}', p['E'], p['W'], f'palp_fem.{s}', True),
              (f'chela.{s}', p['W'], p['H1'], f'palp_pat.{s}', True), (f'finger.{s}', mv[0], mv[-1], f'chela.{s}', True)]
        for k in LEGS:
            C, K, A, F = leg_pts(k, sx)
            B += [(f'femur{k}.{s}', C, K, 'prosoma', True), (f'tibia{k}.{s}', K, A, f'femur{k}.{s}', True),
                  (f'tarsus{k}.{s}', A, F, f'tibia{k}.{s}', True)]
    return B
BONE_NAMES = [b[0] for b in bones()]

class Mesh:
    """A mesh under construction. Every vertex is tagged with the bone it rides on (or two
    bones and a blend, for the membranes that bend at the joints) and with 'rim', how near
    it lies to a joint, where the chitin shows dark brown."""
    def __init__(self, name, uv=False):
        self.name = name; self.bm = bmesh.new(); L = self.bm.verts.layers
        self.b0, self.b1, self.w1, self.rim = L.int.new('b0'), L.int.new('b1'), L.float.new('w1'), L.float.new('rim')
        self.uv = self.bm.loops.layers.uv.new('UV') if uv else None
    def tag(self, bone, bone2=None, wfn=None):
        i0 = BONE_NAMES.index(bone) + 1; i1 = BONE_NAMES.index(bone2) + 1 if bone2 else 0
        for v in self.bm.verts:
            if v[self.b0] == 0:
                v[self.b0] = i0
                if i1: v[self.b1] = i1; v[self.w1] = wfn(v.co)
    def finish(self, smooth_=True):
        """The object, with a vertex group per bone from the tags."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        ob = obj_from_bm(self.name, self.bm, smooth_); me = ob.data; A = me.attributes
        b0 = [a.value for a in A['b0'].data]; b1 = [a.value for a in A['b1'].data]; w1 = [a.value for a in A['w1'].data]
        groups = {i: ob.vertex_groups.new(name=BONE_NAMES[i - 1]) for i in sorted(set(b0) | set(b1)) if i}
        rigid = {}
        for vi, (a, b, w) in enumerate(zip(b0, b1, w1)):
            if b and w > .001:
                if w < .999: groups[a].add([vi], 1 - w, 'REPLACE')
                groups[b].add([vi], w, 'REPLACE')
            else: rigid.setdefault(a, []).append(vi)
        for a, vs in rigid.items(): groups[a].add(vs, 1.0, 'REPLACE')
        for n in ('b0', 'b1', 'w1'): A.remove(A[n])
        return ob

def sheet(M, rows, closed=True, caps=(False, False), loop=False, rim=None, uv=None):
    """Quads through rows of points, each row a section in order along the part: closed rows
    wrap round, loop joins the last row to the first, caps close the ends with a fan. rim(i)
    is a row's nearness to a joint; uv(i, k, face) a corner's UV (face: the face's first k,
    or -1 on a cap)."""
    bm = M.bm; R = [[bm.verts.new(p) for p in row] for row in rows]
    if rim:
        for i, row in enumerate(R):
            r = rim(i)
            for v in row: v[M.rim] = r
    n = len(R[0])
    for i in range(len(R) if loop else len(R) - 1):
        i2 = (i + 1) % len(R)
        for k in range(n if closed else n - 1):
            k2 = (k + 1) % n
            f = bm.faces.new((R[i][k], R[i][k2], R[i2][k2], R[i2][k]))
            if uv:
                for lp, (a, b) in zip(f.loops, ((i, k), (i, k + 1), (i + 1, k + 1), (i + 1, k))): lp[M.uv].uv = uv(a, b, k)
    for on, row, i in ((caps[0], R[0], 0), (caps[1], R[-1], len(R) - 1)):
        if not on: continue
        c = bm.verts.new(sum((v.co for v in row), V()) / n); c[M.rim] = row[0][M.rim]
        for k in range(n):
            f = bm.faces.new((row[k], row[(k + 1) % n], c))
            if uv:
                for lp, kk in zip(f.loops, (k, k + 1, k)): lp[M.uv].uv = uv(i, kk, -1)
    return R

def sec_pt(c, side, up, w, top, bot, a, nt=2.4, nb=2.4, off=0.0, keels=()):
    """The point at angle a (0 at the side, pi/2 on top) of a section centred at c: a
    superellipse of half-width w with top and bot its height above and depth below the centre
    (sheet px), moved off px outward, with keels (angle from the top, height, width) along it."""
    ca, sa = math.cos(a), math.sin(a); n = nt if sa >= 0 else nb; h = top if sa >= 0 else bot
    x = math.copysign(abs(ca) ** (2 / n), ca); y = math.copysign(abs(sa) ** (2 / n), sa)
    nrm = (side * (ca / max(w, .1)) + up * (sa / max(h, .1))).normalized()
    phi = (a - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi
    off = off + sum(kh * math.exp(-((phi - ka) / kw) ** 2) for ka, kh, kw in keels)
    return c + side * (x * w * S) + up * (y * h * S) + nrm * (off * S)

def ring(c, side, up, w, top, bot, K, **kw):
    return [sec_pt(c, side, up, w, top, bot, 2 * math.pi * q / K, **kw) for q in range(K)]

def interp(prof, t): return float(np.interp(t, [p[0] for p in prof], [p[1] for p in prof]))

def tube(M, a, b, side, w, h, prof, K=18, rim=None, keels=(), nt=2.4, nb=2.4):
    """A straight limb segment from a to b: rows (t, k) of profile prof, sections w by h (px)."""
    d = (b - a).normalized(); sd = (side - d * side.dot(d)).normalized(); up = d.cross(sd)
    rows = [ring(a + (b - a) * t, sd, up, w * k, h * k, h * k, K, nt=nt, nb=nb, keels=keels) for t, k in prof]
    sheet(M, rows, caps=(True, True), rim=(lambda i: rim(prof[i][0])) if rim else None)

def blob(M, c, rx, ry, rz, R=None, seg=(16, 10)):
    """An ellipsoid (radii in px) at c."""
    Mx = Matrix.Translation(c) @ (R or Matrix.Identity(3)).to_4x4() @ Matrix.Diagonal((rx * S, ry * S, rz * S, 1))
    bmesh.ops.create_uvsphere(M.bm, u_segments=seg[0], v_segments=seg[1], radius=1, matrix=Mx)

def cone(M, base, d, length, r0, r1=.05, seg=8, curve=None):
    """A tapering spike from base along d (px), bending towards curve as it goes."""
    rows = []; n = 6; p = base.copy(); dd = d.normalized()
    for i in range(n + 1):
        t = i / n; r = (r0 + (r1 - r0) * t ** .8) * S
        sd = dd.orthogonal().normalized(); up = dd.cross(sd)
        rows.append([p + (sd * math.cos(2 * math.pi * q / seg) + up * math.sin(2 * math.pi * q / seg)) * r for q in range(seg)])
        if curve is not None: dd = (dd + curve * (1.0 / n)).normalized()
        p = p + dd * (length * S / n)
    sheet(M, rows, caps=(True, True))

def ramp01(a, b, x): return max(0.0, min(1.0, (x - a) / (b - a)))


# ── The scorpion ────────────────────────────────────────────────────────────
KB = 44   # sections round the body
CARAPACE_KEELS = ((math.pi / 2 - .32, 1.4, .07), (-(math.pi / 2 - .32), 1.4, .07), (0, -.8, .05))

def body_pt(X, a, off=0.0, keels=(), table_=MES, nt=2.5, nb=3.0):
    w, top, bot = table_(X); zc = (top + bot) / 2
    return sec_pt(P(X, 0, zc), SIDE, UP, w, top - zc, zc - bot, a, nt=nt, nb=nb, off=off, keels=keels)

def build_prosoma(M):
    """The carapace and the head beneath it: a flat-topped plate with its margins and a median
    furrow, the coxae of the legs and the pedipalps forming its underside, and the eye mound."""
    Xs = list(np.linspace(314, 424, 60))
    rows = [[body_pt(X, 2 * math.pi * q / KB, keels=CARAPACE_KEELS, table_=PRO, nt=2.9, nb=3.4) for q in range(KB)] for X in Xs]
    sheet(M, rows, caps=(True, True), rim=lambda i: max(ramp01(320, 314, Xs[i]), .6 * ramp01(414, 424, Xs[i])))
    blob(M, P(365, 0, 164.5), 10, 9, 4.5)   # the median eye mound
    for s, sx in SIDES:
        for k, (C, K, A, F) in LEGS.items():   # coxae, meeting under the carapace
            blob(M, P(C[0] + 2, sx * C[1] * .55, 100), 12, C[1] * .55 + 6, 7.5)
        blob(M, P(414, sx * 15, 104), 11, 12, 8)
    M.tag('prosoma')

def build_eyes(M):
    for s, sx in SIDES:
        blob(M, P(367, sx * 4.6, 168.6), 3.6, 3.6, 3.6, seg=(14, 9))
        for dx, dl, dz in ((0, 0, 0), (-4, 2, -1), (4, -1.5, -1.5)):   # three lateral eyes at each front corner
            blob(M, P(409 + dx, sx * (41 + dl), 152 + dz), 1.9, 1.9, 1.9, seg=(10, 6))
    M.tag('prosoma')

def build_chelicerae(M):
    for s, sx in SIDES:
        blob(M, P(418, sx * 9, 116), 10, 7.5, 8)
        cone(M, P(424, sx * 9, 121), V((0, -1, -.35)), 12, 3.6, .4, curve=V((0, 0, -.6)))
        cone(M, P(423, sx * 12, 111), V((-sx * .3, -1, 0)), 11, 3.0, .4, curve=V((sx * .5, 0, .3)))
    M.tag('prosoma')

def plate_rows(pt, nu, nv, Xs=None):
    """Rows for a plate of some thickness: across each row the outer face, then the inner
    face back again, so that the plate is a closed shell. pt(u, v, outer) gives the points."""
    return [[pt(i / nu, j / nv, True) for i in range(nu + 1)] + [pt(i / nu, j / nv, False) for i in range(nu, -1, -1)]
            for j in range(nv + 1)]

def tergite(k, extra=0.0):
    """Where tergite k lies: (u, v) -> point, u across its back and v from its front edge to its
    rear, which stands proud over the next; extra lifts it (the armour lies over it)."""
    Xa, Xb = TERGITES[k]; last = k == len(TERGITES) - 1
    def pt(u, v, out):
        X = Xa + (Xb - Xa) * v
        th = math.radians(74 + (21 * v ** 1.5 if last else 0))
        a = math.pi / 2 + th * (2 * u - 1)
        lift = 1.0 + 2.6 * smooth(0, 1, v) + extra
        fade = min(1.0, v / .25, (1 - v) / .2)
        keels = ((0, 1.1 * fade, .06), (.42, .7 * fade, .06), (-.42, .7 * fade, .06))
        return body_pt(X, a, off=lift - (0 if out else 2.3), keels=keels)
    return pt

def sternite(k, extra=0.0):
    Xa, Xb = STERNITES[k]; last = k == len(STERNITES) - 1
    def pt(u, v, out):
        X = Xa + (Xb - Xa) * v
        th = math.radians(62 + (24 * v ** 1.5 if last else 0))
        a = 1.5 * math.pi + th * (2 * u - 1)
        return body_pt(X, a, off=.6 + 1.6 * smooth(0, 1, v) + extra - (0 if out else 2.0))
    return pt

def build_abdomen(M):
    """The seven tergites, overlapping like tiles from the front, and the five sternites."""
    for k in range(len(TERGITES)):
        nv = 14 if k == len(TERGITES) - 1 else 8
        sheet(M, plate_rows(tergite(k), 40, nv), caps=(True, True), rim=lambda i, nv=nv: ramp01(.6, 1, i / nv) * .8)
        M.tag('meso1' if k < 4 else 'meso2')
    for k in range(len(STERNITES)):
        nv = 12 if k == len(STERNITES) - 1 else 7
        sheet(M, plate_rows(sternite(k), 30, nv), caps=(True, True), rim=lambda i, nv=nv: ramp01(.7, 1, i / nv) * .6)
        M.tag('meso1' if k < 2 else 'meso2')

def build_pleura(M):
    """The soft folded membrane between the plates, from under the carapace to the tail."""
    Xs = list(np.linspace(334, 88, 70))
    rows = [[body_pt(X, 2 * math.pi * q / KB, off=-1.4) for q in range(KB)] for X in Xs]
    sheet(M, rows, caps=(True, True))
    def w(co):   # meso1 from the carapace back, meso2 from the middle
        X = X0 - co.y / S; return ramp01(330, 320, X)
    M.tag('prosoma', 'meso1', w)
    for v in M.bm.verts:   # and on to meso2 behind the fourth tergite
        X = X0 - v.co.y / S
        if v[M.b1] == BONE_NAMES.index('meso1') + 1 and X < 228:
            v[M.b0] = BONE_NAMES.index('meso1') + 1; v[M.b1] = BONE_NAMES.index('meso2') + 1; v[M.w1] = ramp01(228, 204, X)

def build_pectines(M):
    """The comb organs under the second segment of the abdomen, angled out and back."""
    for s, sx in SIDES:
        a, b = P(324, sx * 9, 96.5), P(312, sx * 44, 98.5)
        tube(M, a, b, UP, 2.6, 2.2, [(-.05, .3), (0, 1), (1, .8), (1.04, .3)], K=8)
        for i in range(15):
            p = a.lerp(b, .06 + .9 * i / 14) + V((0, 0, -1.2 * S))
            cone(M, p, V((sx * .25, 1, -.25)), 6.5 - 2 * i / 14, 1.2, .3, seg=6)
    M.tag('meso1')

# The tail segment's profile along its length: a narrow neck that sits inside the segment
# before, the swollen barrel, and a lip at the far end round the next one's neck.
SEG_PROF = [(-.07, .56), (-.03, .64), (0, .72), (.06, .85), (.15, .94), (.3, .985), (.55, 1.0), (.8, .985), (.92, .965),
            (.975, .93), (1.0, .87)]
SEG_T = [-.07, -.03, 0, .03, .06, .1, .15, .22, .3, .4, .5, .6, .7, .8, .87, .92, .955, .975, .99, 1.0]
TAIL_KEELS = ((0, -1.8, .2), (.5, 2.0, .1), (-.5, 2.0, .1), (1.2, 1.4, .1), (-1.2, 1.4, .1), (2.0, 1.3, .1), (-2.0, 1.3, .1),
              (2.7, 1.0, .1), (-2.7, 1.0, .1))

def seg_frame(i):
    a, b = TJ[i], TJ[i + 1]; d = (b - a).normalized(); return a, b, d, dorsal(d)

def seg_pt(i, t, ang, off=0.0, keels=True, k=None):
    """A point on tail segment i at t along it (0 at its base, 1 at the next joint)."""
    a, b, d, n = seg_frame(i); W, Hh = SEG_R[i]; k = interp(SEG_PROF, t) if k is None else k
    fade = min(1.0, max(0.0, (t - .05) / .1), max(0.0, (.97 - t) / .07))
    kl = tuple((ka, kh * fade, kw) for ka, kh, kw in TAIL_KEELS) if keels else ()
    return sec_pt(a + (b - a) * t, SIDE, n, W * k, Hh * k, Hh * k, ang, nt=2.3, nb=2.2, off=off, keels=kl)

def build_tail(M):
    """The five swollen segments of the tail, each with its keels and dorsal groove."""
    K = 40
    for i in range(5):
        rows = [[seg_pt(i, t, 2 * math.pi * q / K) for q in range(K)] for t in SEG_T]
        rows += [[seg_pt(i, t, 2 * math.pi * q / K, keels=False, k=k) for q in range(K)] for t, k in ((1.0, .8), (.985, .75))]
        ts = SEG_T + [1.0, .985]
        sheet(M, rows, caps=(True, True), rim=lambda r, ts=ts: max(ramp01(.12, 0, ts[r]), ramp01(.9, 1.0, ts[r])) * .9)
        M.tag(f'tail{i + 1}')

def build_telson(M, grow=1.0):
    """The bulbous vesicle, flatter on its back, and the sting curving down from its tip."""
    dt, nt = telson_axes(); o = TJ[5]; Lv = TELSON['length'] * S; W, Hh = TELSON['w'] * grow, TELSON['h'] * grow
    prof = [(-.08, .45), (0, .55), (.06, .68), (.12, .79), (.2, .9), (.3, .97), (.42, 1.0), (.55, .96), (.68, .86), (.8, .7),
            (.9, .5), (1.0, .32)]
    rows, rims = [], []; K = 32
    for t, k in prof:
        c = o + dt * (t * Lv) - nt * (2.5 * math.sin(math.pi * max(0, t)) * S)
        rows.append(ring(c, SIDE, nt, W * k, Hh * .82 * k, Hh * 1.08 * k, K, nt=2.2, nb=2.1)); rims.append(ramp01(.1, -.08, t) * .7)
    # the sting: on from the tip of the vesicle, curving towards the belly and tapering to a point
    p = o + dt * Lv - nt * (0 * S); d, up = dt.copy(), nt.copy(); n = 14; La = TELSON['sting'] * S * grow
    for j in range(1, n + 1):
        s = j / n; ang = math.radians(TELSON['curl']) * (s ** 1.25 - ((j - 1) / n) ** 1.25)
        R = Matrix.Rotation(-ang, 3, SIDE); d = R @ d; up = R @ up; p = p + d * (La / n)
        r = .32 * (1 - s) ** .85 + .01
        rows.append(ring(p, SIDE, up, W * r, Hh * r, Hh * r, K)); rims.append(.3 + .7 * s)
    sheet(M, rows, caps=(True, True), rim=lambda i: rims[i])
    M.tag('telson')

def build_palps(M):
    """The pedipalps: femur and patella, and the swollen hand of the chela."""
    for s, sx in SIDES:
        p = palp_pts(sx)
        tube(M, p['C'], p['E'], UP, 8.5, 9.5, [(-.12, .3), (-.08, .7), (0, .9), (.1, 1), (.5, .95), (.9, 1.0), (1.0, .95), (1.06, .7), (1.1, .3)],
             K=22, rim=lambda t: max(ramp01(.1, -.08, t), ramp01(.9, 1.08, t)) * .7)
        M.tag(f'palp_fem.{s}')
        tube(M, p['E'], p['W'], UP, 10.5, 11.5, [(-.1, .3), (-.07, .75), (0, .92), (.15, 1.05), (.5, 1.1), (.85, 1.0), (1.0, .9), (1.05, .7), (1.08, .3)],
             K=24, rim=lambda t: max(ramp01(.1, -.07, t), ramp01(.9, 1.05, t)) * .7, keels=((.4, .8, .1), (-.4, .8, .1)))
        M.tag(f'palp_pat.{s}')
        hand(M, sx); M.tag(f'chela.{s}')

HAND_PROF = [(-.07, .3), (-.06, .45), (0, .64), (.1, .88), (.25, .98), (.45, 1.0), (.62, .98), (.78, .93), (.9, .85), (1.0, .74),
             (1.06, .55), (1.09, .25)]

def hand_pt(sx, t, ang, off=0.0):
    o, f, out, up = hand_frame(sx); L = (palp_pts(sx)['H1'] - o).length; k = interp(HAND_PROF, t)
    keels = ((.0, 1.4, .1), (math.pi / 2 - .25, 1.3, .08), (-(math.pi / 2 - .25), 1.3, .08), (math.pi - .5, 1.0, .1), (-(math.pi - .5), 1.0, .1))
    return sec_pt(o + f * (t * L), out, up, PALP['w'] * k, PALP['h'] * k, PALP['h'] * .94 * k, ang, nt=2.6, nb=2.6, off=off, keels=keels)

def hand(M, sx):
    K = 36; ts = [t for t, _ in HAND_PROF]
    rows = [[hand_pt(sx, t, 2 * math.pi * q / K) for q in range(K)] for t in ts]
    sheet(M, rows, caps=(True, True), rim=lambda i: ramp01(.08, -.06, ts[i]) * .8)

def finger(M, sx, pts, cut, w0=9.0, h0=15.0):
    """A finger of the chela lofted along its points, with a row of denticles on its cutting
    edge (cut: the side, in the hand's up direction, that faces the other finger)."""
    o, f, out, up = hand_frame(sx)
    path = resample(catmull(finger_pts(sx, pts), 8), 16)
    rows = []
    for i, c in enumerate(path):
        t = i / (len(path) - 1); d = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        k = (1 - t) ** .7 * .9 + .1
        rows.append(ring(c, out, (up - d * up.dot(d)).normalized(), w0 * k, h0 * k, h0 * k, 16, nt=2.2, nb=2.2))
    sheet(M, rows, caps=(True, True))
    for i in range(3, len(path) - 2):   # denticles, two larger ones near the middle
        t = i / (len(path) - 1); k = (1 - t) ** .7 * .9 + .1
        big = i in (6, 10)
        cone(M, path[i] + up * (cut * h0 * k * .7 * S), up * cut + f * .3, (6.0 if big else 3.6) * (1.1 - .4 * t), 2.0 if big else 1.4, .2, seg=6)

def build_fingers(M):
    for s, sx in SIDES:
        finger(M, sx, FIXED, -1); M.tag(f'chela.{s}')
        finger(M, sx, MOVABLE, 1, 8.0, 11.0); M.tag(f'finger.{s}')

FEMUR_PROF = [(-.07, .35), (-.05, .7), (0, .85), (.08, 1.0), (.5, .93), (.9, 1.0), (1.0, .95), (1.04, .7), (1.06, .3)]
TIBIA_PROF = [(-.06, .35), (-.04, .75), (0, 1.0), (.08, 1.15), (.18, 1.05), (.24, .88), (.29, .95), (.6, .9), (.9, .85), (1.0, .8),
              (1.04, .6), (1.06, .3)]
TARSUS_PROF = [(-.06, .35), (-.04, .65), (0, .8), (.1, .8), (.56, .7), (.6, .6), (.64, .64), (.95, .45), (1.0, .35), (1.02, .2)]

def build_legs(M):
    """The four pairs of walking legs: femur, patella with tibia, and basitarsus with tarsus,
    ending in two claws, each part on its own bone."""
    for s, sx in SIDES:
        for k in LEGS:
            C, K, A, F = leg_pts(k, sx); g = LEG_R[k]; nh = (K - C).cross(A - K).normalized()
            rim = lambda t: max(ramp01(.08, -.05, t), ramp01(.92, 1.04, t)) * .8
            tube(M, C, K, nh, 9.0 * g, 10.4 * g, FEMUR_PROF, rim=rim, keels=((.6, .6, .1), (-.6, .6, .1))); M.tag(f'femur{k}.{s}')
            tube(M, K, A, nh, 8.2 * g, 9.0 * g, TIBIA_PROF, rim=rim); M.tag(f'tibia{k}.{s}')
            tube(M, A, F, nh, 6.6 * g, 6.6 * g, TARSUS_PROF, K=14, rim=rim)
            d = (F - A).normalized(); fw = V((0, -1, 0)); out = V((sx, 0, 0))
            for c in (-1, 1):   # the two claws, and a pair of spurs at the joint above
                cone(M, F - d * (2 * S), (d + fw * .5 + out * .35 * c + fw.cross(out) * 0).normalized(), 7, 1.7, .2, seg=6, curve=V((0, 0, -1.2)))
                cone(M, A.lerp(F, .6), (d + out * .7 * c).normalized(), 4.5, 1.1, .2, seg=6)
            M.tag(f'tarsus{k}.{s}')

def knot(M, J, r, b0, b1, d):
    """A membrane at a joint: a ball bending between the bones either side."""
    blob(M, J, r, r, r, seg=(14, 9)); dn = d.normalized()
    M.tag(b0, b1, lambda co: smooth(-r * S, r * S, (co - J).dot(dn)))

def build_joints(M):
    """The membranes at every joint of the tail, the pedipalps and the legs."""
    names = ['meso2'] + [f'tail{i + 1}' for i in range(5)] + ['telson']
    dt, _ = telson_axes()
    for i in range(6):
        d = dt if i == 5 else (TJ[i + 1] - TJ[i]).normalized(); dp = (TJ[i] - TJ[i - 1]).normalized() if i else d
        W, Hh = (TELSON['w'], TELSON['h']) if i == 5 else SEG_R[i]; n = dorsal(d)
        rows = [ring(TJ[i] + d * (t * S), SIDE, n, W * .64, Hh * .64, Hh * .64, 28) for t in (-9, -5, 0, 4)]
        sheet(M, rows, caps=(True, True))
        M.tag(names[i], names[i + 1], lambda co, J=TJ[i], d=d: smooth(-4 * S, 3 * S, (co - J).dot(d)))
    for s, sx in SIDES:
        p = palp_pts(sx)
        knot(M, p['C'], 8.5, 'prosoma', f'palp_fem.{s}', p['E'] - p['C'])
        knot(M, p['E'], 9.5, f'palp_fem.{s}', f'palp_pat.{s}', p['W'] - p['E'])
        knot(M, p['W'], 9.5, f'palp_pat.{s}', f'chela.{s}', p['H1'] - p['W'])
        mv = finger_pts(sx, MOVABLE); knot(M, mv[0], 6.5, f'chela.{s}', f'finger.{s}', mv[1] - mv[0])
        for k in LEGS:
            C, K, A, F = leg_pts(k, sx); g = LEG_R[k]
            knot(M, C, 9.6 * g, 'prosoma', f'femur{k}.{s}', K - C)
            knot(M, K, 8.8 * g, f'femur{k}.{s}', f'tibia{k}.{s}', A - K)
            knot(M, A, 6.8 * g, f'tibia{k}.{s}', f'tarsus{k}.{s}', F - A)

def build_band(M):
    """The Veteran's band of hammered gold round the second tail segment, with rolled edges."""
    W, Hh = SEG_R[1]; K = 40
    prof = [(.07, .9, .0), (.075, 1.05, .0), (.09, 1.085, .0), (.12, 1.075, .0), (.5, 1.075, .0), (.88, 1.075, .0), (.91, 1.085, .0),
            (.925, 1.05, .0), (.93, .9, .0)]
    a, b, d, n = seg_frame(1)
    rows = [ring(a + (b - a) * t, SIDE, n, W * k, Hh * k, Hh * k, K, nt=2.3, nb=2.2) for t, k, _ in prof]
    sheet(M, rows, loop=True)
    M.tag('tail2')


# ── Armour (L3): gilded bronze set with lapis lazuli ─────────────────────────
ATLAS = 2048
TILES = {'lotus_wide': (0, 0, 2048, 512), 'lotus_tall': (0, 512, 512, 1024), 'feather_tall': (512, 512, 512, 1024),
         'feather_sq': (1024, 512, 512, 512), 'lotus_sq': (1536, 512, 512, 512), 'gold': (1024, 1024, 1024, 1024)}

def tile_uv(tile, u, v):
    x, y, w, h = TILES[tile]; e = 3
    return ((x + e + u * (w - 2 * e)) / ATLAS, 1 - (y + e + (1 - v) * (h - 2 * e)) / ATLAS)

def armour_plate(M, pt, nu, nv, tile, bone):
    """A plate of gilded bronze: its outer face mapped to an inlay tile of the atlas, its edges
    and underside to plain gold."""
    def uv(i, k, face):
        if 0 <= face < nu: return tile_uv(tile, min(k, nu) / nu, i / nv)
        kk = k if k <= nu else 2 * nu + 1 - k
        return tile_uv('gold', .1 + .8 * max(0, min(nu, kk)) / nu, .1 + .8 * i / nv)
    sheet(M, plate_rows(pt, nu, nv), caps=(True, True), uv=uv)
    M.tag(bone)

def build_armour(M):
    """The Elite's armour: a plate over the carapace, one over each tergite and sternite, four
    round each tail segment (the second wears the gold band), and plates on the pincers."""
    def carapace(u, v, out):
        X = 416 - 94 * v; a = math.pi / 2 + math.radians(70) * (2 * u - 1)
        return body_pt(X, a, off=(3.0 if out else 1.2), keels=CARAPACE_KEELS, table_=PRO, nt=2.9, nb=3.4)
    armour_plate(M, carapace, 32, 12, 'lotus_sq', 'prosoma')
    for k in range(len(TERGITES)):
        last = k == len(TERGITES) - 1
        armour_plate(M, lambda u, v, out, k=k: tergite(k, extra=(2.4 if out else .5))(.04 + .92 * u, .03 + .94 * v, True),
                     36, 12 if last else 6, 'lotus_sq' if last else 'lotus_wide', 'meso1' if k < 4 else 'meso2')
    for k in range(len(STERNITES)):
        last = k == len(STERNITES) - 1
        armour_plate(M, lambda u, v, out, k=k: sternite(k, extra=(2.2 if out else .4))(.05 + .9 * u, .03 + .94 * v, True),
                     28, 10 if last else 6, 'lotus_sq' if last else 'lotus_wide', 'meso1' if k < 2 else 'meso2')
    for i in (0, 2, 3, 4):
        for centre, tile in ((math.pi / 2, 'lotus_tall'), (0, 'feather_tall'), (math.pi, 'feather_tall'), (1.5 * math.pi, 'lotus_tall')):
            def pt(u, v, out, i=i, c=centre):
                t = .1 + .8 * v; a = c + .62 * (2 * u - 1) * (1 if c != math.pi else -1)
                return seg_pt(i, t, a, off=(3.2 if out else 1.5), keels=False, k=1.0 - .04 * abs(2 * v - 1) ** 2)
            armour_plate(M, pt, 12, 10, tile, f'tail{i + 1}')
    for s, sx in SIDES:
        for centre, span in ((0, 1.45), (math.pi, 1.3)):   # the outer and inner faces of the hand
            def pt(u, v, out, c=centre, sp=span, sx=sx):
                t = .1 + .8 * v; return hand_pt(sx, t, c + sp * (2 * u - 1), off=(2.8 if out else 1.2))
            armour_plate(M, pt, 16, 12, 'feather_sq', f'chela.{s}')
        p = palp_pts(sx); d = (p['W'] - p['E']).normalized(); sd = (UP - d * UP.dot(d)).normalized(); up = d.cross(sd)
        def pat(u, v, out, p=p, sd=sd, up=up):
            t = .14 + .72 * v; k = interp([(0, .92), (.15, 1.05), (.5, 1.1), (.85, 1.0), (1, .9)], t)
            c = p['E'] + (p['W'] - p['E']) * t
            return sec_pt(c, sd, up, 10.5 * k, 11.5 * k, 11.5 * k, math.pi / 2 + 1.25 * (2 * u - 1), off=(2.6 if out else 1.0))
        armour_plate(M, pat, 12, 10, 'feather_tall', f'palp_pat.{s}')

def armour_atlas():
    """The armour's textures, drawn as cloisonné: lapis lazuli set in gold cells inside a gold
    border, lotus fans for the body plates and feathers for the tail and the pincers, and a
    plain tile of hammered gold for the edges. Returns colour, metal-roughness and normal images."""
    from PIL import Image, ImageDraw, ImageFilter
    A = ATLAS; k = 2; N = A * k
    gold = Image.new('L', (N, N), 0)
    def petal(base, tip, wmax, lw, fan=False):
        """A lotus petal outlined in gold from its base to its point, with a midrib: rounded at
        the base in a row, widest towards the tip in a fan."""
        (bx, by), (tx, ty) = base, tip; L = math.hypot(tx - bx, ty - by); ux, uy = (tx - bx) / L, (ty - by) / L
        pl, pr = [], []
        for i in range(25):
            s_ = i / 24
            hw = wmax * (s_ ** .9 * (1 - s_) ** .5 / .401 if fan else (1 - s_) ** .55 * math.sqrt(max(0.0, 1 - (1 - min(s_ / .22, 1)) ** 2)))
            cx, cy = bx + ux * L * s_, by + uy * L * s_
            pl.append((cx - uy * hw, cy + ux * hw)); pr.append((cx + uy * hw, cy - ux * hw))
        outline = pl + pr[::-1]
        dr.line(outline + [outline[0]], fill=255, width=lw, joint='curve')
        dr.line([(bx + ux * L * .14, by + uy * L * .14), (bx + ux * L * .8, by + uy * L * .8)], fill=255, width=max(2, lw * 2 // 3))
    for name, (x0, y0, w, h) in TILES.items():
        x, y, w, h = 0, 0, w * k, h * k
        tile = Image.new('L', (w, h), 0); dr = ImageDraw.Draw(tile)
        dr.rectangle((x, y, x + w - 1, y + h - 1), fill=255)
        if name == 'gold': gold.paste(tile, (x0 * k, y0 * k)); continue
        m = min(w, h); b = int(.13 * m); lw = max(8, int(.03 * m))
        dr.rectangle((x + b, y + b, x + w - 1 - b, y + h - 1 - b), fill=0)
        fx0, fy0, fx1, fy1 = x + b, y + b, x + w - b, y + h - b
        if name == 'lotus_wide':   # a row of petals leaning out a little from the middle
            n = 13; pw = (fx1 - fx0) / n
            for i in range(n):
                cx = fx0 + pw * (i + .5); lean = (cx - (fx0 + fx1) / 2) * .12
                petal((cx, fy1 + lw), (cx + lean, fy0 + lw), pw * .44, lw)
        elif name.startswith('lotus'):   # a lotus fan rising from its calyx at the base
            n = 7 if name == 'lotus_tall' else 9; ox, oy = (fx0 + fx1) / 2, fy1 - lw
            R1 = (fy1 - fy0) * .95; R0 = min(R1 * .16, (fx1 - fx0) * .22)
            spread = math.radians(30 if name == 'lotus_tall' else 58)
            for i in range(n):
                f_ = (i + .5) / n * 2 - 1; ang = spread * f_; r1 = R1 * (1 - .12 * abs(f_))
                petal((ox + math.sin(ang) * R0 * .7, oy - math.cos(ang) * R0 * .7), (ox + math.sin(ang) * r1, oy - math.cos(ang) * r1),
                      r1 * spread / n * .54, lw, True)
            dr.pieslice((ox - R0, oy - R0, ox + R0, oy + R0), 180, 360, fill=255)
        else:   # a feather: a rib up the middle and barbs angled towards the tip
            cx = (fx0 + fx1) / 2; dr.line([(cx, fy1), (cx, fy0)], fill=255, width=int(lw * 1.3))
            step = (fx1 - fx0) * .3; yy = fy1 + step * .5
            while yy > fy0 - (fx1 - fx0):
                for sgn in (-1, 1):
                    dr.line([(cx, yy), (cx + sgn * (fx1 - fx0) / 2, yy - (fx1 - fx0) * .55)], fill=255, width=lw)
                yy -= step
            dr.rectangle((x, y, x + w - 1, y + b), fill=255); dr.rectangle((x, y + h - b, x + w - 1, y + h - 1), fill=255)
            dr.rectangle((x, y, x + b, y + h - 1), fill=255); dr.rectangle((x + w - b, y, x + w - 1, y + h - 1), fill=255)
        gold.paste(tile, (x0 * k, y0 * k))
    G = np.asarray(gold.resize((A, A), Image.LANCZOS), np.float32) / 255
    rng = np.random.default_rng(5)
    def noise(cell, octaves=3):
        out = np.zeros((A, A), np.float32); amp = 1.0; tot = 0
        for o in range(octaves):
            n = max(2, int(A / cell) + 1); g = rng.random((n, n)).astype(np.float32)
            out += amp * np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((A, A), Image.BICUBIC), np.float32) / 255
            tot += amp; amp *= .5; cell /= 2
        return out / tot
    hammer = noise(18, 2); vary = noise(160, 3); veins = noise(60, 4); fleck = rng.random((A, A)) > .9975
    def hexc(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    gold_c = hexc('#a5762a')[None, None] + (hexc('#f0c860') - hexc('#a5762a'))[None, None] * (.35 + .65 * (vary * .6 + hammer * .4))[..., None]
    lap = hexc('#080b38')[None, None] + (hexc('#1a2478') - hexc('#080b38'))[None, None] * np.clip((vary - .25) * 1.8, 0, 1)[..., None]
    calcite = np.clip((veins - .62) * 6, 0, 1)[..., None] * .35
    lap = lap * (1 - calcite) + hexc('#4a5498')[None, None] * calcite
    lap[fleck] = hexc('#d9b65a')
    col = lap * (1 - G[..., None]) + gold_c * G[..., None]
    rough = (.16 * (1 - G) + (.2 + .12 * hammer) * G)   # polished stone, hammered gold
    mr = np.stack([np.ones((A, A), np.float32), rough, G], -1)
    hgt = np.asarray(Image.fromarray((G * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255
    hgt = hgt * 2.2 + G * (hammer - .5) * 1.2 + (1 - G) * (veins - .5) * .15
    gy, gx = np.gradient(hgt)
    nx, ny = -gx * 1.4, gy * 1.4; nz = np.ones_like(nx); l = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nrm = np.stack([nx / l, ny / l, nz / l], -1) * .5 + .5
    imgs = []
    for nm, arr, cs in (('color', col, 'sRGB'), ('mr', mr, 'Non-Color'), ('normal', nrm, 'Non-Color')):
        p = os.path.join(OUT, f'scorpion_armour_{nm}.png')
        Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(p)
        img = bpy.data.images.load(p); img.colorspace_settings.name = cs; img.pack(); imgs.append(img)
    return imgs

def m_armour():
    col, mr, nrm = armour_atlas()
    m = bpy.data.materials.new('Armour'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    bsdf = N['Principled BSDF']
    tc = N.new('ShaderNodeTexImage'); tc.image = col; L.new(tc.outputs['Color'], bsdf.inputs['Base Color'])
    tm = N.new('ShaderNodeTexImage'); tm.image = mr; sep = N.new('ShaderNodeSeparateColor'); L.new(tm.outputs['Color'], sep.inputs['Color'])
    L.new(sep.outputs['Green'], bsdf.inputs['Roughness']); L.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
    tn = N.new('ShaderNodeTexImage'); tn.image = nrm; nm = N.new('ShaderNodeNormalMap')
    L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


# ── Materials ───────────────────────────────────────────────────────────────
def m_chitin(name, res=1024, base='#070606', warm='#140d0a', edge='#2f1a10', sheen='#1c1917', gran=110.0, gloss=.13, granules=1.0):
    """Glossy black chitin: granules domed in the bump and catching a little light on top, a
    faint warm cast, and dark brown where the plates meet at the joints (the rim attribute)."""
    m = Mat(name, res=res)
    vor = m.node('ShaderNodeTexVoronoi', Scale=gran); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    dome = m.ramp(vor.outputs['Distance'], [(0, (1, 1, 1)), (.48, (0, 0, 0))])
    big = m.ramp(m.noise(7, 4, .55).outputs['Fac'], [(.35, srgb(base)), (.75, srgb(warm))])
    col = m.mix(big.outputs['Color'], srgb(sheen), m.ramp(dome.outputs['Color'], [(0, (0, 0, 0)), (1, (.45 * granules,) * 3)]).outputs['Color'])
    rim = m.node('ShaderNodeAttribute', attribute_name='rim')
    col = m.mix(col, srgb(edge), rim.outputs['Fac'])
    fine = m.noise(380, 3, .6)
    rough = m.ramp(m.mix(dome.outputs['Color'], fine.outputs['Fac'], .25), [(0, (gloss + .13,) * 3), (.8, (gloss,) * 3)])
    bump = m.mix(m.mix((0, 0, 0), dome.outputs['Color'], granules), fine.outputs['Fac'], .18)
    m.set(col, rough.outputs['Color'], bump, .42, .002)
    return m

def m_membrane(name='Membrane', res=1024):
    """The soft membranes: dark brown, finely folded, a little less glossy than the plates."""
    m = Mat(name, res=res)
    wav = m.node('ShaderNodeTexWave', wave_type='BANDS', Scale=55.0, Distortion=7.0, Detail=3.0); m.L.new(m.coord.outputs['Object'], wav.inputs['Vector'])
    col = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb('#1a120d')), (.7, srgb('#3a2619'))])
    col = m.mix(col.outputs['Color'], srgb('#120c09'), m.ramp(wav.outputs['Fac'], [(.0, (.6, .6, .6)), (.5, (0, 0, 0))]).outputs['Color'])
    m.set(col, .38, wav.outputs['Fac'], .35, .002)
    return m

def m_gold(name, res=512):
    """Hammered gold: shallow facets from the hammer, bright where they turn to the light."""
    m = Mat(name, metal=1.0, res=res)
    vor = m.node('ShaderNodeTexVoronoi', Scale=70.0); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    dimple = m.ramp(vor.outputs['Distance'], [(0, (0, 0, 0)), (.6, (1, 1, 1))])
    col = m.ramp(m.noise(6, 4, .55).outputs['Fac'], [(.3, srgb('#a8792b')), (.55, srgb('#d4a542')), (.8, srgb('#efcb68'))])
    rough = m.ramp(m.noise(40, 3, .6).outputs['Fac'], [(.3, (.16, .16, .16)), (.7, (.3, .3, .3))])
    m.set(col.outputs['Color'], rough.outputs['Color'], dimple.outputs['Color'], .4, .0018)
    return m

def bake(items):
    """hoplite.bake_textures with the normal map at the colour's resolution, for the granules."""
    SC = H.SC; SC.cycles.samples = 4; SC.render.bake.use_selected_to_active = False; SC.render.bake.margin = 6
    for name, (ob, mt, bind) in items.items():
        if mt.res == 0: ob.data.materials.clear(); ob.data.materials.append(mt.m); continue
        if not ob.data.uv_layers: smart_uv(ob, .01)
        imgs = {}
        for kind in ('color', 'rough', 'normal'):
            if kind == 'rough' and not mt.bsdf.inputs['Roughness'].links: continue
            r = mt.res if kind != 'rough' else max(128, mt.res // 2)
            img = bpy.data.images.new(f'{ob.name}_{kind}', r, r, alpha=False)
            img.colorspace_settings.name = 'sRGB' if kind == 'color' else 'Non-Color'; imgs[kind] = img
        m = mt.m.copy(); m.name = f'{mt.m.name}_{ob.name}'; ob.data.materials.clear(); ob.data.materials.append(m)
        nt = m.node_tree; N = nt.nodes; Lk = nt.links; bsdf = N['Principled BSDF']; outn = N['Material Output']
        tex = N.new('ShaderNodeTexImage'); H.activate(ob)
        for kind, img in imgs.items():
            tex.image = img; N.active = tex
            if kind == 'normal':
                Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface']); bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
            else:
                src = bsdf.inputs['Base Color' if kind == 'color' else 'Roughness']; em = N.new('ShaderNodeEmission')
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
            else:
                nm = N.new('ShaderNodeNormalMap'); Lk.new(t.outputs['Color'], nm.inputs['Color']); Lk.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        print('baked', ob.name, list(imgs))


# ── Moves ───────────────────────────────────────────────────────────────────
class Poser:
    """Poses the skeleton by turns and by aiming bones at armature-space targets, solving each
    bone from its parent's posed frame, and keys plain local rotations (nothing to evaluate at
    export, so the browser plays what Blender shows)."""
    def __init__(self, rig):
        self.rig = rig; bs = rig.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in bs}
        self.par = {b.name: (b.parent.name if b.parent else None) for b in bs}
        self.rel = {n: (self.rest[p].inverted() @ self.rest[n] if p else self.rest[n].copy()) for n, p in self.par.items()}
        self.prev = {}; self.clear()
    def clear(self):
        self.q = {n: Quaternion() for n in self.rest}; self.loc = {n: V((0, 0, 0)) for n in self.rest}; self.M = {}
    def base(self, n):
        p = self.par[n]; return (self.mat(p) if p else Matrix.Identity(4)) @ self.rel[n] @ Matrix.Translation(self.loc[n])
    def mat(self, n):
        if n not in self.M: self.M[n] = self.base(n) @ self.q[n].to_matrix().to_4x4()
        return self.M[n]
    def skin(self, n): return self.mat(n) @ self.rest[n].inverted()
    def bend(self, n, axis, ang):
        """Turn bone n by ang about an axis given in the rest pose, carried by its parent."""
        if ang: self.q[n] = self.q[n] @ Quaternion((self.rest[n].to_3x3().inverted() @ V(axis)).normalized(), ang); self.M = {}
    def aim(self, n, d):
        """Point bone n along d (armature space) with the least turn from where its parent carries it."""
        B = self.base(n).to_3x3(); R = B.col[1].rotation_difference(d.normalized()).to_matrix()
        self.q[n] = (B.inverted() @ R @ B).to_quaternion(); self.M = {}
    def place(self, R=None, t=(0, 0, 0), pivot=V((0, 0, 0))):
        """Move the whole scorpion: turn it by R (3x3, armature space) about pivot, then shift by t."""
        R = R or Matrix.Identity(3); R0 = self.rest['root'].to_3x3()
        self.q['root'] = (R0.inverted() @ R @ R0).to_quaternion(); self.loc['root'] = R0.inverted() @ (pivot - R @ pivot + V(t)); self.M = {}
    def key(self, f):
        for pb in self.rig.pose.bones:
            q = self.q[pb.name].copy()
            if pb.name in self.prev and q.dot(self.prev[pb.name]) < 0: q.negate()
            self.prev[pb.name] = q; pb.rotation_quaternion = q; pb.location = self.loc[pb.name]
            pb.keyframe_insert('rotation_quaternion', frame=f); pb.keyframe_insert('location', frame=f)

LEG_REST, PALP_REST, SAMPLES = {}, {}, {}
G1 = {(1, 'L'), (2, 'R'), (3, 'L'), (4, 'R')}   # the two alternating tetrapods

def place_leg(po, k, s, foot, tilt=0.0, curl=0.0):
    """Leg k on side s with its foot at an armature-space point: the leg turned about its coxa
    towards it, the tarsus kept at its slope (its tip lifted by tilt), the knee bent up and out
    as at rest. curl folds it under the body instead, as a dead scorpion's legs."""
    C, K, A, F = LEG_REST[k, s]; lf, lt = (K - C).length, (A - K).length
    Mb = po.skin('prosoma'); fb = Mb.inverted() @ foot
    h0, h1 = (F - C).to_2d(), (fb - C).to_2d()
    Rz = Matrix.Rotation(math.atan2(h0.cross(h1), h0.dot(h1)), 3, 'Z')
    nh = (Rz @ (K - C)).cross(Rz @ (A - K)).normalized()
    tv = Matrix.Rotation(tilt, 3, nh) @ (Rz @ (A - F)); Ab = fb + tv
    Kb = H.two_bone(C, Ab, lf, lt, Rz @ (K - (C + A) / 2))
    if curl:   # fold the femur down to the belly, the tibia back along it and the tarsus in
        n0 = (K - C).cross(A - K).normalized()
        Kc = C + Matrix.Rotation(.9 * curl, 3, n0) @ (K - C)
        Ac = Kc + Matrix.Rotation(2.5 * curl, 3, n0) @ (A - K)
        Fc = Ac + Matrix.Rotation(3.3 * curl, 3, n0) @ (F - A)
        Kb, Ab, fb = Kc, Ac, Fc
    R3 = Mb.to_3x3()
    po.aim(f'femur{k}.{s}', R3 @ (Kb - C)); po.aim(f'tibia{k}.{s}', R3 @ (Ab - Kb)); po.aim(f'tarsus{k}.{s}', R3 @ (fb - Ab))

def place_palp(po, s, dw=(0, 0, 0), turn=(0, 0, 0), open_=0.0):
    """The pedipalp on side s: its wrist moved by dw (px: forward, out, up in the body's rest
    frame), the hand turned by (yaw out, pitch up, roll) and the movable finger opened by open_."""
    sx = 1 if s == 'L' else -1; Cp, E0, W0, H1, ax = PALP_REST[s]
    W = W0 + V((dw[1] * sx, -dw[0], dw[2])) * S
    E = H.two_bone(Cp, W, (E0 - Cp).length, (W0 - E0).length, E0 - (Cp + W0) / 2)
    Mb = po.skin('prosoma'); R3 = Mb.to_3x3()
    po.aim(f'palp_fem.{s}', R3 @ (E - Cp)); po.aim(f'palp_pat.{s}', R3 @ (W - E))
    hd = Matrix.Rotation(turn[0] * sx, 3, 'Z') @ Matrix.Rotation(turn[1], 3, V((1, 0, 0))) @ (H1 - W0)
    po.aim(f'chela.{s}', R3 @ hd)
    if turn[2]: po.bend(f'chela.{s}', (H1 - W0), turn[2] * sx)
    po.bend(f'finger.{s}', ax, open_)

def plant(po, offsets=None):
    for k in LEGS:
        for s, sx in SIDES:
            off = (offsets or {}).get((k, s), (V((0, 0, 0)), 0.0))
            place_leg(po, k, s, LEG_REST[k, s][3] + off[0], off[1])

def tail(po, angles, sway=None):
    """Bend the tail: angles at the six joints (to segments 1-5 and the telson) about the
    side axis (positive curls it forward over the back), sway a sideways bend per joint."""
    names = [f'tail{i + 1}' for i in range(5)] + ['telson']
    for i, n in enumerate(names):
        po.bend(n, (1, 0, 0), angles[i])
        if sway: po.bend(n, dorsal((po.rest[n].col[1].xyz).normalized()), sway[i])

def lowest(po):
    """The lowest point of the posed scorpion, from a sample of each bone's vertices."""
    return min((po.skin(b) @ p).z for b, pts in SAMPLES.items() for p in pts)

def tail_chain():
    """The tail in its midline plane as (y, z) points: the six joints and the sting's tip."""
    pts = [(p.y, p.z) for p in TJ]
    tip = REST_STING_TIP; pts.append((tip.y, tip.z)); return np.array(pts)

def chain_fk(pts, ang):
    pts = pts.copy()
    for i, a in enumerate(ang):
        c, s_ = math.cos(a), math.sin(a); p = pts[i].copy(); d = pts[i + 1:] - p
        pts[i + 1:] = p + np.stack([d[:, 0] * c - d[:, 1] * s_, d[:, 0] * s_ + d[:, 1] * c], 1)
    return pts

def solve_strike(target, aim_dir):
    """Joint angles that bring the sting's tip to target (y, z), stabbing along aim_dir, with
    the bend spread evenly along the tail and the arch kept clear above the body."""
    base = tail_chain(); rng = np.random.default_rng(3)
    def cost(a):
        p = chain_fk(base, a); tip = p[-1]; d = p[-1] - p[-2]; d = d / (np.linalg.norm(d) + 1e-9)
        c = 30 * np.sum((tip - target) ** 2) + .02 * np.sum(np.diff(a[:5]) ** 2) + .05 * (1 - d.dot(aim_dir))
        for q in p[1:6]:   # the arch passes high over the back and the carapace
            if -.4 < q[0] < .4: c += 20 * max(0, .66 - q[1]) ** 2
        return c
    best = np.array([.6, .1, -.1, -.3, -.4, -1.2]); bc = cost(best); step = .3
    for it in range(4000):
        cand = best + rng.normal(0, step, 6); cc = cost(cand)
        if cc < bc: best, bc = cand, cc
        if it % 400 == 399: step *= .6
    print('sting misses its mark by', round(float(np.linalg.norm(chain_fk(base, best)[-1] - target)) * 1000), 'mm')
    return best

def actions(rig):
    po = Poser(rig); A = []
    for s, sx in SIDES:
        for k in LEGS: LEG_REST[k, s] = leg_pts(k, sx)
        p = palp_pts(sx); mv = finger_pts(sx, MOVABLE); o, f, out, up = hand_frame(sx)
        d = (mv[-1] - mv[0]).normalized(); PALP_REST[s] = (p['C'], p['E'], p['W'], p['H1'], d.cross(-up).normalized())
    def clip(name, length, fn, step=1):
        rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
        po.prev = {}
        for fr in sorted(set(range(1, length + 1, step)) | {length}): po.clear(); fn(fr); po.key(fr)
        A.append(act)
    X = (1, 0, 0)
    def idle(f):
        w = 2 * math.pi * (f - 1) / 96
        po.place(Matrix.Rotation(.008 * math.sin(w + .6), 3, 'Y') @ Matrix.Rotation(.006 * math.sin(w), 3, 'X'), (0, 0, .004 * math.sin(2 * w)),
                 P(260, 0, 140))
        po.bend('meso1', X, -.006 * math.sin(2 * w)); po.bend('meso2', X, -.008 * math.sin(2 * w + .5))
        tail(po, [.025 * math.sin(w - .5 * i) for i in range(5)] + [.06 * math.sin(2 * w + 1)],
             [.035 * math.sin(w * 1 + .9 - .45 * i) for i in range(5)] + [0])
        snap = lambda c: math.exp(-((f - c) / 2.2) ** 2)   # the pincers twitch shut now and then
        for s, ph in (('L', 0), ('R', 1.9)):
            place_palp(po, s, (2.5 * math.sin(w + ph), 1.5 * math.sin(2 * w + ph), 1.5 * math.sin(w * 2 + ph + 1)), (.03 * math.sin(w + ph), .04 * math.sin(2 * w + ph), 0),
                       .06 * math.sin(3 * w + ph) - .3 * (snap(30 if s == 'L' else 52) + snap(74 if s == 'L' else 84)))
        plant(po)
    clip('Idle', 96, idle, 2)
    DUTY, STRIDE = .62, .19
    def walk(f):
        t = (f - 1) / 32; w = 2 * math.pi * t
        po.place(Matrix.Rotation(.02 * math.sin(2 * w), 3, 'Z'), (0, 0, 0), P(300, 0, 0))
        tail(po, [.02 * math.sin(2 * w - .4 * i) for i in range(5)] + [.05 * math.sin(2 * w)], [.04 * math.sin(w - .5 * i) for i in range(5)] + [0])
        for s, ph in (('L', 0), ('R', math.pi)):
            place_palp(po, s, (3 * math.sin(w + ph), 0, 3 + 2 * math.sin(2 * w)), (0, .05, 0), .04 * math.sin(2 * w + ph))
        offs = {}
        for k in LEGS:
            for s, sx in SIDES:
                ph = (t + (0 if (k, s) in G1 else .5) + .04 * k) % 1
                if ph < DUTY: dy = -STRIDE / 2 + STRIDE * ph / DUTY; lift = tilt = 0.0
                else:
                    u = (ph - DUTY) / (1 - DUTY); dy = STRIDE / 2 - STRIDE * smooth(0, 1, u)
                    lift = .055 * math.sin(math.pi * u); tilt = .45 * math.sin(math.pi * u)
                offs[k, s] = (V((0, dy, lift)), tilt)
        plant(po, offs)
    clip('Walk', 32, walk)
    ang_strike = solve_strike(np.array([P(545, 0, 185).y, P(545, 0, 185).z]), np.array([-.75, -.66]))
    print('strike angles', [round(float(a), 3) for a in ang_strike])
    ang_wind = [-.3, -.12, .08, .12, .16, .45]
    def strike(f):
        a = smooth(1, 10, f); b = smooth(10, 15, f); r = smooth(21, 40, f)
        jab = .05 * smooth(15, 17, f) * (1 - smooth(17, 21, f))
        ang = [(ang_wind[i] * a * (1 - b) + ang_strike[i] * b) * (1 - r) for i in range(6)]
        ang[0] += jab; ang[5] -= jab * 2
        lunge = b * (1 - r)
        po.place(Matrix.Rotation(.06 * lunge - .03 * a * (1 - b), 3, 'X'), (0, -.05 * lunge, -.012 * a * (1 - b) - .015 * lunge), P(300, 0, 0))
        tail(po, ang)
        for s in ('L', 'R'):
            place_palp(po, s, (6 * lunge - 4 * a * (1 - b), 8 * a * (1 - r), 4 * a * (1 - r)), (.12 * a * (1 - r), .1 * a * (1 - r), 0), .35 * a * (1 - r))
        plant(po)
    clip('Strike', 40, strike)
    def pinch(f):
        a = smooth(1, 8, f); b = smooth(8, 13, f); c = smooth(12.5, 15, f); r = smooth(20, 32, f)
        reach = b * (1 - r); tug = .5 * math.sin(math.pi * smooth(15, 20, f)) * (1 - r)
        po.place(Matrix.Rotation(.035 * reach - .02 * a * (1 - b), 3, 'X'), (0, -.045 * reach + .015 * tug, -.01 * a * (1 - b)), P(300, 0, 0))
        tail(po, [-.06 * a * (1 - r), .03 * a * (1 - r), .04 * a * (1 - r), .03 * a * (1 - r), .02 * a * (1 - r), .1 * a * (1 - r)])
        for s in ('L', 'R'):
            place_palp(po, s, (-8 * a * (1 - b) + 34 * reach - 6 * tug, 8 * a * (1 - b) - 14 * reach, 4 * a * (1 - b) + 2 * reach),
                       (-.18 * reach, -.06 * reach, 0), .4 * a * (1 - c) - .5 * c * (1 - r))
        plant(po)
    clip('Pinch', 32, pinch)
    def hit(f):
        e = smooth(1, 4, f) * (1 - smooth(6, 20, f))
        po.place(Matrix.Rotation(-.07 * e, 3, 'X') @ Matrix.Rotation(.03 * e, 3, 'Y'), (0, .05 * e, .012 * e), P(300, 0, 0))
        tail(po, [-.09 * e, -.05 * e, .04 * e, .06 * e, .06 * e, .25 * e], [.06 * e] * 5 + [0])
        for s in ('L', 'R'): place_palp(po, s, (-12 * e, -4 * e, 6 * e), (0, .15 * e, 0), .25 * e)
        plant(po)
    clip('Hit', 20, hit)
    ang_dead = [-1.6, -.62, -.52, -.5, -.4, -1.4]
    def death(f):
        jerk = math.sin(math.pi * smooth(1, 9, f)); curl = smooth(5, 24, f); roll = smooth(12, 34, f); limp = smooth(6, 26, f)
        R = Matrix.Rotation(math.pi * roll * .98, 3, 'Y') @ Matrix.Rotation(.08 * jerk - .26 * roll, 3, 'X')   # it settles level on its back
        po.place(R, (0, 0, .03 * jerk), P(250, 0, 140))
        tail(po, [ang_dead[i] * limp + (.12 if i < 2 else -.08) * jerk for i in range(6)], [.05 * jerk * (i % 2 * 2 - 1) for i in range(5)] + [0])
        for s in ('L', 'R'): place_palp(po, s, (-30 * curl, -45 * curl, -10 * curl), (.5 * curl, -.3 * curl, 0), .3 * jerk - .3 * limp)
        twitch = .25 * math.exp(-((f - 50) / 2.5) ** 2)
        for k in LEGS:
            for s, sx in SIDES:
                c = min(1.0, curl * (1 + .08 * k)) * (1 - (twitch if (k, s) == (2, 'L') else 0))
                place_leg(po, k, s, LEG_REST[k, s][3] + V((0, 0, .02 * jerk)), 0, c)
        if f > 8:   # it lies where it falls: lowered (or lifted) until it rests on the ground
            z = lowest(po); po.place(R, (0, 0, .03 * jerk - z * smooth(8, 16, f)), P(250, 0, 140))
    clip('Death', 60, death)
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
REST_STING_TIP = None

def geometry():
    """Every mesh of the line, tagged with its bones. Returns {name: (object, material kind)}."""
    global REST_STING_TIP
    parts = {}
    def make(name, fn, kind, uv=False):
        M = Mesh(name, uv); fn(M); parts[name] = (M.finish(), kind)
    make('Body', lambda M: (build_prosoma(M), build_abdomen(M)), 'body')
    make('Tail', build_tail, 'tail')
    make('Legs', build_legs, 'legs')
    make('Palps', build_palps, 'palps')
    make('Membranes', lambda M: (build_pleura(M), build_joints(M)), 'membrane')
    make('Eyes', build_eyes, 'eyes')
    make('Chelicerae', build_chelicerae, 'chelicerae')
    make('Pectines', build_pectines, 'pectines')
    make('L12_Fingers', build_fingers, 'fingers')
    make('L12_Telson', build_telson, 'telson')
    make('L23_Band', build_band, 'gold')
    make('L3_Armour', build_armour, 'armour', uv=True)
    make('L3_Fingers', build_fingers, 'gold')
    make('L3_Telson', lambda M: build_telson(M, 1.04), 'gold')
    tel = parts['L12_Telson'][0]; REST_STING_TIP = max((v.co for v in tel.data.vertices), key=lambda c: (c - TJ[5]).length).copy()
    for name, (ob, kind) in parts.items():   # sample points per bone, for keeping the scorpion on the ground
        if name.startswith(('L2', 'L3')): continue
        gi = {g.index: g.name for g in ob.vertex_groups}
        for v in list(ob.data.vertices)[::23]:
            if len(v.groups) == 1: SAMPLES.setdefault(gi[v.groups[0].group], []).append(v.co.copy())
    return parts

def materials():
    return {'body': m_chitin('Chitin', 2048), 'tail': m_chitin('TailChitin', 2048, gran=120.0),
            'legs': m_chitin('LegChitin', 1024, gran=140.0), 'palps': m_chitin('PalpChitin', 1024, gran=150.0),
            'fingers': m_chitin('FingerChitin', 512, gran=180.0, granules=.6),
            'telson': m_chitin('Telson', 512, base='#1f0d08', warm='#36140c', edge='#070404', sheen='#2e1610', gran=200.0, gloss=.12, granules=.35),
            'membrane': m_membrane(), 'gold': None,
            'eyes': H.m_flat('Eye', '#050505', .05), 'chelicerae': H.m_flat('Chelicera', '#2a140e', .3), 'pectines': H.m_flat('Pecten', '#4a3322', .5)}

def build():
    parts = geometry(); mats = materials(); items = {}
    for name, (ob, kind) in parts.items():
        if kind == 'armour': ob.data.materials.append(m_armour()); continue
        mt = mats[kind] if kind != 'gold' else m_gold(f'Gold_{name}', 1024 if 'Band' in name else 512)
        items[name] = (ob, mt, kind)
    bake(items)
    for ob, _ in parts.values():
        if 'rim' in ob.data.attributes: ob.data.attributes.remove(ob.data.attributes['rim'])
    rig = HR.build_rig('ScorpionRig', bones())
    for ob, _ in parts.values(): skin(ob, rig)
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.validate(): print('repaired', ob.name)
    return rig, actions(rig)

def renders(rig):
    """A lineup of the three tiers, and each tier from the side, front and back beside its sheet."""
    from PIL import Image
    shots = []
    for t in (1, 2, 3):
        k = TIERS[t]['scale']; rig.scale = (k, k, k)
        p = os.path.join(OUT, f'scorpion_L{t}.png')
        H.render(rig, p, 'Idle', 1, t, cam=((3.3 * k, -4.4 * k, 1.9 * k), (76, 0, 37)), res=(560, 520), samples=24); shots.append(p)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'scorpion_lineup.png'))
    rig.scale = (1, 1, 1)
    for t in (1, 2, 3): compare(rig, t)

VIEWS = {'side': ((310, 390), (90, 0, -90)), 'front': (None, (90, 0, 0)), 'back': (None, (90, 0, 180))}
SHEET_VIEWS = {'side': (310, 390), 'front': (760, 390), 'back': (1155, 390)}

def compare(rig, t, size=540, samples=16):
    """Orthographic side, front and back views of tier t at the sheet's scale, beside the sheet."""
    from PIL import Image
    H.render(rig, os.path.join(OUT, '_warmup.png'), 'Idle', 1, t, res=(32, 32), samples=1)
    cam = bpy.data.objects['Cam']; cam.data.type = 'ORTHO'; cam.data.ortho_scale = size * S
    g = bpy.data.objects.get('Ground'); W = H.SC.world.node_tree.nodes['Background'].inputs['Color']
    W.default_value = (.62, .62, .64, 1); g.hide_render = True
    sheet_im = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'refs', 'scorpion', f'scorpion-{t}.png')).convert('RGB')
    cols = []
    for view, (cx, cz) in SHEET_VIEWS.items():
        zc = (645 - cz) * S
        if view == 'side': cam.location = (-6, (X0 - cx) * S, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
        elif view == 'front': cam.location = (0, -6, zc); cam.rotation_euler = (math.radians(90), 0, 0)
        else: cam.location = (0, 6, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
        p = os.path.join(OUT, f'scorpion_L{t}_{view}.png')
        H.SC.cycles.samples = samples; H.SC.render.resolution_x = H.SC.render.resolution_y = size; H.SC.render.filepath = p
        bpy.ops.render.render(write_still=True)
        ref = sheet_im.crop((cx - size // 2, cz - size // 2, cx + size // 2, cz + size // 2))
        both = Image.new('RGB', (size, size * 2)); both.paste(ref, (0, 0)); both.paste(Image.open(p).convert('RGB'), (0, size)); cols.append(both)
    out = Image.new('RGB', (size * 3, size * 2)); [out.paste(c, (i * size, 0)) for i, c in enumerate(cols)]
    out.save(os.path.join(OUT, f'scorpion_compare_L{t}.png'))
    cam.data.type = 'PERSP'; g.hide_render = False; W.default_value = (.36, .42, .5, 1)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'scorpion.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scorpion.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
