"""Realistic Bennu Firebird line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow numpy):
    python tools/blender/bennu.py third_party/makehuman assets/models [--renders]
(the MakeHuman directory is not used, but the build takes the same arguments as the others).

The Bennu bird of Heliopolis, after the reference sheets in refs/bennu: a giant grey heron
about 2 m tall to the crown, on long legs with heron feet (three toes forward and one behind),
its long neck held in an S on a chain of six bones and its dagger bill's lower mandible on a
bone of its own. The torso is lofted from sections traced from the side view of the sheet and
sized to its front view; the neck is lofted along the sheet's S and fused into it by a voxel
remesh. The wings are layered feather cards: ten primaries, fourteen secondaries and four
tertials with their greater, median and lesser coverts, every pair of flight feathers and
their coverts on a bone of its own, so that each wing folds against the flank in a bird's
Z (humerus back, forearm forward, hand back) and spreads to about 3.5 m. The feathers are thin
cambered meshes mapped into a painted atlas per tier; the body, head and legs are baked from
procedural materials.
  L1 Bennu Firebird          grey plumage, the flight feathers shading to fiery red and orange
                             towards their tips; a crest of two lanceolate feathers
  L2 Veteran Bennu Firebird  slender and blue-grey, a white foreneck streaked black, a black
                             stripe to the nape, two long thin plumes streaming back from the
                             head, dark flight feathers
  L3 Elite Bennu Firebird    grey-blue head and neck, the body and wings glowing ember-red and
                             orange like coals, small flames licking from the tips of the
                             flight feathers, the tail and the crest
One skeleton holds the line. The untagged meshes (legs, lower mandible, eyes) are shared; each
tier has its own body, head and feathers (L1_, L2_, L3_), and L3_Flames are emissive cards.
Moves: Idle, Walk (the heron's stately walk), Fly (hovering on beating wings, the neck drawn in
and the legs trailing), Strike (the bill stabs forward), Cast (wings half-spread, the neck drawn
back and thrust forward as it throws fire), Hit and Death (it sinks onto its legs and topples
onto its side).
"""
import bpy, bmesh, math, os, sys, random, json, struct
import numpy as np
from mathutils import Vector, Matrix, Quaternion
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import horse as HR
import scorpion as SP
from hoplite import srgb, Mat
from hydra import catmull, resample, smooth, skin
from scorpion import sheet, ramp01

OUT = H.OUT
random.seed(31)
TIERS = {1: dict(scale=1.0), 2: dict(scale=1.04), 3: dict(scale=1.08)}


# ── Shape (sheet pixels mapped to metres; the bird faces -Y, its left side at +X) ──
# Traced from the side view of refs/bennu/bennu-1.png, where the bird faces right: X runs forward
# along the sheet and y down it, with the ground line at y = 695; the 553 px from the ground to
# the crown are 2 m. Half-widths (lat) come from the front view.
S = 2.0 / 553
X0, Y0 = 231, 695            # under the feet
SIDES = (('L', 1), ('R', -1))
SIDE, UP, FWD = V((1, 0, 0)), V((0, 0, 1)), V((0, -1, 0))

def P(X, lat=0.0, y=Y0): return V((lat * S, (X0 - X) * S, (Y0 - y) * S))

# The torso under the plumage: vertical sections (X, half-width, top y, bottom y), from the rump
# to the breast.
TORSO = [(140, 4, 410, 424), (150, 11, 398, 432), (165, 19, 383, 438), (185, 25, 366, 446), (205, 30, 350, 452),
         (230, 35, 335, 456), (255, 37, 321, 456), (280, 38, 309, 452), (305, 38, 300, 444), (330, 36, 296, 428),
         (350, 33, 299, 404), (362, 27, 306, 384), (370, 18, 316, 366), (374, 7, 330, 350)]
# The neck's midline (X, y) from inside the torso to inside the head, and its half-width, front
# and back half-depth there (px), the lower neck thick with plumes.
NECK = [(322, 352), (338, 322), (347, 296), (346, 270), (338, 246), (326, 222), (317, 198), (314, 178), (318, 162)]
NECK_R = [(22, 25, 22), (19, 24, 20), (16, 21, 16), (14, 17.5, 14), (12.5, 14, 12), (11, 12, 11), (10.5, 11, 10.5),
          (11, 11, 11), (10, 10, 10)]
# The head and upper mandible, and the lower mandible: sections (X, half-width, top y, bottom y,
# roundness of the top and of the bottom); the bill has a ridged culmen and flat cutting edges.
HEAD = [(298, 3, 158, 166, 2.2, 2.2), (302, 9, 150, 175, 2.2, 2.2), (308, 13, 145, 180, 2.3, 2.2), (318, 15, 142.5, 181, 2.4, 2.2),
        (330, 15.5, 142, 180, 2.4, 2.2), (342, 15, 143.5, 178, 2.4, 2.2), (352, 13.5, 146.5, 176, 2.3, 2.3),
        (360, 11.5, 150, 174, 2.2, 2.4), (367, 9.5, 154, 172, 2.0, 2.8), (373, 8, 157.5, 170, 1.9, 3.0), (382, 6.8, 159.5, 170.5, 1.8, 3.0),
        (395, 5.8, 162, 172, 1.8, 3.0), (408, 5, 165, 173.5, 1.8, 3.0), (420, 4, 168, 175.5, 1.8, 3.0), (431, 3, 171.5, 177.5, 1.8, 3.0),
        (440, 2, 175, 179.5, 1.8, 3.0), (446, 1.2, 177.8, 180.8, 1.8, 3.0), (450, .5, 180, 181.6, 1.8, 3.0), (452, .15, 181, 182, 2, 2)]
MANDIBLE = [(350, 3, 171, 176, 2.6, 2.2), (356, 6.5, 169.5, 178, 3.0, 2.0), (366, 7.5, 169.5, 178.5, 3.0, 1.9), (376, 6.8, 170.2, 178.6, 3.0, 1.9),
            (390, 5.8, 171.4, 179.2, 3.0, 1.9), (405, 5, 173.2, 180, 3.0, 1.9), (418, 4, 175.4, 181, 3.0, 1.9), (430, 3, 177.8, 182, 3.0, 1.9),
            (440, 2, 179.8, 183, 3.0, 1.9), (447, 1, 181.4, 183.3, 3.0, 1.9), (452, .15, 182.3, 183, 2, 2)]
EYE = (361, 9.2, 157, 4.2)                     # X, lat, y, radius (px)
# The legs (left): hip and knee inside the body, the intertarsal joint, the foot at the base of
# the toes, and the toes' tips: the hind toe, then the inner, middle and outer toes.
LEG = dict(hip=(222, 20, 392), knee=(246, 25, 418), ankle=(212, 28, 552), foot=(231, 28, 689),
           toes=((197, 27, 691.5), (287, 14, 691.5), (302, 27, 691.5), (288, 42, 691.5)))
TAIL0, TAIL1 = P(160, 0, 408), P(55, 0, 478)

TOR = SP.table(TORSO)

def neck_path():
    """The neck's midline, evenly resampled, with arc lengths along it."""
    pts = resample(catmull([P(x, 0, y) for x, y in NECK], 12), 200)
    arc = [0.0]
    for a, b in zip(pts, pts[1:]): arc.append(arc[-1] + (b - a).length)
    return pts, np.array(arc)
NPATH, NARC = neck_path()
_ys = [y for _, y in NECK][::-1]

def neck_r(p):
    """Half-width, front and back half-depth (m) of the neck at a point on its midline."""
    y = Y0 - p.z / S
    return tuple(float(np.interp(y, _ys, [r[j] for r in NECK_R][::-1])) * S for j in range(3))

def path_at(s):
    i = int(np.clip(np.searchsorted(NARC, s) - 1, 0, len(NARC) - 2)); f = (s - NARC[i]) / max(1e-9, NARC[i + 1] - NARC[i])
    return NPATH[i].lerp(NPATH[i + 1], f)

def nearest(p): return int(np.argmin([(q - p).length for q in NPATH]))
NJ_ARC = [NARC[nearest(P(335, 0, 328))] + k * (NARC[nearest(P(315, 0, 178))] - NARC[nearest(P(335, 0, 328))]) / 6 for k in range(7)]
NJ = [path_at(s) for s in NJ_ARC]   # the neck's joints, J0 in the torso to J6 at the head
BILL_BASE, BILL_TIP = P(373, 0, 164), P(452, 0, 181.6)

def leg_pts(sx):
    L = LEG; f = lambda t: P(t[0], sx * t[1], t[2])
    return f(L['hip']), f(L['knee']), f(L['ankle']), f(L['foot']), [f(t) for t in L['toes']]


# ── The wing (spread, in the rest pose) ──────────────────────────────────────
HUM, FORE, HAND = .25, .33, .27
SHOULDER = (320, 36, 318)
PRIM_L = (.53, .57, .61, .66, .71, .76, .80, .82, .82, .77)     # P1 to P10
LIFT = .0014                                                    # the stacking of feather over feather
CURVE = .12                                                     # every feather bends down towards its tip
# The folded wing lies in a plane against the flank (tilted 10 degrees in at the top and 5 degrees
# in towards the tail); its bones and feathers turn into it at these angles below the back.
TILT, TOE = math.radians(10), math.radians(5)
ARM_FOLD = (28, 160, 31)
# Raised as on the sheet's front view (the display of Cast): the humerus up and out, the forearm on
# up to the wrist, the hand hanging, the upper side of the wing turned to the back.
ARM_SHOW = ((.62, -.1, .78), (.7, -.3, .62), (.22, .05, -.97))

def wing_rest(sx):
    """Shoulder, elbow, wrist and the tip of the hand of the spread wing."""
    S0 = P(SHOULDER[0], sx * SHOULDER[1], SHOULDER[2])
    def d(x, y): return V((x * sx, y, 0)).normalized()
    E = S0 + d(1, .10) * HUM; W = E + d(1, -.08) * FORE; T = W + d(1, .06) * HAND
    return S0, E, W, T

