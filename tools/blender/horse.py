"""A small ancient Greek horse for the cavalry lines, built in Blender.

About 13.5 hands (1.37 m at the withers), stocky, bay with black points, a cropped
upright mane, unshod hooves, a simple bridle with a bronze bit and a sheepskin saddle
cloth held by a girth: no saddle, no stirrups. Proportions follow the reference sheets.

The body is a union of ellipsoids laid along hand-placed lines (barrel, neck, head,
legs, tail dock) and masses (shoulders, haunches, chest), fused by a voxel remesh and
smoothed. Bones are named h_*, so a rider's skeleton can share the armature; `hpose`
places the legs by their hoof targets (a two-bone solve for the upper leg, the cannon
and pastern set by angle), and `gait` makes walk and gallop cycles from leg phases.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
import hoplite as H
import peltast as P
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, Mat, m_leather, m_bronze
from peltast import curve_mesh, ribbon, Surf, m_fur


# ── Shape: (x, y, z, half-width, half-height across the line) ───────────────
# The horse faces -Y like the riders; z is up, the ground at z = 0.
BARREL = [(0, -.70, 1.00, .12, .15), (0, -.64, 1.01, .18, .22), (0, -.55, 1.03, .22, .29), (0, -.42, 1.04, .25, .32),
          (0, -.25, 1.025, .27, .31), (0, -.05, 1.02, .28, .305), (0, .15, 1.035, .275, .295), (0, .32, 1.06, .255, .285),
          (0, .48, 1.085, .23, .27), (0, .60, 1.10, .2, .235), (0, .69, 1.11, .16, .185), (0, .74, 1.12, .1, .115)]
NECK = [(0, -.50, 1.17, .2, .27), (0, -.62, 1.29, .17, .23), (0, -.72, 1.41, .145, .19), (0, -.81, 1.51, .12, .155),
        (0, -.89, 1.60, .1, .125), (0, -.95, 1.67, .092, .108)]
HEAD = [(0, -.96, 1.67, .1, .105), (0, -1.02, 1.59, .115, .13), (0, -1.09, 1.51, .108, .125), (0, -1.16, 1.42, .092, .102),
        (0, -1.23, 1.34, .078, .088), (0, -1.30, 1.26, .07, .078), (0, -1.36, 1.20, .067, .073), (0, -1.40, 1.15, .06, .063)]
FRONT = [(.13, -.56, .98, .09, .115), (.145, -.52, .86, .085, .105), (.147, -.50, .74, .075, .09), (.146, -.495, .60, .057, .066),
         (.145, -.493, .50, .05, .055), (.145, -.493, .45, .054, .058), (.144, -.493, .40, .043, .047), (.143, -.493, .30, .035, .039),
         (.143, -.493, .20, .035, .038), (.143, -.496, .155, .043, .047), (.143, -.51, .11, .036, .038), (.143, -.525, .075, .043, .047)]
HIND = [(.13, .40, 1.00, .13, .18), (.15, .32, .86, .095, .125), (.15, .38, .72, .075, .1), (.15, .50, .58, .056, .074),
        (.15, .585, .50, .048, .068), (.15, .583, .42, .041, .049), (.15, .58, .32, .036, .043), (.15, .58, .22, .036, .041),
        (.15, .58, .155, .043, .048), (.15, .565, .11, .036, .039), (.15, .55, .075, .043, .047)]
DOCK = [(0, .72, 1.25, .045, .05), (0, .77, 1.17, .042, .046), (0, .80, 1.06, .036, .04), (0, .805, .97, .03, .034)]
# Masses: centre, radii (across, along, height) and the along direction (y, z)
MASSES = [((.125, -.47, 1.12), (.075, .18, .11), (-.45, -1)),    # shoulder blades
          ((0, -.37, 1.30), (.075, .14, .07), (1, 0)),          # withers
          ((.1, .42, 1.16), (.12, .22, .15), (1, -.15)),        # haunches
          ((.11, .52, .98), (.1, .15, .18), (1, -1.2)),         # hamstrings, buttock to gaskin
          ((.09, -.63, .93), (.1, .1, .15), (0, 1)),            # chest
          ((.055, -1.01, 1.53), (.07, .115, .1), (-.75, -1)),   # jowls
          ((0, -.95, 1.52), (.075, .09, .08), (-.6, -1)),       # throat
          ((0, -1.38, 1.15), (.07, .07, .065), (-1, -1)),       # muzzle
          ((.15, .63, .50), (.025, .03, .035), (0, 1))]         # point of hock
HOOF_Y = {'F': -.535, 'H': .545}
WITHERS = 1.37

# Bones: name, head, tail, parent, deform. Leg bones run joint to joint.
def bones():
    B = [('h_root', (0, 0, 0), (0, -.4, 0), None, False),
         ('h_body', (0, .12, 1.04), (0, -.28, 1.04), 'h_root', True),
         ('h_pelvis', (0, .12, 1.06), (0, .72, 1.12), 'h_body', True),
         ('h_chest', (0, -.28, 1.06), (0, -.55, 1.16), 'h_body', True),
         ('h_saddle', (0, -.1, 1.36), (0, .1, 1.36), 'h_body', False),
         ('h_neck1', (0, -.52, 1.2), (0, -.74, 1.42), 'h_chest', True),
         ('h_neck2', (0, -.74, 1.42), (0, -.95, 1.64), 'h_neck1', True),
         ('h_head', (0, -.95, 1.64), (0, -1.36, 1.18), 'h_neck2', True),
         ('h_tail1', (0, .74, 1.24), (0, .80, 1.07), 'h_pelvis', True),
         ('h_tail2', (0, .80, 1.07), (0, .82, .88), 'h_tail1', True),
         ('h_tail3', (0, .82, .88), (0, .82, .68), 'h_tail2', True),
         ('h_tail4', (0, .82, .68), (0, .80, .48), 'h_tail3', True)]
    for s, n in ((1, 'L'), (-1, 'R')):
        x = lambda v: v * s
        B += [(f'h_scap.{n}', (x(.12), -.40, 1.24), (x(.135), -.58, 1.0), 'h_chest', True),
              (f'h_humerus.{n}', (x(.135), -.58, 1.0), (x(.145), -.50, .80), f'h_scap.{n}', True),
              (f'h_radius.{n}', (x(.145), -.50, .80), (x(.145), -.493, .45), f'h_humerus.{n}', True),
              (f'h_cannonF.{n}', (x(.145), -.493, .45), (x(.143), -.494, .155), f'h_radius.{n}', True),
              (f'h_pasternF.{n}', (x(.143), -.494, .155), (x(.143), -.53, .035), f'h_cannonF.{n}', True),
              (f'h_femur.{n}', (x(.14), .45, 1.02), (x(.15), .31, .84), 'h_pelvis', True),
              (f'h_tibia.{n}', (x(.15), .31, .84), (x(.15), .59, .49), f'h_femur.{n}', True),
              (f'h_cannonH.{n}', (x(.15), .59, .49), (x(.15), .58, .155), f'h_tibia.{n}', True),
              (f'h_pasternH.{n}', (x(.15), .58, .155), (x(.15), .548, .035), f'h_cannonH.{n}', True)]
    return B

BONE_NAMES = [b[0] for b in bones()]
LEGS = {  # leg: (upper, lower, cannon, pastern, which way the middle joint bends)
    'LF': ('h_humerus.L', 'h_radius.L', 'h_cannonF.L', 'h_pasternF.L', V((0, 1, 0))),
    'RF': ('h_humerus.R', 'h_radius.R', 'h_cannonF.R', 'h_pasternF.R', V((0, 1, 0))),
    'LH': ('h_femur.L', 'h_tibia.L', 'h_cannonH.L', 'h_pasternH.L', V((0, -1, 0))),
    'RH': ('h_femur.R', 'h_tibia.R', 'h_cannonH.R', 'h_pasternH.R', V((0, -1, 0))),
}


# ── Mesh ────────────────────────────────────────────────────────────────────
def _frame(d):
    """An orthonormal frame with Y along d and X as close to the world's X as allowed."""
    y = d.normalized(); x = V((1, 0, 0)); x = (x - y * x.dot(y))
    x = x.normalized() if x.length > 1e-6 else V((0, 0, 1)).cross(y).normalized()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()

