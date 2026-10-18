"""The war chariot of the Kemet Chariot line, built in Blender: a module for chariot.py.

A New Kingdom chariot c. 1300 BC, after the reliefs of Ramesses II and the chariots of
Tutankhamun: a light car of bent wood on a D-shaped floor of woven leather straps, open at
the back; the siding is a curved top rail over a solid front and low side panels, with a
wide opening in each side behind the front; two six-spoked wheels on an axle under the
back of the floor; a pole running forward from under the car and curving up to a bowed
yoke over the horses' withers. The siding comes in rawhide and wicker or sheathed in gold
with reliefs (drawn with PIL, baked like the other materials). The gear on its sides: a
bow case with a quiver strapped to it and a second quiver, or a rack of spare spears.

Frame: the car is built about its axle (the axle's middle at y = 0, z = R_W), facing -Y
like the horses; chariot.py moves it into place. add(ob, material, bind) as in the unit
builds, bind being 'car', 'wheel.L' or 'wheel.R'.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
V = Vector
import hoplite as H
import peltast as P
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, Mat, m_leather
from peltast import curve_mesh, bake_obj_xform

# ── Dimensions (m) ──────────────────────────────────────────────────────────
R_W = .43                      # wheel radius: the wheels are 0.86 m across
TRACK = .8                     # each wheel's middle plane out from the car's middle
AXLE_HALF = .95                # the axle runs out past the hubs to the linch pins
W = .52                        # the floor's half width
Y_REAR, Y_FRONT = .1, -.58     # the floor's straight back edge (just behind the axle) and the front of the D
Z_FLOOR = .5                   # the top of the floor
H_RAIL = .78                   # the top rail over the floor
BAND = .3                      # the low side panels
POST_BEND = .2                 # radius of the bend where the rear posts turn into the rail


# ── Materials ───────────────────────────────────────────────────────────────
def m_bentwood(name='BentWood', light='#c39a66', dark='#8a6238', res=512):
    """Light bent wood (elm and ash): long fine streaks and a soft sheen."""
    m = Mat(name, res=res)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (40, 40, 40)
    w = m.node('ShaderNodeTexWave', wave_type='RINGS', Scale=.6, Distortion=6.0, Detail=5.0); m.L.new(mp.outputs['Vector'], w.inputs['Vector'])
    base = m.ramp(m.noise(9, 4, .55).outputs['Fac'], [(.3, srgb(dark)), (.75, srgb(light))])
    col = m.mix(base.outputs['Color'], tuple(x * .72 for x in srgb(dark)), m.ramp(w.outputs['Fac'], [(.55, (0, 0, 0)), (.95, (1, 1, 1))]).outputs['Color'])
    m.set(col, .5, w.outputs['Fac'], .12, .001)
    return m

def m_gold(name='Gold', res=512, worn=.4):
    """Beaten gold leaf over wood: warm, bright, a little uneven."""
    m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(14, 5, .6).outputs['Fac'], [(.3, srgb('#b8862e')), (.6, srgb('#dcae4a')), (.85, srgb('#f0cd6e'))])
    geo = m.node('ShaderNodeNewGeometry')
    rub = m.ramp(geo.outputs['Pointiness'], [(.5, (0, 0, 0)), (.58, (1, 1, 1))])
    col = m.mix(col.outputs['Color'], srgb('#f6dc8a'), m.mix((0, 0, 0), rub.outputs['Color'], worn))
    rough = m.ramp(m.noise(60, 3).outputs['Fac'], [(.3, (.22, .22, .22)), (.7, (.36, .36, .36))])
    m.set(col, rough.outputs['Color'], m.noise(160, 3).outputs['Fac'], .08, .0006)
    return m

def m_straps(name='FloorStraps', res=1024):
    """The floor: rawhide straps woven over and under on the D-shaped frame (UV in metres x 1)."""
    m = Mat(name, res=res)
    k = 26.0   # straps per metre
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=k / 2); m.L.new(m.coord.outputs['UV'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=k / 2); m.L.new(m.coord.outputs['UV'], w2.inputs['Vector'])
    chk = m.node('ShaderNodeTexChecker', Scale=k); m.L.new(m.coord.outputs['UV'], chk.inputs['Vector'])
    weave = m.mix(w1.outputs['Fac'], w2.outputs['Fac'], chk.outputs['Fac'])
    col = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb('#6e4a2a')), (.7, srgb('#9a6e42'))])
    col = m.mix(col.outputs['Color'], srgb('#2a1a0e'), m.ramp(weave, [(0, (1, 1, 1)), (.22, (0, 0, 0))]).outputs['Color'])
    m.set(col, .7, weave, .5, .002)
    return m

def m_panel(name='SidePanel', res=1024):
    """The wooden car's siding: rawhide stretched over the frame above, wicker below (UV v up the panel)."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['UV'], sep.inputs['Vector'])
    hide = m.ramp(m.noise(12, 5, .6).outputs['Fac'], [(.3, srgb('#a07446')), (.7, srgb('#c49764'))])
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=110.0); m.L.new(m.coord.outputs['UV'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=24.0); m.L.new(m.coord.outputs['UV'], w2.inputs['Vector'])
    chk = m.node('ShaderNodeTexChecker', Scale=48.0); m.L.new(m.coord.outputs['UV'], chk.inputs['Vector'])
    weave = m.mix(w1.outputs['Fac'], w2.outputs['Fac'], chk.outputs['Fac'])
    wick = m.mix(m.ramp(m.noise(25, 4, .6).outputs['Fac'], [(.3, srgb('#6b4a26')), (.7, srgb('#9c7644'))]).outputs['Color'], srgb('#3a2814'),
                 m.ramp(weave, [(0, (1, 1, 1)), (.25, (0, 0, 0))]).outputs['Color'])
    low = m.node('ShaderNodeMath', operation='LESS_THAN'); m.L.new(sep.outputs['Y'], low.inputs[0]); low.inputs[1].default_value = BAND / H_RAIL
    edge = m.node('ShaderNodeMath', operation='LESS_THAN'); m.L.new(sep.outputs['Y'], edge.inputs[0]); edge.inputs[1].default_value = BAND / H_RAIL + .025
    col = m.mix(hide.outputs['Color'], srgb('#5a3a1e'), edge.outputs[0])   # a dark binding over the join
    col = m.mix(col, wick, low.outputs[0])
    bump = m.mix(m.noise(90, 3).outputs['Fac'], weave, low.outputs[0])
    m.set(col, .7, bump, .35, .0015)
    return m

def relief_art(path, S=(2048, 640)):
    """Height map of the gold siding's reliefs, in the panel's UV (u along the siding from
    the rear left corner round the front to the rear right, v up from the floor): borders
    of rosettes and spirals, a frieze of bound captives along each side, the king in his
    chariot over his enemies on each flank, and on the front the union of the Two Lands
    (sema-tawy) under a winged sun disc."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = S; im = Image.new('L', S, 0); d = ImageDraw.Draw(im)
    Y = lambda v: h - v * h                    # v up the panel -> image row
    hi, mid = 235, 150
    def band(v0, v1): d.rectangle((0, Y(v1), w, Y(v0)), fill=60); d.line((0, Y(v1), w, Y(v1)), fill=hi, width=5); d.line((0, Y(v0), w, Y(v0)), fill=hi, width=5)
    # borders: rosettes along the foot, a running spiral under the rail
    band(.0, .085)
    for i in range(int(w / 54)):
        cx, cy = 27 + i * 54, Y(.0425)
        for k in range(8):
            a = k / 8 * 2 * math.pi; d.ellipse((cx + math.cos(a) * 13 - 7, cy + math.sin(a) * 13 - 7, cx + math.cos(a) * 13 + 7, cy + math.sin(a) * 13 + 7), fill=hi)
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=255)
    band(.36, .4)
    for i in range(int(w / 30)):
        x = 15 + i * 30; d.arc((x - 12, Y(.392), x + 12, Y(.368)), 0, 300, fill=hi, width=4)
    band(.93, 1.0)
    for i in range(int(w / 40)):
        x = 20 + i * 40; d.ellipse((x - 12, Y(.985), x + 12, Y(.945)), outline=hi, width=4); d.ellipse((x - 4, Y(.97), x + 4, Y(.96)), fill=hi)
    def captive(x, base, s, face=1):
        """A kneeling bound captive in profile, arms tied behind at the elbows."""
        u = lambda a, b: (x + a * s * face, Y(base) - b * s)
        d.ellipse((u(-9, 92)[0] - 9 * s, u(0, 101)[1] - 9 * s, u(-9, 92)[0] + 9 * s, u(0, 101)[1] + 9 * s), fill=hi)   # head
        d.polygon([u(-14, 82), u(-2, 82), u(4, 50), u(-2, 34), u(-20, 34), u(-20, 52)], fill=hi)                          # torso
        d.polygon([u(-20, 34), u(14, 30), u(16, 0), u(6, 0), u(4, 20), u(-22, 22)], fill=hi)                                 # kneeling legs
        d.line([u(-6, 78), u(-24, 62), u(-28, 72)], fill=mid, width=max(3, int(5 * s)))                                     # arms bound behind
        d.line([u(-24, 62), u(-12, 58)], fill=255, width=max(2, int(3 * s)))
    def horse_chariot(x, base, s, face=1):
        """The king in his chariot behind a galloping horse, drawing his bow."""
        u = lambda a, b: (x + a * s * face, Y(base) - b * s)
        d.polygon([u(0, 40), u(70, 44), u(96, 70), u(112, 96), u(118, 88), u(104, 62), u(92, 42), u(84, 22), u(110, 4), u(100, 0), u(76, 16),
                   u(44, 16), u(18, 6), u(-6, 0), u(-10, 6), u(10, 20), u(4, 34)], fill=hi)                                     # horse in the flying gallop
        for k in range(5): d.line([u(84 + k * 5, 104 - k), u(96 + k * 6, 130 + k * 3)], fill=hi, width=max(2, int(4 * s)))      # plumes
        d.ellipse((u(-46, 28)[0] - 26 * s, u(0, 28)[1] - 26 * s, u(-46, 28)[0] + 26 * s, u(0, 28)[1] + 26 * s), outline=hi, width=max(3, int(5 * s)))   # wheel
        d.polygon([u(-60, 40), u(-12, 40), u(-14, 74), u(-56, 64)], fill=mid)                                                 # car
        d.line([u(-12, 46), u(10, 40)], fill=hi, width=max(3, int(4 * s)))                                                   # pole
        d.polygon([u(-50, 64), u(-34, 64), u(-30, 126), u(-46, 126)], fill=hi)                                               # the king
        d.ellipse((u(-42, 134)[0] - 9 * s, u(0, 134)[1] - 9 * s, u(-42, 134)[0] + 9 * s, u(0, 134)[1] + 9 * s), fill=hi)
        d.polygon([u(-46, 140), u(-40, 158), u(-34, 140)], fill=hi)                                                          # blue crown
        d.arc((u(-6, 150)[0] - 30 * s, u(0, 150)[1] - 40 * s, u(-6, 150)[0] + 30 * s, u(0, 150)[1] + 40 * s), -70 if face > 0 else 110, 70 if face > 0 else 250, fill=hi, width=max(3, int(4 * s)))
        d.line([u(-34, 116), u(-6, 112)], fill=hi, width=max(3, int(4 * s)))
    # the low frieze of captives runs the whole siding
    n = 30
    for i in range(n):
        x = (i + .5) / n * w; face = 1 if x < w / 2 else -1   # they face the front
        captive(x, .1, 2.1, face)
    # the flanks: the king's chariot over fallen enemies, facing forward
    for u0, face in ((.12, -1), (.88, 1)):
        x = u0 * w
        horse_chariot(x, .42, 1.8, -face)
        for k in range(3):
            xx = x + (k - 1) * 70 - face * 60; d.polygon([(xx - 30, Y(.43)), (xx + 30, Y(.44)), (xx + 26, Y(.47)), (xx - 28, Y(.455))], fill=mid)   # fallen foes
    # the front: sema-tawy flanked by captives tied to it, under a winged disc
    c = w / 2
    d.ellipse((c - 28, Y(.86) - 28, c + 28, Y(.86) + 28), fill=255)
    for sx in (-1, 1):
        d.polygon([(c + sx * 26, Y(.88)), (c + sx * 230, Y(.92)), (c + sx * 250, Y(.86)), (c + sx * 200, Y(.82)), (c + sx * 26, Y(.83))], fill=hi)
        for k in range(6): d.line([(c + sx * (60 + k * 30), Y(.835)), (c + sx * (70 + k * 30), Y(.905))], fill=mid, width=4)
    d.rectangle((c - 16, Y(.76), c + 16, Y(.44)), fill=hi)                     # the windpipe and lungs of the sign
    d.ellipse((c - 50, Y(.8), c + 50, Y(.7)), fill=hi)
    for sx in (-1, 1):
        for k in range(5):   # lotus (south) and papyrus (north) stems knotted round it
            yy = .48 + k * .055
            d.line([(c, Y(yy)), (c + sx * (80 + k * 18), Y(yy + .12))], fill=hi, width=7)
            d.ellipse((c + sx * (80 + k * 18) - 14, Y(yy + .12) - 14, c + sx * (80 + k * 18) + 14, Y(yy + .12) + 14), fill=255)
        for k in range(2): captive(c + sx * (190 + k * 120), .44, 2.6, -sx)
    im = im.filter(ImageFilter.GaussianBlur(2.2))
    im.save(path)
    img = bpy.data.images.load(path); img.colorspace_settings.name = 'Non-Color'; img.pack()
    return img

def m_relief(img, name='GoldRelief', res=2048):
    """Gold sheathing with the reliefs beaten up from behind: raised work catches the light,
    the ground between is darker and duller (UV-mapped height image)."""
    m = Mat(name, metal=1.0, res=res)
    t = m.node('ShaderNodeTexImage'); t.image = img; m.L.new(m.coord.outputs['UV'], t.inputs['Vector'])
    base = m.ramp(m.noise(10, 5, .6).outputs['Fac'], [(.3, srgb('#a8782a')), (.7, srgb('#d9a945'))])
    col = m.mix(base.outputs['Color'], srgb('#7a531c'), m.ramp(t.outputs['Color'], [(.05, (1, 1, 1)), (.35, (0, 0, 0))]).outputs['Color'])
    col = m.mix(col, srgb('#f3d47c'), m.ramp(t.outputs['Color'], [(.6, (0, 0, 0)), (.95, (1, 1, 1))]).outputs['Color'])
    rough = m.ramp(t.outputs['Color'], [(.1, (.42, .42, .42)), (.7, (.24, .24, .24))])
    m.set(col, rough.outputs['Color'], t.outputs['Color'], .9, .004)
    return m


# ── Shapes ──────────────────────────────────────────────────────────────────
def outline(n=120):
    """The floor's D from the rear left corner, forward and round the front to the rear right
    corner, resampled to even spacing: (points, cumulative lengths)."""
    raw = []
    for i in range(801):
        a = math.pi * i / 800; c, s = math.cos(a), math.sin(a)
        raw.append(V((W * math.copysign(abs(c) ** (2 / 3.2), c), Y_REAR - (Y_REAR - Y_FRONT) * abs(s) ** (2 / 3.2), 0)))
    acc = [0.0]
    for a, b in zip(raw, raw[1:]): acc.append(acc[-1] + (b - a).length)
    L = acc[-1]; pts, j = [], 0
    for i in range(n + 1):
        t = L * i / n
        while j < len(acc) - 2 and acc[j + 1] < t: j += 1
        f = (t - acc[j]) / max(1e-9, acc[j + 1] - acc[j]); pts.append(raw[j].lerp(raw[j + 1], f))
    return pts, [L * i / n for i in range(n + 1)]

def smooth(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a))); return x * x * (3 - 2 * x)

def panel_top(u):
    """How high the siding is filled at u (0 = rear left corner, .5 = the front, 1 = rear right),
    as a fraction of the rail's height: full across the front, dropping to the low panel along
    a curve that opens each side behind the front."""
    q = min(u, 1 - u)
    return BAND / H_RAIL + (1 - BAND / H_RAIL) * smooth(.07, .23, q)

def rail_path(pts, lens):
    """The top rail: up each rear post, bent forward over POST_BEND, along the outline at the
    rail's height."""
    zt = Z_FLOOR + H_RAIL; out = []
    def post(c, fwd, rev):
        seg = [c + V((0, 0, Z_FLOOR + .02))] + [c + V((0, 0, zt - POST_BEND))]
        seg += [c + fwd * POST_BEND * (1 - math.cos(a)) + V((0, 0, zt - POST_BEND + POST_BEND * math.sin(a))) for a in [math.pi / 2 * k / 8 for k in range(1, 9)]]
        return seg[::-1] if rev else seg
    out += post(pts[0], (pts[3] - pts[0]).normalized(), False)
    out += [p + V((0, 0, zt)) for p, s in zip(pts, lens) if POST_BEND + .01 < s < lens[-1] - POST_BEND - .01]
    out += post(pts[-1], (pts[-4] - pts[-1]).normalized(), True)
    return out

def siding(name, pts, lens):
    """The siding as one sheet: a column at each outline point from the floor up to the
    panel's top there, UV u along the outline, v up the rail's height."""
    bm = bmesh.new(); uvs = []; cols = []; L = lens[-1]
    for p, s in zip(pts, lens):
        u = s / L; top = panel_top(u); k = 10
        col = []
        for j in range(k + 1):
            v = top * j / k; col.append(bm.verts.new(p + V((0, 0, Z_FLOOR + H_RAIL * v)))); uvs.append((u, v))
        cols.append(col)
    bm.verts.ensure_lookup_table()
    uvl = bm.loops.layers.uv.new('UV'); uvmap = {v: uv for v, uv in zip(bm.verts, uvs)}
    for a, b in zip(cols, cols[1:]):
        for j in range(len(a) - 1):
            f = bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
            for lp in f.loops: lp[uvl].uv = uvmap[lp.vert]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm)
    # the faces must point outward: test one at the front
    me = ob.data; me.update()
    fr = min(me.polygons, key=lambda pl: pl.center.y)
    if fr.normal.y > 0: me.flip_normals()
    return ob

