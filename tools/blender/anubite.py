"""Realistic Anubite Warden line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/anubite.py third_party/makehuman assets/models [--renders]

The jackal-headed guardians of the Duat, after the reference sheets in refs/anubite: the
MakeHuman man of the infantry lines, lean and muscular, with black skin as Anubis is
painted in the tombs, his head replaced by a black jackal's head and neck. The head and
neck are traced from the side view of the first sheet (PROFILE, in its pixels), inflated
into round sections (a Poisson solve inside the outline, as for the Minotaur) and sized at
each height to the front view's widths (FRONT_W), then fused by a voxel remesh and laid
onto the shoulders under the broad collar. The build is made at the infantry's scale and
exported at 2.1 m to the top of the head (the ears stand above it).
  L1 Anubite Warden          a white pleated kilt with an embroidered apron and a sash,
                             a broad bead collar, sandals, a bronze khopesh in the right
                             hand, the left hand open
  L2 Veteran Anubite Warden  as L1 with a corselet of feather-shaped bronze scales, gold
                             armlets and a gold wristguard, a cowhide shield strapped to
                             the left forearm and a longer khopesh
  L3 Elite Anubite Warden    a gilded scale corselet, a broad collar of gold and lapis
                             lazuli, gold armlets and wristguards, a gilded khopesh in each
                             hand
Node tags: the head, its fur, ears, eyes and nose, the kilt, apron, sash and sandals are worn
by every tier; L12_Body (the left hand open) by the first two and L3_Body (both hands closed)
by the Elite; L23_ (armlets, the right wristguard) by the last two; L1_, L2_ and L3_ (each
tier's collar laid on what it wears, corselets, khopeshes, the shield) by one tier each.
The fists are bent into the mesh as for Talos, closed round the khopesh grips. Clips: Idle,
Walk, Cleave (the right blade cuts down from over the shoulder, then the left arm sweeps
across: the Elite's second blade, the Veteran's shield, the Warden's open hand), Block, Hit
and Death.
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
import minotaur as M
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat
from peltast import curve_mesh, bake_obj_xform, Surf
import horse as HR

# Lean and muscular, after the sheet: long-limbed, narrow-waisted, the muscles drawn clearly.
H.TARGETS = [('caucasian-male-young.target', .3), ('african-male-young.target', .6), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .4), ('universal-male-young-maxmuscle-minweight.target', .6)]
H.HEIGHT = 1.76
OUT = H.OUT
HEIGHT = 2.1                   # to the top of the head, after the sheet
SCALE = HEIGHT / H.HEIGHT      # the export's scale
random.seed(41)


# ── The jackal's head and neck, traced from the sheet ───────────────────────
# Side view of refs/anubite/anubite-1.png, facing right: the ground at y = 734, the top of
# the head (between the ears) at y = 88.5, which is put at the infantry man's full height;
# x = 688 lies over the middle of the man's chest. Front view: the head's middle at x = 242.5.
PX = H.HEIGHT / (734 - 88.5)
X0, GROUND, FX0 = 688, 734, 242.5
def px(x, y, lat=0.0): return V((lat, (X0 - x) * PX, (GROUND - y) * PX))

# Head and neck in profile, from under the collar at the back, up the back of the neck,
# over the crown (under the ears), down the forehead to the stop, along the muzzle to the
# nose, under the closed jaws and down the throat (straight down under the collar, so every
# upright section crosses the outline only twice); the base lies inside the chest.
PROFILE = [(664, 236), (655, 214), (654, 196), (656, 180), (657, 172), (658, 165), (659, 158), (660, 150), (660, 140),
           (661, 132), (662, 126), (664, 120), (666, 115), (669, 109), (673, 104), (677, 99), (682, 94), (688, 91),
           (696, 89), (705, 88.5), (713, 89), (720, 91), (727, 94), (734, 98), (740, 101), (745, 105), (749, 109),
           (753, 115), (757, 120), (762, 124), (770, 128), (780, 132), (788, 136), (794, 139), (797, 142), (797, 146),
           (794, 150), (789, 155), (783, 159), (772, 160.5), (760, 161), (748, 161), (738, 162.5), (731, 165), (726, 170),
           (723, 176), (722, 184), (721, 196), (720, 210), (719, 222), (718, 236), (700, 240)]
# Full width in the front view at heights of the side view (px): the crown, the brows and
# eyes (the widest, with the cheeks' fur), the muzzle, then the thick neck widening into
# the shoulders under the collar.
FRONT_W = [(88, 30), (92, 44), (97, 58), (103, 70), (110, 78), (116, 78), (122, 75), (130, 71), (140, 68), (148, 64),
           (156, 60), (165, 60), (175, 62), (185, 64), (200, 68), (215, 74), (230, 80)]
# The muzzle is narrower than the inflation makes it: widths scaled along the side view.
MUZZLE_K = [(735, 1.0), (752, .97), (770, .88), (790, .8), (798, .74)]
EYE = (744, 118, 19)           # side-view x, y and the front view's distance from the middle (px)
EAR = (700, 93, 28.5)          # the ear's base: side-view x, y and its distance out (px)
EAR_TIP = (703, 28, 30.5)      # and its tip

def loft(bm, outline, grid, step=1.2, K=28):
    """The inflated profile as a loft of upright sections, back to front (as for the Minotaur),
    narrowed along the muzzle."""
    xa, xb = min(p[0] for p in outline), max(p[0] for p in outline)
    rings = []; x = xa + .3
    while x < xb - .2:
        hh = M._hits(outline, (x, 0), (0, 1))
        if len(hh) >= 2:
            top, bot = hh[0], hh[-1]; k = M._lerp(MUZZLE_K, x)
            zs = [top + (bot - top) * (1 - math.cos(math.pi * i / K)) / 2 for i in range(K + 1)]
            side = [(M._sample(grid, x, z) * k, z) for z in zs]
            pts = side + [(-w, z) for w, z in side[-2:0:-1]]
            rings.append([bm.verts.new(px(x, z, w * PX)) for w, z in pts])
        x += step
    for a, b in zip(rings, rings[1:]):
        k = len(a)
        for i in range(k): bm.faces.new((a[i], a[(i + 1) % k], b[(i + 1) % k], b[i]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])

def jackal_head(name='Head'):
    """The jackal's head and neck: the inflated profile with brows over the eyes, the cheek
    bones and the nose pad's bulk, fused by a voxel remesh and smoothed."""
    bm = bmesh.new(); loft(bm, PROFILE, M.inflate(PROFILE, FRONT_W))
    def blob(c, r):   # an ellipsoid at a sheet point c = (x, y, lat px), radii in px (across, along, up)
        Mx = Matrix.Translation(px(c[0], c[1], c[2] * PX)) @ Matrix.Diagonal((r[0] * PX, r[1] * PX, r[2] * PX, 1))
        bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=10, radius=1, matrix=Mx)
    for s in (1, -1):
        blob((739, 110, 19 * s), (6, 11, 4))       # brows over the eyes
        blob((722, 128, 25 * s), (7, 18, 10))      # the cheek bones
    ob = obj_from_bm(name, bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.004); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=8, lambda_factor=.6, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.2); bake_mods(ob)
    for p in ob.data.polygons: p.use_smooth = True
    return ob

def ear_frame(s):
    """The ear's foot, its axis to the tip, height, the way the cup opens (forward and a
    little outward) and the direction across it."""
    base, tip = px(EAR[0], EAR[1], s * EAR[2] * PX), px(EAR_TIP[0], EAR_TIP[1], s * EAR_TIP[2] * PX)
    up = (tip - base).normalized()
    opening = V((s * math.sin(math.radians(16)), -math.cos(math.radians(16)), 0)); opening = (opening - up * opening.dot(up)).normalized()
    return base, up, (tip - base).length, opening, up.cross(opening).normalized()