def _ellipsoid(bm, c, rx, ry, rz, R):
    M = Matrix.Translation(c) @ R.to_4x4() @ Matrix.Diagonal((rx, ry, rz, 1))
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1, matrix=M)

def _chain(bm, pts, step=.012, mirror=False):
    """Ellipsoids laid densely along a line through pts (x, y, z, half-width, half-height)."""
    for sx in ((1, -1) if mirror else (1,)):
        P_ = [(V((x * sx, y, z)), rw, rh) for x, y, z, rw, rh in pts]
        for (a, wa, ha), (b, wb, hb) in zip(P_, P_[1:]):
            d = b - a; n = max(1, int(d.length / step))
            R = _frame(d)
            for i in range(n + (1 if (b, wb, hb) == P_[-1] else 0)):
                t = i / n; c = a.lerp(b, t); rw = wa + (wb - wa) * t; rh = ha + (hb - ha) * t
                _ellipsoid(bm, c, rw, max(rw, rh) * .9, rh, R)

def build_body(name='Horse'):
    bm = bmesh.new()
    _chain(bm, BARREL); _chain(bm, NECK); _chain(bm, HEAD); _chain(bm, DOCK)
    _chain(bm, FRONT, mirror=True); _chain(bm, HIND, mirror=True)
    for c, (rx, ry, rz), (dy, dz) in MASSES:
        for sx in ((1, -1) if c[0] else (1,)):
            _ellipsoid(bm, V((c[0] * sx, c[1], c[2])), rx, ry, rz, _frame(V((0, dy, dz))))
    ob = obj_from_bm(name, bm)
    mod(ob, 'REMESH', mode='VOXEL', voxel_size=.0075); bake_mods(ob)
    mod(ob, 'LAPLACIANSMOOTH', iterations=14, lambda_factor=.8, use_volume_preserve=True, use_normalized=True); bake_mods(ob)
    mod(ob, 'DECIMATE', ratio=.15); bake_mods(ob)
    ob.data.validate(clean_customdata=False)
    for p in ob.data.polygons: p.use_smooth = True
    return ob


