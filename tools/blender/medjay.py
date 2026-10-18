"""Realistic Medjay line (Kemet), built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/medjay.py third_party/makehuman assets/models [--renders]

The Medjay were the desert scouts and police of New Kingdom Egypt, c. 1300 BC. Built on
the infantry pipeline (hoplite.py, peltast.py): the MakeHuman man at 1.75 m, lean and
athletic (his muscles deepened as for Talos), olive-brown, his hair cropped short with a
single ostrich feather at the crown; his fists are bent into the mesh as for Talos, the
right one round the spear shaft and the left round the shield's grip. Kit follows the
reference sheets in refs/medjay:
  L1 Medjay          bare chest, a bead necklace with an amulet on a cord, a white linen
                     kilt wrapped with a rounded front and a tab, knotted at the back, a
                     tooled leather belt, a bronze dagger at the left hip, a 2 m spear with
                     a bronze leaf blade, a small oval cowhide shield laced with rawhide
  L2 Veteran Medjay  a sleeveless tan leather corselet with a plain yoke and edging, sewn
                     with rows of small bronze plates with rounded lower ends; a khopesh
                     in its sheath at the left hip; a dappled cowhide shield with a rounded
                     top on a wooden frame
  L3 Elite Medjay    a coat of bronze scales to mid-thigh with short sleeves, open at the
                     front below the belt; a broad bead collar, gold armlets and wristlets,
                     a pleated kilt with a beaded triangular apron, the dagger; a 2.2 m
                     spear with a broad blade, gilded socket and bronze butt-spike; a tall
                     cowhide shield with a gilded rim and a sun-disc boss
Every tier: the feather, sandals with ankle straps. The shield is held by its grip in the
left fist, the two larger ones also strapped round the forearm; the spear rides on its
own bone (spear.R) in the right fist, so a clip can slide it through the hand and let it
fall. The kilts and the coat's skirt hang from the hips, taking the thighs' weights only
towards the hem (hang_weights), so they stretch between the legs instead of tearing.
Node tags: L1_, L2_, L3_ for one tier, L12_ for the first two (the plain kilt, its tab,
knot and belt, the necklace and the spear); the body, head kit and sandals are untagged.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
import hamippoi as HM
import talos as T
import minotaur as MT
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat, m_cloth, m_leather, m_wood
from peltast import curve_mesh, ribbon, Surf, ring_on, relax_rim, bake_obj_xform, on_arm

# A lean, athletic man of the desert, olive-skinned: built before the shared modules'
# own settings could apply, so they are set again here.
H.TARGETS = [('caucasian-male-young.target', .86), ('african-male-young.target', .12), ('asian-male-young.target', .02),
             ('universal-male-young-maxmuscle-averageweight.target', .72), ('universal-male-young-averagemuscle-minweight.target', .28)]
H.HEIGHT = 1.75
SC = H.SC
OUT = H.OUT
random.seed(13)


# ── Materials ───────────────────────────────────────────────────────────────
def m_skin(J):
    """Medium olive-brown skin, the eyebrows and a faint shadow of stubble painted in (as
    hoplite.m_skin, in this man's tones, with heavier brows)."""
    eye, mouth, jaw, head = J['l-eye'], J['mouth'], J['jaw'], J['head']
    m = Mat('Skin', res=1024, sss=.1)
    m.bsdf.inputs['Subsurface Radius'].default_value = (.8, .35, .2)
    col = m.ramp(m.noise(9, 5, .55).outputs['Fac'], [(.35, srgb('#5c3e2a')), (.55, srgb('#714d36')), (.75, srgb('#835c40'))])
    red = m.ramp(m.noise(3, 3, .5).outputs['Fac'], [(.5, (0, 0, 0)), (.75, (1, 1, 1))])
    c2 = m.mix(col.outputs['Color'], srgb('#8a4a32'), red.outputs['Color'])
    c2 = m.mix(col.outputs['Color'], c2, .3)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
    arch = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(ax.outputs[0], arch.inputs[0]); arch.inputs[1].default_value = -.1; arch.inputs[2].default_value = eye.z + .023
    dz = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['Z'], dz.inputs[0]); m.L.new(arch.outputs[0], dz.inputs[1])
    adz = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(dz.outputs[0], adz.inputs[0])
    band = m.node('ShaderNodeMapRange', **{'From Min': .0078, 'From Max': .0034}); m.L.new(adz.outputs[0], band.inputs['Value'])
    span = m.node('ShaderNodeMapRange', **{'From Min': .058, 'From Max': .034}); m.L.new(ax.outputs[0], span.inputs['Value'])
    inner = m.node('ShaderNodeMapRange', **{'From Min': .007, 'From Max': .013}); m.L.new(ax.outputs[0], inner.inputs['Value'])
    front = m.node('ShaderNodeMapRange', **{'From Min': eye.y + .022, 'From Max': eye.y + .006}); m.L.new(sep.outputs['Y'], front.inputs['Value'])
    strokes = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=900.0, Distortion=2.0); m.L.new(m.coord.outputs['Object'], strokes.inputs['Vector'])
    mk = band.outputs[0]
    for other in (span.outputs[0], inner.outputs[0], front.outputs[0], strokes.outputs['Fac']):
        mm = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(mk, mm.inputs[0]); m.L.new(other, mm.inputs[1]); mk = mm.outputs[0]
    c2 = m.mix(c2, srgb('#1c120c'), mk)
    def rng(src, a, b):
        n = m.node('ShaderNodeMapRange', **{'From Min': a, 'From Max': b}); m.L.new(src, n.inputs['Value']); return n.outputs[0]
    def mul(a, b):
        n = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(a, n.inputs[0]); m.L.new(b, n.inputs[1]); return n.outputs[0]
    cheek = m.node('ShaderNodeMath', operation='SUBTRACT'); cheek.inputs[0].default_value = 1.0
    m.L.new(mul(rng(sep.outputs['Z'], mouth.z - .012, mouth.z - .002), rng(ax.outputs[0], .026, .036)), cheek.inputs[1])
    beard = mul(mul(rng(sep.outputs['Z'], jaw.z - .05, jaw.z - .028), rng(sep.outputs['Z'], mouth.z + .02, mouth.z + .012)),
                mul(rng(sep.outputs['Y'], head.y + .005, head.y - .025), rng(ax.outputs[0], .08, .062)))
    dots = m.ramp(m.noise(1400, 2, .5).outputs['Fac'], [(.42, (.35, .35, .35)), (.58, (1, 1, 1))])
    beard = mul(mul(beard, cheek.outputs[0]), dots.outputs['Color'])
    fade = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(beard, fade.inputs[0]); fade.inputs[1].default_value = .4
    c2 = m.mix(c2, srgb('#3a2a20'), fade.outputs[0])
    m.set(c2, .5, m.noise(900, 2, .5).outputs['Fac'], .15, .0006)
    return m

def m_crop(name, hexcol, skin='#5e3d29', res=512):
    """Hair cropped to a few millimetres: a dark grain over the scalp, which shows through
    towards the hairline (the shell's 'fade' attribute, 0 at its edge)."""
    m = Mat(name, res=res)
    grain = m.noise(900, 2, .6)
    c = srgb(hexcol)
    col = m.ramp(grain.outputs['Fac'], [(.35, tuple(x * .5 for x in c)), (.65, c)]).outputs['Color']
    at = m.node('ShaderNodeAttribute', attribute_name='fade')
    dots = m.ramp(m.noise(420, 2, .7).outputs['Fac'], [(.3, (0, 0, 0)), (.7, (1, 1, 1))])
    thin = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(dots.outputs['Color'], thin.inputs[0]); thin.inputs[1].default_value = -.6; thin.inputs[2].default_value = .6
    edge = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(at.outputs['Fac'], edge.inputs[0]); m.L.new(thin.outputs[0], edge.inputs[1])
    cover = m.node('ShaderNodeMapRange', **{'From Min': -.3, 'From Max': .55}); m.L.new(edge.outputs[0], cover.inputs['Value'])
    col = m.mix(srgb(skin), col, cover.outputs[0])
    m.set(col, .7, grain.outputs['Fac'], .45, .0008)
    return m

def m_eye(name='Eye', r=.0118, res=512):
    """A dark brown eye on the eyeball (object space, looking to -Y): a large iris with a
    dark limbal ring and pupil, the white toned towards the skin at the corners, and the
    upper lid's shadow over the top of the ball."""
    m = Mat(name, res=res)
    grad = m.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (78, 78, 78); mp.inputs['Location'].default_value = (0, r * 78, 0)   # centred on the front of the eye
    m.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
    col = m.ramp(grad.outputs['Fac'], [(.0, srgb('#7a5a46')), (.22, srgb('#b8a492')), (.4, srgb('#cfc3b3')), (.44, srgb('#170d07')),
                                       (.5, srgb('#2e190c')), (.68, srgb('#43260f')), (.76, srgb('#1a0e06')), (.79, srgb('#040302')), (1.0, srgb('#040302'))]).outputs['Color']
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    lid = m.node('ShaderNodeMapRange', **{'From Min': .0005, 'From Max': .0062}); m.L.new(sep.outputs['Z'], lid.inputs['Value'])
    shade = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(lid.outputs[0], shade.inputs[0]); shade.inputs[1].default_value = .75
    col = m.mix(col, srgb('#2a1c14'), shade.outputs[0])
    m.set(col, .22)
    return m

def m_feather(name='Ostrich', res=256):
    """An ostrich plume: off-white barbs running out from the shaft (bands along the UV's u)."""
    m = Mat(name, res=res)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=60.0, Distortion=1.5, Detail=2.0); m.L.new(m.coord.outputs['UV'], w.inputs['Vector'])
    col = m.ramp(w.outputs['Fac'], [(.15, srgb('#bdb7aa')), (.6, srgb('#ece8de')), (.9, srgb('#f6f3ec'))])
    m.set(col.outputs['Color'], .8, w.outputs['Fac'], .5, .0015)
    return m

def m_cowhide(name, base, patch, scale=3.2, edge=.5, mottle=None, res=1024):
    """Cowhide with the hair on: crisp patches of `patch` on `base`, the hair lying in one
    direction; `mottle` adds a few smaller dapples."""
    m = Mat(name, res=res)
    big = m.ramp(m.noise(scale, 4, .55).outputs['Fac'], [(edge - .015, (0, 0, 0)), (edge + .015, (1, 1, 1))])
    col = m.mix(srgb(base), srgb(patch), big.outputs['Color'])
    if mottle:
        sm = m.ramp(m.noise(scale * 3.2, 3, .6).outputs['Fac'], [(.6, (0, 0, 0)), (.64, (1, 1, 1))])
        col = m.mix(col, srgb(mottle), sm.outputs['Color'])
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (160, 30, 160)
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=1.0, Distortion=7.0, Detail=3.0); m.L.new(mp.outputs['Vector'], hair.inputs['Vector'])
    shade = m.ramp(hair.outputs['Fac'], [(.2, (.82, .82, .82)), (.8, (1, 1, 1))])
    col = m.mix(col, shade.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .85, hair.outputs['Fac'], .35, .0015)
    return m

def m_gold(name='Gold', res=256):
    m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(30, 4, .6).outputs['Fac'], [(.3, srgb('#a07a2c')), (.7, srgb('#d8b158'))])
    m.set(col.outputs['Color'], .26, m.noise(90, 3).outputs['Fac'], .15, .0008)
    return m

def m_plate_bronze(name, cols, rough=.3, res=1024):
    """Bright worked bronze for plates and scales: a polished face, darker towards the
    hammered edges (Pointiness), small dents."""
    m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(7, 5, .55).outputs['Fac'], [(.3, srgb(cols[0])), (.55, srgb(cols[1])), (.8, srgb(cols[2]))]).outputs['Color']
    geo = m.node('ShaderNodeNewGeometry')
    dark = m.ramp(geo.outputs['Pointiness'], [(.46, (1, 1, 1)), (.5, (0, 0, 0))])
    col = m.mix(col, srgb('#2e1f12'), m.mix((0, 0, 0), dark.outputs['Color'], .6))
    fine = m.noise(140, 3, .6)
    rr = m.ramp(fine.outputs['Fac'], [(.3, (rough - .06,) * 3), (.7, (rough + .1,) * 3)])
    m.set(col, rr.outputs['Color'], fine.outputs['Fac'], .2, .001)
    return m