def ear_mesh(name, s, shrink=1.0, inset=0.0, solid=True):
    """One ear (s = 1 left, -1 right) traced from the sheet's front and side views: a tall
    pointed cone split open at the front, nearly as deep as it is wide at the foot, its wall
    thick and furred at the back and thinning to the rims and the tip; the foot sinks into
    the skull. Without `solid`, only the inside of the cup (for the lining), facing out of it."""
    base, up, Hh, opening, across = ear_frame(s)
    W0, D0 = 15 * PX * shrink, 21 * PX * shrink   # half-width and depth of the cup at the foot
    bm = bmesh.new(); nt, ns = 26, 14; inner, outer = [], []
    for j in range(nt + 1):
        t = -.16 + 1.16 * j / nt; tt = min(max(t, 0), 1)
        w = W0 * (1 - tt) ** .72 * (1 + .1 * math.sin(math.pi * tt)); d = D0 * (1 - tt) ** .8
        rin, rout = [], []
        for i in range(ns + 1):
            u = -1 + 2 * i / ns; c = math.sqrt(max(0, 1 - u * u))
            p = base + up * (t * Hh) + across * (u * w) + opening * (D0 * .5 - d * c + inset)
            rin.append(bm.verts.new(p))
            th = (1.2 + (2.2 + 3.5 * (1 - tt)) * c ** .7) * PX * (1 - .85 * tt ** 3)
            if solid: rout.append(bm.verts.new(p - opening * th * c + across * (u * th * .5)))
        inner.append(rin); outer.append(rout)
    for j in range(nt):
        for i in range(ns):
            bm.faces.new((inner[j][i], inner[j][i + 1], inner[j + 1][i + 1], inner[j + 1][i]))
            if solid: bm.faces.new((outer[j][i + 1], outer[j][i], outer[j + 1][i], outer[j + 1][i + 1]))
        if solid:
            for i, k in ((0, 1), (ns, -1)):   # the rims join inside and out
                q = (inner[j][i], outer[j][i], outer[j + 1][i], inner[j + 1][i])
                bm.faces.new(q if k > 0 else q[::-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if solid: bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    else:
        bm.normal_update()
        if sum((f.normal.dot(opening) for f in bm.faces), 0) < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    return obj_from_bm(name, bm), up, opening, across

def face_paint():
    """The markings of the face, painted in the side view's pixels: the gold lines round the
    eye (the brow line and the long lower line of the tomb paintings), a tan patch over the
    brow, and the dark line of the mouth. RGB with alpha; projected across the head."""
    from PIL import Image, ImageDraw, ImageFilter
    k = 8; x0, y0, x1, y1 = DECAL
    im = Image.new('RGBA', ((x1 - x0) * k, (y1 - y0) * k), (0, 0, 0, 0))
    q = lambda pts: [((x - x0) * k, (y - y0) * k) for x, y in pts]
    tan = Image.new('RGBA', im.size, (0, 0, 0, 0)); dt = ImageDraw.Draw(tan)
    dt.ellipse(q([(733, 106.5), (749, 112)]), fill=(110, 78, 44, 150))
    im = Image.alpha_composite(im, tan.filter(ImageFilter.GaussianBlur(k * 1.5)))
    d = ImageDraw.Draw(im); gold = (196, 158, 92, 255)
    d.line(q([(730, 112.8), (734.5, 111.2), (739, 110.3), (743.5, 110), (747.5, 110.8), (750, 112.6)]), fill=gold, width=int(k * .9), joint='curve')
    d.line(q([(729, 118.6), (733, 118.3), (737.5, 118.3), (741, 118.9), (744.5, 120.6), (747.5, 122.6)]), fill=gold, width=int(k * .8), joint='curve')
    d.ellipse(q([(739.8, 115), (748.4, 121.2)]), outline=gold, width=int(k * .5))
    d.line(q([(751, 151.6), (758, 152.6), (766, 153.6), (774, 154.4), (782, 154.6), (787, 153.8)]), fill=(4, 4, 4, 255), width=int(k * 1.1), joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(k * .12))
    p = os.path.join(OUT, 'anubite_face.png'); im.save(p)
    img = bpy.data.images.load(p); img.pack(); return img

DECAL = (700, 95, 805, 170)   # the painted region of the side view (px)

def m_fur(name, res=1024, cols=('#080707', '#121110', '#24211e'), tips='#37332f', decal=None):
    """Short black fur: mottled, darker in the recesses, greyer at the tips of the combed
    strands; the face's painted markings laid over the sides of the head."""
    m = Mat(name, res=res)
    col = m.ramp(m.noise(14, 5, .6).outputs['Fac'], [(.3, srgb(cols[0])), (.55, srgb(cols[1])), (.8, srgb(cols[2]))]).outputs['Color']
    geo = m.node('ShaderNodeNewGeometry')
    cav = m.ramp(geo.outputs['Pointiness'], [(.46, (1, 1, 1)), (.51, (0, 0, 0))])
    col = m.mix(col, srgb(cols[0]), m.mix((0, 0, 0), cav.outputs['Color'], .6))
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (260, 260, 70)
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=7.0, Detail=4.0); m.L.new(mp.outputs['Vector'], hair.inputs['Vector'])
    col = m.mix(col, srgb(tips), m.ramp(hair.outputs['Fac'], [(.62, (0, 0, 0)), (.95, (.55, .55, .55))]).outputs['Color'])
    if decal:   # projected along X from the side view's pixels, onto the sides of the head only
        sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
        x0, y0, x1, y1 = DECAL
        u = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(sep.outputs['Y'], u.inputs[0])
        u.inputs[1].default_value = -1 / (PX * (x1 - x0)); u.inputs[2].default_value = (X0 - x0) / (x1 - x0)
        v = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(sep.outputs['Z'], v.inputs[0])
        v.inputs[1].default_value = 1 / (PX * (y1 - y0)); v.inputs[2].default_value = 1 - (GROUND - y0) / (y1 - y0)
        uv = m.node('ShaderNodeCombineXYZ'); m.L.new(u.outputs[0], uv.inputs['X']); m.L.new(v.outputs[0], uv.inputs['Y'])
        tex = m.node('ShaderNodeTexImage'); tex.image = decal; tex.extension = 'CLIP'; m.L.new(uv.outputs[0], tex.inputs['Vector'])
        nsep = m.node('ShaderNodeSeparateXYZ'); m.L.new(geo.outputs['Normal'], nsep.inputs['Vector'])
        ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(nsep.outputs['X'], ax.inputs[0])
        side = m.node('ShaderNodeMapRange', **{'From Min': .12, 'From Max': .35}); m.L.new(ax.outputs[0], side.inputs['Value'])
        k = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(tex.outputs['Alpha'], k.inputs[0]); m.L.new(side.outputs[0], k.inputs[1])
        col = m.mix(col, tex.outputs['Color'], k.outputs[0])
    m.set(col, .74, hair.outputs['Fac'], .35, .0012)
    return m

def fur_strands(name, head):
    """Short fur standing from the head and neck, combed back over the skull and down the
    neck, thickest in the ruff behind the cheeks; not on the muzzle, round the eyes or on the
    throat under the collar. It softens the outline as the sheet's fur does."""
    rnd = random.Random(9); roots, scale = [], []
    eyes = [px(EYE[0], EYE[1], s * EYE[2] * PX) for s in (1, -1)]
    stop, top = px(752, 0).y, px(0, 92).z
    for v in head.data.vertices:
        p, n = v.co, v.normal
        if p.z < 1.47 or p.y < stop or any((p - e).length < .03 for e in eyes): continue
        if p.z > top - .005 and abs(p.x) > .02: continue          # under the ears
        ruff = M._ramp(abs(p.x), .02, .05) * M._ramp(-abs(p.z - 1.58), -.09, -.02)
        if rnd.random() > .1 + .25 * ruff: continue
        head_part = M._ramp(p.z, 1.6, 1.66)
        flow = V((0, .9, -.25)) * head_part + V((0, .15, -1)) * (1 - head_part)
        roots.append((p - n * .0015, (n * .65 + flow.normalized() * .75).normalized())); scale.append(.7 + .7 * ruff)
    return HR.strands(name, roots, .016, .25, .25, 23, .0011, 4, .7, scale)

def m_eye(name='JackalEye', r=.0125):
    """A jackal's eye: dark amber, nearly all iris, the pupil black and round."""
    em = Mat(name, res=128); k = 56
    grad = em.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
    mp = em.node('ShaderNodeMapping'); em.L.new(em.coord.outputs['Object'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (k, k, k); mp.inputs['Location'].default_value = (0, r * k, 0)
    em.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
    col = em.ramp(grad.outputs['Fac'], [(.0, srgb('#b8aa8c')), (.3, srgb('#b8aa8c')), (.36, srgb('#3a200a')), (.42, srgb('#9a6420')),
                                         (.64, srgb('#6e4214')), (.74, srgb('#24120a')), (.76, (.005, .005, .005))])
    em.set(col.outputs['Color'], .08)
    return em

def face_kit(head, add):
    """Eyes, ears with their lining and hair, and the nose, for the jackal's head."""
    bvh = BVHTree.FromObject(head, bpy.context.evaluated_depsgraph_get())
    eye_m = m_eye(r=.0135); r = .0135
    for s, n in ((1, 'L'), (-1, 'R')):
        gaze = V((s * math.sin(math.radians(34)), -math.cos(math.radians(34)), -.06)).normalized()
        c = px(EYE[0], EYE[1], s * EYE[2] * PX); h = bvh.ray_cast(c + gaze * .15, -gaze, .3)
        at = (h[0] if h[0] else c) - gaze * .0052
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=24, ring_count=16, location=at)
        e = bpy.context.object; e.name = f'Eye{n}'; e.rotation_euler = V((0, -1, 0)).rotation_difference(gaze).to_euler()
        add(e, eye_m, 'head')
    fur, lining = m_fur('EarFur', 512), m_fur('EarLining', 512, ('#2a1c10', '#5e4226', '#8a6a42'), '#b08e60')
    lhair = H.m_flat('EarHair', '#9a7a4e', .7); rnd = random.Random(5)
    for s, n in ((1, 'L'), (-1, 'R')):
        shell, up, opening, across = ear_mesh(f'Ear{n}', s)
        mod(shell, 'SUBSURF', levels=1, render_levels=1); bake_mods(shell); add(shell, fur, 'head')
        ln, _, _, _ = ear_mesh(f'EarLining{n}', s, .9, .0012, solid=False); add(ln, lining, 'head')
        base = ear_frame(s)[0]; roots = []   # pale hair inside the ear, standing out of the cup
        for v in ln.data.vertices:
            t = (v.co - base).dot(up) / ((EAR[1] - EAR_TIP[1]) * PX)
            if .02 < t < .7 and rnd.random() < .5:
                roots.append((v.co + opening * .0008, (opening * .8 + up * .7 + across * rnd.uniform(-.25, .25)).normalized()))
        add(HR.strands(f'EarHair{n}', roots, .016, .1, .2, 17 if s > 0 else 18, .0007, 4, .7), lhair, 'head')
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1)
    for v in bm.verts:   # the nose pad: rounded, flat below, two nostrils at the front
        p = v.co; p.x *= .02; p.y *= .015; p.z *= .014
        if p.z < -.006: p.z = -.006 + (p.z + .006) * .4
        for sx in (1, -1):
            dn = (p - V((sx * .0085, -.012, -.002))).length
            if dn < .0065: p += V((0, .006 * (1 - dn / .0065) ** 2, 0))
    nose = obj_from_bm('Nose', bm); tilt = math.radians(28)
    nose.matrix_world = Matrix.Translation(px(790.5, 143.5)) @ Matrix.Rotation(tilt, 4, 'X'); bake_obj_xform(nose)
    add(nose, H.m_flat('NoseLeather', '#0b0a0a', .28), 'head')


# ── The body ────────────────────────────────────────────────────────────────
HAFT = dict(mcp=1.3, pip=1.55, dip=.8, thumb=(.25, .5), tuck=True)       # closed round a khopesh grip
OPEN = dict(mcp=.22, pip=.32, dip=.18, thumb=(.08, .12), tuck=False)     # the empty left hand, relaxed

def behead(body, J):
    """Remove the man's head and neck: the jackal's thicker neck takes their place. The
    throat goes lower, where the jackal's neck stands further forward than a man's."""
    zc = J['neck'].z - .01
    gone = lambda c: (c.z > zc and abs(c.x) < .14) or (c.z > zc - .05 and abs(c.x) < .06 and c.y < -.03)
    bm = bmesh.new(); bm.from_mesh(body.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if gone(f.calc_center_median())], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(body.data); bm.free()

def weight_head(head, J):
    """The jackal's head follows the head bone from a slanted line behind the skull and
    under the jaw (as a dog's head turns on its neck), the neck the neck bone and its base
    the chest."""
    for n in ('chest', 'neck', 'head'): head.vertex_groups.new(name=n)
    a, b = px(664, 124), px(728, 170)            # the back of the skull, the throat under the jaw
    u = (b - a).normalized(); nrm = V((0, -u.z, u.y))   # towards the face
    if nrm.dot(px(780, 140) - a) < 0: nrm = -nrm
    z0, z1 = J['l-shoulder'].z + .02, J['neck'].z + .04
    for v in head.data.vertices:
        p = v.co; up = M._ramp(nrm.dot(p - a), -.025, .02); mid = M._ramp(p.z, z0, z1)
        w = {'head': up, 'neck': mid * (1 - up), 'chest': (1 - mid) * (1 - up)}
        for n, x in w.items():
            if x > .01: head.vertex_groups[n].add([v.index], x, 'REPLACE')


# ── Materials ───────────────────────────────────────────────────────────────
def m_skin(name='BlackSkin', res=2048):
    """Black skin as Anubis is painted in the tombs: near-black with a warm undertone, the
    recesses of the muscles darker, a slight sheen."""
    m = Mat(name, res=res, sss=.04)
    m.bsdf.inputs['Subsurface Radius'].default_value = (.4, .2, .12)
    col = m.ramp(m.noise(9, 5, .55).outputs['Fac'], [(.3, srgb('#0f0c0a')), (.55, srgb('#1a1410')), (.8, srgb('#2a201a'))]).outputs['Color']
    geo = m.node('ShaderNodeNewGeometry')
    cav = m.ramp(geo.outputs['Pointiness'], [(.47, (1, 1, 1)), (.51, (0, 0, 0))])
    col = m.mix(col, srgb('#070505'), m.mix((0, 0, 0), cav.outputs['Color'], .55))
    rough = m.ramp(m.noise(6, 3, .5).outputs['Fac'], [(.3, (.3, .3, .3)), (.75, (.44, .44, .44))])
    m.set(col, rough.outputs['Color'], m.noise(900, 2, .5).outputs['Fac'], .15, .0006)
    return m

def m_kilt(name='KiltLinen', res=2048):
    """Fine white linen, pleated: the pleats fan down and out from the front of the belt and
    run round the back as soft level folds (in object space), over the weave."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
    front = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', **{'From Min': .03, 'From Max': -.05}); m.L.new(sep.outputs['Y'], front.inputs['Value'])
    t1 = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(ax.outputs[0], t1.inputs[0]); m.L.new(front.outputs[0], t1.inputs[1])
    q = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(t1.outputs[0], q.inputs[0]); q.inputs[1].default_value = .7; m.L.new(sep.outputs['Z'], q.inputs[2])
    cq = m.node('ShaderNodeCombineXYZ'); m.L.new(q.outputs[0], cq.inputs['Z'])
    pl = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', wave_profile='SIN', Scale=9.0, Distortion=1.2, Detail=1.0); m.L.new(cq.outputs[0], pl.inputs['Vector'])
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=700.0); m.L.new(m.coord.outputs['UV'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=700.0); m.L.new(m.coord.outputs['UV'], w2.inputs['Vector'])
    weave = m.mix(w1.outputs['Color'], w2.outputs['Color'], .5)
    h = m.mix(pl.outputs['Color'], weave, .12)
    col = m.ramp(m.noise(16, 4, .6).outputs['Fac'], [(.3, srgb('#e2dfd6')), (.7, srgb('#f3f1ea'))]).outputs['Color']
    col = m.mix(col, srgb('#bdb9ae'), m.ramp(pl.outputs['Fac'], [(.0, (.45, .45, .45)), (.35, (0, 0, 0))]).outputs['Color'])
    m.set(col, .86, h, .55, .004)
    return m

def m_gold(name='Gold', engrave=0.0, res=512, cols=('#9c7428', '#e2bb5c')):
    """Beaten gold: a warm mottle, fine hammer marks, and optionally incised lines."""
    m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb(cols[0])), (.7, srgb(cols[1]))]).outputs['Color']
    bump = m.noise(90, 3).outputs['Fac']
    if engrave:
        sw = m.node('ShaderNodeTexWave', wave_type='RINGS', Scale=60.0, Distortion=9.0, Detail=3.0); m.L.new(m.coord.outputs['Object'], sw.inputs['Vector'])
        lines = m.ramp(sw.outputs['Fac'], [(.0, (1, 1, 1)), (.04, (1, 1, 1)), (.07, (0, 0, 0)), (1.0, (0, 0, 0))])
        col = m.mix(col, srgb('#4a3410'), m.mix((0, 0, 0), lines.outputs['Color'], engrave))
        bump = m.ramp(lines.outputs['Color'], [(0, (1, 1, 1)), (1, (0, 0, 0))]).outputs['Color']
    m.set(col, .24, bump, .25, .0008)
    return m

def m_image(name, img, rough=.5, bump_img=None, metal=0.0, res=1024, strength=.4, dist=.0015):
    """A material painted with PIL in the object's own UVs (colour, and height for the bump)."""
    m = Mat(name, metal=metal, res=res)
    t = m.node('ShaderNodeTexImage'); t.image = img; m.L.new(m.coord.outputs['UV'], t.inputs['Vector'])
    bump = None
    if bump_img:
        b = m.node('ShaderNodeTexImage'); b.image = bump_img; b.image.colorspace_settings.name = 'Non-Color'; m.L.new(m.coord.outputs['UV'], b.inputs['Vector']); bump = b.outputs['Color']
    m.set(t.outputs['Color'], rough, bump, strength, dist)
    return m

def hexrgb(h):
    """A hex colour as display (sRGB) values, for painting images."""
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def to_image(name, rgb, alpha=None):
    """A float array of display colours (rows from the top) as a packed Blender image."""
    h, w = rgb.shape[:2]; img = bpy.data.images.new(name, w, h, alpha=alpha is not None)
    a = np.ones((h, w, 4), np.float32); a[..., :3] = rgb[::-1]
    if alpha is not None: a[..., 3] = alpha[::-1]
    img.pixels.foreach_set(a.ravel()); img.pack(); return img


# ── The broad collar (wesekh) ───────────────────────────────────────────────
# Rows of beads from the neck outwards, as fractions of the collar's width: tubular beads
# of turquoise, lapis lazuli and carnelian (or gold), threaded radially; gold rows are laid
# as metal strips, and the outer edge is a fringe of drop-shaped pendants.
TURQ, LAPIS, CARN, GOLD = '#5cc6c6', '#27398f', '#c44c24', '#d4a84a'
ROWS12 = [(.04, .14, TURQ), (.14, .2, LAPIS), (.2, .33, CARN), (.33, .39, LAPIS), (.39, .55, TURQ), (.55, .61, CARN), (.61, .76, TURQ), (.8, .965, GOLD)]
ROWS3 = [(.04, .13, LAPIS), (.13, .2, GOLD), (.2, .33, LAPIS), (.33, .39, TURQ), (.39, .46, GOLD), (.46, .6, LAPIS), (.6, .65, CARN), (.65, .76, LAPIS), (.8, .965, GOLD)]
STRIPS = [(0, .04), (.76, .8), (.965, 1)]   # gold edges at the neck and the rim, and the row the drops hang from
COLLAR_N = 3                       # the ring is cut into this many strips, stacked in the texture

def collar_paint(name, rows, S=1024, seed=1):
    """The bead rows in the collar's UVs: each strip of the texture is a third of the ring;
    beads are shaded as little cylinders, each a slightly different tint."""
    rnd = np.random.default_rng(seed)
    vv, uu = np.meshgrid((np.arange(S) + .5) / S, (np.arange(S) + .5) / S, indexing='ij')
    vv = 1 - vv                                   # image rows run down, v up
    k = np.floor(vv * COLLAR_N); f = vv * COLLAR_N - k
    theta = (k + uu) / COLLAR_N                   # turns round the neck
    rgb = np.zeros((S, S, 3), np.float32) + .08; hgt = np.zeros((S, S), np.float32)
    for f0, f1, hexcol in rows:
        c = np.array(hexrgb(hexcol), np.float32)
        n = 132 if hexcol != GOLD else 180
        inb = (f >= f0) & (f < f1); t = np.clip((f - f0) / (f1 - f0), 0, 1)
        bead = np.floor(theta * n); s = theta * n - bead
        tint = 1 + .14 * (rnd.random(n + 1)[bead.astype(int) % n] - .5)
        shade = (.3 + .8 * np.sin(np.pi * s) ** .6) * (.6 + .4 * np.sin(np.pi * t) ** .4) * tint
        rgb[inb] = (c[None, :] * shade[inb][:, None])
        hgt[inb] = (np.sin(np.pi * s) ** .5 * np.sin(np.pi * t) ** .3)[inb]
    return to_image(name, np.clip(rgb, 0, 1)), to_image(name + 'H', np.repeat(hgt[..., None], 3, 2))

def collar(tag, under, head, rows, add, gold, drop_m, gap=.004, mats=None):
    """The broad collar laid round the jackal's neck on the shoulders, chest and back (or on
    the corselet: `under` are the surfaces it lies on): a ring of beads (its own UVs,
    painted), gold strips and a fringe of drop pendants. Each section runs from the neck to
    the collar's edge measured on the sheet, and is drawn onto whatever lies beneath."""
    dg = bpy.context.evaluated_depsgraph_get(); hb = BVHTree.FromObject(head, dg)
    bvhs = [BVHTree.FromObject(o, dg) for o in list(under) + [head]]
    yc = NECK_Y; nth, nf = 120, 14
    def ring_r(th, z):   # the neck's radius at angle th, height z
        d = V((math.sin(th), -math.cos(th), 0)); o = V((0, yc, z))
        h = hb.ray_cast(o + d * .4, -d, .4); return (h[0] - o).length if h[0] else .09
    def near(p):
        best = None
        for t in bvhs:
            loc, no, fi, dist = t.find_nearest(p)
            if loc is not None and (best is None or dist < best[2]): best = (loc, no, dist)
        return best
    def snap(p): loc, no, d = near(p); return loc + no * gap
    def clear(p):   # pushed out where it would sink below the surface; left standing over hollows
        loc, no, d = near(p); return p if (p - loc).dot(no) > gap else loc + no * gap
    grid = []
    for i in range(nth + 1):   # a stiff collar: straight from its edge at the neck to its rim, resting on what stands highest
        th = 2 * math.pi * i / nth; d = V((math.sin(th), -math.cos(th), 0))
        zi = 1.495 - .025 * math.cos(th); a = V((0, yc, zi)) + d * (max(ring_r(th, z) for z in (zi - .03, zi - .015, zi)) + .003)
        a, b = snap(a), snap(V((0, yc, collar_edge_z(th))) + d * collar_reach(th))
        grid.append([clear(a.lerp(b, j / nf)) for j in range(nf + 1)])
    grid[-1] = grid[0]
    for _ in range(4):   # smooth the shell round and across the ring, clear of the surface
        g2 = []
        for i in range(nth):
            row = []
            for j in range(nf + 1):
                q = grid[i][j] * .5 + (grid[(i - 1) % nth][j] + grid[(i + 1) % nth][j]) * .25
                if 0 < j < nf: q = q * .6 + (grid[i][j - 1] + grid[i][j + 1]) * .2
                row.append(clear(q))
            g2.append(row)
        grid = g2 + [g2[0]]
    def build(name, f0, f1, lift):
        bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); vs = []
        j0 = min(round(f0 * nf), nf - 1); j1 = max(round(f1 * nf), j0 + 1)
        for i in range(nth + 1):
            row = []
            for j in range(nf + 1):
                p = grid[i][j]; q = grid[i][min(j + 1, nf)] - grid[i][max(j - 1, 0)]; t = grid[(i + 1) % nth][j] - grid[i - 1 if i else nth - 1][j]
                n = t.cross(q).normalized()
                if n.z < 0: n = -n
                row.append(bm.verts.new(p + n * lift))
            vs.append(row)
        per = nth // COLLAR_N
        for i in range(nth):
            k = i // per
            for j in range(j0, j1):
                fc = bm.faces.new((vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]))
                for lp, (a, b) in zip(fc.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    lp[uv].uv = ((a - k * per) / per, (k + b / nf) / COLLAR_N)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        ob = obj_from_bm(name, bm)
        if sum((p.normal.z for p in ob.data.polygons)) < 0:
            for p in ob.data.polygons: p.flip()
        return ob
    beads = build(tag + 'Collar', 0, 1, 0); mod(beads, 'SOLIDIFY', thickness=.005, offset=-1); bake_mods(beads)
    if mats is None:
        img, hgt = collar_paint(tag + 'CollarBeads', rows, seed=len(tag)); mats = m_image(tag + 'CollarBeads', img, .32, hgt, res=1024, strength=.5, dist=.002)
    add(beads, mats, 'skin')
    for k, (f0, f1) in enumerate(STRIPS):
        st = build(f'{tag}CollarGold{k}', f0, f1, .0016); mod(st, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(st); add(st, gold, 'skin')
    bm = bmesh.new(); nd = 96
    def at(th, f):   # a point of the shell at angle th and fraction f across it
        ii = th / (2 * math.pi) * nth; i0 = int(ii) % nth; fr = ii - int(ii); jj = f * nf; j0 = min(int(jj), nf - 1); fj = jj - j0
        row = lambda j: grid[i0][j].lerp(grid[i0 + 1][j], fr)
        return row(j0).lerp(row(j0 + 1), fj)
    for i in range(nd):   # the drop pendants in their row at the rim, lying on the collar
        th = 2 * math.pi * (i + .5) / nd; a, b = at(th, .885), at(th, .8)
        out = (a - b).normalized(); side = (at(th + .01, .885) - at(th - .01, .885)).normalized(); n = side.cross(out).normalized()
        if n.z < 0: n = -n
        ln = (at(th, .96) - b).length * .48
        Mx = Matrix((side * .0052, out * ln, n * .003)).transposed().to_4x4(); Mx.translation = a + n * .0034
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=1, matrix=Mx)
    add(obj_from_bm(tag + 'CollarDrops', bm), drop_m, 'skin')
    return mats


# ── The kilt (shendyt), its apron and sash ──────────────────────────────────
KILT_TOP, KILT_HEM = (734 - 335) * PX, (734 - 521) * PX   # after the sheet's front view

def kilt(name, body):
    """A wrap kilt from the waist to above the knee: each ring starts round the body's convex
    outline at its height (clear of it, flaring a little to the hem, dipping slightly at the
    front), then the cloth simulator drapes it from the waist."""
    vs = [body.matrix_world @ v.co for v in body.data.vertices]
    vs = [v for v in vs if abs(v.x) < .24]
    nr, nz = 80, 30; bm = bmesh.new(); rows = []
    for j in range(nz + 1):
        t = j / nz; z = KILT_TOP - (KILT_TOP - KILT_HEM) * t
        sl = [v for v in vs if abs(v.z - z) < .015] or sl
        yb = sum(v.y for v in sl) / len(sl); row = []
        for i in range(nr):
            a = 2 * math.pi * i / nr; d = V((math.cos(a), math.sin(a), 0))
            r = max((v.x * d.x + (v.y - yb) * d.y) for v in sl) + .007 + .012 * t ** 1.2
            zz = z - (.018 * t * max(0, -d.y) ** 2 if j else 0)
            row.append(bm.verts.new((d.x * r, yb + d.y * r, zz)))
        rows.append(row)
    for j in range(nz):
        for i in range(nr): bm.faces.new((rows[j][i], rows[j][(i + 1) % nr], rows[j + 1][(i + 1) % nr], rows[j + 1][i]))
    ob = obj_from_bm(name, bm)
    H.drape(name, ob, lambda c: c.z > KILT_TOP - .02, body, 60, .25, .003)
    return ob

def apron_paint(S=512):
    """The starched apron's embroidery, white on white: a double border, a column of lotus
    and papyrus motifs down the middle, a fan at the foot. Colour and height."""
    from PIL import Image, ImageDraw, ImageFilter
    W, Hh = S, S * 4; h = Image.new('L', (W, Hh), 0); d = ImageDraw.Draw(h)
    d.rectangle((14, 14, W - 15, Hh - 15), outline=255, width=10); d.rectangle((44, 44, W - 45, Hh - 45), outline=200, width=6)
    m = W // 2
    for x in (m - 110, m + 110): d.line([(x, 70), (x, Hh - 260)], fill=200, width=6)
    y = 110
    while y < Hh - 330:   # lotus buds and papyrus umbels, alternately, with bands between
        d.polygon([(m, y), (m + 70, y + 60), (m + 40, y + 120), (m, y + 90), (m - 40, y + 120), (m - 70, y + 60)], outline=230, width=7)
        d.line([(m, y + 120), (m, y + 190)], fill=230, width=8)
        d.arc((m - 80, y + 150, m + 80, y + 260), 200, 340, fill=210, width=7)
        for k in range(3): d.line([(m - 90, y + 215 + k * 18), (m + 90, y + 215 + k * 18)], fill=180, width=5)
        y += 290
    for k in range(9):   # the fan
        a = math.radians(200 + k * 17.5); d.line([(m, Hh - 70), (m + math.cos(a) * 190, Hh - 70 + math.sin(a) * 190)], fill=220, width=7)
    d.arc((m - 190, Hh - 260, m + 190, Hh + 120), 200, 340, fill=230, width=8)
    h = h.filter(ImageFilter.GaussianBlur(2.2)); ha = np.asarray(h, np.float32) / 255
    base = np.array(hexrgb('#efede6'), np.float32); groove = np.array(hexrgb('#c9c5ba'), np.float32)
    rnd = np.random.default_rng(3).random((Hh, W, 1)).astype(np.float32) * .03
    edge = np.clip(np.abs(np.gradient(ha)[0]) * 6 + np.abs(np.gradient(ha)[1]) * 6, 0, 1)[..., None]
    rgb = base[None, None, :] * (1 - rnd) * (1 - edge) + groove[None, None, :] * edge
    return to_image('ApronCol', np.clip(rgb, 0, 1)), to_image('ApronH', np.repeat(ha[..., None], 3, 2))

def apron(name, sf, z0=(734 - 352) * PX, z1=(734 - 531) * PX):
    """The stiff embroidered apron hanging straight down the front of the kilt from the knot
    of the sash, widening a little to its foot (after the sheet: 35 px wide at the top, 45 at
    the foot). Its own UVs, for the painted embroidery."""
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); rows = []; yprev = 1.0; nz, nx = 24, 8
    for j in range(nz + 1):
        t = j / nz; z = z0 - (z0 - z1) * t; w = (35 + 10 * t) * PX / 2; row = []
        ys = []
        for i in range(nx + 1):
            x = -w + 2 * w * i / nx; h = sf.hit(V((x, 0, z)), V((0, -1, 0)), .6); ys.append((h[0].y if h else -.15) - .008)
        y = min(min(ys), yprev); yprev = y
        for i in range(nx + 1):
            x = -w + 2 * w * i / nx; row.append(bm.verts.new((x, y - .004 * (1 - (2 * i / nx - 1) ** 2), z)))
        rows.append(row)
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))): lp[uv].uv = (a / nx, 1 - b / nz)
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(ob)
    if sum(p.normal.y for p in ob.data.polygons) > 0:
        for p in ob.data.polygons: p.flip()
    return ob