# ── Materials ───────────────────────────────────────────────────────────────
def m_coat(name='Coat', base='#5c3b22', belly='#76553a', points='#1e1713', res=1024):
    """Bay: red-brown body, paler belly, black legs below knee and hock, dark muzzle."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    def mr(src, a, b):   # 0 at a, 1 at b, smooth
        n = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP'); m.L.new(src, n.inputs['Value'])
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b; return n.outputs['Result']
    body = m.ramp(m.noise(7, 4, .55).outputs['Fac'], [(.3, tuple(x * .82 for x in srgb(base))), (.7, srgb(base))])
    col = m.mix(body.outputs['Color'], srgb(belly), mr(sep.outputs['Z'], 1.0, .78))       # paler underneath
    legs = mr(sep.outputs['Z'], .56, .44)                                                  # black points
    muzzle = mr(sep.outputs['Y'], -1.31, -1.39)
    dark = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(legs, dark.inputs[0]); m.L.new(muzzle, dark.inputs[1])
    col = m.mix(col, srgb(points), dark.outputs[0])
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=260.0, Distortion=3.0, Detail=2.0)
    m.L.new(m.coord.outputs['Object'], hair.inputs['Vector'])
    rough = m.ramp(m.noise(40, 3).outputs['Fac'], [(.3, (.64, .64, .64)), (.7, (.78, .78, .78))])   # a short coat's soft sheen, not a gloss
    m.set(col, rough.outputs['Color'], hair.outputs['Fac'], .12, .001)
    return m

def m_flat(name, hexcol, rough=.5, metal=0.0): return H.m_flat(name, hexcol, rough, metal)


# ── Head and hair ───────────────────────────────────────────────────────────
HEAD_AXIS = (V((0, -.96, 1.72)), V((0, -1.44, 1.12)))   # poll top to muzzle tip

def head_loop(bvh, s, a0=0.0, a1=2 * math.pi, n=24, off=.004):
    """Points round the head at fraction s from poll to muzzle, between angles a0..a1
    (0 = the horse's left side, pi/2 = the top), laid on the skin."""
    p0, p1 = HEAD_AXIS; u = (p1 - p0).normalized(); c = p0.lerp(p1, s)
    nrm = V((1, 0, 0)).cross(u).normalized()
    if nrm.z < 0: nrm = -nrm
    pts = []
    for i in range(n):
        a = a0 + (a1 - a0) * i / max(1, n - 1); d = (V((1, 0, 0)) * math.cos(a) + nrm * math.sin(a)).normalized()
        h = bvh.ray_cast(c + d * .4, -d, .5)
        if h[0]: pts.append(h[0] + h[1] * off)
    return pts

def strands(name, roots, length, droop, spread, seed, radius=.004, n=7, taper=.6):
    rnd = random.Random(seed); lines = []
    for base, d in roots:
        ln = length * rnd.uniform(.85, 1.1); p = base.copy(); pts = [tuple(p)]
        dd = (d + V((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), 0))).normalized()
        for k in range(n):
            dd = (dd + V((0, 0, -droop * (k + 1) / n))).normalized()
            p = p + dd * ln / n; pts.append(tuple(p))
        lines.append(pts)
    return curve_mesh(name, lines, radius, radii=lambda t: 1 - taper * t, res=0)