def m_tooled(name, n, base='#6e3a22', line='#c99a5e', deep='#2e1a10', res=512):
    """A belt of tooled leather: a lattice of lozenges between two edge lines, laid along
    the band's UV (u along its length, v across); n lozenges per band."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['UV'], sep.inputs['Vector'])
    def op(kind, a, b=None):
        nd = m.node('ShaderNodeMath', operation=kind)
        for i, x in enumerate((a, b)):
            if x is None: continue
            if hasattr(x, 'links'): m.L.new(x, nd.inputs[i])
            else: nd.inputs[i].default_value = x
        return nd.outputs[0]
    tri = op('MULTIPLY', op('ABSOLUTE', op('SUBTRACT', op('FRACT', op('MULTIPLY', sep.outputs['X'], float(n))), .5)), 2.0)
    v = sep.outputs['Y']
    up = op('LESS_THAN', op('ABSOLUTE', op('SUBTRACT', v, op('ADD', op('MULTIPLY', tri, .6), .2))), .06)
    dn = op('LESS_THAN', op('ABSOLUTE', op('SUBTRACT', v, op('SUBTRACT', .8, op('MULTIPLY', tri, .6)))), .06)
    edges = op('MAXIMUM', op('LESS_THAN', v, .1), op('GREATER_THAN', v, .9))
    lines = op('MAXIMUM', op('MAXIMUM', up, dn), edges)
    dots = op('LESS_THAN', op('ABSOLUTE', op('SUBTRACT', v, .5)), op('MULTIPLY', op('SUBTRACT', .22, op('MULTIPLY', tri, .3)), op('LESS_THAN', tri, .35)))
    col = m.mix(srgb(base), srgb(deep), op('MULTIPLY', op('LESS_THAN', tri, .4), op('LESS_THAN', op('ABSOLUTE', op('SUBTRACT', v, .5)), .12)))
    col = m.mix(col, srgb(line), lines)
    grain = m.ramp(m.noise(260, 3, .6).outputs['Fac'], [(.3, (.8, .8, .8)), (.7, (1, 1, 1))])
    col = m.mix(col, grain.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .6, op('SUBTRACT', 1.0, lines), .4, .001)
    return m

def m_pleated(name, hexcol, pitch=140.0, res=1024):
    """Fine linen pressed in narrow vertical pleats (object space, so they run down the
    body), shaded light and dark along each fold."""
    m = m_cloth(name, hexcol, 700, .04, res)
    cloth_col = m.bsdf.inputs['Base Color'].links[0].from_socket
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=pitch / 6.283, Distortion=.4); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    shade = m.ramp(w.outputs['Fac'], [(.1, (.8, .8, .8)), (.5, (1, 1, 1)), (.9, (.88, .88, .88))])
    col = m.mix(cloth_col, shade.outputs['Color'], 1.0, 'MULTIPLY')
    m.L.new(col, m.bsdf.inputs['Base Color'])
    b = m.node('ShaderNodeBump', Strength=.5, Distance=.003); m.L.new(w.outputs['Fac'], b.inputs['Height']); m.L.new(b.outputs['Normal'], m.bsdf.inputs['Normal'])
    return m

def m_kilt_under(name, hexcol, hem, top, half):
    """The linen of the kilt's under layer, in the overlap's shadow where it shows below
    the rounded front of the outer turn (object space: in front, between the corners)."""
    m = m_cloth(name, hexcol, 700, .04)
    cloth_col = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
    def rng(src, a, b):
        n = m.node('ShaderNodeMapRange', **{'From Min': a, 'From Max': b}); m.L.new(src, n.inputs['Value']); return n.outputs[0]
    def mul(a, b):
        n = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(a, n.inputs[0]); m.L.new(b, n.inputs[1]); return n.outputs[0]
    mask = mul(mul(rng(sep.outputs['Y'], -.04, -.1), rng(ax.outputs[0], half, half - .05)), rng(sep.outputs['Z'], top, hem + .01))
    col = m.mix(cloth_col, srgb('#a8a296'), mul(mask, rng(sep.outputs['Z'], hem - .02, top)))
    m.L.new(col, m.bsdf.inputs['Base Color'])
    return m

def m_image(name, img, rough=.6, metal=0.0, res=1024):
    """A painted or beaded surface from an image (UV), with a little grain."""
    m = Mat(name, metal=metal, res=res)
    t = m.node('ShaderNodeTexImage'); t.image = img; m.L.new(m.coord.outputs['UV'], t.inputs['Vector'])
    m.set(t.outputs['Color'], rough, m.noise(200, 3, .6).outputs['Fac'], .15, .0008)
    return m

def wrap_seam(me, uvl):
    """Faces that straddle the seam of a UV running round the body get their small u
    raised past 1, so the (periodic) pattern runs on across them."""
    for f in me.polygons:
        us = [uvl.data[li].uv[0] for li in f.loop_indices]
        if max(us) - min(us) > .5:
            for li in f.loop_indices:
                if uvl.data[li].uv[0] < .5: uvl.data[li].uv[0] += 1.0

def pil_image(name, im):
    """A PIL image as a packed Blender image."""
    import numpy as np
    from PIL import Image
    img = bpy.data.images.new(name, im.width, im.height)
    a = np.ones((im.height, im.width, 4), np.float32); a[..., :3] = np.asarray(im.convert('RGB').transpose(Image.FLIP_TOP_BOTTOM), np.float32) / 255
    img.pixels.foreach_set(a.ravel()); img.pack()
    return img


# ── Body ────────────────────────────────────────────────────────────────────
def broaden(body, J, wide, deep):
    """Broader shoulders and a deeper chest than the base man (as minotaur.broaden, but
    the neck and head are left as they are and the arms are carried out, not widened)."""
    sx = J['l-shoulder'].x
    def f(p):
        up = MT._ramp(p.z, 1.0, 1.32) * (1 - MT._ramp(p.z, 1.42, 1.52))
        arm = MT._ramp(abs(p.x), sx - .04, sx + .02)
        x = p.x * (1 + wide * up) * (1 - arm) + (p.x + math.copysign(sx * wide * up, p.x)) * arm
        return V((x, p.y * (1 + deep * up * (1 - arm)), p.z))
    for v in body.data.vertices: v.co = f(v.co)
    for j in J: J[j] = f(J[j])
    body.data.update()

def build_body():
    """The MakeHuman man, his muscles deepened a little (T.define), his profile given a
    straighter, stronger nose, and both fists bent closed round a haft (the spear, the
    shield's grip)."""
    body, J = H.build_body()
    broaden(body, J, .07, .06)
    T.define(body, J, .55)
    eye, mouth = J['l-eye'], J['mouth']
    for v in body.data.vertices:   # the bridge of the nose: a few millimetres higher between the eyes
        p = v.co
        if abs(p.x) < .02 and p.y < eye.y - .005 and mouth.z + .02 < p.z < eye.z + .01:
            w = (1 - abs(p.x) / .02) * max(0, min(1, (p.z - mouth.z - .02) / .03)) * max(0, min(1, (eye.z + .01 - p.z) / .015))
            v.co.y -= .0028 * w
        if abs(p.x) < .03 and p.y < eye.y + .0 and mouth.z + .004 < p.z < mouth.z + .04:   # narrower wings of the nose
            w = max(0, min(1, (p.z - mouth.z - .004) / .01)) * max(0, min(1, (mouth.z + .04 - p.z) / .012)) * max(0, min(1, (eye.y - p.y) / .012))
            v.co.x *= 1 - .14 * w
    body.data.update()
    T.clench(body, J, 'lr', **MT.HAFT)
    return body, J


# ── Head: cropped hair, stubble, eyes and the ostrich feather ───────────────
def head_kit(body, J, add):
    head, neck, eye, jaw = J['head'], J['neck'], J['l-eye'], J['jaw']
    # the hairline as a height over the eyes at each bearing round the skull (0 ahead, 180 behind)
    line = [(0, .056), (32, .05), (52, .024), (62, -.022), (76, -.024), (82, .032), (108, .032), (132, -.062), (180, -.068)]
    def hairline(c):
        a = math.degrees(math.atan2(abs(c.x), head.y - c.y))
        for (a0, z0), (a1, z1) in zip(line, line[1:]):
            if a <= a1: return eye.z + z0 + (z1 - z0) * (a - a0) / (a1 - a0)
        return eye.z + line[-1][1]
    def in_hair(c):
        if abs(c.x) > .068 and -.072 < c.y < -.0 and c.z < eye.z + .034: return False   # the ears stay bare
        return c.z > hairline(c)
    hair = region_shell('Hair', body, in_hair, .0034, 0)
    relax_rim(hair, 8)
    mod(hair, 'SUBSURF', levels=1, render_levels=1); bake_mods(hair)
    bm = bmesh.new(); bm.from_mesh(hair.data); bm.normal_update()
    dist = {v: 0.0 for v in bm.verts if v.is_boundary}; front = list(dist)
    while front:   # distance in from the hairline, along the shell
        nxt = []
        for v in front:
            for e in v.link_edges:
                o = e.other_vert(v); d = dist[v] + e.calc_length()
                if d < .02 and d < dist.get(o, 1.0): dist[o] = d; nxt.append(o)
        front = nxt
    fade = [min(1.0, dist.get(v, 1.0) / .014) for v in bm.verts]
    for v, f in zip(bm.verts, fade): v.co -= v.normal * .0028 * (1 - f)   # thinning out to the skin at the hairline
    bm.to_mesh(hair.data); bm.free()
    at = hair.data.attributes.new('fade', 'FLOAT', 'POINT')
    for i, f in enumerate(fade): at.data[i].value = f
    add(hair, m_crop('CroppedHair', '#22170f'), 'head')
    got = {}; eye_m = m_eye()
    P.head_kit(body, J, lambda ob, mt, bind: got.__setitem__(ob.name, (ob, mt)), [], volume=0)
    for n, (ob, mt) in got.items():
        if n.startswith('Eye'): add(ob, eye_m, 'head')
        else: bpy.data.objects.remove(ob)
    # the feather: a quill pushed into the hair at the crown, the plume rising almost upright
    bvh = BVHTree.FromObject(hair, bpy.context.evaluated_depsgraph_get())
    yb = head.y + .055; hit = bvh.ray_cast(V((0, yb, 2.2)), V((0, 0, -1)))
    base = (hit[0] if hit[0] else V((0, yb, eye.z + .11))) - V((0, 0, .012))
    add(feather('Feather', base), m_feather(), 'head')
    return hair

def feather(name, base, length=.21, width=.06):
    """An ostrich plume from `base`: a tapering quill and a soft vane on each side, the
    barbs clumped at the edge and the tip drooping a little backwards."""
    def spine(t):   # rises upright, leaning a little forward, the tip turning back
        return base + V((0, -.03 * t + .045 * t ** 3, length * t))
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); rnd = random.Random(4)
    nu, nv = 28, 5
    for s in (1, -1):
        grid = []
        for i in range(nu + 1):
            t = .1 + .9 * i / nu
            hw = width / 2 * max(0, min(1, (t - .14) * 3.5)) * max(0, 1 - ((t - .58) / .44) ** 4) ** .5
            hw *= 1 + .3 * (rnd.random() - .5)
            row = []
            for j in range(nv + 1):
                k = j / nv
                p = spine(t + .05 * k) + V((s * hw * k, .006 * k * k, 0))   # the barbs angle up and curl back at the edge
                row.append(bm.verts.new(p))
            grid.append(row)
        for i in range(nu):
            for j in range(nv):
                q = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                f = bm.faces.new(q if s > 0 else q[::-1])
                for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)) if s > 0 else ((i, j + 1), (i + 1, j + 1), (i + 1, j), (i, j))):
                    lp[uv].uv = (a / nu * .5 + b / nv * .35, b / nv)   # u runs along the barbs, out and up
    vane = obj_from_bm(name, bm)
    mod(vane, 'SOLIDIFY', thickness=.0012, offset=0); bake_mods(vane)
    quill = curve_mesh(name + 'Quill', [[tuple(spine(-.08 + 1.1 * i / 20)) for i in range(21)]], .0016, radii=lambda t: 1 - .7 * t)
    bm = bmesh.new(); bm.from_mesh(vane.data); bm.from_mesh(quill.data)
    bm.to_mesh(vane.data); bm.free(); bpy.data.objects.remove(quill)
    for p in vane.data.polygons: p.use_smooth = True
    return vane


