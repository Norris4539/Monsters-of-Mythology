"""Builds the Heroes III-style Hoplite line in Blender and exports it as one glTF.

Run with Blender's Python (pip install bpy pillow):
    python tools/blender/hoplite.py assets/models [--renders] [--blend]
Writes hoplite.glb (and optionally preview stills and the .blend file).
tools/blender/glb2json.py turns the .glb into a self-contained .json glTF for
hosts that cannot serve binary model files.

One body and skeleton carry all three levels; each piece of kit is a separate
object whose name starts with its level tag, so the game shows one level at a
time by name:
    L1_  Ephebe       felt pilos, undyed tunic, black chlamys, plain shield
    L2_  Hoplite      Corinthian helmet, linothorax, greaves, Gorgon shield
    L3_  Sacred Band  crested Attic helmet, bronze muscle cuirass, crimson cloak, club shield
    L23_ shared by levels 2 and 3 (greaves, beard)
Untagged objects are worn by every level.

Animations (24 fps): Idle, Walk, Thrust, Block, Hit, Death.
The spear and shield are bones; the hands reach them by IK, so an animation
only moves the body, the spear, the shield and the feet.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

OUT = next((a for a in sys.argv[1:] if os.path.isdir(a)), os.path.dirname(os.path.abspath(__file__)))
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
V = Vector


# ── Helpers ─────────────────────────────────────────────────────────────────
def link(ob):
    SC.collection.objects.link(ob)
    return ob

MATS = {}
def mat(name, color, metal=0.0, rough=0.6, image=None):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if image:
        t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = image
        m.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
    MATS[name] = m
    return m

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)

# Heroes III palette: saturated, warm, readable at small size.
C = {
    'skin': srgb('#d08a5c'), 'bronze': srgb('#c98a3a'), 'bronzeDk': srgb('#8a5a24'), 'gold': srgb('#e7b84a'),
    'linen': srgb('#e9dfc4'), 'tunic': srgb('#d8c9a2'), 'leather': srgb('#7a4422'), 'leatherRed': srgb('#8e2a1c'),
    'crimson': srgb('#a3161a'), 'black': srgb('#1c1714'), 'felt': srgb('#8a6438'), 'wood': srgb('#b88752'),
    'hair': srgb('#2e1d12'), 'iron': srgb('#9aa0a6'), 'crestRed': srgb('#c0171a'), 'blue': srgb('#2d4f9e'),
    'white': srgb('#f1ece0'), 'eye': srgb('#f4efe6'), 'iris': srgb('#3a2414'),
}

def obj_from_bm(name, bm, material=None, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if material: me.materials.append(material)
    if smooth:
        for p in me.polygons: p.use_smooth = True
    return ob

def bake_mods(ob):
    """Apply all modifiers by replacing the mesh with its evaluated copy."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data; ob.modifiers.clear(); ob.data = me
    bpy.data.meshes.remove(old)
    return ob

def subsurf(ob, lv=2):
    m = ob.modifiers.new('sub', 'SUBSURF'); m.levels = lv; m.render_levels = lv
    return bake_mods(ob)

def solidify(ob, t, offset=-1):
    m = ob.modifiers.new('sol', 'SOLIDIFY'); m.thickness = t; m.offset = offset
    return bake_mods(ob)

