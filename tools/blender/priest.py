"""Realistic Priest of Thoth line (Kemet), built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/priest.py third_party/makehuman assets/models [--renders] [--nobake]

The priests of Thoth, the ibis-headed god of writing, wisdom, the moon and healing, kept
his great temple at Hermopolis (Khemenu) in the New Kingdom. Built on the infantry
pipeline (hoplite.py, medjay.py): the MakeHuman man at 1.72 m, a scholar's build (no
muscles deepened), medium brown, his head and face shaven; his fists are bent into the
mesh as for Talos, the right one round the staff and the left a little looser round a
roll of papyrus. Kit follows the reference sheets in refs/priest:
  Every tier  a long robe of white linen pressed in fine pleats: the bodice and its wide
              sleeves to the elbow grown from the body, wrapped over at the front with a
              V at the throat, the skirt to the lower calf draped with the cloth simulator
              in about a hundred knife pleats; a woven sash knotted at the front with its
              two ends hanging; sandals of woven papyrus
  L1 Priest of Thoth           a scribe's palette of wood tucked into the sash at the left
                               hip (two ink wells and the reed pens), a closed papyrus
                               scroll in the left hand, a wooden staff carved at the top
                               into an ibis head, a band of turquoise and gold below it
  L2 Veteran Priest of Thoth   the lector priest: two broad woven bands crossed over the
                               chest and the back, an open papyrus roll written in columns
                               of hieroglyphs in the left hand, the ibis staff
  L3 Elite Priest of Thoth     the high priest: the skin of a single leopard as a mantle
                               (its head lying over the left shoulder, a foreleg hanging
                               over the right side of the chest, the hide down the back to
                               the knees with the hind legs at its corners and the tail
                               down the middle), a broad collar of gold and turquoise, an
                               empty left fist, a staff topped by a gilded ibis standing
                               on a crescent moon under the moon's disc
Magic, for the effects the line grows into (one node per tier, shown with its tier, so a
renderer can hide or restyle it on its own): L1_Magic, the ibis head's eyes glowing
turquoise; L2_Magic, the same, and the hieroglyphs on the open roll lit gold with a soft
halo; L3_Magic, the moon disc lit silver-blue in a halo of light, and a soft glow round
each fist. They are emissive, unbaked materials (the halos nested see-through shells), each
node one skinned mesh riding the bones it belongs to (staff.R, hand.L, hand.R).
The staff rides on its own bone (staff.R) in the right fist, so a clip can slide it
through the hand and let it fall. The skirt, the sash's ends and the lower part of the
leopard skin hang from the hips, taking the legs' weights only towards the hem; the
mantle above the waist keeps to the trunk, so it stays on the shoulders when the arms rise.
Node tags: L1_, L2_, L3_ for one tier, L12_ for the first two (the ibis staff); the body,
robe, sash and sandals are untagged.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import talos as T
import minotaur as MT
import hamippoi as HM
import medjay as MJ
import peltast as P
from hoplite import link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat, m_cloth, m_leather
from peltast import curve_mesh, ribbon, Surf, relax_rim, bake_obj_xform, on_arm

# A man of letters rather than of the field, medium brown: set after medjay's own settings.
H.TARGETS = [('caucasian-male-young.target', .88), ('african-male-young.target', .1), ('asian-male-young.target', .02),
             ('universal-male-young-maxmuscle-averageweight.target', .2), ('universal-male-young-averagemuscle-minweight.target', .2)]
H.HEIGHT = 1.72
SC = H.SC
OUT = H.OUT
random.seed(17)
SCROLL = dict(mcp=1.15, pip=1.35, dip=.7, thumb=(.25, .45), tuck=True)   # the left fist, round a roll of papyrus


# ── Materials ───────────────────────────────────────────────────────────────
def m_skin(J):
    """medjay.m_skin (the brows and a shadow of stubble painted in) in a warmer medium
    brown, with the shaven scalp: a faint grey shadow where the hair would grow."""
    eye, head = J['l-eye'], J['head']
    m = MJ.m_skin(J)
    ramp = next(n for n in m.N if n.type == 'VALTORGB')
    for e, hx in zip(ramp.color_ramp.elements, ('#8a5c3e', '#9e6e4c', '#b1815c')): e.color = (*srgb(hx), 1)
    col = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    def rng(src, a, b):
        n = m.node('ShaderNodeMapRange', **{'From Min': a, 'From Max': b}); m.L.new(src, n.inputs['Value']); return n.outputs[0]
    def op(kind, a, b):
        n = m.node('ShaderNodeMath', operation=kind)
        for i, x in enumerate((a, b)):
            if hasattr(x, 'links'): m.L.new(x, n.inputs[i])
            else: n.inputs[i].default_value = x
        return n.outputs[0]
    ax = op('ABSOLUTE', sep.outputs['X'], 0)
    line = op('SUBTRACT', eye.z + .058, op('MULTIPLY', op('MAXIMUM', op('SUBTRACT', sep.outputs['Y'], eye.y + .02), 0), .62))   # the hairline, falling to the nape
    scalp = rng(op('SUBTRACT', sep.outputs['Z'], line), -.004, .008)
    ears = op('SUBTRACT', 1.0, op('MULTIPLY', rng(ax, .056, .066), rng(sep.outputs['Z'], eye.z + .036, eye.z + .026)))   # bare above the ears
    dots = m.ramp(m.noise(1500, 2, .5).outputs['Fac'], [(.4, (.4, .4, .4)), (.6, (1, 1, 1))])
    mask = op('MULTIPLY', op('MULTIPLY', op('MULTIPLY', scalp, ears), dots.outputs['Color']), .22)
    m.L.new(m.mix(col, srgb('#3e3430'), mask), m.bsdf.inputs['Base Color'])
    return m

def m_pleats(name, hexcol='#efebe2', res=1024, depth=.55):
    """White linen pressed in narrow pleats along the 'Pat' UV's u (one pleat per unit):
    each pleat shaded from its crest into the fold and given its relief in the bump."""
    m = m_cloth(name, hexcol, 700, .035, res)
    cloth_col = m.bsdf.inputs['Base Color'].links[0].from_socket
    weave_bump = m.bsdf.inputs['Normal'].links[0].from_node
    uv = m.node('ShaderNodeUVMap'); uv.uv_map = 'Pat'
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(uv.outputs['UV'], sep.inputs['Vector'])
    fr = m.node('ShaderNodeMath', operation='FRACT'); m.L.new(sep.outputs['X'], fr.inputs[0])
    d = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(fr.outputs[0], d.inputs[0]); d.inputs[1].default_value = .5
    tri = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(d.outputs[0], tri.inputs[0])   # .5 at the crest, 0 in the fold
    shade = m.ramp(tri.outputs[0], [(.0, (depth,) * 3), (.2, (.9,) * 3), (.5, (1, 1, 1))])
    m.L.new(m.mix(cloth_col, shade.outputs['Color'], 1.0, 'MULTIPLY'), m.bsdf.inputs['Base Color'])
    b = m.node('ShaderNodeBump', Strength=.6, Distance=.004); m.L.new(tri.outputs[0], b.inputs['Height'])
    m.L.new(weave_bump.outputs['Normal'], b.inputs['Normal']); m.L.new(b.outputs['Normal'], m.bsdf.inputs['Normal'])
    return m

def m_woven(name, base='#e4dbc9', line='#a3957d', res=512):
    """A sash woven in a small diamond twill: lines of darker thread crossing on the
    diagonals of the 'Pat' UV (u along the band, v across, one diamond per unit), a dot
    in each diamond."""
    m = Mat(name, res=res)
    uv = m.node('ShaderNodeUVMap'); uv.uv_map = 'Pat'
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(uv.outputs['UV'], sep.inputs['Vector'])
    def op(kind, a, b=None):
        nd = m.node('ShaderNodeMath', operation=kind)
        for i, x in enumerate((a, b)):
            if x is None: continue
            if hasattr(x, 'links'): m.L.new(x, nd.inputs[i])
            else: nd.inputs[i].default_value = x
        return nd.outputs[0]
    u, v = sep.outputs['X'], sep.outputs['Y']
    a = op('ABSOLUTE', op('SUBTRACT', op('FRACT', op('ADD', u, v)), .5))
    b = op('ABSOLUTE', op('SUBTRACT', op('FRACT', op('SUBTRACT', u, v)), .5))
    lines = op('MAXIMUM', op('GREATER_THAN', a, .4), op('GREATER_THAN', b, .4))
    dot = op('MULTIPLY', op('LESS_THAN', a, .1), op('LESS_THAN', b, .1))
    col = m.mix(srgb(base), srgb(line), op('MAXIMUM', lines, dot))
    grain = m.ramp(m.noise(400, 3, .6).outputs['Fac'], [(.3, (.86, .86, .86)), (.7, (1, 1, 1))])
    col = m.mix(col, grain.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .85, op('SUBTRACT', 1.0, op('MAXIMUM', lines, dot)), .35, .0012)
    return m

def m_straw(name, hexcol='#c4a86e', res=256):
    """Woven papyrus or palm fibre, for the sandals: a basket weave of flat strands."""
    m = Mat(name, res=res)
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=45.0, Distortion=1.0); m.L.new(m.coord.outputs['Object'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=45.0, Distortion=1.0); m.L.new(m.coord.outputs['Object'], w2.inputs['Vector'])
    k = m.node('ShaderNodeTexChecker', Scale=180.0); m.L.new(m.coord.outputs['Object'], k.inputs['Vector'])
    weave = m.mix(w1.outputs['Color'], w2.outputs['Color'], k.outputs['Fac'])
    c = srgb(hexcol)
    col = m.ramp(m.noise(30, 3, .6).outputs['Fac'], [(.3, tuple(x * .8 for x in c)), (.7, c)]).outputs['Color']
    col = m.mix(col, m.ramp(weave, [(.0, (.72, .72, .72)), (1, (1, 1, 1))]).outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .8, weave, .4, .0015)
    return m

def m_wood(name, cols=('#4a2c18', '#6a4226', '#7e5232'), res=512):
    """A dark hardwood, its grain running along Z (hoplite.m_wood in other tones)."""
    m = Mat(name, res=res)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (70, 70, 1.6)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=3.0, Detail=4.0); m.L.new(mp.outputs['Vector'], w.inputs['Vector'])
    col = m.ramp(w.outputs['Fac'], [(.2, srgb(cols[0])), (.6, srgb(cols[1])), (.9, srgb(cols[2]))])
    m.set(col.outputs['Color'], .45, w.outputs['Fac'], .1, .001)
    return m

def m_papyrus(name, res=512):
    """Papyrus: pale straw, with the strips of pith showing as faint stripes both ways."""
    m = Mat(name, res=res)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=60.0, Distortion=2.0, Detail=3.0); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    col = m.ramp(m.noise(25, 4, .6).outputs['Fac'], [(.3, srgb('#c9ad74')), (.7, srgb('#ddc590'))]).outputs['Color']
    col = m.mix(col, m.ramp(w.outputs['Fac'], [(.2, (.9, .88, .84)), (.8, (1, 1, 1))]).outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .75, w.outputs['Fac'], .15, .0008)
    return m

def m_rolled_end(name, res=256):
    """The end of a rolled papyrus: the turns of the sheet as rings round the 'Pat' UV's centre."""
    m = Mat(name, res=res)
    uv = m.node('ShaderNodeUVMap'); uv.uv_map = 'Pat'
    ln = m.node('ShaderNodeVectorMath', operation='LENGTH'); m.L.new(uv.outputs['UV'], ln.inputs[0])
    w = m.node('ShaderNodeTexWave', wave_type='RINGS', Scale=3.0, Distortion=1.5); m.L.new(uv.outputs['UV'], w.inputs['Vector'])
    col = m.ramp(w.outputs['Fac'], [(.2, srgb('#7a6038')), (.6, srgb('#cbb07a')), (.9, srgb('#d8bf88'))])
    m.set(col.outputs['Color'], .8, w.outputs['Fac'], .3, .0008)
    return m

