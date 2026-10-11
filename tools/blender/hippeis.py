"""Realistic Hippeis line (cavalry), built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/hippeis.py third_party/makehuman assets/models

The horse comes from horse.py; the rider is the MakeHuman man of the infantry lines,
seated without stirrups. One armature holds both: the rider's root bone hangs from
the horse's saddle bone, so he rides every gait. Kit follows the reference sheets:
  L1 Prodromoi  Macedonian scout c. 334 BC: bronze Boeotian helmet, madder chiton with a
                cord belt, blue chlamys over the left shoulder, open-toed endromides, two
                cornel-wood javelins (one to throw, one kept for close fighting)
Node tags: L123_ is the rider (every tier), L1_ the Prodromos' kit; the horse and its
tack are untagged, so a page can show the horse alone (level 0), when L0_Reins lie over
its withers instead of running to the rider's fist. The javelin in the right hand is
the node 'ThrowJavelin', hidden by the game while its copy flies.
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
    for tag, bind in (('ThrowJavelin', 'later:hand.R'), ('L1_Spare0', 'later:spare0')):
        for ob, mt in javelin(tag, (ash, iron, thong)):
            ob.scale = (ob.scale.x, ob.scale.y, ob.scale.z * 1.2); add(ob, mt, bind)
    return hair


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
    """Two sets of reins. L123_Reins run from the bit rings along the sides of the neck to
    the rider's left fist; L0_Reins, for the horse shown alone, lie over the withers."""
    bvh = BVHTree.FromObject(horse_body, bpy.context.evaluated_depsgraph_get())
    rc = ring_centres(); back = V((0, .02, .004))   # the reins buckle to the back of the rings
    held = [rein_path(bvh, rc[k] + back, grip + V((sx * .012, 0, 0)), sx) for k, sx in (('L', 1), ('R', -1))]
    top = bvh.ray_cast(V((0, -.37, 3)), V((0, 0, -1)), 5)[0] + V((0, 0, .012))
    lying = [rein_path(bvh, rc[k] + back, top + V((sx * .01, 0, 0)), sx, 30, .05) for k, sx in (('L', 1), ('R', -1))]
    lying = lying[0] + lying[1][::-1]
    drop = bvh.ray_cast(grip, V((0, 0, -1)), 2)[0] + V((0, 0, .02))   # where the hand end falls when he lets go
    return (curve_mesh('L123_Reins', [[tuple(p) for p in L] for L in held], .0045, res=1), held,
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
            'ik_foot.L': {'loc': foot('l', (.3, -.17, .8))}, 'ik_foot.R': {'loc': foot('r', (-.3, -.17, .8))}, 'knee': (.8, -1, 0),
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
    """In the idle pose: the throwing javelin through the right fist, the spare upright
    through the left with the reins."""
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
        else:
            ob.matrix_world = Ml @ Matrix.Translation((0, 0, .5)) @ ob.matrix_basis; bpy.context.view_layer.update(); H.bind_rigid(ob, rig, 'hand.L')   # held low on the shaft
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
    # tags: the rider is L123_ unless his kit is already tagged; the horse stays untagged
    for name, (ob, mt, bind) in list(items.items()):
        if not re.match(r'^L\d+_', ob.name): ob.name = 'L123_' + ob.name
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