# ── The kilt (shendyt): wrapped linen, draped, with its overlap, tab and knot ─
def hanging_tube(name, body, z0, z1, gap=.02, nr=64, nz=26):
    """A tube from the waist (z0) to the hem (z1) as a wrap kilt hangs before it is draped:
    snug at the waist, then falling straight from the widest point above each spot (the
    seat, the hips, the thighs), so the cloth sim only settles it and lays in the folds."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    cy = .0
    def reach(a, z):
        d = V((math.sin(a), -math.cos(a), 0)); o = V((0, cy, z))
        h = bvh.ray_cast(o + d * .5, -d, .6)
        return (h[0] - o).length if h[0] else .12
    bm = bmesh.new(); rows = []; prev = [0.0] * nr
    for j in range(nz + 1):
        z = z0 - (z0 - z1) * j / nz
        r = [max(prev[i], reach(2 * math.pi * i / nr, z)) for i in range(nr)]
        prev = r
        k = j / nz
        rows.append([bm.verts.new((math.sin(a) * (r[i] + .004 + gap * min(1, k * 3)), cy - math.cos(a) * (r[i] + .004 + gap * min(1, k * 3)), z))
                     for i, a in enumerate(2 * math.pi * i / nr for i in range(nr))])
    for j in range(nz):
        for i in range(nr): bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][(i + 1) % nr], rows[j][(i + 1) % nr]))   # facing out
    return obj_from_bm(name, bm)

def drape_on(name, ob, pin, colliders, frames=50, mass=.25, bend=.5, thickness=.0025):
    """H.drape with several colliders (the body and, for an outer layer, the cloth
    beneath) and stiffer bending, for crisp linen."""
    for c in colliders:
        mod(c, 'COLLISION'); c.collision.thickness_outer = .005
    cl = mod(ob, 'CLOTH'); s = cl.settings
    s.quality = 8; s.mass = mass; s.tension_stiffness = 15; s.compression_stiffness = 15; s.bending_stiffness = bend; s.air_damping = 1.5
    vg = ob.vertex_groups.new(name='pin'); vg.add([v.index for v in ob.data.vertices if pin(v.co)], 1.0, 'REPLACE'); s.vertex_group_mass = 'pin'
    cl.collision_settings.distance_min = .005; cl.collision_settings.use_self_collision = False
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = frames
    for f in range(1, frames + 1): SC.frame_set(f)
    bake_mods(ob); ob.vertex_groups.clear()
    for c in colliders: c.modifiers.remove(c.modifiers['collision'])
    SC.frame_set(1)
    if thickness: mod(ob, 'SOLIDIFY', thickness=thickness, offset=1); bake_mods(ob)
    return ob

KILT = dict(top=1.035, hem=.57, belt=1.005, arch=.085, arch_w=.15)

def trunk(body):
    """A copy of the body without its arms (held out in the rest pose), for laying belts,
    kilts and armour round the trunk by ray casts. Removed when the kit is built."""
    ob = link(body.copy()); ob.data = body.data.copy(); ob.name = 'TrunkProbe'
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.calc_center_median().x) > .235 and f.calc_center_median().z > .8], context='FACES')
    bm.to_mesh(ob.data); bm.free()
    return ob

def kilt(tag, body, mat, add, under_mat=None):
    """The wrapped kilt: the draped linen, the outer turn of the wrap over the front with
    its corner rounded up to the middle (the under layer shows below it), all thickened."""
    k = KILT
    sk = hanging_tube(tag + 'Kilt', body, k['top'], k['hem'])
    drape_on(tag + 'Kilt', sk, lambda c: c.z > k['top'] - .012, [body], thickness=0)
    # the outer turn: the front of the draped cloth lifted clear of it, its hem rounded up
    bm = bmesh.new(); bm.from_mesh(sk.data); bm.normal_update()
    def keep(c):
        if c.y > .02 or abs(c.x) > .25: return False
        u = abs(c.x) / k['arch_w']
        return c.z > k['hem'] + .004 + (k['arch'] * (1 - u) ** 1.7 if u < 1 else 0)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for v in bm.verts: v.co += v.normal * .0045
    ov = obj_from_bm(tag + 'KiltWrap', bm); relax_rim(ov, 3)
    bm = bmesh.new(); bm.from_mesh(ov.data)
    hem = [v for v in HM.boundary_loops(bm) if True]
    lows = max(hem, key=lambda L: -min(v.co.z for v in L)) if hem else []
    edge = [tuple(v.co) for v in lows if v.co.z < KILT['hem'] + KILT['arch'] + .02 and abs(v.co.x) < .2]
    bm.free()
    for o, mt in ((sk, under_mat or mat), (ov, mat)):
        mod(o, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(o); add(o, mt, 'hang')
    hem = None
    if len(edge) > 3:   # the rolled hem of the outer turn, which casts the line of shadow the sheet shows
        edge.sort(key=lambda p: p[0])
        hem = add(curve_mesh(tag + 'KiltHem', [edge], .0032, res=1), mat, 'hang')
    return sk, ov, hem

def kilt_tab(name, under, x0=-.06, w=.076, z0=1.01, z1=.668):
    """The end of the wrap tucked under the belt, hanging down the front as a flat tab."""
    sf = Surf(under); bm = bmesh.new(); rows = []
    for j in range(13):
        z = z0 - (z0 - z1) * j / 12; ww = w * (1 + .12 * j / 12); row = []
        for i in range(5):
            x = x0 + ww * (i / 4 - .5); h = sf.hit(V((x, 0, z)), V((0, -1, 0)))
            p = (h[0] + h[1] * .007) if h else V((x, -.15, z))
            row.append(bm.verts.new(p + V((0, -.002 * math.sin(math.pi * i / 4), 0))))
        rows.append(row)
    for j in range(12):
        for i in range(4): bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(ob)
    return ob

def kilt_knot(name, under, z=1.008, drop=.21):
    """The knot at the small of the back, the loose ends hanging from it in folds."""
    sf = Surf(under); h = sf.hit(V((0, 0, z)), V((0, 1, 0)))
    c = (h[0] if h else V((0, .14, z))) + V((0, .018, 0))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1, matrix=Matrix.Translation(c) @ Matrix.Diagonal((.03, .019, .024, 1)))
    for v in bm.verts:   # gathered folds round the knot
        a = math.atan2(v.co.z - c.z, v.co.x - c.x); v.co.y += .003 * math.sin(a * 5) * (v.co.y > c.y)
    rows = []
    for j in range(15):
        t = j / 14; zz = c.z - .006 - drop * t; ww = .05 + .09 * t ** .8; row = []
        for i in range(9):
            u = i / 8 - .5; x = ww * u - .012 * t
            hh = sf.hit(V((x, 0, zz)), V((0, 1, 0)))
            base = hh[0].y if hh else .14
            y = base + .01 + .012 * (1 - t) + .007 * math.sin(u * math.pi * 3 + 1) * (.4 + t)
            row.append(bm.verts.new((x, y, zz - .05 * t * (u + .5) * (t > .85))))
        rows.append(row)
    for j in range(14):
        for i in range(8): bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1]))
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.003, offset=0); bake_mods(ob)
    return ob

def apron(name, under, z0=.99, z1=.665, w0=.1, w1=.15):
    """The apron hanging in front from the belt, lying over the kilt; UVs fill the square."""
    sf = Surf(under); bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); rows = []
    for j in range(13):
        t = j / 12; z = z0 - (z0 - z1) * t; w = w0 + (w1 - w0) * t; row = []
        for i in range(7):
            x = w * (i / 6 - .5); h = sf.hit(V((x, 0, z)), V((0, -1, 0)))
            y = (h[0].y if h else -.17) - .007 - .012 * t * t
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(12):
        for i in range(6):
            f = bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))): lp[uvl].uv = (a / 6, 1 - b / 12)
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(ob)
    return ob

def belt(name, under, z, width, off=.005):
    pts = ring_on(Surf(under), z, off, 72); pts.append(pts[0])
    ob = ribbon(name, pts, width, .004)
    bm = bmesh.new(); bm.from_mesh(ob.data); uvl = bm.loops.layers.uv.new('UV')
    for f in bm.faces:   # u round the waist, v across the band
        for lp in f.loops:
            p = lp.vert.co; lp[uvl].uv = ((math.atan2(p.x, -p.y) / (2 * math.pi)) % 1.0, (p.z - z) / width + .5)
    bm.to_mesh(ob.data); bm.free(); wrap_seam(ob.data, ob.data.uv_layers['UV'])
    return ob


# ── Jewellery, sandals and blades ───────────────────────────────────────────
def necklace(name, body, J, mats, drop=.035, r=.0042, step=.0092):
    """Beads strung round the base of the neck, high at the back and lying on the
    collarbones in front; every third bead gold."""
    neck, sh_z = J['neck'], J['l-shoulder'].z
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    path = []
    for i in range(96):
        a = 2 * math.pi * i / 96; d = V((math.sin(a), -math.cos(a), 0))
        z = neck.z - .005 - drop * (.5 + .5 * math.cos(a)) ** 1.5
        o = V((0, neck.y + .005, z)); h = bvh.ray_cast(o + d * .3, -d, .35)
        path.append((h[0] + h[1] * (r + .001)) if h[0] else o + d * .07)
    path = [(path[i - 1] + path[i] * 2 + path[(i + 1) % 96]) / 4 for i in range(96)]
    beads, gold, acc, i = bmesh.new(), bmesh.new(), 0.0, 0
    L = sum((path[(k + 1) % 96] - path[k]).length for k in range(96)); n = int(L / step)
    pts = []
    for k in range(96):
        a, b = path[k], path[(k + 1) % 96]; seg = (b - a).length
        while acc <= seg and len(pts) < n:
            pts.append((a.lerp(b, acc / seg), (b - a).normalized())); acc += L / n
        acc -= seg
    for i, (p, t) in enumerate(pts):
        q = t.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bmesh.ops.create_uvsphere(gold if i % 3 == 0 else beads, u_segments=8, v_segments=6, radius=1,
                                  matrix=Matrix.Translation(p) @ q @ Matrix.Diagonal((r, r, r * (.8 if i % 3 else 1.05), 1)))
    return [(obj_from_bm(name, beads), mats[0]), (obj_from_bm(name + 'Gold', gold), mats[1])]

def pendant(name, body, J, z, mats, w=.036, h=.05):
    """An amulet of pale stone, a little tapered, hung on a cord from the necklace (laid
    on `body`, which may be the collar it hangs from instead)."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    hit = bvh.ray_cast(V((0, -.5, z)), V((0, 1, 0)), 1)
    p, n = (hit[0], hit[1]) if hit[0] else (V((0, -.12, z)), V((0, -1, 0)))
    bm = bmesh.new()
    prof = [(-w * .42, 0), (w * .42, 0), (w * .5, -h), (-w * .5, -h)]
    top = [bm.verts.new((x, 0, zz)) for x, zz in prof]; bot = [bm.verts.new((x, .007, zz)) for x, zz in prof]
    bm.faces.new(top[::-1]); bm.faces.new(bot)
    for i in range(4): bm.faces.new((top[i], top[(i + 1) % 4], bot[(i + 1) % 4], bot[i]))
    am = obj_from_bm(name, bm, False); mod(am, 'BEVEL', width=.0025, segments=2); bake_mods(am)
    x = n.cross(V((0, 0, 1))).normalized(); M = Matrix((x, -n, x.cross(-n))).transposed().to_4x4()
    M.translation = p + n * .0035; am.matrix_world = M; bpy.context.view_layer.update(); bake_obj_xform(am)
    neck = J['neck']; cord = []
    for s in (-1, 1):   # the cord from the necklace at each side of the neck down to the amulet's top corners
        pts = []
        for i in range(13):
            t = i / 12; q = V((s * (.045 - .03 * t), 0, neck.z - .035 - (neck.z - .035 - z) * t))
            hh = bvh.ray_cast(q + V((0, -.5, 0)), V((0, 1, 0)), 1)
            pts.append(tuple((hh[0] + hh[1] * .003) if hh[0] else q + V((0, -.12, 0))))
        cord.append(pts)
    return [(am, mats[0]), (curve_mesh(name + 'Cord', cord, .0011, res=1), mats[1])]