def m_leopard(name, res=2048):
    """A leopard's coat: rosettes of broken black rings round a deeper tawny centre on
    golden fur, smaller solid spots where they crowd, paler towards the edges of the hide;
    the hair lying down the skin (bump)."""
    m = Mat(name, res=res)
    warp = m.noise(9, 3, .5)
    wv = m.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD'); m.L.new(warp.outputs['Color'], wv.inputs[0])
    wv.inputs[1].default_value = (.025, .025, .025); m.L.new(m.coord.outputs['Object'], wv.inputs[2])
    vor = m.node('ShaderNodeTexVoronoi', Scale=24.0); vor.inputs['Randomness'].default_value = .85; m.L.new(wv.outputs['Vector'], vor.inputs['Vector'])
    d = vor.outputs['Distance']
    ring = m.ramp(d, [(.2, (0, 0, 0)), (.25, (1, 1, 1)), (.36, (1, 1, 1)), (.41, (0, 0, 0))])
    broken = m.ramp(m.noise(70, 2, .5).outputs['Fac'], [(.4, (0, 0, 0)), (.47, (1, 1, 1))])
    centre = m.ramp(d, [(.17, (1, 1, 1)), (.22, (0, 0, 0))])
    small = m.node('ShaderNodeTexVoronoi', Scale=70.0); m.L.new(wv.outputs['Vector'], small.inputs['Vector'])
    dots = m.ramp(small.outputs['Distance'], [(.16, (1, 1, 1)), (.2, (0, 0, 0))])
    dots_where = m.ramp(m.noise(4, 2, .5).outputs['Fac'], [(.55, (0, 0, 0)), (.62, (1, 1, 1))])
    base = m.ramp(m.noise(5, 4, .55).outputs['Fac'], [(.3, srgb('#a46a24')), (.7, srgb('#c48a38'))]).outputs['Color']
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
    pale = m.node('ShaderNodeMapRange', **{'From Min': .23, 'From Max': .32}); m.L.new(ax.outputs[0], pale.inputs['Value'])
    base = m.mix(base, srgb('#e3c895'), pale.outputs[0])
    col = m.mix(base, srgb('#94601f'), m.mix((0, 0, 0), centre.outputs['Color'], .8))
    ink = m.mix(m.mix(ring.outputs['Color'], broken.outputs['Color'], 1.0, 'MULTIPLY'), dots.outputs['Color'], dots_where.outputs['Color'], 'LIGHTEN')
    col = m.mix(col, srgb('#1e140c'), ink)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (260, 260, 30)
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=6.0, Detail=3.0); m.L.new(mp.outputs['Vector'], hair.inputs['Vector'])
    m.set(col, .82, hair.outputs['Fac'], .35, .0015)
    return m

def m_vcol(name, rough=.8, res=1024, hair=True):
    """Fur painted vertex by vertex (the 'Col' attribute), with the hair in the bump."""
    m = Mat(name, res=res)
    at = m.node('ShaderNodeAttribute', attribute_name='Col')
    bump = None
    if hair:
        bump = m.node('ShaderNodeTexNoise', Scale=600.0, Detail=2.0); m.L.new(m.coord.outputs['Object'], bump.inputs['Vector']); bump = bump.outputs['Fac']
    m.set(at.outputs['Color'], rough, bump, .3, .001)
    return m

def m_glow(name, hexcol, alpha=1.0, strength=2.0, img=None):
    """Magic light: an emissive colour (or an image, its alpha cutting it out), see-through
    below alpha 1. Left unbaked (res 0), so the glTF keeps it as an emissive colour or
    texture; restyle it by changing the colour, strength or alpha here."""
    m = Mat(name, res=0); c = srgb(hexcol); b = m.bsdf
    b.inputs['Base Color'].default_value = (*c, 1); b.inputs['Roughness'].default_value = 1.0
    b.inputs['Emission Color'].default_value = (*c, 1); b.inputs['Emission Strength'].default_value = strength
    b.inputs['Specular IOR Level'].default_value = 0.0
    if img is not None:
        t = m.node('ShaderNodeTexImage'); t.image = img
        m.L.new(t.outputs['Color'], b.inputs['Base Color']); m.L.new(t.outputs['Color'], b.inputs['Emission Color']); m.L.new(t.outputs['Alpha'], b.inputs['Alpha'])
    elif alpha < 1: b.inputs['Alpha'].default_value = alpha
    if img is not None or alpha < 1:
        m.m.surface_render_method = 'BLENDED'; m.m.use_backface_culling = True
    return m

def rgba_image(name, im):
    """A PIL RGBA image as a packed Blender image (medjay.pil_image keeps no alpha)."""
    import numpy as np
    from PIL import Image
    img = bpy.data.images.new(name, im.width, im.height, alpha=True)
    a = np.asarray(im.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM), np.float32) / 255
    img.pixels.foreach_set(a.ravel()); img.pack(); img.alpha_mode = 'STRAIGHT'
    return img


# ── UV helpers: a pattern's own coordinates beside the map baked into ──────────
def pat_uv(ob, fn, period=None):
    """Fill a 'Pat' UV map from fn(face centre, vertex position) -> (u, v), in units of
    the pattern; faces straddling the wrap of a periodic u (period) get it continued."""
    me = ob.data; uvl = me.uv_layers.new(name='Pat')
    for f in me.polygons:
        c = f.center; uvs = [fn(c, me.vertices[me.loops[li].vertex_index].co) for li in f.loop_indices]
        if period:
            us = [u for u, v in uvs]
            if max(us) - min(us) > period / 2: uvs = [(u + period if u < period / 2 else u, v) for u, v in uvs]
        for li, uv in zip(f.loop_indices, uvs): uvl.data[li].uv = uv
    return uvl

def bake_uv(ob):
    """A smart projection to bake into, made the active map beside 'Pat' (which the
    baked material no longer needs and the build removes before export)."""
    me = ob.data; uv = me.uv_layers.new(name='UVMap'); me.uv_layers.active = uv; uv.active_render = True
    H.smart_uv(ob)

def union(name, objs):
    """One mesh holding copies of several (for ray casts and tube building)."""
    bm = bmesh.new()
    for o in objs: bm.from_mesh(o.data)
    return obj_from_bm(name, bm)