def brace_path(pts, lens, side):
    """The curved brace along the top of the low panel and up the front edge of the
    side's opening to the rail (side +1 left, -1 right)."""
    L = lens[-1]; out = []
    for p, s in zip(pts, lens):
        u = s / L
        if (u < .5) != (side > 0): continue
        q = min(u, 1 - u)
        if POST_BEND * .5 / L < q < .235:
            out.append(p + V((0, 0, Z_FLOOR + H_RAIL * panel_top(u))))
    return out if side > 0 else out[::-1]

def tube(name, pts, r, cyclic=False, radii=None):
    return curve_mesh(name, [[tuple(p) for p in pts]], r, cyclic=cyclic, radii=radii, res=2)

def lashings(name, path, at, r, n=5, w=.006):
    """Rawhide lashings: thin rings round a tube at fractions `at` of its length."""
    acc = [0.0]
    for a, b in zip(path, path[1:]): acc.append(acc[-1] + (b - a).length)
    bm = bmesh.new()
    for f in at:
        t = acc[-1] * f; j = max(0, min(len(acc) - 2, next((i for i in range(len(acc) - 1) if acc[i + 1] >= t), len(acc) - 2)))
        p = path[j].lerp(path[j + 1], (t - acc[j]) / max(1e-9, acc[j + 1] - acc[j])); d = (path[j + 1] - path[j]).normalized()
        for k in range(n):
            q = p + d * (k - (n - 1) / 2) * w * 1.6
            M = Matrix.Translation(q) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
            bmesh.ops.create_cone(bm, cap_ends=False, segments=14, radius1=r, radius2=r, depth=w, matrix=M)
    return obj_from_bm(name, bm)

