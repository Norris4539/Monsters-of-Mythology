"""Realistic Peltast line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/peltast.py third_party/makehuman assets/models [--renders]

Reuses the Hoplite pipeline (body, materials, cloth, rig, posing, baking) from
hoplite.py. Kit follows the reference sheets:
  L1 Peltast          undyed exomis, rope belt, barefoot, wicker pelte faced with hide
  L2 Thracian Peltast fox-skin alopekis, patterned zeira, fur-topped boots, painted pelte, sica
  L3 Agrianian        Thracian helmet, patterned tunic, olive cloak, laced boots, round shield, machaira
Spare javelins are held behind the shield; the one in the right hand is the node
'ThrowJavelin', which the game hides while its thrown copy is in the air.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
from hoplite import (link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, envelope, Mat,
                     m_bronze, m_skin, m_cloth, m_leather, m_wood, m_iron, m_hair, m_painted, drape, chiton, cloak)

# A leaner, wirier man than the hoplite.
H.TARGETS = [('caucasian-male-young.target', .75), ('african-male-young.target', .15), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .45), ('universal-male-young-averagemuscle-minweight.target', .55)]
H.HEIGHT = 1.74
SC = H.SC
OUT = H.OUT
random.seed(7)


# ── Materials ───────────────────────────────────────────────────────────────
def m_fur(name, hexcol, light='#d9c2a0', res=512):
    """Short pelt: streaky strands, a paler underside where the hide turns."""
    m = Mat(name, res=res)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (90, 90, 18)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=6.0, Detail=4.0); m.L.new(mp.outputs['Vector'], w.inputs['Vector'])
    c = srgb(hexcol)
    col = m.ramp(m.noise(9, 4, .6).outputs['Fac'], [(.3, tuple(x * .55 for x in c)), (.6, c), (.85, srgb(light))])
    col = m.mix(col.outputs['Color'], tuple(x * .6 for x in c), m.ramp(w.outputs['Fac'], [(.4, (0, 0, 0)), (.9, (1, 1, 1))]).outputs['Color'])
    m.set(col, .85, w.outputs['Fac'], .5, .003)
    return m

def m_wicker(name='Wicker', res=512):
    """Basket weave: over-under bands of willow."""
    m = Mat(name, res=res)
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=70.0); m.L.new(m.coord.outputs['UV'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=70.0); m.L.new(m.coord.outputs['UV'], w2.inputs['Vector'])
    chk = m.node('ShaderNodeTexChecker', Scale=22.0); m.L.new(m.coord.outputs['UV'], chk.inputs['Vector'])
    weave = m.mix(w1.outputs['Color'], w2.outputs['Color'], chk.outputs['Fac'])
    col = m.ramp(m.noise(25, 4, .6).outputs['Fac'], [(.3, srgb('#6b4a26')), (.7, srgb('#a07b48'))])
    col = m.mix(col.outputs['Color'], srgb('#3a2814'), m.ramp(weave, [(0, (1, 1, 1)), (.25, (0, 0, 0))]).outputs['Color'])
    m.set(col, .8, weave, .5, .002)
    return m

def m_rope(name='Rope', hexcol='#b8a27a', res=256):
    m = Mat(name, res=res)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='DIAGONAL', Scale=160.0); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    c = srgb(hexcol)
    m.set(m.ramp(w.outputs['Fac'], [(.2, tuple(x * .6 for x in c)), (.8, c)]).outputs['Color'], .85, w.outputs['Fac'], .4, .0015)
    return m

def m_pattern(name, stops, scale=9.0, zig=40.0, amp=.06, base_var=.08, res=1024):
    """Woven geometric bands (zigzags stepped across the width) in object space, so
    they run horizontally round the body like the Thracian textiles in the sheets."""
    m = m_cloth(name, '#ffffff', 420, base_var, res)
    weave_tex = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ang = m.node('ShaderNodeMath', operation='ARCTAN2'); m.L.new(sep.outputs['X'], ang.inputs[0]); m.L.new(sep.outputs['Y'], ang.inputs[1])
    zx = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(ang.outputs[0], zx.inputs[0]); zx.inputs[1].default_value = zig / 6.283
    pp = m.node('ShaderNodeMath', operation='PINGPONG'); m.L.new(zx.outputs[0], pp.inputs[0]); pp.inputs[1].default_value = .5
    st = m.node('ShaderNodeMath', operation='SNAP'); m.L.new(pp.outputs[0], st.inputs[0]); st.inputs[1].default_value = .125   # stepped, like weaving
    za = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(st.outputs[0], za.inputs[0]); za.inputs[1].default_value = amp * scale
    zs = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(sep.outputs['Z'], zs.inputs[0]); zs.inputs[1].default_value = scale
    f = m.node('ShaderNodeMath', operation='ADD'); m.L.new(zs.outputs[0], f.inputs[0]); m.L.new(za.outputs[0], f.inputs[1])
    fr = m.node('ShaderNodeMath', operation='FRACT'); m.L.new(f.outputs[0], fr.inputs[0])
    r = m.ramp(fr.outputs[0], [(p, srgb(c)) for p, c in stops]); r.color_ramp.interpolation = 'CONSTANT'
    col = m.mix(r.outputs['Color'], weave_tex, 1.0, 'MULTIPLY')
    m.L.new(col, m.bsdf.inputs['Base Color'])
    return m


# ── Shield faces (painted with PIL) ─────────────────────────────────────────
def shield_art(kind):
    from PIL import Image, ImageDraw, ImageFilter
    S = 1024; im = Image.new('RGB', (S, S), (0, 0, 0)); d = ImageDraw.Draw(im); m = S / 2
    blk, red, ochre, cream = (28, 20, 14), (142, 38, 26), (190, 140, 80), (226, 210, 178)
    if kind == 'face':   # Thracian pelte: a glaring painted face under the crescent
        d.rectangle((0, 0, S, S), fill=(184, 140, 86))
        for k in range(40):   # stepped border of red and black triangles on the rim
            a0, a1 = k / 40 * 2 * math.pi, (k + 1) / 40 * 2 * math.pi
            r0, r1 = 470, 410
            pts = [(m + math.cos(a0) * r0, m - math.sin(a0) * r0), (m + math.cos(a1) * r0, m - math.sin(a1) * r0), (m + math.cos((a0 + a1) / 2) * r1, m - math.sin((a0 + a1) / 2) * r1)]
            d.polygon(pts, fill=red if k % 2 else blk)
        cy = m + 70
        for sx in (-1, 1):
            ex = m + sx * 120
            d.ellipse((ex - 85, cy - 120, ex + 85, cy - 40), fill=cream, outline=blk, width=14)
            d.ellipse((ex - 34, cy - 114, ex + 34, cy - 46), fill=blk)
            d.arc((ex - 110, cy - 190, ex + 110, cy - 30), 200, 340, fill=blk, width=22)   # brow
            d.ellipse((ex - 40 + sx * 20, cy + 20, ex + 40 + sx * 20, cy + 100), outline=red, width=16)   # cheek whorls
        d.line([(m, cy - 70), (m, cy + 40)], fill=blk, width=18); d.line([(m - 34, cy + 50), (m + 34, cy + 50)], fill=blk, width=18)
        d.rectangle((m - 150, cy + 120, m + 150, cy + 200), fill=red, outline=blk, width=12)
        for k in range(9):   # teeth
            x0 = m - 140 + k * 31
            d.polygon([(x0, cy + 128), (x0 + 28, cy + 128), (x0 + 14, cy + 165)], fill=cream)
            d.polygon([(x0, cy + 192), (x0 + 28, cy + 192), (x0 + 14, cy + 160)], fill=cream)
    else:   # Agrianian round shield: dark wood, ochre band with a running meander
        d.rectangle((0, 0, S, S), fill=(92, 60, 36))
        rnd = random.Random(3)
        for k in range(160):   # planks' grain
            y = rnd.uniform(0, S); d.line([(0, y), (S, y + rnd.uniform(-20, 20))], fill=(70 + rnd.randint(-10, 10), 45, 26), width=rnd.randint(1, 3))
        for y in range(0, S, 128): d.line([(0, y), (S, y)], fill=(52, 34, 20), width=3)
        r0, r1 = 400, 488
        d.ellipse((m - r1, m - r1, m + r1, m + r1), outline=None, fill=ochre)
        d.ellipse((m - r0, m - r0, m + r0, m + r0), fill=None, outline=blk, width=8)
        im2 = im.copy(); d2 = ImageDraw.Draw(im2)
        N = 28
        key = [(0, .12), (1, .12), (1, .88), (.25, .88), (.25, .38), (.62, .38), (.62, .62)]
        for i in range(N):
            pts = []
            for u, r in key:
                a = (i + u) / N * 2 * math.pi; rr = r0 + 10 + r * (r1 - r0 - 20)
                pts.append((m + math.cos(a) * rr, m - math.sin(a) * rr))
            d2.line(pts, fill=blk, width=11, joint='curve')
        d2.ellipse((m - r1, m - r1, m + r1, m + r1), outline=blk, width=10)
        d2.ellipse((m - r0 + 60, m - r0 + 60, m + r0 - 60, m + r0 - 60), outline=(150, 40, 28), width=12)
        im = im2
    import numpy as np
    img = bpy.data.images.new(f'Art_{kind}', S, S)
    a = np.ones((S, S, 4), np.float32); a[..., :3] = np.asarray(im.transpose(Image.FLIP_TOP_BOTTOM), np.float32) / 255
    img.pixels.foreach_set(a.ravel()); img.pack()
    return img


# ── Geometry helpers ────────────────────────────────────────────────────────
def curve_mesh(name, polylines, depth, cyclic=False, radii=None, res=2):
    """Polylines as round tubes, converted to a mesh."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = depth; cu.bevel_resolution = res
    for k, pts in enumerate(polylines):
        sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1); sp.use_cyclic_u = cyclic
        for i, (pt, q) in enumerate(zip(sp.points, pts)):
            pt.co = (q[0], q[1], q[2], 1)
            if radii: pt.radius = radii(i / max(1, len(pts) - 1))
    cob = link(bpy.data.objects.new(name + '_c', cu)); bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(cob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(cob); bpy.data.curves.remove(cu)
    ob = link(bpy.data.objects.new(name, me))
    for p in me.polygons: p.use_smooth = True
    return ob

def ribbon(name, pts_normals, width, thick=.003):
    """A flat band through points, lying on the surface given by their normals."""
    bm = bmesh.new(); row = []
    for i, (p, nrm) in enumerate(pts_normals):
        nxt = pts_normals[min(i + 1, len(pts_normals) - 1)][0]; prv = pts_normals[max(i - 1, 0)][0]
        w = (nxt - prv).normalized().cross(nrm).normalized() * width / 2
        row.append((bm.verts.new(p - w), bm.verts.new(p + w)))
    for i in range(len(row) - 1): bm.faces.new((row[i][0], row[i + 1][0], row[i + 1][1], row[i][1]))
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=thick); bake_mods(ob)
    return ob

