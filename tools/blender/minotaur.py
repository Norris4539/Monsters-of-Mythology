"""Realistic Minotaur line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/minotaur.py third_party/makehuman assets/models [--renders]

The bull of Minos, after the reference sheets in refs/minotaur: the MakeHuman man of the
infantry lines made massive (broadened through the chest and shoulders, his muscles
deepened as for Talos), his head replaced by a bull's head and neck. The head and neck
are traced from the side view of the first sheet (PROFILE, in its pixels), inflated
into round sections (a Poisson solve inside the outline, as for the horse) and sized at
each height to the front view's widths (FRONT_W), then fused by a voxel remesh. The
build is made at the infantry's scale and exported at 2.3 m to the poll; the gallery
shows Asterion a little larger.
  L1 Minotaur      dark brown hide, Minoan loincloth with a patterned flap, wide leather
                   belt, a bronze labrys about 1 m long
  L2 Labrys Guard  as L1 with a bronze belt, crossed harness straps, bronze armbands, a
                   figure-of-eight oxhide shield on the back, a longer engraved labrys
  L3 Asterion      near-black hide flecked like the stars, gilded horn tips, a bronze
                   plate corselet with shoulder guards, greaves, a crimson kilt, gold
                   armlets, a huge ceremonial labrys
Node tags: L12_ is worn by the first two tiers (the brown body, head and horns), L1_, L2_
and L3_ by one tier each. The fists are bent into the mesh as for Talos; the right one
is closed round the labrys' haft.
"""
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
import talos as T
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat
from peltast import curve_mesh, bake_obj_xform, Surf
import horse as HR

H.TARGETS = [('caucasian-male-young.target', .5), ('african-male-young.target', .4), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .55), ('universal-male-young-maxmuscle-maxweight.target', .45)]
H.HEIGHT = 1.76
OUT = H.OUT
HEIGHT = 2.3                   # to the poll, after the sheet
SCALE = HEIGHT / H.HEIGHT      # the export's scale
random.seed(31)


# ── The bull's head and neck, traced from the sheet ─────────────────────────
# Side view of refs/minotaur/minotaur-1.png, facing right: the ground at y = 740, the poll
# at y = 62, which is put at the infantry man's full height; x = 672 is the middle of the
# trunk. Front view: the head's middle at x = 265.
PX = H.HEIGHT / (740 - 62)
X0, GROUND, FX0 = 672, 740, 265
def px(x, y, lat=0.0): return V((lat, (X0 - x) * PX, (GROUND - y) * PX))

# Head and neck in profile, from the base of the neck at the back, up the hump, over the
# poll (under the horns), down the face to the nose, under the jaw and down the throat.
PROFILE = [(614, 262), (609, 240), (606, 215), (606, 195), (608, 172), (613, 152), (620, 132), (630, 114), (642, 99),
           (655, 87), (670, 78), (688, 70), (705, 65), (720, 62), (733, 64), (745, 71), (757, 79), (766, 88), (774, 100),
           (781, 114), (788, 127), (795, 140), (800, 150), (803, 157), (802, 163), (797, 169), (790, 174), (782, 179),
           (772, 182), (762, 182), (754, 184), (748, 189), (744, 197), (742, 208), (741, 222), (740, 236), (733, 250),
           (715, 262), (690, 270), (660, 272), (635, 270)]
# Full width in the front view at heights of the side view (px): the poll, the forehead
# between the horns, the eyes, the muzzle, then the neck widening below the jaw.
FRONT_W = [(62, 46), (70, 70), (80, 82), (95, 86), (105, 88), (120, 80), (135, 66), (150, 54), (162, 52),
           (172, 118), (185, 138), (200, 146), (240, 146), (275, 130)]

def _lerp(table, x):
    if x <= table[0][0]: return table[0][1]
    for (x0, v0), (x1, v1) in zip(table, table[1:]):
        if x <= x1: return v0 + (v1 - v0) * (x - x0) / (x1 - x0)
    return table[-1][1]

def _hits(outline, o, d):
    out = []
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
        ex, ey = bx - ax, by - ay; den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12: continue
        t = ((ax - o[0]) * ey - (ay - o[1]) * ex) / den; u = ((ax - o[0]) * d[1] - (ay - o[1]) * d[0]) / den
        if t > 1e-9 and 0 <= u <= 1: out.append(t)
    return sorted(out)

def _inside(outline, X, Y):
    ins = np.zeros(X.shape, bool)
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
        ins ^= ((ay > Y) != (by > Y)) & (X < (bx - ax) * (Y - ay) / ((by - ay) or 1e-9) + ax)
    return ins