def build_horse(add):
    """The horse and its tack. add(ob, material, bind) as in the unit builds;
    bind is 'horse' (skin to the horse body), a bone name, or 'tail'."""
    body = build_body()
    add(body, m_coat(), 'body')
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(body, dg)
    dark_hair = m_flat('HorseHair', '#1d1612', .55)
    # eyes on the sides of the head, ears at the poll
    for sx, n in ((1, 'L'), (-1, 'R')):
        h = bvh.ray_cast(V((sx * .5, -1.075, 1.565)), V((-sx, 0, 0)), 1)
        if h[0]:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=.021, segments=20, ring_count=12, location=h[0] - h[1] * .006)
            e = bpy.context.object; e.name = f'HorseEye{n}'; add(e, m_flat('HorseEye', '#0e0a08', .12), 'h_head')
        ear = lathe(f'HorseEar{n}', [(.0, 0), (.03, .015), (.033, .055), (.022, .095), (.006, .125), (0, .13)], 16)
        ear.scale = (1, .5, 1)
        h = bvh.ray_cast(V((sx * .048, -.965, 2.2)), V((0, 0, -1)), 1)
        base = (h[0] - V((0, 0, .02))) if h[0] else V((sx * .048, -.965, 1.72))
        ear.rotation_euler = (math.radians(-12), math.radians(sx * 14), math.radians(sx * -12)); ear.location = base
        P.bake_obj_xform(ear); add(ear, m_coat('EarCoat', '#4f3320', '#4f3320', '#241a14', 256), 'h_head')
    # hooves: unshod, a little flared at the ground
    hoof_m = m_flat('Hoof', '#2b2622', .6)
    for key, x in (('F', .143), ('H', .15)):
        for sx, n in ((1, 'L'), (-1, 'R')):
            hf = lathe(f'Hoof{key}{n}', [(0, 0), (.056, 0), (.054, .03), (.046, .075), (0, .075)], 24)
            hf.location = (sx * x, HOOF_Y[key], 0); P.bake_obj_xform(hf)
            add(hf, hoof_m, f'h_pastern{key}.{n}')
    # the cropped mane stands upright along the crest; a short forelock between the ears
    roots = []
    for i in range(80):
        t = i / 79; y = -.94 + (-.40 + .94) * t
        h = bvh.ray_cast(V((0, y, 2.4)), V((0, 0, -1)), 2)
        if not h[0] or h[0].z < 1.2: continue
        for sx in (-1, 0, 1):
            roots.append((h[0] + V((sx * .009, 0, -.006)), (h[1] * .6 + V((0, .15 * t - .1, .6))).normalized()))
    mane = strands('HorseMane', roots, .09, .0, .08, 3, .0055, 5, .4)
    add(mane, dark_hair, 'horse')
    fl = [(V((sx * .012, -.985, 1.75)), V((0, -.5, .9))) for sx in (-1, -.5, 0, .5, 1)]
    add(strands('HorseForelock', fl, .07, .15, .15, 4, .004, 5), dark_hair, 'h_head')
    # the tail: long and full, falling from the dock nearly to the hocks' height
    roots = []
    for i in range(36):
        t = i / 35; z = 1.16 - .2 * t
        h = bvh.ray_cast(V((0, 1.5, z)), V((0, -1, 0)), 1)
        if not h[0]: continue
        for k in range(3):
            roots.append((h[0] + V(((k - 1) * .012, -.008, 0)), V(((k - 1) * .25, .55, -.2)).normalized()))
    tail = strands('HorseTail', roots, .62, .9, .12, 5, .0055, 9, .5)
    add(tail, dark_hair, 'tail')

    # the sheepskin saddle cloth, draped over the back, and a girth over it
    bm = bmesh.new(); nx, ny = 26, 22
    g = [[bm.verts.new(((i / nx - .5) * 1.0, -.1 + (j / ny - .5) * .72, 1.52)) for i in range(nx + 1)] for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx): bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
    cloth = obj_from_bm('SaddleCloth', bm)
    H.drape('SaddleCloth', cloth, lambda c: False, body, 110, .35, .012)
    add(cloth, m_fur('Sheepskin', '#6b5741', '#a58f72'), 'horse-trunk')
    sf = Surf([body, cloth]); pts = []
    for i in range(41):
        a = i / 40 * 2 * math.pi; d = V((math.cos(a), 0, math.sin(a))); o = V((0, -.33, 1.03))
        h = sf.hit(o, d, .8)
        if h: pts.append((h[0] + h[1] * .005, h[1]))
    add(ribbon('Girth', pts, .045, .004), m_leather('GirthLeather', '#4a3020', 256), 'horse-trunk')

    # the bridle: crownpiece and throatlatch, browband, noseband, cheekpieces, bronze bit rings
    strap = m_leather('Bridle', '#3e2818', 256); bronze = m_bronze('BitBronze', .2, 256)
    lines = [head_loop(bvh, .04, 0, 2 * math.pi, 28), head_loop(bvh, .14, .35, math.pi - .35, 12), head_loop(bvh, .63, 0, 2 * math.pi, 28)]
    lines[0].append(lines[0][0]); lines[2].append(lines[2][0])
    for a in (0, math.pi):   # cheekpieces, dropping toward the mouth corners
        side = -1 if a == 0 else 1; pts = []
        for k in range(12):
            s = .04 + (.88 - .04) * k / 11; aa = a + side * .35 * max(0, s - .6) / .28
            p = head_loop(bvh, s, aa, aa, 1)
            if p: pts.append(p[0])
        if len(pts) > 2: lines.append(pts)
    add(curve_mesh('Bridle', [[tuple(p) for p in L] for L in lines if len(L) > 1], .0045, res=1), strap, 'h_head')
    rings = []
    for a in (0, math.pi):
        p = head_loop(bvh, .9, a + (-.35 if a == 0 else .35), a + (-.35 if a == 0 else .35), 1, .008)
        if not p: continue
        r = lathe('BitRing', [(.019, -.004), (.024, 0), (.019, .004)], 20)
        r.rotation_euler = (0, math.pi / 2, 0); r.location = p[0]; P.bake_obj_xform(r)
        rings.append(r); add(r, bronze, 'h_head')
    for i, r in enumerate(rings): r.name = f'BitRing{"LR"[i]}'
    return body, bvh