class Surf:
    """Outermost hit over several objects, for laying straps and belts on top of clothing."""
    def __init__(self, objs):
        dg = bpy.context.evaluated_depsgraph_get(); self.t = [BVHTree.FromObject(o, dg) for o in objs]
    def hit(self, o, d, far=.6):
        best = None
        for t in self.t:
            h = t.ray_cast(o + d * far, -d, far * 2)
            if h[0] and (best is None or (h[0] - o).dot(d) > (best[0] - o).dot(d)): best = h
        return best

def ring_on(surf, z, off, n=48, centre=V((0, 0, 0))):
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi; d = V((math.cos(a), math.sin(a), 0)); o = V((centre.x, centre.y, z))
        h = surf.hit(o, d)
        pts.append(((h[0] + h[1] * off) if h else o + d * .18, h[1] if h else d))
    return pts

def fringe(name, skirt, n=150, length=.032):
    """Short cords hanging from the lowest edge of a draped skirt."""
    vs = [skirt.matrix_world @ v.co for v in skirt.data.vertices]
    zmin = min(v.z for v in vs); low = [v for v in vs if v.z < zmin + .05]
    bins = {}
    for v in low:
        k = int((math.atan2(v.y, v.x) + math.pi) / (2 * math.pi) * n) % n
        r = V((v.x, v.y, 0)).length
        if k not in bins or v.z < bins[k].z - .002 or (abs(v.z - bins[k].z) < .002 and r > V((bins[k].x, bins[k].y, 0)).length): bins[k] = v
    bm = bmesh.new()
    for k, v in bins.items():
        out = V((v.x, v.y, 0)).normalized(); side = V((-out.y, out.x, 0)) * .0026
        top = v + out * .002 + V((0, 0, .004)); bot = top + V((0, 0, -length * random.uniform(.8, 1.1))) + out * .004
        a, b, c, e = bm.verts.new(top - side), bm.verts.new(top + side), bm.verts.new(bot + side), bm.verts.new(bot - side)
        bm.faces.new((a, b, c, e))
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.002); bake_mods(ob)
    return ob