def inflate(outline, front_w):
    """Half-widths (px) over the outline: a Poisson solve gives round sections across any
    strip of it (as for the horse); each row is then scaled so that its widest point has
    the front view's width there."""
    x0, x1 = min(p[0] for p in outline) - 3, max(p[0] for p in outline) + 3
    y0, y1 = min(p[1] for p in outline) - 3, max(p[1] for p in outline) + 3
    h = None
    for res in (4, 2, 1):
        xs, ys = np.arange(x0, x1, res, dtype=float), np.arange(y0, y1, res, dtype=float)
        X, Y = np.meshgrid(xs, ys); ins = _inside(outline, X, Y)
        if h is None: h = np.zeros(X.shape)
        else: h = np.kron(h, np.ones((2, 2)))[:X.shape[0], :X.shape[1]]
        h = np.pad(h, ((0, X.shape[0] - h.shape[0]), (0, X.shape[1] - h.shape[1])))
        red = (np.add.outer(np.arange(X.shape[0]), np.arange(X.shape[1])) % 2) == 0
        for _ in range(400 if res == 4 else 250):
            for cells in (ins & red, ins & ~red):
                hn = (np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) + np.roll(h, -1, 1) + res * res) / 4
                h = np.where(cells, h + 1.85 * (hn - h), h)
        h = np.where(ins, h, 0.0)
    W = np.sqrt(2 * np.maximum(h, 0))
    rowmax = np.maximum(W.max(axis=1, keepdims=True), 1e-6)
    want = np.array([[_lerp(front_w, y) / 2] for y in ys])
    return xs, ys, W * want / rowmax

def _sample(grid, x, y):
    xs, ys, W = grid; step = xs[1] - xs[0]
    i = min(max((x - xs[0]) / step, 0), len(xs) - 1.001); j = min(max((y - ys[0]) / step, 0), len(ys) - 1.001)
    i0, j0 = int(i), int(j); fi, fj = i - i0, j - j0
    return (W[j0, i0] * (1 - fi) * (1 - fj) + W[j0, i0 + 1] * fi * (1 - fj) + W[j0 + 1, i0] * (1 - fi) * fj + W[j0 + 1, i0 + 1] * fi * fj)

def loft(bm, outline, grid, step=1.2, K=28):
    """The inflated profile as a loft of upright sections, back to front."""
    xa, xb = min(p[0] for p in outline), max(p[0] for p in outline)
    rings = []; x = xa + .3
    while x < xb - .2:
        hh = _hits(outline, (x, 0), (0, 1))
        if len(hh) >= 2:
            top, bot = hh[0], hh[-1]
            zs = [top + (bot - top) * (1 - math.cos(math.pi * i / K)) / 2 for i in range(K + 1)]
            side = [(_sample(grid, x, z), z) for z in zs]
            pts = side + [(-w, z) for w, z in side[-2:0:-1]]
            rings.append([bm.verts.new(px(x, z, w * PX)) for w, z in pts])
        x += step
    for a, b in zip(rings, rings[1:]):
        k = len(a)
        for i in range(k): bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

def bull_head(name='L12_Head'):
    """The bull's head and neck: the inflated profile, brows, cheeks and a broad muzzle
    with the nostrils, fused by a voxel remesh and smoothed."""
    bm = bmesh.new(); loft(bm, PROFILE, inflate(PROFILE, FRONT_W))
    def blob(c, r):   # an ellipsoid at a sheet point c = (x, y, lat px), radii in px (across, along, up)
        M = Matrix.Translation(px(c[0], c[1], c[2] * PX)) @ Matrix.Diagonal((r[0] * PX, r[1] * PX, r[2] * PX, 1))
        bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=1, matrix=M)
    for s in (1, -1):
        blob((754, 95, 26 * s), (9, 12, 7))        # brows over the eyes
        blob((795, 154, 11 * s), (9, 10, 8))       # the nostrils' wings
        blob((736, 70, 28 * s), (11, 11, 9))       # the horn bosses
    ob = obj_from_bm(name, bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.005); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=8, lambda_factor=.6, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.18); bake_mods(ob)
    for p in ob.data.polygons: p.use_smooth = True
    return ob

# The right horn's path (front-view x from the middle, side-view x, y), out from the
# horn boss, sweeping out and a little down, then up and forward to the tip.
HORN = [(36, 732, 70), (58, 737, 78), (80, 744, 82), (97, 752, 74), (106, 762, 56), (106, 774, 38), (100, 788, 22)]

def horns(name, sx=(1, -1)):
    lines = []
    for s in sx:
        pts = [px(sv, y, s * f * PX) for f, sv, y in HORN]
        out = []   # Catmull-Rom through the path
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
            for k in range(8):
                t = k / 8; out.append(tuple(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
        out.append(tuple(pts[-1])); lines.append(out)
    return curve_mesh(name, lines, 10 * PX, radii=lambda t: max(.04, (1 - t) ** .8 * (1 + .25 * (1 - t))), res=4)

def m_horn(name='Horn', tip='#2a2420', gilt=False):
    """Horn: pale and dull at the root, darkening to the tip (gilded for Asterion)."""
    m = Mat(name, res=512)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
    t = m.node('ShaderNodeMapRange', **{'From Min': 60 * PX, 'From Max': 104 * PX}); m.L.new(ax.outputs[0], t.inputs['Value'])
    up = m.node('ShaderNodeMapRange', **{'From Min': (GROUND - 70) * PX, 'From Max': (GROUND - 25) * PX}); m.L.new(sep.outputs['Z'], up.inputs['Value'])
    k = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(t.outputs[0], k.inputs[0]); m.L.new(up.outputs[0], k.inputs[1])
    rings = m.node('ShaderNodeTexWave', wave_type='RINGS', Scale=60.0, Distortion=2.0); m.L.new(m.coord.outputs['Object'], rings.inputs['Vector'])
    base = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb('#9a8f7c')), (.7, srgb('#c4b9a2'))])
    col = m.mix(base.outputs['Color'], srgb('#c9a24a') if gilt else srgb(tip), k.outputs[0])
    if gilt: m.bsdf.inputs['Metallic'].default_value = 0
    m.set(col, .5, rings.outputs['Fac'], .25, .001)
    return m

