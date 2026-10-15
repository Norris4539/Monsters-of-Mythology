"""Realistic Hippeis line (cavalry), built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/hippeis.py third_party/makehuman assets/models

The horse comes from horse.py; the rider is the MakeHuman man of the infantry lines,
seated without stirrups. One armature holds both: the rider's root bone hangs from
the horse's saddle bone, so he rides every gait. Kit follows the reference sheets:
  L1 Prodromos      Macedonian scout c. 334 BC: bronze Boeotian helmet, madder chiton with
                    a cord belt, blue chlamys over the left shoulder, open-toed endromides,
                    two cornel-wood javelins (one to throw, one kept for close fighting)
  L2 Hippeus        Athenian cavalryman c. 420 BC: Attic helmet with cheek pieces, a
                    linothorax over a short chiton, olive chlamys, high riding boots, a
                    cornel-wood spear with a bronze butt-spike
  L3 Hetairos       Alexander's Companion c. 333 BC: Boeotian helmet with a white plume, a
                    linothorax faced with bronze scales, a purple chlamys with a yellow
                    border, high boots, the long xyston lance, a kopis on a baldric
  L4 Hippakontistes mounted javelin thrower c. 400 BC: felt petasos, brown chiton and
                    chlamys, soft boots, three javelins (two held with the reins)
  L5 Tarantine      light cavalryman c. 300 BC: a laurel wreath, a pale chiton, blue
                    chlamys, soft boots, a small round shield on the left arm, three javelins
The spear tiers (2 and 3) and the javelin tiers (4 and 5) are the line's two branches.
Node tags: L12345_ is the rider (every tier), L1_ to L5_ each tier's kit; the throwing
javelin is L145_. The horse and its tack are untagged, so a page can show the horse alone
(level 0), when L0_Reins lie over its withers instead of running to the rider's fist.
The javelin in the right hand is the node 'ThrowJavelin', hidden by the game while its
copy flies.
"""
import bpy, bmesh, math, os, sys, random, re
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
import horse as HR
from hoplite import (link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat,
                     m_bronze, m_skin, m_cloth, m_leather, m_wood, m_iron)
from peltast import (m_rope, curve_mesh, ribbon, Surf, ring_on, javelin, head_kit, on_arm, bake_obj_xform)

H.TARGETS = [('caucasian-male-young.target', .75), ('african-male-young.target', .15), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .6), ('universal-male-young-averagemuscle-minweight.target', .4)]
H.HEIGHT = 1.75
OUT = H.OUT
random.seed(17)

SEAT = V((0, -.074, .532))   # the rider's root offset that puts his pelvis on the saddle cloth