def sandals(add, body, J, sole_m, strap_m):
    """Egyptian sandals: a flat sole and a thong from between the first two toes, splitting
    into a strap across the instep down to both sides of the sole at the arch."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    for side in ('l', 'r'):
        S = side.upper(); an = J[f'{side}-ankle']
        pts = [(body.matrix_world @ v.co) for v in body.data.vertices]
        foot = [p for p in pts if p.z < .03 and abs(p.x - an.x) < .09]
        bm = bmesh.new()
        for p in foot: bm.verts.new((p.x, p.y, 0.0)); bm.verts.new((p.x, p.y, .011))
        bmesh.ops.convex_hull(bm, input=bm.verts)
        so = obj_from_bm(f'Sole{S}', bm, False); so.scale = (1.07, 1.04, 1); bake_obj_xform(so)
        cx = sum(p.x for p in foot) / len(foot)
        for v in so.data.vertices: v.co.x = cx + (v.co.x - cx); v.co.y = v.co.y - .004
        mod(so, 'BEVEL', width=.003, segments=2); bake_mods(so); add(so, sole_m, f'foot.{S}')
        toes = [p for p in foot if p.y < min(q.y for q in foot) + .05]
        sx = 1 if side == 'l' else -1
        post = V((cx + sx * .008 + (sum(p.x for p in toes) / len(toes) - cx) * .6, min(p.y for p in foot) + .045, 0))
        h = bvh.ray_cast(post + V((0, 0, .2)), V((0, 0, -1)), .3); top = h[0] if h[0] else post + V((0, 0, .03))
        strap = []
        for k in range(17):   # the V over the instep, from the outer side of the arch round to the inner
            u = -1 + 2 * k / 16; ang = u * math.radians(88)
            c = V((cx, an.y - .065 + .035 * (1 - abs(u)) ** 1.5 * -1, .045))
            d = V((math.sin(ang), 0, math.cos(ang)))
            hh = bvh.ray_cast(c + d * .2, -d, .25)
            q = (hh[0] + hh[1] * .002) if hh[0] else c + d * .05
            strap.append((V((q.x, q.y, max(q.z, .012))), hh[1] if hh[0] else d))
        add(P.ribbon(f'SandalStrap{S}', strap, .016, .0025), strap_m, f'foot.{S}')
        mid = strap[8][0]
        add(curve_mesh(f'SandalThong{S}', [[tuple(post + V((0, 0, .011))), tuple(top.lerp(post, .4) + V((0, .004, .006))), tuple(mid)]], .0035, res=1), strap_m, f'foot.{S}')


# ── Scale corselets ─────────────────────────────────────────────────────────
NECK_Y = px(690, 0).y   # the neck's axis, which the collar is laid round

def collar_reach(th):
    """How far out from the neck the collar lies at angle th (0 = front, towards the left)."""
    a = .15 if math.cos(th) > 0 else .14
    return 1 / math.sqrt((math.cos(th) / a) ** 2 + (math.sin(th) / .225) ** 2)

def collar_edge_z(th):
    """The height of the collar's outer edge: lowest on the chest, highest over the shoulders."""
    c = math.cos(th); return 1.44 - .1 * max(0, c) ** 1.5 - .055 * max(0, -c) ** 1.5

