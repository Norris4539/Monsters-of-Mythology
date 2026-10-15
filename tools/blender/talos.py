"""Realistic Talos line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/talos.py third_party/makehuman assets/models [--renders]

The bronze men of Crete, after the reference sheets in refs/talos: the MakeHuman man of
the infantry lines, heavier in build, cast in bronze. Each tier has its own body (its own
bronze) on one skeleton. The build is made at the infantry's 1.76 m and exported at the
automaton's 2.6 m; the gallery scales Talos (3 m) and the Colossus (4 m) up from that.
  L1 Bronze Automaton  dark bronze with green patina in the recesses, short cast curls
  L2 Talos             polished bronze with a darker patina, curly hair and beard, a boulder
                       in the right hand
  L3 Colossus          gleaming bronze, a radiate crown of the sun's rays, a cloak of
                       hammered bronze over the shoulders
Every tier: the joints shown as clean seams, inlaid stone eyes, fists clenched, and the
single vein of ichor from the neck to the right ankle, closed there by a bronze nail.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, Mat
from peltast import curve_mesh, bake_obj_xform

# The Riace bronzes: broad, lean and heavily muscled.
H.TARGETS = [('caucasian-male-young.target', .8), ('african-male-young.target', .1), ('asian-male-young.target', .1),
             ('universal-male-young-maxmuscle-averageweight.target', .75), ('universal-male-young-maxmuscle-minweight.target', .25)]
H.HEIGHT = 1.76
OUT = H.OUT
HEIGHTS = {1: 2.6, 2: 3.0, 3: 4.0}   # metres, after the sheets
SCALE = HEIGHTS[1] / H.HEIGHT         # the export's scale: the automaton's height
random.seed(23)


# ── Bronze ──────────────────────────────────────────────────────────────────
# Each tier's bronze: base, middle and high colours, the patina and how much of it
# lies in the recesses and in blotches, polished highlights on the edges, roughness.
BRONZES = {
    1: dict(cols=('#2b2117', '#3f3121', '#5a4630'), patina='#3d5444', recess=.85, blotch=.35, edge='#7b6242', rough=.46),
    2: dict(cols=('#33251a', '#5a4229', '#7d5f3b'), patina='#1c150f', recess=.7, blotch=.15, edge='#a5835a', rough=.32),
    3: dict(cols=('#4f3019', '#7a4c27', '#a06a3c'), patina='#3a2414', recess=.4, blotch=0, edge='#cf9a62', rough=.22),
}

def seam_rings(J):
    """Where the cast pieces meet: rings round the neck and each limb at its joints,
    as (centre, axis, radius of the limb there)."""
    R = [(J['neck'] + (J['head'] - J['neck']) * .1, (J['head'] - J['neck']).normalized(), .085)]
    for s in 'lr':
        sh, el, ha = J[f'{s}-shoulder'], J[f'{s}-elbow'], J[f'{s}-hand']
        hip, kn, an = J[f'{s}-upper-leg'], J[f'{s}-knee'], J[f'{s}-ankle']
        R += [(sh + (el - sh) * .14, (el - sh).normalized(), .07),       # where the arm leaves the shoulder
              (el, (ha - el).normalized(), .058),
              (ha - (ha - el).normalized() * .015, (ha - el).normalized(), .045),
              (hip + (kn - hip) * .13, (kn - hip).normalized(), .1),     # the top of the thigh
              (kn + V((0, 0, .015)), (an - kn).normalized(), .075),
              (an + V((0, 0, .035)), (an - kn).normalized(), .055)]
    return R

def ring_mask(m, rings, width=.0016, soft=.0012):
    """A float socket: 1 on a thin groove round each ring, 0 elsewhere (object space)."""
    acc = None
    for c, u, R in rings:
        sub = m.node('ShaderNodeVectorMath', operation='SUBTRACT'); m.L.new(m.coord.outputs['Object'], sub.inputs[0]); sub.inputs[1].default_value = c
        dot = m.node('ShaderNodeVectorMath', operation='DOT_PRODUCT'); m.L.new(sub.outputs[0], dot.inputs[0]); dot.inputs[1].default_value = u
        ab = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(dot.outputs['Value'], ab.inputs[0])
        band = m.node('ShaderNodeMapRange', **{'From Min': width + soft, 'From Max': width}); m.L.new(ab.outputs[0], band.inputs['Value'])
        sc = m.node('ShaderNodeVectorMath', operation='SCALE'); sc.inputs[0].default_value = u; m.L.new(dot.outputs['Value'], sc.inputs['Scale'])
        rad = m.node('ShaderNodeVectorMath', operation='SUBTRACT'); m.L.new(sub.outputs[0], rad.inputs[0]); m.L.new(sc.outputs[0], rad.inputs[1])
        ln = m.node('ShaderNodeVectorMath', operation='LENGTH'); m.L.new(rad.outputs[0], ln.inputs[0])
        near = m.node('ShaderNodeMapRange', **{'From Min': R + .012, 'From Max': R}); m.L.new(ln.outputs['Value'], near.inputs['Value'])
        mul = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(band.outputs[0], mul.inputs[0]); m.L.new(near.outputs[0], mul.inputs[1])
        if acc is None: acc = mul.outputs[0]
        else:
            mx = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(acc, mx.inputs[0]); m.L.new(mul.outputs[0], mx.inputs[1]); acc = mx.outputs[0]
    return acc

def m_cast(name, lv, rings=None, res=2048, hammer=0.0):
    """Cast bronze of a tier: mottled metal, patina settled in the recesses (and in
    blotches on the automaton), polish on the edges, the joint seams cut in, and for the
    cloak the dents of the hammer."""
    b = BRONZES[lv]; m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(5, 6, .55).outputs['Fac'], [(.3, srgb(b['cols'][0])), (.55, srgb(b['cols'][1])), (.8, srgb(b['cols'][2]))]).outputs['Color']
    geo = m.node('ShaderNodeNewGeometry')
    cav = m.ramp(geo.outputs['Pointiness'], [(.47, (1, 1, 1)), (.505, (0, 0, 0))])
    blot = m.ramp(m.noise(9, 5, .65).outputs['Fac'], [(.5, (0, 0, 0)), (.72, (1, 1, 1))])
    pat = m.mix(m.mix((0, 0, 0), cav.outputs['Color'], b['recess']), m.mix((0, 0, 0), blot.outputs['Color'], b['blotch']), 1.0, 'LIGHTEN')
    col = m.mix(col, srgb(b['patina']), pat)
    wear = m.ramp(geo.outputs['Pointiness'], [(.53, (0, 0, 0)), (.6, (1, 1, 1))])
    col = m.mix(col, srgb(b['edge']), wear.outputs['Color'])
    fine = m.noise(90, 3, .6)
    height = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(fine.outputs['Fac'], height.inputs[0]); height.inputs[1].default_value = .25
    h = height.outputs[0]
    if hammer:
        vor = m.node('ShaderNodeTexVoronoi', Scale=38.0); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
        dent = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(vor.outputs['Distance'], dent.inputs[0]); dent.inputs[1].default_value = hammer; m.L.new(h, dent.inputs[2])
        h = dent.outputs[0]
    if rings:
        seam = ring_mask(m, rings)
        col = m.mix(col, srgb('#120d08'), seam)
        cut = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(seam, cut.inputs[0]); cut.inputs[1].default_value = -1.2; m.L.new(h, cut.inputs[2])
        h = cut.outputs[0]
    rough = m.ramp(fine.outputs['Fac'], [(.3, (b['rough'] - .06,) * 3), (.7, (b['rough'] + .08,) * 3)])
    m.set(col, rough.outputs['Color'], h, .5, .0025)
    return m

def m_stone_eye():
    """Inlaid eyes: white stone, a dark iris and pupil."""
    em = Mat('StoneEye', res=128)
    grad = em.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
    mp = em.node('ShaderNodeMapping'); em.L.new(em.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (95, 95, 95); mp.inputs['Location'].default_value = (0, .0118 * 95, 0)
    em.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
    col = em.ramp(grad.outputs['Fac'], [(.0, srgb('#e6e0d2')), (.5, srgb('#e6e0d2')), (.55, srgb('#5a4a3a')), (.82, srgb('#2a2018')), (.86, (0.01, .01, .01))])
    em.set(col.outputs['Color'], .25)
    return em

def m_stone(name='Boulder'):
    m = Mat(name, res=512)
    col = m.ramp(m.noise(6, 6, .6).outputs['Fac'], [(.3, srgb('#2f2c28')), (.55, srgb('#4a453f')), (.8, srgb('#615a52'))])
    lich = m.ramp(m.noise(14, 4, .7).outputs['Fac'], [(.62, (0, 0, 0)), (.7, (1, 1, 1))])
    col = m.mix(col.outputs['Color'], srgb('#6b6a52'), lich.outputs['Color'])
    m.set(col, .88, m.noise(40, 6, .65).outputs['Fac'], .5, .004)
    return m


# ── Body, shaped in the mesh ────────────────────────────────────────────────
def define(body, J, k=1.0, iters=7):
    """Deepen the muscle forms the base mesh only hints at, as a sculptor would: each
    vertex of the trunk and limbs moves away from where a volume-preserving smooth puts
    it (unsharp masking), fading out at the neck, wrists and ankles."""
    tmp = link(body.copy()); tmp.data = body.data.copy()
    mod(tmp, 'LAPLACIANSMOOTH', iterations=iters, lambda_factor=1.0, use_volume_preserve=True, use_normalized=True)
    dg = bpy.context.evaluated_depsgraph_get(); sm = tmp.evaluated_get(dg).to_mesh()
    smooth = [v.co.copy() for v in sm.vertices]
    tmp.evaluated_get(dg).to_mesh_clear(); me = tmp.data; bpy.data.objects.remove(tmp); bpy.data.meshes.remove(me)
    fade = lambda x, a, b: min(1, max(0, (x - a) / (b - a)))
    nz, az = J['neck'].z, J['l-ankle'].z
    for v, q in zip(body.data.vertices, smooth):
        p = v.co; w = fade(p.z, az + .04, az + .14) * fade(-p.z, -(nz + .01), -(nz - .06))
        for s in 'lr':   # not the hands
            wr, el = J[f'{s}-hand'], J[f'{s}-elbow']; u = (wr - el).normalized()
            w *= 1 - fade((p - wr).dot(u), -.05, -.01)
        v.co = p + (p - q) * k * w
    body.data.update()


# ── Hands, shaped in the mesh ───────────────────────────────────────────────
# MakeHuman's finger joints: 1 the knuckle, 2 and 3 the middle and last joints, 4 the tip;
# for the thumb 1 is its root by the wrist. A statue's hands never open, so the fists are
# bent into the body itself rather than posed: each finger turns at its three joints
# towards the palm, blended across a few millimetres at each joint. The thumb bends at
# its two joints and, in a fist, turns at its root to lie across the first two fingers.
FIST = dict(mcp=1.5, pip=1.7, dip=.9, thumb=(.25, .5), tuck=True)
GRIP = dict(mcp=.55, pip=.8, dip=.5, thumb=(.2, .3), tuck=False)    # cupped round a boulder

def _rot(p, pivot, R): return R @ (p - pivot) + pivot

def hand_frame(J, s):
    """The wrist, the direction along the hand and the palm's normal (rest pose)."""
    wrist = J[f'{s}-hand']; knuck = [J[f'{s}-finger-{k}-1'] for k in (2, 3, 4, 5)]
    along = (sum(knuck, V()) / 4 - wrist).normalized()
    palm = (knuck[3] - knuck[0]).cross(along).normalized()
    if palm.x * (1 if s == 'l' else -1) > 0: palm = -palm   # in the rest pose the palms face the thighs
    return wrist, along, palm