def ring_round(bvh, a, b, t, off, n=36, reach=.09):
    """Points round a limb at fraction t from joint a to joint b, `off` clear of the skin.
    The rays start just outside the limb, so the trunk beside an arm is never hit."""
    c = a.lerp(b, t); u = (b - a).normalized(); e1 = u.orthogonal().normalized(); e2 = u.cross(e1); pts = []
    for i in range(n):
        ang = 2 * math.pi * i / n; d = e1 * math.cos(ang) + e2 * math.sin(ang)
        h = bvh.ray_cast(c + d * reach, -d, reach)
        pts.append((h[0] + h[1] * off) if h[0] else c + d * .05)
    return [tuple(p) for p in pts]

def limb_band(name, bvh, a, b, t, width, off=.005, n=40):
    """minotaur.limb_band with the rays started just outside the limb."""
    pts = ring_round(bvh, a, b, t, 0, n); c = a.lerp(b, t); out = []
    for p in pts + pts[:1]:
        p = V(p); d = (p - c); d -= (b - a).normalized() * d.dot((b - a).normalized()); d.normalize(); out.append((p + d * off, d))
    return ribbon(name, out, width, .003)

def sandals(body, J, add, leather, sole_mat):
    """Leather soles with straps over the toes and instep, crossed straps up the foot,
    two straps round the ankle and one behind the heel (after hoplite.py's)."""
    for side in ('l', 'r'):
        S = side.upper(); an = J[f'{side}-ankle']
        feet = [body.matrix_world @ v.co for v in body.data.vertices]
        foot_pts = [p for p in feet if p.z < .03 and abs(p.x - an.x) < .09]
        bm = bmesh.new()
        for p in foot_pts: bm.verts.new((p.x, p.y, -.001)); bm.verts.new((p.x, p.y, .011))
        bmesh.ops.convex_hull(bm, input=bm.verts)
        so = obj_from_bm(f'Sole{S}', bm, False); mod(so, 'BEVEL', width=.003, segments=2); bake_mods(so)
        for v in so.data.vertices: v.co.x = an.x + (v.co.x - an.x) * 1.07; v.co.y = an.y + (v.co.y - an.y) * 1.04
        add(so, sole_mat, f'foot.{S}')
        bvh_f = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
        loops = []
        for yy, zz, ring in ((an.y - .16, .03, False), (an.y - .125, .04, False), (an.y - .085, .055, False),
                             (an.y, an.z + .012, True), (an.y + .004, an.z + .05, True), (an.y + .006, an.z + .085, True)):
            pts = []
            for i in range(28):
                a = i / 28 * 2 * math.pi
                d = V((math.cos(a), math.sin(a), 0)) if ring else V((math.cos(a), 0, math.sin(a)))
                cx = V((an.x, yy, zz)); h = bvh_f.ray_cast(cx + d * .2, -d, .25)
                q = (h[0] + h[1] * .0025) if h[0] else cx + d * .04
                pts.append(V((q.x, q.y, max(q.z, .011))))
            loops.append([tuple(p) for p in pts])
        straps = curve_mesh(f'Straps{S}', loops, .0042, cyclic=True, res=1)
        straps.scale = (1, 1, 1)
        bm = bmesh.new(); bm.from_mesh(straps.data)
        for v in bm.verts: v.co.z = an.z + (v.co.z - an.z) * 1.0
        bm.to_mesh(straps.data); bm.free()
        add(straps, leather, f'foot.{S}')
        cross = []   # two straps crossing over the instep, from the sole's edges up to the ankle strap
        for sx in (-1, 1):
            a0, a1 = V((an.x + sx * .042, an.y - .1, .014)), V((an.x - sx * .012, an.y - .045, an.z + .012))
            pts = []
            for i in range(9):
                q = a0.lerp(a1, i / 8) + V((0, 0, .02 * math.sin(math.pi * i / 8)))
                loc, no, fi, d = bvh_f.find_nearest(q)
                pts.append(tuple((loc + no * .003) if loc is not None else q))
            cross.append(pts)
        heel = []
        for i in range(7):
            z = .012 + (an.z + .085 - .012) * i / 6; h = bvh_f.ray_cast(V((an.x, .4, z)), V((0, -1, 0)), .6)
            heel.append(tuple((h[0] + h[1] * .003) if h[0] else V((an.x, an.y + .05, z))))
        add(curve_mesh(f'CrossStraps{S}', cross + [heel], .0036, res=1), leather, f'foot.{S}')

def dagger(tag, at, rot, mats, add):
    """A bronze dagger in a leather sheath with a bronze chape, tucked into the belt."""
    leather, bronze = mats
    sc, hilt = P.sheath(tag, .22, 0, at, rot, (leather, bronze), add, width=.02, hilt_scale=.75,
                        radii=lambda t: (1 - .5 * t ** 2) * (1.15 - .15 * t))
    ch = lathe(tag + 'Chape', [(0, -.012), (.012, -.008), (.018, .004), (.018, .016)], 14); ch.scale = (1, .36, 1)
    ch.matrix_world = Matrix.Translation(at) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Translation((0, 0, -.215)) @ ch.matrix_basis
    bake_obj_xform(ch); add(ch, bronze, 'hips')


# ── Spears and shields ──────────────────────────────────────────────────────
def spear(tag, L0, L1, mats, blade=(.24, .028), butt_spike=False, gilt=None):
    """A spear built about its grip (the origin), point to +Z: a tapering wooden shaft,
    a bronze leaf blade with a midrib on a long socket bound to the shaft, and either a
    sharpened butt or a bronze butt-spike. `gilt` gilds the socket and its rings."""
    wood, bronze = mats; bl, bw = blade; out = []
    out.append((lathe(tag + 'Shaft', [(0, -L0), (.009, -L0 + .03), (.0125, -L0 + .2), (.0135, 0), (.0118, L1), (0, L1 + .004)], 12), wood))
    sock = lathe(tag + 'Socket', [(.0128, L1 - .12), (.0148, L1 - .115), (.0142, L1 - .02), (.0118, L1 + .03)], 14)
    rings = lathe(tag + 'SocketRings', [(.0138, L1 - .118), (.0168, L1 - .112), (.0168, L1 - .1), (.0138, L1 - .094)], 14)
    out += [(sock, gilt or bronze), (rings, gilt or bronze)]
    head = lathe(tag + 'Blade', [(.011, L1), (bw * .55, L1 + bl * .12), (bw, L1 + bl * .38), (bw * .86, L1 + bl * .62), (bw * .45, L1 + bl * .86), (0, L1 + bl)], 8)
    head.scale = (1, .16, 1); bake_obj_xform(head)
    rib = lathe(tag + 'Midrib', [(.0085, L1), (.0062, L1 + bl * .5), (0, L1 + bl * .97)], 8)
    out += [(head, bronze), (rib, bronze)]
    if butt_spike:
        out.append((lathe(tag + 'Butt', [(0, -L0 - .13), (.0105, -L0 - .02), (.013, -L0 + .02), (.0125, -L0 + .07)], 10), bronze))
    return out

def oval_shield(tag, mats, add, W=.4, Hh=.6, depth=.035, board=.04):
    """The first tier's small oval shield: cowhide over a dished oval, laced round its rim
    with a rawhide thong. Built about the grip (origin), the grip bar along X, the shield's
    height along Y and its face towards +Z."""
    hide, back_m, thong, wood = mats
    bm = bmesh.new(); rings, segs = 14, 72
    grid = [[None] * segs for _ in range(rings + 1)]
    c = bm.verts.new((0, 0, board + depth))
    for i in range(1, rings + 1):
        r = i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs; x, y = math.cos(a) * W / 2 * r, math.sin(a) * Hh / 2 * r
            grid[i][j] = bm.verts.new((x, y, board + depth * (1 - r * r)))
    for j in range(segs): bm.faces.new((c, grid[1][j], grid[1][(j + 1) % segs]))
    for i in range(1, rings):
        for j in range(segs): bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][(j + 1) % segs], grid[i][(j + 1) % segs]))
    uvl = bm.loops.layers.uv.new('UV')
    for f in bm.faces:
        for lp in f.loops: lp[uvl].uv = (lp.vert.co.x / Hh + .5, lp.vert.co.y / Hh + .5)
    face = obj_from_bm(tag + 'ShieldFace', bm)
    back = face.copy(); back.data = face.data.copy(); back.name = tag + 'ShieldBack'; link(back)
    for v in back.data.vertices: v.co.z -= .004
    back.data.flip_normals()
    mod(face, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(face)
    add(face, hide, 'later:shield'); add(back, back_m, 'later:shield')   # hair-on hide both sides, laced round the rim
    rim = [(math.cos(2 * math.pi * j / 96) * W / 2, math.sin(2 * math.pi * j / 96) * Hh / 2, board - .002) for j in range(96)]
    add(curve_mesh(tag + 'ShieldRim', [rim], .006, cyclic=True), thong, 'later:shield')
    st = []   # the lacing: a stitch over the rim every few centimetres
    for j in range(44):
        a = 2 * math.pi * j / 44; cx, cy = math.cos(a), math.sin(a)
        p0 = (cx * (W / 2 - .02), cy * (Hh / 2 - .02), board + depth * .08 + .002)
        p1 = (cx * (W / 2 + .004), cy * (Hh / 2 + .004), board + .002)
        p2 = (cx * (W / 2 - .014), cy * (Hh / 2 - .014), board - .006)
        st.append([p0, p1, p2])
    add(curve_mesh(tag + 'ShieldLacing', st, .0024, res=1), thong, 'later:shield')
    grip_bar(tag, wood, add, board)

def grip_bar(tag, wood, add, board, span=.075):
    """The wooden grip across the shield's back: a bar through the fist, on two posts."""
    bar = curve_mesh(tag + 'ShieldGrip', [[(-span - .015, 0, board), (-span, 0, .012), (-.05, 0, 0), (.05, 0, 0), (span, 0, .012), (span + .015, 0, board)]], .0115, res=2)
    add(bar, wood, 'later:shield')


# ── Armour: plates and scales sewn onto a backing ───────────────────────────
def columns(surf_bvh, z, n, centre=V((0, .0, 0))):
    """n bearings round the trunk at height z, spaced evenly along the girth there (so the
    columns of plates or scales above and below line up with them)."""
    pts = []
    for i in range(360):
        a = 2 * math.pi * i / 360; d = V((math.sin(a), -math.cos(a), 0)); o = V((centre.x, centre.y, z))
        h = surf_bvh.ray_cast(o + d * .6, -d, .7)
        pts.append((a, h[0] if h[0] else o + d * .15))
    acc = [0.0]
    for i in range(1, 361): acc.append(acc[-1] + (pts[i % 360][1] - pts[i - 1][1]).length)
    out, j = [], 0
    for k in range(n):
        t = acc[-1] * k / n
        while acc[j + 1] < t: j += 1
        f = (t - acc[j]) / max(1e-9, acc[j + 1] - acc[j]); out.append((j + f) * 2 * math.pi / 360)
    return out, acc[-1]

def scale_mesh(name, spots, w, h, lift=(.0012, .0045), round_=.35, bulge=.0008):
    """One small plate or scale at each spot (centre, outward normal, width factor and,
    optionally, the direction it hangs): its top edge straight and close to the backing,
    its sides straight, its lower end rounded (round_ 1 a half circle) and lifted clear,
    so each row lies over the top of the row below; a little domed across. Each gets its
    own cell of the UV square, so the bake varies them one by one."""
    bm = bmesh.new(); uv = bm.loops.layers.uv.new('UV'); cells = int(math.ceil(math.sqrt(len(spots)))) or 1
    us, vs = (-.5, -.25, 0, .25, .5), (-.5, -.2, .1, .5 - round_ * .5, .5 - round_ * .25, .5)
    r = round_ * .5
    def wid(v):   # half-width factor down the plate: straight, then the rounded lower end
        if v <= .5 - r or r == 0: return 1.0
        return math.sqrt(max(0, 1 - ((v - (.5 - r)) / r) ** 2)) ** .9
    for k, spot in enumerate(spots):
        p, n, wf = spot[:3]
        down = spot[3] if len(spot) > 3 else V((0, 0, -1))
        down = (down - n * down.dot(n)).normalized(); side = n.cross(down)
        ww = w * wf; cu, cv = (k % cells) / cells, (k // cells) / cells
        grid = []
        for v in vs:
            row = []
            for u in us:
                q = p + side * (u * ww * wid(v)) + down * (v * h) + n * (lift[0] + (lift[1] - lift[0]) * (v + .5) + bulge * (1 - 4 * u * u))
                row.append(bm.verts.new(q))
            grid.append(row)
        for j in range(len(vs) - 1):
            for i in range(len(us) - 1):
                f = bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))
                for lp, (a, b) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                    lp[uv].uv = (cu + (us[a] + .5) * .9 / cells, cv + (vs[b] + .5) * .9 / cells)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return obj_from_bm(name, bm)