def wheel(name, mats, add, bind, side):
    """A six-spoked wheel about its hub, the axle along X: felloe and rawhide tyre, spokes
    swelling at the nave, a long nave and a linch pin at its outer end."""
    wood, hide, dark = mats; s = 1 if side == 'L' else -1
    rf0, rf1 = R_W - .058, R_W - .012          # felloe, inside to out
    bm = bmesh.new(); segs = 72
    prof = [(rf0, -.024), (rf1, -.026), (rf1, .026), (rf0, .024)]
    rings = [[bm.verts.new((x, math.cos(a) * r, math.sin(a) * r)) for r, x in prof] for a in [2 * math.pi * i / segs for i in range(segs)]]
    for i in range(segs):
        a, b = rings[i], rings[(i + 1) % segs]
        for k in range(4): bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    fel = obj_from_bm(name + 'Felloe', bm); mod(fel, 'BEVEL', width=.004, segments=2); bake_mods(fel)
    tyre = lathe(name + 'Tyre', [(R_W - .014, -.021), (R_W - .002, -.02), (R_W, 0), (R_W - .002, .02), (R_W - .014, .021)], 72)
    tyre.rotation_euler = (0, math.pi / 2, 0); bake_obj_xform(tyre)
    bm = bmesh.new()
    for k in range(6):   # spokes: thick at the nave, slimmer out to the felloe, set a little dished
        a = 2 * math.pi * k / 6 + math.pi / 6; d = V((0, math.cos(a), math.sin(a)))
        p0 = d * .05 + V((s * -.012, 0, 0)); p1 = d * (rf0 + .01) + V((s * .01, 0, 0))
        n = 8
        for j in range(n):
            t0, t1 = j / n, (j + 1) / n; q0, q1 = p0.lerp(p1, t0), p0.lerp(p1, t1)
            r0, r1 = .019 - .007 * t0 ** .6, .019 - .007 * t1 ** .6
            M = Matrix.Translation((q0 + q1) / 2) @ (q1 - q0).to_track_quat('Z', 'Y').to_matrix().to_4x4()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r0, radius2=r1, depth=(q1 - q0).length * 1.02, matrix=M)
    sp = obj_from_bm(name + 'Spokes', bm)
    nave = lathe(name + 'Nave', [(0, -.13), (.032, -.13), (.042, -.08), (.056, -.02), (.058, .0), (.05, .05), (.036, .09), (.03, .1), (0, .1)], 28)
    nave.rotation_euler = (0, s * math.pi / 2, 0); bake_obj_xform(nave)
    pin = lathe(name + 'LinchPin', [(0, -.07), (.008, -.07), (.008, .05), (.014, .06), (.012, .075), (0, .08)], 10)
    pin.location = (s * .12, 0, 0); bake_obj_xform(pin)
    binding = lathe(name + 'NaveBinding', [(.057, -.03), (.06, -.022), (.06, .022), (.057, .03)], 28)
    binding.rotation_euler = (0, math.pi / 2, 0); bake_obj_xform(binding)
    for o, mt in ((fel, wood), (tyre, hide), (sp, wood), (nave, wood), (pin, dark), (binding, hide)): add(o, mt, bind)
    return nave