def clench(body, J, sides, mcp, pip, dip, thumb, tuck, blend=.006):
    me = body.data
    for s in sides:
        wrist, along, palm = hand_frame(J, s); sgn = 1 if s == 'l' else -1
        def toward_palm(js, i, a):   # a turn by a at joint i that bends the rest of the digit towards the palm
            ax = (js[i + 1] - js[i]).normalized().cross(palm).normalized()
            if (_rot(js[3], js[i], Matrix.Rotation(.3, 3, ax)) - js[3]).dot(palm) < 0: ax = -ax
            return Matrix.Rotation(a, 3, ax)
        chains = {}
        for k in (2, 3, 4, 5):
            js = [J[f'{s}-finger-{k}-{i}'] for i in (1, 2, 3, 4)]
            chains[k] = (js, [toward_palm(js, i, a) for i, a in enumerate((mcp, pip, dip))])
        js = [J[f'{s}-finger-1-{i}'] for i in (1, 2, 3, 4)]
        bent = lambda k: (toward_palm(js, 1, thumb[0] * k), toward_palm(js, 2, thumb[1] * k))
        R1, R2 = bent(1); R0 = Matrix.Identity(3)
        if tuck:   # bend the thumb until it reaches just over the curled index and middle fingers, and turn it there at its root
            mids = [_rot(chains[k][0][1], chains[k][0][0], chains[k][1][0]) for k in (2, 3)]
            target = (mids[0] * .6 + mids[1] * .4) + palm * .016
            for k in [1 + .1 * i for i in range(30)]:
                R1, R2 = bent(k); tip = _rot(_rot(js[3], js[2], R2), js[1], R1)
                if (tip - js[0]).length <= (target - js[0]).length: break
            R0 = (tip - js[0]).rotation_difference(target - js[0]).to_matrix()
        chains[1] = (js, [R0, R1, R2])
        def nearest(p, ks):   # (distance, digit, how far along it from its first joint) of the nearest digit in ks
            best = None
            for k in ks:
                js, acc = chains[k][0], 0.0
                for i in range(3):
                    a, b = js[i], js[i + 1]; u = b - a; L = u.length
                    t = (p - a).dot(u) / (L * L); q = a + u * max(0, min(1, t))
                    if 0 <= t <= 1 or (i == 0 and t < 0) or i == 2:
                        d = (p - q).length
                        if best is None or d < best[0]: best = (d, k, acc + t * L)
                    acc += L
            return best
        def moved(p, k, arc):   # p carried by digit k's turns, blended across each joint
            js, Rs = chains[k]
            lens = [(js[i + 1] - js[i]).length for i in range(3)]; marks = [0, lens[0], lens[0] + lens[1]]
            bl = (.022 if k == 1 else blend, blend, blend)   # the thumb turns at its root over the whole ball of the thumb
            ws = [min(1, max(0, (arc - m + w) / (2 * w))) for m, w in zip(marks, bl)]
            ws = [w * w * (3 - 2 * w) for w in ws]
            pos = [p]   # p moved by the first n joints' turns, distal first
            for n in (1, 2, 3):
                q = p.copy()
                for i in reversed(range(n)): q = _rot(q, js[i], Rs[i])
                pos.append(q)
            return pos[0] * (1 - ws[0]) + pos[1] * (ws[0] - ws[1]) + pos[2] * (ws[1] - ws[2]) + pos[3] * ws[2]
        for v in me.vertices:
            p = v.co.copy()
            if p.x * sgn < .3 or (p - wrist).dot(along) < -.01 or (p - wrist).length > .3: continue
            df, kf, af = nearest(p, (2, 3, 4, 5)); dt, _, at = nearest(p, (1,))
            m = min(1, max(0, (df - dt) / .016 + .5)); m = m * m * (3 - 2 * m)   # how much it belongs to the thumb
            v.co = moved(p, 1, at) * m + moved(p, kf, af) * (1 - m)
    me.update()