def plate_rows(shell, rows, n, w, h, centre=V((0, 0, 0)), stagger=False, keep=lambda p: True, mid=None):
    """Spots for scale_mesh: rows of n plates on the shell at the given heights, their
    columns spaced along the girth of the middle row (or of the row at height `mid`)."""
    bvh = BVHTree.FromObject(shell, bpy.context.evaluated_depsgraph_get())
    angs, girth = columns(bvh, mid or rows[len(rows) // 2], n, centre)
    spots = []
    for r, z in enumerate(rows):
        _, g = columns(bvh, z, 8, centre)
        for k, a in enumerate(angs):
            if stagger and r % 2: a = (a + angs[(k + 1) % n] + (2 * math.pi if k == n - 1 else 0)) / 2
            d = V((math.sin(a), -math.cos(a), 0)); o = V((centre.x, centre.y, z))
            hit = bvh.ray_cast(o + d * .6, -d, .7)
            if not hit[0] or hit[1].dot(d) < .2 or not keep(hit[0]): continue
            nn = V((d.x * .7 + hit[1].x * .3, d.y * .7 + hit[1].y * .3, hit[1].z)).normalized()   # the shell's slope, without its small bumps
            spots.append((hit[0], nn, g / girth))
    return spots

def corselet(tag, body, J, add, mats):
    """The second tier's corselet: tan leather from the shoulders to the waist, sleeveless,
    a plain yoke over the shoulders and a band round the lower edge, and between them
    straight rows of small bronze plates with rounded lower ends, sewn on in columns."""
    leather, edge_m, plate_m = mats
    neck, sh, eye = J['neck'], J['l-shoulder'], J['l-eye']
    def keep(c):
        if c.z < 1.03 or c.z > neck.z + .01: return False
        if on_arm(J, .04, 1.1, .07)(c) or abs(c.x) > .2: return False                           # the armholes
        if c.z > sh.z + .01 and V((c.x, c.y - neck.y - .008, 0)).length < .074: return False    # the neck
        return True
    sh_ = region_shell(tag + 'Corselet', body, keep, .011, 10, .5, guard=.009); relax_rim(sh_, 14)
    add(HM.edge_band(tag + 'CorseletEdge', sh_, lambda info: [L for c, L in info], .016, .003, body), edge_m, 'skin')
    mod(sh_, 'SOLIDIFY', thickness=.004, offset=1); bake_mods(sh_)
    add(sh_, leather, 'skin')
    yoke_z = sh.z - .022
    rows = [yoke_z - .0265 * i for i in range(13) if yoke_z - .0265 * i > 1.07]
    spots = plate_rows(sh_, rows, 38, .024, .034, keep=lambda p: p.z < yoke_z + .02)
    plates = scale_mesh(tag + 'Plates', spots, .0258, .034, (.0014, .0036), .5, .0007)
    add(plates, plate_m, 'skin:' + sh_.name)
    return sh_

def khopesh(tag, mats, add, at, rot):
    """The sickle sword: a grip and pommel, a straight bronze neck and the crescent blade,
    which rides in a sheath of tan leather cut to its shape. Built with the grip upward
    from the origin and the blade hooking towards +Y, then hung at `at`, turned by `rot`."""
    bronze, sheath_m, grip_m = mats
    parts = [(lathe(tag + 'KhopeshGrip', [(0, .125), (.019, .122), (.02, .108), (.013, .1), (.0145, .05), (.0135, .012), (.019, 0)], 14), grip_m)]
    parts[0][0].scale = (.85, 1, 1)
    bm = bmesh.new()   # the neck, a flat bar
    for (y0, y1), z0, z1 in (((-.013, .013), 0, -.165),):
        bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((0, 0, (z0 + z1) / 2)) @ Matrix.Diagonal((.009, .026, z0 - z1, 1)))
    parts.append((obj_from_bm(tag + 'KhopeshNeck', bm, False), bronze))
    R, cy, cz = .125, .125, -.165; bm = bmesh.new(); rows = []
    for i in range(25):   # the crescent: wide in the middle, the convex edge outward, a hooked point
        t = i / 24; th = math.pi + t * math.radians(128)
        w = .02 + .03 * math.sin(math.pi * min(1, t * 1.1)) ** .8 if t < .97 else .004
        c = V((0, cy + math.cos(th) * R, cz + math.sin(th) * R)); out = V((0, math.cos(th), math.sin(th)))
        rows.append((bm.verts.new(c - out * .012), bm.verts.new(c + out * (w - .012))))
    for i in range(24): bm.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
    sh = obj_from_bm(tag + 'KhopeshSheath', bm); mod(sh, 'SOLIDIFY', thickness=.016, offset=0); mod(sh, 'BEVEL', width=.004, segments=2, limit_method='ANGLE'); bake_mods(sh)
    parts.append((sh, sheath_m))
    M = Matrix.Translation(at) @ Euler(rot).to_matrix().to_4x4()
    for o, mt in parts:
        o.matrix_world = M @ o.matrix_basis; bpy.context.view_layer.update(); bake_obj_xform(o); add(o, mt, 'hips')


def framed_shield(tag, mats, add, Hh, wt, wb, grip, depth=.05, board=.04, rim=.009, frame=True, feet=.012):
    """A tall shield with a rounded top and a straight lower edge, hide stretched over a
    wooden frame and edged round its rim. Built about the grip as oval_shield is (grip bar
    along X, height along Y, face to +Z); `grip` is the grip's height above the lower edge."""
    hide, back_m, rim_m, wood = mats
    y0, y1 = -grip, Hh - grip; yc = y1 - wt
    def hw(y):
        if y <= yc: return wb + (wt - wb) * (y - y0) / (yc - y0)
        return wt * math.sqrt(max(0, 1 - ((y - yc) / wt) ** 2))
    def surf(x, y, off=0.0):
        wmax = wb * 1.05
        return board + depth * (1 - (x / wmax) ** 2) * (1 - .25 * ((y - (y0 + y1) / 2) / (Hh / 2)) ** 2) + off
    nu, nv = 24, 44; bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); grid = []
    for j in range(nv + 1):
        t = j / nv; y = y0 + (y1 - y0) * (1 - (1 - t) ** 1.0); row = []
        for i in range(nu + 1):
            u = i / nu * 2 - 1; x = u * hw(y)
            yy = y + (feet * abs(u) ** 6 * -1 + .012 * (1 - u * u)) * (1 - t) ** 8   # the lower edge: a little hollow, the corners drawn down
            row.append(bm.verts.new((x, yy, surf(x, yy))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp in f.loops: lp[uvl].uv = (lp.vert.co.x / Hh + .5, lp.vert.co.y / Hh + .5)
    outline = [grid[j][0].co.copy() for j in range(nv + 1)] + [grid[nv][i].co.copy() for i in range(1, nu + 1)] + \
              [grid[j][nu].co.copy() for j in range(nv - 1, -1, -1)] + [grid[0][i].co.copy() for i in range(nu - 1, 0, -1)]
    outline = [p for k, p in enumerate(outline) if k == 0 or (p - outline[k - 1]).length > 1e-4]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    face = obj_from_bm(tag + 'ShieldFace', bm)
    back = face.copy(); back.data = face.data.copy(); back.name = tag + 'ShieldBack'; link(back)
    for v in back.data.vertices: v.co.z -= .005
    back.data.flip_normals()
    mod(face, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(face)
    add(face, hide, 'later:shield'); add(back, back_m, 'later:shield')
    add(curve_mesh(tag + 'ShieldRim', [[tuple(p - V((0, 0, .002))) for p in outline]], rim, cyclic=True), rim_m, 'later:shield')
    if frame:   # the frame on the back: a stile up the middle, a slat inside the rim and a diagonal brace
        def on_back(x, y): return (x, y, surf(x, y) - .013)
        stile = [on_back(0, y0 + .02 + (y1 - y0 - .05) * k / 20) for k in range(21)]
        inner = [on_back(p.x * .9, y0 + (p.y - y0) * .96 + .01) for p in outline[::2]]
        brace = [on_back(-hw(y0 + .05) * .8 + (hw(yc) * 1.6) * k / 16, y0 + .05 + (yc - y0 - .05) * k / 16) for k in range(17)]
        fr = curve_mesh(tag + 'ShieldFrame', [stile, brace], .007, res=1)
        fr2 = curve_mesh(tag + 'ShieldFrameRim', [inner], .006, cyclic=True, res=1)
        add(fr, wood, 'later:shield'); add(fr2, wood, 'later:shield')
        lash = []   # rawhide lashings binding the frame at the lower corners
        for sx in (-1, 1):
            cx, cy_ = sx * (wb - .015), y0 + .02
            for k in range(5):
                a = k / 5 * 2 * math.pi
                lash.append([(cx + .012 * math.cos(a + q * .4), cy_ + .006 * (k - 2) * .6, surf(cx, cy_) - .01 + .016 * math.sin(a + q * .4)) for q in range(16)])
        add(curve_mesh(tag + 'ShieldLashing', lash, .0018, res=1), rim_m, 'later:shield')
    grip_bar(tag, wood, add, board - (.014 if frame else 0))
    return face

# ── The third tier's coat of scales, collar and gold ────────────────────────
def collar_image():
    """The broad collar (wesekh) in its UV square: u round the neck, v from the neck out.
    Rows of turquoise, lapis and gold beads, then a fringe of gold drops."""
    from PIL import Image, ImageDraw
    W, Hh = 2048, 256; im = Image.new('RGB', (W, Hh), (40, 34, 26)); d = ImageDraw.Draw(im)
    rows = [(0, 12, (196, 152, 64), 4), (12, 40, (52, 150, 152), 3), (40, 50, (196, 152, 64), 4), (50, 78, (34, 52, 110), 3),
            (78, 106, (60, 160, 160), 3), (106, 116, (196, 152, 64), 4), (116, 140, (34, 52, 110), 3), (140, 166, (60, 160, 160), 3), (166, 180, (210, 166, 74), 4)]
    for y0, y1, col, k in rows:   # each row a string of round beads, lit from above
        r = (y1 - y0) / 2; n = int(W / (2 * r * .92))
        for i in range(n):
            x = (i + .5) * W / n
            d.ellipse((x - r, y0, x + r, y1), fill=tuple(int(c * .55) for c in col))
            d.ellipse((x - r * .8, y0 + r * .15, x + r * .7, y1 - r * .35), fill=col)
            d.ellipse((x - r * .35, y0 + r * .3, x + r * .05, y0 + r * .7), fill=tuple(min(255, int(c * 1.45 + 30)) for c in col))
    n = 150
    for i in range(n):   # the drops: long gold beads widening to a rounded foot
        x = (i + .5) * W / n; y0, y1 = 182, 252; w = W / n * .42
        d.polygon([(x - w * .35, y0), (x + w * .35, y0), (x + w, y1 - 10), (x, y1), (x - w, y1 - 10)], fill=(150, 110, 40))
        d.polygon([(x - w * .15, y0 + 2), (x + w * .25, y0 + 2), (x + w * .6, y1 - 14), (x - w * .3, y1 - 16)], fill=(222, 182, 92))
    return pil_image('CollarArt', im)

def apron_image():
    """The apron hung from the belt: a middle panel of gold lozenges on red, a beaded border,
    red side lappets dotted with gold, and a gold triangle at the foot (after the sheet)."""
    from PIL import Image, ImageDraw
    W, Hh = 256, 512; im = Image.new('RGB', (W, Hh), (110, 34, 24)); d = ImageDraw.Draw(im)
    gold, dark, red = (208, 162, 70), (60, 20, 14), (150, 52, 32)
    for x0 in (0, W - 52):   # side lappets
        d.rectangle((x0, 0, x0 + 52, Hh), fill=red)
        for y in range(10, Hh, 22):
            for x in (x0 + 14, x0 + 38): d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=gold)
    d.rectangle((52, 0, W - 52, Hh), fill=gold); d.rectangle((62, 0, W - 62, Hh - 70), fill=dark)
    for k in range(7):   # stacked lozenges
        cy = 34 + k * 58; cx = W / 2
        d.polygon([(cx, cy - 26), (cx + 52, cy), (cx, cy + 26), (cx - 52, cy)], fill=gold)
        d.polygon([(cx, cy - 15), (cx + 30, cy), (cx, cy + 15), (cx - 30, cy)], fill=red)
        d.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=gold)
    d.rectangle((52, Hh - 70, W - 52, Hh), fill=gold)
    d.polygon([(W / 2 - 50, Hh - 62), (W / 2 + 50, Hh - 62), (W / 2, Hh - 12)], fill=dark)
    d.polygon([(W / 2 - 30, Hh - 54), (W / 2 + 30, Hh - 54), (W / 2, Hh - 24)], fill=red)
    for y in range(4, Hh, 12):   # beaded edges of the middle panel
        for x in (57, W - 57): d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(236, 200, 110))
    return pil_image('ApronArt', im)