# ── Posing ──────────────────────────────────────────────────────────────────
def rest_hoof(rig, leg):
    b = rig.data.bones[LEGS[leg][3]]; return b.tail_local.copy()

def rest_angles(rig, leg):
    """The cannon's and pastern's rest angles from vertical (cannon + = hoof behind, pastern + = toe forward)."""
    c, p = (rig.data.bones[n] for n in LEGS[leg][2:4])
    dc, dp = c.tail_local - c.head_local, p.tail_local - p.head_local
    return math.atan2(dc.y, -dc.z), math.atan2(-dp.y, -dp.z)

def hpose(rig, HP):
    """Pose the horse. HP: body {'loc', 'rot', 'pivot'}, chest/neck1/neck2/head/tail1..4 {'rot'},
    legs {leg: {'off': hoof offset from rest (in the ground frame, or the body frame with
    'body': True), 'cannon': angle from vertical (+ = hoof behind), 'pastern': angle (+ = toe forward)}}."""
    PB = rig.pose.bones
    for n in BONE_NAMES:
        PB[n].rotation_quaternion = (1, 0, 0, 0); PB[n].location = (0, 0, 0)
    b = HP.get('body', {})
    rot = Euler(b.get('rot', (0, 0, 0))).to_matrix()
    pivot = V(b.get('pivot', rig.data.bones['h_body'].head_local))
    head0 = rig.data.bones['h_body'].head_local
    shift = pivot + rot @ (head0 - pivot) - head0     # rotate about the pivot rather than the bone's head
    PB['h_body'].location = rig.data.bones['h_body'].matrix_local.to_3x3().inverted() @ (V(b.get('loc', (0, 0, 0))) + shift)
    PB['h_body'].rotation_quaternion = (rig.data.bones['h_body'].matrix_local.to_3x3().inverted() @ rot @ rig.data.bones['h_body'].matrix_local.to_3x3()).to_quaternion()
    for n in ('h_pelvis', 'h_chest', 'h_neck1', 'h_neck2', 'h_head', 'h_tail1', 'h_tail2', 'h_tail3', 'h_tail4'):
        if n in HP: PB[n].rotation_quaternion = Euler(HP[n].get('rot', (0, 0, 0))).to_quaternion()
    H._upd()
    body_m = PB['h_body'].matrix @ rig.data.bones['h_body'].matrix_local.inverted()
    for leg, (b1, b2, b3, b4, bend) in LEGS.items():
        spec = HP.get('legs', {}).get(leg, {})
        off = V(spec.get('off', (0, 0, 0)))
        T = rest_hoof(rig, leg) + off
        if spec.get('body'): T = body_m @ T
        ac0, ap0 = rest_angles(rig, leg)
        ac, ap = spec.get('cannon', ac0), spec.get('pastern', ap0)
        l1, l2, l3, l4 = (rig.data.bones[n].length for n in (b1, b2, b3, b4))
        dirp = V((0, -math.sin(ap), -math.cos(ap))); dirc = V((0, math.sin(ac), -math.cos(ac)))
        if spec.get('body'): dirp = body_m.to_3x3() @ dirp; dirc = body_m.to_3x3() @ dirc
        P3 = T - dirp * l4; P2 = P3 - dirc * l3
        S = PB[b1].head.copy()
        E = H.two_bone(S, P2, l1, l2, body_m.to_3x3() @ bend)
        H.swing(rig, b1, E - S); H.swing(rig, b2, P2 - PB[b2].head)
        H.swing(rig, b3, P3 - PB[b3].head); H.swing(rig, b4, T - PB[b4].head)