# ── The car ─────────────────────────────────────────────────────────────────
def build_car(add, yoke, horse_x, out_dir):
    """The car, wheels, axle, pole and yoke. yoke: (y, z) of the yoke's middle over the
    withers; horse_x: each horse's distance out from the pole. Returns the gilded car's
    relief material (shared with nothing else) and the rail path."""
    wood, hide = m_bentwood(), m_leather('Rawhide', '#6a4a30', 256)
    dark = m_leather('DarkWood', '#3a2616', 256)
    gold = m_gold('Gilt', 512)
    pts, lens = outline()
    # floor: a frame round the D and woven straps across it, two bearers under them
    frame = pts + [pts[0]]
    add(tube('FloorFrame', [p + V((0, 0, Z_FLOOR - .018)) for p in frame], .02, cyclic=True), wood, 'car')
    bm = bmesh.new(); vs = [bm.verts.new(p + V((0, 0, Z_FLOOR - .012))) for p in pts]
    f = bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=[f])
    uvl = bm.loops.layers.uv.new('UV')
    for fc in bm.faces:
        for lp in fc.loops: lp[uvl].uv = (lp.vert.co.x + .5, lp.vert.co.y + .5)
    floor = obj_from_bm('FloorStraps', bm, False); me = floor.data
    for pl in me.polygons:
        if pl.normal.z < 0: pl.flip()
    mod(floor, 'SOLIDIFY', thickness=.012, offset=-1); bake_mods(floor)
    add(floor, m_straps(), 'car')
    for x in (-.3, .3):
        yf = min(pts, key=lambda p: abs(p.x - x)).y
        add(tube(f'FloorBearer{"LR"[x < 0]}', [V((x, Y_REAR, Z_FLOOR - .04)), V((x, yf + .02, Z_FLOOR - .04))], .016), wood, 'car')
    # siding: the rail, the front post, the braces round the side openings, the panels
    rail = rail_path(pts, lens)
    add(tube('L0124_Rail', rail, .021), wood, 'car'); add(tube('L35_Rail', rail, .023), gold, 'car')
    add(lashings('L0124_RailLashings', rail, [.035, .12, .3, .5, .7, .88, .965], .024), hide, 'car')
    fpost = [V((0, Y_FRONT - .012, Z_FLOOR - .01)), V((0, Y_FRONT - .016, Z_FLOOR + H_RAIL))]
    add(tube('L0124_FrontPost', fpost, .02), wood, 'car'); add(tube('L35_FrontPost', fpost, .022), gold, 'car')
    for side in (1, -1):
        br = brace_path(pts, lens, side); nm = 'L' if side > 0 else 'R'
        add(tube(f'L0124_Brace{nm}', br, .015), wood, 'car'); add(tube(f'L35_Brace{nm}', br, .017), gold, 'car')
    wood_panel = siding('L0124_Siding', pts, lens)
    mod(wood_panel, 'SOLIDIFY', thickness=.01, offset=-1); bake_mods(wood_panel); add(wood_panel, m_panel(), 'car')
    gold_panel = siding('L35_Siding', pts, lens)
    mod(gold_panel, 'SOLIDIFY', thickness=.012, offset=-1); bake_mods(gold_panel)
    relief = m_relief(relief_art(os.path.join(out_dir, 'relief.png')))
    add(gold_panel, relief, 'car')
    # gilded fittings of the veteran's car: caps on the rail's bends and bands round the posts
    bm = bmesh.new()
    for f_ in (.0, 1.0, .09, .91, .5):
        acc = [0.0]
        for a, b in zip(rail, rail[1:]): acc.append(acc[-1] + (b - a).length)
        t = acc[-1] * f_; j = min(len(acc) - 2, next((i for i in range(len(acc) - 1) if acc[i + 1] >= t), len(acc) - 2))
        p = rail[j].lerp(rail[j + 1], (t - acc[j]) / max(1e-9, acc[j + 1] - acc[j])); d = (rail[j + 1] - rail[j]).normalized()
        M = Matrix.Translation(p) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=.027, radius2=.027, depth=.05, matrix=M)
    add(obj_from_bm('L2_GiltBands', bm), gold, 'car')
    # wheels, axle
    for side, sx in (('L', 1), ('R', -1)):
        nave = wheel(f'Wheel{side}', (wood, hide, dark), add, f'wheel.{side}', side)
        for o in [o for o in bpy.data.objects if o.name.startswith(f'Wheel{side}')]:
            o.location.x += sx * TRACK; bake_obj_xform(o)
        cap = lathe(f'L235_HubCap{side}', [(0, .095), (.034, .095), (.037, .07), (.033, .05), (0, .05)], 24)
        cap.rotation_euler = (0, sx * math.pi / 2, 0); cap.location = (sx * TRACK, 0, 0); bake_obj_xform(cap)
        add(cap, gold, f'wheel.{side}')
    axle = lathe('Axle', [(0, -AXLE_HALF), (.026, -AXLE_HALF), (.03, -TRACK + .14), (.036, -W), (.036, W), (.03, TRACK - .14), (.026, AXLE_HALF), (0, AXLE_HALF)], 16)
    axle.rotation_euler = (0, math.pi / 2, 0); bake_obj_xform(axle); add(axle, wood, 'car')
    for o in [o for o in bpy.data.objects if o.name.startswith('Wheel')]:
        o.location.z += R_W; bake_obj_xform(o)
    for o in [axle] + [o for o in bpy.data.objects if 'HubCap' in o.name]:
        if o is axle: o.location.z += R_W
        else: o.location.z += R_W
        bake_obj_xform(o)
    # the pole: lashed on the axle, under the floor, rising between the horses to the yoke
    yy, yz = yoke
    pole = [V((0, .06, R_W + .02)), V((0, Y_FRONT + .05, Z_FLOOR - .055))]
    y0, z0 = Y_FRONT + .05, Z_FLOOR - .055
    for i in range(1, 25):   # a long straight rise, then a firmer bend up into the yoke
        t = i / 24; y = y0 + (yy + .04 - y0) * t
        pole.append(V((0, y, z0 + (yz - .05 - z0) * (.35 * t + .65 * t ** 4))))
    pole.append(V((0, yy - .03, yz + .02)))
    add(tube('Pole', pole, .032, radii=lambda t: 1 - .2 * t), wood, 'car')
    add(lashings('PoleLashings', pole, [.08, .2, .93, .975], .036, 6), hide, 'car')
    # the yoke: a bowed bar over both withers with its ends turned up
    yk = []
    for i in range(41):
        x = -.78 + 1.56 * i / 40; u = abs(x) / .78
        yk.append(V((x, yy, yz + .03 * (1 - (x / horse_x) ** 2) * (abs(x) < horse_x) - .0 + .09 * smooth(.82, 1, u) ** 1.5)))
    add(tube('Yoke', yk, .026, radii=lambda t: .8 + .2 * math.sin(math.pi * t)), wood, 'car')
    add(lashings('YokeLashings', yk, [.5 - horse_x / 1.56 - .02, .5 - horse_x / 1.56 + .02, .48, .52, .5 + horse_x / 1.56 - .02, .5 + horse_x / 1.56 + .02], .03, 5), hide, 'car')
    for sx in (1, -1):
        knob = lathe(f'YokeKnob{"LR"[sx < 0]}', [(0, 0), (.022, .005), (.03, .025), (.02, .045), (0, .05)], 16)
        knob.location = yk[0 if sx < 0 else -1] + V((0, 0, -.005)); bake_obj_xform(knob); add(knob, gold, 'car')
    return rail, (wood, hide, gold, dark)