def scale_coat(body, J, add, mats):
    """The coat's body and short sleeves, grown from the body, scaled all over: small
    round-ended bronze scales in staggered rows, sewn to a leather backing."""
    leather, scale_m = mats
    neck, sh = J['neck'], J['l-shoulder']
    def keep(c):
        if c.z < .965 or c.z > neck.z + .01: return False
        if on_arm(J, .02, 1.1, .075)(c) or abs(c.x) > .21: return False
        if c.z > sh.z + .01 and V((c.x, c.y - neck.y - .008, 0)).length < .074: return False
        return True
    coat = region_shell('L3_Coat', body, keep, .013, 10, .5, guard=.011); relax_rim(coat, 14)
    mod(coat, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(coat); add(coat, leather, 'skin')
    sl = region_shell('L3_CoatSleeves', body, on_arm(J, -.3, .5, .1), .017, 3, .5, guard=.015); relax_rim(sl, 10)
    mod(sl, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(sl); add(sl, leather, 'skin')
    rows = [sh.z - .015 - .018 * i for i in range(40) if sh.z - .015 - .018 * i > .968]
    spots = plate_rows(coat, rows, 40, .026, .026, stagger=True, mid=1.2)
    add(scale_mesh('L3_CoatScales', spots, .027, .028, (.0012, .0042), .9, .0009), scale_m, 'skin:L3_Coat')
    bvh = BVHTree.FromObject(sl, bpy.context.evaluated_depsgraph_get()); spots = []
    for sd in ('l', 'r'):   # on the sleeves the rows run round the arm and the scales hang towards the elbow
        S, E = J[f'{sd}-shoulder'], J[f'{sd}-elbow']; u = (E - S).normalized(); L = (E - S).length
        e1 = u.cross(V((0, 1, 0))).normalized(); e2 = u.cross(e1)
        for r, t in enumerate([-.26 + .018 / L * i for i in range(50) if -.26 + .018 / L * i < .47]):
            c = S + (E - S) * t
            for k in range(15):
                a = 2 * math.pi * (k + .5 * (r % 2)) / 15; d = e1 * math.cos(a) + e2 * math.sin(a)
                h = bvh.ray_cast(c + d * .3, -d, .35)
                if h[0] and h[1].dot(d) > .3: spots.append((h[0], h[1], 1.0, u))
    add(scale_mesh('L3_SleeveScales', spots, .025, .028, (.0012, .0042), .9, .0009), scale_m, 'skin:L3_CoatSleeves')
    return coat, sl

def coat_skirt(name, under, z0=.99, z1=.62, nr=80, nz=24):
    """The coat below the belt: stiff with its scales, so modelled rather than draped,
    falling from the widest point above each spot clear of the kilt beneath, and open at
    the front in a widening arch over the apron, its corners rounded up."""
    sf = Surf(under); bm = bmesh.new(); grid = []; prev = [0.0] * nr
    for j in range(nz + 1):
        t = j / nz; z = z0 - (z0 - z1) * t; row = []
        r = []
        for i in range(nr):
            a = 2 * math.pi * i / nr; d = V((math.sin(a), -math.cos(a), 0)); h = sf.hit(V((0, 0, z)), d)
            r.append(max(prev[i], (V((h[0].x, h[0].y, 0)).length if h else .16)))
        r = [(r[i - 1] + 2 * r[i] + r[(i + 1) % nr]) / 4 for i in range(nr)]; prev = r
        for i in range(nr):
            a = 2 * math.pi * i / nr; rr = r[i] + .007 + .007 * t
            row.append(bm.verts.new((math.sin(a) * rr, -math.cos(a) * rr, z)))
        grid.append(row)
    def opening(a, z):   # inside the front opening: wider lower down, the hem's corners rounded up
        t = (z0 - z) / (z0 - z1); half = math.radians(15 + 25 * t ** .7)
        a = abs((a + math.pi) % (2 * math.pi) - math.pi)
        corner = math.radians(16) * max(0, 1 - (z - z1) / .06) ** 2
        return t > .04 and a < half + corner
    for j in range(nz):
        for i in range(nr):
            a = 2 * math.pi * (i + .5) / nr; z = z0 - (z0 - z1) * (j + .5) / nz
            if not opening(a, z): bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][(i + 1) % nr], grid[j][(i + 1) % nr]))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    ob = obj_from_bm(name, bm); relax_rim(ob, 2)
    return ob

def gold_bands(body, J, add, gold, leather):
    """Broad gold armlets where the sleeves end and ribbed gold wristlets."""
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    for sd in ('l', 'r'):
        S, E, W = J[f'{sd}-shoulder'], J[f'{sd}-elbow'], J[f'{sd}-hand']; n = sd.upper()
        band = limb_band(f'L3_Armlet{n}', bvh, S, E, .6, .046, .013)
        rims = curve_mesh(f'L3_ArmletRims{n}', [ring_round(bvh, S, E, t, .016) for t in (.52, .68)], .0035, cyclic=True, res=1)
        add(band, gold, 'skin'); add(rims, gold, 'skin')
        add(limb_band(f'L3_Wristlet{n}', bvh, E, W, .86, .05, .0045), gold, f'forearm.{n}')
        add(curve_mesh(f'L3_WristletRibs{n}', [ring_round(bvh, E, W, .8 + .12 * k / 6, .0072) for k in range(7)], .0026, cyclic=True, res=1), gold, f'forearm.{n}')

def wesekh(name, body, J, img):
    """The broad collar over the coat: a shell round the neck out over the shoulders, its
    UVs running round (u) and outward (v) so the painted rows of beads follow its shape."""
    neck, sh = J['neck'], J['l-shoulder']; N0 = V((0, neck.y + .005, sh.z + .045))
    def dist(c):
        q = c - N0; return math.sqrt(q.x ** 2 + (q.y * (1.0 if q.y < 0 else 1.12)) ** 2 + (q.z * 1.1) ** 2)
    def keep(c):
        if c.z > sh.z + .01 and V((c.x, c.y - neck.y - .008, 0)).length < .074: return False
        return dist(c) < .166 and c.z > sh.z - .12
    col = region_shell(name, body, keep, .03, 4, .5, guard=.028); relax_rim(col, 10)
    me = col.data; uvl = me.uv_layers.new(name='UV'); ds = [dist(v.co) for v in me.vertices]
    r0 = min(ds); r1 = max(ds)
    for lp in me.loops:
        c = me.vertices[lp.vertex_index].co
        uvl.data[lp.index].uv = ((math.atan2(c.x, -c.y) / (2 * math.pi)) % 1.0, 1 - (ds[lp.vertex_index] - r0) / (r1 - r0))
    wrap_seam(me, uvl)
    mod(col, 'SOLIDIFY', thickness=.004, offset=-1); bake_mods(col)
    return col

def sun_boss(tag, face, gold, add, y):
    """A gilded boss like the sun's disc, its rays standing out round it, on the shield's face."""
    bvh = BVHTree.FromObject(face, bpy.context.evaluated_depsgraph_get())
    h = bvh.ray_cast(V((0, y, 1)), V((0, 0, -1)), 2); z = h[0].z if h[0] else .09
    dome = lathe(tag + 'SunBoss', [(0, .032), (.025, .029), (.045, .019), (.058, .007), (.062, 0)], 32); dome.location = (0, y, z + .002); bake_obj_xform(dome)
    bm = bmesh.new()
    for i in range(18):
        a = 2 * math.pi * i / 18; d = V((math.cos(a), math.sin(a), 0)); sd = V((-d.y, d.x, 0)); L = .108 if i % 2 else .09
        base = V((0, y, z + .003)); vs = [bm.verts.new(base + d * .058 + sd * .012), bm.verts.new(base + d * L + V((0, 0, .001))), bm.verts.new(base + d * .058 - sd * .012),
                                            bm.verts.new(base + d * .07 + V((0, 0, .005)))]
        bm.faces.new((vs[0], vs[3], vs[1])); bm.faces.new((vs[1], vs[3], vs[2]))
    rays = obj_from_bm(tag + 'SunRays', bm, False); mod(rays, 'SOLIDIFY', thickness=.002, offset=-1); bake_mods(rays)
    add(dome, gold, 'later:shield'); add(rays, gold, 'later:shield')