def smooth(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


# ── Body ────────────────────────────────────────────────────────────────────
def build_body():
    """The MakeHuman man, his profile given a straighter nose (as medjay.build_body), the
    right fist bent closed round the staff and the left a little looser round a scroll."""
    body, J = H.build_body()
    eye, mouth = J['l-eye'], J['mouth']
    for v in body.data.vertices:
        p = v.co
        if abs(p.x) < .02 and p.y < eye.y - .005 and mouth.z + .02 < p.z < eye.z + .01:
            w = (1 - abs(p.x) / .02) * max(0, min(1, (p.z - mouth.z - .02) / .03)) * max(0, min(1, (eye.z + .01 - p.z) / .015))
            v.co.y -= .0024 * w
    body.data.update()
    T.clench(body, J, 'r', **MT.HAFT)
    T.clench(body, J, 'l', **SCROLL)
    return body, J

def head_kit(body, J, add):
    """Only the eyes (peltast.head_kit's): the head and face are shaven."""
    got = {}; eye_m = MJ.m_eye()
    P.head_kit(body, J, lambda ob, mt, bind: got.__setitem__(ob.name, (ob, mt)), [], volume=0)
    for n, (ob, mt) in got.items():
        if n.startswith('Eye'): add(ob, eye_m, 'head')
        else: bpy.data.objects.remove(ob)


# ── The robe: bodice and sleeves from the body, the skirt draped in pleats ────
ROBE = dict(vee=1.29, slope=2.4, waist=.975, top=1.035, hem=.19)
BINDREF = {}   # robe parts weighted from a copy of themselves before the sleeves flared

def sleeve_frame(J, s):
    S, E = J[f'{s}-shoulder'], J[f'{s}-elbow']; u = (E - S).normalized()
    e1 = u.cross(V((0, 0, 1))).normalized(); e2 = u.cross(e1)
    return S, E, u, e1, e2

def bodice(name, body, J):
    """The robe above the sash: a loose shell grown from the body over the trunk and the
    upper arms, open in a V at the throat where the wrap crosses; the sleeves flare out
    wide to the elbow and their undersides droop. A copy made before the flare is kept
    (BINDREF), which the skin weights are taken from, so the sleeves follow the arms."""
    neck, sh = J['neck'], J['l-shoulder']
    arm = on_arm(J, -.35, 1.0, .12)
    def keep(c):
        if c.z < ROBE['waist'] or c.z > neck.z + .02: return False
        if c.z > sh.z and V((c.x, c.y - neck.y - .008, 0)).length < .078: return False   # the neck
        if c.y < neck.y - .01 and c.z > ROBE['vee'] + ROBE['slope'] * abs(c.x): return False   # the V of the wrap
        return abs(c.x) < .19 or arm(c)
    ob = region_shell(name, body, keep, .016, 8, .5, guard=.014); relax_rim(ob, 12)
    mod(ob, 'SOLIDIFY', thickness=.0025, offset=1); bake_mods(ob)
    ref = link(ob.copy()); ref.data = ob.data.copy(); ref.name = name + 'Bind'; BINDREF[name] = ref
    for v in ob.data.vertices:
        p = v.co.copy()
        for s, sg in (('l', 1), ('r', -1)):
            S, E, u, e1, e2 = sleeve_frame(J, s); L = (E - S).length; t = (p - S).dot(u) / L
            r = p - (S + u * t * L)
            if p.x * sg < .12 or t < .05 or r.length > .095: continue
            k = smooth((t - .08) / .92); rn = r.normalized()
            v.co = p + rn * .05 * k + V((0, 0, -.026 * k * (.35 + max(0, -rn.z))))
    ob.data.update()
    def coord(c, p):   # pleats round the trunk (vertical) and round each sleeve (along the arm)
        for s, sg in (('l', 1), ('r', -1)):
            S, E, u, e1, e2 = sleeve_frame(J, s); L = (E - S).length; t = (c - S).dot(u) / L
            if c.x * sg > .14 and t > .1 and (c - (S + u * t * L)).length < .14:
                q = p - S; return ((math.atan2(q.dot(e2), q.dot(e1)) / (2 * math.pi)) % 1.0 * 32 + 100, q.dot(u))
        return ((math.atan2(p.x, -p.y) / (2 * math.pi)) % 1.0 * 84, p.z)
    pat_uv(ob, coord, 32)   # the trunk's 84 and the sleeves' 32 pleats wrap on whole numbers
    bake_uv(ob)
    return ob

EDGE = [(1.43, .066), (1.296, .006), (1.12, -.06), (.96, -.118)]   # the outer turn's edge: (z, x) down the front

def edge_x(z):
    for (z0, x0), (z1, x1) in zip(EDGE, EDGE[1:]):
        if z >= z1: return x0 + (x1 - x0) * (z0 - z) / (z0 - z1)
    return EDGE[-1][1]

def wrap_edges(robe, mat, add):
    """The wrap's outer turn, from the left side of the neck down the V and on across the
    body to the right hip: the cloth on its side stands a few millimetres proud (a soft
    step), with a narrow folded hem along the edge."""
    bm = bmesh.new(); bm.from_mesh(robe.data); bm.normal_update()
    for v in bm.verts:
        p = v.co
        if p.y > -.02 or abs(p.x) > .2 or p.z < .95: continue
        v.co = p + v.normal * .0035 * smooth((p.x - edge_x(p.z)) / .008) * smooth((-p.y - .02) / .04)
    bm.to_mesh(robe.data); bm.free(); robe.data.update()
    sf = Surf([robe]); pts = []
    for i in range(41):
        z = EDGE[0][0] - (EDGE[0][0] - EDGE[-1][0]) * i / 40; h = sf.hit(V((edge_x(z) + .004, 0, z)), V((0, -1, 0)))
        if h: pts.append((h[0] + h[1] * .001, h[1]))
    add(ribbon('RobeEdge', pts, .011, .003), mat, 'skin')

def robe_skirt(name, probe, robe, top=ROBE['top'], hem=ROBE['hem'], nr=200, nz=44):
    """The skirt from the waist to the lower calf: a tube falling straight from the widest
    point above each spot, pressed in knife pleats (the columns alternately out and in),
    then draped with the cloth simulator, which keeps the pleats (stiff bending) while it
    settles the cloth on the hips and seat."""
    tmp = union('SkirtProbe', [probe, robe])
    sk = MJ.hanging_tube(name, tmp, top, hem, gap=.03, nr=nr, nz=nz)
    bpy.data.objects.remove(tmp)
    vs = sk.data.vertices
    for j in range(nz + 1):   # each row bridged over hollows (the small of the back, between the buttocks), as cloth hangs
        r = [V((vs[j * nr + i].co.x, vs[j * nr + i].co.y, 0)).length for i in range(nr)]
        r = [max(r[(i + k) % nr] for k in range(-6, 7)) for i in range(nr)]
        for _ in range(3): r = [(r[i - 1] + 2 * r[i] + r[(i + 1) % nr]) / 4 for i in range(nr)]
        for i in range(nr):
            v = vs[j * nr + i]; d = V((v.co.x, v.co.y, 0)).normalized(); v.co = V((d.x * r[i], d.y * r[i], v.co.z))
    for v in sk.data.vertices:
        i, j = v.index % nr, v.index // nr; d = V((v.co.x, v.co.y, 0)).normalized()
        v.co += d * (.0032 + .0026 * j / nz) * (1 if i % 2 == 0 else -1)
    pat_uv(sk, lambda c, p: ((math.atan2(p.x, -p.y) / (2 * math.pi)) % 1.0 * nr / 2, p.z), nr / 2)
    MJ.drape_on(name, sk, lambda c: c.z > top - .025, [probe], frames=50, mass=.3, bend=2.0, thickness=.002)
    bake_uv(sk)
    return sk


# ── The sash, the palette and the lector's bands ────────────────────────────
SASH = dict(z=1.0, w=.085, knot=-.035)

def strip(name, pts_normals, width, thick=.004, pitch=.011):
    """A flat band through points lying on a surface (peltast.ribbon) with 'Pat' UVs in
    pattern units, u along it and v across."""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('Pat'); rows = []; acc = 0.0
    for i, (p, nrm) in enumerate(pts_normals):
        nxt = pts_normals[min(i + 1, len(pts_normals) - 1)][0]; prv = pts_normals[max(i - 1, 0)][0]
        w = (nxt - prv).normalized().cross(nrm).normalized()
        wd = width(i / (len(pts_normals) - 1)) if callable(width) else width
        if i: acc += (p - pts_normals[i - 1][0]).length
        rows.append((bm.verts.new(p - w * wd / 2), bm.verts.new(p + w * wd / 2), acc, wd))
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        f = bm.faces.new((a[0], b[0], b[1], a[1]))
        for lp, uv in zip(f.loops, ((a[2], -a[3] / 2), (b[2], -b[3] / 2), (b[2], b[3] / 2), (a[2], a[3] / 2))): lp[uvl].uv = (uv[0] / pitch, uv[1] / pitch)
    ob = obj_from_bm(name, bm); mod(ob, 'SOLIDIFY', thickness=thick, offset=1); bake_mods(ob)
    bake_uv(ob)
    return ob

def sash(under, skirt, mat, add):
    """The woven sash: a band round the waist, a knot at the front a little to the right,
    and its two ends hanging from the knot to mid-thigh."""
    sf = Surf(under); z, w = SASH['z'], SASH['w']
    pts = []
    for i in range(97):
        a = 2 * math.pi * i / 96; d = V((math.sin(a), -math.cos(a), 0)); h = sf.hit(V((0, 0, z)), d)
        pts.append(((h[0] + h[1] * .005) if h else d * .18 + V((0, 0, z)), V((d.x, d.y, 0))))
    band = strip('Sash', pts, w, .004)
    add(band, mat, 'skin')
    sfb = Surf([band]); h = sfb.hit(V((SASH['knot'], 0, z)), V((0, -1, 0)))
    c = (h[0] if h else V((SASH['knot'], -.15, z))) + V((0, -.012, -.004))
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1, matrix=Matrix.Translation(c) @ Matrix.Diagonal((.032, .016, .026, 1)))
    for v in bm.verts:   # gathered folds round the knot
        q = v.co - c; a = math.atan2(q.z, q.x); v.co += q.normalized() * .0025 * math.sin(a * 6) * (q.y < 0)
    knot = obj_from_bm('SashKnot', bm)
    pat_uv(knot, lambda cc, p: (math.atan2(p.z - c.z, p.x - c.x) * 6, (p.y - c.y) / .011)); bake_uv(knot)
    add(knot, mat, 'skin')
    sk = Surf([skirt]); bvh = BVHTree.FromObject(skirt, bpy.context.evaluated_depsgraph_get())
    for nm, x0, dx, z1 in (('SashEndR', SASH['knot'] - .022, -.016, .6), ('SashEndL', SASH['knot'] + .02, .012, .64)):
        path = []
        for i in range(25):
            t = i / 24; zz = c.z - .018 - (c.z - .018 - z1) * t; x = x0 + dx * t
            hh = sk.hit(V((x, 0, zz)), V((0, -1, 0)))
            p = hh[0] if hh else V((x, -.16, zz)); nrm = V((0, -1, 0))
            path.append((p + nrm * (.006 + .016 * (1 - t) ** 3), nrm))
        add(strip(nm, path, lambda t: .056 + .006 * t, .003), mat, 'hang')
    return band, knot

def palette(tag, under, skirt, mats, add, a=math.radians(42)):
    """The scribe's palette tucked into the sash at the left hip: a long board of wood with
    a handle at its top end, two wells of black and red ink, and the reed pens in their
    slot, standing up out of it. Built in a frame of its own (face to -Y, top up) and laid
    along the robe below the sash."""
    wood, black, red, reed = mats
    d = V((math.sin(a), -math.cos(a), 0))
    h0 = Surf(under).hit(V((0, 0, SASH['z'])), d); h1 = Surf([skirt]).hit(V((0, 0, .85)), d)
    top = (h0[0] + h0[1] * .014) if h0 else V((.12, -.13, 1.0)); n = h0[1] if h0 else -d
    bot = (h1[0] + h1[1] * .013) if h1 else top + V((0, 0, -.15))
    zax = (top - bot).normalized(); yax = -(n - zax * n.dot(zax)).normalized(); xax = yax.cross(zax)
    M = Matrix((xax, yax, zax)).transposed().to_4x4(); M.translation = top + zax * .03
    parts = []
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((0, 0, -.1)) @ Matrix.Diagonal((.074, .012, .2, 1)))
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((0, 0, .03)) @ Matrix.Diagonal((.03, .012, .07, 1)))
    board = obj_from_bm(tag + 'PaletteBoard', bm, False); mod(board, 'BEVEL', width=.004, segments=2); bake_mods(board)
    parts.append((board, wood))
    for x, mt in ((-.016, black), (.012, red)):
        well = lathe(tag + 'PaletteInk' + ('K' if mt is black else 'R'), [(0, .0005), (.0085, .0005), (.0095, -.001)], 20)
        well.rotation_euler = (math.radians(90), 0, 0); well.location = (x, -.0062, -.03); bpy.context.view_layer.update(); bake_obj_xform(well)
        parts.append((well, mt))
    pens = []
    for i, x in enumerate((.02, .026, .032)):   # the reed pens, in a slot down the right of the board
        pens.append([(x, -.0075, -.16 + .01 * i), (x + .001 * i, -.0075, .065 + .012 * i)])
    parts.append((curve_mesh(tag + 'PalettePens', pens, .0021, res=1), reed))
    for o, mt in parts:
        o.matrix_world = M @ o.matrix_basis; bpy.context.view_layer.update(); bake_obj_xform(o); add(o, mt, 'hips')

def lector_bands(tag, under, mat, add):
    """The lector priest's broad sash, worn as two bands crossed over the chest and over the
    back, each passing over one shoulder; laid on the robe by ray casts and smoothed."""
    sf = Surf(under); bvh = [BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get()) for o in under]
    for k, s in enumerate((1, -1)):
        pts = []
        for i in range(17):   # the front: from under the waist sash at the far hip up to the shoulder
            t = i / 16; z = .975 + (1.3 - .975) * t; x = -s * .115 + (s * .19) * t
            h = sf.hit(V((x, 0, z)), V((0, -1, 0))); pts.append(h)
        for i in range(1, 12):   # over the shoulder
            ph = math.pi * i / 12; h = sf.hit(V((s * .1, -.005, 1.3)), V((0, -math.cos(ph), math.sin(ph))), .35); pts.append(h)
        for i in range(17):   # the back, down to the far hip
            t = i / 16; z = 1.3 - (1.3 - .975) * t; x = s * .075 - (s * .19) * t
            h = sf.hit(V((x, 0, z)), V((0, 1, 0))); pts.append(h)
        P = [h[0] for h in pts if h]
        for _ in range(4): P = [P[0]] + [(P[i - 1] + 2 * P[i] + P[i + 1]) / 4 for i in range(1, len(P) - 1)] + [P[-1]]
        pn = []
        for p in P:
            best = None
            for b in bvh:
                loc, no, fi, dd = b.find_nearest(p)
                if loc is not None and (best is None or dd < best[2]): best = (loc, no, dd)
            pn.append((p + best[1] * (.004 + .0035 * k), best[1]))
        add(strip(f'{tag}LectorBand{k}', pn, .074, .004), mat, 'skin')


