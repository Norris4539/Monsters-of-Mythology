"""Realistic Hoplite line, built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow):
    python tools/blender/fetch_makehuman.py third_party/makehuman
    python tools/blender/hoplite.py third_party/makehuman assets/models [--renders]
The first command downloads the MakeHuman base mesh and shape targets (CC0).

Body: the MakeHuman base mesh morphed to a young, athletic Mediterranean man, 1.76 m.
Kit at historical scale, fitted to the body: the muscle cuirass, linothorax and
greaves are grown from the body's own surface; the chiton and cloaks are draped
with Blender's cloth simulation. Materials are procedural and baked to textures
(colour, roughness, normal) so they survive export to the browser.

Levels share one skeleton and animation set; kit nodes are named L1_, L2_, L3_
or L23_ (levels 2 and 3), the rest are worn by every level.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mhbody import load_mh

ARGS = [a for a in sys.argv[1:] if os.path.isdir(a)]
MH, OUT = ARGS[0], ARGS[1]
random.seed(11)
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.render.engine = 'CYCLES'; SC.cycles.device = 'CPU'


# ── Generic helpers ─────────────────────────────────────────────────────────
def link(ob): SC.collection.objects.link(ob); return ob

def obj_from_bm(name, bm, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me))
    for p in me.polygons: p.use_smooth = smooth
    return ob

def bake_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data; ob.modifiers.clear(); ob.data = me
    if old.users == 0: bpy.data.meshes.remove(old)
    return ob

def mod(ob, kind, **kw):
    m = ob.modifiers.new(kind.lower(), kind)
    for k, v in kw.items(): setattr(m, k, v)
    return m

def activate(ob):
    bpy.ops.object.select_all(action='DESELECT'); ob.select_set(True); bpy.context.view_layer.objects.active = ob

def lathe(name, prof, segs=48):
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in prof]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=segs, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    return obj_from_bm(name, bm)

def smart_uv(ob, margin=.02):
    activate(ob); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c)


# ── Body ────────────────────────────────────────────────────────────────────
TARGETS = [('caucasian-male-young.target', .8), ('african-male-young.target', .1), ('asian-male-young.target', .1),
           ('universal-male-young-maxmuscle-averageweight.target', .7), ('universal-male-young-averagemuscle-minweight.target', .3)]
HEIGHT = 1.76

def build_body():
    vs, vts, groups, J = load_mh(os.path.join(MH, 'base.obj'), [(os.path.join(MH, f), w) for f, w in TARGETS])
    ground = J['ground'].z
    used = sorted({i for fc in groups['body'] for i, _ in fc})
    k = HEIGHT / (max(vs[i].z for i in used) - ground)
    for v in vs: v.z -= ground; v *= k
    for j in J: J[j] = (J[j] - V((0, 0, ground))) * k
    remap = {o: n for n, o in enumerate(used)}
    me = bpy.data.meshes.new('Body')
    me.from_pydata([tuple(vs[i]) for i in used], [], [[remap[i] for i, _ in fc] for fc in groups['body']])
    uv = me.uv_layers.new(name='UV'); li = 0
    for fc in groups['body']:
        for _, t in fc: uv.data[li].uv = vts[t] if t is not None else (0, 0); li += 1
    ob = link(bpy.data.objects.new('Body', me))
    for p in me.polygons: p.use_smooth = True
    return ob, J

def region_shell(name, src, keep, offset, smooth=0, factor=.5, guard=None):
    """Copy the faces of src whose centre passes keep(), push them out along the
    normals and optionally smooth them, never closer than `guard` to src."""
    bm = bmesh.new(); bm.from_mesh(src.data); bm.normal_update()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for v in bm.verts: v.co += v.normal * offset
    for layer in list(bm.loops.layers.uv.values()): bm.loops.layers.uv.remove(layer)
    for _ in range(smooth):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if guard:
        bvh = BVHTree.FromObject(src, bpy.context.evaluated_depsgraph_get())
        for v in bm.verts:
            loc, no, fi, d = bvh.find_nearest(v.co)
            if loc is not None and d < guard:
                dirv = (v.co - loc); dirv = dirv.normalized() if dirv.length > 1e-6 else no
                v.co = loc + dirv * guard
    return obj_from_bm(name, bm)


def envelope(name, src, keep, centre, guard, iters=60):
    """A smooth hull over part of src: radii from `centre` are averaged with their
    neighbours but never come closer than `guard` to src. Bridges over lips and
    chin like a helmet does, leaving a ridge over the nose."""
    bm = bmesh.new(); bm.from_mesh(src.data); bm.normal_update()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f.calc_center_median())], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    for layer in list(bm.loops.layers.uv.values()): bm.loops.layers.uv.remove(layer)
    bvh = BVHTree.FromObject(src, bpy.context.evaluated_depsgraph_get())
    dirs, rmin = [], []
    for v in bm.verts:
        d = (v.co - centre).normalized(); dirs.append(d)
        hit = bvh.ray_cast(centre, d, .3)   # first surface outward from inside the skull
        rb = (hit[0] - centre).length if hit[0] else (v.co - centre).length
        rmin.append(max(rb, min((v.co - centre).length, rb + .01)) + guard)
    bm.verts.index_update()
    r = list(rmin)
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    for _ in range(iters):
        r = [max(rmin[i], .5 * r[i] + .5 * sum(r[j] for j in nbr[i]) / max(1, len(nbr[i]))) for i in range(len(r))]
    for i, v in enumerate(bm.verts): v.co = centre + dirs[i] * r[i]
    return obj_from_bm(name, bm)

# ── Procedural materials, baked to textures later ───────────────────────────
class Mat:
    """A node-built material. color/rough/bump are output sockets fed to a Principled BSDF."""
    def __init__(self, name, metal=0.0, res=512, sss=0.0):
        self.m = bpy.data.materials.new(name); self.m.use_nodes = True
        self.nt = self.m.node_tree; self.N = self.nt.nodes; self.L = self.nt.links
        self.bsdf = self.N['Principled BSDF']; self.bsdf.inputs['Metallic'].default_value = metal
        if sss: self.bsdf.inputs['Subsurface Weight'].default_value = sss
        self.res = res; self.metal = metal
        self.coord = self.N.new('ShaderNodeTexCoord')
    def node(self, kind, **inputs):
        n = self.N.new(kind)
        for k, v in inputs.items():
            if k in n.inputs and not hasattr(v, 'links'): n.inputs[k].default_value = v
            elif hasattr(v, 'links'): self.L.new(v, n.inputs[k])
            else: setattr(n, k, v)
        return n
    def noise(self, scale, detail=4, rough=.5, vec='Object', **kw):
        n = self.node('ShaderNodeTexNoise', Scale=scale, Detail=detail, Roughness=rough)
        self.L.new(self.coord.outputs[vec], n.inputs['Vector']); return n
    def ramp(self, fac, stops):
        r = self.N.new('ShaderNodeValToRGB'); self.L.new(fac, r.inputs['Fac'])
        cr = r.color_ramp; cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
        cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
        for p, c in stops[1:-1]: e = cr.elements.new(p); e.color = (*c, 1)
        return r
    def mix(self, a, b, fac, blend='MIX'):
        n = self.N.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = blend
        for sock, v in (('A', a), ('B', b)):
            s = n.inputs[sock] if sock == 'A' else n.inputs[sock]
            tgt = [i for i in n.inputs if i.name == sock and i.type == 'RGBA'][0]
            if hasattr(v, 'links'): self.L.new(v, tgt)
            else: tgt.default_value = (*v, 1)
        f = n.inputs['Factor'] if 'Factor' in n.inputs else n.inputs[0]
        if hasattr(fac, 'links'): self.L.new(fac, f)
        else: f.default_value = fac
        return [o for o in n.outputs if o.type == 'RGBA'][0]
    def set(self, color=None, rough=None, bump=None, bump_strength=.4, bump_dist=.002):
        if color is not None:
            if hasattr(color, 'links'): self.L.new(color, self.bsdf.inputs['Base Color'])
            else: self.bsdf.inputs['Base Color'].default_value = (*color, 1)
        if rough is not None:
            if hasattr(rough, 'links'): self.L.new(rough, self.bsdf.inputs['Roughness'])
            else: self.bsdf.inputs['Roughness'].default_value = rough
        if bump is not None:
            b = self.node('ShaderNodeBump', Strength=bump_strength, Distance=bump_dist)
            self.L.new(bump, b.inputs['Height']); self.L.new(b.outputs['Normal'], self.bsdf.inputs['Normal'])
        return self

def m_bronze(name='Bronze', patina=.35, res=512):
    m = Mat(name, metal=1.0, res=res)
    big = m.noise(6, 6, .55); fine = m.noise(80, 3, .6)
    vor = m.node('ShaderNodeTexVoronoi', Scale=55.0); m.L.new(m.coord.outputs['Object'], vor.inputs['Vector'])
    base = m.ramp(big.outputs['Fac'], [(.3, srgb('#7a4f24')), (.55, srgb('#b07a3c')), (.75, srgb('#d6a45a'))])
    pat = m.ramp(m.noise(14, 5, .65).outputs['Fac'], [(.55, (0, 0, 0)), (.75, (1, 1, 1))])
    col = m.mix(base.outputs['Color'], srgb('#4f7f62'), pat.outputs['Color'])
    col = m.mix(col, base.outputs['Color'], 1 - patina)
    rough = m.ramp(fine.outputs['Fac'], [(.35, (.22, .22, .22)), (.7, (.5, .5, .5))])
    m.set(col, rough.outputs['Color'], vor.outputs['Distance'], .25, .0015)
    return m

def m_skin(eye=None):
    m = Mat('Skin', res=1024, sss=.12)
    m.bsdf.inputs['Subsurface Radius'].default_value = (.9, .35, .2)
    tone = m.noise(9, 5, .55)
    col = m.ramp(tone.outputs['Fac'], [(.35, srgb('#a2643f')), (.55, srgb('#bb7a52')), (.75, srgb('#c98e66'))])
    red = m.ramp(m.noise(3, 3, .5).outputs['Fac'], [(.5, (0, 0, 0)), (.75, (1, 1, 1))])
    c2 = m.mix(col.outputs['Color'], srgb('#b2563f'), red.outputs['Color'])
    c2 = m.mix(col.outputs['Color'], c2, .35)
    if eye is not None:   # eyebrows painted into the skin: a tapered arch of fine strokes
        sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
        ax = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(sep.outputs['X'], ax.inputs[0])
        arch = m.node('ShaderNodeMath', operation='MULTIPLY_ADD'); m.L.new(ax.outputs[0], arch.inputs[0]); arch.inputs[1].default_value = -.12; arch.inputs[2].default_value = eye.z + .024
        dz = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['Z'], dz.inputs[0]); m.L.new(arch.outputs[0], dz.inputs[1])
        adz = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(dz.outputs[0], adz.inputs[0])
        band = m.node('ShaderNodeMapRange', **{'From Min': .0055, 'From Max': .002}); m.L.new(adz.outputs[0], band.inputs['Value'])
        span = m.node('ShaderNodeMapRange', **{'From Min': .056, 'From Max': .03}); m.L.new(ax.outputs[0], span.inputs['Value'])
        inner = m.node('ShaderNodeMapRange', **{'From Min': .008, 'From Max': .014}); m.L.new(ax.outputs[0], inner.inputs['Value'])
        front = m.node('ShaderNodeMapRange', **{'From Min': eye.y + .02, 'From Max': eye.y + .005}); m.L.new(sep.outputs['Y'], front.inputs['Value'])
        strokes = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=900.0, Distortion=2.0); m.L.new(m.coord.outputs['Object'], strokes.inputs['Vector'])
        mk = band.outputs[0]
        for other in (span.outputs[0], inner.outputs[0], front.outputs[0], strokes.outputs['Fac']):
            mm = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(mk, mm.inputs[0]); m.L.new(other, mm.inputs[1]); mk = mm.outputs[0]
        c2 = m.mix(c2, srgb('#2a1a10'), mk)
    pores = m.noise(900, 2, .5)
    m.set(c2, .52, pores.outputs['Fac'], .15, .0006)
    return m

def m_cloth(name, hexcol, weave=600, var=.06, res=512, rough=.9):
    m = Mat(name, res=res)
    w1 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=weave); m.L.new(m.coord.outputs['UV'], w1.inputs['Vector'])
    w2 = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Y', Scale=weave); m.L.new(m.coord.outputs['UV'], w2.inputs['Vector'])
    weave_ = m.mix(w1.outputs['Color'], w2.outputs['Color'], .5)
    c = srgb(hexcol); dark = tuple(x * (1 - var * 3) for x in c)
    col = m.ramp(m.noise(18, 4, .6).outputs['Fac'], [(.3, dark), (.7, c)])
    m.set(col.outputs['Color'], rough, weave_, .25, .001)
    return m

def m_linen_band(name, base, band, top, bot):
    """Linen with painted borders (object-space Z bands) in a stepped meander colour."""
    m = m_cloth(name, base, 700, .04, 1024)
    cloth_col = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    masks = []
    for z0 in (top, bot):
        d = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['Z'], d.inputs[0]); d.inputs[1].default_value = z0
        a_ = m.node('ShaderNodeMath', operation='ABSOLUTE'); m.L.new(d.outputs[0], a_.inputs[0])
        lt = m.node('ShaderNodeMath', operation='LESS_THAN'); m.L.new(a_.outputs[0], lt.inputs[0]); lt.inputs[1].default_value = .022
        masks.append(lt)
    mx = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(masks[0].outputs[0], mx.inputs[0]); m.L.new(masks[1].outputs[0], mx.inputs[1])
    wave = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=40.0); m.L.new(m.coord.outputs['Object'], wave.inputs['Vector'])
    pat = m.ramp(wave.outputs['Fac'], [(.45, srgb(band)), (.55, srgb('#a8322a'))])
    col = m.mix(cloth_col, pat.outputs['Color'], mx.outputs[0])
    m.L.new(col, m.bsdf.inputs['Base Color'])
    return m

def m_leather(name, hexcol, res=512):
    m = Mat(name, res=res)
    grain = m.node('ShaderNodeTexVoronoi', Scale=180.0); m.L.new(m.coord.outputs['Object'], grain.inputs['Vector'])
    c = srgb(hexcol)
    col = m.ramp(m.noise(20, 5, .6).outputs['Fac'], [(.3, tuple(x * .6 for x in c)), (.7, c)])
    m.set(col.outputs['Color'], .62, grain.outputs['Distance'], .2, .001)
    return m

def m_wood(name='Ash', res=512):
    m = Mat(name, res=res)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (60, 60, 1.5)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=1.0, Distortion=3.0, Detail=4.0); m.L.new(mp.outputs['Vector'], w.inputs['Vector'])
    col = m.ramp(w.outputs['Fac'], [(.2, srgb('#8a6238')), (.6, srgb('#b48a5a')), (.9, srgb('#c49c6c'))])
    m.set(col.outputs['Color'], .55, w.outputs['Fac'], .1, .001)
    return m

def m_iron(name='Iron', res=256):
    m = Mat(name, metal=1.0, res=res)
    col = m.ramp(m.noise(30, 5, .6).outputs['Fac'], [(.4, srgb('#5d5f62')), (.7, srgb('#9ea2a6'))])
    m.set(col.outputs['Color'], .38, m.noise(120, 3).outputs['Fac'], .2, .0008)
    return m

def m_hair(name, hexcol, res=512):
    m = Mat(name, res=res)
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=180.0, Distortion=4.0, Detail=3.0); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    c = srgb(hexcol)
    col = m.ramp(w.outputs['Fac'], [(.2, tuple(x * .5 for x in c)), (.8, c)])
    m.set(col.outputs['Color'], .7, w.outputs['Fac'], .6, .002)
    return m

def m_flat(name, hexcol, rough=.5, metal=0.0):
    m = Mat(name, metal=metal, res=0); m.set(srgb(hexcol), rough); return m

def m_painted(name, img, metal_bg=False, res=1024):
    """Painted shield face: the blazon worn through to bronze at chips and the rim."""
    m = Mat(name, metal=0.0, res=res)
    t = m.node('ShaderNodeTexImage'); t.image = img; m.L.new(m.coord.outputs['UV'], t.inputs['Vector'])
    chips = m.ramp(m.noise(22, 6, .7).outputs['Fac'], [(.66, (0, 0, 0)), (.7, (1, 1, 1))])
    dirt = m.ramp(m.noise(5, 4, .6).outputs['Fac'], [(.3, (1, 1, 1)), (.8, (.75, .7, .62))])
    col = m.mix(t.outputs['Color'], srgb('#b07a3c'), chips.outputs['Color'])
    col = m.mix(col, dirt.outputs['Color'], 1.0, 'MULTIPLY')
    rough = m.ramp(chips.outputs['Color'], [(0, (.55, .55, .55)), (1, (.3, .3, .3))])
    m.set(col, rough.outputs['Color'], m.noise(60, 4).outputs['Fac'], .15, .001)
    return m


# ── Shield blazons (painted in the black-figure manner) ─────────────────────
def blazon(kind):
    from PIL import Image, ImageDraw, ImageFilter
    S = 1024; im = Image.new('RGB', (S, S), (0, 0, 0)); d = ImageDraw.Draw(im); m = S / 2
    blk, red, cream = (26, 20, 16), (128, 30, 22), (226, 214, 188)
    if kind == 1:   # Ephebe: plain ochre with the lambda of the city levy
        d.rectangle((0, 0, S, S), fill=(170, 120, 60))
        d.polygon([(m, 210), (m + 210, 760), (m + 120, 760), (m, 420), (m - 120, 760), (m - 210, 760)], fill=blk)
    elif kind == 2:   # Hoplite: gorgoneion on bronze
        d.rectangle((0, 0, S, S), fill=(176, 122, 60))
        for k in range(18):
            a = k / 18 * 2 * math.pi
            pts = [(m + math.cos(a + t * .5) * (175 + t * 150), m + math.sin(a + t * .5) * (175 + t * 150)) for t in [i / 10 for i in range(11)]]
            d.line(pts, fill=blk, width=22, joint='curve'); x, y = pts[-1]; d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=blk)
        d.ellipse((m - 185, m - 185, m + 185, m + 185), fill=blk)
        for dx in (-72, 72):
            d.ellipse((m + dx - 40, m - 80, m + dx + 40, m - 10), fill=cream); d.ellipse((m + dx - 17, m - 62, m + dx + 17, m - 28), fill=red)
        d.chord((m - 100, m + 10, m + 100, m + 140), 0, 180, fill=cream); d.ellipse((m - 26, m + 60, m + 26, m + 170), fill=red)
        for t in range(-4, 5): d.line((m + t * 20, m + 75, m + t * 20, m + 100), fill=blk, width=7)
    else:   # Sacred Band: club of Heracles on cream with a red border
        d.rectangle((0, 0, S, S), fill=cream); d.ellipse((40, 40, S - 40, S - 40), outline=red, width=46)
        d.polygon([(m - 40, m + 330), (m + 40, m + 330), (m + 120, m - 300), (m, m - 380), (m - 120, m - 300)], fill=blk)
        for k in range(10):
            t = k / 9; y = m + 260 - t * 600; w = 50 + 70 * t; x = m + (w if k % 2 else -w)
            d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=blk)
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    p = os.path.join(OUT, f'blazon{kind}.png'); im.save(p)
    img = bpy.data.images.load(p); img.pack(); return img


# ── Kit ─────────────────────────────────────────────────────────────────────
def kit(body, J):
    out = {}   # name -> (object, material, bind)  bind: bone name for rigid, 'skin' for skinned
    def add(ob, mt, bind): out[ob.name] = (ob, mt, bind); return ob
    head, neck, eye = J['head'], J['neck'], J['l-eye']
    sh_z = J['l-shoulder'].z

    # Hair, beard, brows: thin shells grown from the face
    def in_beard(c):
        mz = J['mouth'].z
        if c.z > mz + .014 or c.z < J['jaw'].z - .08 or c.y > head.y + .02 or c.z < neck.z + .03: return False
        if c.z > mz - .004 and abs(c.x) > .03: return False          # keep the cheeks bare above the mouth
        return abs(c.x) < .072
    beard = region_shell('L23_Beard', body, in_beard, .0, 0)
    bvh_b = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    bm = bmesh.new(); bm.from_mesh(beard.data); bm.normal_update(); bm.verts.index_update()
    edge = [v for v in bm.verts if v.is_boundary]; dist = {v.index: 0 for v in edge}; front = list(edge)
    while front:   # hops from the beard's edge
        nxt = []
        for v in front:
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.index not in dist: dist[o.index] = dist[v.index] + 1; nxt.append(o)
        front = nxt
    nz = lambda p: math.sin(p.x * 310) * math.sin(p.z * 270 + p.x * 90) * math.sin(p.y * 330)
    for v in bm.verts:
        k = min(1, dist.get(v.index, 0) / 4)
        chin = max(0, (J['mouth'].z - .02 - v.co.z)) * .35
        loc, no, fi, d = bvh_b.find_nearest(v.co)
        nrm = no if no is not None else v.normal   # the skin's outward normal
        v.co = (loc if loc is not None else v.co) + nrm * ((.0018 + .0042 * k + chin * .7 * k) * (1 + .3 * nz(v.co)))
    bm.to_mesh(beard.data); bm.free()
    mod(beard, 'SUBSURF', levels=1, render_levels=1); bake_mods(beard)
    add(beard, m_hair('Beard', '#46301e'), 'head')
    hair = region_shell('Hair', body, lambda c: (c.z > eye.z + .045 and c.y > eye.y + .055) or (c.z > eye.z + .085) or (c.z > J['jaw'].z - .01 and c.y > head.y + .035 and c.z > neck.z + .04), .006, 3, .5, guard=.005)
    add(hair, m_hair('Hair', '#2a1a10'), 'head')
    for s, side in ((1, 'l'), (-1, 'r')):
        e = J[f'{side}-eye']
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.0118, segments=24, ring_count=16, location=e + V((0, .004, 0)))
        ob = bpy.context.object; ob.name = 'Eye' + side.upper()
        em = Mat('Eye', res=128)
        grad = em.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
        mp = em.node('ShaderNodeMapping'); em.L.new(em.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (95, 95, 95); mp.inputs['Location'].default_value = (0, .0118 * 95, 0)   # centre the iris on the front of the eye
        em.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
        col = em.ramp(grad.outputs['Fac'], [(.0, srgb('#efe8de')), (.55, srgb('#efe8de')), (.6, srgb('#4a2c18')), (.85, srgb('#2a170c')), (.88, (0.01, .01, .01))])
        em.set(col.outputs['Color'], .15)
        add(ob, em, 'head')

    # Helmets ---------------------------------------------------------------
    bronze = m_bronze('Bronze', .3, 512)
    hc = V((0, eye.y + .085, eye.z - .005))   # centre of the skull
    def helmet_shell(name, open_face=False):
        keep = lambda c: c.z > J['jaw'].z - .045 and c.z > neck.z + .02 and (c.y > head.y - .02 or c.z > eye.z + .03 or not open_face)
        return envelope(name, body, keep, hc, .014)
    cor = helmet_shell('L2_Helmet')
    # Corinthian T-shaped opening: eye slits joined to a central slot over the mouth
    bm = bmesh.new()
    for x0, x1, z0, z1 in ((-.068, -.009, eye.z - .02, eye.z + .017), (.009, .068, eye.z - .02, eye.z + .017), (-.019, .019, J['jaw'].z - .08, eye.z - .018)):
        bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation(((x0 + x1) / 2, head.y - .12, (z0 + z1) / 2)) @ Matrix.Diagonal((x1 - x0, .14, z1 - z0, 1)))
    cut = obj_from_bm('cut', bm, False); mod(cor, 'BOOLEAN', object=cut, operation='DIFFERENCE', solver='EXACT'); bake_mods(cor); bpy.data.objects.remove(cut)
    mod(cor, 'SOLIDIFY', thickness=.003, offset=1); mod(cor, 'SUBSURF', levels=1, render_levels=1); bake_mods(cor)
    add(cor, bronze, 'head')
    att = helmet_shell('L3_Helmet', open_face=True)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation((0, head.y - .09, (eye.z - .03 + J['jaw'].z - .08) / 2)) @ Matrix.Diagonal((.13, .12, (eye.z + .012) - (J['jaw'].z - .08), 1)))
    cut = obj_from_bm('cut', bm, False); mod(att, 'BOOLEAN', object=cut, operation='DIFFERENCE', solver='EXACT'); bake_mods(att); bpy.data.objects.remove(cut)
    mod(att, 'SOLIDIFY', thickness=.003, offset=1); mod(att, 'SUBSURF', levels=1, render_levels=1); bake_mods(att)
    add(att, bronze, 'head')
    brim = lathe('L3_Brim', [(.095, 0), (.112, -.004), (.115, -.008)], 48); brim.scale = (.95, 1.08, 1); brim.location = (0, head.y - .005, eye.z + .02)
    mod(brim, 'SOLIDIFY', thickness=.002); bake_mods(brim); add(brim, m_bronze('Gilt', .05, 256), 'head')
    pil = lathe('L1_Pilos', [(0, .175), (.03, .165), (.065, .11), (.09, .05), (.1, 0), (.103, -.012)], 48)
    pil.location = (0, head.y + .008, eye.z + .026); pil.scale = (1.04, 1.15, 1); mod(pil, 'SOLIDIFY', thickness=.004); bake_mods(pil)
    add(pil, m_cloth('Felt', '#7d5a36', 250, .1, 512, .95), 'head')
    # Crests: horsehair on a bronze stilt
    def crest(name, hexa, hexb, z0, length=.36, tall=.13, width=.04, tail=.18):
        bm = bmesh.new(); n = 24; rows = []
        for i in range(n + 1):
            t = i / n; y = (t - .42) * length
            h = tall * math.sin(min(1, t * 1.35) * math.pi / 2) ** .7 * (1 - .15 * t)
            drop = max(0, t - .85) / .15 * tail
            rows.append([bm.verts.new((sx * width / 2 * (1 - .4 * t), y, (h - drop) * kk + (-drop * .6 if kk == 0 else 0))) for sx in (-1, 1) for kk in (0, 1)])
        for i in range(n):
            a, b = rows[i], rows[i + 1]
            for q in ((a[0], b[0], b[1], a[1]), (a[2], a[3], b[3], b[2]), (a[1], b[1], b[3], a[3]), (a[0], a[2], b[2], b[0])): bm.faces.new(q)
        ob = obj_from_bm(name, bm); mod(ob, 'SUBSURF', levels=2, render_levels=2); bake_mods(ob)
        ob.location = (0, head.y + .01, z0)
        add(ob, m_hair(name + 'Mat', hexa), 'head')
        st = lathe(name + 'Stilt', [(.008, -.04), (.01, 0), (.014, .012), (.008, .02)], 16); st.location = (0, head.y + .0, z0)
        add(st, bronze, 'head')
    top = max((body.matrix_world @ v.co).z for v in body.data.vertices) + .016
    crest('L2_Crest', '#1d1712', '#e8e0d0', top + .025)
    crest('L3_Crest', '#8e1a14', '#8e1a14', top + .03, .4, .16, .045)

    # Body armour ------------------------------------------------------------
    torso = lambda z0, z1, w: (lambda c: z0 < c.z < z1 and abs(c.x) < w)
    cuirass = region_shell('L3_Cuirass', body, torso(.93, sh_z + .035, .2), .018, 3, .5, guard=.015)
    mod(cuirass, 'SOLIDIFY', thickness=.003, offset=1); mod(cuirass, 'SUBSURF', levels=1, render_levels=1); bake_mods(cuirass)
    add(cuirass, m_bronze('BronzeCuirass', .25, 1024), 'skin')
    lino = region_shell('L2_Linothorax', body, torso(.9, sh_z + .03, .205), .024, 14, .6, guard=.02)
    mod(lino, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(lino)
    add(lino, m_linen_band('Linothorax', '#e4dbc4', '#2b4d8f', 1.0, sh_z - .02), 'skin')
    tunic = region_shell('L1_Tunic', body, torso(.9, sh_z + .03, .21), .008, 6, .5, guard=.006)
    mod(tunic, 'SOLIDIFY', thickness=.002, offset=1); bake_mods(tunic)
    add(tunic, m_cloth('Tunic', '#cdbf9c', 500, .08), 'skin')
    for name, z0 in (('L23_Greaves', 0),):
        for side in ('l', 'r'):
            kz, az = J[f'{side}-knee'].z, J[f'{side}-ankle'].z
            g = region_shell(f'L23_Greave{side.upper()}', body, (lambda kz, az, sx: lambda c: az + .05 < c.z < kz + .05 and c.x * sx > .03)(kz, az, 1 if side == 'l' else -1), .0045, 1, .4, guard=.0035)
            mod(g, 'SOLIDIFY', thickness=.002, offset=1); mod(g, 'SUBSURF', levels=1, render_levels=1); bake_mods(g)
            add(g, bronze, f'shin.{side.upper()}')
    # Pteruges: two layers of strips around the hips
    def pteruges(name, hexcol, z=.94, n=28, length=.17):
        bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
        bm = bmesh.new()
        for L in range(2):
            for i in range(n):
                a = (i + L * .5) / n * 2 * math.pi
                d = V((math.cos(a), math.sin(a), 0))
                hit = bvh.ray_cast(V((0, 0, z - L * .04)) + d * .6, -d)
                r = (hit[0] - V((0, 0, z - L * .04))).length if hit[0] else .18
                c = V((0, 0, z - L * .04)) + d * (r + .03 + L * .008)
                ln = length + L * .045
                m = Matrix.Translation(c - V((0, 0, ln / 2))) @ Matrix.Rotation(math.atan2(d.y, d.x) - math.pi / 2, 4, 'Z') @ Matrix.Rotation(-.1 - L * .04, 4, 'X') @ Matrix.Diagonal((.036, .004, ln, 1))
                bmesh.ops.create_cube(bm, size=1, matrix=m)
        ob = obj_from_bm(name, bm, smooth=False)
        mod(ob, 'BEVEL', width=.0015, segments=1); bake_mods(ob)
        return ob
    add(pteruges('L2_Pteruges', '#e4dbc4'), m_cloth('Strips', '#e2d6bc', 400, .05), 'skin')
    add(pteruges('L3_Pteruges', '#7a2a1c'), m_leather('RedLeather', '#7c2a1c'), 'skin')

    # Sandals --------------------------------------------------------------
    leather = m_leather('Leather', '#6a4022')
    for side in ('l', 'r'):
        S = side.upper(); an = J[f'{side}-ankle']
        foot_pts = [(body.matrix_world @ v.co) for v in body.data.vertices if (body.matrix_world @ v.co).z < .03 and abs((body.matrix_world @ v.co).x - an.x) < .09]
        bm = bmesh.new()
        for p in foot_pts: bm.verts.new((p.x, p.y, 0.0)); bm.verts.new((p.x, p.y, .012))
        bmesh.ops.convex_hull(bm, input=bm.verts)
        so = obj_from_bm(f'Sole{S}', bm, False); mod(so, 'BEVEL', width=.003, segments=2); bake_mods(so)
        so.scale = (1.06, 1.04, 1); add(so, leather, f'foot.{S}')
        for zz, yy, rr in ((an.z + .015, an.y + .01, .047), (.045, an.y - .1, .045)):
            st = lathe(f'Strap{S}{zz:.2f}', [(rr, -.006), (rr + .002, 0), (rr, .006)], 24); st.location = (an.x, yy, zz); st.scale = (1, 1.15, 1)
            add(st, leather, f'foot.{S}')

    # Shield and spear: built about their own origin (shield: +Z faces the enemy,
    # spear: +Z towards the point, grip at the origin) and put in the hands later.
    for lv in (1, 2, 3):
        R, rim = .45, .045
        face = lathe(f'L{lv}_ShieldFace', [(0, .12), (.15, .113), (.28, .09), (.37, .055), (R - rim, .01)], 64)
        me = face.data; uvl = me.uv_layers.new(name='UV')
        for poly in me.polygons:
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uvl.data[li].uv = (co.x / (2 * (R - rim)) + .5, co.y / (2 * (R - rim)) + .5)
        rimo = lathe(f'L{lv}_ShieldRim', [(R - rim, .01), (R - rim * .5, .02), (R, .012), (R + .004, -.005), (R - .006, -.012)], 64)
        back = lathe(f'L{lv}_ShieldBack', [(0, .1), (.2, .085), (R - .01, -.012)], 48)
        add(face, m_painted(f'Blazon{lv}', blazon(lv)), 'later:forearm.L'); add(rimo, bronze, 'later:forearm.L'); add(back, m_wood('ShieldWood'), 'later:forearm.L')
        # porpax: bronze armband at the centre, around the forearm (forearm runs along local X)
        por = lathe(f'L{lv}_Porpax', [(.042, -.018), (.047, 0), (.042, .018)], 24)
        por.rotation_euler.y = math.pi / 2; por.location = (0, 0, .064); por.scale = (1, .75, 1)
        mod(por, 'SOLIDIFY', thickness=.003); bake_mods(por)
        add(por, bronze, 'later:forearm.L')
        # antilabe: the cord grip near the rim, where the hand closes
        ant = lathe(f'L{lv}_Antilabe', [(.022, -.03), (.026, 0), (.022, .03)], 16)
        ant.location = (-.19, 0, .07); ant.scale = (.6, 1, 1)
        add(ant, m_leather('Cord', '#5a3a20'), 'later:forearm.L')
    ash, iron = m_wood('Ash'), m_iron()
    L0, L1 = .8, 1.45
    shaft = lathe('SpearShaft', [(0, -L0), (.013, -L0 + .01), (.0145, 0), (.013, L1), (0, L1 + .005)], 12)
    head_ = lathe('SpearHead', [(.013, L1 - .03), (.026, L1 + .05), (.022, L1 + .16), (0, L1 + .27)], 8); head_.scale = (1, .3, 1)
    butt = lathe('SpearButt', [(0, -L0 - .2), (.014, -L0 - .02), (.0135, -L0 + .02)], 8)
    for o, mt in ((shaft, ash), (head_, iron), (butt, bronze)): add(o, mt, 'later:hand.R')
    return out


# ── Cloth: drape the chiton skirt and the cloaks with the cloth simulator ───
def drape(name, src_ob, pin_fn, collider, frames=45, mass=.3, thickness=.004):
    co = mod(collider, 'COLLISION'); collider.collision.thickness_outer = .006
    cl = mod(src_ob, 'CLOTH'); s = cl.settings
    s.quality = 8; s.mass = mass; s.tension_stiffness = 10; s.compression_stiffness = 10; s.bending_stiffness = .08
    s.air_damping = 1.5
    vg = src_ob.vertex_groups.new(name='pin')
    vg.add([v.index for v in src_ob.data.vertices if pin_fn(v.co)], 1.0, 'REPLACE')
    s.vertex_group_mass = 'pin'
    cl.collision_settings.distance_min = .006; cl.collision_settings.use_self_collision = False
    cl.point_cache.frame_start = 1; cl.point_cache.frame_end = frames
    for f in range(1, frames + 1): SC.frame_set(f)
    bake_mods(src_ob)
    src_ob.vertex_groups.clear()
    collider.modifiers.remove(collider.modifiers['collision'])
    SC.frame_set(1)
    mod(src_ob, 'SOLIDIFY', thickness=thickness, offset=1); bake_mods(src_ob)
    return src_ob

def chiton(name, hexcol, z0=1.0, z1=.68):
    bm = bmesh.new(); nr, nz = 56, 18
    rows = []
    for j in range(nz + 1):
        z = z0 - (z0 - z1) * j / nz; r = .17 + .08 * j / nz
        rows.append([bm.verts.new((math.cos(a) * r * 1.12, math.sin(a) * r * .9, z)) for a in [2 * math.pi * i / nr for i in range(nr)]])
    for j in range(nz):
        for i in range(nr): bm.faces.new((rows[j][i], rows[j][(i + 1) % nr], rows[j + 1][(i + 1) % nr], rows[j + 1][i]))
    ob = obj_from_bm(name, bm)
    return ob

def cloak(name, z_top, w=.56, h=1.0):
    bm = bmesh.new(); nx, nz = 26, 32
    def at(i, j):
        u = i / nx - .5; t = j / nz
        return ((u * w) * (1 + .25 * t), .14 + .22 * u * u * (1 - t * .5), z_top - .07 * (2 * u) ** 2 - t * h)
    g = [[bm.verts.new(at(i, j)) for i in range(nx + 1)] for j in range(nz + 1)]
    for j in range(nz):
        for i in range(nx): bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
    return obj_from_bm(name, bm)


# ── Skeleton from the MakeHuman joints ──────────────────────────────────────
def skeleton_spec(J):
    sp = sorted([J[k] for k in J if k.startswith('spine-')], key=lambda v: v.z)
    mean = lambda ks: sum((J[k] for k in ks), V()) / len(ks)
    B = [('root', (0, 0, 0), (0, .3, 0), None, False),
         ('hips', J['pelvis'], sp[1], 'root', True), ('spine', sp[1], sp[2], 'hips', True),
         ('chest', sp[2], J['neck'], 'spine', True), ('neck', J['neck'], J['head'], 'chest', True),
         ('head', J['head'], J['head'] + V((0, 0, .2)), 'neck', True)]
    for s, n in (('l', 'L'), ('r', 'R')):
        knuck = mean([f'{s}-finger-{k}-2' for k in (2, 3, 4, 5)]); tips = mean([f'{s}-finger-{k}-4' for k in (2, 3, 4, 5)])
        mid = mean([f'{s}-finger-{k}-3' for k in (2, 3, 4, 5)])
        B += [(f'shoulder.{n}', J[f'{s}-clavicle'], J[f'{s}-shoulder'], 'chest', True),
              (f'upperarm.{n}', J[f'{s}-shoulder'], J[f'{s}-elbow'], f'shoulder.{n}', True),
              (f'forearm.{n}', J[f'{s}-elbow'], J[f'{s}-hand'], f'upperarm.{n}', True),
              (f'hand.{n}', J[f'{s}-hand'], knuck, f'forearm.{n}', True),
              (f'fingers.{n}', knuck, mid, f'hand.{n}', True), (f'fingertips.{n}', mid, tips, f'fingers.{n}', True),
              (f'thumb.{n}', J[f'{s}-finger-1-2'], J[f'{s}-finger-1-4'], f'hand.{n}', True),
              (f'thigh.{n}', J[f'{s}-upper-leg'], J[f'{s}-knee'], 'hips', True),
              (f'shin.{n}', J[f'{s}-knee'], J[f'{s}-ankle'], f'thigh.{n}', True),
              (f'ik_foot.{n}', J[f'{s}-ankle'], J[f'{s}-ankle'] + V((0, .12, 0)), 'root', False),   # foot control
              (f'foot.{n}', J[f'{s}-ankle'], J[f'{s}-foot-2'], f'ik_foot.{n}', True)]
    return B

def build_armature(B, J):
    arm = bpy.data.armatures.new('HopliteRig'); ob = link(bpy.data.objects.new('HopliteRig', arm))
    activate(ob); bpy.ops.object.mode_set(mode='EDIT')
    for name, h, t, parent, deform in B:
        b = arm.edit_bones.new(name); b.head = h; b.tail = t; b.roll = 0; b.use_deform = deform
        if parent: b.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in ob.pose.bones: pb.rotation_mode = 'QUATERNION'
    # Hand reference vectors in each hand bone's own frame: the knuckle line
    # (index to little finger) and the palm normal.
    for s, n in (('l', 'L'), ('r', 'R')):
        bone = arm.bones[f'hand.{n}']; inv = bone.matrix_local.to_3x3().inverted()
        k = J[f'{s}-finger-5-2'] - J[f'{s}-finger-2-2']
        y = (bone.tail_local - bone.head_local).normalized()
        palm = k.cross(y).normalized()
        if palm.x * (1 if n == 'L' else -1) > 0: palm = -palm   # in the rest pose the palms face the thighs
        HAND_REF[n] = (inv @ k, inv @ palm)
    return ob

def bind_rigid(ob, rig, bone):
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = bone
    bpy.context.view_layer.update(); ob.matrix_world = mw

def bind_skin(ob, rig, body):
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    names = {g.index: g.name for g in body.vertex_groups}
    for g in body.vertex_groups: ob.vertex_groups.new(name=g.name)
    bme = body.data
    for v in ob.data.vertices:
        loc, no, fi, d = bvh.find_nearest(ob.matrix_world @ v.co)
        if fi is None: continue
        acc = {}
        for vi in bme.polygons[fi].vertices:
            for ge in bme.vertices[vi].groups: acc[ge.group] = acc.get(ge.group, 0) + ge.weight
        tot = sum(acc.values()) or 1
        for gi, w in acc.items():
            if w / tot > .02: ob.vertex_groups[names[gi]].add([v.index], w / tot, 'REPLACE')
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    m = ob.modifiers.new('Armature', 'ARMATURE'); m.object = rig


# ── Posing: limbs solved directly, keyed as plain rotations (no IK at runtime) ─
HAND_REF = {}
def _upd(): bpy.context.view_layer.update()

def two_bone(S, T, a, b, hint):
    """Elbow/knee position for a chain of lengths a, b from S reaching T, bent towards hint."""
    d = T - S; L = min(max(d.length, abs(a - b) + 1e-4), (a + b) * .999); u = d.normalized()
    x = (a * a - b * b + L * L) / (2 * L); h = math.sqrt(max(0, a * a - x * x))
    p = hint - u * hint.dot(u); p = p.normalized() if p.length > 1e-6 else u.orthogonal().normalized()
    return S + u * x + p * h

def swing(rig, name, d_new, twist=0.0):
    """Point a bone along d_new with the smallest rotation from where its parent carries it."""
    pb = rig.pose.bones[name]; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); _upd()
    M = pb.matrix.copy(); d0 = M.col[1].xyz.normalized(); dn = d_new.normalized()
    R = d0.rotation_difference(dn).to_matrix()
    if twist: R = Matrix.Rotation(twist, 3, dn) @ R
    Mn = (R @ M.to_3x3()).to_4x4(); Mn.translation = M.translation
    pb.matrix = Mn; _upd()

def orient(rig, name, y_t, k_t, k_local):
    """Set a bone's full orientation: its axis along y_t and its local vector k_local along k_t."""
    pb = rig.pose.bones[name]; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); _upd()
    M = pb.matrix.copy()
    yl = V((0, 1, 0)); kl = (k_local - yl * k_local.dot(yl)).normalized()
    yt = y_t.normalized(); kt = (k_t - yt * k_t.dot(yt)).normalized()
    Bl = Matrix((kl, yl, kl.cross(yl))).transposed(); Bt = Matrix((kt, yt, kt.cross(yt))).transposed()
    Mn = (Bt @ Bl.inverted()).to_4x4(); Mn.translation = M.translation
    pb.matrix = Mn; _upd()