_WING = {}
def wing_columns(sx, s):
    """The flight feathers in order from the lowest (P10) to the topmost (the last tertial), as
    columns: each with its root, direction, length and width, its atlas slot, its bone, its span
    position (0 at the body, 1 at the tip) and its rank in the stack."""
    if s in _WING: return _WING[s]
    S0, E, W, T = wing_rest(sx); back = V((0, 1, 0)); cols = []
    def dirn(deg): a = math.radians(deg); return V((math.cos(a) * sx, math.sin(a), 0))
    for i in range(10, 0, -1):          # primaries, fanned from the hand
        k = (i - 1) / 9
        cols.append(dict(root=W.lerp(T, .05 + .9 * k) + back * .012, d=dirn(80 - 66 * k ** .85), L=PRIM_L[i - 1], W=.088 - .01 * k,
                         kind='outer' if i >= 7 else 'remex', slot=f'rem{i - 1}', bone=f'pri{(i + 1) // 2}.{s}', span=.62 + .38 * k, prim=True))
    for j in range(1, 15):              # secondaries along the forearm, S1 at the wrist
        k = (j - 1) / 13
        cols.append(dict(root=W.lerp(E, (j - .5) / 14) + back * .012, d=dirn(82 + 12 * k), L=.5 - .02 * k, W=.09, kind='remex',
                         slot=f'rem{9 + j}', bone=f'sec{(j + 1) // 2}.{s}', span=.6 - .45 * k, prim=False))
    for j in range(1, 5):               # tertials over the elbow
        k = (j - 1) / 3
        cols.append(dict(root=E.lerp(S0, .08 + .45 * k) + back * .015, d=dirn(92 + 6 * k), L=.58 + .03 * k, W=.095, kind='remex',
                         slot=f'rem{23 + j}', bone=f'ter{(j + 1) // 2}.{s}', span=.1 - .08 * k, prim=False, tert=True))
    for r, c in enumerate(cols): c['rank'] = r
    _WING[s] = cols
    return cols

def wing_groups(sx, s):
    """The feather bones: each the mean root and direction of its flight feathers, on its arm bone."""
    out = {}
    for c in wing_columns(sx, s): out.setdefault(c['bone'], []).append(c)
    par = {'pri': f'hand.{s}', 'sec': f'forearm.{s}', 'ter': f'humerus.{s}'}
    return {g: (sum((c['root'] for c in cs), V()) / len(cs), (sum((c['d'] for c in cs), V())).normalized(), par[g[:3]])
            for g, cs in out.items()}

GROUP_FOLD = {'pri': 31, 'sec': (35, 31), 'ter': 30}   # the angle each group lies at below the back when folded

def group_fold_angle(g):
    k = int(g[3]) - 1
    if g.startswith('pri'): return GROUP_FOLD['pri'] + .5 * k
    if g.startswith('sec'): a, b = GROUP_FOLD['sec']; return a + (b - a) * k / 6
    return GROUP_FOLD['ter'] - 2 * k

def wing_specs(sx, s):
    """Every feather of a wing: the flight feathers and, over each, a greater, median and lesser
    covert, stacked by rank so that each lies over the one beyond it."""
    out = []
    for c in wing_columns(sx, s):
        r = c['rank']; d = c['d']
        base = dict(d=d, n=UP, bone=c['bone'], outer=-sx)
        out.append(dict(base, root=c['root'], L=c['L'], W=c['W'], kind=c['kind'], slot=c['slot'], lift=r * LIFT, ov=.36, nv=8,
                        span=c['span'], tip=True))
        g = 'pc' if c['prim'] else 'gc'
        out.append(dict(base, root=c['root'] - d * .007, L=(.3 if c['prim'] else .44) * c['L'], W=c['W'] * .95, kind='covert',
                        slot=f'{g}{r % (3 if c["prim"] else 4)}', lift=(r + 5) * LIFT, ov=.42, nv=5))
        out.append(dict(base, root=c['root'] - d * .03, L=.11 + .01 * (r % 2), W=.07, kind='covert', slot=f'mc{r % 4}', lift=(r + 9) * LIFT, ov=.45, nv=4))
        out.append(dict(base, root=c['root'] - d * .052, L=.075, W=.055, kind='covert', slot=f'lc{r % 4}', lift=(r + 12) * LIFT, ov=.45, nv=4))
    return out

def tail_specs():
    """Twelve tail feathers fanned a little, the middle pair on top."""
    d0 = (TAIL1 - TAIL0).normalized(); n0 = SIDE.cross(d0)
    n0 = n0 if n0.z > 0 else -n0; out = []
    order = sorted(range(12), key=lambda i: -abs(i - 5.5))
    for rank, i in enumerate(order):
        q = (i - 5.5) / 5.5
        d = Matrix.Rotation(math.radians(11) * q, 3, n0) @ d0
        out.append(dict(root=TAIL0 + SIDE * (q * .045) - UP * (.018 * q * q), d=d, n=(n0 + SIDE * (q * .9)).normalized(), L=.42 - .03 * abs(q), W=.075, kind='tail', slot=f'tail{i}',
                        bone='tail', lift=rank * .0016, ov=.5, nv=7, outer=1, tip=True))
    return out

def torso_pt(X, a, off=0.0, slim=1.0):
    """A point on the torso at angle a round section X (0 at the side, pi/2 on top), off metres out."""
    hw, top, bot = TOR(X); zc = (top + bot) / 2; w, h = hw * S * slim, ((zc - top) if math.sin(a) >= 0 else (bot - zc)) * S
    ca, sa = math.cos(a), math.sin(a)
    p = P(X, 0, zc) + SIDE * (math.copysign(abs(ca) ** (2 / 2.3), ca) * w) + UP * (math.copysign(abs(sa) ** (2 / 2.2), sa) * h)
    nrm = (SIDE * (ca / w) + UP * (sa / h)).normalized()
    return p + nrm * off, nrm

def scapular_specs():
    """Long plumes over the back, lying out over the top of the folded wings."""
    out = []
    for s, sx in SIDES:
        for i in range(9):
            X = 316 - 8.5 * i; a = math.pi / 2 - (.28 + .09 * (i % 3)) * sx
            root, nrm = torso_pt(X, a, .022 + .002 * i)
            d = V((sx * .42, math.cos(math.radians(26)), -math.sin(math.radians(26)))).normalized()
            out.append(dict(root=root, d=d, n=V((sx * .45, 0, 1)), L=.3 + .016 * i, W=.06, kind='plume', slot=f'sp{i % 4}', bone='body',
                            lift=.0015 * (8 - i), ov=.5, nv=6, outer=1, curve=.35, tip=True))
    return out