# ── The leopard skin (third tier) ───────────────────────────────────────────
PELT = dict(th=76, nth=39, fan=9, rows=34, bottom=.38, off=.036)

def pelt_edge(th):
    """The hide's lower edge at a bearing th (degrees from straight behind): the rump in
    the middle, the hind legs hanging lower at the corners, the flanks rising at the sides."""
    tab = [(0, .5), (14, .52), (30, .55), (38, .47), (43, .39), (53, .39), (58, .47), (64, .6), (76, .74)]
    a = abs(th)
    for (a0, z0), (a1, z1) in zip(tab, tab[1:]):
        if a <= a1: return z0 + (z1 - z0) * smooth((a - a0) / (a1 - a0))
    return tab[-1][1]

def pelt(name, body, probe, under, J):
    """The hide laid as a mantle over the shoulders and hanging down the back: a grid of
    columns at bearings round the back, each first fanned from a point in the chest over
    the shoulder (rays out through the skin, kept clear of the robe), then falling straight
    from the widest point above, clear of the robe, sash and seat; cut to the outline of
    the skin (pelt_edge)."""
    neck = J['neck']; c = V((0, .0, 1.25)); P_ = PELT
    dg = bpy.context.evaluated_depsgraph_get()
    bvh_b = BVHTree.FromObject(body, dg); out_sf = Surf(under); probe_sf = Surf([probe])
    grid = []
    for i in range(P_['nth']):
        th = math.radians(-P_['th'] + 2 * P_['th'] * i / (P_['nth'] - 1)); d = V((math.sin(th), math.cos(th), 0))
        def fan(al):
            e = d * math.sin(al) + V((0, 0, math.cos(al))); h = bvh_b.ray_cast(c, e, .6)
            return (h[0] + e * P_['off']) if h[0] else c + e * .2
        a0 = math.radians(14)
        while a0 < math.radians(60):
            p = fan(a0)
            if p.z < neck.z + .04 and V((p.x, p.y - neck.y, 0)).length > .11: break
            a0 += math.radians(2)
        col = [fan(a0 + (math.radians(70) - a0) * k / (P_['fan'] - 1)) for k in range(P_['fan'])]
        r = V((col[-1].x, col[-1].y, 0)).length; z0 = col[-1].z
        for k in range(1, P_['rows'] + 1):
            z = z0 - (z0 - P_['bottom']) * k / P_['rows']; o = V((0, 0, z))
            hp = probe_sf.hit(o, d); ho = out_sf.hit(o, d)
            need = max(V((hp[0].x, hp[0].y, 0)).length + P_['off'] if hp else 0, V((ho[0].x, ho[0].y, 0)).length + .012 if ho else 0)
            r = max(r * .985, need); col.append(o + d * r)
        grid.append((math.degrees(th), col))
    bm = bmesh.new(); vs = [[bm.verts.new(p) for p in col] for th, col in grid]
    for i in range(len(vs) - 1):
        th = (grid[i][0] + grid[i + 1][0]) / 2
        for k in range(len(vs[i]) - 1):
            zc = (vs[i][k].co.z + vs[i + 1][k + 1].co.z) / 2
            if zc > pelt_edge(th): bm.faces.new((vs[i][k], vs[i][k + 1], vs[i + 1][k + 1], vs[i + 1][k]))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(name, bm); relax_rim(ob, 6)
    mod(ob, 'SUBSURF', levels=1, render_levels=1); mod(ob, 'SOLIDIFY', thickness=.006, offset=-1); bake_mods(ob)
    return ob

def paw(name, at, fwd, up, s=1.0):
    """A paw at the end of a leg of the hide: a pad with four toes, flattened."""
    bm = bmesh.new(); x = fwd.cross(up).normalized()
    M = Matrix((x, fwd, up)).transposed().to_4x4(); M.translation = at
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=1, matrix=M @ Matrix.Diagonal((.03 * s, .032 * s, .016 * s, 1)))
    for k in range(4):
        q = V(((k - 1.5) * .0135 * s, .03 * s - abs(k - 1.5) * .004 * s, 0))
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1, matrix=M @ Matrix.Translation(q) @ Matrix.Diagonal((.0085 * s, .011 * s, .011 * s, 1)))
    return obj_from_bm(name, bm)

def leopard_head(name):
    """The leopard's head as it is left on a hide: the skull's shape, flattened beneath,
    built along local -Y (the muzzle) with Z up; ears, glass eyes and the nose apart.
    Painted vertex by vertex: tawny with small black spots over the brow and crown,
    white on the muzzle, chin and lips, a dark line round the mouth."""
    W = [(-1, .042), (-.6, .058), (-.2, .066), (.15, .058), (.45, .04), (.75, .03), (1, .018)]
    Hh = [(-1, .028), (-.5, .04), (0, .04), (.4, .031), (.8, .026), (1, .016)]
    def lerp(tab, s):
        for (a, x), (b, y) in zip(tab, tab[1:]):
            if s <= b: return x + (y - x) * (s - a) / (b - a)
        return tab[-1][1]
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=36, v_segments=24, radius=1, matrix=Matrix.Rotation(math.pi / 2, 4, 'X'))
    for v in bm.verts:
        x, y, z = v.co; s = -y
        zz = z * lerp(Hh, s) * (.85 if z > 0 else .5) - .012 * max(0, s) ** 1.5
        v.co = V((x * lerp(W, s), -.03 + y * .095, zz))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    head = obj_from_bm(name, bm)
    rnd = random.Random(5); me = head.data
    spots = [me.vertices[rnd.randrange(len(me.vertices))].co.copy() for _ in range(420)]
    spots = [(p, .0022 + .002 * rnd.random()) for p in spots if p.z > -.004 and p.y > -.085]
    col = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    for v in me.vertices:
        p = v.co; s = -(p.y + .03) / .095
        c = V(srgb('#c48c3e')) * (.92 + .08 * math.sin(p.x * 300) * math.sin(p.y * 270))
        white = smooth((s - .5) / .2) * smooth((-p.z + .006) / .012) + smooth((-p.z - .004) / .01)
        c = c.lerp(V(srgb('#ece0c6')), min(1, white))
        if s > .55 and abs(p.z + .002 + .01 * (s - .55)) < .0022: c = V(srgb('#2a1c14'))   # the line of the mouth
        if s < .7 and any((p - q).length < r for q, r in spots): c = V(srgb('#1c140e'))
        col.data[v.index].color = (*c, 1)
    parts = [(head, 'fur')]
    for sx in (1, -1):   # ears: rounded, set back on the crown
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1,
            matrix=Matrix.Translation((sx * .04, .035, .024)) @ Matrix.Rotation(sx * -.6, 4, 'Y') @ Matrix.Rotation(-.6, 4, 'X') @ Matrix.Diagonal((.015, .006, .016, 1)))
        parts.append((obj_from_bm(name + ('EarL' if sx > 0 else 'EarR'), bm), 'ear'))
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1,
            matrix=Matrix.Translation((sx * .033, -.058, .017)) @ Matrix.Rotation(sx * .5, 4, 'Z') @ Matrix.Diagonal((.011, .007, .0065, 1)))
        parts.append((obj_from_bm(name + ('EyeL' if sx > 0 else 'EyeR'), bm), 'eye'))
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1, matrix=Matrix.Translation((0, -.122, .006)) @ Matrix.Diagonal((.014, .008, .008, 1)))
    parts.append((obj_from_bm(name + 'Nose', bm), 'nose'))
    return parts

def foreleg(name, under, J, s=-1):
    """A foreleg of the hide hanging over the shoulder and down the chest: a strip laid on
    the robe, narrowing to the paw."""
    sf = Surf(under); pts = []
    for i in range(1, 7):   # from over the shoulder
        ph = math.pi / 2 * (1 - i / 7); h = sf.hit(V((s * .135, .0, 1.32)), V((0, -math.cos(ph), math.sin(ph))), .35)
        if h: pts.append(h)
    for i in range(14):
        t = i / 13; z = 1.32 - (1.32 - .93) * t; x = s * (.135 - .02 * t)
        h = sf.hit(V((x, 0, z)), V((0, -1, 0)))
        if h: pts.append(h)
    pn = [(h[0] + h[1] * .02, h[1]) for h in pts]
    leg = strip(name, pn, lambda t: .1 - .045 * t, .008)
    end, n = pn[-1]; dn = (pn[-1][0] - pn[-3][0]).normalized()
    return leg, paw(name + 'Paw', end + dn * .02 + n * .004, dn, n, .95)


# ── The staves ──────────────────────────────────────────────────────────────
STAFF = dict(L0=1.1, L1=.4)

def ibis_staff(tag, mats, L0=STAFF['L0'], L1=STAFF['L1']):
    """The first two tiers' staff, built about its grip (the origin), the top to +Z: a
    shaft of dark wood with a bronze ferrule, carved at the top into the head and neck of
    an ibis, the long beak curving down (towards -X, the figure's right, as the sheets
    show it); a band of turquoise between gold rings below. Returns the parts and the
    eyes' centres (for the magic)."""
    wood, gold, turq, bronze, eye_m = mats; out = []
    out.append((lathe(tag + 'StaffShaft', [(0, -L0), (.012, -L0 + .004), (.0135, -L0 + .2), (.0145, 0), (.0132, L1), (0, L1 + .01)], 16), wood))
    out.append((lathe(tag + 'StaffFerrule', [(0, -L0 - .003), (.0125, -L0), (.0142, -L0 + .045), (.0136, -L0 + .052)], 16), bronze))
    out.append((lathe(tag + 'StaffBand', [(.0136, L1 - .085), (.0158, L1 - .082), (.0158, L1 - .074), (.0152, L1 - .072), (.0152, L1 - .052),
                                          (.0158, L1 - .05), (.0158, L1 - .042), (.0136, L1 - .039)], 16), turq))
    for z in (L1 - .078, L1 - .062, L1 - .046):
        out.append((lathe(tag + f'StaffRing{int(z * 1000)}', [(.0138, z - .004), (.0166, z - .0025), (.0166, z + .0025), (.0138, z + .004)], 16), gold))
    P = [(0, L1 - .01), (0, L1 + .03), (.002, L1 + .058), (-.004, L1 + .08), (-.016, L1 + .093), (-.032, L1 + .095), (-.058, L1 + .088),
         (-.083, L1 + .072), (-.103, L1 + .05), (-.116, L1 + .026), (-.122, L1 + .008)]
    R = [.0132, .0128, .0135, .018, .019, .0125, .0098, .008, .0064, .0048, .0024]
    neck = curve_mesh(tag + 'StaffIbis', [[(x, 0, z) for x, z in P]], .01, radii=lambda t: R[round(t * (len(R) - 1))] / .01)
    skull = bmesh.new(); bmesh.ops.create_uvsphere(skull, u_segments=20, v_segments=12, radius=1, matrix=Matrix.Translation((-.013, 0, L1 + .088)) @ Matrix.Diagonal((.029, .021, .024, 1)))
    bm = bmesh.new(); bm.from_mesh(neck.data); sk = obj_from_bm('tmp', skull); bm.from_mesh(sk.data); bpy.data.objects.remove(sk)
    bm.to_mesh(neck.data); bm.free(); out.append((neck, wood))
    eyes = [V((-.024, sy * .0195, L1 + .094)) for sy in (1, -1)]
    bm = bmesh.new()
    for e in eyes: bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=.0036, matrix=Matrix.Translation(e))
    out.append((obj_from_bm(tag + 'StaffEyes', bm), eye_m))
    return out, eyes