def curl(rig, side, fist=1.0):
    """Close the fingers and thumb towards the palm."""
    hand = rig.pose.bones[f'hand.{side}']; palm = (hand.matrix.to_3x3() @ HAND_REF[side][1]).normalized()
    for name, ang in ((f'fingers.{side}', 1.35 * fist), (f'fingertips.{side}', 1.45 * fist), (f'thumb.{side}', .55 * fist)):
        pb = rig.pose.bones[name]; pb.rotation_quaternion = (1, 0, 0, 0); _upd()
        d0 = pb.matrix.col[1].xyz.normalized(); ax = d0.cross(palm)
        if ax.length < 1e-6: continue
        swing(rig, name, Matrix.Rotation(ang, 3, ax.normalized()) @ d0)

def pose(rig, P):
    """Apply a pose spec. Body bones take local euler rotations and offsets; feet are
    world offsets of the foot controls; arms are wrist targets and elbow hints given
    in the chest's rest frame, so they ride along with the torso."""
    PB = rig.pose.bones
    for pb in PB: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    for name in ('root', 'hips', 'spine', 'chest', 'neck', 'head', 'ik_foot.L', 'ik_foot.R'):
        p = P.get(name, {})
        PB[name].location = p.get('loc', (0, 0, 0)); PB[name].rotation_quaternion = Euler(p.get('rot', (0, 0, 0))).to_quaternion()
    _upd()
    # Legs: hip to the foot control, knees forward.
    hips_rot = PB['hips'].matrix.to_3x3() @ rig.data.bones['hips'].matrix_local.to_3x3().inverted()
    for n in 'LR':
        th, sh = PB[f'thigh.{n}'], PB[f'shin.{n}']
        S, A = th.head.copy(), PB[f'ik_foot.{n}'].head.copy()
        E = two_bone(S, A, th.bone.length, sh.bone.length, hips_rot @ V((.15 if n == 'L' else -.15, -1, 0)))
        swing(rig, f'thigh.{n}', E - S); swing(rig, f'shin.{n}', A - PB[f'shin.{n}'].head)
    # Arms, relative to the chest.
    D = PB['chest'].matrix @ rig.data.bones['chest'].matrix_local.inverted(); D3 = D.to_3x3()
    for n in 'LR':
        a = P['arm' + n]
        up, fo = PB[f'upperarm.{n}'], PB[f'forearm.{n}']
        S = up.head.copy(); W = D @ V(a['w'])
        E = two_bone(S, W, up.bone.length, fo.bone.length, D3 @ V(a['hint']))
        swing(rig, f'upperarm.{n}', E - S); swing(rig, f'forearm.{n}', W - PB[f'forearm.{n}'].head)
        fdir = (W - E).normalized()
        if 'spear' in a:   # overhand grip: knuckle line along the shaft, towards the point
            sd = (D3 @ V(a['spear'])).normalized()
            orient(rig, f'hand.{n}', fdir - sd * fdir.dot(sd) + D3 @ V(a.get('wrist', (0, 0, 0))), sd, HAND_REF[n][0])
        else:
            swing(rig, f'hand.{n}', fdir + D3 @ V(a.get('wrist', (0, 0, 0))))
        curl(rig, n, a.get('fist', 1.0))