def clear_of(ob, under, gap):
    """Push a draped panel radially outward wherever it dips into the clothes beneath."""
    sf = Surf(under); me = ob.data
    for v in me.vertices:
        d = V((v.co.x, v.co.y, 0))
        if d.length < 1e-4: continue
        d.normalize(); h = sf.hit(V((0, 0, v.co.z)), d)
        if not h: continue
        r_s = V((h[0].x, h[0].y, 0)).length; r_v = V((v.co.x, v.co.y, 0)).length
        if r_v < r_s + gap: v.co.x, v.co.y = d.x * (r_s + gap), d.y * (r_s + gap)
    me.update()

def relax_rim(ob, iters=5):
    """Smooth the open edge of a shell cut from the body so it reads as a clean rim."""
    bm = bmesh.new(); bm.from_mesh(ob.data)
    for _ in range(iters):
        new = {}
        for v in bm.verts:
            if not v.is_boundary: continue
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2: new[v] = v.co * .5 + (nb[0].co + nb[1].co) * .25
        for v, co in new.items(): v.co = co
    bm.to_mesh(ob.data); bm.free()

def boundary_loop(bm):
    edges = [e for e in bm.edges if e.is_boundary]
    if not edges: return []
    nb = {}
    for e in edges:
        a, b = e.verts; nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)
    start = edges[0].verts[0]; loop = [start]; prev, cur = None, start
    while True:
        nxt = [v for v in nb[cur] if v is not prev]
        if not nxt or nxt[0] is start: break
        prev, cur = cur, nxt[0]; loop.append(cur)
        if len(loop) > len(nb): break
    return [v.co.copy() for v in loop]


# ── Shields: built about the hand grip (origin), facing +Z ──────────────────
def shield_mesh(name, R, notch=None, depth=.05, back=.045):
    """A dished disc with an optional crescent notch cut from the top: the pelte."""
    bm = bmesh.new(); rings, segs = 18, 96
    centre = bm.verts.new((0, 0, 0)); prev = None; grid = []
    for i in range(1, rings + 1):
        r = R * i / rings
        grid.append([bm.verts.new((math.cos(a) * r, math.sin(a) * r, 0)) for a in [2 * math.pi * j / segs for j in range(segs)]])
    for j in range(segs): bm.faces.new((centre, grid[0][j], grid[0][(j + 1) % segs]))
    for i in range(rings - 1):
        for j in range(segs): bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][(j + 1) % segs], grid[i][(j + 1) % segs]))
    if notch:
        c, rn = V((0, notch[0], 0)), notch[1]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.calc_center_median() - c).length < rn], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        for v in bm.verts:   # pull the ragged notch edge onto the arc
            if v.is_boundary and (v.co - c).length < rn + R / rings * 1.5 and v.co.length < R - 1e-4:
                v.co = c + (v.co - c).normalized() * rn
    for v in bm.verts:
        r2 = (v.co.x ** 2 + v.co.y ** 2) / (R * R); v.co.z = back + depth * (1 - r2)
    uvl = bm.loops.layers.uv.new('UV')
    for f in bm.faces:
        for lp in f.loops: lp[uvl].uv = (lp.vert.co.x / (2 * R) + .5, lp.vert.co.y / (2 * R) + .5)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    if bm.faces and bm.faces[0].normal.z < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    rim = boundary_loop(bm)
    return obj_from_bm(name, bm), rim

def shield(lv, kind, add):
    tag = f'L{lv}_'
    R = .34 if kind != 'round' else .31
    notch = (R * 1.02, R * .62) if kind != 'round' else None
    face, rim = shield_mesh(tag + 'ShieldFace', R, notch, .05 if kind != 'round' else .035)
    backm = face.copy(); backm.data = face.data.copy(); backm.name = tag + 'ShieldBack'; link(backm)
    for v in backm.data.vertices: v.co.z -= .006
    backm.data.flip_normals()
    mod(face, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(face)
    if kind == 'hide': fm = m_fur('Hide', '#6a4a2c', '#a88a62')
    elif kind == 'face': fm = m_painted('PelteFace', shield_art('face'), res=1024)
    else: fm = m_painted('RoundFace', shield_art('round'), res=1024)
    add(face, fm, 'later:hand.L')
    add(backm, m_wicker() if kind != 'round' else m_wood('ShieldPlanks'), 'later:hand.L')
    rimo = curve_mesh(tag + 'ShieldRim', [rim], .009 if kind != 'round' else .007, cyclic=True)
    add(rimo, m_wicker('WickerRim', 256) if kind != 'round' else bronze_, 'later:hand.L')
    # the grip: a leather-bound bar across the back, where the fist closes
    grip = curve_mesh(tag + 'ShieldGrip', [[(0, -.075, .045), (0, -.06, .02), (0, -.03, .0), (0, .03, .0), (0, .06, .02), (0, .075, .045)]], .0095)
    add(grip, m_leather('GripLeather', '#4a2e18'), 'later:hand.L')
    if kind != 'hide':
        boss = lathe(tag + 'ShieldBoss', [(0, .03), (.03, .026), (.05, .012), (.062, 0)], 32); boss.location = (0, -.02 if kind == 'face' else 0, .045 + (.05 if kind == 'face' else .035))
        add(boss, bronze_, 'later:hand.L')
    if kind == 'round':
        bvh = BVHTree.FromObject(face, bpy.context.evaluated_depsgraph_get())
        for i in range(12):
            a = i / 12 * 2 * math.pi; p = V((math.cos(a) * R * .88, math.sin(a) * R * .88, 1)); h = bvh.ray_cast(p, V((0, 0, -1)))
            if not h[0]: continue
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.009, segments=12, ring_count=6, location=h[0]); s = bpy.context.object
            s.name = f'{tag}ShieldStud{i}'; s.scale = (1, 1, .55); add(s, bronze_, 'later:hand.L')

def javelin(prefix, mats, loop=True):
    """A 1.5 m javelin built about its grip (origin), point to +Z, throwing loop at the grip."""
    ash, iron, leather = mats
    L0, L1 = .62, .86
    parts = [lathe(prefix + 'Shaft', [(0, -L0), (.0085, -L0 + .01), (.0095, 0), (.008, L1), (0, L1 + .004)], 10),
             lathe(prefix + 'Head', [(.0085, L1 - .03), (.012, L1 + .005), (.016, L1 + .05), (.011, L1 + .09), (0, L1 + .14)], 8)]
    parts[1].scale = (1, .35, 1)
    add_m = [ash, iron]
    if loop:
        pts = [(.0095 + .022 * math.sin(t * math.pi), 0, -.03 + .06 * t - .025 * math.sin(t * math.pi)) for t in [i / 12 for i in range(13)]]
        parts.append(curve_mesh(prefix + 'Loop', [pts], .0025, res=1)); add_m.append(leather)
        parts.append(lathe(prefix + 'Wrap', [(.0105, -.035), (.0112, 0), (.0105, .035)], 10)); add_m.append(leather)
    return list(zip(parts, add_m))