def gilded_staff(tag, mats, L0=STAFF['L0'], L1=STAFF['L1']):
    """The high priest's staff: the dark shaft and ferrule, a gilded socket, and on it a
    crescent moon, horns up, a gilded ibis standing in it and the moon's disc above the
    bird's back, all in the plane facing the front (the bird faces -X). Returns the parts
    and the disc's centre and radius (for the magic)."""
    wood, gold, bronze = mats; out = []
    out.append((lathe(tag + 'StaffShaft', [(0, -L0), (.012, -L0 + .004), (.0135, -L0 + .2), (.0145, 0), (.0135, L1 - .1), (0, L1 - .09)], 16), wood))
    out.append((lathe(tag + 'StaffFerrule', [(0, -L0 - .003), (.0125, -L0), (.0142, -L0 + .045), (.0136, -L0 + .052)], 16), bronze))
    out.append((lathe(tag + 'StaffSocket', [(.0142, L1 - .13), (.0172, L1 - .126), (.0172, L1 - .118), (.0152, L1 - .112), (.0158, L1 - .04),
                                            (.02, L1 - .022), (.02, L1 - .012), (.012, L1 + .0), (.0, L1 + .004)], 24), gold))
    bm = bmesh.new(); cz = L1 + .072; rows = []
    for i in range(33):   # the crescent: an arc of the moon's rim, widest at the bottom, the horns drawn to points
        t = i / 32 * 2 - 1; a = math.radians(270 + 72 * t); w = .021 * (1 - t * t) ** .75 + .0015
        dr = V((math.cos(a), 0, math.sin(a))); c = V((0, 0, cz)) + dr * .056
        rows.append((bm.verts.new(c - dr * w * .35), bm.verts.new(c + dr * w * .65)))
    for i in range(32): bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
    cr = obj_from_bm(tag + 'StaffCrescent', bm); mod(cr, 'SOLIDIFY', thickness=.009, offset=0); mod(cr, 'BEVEL', width=.002, segments=2, limit_method='ANGLE'); bake_mods(cr)
    out.append((cr, gold))
    zb = cz - .056 + .014   # the crescent's inner edge at the bottom, where the bird stands
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1,
                              matrix=Matrix.Translation((.004, 0, zb + .07)) @ Matrix.Rotation(math.radians(18), 4, 'Y') @ Matrix.Diagonal((.048, .021, .026, 1)))
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1, matrix=Matrix.Translation((-.052, 0, zb + .132)) @ Matrix.Diagonal((.012, .0095, .011, 1)))
    bird = obj_from_bm(tag + 'StaffBird', bm)
    neck = curve_mesh(tag + 'StaffBirdNeck', [[(-.034, 0, zb + .08), (-.046, 0, zb + .1), (-.044, 0, zb + .118), (-.05, 0, zb + .132)]], .0065)
    beak = curve_mesh(tag + 'StaffBirdBeak', [[(-.058, 0, zb + .134), (-.078, 0, zb + .128), (-.096, 0, zb + .114), (-.108, 0, zb + .096)]], .004, radii=lambda t: 1 - .7 * t)
    legs = curve_mesh(tag + 'StaffBirdLegs', [[(sx * .004, sy * .006, zb + .052), (sx * .006, sy * .007, zb + .026), (sx * .006 - .008, sy * .007, zb + .002)]
                                              for sx, sy in ((1, 1), (-1, -1))], .0026)
    tail = bmesh.new(); bmesh.ops.create_cone(tail, cap_ends=True, segments=10, radius1=.014, radius2=.002, depth=.04,
                                               matrix=Matrix.Translation((.056, 0, zb + .052)) @ Matrix.Rotation(math.radians(-118), 4, 'Y') @ Matrix.Diagonal((1, .6, 1, 1)))
    tl = obj_from_bm('tmp', tail)
    bm = bmesh.new()
    for o in (bird, neck, beak, legs, tl): bm.from_mesh(o.data)
    for o in (neck, beak, legs, tl): bpy.data.objects.remove(o)
    bm.to_mesh(bird.data); bm.free(); out.append((bird, gold))
    dc, dr = V((-.008, 0, zb + .172)), .036
    disc = lathe(tag + 'StaffMoon', [(0, -.0035), (dr - .002, -.0035), (dr, -.0015), (dr, .0015), (dr - .002, .0035), (0, .0035)], 40)
    disc.rotation_euler = (math.radians(90), 0, 0); disc.location = dc; bpy.context.view_layer.update(); bake_obj_xform(disc)
    out.append((disc, gold))
    out.append((curve_mesh(tag + 'StaffMoonPost', [[(0, 0, zb + .09), (-.004, 0, zb + .12), (-.008, 0, dc.z - dr + .004)]], .0035), gold))
    S = Matrix.Translation((0, 0, L1)) @ Matrix.Diagonal((1.25, 1.25, 1.25, 1)) @ Matrix.Translation((0, 0, -L1))
    for o, mt in out[3:]: o.data.transform(S)
    return out, (S @ dc, dr * 1.25)


# ── Papyrus: the closed scroll and the open roll ────────────────────────────
def glyph_masks(W=512, Hh=768, seed=3):
    """Columns of hieroglyphs in the papyrus's frame (ink and red rubrics as two masks):
    ankh, the eye of Horus, the ibis of Thoth, the moon, water, reed leaf, loaf, djed,
    sun and mouth, drawn as plain strokes and shapes."""
    from PIL import Image, ImageDraw
    ink = Image.new('L', (W, Hh), 0); red = Image.new('L', (W, Hh), 0); rnd = random.Random(seed)
    def glyph(d, kind, cx, cy, s):
        w = max(2, int(s * .09))
        if kind == 0:   # ankh
            d.ellipse((cx - s * .2, cy - s * .46, cx + s * .2, cy - s * .08), outline=255, width=w)
            d.line((cx - s * .3, cy - s * .04, cx + s * .3, cy - s * .04), fill=255, width=w); d.line((cx, cy - s * .08, cx, cy + s * .46), fill=255, width=w)
        elif kind == 1:   # wedjat eye
            d.arc((cx - s * .42, cy - s * .3, cx + s * .42, cy + s * .2), 200, 340, fill=255, width=w)
            d.arc((cx - s * .42, cy - s * .32, cx + s * .42, cy + s * .14), 20, 160, fill=255, width=w)
            d.ellipse((cx - s * .1, cy - s * .14, cx + s * .1, cy + s * .06), fill=255)
            d.line((cx - s * .1, cy + s * .1, cx - s * .16, cy + s * .42), fill=255, width=w); d.arc((cx + s * .02, cy + s * .1, cx + s * .36, cy + s * .44), 90, 300, fill=255, width=w)
        elif kind == 2:   # ibis
            d.ellipse((cx - s * .22, cy - s * .12, cx + s * .26, cy + s * .14), fill=255)
            d.line((cx - s * .16, cy - s * .04, cx - s * .26, cy - s * .36), fill=255, width=w)
            d.arc((cx - s * .64, cy - s * .44, cx - s * .2, cy + s * .04), 190, 300, fill=255, width=w)
            d.line((cx, cy + s * .12, cx - s * .04, cy + s * .46), fill=255, width=w); d.line((cx + s * .1, cy + s * .12, cx + s * .12, cy + s * .46), fill=255, width=w)
        elif kind == 3:   # moon: crescent and disc
            d.ellipse((cx - s * .2, cy - s * .44, cx + s * .2, cy - s * .04), fill=255)
            d.chord((cx - s * .36, cy - s * .2, cx + s * .36, cy + s * .42), 0, 180, fill=255)
            d.chord((cx - s * .28, cy - s * .2, cx + s * .28, cy + s * .26), 0, 180, fill=0)
        elif kind == 4:   # water
            for k in range(3):
                y = cy - s * .2 + k * s * .2
                d.line([(cx - s * .4 + i * s * .1, y + (s * .05 if i % 2 else -s * .05)) for i in range(9)], fill=255, width=w)
        elif kind == 5:   # reed leaf
            d.polygon([(cx, cy - s * .46), (cx + s * .1, cy - s * .2), (cx + s * .08, cy + s * .46), (cx - s * .06, cy + s * .46), (cx - s * .04, cy - s * .1)], fill=255)
        elif kind == 6:   # loaf
            d.chord((cx - s * .26, cy - s * .1, cx + s * .26, cy + s * .3), 180, 360, fill=255)
        elif kind == 7:   # djed
            d.rectangle((cx - s * .08, cy - s * .2, cx + s * .08, cy + s * .46), fill=255)
            for k in range(4): d.line((cx - s * .24, cy - s * .38 + k * s * .07, cx + s * .24, cy - s * .38 + k * s * .07), fill=255, width=w)
        elif kind == 8:   # sun
            d.ellipse((cx - s * .24, cy - s * .24, cx + s * .24, cy + s * .24), outline=255, width=w); d.ellipse((cx - s * .05, cy - s * .05, cx + s * .05, cy + s * .05), fill=255)
        else:   # mouth
            d.chord((cx - s * .34, cy - s * .16, cx + s * .34, cy + s * .2), 0, 360, fill=255); d.line((cx - s * .3, cy, cx + s * .3, cy), fill=0, width=w)
    di, dr = ImageDraw.Draw(ink), ImageDraw.Draw(red)
    cols, s = 8, 46; x0 = 40; step = (W - 2 * x0) / cols
    for c in range(cols + 1): di.line((x0 + c * step, 30, x0 + c * step, Hh - 40), fill=255, width=2)
    for c in range(cols):
        cx = x0 + (c + .5) * step
        for r in range(int((Hh - 90) / (s * 1.1))):
            cy = 52 + r * s * 1.1; kind = rnd.randrange(10)
            glyph(dr if rnd.random() < .12 else di, kind, cx, cy, s * (.82 + .12 * rnd.random()))
    return ink, red