def polar(p):
    d = V((p.x, p.y - NECK_Y, 0)); return math.atan2(d.x, -d.y), d.length

def scale_atlas(name, kind, G=20, S=1024, seed=2):
    """One cell per scale (G x G), painted: feather-shaped bronze scales with a midrib and
    barbs under a green patina, or round gilded scales with a raised rim. Colour and height."""
    c = S // G; rnd = np.random.default_rng(seed)
    yy, xx = np.meshgrid((np.arange(c) + .5) / c, (np.arange(c) + .5) / c, indexing='ij')
    u = xx * 2 - 1; v = 1 - yy                                  # across, and up the scale
    rgb = np.zeros((S, S, 3), np.float32); hgt = np.zeros((S, S), np.float32)
    for gy in range(G):
        for gx in range(G):
            n = rnd.random(3)
            if kind == 'feather':
                edge = np.clip(1 - np.abs(u) ** 6 - (1 - v) ** 8, 0, 1)
                rib = np.exp(-(u / .07) ** 2) * (v > .08)
                barbs = .5 + .5 * np.sin((v * 22 - np.abs(u) * 9) * math.pi)
                h = .55 * edge + .3 * rib + .12 * barbs * edge
                base = np.array(hexrgb('#6c8a74'), np.float32) * (.85 + .3 * n[0]); bronze = np.array(hexrgb('#8a6a3a'), np.float32)
                col = base[None, None] * (.7 + .45 * h[..., None]) * (1 - .25 * barbs[..., None] * edge[..., None])
                rim = np.clip((1 - edge) * 1.6, 0, 1)[..., None]
                col = col * (1 - rim) + bronze[None, None] * (.7 + .3 * n[1]) * rim
            else:
                r = np.sqrt(u ** 2 + ((1 - v) * 1.15) ** 2)
                h = np.clip(1 - r, 0, 1) ** .5; rim = np.exp(-((r - .86) / .06) ** 2)
                h = h * .8 + rim * .35
                gold = np.array(hexrgb('#e6c46c'), np.float32) * (.88 + .24 * n[0])
                col = gold[None, None] * (.55 + .5 * h[..., None])
            rgb[gy * c:(gy + 1) * c, gx * c:(gx + 1) * c] = np.clip(col, 0, 1)
            hgt[gy * c:(gy + 1) * c, gx * c:(gx + 1) * c] = h
    return to_image(name, rgb), to_image(name + 'H', np.repeat(hgt[..., None], 3, 2))