def key_all(rig, f):
    for pb in rig.pose.bones:
        pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)

def make_action(rig, name, frames):
    rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True
    rig.animation_data.action = act
    for f, P in frames: pose(rig, P); key_all(rig, f)
    return act

def poses(J):
    """Pose specs. Arm targets are offsets from each shoulder joint in the rest frame."""
    SR, SL = J['r-shoulder'], J['l-shoulder']
    def armR(w, hint=(-1, .35, .15), spear=(0, -1, -.06), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': spear, **kw}
    def armL(w, hint=(1, .1, -.45), **kw): return {'w': SL + V(w), 'hint': hint, **kw}
    base = {'hips': {'loc': (0, 0, -.05)}, 'chest': {'rot': (.03, 0, .1)}, 'head': {'rot': (-.03, 0, -.08)},
            'ik_foot.L': {'loc': (-.02, -.2, 0)}, 'ik_foot.R': {'loc': (.02, .18, 0)},
            'armR': armR((-.08, -.16, .13)), 'armL': armL((-.17, -.26, -.2))}
    def st(**over):
        P = {k: dict(v) for k, v in base.items()}
        for k, v in over.items(): P[k] = v if k.startswith('arm') else {**P.get(k, {}), **v}
        return P
    return st, armR, armL

def actions(rig, J):
    st, armR, armL = poses(J)
    A = []
    A.append(make_action(rig, 'Idle', [(1, st()), (24, st(hips={'loc': (0, 0, -.058)}, chest={'rot': (.042, 0, .1)}, armR=armR((-.08, -.16, .12)))), (48, st())]))
    W = lambda fl, fr, zl, zr, hz: st(**{'ik_foot.L': {'loc': (-.02, fl, zl)}, 'ik_foot.R': {'loc': (.02, fr, zr)}, 'hips': {'loc': (0, 0, -.05 + hz)}})
    A.append(make_action(rig, 'Walk', [(1, W(-.22, .2, 0, 0, -.012)), (7, W(-.01, -.01, 0, .09, .018)), (13, W(.2, -.22, 0, 0, -.012)), (19, W(-.01, -.01, .09, 0, .018)), (25, W(-.22, .2, 0, 0, -.012))]))
    A.append(make_action(rig, 'Thrust', [
        (1, st()),
        (7, st(chest={'rot': (-.05, 0, .28)}, hips={'loc': (0, .04, -.05)}, armR=armR((-.02, .02, .17), spear=(0, -1, .02)))),
        (11, st(chest={'rot': (.18, 0, -.08)}, hips={'loc': (0, -.13, -.1)}, **{'ik_foot.L': {'loc': (-.02, -.4, 0)}},
                armR=armR((.03, -.44, .05), hint=(-1, .2, .05), spear=(.03, -1, -.12)), armL=armL((-.15, -.22, -.21)))),
        (16, st(chest={'rot': (.16, 0, -.06)}, hips={'loc': (0, -.12, -.1)}, **{'ik_foot.L': {'loc': (-.02, -.4, 0)}},
                armR=armR((.03, -.4, .05), hint=(-1, .2, .05), spear=(.03, -1, -.1)))),
        (25, st())]))
    blk = dict(hips={'loc': (0, .02, -.12)}, chest={'rot': (.11, 0, .18)}, head={'rot': (.08, 0, -.08)},
               armL=armL((-.14, -.33, -.08), hint=(1, .1, -.2)), armR=armR((-.04, -.12, .17), spear=(0, -1, .1)))
    A.append(make_action(rig, 'Block', [(1, st()), (6, st(**blk)), (14, st(**blk)), (20, st())]))
    A.append(make_action(rig, 'Hit', [(1, st()),
        (4, st(chest={'rot': (-.25, 0, .22)}, head={'rot': (-.3, 0, .1)}, hips={'loc': (0, .09, -.07)}, armL=armL((-.17, -.2, -.17)), armR=armR((-.05, -.08, .16), spear=(0, -1, .1)))),
        (9, st(chest={'rot': (-.1, 0, .14)}, head={'rot': (-.12, 0, 0)}, hips={'loc': (0, .04, -.06)})), (17, st())]))
    fallR, fallL = armR((-.2, -.05, -.12), hint=(-1, .2, -.3), spear=(.4, -1, -.35), fist=.8), armL((.05, -.2, -.3), hint=(1, .2, -.5))
    fall = dict(chest={'rot': (-.1, 0, .1)}, hips={'loc': (0, 0, -.1)}, armR=fallR, armL=fallL)
    A.append(make_action(rig, 'Death', [(1, st()),
        (8, st(chest={'rot': (.32, 0, .18)}, head={'rot': (.28, 0, 0)}, hips={'loc': (0, .02, -.22)}, armR=armR((-.12, -.1, .02), spear=(.15, -1, -.3)))),
        (20, st(root={'loc': (0, .27, 0), 'rot': (-1.38, 0, .08)}, head={'rot': (-.3, 0, .2)}, **fall)),
        (25, st(root={'loc': (0, .29, 0), 'rot': (-1.52, 0, .08)}, head={'rot': (-.4, 0, .2)}, **fall)),
        (40, st(root={'loc': (0, .29, 0), 'rot': (-1.5, 0, .08)}, head={'rot': (-.45, 0, .25)}, **fall))]))
    rig.animation_data.action = A[0]
    return A

def place_in_hands(rig, items):
    """In the idle pose, put the spear through the right fist and strap the shield
    to the left forearm, then parent them to those bones."""
    PB = rig.pose.bones
    hand = PB['hand.R']; Mh = hand.matrix.to_3x3()
    palm = (Mh @ HAND_REF['R'][1]).normalized(); k = (Mh @ HAND_REF['R'][0]).normalized()
    grip = hand.head + (hand.tail - hand.head) * .5 + palm * .028
    z = k; x = z.orthogonal().normalized(); y = z.cross(x)
    Ms = Matrix((x, y, z)).transposed().to_4x4(); Ms.translation = grip
    fo = PB['forearm.L']; E, W = fo.head.copy(), fo.tail.copy()
    fdir = (W - E).normalized()
    n = V((0, -1, .05)).normalized(); n = (n - fdir * n.dot(fdir)).normalized()   # face the enemy, square to the forearm
    xs = -fdir; ys = n.cross(xs)   # the hand end of the forearm points to local -X (the antilabe)
    centre = E + (W - E) * .3 - n * .064   # the porpax (local z .064) sits on the forearm near the elbow
    Mf = Matrix((xs, ys, n)).transposed().to_4x4(); Mf.translation = centre
    for name, (ob, mt, bind) in items.items():
        if not bind.startswith('later:'): continue
        bone = bind.split(':')[1]
        ob.matrix_world = (Ms if bone == 'hand.R' else Mf) @ ob.matrix_basis
        bpy.context.view_layer.update()
        bind_rigid(ob, rig, bone)

# ── Bake procedural materials to textures ───────────────────────────────────
def bake_textures(items):
    SC.cycles.samples = 4; SC.render.bake.use_selected_to_active = False; SC.render.bake.margin = 6
    done = {}
    for name, (ob, mt, bind) in items.items():
        if mt.res == 0:   # flat colours need no texture
            ob.data.materials.clear(); ob.data.materials.append(mt.m); continue
        if not ob.data.uv_layers: smart_uv(ob)
        key_ = (mt.m.name, ob.name)
        imgs = {}
        for kind in ('color', 'rough', 'normal'):
            if kind == 'rough' and not mt.bsdf.inputs['Roughness'].links: continue
            r = mt.res if kind == 'color' else max(128, mt.res // 2)
            img = bpy.data.images.new(f'{ob.name}_{kind}', r, r, alpha=False)
            img.colorspace_settings.name = 'sRGB' if kind == 'color' else 'Non-Color'
            imgs[kind] = img
        m = mt.m.copy(); m.name = f'{mt.m.name}_{ob.name}'
        ob.data.materials.clear(); ob.data.materials.append(m)
        nt = m.node_tree; N = nt.nodes; Lk = nt.links
        bsdf = N['Principled BSDF']; outn = N['Material Output']
        tex = N.new('ShaderNodeTexImage'); N.active = tex
        activate(ob)
        for kind, img in imgs.items():
            tex.image = img; N.active = tex
            if kind == 'normal':
                Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface'])
                bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
            else:
                src = bsdf.inputs['Base Color' if kind == 'color' else 'Roughness']
                em = N.new('ShaderNodeEmission')
                if src.links: Lk.new(src.links[0].from_socket, em.inputs['Color'])
                else:
                    v = src.default_value; em.inputs['Color'].default_value = tuple(v) if kind == 'color' else (v, v, v, 1)
                Lk.new(em.outputs['Emission'], outn.inputs['Surface'])
                bpy.ops.object.bake(type='EMIT')
                N.remove(em)
            img.pack()
        # Final, export-friendly material: textures straight into the BSDF.
        for n in list(N):
            if n not in (bsdf, outn): N.remove(n)
        Lk.new(bsdf.outputs['BSDF'], outn.inputs['Surface'])
        for kind, img in imgs.items():
            t = N.new('ShaderNodeTexImage'); t.image = img
            if kind == 'color': Lk.new(t.outputs['Color'], bsdf.inputs['Base Color'])
            elif kind == 'rough': Lk.new(t.outputs['Color'], bsdf.inputs['Roughness'])
            else:
                nm = N.new('ShaderNodeNormalMap'); Lk.new(t.outputs['Color'], nm.inputs['Color']); Lk.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        print('baked', ob.name, list(imgs))


# ── Build ───────────────────────────────────────────────────────────────────
def build():
    body, J = build_body()
    items = kit(body, J)
    items['Body'] = (body, m_skin(J['l-eye']), 'body')
    # cloth
    sk = chiton('L23_Chiton', '#e6dcc4'); drape('L23_Chiton', sk, lambda c: c.z > .985, body)
    items['L23_Chiton'] = (sk, m_cloth('Chiton', '#e6dcc4', 600), 'skin')
    sk1 = chiton('L1_Skirt', '#cdbf9c', .97, .66); drape('L1_Skirt', sk1, lambda c: c.z > .955, body)
    items['L1_Skirt'] = (sk1, m_cloth('TunicSkirt', '#cdbf9c', 500, .08), 'skin')
    top = J['l-shoulder'].z + .04
    for nm, col in (('L1_Cloak', '#1e1a18'), ('L3_Cloak', '#7a1414')):
        ck = cloak(nm, top); drape(nm, ck, lambda c, t=top: c.z > t - .016, body, 70, .2)   # pinned across the upper back; the sides fall free
        items[nm] = (ck, m_cloth(nm + 'Wool', col, 300, .12, 1024), 'skin')
    bake_textures(items)
    rig = build_armature(skeleton_spec(J), J)
    rig.data.pose_position = 'REST'; _upd()
    activate(body); rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    print('weighted', sum(1 for v in body.data.vertices if v.groups), '/', len(body.data.vertices))
    for name, (ob, mt, bind) in items.items():
        if ob is body or bind.startswith('later:'): continue
        if bind == 'skin': bind_skin(ob, rig, body)
        else: bind_rigid(ob, rig, bind)
    rig.data.pose_position = 'POSE'; _upd()
    st, _, _ = poses(J); pose(rig, st())
    place_in_hands(rig, items)
    return rig, actions(rig, J)

def export(rig, path):
    bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
    for o in rig.children_recursive: o.select_set(True)
    rig.animation_data.action = bpy.data.actions['Idle']; SC.frame_set(1)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_animation_mode='ACTIONS',
                              export_def_bones=False, export_force_sampling=True, export_optimize_animation_size=True,
                              export_image_format='JPEG', export_jpeg_quality=85, export_yup=True)
    print('exported', path, os.path.getsize(path) // 1024, 'KB')

def render(rig, path, action='Idle', frame=1, level=2, cam=((2.0, -3.1, 1.4), (85, 0, 33)), res=(420, 560), samples=32, hide=()):
    for o in SC.objects:
        if o.type == 'MESH':
            tag = o.name.split('_')[0]
            o.hide_render = (tag[:1] == 'L' and tag[1:].isdigit() and str(level) not in tag[1:]) or any(h in o.name for h in hide)
    rig.animation_data.action = bpy.data.actions[action]; SC.frame_set(frame)
    if 'Cam' not in bpy.data.objects:
        bpy.ops.object.camera_add(); c = bpy.context.object; c.name = 'Cam'; c.data.lens = 55; SC.camera = c
        bpy.ops.object.light_add(type='SUN', rotation=(math.radians(52), 0, math.radians(-35))); l = bpy.context.object; l.data.energy = 3.4; l.data.angle = math.radians(2)
        bpy.ops.object.light_add(type='SUN', rotation=(math.radians(75), 0, math.radians(150))); bpy.context.object.data.energy = 1.0
        w = bpy.data.worlds.new('W'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (.36, .42, .5, 1); SC.world = w
        bpy.ops.mesh.primitive_plane_add(size=8); g = bpy.context.object; g.name = 'Ground'
        gm = bpy.data.materials.new('Ground'); gm.use_nodes = True; gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*srgb('#7a7458'), 1); g.data.materials.append(gm)
    c = bpy.data.objects['Cam']; c.location = cam[0]; c.rotation_euler = [math.radians(a) for a in cam[1]]
    SC.cycles.samples = samples; SC.render.resolution_x, SC.render.resolution_y = res; SC.render.filepath = path
    SC.view_settings.view_transform = 'AgX'
    bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    rig, acts = build()
    export(rig, os.path.join(OUT, 'hoplite.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'hoplite_real.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3): render(rig, os.path.join(OUT, f'real_L{lv}.png'), 'Idle', 1, lv)
    print('built', [a.name for a in acts])