def lathe(name, prof, segs=48, material=None, smooth=True):
    """Spin a (radius, z) profile around Z."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in prof]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=segs, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    return obj_from_bm(name, bm, material, smooth)

def metaballs(name, elems, res=.016, thresh=.6, material=None):
    """elems: (kind, centre, radius, size or (a, b) for capsules, stiffness)."""
    mb = bpy.data.metaballs.new(name); mb.resolution = res; mb.render_resolution = res; mb.threshold = thresh
    ob = link(bpy.data.objects.new(name, mb))
    for kind, p, r, size, stiff in elems:
        e = mb.elements.new()
        e.radius = r; e.stiffness = stiff
        if kind == 'SEG':
            a, b = V(p), V(size); d = b - a
            e.type = 'CAPSULE'; e.co = (a + b) / 2; e.size_x = d.length / 2
            e.rotation = d.normalized().to_track_quat('X', 'Z')
        else:
            e.type = kind; e.co = V(p)
            if kind == 'ELLIPSOID': e.size_x, e.size_y, e.size_z = size
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.metaballs.remove(mb)
    out = link(bpy.data.objects.new(name, me))
    for p in me.polygons: p.use_smooth = True
    if material: me.materials.append(material)
    return out

def B(p, r, st=2.5): return ('BALL', p, r, None, st)
def E(p, r, s, st=2.5): return ('ELLIPSOID', p, r, s, st)
def S(a, b, r, st=2.5): return ('SEG', a, r, b, st)

def shade_flat_ok(ob):
    for p in ob.data.polygons: p.use_smooth = True


# ── Body (heroic proportions, A-pose) ──────────────────────────────────────
K = 1.7
def body():
    el = [E((0, 0, 1.0), .16 * K, (.95, .75, .8)), E((0, .005, 1.14), .135 * K, (.9, .72, .9)), E((0, 0, 1.32), .19 * K, (1.2, .74, .85), 2.2)]
    for s in (-1, 1):
        el += [E((s * .085, -.07, 1.37), .09 * K, (1, .55, .7), 3.5), B((s * .215, 0, 1.445), .09 * K, 3.2),
               E((s * .11, .02, 1.49), .075 * K, (1.2, .8, .7), 3), E((s * .12, .07, 1.32), .095 * K, (.8, .5, 1.2), 3)]
    el += [S((0, 0, 1.48), (0, -.01, 1.64), .065 * K)]
    for s in (-1, 1):
        sh, elb, wr, ha = V((s * .22, 0, 1.44)), V((s * .4, .01, 1.22)), V((s * .54, -.02, 1.03)), V((s * .6, -.03, .95))
        el += [S(sh, elb, .055 * K), E(sh.lerp(elb, .45) + V((0, .015, 0)), .066 * K, (1, .82, .82), 3.5),
               S(elb, wr, .042 * K), E(elb.lerp(wr, .3), .056 * K, (1, .85, .85), 3.5), E(ha, .048 * K, (.65, 1, 1.15), 3)]
        hp, kn, an, toe = V((s * .1, 0, .95)), V((s * .12, -.01, .52)), V((s * .12, .02, .1)), V((s * .12, -.13, .03))
        el += [S(hp, kn, .075 * K), E(hp.lerp(kn, .45) + V((0, -.02, 0)), .09 * K, (.9, .9, 1.3), 3),
               B(kn + V((0, -.02, 0)), .055 * K, 3), S(kn, an, .05 * K), E(kn.lerp(an, .3) + V((0, .035, 0)), .066 * K, (.85, .9, 1.3), 3.5),
               S(an + V((0, .01, -.05)), toe, .045 * K, 3)]
    return metaballs('Body', el, .015, material=mat('Skin', C['skin'], 0, .55))

def head():
    el = [E((0, -.005, 1.735), .1 * K, (.92, 1, 1.08), 2.5), E((0, -.04, 1.655), .068 * K, (1, .95, .85), 3),
          S((0, -.098, 1.722), (0, -.118, 1.685), .018 * K, 4), E((0, -.088, 1.742), .05 * K, (1.45, .45, .35), 4),
          B((0, -.08, 1.612), .034 * K, 3.5)]
    for s in (-1, 1):
        el += [B((s * .045, -.075, 1.695), .03 * K, 3.5), E((s * .098, -.005, 1.71), .025 * K, (.5, 1, 1.4), 4)]
    h = metaballs('Head', el, .008, material=mat('Skin', C['skin']))
    for s in (-1, 1):
        for nm, r, y, col in (('EyeW', .014, -.083, C['eye']), ('Iris', .008, -.094, C['iris'])):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=16, ring_count=10, location=(s * .036, y, 1.712))
            e = bpy.context.object; e.name = f'{nm}{"RL"[s > 0]}'; e.data.materials.append(mat(nm, col, 0, .2)); shade_flat_ok(e)
    return h

def curls(name, pts, r, material, jitter=.008):
    el = [B(V(p) + V((random.uniform(-jitter, jitter), random.uniform(-jitter, jitter), random.uniform(-jitter, jitter))), r * K * random.uniform(.85, 1.15), 4.5) for p in pts]
    return metaballs(name, el, .006, material=material)

def beard():
    pts = []
    for i in range(26):
        a = -1.25 + 2.5 * i / 25
        for z, rr in ((1.645, .078), (1.615, .07), (1.59, .055)):
            if abs(a) > 1.05 and z < 1.6: continue
            pts.append((math.sin(a) * rr, -math.cos(a) * rr * .95 - .035, z))
    pts += [(s * .02, -.1, 1.665) for s in (-1, 0, 1)]
    return curls('L23_Beard', pts, .016, mat('Hair', C['hair'], 0, .8))

def hair():
    pts = []
    for i in range(30):
        a = math.pi * (.35 + 1.3 * i / 29)
        for z in (1.68, 1.715, 1.75):
            pts.append((math.sin(a) * .1, -math.cos(a) * .1 + .005, z))
    return curls('Hair', pts, .017, mat('Hair', C['hair'], 0, .8))


# ── Kit ─────────────────────────────────────────────────────────────────────
HEAD_C = V((0, -.005, 1.735))

def corinthian():
    """Bronze shell with the T-shaped face opening, flared neck guard and a tall crest."""
    prof = [(0, .145), (.05, .14), (.095, .11), (.122, .06), (.13, 0), (.128, -.06), (.122, -.11), (.13, -.15), (.15, -.17)]
    h = lathe('L2_Helmet', prof, 56, mat('Bronze', C['bronze'], .85, .32))
    h.scale = (.9, 1.0, 1.0); h.location = HEAD_C + V((0, 0, .005))
    bpy.context.view_layer.update()
    # Face opening: eye slots joined to a vertical slot down the middle.
    bm = bmesh.new()
    for x0, x1, z0, z1 in ((-.075, .075, -.005, .03), (-.022, .022, -.17, .03)):
        bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation(((x0 + x1) / 2, -.12, (z0 + z1) / 2)) @ Matrix.Diagonal((x1 - x0, .12, z1 - z0, 1)))
    cut = obj_from_bm('cut', bm, smooth=False); cut.location = h.location
    bo = h.modifiers.new('cut', 'BOOLEAN'); bo.object = cut; bo.operation = 'DIFFERENCE'; bo.solver = 'EXACT'
    bake_mods(h); bpy.data.objects.remove(cut)
    solidify(h, .008); subsurf(h, 1)
    crest = crest_mesh('L2_Crest', C['black'], C['white'], h.location + V((0, .01, .14)), length=.34, tall=.15)
    return [h, crest]

def crest_mesh(name, ca, cb, at, length=.34, tall=.15, width=.045, transverse=False):
    """Horsehair crest: a curved fin with a ridge of stripes, plus the trailing tail."""
    bm = bmesh.new()
    n = 18
    rows = []
    for i in range(n + 1):
        t = i / n; y = (t - .5) * length
        top = tall * (math.sin(t * math.pi) ** .6) * (1.08 - .25 * t)
        tail = max(0, t - .78) * 2.6
        rows.append([bm.verts.new((sx * width / 2 * (1 - .2 * abs(t - .5)), y, top * k - tail * (k * .55))) for sx in (-1, 1) for k in (0, 1)])
    for i in range(n):
        a, b = rows[i], rows[i + 1]
        for q in ((a[0], b[0], b[1], a[1]), (a[2], a[3], b[3], b[2]), (a[1], b[1], b[3], a[3]), (a[0], a[2], b[2], b[0])):
            bm.faces.new(q)
    ob = obj_from_bm(name, bm, mat('Crest' + name, ca, 0, .85))
    ob.data.materials.append(mat('Crest2' + name, cb, 0, .85))
    for p in ob.data.polygons:   # stripes across the fin
        p.material_index = int((p.center.y / length + .5) * 7) % 2
    if transverse: ob.rotation_euler.z = math.pi / 2
    ob.location = at
    subsurf(ob, 2)
    holder = lathe(name + 'Holder', [(.012, 0), (.016, .02), (.01, .03)], 16, mat('Bronze', C['bronze']))
    holder.location = at - V((0, 0, .02))
    return [ob, holder]

def attic():
    """Attic helmet: open face, brow peak, hinged cheek guards, tall red crest and a gilded brow band."""
    prof = [(0, .15), (.055, .143), (.1, .11), (.125, .055), (.132, 0), (.128, -.03), (.136, -.05)]
    h = lathe('L3_Helmet', prof, 56, mat('Bronze', C['bronze'], .85, .32)); h.scale = (.9, 1.0, 1.0); h.location = HEAD_C + V((0, 0, .04))
    solidify(h, .008); subsurf(h, 1)
    parts = [h]
    peak = lathe('L3_Peak', [(.118, .0), (.15, -.012), (.155, -.016)], 40, mat('Gold', C['gold'], 1, .25))
    peak.location = HEAD_C + V((0, -.012, .055)); peak.scale = (.92, 1.02, 1)
    parts.append(peak)
    for s in (-1, 1):
        bm = bmesh.new()
        pts = [(0, 0), (.0, -.11), (-.03, -.135), (-.07, -.12), (-.085, -.04), (-.07, 0)]
        vs = [bm.verts.new((s * .118, y + .02, z)) for y, z in [(p[0] * -1 - .0, p[1]) for p in pts]]
        bm.faces.new(vs)
        ch = obj_from_bm(f'L3_Cheek{"RL"[s > 0]}', bm, mat('Bronze', C['bronze']))
        ch.location = HEAD_C + V((0, -.05, .02)); solidify(ch, .007); subsurf(ch, 1)
        parts.append(ch)
    parts += crest_mesh('L3_Crest', C['crestRed'], C['crestRed'], h.location + V((0, .0, .145)), length=.4, tall=.2, width=.055)
    return parts

def pilos():
    p = lathe('L1_Pilos', [(0, .2), (.03, .19), (.07, .13), (.1, .06), (.112, .0), (.116, -.02)], 40, mat('Felt', C['felt'], 0, .9))
    p.location = HEAD_C + V((0, 0, .05)); solidify(p, .006)
    return [p]

def torso_shell(name, grow, material, z0=.93, z1=1.52, abs_=True):
    el = [E((0, 0, 1.0), .16 * K + grow, (.95, .75, .8)), E((0, .005, 1.14), .135 * K + grow, (.9, .72, .9)),
          E((0, 0, 1.32), .19 * K + grow, (1.2, .74, .85), 2.2)]
    for s in (-1, 1):
        el += [E((s * .085, -.07, 1.37), .09 * K + grow, (1, .55, .7), 3.5), E((s * .11, .02, 1.49), .075 * K + grow * .5, (1.2, .8, .7), 3),
               E((s * .12, .07, 1.32), .095 * K + grow, (.8, .5, 1.2), 3)]
        if abs_:
            for z in (1.2, 1.12, 1.04):
                el.append(E((s * .045, -.105, z), .038 * K, (1, .55, .7), 5))
    ob = metaballs(name, el, .014, material=material)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    for co, no in ((V((0, 0, z0)), V((0, 0, -1))), (V((0, 0, z1)), V((0, 0, 1)))):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, clear_outer=True)
    # arm holes
    for s in (-1, 1):
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(s * .25, 0, 0), plane_no=(s, 0, 0), clear_outer=True)
    bm.to_mesh(ob.data); bm.free()
    return solidify(ob, .01, 1)

def muscle_cuirass():
    c = torso_shell('L3_Cuirass', .012, mat('Bronze', C['bronze'], .85, .32))
    for z, r in ((.935, .17), (1.515, .085)):
        band = lathe('L3_CuirassLip' + str(z), [(r * 1.02 + .012, z - .008), (r * 1.02 + .016, z), (r * 1.02 + .012, z + .008)], 48, mat('Gold', C['gold'], 1, .25))
        band.scale = (1.15 if z < 1 else 1.0, .8, 1)
    return [c]

def linothorax():
    m = mat('Linen', C['linen'], 0, .85)
    body_ = lathe('L2_Linothorax', [(.18, .93), (.175, 1.0), (.168, 1.1), (.18, 1.25), (.2, 1.38), (.19, 1.46), (.12, 1.53)], 48, m)
    body_.scale = (1.12, .85, 1)
    band = lathe('L2_LinoBand', [(.184, 1.06), (.186, 1.1), (.184, 1.14)], 48, mat('Meander', C['blue'], 0, .8)); band.scale = (1.12, .85, 1)
    scales = lathe('L2_LinoScales', [(.183, 1.15), (.188, 1.2), (.19, 1.26)], 48, mat('BronzeDk', C['bronzeDk'], .8, .4)); scales.scale = (1.12, .85, 1)
    out = [body_, band, scales]
    for s in (-1, 1):   # shoulder yoke flaps
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((s * .14, 0, 1.5)) @ Matrix.Diagonal((.13, .28, .03, 1)))
        f = obj_from_bm(f'L2_Yoke{"RL"[s > 0]}', bm, m); f.rotation_euler.y = s * -.35
        bev = f.modifiers.new('b', 'BEVEL'); bev.width = .012; bev.segments = 2; bake_mods(f)
        out.append(f)
    return out

def skirt(name, color, top=.99, bottom=.74, r0=.17, r1=.24, folds=14):
    o = lathe(name, [(r0, top), (r0 * .5 + r1 * .5, (top + bottom) / 2), (r1, bottom)], 64, mat('Cloth' + name, color, 0, .9))
    for v in o.data.vertices:
        a = math.atan2(v.co.y, v.co.x); k = (top - v.co.z) / (top - bottom)
        f = 1 + .06 * math.sin(a * folds) * k
        v.co.x *= f; v.co.y *= f * .82
    return o

def pteruges(name, color, z=.94, n=26, length=.17, r=.2, layers=2):
    obs = []
    bm = bmesh.new()
    for L in range(layers):
        for i in range(n):
            a = (i + L * .5) / n * 2 * math.pi
            c = V((math.cos(a) * (r + L * .008) * 1.12, math.sin(a) * (r + L * .008) * .86, z - L * .05))
            ln = length + L * .04
            m = Matrix.Translation(c - V((0, 0, ln / 2))) @ Matrix.Rotation(-a + math.pi / 2, 4, 'Z') @ Matrix.Rotation(.12 + L * .05, 4, 'X') @ Matrix.Diagonal((.035, .008, ln, 1))
            bmesh.ops.create_cube(bm, size=1, matrix=m)
    ob = obj_from_bm(name, bm, mat('Ptery' + name, color, 0, .75), smooth=False)
    return ob

def greaves():
    out = []
    for s in (-1, 1):
        g = lathe(f'L23_Greave{"RL"[s > 0]}', [(.052, .13), (.06, .2), (.075, .3), (.072, .4), (.066, .48), (.07, .53)], 32, mat('Bronze', C['bronze'], .85, .32))
        g.location = (s * .12, .025, 0); g.scale = (1, .95, 1)
        solidify(g, .006)
        out.append(g)
    return out

def sandals():
    out = []
    for s in (-1, 1):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((s * .12, -.05, .008)) @ Matrix.Diagonal((.1, .27, .016, 1)))
        so = obj_from_bm(f'Sandal{"RL"[s > 0]}', bm, mat('Leather', C['leather'], 0, .7), smooth=False)
        bev = so.modifiers.new('b', 'BEVEL'); bev.width = .006; bev.segments = 2; bake_mods(so)
        out.append(so)
        for zz in (.07, .11):
            st = lathe(f'SandalStrap{"RL"[s > 0]}{zz}', [(.052, zz - .008), (.054, zz), (.052, zz + .008)], 20, mat('Leather', C['leather']))
            st.location = (s * .12, .02, 0); out.append(st)
    return out

def blazon_image(kind):
    """Paint a shield face in the Heroes III manner: flat colour, bold shapes, dark outline."""
    from PIL import Image, ImageDraw
    S = 512; im = Image.new('RGBA', (S, S)); d = ImageDraw.Draw(im); m = S / 2
    if kind == 'L1':
        d.ellipse((0, 0, S, S), fill=(198, 152, 74)); d.ellipse((60, 60, S - 60, S - 60), outline=(40, 26, 14), width=16)
        d.polygon([(m, 120), (m + 120, 380), (m + 70, 380), (m, 220), (m - 70, 380), (m - 120, 380)], fill=(40, 26, 14))   # lambda for Lakedaimon-style recruits
    elif kind == 'L2':
        d.ellipse((0, 0, S, S), fill=(214, 160, 80))
        for k in range(16):
            a = k / 16 * 2 * math.pi
            x0, y0 = m + math.cos(a) * 90, m + math.sin(a) * 90
            x1, y1 = m + math.cos(a + .35) * 150, m + math.sin(a + .35) * 150
            d.line((x0, y0, x1, y1), fill=(30, 20, 14), width=16); d.ellipse((x1 - 13, y1 - 13, x1 + 13, y1 + 13), fill=(30, 20, 14))
        d.ellipse((m - 95, m - 95, m + 95, m + 95), fill=(30, 20, 14))
        for dx in (-38, 38):
            d.ellipse((m + dx - 20, m - 40, m + dx + 20, m), fill=(240, 232, 214)); d.ellipse((m + dx - 9, m - 29, m + dx + 9, m - 11), fill=(160, 20, 20))
        d.chord((m - 50, m + 10, m + 50, m + 70), 0, 180, fill=(240, 232, 214)); d.ellipse((m - 14, m + 35, m + 14, m + 85), fill=(170, 24, 24))
    else:
        d.ellipse((0, 0, S, S), fill=(238, 230, 212)); d.ellipse((24, 24, S - 24, S - 24), outline=(150, 22, 24), width=26)
        cx, cy = m, m
        pts = [(cx - 22, cy + 160), (cx + 22, cy + 160), (cx + 62, cy - 150), (cx, cy - 190), (cx - 62, cy - 150)]
        d.polygon(pts, fill=(30, 22, 16))
        for k in range(9):
            t = k / 8; y = cy + 130 - t * 300; w = 26 + 34 * t
            d.ellipse((cx + (w if k % 2 else -w) - 18, y - 18, cx + (w if k % 2 else -w) + 18, y + 18), fill=(30, 22, 16))
    path = os.path.join(OUT, f'blazon_{kind}.png'); im.save(path)
    img = bpy.data.images.load(path); img.pack()
    return img

SHIELD_C = V((-.14, -.36, 1.17))
def aspis(level):
    R, rim = .5, .06
    tag = f'L{level}_'
    face = lathe(tag + 'ShieldFace', [(0, .1), (.15, .095), (.3, .075), (.4, .045), (R - rim, .0)], 64, None)
    # planar UVs for the painted blazon
    me = face.data; uv = me.uv_layers.new(name='UV')
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x / (2 * (R - rim)) + .5, co.y / (2 * (R - rim)) + .5)
    me.materials.append(mat(f'Blazon{level}', (1, 1, 1), .25 if level == 2 else 0, .45, blazon_image(f'L{level}')))
    rimo = lathe(tag + 'ShieldRim', [(R - rim, .0), (R - rim * .5, .012), (R, .0), (R + .006, -.02), (R - .01, -.03)], 64, mat('Bronze', C['bronze'], .85, .32))
    back = lathe(tag + 'ShieldBack', [(0, .07), (.25, .05), (R - .01, -.03)], 48, mat('Wood', C['wood'], 0, .8))
    for o in (face, rimo, back):   # face the enemy: the dome points along -Y
        o.rotation_euler.x = math.pi / 2; o.location = SHIELD_C
    return [face, rimo, back]

SPEAR_GRIP = V((.3, -.1, 1.52))
def spear():
    m_ash = mat('Ash', C['wood'], 0, .7)
    L0, L1 = .95, 1.55   # behind and in front of the grip
    shaft = lathe('SpearShaft', [(0, -L0), (.016, -L0 + .01), (.018, 0), (.016, L1), (0, L1 + .01)], 10, m_ash)
    head_ = lathe('SpearHead', [(.016, L1 - .02), (.034, L1 + .06), (.03, L1 + .16), (.0, L1 + .3)], 4, mat('Iron', C['iron'], .9, .35))
    head_.scale = (1, .35, 1)
    butt = lathe('SpearButt', [(.0, -L0 - .16), (.02, -L0 - .02), (.017, -L0 + .02)], 8, mat('Bronze', C['bronze']))
    out = [shaft, head_, butt]
    for o in out:   # lay the spear along -Y (forward), tip slightly down
        o.rotation_euler = (-math.pi / 2 + .08, 0, 0); o.location = SPEAR_GRIP
    return out

def cloak(name, color):
    bm = bmesh.new(); w, h, nx, nz = .5, .85, 12, 14
    grid = [[bm.verts.new(((i / nx - .5) * w, 0, -j / nz * h)) for i in range(nx + 1)] for j in range(nz + 1)]
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    ob = obj_from_bm(name, bm, mat('Cloak' + name, color, 0, .9))
    for v in ob.data.vertices:
        d = -v.co.z / h; x = v.co.x
        v.co.x = x * (1 + d * .35)
        v.co.y = .2 * (2 * x / w) ** 2 * (1 - d * .6) + .05 * math.sin(x * 30 + d * 3) * d + d * .12
    ob.location = (0, .17, 1.52)
    return solidify(ob, .01)


# ── Skeleton ────────────────────────────────────────────────────────────────
BONES = [  # name, head, tail, parent, deform
    ('root', (0, 0, 0), (0, .3, 0), None, False),
    ('hips', (0, .0, .97), (0, 0, 1.1), 'root', True),
    ('spine', (0, 0, 1.1), (0, 0, 1.28), 'hips', True),
    ('chest', (0, 0, 1.28), (0, 0, 1.48), 'spine', True),
    ('neck', (0, 0, 1.5), (0, -.01, 1.62), 'chest', True),
    ('head', (0, -.01, 1.62), (0, -.01, 1.86), 'neck', True),
]
for s, n in ((1, 'L'), (-1, 'R')):
    BONES += [
        (f'shoulder.{n}', (s * .05, 0, 1.46), (s * .2, 0, 1.445), 'chest', True),
        (f'upperarm.{n}', (s * .2, 0, 1.445), (s * .4, .01, 1.22), f'shoulder.{n}', True),
        (f'forearm.{n}', (s * .4, .01, 1.22), (s * .54, -.02, 1.03), f'upperarm.{n}', True),
        (f'hand.{n}', (s * .54, -.02, 1.03), (s * .62, -.03, .92), f'forearm.{n}', True),
        (f'thigh.{n}', (s * .1, 0, .95), (s * .12, -.01, .52), 'hips', True),
        (f'shin.{n}', (s * .12, -.01, .52), (s * .12, .02, .1), f'thigh.{n}', True),
        (f'ik_foot.{n}', (s * .12, .02, .1), (s * .12, .12, .1), 'root', False),
        (f'foot.{n}', (s * .12, .02, .1), (s * .12, -.13, .03), f'ik_foot.{n}', True),   # feet stay level, driven by the foot control
        (f'pole_knee.{n}', (s * .14, -.6, .55), (s * .14, -.5, .55), 'root', False),
    ]
BONES += [
    ('spear', tuple(SPEAR_GRIP), tuple(SPEAR_GRIP + V((0, .2, 0))), 'chest', True),
    ('shield', tuple(SHIELD_C), tuple(SHIELD_C + V((0, .2, 0))), 'chest', True),
    ('ik_hand.R', tuple(SPEAR_GRIP), tuple(SPEAR_GRIP + V((0, .1, 0))), 'spear', False),
    ('ik_hand.L', tuple(SHIELD_C + V((-.17, .09, -.02))), tuple(SHIELD_C + V((-.17, .19, -.02))), 'shield', False),
    ('pole_elbow.R', (-.7, .45, 1.55), (-.7, .55, 1.55), 'chest', False),
    ('pole_elbow.L', (.75, .2, 1.05), (.75, .3, 1.05), 'chest', False),
]

def build_armature():
    arm = bpy.data.armatures.new('HopliteRig'); ob = link(bpy.data.objects.new('HopliteRig', arm))
    bpy.context.view_layer.objects.active = ob; bpy.ops.object.mode_set(mode='EDIT')
    for name, h, t, parent, deform in BONES:
        b = arm.edit_bones.new(name); b.head = h; b.tail = t; b.roll = 0; b.use_deform = deform
        if parent: b.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='POSE')
    P = ob.pose.bones
    for side in 'LR':
        c = P[f'forearm.{side}'].constraints.new('IK'); c.target = ob; c.subtarget = f'ik_hand.{side}'
        c.pole_target = ob; c.pole_subtarget = f'pole_elbow.{side}'; c.pole_angle = math.radians(-90); c.chain_count = 2
        c = P[f'shin.{side}'].constraints.new('IK'); c.target = ob; c.subtarget = f'ik_foot.{side}'
        c.pole_target = ob; c.pole_subtarget = f'pole_knee.{side}'; c.pole_angle = math.radians(-90); c.chain_count = 2
    for pb in P: pb.rotation_mode = 'XYZ'
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob

def bind_rigid(ob, rig, bone):
    mw = ob.matrix_world.copy()
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = bone
    bpy.context.view_layer.update(); ob.matrix_world = mw

def bind_skin(ob, rig, body_ob):
    """Copy skin weights from the nearest point on the body (for cloth and armour that bends)."""
    bvh = BVHTree.FromObject(body_ob, bpy.context.evaluated_depsgraph_get())
    groups = {g.index: g.name for g in body_ob.vertex_groups}
    for g in body_ob.vertex_groups: ob.vertex_groups.new(name=g.name)
    bme = body_ob.data
    for v in ob.data.vertices:
        co = ob.matrix_world @ v.co
        loc, no, fi, dist = bvh.find_nearest(body_ob.matrix_world.inverted() @ co)
        if fi is None: continue
        acc = {}
        for vi in bme.polygons[fi].vertices:
            for ge in bme.vertices[vi].groups:
                acc[ge.group] = acc.get(ge.group, 0) + ge.weight
        tot = sum(acc.values()) or 1
        for gi, w in acc.items():
            ob.vertex_groups[groups[gi]].add([v.index], w / tot, 'REPLACE')
    ob.parent = rig
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig


# ── Animation ───────────────────────────────────────────────────────────────
def key(rig, frame, pose):
    """pose: {bone: dict(loc=(x,y,z), rot=(x,y,z))}; unspecified bones return to rest."""
    for pb in rig.pose.bones:
        p = pose.get(pb.name, {})
        pb.location = p.get('loc', (0, 0, 0)); pb.rotation_euler = p.get('rot', (0, 0, 0))
        pb.keyframe_insert('location', frame=frame); pb.keyframe_insert('rotation_euler', frame=frame)

def make_action(rig, name, frames, loop=False):
    rig.animation_data_create()
    act = bpy.data.actions.new(name); act.use_fake_user = True
    rig.animation_data.action = act
    for f, pose in frames:
        key(rig, f, pose)
    act.frame_range = (frames[0][0], frames[-1][0])
    return act

def stance(**over):
    """The guard stance: left foot forward, knees soft, spear overhand, shield up."""
    p = {
        'hips': {'loc': (0, 0, -.06)},
        'chest': {'rot': (.04, 0, .12)},
        'head': {'rot': (-.04, 0, -.1)},
        'ik_foot.L': {'loc': (0, -.2, 0)}, 'ik_foot.R': {'loc': (.02, .2, 0)},
    }
    for k, v in over.items():
        p.setdefault(k, {}); p[k] = {**p[k], **v}
    return p

def actions(rig):
    acts = []
    acts.append(make_action(rig, 'Idle', [
        (1, stance()), (24, stance(hips={'loc': (0, 0, -.072)}, chest={'rot': (.06, 0, .12)}, spear={'loc': (0, 0, -.012)})), (48, stance())]))
    W = lambda fl, fr, zl, zr, hz: stance(**{'ik_foot.L': {'loc': (0, fl, zl)}, 'ik_foot.R': {'loc': (.02, fr, zr)}, 'hips': {'loc': (0, 0, -.06 + hz)}})
    acts.append(make_action(rig, 'Walk', [
        (1, W(-.24, .22, 0, 0, -.015)), (7, W(-.02, -.02, 0, .1, .02)), (13, W(.22, -.24, 0, 0, -.015)), (19, W(-.02, -.02, .1, 0, .02)), (25, W(-.24, .22, 0, 0, -.015))]))
    acts.append(make_action(rig, 'Thrust', [
        (1, stance()),
        (7, stance(spear={'loc': (.02, .26, .04), 'rot': (-.12, 0, 0)}, chest={'rot': (-.06, 0, .3)}, hips={'loc': (0, .05, -.06)})),
        (11, stance(spear={'loc': (-.04, -.55, -.1), 'rot': (.12, 0, -.06)}, chest={'rot': (.22, 0, -.08)}, hips={'loc': (0, -.14, -.11)},
                    **{'ik_foot.L': {'loc': (0, -.42, 0)}}, shield={'loc': (.02, .06, -.04)})),
        (16, stance(spear={'loc': (-.04, -.5, -.1), 'rot': (.1, 0, -.06)}, chest={'rot': (.2, 0, -.06)}, hips={'loc': (0, -.13, -.11)},
                    **{'ik_foot.L': {'loc': (0, -.42, 0)}})),
        (25, stance())]))
    acts.append(make_action(rig, 'Block', [
        (1, stance()),
        (6, stance(shield={'loc': (.06, -.14, .12), 'rot': (-.2, 0, -.15)}, hips={'loc': (0, .02, -.13)}, chest={'rot': (.12, 0, .2)}, head={'rot': (.1, 0, -.1)}, spear={'loc': (0, .1, -.05)})),
        (14, stance(shield={'loc': (.06, -.14, .12), 'rot': (-.2, 0, -.15)}, hips={'loc': (0, .02, -.13)}, chest={'rot': (.12, 0, .2)}, head={'rot': (.1, 0, -.1)}, spear={'loc': (0, .1, -.05)})),
        (20, stance())]))
    acts.append(make_action(rig, 'Hit', [
        (1, stance()),
        (4, stance(chest={'rot': (-.28, 0, .25)}, head={'rot': (-.35, 0, .1)}, hips={'loc': (0, .1, -.08)}, shield={'loc': (0, .12, .04), 'rot': (.15, 0, 0)}, spear={'loc': (0, .12, .08)})),
        (9, stance(chest={'rot': (-.12, 0, .16)}, head={'rot': (-.15, 0, 0)}, hips={'loc': (0, .05, -.07)})),
        (17, stance())]))
    acts.append(make_action(rig, 'Death', [
        (1, stance()),
        (8, stance(chest={'rot': (.35, 0, .2)}, head={'rot': (.3, 0, 0)}, hips={'loc': (0, .02, -.24)}, spear={'loc': (0, .1, -.1), 'rot': (.3, 0, .2)})),
        (20, stance(root={'loc': (0, .28, 0), 'rot': (-1.38, 0, .08)}, chest={'rot': (-.15, 0, .1)}, head={'rot': (-.3, 0, .2)}, hips={'loc': (0, 0, -.1)},
                    spear={'loc': (.1, .2, -.05), 'rot': (-.8, .4, .5)}, shield={'loc': (-.05, .1, .05), 'rot': (.6, 0, .3)})),
        (25, stance(root={'loc': (0, .3, 0), 'rot': (-1.52, 0, .08)}, chest={'rot': (-.1, 0, .1)}, head={'rot': (-.4, 0, .2)}, hips={'loc': (0, 0, -.1)},
                    spear={'loc': (.1, .2, -.05), 'rot': (-.8, .4, .5)}, shield={'loc': (-.05, .1, .05), 'rot': (.6, 0, .3)})),
        (40, stance(root={'loc': (0, .3, 0), 'rot': (-1.5, 0, .08)}, chest={'rot': (-.1, 0, .1)}, head={'rot': (-.45, 0, .25)}, hips={'loc': (0, 0, -.1)},
                    spear={'loc': (.1, .2, -.05), 'rot': (-.8, .4, .5)}, shield={'loc': (-.05, .1, .05), 'rot': (.6, 0, .3)}))]))
    for a in acts:   # crisp, game-like timing
        for fc in a.fcurves if hasattr(a, 'fcurves') else []:
            for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'
    rig.animation_data.action = acts[0]
    return acts


# ── Painted shading: bake ambient occlusion into vertex colours ─────────────
def bake_ao(objs):
    SC.render.engine = 'CYCLES'; SC.cycles.samples = 48; SC.cycles.device = 'CPU'
    SC.render.bake.target = 'VERTEX_COLORS'
    for ob in objs:
        if ob.type != 'MESH': continue
        me = ob.data
        if not me.color_attributes:
            me.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        me.color_attributes.active_color = me.color_attributes[0]
        bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob
        try:
            bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
        except Exception as e:
            print('AO bake failed for', ob.name, e)
        # Lift the shadows a little and warm them, like a painted sprite.
        ca = me.color_attributes[0]
        for d in ca.data:
            a = d.color[0]; a = .35 + .65 * a
            d.color = (min(1, a * 1.04), a, a * .94, 1)


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    rig = build_armature()
    bod = body(); hd = head()
    kit = {'rigid': [], 'skin': []}
    eyes = [o for o in SC.objects if o.name.startswith(('EyeW', 'Iris'))]
    hr = hair(); bd = beard()
    helm2 = corinthian(); helm3 = attic(); helm1 = pilos()
    for o in [hd, hr, bd, *eyes, *helm1, helm2[0], *helm2[1], *helm3]:
        kit['rigid'].append((o, 'head'))
    tunic = skirt('L1_Tunic', C['tunic'], top=1.5, bottom=.74, r0=.2, r1=.25, folds=18)
    for v in tunic.data.vertices:   # follow the torso a little
        z = v.co.z; k = 1 if z > 1.2 else .9
        v.co.x *= k * 1.0; v.co.y *= .85
    chiton = skirt('L23_Chiton', C['linen'], top=1.0, bottom=.76)
    pt2 = pteruges('L2_Pteruges', C['linen']); pt3 = pteruges('L3_Pteruges', C['leatherRed'])
    kit['skin'] += [tunic, chiton, pt2, pt3]
    for o in linothorax(): kit['rigid'].append((o, 'chest'))
    for o in muscle_cuirass(): kit['rigid'].append((o, 'chest'))
    for o in [x for x in SC.objects if x.name.startswith('L3_CuirassLip')]: kit['rigid'].append((o, 'chest'))
    for o in greaves(): kit['rigid'].append((o, 'shin.' + o.name[-1]))
    for o in sandals(): kit['rigid'].append((o, 'foot.' + ('L' if o.name.startswith(('SandalL', 'SandalStrapL')) else 'R')))
    for lv in (1, 2, 3):
        for o in aspis(lv): kit['rigid'].append((o, 'shield'))
    for o in spear(): kit['rigid'].append((o, 'spear'))
    kit['rigid'] += [(cloak('L1_Cloak', C['black']), 'chest'), (cloak('L3_Cloak', C['crimson']), 'chest')]
    # Bake AO with everything in place (rest pose), then bind.
    objs = [o for o in SC.objects if o.type == 'MESH']
    bake_ao(objs)
    # Bind in the true rest pose (IK off) so kit sits where it was modelled.
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    # Skin the body to the deform bones (spear and shield excluded).
    for n in ('spear', 'shield'): rig.data.bones[n].use_deform = False
    bpy.ops.object.select_all(action='DESELECT'); bod.select_set(True); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for n in ('spear', 'shield'): rig.data.bones[n].use_deform = True
    print('body groups', len(bod.vertex_groups), 'weighted verts', sum(1 for v in bod.data.vertices if v.groups))
    for o in kit['skin']: bind_skin(o, rig, bod)
    for o, bone in kit['rigid']: bind_rigid(o, rig, bone)
    rig.data.pose_position = 'POSE'; bpy.context.view_layer.update()
    acts = actions(rig)
    return rig, acts

def export(rig, path):
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    for o in rig.children_recursive: o.select_set(True)
    rig.animation_data.action = bpy.data.actions['Idle']; SC.frame_set(1)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_animation_mode='ACTIONS',
                              export_vertex_color='ACTIVE', export_def_bones=False, export_force_sampling=True,
                              export_optimize_animation_size=True, export_image_format='AUTO', export_yup=True)
    print('exported', path, os.path.getsize(path) // 1024, 'KB')

def render(rig, path, action='Idle', frame=1, level=2, cam=((2.2, -3.4, 1.45), (84, 0, 33)), res=(420, 560)):
    for o in SC.objects:
        if o.type == 'MESH':
            tag = o.name.split('_')[0]
            show = not tag.startswith('L') or not tag[1:].isdigit() or str(level) in tag[1:]
            o.hide_render = not show
    rig.animation_data.action = bpy.data.actions[action]; SC.frame_set(frame)
    if 'Cam' not in bpy.data.objects:
        bpy.ops.object.camera_add(); c = bpy.context.object; c.name = 'Cam'; c.data.lens = 50; SC.camera = c
        bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50), 0, math.radians(-30))); bpy.context.object.data.energy = 3.2
        bpy.ops.object.light_add(type='SUN', rotation=(math.radians(70), 0, math.radians(150))); bpy.context.object.data.energy = 1.2
        w = bpy.data.worlds.new('W'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (.32, .36, .4, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = .8; SC.world = w
        bpy.ops.mesh.primitive_plane_add(size=6); g = bpy.context.object; g.name = 'Ground'; g.data.materials.append(mat('Ground', srgb('#6f8f4a'), 0, .9))
    c = bpy.data.objects['Cam']; c.location = cam[0]; c.rotation_euler = [math.radians(a) for a in cam[1]]
    SC.render.engine = 'CYCLES'; SC.cycles.samples = 24; SC.render.resolution_x, SC.render.resolution_y = res
    SC.render.film_transparent = False; SC.render.filepath = path
    bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    rig, acts = build()
    export(rig, os.path.join(OUT, 'hoplite.glb'))
    if '--blend' in sys.argv:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'hoplite.blend'))
    if '--renders' in sys.argv:   # preview stills of each animation
        shots = [('Idle', 1, 2, 'a'), ('Walk', 7, 2, 'b'), ('Thrust', 7, 3, 'b'), ('Thrust', 11, 3, 'b'), ('Block', 8, 1, 'b'), ('Death', 30, 2, 'b')]
        cams = {'a': ((2.2, -3.4, 1.45), (84, 0, 33)), 'b': ((-2.9, -2.6, 1.35), (84, 0, -48))}
        for act, f, lv, cv in shots:
            render(rig, os.path.join(OUT, f'shot_{act}_{f}_L{lv}.png'), act, f, lv, cam=cams[cv], res=(340, 460))
    print('built', [a.name for a in acts])