def m_hide(name, base, light, dark, muzzle=None, stars=0.0, res=2048):
    """Short, dark bull's hair over the skin: mottled, darker in the recesses, combed
    strands in the bump; a greyer muzzle on the head; pale flecks for Asterion."""
    m = Mat(name, res=res)
    col = m.ramp(m.noise(7, 5, .6).outputs['Fac'], [(.3, srgb(dark)), (.55, srgb(base)), (.8, srgb(light))]).outputs['Color']
    geo = m.node('ShaderNodeNewGeometry')
    cav = m.ramp(geo.outputs['Pointiness'], [(.46, (1, 1, 1)), (.51, (0, 0, 0))])
    col = m.mix(col, srgb(dark), m.mix((0, 0, 0), cav.outputs['Color'], .6))
    if muzzle:   # the front of the face, below the eyes
        sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
        fy = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', **{'From Min': px(778, 0).y, 'From Max': px(792, 0).y}); m.L.new(sep.outputs['Y'], fy.inputs['Value'])
        col = m.mix(col, srgb(muzzle), fy.outputs[0])
    if stars:
        vor = m.node('ShaderNodeTexVoronoi', Scale=70.0, feature='F1'); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
        dots = m.ramp(vor.outputs['Distance'], [(.0, (1, 1, 1)), (.06, (1, 1, 1)), (.1, (0, 0, 0))])
        few = m.ramp(m.noise(30, 2, .5).outputs['Fac'], [(.55, (0, 0, 0)), (.62, (1, 1, 1))])
        col = m.mix(col, srgb('#d9d2c4'), m.mix((0, 0, 0), m.mix(dots.outputs['Color'], (0, 0, 0), few.outputs['Color'], 'MULTIPLY'), stars))
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (240, 240, 60)
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=7.0, Detail=4.0); m.L.new(mp.outputs['Vector'], hair.inputs['Vector'])
    m.set(col, .78, hair.outputs['Fac'], .35, .0012)
    return m


# ── The body ────────────────────────────────────────────────────────────────
def _ramp(x, a, b):
    t = min(1, max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t)

def broaden(body, J, wide=.24, deep=.32):
    """The sheet's bull-man is far broader and deeper through the chest than the
    infantry man: widen the shoulders (carrying the arms out with them) and deepen the
    trunk alone, both fading in above the waist; the joints move with the skin."""
    def f(p):
        up = _ramp(p.z, .9, 1.32)
        x = p.x * (1 + wide * up)
        y = p.y * (1 + deep * up * (1 - _ramp(abs(x), .2, .34)))
        return V((x, y, p.z))
    for v in body.data.vertices: v.co = f(v.co)
    for j in J: J[j] = f(J[j])
    body.data.update()

def behead(body, J):
    """Remove the man's head and upper neck: the bull's neck takes their place."""
    bm = bmesh.new(); bm.from_mesh(body.data)
    zc = J['neck'].z - .01
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > zc and abs(f.calc_center_median().x) < .14], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(body.data); bm.free()

HAFT = dict(mcp=1.25, pip=1.5, dip=.75, thumb=(.25, .5), tuck=True)   # closed round a haft

def settle(head, body, z0=1.3, z1=1.52, gap=.004):
    """Lay the bottom of the bull's neck on the man's shoulders, chest and back: below z1
    its skin is drawn onto the body's surface, wholly so by z0, so the two meet without
    a ledge. What lies inside the body is left there, out of sight."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    for v in head.data.vertices:
        t = 1 - _ramp(v.co.z, z0, z1)
        if t <= 0: continue
        loc, no, fi, d = bvh.find_nearest(v.co)
        if loc is not None and (v.co - loc).dot(no) > 0: v.co = v.co.lerp(loc + no * gap, t)
    head.data.update()

def weight_head(head, J):
    """The bull's head follows the head bone, its neck the neck bone, its base the chest."""
    for n in ('chest', 'neck', 'head'): head.vertex_groups.new(name=n)
    z0, z1, z2 = J['l-shoulder'].z + .02, J['neck'].z + .03, J['head'].z
    for v in head.data.vertices:
        z = v.co.z; up = _ramp(z, z1, z2); mid = _ramp(z, z0, z1)
        w = {'head': up, 'neck': mid * (1 - up), 'chest': 1 - mid}
        for n, x in w.items():
            if x > .01: head.vertex_groups[n].add([v.index], x, 'REPLACE')


