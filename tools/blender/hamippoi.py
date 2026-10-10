"""Realistic Hamippoi line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/hamippoi.py third_party/makehuman assets/models [--renders]

The hamippoi ran among the cavalry, keeping pace by holding the horses' manes;
they threw their javelins, then closed in with knife or sword. Built on the
Hoplite and Peltast pipelines. Kit follows the reference sheets:
  L1 Hamippoi           ochre wool tunic with dark woven borders, leather belt and
                        knife, petasos hung on the back, two javelins
  L2 Boeotian Hamippoi  madder tunic, rope belt, petasos, baldric and xiphos, a small
                        wicker shield with a tooled leather boss, three javelins
  L3 Epilektoi Hamippoi bronze pilos helmet, linen corselet with shoulder flaps and red
                        trim over a red chiton, baldric and xiphos, a small bronze
                        shield with a thunderbolt, four javelins
All three go barefoot. Shields are strapped to the left forearm; the spare javelins
ride in the left hand. The javelin in the right hand is the node 'ThrowJavelin',
which the game hides while its thrown copy is in the air.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
from hoplite import (link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat,
                     m_bronze, m_skin, m_cloth, m_leather, m_wood, m_iron, m_painted, drape, chiton)
from peltast import (m_wicker, m_rope, curve_mesh, ribbon, Surf, ring_on, relax_rim, shield_mesh,
                     javelin, head_kit, on_arm, sheath, bake_obj_xform)

# Runners: lean and long-legged.
H.TARGETS = [('caucasian-male-young.target', .75), ('african-male-young.target', .15), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .55), ('universal-male-young-averagemuscle-minweight.target', .45)]
H.HEIGHT = 1.75
OUT = H.OUT
random.seed(5)


# ── Materials ───────────────────────────────────────────────────────────────
def m_border(name, n, base='#33240f', line='#c99a45', res=512):
    """A woven border band: a running zigzag between two edge lines, laid out along
    the band's UV (u along its length, v across it); n zigzags per band."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['UV'], sep.inputs['Vector'])
    def op(kind, a, b=None):
        nd = m.node('ShaderNodeMath', operation=kind)
        for i, x in enumerate((a, b)):
            if x is None: continue
            if hasattr(x, 'links'): m.L.new(x, nd.inputs[i])
            else: nd.inputs[i].default_value = x
        return nd.outputs[0]
    zig = op('MULTIPLY', op('ABSOLUTE', op('SUBTRACT', op('FRACT', op('MULTIPLY', sep.outputs['X'], float(n))), .5)), 2.0)
    d = op('ABSOLUTE', op('SUBTRACT', sep.outputs['Y'], op('ADD', op('MULTIPLY', zig, .56), .22)))
    mask = op('MAXIMUM', op('LESS_THAN', d, .09), op('MAXIMUM', op('LESS_THAN', sep.outputs['Y'], .09), op('GREATER_THAN', sep.outputs['Y'], .91)))
    col = m.mix(srgb(base), srgb(line), mask)
    fuzz = m.ramp(m.noise(300, 3, .6).outputs['Fac'], [(.3, (.8, .8, .8)), (.7, (1, 1, 1))])
    col = m.mix(col, fuzz.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .85, mask, .3, .0008)
    return m

def art(kind):
    """Painted shield art: a tooled triskele for the leather boss, a thunderbolt for the bronze shield."""
    from PIL import Image, ImageDraw
    import numpy as np
    S = 512 if kind == 'triskele' else 1024
    im = Image.new('RGB', (S, S)); d = ImageDraw.Draw(im); m = S / 2
    if kind == 'triskele':
        d.rectangle((0, 0, S, S), fill=(118, 74, 40))
        d.ellipse((10, 10, S - 10, S - 10), outline=(62, 38, 20), width=20)
        R1 = .36 * m
        for k in range(3):   # three spirals running out of the centre
            base = k * 2 * math.pi / 3; C = (m + math.cos(base) * R1, m - math.sin(base) * R1)
            pts = []
            for i in range(90):
                t = i / 89; ph = base + math.pi + t * 2.3 * math.pi; rho = R1 * (1 - .82 * t)
                pts.append((C[0] + math.cos(ph) * rho, C[1] - math.sin(ph) * rho))
            d.line(pts, fill=(58, 34, 18), width=26, joint='curve')
            d.line([(x - 4, y - 4) for x, y in pts], fill=(150, 100, 58), width=5, joint='curve')
    else:
        d.rectangle((0, 0, S, S), fill=(178, 128, 66))
        d.ellipse((m - .9 * m, m - .9 * m, m + .9 * m, m + .9 * m), outline=(28, 20, 14), width=16)
        d.ellipse((m - .8 * m, m - .8 * m, m + .8 * m, m + .8 * m), outline=(140, 40, 28), width=12)
        bolt = [(-.18, .62), (.3, .62), (.04, .12), (.32, .12), (-.22, -.66), (-.04, -.06), (-.32, -.06)]
        d.polygon([(m + x * m, m - y * m) for x, y in bolt], fill=(26, 18, 12), outline=(140, 40, 28))
    img = bpy.data.images.new(f'Art_{kind}', S, S)
    a = np.ones((S, S, 4), np.float32); a[..., :3] = np.asarray(im.transpose(Image.FLIP_TOP_BOTTOM), np.float32) / 255
    img.pixels.foreach_set(a.ravel()); img.pack()
    return img