def leg_cycle(phase, stance, stride, lift, front, ac0, ap0):
    """Hoof offset and joint angles for one leg at a point in its cycle: on the ground
    sliding back during the stance, folded and swung forward in the air after it."""
    if phase < stance:
        t = phase / stance
        return {'off': (0, -stride / 2 + stride * t, 0), 'cannon': ac0 - .12 + .32 * t, 'pastern': ap0 + .25 * math.sin(math.pi * t)}
    u = (phase - stance) / (1 - stance); e = .5 - .5 * math.cos(math.pi * u)
    fold = math.sin(math.pi * min(1, u * 1.15))
    if front: ac, ap = ac0 + .2 + 1.35 * fold - .32 * u, ap0 - 1.9 * fold
    else: ac, ap = ac0 + .2 - .6 * fold - .32 * u, ap0 - 1.0 * fold
    return {'off': (0, stride / 2 - stride * e, lift * math.sin(math.pi * u)), 'cannon': ac, 'pastern': ap}

GAITS = {   # frames per cycle, leg phases, stance fraction, stride, hoof lift (front, hind), body bob, pitch
    'walk':   dict(frames=28, phase={'LH': 0, 'LF': .25, 'RH': .5, 'RF': .75}, stance=.64, stride=.62, lift=(.16, .1), bob=.012, pitch=.015),
    'gallop': dict(frames=16, phase={'LH': 0, 'RH': .12, 'LF': .42, 'RF': .54}, stance=.32, stride=1.05, lift=(.38, .24), bob=.05, pitch=.08),
}