# ── Gear on the car's sides ─────────────────────────────────────────────────
def arrows(name, n, base, axis, spread, length, seed, mats, fletch=True):
    """A sheaf of arrows standing in a quiver: shafts from base along axis, heads hidden,
    feathers showing."""
    reed, feather = mats; rnd = random.Random(seed); bm, bf = bmesh.new(), bmesh.new()
    ax = axis.normalized(); side = ax.orthogonal().normalized(); up = ax.cross(side)
    for i in range(n):
        o = base + side * rnd.uniform(-spread, spread) + up * rnd.uniform(-spread * .6, spread * .6)
        d = (ax + side * rnd.uniform(-.06, .06) + up * rnd.uniform(-.06, .06)).normalized()
        L = length * rnd.uniform(.97, 1.03)
        M = Matrix.Translation(o + d * L / 2) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=.0045, radius2=.0045, depth=L, matrix=M)
        if fletch:
            for k in range(3):
                a = 2 * math.pi * k / 3 + rnd.uniform(0, 1); r = (side * math.cos(a) + up * math.sin(a))
                tip = o + d * L
                q = [tip - d * .02, tip - d * .13, tip - d * .12 + r * .016, tip - d * .03 + r * .014]
                bf.faces.new([bf.verts.new(p) for p in q])
    sh = obj_from_bm(name + 'Shafts', bm)
    fl = obj_from_bm(name + 'Fletching', bf); mod(fl, 'SOLIDIFY', thickness=.0015); bake_mods(fl)
    return [(sh, reed), (fl, feather)]