def corselet(tag, body, J, kind, add, back_m, scale_m, G=20):
    """A sleeveless corselet of scales from the waist to under the collar: a backing grown
    from the body (the collar lies on it), and rows of scales laid on it from
    the bottom up, each hanging from its top over the row below, every other row offset
    by half a scale. Each scale has its own cell of the painted atlas."""
    sh = J['l-shoulder']; on_up = P.on_arm(J, -.35, 1.1, .09)
    keep = lambda c: 1.07 < c.z < sh.z + .06 and abs(c.x) < (.205 if c.z < 1.17 else .158) and not on_up(c)
    back = region_shell(tag + 'Corselet', body, keep, .012, 4, .5, guard=.011)
    P.relax_rim(back, 4); mod(back, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(back); add(back, back_m, 'skin')
    sf = Surf([back])
    W, Hs = (.019, .054) if kind == 'feather' else (.0155, .038)
    dz = Hs * (.6 if kind == 'feather' else .58); rows = []; z = 1.085
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); cell = 0; j = 0
    while z < sh.z + .04:
        yb = -.005; hits = []
        for k in range(720):
            a = 2 * math.pi * k / 720; d = V((math.cos(a), math.sin(a), 0)); h = sf.hit(V((0, yb, z)), d, .5)
            th = polar(h[0])[0] if h else 0
            ok = h and z + Hs * .3 < collar_edge_z(th) + .006 and (h[0] - V((0, yb, z))).dot(d) > .05
            hits.append((h[0], h[1]) if ok else None)
        start = next((k for k in range(720) if hits[k] is None), 0)   # walk the ring from a gap, so runs never wrap
        run, acc, sp = [], 0.0, 2 * W * .92
        for k in range(721):
            hk = hits[(start + k) % 720]
            if hk is None:
                run, acc = [], (sp * .5 if j % 2 else 0.0); continue
            if run: acc += (hk[0] - run[-1]).length
            run.append(hk[0])
            if acc >= sp:
                acc -= sp; p, n = hk
                up = V((0, 0, 1)) - n * n.z; up.normalize(); ac = up.cross(n).normalized()
                gx, gy = cell % G, (cell // G) % G; cell += 1
                nu, nv = 4, 6; grid = []
                for b in range(nv + 1):
                    vv = b / nv; w = W * (1 - (1 - min(1, vv / .5)) ** 2) ** .5 if kind == 'feather' else W * (1 - (1 - min(1, vv / .55)) ** 2) ** .5
                    grid.append([bm.verts.new(p + ac * (uu * w) + up * ((vv - .7) * Hs) + n * (.0065 * (1 - vv) ** 1.3 + .0018 * (1 - uu * uu) + .001))
                                 for uu in [-1 + 2 * a_ / nu for a_ in range(nu + 1)]])
                for b in range(nv):
                    for a_ in range(nu):
                        f = bm.faces.new((grid[b][a_], grid[b][a_ + 1], grid[b + 1][a_ + 1], grid[b + 1][a_]))
                        for lp, (x_, y_) in zip(f.loops, ((a_, b), (a_ + 1, b), (a_ + 1, b + 1), (a_, b + 1))):
                            lp[uvl].uv = ((gx + (.04 + .92 * x_ / nu)) / G, 1 - (gy + 1 - (.04 + .92 * y_ / nv)) / G)
        z += dz; j += 1
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    sc = obj_from_bm(tag + 'Scales', bm); mod(sc, 'SOLIDIFY', thickness=.0016, offset=-1); bake_mods(sc)
    add(sc, scale_m, 'skin')
    print(tag, 'scales', cell)
    return back, sc


# ── Gold armlets and wristguards, the shield ────────────────────────────────
def armlet(name, bvh, a, b, t, width, add, gold, rim_m, bone):
    """A gold band round a limb with a raised rim at each edge."""
    add(M.limb_band(name, bvh, a, b, t, width, .0055, 48), gold, bone)
    u = (b - a).normalized(); L = (b - a).length; rims = []
    for dt in (-1, 1):
        c = a.lerp(b, t) + u * dt * (width / 2 - .002); e1 = u.orthogonal().normalized(); e2 = u.cross(e1); pts = []
        for i in range(48):
            ang = 2 * math.pi * i / 48; d = e1 * math.cos(ang) + e2 * math.sin(ang)
            h = bvh.ray_cast(c + d * .3, -d, .35); pts.append(tuple((h[0] + h[1] * .0085) if h[0] else c + d * .05))
        rims.append(pts)
    add(curve_mesh(name + 'Rims', rims, .0028, cyclic=True, res=1), rim_m, bone)

def wristguard(name, body, J, side, add, gold, rim_m):
    """A flared gold guard over the forearm from its middle to the wrist, rims at both ends."""
    E, W = J[f'{side}-elbow'], J[f'{side}-hand']; u = W - E
    def keep(c):
        t = (c - E).dot(u) / u.length_squared
        return .36 < t < .94 and (c - (E + u * t)).length < .075
    g = region_shell(name, body, keep, .007, 3, .5, guard=.0065)
    for v in g.data.vertices:   # a little flare towards the elbow
        t = (v.co - E).dot(u) / u.length_squared; ax = E + u * t; v.co = ax + (v.co - ax) * (1 + .12 * max(0, .62 - t))
    P.relax_rim(g, 6); mod(g, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(g); add(g, gold, f'forearm.{side.upper()}')
    bm = bmesh.new(); bm.from_mesh(g.data)
    rims = []
    for t0 in (.405, .9):
        c = E + u * t0; e1 = u.normalized().orthogonal().normalized(); e2 = u.normalized().cross(e1); pts = []
        bvh = BVHTree.FromObject(g, bpy.context.evaluated_depsgraph_get())
        for i in range(40):
            ang = 2 * math.pi * i / 40; d = e1 * math.cos(ang) + e2 * math.sin(ang)
            h = bvh.ray_cast(c + d * .3, -d, .35)
            if h[0]: pts.append(tuple(h[0] + h[1] * .001))
        rims.append(pts)
    bm.free()
    add(curve_mesh(name + 'Rims', rims, .0026, cyclic=True, res=1), rim_m, f'forearm.{side.upper()}')

def shield(tag, add, hide_m, rim_m, back_m, Hh=.56, Wd=.4):
    """An Egyptian shield of cowhide on a wooden frame: a round top, straight sides narrowing
    a little to a flat foot with rounded corners, slightly domed; a stitched leather rim and
    two straps for the forearm behind. Built facing +Z, its height along +Y, about its middle."""
    R = Wd / 2; yc = Hh / 2 - R; bot = -Hh / 2
    def hw(y):   # half-width at height y
        if y > yc: return math.sqrt(max(0, R * R - (y - yc) ** 2))
        t = (yc - y) / (yc - bot); w = R * (1 - .1 * t)
        k = (y - bot) / .045
        return w * (math.sqrt(max(0, 1 - (1 - k) ** 2)) if k < 1 else 1)
    nu, nv = 18, 40; bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); grid = []
    for j in range(nv + 1):
        y = bot + (Hh) * j / nv; w = max(hw(y), .002); row = []
        for i in range(nu + 1):
            u = -1 + 2 * i / nu; x = u * w
            row.append(bm.verts.new((x, y, .035 * (1 - u * u) * (1 - ((y) / (Hh / 2)) ** 2 * .6))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp in f.loops: lp[uv].uv = (lp.vert.co.x / Wd + .5, lp.vert.co.y / Hh + .5)
    rim = [tuple(grid[j][nu].co) for j in range(nv + 1)] + [tuple(grid[j][0].co) for j in range(nv, -1, -1)]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    face = obj_from_bm(tag + 'Shield', bm); mod(face, 'SOLIDIFY', thickness=.012, offset=-1); bake_mods(face)
    add(face, hide_m, 'later:forearm.L')
    add(curve_mesh(tag + 'ShieldRim', [rim], .0075, cyclic=True), rim_m, 'later:forearm.L')
    for k, y in enumerate((.1, -.12)):   # straps behind, the forearm passes through them
        pts = [(-.05, y, -.012), (-.042, y, -.04), (-.02, y, -.06), (.02, y, -.06), (.042, y, -.04), (.05, y, -.012)]
        st = curve_mesh(f'{tag}ShieldStrap{k}', [pts], .012, res=1); st.scale = (1, .35 / .35, 1)
        bm2 = bmesh.new(); bm2.from_mesh(st.data)
        for v in bm2.verts: v.co.y = y + (v.co.y - y) * 1.8
        bm2.to_mesh(st.data); bm2.free(); add(st, back_m, 'later:forearm.L')


# ── The khopesh ─────────────────────────────────────────────────────────────
# Traced from the side view of the first sheet, where it is held point forward, edge down:
# the grip from the pommel to the guard, then the back (TOP) and edge (BOT) of the shank and
# blade to the point, with the barb on the back near the point (px).
KH_POMMEL, KH_GUARD = (690, 415), (748, 426)
KH_TOP = [(750, 425), (765, 429), (785, 437), (803, 446), (809, 449), (813, 453), (817, 461), (822, 469), (830, 476), (842, 485),
          (854, 492), (866, 498), (878, 502), (890, 505), (902, 508), (914, 508.5), (926, 507.5), (933, 505), (937, 498), (941, 503),
          (948, 506.5), (956, 509), (965, 511)]
KH_BOT = [(750, 433), (765, 440), (785, 447), (799, 454), (805, 462), (811, 474), (819, 482), (830, 491), (842, 499), (854, 505),
          (866, 510), (878, 514), (890, 517), (902, 519), (914, 520), (926, 520.5), (938, 520), (948, 518), (957, 515.5), (965, 511)]

def khopesh(tag, k, mats, gilt_grip=False):
    """A khopesh built about its grip (the origin): the grip runs along +Z to the blade, the
    shank and sickle blade lie in the XZ plane with the cutting edge towards +X. k scales the
    sheet's weapon (0.74 m at the build's scale)."""
    wood, metal, band = mats
    g = V(((KH_POMMEL[0] + KH_GUARD[0]) / 2, (KH_POMMEL[1] + KH_GUARD[1]) / 2))
    zd = (V(KH_GUARD) - V(KH_POMMEL)).normalized(); xd = V((-zd.y, zd.x))
    if xd.y < 0: xd = -xd   # the edge side: down in the sheet
    loc = lambda p: ((V(p) - g).dot(xd) * PX * k, (V(p) - g).dot(zd) * PX * k)
    zp, zg = loc(KH_POMMEL)[1], loc(KH_GUARD)[1]
    out = [(lathe(tag + 'Grip', [(0, zp - .006 * k), (.017 * k, zp), (.02 * k, zp + .012 * k), (.0135 * k, zp + .03 * k), (.0145 * k, zp + .075 * k),
                                 (.0155 * k, zg - .012 * k), (.016 * k, zg)], 16), wood),
           (lathe(tag + 'Guard', [(.0165 * k, zg - .002), (.0205 * k, zg + .003 * k), (.0205 * k, zg + .016 * k), (.012 * k, zg + .024 * k)], 16), band),
           (lathe(tag + 'Pommel', [(0, zp - .012 * k), (.012 * k, zp - .01 * k), (.0195 * k, zp - .003 * k), (.018 * k, zp + .004 * k)], 16), band)]
    def resample(poly, n):   # n + 1 points evenly along a polyline
        pts = [V((loc(p)[0], 0, loc(p)[1])) for p in poly]; L = [0.0]
        for a, b in zip(pts, pts[1:]): L.append(L[-1] + (b - a).length)
        out_, i = [], 0
        for k in range(n + 1):
            d = L[-1] * k / n
            while i < len(pts) - 2 and L[i + 1] < d: i += 1
            out_.append(pts[i].lerp(pts[i + 1], (d - L[i]) / max(1e-9, L[i + 1] - L[i])))
        return out_
    bm = bmesh.new(); n = 60   # a strip of quads from the back to the edge, guard to point
    tp, bp = resample(KH_TOP, n), resample(KH_BOT, n)   # a little broader than drawn, so the blade reads from afar
    tv = [bm.verts.new(p) for p in tp]; bv = [bm.verts.new(t + (b - t) * 1.25) for t, b in zip(tp[:-1], bp[:-1])] + [tv[-1]]
    for i in range(n): bm.faces.new((tv[i], tv[i + 1], bv[i + 1], bv[i]) if i < n - 1 else (tv[i], tv[i + 1], bv[i]))
    bl = obj_from_bm(tag + 'Blade', bm, smooth=False)
    mod(bl, 'SOLIDIFY', thickness=.0065 * k, offset=0); mod(bl, 'BEVEL', width=.0018 * k, segments=2, limit_method='ANGLE'); bake_mods(bl)
    tz, bz = [loc(p) for p in KH_TOP], [loc(p) for p in KH_BOT]
    xt = lambda z: np.interp(z, [q[1] for q in tz], [q[0] for q in tz]); xb = lambda z: np.interp(z, [q[1] for q in bz], [q[0] for q in bz])
    for v in bl.data.vertices:   # thin the blade towards its edge; the shank keeps its thickness
        if v.co.z > loc((812, 450))[1]:
            e = min(1, max(0, (v.co.x - xt(v.co.z)) / max(1e-4, xb(v.co.z) - xt(v.co.z))))
            v.co.y *= 1 - .6 * e ** 1.5
    out.append((bl, metal))
    return out


# ── Kit ─────────────────────────────────────────────────────────────────────
def weight_skirt(ob, J):
    """The kilt keeps the skin's own weights at the waist and hips (bound as the other
    garments are), and towards the hem follows the nearer thigh (both alike between the
    legs), so it swings with the legs without the thighs coming through it."""
    names = {g.index: g.name for g in ob.vertex_groups}
    for n in ('hips', 'thigh.L', 'thigh.R'):
        if n not in ob.vertex_groups: ob.vertex_groups.new(name=n)
    def dist(p, a, b):
        u = b - a; t = max(0, min(1, (p - a).dot(u) / u.length_squared)); return (p - (a + u * t)).length
    for v in ob.data.vertices:
        p = v.co; down = M._ramp(-p.z, -1.0, -.8) * .95; k = M._ramp(-p.z, -.99, -.86)
        dl, dr = dist(p, J['l-upper-leg'], J['l-knee']), dist(p, J['r-upper-leg'], J['r-knee'])
        side = M._ramp(dr - dl, -.04, .04)
        w = {'thigh.L': down * side, 'thigh.R': down * (1 - side)}; w['hips'] = 1 - w['thigh.L'] - w['thigh.R']
        skin = {names[g.group]: g.weight for g in v.groups}; tot = sum(skin.values()) or 1
        for n in set(w) | set(skin):
            x = (1 - k) * skin.get(n, 0) / tot + k * w.get(n, 0)
            if x > .005: ob.vertex_groups[n].add([v.index], x, 'REPLACE')
            elif n in ob.vertex_groups: ob.vertex_groups[n].remove([v.index])

def grip_frame(J, s):
    """The rest-pose frame of a fist's grip: the origin in the fist, Z along the knuckle line
    towards the thumb (where the blade goes), X along the hand (the edge's side)."""
    wrist, along, palm = T.hand_frame(J, s)
    mcp = sum((J[f'{s}-finger-{k}-1'] for k in (2, 3, 4, 5)), V()) / 4
    k = (J[f'{s}-finger-5-1'] - J[f'{s}-finger-2-1']).normalized(); k = (k - along * k.dot(along)).normalized()
    z = -k; x = (along - z * along.dot(z)).normalized()
    Mg = Matrix((x, z.cross(x), z)).transposed().to_4x4(); Mg.translation = mcp + palm * .021 - along * .006
    return Mg

def kit(body, head, J):
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(body, dg)
    face_kit(head, add)
    gold, gold_rim = m_gold('GoldEngraved', .4), m_gold('GoldRim', res=256)

    # The kilt of every tier: pleated linen, the embroidered apron, the sash and its knot
    sk = kilt('Kilt', body); add(sk, m_kilt(), 'kilt')
    sf = Surf([sk, body]); img, hgt = apron_paint()
    add(apron('KiltApron', sf), m_image('Apron', img, .85, hgt, res=1024, strength=.6, dist=.002), 'kilt')
    linen = m_kilt('SashLinen', 512); z = KILT_TOP - .02
    pts = P.ring_on(Surf([sk]), z, .004, 72); pts.append(pts[0]); add(P.ribbon('Sash', pts, .042, .004), linen, 'kilt')
    sf2 = Surf([sk, out['Sash'][0]]); knot = [p for p in P.ring_on(sf2, z + .004, .004, 96)[64:81]]
    add(P.ribbon('SashKnot', [(p, n) for p, n in knot], .056, .006), linen, 'kilt')
    sandals(add, body, J, H.m_leather('SandalSole', '#5e4128'), H.m_leather('SandalStrap', '#7a5434'))

    # The scale corselets of the Veteran (bronze feathers) and the Elite (gilded)
    img2, h2 = scale_atlas('FeatherScales', 'feather'); img3, h3 = scale_atlas('GiltScales', 'round', seed=3)
    back2, _ = corselet('L2_', body, J, 'feather', add, H.m_leather('CorseletBack2', '#3a2a1c'), m_image('BronzeScales', img2, .4, h2, metal=.45, strength=.7, dist=.0025))
    back3, _ = corselet('L3_', body, J, 'round', add, H.m_leather('CorseletBack3', '#3a2a1c'), m_image('GiltScales', img3, .24, h3, metal=1.0, strength=.7, dist=.0025))

    # Broad collars: beads of turquoise, lapis and carnelian for the first two (on the skin, and
    # on the Veteran's corselet), gold and lapis for the Elite
    cg, carn = m_gold('CollarGold', res=256), H.m_flat('Carnelian', '#8e2f14', .25)
    beads = collar('L1_', [body], head, ROWS12, add, cg, carn)
    collar('L2_', [body, back2], head, ROWS12, add, cg, carn, mats=beads)
    collar('L3_', [body, back3], head, ROWS3, add, m_gold('CollarGold3', res=256), m_gold('GoldDrops', res=256))

    # Gold armlets (Veteran and Elite), wristguards, the Veteran's shield bands and shield
    for s in 'lr':
        armlet(f'L23_Armlet{s.upper()}', bvh, J[f'{s}-shoulder'], J[f'{s}-elbow'], .6, .068, add, gold, gold_rim, f'upperarm.{s.upper()}')
    wristguard('L23_WristguardR', body, J, 'r', add, gold, gold_rim)
    wristguard('L3_WristguardL', body, J, 'l', add, gold, gold_rim)
    strap = H.m_leather('ShieldStraps', '#4a2e18')
    for k, t in enumerate((.3, .74)): add(M.limb_band(f'L2_ShieldBand{k}', bvh, J['l-elbow'], J['l-hand'], t, .026, .006), strap, 'forearm.L')
    shield('L2_', add, M.m_cowhide('Cowhide'), H.m_leather('ShieldRim', '#3e2614'), strap)

    # The khopesh of each tier in the right fist, and the Elite's second in the left
    wood, band = H.m_wood('KhopeshGrip'), H.m_bronze('KhopeshBand', .15, 256)
    gilt = m_gold('KhopeshGilt', .25, 512, ('#a67c2c', '#ecc66a'))
    for tag, k, metal, s in (('L1_Khopesh', .86, m_gold('Khopesh1', 0, 512, ('#5e3f1e', '#94683a')), 'r'), ('L2_Khopesh', 1.0, m_gold('Khopesh2', .3, 512, ('#644422', '#9c7040')), 'r'),
                             ('L3_KhopeshR', .84, gilt, 'r'), ('L3_KhopeshL', .84, gilt, 'l')):
        Mg = grip_frame(J, s)
        for o, mt in khopesh(tag, k, (wood, metal, gold if tag.startswith('L3') else band)):
            o.matrix_world = Mg @ o.matrix_world; bpy.context.view_layer.update(); bake_obj_xform(o); add(o, mt, f'hand.{s.upper()}')
    return out

def place_shield(rig, items, J):
    """Strap the shield to the outside of the left forearm (rest pose), its round top towards
    the elbow, and note its facing in the forearm's frame for the Block."""
    E, W = J['l-elbow'], J['l-hand']; fdir = (W - E).normalized()
    out = V((1, 0, 0)); nrm = (out - fdir * out.dot(fdir)).normalized()
    H.FOREARM_N['L'] = (rig.data.bones['forearm.L'].matrix_local.to_3x3().inverted() @ nrm).normalized()
    ys = -fdir; xs = ys.cross(nrm)
    Mf = Matrix((xs, ys, nrm)).transposed().to_4x4(); Mf.translation = E + (W - E) * .5 + nrm * .062
    for name, (ob, mt, bind) in items.items():
        if bind != 'later:forearm.L': continue
        ob.matrix_world = Mf @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'forearm.L')


# ── Poses and moves ─────────────────────────────────────────────────────────
def poses(J):
    """Arm targets are offsets from each shoulder in the chest's rest frame; `blade` is where
    the khopesh's grip points (its blade lies beyond the thumb), the opposite of the knuckle
    line the solver orients the fist by. The fists are in the mesh, so the fingers stay."""
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-.4, 1, -.1), blade=(-.05, -1, -.2), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': tuple(-V(blade)), 'fist': 0, **kw}
    def armL(w, hint=(.4, 1, -.1), blade=(.05, -1, -.2), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': tuple(-V(blade)), 'fist': 0, **kw}
    base = {'hips': {'loc': (0, -.005, 0)}, 'chest': {'rot': (.02, 0, 0)}, 'neck': {'rot': (-.03, 0, 0)}, 'head': {'rot': (.03, 0, 0)},
            'ik_foot.L': {'loc': (-.035, -.02, 0)}, 'ik_foot.R': {'loc': (.035, .02, 0)},
            'armR': armR((-.14, -.1, -.48)), 'armL': armL((.14, -.1, -.48))}   # both fists a little forward, blades pointing ahead
    def st(**over):
        Pp = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): Pp[k] = v if k.startswith('arm') or k == 'knee' else {**Pp.get(k, {}), **v}
        return Pp
    return st, armR, armL

def actions(rig, J):
    """Idle, Walk, Cleave (the right blade cuts down from over the right shoulder, then the
    left arm sweeps across: the Elite's second blade, the Veteran's shield, the Warden's open
    hand), Block (the shield brought round to the front; the blades crossed for the Elite, the
    khopesh across for the Warden), Hit and Death."""
    st, armR, armL = poses(J); mk = H.make_action; A = []
    A.append(mk(rig, 'Idle', [(1, st()), (24, st(chest={'rot': (.035, 0, 0)}, head={'rot': (.05, 0, .14)}, neck={'rot': (-.02, 0, .06)})),
                              (48, st(chest={'rot': (.02, 0, 0)}, head={'rot': (0, 0, -.1)}, neck={'rot': (-.04, 0, -.04)})), (72, st())]))
    W = lambda fl, fr, zl, zr, hz, tw: st(**{'ik_foot.L': {'loc': (-.035, fl, zl)}, 'ik_foot.R': {'loc': (.035, fr, zr)},
                                            'hips': {'loc': (0, -.005 + hz, 0), 'rot': (0, tw * .08, 0)}, 'chest': {'rot': (.03, -tw * .1, 0)},
                                            'armR': armR((-.14, -.1 + .07 * tw, -.48)), 'armL': armL((.14, -.1 - .07 * tw, -.48))})
    A.append(mk(rig, 'Walk', [(1, W(-.25, .23, 0, 0, -.02, 1)), (9, W(-.01, -.01, 0, .1, .012, 0)), (17, W(.23, -.25, 0, 0, -.02, -1)),
                              (25, W(-.01, -.01, .1, 0, .012, 0)), (33, W(-.25, .23, 0, 0, -.02, 1))]))
    step = {'ik_foot.L': {'loc': (-.05, -.3, 0)}, 'ik_foot.R': {'loc': (.05, .08, 0)}}
    # A blade is held across the line of the forearm, so each key keeps it so: raised behind
    # the shoulder with the forearm upright, levelled forward as the arm comes down.
    upR = armR((-.3, .05, .21), hint=(-1, -.3, 0), blade=(.05, 1, .3)); upL = armL((.3, .05, .21), hint=(1, -.3, 0), blade=(-.05, 1, .3))
    guardR = armR((-.07, -.34, -.02), hint=(-1, .4, -.4), blade=(.3, -.6, .75)); guardL = armL((.07, -.34, -.02), hint=(1, .4, -.4), blade=(-.3, -.6, .75))
    A.append(mk(rig, 'Cleave', [
        (1, st()),
        (8, st(chest={'rot': (-.06, -.35, .05)}, hips={'loc': (0, .02, 0), 'rot': (0, -.12, 0)}, head={'rot': (0, .2, 0)}, armR=upR, armL=guardL)),
        (13, st(chest={'rot': (.28, .35, -.04)}, hips={'loc': (0, -.1, -.06), 'rot': (0, .12, 0)}, head={'rot': (.08, -.15, 0)}, **step,
                armR=armR((.1, -.46, -.06), hint=(-1, .3, -.2), blade=(.25, -.9, .3)), armL=armL((.15, -.1, -.4), blade=(.1, -1, -.3)))),
        (17, st(chest={'rot': (.3, .4, -.04)}, hips={'loc': (0, -.11, -.07), 'rot': (0, .14, 0)}, head={'rot': (.08, -.2, 0)}, **step,
                armR=armR((.22, -.32, -.28), hint=(-1, .3, -.1), blade=(.5, -.75, 0)), armL=upL)),
        (23, st(chest={'rot': (.28, -.35, .04)}, hips={'loc': (0, -.1, -.06), 'rot': (0, -.12, 0)}, head={'rot': (.08, .15, 0)}, **step,
                armR=guardR, armL=armL((-.1, -.46, -.06), hint=(1, .3, -.2), blade=(-.25, -.9, .3)))),
        (27, st(chest={'rot': (.26, -.4, .04)}, hips={'loc': (0, -.1, -.06), 'rot': (0, -.14, 0)}, head={'rot': (.08, .2, 0)}, **step,
                armR=guardR, armL=armL((-.22, -.32, -.28), hint=(1, .3, -.1), blade=(-.5, -.75, 0)))),
        (40, st())]))
    blk = dict(hips={'loc': (0, .03, -.06)}, chest={'rot': (.1, 0, 0)}, head={'rot': (.12, 0, 0)}, **{'ik_foot.L': {'loc': (-.05, -.16, 0)}},
               armR=armR((.04, -.36, .06), hint=(-1, .2, -.5), blade=(.55, -.25, 1)), armL=armL((-.05, -.36, .02), hint=(1, .2, -.5), blade=(-.55, -.25, 1), face=(0, -1, .1)))
    A.append(mk(rig, 'Block', [(1, st()), (6, st(**blk)), (15, st(**blk)), (22, st())]))
    A.append(mk(rig, 'Hit', [(1, st()),
        (5, st(chest={'rot': (-.22, 0, .12)}, head={'rot': (-.3, 0, .15)}, neck={'rot': (-.1, 0, 0)}, hips={'loc': (0, .06, -.02)},
               armR=armR((-.16, .02, -.42)), armL=armL((.17, .02, -.42)))),
        (11, st(chest={'rot': (-.06, 0, .04)}, head={'rot': (-.08, 0, 0)})), (22, st())]))
    kneel = dict(hips={'loc': (0, -.38, .05)}, chest={'rot': (.3, 0, .05)}, head={'rot': (.3, 0, 0)},
                 **{'ik_foot.L': {'loc': (-.05, .1, 0)}, 'ik_foot.R': {'loc': (.05, .14, 0)}}, knee=(.1, -1, 0),
                 armR=armR((-.12, -.18, -.45), blade=(-.1, -1, -.6)), armL=armL((.12, -.18, -.45), blade=(.1, -1, -.6)))
    fall = dict(chest={'rot': (-.1, 0, .05)}, head={'rot': (-.35, 0, .2)}, neck={'rot': (-.15, 0, 0)}, hips={'loc': (0, -.05, 0)},
                armR=armR((-.32, .05, -.2), hint=(-1, .2, -.3), blade=(-.3, -1, .1)), armL=armL((.32, .05, -.22), hint=(1, .2, -.3), blade=(.3, -1, .1)))
    A.append(mk(rig, 'Death', [(1, st()),
        (9, st(chest={'rot': (.15, 0, .1)}, head={'rot': (.3, 0, 0)}, hips={'loc': (0, -.06, 0)})),
        (20, st(**kneel)),
        (31, st(root={'loc': (0, .33, 0), 'rot': (-1.3, 0, .05)}, **fall)),
        (37, st(root={'loc': (0, .37, 0), 'rot': (-1.55, 0, .05)}, **fall)),
        (56, st(root={'loc': (0, .37, 0), 'rot': (-1.52, 0, .05)}, **fall))]))
    rig.animation_data.action = A[0]
    return A


# ── Build ───────────────────────────────────────────────────────────────────
SKIN_TRUNK = ('Collar', 'Corselet', 'Scales')   # skinned to the trunk alone

def build():
    body, J = H.build_body()
    M.broaden(body, J, .07, .05); T.define(body, J, .7); behead(body, J)
    J['head'] = px(686, 134)   # a jackal's head turns at the back of the skull
    b3 = link(body.copy()); b3.data = body.data.copy(); b3.name = 'L3_Body'
    T.clench(body, J, 'r', **HAFT); T.clench(body, J, 'l', **OPEN); body.name = 'L12_Body'
    T.clench(b3, J, 'lr', **HAFT)
    head = jackal_head('Head'); M.settle(head, body, 1.36, 1.44)
    items = kit(body, head, J)
    items['L12_Body'] = (body, m_skin(), 'body')
    items['Head'] = (head, m_fur('HeadFur', 2048, decal=face_paint()), 'body')
    items['Fur'] = (fur_strands('Fur', head), H.m_flat('FurStrands', '#151311', .8), 'neck-weights')
    shared = {n: n.replace('L2_', 'L1_') for n in items if n.startswith('L2_Collar')}   # the same beads in the same UVs
    shared['L3_Body'] = 'L12_Body'                                                         # the same mesh and UVs: the same skin
    H.bake_textures({n: it for n, it in items.items() if n not in shared})
    for n, src in shared.items():
        ob = items[n][0] if n in items else b3; ob.data.materials.clear(); ob.data.materials.append(items[src][0].data.materials[0])
    rig = H.build_armature(H.skeleton_spec(J), J); rig.name = 'AnubiteRig'; rig.data.name = 'AnubiteRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    T.copy_weights(body, b3); weight_head(head, J); weight_head(items['Fur'][0], J)
    for ob in (b3, head, items['Fur'][0]):
        mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
        m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    place_shield(rig, items, J)
    for name, (ob, mt, bind) in items.items():
        if bind in ('body', 'neck-weights') or bind.startswith('later:'): continue
        if bind == 'kilt': H.bind_skin(ob, rig, body); weight_skirt(ob, J)
        elif bind == 'skin':
            H.bind_skin(ob, rig, body)
            if any(k in name for k in SKIN_TRUNK): T.trunk_only(ob)
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    return rig, actions(rig, J)

def renders(rig):
    from PIL import Image
    shots = []
    for lv in (1, 2, 3):
        p = os.path.join(OUT, f'anubite_L{lv}.png')
        H.render(rig, p, 'Idle', 1, lv, cam=((2.6, -4.6, 1.6), (84, 0, 29)), res=(520, 760), samples=24); shots.append(p)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height)); x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'anubite_lineup.png'))

if __name__ == '__main__':
    rig, acts = build()
    rig.scale = (SCALE,) * 3; H._upd()
    H.export(rig, os.path.join(OUT, 'anubite.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'anubite.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