def gait(rig, name, f, extra=None):
    """The horse's pose at frame f of a gait cycle."""
    G = GAITS[name]; c = (f % G['frames']) / G['frames']
    legs = {}
    for k, p in G['phase'].items():
        front = k[1] == 'F'; ac0, ap0 = rest_angles(rig, k)
        legs[k] = leg_cycle((c - p) % 1, G['stance'], G['stride'], G['lift'][0 if front else 1], front, ac0, ap0)
    w = 2 * math.pi * c * (2 if name == 'walk' else 1)
    HP = {'body': {'loc': (0, 0, G['bob'] * math.sin(w)), 'rot': (G['pitch'] * math.sin(w + .8), 0, 0)},
          'h_neck1': {'rot': (-G['pitch'] * 1.2 * math.sin(w + .4), 0, 0)}, 'h_head': {'rot': (G['pitch'] * .6 * math.sin(w), 0, 0)},
          'h_tail2': {'rot': (.15 * math.sin(w) * (2 if name == 'gallop' else 1), 0, 0)}, 'legs': legs}
    if name == 'gallop': HP['h_tail1'] = {'rot': (-.5, 0, 0)}
    for k, v in (extra or {}).items(): HP[k] = v
    return HP


def build_rig(name='HorseRig', B=None):
    """An armature from a bone list (name, head, tail, parent, deform)."""
    arm = bpy.data.armatures.new(name); ob = link(bpy.data.objects.new(name, arm))
    H.activate(ob); bpy.ops.object.mode_set(mode='EDIT')
    for n, h, t, parent, deform in (B or bones()):
        b = arm.edit_bones.new(n); b.head = h; b.tail = t; b.roll = 0; b.use_deform = deform
        if parent: b.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones: pb.rotation_mode = 'QUATERNION'
    return ob

def weight_to_chain(ob, rig, names):
    """Skin a strand mesh (the tail) along a chain of bones: each vertex goes to the
    nearest two bones, weighted by distance, so the hair bends with the dock."""
    segs = [(n, rig.data.bones[n].head_local, rig.data.bones[n].tail_local) for n in names]
    for n in names:
        if n not in ob.vertex_groups: ob.vertex_groups.new(name=n)
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co; ds = []
        for n, a, b in segs:
            u = b - a; t = max(0.0, min(1.0, (p - a).dot(u) / u.length_squared)); ds.append(((p - (a + u * t)).length, n))
        ds.sort(); (d1, n1), (d2, n2) = ds[0], ds[1]
        w1 = (d2 + 1e-4) / (d1 + d2 + 2e-4)
        ob.vertex_groups[n1].add([v.index], w1, 'REPLACE'); ob.vertex_groups[n2].add([v.index], 1 - w1, 'REPLACE')
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig

TAIL_BONES = ['h_tail1', 'h_tail2', 'h_tail3', 'h_tail4']

LEG_BONE = ('scap', 'humerus', 'radius', 'cannon', 'pastern', 'femur', 'tibia')

def trunk_only(ob):
    """Drop leg-bone weights from tack skinned to the horse (girth, saddle cloth), so it
    rides on the trunk instead of following a leg that passes near it."""
    legs = [g for g in ob.vertex_groups if any(k in g.name for k in LEG_BONE)]
    keep = [g for g in ob.vertex_groups if g not in legs]
    body = ob.vertex_groups.get('h_body') or ob.vertex_groups.new(name='h_body')
    for v in ob.data.vertices:
        ws = {g.group: g.weight for g in v.groups}
        tot = sum(w for gi, w in ws.items() if ob.vertex_groups[gi] in keep)
        for g in legs: g.remove([v.index])
        if tot < 1e-4: body.add([v.index], 1.0, 'REPLACE')
        else:
            for gi, w in ws.items():
                if ob.vertex_groups[gi] in keep: ob.vertex_groups[gi].add([v.index], w / tot, 'REPLACE')