def papyrus_images():
    """The written face of the open roll (papyrus, black ink, red rubrics) and the light of
    its writing for L2_Magic: the same glyphs in pale gold with a soft halo, on clear."""
    from PIL import Image, ImageFilter, ImageChops
    ink, red = glyph_masks(); W, Hh = ink.size
    rnd = random.Random(9); base = Image.new('RGB', (W, Hh), (214, 190, 140))
    from PIL import ImageDraw
    d = ImageDraw.Draw(base)
    for i in range(0, Hh, 3): d.line((0, i, W, i), fill=tuple(int(x * (.93 + .07 * rnd.random())) for x in (214, 190, 140)))
    for i in range(0, W, 9): d.line((i, 0, i, Hh), fill=tuple(int(x * (.95 + .05 * rnd.random())) for x in (214, 190, 140)), width=4)
    text = Image.composite(Image.new('RGB', (W, Hh), (34, 26, 18)), base, ink.filter(ImageFilter.GaussianBlur(.6)))
    text = Image.composite(Image.new('RGB', (W, Hh), (150, 40, 26)), text, red.filter(ImageFilter.GaussianBlur(.6)))
    both = ImageChops.lighter(ink, red)
    halo = both.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(9)).point(lambda a: min(255, int(a * 1.6)))
    alpha = ImageChops.lighter(both.filter(ImageFilter.MaxFilter(3)), halo.point(lambda a: int(a * .55)))
    glow = Image.merge('RGBA', (Image.new('L', (W, Hh), 255), Image.new('L', (W, Hh), 200), Image.new('L', (W, Hh), 90), alpha))
    return MJ.pil_image('PapyrusText', text), rgba_image('GlyphLight', glow)

def roll_mesh(name, r, L, x0=0.0, y0=0.0, z0=0.0):
    """A rolled papyrus along local X (lathe), with its two ends apart for their own rings."""
    side = lathe(name, [(r, -L / 2), (r, L / 2)], 24)
    side.rotation_euler = (0, math.radians(90), 0); side.location = (x0, y0, z0); bpy.context.view_layer.update(); bake_obj_xform(side)
    bm = bmesh.new()
    for sx in (-1, 1):
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=r * .985,
                                matrix=Matrix.Translation((x0 + sx * L / 2, y0, z0)) @ Matrix.Rotation(math.radians(90) * sx, 4, 'Y'))
    ends = obj_from_bm(name + 'Ends', bm)
    pat_uv(ends, lambda c, p: ((p.y - y0) / r * 6, (p.z - z0) / r * 6))
    bake_uv(ends)
    return side, ends

def scroll(tag, mats):
    """A closed papyrus roll, built about the grip of the left fist (local X along the
    knuckles, Y up the hand, Z out from the palm)."""
    pap, end = mats
    side, ends = roll_mesh(tag + 'Scroll', .0165, .21)
    return [(side, pap), (ends, end)]

def open_roll(tag, mats):
    """The lector's open roll: its upper roll in the fist, the written sheet hanging from
    it down the outer side of the hand in a gentle curve to the lower roll; the text on
    the face, a plain back. Returns the parts and the light of the writing (L2_Magic),
    a sheet just over the face with the glowing glyphs."""
    pap, end = mats; L, Ld, nu, nv = .2, .3, 8, 24
    parts = []
    s1, e1 = roll_mesh(tag + 'RollTop', .015, L); s2, e2 = roll_mesh(tag + 'RollFoot', .0125, L * .98, 0, -Ld, .004)
    parts += [(s1, pap), (e1, end), (s2, pap), (e2, end)]
    def at(u, v):   # the sheet: from the top roll's outer side, bowing out, to the foot roll
        y = -Ld * v; z = .015 * (1 - v) + .0165 * v + .03 * math.sin(math.pi * v) - .006 * math.sin(math.pi * u)
        return V(((u - .5) * L * .96, y + .004 * math.sin(math.pi * u), z))
    def sheet(name, off, flip, uv=True):
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); g = [[bm.verts.new(at(i / nu, j / nv) + V((0, 0, off))) for i in range(nu + 1)] for j in range(nv + 1)]
        for j in range(nv):
            for i in range(nu):
                q = (g[j][i], g[j + 1][i], g[j + 1][i + 1], g[j][i + 1]); f = bm.faces.new(q[::-1] if flip else q)
                for lp in f.loops:
                    jj, ii = next((a, b) for a in range(nv + 1) for b in range(nu + 1) if g[a][b] is lp.vert)
                    lp[uvl].uv = (ii / nu, 1 - jj / nv)
        return obj_from_bm(name, bm)
    parts.append((sheet(tag + 'RollText', 0, False), 'text'))
    parts.append((sheet(tag + 'RollBack', -.0012, True), pap))
    light = sheet('L2_MagicGlyphs', .0016, False)
    return parts, light


# ── Magic light ─────────────────────────────────────────────────────────────
def halo(name, centre, r, mats, steps=(1.0, 1.4, 1.9, 2.5), squash=(1, 1, 1)):
    """A soft glow: nested see-through spheres of one colour, fainter outward (mats are
    their materials, inner to outer). Same colour, so the order they are drawn in does
    not matter."""
    out = []
    for k, (s, mt) in enumerate(zip(steps, mats)):
        bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*(r * s * q for q in squash), 1)))
        out.append((obj_from_bm(f'{name}{k}', bm), mt))
    return out

def skin_rigid(name, rig, parts):
    """Join magic parts (in the idle pose, each with the bone it rides) into one skinned
    mesh: each part is carried back to the rest pose through its bone and weighted to it
    alone, so one node holds light riding the staff and both hands."""
    objs = []
    for ob, bone in parts:
        pb = rig.pose.bones[bone]; R = rig.data.bones[bone].matrix_local @ pb.matrix.inverted()
        ob.data.transform(R @ ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
        vg = ob.vertex_groups.new(name=bone); vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
        objs.append(ob)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join()
    ob = objs[0]; ob.name = name; ob.data.name = name
    if ob.data.uv_layers: ob.data.uv_layers[0].active_render = True; ob.data.uv_layers.active = ob.data.uv_layers[0]
    ob.parent = rig; m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
    return ob


# ── Kit ─────────────────────────────────────────────────────────────────────
def kit(body, J):
    out = {}
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    head_kit(body, J, add)
    MJ.sandals(body, J, add, m_straw('PapyrusStraps', '#c8ad74'), m_straw('PapyrusSole', '#b39660'))
    gold = MJ.m_gold('Gold', 512); bronze = H.m_bronze('Ferrule', .25, 256)
    walnut = m_wood('Walnut')
    turq = H.m_flat('Turquoise', '#2fa39a', .35); inlay = H.m_flat('Inlay', '#0d1a1c', .2)
    parts, eyes = ibis_staff('L12_', (walnut, gold, turq, bronze, inlay))
    for ob, mt in parts: add(ob, mt, 'later:staff')
    MAGIC['eyes'] = eyes
    parts, moon = gilded_staff('L3_', (m_wood('Walnut3', ('#4e2c18', '#6e4226', '#84563a')), gold, bronze))
    for ob, mt in parts: add(ob, mt, 'later:staff')
    MAGIC['moon'] = moon
    pap = m_papyrus('Papyrus'); end = m_rolled_end('PapyrusEnds')
    for ob, mt in scroll('L1_', (pap, end)): add(ob, mt, 'later:hand.L')
    text_img, glow_img = papyrus_images()
    parts, light = open_roll('L2_', (pap, end))
    for ob, mt in parts: add(ob, MJ.m_image('PapyrusText', text_img, .7, 0, 1024) if mt == 'text' else mt, 'later:hand.L')
    MAGIC['glyphs'] = light; MAGIC['glyph_img'] = glow_img
    return out


# ── Robe, sash and the tiers' kit worn over it ──────────────────────────────
def dress(body, J, items):
    def add(ob, mt, bind): items[ob.name] = (ob, mt, bind); return ob
    probe = MJ.trunk(body)
    linen = m_pleats('RobeLinen', res=2048)
    robe = add(bodice('RobeTop', body, J), linen, 'robe')
    skirt = add(robe_skirt('RobeSkirt', probe, robe), m_pleats('SkirtLinen', res=2048, depth=.62), 'hang')
    wrap_edges(robe, m_cloth('RobeHem', '#efebe2', 700, .03, 512), add)
    woven = m_woven('Sash')
    lector_bands('L2_', [robe, skirt], m_woven('LectorBand', '#ddd2bc', '#8f7f62'), add)
    bands = [items[n][0] for n in items if n.startswith('L2_LectorBand')]
    band, knot = sash([skirt, robe] + bands, skirt, woven, add)
    palette('L1_', [band], skirt, (m_wood('PaletteWood', ('#6a3c1e', '#8a5630', '#9c683c'), 512), H.m_flat('InkBlack', '#0c0a08', .25),
                                    H.m_flat('InkRed', '#8a2a18', .3), H.m_flat('Reed', '#b89a5e', .6)), add)
    # L3: the collar, then the leopard's skin over everything
    col = MJ.wesekh('L3_Collar', body, J, None)
    add(col, MJ.m_image('Collar', collar_image(), .4, .35, 1024), 'skin')
    leo = m_leopard('Leopard')
    under = [robe, skirt, band, knot] + [items[n][0] for n in ('SashEndR', 'SashEndL')]
    pl = add(pelt('L3_Pelt', body, probe, under, J), leo, 'pelt')
    for sx in (1, -1):
        th = sx * 48; d = V((math.sin(math.radians(th)), math.cos(math.radians(th)), 0))
        h = Surf([pl]).hit(V((0, 0, .44)), d)
        at = (h[0] if h else d * .2 + V((0, 0, .44))) + V((0, 0, -.03))
        add(paw(f'L3_HindPaw{"L" if sx > 0 else "R"}', at, V((0, 0, -1)), d), leo, 'pelt')
    pts = []
    sk = Surf([skirt])
    for i in range(16):   # the tail, from the rump down the back of the robe
        t = i / 15; z = .53 - .28 * t; h = sk.hit(V((0, 0, z)), V((0, 1, 0)))
        p = h[0] if h else V((0, .16, z)); pts.append(tuple(p + V((.012 * math.sin(t * 3), .02 + .012 * (1 - t), 0))))
    add(curve_mesh('L3_Tail', [pts], .02, radii=lambda t: 1 - .35 * t), m_tail('LeopardTail'), 'pelt')
    leg, lpaw = foreleg('L3_Foreleg', [robe, band, knot] + [items['L3_Collar'][0]], J, -1)
    add(leg, leo, 'pelt'); add(lpaw, leo, 'pelt')
    place_head(body, J, add)
    bpy.data.objects.remove(probe)

def collar_image():
    """The high priest's broad collar (after medjay.collar_image, as the sheet has it):
    rows of gold beads with one of turquoise and one of carnelian, a fringe of gold drops."""
    from PIL import Image, ImageDraw
    W, Hh = 2048, 256; im = Image.new('RGB', (W, Hh), (60, 44, 20)); d = ImageDraw.Draw(im)
    gold, turq, carn = (204, 160, 66), (46, 160, 150), (160, 60, 34)
    for y0, y1, col in ((0, 14, gold), (14, 40, gold), (40, 66, turq), (66, 80, gold), (80, 104, gold), (104, 118, carn), (118, 144, gold), (144, 168, gold)):
        r = (y1 - y0) / 2; n = int(W / (2 * r * .92))
        for i in range(n):
            x = (i + .5) * W / n
            d.ellipse((x - r, y0, x + r, y1), fill=tuple(int(c * .55) for c in col))
            d.ellipse((x - r * .8, y0 + r * .15, x + r * .7, y1 - r * .35), fill=col)
            d.ellipse((x - r * .35, y0 + r * .3, x + r * .05, y0 + r * .7), fill=tuple(min(255, int(c * 1.4 + 30)) for c in col))
    for i in range(140):
        x = (i + .5) * W / 140; y0, y1 = 170, 250; w = W / 140 * .42
        d.polygon([(x - w * .35, y0), (x + w * .35, y0), (x + w, y1 - 10), (x, y1), (x - w, y1 - 10)], fill=(150, 110, 40))
        d.polygon([(x - w * .15, y0 + 2), (x + w * .25, y0 + 2), (x + w * .6, y1 - 14), (x - w * .3, y1 - 16)], fill=(226, 186, 96))
    return MJ.pil_image('CollarArt', im)

def m_tail(name, res=512):
    """The tail: the leopard's coat towards its root, then black rings closing in and a
    black tip (rings by height, as it hangs)."""
    m = m_leopard(name, res)
    col = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=1.6, Distortion=.5); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    rings = m.ramp(w.outputs['Fac'], [(.62, (0, 0, 0)), (.7, (1, 1, 1))])
    low = m.node('ShaderNodeMapRange', **{'From Min': .42, 'From Max': .36}); m.L.new(sep.outputs['Z'], low.inputs['Value'])
    tip = m.node('ShaderNodeMapRange', **{'From Min': .3, 'From Max': .28}); m.L.new(sep.outputs['Z'], tip.inputs['Value'])
    f = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(rings.outputs['Color'], f.inputs[0]); m.L.new(low.outputs[0], f.inputs[1])
    f2 = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(f.outputs[0], f2.inputs[0]); m.L.new(tip.outputs[0], f2.inputs[1])
    m.L.new(m.mix(col, srgb('#1a120c'), f2.outputs[0]), m.bsdf.inputs['Base Color'])
    return m