def plume_specs(t):
    """The long plumes that hang from the base of the foreneck over the breast."""
    out = []; Lk = 1.35 if t == 2 else 1.0
    for i in range(12):
        p = path_at(NJ_ARC[1] + .45 * (i % 4) / 3 * (NJ_ARC[3] - NJ_ARC[1]))
        hw, fr, bk = neck_r(p); ang = (-.9 + 1.8 * (i // 4) / 2) + .15 * (i % 2)
        dirf = FWD * math.cos(ang) + SIDE * math.sin(ang)
        root = p + FWD * (fr * .8 * math.cos(ang)) + SIDE * (hw * .85 * math.sin(ang))
        d = (V((0, 0, -1)) + dirf * .3).normalized()
        out.append(dict(root=root, d=d, n=dirf, L=(.2 + .03 * (i % 3)) * Lk, W=.032, kind='plume', slot=f'bp{i % 4}',
                        bone='neck2', lift=.004 * (3 - i % 4), ov=.5, nv=6, outer=1, curve=-.25, tip=True))
    return out

def crest_specs(t):
    """L1 and L3: two lanceolate crest feathers rising in a V from the back of the crown, with a
    dark tuft at the nape (L1) or two thin plumes that end in flames (L3); L2: two long thin plumes
    streaming back from the nape."""
    out = []
    for s, sx in SIDES:
        if t in (1, 3):
            root = P(318, sx * 3, 146); tipp = P(266 if t == 1 else 262, sx * 16, 86 if t == 1 else 80)
            d = (tipp - root).normalized(); n = SIDE.cross(d); n = n if n.y < 0 else -n
            out.append(dict(root=root, d=d, n=(n + SIDE * sx * .35).normalized(), L=(tipp - root).length, W=.048, kind='crest', slot='cr0',
                            bone='crest', lift=0, ov=.5, nv=9, outer=1, curve=.4, tip=True, flame=t == 3))
        if t == 1:
            for k in range(3):
                out.append(dict(root=P(304, sx * (1 + 2 * k), 163 + 2 * k), d=V((sx * .15, 1, -.25)).normalized(), n=V((sx, 0, .4)), L=.11 - .015 * k,
                                W=.018, kind='plume', slot='tuft0', bone='crest', lift=0, ov=.5, nv=5, outer=1, curve=.5))
        if t == 2:
            out.append(dict(root=P(306, sx * 3, 150), d=V((sx * .12, .97, .03)).normalized(), n=V((sx * .8, 0, .6)), L=.5, W=.012, kind='ribbon',
                            slot='rib0', bone='crest', lift=0, ov=.5, nv=14, outer=1, curve=.9, bend=V((0, 0, -1)), tip=True))
        if t == 3:
            out.append(dict(root=P(312, sx * 2, 141), d=V((sx * .1, .72, .69)).normalized(), n=V((sx, 0, 0)), L=.29, W=.011, kind='ribbon',
                            slot='rib0', bone='crest', lift=0, ov=.5, nv=10, outer=1, curve=.5, bend=V((0, 1, 0)), tip=True, flame=True))
    return out

def feather_specs(t):
    out = []
    for s, sx in SIDES: out += wing_specs(sx, s)
    return out + tail_specs() + scapular_specs() + plume_specs(t) + crest_specs(t)


# ── Mesh building ───────────────────────────────────────────────────────────
def bones():
    B = [('root', V((0, 0, 0)), V((0, -.3, 0)), None, False),
         ('body', P(220, 0, 392), P(335, 0, 338), 'root', True),
         ('tail', TAIL0, TAIL0.lerp(TAIL1, .6), 'body', True)]
    prev = 'body'
    for i in range(6): B.append((f'neck{i + 1}', NJ[i], NJ[i + 1], prev, True)); prev = f'neck{i + 1}'
    B += [('head', NJ[6], BILL_BASE, 'neck6', True), ('jaw', P(354, 0, 172), BILL_TIP + V((0, 0, -.005)), 'head', True),
          ('crest', P(318, 0, 146), P(292, 0, 118), 'head', True)]
    for s, sx in SIDES:
        Hp, K, A, F, tips = leg_pts(sx)
        B += [(f'thigh.{s}', Hp, K, 'body', True), (f'shank.{s}', K, A, f'thigh.{s}', True), (f'tarsus.{s}', A, F, f'shank.{s}', True)]
        B += [(f'toe{i + 1}.{s}', F, tp, f'tarsus.{s}', True) for i, tp in enumerate(tips)]
        S0, E, W, T = wing_rest(sx)
        B += [(f'humerus.{s}', S0, E, 'body', True), (f'forearm.{s}', E, W, f'humerus.{s}', True), (f'hand.{s}', W, T, f'forearm.{s}', True)]
        B += [(g, h, h + d * .2, par, True) for g, (h, d, par) in wing_groups(sx, s).items()]
    return B
BONE_NAMES = [b[0] for b in bones()]
SP.BONE_NAMES = BONE_NAMES   # scorpion's Mesh tags vertices by name from this list
Mesh = SP.Mesh

def oval(c, side, up, w, top, bot, K, nt=2.2, nb=2.2):
    """K points round a section centred at c: a superellipse of half-width w, top above and bot
    below (m); nt and nb set how round its upper and lower halves are."""
    pts = []
    for q in range(K):
        a = 2 * math.pi * q / K; ca, sa = math.cos(a), math.sin(a); n = nt if sa >= 0 else nb
        pts.append(c + side * (math.copysign(abs(ca) ** (2 / n), ca) * w) + up * (math.copysign(abs(sa) ** (2 / n), sa) * (top if sa >= 0 else bot)))
    return pts

def ball(M, c, r, seg=(14, 9)):
    bmesh.ops.create_uvsphere(M.bm, u_segments=seg[0], v_segments=seg[1], radius=r, matrix=Matrix.Translation(c))

def build_torso(M, slim):
    Xs = list(np.linspace(140, 374, 56)); rows = []
    for X in Xs:
        hw, top, bot = TOR(X); zc = (top + bot) / 2
        rows.append(oval(P(X, 0, zc), SIDE, UP, hw * S * slim, (zc - top) * S, (bot - zc) * S, 40, 2.3, 2.1))
    sheet(M, rows, caps=(True, True))

def build_neck(M, slim):
    rows = []
    for i in range(0, len(NPATH), 2):
        p = NPATH[i]; t = (NPATH[min(i + 1, len(NPATH) - 1)] - NPATH[max(i - 1, 0)]).normalized()
        up = t.cross(SIDE).normalized(); hw, fr, bk = neck_r(p)   # up: the back of the neck
        rows.append(oval(p, SIDE, up, hw * slim, bk * slim, fr * slim, 32))
    sheet(M, rows, caps=(True, True))

def build_body(t):
    """The torso and neck as one surface: lofted, fused by a voxel remesh, smoothed, and skinned
    to the body and the neck chain by where each vertex lies along the neck."""
    slim = .94 if t == 2 else 1.0
    M = Mesh(f'L{t}_Body'); build_torso(M, slim); build_neck(M, slim); M.tag('body'); ob = M.finish()
    H.mod(ob, 'REMESH', mode='VOXEL', voxel_size=.0085); H.mod(ob, 'SMOOTH', factor=.6, iterations=5); H.bake_mods(ob)
    ob.data.shade_smooth()
    for g in list(ob.vertex_groups): ob.vertex_groups.remove(g)
    weight_body(ob)
    return ob

def weight_body(ob):
    """Weights along the neck: each vertex follows the bone of the stretch of the neck nearest it,
    blended across the joints; vertices far from the neck's midline stay on the body. Also writes
    the attributes the plumage is painted by (neck, its front, and the back of the torso)."""
    me = ob.data; n = len(me.vertices); co = np.empty(n * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    path = np.array([tuple(p) for p in NPATH]); d2 = ((co[:, None, :] - path[None]) ** 2).sum(-1)
    idx = d2.argmin(1); r = np.sqrt(d2[np.arange(n), idx]); s = NARC[idx]
    rr = np.array([neck_r(NPATH[i])[0] for i in range(len(NPATH))])[idx]
    sm = lambda a, b, x: (lambda u: u * u * (3 - 2 * u))(np.clip((x - a) / (b - a), 0, 1))
    after = [sm(NJ_ARC[j] - .3 * (NJ_ARC[1] - NJ_ARC[0]), NJ_ARC[j] + .3 * (NJ_ARC[1] - NJ_ARC[0]), s) for j in range(7)]
    W = np.zeros((n, 8)); W[:, 0] = 1 - after[0]
    for k in range(1, 7): W[:, k] = after[k - 1] - after[k]
    W[:, 7] = after[6]
    g = sm(2.4 * rr, 1.6 * rr, r); W = W * g[:, None]; W[:, 0] += 1 - g
    names = ['body'] + [f'neck{i + 1}' for i in range(6)] + ['head']
    groups = [ob.vertex_groups.new(name=nm) for nm in names]
    for vi in range(n):
        for k in np.nonzero(W[vi] > .002)[0]: groups[k].add([vi], float(W[vi, k]), 'REPLACE')
    T = np.array([tuple((NPATH[min(i + 1, len(NPATH) - 1)] - NPATH[max(i - 1, 0)]).normalized()) for i in range(len(NPATH))])
    front = np.cross(np.array([1.0, 0, 0])[None], T)[idx]
    rel = co - path[idx]; fr = (rel * front).sum(1) / np.maximum(r, 1e-6)
    X = X0 - co[:, 1] / S; tb = np.array([TOR(x) for x in np.clip(X, 140, 374)]); zc = (tb[:, 1] + tb[:, 2]) / 2
    dors = sm(-.1, .8, (co[:, 2] - (Y0 - zc) * S) / np.maximum((tb[:, 2] - tb[:, 1]) / 2 * S, .01))
    for nm, arr in (('neck', 1 - W[:, 0]), ('fore', sm(.15, .65, fr) * (1 - W[:, 0])), ('dors', dors * W[:, 0])):
        a = me.attributes.new(nm, 'FLOAT', 'POINT'); a.data.foreach_set('value', arr.astype(np.float32))

def set_attrs(ob, fn):
    """Per-vertex float attributes from fn(sheet X, sheet y, lat px) -> {name: value}."""
    me = ob.data; vals = {}
    for i, v in enumerate(me.vertices):
        for k, x in fn(X0 - v.co.y / S, Y0 - v.co.z / S, v.co.x / S).items(): vals.setdefault(k, np.zeros(len(me.vertices), np.float32))[i] = x
    for k, arr in vals.items(): a = me.attributes.new(k, 'FLOAT', 'POINT'); a.data.foreach_set('value', arr)

def loft(M, rows_tab, X1, X2, n, K=36, sigma=1.0):
    tab = SP.table(rows_tab, sigma); rows = []
    for X in np.linspace(X1, X2, n):
        hw, top, bot, nt, nb = tab(X); zc = (top + bot) / 2
        rows.append(oval(P(X, 0, zc), SIDE, UP, max(hw, .08) * S, max(zc - top, .08) * S, max(bot - zc, .08) * S, K, nt, nb))
    sheet(M, rows, caps=(True, True))

def head_attrs(t):
    def fn(X, y, lat):
        bill = ramp01(368, 376, X)
        lore = (1 - bill) * ramp01(352, 364, X) * ramp01(150, 156, y) * ramp01(172, 165, y) * ramp01(9, 12.5, abs(lat))
        stripe = ramp01(357, 349, X) * ramp01(143, 147, y) * ramp01(156, 151, y) * ramp01(5, 9, abs(lat)) * (0 if t == 3 else 1)
        cap = ramp01(150, 144, y) * ramp01(360, 330, X) * (1 if t == 2 else .5)
        face = (1 - bill) * ramp01(158, 166, y) * ramp01(318, 336, X)
        return dict(bill=bill, lore=lore, stripe=max(stripe, cap), face=face, culmen=bill * ramp01(166, 160, y - (X - 373) * .21))
    return fn

def build_head(t):
    M = Mesh(f'L{t}_Head'); loft(M, HEAD, 298, 452, 64); M.tag('head'); ob = M.finish(); set_attrs(ob, head_attrs(t)); return ob

def build_jaw():
    M = Mesh('Jaw'); loft(M, MANDIBLE, 350, 452, 40, 24); M.tag('jaw'); return M.finish()

def build_eyes(M, pupil=False):
    X, lat, y, r = EYE
    for s, sx in SIDES:
        if pupil: ball(M, P(X + .4, sx * (lat + r * .62), y), r * .48 * S, (12, 8))
        else: ball(M, P(X, sx * lat, y), r * S, (16, 10))
    M.tag('head')

def tube_m(M, a, b, side, prof, K=12, flat=1.0):
    """A straight round segment from a to b with radius profile prof [(t, r m)]."""
    d = (b - a).normalized(); sd = (side - d * side.dot(d)).normalized(); up = d.cross(sd)
    rows = [oval(a + (b - a) * t, sd, up, r, r * flat, r * flat, K) for t, r in prof]
    sheet(M, rows, caps=(True, True))

def build_legs(M):
    """Shank (feathered at the top), the scaled tarsus, the foot and four toes with claws, every
    part on its own bone and a ball at each joint bending between them."""
    for s, sx in SIDES:
        Hp, K, A, F, tips = leg_pts(sx)
        tube_m(M, K, A, SIDE, [(-.05, .012), (0, .03), (.15, .03), (.35, .02), (.55, .0145), (.9, .0135), (1.0, .015), (1.04, .01)], 14)
        M.tag(f'shank.{s}')
        ball(M, A, .018); M.tag(f'shank.{s}', f'tarsus.{s}', lambda co, A=A, F=F: smooth(-.016, .016, (co - A).dot((F - A).normalized())))
        tube_m(M, A, F, SIDE, [(-.03, .01), (0, .015), (.1, .0135), (.5, .0125), (.9, .0135), (1.0, .015), (1.04, .01)], 14, .9)
        ball(M, F + V((0, 0, -.004)), .02, (12, 8)); M.tag(f'tarsus.{s}')
        for i, tp in enumerate(tips):
            d = (tp - F).normalized(); L = (tp - F).length; side = d.cross(UP).normalized()
            tube_m(M, F, tp, side, [(0, .012), (.2, .0095), (.35, .0105), (.55, .0085), (.7, .0092), (.9, .006), (1.0, .0045), (1.03, .002)], 10, .8)
            claw(M, tp - d * .004, d, .028 if i else .032, .0042)
            M.tag(f'toe{i + 1}.{s}')

def claw(M, base, d, length, r0):
    rows = []; p = base.copy(); dd = d.normalized(); n = 6
    for i in range(n + 1):
        t = i / n; r = r0 * (1 - t) + .0003; sd = dd.cross(UP).normalized(); up = sd.cross(dd)
        rows.append([p + (sd * math.cos(2 * math.pi * q / 8) + up * math.sin(2 * math.pi * q / 8)) * r for q in range(8)])
        dd = (dd - UP * (.9 / n)).normalized(); p = p + dd * (length / n)
    sheet(M, rows, caps=(True, True))

def leg_attrs(X, y, lat):
    return dict(feath=ramp01(458, 445, y), claw=0.0)


# ── Feather cards ───────────────────────────────────────────────────────────
US = (0, .25, .5, .75, 1)

def shape(kind, v):
    """The half-width of a feather along its length, as a fraction of its widest."""
    if kind in ('remex', 'outer', 'tail'):
        w = .55 + .45 * smooth(0, .15, v)
        if v > .78: w *= .2 + .8 * math.sqrt(max(0.0, 1 - ((v - .78) / .22) ** 2))
        if kind == 'outer': w *= 1 - .38 * smooth(.42, .62, v)
        return max(w, .05)
    if kind == 'covert':
        w = .62 + .38 * smooth(0, .4, v)
        return max(.06, w * (.15 + .85 * math.sqrt(max(0.0, 1 - ((v - .5) / .5) ** 2))) if v > .5 else w)
    if kind == 'plume': return max(.05, math.sin(math.pi * min(1.0, .1 + .9 * v ** .8)) ** .7)
    if kind == 'crest': return max(.05, math.sin(math.pi * min(1.0, .05 + .95 * v ** 1.25)) ** .8)
    return 1.0 if v < .85 else max(.1, (1 - v) / .15)   # ribbon

def card(M, f):
    """A feather as a thin cambered surface: rows from root to tip, five points across from its
    outer edge over the rachis to its inner edge, bending down along its length."""
    d = f['d'].normalized(); n = (f['n'] - d * f['n'].dot(d)).normalized(); s = n.cross(d); o = s * f.get('outer', 1)
    nv = f.get('nv', 6); ov = f.get('ov', .5); cam = f.get('camber', .015); k = f.get('curve', CURVE); bend = f.get('bend', -n)
    rows = []
    for j in range(nv + 1):
        v = j / nv; hw = shape(f['kind'], v) * f['W'] / 2; dist = v * f['L']
        c = f['root'] + d * dist + n * f.get('lift', 0) + bend * (k * dist * dist)
        rows.append([c - o * ((2 * u - 1) * 2 * hw * (ov if u < .5 else 1 - ov)) - n * (cam * 2 * hw * (2 * u - 1) ** 2) for u in US])
    sheet(M, rows, closed=False, uv=lambda i, kk, face: slot_uv(f['slot'], US[min(kk, 4)], i / nv))
    M.tag(f['bone'])
    return rows

def build_patagia(M):
    """The leading edge of each wing over its arm bones, rigid on each, under the lesser coverts."""
    for s, sx in SIDES:
        S0, E, W, T = wing_rest(sx); lead = V((0, -.022, .012))
        for b, a, c, ext in ((f'humerus.{s}', S0 - V((sx * .02, 0, 0)), E, .02), (f'forearm.{s}', E, W, .02), (f'hand.{s}', W, T, .0)):
            d = (c - a).normalized(); a2, c2 = a - d * .015 + lead, c + d * ext + lead
            K = 14; rows = []
            for t in np.linspace(0, 1, 6):
                r = .02 if b.startswith('hand') and t > .5 else .026
                rows.append(oval(a2.lerp(c2, t), V((0, -1, 0)), UP, r * (1 - .5 * t if b.startswith('hand') else 1), .012, .009, K))
            sheet(M, rows, caps=(True, True), uv=lambda i, kk, face: slot_uv('down0', min(kk, K) / K if face >= 0 else .5, i / 5))
            M.tag(b)

def build_feathers(t):
    M = Mesh(f'L{t}_Feathers', uv=True); specs = feather_specs(t)
    for f in specs: f['rows'] = card(M, f)
    build_patagia(M)
    return M.finish(), specs

def build_flames(specs):
    """Small flames licking from the tips of the flight feathers, the tail and the crest, and
    rising from the wrists: crossed emissive cards on the feathers' bones."""
    M = Mesh('L3_Flames', uv=True); rng = random.Random(7); k = 0
    def flame(base, d, n, L, W, bone):
        nonlocal k
        d = d.normalized(); n = (n - d * n.dot(d)).normalized()
        for side in (n, n.cross(d)):
            s = side.cross(d).normalized(); var = k % 3; k += 1
            rows = [[base + d * (v * L) - s * ((u - .5) * W) for u in (0, 1)] for v in (0, 1)]
            sheet(M, rows, closed=False, uv=lambda i, kk, face, var=var: ((var + (kk if kk < 2 else 1)) / 3, i * .98 + .01))
        M.tag(bone)
    for f in specs:
        if not f.get('tip') or f['kind'] == 'covert': continue
        sl = f['slot']; i = int(sl[3:]) if sl.startswith('rem') else -1
        if sl.startswith('rem') and not (3 <= i <= 9 or i in (11, 15, 19, 23)): continue
        if sl.startswith('tail') and int(sl[4:]) % 3: continue
        if sl.startswith(('sp', 'bp')): continue
        if f['bone'] == 'crest' and not f.get('flame'): continue
        row = f['rows'][-1]; tipc = row[2]; d = (row[2] - f['rows'][-2][2]).normalized(); n = f['n']
        L = (.13 if sl.startswith('rem') else .11) * (.8 + .4 * rng.random()); W = L * .6
        flame(tipc - d * .03, (d * .75 + n.normalized() * .45), n, L, W, f['bone'])
    for s, sx in SIDES:   # rising from the leading edge at the wrist
        S0, E, W_, T = wing_rest(sx)
        for p, bone in ((W_.lerp(T, .15), f'hand.{s}'), (W_.lerp(E, .25), f'forearm.{s}')):
            flame(p + V((0, -.03, .03)), V((sx * .15, .1, 1)), FWD, .16 * (.85 + .3 * rng.random()), .1, bone)
    return M.finish()


# ── Textures ────────────────────────────────────────────────────────────────
AW, AH = 2048, 1024
def make_slots():
    d = {}
    for i in range(40): d[f'rem{i}' if i < 28 else f'tail{i - 28}'] = (8 + 48 * i, 0, 48, 512)
    names = ([f'gc{i}' for i in range(4)] + [f'mc{i}' for i in range(4)] + [f'lc{i}' for i in range(4)] + [f'pc{i}' for i in range(3)] +
             [f'sp{i}' for i in range(4)] + [f'bp{i}' for i in range(4)] + ['cr0', 'rib0', 'down0', 'tuft0'])
    for i, nm in enumerate(names): d[nm] = (8 + 64 * i, 512, 64, 512)
    return d
SLOTS = make_slots()

def slot_uv(name, u, v, pad=3):
    x, y, w, h = SLOTS[name]
    return ((x + pad + u * (w - 2 * pad)) / AW, 1 - (y + pad + (1 - v) * (h - 2 * pad)) / AH)

def hexa(h): return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255

def grad(stops, v):
    P_ = [p for p, _ in stops]; C = np.array([hexa(c) for _, c in stops])
    return np.stack([np.interp(v, P_, C[:, j]) for j in range(3)], -1)

# Each tier's plumage: colour stops along a feather (base to tip) by kind; 'glow' is L3's ember light.
def stops(t, name, span=0.0, tert=False):
    if t == 1:
        if name.startswith('rem'):
            if tert: return [(0, '#7d8187'), (1, '#6c7076')]
            fs = min(.78, max(.18, .86 - .62 * span))
            return [(0, '#787c82'), (fs, '#64686e'), (fs + .22 * (1 - fs), '#6a2a1d'), (fs + .5 * (1 - fs), '#bd3318'), (fs + .82 * (1 - fs), '#e8621c'), (1, '#f08a2c')]
        if name.startswith('tail'): return [(0, '#57595f'), (1, '#2d2f34')]
        if name.startswith('pc'): return [(0, '#73777d'), (1, '#666a70')]
        if name.startswith(('gc', 'mc', 'lc', 'down')): return [(0, '#868a90'), (1, '#91959b')]
        if name.startswith('sp'): return [(0, '#8f9399'), (1, '#a6a9ae')]
        if name.startswith('bp'): return [(0, '#b2b5b9'), (1, '#d2d4d7')]
        if name.startswith('cr'): return [(0, '#6f7379'), (1, '#9a9ea3')]
        return [(0, '#2c2e32'), (1, '#1e1f22')]
    if t == 2:
        if name.startswith('rem'):
            if tert: return [(0, '#6e8098'), (1, '#5d6f87')]
            return [(0, '#4e5867'), (.45, '#353c47'), (1, '#1c2027')]
        if name.startswith('tail'): return [(0, '#6c7e94'), (1, '#55667b')]
        if name.startswith('pc'): return [(0, '#3f4754'), (1, '#323843')]
        if name.startswith(('gc', 'mc', 'lc', 'down')): return [(0, '#7387a0'), (1, '#8597ae')]
        if name.startswith('sp'): return [(0, '#93a4b9'), (1, '#b9c4d1')]
        if name.startswith('bp'): return [(0, '#cbd2da'), (1, '#e6eaee')]
        return [(0, '#202429'), (1, '#16181c')]
    if name.startswith('bp'): return [(0, '#6e8196'), (1, '#91a1b2')]
    if name.startswith('cr') or name.startswith('rib'): return [(0, '#5d7084'), (.75, '#6f8296'), (1, '#e8862e')]
    if name.startswith(('rem', 'tail')): return [(0, '#3e1006'), (.35, '#7a1d09'), (.7, '#b8400f'), (1, '#ec7a22')]
    return [(0, '#4a1207'), (.6, '#8c2a0b'), (1, '#b84a12')]

def atlas_pattern(name, w, h, pad=3):
    """The pattern of one slot: u across the vane, v along it, the barbs, the rachis and the edge."""
    u = np.clip((np.arange(w) + .5 - pad) / (w - 2 * pad), 0, 1)[None, :].repeat(h, 0)
    v = np.clip(1 - (np.arange(h) + .5 - pad) / (h - 2 * pad), 0, 1)[:, None].repeat(w, 1)
    q = np.abs(u - .5) * 2; long_ = name.startswith(('rem', 'tail', 'sp', 'bp', 'rib', 'cr'))
    nb = 90 if long_ else 34
    ph = (v * nb - q * nb * (.16 if long_ else .3)) % 1.0
    barb = np.clip(1 - np.abs(ph - .5) / .5, 0, 1) ** 6
    rw = (.07 if long_ else .1) * (1 - .6 * v) + .012
    rachis = np.exp(-(q / rw) ** 2) * (v < .985)
    edge = np.clip((q - .78) / .22, 0, 1) ** 2
    return u, v, q, barb, rachis, edge

def paint_atlas(t, rng):
    """The tier's feather atlas: colour (and L3's ember glow), slot by slot."""
    col = np.zeros((AH, AW, 3), np.float32); emit = np.zeros((AH, AW, 3), np.float32) if t == 3 else None
    span = {}; tert = set()
    for c in wing_columns(1, 'L'): span[c['slot']] = c['span']; tert |= {c['slot']} if c.get('tert') else set()
    for name, (x, y, w, h) in SLOTS.items():
        u, v, q, barb, rachis, edge = atlas_pattern(name, w, h)
        base = grad(stops(t, name, span.get(name, 0), name in tert), v)
        mott = 1 + .07 * (rng.random((h, w)) - .5) + .05 * np.sin(v * 37 + rng.random() * 6)
        c = base * (1 - .16 * barb[..., None]) * (1 - .14 * edge[..., None]) * mott[..., None]
        light = np.clip(base * 1.35 + .05, 0, 1)
        c = c * (1 - .6 * rachis[..., None]) + light * (.6 * rachis[..., None])
        if t == 2 and name.startswith(('gc', 'mc', 'lc')): c = c * (1 - .3 * edge[..., None]) + hexa('#b3c0cf') * (.3 * edge[..., None])
        if name.startswith('bp') and t != 3: c = c * (1 - .25 * (rachis[..., None])) + hexa('#2a2d32') * (.12 * barb[..., None] * (v[..., None] > .5))
        col[y:y + h, x:x + w] = c * (.62 if t == 3 else .8)
        if emit is not None and not name.startswith('bp'):
            glow = hexa('#ff7a1c'); hot = hexa('#ffc45a')
            k = (.06 + .45 * barb + .55 * rachis + .8 * edge) * (.25 + .75 * v ** 1.5)
            if name.startswith(('cr', 'rib')): k = k * np.clip((v - .7) / .3, 0, 1)
            emit[y:y + h, x:x + w] = glow * k[..., None] * .9 + hot * (np.clip(k - .7, 0, 1)[..., None])
    return col, emit

def atlas_normal():
    """The feathers' normal map: the raised rachis and the grooves between the barbs."""
    hgt = np.zeros((AH, AW), np.float32)
    for name, (x, y, w, h) in SLOTS.items():
        u, v, q, barb, rachis, edge = atlas_pattern(name, w, h)
        hgt[y:y + h, x:x + w] = 1.6 * rachis - .5 * barb - .6 * edge
    gy, gx = np.gradient(hgt); nx, ny = -gx * 1.2, gy * 1.2; nz = np.ones_like(nx); l = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    return np.stack([nx / l, ny / l, nz / l], -1) * .5 + .5

def save_img(arr, name, cs, alpha=None):
    from PIL import Image
    a = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    if alpha is not None: a = np.concatenate([a, (np.clip(alpha, 0, 1) * 255).astype(np.uint8)[..., None]], -1)
    p = os.path.join(OUT, f'bennu_{name}.png'); Image.fromarray(a).save(p)
    img = bpy.data.images.load(p); img.colorspace_settings.name = cs; img.pack(); return img

def flame_texture():
    """Three tongues of flame side by side: white-yellow at the root, orange, red at the tips."""
    w, h = 128, 256; rng = np.random.default_rng(4); cols, alps = [], []
    for k in range(3):
        u = (np.arange(w) + .5) / w * 2 - 1; v = 1 - (np.arange(h) + .5) / h
        U, Vv = np.meshgrid(u, v); a = np.zeros_like(U); heat = np.zeros_like(U)
        for off, hgt, wd in ((0, 1.0, .5), (-.36, .58 + .1 * k, .3), (.38, .7 - .08 * k, .28)):   # a main tongue and two lesser ones
            t = np.clip(Vv / hgt, 0, 1); ph = rng.random() * 6
            uu = (U - off - .25 * off * t) / wd + .35 * t ** 1.4 * np.sin(t * 8 + ph) + .1 * np.sin(t * 21 + ph * 2) * t
            prof = np.sin(np.pi * np.clip(t, .001, 1) ** .5) * (1 - t) ** .5 * (Vv < hgt)
            inside = np.abs(uu) < prof
            a = np.maximum(a, inside); heat = np.maximum(heat, inside * np.clip(1 - np.abs(uu) / np.maximum(prof, 1e-3), 0, 1) * (1 - t) ** .5)
        c = grad([(0, '#b8260a'), (.3, '#ff5a10'), (.6, '#ffa52e'), (1, '#fff0b0')], heat)
        cols.append(c); alps.append(a)
    return save_img(np.concatenate(cols, 1), 'flame', 'sRGB', np.concatenate(alps, 1))


# ── Materials ───────────────────────────────────────────────────────────────
PAL = {1: dict(body='#62666d', body2='#565a61', back='#53575e', neck='#6c7076', fore='#8a8e93', streak='#25272b', face='#a9adb2',
               stripe='#222428', bill='#6f6550', bill2='#968558', lore='#9c955c'),
       2: dict(body='#4b5b70', body2='#415065', back='#45556a', neck='#8c97a4', fore='#cfd4d9', streak='#1a1e24', face='#d3d7db',
               stripe='#131518', bill='#7e6c4a', bill2='#a88f58', lore='#a6995a'),
       3: dict(body='#260904', body2='#3a0d05', back='#200703', neck='#4d5e71', fore='#68798b', streak='#232d38', face='#5f7286',
               stripe='#2a3542', bill='#6f6a5e', bill2='#9a8e72', lore='#b0a060')}

def m_plumage(name, t, res, head=False):
    """Contour feathers in the object's space: overlapping rounded tips darker at their edges, with
    fine barbs; grey (or ember, for L3's body) by region from the vertex attributes."""
    p = PAL[t]; m = Mat(name, res=res)
    A = lambda nm: m.node('ShaderNodeAttribute', attribute_name=nm).outputs['Fac']
    vor = m.node('ShaderNodeTexVoronoi', Scale=46.0 if head else (52.0 if t == 3 else 34.0)); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    edge = m.ramp(vor.outputs['Distance'], [(.15, (0, 0, 0)), (.62, (1, 1, 1))]).outputs['Color']
    mp = m.node('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, .16); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector'])
    st = m.node('ShaderNodeTexNoise', Scale=70.0, Detail=2.0); m.L.new(mp.outputs['Vector'], st.inputs['Vector'])
    streak = m.ramp(st.outputs['Fac'], [(.6, (0, 0, 0)), (.68, (1, 1, 1))]).outputs['Color']
    wav = m.node('ShaderNodeTexWave', wave_type='BANDS', Scale=180.0, Distortion=5.0, Detail=2.0); m.L.new(m.coord.outputs['Object'], wav.inputs['Vector'])
    col = m.ramp(m.noise(9, 4, .55).outputs['Fac'], [(.35, srgb(p['body'])), (.7, srgb(p['body2']))]).outputs['Color']
    if head:
        col = m.mix(srgb(p['neck']), srgb(p['face']), A('face'))
    else:
        col = m.mix(col, srgb(p['back']), A('dors'))
        if t == 3: col = m.mix(col, srgb('#4e1607'), edge)
        col = m.mix(col, srgb(p['neck']), A('neck'))
        col = m.mix(col, m.mix(srgb(p['fore']), srgb(p['streak']), streak), A('fore'))
    col = m.mix(col, (0, 0, 0), m.ramp(edge, [(0, (0, 0, 0)), (1, (.22, .22, .22))]).outputs['Color'])
    col = m.mix(col, (0, 0, 0), m.ramp(wav.outputs['Fac'], [(0, (.08, .08, .08)), (1, (0, 0, 0))]).outputs['Color'])
    bump = m.mix(m.mix((0, 0, 0), (1, 1, 1), m.ramp(edge, [(0, (1, 1, 1)), (1, (0, 0, 0))]).outputs['Color']), wav.outputs['Fac'], .25)
    rough = .82
    if head:
        col = m.mix(col, srgb(p['stripe']), A('stripe'))
        col = m.mix(col, srgb(p['lore']), A('lore'))
        bill = m.ramp(m.noise(30, 3, .5).outputs['Fac'], [(.3, srgb(p['bill2'])), (.7, srgb(p['bill2']))]).outputs['Color']
        bill = m.mix(bill, srgb(p['bill']), A('culmen'))
        col = m.mix(col, bill, A('bill'))
        bump = m.mix(bump, (.5, .5, .5), A('bill'))
        rough = m.ramp(A('bill'), [(0, (.82, .82, .82)), (1, (.38, .38, .38))]).outputs['Color']
    m.set(col, rough, bump, .3, .003)
    if t == 3 and not head:   # coals: the seams between the feathers glow through, the neck stays grey
        glow = m.mix(srgb('#ff6a12'), srgb('#ffb040'), m.noise(14, 3, .5).outputs['Fac'])
        ve = m.node('ShaderNodeTexVoronoi', Scale=52.0, feature='DISTANCE_TO_EDGE'); m.L.new(m.coord.outputs['Object'], ve.inputs['Vector'])
        seam = m.ramp(ve.outputs['Distance'], [(0, (1, 1, 1)), (.07, (0, 0, 0))]).outputs['Color']
        k = m.mix(m.mix(seam, (1, 1, 1), m.ramp(edge, [(0, (0, 0, 0)), (1, (.12, .12, .12))]).outputs['Color']), (0, 0, 0), A('neck'))
        e = m.mix((0, 0, 0), glow, m.ramp(k, [(0, (0, 0, 0)), (1, (.75, .75, .75))]).outputs['Color'])
        m.L.new(e, m.bsdf.inputs['Emission Color']); m.bsdf.inputs['Emission Strength'].default_value = 1.0
    return m

def m_leg():
    """Scaled grey-brown skin: domed scutes, darker between them, the claws dark horn and the top
    of the shank feathered grey."""
    m = Mat('Leg', res=1024)
    vor = m.node('ShaderNodeTexVoronoi', Scale=230.0); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    dome = m.ramp(vor.outputs['Distance'], [(0, (1, 1, 1)), (.5, (0, 0, 0))]).outputs['Color']
    col = m.ramp(m.noise(20, 3, .5).outputs['Fac'], [(.3, srgb('#6f675c')), (.7, srgb('#8a8174'))]).outputs['Color']
    col = m.mix(srgb('#4a443d'), col, dome)
    fe = m.node('ShaderNodeAttribute', attribute_name='feath').outputs['Fac']
    col = m.mix(col, srgb('#7a7e84'), fe)
    m.set(col, .55, m.mix(dome, (0, 0, 0), fe), .35, .0015)
    return m

def m_feathers(t, col, nrm, emit):
    m = bpy.data.materials.new(f'Feathers_L{t}'); m.use_nodes = True; m.use_backface_culling = False
    N = m.node_tree.nodes; L = m.node_tree.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexImage'); tc.image = col; L.new(tc.outputs['Color'], b.inputs['Base Color'])
    tn = N.new('ShaderNodeTexImage'); tn.image = nrm; nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = .6
    L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Roughness'].default_value = .72
    if emit is not None:
        te = N.new('ShaderNodeTexImage'); te.image = emit; L.new(te.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.0
    return m

def m_flame(img):
    m = bpy.data.materials.new('Flame'); m.use_nodes = True; m.use_backface_culling = False
    N = m.node_tree.nodes; L = m.node_tree.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexImage'); tc.image = img; L.new(tc.outputs['Color'], b.inputs['Base Color']); L.new(tc.outputs['Color'], b.inputs['Emission Color'])
    rd = N.new('ShaderNodeMath'); rd.operation = 'ROUND'; L.new(tc.outputs['Alpha'], rd.inputs[0]); L.new(rd.outputs['Value'], b.inputs['Alpha'])
    b.inputs['Emission Strength'].default_value = 1.0; b.inputs['Roughness'].default_value = 1.0
    return m

def bake(items):
    """scorpion.bake, also baking an emission map where the material glows."""
    SC = H.SC; SC.cycles.samples = 4; SC.render.bake.use_selected_to_active = False; SC.render.bake.margin = 6
    for name, (ob, mt) in items.items():
        if not ob.data.uv_layers: H.smart_uv(ob, .01)
        bs = mt.bsdf; imgs = {}
        kinds = ['color'] + (['rough'] if bs.inputs['Roughness'].links else []) + ['normal'] + (['emit'] if bs.inputs['Emission Color'].links else [])
        for kind in kinds:
            r = mt.res if kind in ('color', 'emit') else max(128, mt.res // 2)
            img = bpy.data.images.new(f'{ob.name}_{kind}', r, r, alpha=False)
            img.colorspace_settings.name = 'sRGB' if kind in ('color', 'emit') else 'Non-Color'; imgs[kind] = img
        m = mt.m.copy(); m.name = f'{mt.m.name}_{ob.name}'; ob.data.materials.clear(); ob.data.materials.append(m)
        nt = m.node_tree; N = nt.nodes; Lk = nt.links; bsdf = N['Principled BSDF']; outn = N['Material Output']
        tex = N.new('ShaderNodeTexImage'); H.activate(ob)
        for kind, img in imgs.items():
            tex.image = img; N.active = tex
            if kind == 'normal':
                Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface']); bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
            else:
                src = bsdf.inputs[{'color': 'Base Color', 'rough': 'Roughness', 'emit': 'Emission Color'}[kind]]; em = N.new('ShaderNodeEmission')
                if src.links: Lk.new(src.links[0].from_socket, em.inputs['Color'])
                else: v = src.default_value; em.inputs['Color'].default_value = tuple(v) if kind != 'rough' else (v, v, v, 1)
                Lk.new(em.outputs['Emission'], outn.inputs['Surface']); bpy.ops.object.bake(type='EMIT'); N.remove(em)
            img.pack()
        for n in list(N):
            if n not in (bsdf, outn): N.remove(n)
        Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface'])
        for kind, img in imgs.items():
            t_ = N.new('ShaderNodeTexImage'); t_.image = img
            if kind == 'color': Lk.new(t_.outputs['Color'], bsdf.inputs['Base Color'])
            elif kind == 'rough': Lk.new(t_.outputs['Color'], bsdf.inputs['Roughness'])
            elif kind == 'emit': Lk.new(t_.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 1.0
            else:
                nm = N.new('ShaderNodeNormalMap'); Lk.new(t_.outputs['Color'], nm.inputs['Color']); Lk.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        print('baked', ob.name, list(imgs))


# ── Moves ───────────────────────────────────────────────────────────────────
class Poser(SP.Poser):
    """scorpion.Poser, with a turn about an axis carried by the parent (before the bone's own
    rotation) and a bone set to a given armature-space rotation."""
    def turn(self, n, axis, ang):
        if ang: self.q[n] = Quaternion((self.rest[n].to_3x3().inverted() @ V(axis)).normalized(), ang) @ self.q[n]; self.M = {}
    def orient(self, n, R):
        B = self.base(n).to_3x3(); self.q[n] = (B.inverted() @ R @ self.rest[n].to_3x3()).to_quaternion(); self.M = {}

def frame(d, n):
    """The rotation whose columns are the side, d and the normal n made square to d."""
    d = d.normalized(); s = d.cross(n).normalized(); n = s.cross(d)
    return Matrix((s, d, n)).transposed()

def fold_plane(sx):
    """The folded wing's plane: its outward normal and its directions back and down."""
    Rz = Matrix.Rotation(sx * TOE, 3, 'Z'); N = Rz @ V((sx * math.cos(TILT), 0, math.sin(TILT)))
    eb = Rz @ V((0, 1, 0)); return N, eb, eb.cross(N).normalized() * sx

FOLD, SHOW, WING_BONES, LEG_REST, SAMPLES = {}, {}, {}, {}, {}

def solve_fold(po):
    """The local rotations of every wing bone with the wing folded: the arm in its Z and each
    feather bone turned to lie back along the flank in the fold's plane."""
    po.clear()
    for s, sx in SIDES:
        N, eb, ed = fold_plane(sx); fd = lambda a: eb * math.cos(math.radians(a)) + ed * math.sin(math.radians(a))
        S0, E, W, T = wing_rest(sx); names = []
        for b, d0, a in ((f'humerus.{s}', E - S0, ARM_FOLD[0]), (f'forearm.{s}', W - E, ARM_FOLD[1]), (f'hand.{s}', T - W, ARM_FOLD[2])):
            po.orient(b, frame(fd(a), N) @ frame(d0, UP).inverted()); names.append(b)
        for g, (h, d0, par) in wing_groups(sx, s).items():
            po.orient(g, frame(fd(group_fold_angle(g)), N) @ frame(d0, UP).inverted()); names.append(g)
        WING_BONES[s] = names
        for n in names: q = po.q[n].copy(); FOLD[n] = q if q.w >= 0 else -q
        po.clear()
        for b, d0, d1 in zip(names[:3], (E - S0, W - E, T - W), ARM_SHOW):
            po.orient(b, frame(V((d1[0] * sx, d1[1], d1[2])), V((0, 1, 0))) @ frame(d0, UP).inverted())
        for n in names: q = po.q[n].copy(); SHOW[n] = q if q.w >= 0 else -q
    po.clear()

def wing(po, s, fold, lift=0.0, sweep=0.0, show=0.0):
    """Wing s between spread (0) and folded (1), or towards the raised display by show, then raised
    by lift and swept forward by sweep (radians) about the shoulder."""
    sx = 1 if s == 'L' else -1
    for n in WING_BONES[s]:
        q = Quaternion().slerp(FOLD[n], fold); po.q[n] = q.slerp(SHOW[n] if q.dot(SHOW[n]) >= 0 else -SHOW[n], show) if show else q
    po.M = {}
    po.turn(f'humerus.{s}', (0, 1, 0), -sx * lift); po.turn(f'humerus.{s}', (0, 0, 1), -sx * sweep)

def place_leg(po, s, foot, swing=0.0, curl=0.0):
    """Leg s with its foot at an armature-space point: the thigh swung about the hip by swing, the
    shank and tarsus solved with the intertarsal joint bending back, the toes flat on the ground
    or drooping by curl."""
    Hp, K, A, F, tips = LEG_REST[s]; Mb = po.skin('body'); R3 = Mb.to_3x3(); Rs = Matrix.Rotation(swing, 3, 'X')
    po.aim(f'thigh.{s}', R3 @ (Rs @ (K - Hp))); Kb = Mb @ (Hp + Rs @ (K - Hp))
    Ab = H.two_bone(Kb, foot, (A - K).length, (F - A).length, R3 @ (A - (K + F) / 2))
    po.aim(f'shank.{s}', Ab - Kb); po.aim(f'tarsus.{s}', foot - Ab)
    for i, tp in enumerate(tips):
        d = R3 @ (tp - F); d = V((d.x, d.y, -.03 * math.hypot(d.x, d.y))).normalized()
        if curl: d = Matrix.Rotation(curl * (1.25 if i else .7), 3, UP.cross(d).normalized()) @ d
        po.aim(f'toe{i + 1}.{s}', d)

def plant(po, offs=None):
    for s, sx in SIDES:
        o = (offs or {}).get(s, (V((0, 0, 0)), 0.0, 0.0))
        place_leg(po, s, LEG_REST[s][3] + o[0], o[1], o[2])

def neck(po, a, yaw=0.0, tilt=0.0):
    """Bend the neck: a holds the turns at the six neck joints and the head (positive pitches
    forward and down); yaw turns the head to the side, spread down the upper neck."""
    for i in range(6): po.bend(f'neck{i + 1}', (1, 0, 0), a[i])
    po.bend('head', (1, 0, 0), a[6])
    for n, k in (('neck4', .15), ('neck5', .25), ('neck6', .3), ('head', .3)): po.bend(n, (0, 0, 1), yaw * k)
    if tilt: po.bend('head', (0, 1, 0), tilt)

def neck_chain():
    return np.array([(p.y, p.z) for p in NJ] + [(BILL_BASE.y, BILL_BASE.z), (BILL_TIP.y, BILL_TIP.z)])

def solve_neck(target, aim, seed=3, tip_w=40.0):
    """Turns at the neck joints and the head that bring the bill's tip to target (y, z, in the
    body's rest frame) pointing along aim, with the bend spread along the neck."""
    base = neck_chain(); rng = np.random.default_rng(seed); target = np.array(target); aim = np.array(aim) / np.linalg.norm(aim)
    def cost(a):
        p = SP.chain_fk(base, a); tip = p[-1]; d = p[-1] - p[-2]; d = d / (np.linalg.norm(d) + 1e-9)
        c = tip_w * np.sum((tip - target) ** 2) + .6 * (1 - d.dot(aim)) + .05 * np.sum(np.diff(a[:6]) ** 2) + .015 * np.sum(a ** 2)
        c += 3 * np.sum(np.maximum(0, np.abs(a) - np.array([.8, 1.1, 1.2, 1.2, 1.2, 1.1, 1.2])) ** 2)
        for q in p[2:7]:   # keep the neck out of the back
            if q[0] > base[0][0] - .02: c += 30 * max(0, base[0][1] + .12 - q[1]) ** 2
        return c
    best = np.zeros(7); bc = cost(best); step = .35
    for it in range(5000):
        cand = best + rng.normal(0, step, 7); cc = cost(cand)
        if cc < bc: best, bc = cand, cc
        if it % 500 == 499: step *= .6
    print('bill misses its mark by', round(float(np.linalg.norm(SP.chain_fk(base, best)[-1] - target)) * 1000), 'mm')
    return best

def lowest(po):
    return min((po.skin(b) @ p).z for b, pts in SAMPLES.items() for p in pts)

def bump(f, c, w): return math.exp(-((f - c) / w) ** 2)

def actions(rig):
    po = Poser(rig); A = []
    for s, sx in SIDES: LEG_REST[s] = leg_pts(sx)
    solve_fold(po)
    FEET = V((0, LEG_REST['L'][3].y, 0)); X = (1, 0, 0)
    tip0 = np.array([BILL_TIP.y, BILL_TIP.z])
    def rel(dy, dz): return tip0 + np.array([dy, dz])
    def dirv(deg): a = math.radians(deg); return np.array([-math.cos(a), math.sin(a)])   # forward, deg above level
    A_DRAW = solve_neck(rel(.26, -.22), dirv(-18), 1)
    A_STAB = solve_neck(rel(-.58, -.72), dirv(-38), 2)
    A_COIL = solve_neck(rel(.24, .1), dirv(30), 3)
    A_THRUST = solve_neck(rel(-.46, -.3), dirv(-12), 4)
    PITCH = .5   # in flight the body is level: pitched tail-up from its standing slope
    j0 = np.array([NJ[0].y, NJ[0].z]); c_, s_ = math.cos(-PITCH), math.sin(-PITCH)
    rot = lambda v: np.array([v[0] * c_ - v[1] * s_, v[0] * s_ + v[1] * c_])
    A_FLY = solve_neck(j0 + rot(np.array([-.5, .2])), rot(np.array([-1.0, -.05])), 5)
    print('neck poses', {k: [round(float(x), 2) for x in v] for k, v in (('draw', A_DRAW), ('stab', A_STAB), ('coil', A_COIL), ('thrust', A_THRUST), ('fly', A_FLY))})
    def clip(name, length, fn, step=1):
        rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
        po.prev = {}
        for fr in sorted(set(range(1, length + 1, step)) | {length}): po.clear(); fn(fr); po.key(fr)
        A.append(act)
    def idle(f):
        w = 2 * math.pi * (f - 1) / 96
        po.place(Matrix.Rotation(.006 * math.sin(w), 3, 'X'), (0, 0, .003 * math.sin(2 * w)), FEET)
        look = smooth(14, 24, f) * (1 - smooth(40, 50, f)) - .7 * smooth(58, 66, f) * (1 - smooth(80, 90, f))
        neck(po, [.015 * math.sin(w + .5 * i) for i in range(6)] + [.04 * math.sin(2 * w) - .06 * bump(f, 33, 6)], .6 * look,
             .1 * smooth(18, 28, f) * (1 - smooth(38, 48, f)))
        po.bend('crest', X, .05 * math.sin(2 * w + 1)); po.bend('tail', X, .025 * math.sin(w))
        for s in ('L', 'R'): wing(po, s, 1 - .07 * bump(f, 74, 5), .03 * bump(f, 74, 5))
        plant(po)
    clip('Idle', 96, idle, 2)
    STRIDE, DUTY = .3, .56
    def walk(f):
        t = (f - 1) / 40; w = 2 * math.pi * t
        po.place(Matrix.Rotation(.02 * math.sin(w), 3, 'Y') @ Matrix.Rotation(.03 + .012 * math.cos(2 * w), 3, 'X'),
                 (.012 * math.sin(w), 0, -.025 + .01 * math.cos(2 * w)), FEET)
        neck(po, [.05 * math.sin(2 * w), .03 * math.sin(2 * w), 0, -.03 * math.sin(2 * w), -.04 * math.sin(2 * w), -.03 * math.sin(2 * w),
                  .03 * math.sin(2 * w) - .04], .05 * math.sin(w))
        po.bend('tail', X, .03 * math.sin(2 * w)); po.bend('crest', X, .04 * math.sin(2 * w + 1))
        for s in ('L', 'R'): wing(po, s, 1.0)
        offs = {}
        for s, ph0 in (('L', 0), ('R', .5)):
            ph = (t + ph0) % 1
            if ph < DUTY: dy = -STRIDE / 2 + STRIDE * ph / DUTY; lift = curl = 0.0; u = 0.0
            else:
                u = (ph - DUTY) / (1 - DUTY); dy = STRIDE / 2 - STRIDE * smooth(0, 1, u)
                lift = .15 * math.sin(math.pi * u) ** .8; curl = 1.0 * math.sin(math.pi * u)
            offs[s] = (V((0, dy, lift)), -1.2 * (-dy) - .45 * math.sin(math.pi * u), curl)
        plant(po, offs)
    clip('Walk', 40, walk)
    def fly(f):
        p = 2 * math.pi * (f - 1) / 24
        po.place(Matrix.Rotation(PITCH + .04 * math.sin(p), 3, 'X'), (0, .08, .62 - .045 * math.cos(p)), P(250, 0, 380))
        neck(po, list(A_FLY + np.array([.03, .02, 0, -.02, -.03, -.02, .02]) * math.sin(p + 1)))
        po.bend('tail', X, .1 + .06 * math.sin(p + .5)); po.bend('crest', X, -.35 + .06 * math.sin(p + 1))
        for s in ('L', 'R'): wing(po, s, .42 * max(0.0, -math.sin(p)) ** .9, .2 + .82 * math.cos(p), .1 * math.sin(p))
        for s, sx in SIDES:   # the legs trail straight back, the toes closed
            Hp, K, A_, F, tips = LEG_REST[s]; R3 = po.skin('body').to_3x3()
            po.aim(f'thigh.{s}', R3 @ (Matrix.Rotation(.35, 3, 'X') @ (K - Hp)))
            po.aim(f'shank.{s}', V((sx * .05, .72, -.69))); po.aim(f'tarsus.{s}', V((sx * .02, .985, -.17 + .02 * math.sin(p))))
            for i in range(4): po.aim(f'toe{i + 1}.{s}', V((sx * (.0, -.05, 0, .06)[i], .97, -.24)) if i else V((sx * .02, .96, -.1)))
    clip('Fly', 24, fly)
    def strike(f):
        a = smooth(1, 9, f); b = smooth(10, 14, f); r = smooth(19, 34, f); k = 1 - r
        ang = (A_DRAW * a * (1 - b) + A_STAB * b) * k
        po.place(Matrix.Rotation((.04 * a * (1 - b) + .2 * b) * k, 3, 'X'), (0, 0, -.03 * a * k), FEET)
        neck(po, list(ang)); po.bend('jaw', X, .18 * smooth(12, 14, f) * (1 - smooth(16, 21, f)))
        po.bend('crest', X, (-.15 * a * (1 - b) - .3 * b) * k); po.bend('tail', X, .12 * b * k)
        for s in ('L', 'R'): wing(po, s, 1 - .14 * b * k, .12 * b * k)
        plant(po)
    clip('Strike', 36, strike)
    def cast(f):
        a = smooth(1, 12, f); b = smooth(17, 22, f); r = smooth(32, 46, f); k = 1 - r
        ang = (A_COIL * a * (1 - b) + A_THRUST * b) * k
        po.place(Matrix.Rotation((-.06 * a * (1 - b) + .14 * b) * k, 3, 'X'), (0, 0, -.02 * a * k), FEET)
        neck(po, list(ang)); po.bend('jaw', X, .6 * smooth(18, 21, f) * (1 - smooth(30, 36, f)))
        po.bend('crest', X, (.3 * a * (1 - b) - .25 * b) * k); po.bend('tail', X, .15 * a * k)
        for s in ('L', 'R'): wing(po, s, 1.0, (-.25 * b + .1 * math.sin(math.pi * smooth(17, 30, f))) * k, (.35 * b) * k, a * k)
        plant(po)
    clip('Cast', 48, cast)
    def hit(f):
        e = smooth(1, 4, f) * (1 - smooth(6, 20, f))
        po.place(Matrix.Rotation(-.1 * e, 3, 'X'), (0, .05 * e, 0), FEET)
        neck(po, [.1 * e, .05 * e, -.1 * e, -.2 * e, -.2 * e, -.1 * e, .25 * e]); po.bend('jaw', X, .25 * e)
        po.bend('crest', X, -.3 * e); po.bend('tail', X, .1 * e)
        for s in ('L', 'R'): wing(po, s, 1.0, 0, 0, .4 * e)
        plant(po)
    clip('Hit', 20, hit)
    A_DEAD = np.array([.45, .4, .35, .3, .25, .2, -.2])
    def death(f):
        jerk = math.sin(math.pi * smooth(1, 8, f)); sink = smooth(5, 26, f); roll = smooth(22, 42, f); limp = smooth(8, 34, f)
        R0 = Matrix.Rotation(-.12 * jerk + .22 * sink, 3, 'X'); t0 = V((0, .04 * jerk, -.48 * sink))
        po.place(R0, t0, FEET); plant(po)   # the legs fold under it with the feet planted ...
        R = Matrix.Rotation(1.38 * roll, 3, 'Y') @ R0; piv = V((.12, FEET.y - .1, .1))
        po.place(R, t0, piv)                # ... then it rolls onto its left side, the legs going with it
        neck(po, list(A_DEAD * limp + np.array([-.1, -.1, .1, .15, .1, .05, .2]) * jerk))
        for i in range(6): po.bend(f'neck{i + 1}', (0, 1, 0), (.22 if i < 4 else .1) * roll)
        po.bend('jaw', X, .3 * limp); po.bend('crest', X, -.4 * limp); po.bend('tail', X, -.1 * limp)
        wing(po, 'L', 1.0, 0, 0, .35 * jerk * (1 - roll)); wing(po, 'R', 1 - .4 * limp, -.35 * roll, 0, .4 * jerk)
        if f > 6: z = lowest(po); po.place(R, t0 - V((0, 0, z * smooth(6, 14, f))), piv)
    clip('Death', 64, death)
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
def geometry():
    """Every mesh of the line, skinned by vertex groups. Returns {name: object} and the specs of
    the third tier's feathers (for its flames)."""
    parts = {}; specs3 = None
    for t in (1, 2, 3):
        parts[f'L{t}_Body'] = build_body(t); parts[f'L{t}_Head'] = build_head(t)
        ob, specs = build_feathers(t); parts[ob.name] = ob
        if t == 3: specs3 = specs
    parts['Jaw'] = build_jaw()
    M = Mesh('Eyes'); build_eyes(M); parts['Eyes'] = M.finish()
    M = Mesh('Pupils'); build_eyes(M, True); parts['Pupils'] = M.finish()
    M = Mesh('Legs'); build_legs(M); parts['Legs'] = M.finish(); set_attrs(parts['Legs'], leg_attrs)
    parts['L3_Flames'] = build_flames(specs3)
    for name, ob in parts.items():   # sample points per bone, for laying the dead bird on the ground
        if name.startswith(('L2', 'L3')) or name in ('Eyes', 'Pupils'): continue
        gi = {g.index: g.name for g in ob.vertex_groups}
        for v in list(ob.data.vertices)[::17]:
            if len(v.groups) == 1 or (v.groups and max(g.weight for g in v.groups) > .97):
                g = max(v.groups, key=lambda g: g.weight); SAMPLES.setdefault(gi[g.group], []).append(v.co.copy())
    return parts

def build():
    parts = geometry(); rng = np.random.default_rng(11)
    nrm = save_img(atlas_normal(), 'feather_normal', 'Non-Color'); flame = flame_texture(); items = {}
    for t in (1, 2, 3):
        col, emit = paint_atlas(t, rng)
        parts[f'L{t}_Feathers'].data.materials.append(m_feathers(t, save_img(col, f'feathers{t}', 'sRGB'),
                                                                   nrm, save_img(emit, f'feathers{t}_emit', 'sRGB') if emit is not None else None))
        items[f'L{t}_Body'] = (parts[f'L{t}_Body'], m_plumage(f'Plumage{t}', t, 2048))
        items[f'L{t}_Head'] = (parts[f'L{t}_Head'], m_plumage(f'Head{t}', t, 1024, head=True))
    items['Legs'] = (parts['Legs'], m_leg())
    bake(items)
    parts['L3_Flames'].data.materials.append(m_flame(flame))
    parts['Jaw'].data.materials.append(H.m_flat('Bill', '#8f7f56', .38).m)
    parts['Eyes'].data.materials.append(H.m_flat('Iris', '#e6be1c', .15).m)
    parts['Pupils'].data.materials.append(H.m_flat('Pupil', '#050505', .05).m)
    for ob in parts.values():
        for nm in ('rim', 'neck', 'fore', 'dors', 'bill', 'lore', 'stripe', 'face', 'culmen', 'feath', 'claw'):
            if nm in ob.data.attributes: ob.data.attributes.remove(ob.data.attributes[nm])
    rig = HR.build_rig('BennuRig', bones())
    for ob in parts.values(): skin(ob, rig)
    for ob in rig.children:
        if ob.type == 'MESH' and ob.data.validate(): print('repaired', ob.name)
    return rig, actions(rig)

def export(rig, path):
    """hoplite.export, then the feathers marked double-sided and the flames alpha-masked."""
    H.export(rig, path)
    data = open(path, 'rb').read(); jl = struct.unpack('<I', data[12:16])[0]; js = json.loads(data[20:20 + jl]); rest = data[20 + jl:]
    for m in js.get('materials', []):
        if m['name'].startswith(('Feathers', 'Flame')): m['doubleSided'] = True
        if m['name'].startswith('Flame'):   # pure fire: the light comes from the emissive map, not from the lamps
            m['alphaMode'] = 'MASK'; m['alphaCutoff'] = .5; m['pbrMetallicRoughness']['baseColorFactor'] = [.08, .08, .08, 1]; m['emissiveFactor'] = [1, 1, 1]
    j = json.dumps(js, separators=(',', ':')).encode(); j += b' ' * (-len(j) % 4)
    open(path, 'wb').write(struct.pack('<III', 0x46546C67, 2, 20 + len(j) + len(rest)) + struct.pack('<II', len(j), 0x4E4F534A) + j + rest)

def renders(rig):
    """A lineup of the three tiers standing and flying, and each tier from the side, front and back
    beside its sheet."""
    from PIL import Image
    for clip_, fr, tag in (('Idle', 1, 'lineup'), ('Fly', 1, 'fly')):
        shots = []
        for t in (1, 2, 3):
            k = TIERS[t]['scale']; rig.scale = (k, k, k); p = os.path.join(OUT, f'bennu_{tag}_L{t}.png')
            H.render(rig, p, clip_, fr, t, cam=((4.6 * k, -6.6 * k, 2.6 * k), (80, 0, 35)), res=(520, 520), samples=20); shots.append(p)
        ims = [Image.open(p) for p in shots]; row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
        for i in ims: row.paste(i, (x, 0)); x += i.width
        row.save(os.path.join(OUT, f'bennu_{tag}.png'))
    rig.scale = (1, 1, 1)
    for t in (1, 2, 3): compare(rig, t)

SHEET_VIEWS = {'side': (240, 392), 'front': (687, 392), 'back': (1135, 392)}

def compare(rig, t, size=640, samples=16, clip_='Idle', frame_=1):
    """Orthographic side, front and back views of tier t at the sheet's scale, beside the sheet."""
    from PIL import Image
    H.render(rig, os.path.join(OUT, '_warmup.png'), clip_, frame_, t, res=(32, 32), samples=1)
    cam = bpy.data.objects['Cam']; cam.data.type = 'ORTHO'; cam.data.ortho_scale = size * S
    g = bpy.data.objects.get('Ground'); Wc = H.SC.world.node_tree.nodes['Background'].inputs['Color']
    Wc.default_value = (.62, .62, .64, 1); g.hide_render = True
    sheet_im = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'refs', 'bennu', f'bennu-{t}.png')).convert('RGB')
    cols = []
    for view, (cx, cz) in SHEET_VIEWS.items():
        zc = (Y0 - cz) * S
        if view == 'side': cam.location = (-6, (X0 - cx) * S, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
        elif view == 'front': cam.location = (0, -6, zc); cam.rotation_euler = (math.radians(90), 0, 0)
        else: cam.location = (0, 6, zc); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
        p = os.path.join(OUT, f'bennu_L{t}_{view}.png')
        H.SC.cycles.samples = samples; H.SC.render.resolution_x = H.SC.render.resolution_y = size; H.SC.render.filepath = p
        bpy.ops.render.render(write_still=True)
        ref = sheet_im.crop((cx - size // 2, cz - size // 2, cx + size // 2, cz + size // 2))
        both = Image.new('RGB', (size, size * 2)); both.paste(ref, (0, 0)); both.paste(Image.open(p).convert('RGB'), (0, size)); cols.append(both)
    out = Image.new('RGB', (size * 3, size * 2)); [out.paste(c, (i * size, 0)) for i, c in enumerate(cols)]
    out.save(os.path.join(OUT, f'bennu_compare_L{t}.png'))
    cam.data.type = 'PERSP'; g.hide_render = False; Wc.default_value = (.36, .42, .5, 1)

if __name__ == '__main__':
    rig, acts = build()
    export(rig, os.path.join(OUT, 'bennu.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'bennu.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