# ── Kit ─────────────────────────────────────────────────────────────────────
def kit(body, J):
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    head_kit(body, J, add)
    bronze = H.m_bronze('Bronze', .2, 512)
    leather = m_leather('SandalLeather', '#5a3824', 256)
    sandals(body, J, add, leather, m_leather('Soles', '#4a2e1c', 256))
    # L1 and L2: the bead necklace; L1: the amulet on its cord
    for ob, mt in necklace('L12_Necklace', body, J, (H.m_flat('Beads', '#5a3420', .45), m_gold('BeadGold'))): add(ob, mt, 'skin')
    for ob, mt in pendant('L1_Amulet', body, J, J['l-shoulder'].z - .045, (H.m_flat('Amulet', '#d6c9ae', .7), m_leather('Cord', '#3a2416', 256))): add(ob, mt, 'skin')
    # a leather band on the left wrist (first tier)
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    el, wr = J['l-elbow'], J['l-hand']
    add(limb_band('L1_WristBand', bvh, el, wr, .86, .035, .004), m_leather('WristLeather', '#4a2c1a', 256), 'forearm.L')
    # L2: the corselet of plates
    corselet('L2_', body, J, add, (m_leather('Corselet', '#8a6038', 1024), m_leather('CorseletEdge', '#5a3a22', 256),
                                    m_plate_bronze('Plates', ('#34220f', '#4f3a1e', '#735632'), .4, 1024)))
    # L3: the coat of scales, the broad collar with its amulet, armlets, wristlets
    gold = m_gold('Gold', 512)
    scale_coat(body, J, add, (m_leather('CoatBacking', '#4a2e1a', 512), m_plate_bronze('Scales', ('#4a2c14', '#7a5530', '#a87e4c'), .3, 2048)))
    col = wesekh('L3_Collar', body, J, None); add(col, m_image('Collar', collar_image(), .45, 0, 1024), 'skin')
    for ob, mt in pendant('L3_Amulet', out['L3_CoatScales'][0], J, J['l-shoulder'].z - .07, (H.m_flat('Amulet3', '#d6c9ae', .7), gold)):
        if 'Cord' in ob.name: bpy.data.objects.remove(ob)
        else: add(ob, mt, 'skin')
    gold_bands(body, J, add, gold, m_leather('Strap', '#5a3420', 256))
    # spears and shields, built about their own grips and put in the fists later
    ash = H.m_wood('Shaft')
    for ob, mt in spear('L12_Spear', 1.0, .52, (ash, bronze), (.28, .027)): add(ob, mt, 'later:spear')   # 1.9 m
    for ob, mt in spear('L3_Spear', 1.0, .49, (ash, bronze), (.38, .038), True, gold): add(ob, mt, 'later:spear')   # 2 m, a little longer than the others
    hide1 = m_cowhide('Cowhide1', '#ece6da', '#1c1714', 3.0, .47)
    grip_wood = H.m_wood('GripWood', 256)
    oval_shield('L1_', (hide1, m_cowhide('Cowhide1Back', '#e2dccf', '#1c1714', 3.4, .5, res=512), m_leather('Rawhide', '#c8b48a', 256), grip_wood), add)
    framed_shield('L2_', (m_cowhide('Cowhide2', '#f0e8dc', '#8e4c22', 2.8, .5, '#6a3418'), m_leather('HideInside', '#a07a52', 512),
                          m_leather('Edging', '#6a4428', 256), H.m_wood('Frame', 256)), add, .82, .185, .235, .4)
    hide3 = m_cowhide('Cowhide3', '#efebe4', '#1a1614', 2.6, .55)
    f3 = framed_shield('L3_', (hide3, m_cowhide('Cowhide3Back', '#e6e1d8', '#1a1614', 3.0, .55, res=512), gold, grip_wood), add, .9, .21, .22, .42,
                       rim=.012, frame=False)
    sun_boss('L3_', f3, gold, add, .03)
    return out


# ── Cloth and what lies over it ─────────────────────────────────────────────
def dress(body, J, items):
    def add(ob, mt, bind): items[ob.name] = (ob, mt, bind); return ob
    probe = trunk(body)
    linen = m_cloth('Linen', '#ebe6db', 700, .04)
    sk, ov, hem = kilt('L12_', probe, linen, add, m_kilt_under('LinenUnder', '#ebe6db', KILT['hem'], KILT['hem'] + KILT['arch'] + .01, KILT['arch_w']))
    add(kilt_tab('L12_KiltTab', [ov, sk]), linen, 'hang')
    add(kilt_knot('L12_KiltKnot', [sk]), linen, 'hang')
    add(belt('L12_Belt', [sk], KILT['belt'], .044), m_tooled('TooledBelt', 22, '#5a2c1a', '#b8844e', '#26140c'), 'skin')
    bronze = H.m_bronze('DaggerBronze', .15, 256); sheath_m = m_leather('Sheath', '#4a2a18', 256)
    sf = Surf([sk]); a = math.radians(50); d = V((math.sin(a), -math.cos(a), 0)); h = sf.hit(V((0, 0, .99)), d)
    at = tuple(h[0] + h[1] * .02) if h else (.17, -.08, 1.0)
    dagger('L1_Dagger', at, (math.radians(6), math.radians(-22), a), (sheath_m, bronze), add)
    a = math.radians(64); d = V((math.sin(a), -math.cos(a), 0)); h = sf.hit(V((0, 0, .985)), d)
    at = tuple(h[0] + h[1] * .03) if h else (.18, -.07, .985)
    khopesh('L2_', (H.m_bronze('KhopeshBronze', .1, 256), m_leather('KhopeshSheath', '#a0784c', 512), H.m_wood('KhopeshGrip', 256)), add,
            at, (math.radians(-14), math.radians(-6), a - math.pi / 2))
    # L3: the same kilt in pleated linen under the coat's skirt, with the apron hung in front
    pleated = m_pleated('PleatedLinen', '#efebe2')
    k3 = []
    for o in (sk, ov, hem):
        if o is None: continue
        c = link(o.copy()); c.data = o.data.copy(); c.name = o.name.replace('L12_', 'L3_'); add(c, pleated, 'hang'); k3.append(c)
        bm = bmesh.new(); bm.from_mesh(c.data)   # its top is under the coat
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > .972], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS'); bm.to_mesh(c.data); bm.free()
    add(apron('L3_Apron', k3), m_image('Apron', apron_image(), .55, 0, 512), 'hang')
    coat, sleeves, scales = (items[n][0] for n in ('L3_Coat', 'L3_CoatSleeves', 'L3_CoatScales'))
    skirt = coat_skirt('L3_CoatSkirt', k3 + [probe])
    spots = plate_rows(skirt, [.985 - .018 * i for i in range(21) if .985 - .018 * i > .615], 46, .026, .026, stagger=True)
    add(HM.edge_band('L3_SkirtEdge', skirt, HM.pick_lowest, .014, .006, probe), m_leather('Binding', '#3a2214', 256), 'hang')
    mod(skirt, 'SOLIDIFY', thickness=.003, offset=-1); bake_mods(skirt); add(skirt, items['L3_Coat'][1], 'hang')
    add(scale_mesh('L3_SkirtScales', spots, .027, .028, (.0012, .0042), .9, .0009), items['L3_CoatScales'][1], 'skin:L3_CoatSkirt')
    over = [scales, items['L3_SkirtScales'][0], coat, skirt]
    add(belt('L3_Belt', over, .982, .022, .004), m_leather('Belt3', '#3a2214', 256), 'skin')
    sf3 = Surf(over); pts = []
    for i in range(14):   # the coat's closure down the breast, a strip of leather over the scales
        z = J['l-shoulder'].z - .07 - (J['l-shoulder'].z - .07 - .985) * i / 13; hh = sf3.hit(V((0, 0, z)), V((0, -1, 0)))
        if hh: pts.append((hh[0] + hh[1] * .002, hh[1]))
    if len(pts) > 3: add(ribbon('L3_Closure', pts, .014, .004), m_leather('Closure', '#3a2214', 256), 'skin')
    add(kilt_knot('L3_KiltKnot', over, .985, .2), pleated, 'hang')
    a = math.radians(58); d = V((math.sin(a), -math.cos(a), 0)); h = sf3.hit(V((0, 0, .975)), d)
    at = tuple(h[0] + h[1] * .016) if h else (.19, -.08, .975)
    dagger('L3_Dagger', at, (math.radians(6), math.radians(-18), a), (sheath_m, bronze), add)
    bpy.data.objects.remove(probe)


# ── Rig, poses and moves ────────────────────────────────────────────────────
def grip_frame(J, s):
    """The rest-pose fist: the centre of the hole the fingers close round, the knuckle line
    (index to little finger, as the pose solver aligns it: H.HAND_REF), the palm's normal
    and the hand bone's direction."""
    knuck = sum((J[f'{s}-finger-{k}-2'] for k in (2, 3, 4, 5)), V()) / 4
    along = (knuck - J[f'{s}-hand']).normalized()
    k = J[f'{s}-finger-5-2'] - J[f'{s}-finger-2-2']; k = (k - along * k.dot(along)).normalized()
    palm = k.cross(along).normalized()
    if palm.x * (1 if s == 'l' else -1) > 0: palm = -palm   # in the rest pose the palms face the thighs
    wrist, along_m, palm_m = T.hand_frame(J, s)
    mcp = sum((J[f'{s}-finger-{k_}-1'] for k_ in (2, 3, 4, 5)), V()) / 4
    return mcp + palm_m * .021 - along_m * .006, k, palm, along

def skeleton(J):
    """The infantry skeleton and a bone for the spear, from the right fist's grip along
    the shaft (towards the point, the thumb's side of the fist)."""
    B = H.skeleton_spec(J)
    g, k, palm, along = grip_frame(J, 'r')
    B.append(('spear.R', g, g - k * .3, 'hand.R', False))
    return B

def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-.5, .8, -.4), pt=(-.02, -.02, 1), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': tuple(-x for x in pt), 'fist': 0, **kw}   # pt: where the spear points
    def armL(w, hint=(.6, .7, -.3), bar=(.62, .78, 0), wrist=(-.2, .08, 0), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': bar, 'wrist': wrist, 'fist': 0, **kw}   # bar: the shield's grip, along the knuckles
    base = {'hips': {'loc': (0, 0, -.012)}, 'chest': {'rot': (.03, 0, 0)}, 'head': {'rot': (-.02, 0, 0)},
            'ik_foot.L': {'loc': (-.045, -.01, 0), 'rot': (0, 0, .12)}, 'ik_foot.R': {'loc': (.045, .01, 0), 'rot': (0, 0, -.12)},
            'armR': armR((-.21, -.19, -.31)), 'armL': armL((.14, -.07, -.48))}
    def st(**over):
        Pp = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): Pp[k] = v if k.startswith('arm') or k in ('knee', 'spear') else {**Pp.get(k, {}), **v}
        return Pp
    return st, armR, armL

def hang_weights(ob, z_top=1.02, z_bot=.84, legs=1.0, iters=3):
    """A skirt hangs from the waist: there it follows the hips alone, and towards the hem it
    takes more of the thighs' weights from the body beneath (up to `legs`), the weights then
    smoothed over the cloth so it stretches evenly between the legs instead of tearing."""
    me = ob.data; names = {g.index: g.name for g in ob.vertex_groups}
    if 'hips' not in [g.name for g in ob.vertex_groups]: ob.vertex_groups.new(name='hips')
    W = []
    for v in me.vertices:
        t = max(0, min(1, (z_top - v.co.z) / (z_top - z_bot))); f = legs * t * t * (3 - 2 * t)
        w = {names[g.group]: g.weight * f for g in v.groups}
        w['hips'] = w.get('hips', 0) + (1 - f); W.append(w)
    nbr = [[] for _ in me.vertices]
    for e in me.edges: a, b = e.vertices; nbr[a].append(b); nbr[b].append(a)
    for _ in range(iters):
        new = []
        for i, w in enumerate(W):
            if not nbr[i]: new.append(w); continue
            acc = {k: .5 * x for k, x in w.items()}
            for j in nbr[i]:
                for k, x in W[j].items(): acc[k] = acc.get(k, 0) + .5 * x / len(nbr[i])
            new.append(acc)
        W = new
    for g in list(ob.vertex_groups): ob.vertex_groups.remove(g)
    for i, w in enumerate(W):
        tot = sum(w.values()) or 1
        for k, x in w.items():
            if x / tot > .01: (ob.vertex_groups.get(k) or ob.vertex_groups.new(name=k)).add([i], x / tot, 'REPLACE')

def make_action(rig, name, frames):
    """H.make_action, and the spear: 'slide' moves it along its shaft through the fist,
    'matrix' puts it anywhere (armature space), when it has left the hand."""
    rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True
    rig.animation_data.action = act
    for f, Pp in frames:
        H.pose(rig, Pp); sp = Pp.get('spear', {}); pb = rig.pose.bones['spear.R']
        if 'slide' in sp: pb.location = (0, sp['slide'], 0)
        if 'matrix' in sp: H._upd(); M = sp['matrix'].copy(); pb.matrix = M
        H._upd(); H.key_all(rig, f)
    return act