def place_head(body, J, add):
    """The leopard's head over the left shoulder, lying on it with the muzzle down the
    front of the chest, the crown turned forward."""
    sh = J['l-shoulder']; bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    h = bvh.ray_cast(V((.14, -.03, 2)), V((0, 0, -1)), 1)
    top = h[0] if h[0] else V((.125, -.035, sh.z + .07))
    mz = V((.1, -.85, -.5)).normalized(); up = (V((0, -.45, .9)) - mz * V((0, -.45, .9)).dot(mz)).normalized()
    Y = -mz; X = Y.cross(up)
    M = Matrix((X, Y, up)).transposed().to_4x4() @ Matrix.Diagonal((1.3, 1.3, 1.3, 1)); M.translation = top + V((.015, -.06, .03))
    fur = m_vcol('LeopardHead', .8, 1024); ear = H.m_flat('LeopardEar', '#5a3c22', .8)
    eye = H.m_flat('GlassEye', '#6e4a14', .12); nose = H.m_flat('LeopardNose', '#7e4a3e', .5)
    for ob, kind in leopard_head('L3_LeopardHead'):
        ob.matrix_world = M; bpy.context.view_layer.update(); bake_obj_xform(ob)
        add(ob, {'fur': fur, 'ear': ear, 'eye': eye, 'nose': nose}[kind], 'pelt')


# ── Rig, poses and moves ────────────────────────────────────────────────────
def skeleton(J):
    """The infantry skeleton and a bone for the staff, from the right fist's grip along
    the shaft (towards its top, the thumb's side of the fist)."""
    B = H.skeleton_spec(J)
    g, k, palm, along = MJ.grip_frame(J, 'r')
    B.append(('staff.R', g, g - k * .3, 'hand.R', False))
    return B

TRUNK = ('hips', 'spine', 'chest', 'neck')

def hang_weights(ob, z_top=1.0, z_bot=.45, legs=.85, iters=4):
    """medjay.hang_weights for long cloth and the hide: above z_top a vertex keeps the
    trunk's share of the body's weights (not the arms', so the mantle stays on the
    shoulders when they rise); below, it hangs from the hips and takes more of the legs'
    weights (up to `legs`) towards z_bot; then the weights are smoothed over the mesh."""
    me = ob.data; names = {g.index: g.name for g in ob.vertex_groups}
    W = []
    for v in me.vertices:
        f = legs * smooth((z_top - v.co.z) / (z_top - z_bot))
        body = {names[g.group]: g.weight for g in v.groups}
        tr = {k: x for k, x in body.items() if k in TRUNK}; s = sum(tr.values())
        tr = {k: x / s for k, x in tr.items()} if s > 1e-4 else {'chest' if v.co.z > 1.1 else 'hips': 1.0}
        if f > 0: tr = {'hips': 1.0} if v.co.z < z_top else tr
        w = {k: x * (1 - f) for k, x in tr.items()}
        for k, x in body.items(): w[k] = w.get(k, 0) + x * f
        W.append(w)
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

def poses(J):
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-.5, .8, -.4), pt=(-.03, -.04, 1), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': tuple(-x for x in pt), 'fist': 0, **kw}   # pt: where the staff's top points
    def armL(w, hint=(.6, .7, -.3), bar=(.95, -.3, 0), wrist=(0, 0, 0), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': bar, 'wrist': wrist, 'fist': 0, **kw}   # bar: the scroll, along the knuckles
    base = {'hips': {'loc': (0, 0, -.01)}, 'chest': {'rot': (.02, 0, 0)}, 'head': {'rot': (-.02, 0, 0)},
            'ik_foot.L': {'loc': (-.035, -.01, 0), 'rot': (0, 0, .1)}, 'ik_foot.R': {'loc': (.035, .01, 0), 'rot': (0, 0, -.1)},
            'armR': armR((-.15, -.2, -.3)), 'armL': armL((.12, -.05, -.5))}
    def st(**over):
        Pp = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): Pp[k] = v if k.startswith('arm') or k in ('knee', 'staff') else {**Pp.get(k, {}), **v}
        return Pp
    return st, armR, armL

def make_action(rig, name, frames):
    """H.make_action, and the staff: 'slide' moves it along its shaft through the fist,
    'matrix' puts it anywhere (armature space), when it has left the hand."""
    rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True
    rig.animation_data.action = act
    for f, Pp in frames:
        H.pose(rig, Pp); sp = Pp.get('staff', {}); pb = rig.pose.bones['staff.R']
        if 'slide' in sp: pb.location = (0, sp['slide'], 0)
        if 'matrix' in sp: H._upd(); pb.matrix = sp['matrix'].copy()
        H._upd(); H.key_all(rig, f)
    return act

def actions(rig, J):
    """Idle, Walk, Cast (the staff raised, then pointed at the foe, the scroll lifted),
    Heal (both hands raised in blessing, the staff held high), Strike (a blow with the
    staff, slid down through the fist to swing it by its lower end), Hit and Death (he
    falls backwards and the staff drops beside him)."""
    st, armR, armL = poses(J); A = []
    A.append(make_action(rig, 'Idle', [(1, st()), (30, st(hips={'loc': (0, 0, -.014)}, chest={'rot': (.03, 0, .01)}, head={'rot': (-.01, 0, .05)},
                                                            armR=armR((-.15, -.2, -.305)), armL=armL((.12, -.05, -.505)))), (60, st())]))
    def W(fl, fr, zl, zr, hz, sw):
        return st(**{'ik_foot.L': {'loc': (-.035, fl, zl), 'rot': (0, 0, .08)}, 'ik_foot.R': {'loc': (.035, fr, zr), 'rot': (0, 0, -.08)},
                     'hips': {'loc': (0, 0, -.012 + hz), 'rot': (0, sw * .04, 0)}, 'chest': {'rot': (.03, -sw * .05, 0)}},
                  armR=armR((-.15, -.22 - .04 * sw, -.3), pt=(-.03, -.1 - .05 * sw, 1)), armL=armL((.12, -.05 + .06 * sw, -.49)), staff={'slide': .06})
    A.append(make_action(rig, 'Walk', [(1, W(-.2, .19, 0, 0, -.012, 1)), (7, W(-.01, -.01, 0, .08, .012, 0)), (13, W(.19, -.2, 0, 0, -.012, -1)),
                                       (19, W(-.01, -.01, .08, 0, .012, 0)), (25, W(-.2, .19, 0, 0, -.012, 1))]))
    step = {'ik_foot.L': {'loc': (-.04, -.09, 0), 'rot': (0, 0, .1)}}
    read = armL((.0, -.3, -.3), hint=(.8, .3, -.6), bar=(1, 0, 0), wrist=(0, .2, -1.2))   # the roll held out, its writing to the foe
    A.append(make_action(rig, 'Cast', [(1, st()),
        (10, st(chest={'rot': (-.06, 0, .06)}, head={'rot': (-.1, 0, 0)}, hips={'loc': (0, .02, -.02)},
                armR=armR((-.08, -.3, .12), hint=(-.8, .5, -.3), pt=(-.15, -.35, 1)), armL=read)),
        (18, st(chest={'rot': (.12, 0, -.08)}, head={'rot': (-.02, 0, .06)}, hips={'loc': (0, -.04, -.03)}, **step,
                armR=armR((.0, -.46, -.04), hint=(-.8, .3, -.4), pt=(.05, -1, .3)), armL=read)),
        (32, st(chest={'rot': (.1, 0, -.06)}, head={'rot': (-.02, 0, .05)}, hips={'loc': (0, -.035, -.03)}, **step,
                armR=armR((.0, -.44, -.03), hint=(-.8, .3, -.4), pt=(.04, -1, .32)), armL=read)),
        (44, st())]))
    bless = dict(chest={'rot': (-.08, 0, 0)}, head={'rot': (-.2, 0, 0)}, hips={'loc': (0, .01, -.005)},
                 armR=armR((-.1, -.2, .3), hint=(-.9, .3, -.2), pt=(-.08, -.15, 1)),
                 armL=armL((.12, -.24, .26), hint=(.9, .3, -.2), bar=(.2, -.3, 1), wrist=(0, -.4, .2)))
    bless2 = dict(bless, head={'rot': (-.24, 0, .03)}, armR=armR((-.1, -.21, .33), hint=(-.9, .3, -.2), pt=(-.08, -.15, 1)),
                  armL=armL((.12, -.26, .29), hint=(.9, .3, -.2), bar=(.2, -.3, 1), wrist=(0, -.4, .2)))
    A.append(make_action(rig, 'Heal', [(1, st()), (12, st(**bless)), (24, st(**bless2)), (36, st(**bless)), (48, st())]))
    A.append(make_action(rig, 'Strike', [(1, st()),
        (8, st(chest={'rot': (-.06, 0, .32)}, head={'rot': (0, 0, -.2)}, hips={'loc': (0, .03, -.02), 'rot': (0, 0, .1)},
               armR=armR((-.02, .02, .3), hint=(-.6, .6, -.2), pt=(.2, .7, .7)), armL=armL((.08, -.15, -.42)), staff={'slide': .5})),
        (13, st(chest={'rot': (.24, 0, -.3)}, head={'rot': (.06, 0, .2)}, hips={'loc': (0, -.06, -.05), 'rot': (0, 0, -.1)}, **step,
                armR=armR((.1, -.45, -.08), hint=(-.8, .2, -.5), pt=(.3, -1, .2)), armL=armL((.14, .02, -.46)), staff={'slide': .5})),
        (17, st(chest={'rot': (.26, 0, -.36)}, head={'rot': (.06, 0, .22)}, hips={'loc': (0, -.06, -.05), 'rot': (0, 0, -.12)}, **step,
                armR=armR((.14, -.42, -.15), hint=(-.8, .2, -.5), pt=(.45, -1, -.05)), armL=armL((.14, .03, -.46)), staff={'slide': .5})),
        (28, st())]))
    A.append(make_action(rig, 'Hit', [(1, st()),
        (4, st(chest={'rot': (-.25, 0, .16)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, .08, -.05)}, armL=armL((.16, .02, -.42)), armR=armR((-.17, -.12, -.3)))),
        (9, st(chest={'rot': (-.1, 0, .07)}, head={'rot': (-.12, 0, 0)}, hips={'loc': (0, .03, -.03)})), (17, st())]))
    a = V((-.3, -1, 0)).normalized(); x = V((0, 0, 1)).cross(a).normalized()
    ground = Matrix((x, a, x.cross(a))).transposed().to_4x4(); ground.translation = V((-.62, .22, .016))
    m = (V((0, 0, 1)) + a).normalized(); xm = V((0, 0, 1)).cross(m).normalized()
    mid = Matrix((xm, m, xm.cross(m))).transposed().to_4x4(); mid.translation = V((-.5, .1, .6))
    fall = dict(chest={'rot': (-.1, 0, .1)}, hips={'loc': (0, 0, -.1)}, armR=armR((-.25, .05, -.15), hint=(-1, .2, -.3), pt=(0, -1, .1)), armL=armL((.2, -.05, -.3), hint=(1, .2, -.5)))
    A.append(make_action(rig, 'Death', [(1, st()),
        (8, st(chest={'rot': (.3, 0, .12)}, head={'rot': (.26, 0, 0)}, hips={'loc': (0, .02, -.2)}, armR=armR((-.18, -.15, -.32), pt=(-.15, -.3, 1)))),
        (14, st(root={'loc': (0, .12, 0), 'rot': (-.6, 0, .05)}, head={'rot': (-.2, 0, .1)}, **fall, staff={'matrix': mid})),
        (20, st(root={'loc': (0, .27, 0), 'rot': (-1.38, 0, .08)}, head={'rot': (-.3, 0, .2)}, **fall, staff={'matrix': ground})),
        (25, st(root={'loc': (0, .29, 0), 'rot': (-1.52, 0, .08)}, head={'rot': (-.4, 0, .2)}, **fall, staff={'matrix': ground})),
        (40, st(root={'loc': (0, .29, 0), 'rot': (-1.5, 0, .08)}, head={'rot': (-.45, 0, .25)}, **fall, staff={'matrix': ground}))]))
    rig.animation_data.action = A[0]
    return A