# ── Borders laid along the open edges of cloth shells ───────────────────────
def boundary_loops(bm):
    """Every open edge loop of a mesh, as ordered lists of BMVerts."""
    nb = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts; nb.setdefault(a, []).append(b); nb.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in nb:
        if start in seen: continue
        loop = [start]; seen.add(start); prev, cur = None, start
        while True:
            nxt = [v for v in nb[cur] if v is not prev and v not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]; loop.append(cur); seen.add(cur)
        if len(loop) > 4: loops.append(loop)
    return loops

def edge_band(name, ob, pick, width, lift, body):
    """A band laid along open edges of a shell and turned in over the cloth. `pick`
    chooses loops from [(centroid, loop)]. UVs run along the band (u) and across it (v)."""
    bm = bmesh.new(); bm.from_mesh(ob.data); bm.normal_update()
    chosen = pick([(sum((v.co for v in L), V()) / len(L), L) for L in boundary_loops(bm)])
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    out = bmesh.new(); uvl = out.loops.layers.uv.new('UV')
    for L in chosen:
        pts = [v.co.copy() for v in L]; n = len(pts)
        acc = [0.0]
        for i in range(1, n + 1): acc.append(acc[-1] + (pts[i % n] - pts[i - 1]).length)
        rows = []
        for i, v in enumerate(L):
            p = pts[i]; t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
            nrm = v.normal.copy(); loc = bvh.find_nearest(p)[0]
            if loc is not None and nrm.dot(p - loc) < 0: nrm = -nrm      # away from the skin
            b = nrm.cross(t).normalized()
            f = next(iter(v.link_faces), None)
            if f is not None and b.dot(f.calc_center_median() - p) < 0: b = -b   # in over the cloth
            rows.append((out.verts.new(p + nrm * lift), out.verts.new(p + nrm * lift + b * width)))
        rows.append((out.verts.new(rows[0][0].co), out.verts.new(rows[0][1].co)))   # a seam copy, so u runs 0..1
        for i in range(n):
            f = out.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
            u0, u1 = acc[i] / acc[n], acc[i + 1] / acc[n]
            for lp, uv in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))): lp[uvl].uv = uv
    bm.free()
    band = obj_from_bm(name, out); mod(band, 'SOLIDIFY', thickness=.0015, offset=1); bake_mods(band)
    return band

def pick_neck(info):
    near = [cl for cl in info if abs(cl[0].x) < .06]
    return [max(near, key=lambda cl: cl[0].z)[1]] if near else []

def pick_lowest(info):
    return [min(info, key=lambda cl: cl[0].z)[1]] if info else []

def pick_sleeve_ends(J):
    def f(info):
        out = []
        for sd in ('l', 'r'):
            S, E = J[f'{sd}-shoulder'], J[f'{sd}-elbow']; u = (E - S).normalized()
            side = [cl for cl in info if (cl[0].x > 0) == (S.x > 0)]
            if side: out.append(max(side, key=lambda cl: (cl[0] - S).dot(u))[1])
        return out
    return f


# ── Shields strapped to the forearm: built facing +Z, the forearm along local X ─
SHIELDS = {}   # tag -> (radius, forearm fraction at the porpax, porpax height)