# ── Rider kit ───────────────────────────────────────────────────────────────
def boeotian_helmet(name, body, hair, J, mat):
    """A bronze Boeotian helmet: a round crown and a wide brim folded down like a sun
    hat, lowest at the sides and back."""
    eye, head = J['l-eye'], J['head']; zb = eye.z + .045
    ring = [v.co for v in hair.data.vertices if abs(v.co.z - zb) < .012] + \
           [v.co for v in body.data.vertices if abs(v.co.z - zb) < .012 and abs(v.co.x) < .12 and v.co.y > head.y - .16]
    rx = max(abs(p.x) for p in ring) + .01; y0, y1 = min(p.y for p in ring), max(p.y for p in ring)
    cy, ry = (y0 + y1) / 2, (y1 - y0) / 2 + .01
    rb = .1
    dome = lathe(name, [(rb + .002, 0), (rb * .985, .03), (rb * .93, .065), (rb * .8, .1), (rb * .55, .13), (rb * .25, .146), (0, .151)], 48)
    dome.scale = (rx / rb, ry / rb, 1); dome.location = (0, cy, zb); bake_obj_xform(dome)
    mod(dome, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(dome)
    bm = bmesh.new(); rows = []
    for w, k in ((0, 0), (.45, .35), (1, 1)):   # inner edge, the fold, outer edge
        row = []
        for i in range(72):
            ph = 2 * math.pi * i / 72; ex, ey = math.sin(ph), -math.cos(ph)      # ph = 0 at the front
            back = (1 - math.cos(ph)) / 2; side = abs(math.sin(ph))
            width = .048 + .016 * back; drop = .006 + .03 * back + .016 * side
            p = V((ex * rx, cy + ey * ry, zb)) + V((ex, ey, 0)) * width * w + V((0, 0, -drop * k))
            row.append(bm.verts.new(p))
        rows.append(row)
    for a, b in zip(rows, rows[1:]):
        for i in range(72): bm.faces.new((a[i], a[(i + 1) % 72], b[(i + 1) % 72], b[i]))
    brim = obj_from_bm(name + 'Brim', bm)
    mod(brim, 'SOLIDIFY', thickness=.003, offset=0); mod(brim, 'SUBSURF', levels=1, render_levels=1); bake_mods(brim)
    return dome, brim

def rider_kit(body, J, add):
    head, neck, eye = J['head'], J['neck'], J['l-eye']; sh_z = J['l-shoulder'].z
    bronze = m_bronze('Bronze', .3, 512)
    hair = head_kit(body, J, add, [('L1_Beard', .0028, .14, '#3a2a1c')], '#1c130c', 1.2, edge_hops=8)
    # madder chiton: body, cap sleeves riding over the shoulder, and a skirt that lies on the thighs
    wool = m_cloth('Madder', '#6b2220', 500, .09)
    tun = region_shell('L1_Chiton', body, lambda c: .9 < c.z < sh_z + .04 and abs(c.x) < .21, .009, 6, .5, guard=.007)
    sl = region_shell('L1_Sleeves', body, on_arm(J, -.12, .4, .1), .015, 2, .5, guard=.0135)
    def on_thigh(c):
        for sd in ('l', 'r'):
            S, E = J[f'{sd}-upper-leg'], J[f'{sd}-knee']; u = E - S; t = (c - S).dot(u) / u.length_squared
            if -.3 < t < .6 and (c - (S + u * t)).length < .13: return True
        return False
    sk = region_shell('L1_Skirt', body, lambda c: c.z <= .92 and (on_thigh(c) or (c.z > .8 and abs(c.x) < .2)), .013, 3, .5, guard=.011)
    for o, t in ((tun, .0025), (sl, .002), (sk, .0025)):
        mod(o, 'SOLIDIFY', thickness=t, offset=1); bake_mods(o); add(o, wool, 'skin')
    # cord belt knotted at the front, the ends hanging
    sf = Surf([body, tun, sk])
    add(curve_mesh('L1_CordBelt', [[tuple(p) for p, n in ring_on(sf, .99, .006)]], .005, cyclic=True), m_rope('Cord', '#8a6a46'), 'skin')
    hf = sf.hit(V((0, 0, .99)), V((0, -1, 0))); kp = hf[0] + hf[1] * .01
    ends = [[tuple(kp), tuple(kp + V((s * .01, -.006, -.05))), tuple(kp + V((s * .016, -.008, -.1))), tuple(kp + V((s * .014, -.008, -.14)))] for s in (-1, 1)]
    add(curve_mesh('L1_CordEnds', ends, .0045, radii=lambda t: 1 - .3 * t), m_rope('CordEnds', '#8a6a46'), 'skin')
    # blue chlamys: pinned at the right shoulder, over the left shoulder and down the back
    blue = m_cloth('ChlamysBlue', '#3c4a63', 400, .1)
    top = sh_z + .04
    ck = H.cloak('L1_Chlamys', top, .6, .62); H.drape('L1_Chlamys', ck, lambda c, t=top: c.z > t - .016, body, 70, .2)
    add(ck, blue, 'skin')
    fold = region_shell('L1_ChlamysFold', body, lambda c: c.x > .03 and c.z > sh_z - .14 and (abs(c.y) < .13 or on_arm(J, -.2, .3, .11)(c)) and c.z < neck.z + .01,
                        .022, 4, .5, guard=.02)
    mod(fold, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(fold); add(fold, blue, 'skin')
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.013, segments=14, ring_count=8, location=(-.15, -.06, sh_z + .02)); pin = bpy.context.object
    pin.name = 'L1_Fibula'; add(pin, bronze, 'skin')
    # open-toed endromides up to mid-calf, with a turned-down cuff
    boots = region_shell('L1_Boots', body, lambda c: c.z < .36 and not (c.y < -.12 and c.z < .06), .006, 2, .5, guard=.005)
    mod(boots, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(boots); add(boots, m_leather('Endromides', '#9a7650'), 'skin')
    cuff = region_shell('L1_BootCuffs', body, lambda c: .3 < c.z < .37, .016, 3, .5, guard=.014)
    mod(cuff, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(cuff); add(cuff, m_leather('EndromidesCuff', '#b08a5e', 256), 'skin')
    # bronze Boeotian helmet
    for o in boeotian_helmet('L1_Helmet', body, hair, J, bronze): add(o, bronze, 'head')
    # two cornel-wood javelins, longer than the infantry's
    ash, iron, thong = m_wood('Cornel'), m_iron(), m_leather('Thong', '#5a3a20', 256)
    for tag, bind in (('L145_ThrowJavelin', 'later:hand.R'), ('L1_Spare0', 'later:spare0'), ('L4_Spare0', 'later:spare0'), ('L4_Spare1', 'later:spare1'),
                      ('L5_Spare0', 'later:spare0'), ('L5_Spare1', 'later:spare1')):
        for ob, mt in javelin(tag, (ash, iron, thong)):
            ob.scale = (ob.scale.x, ob.scale.y, ob.scale.z * 1.2); add(ob, mt, bind)
    tier_kit(body, J, add, hair, (ash, iron))
    return hair


def tunic(tag, body, J, add, col, skirt=True):
    """A short chiton as for the Prodromos: body, cap sleeves and a skirt lying on the thighs."""
    sh_z = J['l-shoulder'].z; wool = m_cloth(tag + 'Wool', col, 500, .08)
    tun = region_shell(tag + 'Chiton', body, lambda c: .9 < c.z < sh_z + .04 and abs(c.x) < .21, .009, 6, .5, guard=.007)
    sl = region_shell(tag + 'Sleeves', body, on_arm(J, -.12, .4, .1), .015, 2, .5, guard=.0135)
    def on_thigh(c):
        for sd in ('l', 'r'):
            S, E = J[f'{sd}-upper-leg'], J[f'{sd}-knee']; u = E - S; t = (c - S).dot(u) / u.length_squared
            if -.3 < t < .6 and (c - (S + u * t)).length < .13: return True
        return False
    parts = [(tun, .0025), (sl, .002)]
    if skirt: parts.append((region_shell(tag + 'Skirt', body, lambda c: c.z <= .92 and (on_thigh(c) or (c.z > .8 and abs(c.x) < .2)), .013, 3, .5, guard=.011), .0025))
    for o, t in parts:
        mod(o, 'SOLIDIFY', thickness=t, offset=1); bake_mods(o); add(o, wool, 'skin')
    return [o for o, t in parts]

def m_chlamys(name, col, border=None):
    """Wool for a chlamys, with a woven border along its sides and hem when given."""
    m = m_cloth(name, col, 400, .1)
    if border:
        sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['UV'], sep.inputs['Vector'])
        def lt(src, v, flip=False):
            n = m.node('ShaderNodeMath', operation='GREATER_THAN' if flip else 'LESS_THAN'); m.L.new(src, n.inputs[0]); n.inputs[1].default_value = v; return n.outputs[0]
        a = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(lt(sep.outputs['X'], .05), a.inputs[0]); m.L.new(lt(sep.outputs['X'], .95, True), a.inputs[1])
        b = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(a.outputs[0], b.inputs[0]); m.L.new(lt(sep.outputs['Y'], .07), b.inputs[1])
        cloth = m.bsdf.inputs['Base Color'].links[0].from_socket
        m.L.new(m.mix(cloth, srgb(border), b.outputs[0]), m.bsdf.inputs['Base Color'])
    return m

def chlamys(tag, body, J, add, col, border=None):
    """The Prodromos' chlamys for another tier: pinned at the right shoulder, over the left
    shoulder and down the back, the grid given UVs so a border can run round its edge."""
    sh_z, neck = J['l-shoulder'].z, J['neck']; top = sh_z + .04
    ck = H.cloak(tag + 'Chlamys', top, .6, .62)
    me = ck.data; uvl = me.uv_layers.new(name='UV'); nx, nz = 26, 32
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index; uvl.data[li].uv = ((vi % (nx + 1)) / nx, 1 - (vi // (nx + 1)) / nz)
    H.drape(tag + 'Chlamys', ck, lambda c, t=top: c.z > t - .016, body, 70, .2)
    mat = m_chlamys(tag + 'ChlamysWool', col, border); add(ck, mat, 'skin')
    fold = region_shell(tag + 'ChlamysFold', body, lambda c: c.x > .03 and c.z > sh_z - .14 and (abs(c.y) < .13 or on_arm(J, -.2, .3, .11)(c)) and c.z < neck.z + .01,
                        .022, 4, .5, guard=.02)
    mod(fold, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(fold); add(fold, m_cloth(tag + 'FoldWool', col, 400, .1), 'skin')
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.013, segments=14, ring_count=8, location=(-.15, -.06, sh_z + .02)); pin = bpy.context.object
    pin.name = tag + 'Fibula'; add(pin, m_bronze(tag + 'FibulaBronze', .25, 128), 'skin')

def boots(tag, body, J, add, col, high=True):
    """Closed riding boots: high to below the knee, or soft ones to mid-calf, with a turned cuff."""
    top = (J['l-knee'].z - .05) if high else .3
    b = region_shell(tag + 'Boots', body, lambda c: c.z < top, .006, 2, .5, guard=.005)
    mod(b, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(b); add(b, m_leather(tag + 'BootLeather', col), 'skin')
    cf = region_shell(tag + 'BootCuffs', body, lambda c: top - .05 < c.z < top + .005, .015, 3, .5, guard=.013)
    mod(cf, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(cf); add(cf, m_leather(tag + 'CuffLeather', col, 256), 'skin')

def linothorax(tag, body, J, add, mat, yoke_mat):
    sh_z = J['l-shoulder'].z
    lino = region_shell(tag + 'Linothorax', body, lambda c: .92 < c.z < sh_z + .03 and abs(c.x) < .205, .026, 14, .6, guard=.022)
    mod(lino, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(lino); add(lino, mat, 'skin')
    yoke = region_shell(tag + 'Yoke', body, lambda c: sh_z - .04 < c.z < sh_z + .05 and .05 < abs(c.x) < .19 and abs(c.y) < .11, .032, 4, .5, guard=.029)
    mod(yoke, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(yoke); add(yoke, yoke_mat, 'skin')
    return lino

def m_scales(name='BronzeScales'):
    """Small bronze scales sewn in overlapping rows, each a little domed and darker at its foot."""
    m = Mat(name, metal=1.0, res=1024)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (55, 55, 38)
    br = m.node('ShaderNodeTexBrick', offset=.5, squash=1.0); m.L.new(mp.outputs['Vector'], br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = .04; br.inputs['Brick Width'].default_value = .5; br.inputs['Row Height'].default_value = .35
    br.inputs['Color1'].default_value = (*srgb('#8c6b3c'), 1); br.inputs['Color2'].default_value = (*srgb('#a8834c'), 1); br.inputs['Mortar'].default_value = (*srgb('#2a1e10'), 1)
    m.set(br.outputs['Color'], .3, br.outputs['Fac'], .6, .002)
    return m

def attic_helmet(name, body, hair, J, mat):
    """A bronze Attic helmet: a skull with the face open, cheek pieces down to the jaw, the
    nape covered, and a bronze brow band."""
    head, eye, jaw, neck = J['head'], J['l-eye'], J['jaw'], J['neck']
    hc = V((0, eye.y + .085, eye.z - .005))
    keep = lambda c: (c.z > eye.z + .028 and c.y > eye.y - .02) or (c.y > eye.y + .045 and c.z > jaw.z - .01 and c.z > neck.z + .035) or \
                     (abs(c.x) > .05 and c.y > eye.y + .015 and c.z > jaw.z - .012 and c.z < eye.z + .03)
    hel = H.envelope(name, body, keep, hc, .015, also=[hair], flare=lambda p: max(0, eye.z - .02 - p.z) * .2)
    P.relax_rim(hel, 6)
    mod(hel, 'SOLIDIFY', thickness=.0035, offset=1); mod(hel, 'SUBSURF', levels=1, render_levels=1); bake_mods(hel)
    band = region_shell(name + 'Brow', hel, lambda c: eye.z + .03 < c.z < eye.z + .046 and c.y < head.y + .02, .0022)
    mod(band, 'SOLIDIFY', thickness=.002, offset=1); bake_mods(band)
    return hel, band

def plume(name, top, n=220, length=.22, seed=21):
    """A white horsehair plume standing from the crown and falling back."""
    rnd = random.Random(seed); roots = []
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(0, .016)
        roots.append((top + V((math.cos(a) * r, math.sin(a) * r, 0)), V((math.cos(a) * .3, .35 + math.sin(a) * .3, 1)).normalized()))
    return HR.strands(name, roots, length, 1.0, .3, seed, .0042, 7, .45)

def wreath(name, body, hair, J):
    """A laurel wreath round the head above the brow: pairs of leaves along a twig laid
    on the hair (or the skin, where the hair has receded), the ends meeting at the back."""
    eye, head = J['l-eye'], J['head']; zb = eye.z + .05; c = V((0, head.y - .01, zb))
    sf = Surf([body, hair]); bm = bmesh.new(); twig = []
    for i in range(48):
        a = 2 * math.pi * i / 48; d = V((math.sin(a), -math.cos(a), 0))   # a = 0 at the front
        h = sf.hit(c, d, .3); p = (h[0] + d * .003) if h else c + d * .1
        p.z += .008 * math.cos(a); twig.append(tuple(p))
        if abs(math.cos(a / 2)) < .1: continue
        tang = V((math.cos(a), math.sin(a), 0))
        for sgn in (1, -1):
            out = (d * .45 + V((0, 0, sgn * .7)) + tang * .6).normalized()
            M = Matrix.Translation(p + out * .011 + d * .002) @ out.to_track_quat('Y', 'Z').to_matrix().to_4x4() @ Matrix.Diagonal((.0065, .016, .0018, 1))
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=1, matrix=M)
    return obj_from_bm(name, bm), curve_mesh(name + 'Twig', [twig], .0022, cyclic=True, res=1)

def petasos(name, J):
    """A wide-brimmed felt petasos worn on the head."""
    eye, head = J['l-eye'], J['head']
    prof = [(0, .088), (.03, .085), (.055, .074), (.07, .055), (.078, .03), (.082, .012), (.12, .004), (.16, -.005), (.19, -.016)]
    hat = lathe(name, prof, 48); hat.scale = (1, 1.12, 1); hat.location = (0, head.y - .01, eye.z + .035); bake_obj_xform(hat)
    mod(hat, 'SOLIDIFY', thickness=.004, offset=-1); bake_mods(hat)
    return hat

def spear(tag, L0, L1, mats, head_len=.22, butt=True, double=False):
    """A cavalry spear built about its grip (origin), point to +Z: a cornel shaft, an iron
    head, a bronze butt-spike (or a second blade, for the xyston)."""
    wood, iron, bronze = mats
    out = [(lathe(tag + 'Shaft', [(0, -L0), (.0105, -L0 + .01), (.0125, 0), (.0105, L1), (0, L1 + .004)], 12), wood),
           (lathe(tag + 'Head', [(.0105, L1 - .03), (.018, L1 + .02), (.022, L1 + head_len * .35), (.012, L1 + head_len * .75), (0, L1 + head_len)], 8), iron)]
    out[1][0].scale = (1, .32, 1)
    if double:
        hb = lathe(tag + 'Butt', [(.0105, -L0 + .03), (.018, -L0 - .02), (.02, -L0 - head_len * .3), (.01, -L0 - head_len * .65), (0, -L0 - head_len * .8)], 8); hb.scale = (1, .32, 1)
        out.append((hb, iron))
    elif butt:
        out.append((lathe(tag + 'Butt', [(0, -L0 - .16), (.012, -L0 - .02), (.0115, -L0 + .02)], 8), bronze))
    return out

def baldric_kopis(tag, body, under, J, add, mats):
    """A baldric from the right shoulder to the left hip over the armour, and a kopis
    in its scabbard hanging there."""
    leather, bronze, iron = mats; sh_z = J['l-shoulder'].z; sf = Surf([body] + under)
    pts = []
    for front in (True, False):
        row = []
        for i in range(25):
            t = i / 24; x = -.12 + .3 * t; zz = sh_z + .05 - (sh_z + .05 - .95) * t
            h = sf.hit(V((x, 0, zz)), V((0, -1 if front else 1, 0)), .6)
            if h: row.append((h[0] + h[1] * .006, h[1]))
        add(P.ribbon(f'{tag}Baldric{"F" if front else "B"}', row, .035, .003), leather, 'skin')
    P.sheath(tag + 'Kopis', .5, .9, V((.2, .02, .95)), (math.radians(-28), math.radians(12), 0), (leather, bronze), add, width=.03, hilt_scale=1.1)

def tier_kit(body, J, add, hair, wood_iron):
    """Kit for tiers 2 to 5."""
    wood, iron = wood_iron; bronze = m_bronze('RiderBronze', .3, 512)
    sh_z = J['l-shoulder'].z
    # L2 Hippeus
    tunic('L2_', body, J, add, '#cdc3a6', skirt=True)
    lino2 = linothorax('L2_', body, J, add, H.m_linen_band('Lino2', '#d9cba6', '#6b4a2a', 1.0, sh_z - .02), m_cloth('Yoke2', '#d9cba6', 700, .04))
    chlamys('L2_', body, J, add, '#6e6646')
    boots('L2_', body, J, add, '#5c3c22', high=True)
    for o in attic_helmet('L2_Helmet', body, hair, J, bronze): add(o, bronze, 'head')
    for o, mt in spear('L2_Spear', .82, 1.5, (wood, iron, bronze)): add(o, mt, 'later:spear')
    # L3 Hetairos
    tunic('L3_', body, J, add, '#d8d0bc', skirt=True)
    lino3 = linothorax('L3_', body, J, add, m_scales(), m_cloth('Yoke3', '#e2d8c0', 700, .04))
    chlamys('L3_', body, J, add, '#4e1838', border='#d2a62e')
    boots('L3_', body, J, add, '#4a2e1a', high=True)
    dome, brim = boeotian_helmet('L3_Helmet', body, hair, J, bronze); add(dome, bronze, 'head'); add(brim, bronze, 'head')
    top = max((dome.matrix_world @ v.co for v in dome.data.vertices), key=lambda q: q.z)
    add(plume('L3_Plume', top - V((0, 0, .004))), H.m_flat('Horsehair', '#ece6da', .6), 'head')
    for o, mt in spear('L3_Xyston', 1.25, 2.15, (wood, iron, bronze), .2, double=True): add(o, mt, 'later:spear')
    baldric_kopis('L3_', body, [lino3], J, add, (m_leather('Baldric3', '#3a2414'), bronze, iron))
    # L4 Hippakontistes
    tunic('L4_', body, J, add, '#7a5638', skirt=True)
    chlamys('L4_', body, J, add, '#5a4430')
    boots('L4_', body, J, add, '#6a4a2c', high=False)
    add(petasos('L4_Petasos', J), m_cloth('Felt4', '#8a6a44', 250, .1, 512, .95), 'head')
    # L5 Tarantine
    tunic('L5_', body, J, add, '#c8c2b2', skirt=True)
    chlamys('L5_', body, J, add, '#3b4a6b')
    boots('L5_', body, J, add, '#6a4a2c', high=False)
    leaves, twig = wreath('L5_Wreath', body, hair, J)
    add(leaves, H.m_flat('Laurel', '#3e5a2a', .55), 'head'); add(twig, H.m_flat('LaurelTwig', '#4a3a22', .7), 'head')
    shield = lathe('L5_Shield', [(0, .05), (.12, .045), (.22, .03), (.28, .012), (.3, 0), (.302, -.006)], 48)
    mod(shield, 'SOLIDIFY', thickness=.004, offset=-1); bake_mods(shield)
    boss = lathe('L5_ShieldBoss', [(0, .072), (.03, .068), (.05, .056), (.06, .046)], 24)
    add(shield, m_bronze('ShieldBronze', .25, 512, engrave=.3), 'later:shield'); add(boss, bronze, 'later:shield')


# ── Rig ─────────────────────────────────────────────────────────────────────
def rider_spec(J):
    B = H.skeleton_spec(J)
    return [(n, h, t, 'h_saddle' if n == 'root' else p, d) for n, h, t, p, d in B]

def set_deform(rig, names, on):
    for n in names: rig.data.bones[n].use_deform = on

REINS = 'reins'   # the bone that carries the reins' hand end: it rides the saddle and is keyed to the left fist

def smooth(a, b, t):
    x = min(1.0, max(0.0, (t - a) / (b - a))); return x * x * (3 - 2 * x)

def ring_centres():
    out = {}
    for o in bpy.data.objects:
        if o.name.startswith('BitRing'):
            out[o.name[-1]] = o.matrix_world @ (sum((v.co for v in o.data.vertices), V()) / len(o.data.vertices))
    return out

def beside(bvh, pts, sx, clear=.012):
    """Push points out of the horse sideways, so a rein runs along the side of the neck
    instead of through it."""
    out = []
    for p in pts:
        h = bvh.ray_cast(V((sx, p.y, p.z)), V((-sx, 0, 0)), 2); q = p.copy()
        if h[0] is not None and sx * q.x < sx * h[0].x + clear: q.x = h[0].x + sx * clear
        out.append(q)
    return out

def rein_path(bvh, a, b, sx, n=36, sag=0.0):
    pts = [a.lerp(b, i / (n - 1)) - V((0, 0, sag * 4 * i / (n - 1) * (1 - i / (n - 1)))) for i in range(n)]
    for _ in range(5):
        pts = beside(bvh, pts, sx)
        pts = [pts[0]] + [(pts[i - 1] + pts[i] * 2 + pts[i + 1]) / 4 for i in range(1, n - 1)] + [pts[-1]]
    return beside(bvh, pts, sx)

def skin_reins(ob, rig, horse_body, paths, hand=(.55, .9)):
    """Skin reins to the horse from its nearest face (head and neck, never a leg), handing
    over to the reins bone towards the fist when hand is given."""
    bvh = BVHTree.FromObject(horse_body, bpy.context.evaluated_depsgraph_get())
    names = {g.index: g.name for g in horse_body.vertex_groups}; hb = horse_body.data
    samples = [(p, i / (len(pts) - 1)) for pts in paths for i, p in enumerate(pts)]
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        s = smooth(*hand, min(samples, key=lambda q: (q[0] - p).length_squared)[1]) if hand else 0.0
        acc = {}
        if s < 1:
            fi = bvh.find_nearest(p)[2]
            for vi in hb.polygons[fi].vertices:
                for ge in hb.vertices[vi].groups:
                    n = names[ge.group]
                    if not any(k in n for k in HR.LEG_BONE): acc[n] = acc.get(n, 0) + ge.weight
            tot = sum(acc.values())
            acc = {n: w / tot * (1 - s) for n, w in acc.items() if w / tot > .02} if tot > 1e-4 else {'h_neck1': 1 - s}
        if s > 0: acc[REINS] = s
        for n, w in acc.items(): (ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)).add([v.index], w, 'REPLACE')
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig

def reins(rig, horse_body, grip):
    """Two sets of reins. L12345_Reins run from the bit rings along the sides of the neck to
    the rider's left fist; L0_Reins, for the horse shown alone, lie over the withers."""
    bvh = BVHTree.FromObject(horse_body, bpy.context.evaluated_depsgraph_get())
    rc = ring_centres(); back = V((0, .02, .004))   # the reins buckle to the back of the rings
    held = [rein_path(bvh, rc[k] + back, grip + V((sx * .012, 0, 0)), sx) for k, sx in (('L', 1), ('R', -1))]
    top = bvh.ray_cast(V((0, -.27, 3)), V((0, 0, -1)), 5)[0] + V((0, 0, .012))   # over the withers, behind the mane
    lying = [rein_path(bvh, rc[k] + back, top + V((sx * .01, 0, 0)), sx, 30, .05) for k, sx in (('L', 1), ('R', -1))]
    lying = lying[0] + lying[1][::-1]
    drop = bvh.ray_cast(grip, V((0, 0, -1)), 2)[0] + V((0, 0, .02))   # where the hand end falls when he lets go
    return (curve_mesh('L12345_Reins', [[tuple(p) for p in L] for L in held], .0045, res=1), held,
            curve_mesh('L0_Reins', [[tuple(p) for p in lying]], .0045, res=1), [lying], drop)

def add_reins_bone(rig, at):
    H.activate(rig); bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones.new(REINS); eb.head = at; eb.tail = at + V((0, .08, 0)); eb.roll = 0; eb.use_deform = True
    eb.parent = rig.data.edit_bones['h_saddle']
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.pose.bones[REINS].rotation_mode = 'QUATERNION'

def fist_point(rig, n):
    """The middle of a closed fist: where a shaft or the reins pass through it."""
    hand = rig.pose.bones[f'hand.{n}']; Mh = hand.matrix.to_3x3()
    palm = (Mh @ H.HAND_REF[n][1]).normalized()
    return hand.head + (hand.tail - hand.head) * .5 + palm * .026

def key_reins(rig, length, drop, release=None):
    """Key the reins bone to the left fist on every frame. With release=(f0, f1) the
    rider lets go between those frames and the reins settle on the withers."""
    pb = rig.pose.bones[REINS]; sad = rig.pose.bones['h_saddle']
    inv = rig.data.bones['h_saddle'].matrix_local.inverted(); rel = inv @ rig.data.bones[REINS].matrix_local
    for f in range(1, length + 1):
        bpy.context.scene.frame_set(f)
        M = sad.matrix @ rel; target = fist_point(rig, 'L')
        if release:
            s = smooth(release[0], release[1], f)
            if s > 0: target = target.lerp(sad.matrix @ inv @ drop, s)
        M.translation = target; pb.matrix = M; H._upd()
        pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)


# ── Poses ───────────────────────────────────────────────────────────────────
def rider_poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def foot(side, w): return tuple(V(w) - J[f'{side}-ankle'] - SEAT)
    def armR(w, hint=(-.4, .6, -.4), jav=(0, -1, .1), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': jav, **kw}
    def armL(w, hint=(.4, .6, -.4), grip=(0, -.1, -1), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': grip, **kw}
    base = {'root': {'loc': tuple(SEAT)}, 'hips': {'rot': (-.08, 0, 0)}, 'chest': {'rot': (.06, 0, 0)}, 'head': {'rot': (.03, 0, 0)},
            'ik_foot.L': {'loc': foot('l', (.27, -.15, .64))}, 'ik_foot.R': {'loc': foot('r', (-.27, -.15, .64))}, 'knee': (.8, -1, 0),
            'armR': armR((-.05, -.24, -.33)), 'armL': armL((-.09, -.3, -.27))}
    def st(**over):
        P_ = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
        for k, v in over.items(): P_[k] = v if (k.startswith('arm') or k == 'knee') else {**P_.get(k, {}), **v}
        return P_
    return st, armR, armL

def root_lying(J, at, rot):
    """An armature-space matrix for the rider's root that puts his pelvis at `at`, turned by rot."""
    R = Euler(rot).to_matrix(); pelvis = J['pelvis']
    M = R.to_4x4(); M.translation = V(at) - R @ pelvis
    return M

THROW_RELEASE = 12

def key_bones(rig, names, f):
    for n in names:
        pb = rig.pose.bones[n]; pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)

def actions(rig, J, drop):
    st, armR, armL = rider_poses(J)
    HB = HR.BONE_NAMES; RB = [b.name for b in rig.pose.bones if b.name not in HB and b.name != REINS]
    A = []
    def clip(name, length, horse, rider, release=None):
        """horse: a function of the frame (keyed every frame) or [(frame, HP)]; rider: [(frame, spec or callable)].
        The reins follow the left fist, until release=(f0, f1) when he lets go."""
        rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
        hkeys = [(f, horse(f)) for f in range(1, length + 1)] if callable(horse) else horse
        hmap = dict(hkeys)
        def horse_at(f):   # nearest earlier horse key, so the rider is solved on the right mount pose
            ks = [k for k in hmap if k <= f]; return hmap[max(ks)] if ks else hkeys[0][1]
        for f, HP in hkeys:
            HR.hpose(rig, HP); key_bones(rig, HB, f)
        for f, R in rider:
            HR.hpose(rig, horse_at(f)); spec = R() if callable(R) else R
            H.pose(rig, spec, keep=HB); key_bones(rig, RB, f)
        key_reins(rig, length, drop, release)
        A.append(act)
    idle_h = [(f, {'body': {'loc': (0, 0, .005 * math.sin(2 * math.pi * f / 48))}, 'h_neck1': {'rot': (.03 * math.sin(2 * math.pi * f / 48 + 1), 0, 0)},
                   'h_tail2': {'rot': (0, 0, .14 * math.sin(2 * math.pi * f / 24))}}) for f in (1, 7, 13, 19, 25, 31, 37, 43, 48)]
    clip('Idle', 48, idle_h, [(1, st()), (24, st(chest={'rot': (.075, 0, 0)}, armR=armR((-.05, -.24, -.34)))), (48, st())])
    clip('Walk', 28, lambda f: HR.gait(rig, 'walk', f - 1),
         [(1, st(hips={'rot': (-.08, 0, .03)})), (8, st()), (15, st(hips={'rot': (-.08, 0, -.03)})), (22, st()), (28, st(hips={'rot': (-.08, 0, .03)}))])
    lean = dict(hips={'rot': (-.02, 0, 0)}, chest={'rot': (.2, 0, 0)}, head={'rot': (-.12, 0, 0)})
    clip('Gallop', 16, lambda f: HR.gait(rig, 'gallop', f - 1),
         [(1, st(**lean)), (5, st(**{**lean, 'chest': {'rot': (.24, 0, 0)}})), (9, st(**lean)), (13, st(**{**lean, 'chest': {'rot': (.24, 0, 0)}})), (16, st(**lean))])
    gallop = lambda f: HR.gait(rig, 'gallop', f - 1)
    clip('Throw', 32, gallop, [
        (1, st(**lean)),
        (8, st(hips={'rot': (-.04, 0, .1)}, chest={'rot': (-.02, 0, .45)}, head={'rot': (-.05, 0, -.4)},
               armR=armR((-.05, .16, .2), hint=(-1, .15, -.35), jav=(0, -1, .2)), armL=armL((-.06, -.42, -.12), hint=(1, .3, -.3)))),
        (THROW_RELEASE, st(chest={'rot': (.16, 0, -.2)}, head={'rot': (0, 0, .1)},
               armR=armR((.04, -.36, .16), hint=(-1, .3, 0), jav=(0, -1, .05)))),
        (16, st(chest={'rot': (.24, 0, -.28)}, armR=armR((.12, -.32, -.2), hint=(-1, .4, -.3), jav=(.2, -1, -.4)))),
        (28, st(**lean)), (32, st(**lean))])
    clip('Thrust', 32, gallop, [
        (1, st(**lean)),
        (7, st(chest={'rot': (.05, 0, .26)}, armR=armR((-.02, .05, .15), hint=(-1, .35, .15), jav=(0, -1, .02)))),
        (11, st(chest={'rot': (.22, 0, -.1)}, armR=armR((.03, -.42, .02), hint=(-1, .2, .05), jav=(.03, -1, -.18)))),
        (16, st(chest={'rot': (.2, 0, -.08)}, armR=armR((.03, -.38, .02), hint=(-1, .2, .05), jav=(.03, -1, -.16)))),
        (28, st(**lean)), (32, st(**lean))])
    hind = HR.rest_hoof(rig, 'LH'); pivot = (0, hind.y, .1)
    fold = {'off': (0, -.1, .32), 'cannon': 1.5, 'pastern': -1.2}
    rear_up = {'body': {'rot': (-.62, 0, 0), 'pivot': pivot}, 'h_neck1': {'rot': (.25, 0, 0)}, 'h_head': {'rot': (.2, 0, 0)}, 'h_tail1': {'rot': (.3, 0, 0)},
               'legs': {'LF': {**fold, 'body': True}, 'RF': {**fold, 'off': (0, -.05, .27), 'body': True},
                        'LH': {'off': (0, -.12, 0)}, 'RH': {'off': (0, -.1, 0)}}}
    clip('Rear', 32, [(1, {}), (9, rear_up), (17, {**rear_up, 'body': {'rot': (-.66, 0, 0), 'pivot': pivot}}), (26, {'legs': {'LF': {'off': (0, -.12, .05)}}}), (32, {})],
         [(1, st()), (9, st(hips={'rot': (.1, 0, 0)}, chest={'rot': (.55, 0, 0)}, head={'rot': (-.3, 0, 0)}, armL=armL((-.06, -.42, -.22)))),
          (17, st(hips={'rot': (.12, 0, 0)}, chest={'rot': (.58, 0, 0)}, head={'rot': (-.32, 0, 0)}, armL=armL((-.06, -.42, -.22)))), (26, st()), (32, st())])
    flinch = {'body': {'loc': (.06, .04, .02), 'rot': (-.06, 0, .08)}, 'h_neck1': {'rot': (-.25, 0, -.1)}, 'h_head': {'rot': (-.2, 0, 0)},
              'legs': {'LF': {'off': (.02, -.05, .12), 'cannon': .8, 'pastern': -.4}}}
    clip('Hit', 18, [(1, {}), (4, flinch), (10, {'body': {'loc': (.02, .01, 0)}, 'h_neck1': {'rot': (-.08, 0, 0)}}), (18, {})],
         [(1, st()), (4, st(chest={'rot': (-.28, 0, .18)}, head={'rot': (-.28, 0, .1)}, armR=armR((.0, -.1, -.3)), armL=armL((-.02, -.2, -.25)))),
          (10, st(chest={'rot': (-.08, 0, .08)})), (18, st())])
    # Death: the horse stumbles, drops to its knees and rolls onto its left side; the rider
    # is thrown off to the right and lands on his back clear of it.
    kneel = {'off': (0, .1, .26), 'cannon': 1.55, 'pastern': -1.3, 'body': True}
    tuck = {'off': (0, -.32, .3), 'cannon': -1.2, 'pastern': -.2, 'body': True}
    death_h = [(1, {}),
               (8, {'body': {'loc': (0, -.04, -.03), 'rot': (.1, 0, 0)}, 'h_neck1': {'rot': (.25, 0, 0)}, 'legs': {'LF': {'off': (0, -.05, 0), 'cannon': .3}}}),
               (16, {'body': {'loc': (0, -.05, -.34), 'rot': (.36, 0, 0)}, 'h_neck1': {'rot': (.35, 0, 0)}, 'h_head': {'rot': (.2, 0, 0)},
                     'legs': {'LF': kneel, 'RF': kneel}}),
               (26, {'body': {'loc': (0, -.02, -.6), 'rot': (.04, 0, 0)}, 'h_neck1': {'rot': (.2, 0, 0)},
                     'legs': {'LF': kneel, 'RF': kneel, 'LH': tuck, 'RH': tuck}}),
               (36, {'body': {'loc': (.28, 0, -.66), 'rot': (0, -1.35, 0)}, 'h_neck1': {'rot': (.15, 0, .3)}, 'h_head': {'rot': (.1, 0, .25)},
                     'legs': {k: {'off': (0, 0, 0), 'body': True} for k in ('LF', 'RF', 'LH', 'RH')}}),
               (48, {'body': {'loc': (.3, 0, -.67), 'rot': (0, -1.4, 0)}, 'h_neck1': {'rot': (.1, 0, .35)}, 'h_head': {'rot': (.05, 0, .35)},
                     'legs': {k: {'off': (0, .03, 0), 'body': True} for k in ('LF', 'RF', 'LH', 'RH')}})]
    # arms flung out as he falls, still gripping the javelins, which then lie along his body
    limp = dict(armR=armR((-.44, -.1, -.16), hint=(0, .5, -1), jav=(0, -.1, -1), fist=.6), armL=armL((.44, -.1, -.16), hint=(0, .5, -1), grip=(0, .1, 1), fist=.6))
    clip('Death', 48, death_h, [
        (1, st()), (6, st(chest={'rot': (-.3, 0, .1)}, head={'rot': (-.3, 0, 0)})),
        (14, st(root={'loc': tuple(SEAT + V((-.08, 0, -.02))), 'rot': (0, -.45, 0)}, chest={'rot': (.1, -.2, 0)}, **limp)),
        (20, lambda: st(root={'matrix': root_lying(J, (-.62, -.12, .78), (-.55, -.9, 0))}, chest={'rot': (.1, 0, 0)}, knee=(.15, -1, 0),
                        **{'ik_foot.L': {'loc': (0, 0, 0)}, 'ik_foot.R': {'loc': (0, 0, 0)}}, **limp)),
        (27, lambda: st(root={'matrix': root_lying(J, (-.95, -.15, .12), (-math.pi / 2, 0, .1))}, chest={'rot': (0, 0, 0)}, knee=(.15, -1, 0),
                        **{'ik_foot.L': {'loc': (0, 0, 0)}, 'ik_foot.R': {'loc': (0, .05, .03)}}, **limp)),
        (48, lambda: st(root={'matrix': root_lying(J, (-.96, -.15, .11), (-math.pi / 2, 0, .1))}, chest={'rot': (0, 0, 0)}, head={'rot': (0, .3, 0)},
                        knee=(.15, -1, 0), **{'ik_foot.L': {'loc': (0, 0, 0)}, 'ik_foot.R': {'loc': (0, .05, .03)}}, **limp))], release=(8, 13))
    rig.animation_data.action = A[0]
    return A

def place_in_hands(rig, items):
    """In the idle pose: the throwing javelin (or a tier's spear) through the right fist,
    the spares upright through the left with the reins, the Tarantine's shield on the
    outside of the left forearm."""
    PB = rig.pose.bones
    def fist(n): return fist_point(rig, n), (PB[f'hand.{n}'].matrix.to_3x3() @ H.HAND_REF[n][0]).normalized()
    grip, k = fist('R'); x = k.orthogonal().normalized(); Mj = Matrix((x, k.cross(x), k)).transposed().to_4x4(); Mj.translation = grip
    gripL, kL = fist('L'); up = -kL; xl = up.orthogonal().normalized(); Ml = Matrix((xl, up.cross(xl), up)).transposed().to_4x4(); Ml.translation = gripL
    throw_root = bpy.data.objects.new('ThrowJavelin', None); link(throw_root); throw_root.matrix_world = Mj
    bpy.context.view_layer.update(); H.bind_rigid(throw_root, rig, 'hand.R')
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        if bind == 'later:hand.R':
            ob.matrix_world = Mj @ ob.matrix_basis; bpy.context.view_layer.update()
            mw = ob.matrix_world.copy(); ob.parent = throw_root; ob.matrix_world = mw
        elif bind == 'later:spear':
            ob.matrix_world = Mj @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.R')
        elif bind == 'later:shield':
            fo = PB['forearm.L']; ax = (fo.tail - fo.head).normalized()
            out = V((1, -.35, .1)); out = (out - ax * out.dot(ax)).normalized()   # out to the left and a little forward
            x = ax.cross(out).normalized(); Ms = Matrix((x, out.cross(x), out)).transposed().to_4x4()
            Ms.translation = fo.head + (fo.tail - fo.head) * .45 + out * .05
            ob.matrix_world = Ms @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'forearm.L')
        else:
            i = int(bind[-1]); spread = Matrix.Rotation(math.radians(5 * i), 4, 'Y') @ Matrix.Translation((.012 * i, 0, 0))
            ob.matrix_world = Ml @ spread @ Matrix.Translation((0, 0, .5)) @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.L')   # held low on the shaft
    return gripL


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    body, J = H.build_body()
    items = {}
    def add(ob, mt, bind): items[ob.name] = (ob, mt, bind); return ob
    rider_kit(body, J, add)
    items['Body'] = (body, m_skin(J['l-eye']), 'skin-body')
    horse_items = {}
    def hadd(ob, mt, bind): horse_items[ob.name] = (ob, mt, bind); return ob
    horse_body, _ = HR.build_horse(hadd)
    # tags: the rider is L12345_ unless his kit is already tagged; the horse stays untagged
    for name, (ob, mt, bind) in list(items.items()):
        if not re.match(r'^L\d+_', ob.name): ob.name = 'L12345_' + ob.name
    allitems = {**items, **horse_items}
    H.bake_textures(allitems)
    B = HR.bones() + rider_spec(J)
    rig = H.build_armature(B, J); rig.name = 'HippeisRig'; rig.data.name = 'HippeisRig'
    horse_def = [b[0] for b in HR.bones() if b[4]]; rider_def = [b[0] for b in rider_spec(J) if b[4]]
    rig.data.pose_position = 'REST'; H._upd()
    for target, off in ((body, horse_def), (horse_body, rider_def)):
        set_deform(rig, off, False)
        H.activate(target); rig.select_set(True); bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        set_deform(rig, off, True)
    for name, (ob, mt, bind) in allitems.items():
        if ob in (body, horse_body) or bind.startswith('later:'): continue
        if bind == 'skin': H.bind_skin(ob, rig, body)
        elif bind in ('horse', 'horse-trunk'):
            H.bind_skin(ob, rig, horse_body)
            if bind == 'horse-trunk': HR.trunk_only(ob)
        elif bind == 'tail': HR.weight_to_chain(ob, rig, HR.TAIL_BONES)
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = rider_poses(J)
    HR.hpose(rig, {}); H.pose(rig, st(), keep=HR.BONE_NAMES)
    grip = place_in_hands(rig, allitems)
    add_reins_bone(rig, grip)
    held, held_paths, lying, lying_paths, drop = reins(rig, horse_body, grip)
    leather = m_leather('Reins', '#3e2818', 256)
    H.bake_textures({o.name: (o, leather, '') for o in (held, lying)})
    skin_reins(held, rig, horse_body, held_paths)
    skin_reins(lying, rig, horse_body, lying_paths, hand=None)
    if horse_body.data.validate(verbose=True): print('repaired the horse mesh')   # the glTF exporter checks this too
    return rig, actions(rig, J, drop)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'hippeis.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'hippeis.blend'))
    print('built', [a.name for a in acts])