# ── Shared light-infantry kit ───────────────────────────────────────────────
def head_kit(body, J, add, beards, hair_col='#1d130c', volume=1.0, edge_hops=4):
    """Face kit shared by the light infantry: a beard per level (name, thickness,
    chin growth, colour), curly hair and eyes; beards thin out over edge_hops rings of
    vertices at their edge. Returns the hair, which helmets clear."""
    head, neck, eye, jaw = J['head'], J['neck'], J['l-eye'], J['jaw']
    bvh_b = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    def beard(name, thick, chin, col):
        """A beard shell with a drawn outline: moustache, bare lips and cheeks, sideburns
        up to the ear. Cut from a subdivided patch so the edge is smooth, then grown
        thicker away from the edge."""
        mz, ez = J['mouth'].z, eye.z
        prof = [(0, mz + .013), (.024, mz + .011), (.034, mz - .004), (.048, mz + .004), (.06, ez - .045), (.1, ez - .03)]
        def ztop(ax):
            for (x0, z0), (x1, z1) in zip(prof, prof[1:]):
                if ax <= x1: return z0 + (z1 - z0) * (ax - x0) / (x1 - x0)
            return prof[-1][1]
        def keep(c):
            if c.y > head.y + .02 or c.z < neck.z + .03 or c.z < jaw.z - .085: return False
            if (c.x / .025) ** 2 + ((c.z - mz + .003) / .0085) ** 2 < 1: return False
            return abs(c.x) < .085 and c.z < ztop(abs(c.x)) and (abs(c.x) < .055 or c.y > head.y - .065 or c.z < mz)
        bd = region_shell(name, body, lambda c: c.y < head.y + .03 and c.z > jaw.z - .1 and c.z < ez - .02 and abs(c.x) < .095, .0, 0)
        bm = bmesh.new(); bm.from_mesh(bd.data)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        for _ in range(4):
            new = {}
            for v in bm.verts:
                if not v.is_boundary: continue
                nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
                if len(nb) == 2: new[v] = v.co * .5 + (nb[0].co + nb[1].co) * .25
            for v, co in new.items(): v.co = co
        bm.verts.index_update()
        edge = [v for v in bm.verts if v.is_boundary]; dist = {v.index: 0 for v in edge}; front = list(edge)
        while front:
            nxt = []
            for v in front:
                for e in v.link_edges:
                    o = e.other_vert(v)
                    if o.index not in dist: dist[o.index] = dist[v.index] + 1; nxt.append(o)
            front = nxt
        nz = lambda p: math.sin(p.x * 310) * math.sin(p.z * 270 + p.x * 90) * math.sin(p.y * 330)
        for v in bm.verts:
            k = min(1, dist.get(v.index, 0) / edge_hops)
            ch = max(0, (mz - .02 - v.co.z)) * chin
            loc, no, fi, d = bvh_b.find_nearest(v.co)
            nrm = no if no is not None else v.normal
            v.co = (loc if loc is not None else v.co) + nrm * ((.0008 + thick * k + ch * k) * (1 + .3 * nz(v.co)))
        bm.to_mesh(bd.data); bm.free()
        for pl in bd.data.polygons: pl.use_smooth = True
        add(bd, m_hair(name + 'Hair', col), 'head')
    for b in beards: beard(*b)
    hair = region_shell('Hair', body, lambda c: (c.z > eye.z + .04 and c.y > eye.y + .05) or (c.z > eye.z + .08) or (c.z > jaw.z - .005 and c.y > head.y + .03 and c.z > neck.z + .04), .007, 3, .5, guard=.006)
    bm = bmesh.new(); bm.from_mesh(hair.data); bm.normal_update()
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True); bm.normal_update()
    curls = lambda p: (math.sin(p.x * 120 + math.sin(p.z * 100) * 2.5) * math.sin(p.z * 115 + math.sin(p.y * 105) * 2.5) * math.sin(p.y * 118 + p.x * 50))
    for v in bm.verts:
        edge = 0 if v.is_boundary else 1
        v.co += v.normal * edge * (.006 + .007 * curls(v.co)) * volume
    bm.to_mesh(hair.data); bm.free()
    mod(hair, 'SUBSURF', levels=1, render_levels=1); bake_mods(hair)
    add(hair, m_hair('CurlyHair', hair_col), 'head')
    for side in ('l', 'r'):
        e = J[f'{side}-eye']
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.0118, segments=24, ring_count=16, location=e + V((0, .004, 0)))
        ob = bpy.context.object; ob.name = 'Eye' + side.upper()
        em = Mat('Eye', res=128)
        grad = em.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
        mp = em.node('ShaderNodeMapping'); em.L.new(em.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (95, 95, 95); mp.inputs['Location'].default_value = (0, .0118 * 95, 0)
        em.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
        col = em.ramp(grad.outputs['Fac'], [(.0, srgb('#efe8de')), (.55, srgb('#efe8de')), (.6, srgb('#3a2414')), (.85, srgb('#22140a')), (.88, (0.01, .01, .01))])
        em.set(col.outputs['Color'], .15)
        add(ob, em, 'head')
    return hair

def on_arm(J, t0, t1, rad, seg='upper'):
    """Faces along the upper arm (shoulder to elbow) or forearm, between fractions t0 and t1."""
    def f(c):
        for sd in ('l', 'r'):
            if seg == 'upper': S, E = J[f'{sd}-shoulder'], J[f'{sd}-elbow']
            else: S, E = J[f'{sd}-elbow'], J[f'{sd}-hand']
            u = E - S; t = (c - S).dot(u) / u.length_squared
            if t0 < t < t1 and (c - (S + u * t)).length < rad: return True
        return False
    return f

def sheath(tag, ln, bend, at, rot, mats, add, width=.024, bone='hips', hilt_scale=1.0, radii=None):
    """A blade in its scabbard (curved by bend, 0 for straight) with its hilt, hung at
    `at` with rotation `rot` and bound rigidly to a bone. `radii` shapes the scabbard
    along its length (default: tapering to the tip)."""
    pts = [(math.sin(t * bend) * ln / bend * .4 if bend else 0, 0, -t * ln) for t in [i / 12 for i in range(13)]]
    sc = curve_mesh(f'{tag}Scabbard', [pts], width, radii=radii or (lambda t: 1 - .55 * t ** 2))
    sc.scale = (1, .32, 1); bake_mods(sc)
    hilt = lathe(f'{tag}Hilt', [(0, .11), (.018, .105), (.02, .09), (.012, .08), (.013, .02), (.034, .01), (.03, 0)], 14)
    hilt.scale = (hilt_scale, .5 * hilt_scale, hilt_scale)
    for o, mt in zip((sc, hilt), mats):
        o.rotation_euler = rot; o.location = at; bpy.context.view_layer.update(); bake_obj_xform(o); add(o, mt, bone)
    return sc, hilt


# ── Kit ─────────────────────────────────────────────────────────────────────
bronze_ = None
def kit(body, J):
    global bronze_
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    head, neck, eye, jaw = J['head'], J['neck'], J['l-eye'], J['jaw']
    sh_z = J['l-shoulder'].z
    bronze_ = m_bronze('Bronze', .3, 512)
    hc = V((0, eye.y + .085, eye.z - .005))
    bvh_b = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    hair = head_kit(body, J, add, [('L1_Stubble', .0005, .0, '#6e5240'), ('L2_Beard', .0048, .3, '#4a3322'), ('L3_Beard', .0026, .12, '#4a3526')])

    # L2: the alopekis, a fox-skin cap with ear flaps, the fox's mask on the brow
    fox = m_fur('Fox', '#a8582a', '#e8d8bc')
    cap = region_shell('L2_Alopekis', body, lambda c: c.z > eye.z + .022 or (abs(c.x) > .05 and c.z > jaw.z - .015 and head.y - .045 < c.y < head.y + .08)
                       or (c.y > head.y + .02 and c.z > neck.z + .02), .024, 4, .5, guard=.022)
    mod(cap, 'SOLIDIFY', thickness=.006, offset=1); mod(cap, 'SUBSURF', levels=1, render_levels=1); bake_mods(cap)
    add(cap, fox, 'head')
    bvh_cap = BVHTree.FromObject(cap, bpy.context.evaluated_depsgraph_get())
    hf = bvh_cap.ray_cast(V((0, -1, eye.z + .045)), V((0, 1, 0)))
    if hf[0]:
        Pf = hf[0]
        sn = lathe('L2_FoxSnout', [(.03, 0), (.026, .03), (.016, .06), (.006, .078), (0, .082)], 20)
        sn.rotation_euler = (math.radians(100), 0, 0); sn.location = Pf + V((0, .01, -.004)); sn.scale = (1, .75, 1)
        add(sn, fox, 'head')
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.0085, location=Pf + V((0, -.083, -.018))); nose = bpy.context.object; nose.name = 'L2_FoxNose'
        add(nose, H.m_flat('FoxNose', '#141010', .3), 'head')
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.007, location=Pf + V((sx * .03, -.012, .016))); fe = bpy.context.object; fe.name = f'L2_FoxEye{"LR"[sx > 0]}'
            add(fe, H.m_flat('FoxEye', '#1a120a', .15), 'head')
            ht = bvh_cap.ray_cast(V((sx * .048, head.y - .035, 3)), V((0, 0, -1)))
            if ht[0]:
                ear = lathe(f'L2_FoxEar{"LR"[sx > 0]}', [(.03, 0), (.022, .03), (.008, .058), (0, .07)], 16)
                ear.location = ht[0] - V((0, 0, .012)); ear.rotation_euler = (math.radians(-12), math.radians(sx * 18), 0); ear.scale = (1, .45, 1)
                add(ear, m_fur('FoxEar', '#9a4c22', '#1a1008', 256), 'head')

    # L3: Thracian helmet, a bowl with a forward peak, long cheek pieces and a crest
    def keep_th(c):
        if c.y < head.y - .005: return c.z > eye.z + .02
        return c.z > neck.z - .02
    th = envelope('L3_Helmet', body, keep_th, hc, .02, also=[hair], flare=lambda p: max(0, jaw.z + .01 - p.z) * .35); relax_rim(th)
    mod(th, 'SOLIDIFY', thickness=.0035, offset=1); mod(th, 'BEVEL', width=.0012, segments=1, limit_method='ANGLE'); bake_mods(th)
    add(th, bronze_, 'head')
    bvh_th = BVHTree.FromObject(th, bpy.context.evaluated_depsgraph_get())
    bm = bmesh.new(); inner, outer = [], []
    for i in range(29):   # the peak: widest over the brow, narrowing to nothing at the temples
        phi = math.radians(-78 + 156 * i / 28); d = V((math.sin(phi), -math.cos(phi), 0))
        o = V((hc.x, hc.y, eye.z + .026)); h = bvh_th.ray_cast(o + d * .3, -d)
        p = h[0] if h[0] else o + d * .11
        w = .055 * math.cos(phi * 1.12) ** 1.4
        inner.append(bm.verts.new(p - d * .004 + V((0, 0, .002))))
        outer.append(bm.verts.new(p + d * w + V((0, 0, .012 * w / .055 - .018 * (w / .055) ** 2))))
    for i in range(28): bm.faces.new((inner[i], inner[i + 1], outer[i + 1], outer[i]))
    peak = obj_from_bm('L3_HelmetPeak', bm); mod(peak, 'SOLIDIFY', thickness=.003); mod(peak, 'SUBSURF', levels=1, render_levels=1); bake_mods(peak)
    add(peak, bronze_, 'head')
    cheeks = envelope('L3_HelmetCheeks', body, lambda c: abs(c.x) > .04 and head.y - .095 < c.y < head.y + .03 and jaw.z - .03 < c.z < eye.z + .03, hc, .021, also=[hair],
                      flare=lambda p: max(0, eye.z - .03 - p.z) * .12); relax_rim(cheeks, 8)
    mod(cheeks, 'SOLIDIFY', thickness=.003, offset=1); mod(cheeks, 'BEVEL', width=.0012, segments=1, limit_method='ANGLE'); bake_mods(cheeks)
    add(cheeks, bronze_, 'head')
    ridge = lambda y: (bvh_th.ray_cast(V((0, y, 3)), V((0, 0, -1)))[0] or V((0, y, eye.z + .12))).z
    crest_pts = [(0, head.y - .07 + .16 * t, ridge(head.y - .07 + .16 * t) + .004) for t in [i / 14 for i in range(15)]]
    holder = curve_mesh('L3_CrestHolder', [crest_pts], .011, res=2)
    holder.scale = (.6, 1, 1); bake_mods(holder); add(holder, bronze_, 'head')
    strands, rnd = [], random.Random(9)
    for i in range(70):   # the plume: a forward-curving tuft of horsehair
        t = i / 69; y = head.y - .065 + .15 * t; z0 = ridge(y) + .008
        ang = math.radians(-25 + 70 * t) + rnd.uniform(-.08, .08); ln = (.1 + .07 * math.sin(math.pi * t)) * rnd.uniform(.9, 1.08)
        for sx in (-1, 0, 1):
            p = V((sx * .004, y, z0)); pts = [tuple(p)]; a = ang
            for k in range(10):
                a += (2.6 + 1.5 * t) * ln / 10
                p = p + V((sx * .002, math.sin(a), math.cos(a) - .4 * (k / 10) ** 2)).normalized() * ln / 10; pts.append(tuple(p))
            strands.append(pts)
    plume = curve_mesh('L3_Plume', strands, .0035, radii=lambda t: 1 - .6 * t, res=0)
    add(plume, H.m_flat('PlumeHair', '#7a6248', .45), 'head')

    # Upper body garments
    torso = lambda z0, z1, w: (lambda c: z0 < c.z < z1 and abs(c.x) < w)
    # L1 exomis: pinned on the left shoulder, the right shoulder and breast bare
    zl = lambda x: sh_z + .03 + (x - .08) * (.17 / .25)
    ex = region_shell('L1_Exomis', body, lambda c: .9 < c.z < sh_z + .04 and abs(c.x) < .21 and c.z < zl(c.x), .008, 6, .5, guard=.006)
    mod(ex, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(ex)
    add(ex, m_cloth('Exomis', '#ddd2bb', 600, .06), 'skin')
    knot = lathe('L1_ExomisKnot', [(0, .012), (.014, .008), (.016, 0), (.012, -.008), (0, -.012)], 14)
    h = bvh_b.ray_cast(V((.1, -.02, 2)), V((0, 0, -1)))
    knot.location = (h[0] + V((0, 0, .012))) if h[0] else V((.1, -.02, sh_z + .05)); add(knot, m_cloth('KnotLinen', '#cfc3a8', 300, .06, 256), 'skin')
    # L2: long-sleeved wool tunic under the zeira
    tun2 = region_shell('L2_Tunic', body, torso(.9, sh_z + .04, .21), .007, 6, .5, guard=.005)
    mod(tun2, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(tun2); add(tun2, m_cloth('TunicTan', '#8c7550', 500, .08), 'skin')
    # L3: patterned tunic with short sleeves
    tunic_pat = m_pattern('AgrianianWeave', [(0, '#b9772e'), (.18, '#5a3418'), (.3, '#c88a3c'), (.55, '#2b2a3a'), (.62, '#c88a3c'), (.85, '#6b4020')], 7.5, 36, .05)
    tun3 = region_shell('L3_Tunic', body, torso(.9, sh_z + .04, .21), .008, 6, .5, guard=.006)
    mod(tun3, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(tun3); add(tun3, tunic_pat, 'skin')
    sl2 = region_shell('L2_Sleeves', body, lambda c: on_arm(J, -.2, 1.05, .09)(c) or on_arm(J, -.05, .85, .07, 'fore')(c), .006, 2, .5, guard=.005)
    mod(sl2, 'SOLIDIFY', thickness=.002, offset=1); bake_mods(sl2); add(sl2, m_cloth('SleeveTan', '#8c7550', 500, .08), 'skin')
    sl3 = region_shell('L3_Sleeves', body, on_arm(J, -.2, .5, .09), .007, 2, .5, guard=.005)
    mod(sl3, 'SOLIDIFY', thickness=.002, offset=1); bake_mods(sl3); add(sl3, tunic_pat, 'skin')
    # L2: the zeira mantle over shoulders and upper arms, open down the breast
    zeira = m_pattern('Zeira', [(0, '#5e1c22'), (.14, '#1e2440'), (.26, '#5e1c22'), (.4, '#b08440'), (.46, '#5e1c22'), (.62, '#1e2440'), (.74, '#d9c8a4'), (.78, '#3a1418')], 11, 52, .05)
    def in_mantle(c):
        if c.z < sh_z - .24 or c.z < .95 or c.z > neck.z + .015: return False
        if c.y < 0 and abs(c.x) < .055 and c.z < sh_z - .03: return False   # open at the breast
        if abs(c.x) > .2: return on_arm(J, -.2, .55, .1)(c)
        return c.z > neck.z - .06 or abs(c.x) > .045
    mantle = region_shell('L2_Zeira', body, in_mantle, .03, 5, .5, guard=.026)
    mod(mantle, 'SOLIDIFY', thickness=.006, offset=1); bake_mods(mantle); add(mantle, zeira, 'skin')
    # Boots: L2 fawnskin with fur cuffs, L3 laced leather
    for lv, top in ((2, .3), (3, .32)):
        b = region_shell(f'L{lv}_Boots', body, lambda c, top=top: c.z < top and abs(c.x) > .015, .007, 2, .5, guard=.006)
        mod(b, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(b)
        add(b, m_leather(f'Boot{lv}', '#a07a4c' if lv == 2 else '#8a6238'), 'skin')
        if lv == 2:
            cuff = region_shell('L2_BootCuffs', body, lambda c: top - .055 < c.z < top + .012 and abs(c.x) > .015, .024, 3, .5, guard=.02)
            mod(cuff, 'SOLIDIFY', thickness=.006, offset=1); mod(cuff, 'SUBSURF', levels=1, render_levels=1); bake_mods(cuff)
            add(cuff, m_fur('BootFur', '#d2bc96', '#f2ead8', 256), 'skin')
        bvh_bt = BVHTree.FromObject(b, bpy.context.evaluated_depsgraph_get())
        lines = []
        for side in ('l', 'r'):
            cx = (J[f'{side}-knee'].x + J[f'{side}-ankle'].x) / 2; az = J[f'{side}-ankle'].z
            pts = []
            for i in range(11):
                z = az + .02 + i * (top - .03 - az) / 10; x = cx + (.026 if i % 2 else -.026)
                hh = bvh_bt.ray_cast(V((x, -1, z)), V((0, 1, 0)))
                if hh[0]: pts.append(tuple(hh[0] + hh[1] * .003))
            if len(pts) > 2: lines.append(pts)
        if lines: add(curve_mesh(f'L{lv}_BootLaces', lines, .0022, res=1), m_leather('Lace', '#3a2414', 256), 'skin')

    # Weapons
    ash, iron, thong = m_wood('Ash'), m_iron(), m_leather('Thong', '#5a3a20', 256)
    for ob, mt in javelin('ThrowJavelin', (ash, iron, thong)): add(ob, mt, 'later:hand.R')
    for k, tag in enumerate(('', 'L23_', 'L3_')):   # spares behind the shield: 2, 3 and 4 javelins in all
        for ob, mt in javelin(f'{tag}Spare{k}', (ash, iron, thong), loop=True): add(ob, mt, f'later:spare{k}')
    shield(1, 'hide', add); shield(2, 'face', add); shield(3, 'round', add)
    return out


# ── Cloth and items laid over it, after the drape ───────────────────────────
def dress(body, J, items):
    def add(ob, mt, bind): items[ob.name] = (ob, mt, bind); return ob
    sh_z = J['l-shoulder'].z
    skirts = {}
    for lv, col, z1 in ((1, '#ddd2bb', .66), (2, '#8c7550', .62), (3, None, .66)):
        sk = chiton(f'L{lv}_Skirt', col or '#ffffff', .98, z1); drape(f'L{lv}_Skirt', sk, lambda c: c.z > .965, body)
        mt = items['L3_Tunic'][1] if lv == 3 else m_cloth(f'Skirt{lv}', col, 600 if lv == 1 else 500, .07)
        add(sk, mt, 'skin'); skirts[lv] = sk
        if lv < 3:
            fr = fringe(f'L{lv}_SkirtFringe', sk)
            add(fr, m_cloth(f'Fringe{lv}', col, 300, .1, 256), 'skin')
    hem = fringe('L3_Hem', skirts[3], 150, .012)   # a dark woven hem band
    add(hem, m_cloth('HemBand', '#22263a', 300, .08, 256), 'skin')
    # L2 zeira back panel and L3 olive cloak, pinned across the shoulders
    top = sh_z + .04
    zb = cloak('L2_ZeiraBack', top, .62, .92)
    drape('L2_ZeiraBack', zb, lambda c, t=top: c.z > t - .016, body, 70, .25); clear_of(zb, [body, skirts[2]], .008)
    add(zb, items['L2_Zeira'][1], 'skin')
    zbf = fringe('L2_ZeiraFringe', zb, 90, .04); add(zbf, m_cloth('ZeiraFringe', '#5e1c22', 300, .1, 256), 'skin')
    oc = cloak('L3_Cloak', top, .5, .62)
    drape('L3_Cloak', oc, lambda c, t=top: c.z > t - .016, body, 70, .22); clear_of(oc, [body, skirts[3]], .008)
    add(oc, m_cloth('OliveWool', '#6b6a3e', 300, .12, 512), 'skin')
    # Belts: rope for L1, leather for L2 and L3
    surf = {lv: Surf([body, skirts[lv]] + [items[n][0] for n in (('L1_Exomis',), ('L2_Tunic',), ('L3_Tunic',))[lv - 1]]) for lv in (1, 2, 3)}
    rope = curve_mesh('L1_RopeBelt', [[tuple(p) for p, n in ring_on(surf[1], 1.0, .006)]], .0065, cyclic=True)
    add(rope, m_rope(), 'skin')
    for lv in (2, 3):
        pts = ring_on(surf[lv], 1.0, .005, 64); pts.append(pts[0])
        add(ribbon(f'L{lv}_Belt', pts, .034), m_leather(f'Belt{lv}', '#4a2c18'), 'skin')
    # Baldric (right shoulder to left hip) carrying the sica (L2) or machaira (L3)
    for lv in (2, 3):
        objs = [body, items[f'L{lv}_Tunic'][0]] + ([items['L2_Zeira'][0]] if lv == 2 else [])
        sf = Surf(objs); P = []
        for front in (True, False):
            row = []
            for i in range(25):
                t = i / 24; x = -.12 + .3 * t; zz = sh_z + .05 - (sh_z + .05 - .97) * t
                d = V((0, -1 if front else 1, 0)); hh = sf.hit(V((x, 0, zz)), d)
                if hh: row.append((hh[0] + hh[1] * .006, hh[1]))
            if len(row) > 2: add(ribbon(f'L{lv}_Baldric{"FB"[not front]}', row, .03), m_leather(f'Baldric{lv}', '#4a2c18'), 'skin')
    leather_sc = m_leather('Scabbard', '#3a2414')
    for lv, ln, bend, at, rot in ((2, .36, .5, (.13, -.12, .98), (math.radians(-75), 0, math.radians(-20))), (3, .5, .25, (.2, .03, .96), (0, 0, 0))):
        sheath(f'L{lv}_', ln, bend, at, rot, (leather_sc, m_wood('HiltWood', 256)), add)
    # L2 fox tail down the back, over the zeira
    sf = Surf([body, items['L2_Zeira'][0], zb]); eye = J['l-eye']; pts = []
    for i in range(16):
        z = eye.z - .02 - i * .028
        hh = sf.hit(V((0, 0, z)), V((0, 1, 0)))
        if hh: pts.append(tuple(hh[0] + hh[1] * (.02 + .012 * math.sin(math.pi * i / 15))))
    if len(pts) > 3:
        tail = curve_mesh('L2_FoxTail', [pts], .03, radii=lambda t: .55 + .6 * math.sin(math.pi * min(1, t * 1.1)) * (1 - .3 * t), res=3)
        add(tail, m_fur('FoxTail', '#a8582a', '#f0e6d4'), 'skin')

def bake_obj_xform(o):
    o.data.transform(o.matrix_basis); o.matrix_basis = Matrix.Identity(4)


# ── Poses and moves ─────────────────────────────────────────────────────────
def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-.3, 1, -.1), jav=(0, -1, -.75), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': jav, **kw}
    def armL(w, hint=(1, .25, -.55), grip=(0, 0, -1), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': grip, **kw}
    base = {'hips': {'loc': (0, 0, -.03)}, 'chest': {'rot': (.03, 0, .04)}, 'head': {'rot': (0, 0, -.04)},
            'ik_foot.L': {'loc': (-.01, -.07, 0)}, 'ik_foot.R': {'loc': (.01, .06, 0)},
            'armR': armR((.0, -.07, -.47)), 'armL': armL((-.05, -.3, -.29))}
    def st(**over):
        P = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): P[k] = v if k.startswith('arm') else {**P.get(k, {}), **v}
        return P
    return st, armR, armL

THROW_RELEASE = 12   # frame at which the javelin leaves the hand (the game spawns its copy here)

def actions(rig, J):
    st, armR, armL = poses(J)
    mk = H.make_action; A = []
    A.append(mk(rig, 'Idle', [(1, st()), (24, st(hips={'loc': (0, 0, -.036)}, chest={'rot': (.045, 0, .04)}, armR=armR((.0, -.07, -.465)))), (48, st())]))
    W = lambda fl, fr, zl, zr, hz: st(**{'ik_foot.L': {'loc': (-.01, fl, zl)}, 'ik_foot.R': {'loc': (.01, fr, zr)}, 'hips': {'loc': (0, 0, -.03 + hz)}})
    A.append(mk(rig, 'Walk', [(1, W(-.24, .22, 0, 0, -.014)), (7, W(-.01, -.01, 0, .1, .016)), (13, W(.22, -.24, 0, 0, -.014)), (19, W(-.01, -.01, .1, 0, .016)), (25, W(-.24, .22, 0, 0, -.014))]))
    step = {'ik_foot.L': {'loc': (-.01, -.34, 0)}}
    A.append(mk(rig, 'Throw', [
        (1, st()),
        (8, st(chest={'rot': (-.08, 0, .42)}, hips={'loc': (0, .05, -.05), 'rot': (0, 0, .18)}, head={'rot': (0, 0, -.36)},
               armR=armR((-.05, .17, .19), hint=(-1, .15, -.35), jav=(0, -1, .22)), armL=armL((-.06, -.42, -.1), hint=(1, .2, -.4)))),
        (THROW_RELEASE, st(chest={'rot': (.14, 0, -.22)}, hips={'loc': (0, -.1, -.07), 'rot': (0, 0, -.1)}, head={'rot': (.04, 0, .1)}, **step,
               armR=armR((.04, -.36, .16), hint=(-1, .3, 0), jav=(0, -1, .05)), armL=armL((-.02, -.25, -.3)))),
        (16, st(chest={'rot': (.22, 0, -.3)}, hips={'loc': (0, -.12, -.08), 'rot': (0, 0, -.12)}, **step,
                armR=armR((.15, -.3, -.24), hint=(-1, .4, -.3), jav=(.2, -1, -.4)), armL=armL((.0, -.2, -.33)))),
        (30, st())]))
    A.append(mk(rig, 'Thrust', [
        (1, st()),
        (6, st(chest={'rot': (-.05, 0, .26)}, hips={'loc': (0, .04, -.04)}, armR=armR((-.02, .05, .15), hint=(-1, .35, .15), jav=(0, -1, .02)))),
        (10, st(chest={'rot': (.16, 0, -.08)}, hips={'loc': (0, -.11, -.08)}, **step,
                armR=armR((.03, -.42, .06), hint=(-1, .2, .05), jav=(.03, -1, -.1)), armL=armL((-.06, -.26, -.24)))),
        (15, st(chest={'rot': (.14, 0, -.06)}, hips={'loc': (0, -.1, -.08)}, **step,
                armR=armR((.03, -.38, .06), hint=(-1, .2, .05), jav=(.03, -1, -.08)))),
        (24, st())]))
    blk = dict(hips={'loc': (0, .02, -.1)}, chest={'rot': (.1, 0, .14)}, head={'rot': (.08, 0, -.06)},
               armL=armL((-.12, -.36, -.05), hint=(1, .1, -.25)), armR=armR((.02, -.02, -.4), jav=(0, -1, -.4)))
    A.append(mk(rig, 'Block', [(1, st()), (6, st(**blk)), (14, st(**blk)), (20, st())]))
    A.append(mk(rig, 'Hit', [(1, st()),
        (4, st(chest={'rot': (-.26, 0, .22)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, .09, -.06)}, armL=armL((-.08, -.2, -.22)), armR=armR((.04, .02, -.42)))),
        (9, st(chest={'rot': (-.1, 0, .12)}, head={'rot': (-.12, 0, 0)}, hips={'loc': (0, .04, -.05)})), (17, st())]))
    fall = dict(chest={'rot': (-.1, 0, .1)}, hips={'loc': (0, 0, -.1)}, armR=armR((.12, -.15, -.25), hint=(-1, .2, -.3), jav=(.4, -1, -.35), fist=.8), armL=armL((.05, -.2, -.3), hint=(1, .2, -.5)))
    A.append(mk(rig, 'Death', [(1, st()),
        (8, st(chest={'rot': (.32, 0, .18)}, head={'rot': (.28, 0, 0)}, hips={'loc': (0, .02, -.22)}, armR=armR((.0, -.1, -.4)))),
        (20, st(root={'loc': (0, .27, 0), 'rot': (-1.38, 0, .08)}, head={'rot': (-.3, 0, .2)}, **fall)),
        (25, st(root={'loc': (0, .29, 0), 'rot': (-1.52, 0, .08)}, head={'rot': (-.4, 0, .2)}, **fall)),
        (40, st(root={'loc': (0, .29, 0), 'rot': (-1.5, 0, .08)}, head={'rot': (-.45, 0, .25)}, **fall))]))
    rig.animation_data.action = A[0]
    return A

def place_in_hands(rig, items):
    """In the idle pose: the throwing javelin through the right fist, the shield's
    grip in the left fist with the spare javelins held behind it."""
    PB = rig.pose.bones
    def fist(n):
        hand = PB[f'hand.{n}']; Mh = hand.matrix.to_3x3()
        palm = (Mh @ H.HAND_REF[n][1]).normalized(); k = (Mh @ H.HAND_REF[n][0]).normalized()
        return hand, hand.head + (hand.tail - hand.head) * .5 + palm * .026, k, (hand.tail - hand.head).normalized()
    hand, grip, k, _ = fist('R')
    z = k; x = z.orthogonal().normalized(); y = z.cross(x)
    Mj = Matrix((x, y, z)).transposed().to_4x4(); Mj.translation = grip
    hand, gripL, kL, fwd = fist('L')
    n = (fwd - kL * fwd.dot(kL)).normalized()          # shield faces where the knuckles point
    up = -kL                                           # the grip bar runs along the fist, thumb end up
    Ms = Matrix((up.cross(n), up, n)).transposed().to_4x4(); Ms.translation = gripL
    jav = Ms.copy(); jav.translation = gripL + n * -.004
    throw_root = bpy.data.objects.new('ThrowJavelin', None); link(throw_root); throw_root.matrix_world = Mj
    bpy.context.view_layer.update(); H.bind_rigid(throw_root, rig, 'hand.R')
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        tgt = bind.split(':')[1]
        if tgt == 'hand.R':
            ob.matrix_world = Mj @ ob.matrix_basis; bpy.context.view_layer.update()
            mw = ob.matrix_world.copy(); ob.parent = throw_root; ob.matrix_world = mw
        elif tgt.startswith('spare'):
            i = int(tgt[5:]); spread = (i - 1) * .022
            tilt = Matrix.Rotation(math.radians(-98 + i * 3), 4, 'X')   # +Z (the point) turned to the shield's up, leaning back off it
            M = jav @ Matrix.Translation((spread, 0, -.015 * i)) @ tilt @ Matrix.Translation((0, 0, -.3))   # held a third of the way up
            ob.matrix_world = M @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.L')
        else:
            ob.matrix_world = Ms @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.L')


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    body, J = H.build_body()
    items = kit(body, J)
    items['Body'] = (body, m_skin(J['l-eye']), 'body')
    dress(body, J, items)
    H.bake_textures(items)
    rig = H.build_armature(H.skeleton_spec(J), J); rig.name = 'PeltastRig'; rig.data.name = 'PeltastRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for name, (ob, mt, bind) in items.items():
        if ob is body or bind.startswith('later:'): continue
        if bind == 'skin': H.bind_skin(ob, rig, body)
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    place_in_hands(rig, items)
    return rig, actions(rig, J)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'peltast.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'peltast.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3): H.render(rig, os.path.join(OUT, f'peltast_L{lv}.png'), 'Idle', 1, lv)
    print('built', [a.name for a in acts])