def mantle(name, body, J, length=1.15, nu=44, nv=36):
    """A cloak laid round the back of the neck and over both shoulders, hanging down the
    back clear of the arms; its top edge is pinned where it lies."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    sh_z = J['l-shoulder'].z; bm = bmesh.new(); grid = []; top = set()
    for j in range(nv + 1):
        t = j / nv; row = []
        for i in range(nu + 1):
            a = (i / nu - .5) * math.radians(172); x0, y0 = math.sin(a) * .215, .012 + math.cos(a) * .095
            h = bvh.ray_cast(V((x0, y0, sh_z + .2)), V((0, 0, -1)), 1)
            z0 = (h[0].z if h[0] else sh_z + .03) + .014
            p = V((x0 * (1 + .9 * t), y0 + .36 * t + .1 * t * t, z0 - length * t))
            vtx = bm.verts.new(p); row.append(vtx)
            if j == 0: top.add(tuple(round(c, 4) for c in p))
        grid.append(row)
    uv = bm.loops.layers.uv.new('UV')   # the grid's own UVs: one unbroken island, so the hammered dents shade evenly
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))): lp[uv].uv = (a / nu, 1 - b / nv)
    ob = obj_from_bm(name, bm)
    H.drape(name, ob, lambda c: tuple(round(x, 4) for x in c) in top, body, 80, .3, .006)
    return ob


# ── Kit ─────────────────────────────────────────────────────────────────────
def kit(bodies, J):
    """Hair, beard, eyes, the vein and nail, the crown and boulder. bodies: {level: body}."""
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    body = bodies[1]; head, eye = J['head'], J['l-eye']
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(body, dg)

    # Hair (every tier) and Talos' beard, cast with the head: the infantry's curls in bronze
    got = {}
    P.head_kit(body, J, lambda ob, mt, bind: got.__setitem__(ob.name, ob), [('L2_Beard', .011, .3, '#000000')], volume=1.1)
    for n in ('EyeL', 'EyeR'): add(got[n], m_stone_eye(), 'head')
    hair = got['Hair']
    for lv in (1, 2, 3):
        h = hair if lv == 1 else link(hair.copy())
        if lv > 1: h.data = hair.data.copy()
        h.name = f'L{lv}_Hair'; add(h, m_cast(f'HairBronze{lv}', lv, res=512), 'head')
    add(got['L2_Beard'], m_cast('BeardBronze', 2, res=512), 'head')

    # The vein: from the pit of the neck down the right side of the body to the ankle
    sx = 1 if J['r-ankle'].x > 0 else -1   # the right side's sign of x
    nk, sh_z, pel = J['neck'], J['r-shoulder'].z, J['pelvis']
    hip, kn, an = J['r-upper-leg'], J['r-knee'], J['r-ankle']
    def front(x, z):   # first hit on the front of the trunk
        h = bvh.ray_cast(V((x, -1, z)), V((0, 1, 0)), 2); return h[0]
    def round_leg(a, b, t, ang):   # the leg's skin, seen from the front-outer side at angle ang
        c = a.lerp(b, t); d = V((sx * math.sin(ang), -math.cos(ang), 0))
        h = bvh.ray_cast(c + d * .4, -d, .5); return h[0]
    way = [front(.012 * sx, nk.z - .035), front(.045 * sx, sh_z - .07), front(.075 * sx, sh_z - .2), front(.08 * sx, pel.z + .2),
           front(.085 * sx, pel.z + .07), round_leg(hip, kn, .3, .35), round_leg(hip, kn, .7, .55), round_leg(kn, an, .05, .75),
           round_leg(kn, an, .5, .95), round_leg(kn, an, .88, 1.15)]
    way = [p for p in way if p is not None]
    pts = []
    for i in range(len(way) - 1):   # Catmull-Rom through the waypoints, laid back on the skin
        p0, p1, p2, p3 = way[max(i - 1, 0)], way[i], way[i + 1], way[min(i + 2, len(way) - 1)]
        for k in range(12):
            t = k / 12
            q = .5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            loc, no, fi, d = bvh.find_nearest(q)
            pts.append(tuple(loc + no * .0022))
    loc, no, fi, d = bvh.find_nearest(way[-1]); pts.append(tuple(loc + no * .0022))
    vein = curve_mesh('Vein', [pts], .0042, radii=lambda t: .7 + .3 * min(1, t * 6))
    add(vein, H.m_bronze('VeinBronze', .15, 512), 'skin')
    nail = lathe('Nail', [(0, -.012), (.0055, -.012), (.0055, .012), (.0125, .0135), (.014, .019), (.009, .023), (0, .024)], 20)
    z = no.normalized(); x = z.orthogonal().normalized(); M = Matrix((x, z.cross(x), z)).transposed().to_4x4(); M.translation = loc
    nail.matrix_world = M; bpy.context.view_layer.update(); bake_obj_xform(nail)
    add(nail, H.m_bronze('NailBronze', .1, 256), 'shin.R')

    # Talos' boulder, held in the right fist (placed there in the idle pose)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=4, radius=.09)
    rnd = random.Random(4); bumps = [(V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized(), rnd.uniform(.06, .2)) for _ in range(14)]
    for v in bm.verts:
        d = v.co.normalized(); r = 1.0
        for c, a in bumps: r -= a * max(0, d.dot(c) - .55) * 2.2   # flat faces knocked off it
        r += .04 * math.sin(d.x * 11) * math.sin(d.y * 9 + 1) * math.sin(d.z * 13 + 2)
        v.co = d * .09 * r * V((1.05, .92, 1.0))
    boulder = obj_from_bm('L2_Boulder', bm)
    wrist, along, palm = hand_frame(J, 'r'); boulder.location = wrist + along * .065 + palm * .1   # in the cupped hand
    add(boulder, m_stone(), 'hand.R')

    # The Colossus' radiate crown: a band round the head with the sun's rays standing from it
    zb = eye.z + .05
    ring = [v.co for v in hair.data.vertices if abs(v.co.z - zb) < .01]
    rx = max(abs(p.x) for p in ring) + .006; y0, y1 = min(p.y for p in ring), max(p.y for p in ring)
    cy, ry = (y0 + y1) / 2, (y1 - y0) / 2 + .006
    gilt = m_cast('CrownBronze', 3, res=512)
    band = lathe('L3_Crown', [(.1, -.014), (.104, -.01), (.105, .01), (.1, .014)], 48)
    band.scale = (rx / .1, ry / .1, 1); band.location = (0, cy, zb); bake_obj_xform(band)
    mod(band, 'SOLIDIFY', thickness=.004, offset=-1); bake_mods(band); add(band, gilt, 'head')
    bmr = bmesh.new()
    for i in range(12):
        a = 2 * math.pi * i / 12; d = V((math.sin(a), -math.cos(a), 0))
        base = V((d.x * rx * 1.02, cy + d.y * ry * 1.02, zb + .004))
        out_ = (d * math.cos(math.radians(32)) + V((0, 0, math.sin(math.radians(32))))).normalized()
        side = V((-d.y, d.x, 0)); L = .17 if i % 2 == 0 else .13
        tip = base + out_ * L
        w, t_ = .013, .005
        q = [base + side * w, base - side * w, base + d * t_ - side * .002, base + d * t_ + side * .002]
        vs = [bmr.verts.new(p) for p in (q[0], q[1], base - d * t_, tip)]
        bmr.faces.new((vs[0], vs[1], vs[3])); bmr.faces.new((vs[1], vs[2], vs[3])); bmr.faces.new((vs[2], vs[0], vs[3])); bmr.faces.new((vs[0], vs[2], vs[1]))
    bmesh.ops.recalc_face_normals(bmr, faces=bmr.faces)
    rays = obj_from_bm('L3_CrownRays', bmr, smooth=False); add(rays, gilt, 'head')
    return out


# ── Poses and moves ─────────────────────────────────────────────────────────
def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-1, .5, -.1), **kw): return {'w': SR + V(w), 'hint': hint, 'fist': 0, **kw}   # the fists are in the mesh
    def armL(w, hint=(1, .5, -.1), **kw): return {'w': SL + V(w), 'hint': hint, 'fist': 0, **kw}
    base = {'hips': {'loc': (0, -.008, 0)}, 'chest': {'rot': (.02, 0, 0)}, 'head': {'rot': (.03, 0, 0)},
            'ik_foot.L': {'loc': (-.06, -.02, 0)}, 'ik_foot.R': {'loc': (.06, .02, 0)},
            'armR': armR((-.13, -.02, -.5)), 'armL': armL((.13, -.02, -.5))}
    def st(**over):
        Pp = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): Pp[k] = v if k.startswith('arm') or k == 'knee' else {**Pp.get(k, {}), **v}
        return Pp
    return st, armR, armL

def actions(rig, J):
    """A heavy, deliberate bronze man: Idle, Walk, Smash (a hammer blow of the right fist,
    or the boulder), Hit and Death (he sinks to his knees and topples backwards)."""
    st, armR, armL = poses(J)
    mk = H.make_action; A = []
    A.append(mk(rig, 'Idle', [(1, st()), (36, st(chest={'rot': (.03, 0, .02)}, head={'rot': (.03, 0, .06)})), (72, st())]))
    W = lambda fl, fr, zl, zr, hz, tw: st(**{'ik_foot.L': {'loc': (-.06, fl, zl)}, 'ik_foot.R': {'loc': (.06, fr, zr)},
                                            'hips': {'loc': (0, -.008 + hz, 0), 'rot': (0, tw * .08, 0)}, 'chest': {'rot': (.03, -tw * .1, 0)},
                                            'armR': armR((-.13, .1 * tw, -.49)), 'armL': armL((.13, -.1 * tw, -.49))})
    A.append(mk(rig, 'Walk', [(1, W(-.24, .22, 0, 0, -.02, 1)), (9, W(-.01, -.01, 0, .09, .012, 0)), (17, W(.22, -.24, 0, 0, -.02, -1)),
                              (25, W(-.01, -.01, .09, 0, .012, 0)), (33, W(-.24, .22, 0, 0, -.02, 1))]))
    step = {'ik_foot.L': {'loc': (-.06, -.3, 0)}}
    A.append(mk(rig, 'Smash', [
        (1, st()),
        (12, st(chest={'rot': (-.16, 0, .3)}, hips={'loc': (0, -.02, .03)}, head={'rot': (.05, 0, -.2)},
                armR=armR((-.02, .12, .5), hint=(-1, .3, .3)), armL=armL((.18, -.2, -.3)))),
        (17, st(chest={'rot': (.36, 0, -.12)}, hips={'loc': (0, -.09, -.06)}, head={'rot': (.1, 0, .05)}, **step,
                armR=armR((.06, -.48, -.32), hint=(-1, .2, .3)), armL=armL((.16, -.15, -.4)))),
        (23, st(chest={'rot': (.32, 0, -.1)}, hips={'loc': (0, -.08, -.05)}, **step,
                armR=armR((.05, -.45, -.36), hint=(-1, .2, .3)), armL=armL((.16, -.15, -.4)))),
        (38, st())]))
    A.append(mk(rig, 'Hit', [(1, st()),
        (5, st(chest={'rot': (-.2, 0, .15)}, head={'rot': (-.22, 0, .08)}, hips={'loc': (0, -.01, .06)}, armR=armR((-.16, .06, -.45)), armL=armL((.17, .06, -.45)))),
        (11, st(chest={'rot': (-.08, 0, .05)}, head={'rot': (-.08, 0, 0)})), (22, st())]))
    kneel = dict(hips={'loc': (0, -.4, .05)}, chest={'rot': (.25, 0, .05)}, head={'rot': (.2, 0, 0)},
                 **{'ik_foot.L': {'loc': (-.06, .12, 0)}, 'ik_foot.R': {'loc': (.06, .16, 0)}},
                 armR=armR((-.1, -.15, -.45)), armL=armL((.1, -.12, -.45)), knee=(.1, -1, 0))
    fall = dict(chest={'rot': (-.1, 0, .05)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, -.05, 0)},
                armR=armR((-.3, .05, -.25), hint=(-1, .2, -.3)), armL=armL((.3, .05, -.25), hint=(1, .2, -.3)))
    A.append(mk(rig, 'Death', [(1, st()),
        (10, st(chest={'rot': (.12, 0, .1)}, head={'rot': (.25, 0, 0)}, hips={'loc': (0, -.06, 0)}, armR=armR((-.08, -.1, -.45)))),
        (22, st(**kneel)),
        (34, st(root={'loc': (0, .32, 0), 'rot': (-1.3, 0, .05)}, **fall)),
        (40, st(root={'loc': (0, .36, 0), 'rot': (-1.55, 0, .05)}, **fall)),
        (60, st(root={'loc': (0, .36, 0), 'rot': (-1.52, 0, .05)}, **fall))]))
    rig.animation_data.action = A[0]
    return A

# ── Build ───────────────────────────────────────────────────────────────────
def trunk_only(ob, keep=('hips', 'spine', 'chest', 'neck')):
    """Hang a skinned garment from the trunk alone, so a swinging arm or leg cannot
    pull strips out of it: weights to other bones are dropped and the rest renormalized."""
    vg = {g.index: g for g in ob.vertex_groups}
    chest = ob.vertex_groups.get('chest') or ob.vertex_groups.new(name='chest')
    for v in ob.data.vertices:
        ws = {g.group: g.weight for g in v.groups}
        tot = sum(w for gi, w in ws.items() if vg[gi].name in keep)
        for gi in ws:
            if vg[gi].name not in keep: vg[gi].remove([v.index])
        if tot < 1e-4: chest.add([v.index], 1.0, 'REPLACE')
        else:
            for gi, w in ws.items():
                if vg[gi].name in keep: vg[gi].add([v.index], w / tot, 'REPLACE')

def copy_weights(src, dst):
    for g in src.vertex_groups: dst.vertex_groups.new(name=g.name)
    for v in src.data.vertices:
        for ge in v.groups: dst.vertex_groups[src.vertex_groups[ge.group].name].add([v.index], ge.weight, 'REPLACE')

def build():
    body, J = H.build_body()
    define(body, J); body.name = 'L1_Body'; bodies = {1: body}
    for lv in (2, 3):
        b = link(body.copy()); b.data = body.data.copy(); b.name = f'L{lv}_Body'; bodies[lv] = b
    clench(bodies[1], J, 'lr', **FIST); clench(bodies[3], J, 'lr', **FIST)
    clench(bodies[2], J, 'l', **FIST); clench(bodies[2], J, 'r', **GRIP)   # Talos holds his boulder
    items = kit(bodies, J)
    rings = seam_rings(J)
    for lv, b in bodies.items(): items[b.name] = (b, m_cast(f'Bronze{lv}', lv, rings), 'body')
    ck = mantle('L3_Cloak', body, J)
    items['L3_Cloak'] = (ck, m_cast('HammeredBronze', 3, res=1024, hammer=.35), 'skin')
    H.bake_textures(items)
    rig = H.build_armature(H.skeleton_spec(J), J); rig.name = 'TalosRig'; rig.data.name = 'TalosRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for lv in (2, 3):
        b = bodies[lv]; copy_weights(body, b)
        mw = b.matrix_world.copy(); b.parent = rig; b.matrix_world = mw
        m = b.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    for name, (ob, mt, bind) in items.items():
        if ob.name.endswith('_Body'): continue
        if bind == 'skin':
            H.bind_skin(ob, rig, body)
            if 'Cloak' in name: trunk_only(ob)
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    return rig, actions(rig, J)

def renders(rig):
    """A lineup of the three at their heights, and each one close."""
    from PIL import Image
    shots = []
    for lv in (1, 2, 3):
        k = HEIGHTS[lv] / H.HEIGHT; rig.scale = (k, k, k)
        p = os.path.join(OUT, f'talos_L{lv}.png')
        H.render(rig, p, 'Idle', 1, lv, cam=((3.6, -6.4, 2.6), (84, 0, 29)), res=(520, 800), samples=24); shots.append(p)
        f = HEIGHTS[lv] / HEIGHTS[3]
        H.render(rig, os.path.join(OUT, f'talos_L{lv}_close.png'), 'Idle', 1, lv,
                 cam=((2.2 * f * 1.5, -3.9 * f * 1.5, 1.55 * f * 1.6), (82, 0, 29)), res=(520, 760), samples=32)
    ims = [Image.open(p) for p in shots]
    row = Image.new('RGB', (sum(i.width for i in ims), ims[0].height))
    x = 0
    for i in ims: row.paste(i, (x, 0)); x += i.width
    row.save(os.path.join(OUT, 'talos_lineup.png'))
    rig.scale = (SCALE,) * 3

if __name__ == '__main__':
    rig, acts = build()
    rig.scale = (SCALE,) * 3; H._upd()
    H.export(rig, os.path.join(OUT, 'talos.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'talos.blend'))
    if '--renders' in sys.argv: renders(rig)
    print('built', [a.name for a in acts])