def case(name, a, b, r0, r1, flat=.55, segs=20):
    """A leather case from a (closed bottom) to b (open top), round tapering to flattened."""
    d = (b - a); L = d.length
    ob = lathe(name, [(0, 0), (r0 * .8, 0), (r0, .03), (r1, L - .01), (r1 * .96, L)], segs)
    ob.scale = (1, flat, 1)
    ob.matrix_world = Matrix.Translation(a) @ d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Diagonal((1, flat, 1, 1))
    bpy.context.view_layer.update(); bake_obj_xform(ob)
    return ob

def gear(add, mats, bow_mesh):
    """The archers' bow case and quivers (L123_) and the spear crews' rack (L45_).
    bow_mesh: a function making a spare bow (name) about its grip, limbs along Z."""
    wood, hide, gold, dark = mats
    red = m_leather('CaseLeather', '#7a3e24'); reed = H.m_flat('Reed', '#b49a6a', .6); feather = H.m_flat('Fletch', '#e8e0d0', .8)
    bronze = H.m_bronze('RackBronze', .25, 256)
    xo = W + .055
    # left side: the bow case slung slanting back up the car's side, a quiver strapped on it
    a, b = V((xo, Y_FRONT + .16, Z_FLOOR + .18)), V((xo, Y_REAR - .02, Z_FLOOR + .84))
    add(case('L123_BowCase', a, b, .04, .075, .5), red, 'car')
    bow = bow_mesh('L123_SpareBow'); d = (b - a).normalized()
    bow.matrix_world = Matrix.Translation(a + (b - a) * .72 + V((.012, 0, 0))) @ d.to_track_quat('Z', 'X').to_matrix().to_4x4() @ Matrix.Rotation(-.08, 4, 'X')
    bpy.context.view_layer.update(); bake_obj_xform(bow)
    add(bow, H.m_flat('SpareBowWood', '#7a4a26', .5), 'car')
    qa, qb = a + V((.05, .06, .02)), b + V((.05, -.06, -.1))
    add(case('L123_QuiverL', qa, qb, .034, .045, .8), red, 'car')
    for o, mt in arrows('L123_ArrowsL', 9, qb - (qb - qa).normalized() * .45, qb - qa, .02, .58, 3, (reed, feather)): add(o, mt, 'car')
    for k, f_ in enumerate((.25, .7)):   # straps round case and quiver, gilded for the veterans
        p = a.lerp(b, f_) + V((.025, 0, 0))
        st = lathe(f'L123_CaseStrap{k}', [(.085, -.012), (.09, 0), (.085, .012)], 20); st.scale = (1, .6, 1)
        st.matrix_world = Matrix.Translation(p) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Diagonal((1, .62, 1, 1)); bpy.context.view_layer.update(); bake_obj_xform(st)
        add(st, hide, 'car')
        g = st.copy(); g.data = st.data.copy(); g.name = f'L23_CaseGilt{k}'; link(g)
        for v in g.data.vertices: v.co += (v.co - p) * .06
        add(g, gold, 'car')
    # right side: a second quiver by the rear post
    qa, qb = V((-xo, Y_FRONT + .3, Z_FLOOR + .1)), V((-xo - .01, Y_REAR + .01, Z_FLOOR + .74))
    add(case('L123_QuiverR', qa, qb, .036, .048, .8), red, 'car')
    for o, mt in arrows('L123_ArrowsR', 10, qb - (qb - qa).normalized() * .45, qb - qa, .022, .58, 4, (reed, feather)): add(o, mt, 'car')
    # the spear crews' rack: three spare spears slanting up the left side in a sleeve and a band
    a, b = V((xo, Y_FRONT + .12, Z_FLOOR + .12)), V((xo + .01, Y_REAR + .05, Z_FLOOR + .86))
    add(case('L45_RackSleeve', a, a + (b - a).normalized() * .3, .045, .05, .55), red, 'car')
    d = (b - a).normalized(); side = V((1, 0, 0)).cross(d).normalized()
    for i in range(3):
        o = a + side * (i - 1) * .032 + V((.012 * (i % 2), 0, 0)) + d * .02
        dd = (d + side * (i - 1) * .03).normalized()
        sh = lathe(f'L45_RackShaft{i}', [(0, 0), (.011, .005), (.012, 1.0), (.009, 1.42), (0, 1.43)], 10)
        hd = lathe(f'L45_RackHead{i}', [(.009, 1.39), (.017, 1.43), (.024, 1.5), (.012, 1.6), (0, 1.66)], 8); hd.scale = (1, .3, 1)
        for o2, mt in ((sh, wood), (hd, bronze)):
            o2.matrix_world = Matrix.Translation(o) @ dd.to_track_quat('Z', 'X').to_matrix().to_4x4() @ o2.matrix_basis
            bpy.context.view_layer.update(); bake_obj_xform(o2); add(o2, mt, 'car')
    band = lathe('L45_RackBand', [(.07, -.015), (.075, 0), (.07, .015)], 20)
    band.matrix_world = Matrix.Translation(a + d * .62) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Diagonal((1, .55, 1, 1))
    bpy.context.view_layer.update(); bake_obj_xform(band); add(band, hide, 'car')