def actions(rig, J):
    """Idle, Walk, Run, Thrust (an underhand thrust from the hip, the spear slid forward
    through the fist), Block (the shield brought round in front), Hit and Death (he falls
    backwards and the spear drops from his hand)."""
    st, armR, armL = poses(J); A = []
    A.append(make_action(rig, 'Idle', [(1, st()), (30, st(hips={'loc': (0, 0, -.016)}, chest={'rot': (.04, 0, .01)}, head={'rot': (-.01, 0, .05)},
                                                            armR=armR((-.21, -.19, -.315)), armL=armL((.14, -.07, -.485)))), (60, st())]))
    # Walk: the spear carried upright just clear of the ground, the shield swinging a little
    def W(fl, fr, zl, zr, hz, sw):
        return st(**{'ik_foot.L': {'loc': (-.045, fl, zl), 'rot': (0, 0, .1)}, 'ik_foot.R': {'loc': (.045, fr, zr), 'rot': (0, 0, -.1)},
                     'hips': {'loc': (0, 0, -.015 + hz), 'rot': (0, sw * .05, 0)}, 'chest': {'rot': (.04, -sw * .06, 0)}},
                  armR=armR((-.2, -.2 - .03 * sw, -.31), pt=(-.02, -.12 - .04 * sw, 1)), armL=armL((.14, -.07 + .07 * sw, -.47)), spear={'slide': .07})
    A.append(make_action(rig, 'Walk', [(1, W(-.24, .22, 0, 0, -.014, 1)), (7, W(-.01, -.01, 0, .1, .014, 0)), (13, W(.22, -.24, 0, 0, -.014, -1)),
                                       (19, W(-.01, -.01, .1, 0, .014, 0)), (25, W(-.24, .22, 0, 0, -.014, 1))]))
    # Run: leaning into the stride, the spear held low and slanting forward, the shield arm pumping
    def R(fl, fr, zl, zr, hz, s):
        return st(**{'ik_foot.L': {'loc': (-.05, fl, zl)}, 'ik_foot.R': {'loc': (.05, fr, zr)}, 'hips': {'loc': (0, .0, hz), 'rot': (.16, s * .07, 0)}},
                  chest={'rot': (.3, -s * .08, 0)}, head={'rot': (-.24, 0, 0)},
                  armR=armR((-.16, -.2 - .1 * s, -.3), hint=(-.6, .8, -.2), pt=(.05, -.85, .5)), armL=armL((.1, -.12 + .14 * s, -.32), hint=(.3, .9, -.3), bar=(.75, .65, -.1)),
                  spear={'slide': .32})
    A.append(make_action(rig, 'Run', [(1, R(-.27, .36, 0, .22, -.03, 1)), (5, R(.0, -.06, 0, .3, -.05, 0)), (9, R(.36, -.27, .22, 0, -.03, -1)),
                                      (13, R(-.06, .0, .3, 0, -.05, 0)), (17, R(-.27, .36, 0, .22, -.03, 1))]))
    # Thrust: the spear lowered to the hip, slid forward through the fist, driven out with a step
    step = {'ik_foot.L': {'loc': (-.04, -.3, 0), 'rot': (0, 0, .1)}}
    guard = armL((.05, -.2, -.36), hint=(.5, .6, -.5), bar=(.85, .5, 0))
    A.append(make_action(rig, 'Thrust', [
        (1, st()),
        (7, st(chest={'rot': (-.04, 0, .3)}, hips={'loc': (0, .05, -.04), 'rot': (0, 0, .12)}, head={'rot': (0, 0, -.25)},
               armR=armR((-.12, .12, -.3), hint=(-.6, .6, -.4), pt=(-.04, -1, .14)), armL=guard, spear={'slide': .42})),
        (11, st(chest={'rot': (.18, 0, -.16)}, hips={'loc': (0, -.14, -.09), 'rot': (0, 0, -.06)}, head={'rot': (.02, 0, .14)}, **step,
                armR=armR((.0, -.46, -.18), hint=(-.8, .4, -.3), pt=(.0, -1, .1)), armL=guard, spear={'slide': .5})),
        (16, st(chest={'rot': (.16, 0, -.14)}, hips={'loc': (0, -.13, -.09), 'rot': (0, 0, -.05)}, head={'rot': (.02, 0, .12)}, **step,
                armR=armR((.0, -.43, -.19), hint=(-.8, .4, -.3), pt=(.0, -1, .1)), armL=guard, spear={'slide': .5})),
        (21, st(chest={'rot': (.04, 0, .1)}, hips={'loc': (0, -.02, -.04)}, armR=armR((-.16, -.12, -.3), pt=(-.02, -.5, .8)), spear={'slide': .2})),
        (28, st())]))
    # Block: the shield brought round in front of the body, crouching behind it
    blk = dict(hips={'loc': (0, .03, -.1)}, chest={'rot': (.12, 0, -.12)}, head={'rot': (.06, 0, .1)},
               **{'ik_foot.L': {'loc': (-.04, -.16, 0), 'rot': (0, 0, .1)}, 'ik_foot.R': {'loc': (.045, .1, 0), 'rot': (0, 0, -.2)}},
               armL=armL((-.1, -.3, -.4), hint=(.2, -1, .6), bar=(1, 0, 0), wrist=(0, 0, 0)), armR=armR((-.22, -.08, -.3), pt=(-.05, -.25, 1)), spear={'slide': .1})
    A.append(make_action(rig, 'Block', [(1, st()), (6, st(**blk)), (14, st(**blk)), (20, st())]))
    A.append(make_action(rig, 'Hit', [(1, st()),
        (4, st(chest={'rot': (-.25, 0, .18)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, .08, -.05)}, armL=armL((.17, .02, -.38)), armR=armR((-.23, -.12, -.3)))),
        (9, st(chest={'rot': (-.1, 0, .08)}, head={'rot': (-.12, 0, 0)}, hips={'loc': (0, .03, -.03)})), (17, st())]))
    # Death: he doubles over, falls backwards and lets the spear go, which drops beside him
    a = V((-.25, -1, 0)).normalized(); x = V((0, 0, 1)).cross(a).normalized()
    ground = Matrix((x, a, x.cross(a))).transposed().to_4x4(); ground.translation = V((-.66, .25, .016))
    m = (V((0, 0, 1)) + a).normalized(); xm = V((0, 0, 1)).cross(m).normalized()
    mid = Matrix((xm, m, xm.cross(m))).transposed().to_4x4(); mid.translation = V((-.52, .08, .62))
    fall = dict(chest={'rot': (-.1, 0, .1)}, hips={'loc': (0, 0, -.1)}, armR=armR((-.25, .05, -.15), hint=(-1, .2, -.3), pt=(0, -1, .1)), armL=armL((.2, -.05, -.3), hint=(1, .2, -.5)))
    A.append(make_action(rig, 'Death', [(1, st()),
        (8, st(chest={'rot': (.32, 0, .14)}, head={'rot': (.28, 0, 0)}, hips={'loc': (0, .02, -.2)}, armR=armR((-.2, -.15, -.32), pt=(-.15, -.3, 1)))),
        (14, st(root={'loc': (0, .12, 0), 'rot': (-.6, 0, .05)}, head={'rot': (-.2, 0, .1)}, **fall, spear={'matrix': mid})),
        (20, st(root={'loc': (0, .27, 0), 'rot': (-1.38, 0, .08)}, head={'rot': (-.3, 0, .2)}, **fall, spear={'matrix': ground})),
        (25, st(root={'loc': (0, .29, 0), 'rot': (-1.52, 0, .08)}, head={'rot': (-.4, 0, .2)}, **fall, spear={'matrix': ground})),
        (40, st(root={'loc': (0, .29, 0), 'rot': (-1.5, 0, .08)}, head={'rot': (-.45, 0, .25)}, **fall, spear={'matrix': ground}))]))
    rig.animation_data.action = A[0]
    return A

def place(rig, items):
    """In the idle pose: the spear through the right fist on its bone, its butt just
    clear of the ground; each shield's grip in the left fist, its face turned out."""
    PB = rig.pose.bones; J = JOINTS
    sp = PB['spear.R']; g = sp.head.copy(); ax = (sp.tail - sp.head).normalized()
    x = ax.orthogonal().normalized(); Ms = Matrix((x, ax.cross(x), ax)).transposed().to_4x4(); Ms.translation = g
    spears = {}
    for n, (ob, mt, b) in items.items():
        if b == 'later:spear': spears.setdefault(n.split('_')[0], []).append(ob)
    shift = {}
    for tag, obs in spears.items():   # each spear slid through the fist until its butt rests on the ground
        butt = min((Ms @ (ob.matrix_basis @ v.co)).z for ob in obs for v in ob.data.vertices)
        shift[tag] = Matrix.Translation(ax * (.006 - butt) / ax.z)
    hand = PB['hand.L']; D = (hand.matrix @ rig.data.bones['hand.L'].matrix_local.inverted())
    gr, k, palm, along = grip_frame(J, 'l')
    gw = D @ gr; kw = (D.to_3x3() @ k).normalized(); n = -(D.to_3x3() @ palm).normalized(); up = n.cross(kw)
    if up.dot(-(D.to_3x3() @ along)) < 0: kw = -kw; up = -up
    Mh = Matrix((kw, up, n)).transposed().to_4x4(); Mh.translation = gw
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        if bind == 'later:spear': ob.matrix_world = shift[name.split('_')[0]] @ Ms @ ob.matrix_basis; bone = 'spear.R'
        else: ob.matrix_world = Mh @ ob.matrix_basis; bone = 'hand.L'
        bpy.context.view_layer.update(); H.bind_rigid(ob, rig, bone)
    # the larger shields' strap: a loop round the forearm above the wrist, its ends tied to the board
    body = bpy.data.objects['Body']; bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    W = PB['hand.L'].head.copy(); E = PB['forearm.L'].head.copy(); u = (E - W).normalized()
    strap = H.m_flat('ShieldStrap', '#4a2c18', .6)
    for tag in ('L2_', 'L3_'):
        c = W + u * .075; ring = [V(p) for p in ring_round(bvh, W, E, .075 / (E - W).length, .012, 24)]
        pts = [(p, (p - c - u * (p - c).dot(u)).normalized()) for p in ring + ring[:1]]
        loop = ribbon(tag + 'ShieldStrap', pts, .024, .003)
        near = max(ring, key=lambda p: (p - c).dot(n))   # the side towards the board: two tails tied to it
        tails = []
        for sgn in (1, -1):
            a = near + u * sgn * .008; b = a + u * sgn * .012 + n * max(.004, (gw + n * .034 - a).dot(n))
            tails.append([(a.lerp(b, t / 4), n.cross(u).normalized()) for t in range(5)])
        objs = [loop] + [ribbon(tag + f'ShieldStrapTail{i}', tl, .02, .003) for i, tl in enumerate(tails)]
        for o in objs:
            o.data.materials.append(strap.m); H.bind_rigid(o, rig, 'hand.L')


# ── Build ───────────────────────────────────────────────────────────────────
JOINTS = {}
def build(bake=True):
    body, J = build_body(); JOINTS.update(J)
    items = kit(body, J)
    dress(body, J, items)
    items['Body'] = (body, m_skin(J), 'body')
    if bake: H.bake_textures(items)
    else:
        for name, (ob, mt, bind) in items.items(): ob.data.materials.clear(); ob.data.materials.append(mt.m)
    rig = H.build_armature(skeleton(J), J); rig.name = 'MedjayRig'; rig.data.name = 'MedjayRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for name, (ob, mt, bind) in items.items():
        if ob is body or bind.startswith('later:') or bind.startswith('skin:'): continue
        if bind in ('skin', 'hang'): H.bind_skin(ob, rig, body)
        else: H.bind_rigid(ob, rig, bind)
        if bind == 'hang': hang_weights(ob)
    for name, (ob, mt, bind) in items.items():   # plates and scales take their backing's weights
        if bind.startswith('skin:'): H.bind_skin(ob, rig, bpy.data.objects[bind[5:]])
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    place(rig, items)
    return rig, actions(rig, J)

if __name__ == '__main__':
    rig, acts = build()
    H.export(rig, os.path.join(OUT, 'medjay.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'medjay.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3): H.render(rig, os.path.join(OUT, f'medjay_L{lv}.png'), 'Idle', 1, lv)
    print('built', [a.name for a in acts])