MAGIC = {}   # what the kit leaves for the magic: the staff's eyes, the moon disc, the light of the writing

def place(rig, items):
    """In the idle pose: the staves through the right fist on their bone, each slid until
    its foot rests on the ground; the scrolls in the left fist (local X along the knuckles,
    Y up the hand, Z out from the palm). Then the magic, one skinned node per tier."""
    PB = rig.pose.bones; J = JOINTS
    sp = PB['staff.R']; g = sp.head.copy(); ax = (sp.tail - sp.head).normalized()
    x = V((1, 0, 0)); x = (x - ax * x.dot(ax)).normalized(); Ms = Matrix((x, ax.cross(x), ax)).transposed().to_4x4(); Ms.translation = g
    staves = {}
    for n, (ob, mt, b) in items.items():
        if b == 'later:staff': staves.setdefault(n.split('_')[0] + '_', []).append(ob)
    shift = {}
    for tag, obs in staves.items():
        foot = min((Ms @ (ob.matrix_basis @ v.co)).z for ob in obs for v in ob.data.vertices)
        shift[tag] = Matrix.Translation(ax * (.004 - foot) / ax.z) @ Ms
    hand = PB['hand.L']; D = hand.matrix @ rig.data.bones['hand.L'].matrix_local.inverted()
    gr, k, palm, along = MJ.grip_frame(J, 'l')
    gw = D @ (gr + palm * .002); kw = (D.to_3x3() @ k).normalized(); n = -(D.to_3x3() @ palm).normalized(); up = n.cross(kw)
    if up.dot(-(D.to_3x3() @ along)) < 0: kw = -kw; up = -up
    Mh = Matrix((kw, up, n)).transposed().to_4x4(); Mh.translation = gw
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        if bind == 'later:staff': ob.matrix_world = shift[name.split('_')[0] + '_'] @ ob.matrix_basis; bone = 'staff.R'
        else: ob.matrix_world = Mh @ ob.matrix_basis; bone = 'hand.L'
        bpy.context.view_layer.update(); H.bind_rigid(ob, rig, bone)
    # the magic, built in the idle pose and carried back to the rest pose through its bones
    rig.data.bones['staff.R'].use_deform = True   # (the body has no group for it: its weights were made before)
    teal = [m_glow(f'GlowEye{k}', '#5ff0dc', a, 1.0) for k, a in enumerate((1.0, .22, .09))]
    gl = MAGIC['glyphs']; gl.matrix_world = Mh @ gl.matrix_basis; bpy.context.view_layer.update()
    glyph_m = m_glow('GlyphLight', '#ffd070', 1.0, 1.0, MAGIC['glyph_img'])
    gl.data.materials.append(glyph_m.m)
    def eyes(tag, sc):
        out = []
        for e in MAGIC['eyes']:
            p = shift['L12_'] @ e
            for ob, mt in halo(f'{tag}Eye', p, .0042 * sc, teal, (1.0, 1.9, 2.8)):
                ob.data.materials.append(mt.m); out.append((ob, 'staff.R'))
        return out
    moon_c, moon_r = MAGIC['moon']; mc = shift['L3_'] @ moon_c
    silver = [m_glow(f'GlowMoon{k}', '#eef4ff', 1.0, 1.0)] + [m_glow(f'GlowMoon{k + 1}', '#a8ccff', a, 1.0) for k, a in enumerate((.3, .16, .08, .04))]
    disc = lathe('L3_MagicDisc', [(0, -.0052), (moon_r + .002, -.0052), (moon_r + .003, 0), (moon_r + .002, .0052), (0, .0052)], 40)
    disc.rotation_euler = (math.radians(90), 0, 0); disc.location = moon_c; bpy.context.view_layer.update(); bake_obj_xform(disc)
    disc.matrix_world = shift['L3_']; bpy.context.view_layer.update(); disc.data.materials.append(silver[0].m)
    parts3 = [(disc, 'staff.R')]
    for ob, mt in halo('L3_MagicMoon', mc, moon_r, silver[1:], (1.3, 1.7, 2.3, 3.0)):
        ob.data.materials.append(mt.m); parts3.append((ob, 'staff.R'))
    warm = [m_glow(f'GlowHand{k}', '#a8ccff', a, 1.0) for k, a in enumerate((.26, .13, .06))]
    for c, bone in ((gw, 'hand.L'), (g, 'hand.R')):
        for ob, mt in halo('L3_MagicHand', c, .038, warm, (1.0, 1.45, 2.0)):
            ob.data.materials.append(mt.m); parts3.append((ob, bone))
    for name, parts in (('L1_Magic', eyes('L1_Magic', 1.0)), ('L2_Magic', eyes('L2_Magic', 1.25) + [(gl, 'hand.L')]), ('L3_Magic', parts3)):
        skin_rigid(name, rig, parts)


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
    for name, (ob, mt, bind) in items.items():   # the pattern maps were only for the bake
        if bake and 'Pat' in ob.data.uv_layers: ob.data.uv_layers.remove(ob.data.uv_layers['Pat'])
    rig = H.build_armature(skeleton(J), J); rig.name = 'PriestRig'; rig.data.name = 'PriestRig'
    rig.data.pose_position = 'REST'; H._upd()
    H.activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for name, (ob, mt, bind) in items.items():
        if ob is body or bind.startswith('later:'): continue
        if bind == 'robe':   # weighted from the copy made before the sleeves flared
            ref = BINDREF[name]; H.bind_skin(ref, rig, body)
            for g in ref.vertex_groups: ob.vertex_groups.new(name=g.name)
            for v in ref.data.vertices:
                for ge in v.groups: ob.vertex_groups[ref.vertex_groups[ge.group].name].add([v.index], ge.weight, 'REPLACE')
            bpy.data.objects.remove(ref)
            mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw; m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig
        elif bind in ('skin', 'hang', 'pelt'):
            H.bind_skin(ob, rig, body)
            if bind == 'hang': hang_weights(ob, .99, .74, 1.0, 6)
            if bind == 'pelt': hang_weights(ob, 1.0, .5, .5, 3)
        else: H.bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; H._upd()
    st, _, _ = poses(J); H.pose(rig, st())
    place(rig, items)
    return rig, actions(rig, J)

def views(rig, prefix, level, action='Idle', frame=1, res=(300, 500), samples=24):
    """Front, side (his left) and back at once, for comparing with the sheets."""
    cams = [((0, -4.2, .95), (90, 0, 0)), ((4.2, 0, .95), (90, 0, 90)), ((0, 4.2, .95), (90, 0, 180))]
    paths = []
    for k, cam in enumerate(cams):
        p = f'{prefix}_{k}.png'; H.render(rig, p, action, frame, level, cam, res, samples); paths.append(p)
    from PIL import Image
    ims = [Image.open(p) for p in paths]; out = Image.new('RGB', (sum(i.width for i in ims), ims[0].height))
    x = 0
    for im in ims: out.paste(im, (x, 0)); x += im.width
    out.save(prefix + '.png')
    for p in paths: os.remove(p)

if __name__ == '__main__':
    rig, acts = build('--nobake' not in sys.argv)
    H.export(rig, os.path.join(OUT, 'priest.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'priest.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3): views(rig, os.path.join(OUT, f'priest_L{lv}'), lv)
    print('built', [a.name for a in acts])