def strapped_shield(tag, R, depth, along, mats, rim_r, add):
    """A dished round shield. The forearm runs along local X behind it through the
    porpax at (0, 0, zp); the hand closes on the antilabe, placed later at the fist."""
    face_m, back_m, rim_m, strap_m = mats
    face, rim = shield_mesh(tag + 'ShieldFace', R, None, depth, 0.0)
    backm = face.copy(); backm.data = face.data.copy(); backm.name = tag + 'ShieldBack'; link(backm)
    for v in backm.data.vertices: v.co.z -= .006
    backm.data.flip_normals()
    mod(face, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(face)
    add(face, face_m, 'later:shield'); add(backm, back_m, 'later:shield')
    add(curve_mesh(tag + 'ShieldRim', [rim], rim_r, cyclic=True), rim_m, 'later:shield')
    zp = depth - .006 - .047
    por = lathe(tag + 'Porpax', [(.041, -.02), (.046, 0), (.041, .02)], 24)
    por.rotation_euler.y = math.pi / 2; por.location = (0, 0, zp); por.scale = (1, .82, 1); bake_obj_xform(por)
    mod(por, 'SOLIDIFY', thickness=.003); bake_mods(por); add(por, strap_m, 'later:shield')
    ant = curve_mesh(tag + 'Antilabe', [[(0, -.048, .03), (0, -.034, .008), (0, -.012, 0), (0, .012, 0), (0, .034, .008), (0, .048, .03)]], .006)
    add(ant, strap_m, 'later:antilabe')
    SHIELDS[tag] = (R, along, zp, depth)
    return face


# ── Kit ─────────────────────────────────────────────────────────────────────
bronze_ = None
def kit(body, J):
    global bronze_
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    head, neck, eye, jaw, mouth = J['head'], J['neck'], J['l-eye'], J['jaw'], J['mouth']
    sh_z = J['l-shoulder'].z
    bronze_ = m_bronze('Bronze', .3, 512)
    hair = head_kit(body, J, add, [('L1_Beard', .0014, .05, '#5a4130'), ('L2_Beard', .003, .18, '#45301f'), ('L3_Stubble', .0004, .0, '#7a5a46')],
                    '#1a120b', 1.25, edge_hops=8)

    # Tunics: torso and short sleeves (the skirts are draped in dress())
    for lv, col, sl_end in ((1, '#b0812e', .42), (2, '#6c2421', .34), (3, '#b3382c', .38)):
        tun = region_shell(f'L{lv}_Tunic', body, lambda c: .9 < c.z < sh_z + .04 and abs(c.x) < .21, .008, 6, .5, guard=.006)
        sl = region_shell(f'L{lv}_Sleeves', body, on_arm(J, -.12, sl_end, .1), .015, 2, .5, guard=.0135)   # rides clear of the torso
        if lv == 1:   # woven borders at the neck and the sleeve ends, laid before the cloth is thickened
            add(edge_band('L1_NeckBand', tun, pick_neck, .022, .004, body), m_border('NeckBorder', 18), 'skin')
            add(edge_band('L1_SleeveBands', sl, pick_sleeve_ends(J), .02, .0035, body), m_border('SleeveBorder', 12), 'skin')
        mod(tun, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(tun)
        mod(sl, 'SOLIDIFY', thickness=.002, offset=1); bake_mods(sl)
        cl = m_cloth(f'Wool{lv}', col, 500, .09)
        add(tun, cl, 'skin'); add(sl, cl, 'skin')

    # L3: linen corselet with shoulder flaps, edged in red leather
    trim = m_leather('Trim', '#8a3a22', 256)
    lino = region_shell('L3_Linothorax', body, lambda c: .93 < c.z < sh_z + .02 and abs(c.x) < .205, .022, 12, .6, guard=.02)
    add(edge_band('L3_LinoHem', lino, pick_lowest, .02, .0065, body), trim, 'skin')
    mod(lino, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(lino)
    add(lino, m_cloth('Linen', '#e4dcc6', 700, .04), 'skin')
    def in_yoke(c):
        if not (.06 < abs(c.x) < .165): return False
        if c.z > sh_z - .03: return abs(c.y) < .11 and c.z < sh_z + .05
        return c.y < 0 and c.z > sh_z - .12 and abs(c.x) < .14
    yoke = region_shell('L3_Yoke', body, in_yoke, .029, 4, .5, guard=.027); relax_rim(yoke, 6)
    add(edge_band('L3_YokeTrim', yoke, lambda info: [L for c, L in info], .014, .0065, body), trim, 'skin')
    mod(yoke, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(yoke)
    add(yoke, m_cloth('YokeLinen', '#e9e2cf', 700, .04), 'skin')

    # L3: bronze pilos, a tall cone sized to clear the hair, with a chin strap
    zb = eye.z + .02
    ring = [v.co for v in hair.data.vertices if abs(v.co.z - zb) < .012] + \
           [v.co for v in body.data.vertices if abs(v.co.z - zb) < .012 and abs(v.co.x) < .12 and v.co.y > head.y - .16]
    rx = max(abs(p.x) for p in ring) + .008; y0, y1 = min(p.y for p in ring), max(p.y for p in ring)
    cy, ry = (y0 + y1) / 2, (y1 - y0) / 2 + .008
    rb = .1
    pil = lathe('L3_Helmet', [(rb + .007, -.007), (rb + .005, 0), (rb * .985, .03), (rb * .9, .08), (rb * .72, .14), (rb * .45, .2), (rb * .18, .24), (0, .255)], 48)
    pil.scale = (rx / rb, ry / rb, 1); pil.location = (0, cy, zb); bake_obj_xform(pil)
    mod(pil, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(pil)
    add(pil, bronze_, 'head')
    bvh_b = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    path = [(-rx * .96, cy + .012, zb + .002), (-.072, mouth.y + .065, eye.z - .035), (-.058, mouth.y + .04, mouth.z - .012),
            (-.032, mouth.y + .03, jaw.z - .07), (0, mouth.y + .03, jaw.z - .082)]
    path = path + [(-x, y, z) for x, y, z in reversed(path[:-1])]
    pts = []
    for i, p in enumerate(path):
        p = V(p)
        if 0 < i < len(path) - 1:
            loc, no, fi, d = bvh_b.find_nearest(p)
            if loc is not None: p = loc + no * .006
        pts.append(tuple(p))
    add(curve_mesh('L3_ChinStrap', [pts], .0032, res=1), m_leather('ChinStrap', '#4a2c18', 256), 'head')

    # Shields on the left forearm: L2 wicker with a tooled leather boss, L3 bronze with a thunderbolt
    strap = m_leather('Strap', '#4a2c18', 256)
    strapped_shield('L2_', .21, .06, .55, (m_wicker('ShieldWicker'), m_wicker('ShieldWickerBack', 256), m_wicker('WickerRim', 256), strap), .008, add)
    boss = lathe('L2_ShieldBoss', [(0, .022), (.025, .02), (.045, .012), (.058, .004), (.062, 0)], 32)
    uvl = boss.data.uv_layers.new(name='UV')
    for lp in boss.data.loops:
        co = boss.data.vertices[lp.vertex_index].co; uvl.data[lp.index].uv = (co.x / .124 + .5, co.y / .124 + .5)
    boss.location = (0, 0, .06 + .003); bake_obj_xform(boss)
    add(boss, m_painted('TriskeleBoss', art('triskele'), res=512), 'later:shield')
    strapped_shield('L3_', .28, .07, .42, (m_painted('Thunderbolt', art('thunderbolt'), res=1024), m_wood('ShieldWood'), bronze_, bronze_), .009, add)

    # Javelins: one in the right hand to throw, spares in the left (2, 3 and 4 in all)
    ash, iron, thong = m_wood('Ash'), m_iron(), m_leather('Thong', '#5a3a20', 256)
    for ob, mt in javelin('ThrowJavelin', (ash, iron, thong)): add(ob, mt, 'later:hand.R')
    for k, tag in enumerate(('', 'L23_', 'L3_')):
        for ob, mt in javelin(f'{tag}Spare{k}', (ash, iron, thong)): add(ob, mt, f'later:spare{k}')
    return out


# ── Skirts, belts, blades and hats, laid over the tunics ────────────────────
def dress(body, J, items):
    def add(ob, mt, bind): items[ob.name] = (ob, mt, bind); return ob
    sh_z = J['l-shoulder'].z; neck = J['neck']
    skirts = {}
    for lv, z1 in ((1, .64), (2, .62), (3, .66)):
        sk = chiton(f'L{lv}_Skirt', '#ffffff', .98, z1); drape(f'L{lv}_Skirt', sk, lambda c: c.z > .965, body, thickness=0)
        if lv == 1: add(edge_band('L1_HemBand', sk, pick_lowest, .024, .004, body), m_border('HemBorder', 64, res=1024), 'skin')
        mod(sk, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(sk)
        add(sk, items[f'L{lv}_Tunic'][1], 'skin'); skirts[lv] = sk
    surf = {lv: Surf([body, skirts[lv], items[f'L{lv}_Tunic'][0]] + ([items['L3_Linothorax'][0]] if lv == 3 else [])) for lv in (1, 2, 3)}

    # L1: leather belt with a bronze buckle, a knife at the right hip
    pts = ring_on(surf[1], 1.0, .005, 64); pts.append(pts[0])
    add(ribbon('L1_Belt', pts, .03), m_leather('Belt1', '#6b4024'), 'skin')
    hf = surf[1].hit(V((0, 0, 1.0)), V((0, -1, 0)))
    bpy.ops.mesh.primitive_cube_add(size=1); bk = bpy.context.object; bk.name = 'L1_Buckle'
    bk.scale = (.042, .008, .034); bk.location = hf[0] + hf[1] * .009; bake_obj_xform(bk)
    mod(bk, 'BEVEL', width=.002, segments=2); bake_mods(bk); add(bk, bronze_, 'skin')
    a = math.radians(-120); d = V((math.cos(a), math.sin(a), 0)); hk = surf[1].hit(V((0, 0, .985)), d)
    sheath('L1_Knife', .2, 0, tuple(hk[0] + hk[1] * .016), (math.radians(-10), 0, a - math.pi / 2),
           (m_leather('KnifeSheath', '#5a3420'), m_wood('KnifeHilt', 256)), add, width=.017, hilt_scale=.72)

    # L3: a leather belt round the corselet's waist
    pts = ring_on(Surf([items['L3_Linothorax'][0]]), 1.025, .004, 64); pts.append(pts[0])
    add(ribbon('L3_Belt', pts, .028), m_leather('Belt3', '#5a3420'), 'skin')

    # L2: rope belt knotted at the front, the ends hanging
    add(curve_mesh('L2_RopeBelt', [[tuple(p) for p, n in ring_on(surf[2], 1.0, .006)]], .0065, cyclic=True), m_rope('Rope2', '#a07850'), 'skin')
    hf = surf[2].hit(V((0, 0, 1.0)), V((0, -1, 0))); kp = hf[0] + hf[1] * .012
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.012, segments=16, ring_count=10, location=kp); kn = bpy.context.object; kn.name = 'L2_BeltKnot'
    kn.scale = (1.3, .8, 1); bake_obj_xform(kn); add(kn, m_rope('Rope2Knot', '#a07850'), 'skin')
    ends = [[tuple(kp + V((s * .006, -.004, -.008))), tuple(kp + V((s * .014, -.008, -.06))), tuple(kp + V((s * .022, -.01, -.12))), tuple(kp + V((s * .02, -.009, -.17)))] for s in (-1, 1)]
    add(curve_mesh('L2_BeltEnds', ends, .0055, radii=lambda t: 1 - .3 * t), m_rope('Rope2Ends', '#a07850'), 'skin')

    # L2 and L3: baldric from the right shoulder to the left hip, a xiphos at the hip
    for lv in (2, 3):
        objs = [body, items[f'L{lv}_Tunic'][0]] + ([items['L3_Linothorax'][0], items['L3_Yoke'][0]] if lv == 3 else [])
        sf = Surf(objs)
        for front in (True, False):
            row = []
            for i in range(25):
                t = i / 24; x = -.12 + .3 * t; zz = sh_z + .05 - (sh_z + .05 - .97) * t
                hh = sf.hit(V((x, 0, zz)), V((0, -1 if front else 1, 0)))
                if hh: row.append((hh[0] + hh[1] * .006, hh[1]))
            if len(row) > 2: add(ribbon(f'L{lv}_Baldric{"FB"[not front]}', row, .028), m_leather(f'Baldric{lv}', '#4a2c18'), 'skin')
    at, rot, ln = V((.2, .03, .97)), Euler((math.radians(22), 0, math.radians(-6))), .46
    sheath('L23_Sword', ln, 0, tuple(at), tuple(rot), (m_leather('Scabbard', '#3a2414'), m_wood('HiltWood', 256)), add, width=.023,
           radii=lambda t: (.72 + .42 * math.sin(math.pi * min(1, t * 1.2))) * (1 - .5 * t ** 3))
    ch = lathe('L23_SwordChape', [(0, -.022), (.012, -.016), (.018, -.004), (.017, .01)], 16); ch.scale = (1, .36, 1)
    ch.matrix_world = Matrix.Translation(at) @ rot.to_matrix().to_4x4() @ Matrix.Translation((0, 0, -ln + .008)) @ ch.matrix_basis
    bake_obj_xform(ch); add(ch, bronze_, 'hips')

    # L1 and L2: the petasos hung on the back from a cord round the neck
    prof = [(0, .068), (.03, .065), (.055, .055), (.07, .038), (.077, .015), (.08, .002), (.12, -.003), (.16, -.011), (.19, -.022)]
    for lv, col in ((1, '#5a4330'), (2, '#6b6152')):
        sf = Surf([body, items[f'L{lv}_Tunic'][0]])
        hb = sf.hit(V((0, 0, sh_z - .11)), V((0, 1, 0)))
        c0 = hb[0] + V((0, .03, 0))
        hat = lathe(f'L{lv}_Petasos', prof, 48)
        hat.rotation_euler = (math.radians(-98), 0, 0); hat.location = c0; bake_obj_xform(hat)
        mod(hat, 'SOLIDIFY', thickness=.004, offset=-1); bake_mods(hat)
        add(hat, m_cloth(f'Felt{lv}', col, 250, .1, 512, .95), 'chest')
        zr = neck.z - .012
        ring = [p for p, n in ring_on(sf, zr, .004, 32, V((0, neck.y, zr)))]
        add(curve_mesh(f'L{lv}_HatCord', [[tuple(p) for p in ring]], .0022, cyclic=True, res=1), m_leather(f'HatCord{lv}', '#3a2414', 256), 'skin')
        strands = []
        for s in (-1, 1):   # down the back to the crown, and two ends tied under the chin
            back = max(ring, key=lambda p: p.y - abs(p.x - s * .035) * 3)
            att = c0 + V((s * .062, -.01, .05))
            strands.append([tuple(back), tuple((back + att) / 2 + V((0, .012, 0))), tuple(att)])
        front = min(ring, key=lambda p: p.y)
        for s in (-1, 1):
            strands.append([tuple(front), tuple(front + V((s * .008, -.006, -.035))), tuple(front + V((s * .014, -.008, -.07)))])
        add(curve_mesh(f'L{lv}_HatCordEnds', strands, .0022, res=1), m_leather(f'HatCordEnds{lv}', '#3a2414', 256), 'skin')


# ── Poses and moves ─────────────────────────────────────────────────────────
def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-.3, 1, -.1), jav=(0, -1, -.75), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': jav, **kw}
    def armL(w, hint=(.3, 1, -.1), grip=(0, -1, -.75), face=(1, 0, 0), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': grip, 'face': face, **kw}
    base = {'hips': {'loc': (0, 0, -.025)}, 'chest': {'rot': (.03, 0, 0)}, 'head': {'rot': (0, 0, 0)},
            'ik_foot.L': {'loc': (-.01, -.04, 0)}, 'ik_foot.R': {'loc': (.01, .05, 0)},
            'armR': armR((.0, -.07, -.47)), 'armL': armL((.0, -.07, -.47))}
    def st(**over):
        P_ = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): P_[k] = v if k.startswith('arm') else {**P_.get(k, {}), **v}
        return P_
    return st, armR, armL

THROW_RELEASE = 12   # frame at which the javelin leaves the hand

def actions(rig, J):
    st, armR, armL = poses(J)
    mk = H.make_action; A = []
    A.append(mk(rig, 'Idle', [(1, st()), (24, st(hips={'loc': (0, 0, -.031)}, chest={'rot': (.045, 0, 0)}, armR=armR((.0, -.07, -.465)), armL=armL((.0, -.07, -.465)))), (48, st())]))
    W = lambda fl, fr, zl, zr, hz, sw: st(**{'ik_foot.L': {'loc': (-.01, fl, zl)}, 'ik_foot.R': {'loc': (.01, fr, zr)}, 'hips': {'loc': (0, 0, -.025 + hz)}},
                                         armR=armR((.0, -.07 - sw, -.465)), armL=armL((.0, -.07 + sw, -.465)))
    A.append(mk(rig, 'Walk', [(1, W(-.24, .22, 0, 0, -.014, .06)), (7, W(-.01, -.01, 0, .1, .016, 0)), (13, W(.22, -.24, 0, 0, -.014, -.06)), (19, W(-.01, -.01, .1, 0, .016, 0)), (25, W(-.24, .22, 0, 0, -.014, .06))]))
    # Run: a light, forward-leaning stride, javelin carried level, the shield arm pumping
    def R(fl, fr, zl, zr, hz, s):
        return st(**{'ik_foot.L': {'loc': (-.01, fl, zl)}, 'ik_foot.R': {'loc': (.01, fr, zr)}, 'hips': {'loc': (0, 0, -.06 + hz)}},
                  chest={'rot': (.22, 0, -.06 * s)}, head={'rot': (-.14, 0, .04 * s)},
                  armR=armR((.03, -.04 - .14 * s, -.36), hint=(-.4, 1, -.3), jav=(0, -1, -.12)),
                  armL=armL((-.03, -.06 + .16 * s, -.3), hint=(.4, 1, -.3), grip=(0, -1, -.3)))
    A.append(mk(rig, 'Run', [(1, R(-.34, .3, 0, .15, -.02, 1)), (5, R(-.03, -.12, 0, .2, .025, 0)), (9, R(.3, -.34, .15, 0, -.02, -1)),
                             (13, R(-.12, -.03, .2, 0, .025, 0)), (17, R(-.34, .3, 0, .15, -.02, 1))]))
    step = {'ik_foot.L': {'loc': (-.01, -.34, 0)}}
    A.append(mk(rig, 'Throw', [
        (1, st()),
        (8, st(chest={'rot': (-.08, 0, .42)}, hips={'loc': (0, .05, -.05), 'rot': (0, 0, .18)}, head={'rot': (0, 0, -.36)},
               armR=armR((-.05, .17, .19), hint=(-1, .15, -.35), jav=(0, -1, .22)), armL=armL((-.06, -.42, -.1), hint=(1, .2, -.4), grip=(0, -.4, -1), face=(.4, -1, 0)))),
        (THROW_RELEASE, st(chest={'rot': (.14, 0, -.22)}, hips={'loc': (0, -.1, -.07), 'rot': (0, 0, -.1)}, head={'rot': (.04, 0, .1)}, **step,
               armR=armR((.04, -.36, .16), hint=(-1, .3, 0), jav=(0, -1, .05)), armL=armL((-.02, -.25, -.3), hint=(1, .3, -.4), grip=(0, -.4, -1), face=(.6, -1, 0)))),
        (16, st(chest={'rot': (.22, 0, -.3)}, hips={'loc': (0, -.12, -.08), 'rot': (0, 0, -.12)}, **step,
                armR=armR((.15, -.3, -.24), hint=(-1, .4, -.3), jav=(.2, -1, -.4)), armL=armL((.02, -.18, -.36), hint=(1, .4, -.4)))),
        (30, st())]))
    A.append(mk(rig, 'Thrust', [
        (1, st()),
        (6, st(chest={'rot': (-.05, 0, .26)}, hips={'loc': (0, .04, -.04)}, armR=armR((-.02, .05, .15), hint=(-1, .35, .15), jav=(0, -1, .02)),
               armL=armL((-.04, -.2, -.32), hint=(1, .3, -.4), grip=(0, -.4, -1), face=(.5, -1, 0)))),
        (10, st(chest={'rot': (.16, 0, -.08)}, hips={'loc': (0, -.11, -.08)}, **step,
                armR=armR((.03, -.42, .06), hint=(-1, .2, .05), jav=(.03, -1, -.1)), armL=armL((-.06, -.26, -.24), hint=(1, .3, -.4), grip=(0, -.4, -1), face=(.5, -1, 0)))),
        (15, st(chest={'rot': (.14, 0, -.06)}, hips={'loc': (0, -.1, -.08)}, **step,
                armR=armR((.03, -.38, .06), hint=(-1, .2, .05), jav=(.03, -1, -.08)), armL=armL((-.06, -.26, -.24), hint=(1, .3, -.4), grip=(0, -.4, -1), face=(.5, -1, 0)))),
        (24, st())]))
    guard = armL((-.2, -.3, -.12), hint=(1, -.1, -.5), grip=(-.3, 0, 1), face=(0, -1, 0))
    blk = dict(hips={'loc': (0, .02, -.08)}, chest={'rot': (.1, 0, .12)}, head={'rot': (.08, 0, -.06)}, armL=guard, armR=armR((.02, -.02, -.42), jav=(0, -1, -.4)))
    A.append(mk(rig, 'Block', [(1, st()), (6, st(**blk)), (14, st(**blk)), (20, st())]))
    A.append(mk(rig, 'Hit', [(1, st()),
        (4, st(chest={'rot': (-.26, 0, .22)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, .09, -.06)}, armL=armL((-.04, -.12, -.42)), armR=armR((.04, .02, -.42)))),
        (9, st(chest={'rot': (-.1, 0, .12)}, head={'rot': (-.12, 0, 0)}, hips={'loc': (0, .04, -.05)})), (17, st())]))
    fall = dict(chest={'rot': (-.1, 0, .1)}, hips={'loc': (0, 0, -.1)}, armR=armR((.12, -.15, -.25), hint=(-1, .2, -.3), jav=(.4, -1, -.35), fist=.8),
                armL=armL((.1, -.12, -.36), hint=(1, .2, -.5)))
    A.append(mk(rig, 'Death', [(1, st()),
        (8, st(chest={'rot': (.32, 0, .18)}, head={'rot': (.28, 0, 0)}, hips={'loc': (0, .02, -.22)}, armR=armR((.0, -.1, -.4)))),
        (20, st(root={'loc': (0, .27, 0), 'rot': (-1.38, 0, .08)}, head={'rot': (-.3, 0, .2)}, **fall)),
        (25, st(root={'loc': (0, .29, 0), 'rot': (-1.52, 0, .08)}, head={'rot': (-.4, 0, .2)}, **fall)),
        (40, st(root={'loc': (0, .29, 0), 'rot': (-1.5, 0, .08)}, head={'rot': (-.45, 0, .25)}, **fall))]))
    rig.animation_data.action = A[0]
    return A

def place_in_hands(rig, items):
    """In the idle pose: the throwing javelin through the right fist, spares through
    the left, shields strapped to the left forearm facing out, the hand on the grip."""
    PB = rig.pose.bones
    def fist(n):
        hand = PB[f'hand.{n}']; Mh = hand.matrix.to_3x3()
        palm = (Mh @ H.HAND_REF[n][1]).normalized(); k = (Mh @ H.HAND_REF[n][0]).normalized()
        return hand.head + (hand.tail - hand.head) * .5 + palm * .026, k
    grip, k = fist('R')
    x = k.orthogonal().normalized(); Mj = Matrix((x, k.cross(x), k)).transposed().to_4x4(); Mj.translation = grip
    gripL, kL = fist('L')
    xl = kL.orthogonal().normalized(); Ml = Matrix((xl, kL.cross(xl), kL)).transposed().to_4x4(); Ml.translation = gripL
    fo = PB['forearm.L']; E, Wr = fo.head.copy(), fo.tail.copy(); fdir = (Wr - E).normalized()
    out = V((1, 0, 0)); nrm = (out - fdir * out.dot(fdir)).normalized()          # the shield faces away from the body
    H.FOREARM_N['L'] = (fo.matrix.to_3x3().inverted() @ nrm).normalized()
    xs = -fdir; ys = nrm.cross(xs)
    frames = {}
    for tag, (R, along, zp, depth) in SHIELDS.items():
        Mf = Matrix((xs, ys, nrm)).transposed().to_4x4(); Mf.translation = E + (Wr - E) * along - nrm * zp
        hl = Mf.inverted() @ gripL   # the fist in the shield's frame: the antilabe goes there
        frames[tag] = (Mf, hl)
    throw_root = bpy.data.objects.new('ThrowJavelin', None); link(throw_root); throw_root.matrix_world = Mj
    bpy.context.view_layer.update(); H.bind_rigid(throw_root, rig, 'hand.R')
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        tgt = bind.split(':')[1]
        if tgt == 'hand.R':
            ob.matrix_world = Mj @ ob.matrix_basis; bpy.context.view_layer.update()
            mw = ob.matrix_world.copy(); ob.parent = throw_root; ob.matrix_world = mw
            continue
        if tgt.startswith('spare'):
            i = int(tgt[5:])
            M = Matrix.Translation(-nrm * .016) @ Ml @ Matrix.Translation(((i - 1) * .02, .012 * i, 0)) @ Matrix.Rotation(math.radians(4 * (i - 1)), 4, 'Y')   # inside the shield's rim
            ob.matrix_world = M @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.L')
            continue
        Mf, hl = frames[name[:3]]
        if tgt == 'antilabe':
            ob.matrix_world = Mf @ Matrix.Translation(hl) @ ob.matrix_basis
        else:
            ob.matrix_world = Mf @ ob.matrix_basis
        bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'forearm.L')


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    body, J = H.build_body()
    items = kit(body, J)
    items['Body'] = (body, m_skin(J['l-eye']), 'body')
    dress(body, J, items)
    H.bake_textures(items)
    rig = H.build_armature(H.skeleton_spec(J), J); rig.name = 'HamippoiRig'; rig.data.name = 'HamippoiRig'
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
    H.export(rig, os.path.join(OUT, 'hamippoi.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'hamippoi.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3): H.render(rig, os.path.join(OUT, f'hamippoi_L{lv}.png'), 'Idle', 1, lv)
    print('built', [a.name for a in acts])