# ── Head, tail and hair ─────────────────────────────────────────────────────
def face_kit(head, add, tag, hide, hair):
    """Eyes, ears, a curly forelock between the horns and the shaggy hair along the hump,
    for one head (tag L12_ or L3_)."""
    bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())
    eye_m = Mat('BullEye', res=0); eye_m.set(srgb('#0d0907'), .12)
    for s, n in ((1, 'L'), (-1, 'R')):
        o = px(757, 113, s * .4); h = bvh.ray_cast(o, V((-s, 0, 0)), 1)
        if h[0]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.0125, segments=20, ring_count=12, location=h[0] - h[1] * .005)
            e = bpy.context.object; e.name = f'{tag}Eye{n}'; add(e, eye_m, 'head')
        o = px(737, 106, s * .4); h = bvh.ray_cast(o, V((-s, 0, 0)), 1)
        if h[0]:
            ear = lathe(f'{tag}Ear{n}', [(0, 0), (.024, .012), (.028, .042), (.021, .072), (.008, .094), (0, .1)], 16)
            ear.scale = (1, .42, 1); bake_obj_xform(ear)
            d = V((s * .92, .12, -.36)).normalized(); fwd = V((0, -1, .2)); fwd = (fwd - d * fwd.dot(d)).normalized()
            M = Matrix((fwd.cross(d), fwd, d)).transposed().to_4x4(); M.translation = h[0] - d * .01
            ear.matrix_world = M; bpy.context.view_layer.update(); bake_obj_xform(ear); add(ear, hide, 'head')
    rnd = random.Random(12); roots = []
    for k in range(70):   # the forelock: curls on the poll between the horn bosses
        x, lat = rnd.uniform(712, 742), rnd.uniform(-22, 22)
        o = px(x, 0, lat * PX); o.z = 3; h = bvh.ray_cast(o, V((0, 0, -1)), 4)
        if h[0] and h[0].z > (GROUND - 80) * PX: roots.append((h[0] - h[1] * .002, (h[1] + V((0, -.5, .2))).normalized()))
    add(HR.strands(f'{tag}Forelock', roots, .06, .5, .45, 13, .0042, 5, .45), hair, 'head')
    roots = []
    for v in head.data.vertices:   # shaggy hair along the hump and the back of the neck
        if v.co.y > .02 and v.co.z > J_HUMP and rnd.random() < .05 and (v.normal.y > .25 or v.normal.z > .5):
            roots.append((v.co - v.normal * .002, (v.normal * .7 + V((0, .35, -.55))).normalized()))
    add(HR.strands(f'{tag}Mane', roots, .055, .6, .5, 14, .004, 4, .5), hair, 'neck')

J_HUMP = 1.38   # the shaggy hair starts above this height on the back of the neck

def tail(body, add, tag, hide, hair):
    """A short bull's tail from the base of the spine, hanging to the knee with a tuft."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    h = bvh.ray_cast(V((0, 1, 1.0)), V((0, -1, 0)), 2)
    r = h[0] if h[0] else V((0, .14, 1.0))
    pts = [r - V((0, .01, 0)), r + V((0, .04, -.05)), r + V((0, .07, -.16)), r + V((.004, .075, -.32)), r + V((.01, .07, -.46))]
    add(curve_mesh(f'{tag}Tail', [[tuple(p) for p in pts]], .016, radii=lambda t: 1 - .45 * t, res=3), hide, 'hips')
    end = pts[-1]; roots = []
    for k in range(60):
        a = k / 60 * 2 * math.pi; z = random.uniform(0, .07)
        roots.append((end + V((math.cos(a) * .008, math.sin(a) * .008, z)), V((math.cos(a) * .2, math.sin(a) * .2 + .05, -1)).normalized()))
    add(HR.strands(f'{tag}TailTuft', roots, .13, .3, .25, 15, .0045, 5, .5), hair, 'hips')


# ── Kit ─────────────────────────────────────────────────────────────────────
def limb_band(name, bvh, a, b, t, width, off=.005, n=40):
    """A band round a limb at fraction t from joint a to joint b, laid on the skin."""
    c = a.lerp(b, t); u = (b - a).normalized(); e1 = u.orthogonal().normalized(); e2 = u.cross(e1); pts = []
    for i in range(n + 1):
        ang = 2 * math.pi * i / n; d = e1 * math.cos(ang) + e2 * math.sin(ang)
        h = bvh.ray_cast(c + d * .3, -d, .35)
        pts.append(((h[0] + h[1] * off) if h[0] else c + d * .05, h[1] if h[0] else d))
    return P.ribbon(name, pts, width, .003)

def labrys(tag, haft, W, Hh, mats, double=False):
    """A double axe built about its grip (the origin): the haft runs along -Z to the head,
    a short butt along +Z; the two blades lie in the XZ plane, curved edges outward and
    hollow sides towards the haft."""
    wood, bronze = mats; zc = -haft + .11; out = []
    out.append((lathe(f'{tag}Haft', [(0, .13), (.016, .12), (.0175, 0), (.0175, -haft + .02), (.012, -haft - .02), (0, -haft - .025)], 14), wood))
    out.append((lathe(f'{tag}Socket', [(.019, zc - .07), (.03, zc - .055), (.03, zc + .055), (.019, zc + .07)], 16), bronze))
    out.append((lathe(f'{tag}Ferrule', [(.0185, .09), (.022, .1), (.022, .13), (0, .14)], 14), bronze))
    bm = bmesh.new()
    for z0, k in ([(zc - .12, .8), (zc + .1, 1.0)] if double else [(zc, 1.0)]):
        w, h = W * k, Hh * k
        for sgn in (1, -1):
            side = [(.026, .045)] + [(.026 + (w - .026) * t, .045 + (h - .045) * t ** 1.9) for t in (.2, .4, .6, .8, 1)]   # hollow sides
            edge = [(w + .06 * (1 - (z / h) ** 2), z) for z in [h - 2 * h * i / 12 for i in range(1, 12)]]
            poly = side + edge + [(x, -z) for x, z in reversed(side)]
            vs = [bm.verts.new((sgn * x, 0, z0 + z)) for x, z in poly]
            f = bm.faces.new(vs if sgn > 0 else vs[::-1])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bl = obj_from_bm(f'{tag}Blades', bm, smooth=False)
    mod(bl, 'SOLIDIFY', thickness=.012, offset=0); mod(bl, 'BEVEL', width=.004, segments=2, limit_method='ANGLE'); bake_mods(bl)
    out.append((bl, bronze))
    return out

def fig8_shield(name, depth=.1, n=(28, 36)):
    """The Mycenaean figure-of-eight shield: two lobes of oxhide on a frame, pinched at
    the waist, both bulging outward. Built facing +Z, its height along Y."""
    lobes = [(.21, .23), (-.19, .25)]   # (centre, radius) along the height
    def hw(v):
        w = max(math.sqrt(max(0, r * r - (v - c) ** 2)) for c, r in lobes)
        return w * (1 - .22 * math.exp(-((v - .01) / .06) ** 2))
    def bulge(v): return max(math.sqrt(max(0, 1 - ((v - c) / r) ** 2)) for c, r in lobes)
    nu, nv = n; bm = bmesh.new(); grid = []; v0, v1 = lobes[1][0] - lobes[1][1], lobes[0][0] + lobes[0][1]
    for j in range(nv + 1):
        v = v0 + (v1 - v0) * j / nv; w = hw(v); row = []
        for i in range(nu + 1):
            u = (i / nu * 2 - 1); x = u * w
            row.append(bm.verts.new((x, v, depth * math.sqrt(max(0, 1 - u * u)) * bulge(v))))
        grid.append(row)
    uv = bm.loops.layers.uv.new('UV')
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))): lp[uv].uv = (a / nu, b / nv)
    rim = [tuple(grid[j][nu].co) for j in range(nv + 1)] + [tuple(grid[j][0].co) for j in range(nv, -1, -1)]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.014, offset=-1); bake_mods(ob)
    return ob, curve_mesh(name + 'Rim', [rim], .011, cyclic=True)

def m_cowhide(name='Oxhide'):
    m = Mat(name, res=1024)
    patches = m.ramp(m.noise(3.5, 3, .55).outputs['Fac'], [(.47, (0, 0, 0)), (.5, (1, 1, 1))])
    col = m.mix(srgb('#e8dcc4'), srgb('#5a3420'), patches.outputs['Color'])
    col = m.mix(col, srgb('#2a1a10'), m.ramp(m.noise(9, 4, .6).outputs['Fac'], [(.62, (0, 0, 0)), (.68, (1, 1, 1))]).outputs['Color'])
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (200, 60, 200)
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=1.0, Distortion=6.0); m.L.new(mp.outputs['Vector'], hair.inputs['Vector'])
    m.set(col, .8, hair.outputs['Fac'], .3, .0015)
    return m

def m_gold(name='Gold'):
    m = Mat(name, metal=1.0, res=256)
    col = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb('#a8812e')), (.7, srgb('#e0b85a'))])
    m.set(col.outputs['Color'], .28, m.noise(90, 3).outputs['Fac'], .15, .0008)
    return m

def kit(bodies, heads, J):
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    body = bodies[12]; dg = bpy.context.evaluated_depsgraph_get()
    hair = H.m_flat('BullHair', '#140e0a', .7); hair3 = H.m_flat('StarHair', '#0a0808', .7)
    hides = {12: m_hide('Hide12', '#3b2a20', '#5a4535', '#1e150f', res=512), 3: m_hide('Hide3', '#1a1512', '#2c2420', '#0a0807', stars=.8, res=512)}
    for lv, tag in ((12, 'L12_'), (3, 'L3_')):
        face_kit(heads[lv], add, tag, hides[lv], hair if lv == 12 else hair3)
        tail(body, add, tag, hides[lv], hair if lv == 12 else hair3)
    add(horns('L12_Horns'), m_horn('Horn'), 'head'); add(horns('L3_Horns'), m_horn('GiltHorn', gilt=True), 'head')

    # Kilts, flaps and belts
    linen = lambda n: H.m_linen_band(n, '#d9caa6', '#5c3a22', 1.0, .81)
    for tag, mat, flap_stops in (('L12_', linen('Kilt12'), [(0, '#d9caa6'), (.4, '#6b3d22'), (.6, '#a2552e'), (.8, '#d9caa6')]),
                                 ('L3_', H.m_linen_band('Kilt3', '#7d1a16', '#c9a24a', 1.0, .81), [(0, '#7d1a16'), (.45, '#c9a24a'), (.65, '#7d1a16')])):
        sk = H.chiton(tag + 'Kilt', '#ffffff', 1.0, .79)
        for v in sk.data.vertices: v.co.x *= 1.1; v.co.y *= 1.15; v.co.x *= 1 - .2 * (1 - (v.co.z - .79) / .21)   # less flare at the hem
        H.drape(tag + 'Kilt', sk, lambda c: c.z > .985, body, 70, .25, .004); add(sk, mat, 'skin')
        sf = Surf([sk, body]); bm = bmesh.new(); rows = []
        for j in range(15):
            z = 1.0 - .36 * j / 14; row = []
            for i in range(7):
                x = -.1 + .2 * i / 6; h = sf.hit(V((x, 0, max(z, .8))), V((0, -1, 0)), .6)
                y = (h[0].y if h else -.2) - .012
                row.append(bm.verts.new((x, y - max(0, .8 - z) * .05, z)))
            rows.append(row)
        for j in range(14):
            for i in range(6): bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
        fl = obj_from_bm(tag + 'Flap', bm); mod(fl, 'SOLIDIFY', thickness=.004); bake_mods(fl)
        add(fl, P.m_pattern(tag + 'FlapCloth', flap_stops, 22.0, 30.0, .05), 'skin')
        if tag == 'L12_':
            pts = P.ring_on(sf, .995, .008, 64); pts.append(pts[0])
            add(P.ribbon('L1_Belt', pts, .075, .005), H.m_leather('BeltLeather', '#4a2e1a'), 'skin')
            pts = P.ring_on(sf, .995, .009, 64); pts.append(pts[0])
            add(P.ribbon('L2_Belt', pts, .08, .004), H.m_bronze('BeltBronze', .25, 512, engrave=.3), 'skin')

    # The Labrys Guard: crossed harness straps, armbands and the figure-of-eight shield
    bvh = BVHTree.FromObject(body, dg); sh = J['l-shoulder']; leather = H.m_leather('Harness', '#3a2414')
    for s in (1, -1):
        for face, sgn in (('F', -1), ('B', 1)):
            pts = []
            for i in range(21):
                t = i / 20; x = s * (.13 - .3 * t); z = sh.z + .03 - (sh.z + .03 - 1.03) * t
                h = bvh.ray_cast(V((x, sgn * 1, z)), V((0, -sgn, 0)), 2)
                if h[0]: pts.append((h[0] + h[1] * .02, h[1]))
            add(P.ribbon(f'L2_Strap{face}{"LR"[s < 0]}', pts, .045, .004), leather, 'skin')
        top = []
        for i in range(9):
            y = -.12 + .26 * i / 8; h = bvh.ray_cast(V((s * .13, y, 3)), V((0, 0, -1)), 4)
            if h[0]: top.append((h[0] + h[1] * .02, h[1]))
        add(P.ribbon(f'L2_StrapTop{"LR"[s < 0]}', top, .045, .004), leather, 'skin')
        side = 'l' if s > 0 else 'r'; el, wr = J[f'{side}-elbow'], J[f'{side}-hand']
        for k, t in enumerate((.6, .7, .8)):
            add(limb_band(f'L2_Armband{side.upper()}{k}', bvh, el, wr, t, .022, .006), H.m_bronze('ArmBronze', .2, 256), f'forearm.{side.upper()}')
        add(limb_band(f'L3_Armlet{side.upper()}', bvh, el, wr, .76, .06, .007), m_gold(), f'forearm.{side.upper()}')
    sh_ob, rim = fig8_shield('L2_Shield')
    zc = (GROUND - 268) * PX; h = bvh.ray_cast(V((0, 1, zc)), V((0, -1, 0)), 2)
    yb = h[0].y if h[0] else .18
    M = Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0))).to_4x4(); M.translation = V((0, yb + .035, zc))   # its height up, its face out behind
    for o in (sh_ob, rim): o.matrix_world = M; bpy.context.view_layer.update(); bake_obj_xform(o)
    add(sh_ob, m_cowhide(), 'chest'); add(rim, H.m_leather('ShieldRim', '#3a2414'), 'chest')

    # Asterion: a Dendra-style corselet with shoulder guards and a girdle, greaves
    dendra = H.m_bronze('Dendra', .2, 1024, engrave=.2)
    cor = region_shell('L3_Corselet', body, lambda c: 1.04 < c.z < sh.z + .03 and abs(c.x) < .24, .022, 4, .5, guard=.018)
    mod(cor, 'SOLIDIFY', thickness=.004, offset=1); mod(cor, 'SUBSURF', levels=1, render_levels=1); bake_mods(cor); add(cor, dendra, 'skin')
    gd = region_shell('L3_ShoulderGuards', body, lambda c: c.z > sh.z - .07 and .13 < abs(c.x) < .33 and abs(c.y) < .16, .036, 3, .5, guard=.03)
    mod(gd, 'SOLIDIFY', thickness=.004, offset=1); mod(gd, 'BEVEL', width=.002, segments=2, limit_method='ANGLE'); bake_mods(gd); add(gd, dendra, 'skin')
    gi = region_shell('L3_Girdle', body, lambda c: .95 < c.z < 1.06 and abs(c.x) < .3, .03, 3, .5, guard=.026)
    mod(gi, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(gi); add(gi, dendra, 'skin')
    for side in ('l', 'r'):
        kz, az = J[f'{side}-knee'].z, J[f'{side}-ankle'].z
        g = region_shell(f'L3_Greave{side.upper()}', body, (lambda kz, az, sx: lambda c: az + .05 < c.z < kz + .07 and c.x * sx > .03)(kz, az, 1 if side == 'l' else -1), .006, 1, .4, guard=.005)
        mod(g, 'SOLIDIFY', thickness=.003, offset=1); mod(g, 'SUBSURF', levels=1, render_levels=1); bake_mods(g); add(g, dendra, f'shin.{side.upper()}')

    # The labrys of each tier, put into the right fist (rest pose): the haft through the
    # fist along the knuckle line, the blades square to the palm
    wrist, along, palm = T.hand_frame(J, 'r')
    mcp = sum((J[f'r-finger-{k}-1'] for k in (2, 3, 4, 5)), V()) / 4
    k = (J['r-finger-5-1'] - J['r-finger-2-1']).normalized(); k = (k - along * k.dot(along)).normalized()
    grip = mcp + palm * .021 - along * .006
    bx = k.cross(palm).normalized()
    Mg = Matrix((bx, k.cross(bx), k)).transposed().to_4x4(); Mg.translation = grip
    ash = H.m_wood('LabrysHaft')
    for tag, haft, W, Hh, bronze, double in (('L1_', .74, .19, .17, H.m_bronze('Labrys1', .3, 512), False),
                                             ('L2_', .98, .21, .19, H.m_bronze('Labrys2', .2, 512, engrave=.45), False),
                                             ('L3_', 1.12, .24, .21, m_gold('LabrysGilt'), True)):
        for o, mt in labrys(tag + 'Labrys', haft, W, Hh, (ash, bronze), double):
            o.matrix_world = Mg @ o.matrix_world; bpy.context.view_layer.update(); bake_obj_xform(o); add(o, mt, 'hand.R')
    return out


# ── Poses and moves ─────────────────────────────────────────────────────────
def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-1, .7, -.2), axe=(0, .15, -1), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': axe, 'fist': 0, **kw}
    def armL(w, hint=(1, .5, -.2), **kw): return {'w': SL + V(w), 'hint': hint, 'fist': 0, **kw}
    base = {'hips': {'loc': (0, -.01, .01)}, 'chest': {'rot': (.07, 0, 0)}, 'neck': {'rot': (-.04, 0, 0)}, 'head': {'rot': (-.02, 0, 0)},
            'ik_foot.L': {'loc': (-.05, -.04, 0)}, 'ik_foot.R': {'loc': (.05, .04, 0)},
            'armR': armR((-.17, -.17, -.36), axe=(.3, .1, -1)), 'armL': armL((.15, -.04, -.5))}   # the axe held out to the side, its head leaning away
    def st(**over):
        Pp = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): Pp[k] = v if k.startswith('arm') or k == 'knee' else {**Pp.get(k, {}), **v}
        return Pp
    return st, armR, armL

def actions(rig, J):
    """Idle, Walk, Cleave (an overhead chop with the labrys), Gore (head down, a lunge
    on the horns and a toss), Hit and Death."""
    st, armR, armL = poses(J); mk = H.make_action; A = []
    A.append(mk(rig, 'Idle', [(1, st()), (30, st(chest={'rot': (.09, 0, .02)}, head={'rot': (.04, 0, .1)}, neck={'rot': (-.02, 0, .05)})), (60, st())]))
    W = lambda fl, fr, zl, zr, hz, tw: st(**{'ik_foot.L': {'loc': (-.05, fl, zl)}, 'ik_foot.R': {'loc': (.05, fr, zr)},
                                            'hips': {'loc': (0, -.01 + hz, .01), 'rot': (0, tw * .09, 0)}, 'chest': {'rot': (.08, -tw * .1, 0)},
                                            'armL': armL((.15, .12 * tw, -.49)), 'armR': armR((-.17, -.17 - .04 * tw, -.36), axe=(.3, .1, -1))})
    A.append(mk(rig, 'Walk', [(1, W(-.25, .23, 0, 0, -.02, 1)), (9, W(-.01, -.01, 0, .1, .014, 0)), (17, W(.23, -.25, 0, 0, -.02, -1)),
                              (25, W(-.01, -.01, .1, 0, .014, 0)), (33, W(-.25, .23, 0, 0, -.02, 1))]))
    step = {'ik_foot.L': {'loc': (-.05, -.34, 0)}}
    A.append(mk(rig, 'Cleave', [
        (1, st()),
        (12, st(chest={'rot': (-.14, 0, .34)}, hips={'loc': (0, -.01, .04)}, head={'rot': (-.1, 0, -.15)},
                armR=armR((.02, .14, .5), hint=(-1, .3, .4), axe=(0, -.55, -.85)), armL=armL((.2, -.25, -.25)))),
        (17, st(chest={'rot': (.42, 0, -.16)}, hips={'loc': (0, -.1, -.08)}, head={'rot': (.12, 0, .05)}, **step,
                armR=armR((.06, -.5, -.2), hint=(-1, .2, .3), axe=(0, .75, .65)), armL=armL((.18, -.15, -.42)))),
        (24, st(chest={'rot': (.38, 0, -.14)}, hips={'loc': (0, -.09, -.07)}, **step,
                armR=armR((.06, -.48, -.24), hint=(-1, .2, .3), axe=(0, .75, .65)), armL=armL((.18, -.15, -.42)))),
        (36, st())]))
    A.append(mk(rig, 'Gore', [
        (1, st()),
        (10, st(chest={'rot': (.4, 0, 0)}, neck={'rot': (.25, 0, 0)}, head={'rot': (.35, 0, 0)}, hips={'loc': (0, -.1, -.04)}, **step,
                armR=armR((-.12, .1, -.42)), armL=armL((.16, .1, -.45)))),
        (16, st(root={'loc': (0, -.3, 0)}, chest={'rot': (.48, 0, 0)}, neck={'rot': (.3, 0, 0)}, head={'rot': (.42, 0, 0)}, hips={'loc': (0, -.12, -.12)},
                **{'ik_foot.L': {'loc': (-.05, -.5, 0)}, 'ik_foot.R': {'loc': (.05, .12, 0)}}, armR=armR((-.12, .16, -.4)), armL=armL((.16, .16, -.42)))),
        (21, st(root={'loc': (0, -.36, 0)}, chest={'rot': (.12, 0, 0)}, neck={'rot': (-.2, 0, 0)}, head={'rot': (-.35, 0, .1)}, hips={'loc': (0, -.05, -.1)},
                **{'ik_foot.L': {'loc': (-.05, -.5, 0)}, 'ik_foot.R': {'loc': (.05, .12, 0)}})),
        (32, st())]))
    A.append(mk(rig, 'Hit', [(1, st()),
        (5, st(chest={'rot': (-.22, 0, .18)}, head={'rot': (-.3, 0, .15)}, hips={'loc': (0, -.01, .07)}, armL=armL((.18, .08, -.44)))),
        (11, st(chest={'rot': (-.05, 0, .06)}, head={'rot': (-.1, 0, 0)})), (22, st())]))
    kneel = dict(hips={'loc': (0, -.38, .05)}, chest={'rot': (.3, 0, .05)}, head={'rot': (.3, 0, 0)},
                 **{'ik_foot.L': {'loc': (-.05, .1, 0)}, 'ik_foot.R': {'loc': (.05, .14, 0)}}, armR=armR((-.1, -.2, -.45), axe=(0, -.3, -1)), knee=(.1, -1, 0))
    fall = dict(chest={'rot': (-.1, 0, .05)}, head={'rot': (-.3, 0, .2)}, hips={'loc': (0, -.05, 0)},
                armR=armR((-.3, .05, -.22), hint=(-1, .2, -.3), axe=(.3, -.9, -.2)), armL=armL((.3, .05, -.25), hint=(1, .2, -.3)))
    A.append(mk(rig, 'Death', [(1, st()),
        (9, st(chest={'rot': (.15, 0, .1)}, head={'rot': (.3, 0, 0)}, hips={'loc': (0, -.06, 0)})),
        (20, st(**kneel)),
        (31, st(root={'loc': (0, .33, 0), 'rot': (-1.3, 0, .05)}, **fall)),
        (37, st(root={'loc': (0, .37, 0), 'rot': (-1.55, 0, .05)}, **fall)),
        (56, st(root={'loc': (0, .37, 0), 'rot': (-1.52, 0, .05)}, **fall))]))
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    body, J = H.build_body()
    broaden(body, J); T.define(body, J); behead(body, J)
    T.clench(body, J, 'l', **T.FIST); T.clench(body, J, 'r', **HAFT)
    body.name = 'L12_Body'
    head = bull_head('L12_Head'); settle(head, body)
    b3 = link(body.copy()); b3.data = body.data.copy(); b3.name = 'L3_Body'
    h3 = link(head.copy()); h3.data = head.data.copy(); h3.name = 'L3_Head'
    items = kit({12: body, 3: b3}, {12: head, 3: h3}, J)
    items['L12_Body'] = (body, m_hide('BodyHide12', '#3b2a20', '#5a4535', '#1e150f'), 'body')
    items['L3_Body'] = (b3, m_hide('BodyHide3', '#1a1512', '#2c2420', '#0a0807', stars=.8), 'body')
    items['L12_Head'] = (head, m_hide('HeadHide12', '#30221a', '#4a3a2e', '#160f0a', muzzle='#4c4442', res=1024), 'head-mesh')
    items['L3_Head'] = (h3, m_hide('HeadHide3', '#16120f', '#262019', '#090706', muzzle='#2e2a28', stars=.8, res=1024), 'head-mesh')
    H.bake_textures(items)
    rig = H.build_armature(H.skeleton_spec(J), J); rig.name = 'MinotaurRig'; rig.data.name = 'MinotaurRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    T.copy_weights(body, b3)
    for ob in (b3, head, h3):
        if ob is not b3: weight_head(ob, J)
        mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
        m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    for name, (ob, mt, bind) in items.items():
        if bind in ('body', 'head-mesh'): continue
        if bind == 'skin':
            H.bind_skin(ob, rig, body)
            if 'Kilt' in name or 'Flap' in name or 'Belt' in name or 'Strap' in name or 'Girdle' in name or 'Corselet' in name:
                T.trunk_only(ob, ('hips', 'spine', 'chest', 'neck') if 'Kilt' not in name and 'Flap' not in name else ('hips', 'spine'))
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    return rig, actions(rig, J)

def renders(rig):
    from PIL import Image
    shots = []
    for lv in (1, 2, 3):
        k = SCALE * (1.08 if lv == 3 else 1); rig.scale = (k, k, k)
        p = os.path.join(OUT, f'minotaur_L{lv}.png')
        H.render(rig, p, 'Idle', 1, lv, cam=((2.6, -4.6, 1.75), (84, 0, 29)), res=(520, 760), samples=24); shots.append(p)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'minotaur_lineup.png'))
    rig.scale = (SCALE,) * 3

if __name__ == '__main__':
    rig, acts = build()
    rig.scale = (SCALE,) * 3; H._upd()
    H.export(rig, os.path.join(OUT, 'minotaur.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'minotaur.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
