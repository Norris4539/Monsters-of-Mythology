"""Realistic Chariot line of Kemet (New Kingdom Egypt), built in Blender and exported as one glTF.

Run with Blender's Python (pip install bpy pillow), after fetch_makehuman.py:
    python tools/blender/chariot.py third_party/makehuman assets/models [--renders]

A war chariot c. 1300 BC (chariot_car.py), its team of two horses (horse.py, in a yoke
harness instead of the Greek sheepskin) and a crew of two built on the infantry pipeline
(hoplite.py): a driver with the reins and a shield, and a fighter. One armature holds
them all: the car's bone pivots on the axle and carries the crew, each wheel turns on its
own bone, each horse has its own set of horse.py's bones (hl_*, hr_*) and each man his
own of hoplite.py's (ar_, dr_, ds_, sp_ before the bone's name). Kit follows the sheets:
  L1 Chariot Archer          linen kilts, bare chests, shaven heads; a composite bow; the
                             car of bent wood, rawhide and wicker with a bow case and two
                             quivers; the team in leather harness under tall ostrich plumes
  L2 Veteran Chariot Archer  bronze scale corselets; red and blue striped saddle cloths and
                             breast bands with tassels; gilded fittings on the car
  L3 Elite Chariot Archer    scale corselets with broad collars; the car sheathed in gold with
                             reliefs; gilded harness; a large gilded bow
  L4 Chariot Spearman        padded linen corselets; cowhide shields; a spear of 2.5 m and a
                             bronze khopesh; red and blue trappings; a rack of spare spears
  L5 Royal Chariot Guard     scale corselets with broad collars; gilded shields; a long
                             bronze spear and a gilded khopesh; the gold car; the horses in
                             coats of bronze scales, gilded harness and face plates
The archers (L1-L3) and the spear crews (L4, L5) are the line's two branches, each with its
own pair of men as on the sheets: the archer on the left and the driver on the right, or
the driver on the left and the spearman on the right.
Node tags: the car's floor, wheels, axle, pole and yoke and the horses with their bridles,
plumes, yoke saddles and girths are untagged; L0124_ is the wooden siding and L35_ the gold
one, L123_ the archer crew with the bow case and quivers, L45_ the spear crew with the
spear rack, L24_ the red and blue trappings. Level 0 (the car and team alone) has
L0_Reins tied to the front rail instead of reins running to a driver's fists.
The arrow on the string is the node 'ShootArrow', hidden by the game from the release in
Shoot (frame 15) while its copy flies.
"""
import bpy, bmesh, math, os, sys, random
from types import SimpleNamespace
from mathutils import Vector, Matrix, Euler, Quaternion
from mathutils.bvhtree import BVHTree
V = Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hoplite as H
import peltast as P
import horse as HR
import hippeis as HP
import chariot_car as C
from hoplite import (link, obj_from_bm, bake_mods, mod, lathe, srgb, region_shell, Mat,
                     m_bronze, m_cloth, m_leather, m_wood)
from peltast import curve_mesh, ribbon, Surf, ring_on, relax_rim, bake_obj_xform

# Lean Egyptian men, a little shorter than the Greeks.
H.TARGETS = [('caucasian-male-young.target', .5), ('african-male-young.target', .38), ('asian-male-young.target', .12),
             ('universal-male-young-maxmuscle-averageweight.target', .5), ('universal-male-young-averagemuscle-minweight.target', .5)]
H.HEIGHT = 1.70
OUT = H.OUT
SC = H.SC
random.seed(23)

# ── Layout (m): the chariot faces -Y, its middle over the origin ────────────
Y_H = -.44                 # the horses' origin (horse.py's frame, under the middle of the back)
HX = .46                   # each horse out from the pole
Y_A = Y_H + 1.75           # the axle, under the back of the car
YS_Y = -.3                 # the yoke saddles: on the neck just in front of the withers (horse frame)
GIRTH_Y = YS_Y + .055      # the girth, just behind the elbows
FLOOR = C.Z_FLOOR
CREW = {   # each man: place on the floor (x, y), branch tag, kilt, tier kit
    'ar': dict(at=(.27, Y_A - .01), tag='L123_', kilt='KiltWhite', kit=[('Scales', 'L23_'), ('Collar', 'L3_')]),
    'dr': dict(at=(-.27, Y_A - .06), tag='L123_', kilt='KiltCream', kit=[('Scales', 'L23_'), ('Collar', 'L3_')]),
    'ds': dict(at=(.27, Y_A - .06), tag='L45_', kilt='KiltWhite', kit=[('Padded', 'L4_'), ('Scales', 'L5_'), ('Collar', 'L5_')]),
    'sp': dict(at=(-.27, Y_A - .01), tag='L45_', kilt='KiltCream', kit=[('Padded', 'L4_'), ('Scales', 'L5_'), ('Collar', 'L5_')]),
}
DRIVERS = {'dr': 'L123_', 'ds': 'L45_'}
SHOOT_RELEASE = 15          # the frame the arrow leaves the string (the game launches its copy here)


# ── Materials ───────────────────────────────────────────────────────────────
def m_skin_kemet(eye):
    """hoplite.py's skin, darkened to the sheets' warm brown."""
    m = H.m_skin(eye)
    ramp = next(n for n in m.N if n.type == 'VALTORGB')
    for el, c in zip(ramp.color_ramp.elements, ('#6a3d24', '#7e4b2e', '#93593a')): el.color = (*srgb(c), 1)
    m.bsdf.inputs['Subsurface Radius'].default_value = (.7, .3, .18)
    return m

def m_stubble(name='Stubble'):
    """A shaven scalp: skin with fine dark stubble."""
    m = Mat(name, res=512)
    dots = m.ramp(m.noise(1400, 2, .5).outputs['Fac'], [(.42, srgb('#21160f')), (.62, srgb('#5a3826'))])
    tone = m.ramp(m.noise(8, 3, .5).outputs['Fac'], [(.3, (.85, .85, .85)), (.7, (1, 1, 1))])
    m.set(m.mix(dots.outputs['Color'], tone.outputs['Color'], 1.0, 'MULTIPLY'), .6, m.noise(1400, 2).outputs['Fac'], .1, .0004)
    return m

def tile_image(path, kind, S=512):
    """Tileable height images drawn with PIL: 'scales' (rows of round-ended bronze scales,
    each row overlapping the one below, domed with a midrib) or 'cowhide' (white with
    brown patches, not tiled)."""
    from PIL import Image, ImageDraw, ImageFilter
    if kind == 'scales':
        im = Image.new('L', (S, S), 0); d = ImageDraw.Draw(im); cols, rows = 4, 5
        cw, rh = S / cols, S / rows
        for r in range(rows * 2 + 2, -2, -1):   # lower rows first, so each row lies over the one below
            for c in range(-1, cols + 1):
                x0 = (c + (.5 if r % 2 else 0)) * cw; y0 = r * rh / 2 - rh * .6
                for dx in (-S, 0, S):
                    for dy in (-S, 0, S):
                        x, y = x0 + dx, y0 + dy
                        if x < -cw or x > S + cw or y < -rh * 2 or y > S + rh: continue
                        for k in range(12, 0, -1):   # concentric fills make the dome
                            f = k / 12; w = cw * .48 * f
                            d.rounded_rectangle((x - w, y + rh * (1 - f) * .5, x + w, y + rh * 1.15 * (.55 + .45 * f)), radius=w, fill=int(40 + 190 * (1 - f) ** .7))
                        d.line((x, y + rh * .2, x, y + rh * 1.0), fill=245, width=3)
                        d.arc((x - cw * .48, y + rh * 1.15 - cw * .96, x + cw * .48, y + rh * 1.15), 20, 160, fill=15, width=4)
        im = im.filter(ImageFilter.GaussianBlur(1.1))
    else:
        rnd = random.Random(31); W_, H_ = S, S * 2
        im = Image.new('RGB', (W_, H_), (232, 226, 214)); d = ImageDraw.Draw(im)
        for k in range(9):   # brown patches, each a cluster of blobs
            cx, cy = rnd.uniform(0, W_), rnd.uniform(0, H_); col = (rnd.randint(92, 120), rnd.randint(50, 66), rnd.randint(28, 40))
            for j in range(26):
                r = rnd.uniform(25, 75) * (1.3 if k % 3 == 0 else 1)
                x, y = cx + rnd.gauss(0, 60), cy + rnd.gauss(0, 80); d.ellipse((x - r, y - r * 1.2, x + r, y + r * 1.2), fill=col)
        im = im.filter(ImageFilter.GaussianBlur(3))
        px_ = im.load()
        for i in range(60000):   # hair: fine flecks
            x, y = rnd.randrange(W_), rnd.randrange(H_); r, g, b = px_[x, y]; t = rnd.uniform(.85, 1.08)
            px_[x, y] = (min(255, int(r * t)), min(255, int(g * t)), min(255, int(b * t)))
    im.save(path)
    img = bpy.data.images.load(path)
    if kind == 'scales': img.colorspace_settings.name = 'Non-Color'
    img.pack(); return img

def m_scales(name, img, size, base=('#6b4a22', '#a87a3a', '#d9aa5c'), res=1024, rough=.32):
    """Bronze scales sewn in overlapping rows: the tile image box-projected in object space
    (size: m per tile), the domes bright, the gaps dark."""
    m = Mat(name, metal=1.0, res=res)
    mp = m.node('ShaderNodeMapping'); m.L.new(m.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (1 / size,) * 3
    t = m.node('ShaderNodeTexImage', projection='BOX', projection_blend=.3); t.image = img; m.L.new(mp.outputs['Vector'], t.inputs['Vector'])
    var = m.ramp(m.noise(18, 4, .6).outputs['Fac'], [(.3, (.8, .8, .8)), (.7, (1, 1, 1))])
    col = m.ramp(t.outputs['Color'], [(.12, srgb('#1e140a')), (.3, srgb(base[0])), (.6, srgb(base[1])), (.95, srgb(base[2]))])
    col = m.mix(col.outputs['Color'], var.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, rough, t.outputs['Color'], .7, .003)
    return m

def m_collar(name, centre, res=1024):
    """A broad collar (wesekh) of faience beads: bands of gold, turquoise, carnelian and lapis
    round the neck (object-space distance from its middle), beads strung across the bands,
    an outer row of drop beads."""
    m = Mat(name, res=res)
    dist = m.node('ShaderNodeVectorMath', operation='DISTANCE'); m.L.new(m.coord.outputs['Object'], dist.inputs[0]); dist.inputs[1].default_value = tuple(centre)
    bands = [(0, '#c9a03c'), (.08, '#2f9c94'), (.098, '#c9a03c'), (.106, '#a8321e'), (.122, '#c9a03c'), (.13, '#28427e'), (.146, '#2f9c94'),
             (.165, '#c9a03c'), (.172, '#a8321e'), (.19, '#2f9c94')]
    r = m.ramp(dist.outputs['Value'], [(p / .22, srgb(c)) for p, c in bands]); r.color_ramp.interpolation = 'CONSTANT'
    sc = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(dist.outputs['Value'], sc.inputs[0]); sc.inputs[1].default_value = 1 / .22
    m.L.new(sc.outputs[0], r.inputs['Fac'])
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    sx = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['X'], sx.inputs[0]); sx.inputs[1].default_value = centre.x
    sy = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['Y'], sy.inputs[0]); sy.inputs[1].default_value = centre.y
    sz = m.node('ShaderNodeMath', operation='SUBTRACT'); m.L.new(sep.outputs['Z'], sz.inputs[0]); sz.inputs[1].default_value = centre.z
    ang = m.node('ShaderNodeMath', operation='ARCTAN2'); m.L.new(sx.outputs[0], ang.inputs[0]); m.L.new(sz.outputs[0], ang.inputs[1])
    beads = m.node('ShaderNodeMath', operation='SINE'); mul = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(ang.outputs[0], mul.inputs[0]); mul.inputs[1].default_value = 140
    m.L.new(mul.outputs[0], beads.inputs[0])
    rows = m.node('ShaderNodeMath', operation='SINE'); mr = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(dist.outputs['Value'], mr.inputs[0]); mr.inputs[1].default_value = 900
    m.L.new(mr.outputs[0], rows.inputs[0])
    bb = m.node('ShaderNodeMath', operation='MULTIPLY'); m.L.new(beads.outputs[0], bb.inputs[0]); m.L.new(rows.outputs[0], bb.inputs[1])
    shade = m.ramp(bb.outputs[0], [(-.6, (.55, .55, .55)), (.4, (1, 1, 1))])
    col = m.mix(r.outputs['Color'], shade.outputs['Color'], 1.0, 'MULTIPLY')
    m.set(col, .35, bb.outputs[0], .35, .0015)
    return m

def m_quilted(name='QuiltedLinen', res=1024):
    """Padded linen: quilted in horizontal rolls with stitched seams between."""
    m = m_cloth(name, '#dccfae', 650, .05, res)
    cloth = m.bsdf.inputs['Base Color'].links[0].from_socket
    w = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=7.0, wave_profile='SIN'); m.L.new(m.coord.outputs['Object'], w.inputs['Vector'])
    seams = m.ramp(w.outputs['Fac'], [(.0, (0, 0, 0)), (.1, (1, 1, 1))])
    v = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', Scale=11.0); m.L.new(m.coord.outputs['Object'], v.inputs['Vector'])
    vs = m.ramp(v.outputs['Fac'], [(.0, (0, 0, 0)), (.06, (1, 1, 1))])
    both = m.mix(seams.outputs['Color'], vs.outputs['Color'], 1.0, 'MULTIPLY')
    m.L.new(m.mix(srgb('#8a7a5a'), cloth, both), m.bsdf.inputs['Base Color'])
    b = m.node('ShaderNodeBump', Strength=.8, Distance=.006); m.L.new(m.mix(w.outputs['Fac'], (0, 0, 0), m.ramp(vs.outputs['Color'], [(0, (1, 1, 1)), (1, (0, 0, 0))]).outputs['Color']), b.inputs['Height'])
    m.L.new(b.outputs['Normal'], m.bsdf.inputs['Normal'])
    return m

def m_team_coat(name='TeamCoat', res=1024):
    """The sheets' team: a light bay, darker over the neck and head, the legs dark from the
    knees and hocks with white socks, a dark grey muzzle and a white blaze (the 'blaze'
    colour attribute)."""
    m = Mat(name, res=res)
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['Object'], sep.inputs['Vector'])
    def mr(src, a, b):
        n = m.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP'); m.L.new(src, n.inputs['Value'])
        n.inputs['From Min'].default_value = a; n.inputs['From Max'].default_value = b; return n.outputs['Result']
    body = m.ramp(m.noise(6, 4, .55).outputs['Fac'], [(.3, srgb('#8e6440')), (.55, srgb('#a8794f')), (.8, srgb('#b88a5e'))])
    col = m.mix(body.outputs['Color'], srgb('#6c4529'), mr(sep.outputs['Y'], -.3, -.62))           # darker neck and head
    col = m.mix(col, srgb('#7a5236'), mr(sep.outputs['Z'], 1.0, .8))                                # shaded belly
    col = m.mix(col, srgb('#4a3324'), mr(sep.outputs['Z'], .62, .48))                               # forearms and gaskins darken
    col = m.mix(col, srgb('#231c17'), mr(sep.outputs['Z'], .46, .36))                               # dark cannons
    col = m.mix(col, srgb('#c9c2b6'), mr(sep.outputs['Z'], .21, .15))                               # white socks
    col = m.mix(col, srgb('#5e534b'), mr(sep.outputs['Y'], -.93, -.99))                             # grey muzzle
    attr = m.node('ShaderNodeAttribute', attribute_name='blaze')
    col = m.mix(col, srgb('#ddd6cb'), attr.outputs['Fac'])
    hair = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z', Scale=260.0, Distortion=3.0, Detail=2.0)
    m.L.new(m.coord.outputs['Object'], hair.inputs['Vector'])
    rough = m.ramp(m.noise(40, 3).outputs['Fac'], [(.3, (.72, .72, .72)), (.7, (.86, .86, .86))])
    m.set(col, rough.outputs['Color'], hair.outputs['Fac'], .12, .001)
    return m

def m_stripes(name, stops, axis='Y', border=None, res=512):
    """Woven wool in bands across the UV's v (stops: (v, colour), constant), a patterned border
    at both v ends and the u ends when given."""
    m = m_cloth(name, '#ffffff', 380, .06, res)
    weave = m.bsdf.inputs['Base Color'].links[0].from_socket
    sep = m.node('ShaderNodeSeparateXYZ'); m.L.new(m.coord.outputs['UV'], sep.inputs['Vector'])
    r = m.ramp(sep.outputs[axis], [(p, srgb(c)) for p, c in stops]); r.color_ramp.interpolation = 'CONSTANT'
    col = r.outputs['Color']
    if border:   # a cream border with a red zigzag at the u ends and the hems
        uu = sep.outputs['X' if axis == 'Y' else 'Y']; vv = sep.outputs[axis]
        def edge(src, a):
            lo = m.node('ShaderNodeMath', operation='LESS_THAN'); m.L.new(src, lo.inputs[0]); lo.inputs[1].default_value = a
            hi = m.node('ShaderNodeMath', operation='GREATER_THAN'); m.L.new(src, hi.inputs[0]); hi.inputs[1].default_value = 1 - a
            mx = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(lo.outputs[0], mx.inputs[0]); m.L.new(hi.outputs[0], mx.inputs[1]); return mx.outputs[0]
        mx = m.node('ShaderNodeMath', operation='MAXIMUM'); m.L.new(edge(uu, border[0]), mx.inputs[0]); m.L.new(edge(vv, border[1]), mx.inputs[1])
        zig = m.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='DIAGONAL', Scale=60.0, wave_profile='TRI'); m.L.new(m.coord.outputs['UV'], zig.inputs['Vector'])
        bc = m.ramp(zig.outputs['Fac'], [(.0, srgb('#e6d6a8')), (.7, srgb('#e6d6a8')), (.75, srgb('#a8281e'))])
        col = m.mix(col, bc.outputs['Color'], mx.outputs[0])
    m.L.new(m.mix(col, weave, 1.0, 'MULTIPLY'), m.bsdf.inputs['Base Color'])
    return m

def plume_palette(path, cols, S=64, L=512):
    """Ostrich feathers drawn with PIL, one per column: a pale shaft, a soft vane of barbs
    lighter towards the tip, and a ragged fringe of single barbs round it (the alpha)."""
    from PIL import Image, ImageDraw
    rnd = random.Random(12); im = Image.new('RGBA', (S * len(cols), L), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, c in enumerate(cols):
        r, g, b = [int(255 * x ** (1 / 2.2)) for x in srgb(c)]; x0 = i * S + S / 2
        for y in range(L - 1, 2, -1):
            t = 1 - y / L                              # 0 at the base, 1 at the tip
            w = (S / 2 - 2) * math.sin(math.pi * min(1, .08 + t * 1.05)) ** .55
            k = .62 + .5 * t + rnd.uniform(-.14, .14)
            col = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255)
            d.line([(x0 - w * .7, y), (x0 + w * .7, y)], fill=col, width=1)
            for s_ in (-1, 1):
                if rnd.random() < .7:
                    ln = w * rnd.uniform(.75, 1.0); d.line([(x0 + s_ * w * .6, y), (x0 + s_ * ln, y + rnd.randint(1, 5))], fill=col, width=1)
        d.line([(x0, L), (x0, 10)], fill=(232, 224, 205, 255), width=2)
    im.save(path)
    img = bpy.data.images.load(path); img.pack(); return img

def m_feathers(img):
    """Image colours with the barbs' gaps cut out (alpha mask), not baked."""
    m = Mat('Plume', res=0)
    t = m.node('ShaderNodeTexImage'); t.image = img; m.L.new(m.coord.outputs['UV'], t.inputs['Vector'])
    m.set(t.outputs['Color'], .8)
    rnd_ = m.node('ShaderNodeMath', operation='ROUND'); m.L.new(t.outputs['Alpha'], rnd_.inputs[0]); m.L.new(rnd_.outputs[0], m.bsdf.inputs['Alpha'])
    m.m.blend_method = 'CLIP' if hasattr(m.m, 'blend_method') else None
    return m


# ── The crew: kit grown on the template body, at the origin ─────────────────
def crew_kit(body, J, add):
    """Shaven head, eyes, kilts and belts, and each tier's armour, on the template body;
    copied to each man later."""
    head, neck, eye, jaw = J['head'], J['neck'], J['l-eye'], J['jaw']; sh_z = J['l-shoulder'].z
    hair = region_shell('Hair', body, lambda c: (c.z > eye.z + .04 and c.y > eye.y + .05) or (c.z > eye.z + .075) or
                        (c.z > jaw.z + .005 and c.y > head.y + .035 and c.z > neck.z + .05), .0016, 2, .5, guard=.0012)
    P.relax_rim(hair, 4); add(hair, m_stubble(), 'head')
    for side in ('l', 'r'):
        e = J[f'{side}-eye']
        bpy.ops.mesh.primitive_uv_sphere_add(radius=.0118, segments=16, ring_count=10, location=e + V((0, .004, 0)))
        ob = bpy.context.object; ob.name = 'Eye' + side.upper(); bake_obj_xform(ob)
        em = Mat('Eye', res=128)
        grad = em.node('ShaderNodeTexGradient', gradient_type='SPHERICAL')
        mp = em.node('ShaderNodeMapping'); em.L.new(em.coord.outputs['Object'], mp.inputs['Vector']); mp.inputs['Scale'].default_value = (95, 95, 95)
        mp.inputs['Location'].default_value = (-e.x * 95, (.0118 - e.y - .004) * 95, -e.z * 95)
        em.L.new(mp.outputs['Vector'], grad.inputs['Vector'])
        col = em.ramp(grad.outputs['Fac'], [(.0, srgb('#efe8de')), (.55, srgb('#efe8de')), (.6, srgb('#2a170c')), (.85, srgb('#1a0e06')), (.88, (0.01, .01, .01))])
        em.set(col.outputs['Color'], .15)
        add(ob, em, 'head')
    # the shendyt: a linen kilt wrapped round the hips to above the knee, draped
    z0, z1 = .985, .565
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    bm = bmesh.new(); nr, nz = 64, 20; rows = []
    for j in range(nz + 1):
        z = z0 - (z0 - z1) * j / nz; row = []
        for i in range(nr):
            a = 2 * math.pi * i / nr; d = V((math.cos(a), math.sin(a), 0))
            h = bvh.ray_cast(V((0, .01, z0)) + d * .5, -d, .6); r0 = (h[0] - V((0, .01, z0))).length if h[0] else .16
            r = r0 + .008 + .075 * (j / nz) ** 1.2
            row.append(bm.verts.new(V((0, .01, z)) + d * r))
        rows.append(row)
    for j in range(nz):
        for i in range(nr): bm.faces.new((rows[j][i], rows[j][(i + 1) % nr], rows[j + 1][(i + 1) % nr], rows[j + 1][i]))
    kilt = obj_from_bm('KiltWhite', bm)
    H.drape('KiltWhite', kilt, lambda c: c.z > z0 - .03, body, 50, .25, 0)
    # the wrap's free edge: the front fold of the kilt, a little proud of it, slanting to the hem
    sf = Surf([body, kilt]); pts = []
    for k in range(13):
        z = z0 - .01 - (z0 - z1 - .02) * k / 12; x = .03 + .07 * k / 12
        h = sf.hit(V((x, 0, z)), V((0, -1, 0)), .5)
        if h: pts.append((h[0] + h[1] * .004, h[1]))
    fold = ribbon('KiltFold', pts, .022, .0025)
    mod(kilt, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(kilt)
    cream = kilt.copy(); cream.data = kilt.data.copy(); cream.name = 'KiltCream'; link(cream)
    fold2 = fold.copy(); fold2.data = fold.data.copy(); fold2.name = 'KiltFoldCream'; link(fold2); fold.name = 'KiltFoldWhite'
    white_l, cream_l = m_cloth('LinenWhite', '#e9e4d8', 700, .04), m_cloth('LinenCream', '#d2c4a4', 700, .05)
    add(kilt, white_l, 'skin'); add(cream, cream_l, 'skin'); add(fold, white_l, 'skin'); add(fold2, cream_l, 'skin')
    # the belt: a linen sash wound round the top of the kilt, knotted at the front
    sfk = Surf([body, kilt]); pts = ring_on(sfk, z0 - .018, .005, 64); pts.append(pts[0])
    for nm, mt in (('BeltWhite', m_cloth('SashWhite', '#ddd6c6', 500, .05, 256)), ('BeltCream', m_cloth('SashCream', '#c4b490', 500, .05, 256))):
        add(ribbon(nm, pts, .04, .004), mt, 'skin')
    # armour, sleeveless to the waist: bronze scales, or padded linen
    def vest(c, top=neck.z - .025):
        if c.z < .965 or c.z > top: return False
        if P.on_arm(J, -.05, 1.1, .085)(c): return False
        return abs(c.x) < .2
    sc = region_shell('Scales', body, vest, .013, 6, .5, guard=.011); relax_rim(sc, 6)
    mod(sc, 'SOLIDIFY', thickness=.005, offset=1); bake_mods(sc)
    add(sc, m_scales('CorseletScales', tile_image(os.path.join(OUT, 'scales.png'), 'scales'), .13), 'skin')
    pd = region_shell('Padded', body, vest, .017, 8, .5, guard=.015); relax_rim(pd, 6)
    mod(pd, 'SOLIDIFY', thickness=.008, offset=1); bake_mods(pd); add(pd, m_quilted(), 'skin')
    # the broad collar over the corselet: neck to upper chest, shoulders and upper back
    cn = V((0, neck.y + .005, neck.z - .02))
    def collar(c):
        dh = V((c.x - cn.x, c.y - cn.y, 0)).length
        return cn.z - .19 < c.z < cn.z + .012 and (c - cn).length < .2 and not (dh < .068 and c.z > cn.z - .03) and abs(c.x) < .2
    co = region_shell('Collar', body, collar, .026, 6, .5, guard=.023); relax_rim(co, 8)
    mod(co, 'SOLIDIFY', thickness=.006, offset=1); bake_mods(co); add(co, m_collar('BroadCollar', cn), 'skin')
    return hair


# ── Weapons, built about their grips ────────────────────────────────────────
BRACE = .15

def bow_mesh(name, L=1.2):
    """A recurved composite bow about its grip (origin), the limbs along Z and the string's side
    +Y: they sweep back to the string at the string bridges, then the tips curve forward.
    Returns the bow and its two string bridges."""
    half = L / 2; pts, rads = [], []
    def at(u, s):   # u: 0 at the grip, 1 at a tip; s: +1 upper limb, -1 lower
        y = BRACE * (u / .88) ** 1.7 if u <= .88 else BRACE - .28 * (u - .88)
        return V((0, y, s * (.05 + (half - .05) * u)))
    for k in range(41):
        u = abs(k - 20) / 20; s = 1 if k > 20 else -1
        pts.append(at(u, s if k != 20 else 1)); rads.append(1 - .55 * u)
    ob = curve_mesh(name, [[tuple(p) for p in pts]], .013, radii=lambda t: 1 - .55 * abs(2 * t - 1))
    for v in ob.data.vertices: v.co.x *= 1.35
    return ob, (at(.88, 1), at(.88, -1))

def arrow_parts(prefix, mats):
    """An arrow along +Z from its nock (origin): reed shaft, bronze head, three fletchings."""
    reed, bronze, feather = mats; L = .82
    shaft = lathe(prefix + 'Shaft', [(0, -.005), (.0045, 0), (.0048, .4), (.0042, L - .02), (0, L)], 8)
    head = lathe(prefix + 'Head', [(.004, L - .025), (.011, L + .01), (.008, L + .035), (0, L + .055)], 8); head.scale = (1, .35, 1)
    bm = bmesh.new()
    for k in range(3):
        a = 2 * math.pi * k / 3; r = V((math.cos(a), math.sin(a), 0))
        bm.faces.new([bm.verts.new(p) for p in (V((0, 0, .03)), V((0, 0, .15)), r * .017 + V((0, 0, .14)), r * .015 + V((0, 0, .045)))])
    fl = obj_from_bm(prefix + 'Fletch', bm); mod(fl, 'SOLIDIFY', thickness=.0012); bake_mods(fl)
    return [(shaft, reed), (head, bronze), (fl, feather)]

def shield_parts(prefix, face_mat, rim_mat, back_mat, boss=None):
    """An Egyptian shield about its grip (origin): flat at the foot, round at the top, a
    little domed, facing +Z with its top +Y; a vertical grip bar behind it."""
    w, h0, h1 = .21, -.4, .34
    outline = [V((w, h0, 0)), V((w, .14, 0))] + [V((w * math.cos(a), .14 + (h1 - .14) * math.sin(a), 0)) for a in [math.pi * k / 20 for k in range(1, 20)]] + \
              [V((-w, .14, 0)), V((-w, h0, 0))] + [V((w * (-1 + 2 * k / 10), h0, 0)) for k in range(1, 10)]
    bm = bmesh.new(); c = bm.verts.new((0, (h0 + h1) / 2, 0)); ring = [bm.verts.new(p) for p in outline]
    for i in range(len(ring)): bm.faces.new((c, ring[i], ring[(i + 1) % len(ring)]))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    for v in bm.verts:
        u = (v.co.x / w) ** 2 + ((v.co.y - (h0 + h1) / 2) / ((h1 - h0) / 2)) ** 2
        v.co.z = .05 + .025 * max(0, 1 - u)
    uvl = bm.loops.layers.uv.new('UV')
    for f in bm.faces:
        for lp in f.loops: lp[uvl].uv = (lp.vert.co.x / (2 * w) + .5, (lp.vert.co.y - h0) / (h1 - h0))
    face = obj_from_bm(prefix + 'Face', bm)
    if face.data.polygons[0].normal.z < 0: face.data.flip_normals()
    back = face.copy(); back.data = face.data.copy(); back.name = prefix + 'Back'; link(back)
    for v in back.data.vertices: v.co.z -= .008
    back.data.flip_normals()
    rimp = [p + V((0, 0, .05)) for p in outline]
    rim = curve_mesh(prefix + 'Rim', [[tuple(p) for p in rimp]], .011, cyclic=True)
    grip = curve_mesh(prefix + 'Grip', [[(0, -.11, .035), (0, -.08, .012), (0, -.04, .0), (0, .04, .0), (0, .08, .012), (0, .11, .035)]], .011)
    out = [(face, face_mat), (back, back_mat), (rim, rim_mat), (grip, m_leather('ShieldGrip', '#4a2e18', 256))]
    if boss:
        b = lathe(prefix + 'Boss', [(0, .115), (.03, .11), (.055, .093), (.07, .075), (.075, .07)], 32); out.append((b, boss))
    return out

def spear_parts(prefix, L0, L1, head_len, mats, gilt=None):
    """A spear about its grip, point to +Z: shaft, leaf-shaped bronze head with a socket,
    a bronze butt."""
    wood, bronze = mats
    out = [(lathe(prefix + 'Shaft', [(0, -L0), (.0115, -L0 + .01), (.0135, 0), (.0115, L1), (0, L1 + .004)], 12), wood)]
    hd = lathe(prefix + 'Head', [(.013, L1 - .06), (.016, L1), (.03, L1 + head_len * .3), (.024, L1 + head_len * .65), (0, L1 + head_len)], 10)
    hd.scale = (1, .3, 1); out.append((hd, bronze))
    out.append((lathe(prefix + 'Socket', [(.0135, L1 - .08), (.016, L1 - .06), (.016, L1 + .01), (.013, L1 + .03)], 12), bronze))
    out.append((lathe(prefix + 'Butt', [(0, -L0 - .07), (.012, -L0 - .01), (.0125, -L0 + .03)], 10), gilt or bronze))
    return out

def khopesh(prefix, blade_mat, grip_mat):
    """A khopesh: a straight grip and neck, then the hooked blade, its edge on the outer curve
    (built flat in the XY plane, the grip along +Y from the origin)."""
    out_e, in_e = [], []
    for k in range(25):   # the blade: an arc from the neck over and down to the hooked tip
        a = math.radians(180 - 215 * k / 24); out_e.append((.07 + .085 * math.cos(a), .37 + .085 * math.sin(a)))
        a2 = math.radians(180 - 200 * k / 24); in_e.append((.07 + .045 * math.cos(a2), .37 + .042 * math.sin(a2)))
    poly = [(-.011, .13), (-.013, .37)] + out_e[1:] + in_e[::-1][:-1] + [(.011, .36), (.011, .13)]
    bm = bmesh.new(); vs = [bm.verts.new((x, y, 0)) for x, y in poly]
    f = bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=[f])
    blade = obj_from_bm(prefix + 'Blade', bm, False); mod(blade, 'SOLIDIFY', thickness=.006, offset=0); mod(blade, 'BEVEL', width=.0015, segments=1); bake_mods(blade)
    grip = lathe(prefix + 'Grip', [(0, -.005), (.014, 0), (.016, .06), (.014, .125), (.018, .135), (0, .14)], 12); grip.scale = (1, .8, 1)
    grip.rotation_euler = (-math.pi / 2, 0, 0); bake_obj_xform(grip)
    for v in grip.data.vertices: v.co.y, v.co.z = -v.co.z, v.co.y
    return [(blade, blade_mat), (grip, grip_mat)]


# ── The team: chariot harness on horse.py's horse ───────────────────────────
def blaze_attr(ob, bvh):
    """The white blaze down the face, as a colour attribute: on the front of the head between
    the brows and the nostrils, narrow between the eyes, widening over the nose."""
    me = ob.data; attr = me.color_attributes.new('blaze', 'FLOAT_COLOR', 'POINT')
    p0, p1 = HR.HEAD_AXIS; u = (p1 - p0).normalized(); L = (p1 - p0).length
    nrm = V((1, 0, 0)).cross(u).normalized()
    if nrm.z < 0: nrm = -nrm
    for v, a in zip(me.vertices, attr.data):
        s = (v.co - p0).dot(u) / L; c = p0 + u * s * L; up = (v.co - c).dot(nrm)
        w = .03 - .016 * C.smooth(.15, .4, s) + .016 * C.smooth(.45, .85, s)
        b = 0.0
        if .12 < s < .92 and up > 0 and v.co.y < -.6:
            b = C.smooth(w + .006, w - .004, abs(v.co.x)) * C.smooth(.12, .17, s) * C.smooth(.92, .86, s)
        a.color = (b, b, b, 1)

def neck_side(bvh, y, z, sx, off=.014):
    h = bvh.ray_cast(V((sx * 1.0, y, z)), V((-sx, 0, 0)), 2)
    return (h[0] + h[1] * off) if h[0] else None

def horse_kit(hbody, add):
    """The chariot harness and trappings on the template horse (horse.py's frame): yoke
    saddle, girth, breast straps, plume, rosettes, the L24_ cloths and the L5_ armour.
    Returns the yoke saddle's top (where the yoke rests) and the terrets for the reins."""
    dg = bpy.context.evaluated_depsgraph_get(); bvh = BVHTree.FromObject(hbody, dg)
    leather = m_leather('Harness', '#5a3820'); dark = m_leather('YokeSaddle', '#3a2416', 256)
    gold = C.m_gold('HarnessGold', 512); bronze = m_bronze('HarnessBronze', .2, 256)
    top = bvh.ray_cast(V((0, YS_Y, 3)), V((0, 0, -1)), 4)[0]
    # the yoke saddle: a stem lashed to the yoke, legs astride the neck down to the shoulders
    legs, ends = [], []
    for sx in (1, -1):
        pts = [top + V((0, 0, .02))]
        for k in range(1, 9):
            z = top.z - .02 - .27 * k / 8; p = neck_side(bvh, YS_Y - .07 * k / 8, z, sx, .016)
            if p: pts.append(p)
        legs.append(pts); ends.append(pts[-1])
    stem = [top + V((0, 0, .015)), top + V((0, 0, .095))]
    ys = curve_mesh('YokeSaddle', [[tuple(p) for p in L] for L in legs] + [[tuple(p) for p in stem]], .017, radii=None)
    add(ys, dark, 'h_chest')
    ysg = curve_mesh('L35_YokeSaddleGilt', [[tuple(p) for p in L] for L in legs] + [[tuple(p) for p in stem]], .0185)
    add(ysg, gold, 'h_chest')
    for i, e in enumerate(ends):
        k = lathe(f'YokeSaddleKnob{i}', [(0, -.03), (.022, -.02), (.024, 0), (.012, .02), (0, .022)], 14); k.location = e; bake_obj_xform(k)
        add(k, gold, 'h_chest')
    fin = lathe('YokeSaddleFinial', [(0, 0), (.02, .004), (.016, .03), (.026, .05), (.012, .075), (0, .08)], 16); fin.location = top + V((0, 0, .095)); bake_obj_xform(fin)
    add(fin, gold, 'h_chest')
    terrets = []
    for sx in (1, -1):   # rings for the reins on the legs, near the top
        p = legs[0 if sx > 0 else 1][2]
        r = lathe(f'Terret{"LR"[sx < 0]}', [(.016, -.004), (.021, 0), (.016, .004)], 16); r.rotation_euler = (math.pi / 2, 0, 0); r.location = p + V((sx * .012, 0, .02)); bake_obj_xform(r)
        add(r, bronze, 'h_chest'); terrets.append(p + V((sx * .012, 0, .02)))
    # girth round the barrel behind the elbows; breast strap round the chest from the saddle's legs
    sf = Surf([hbody])
    def girth_pts(surf, off):
        pts = []
        for i in range(49):
            a = 2 * math.pi * i / 48; d = V((math.cos(a), 0, math.sin(a))); h = surf.hit(V((0, GIRTH_Y, 1.0)), d, .8)
            if h: pts.append((h[0] + h[1] * off, h[1]))
        return pts
    def breast_pts(surf, off):
        pts = []
        for i in range(33):
            a = math.radians(-80 + 160 * i / 32); u = abs(a) / math.radians(80)
            z = 1.04 + (ends[0].z - .02 - 1.04) * u ** 2
            h = surf.hit(V((0, YS_Y + .04 - .06 * u, z)), V((math.sin(a), -math.cos(a), 0)), .9)
            if h: pts.append((h[0] + h[1] * off, h[1]))
        return pts
    add(ribbon('L01234_Girth', girth_pts(sf, .006), .045, .004), leather, 'horse-trunk')
    add(ribbon('L01_BreastStrap', breast_pts(sf, .007), .05, .005), leather, 'horse-trunk')
    add(ribbon('L3_BreastStrap', breast_pts(sf, .007), .055, .005), gold, 'horse-trunk')
    band = m_stripes('BreastBand', [(0, '#b0281e'), (.33, '#26489a'), (.66, '#b0281e')], 'Y')
    br = ribbon('L24_BreastStrap', breast_pts(sf, .008), .075, .006); P_uv_strip(br, 33)
    add(br, band, 'horse-trunk')
    # red and blue striped saddle cloth with a border and tassels (L24_)
    bm = bmesh.new(); nx, ny = 30, 18; g = []
    def back(y): h = bvh.ray_cast(V((0, y, 3)), V((0, 0, -1)), 4); return h[0].z if h[0] else 1.3
    y0c, y1c = GIRTH_Y + .05, GIRTH_Y + .66
    for j in range(ny + 1):
        y = y0c + (y1c - y0c) * j / ny; zb = back(y) + .02
        g.append([bm.verts.new(((i / nx - .5) * .86, y, zb - max(0, abs(i / nx - .5) - .06) * .3)) for i in range(nx + 1)])
    uvl = bm.loops.layers.uv.new('UV')
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i]))
            for lp, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))): lp[uvl].uv = (b / ny, a / nx)
    cloth = obj_from_bm('L24_SaddleCloth', bm)
    H.drape('L24_SaddleCloth', cloth, lambda c: abs(c.x) < .05, hbody, 80, .35, 0)
    corners = []
    bmc = bmesh.new(); bmc.from_mesh(cloth.data); bmc.verts.ensure_lookup_table()
    for j in (0, ny // 2, ny):
        for i in (0, nx):
            corners.append(bmc.verts[j * (nx + 1) + i].co.copy())
    bmc.free()
    mod(cloth, 'SOLIDIFY', thickness=.006, offset=1); bake_mods(cloth)
    stripes = [(0, '#a8261c')] + [(.08 + .1 * k, ('#2a4c9c', '#a8261c')[k % 2]) for k in range(9)]
    add(cloth, m_stripes('SaddleCloth', stripes, 'Y', border=(.05, .07)), 'horse-trunk')
    bm = bmesh.new()
    for c in corners:   # tassels: a cord, a gilt cap and a red tuft
        out = V((c.x, 0, 0)).normalized() * .01
        for k, (r0, r1, z0, z1) in enumerate(((.004, .004, 0, -.04), (.009, .013, -.04, -.06), (.013, .02, -.06, -.13))):
            M = Matrix.Translation(c + out + V((0, 0, (z0 + z1) / 2)))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=r1, radius2=r0, depth=abs(z1 - z0), matrix=M)
    tas = obj_from_bm('L24_Tassels', bm); add(tas, m_cloth('Tassel', '#a8261c', 300, .1, 256), 'horse-trunk')
    # bronze scale armour over the back and neck (L5_), with the harness laid over it
    big = tile_image(os.path.join(OUT, 'scales_big.png'), 'scales')
    hscale = m_scales('HorseScales', big, .24, ('#5e3a1c', '#9a6a38', '#d6a466'))
    coat = region_shell('L5_ArmourCoat', hbody, lambda c: c.z > .86 + .06 * C.smooth(.3, .5, c.y) and -.4 < c.y < .5, .03, 6, .5, guard=.026)
    relax_rim(coat, 10); mod(coat, 'DECIMATE', ratio=.5); mod(coat, 'SOLIDIFY', thickness=.008, offset=1); bake_mods(coat); add(coat, hscale, 'horse-trunk')
    ycut = lambda z: -.739 + (1.656 - z) * .19
    crin = region_shell('L5_ArmourNeck', hbody, lambda c: c.y < -.26 and c.y > ycut(c.z) + .035 and c.z > .97, .026, 6, .5, guard=.022)
    relax_rim(crin, 10); mod(crin, 'DECIMATE', ratio=.5); mod(crin, 'SOLIDIFY', thickness=.008, offset=1); bake_mods(crin); add(crin, hscale, 'horse-trunk')
    sa = Surf([hbody, coat, crin])
    add(ribbon('L5_Girth', girth_pts(sa, .006), .045, .004), leather, 'horse-trunk')
    add(ribbon('L5_BreastStrap', breast_pts(sa, .007), .055, .005), gold, 'horse-trunk')
    # gold face plate (L5_)
    p0, p1 = HR.HEAD_AXIS; u = (p1 - p0).normalized(); L = (p1 - p0).length
    nrm = V((1, 0, 0)).cross(u).normalized(); nrm = nrm if nrm.z > 0 else -nrm
    def face_front(c):
        s = (c - p0).dot(u) / L; q = p0 + u * s * L
        return .1 < s < .8 and (c - q).dot(nrm) > .02 and abs(c.x) < .085 - .03 * s
    ch = region_shell('L5_Chamfron', hbody, face_front, .01, 3, .5, guard=.008); relax_rim(ch, 6)
    mod(ch, 'SOLIDIFY', thickness=.003, offset=1); bake_mods(ch); add(ch, gold, 'h_head')
    # rosettes on the bridle's cheeks, the plume's holder at the poll and the plume
    for sx in (1, -1):
        p = HR.head_loop(bvh, .3, 0 if sx > 0 else math.pi, 0 if sx > 0 else math.pi, 1, .012)
        if not p: continue
        for tag, mt, r in (('L0124_', bronze, .024), ('L35_', gold, .027)):
            ro = lathe(f'{tag}Rosette{"LR"[sx < 0]}', [(0, .006), (r * .5, .005), (r, 0)], 20)
            ro.rotation_euler = (0, sx * math.pi / 2, 0); ro.location = p[0]; bake_obj_xform(ro); add(ro, mt, 'h_head')
    poll = bvh.ray_cast(V((0, HR.px(242, 0).y, 3)), V((0, 0, -1)), 4)[0]
    tilt = Matrix.Rotation(-.22, 4, 'X')
    holder = lathe('PlumeHolder', [(0, -.01), (.014, -.01), (.016, .02), (.012, .055), (.02, .07), (.016, .085), (0, .085)], 14)
    holder.matrix_world = Matrix.Translation(poll + V((0, .005, -.01))) @ tilt; bpy.context.view_layer.update(); bake_obj_xform(holder)
    add(holder, gold, 'h_head')
    base = poll + V((0, .005, -.01)) + (tilt.to_3x3() @ V((0, 0, .08)))
    cols = ['#c42a2a', '#e08a28', '#e8c84a', '#4a8a3a', '#2a9a9a', '#2a4aa8', '#7a3a8a', '#d0506a']
    add(plume(base, cols), m_feathers(plume_palette(os.path.join(OUT, 'plume.png'), cols)), 'h_head')
    return top + V((0, 0, .095)), terrets

def P_uv_strip(ob, n):
    """UVs for a ribbon made by peltast.ribbon: u along its length, v across."""
    me = ob.data; uvl = me.uv_layers.new(name='UV')
    for pl in me.polygons:
        for li in pl.loop_indices:
            vi = me.loops[li].vertex_index; k = vi % (2 * (n)); uvl.data[li].uv = ((k // 2) / max(1, n - 1), (k % 2))

def plume(base, cols, n=24, seed=4):
    """Tall ostrich plumes fanned from the holder: each feather a curved strip, wide in its
    middle and drooping at the tip, turned every way about its shaft so the plume reads full
    from any side; one palette column each."""
    rnd = random.Random(seed); bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UV'); K = len(cols)
    for i in range(n):
        side = (i / (n - 1) - .5) * 2 + rnd.uniform(-.1, .1)   # across the fan
        fwd = rnd.uniform(-.6, .5)
        d = V((side * .45, fwd * .75 + .12, 1)).normalized(); bend = V((side * .45, .6 + fwd * .3, 0))
        L = .5 * rnd.uniform(.82, 1.06) * (1 - .15 * abs(side)); wmax = .085
        col = (i * 3) % K; u0, u1 = col / K, (col + 1) / K
        spin = rnd.uniform(0, math.pi)
        prev = None; p = base + V((rnd.uniform(-.008, .008), rnd.uniform(-.008, .008), 0)); dd = d.copy(); seg = 12
        for k in range(seg + 1):
            t = k / seg
            if k: dd = (dd + bend * (L / seg) * 2.4 * t).normalized(); p = p + dd * L / seg
            sv = Matrix.Rotation(spin, 3, dd) @ dd.orthogonal().normalized()
            w = wmax * .5 * max(.1, math.sin(math.pi * min(1, .06 + t * 1.05)) ** .55)
            a, b = bm.verts.new(p - sv * w), bm.verts.new(p + sv * w)
            if prev:
                f = bm.faces.new((prev[0], prev[1], b, a))
                for lp, uv in zip(f.loops, ((u0, prev[2]), (u1, prev[2]), (u1, t), (u0, t))): lp[uvl].uv = uv
            prev = (a, b, t)
    return obj_from_bm('Plume', bm)


# ── Shared armature, and the bones of one figure in it ──────────────────────
class Part:
    """One horse's or man's bones inside the shared armature, addressed by the names the
    shared modules use (horse.py's h_*, hoplite.py's hips, chest ...), so their posing
    functions work on it unchanged."""
    class Bones:
        def __init__(self, coll, f, names): self.c, self.f, self.names = coll, f, names
        def __getitem__(self, n): return self.c[self.f(n)]
        def __iter__(self): return iter([self.c[self.f(n)] for n in self.names])
        def get(self, n, d=None): return self.c.get(self.f(n), d)
    def __init__(self, rig, f, names):
        self.rig, self.f = rig, f
        self.pose = SimpleNamespace(bones=Part.Bones(rig.pose.bones, f, names))
        self.data = SimpleNamespace(bones=Part.Bones(rig.data.bones, f, names))

def horse_name(pre): return lambda n: pre + n[1:] if n.startswith('h_') else n
def man_name(pre): return lambda n: f'{pre}_{n}'

def bone_list(J):
    B = [('root', (0, 0, 0), (0, -.4, 0), None, False),
         ('car', (0, Y_A, C.R_W), (0, Y_A - .4, C.R_W), 'root', True)]
    for side, sx in (('L', 1), ('R', -1)):
        B.append((f'wheel.{side}', (sx * C.TRACK, Y_A, C.R_W), (sx * C.TRACK + .25, Y_A, C.R_W), 'car', False))
    for pre, sx in (('hl', 1), ('hr', -1)):
        f = horse_name(pre); off = V((sx * HX, Y_H, 0))
        for n, h, t, p, d in HR.bones():
            B.append((f(n), V(h) + off, V(t) + off, f(p) if p else 'root', d))
    for pre, cw in CREW.items():
        f = man_name(pre); off = V((cw['at'][0], cw['at'][1], FLOOR))
        for n, h, t, p, d in H.skeleton_spec(J):
            B.append((f(n), V(h) + off, V(t) + off, f(p) if p else 'car', d))
    return B

def add_bone(rig, name, head, tail, parent, deform=True):
    H.activate(rig); bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones.new(name); eb.head = head; eb.tail = tail; eb.roll = 0; eb.use_deform = deform
    eb.parent = rig.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT'); rig.pose.bones[name].rotation_mode = 'QUATERNION'

def instance(src, name, rig, off, rename, bind):
    """A copy of a template object for one horse or man: moved by off, its vertex groups
    renamed to that figure's bones, bound to the shared armature (bind: 'skin' or a bone)."""
    ob = src.copy(); ob.data = src.data.copy(); ob.name = name; link(ob)
    mw = src.matrix_world.copy(); ob.parent = None; ob.matrix_world = Matrix.Identity(4)
    ob.data.transform(Matrix.Translation(off) @ mw)
    for g in ob.vertex_groups: g.name = rename(g.name)
    if bind == 'skin':
        ob.parent = rig
        for m in ob.modifiers:
            if m.type == 'ARMATURE': m.object = rig
        if not any(m.type == 'ARMATURE' for m in ob.modifiers): ob.modifiers.new('Armature', 'ARMATURE').object = rig
    else:
        ob.modifiers.clear(); H.bind_rigid(ob, rig, rename(bind))
    return ob


# ── Hands: weapons, shields, reins, the string and the arrow ────────────────
def fist(part, n):
    """The middle of a closed fist and its frame: knuckle line (index to little finger) and
    the way the hand points."""
    hand = part.pose.bones[f'hand.{n}']; Mh = hand.matrix.to_3x3()
    k = (Mh @ H.HAND_REF[n][0]).normalized(); f = (hand.tail - hand.head).normalized()
    return HP.fist_point(part, n), k, (f - k * f.dot(k)).normalized()

def frame(z, y, at):
    """A matrix with its Z along z and Y as near y as allowed, at `at`."""
    z = z.normalized(); x = y.cross(z).normalized(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = at; return M


# ── Reins ───────────────────────────────────────────────────────────────────
def rein_line(bvh, bit, terret, end, sx, sag=.06):
    """A rein from a bit ring back beside the neck to the terret on the yoke saddle, then a
    sagging span to `end`; also returns where the span starts."""
    neck = HP.rein_path(bvh, bit, terret, sx, 24)
    n = 20; span = [terret.lerp(end, i / n) - V((0, 0, sag * 4 * (i / n) * (1 - i / n))) for i in range(1, n + 1)]
    return neck + span, len(neck)

def skin_reins(ob, rig, horses, lines, ends):
    """Skin reins: the neck part to the nearest face of its horse (no legs), the span blended
    from that horse's chest to the end bone (ends: per line, a bone name)."""
    acc_lines = []
    for (pts, k), (hb, pre), end in zip(lines, horses, ends): acc_lines.append((pts, k, hb, pre, end))
    bvhs = {id(hb): (BVHTree.FromObject(hb, bpy.context.evaluated_depsgraph_get()), {g.index: g.name for g in hb.vertex_groups}) for _, _, hb, _, _ in acc_lines}
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co; best = None
        for li, (pts, k, hb, pre, end) in enumerate(acc_lines):
            for i, q in enumerate(pts):
                d = (q - p).length_squared
                if best is None or d < best[0]: best = (d, li, i)
        _, li, i = best; pts, k, hb, pre, end = acc_lines[li]
        acc = {}
        if i < k:
            bvh, names = bvhs[id(hb)]; fi = bvh.find_nearest(p)[2]
            for vi in hb.data.polygons[fi].vertices:
                for ge in hb.data.vertices[vi].groups:
                    n = names[ge.group]
                    if not any(t in n for t in HR.LEG_BONE): acc[n] = acc.get(n, 0) + ge.weight
            tot = sum(acc.values()) or 1; acc = {n: w / tot for n, w in acc.items() if w / tot > .02}
        else:
            s = (i - k + 1) / (len(pts) - k); acc = {pre + '_chest': 1 - s, end: s}
        for n, w in acc.items(): (ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)).add([v.index], w, 'REPLACE')
    mw = ob.matrix_world.copy(); ob.parent = rig; ob.matrix_world = mw
    ob.modifiers.new('Armature', 'ARMATURE').object = rig


# ── Poses ───────────────────────────────────────────────────────────────────
def crew_poses(J, pre):
    """Pose builders for one man: his J moved to his place in the car; st() gives his
    role's ready stance with overrides."""
    off = V((CREW[pre]['at'][0], CREW[pre]['at'][1], FLOOR)); SR, SL = J['r-shoulder'] + off, J['l-shoulder'] + off
    def armR(w, hint=(-1, .45, -.55), grip=(0, 0, -1), **kw): return {'w': SR + V(w), 'hint': hint, 'spear': grip, **kw}
    def armL(w, hint=(1, .45, -.55), grip=(0, 0, -1), **kw): return {'w': SL + V(w), 'hint': hint, 'spear': grip, **kw}
    base = {'hips': {'loc': (0, 0, -.035)}, 'chest': {'rot': (.08, 0, 0)}, 'head': {'rot': (-.05, 0, 0)},
            'ik_foot.L': {'loc': (-.065, -.05, 0)}, 'ik_foot.R': {'loc': (.065, .05, 0)}, 'knee': (.25, -1, 0)}
    if pre in DRIVERS:   # the reins in both fists, thumbs up, the shield's grip in the left
        base.update(armR=armR((.07, -.3, -.3)), armL=armL((-.07, -.3, -.28)))
    elif pre == 'ar':    # the bow low in the left fist, an arrow on the string in the right
        base.update(armL=armL((-.02, -.32, -.2), hint=(1, .3, -.7)), armR=armR((.33, -.17, -.2), hint=(-.4, .7, -.6)),
                    **{'ik_foot.L': {'loc': (-.06, -.08, 0)}, 'ik_foot.R': {'loc': (.07, .07, 0)}})
    else:                # the spear upright in the right fist, the shield's grip in the left
        base.update(armR=armR((-.03, -.22, -.3), hint=(-1, .5, -.4)), armL=armL((-.1, -.3, -.22)))
    def st(**over):
        P_ = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
        for k, v in over.items(): P_[k] = v if (k.startswith('arm') or k == 'knee') else {**P_.get(k, {}), **v}
        return P_
    return st, armR, armL, off


# ── Build ───────────────────────────────────────────────────────────────────
def build(static=False):
    body, J = H.build_body()
    T = {}   # template objects: name -> (object, material, bind)
    def add(ob, mt, bind): T[ob.name] = (ob, mt, bind); return ob
    crew_kit(body, J, add)
    add(body, m_skin_kemet(J['l-eye']), 'skin-body')
    # weapons, built about their grips
    reed, bronze, feather = H.m_flat('Reed', '#b8a070', .6), m_bronze('WeaponBronze', .25, 256), H.m_flat('Fletching', '#e4ddd0', .8)
    gold = C.m_gold('WeaponGold', 512)
    bow12, nocks12 = bow_mesh('Bow12', 1.2); add(bow12, H.m_flat('BowWood', '#7a4a26', .45), 'later')
    bow3, nocks3 = bow_mesh('Bow3', 1.36); add(bow3, gold, 'later')
    for o, mt in arrow_parts('Arrow', (reed, bronze, feather)): add(o, mt, 'later')
    cow = Mat('Cowhide', res=1024); t = cow.node('ShaderNodeTexImage'); t.image = tile_image(os.path.join(OUT, 'cowhide.png'), 'cowhide')
    cow.L.new(cow.coord.outputs['UV'], t.inputs['Vector']); cow.set(t.outputs['Color'], .8, cow.noise(300, 3).outputs['Fac'], .2, .001)
    for o, mt in shield_parts('ShieldCow', cow, m_leather('ShieldRim', '#c09a6a', 256), m_wood('ShieldWood')): add(o, mt, 'later')
    for o, mt in shield_parts('ShieldGold', gold, gold, m_wood('ShieldWood2'), boss=gold): add(o, mt, 'later')
    for o, mt in spear_parts('Spear4', .9, 1.42, .24, (m_wood('SpearWood'), bronze)): add(o, mt, 'later')
    for o, mt in spear_parts('Spear5', 1.0, 1.6, .3, (m_wood('SpearWood5'), bronze), gilt=gold): add(o, mt, 'later')
    for o, mt in khopesh('Khopesh4', bronze, m_leather('KhopeshGrip', '#3a2416', 256)): add(o, mt, 'later')
    for o, mt in khopesh('Khopesh5', gold, gold): add(o, mt, 'later')
    # the horse: horse.py's, without its Greek sheepskin, girth and breast strap
    HT = {}
    drop = []
    def hadd(ob, mt, bind):
        if ob.name in ('SaddleCloth', 'SheepskinFringe', 'Girth', 'BreastStrap'): drop.append(ob); return ob
        if ob.name in ('HorseMane', 'HorseForelock'): ob.name = 'L01234_' + ob.name[5:]
        HT[ob.name] = (ob, mt, bind); return ob
    drape = H.drape; H.drape = lambda name, ob, *a, **k: ob   # the sheepskin is dropped: skip its cloth sim
    hbody, hbvh = HR.build_horse(hadd)
    H.drape = drape
    for ob in drop: bpy.data.objects.remove(ob)
    for nm, k in (('L01234_Mane', .35), ('HorseTail', .35), ('Horse', .75)):   # two horses: lighter hair and hide
        mod(HT[nm][0], 'DECIMATE', ratio=k); bake_mods(HT[nm][0])
    hbody.data.validate(clean_customdata=False)
    HT = {v[0].name: v for v in HT.values()}   # the bit rings are renamed after they are added
    blaze_attr(hbody, hbvh); HT['Horse'] = (hbody, m_team_coat(), 'body')
    yoke_top, terrets = horse_kit(hbody, lambda ob, mt, bind: HT.__setitem__(ob.name, (ob, mt, bind)) or ob)
    # the car, built about its axle
    CT = {}
    rail, cmats = C.build_car(lambda ob, mt, bind: CT.__setitem__(ob.name, (ob, mt, bind)) or ob,
                              (Y_H + YS_Y - Y_A, yoke_top.z + .025), HX, OUT)
    C.gear(lambda ob, mt, bind: CT.__setitem__(ob.name, (ob, mt, bind)) or ob, cmats, lambda nm: bow_mesh(nm, 1.15)[0])
    for ob, mt, bind in CT.values(): ob.location.y += Y_A; bake_obj_xform(ob)
    H.bake_textures({**T, **HT, **CT})
    if 'blaze' in hbody.data.color_attributes: hbody.data.color_attributes.remove(hbody.data.color_attributes['blaze'])
    # template weights: each body auto-weighted to a skeleton of its own at the origin, kit from it
    tman = HR.build_rig('TmpManRig', H.skeleton_spec(J))
    H.activate(body); tman.select_set(True); bpy.context.view_layer.objects.active = tman; bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for nm, (ob, mt, bind) in T.items():
        if bind == 'skin': H.bind_skin(ob, tman, body)
    thorse = HR.build_rig('TmpHorseRig')
    H.activate(hbody); thorse.select_set(True); bpy.context.view_layer.objects.active = thorse; bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for nm, (ob, mt, bind) in HT.items():
        if ob is hbody: continue
        if bind in ('horse', 'horse-trunk'):
            H.bind_skin(ob, thorse, hbody)
            if bind == 'horse-trunk': HR.trunk_only(ob)
        elif bind == 'tail': HR.weight_to_chain(ob, thorse, HR.TAIL_BONES)
    # the shared armature, and the figures copied onto it
    rig = HR.build_rig('ChariotRig', bone_list(J))
    for n in 'LR':   # hand reference vectors, as hoplite.build_armature finds them
        s = n.lower(); bone = rig.data.bones[f'ar_hand.{n}']; inv = bone.matrix_local.to_3x3().inverted()
        k = J[f'{s}-finger-5-2'] - J[f'{s}-finger-2-2']; y = (bone.tail_local - bone.head_local).normalized(); palm = k.cross(y).normalized()
        if palm.x * (1 if n == 'L' else -1) > 0: palm = -palm
        H.HAND_REF[n] = (inv @ k, inv @ palm)
    rig.data.pose_position = 'REST'; H._upd()
    objs = {}
    for pre, sx in (('hl', 1), ('hr', -1)):
        off = V((sx * HX, Y_H, 0)); f = horse_name(pre)
        for nm, (ob, mt, bind) in HT.items():
            b = 'skin' if bind in ('body', 'horse', 'horse-trunk', 'tail') else bind
            objs[f'{nm}{"LR"[sx < 0]}'] = instance(ob, f'{nm}{"LR"[sx < 0]}', rig, off, f, b)
    for pre, cw in CREW.items():
        off = V((cw['at'][0], cw['at'][1], FLOOR)); f = man_name(pre); P_ = pre.upper()
        names = [('Body', cw['tag']), ('EyeL', cw['tag']), ('EyeR', cw['tag']), ('Hair', cw['tag']), (cw['kilt'], cw['tag']),
                 ('KiltFold' + cw['kilt'][4:], cw['tag']), ('Belt' + cw['kilt'][4:], cw['tag'])] + cw['kit']
        for nm, tag in names:
            ob, mt, bind = T[nm]
            objs[tag + nm + P_] = instance(ob, tag + nm + P_, rig, off, f, 'skin' if bind in ('skin', 'skin-body') else bind)
    for nm, (ob, mt, bind) in CT.items(): H.bind_rigid(ob, rig, bind); objs[nm] = ob
    rig.data.pose_position = 'POSE'; H._upd()
    # the idle pose, and everything held placed in the hands
    parts = {pre: Part(rig, man_name(pre), [b[0] for b in H.skeleton_spec(J)]) for pre in CREW}
    horses = {pre: Part(rig, horse_name(pre), HR.BONE_NAMES) for pre in ('hl', 'hr')}
    for hp in horses.values(): HR.hpose(hp, {})
    for pre, part in parts.items(): H.pose(part, crew_poses(J, pre)[0]())
    held = place_gear(rig, parts, T, J)
    reins = make_reins(rig, parts, objs, terrets, rail)
    for o in rig.children:   # the glTF exporter checks this too
        if o.type == 'MESH' and o.name.startswith('Horse') and o.data.validate(): print('repaired', o.name)
    for ob in [v[0] for v in T.values()] + [v[0] for v in HT.values()] + [tman, thorse]:   # the templates have all been copied
        bpy.data.objects.remove(ob)
    if static: return rig, [], parts, horses
    return rig, actions(rig, J, parts, horses, {'yoke_top': yoke_top}), parts, horses

def place_gear(rig, parts, T, J):
    """In the idle pose: the bows (and their strings) in the archer's left fist with the arrow
    on the string, the shields in the left fists, the spear in the spearman's right fist (on
    a bone of its own, so its grip can change), the khopesh at his belt."""
    used = set()
    def put(names, M, bone, tag, suffix):
        for nm in names:
            ob, mt, bind = T[nm]; c = ob.copy(); c.data = ob.data.copy(); c.name = tag + nm + suffix; link(c)
            c.matrix_world = M @ ob.matrix_world; bpy.context.view_layer.update(); H.bind_rigid(c, rig, bone); used.add(nm)
    ar = parts['ar']; pL, kL, fL = fist(ar, 'L')
    Mbow = frame(-kL, -fL, pL)   # limbs along the knuckle line (thumb up), the string toward him
    put(['Bow12'], Mbow, 'ar_hand.L', 'L12_', ''); put(['Bow3'], Mbow, 'ar_hand.L', 'L3_', '')
    nock = Mbow @ V((0, BRACE, 0))
    add_bone(rig, 'nock', nock, nock + (Mbow.to_3x3() @ V((0, .06, 0))), 'ar_hand.L')
    pR, kR, fR = fist(ar, 'R'); d = ((pL + kL * -.02) - nock).normalized()
    add_bone(rig, 'arrow', nock, nock + d * .1, 'car', False)
    H._upd()
    for tag in ('L12_', 'L3_'):   # the strings: each half skinned from the bow's tip to the nock bone
        L = 1.2 if tag == 'L12_' else 1.36; half = L / 2
        tip = lambda s: Mbow @ V((0, BRACE, s * (.05 + (half - .05) * .88)))
        lines = [[tip(1).lerp(nock, i / 12) for i in range(13)], [nock.lerp(tip(-1), i / 12) for i in range(13)]]
        st = curve_mesh(tag + 'String', [[tuple(p) for p in L_] for L_ in lines], .0017, res=1)
        st.data.materials.append(H.m_flat('String', '#d8ccb0', .7).m)
        g0, g1 = st.vertex_groups.new(name='ar_hand.L'), st.vertex_groups.new(name='nock')
        for v in st.data.vertices:
            p = st.matrix_world @ v.co; a = min((p - tip(1)).length, (p - tip(-1)).length); b = (p - nock).length; w = a / max(1e-6, a + b)
            g0.add([v.index], 1 - w, 'REPLACE'); g1.add([v.index], w, 'REPLACE')
        st.parent = rig; st.modifiers.new('Armature', 'ARMATURE').object = rig
    root = bpy.data.objects.new('ShootArrow', None); link(root)
    root.matrix_world = frame(d, V((0, 0, 1)), nock); bpy.context.view_layer.update(); H.bind_rigid(root, rig, 'arrow')
    for nm in ('ArrowShaft', 'ArrowHead', 'ArrowFletch'):
        ob, mt, bind = T[nm]; c = ob.copy(); c.data = ob.data.copy(); c.name = 'L123_' + nm; link(c)
        c.matrix_world = root.matrix_world @ ob.matrix_world; bpy.context.view_layer.update()
        mw = c.matrix_world.copy(); c.parent = root; c.matrix_world = mw; used.add(nm)
    # shields: the grip bar up the fist, the face forward
    for pre, tags in (('dr', [('ShieldCow', 'L123_')]), ('ds', [('ShieldCow', 'L4_'), ('ShieldGold', 'L5_')]), ('sp', [('ShieldCow', 'L4_'), ('ShieldGold', 'L5_')])):
        p, k, f = fist(parts[pre], 'L'); fw = V((0, -1, 0)); M = frame(fw - k * fw.dot(k), -k, p)
        for base, tag in tags:
            names = [n for n in T if n.startswith(base) and n[len(base):] in ('Face', 'Back', 'Rim', 'Grip', 'Boss')]
            put(names, M, f'{pre}_hand.L', tag, pre.upper())
    # the spear on its own bone at the right fist, upright
    p, k, f = fist(parts['sp'], 'R'); up = V((0, -.06, 1)).normalized()
    add_bone(rig, 'spear', p, p + up * .1, 'car', False); H._upd()
    for base, tag in (('Spear4', 'L4_'), ('Spear5', 'L5_')):
        put([n for n in T if n.startswith(base)], frame(up, V((0, -1, 0)), p), 'spear', tag, '')
    # the khopesh tucked in the belt at the left hip, blade hanging forward
    off = V((CREW['sp']['at'][0], CREW['sp']['at'][1], FLOOR))
    Mk = Matrix.Translation(off + V((.16, -.06, 1.0))) @ Matrix.Rotation(math.radians(160), 4, 'X') @ Matrix.Rotation(math.radians(-80), 4, 'Y') @ Matrix.Rotation(math.radians(10), 4, 'Z')
    for base, tag in (('Khopesh4', 'L4_'), ('Khopesh5', 'L5_')):
        put([n for n in T if n.startswith(base)], Mk, 'sp_hips', tag, '')
    return used

def make_reins(rig, parts, objs, terrets, rail):
    """Each driver's reins (four: a pair from each horse, the left horse's to his left fist,
    the right horse's to his right) on bones keyed to his fists; L0_Reins tied to the front
    rail for the car and team alone."""
    leather = m_leather('Reins', '#3e2818', 256)
    hb = {pre: objs['Horse' + s] for pre, s in (('hl', 'L'), ('hr', 'R'))}
    bvh = {pre: BVHTree.FromObject(hb[pre], bpy.context.evaluated_depsgraph_get()) for pre in hb}
    rings = {}
    for pre, s in (('hl', 'L'), ('hr', 'R')):
        for side in 'LR':
            o = objs[f'BitRing{side}{s}']; rings[(pre, side)] = o.matrix_world @ (sum((v.co for v in o.data.vertices), V()) / len(o.data.vertices))
    def terret(pre, side):
        sx = HX if pre == 'hl' else -HX; t = terrets[0 if side == 'L' else 1]; return V((t.x + sx, t.y + Y_H, t.z))
    out = []
    for drv, tag in DRIVERS.items():
        part = parts[drv]; lines, horses_, ends = [], [], []
        for pre in ('hl', 'hr'):
            hand = 'L' if pre == 'hl' else 'R'; p, k, f = fist(part, hand)
            bone = f'reins.{drv}.{hand}'
            if bone not in rig.data.bones: add_bone(rig, bone, p, p + V((0, .08, 0)), 'car')
            for side in 'LR':
                sx = 1 if side == 'L' else -1
                lines.append(rein_line(bvh[pre], rings[(pre, side)] + V((0, .02, .004)), terret(pre, side), p + V((sx * .008, 0, 0)), sx))
                horses_.append((hb[pre], pre)); ends.append(bone)
        ob = curve_mesh(tag + 'Reins', [[tuple(q) for q in L[0]] for L in lines], .0045, res=1)
        H.bake_textures({ob.name: (ob, leather, '')}); skin_reins(ob, rig, horses_, lines, ends); out.append(ob)
    # the car and team alone: the reins tied round the front rail
    lines, horses_, ends = [], [], []
    for pre in ('hl', 'hr'):
        for side in 'LR':
            sx = 1 if side == 'L' else -1; xr = (.12 if pre == 'hl' else -.12) + sx * .015
            q = min(rail, key=lambda r: abs(r.x - xr) + 3 * max(0, r.y - C.Y_FRONT - .2)) + V((0, Y_A, .0))
            lines.append(rein_line(bvh[pre], rings[(pre, side)] + V((0, .02, .004)), terret(pre, side), q, sx, .1))
            horses_.append((hb[pre], pre)); ends.append('car')
    ob = curve_mesh('L0_Reins', [[tuple(q) for q in L[0]] for L in lines], .0045, res=1)
    H.bake_textures({ob.name: (ob, leather, '')}); skin_reins(ob, rig, horses_, lines, ends); out.append(ob)
    return out


# ── Moves ───────────────────────────────────────────────────────────────────
# horse.py's gaits with the strides set so the wheels turn a whole number of spokes per
# stride (the clips loop seamlessly) at the speed the hooves pass over the ground.
SPOKE = math.pi / 3
HR.GAITS['walk'] = {**HR.GAITS['walk'], 'stride': 2 * SPOKE * C.R_W * HR.GAITS['walk']['stance']}
HR.GAITS['gallop'] = {**HR.GAITS['gallop'], 'stride': 7 * SPOKE * C.R_W * HR.GAITS['gallop']['stance']}
def ground_speed(g):   # metres per frame
    G = HR.GAITS[g]; return G['stride'] / G['stance'] / G['frames']

def slerp_dir(keys, f):
    """A direction keyed at frames (smoothstep between keys)."""
    keys = sorted(keys)
    if f <= keys[0][0]: return V(keys[0][1]).normalized()
    for (f0, d0), (f1, d1) in zip(keys, keys[1:]):
        if f <= f1:
            t = C.smooth(f0, f1, f); q = V(d0).normalized().rotation_difference(V(d1).normalized())
            return Quaternion().slerp(q, t) @ V(d0).normalized()
    return V(keys[-1][1]).normalized()

def actions(rig, J, parts, horses, info):
    PB = rig.pose.bones
    HB = [p.f(n) for p in horses.values() for n in HR.BONE_NAMES]
    MB = {pre: [p.f(b[0]) for b in H.skeleton_spec(J)] for pre, p in parts.items()}
    car_rest = rig.data.bones['car'].matrix_local.copy(); axle = V((0, Y_A, C.R_W))
    yk = {pre: info['yoke_top'] + V((sx * HX, Y_H, 0)) for pre, sx in (('hl', 1), ('hr', -1))}
    y0 = (yk['hl'] + yk['hr']) / 2; dy0, dz0 = y0.y - Y_A, y0.z - C.R_W
    poses = {pre: crew_poses(J, pre) for pre in parts}
    for o in SC.objects:   # posing need not re-evaluate the skinned meshes
        for m in o.modifiers:
            if m.type == 'ARMATURE': m.show_viewport = False
    def key(names, f):
        for n in names: pb = PB[n]; pb.keyframe_insert('location', frame=f); pb.keyframe_insert('rotation_quaternion', frame=f)
    def car_matrix(extra):
        """The car pivots on its axle so the pole's end stays on the yoke saddles."""
        ps = [horses[pre].pose.bones['h_chest'].matrix @ horses[pre].data.bones['h_chest'].matrix_local.inverted() @ yk[pre] for pre in yk]
        z = max((ps[0].z + ps[1].z) / 2, .14) - C.R_W
        th = -(math.atan2(z, -dy0) - math.atan2(dz0, -dy0))
        M = Matrix.Translation(axle) @ Matrix.Rotation(th, 4, 'X') @ Matrix.Translation(-axle)
        return (extra @ M if extra is not None else M) @ car_rest
    def clip(name, length, horse_fn, crew, speed=0.0, spear=None, release=None, drop=None, car_extra=None):
        """horse_fn(f) -> {'hl': spec, 'hr': spec} (keyed every frame); crew: {man: [(frame, spec or callable)]};
        speed: ground covered per frame (the wheels turn to it, or speed(f) for the angle);
        spear: [(frame, direction)]; release: (f0, f1) the string held from f0 to f1 (from 1 when f0 is None);
        drop: (f0, f1) the drivers let go of the reins; car_extra(f): a matrix applied to the car."""
        rig.animation_data_create(); act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
        if callable(horse_fn):
            for f in range(1, length + 1):
                for pre, spec in horse_fn(f).items(): HR.hpose(horses[pre], spec)
                key(HB, f)
        else:   # keyed at its own frames per horse
            for pre, keys in horse_fn.items():
                for f, spec in keys: HR.hpose(horses[pre], spec); key([horses[pre].f(n) for n in HR.BONE_NAMES], f)
        for f in range(1, length + 1):
            SC.frame_set(f)
            PB['car'].matrix = car_matrix(car_extra(f) if car_extra else None); H._upd(); key(['car'], f)
            ang = speed(f) if callable(speed) else speed * (f - 1) / C.R_W
            for w in ('wheel.L', 'wheel.R'): PB[w].rotation_quaternion = Quaternion((0, 1, 0), ang); PB[w].location = (0, 0, 0)
            key(['wheel.L', 'wheel.R'], f)
        for pre, keys in crew.items():
            for f, spec in keys:
                SC.frame_set(f); spec = spec() if callable(spec) else spec
                H.pose(parts[pre], spec); key(MB[pre], f)
        ar, sp = parts['ar'], parts['sp']
        rel = {n: car_rest.inverted() @ rig.data.bones[n].matrix_local for n in rig.data.bones.keys() if n.startswith('reins.')}
        nock_rest = rig.data.bones['nock'].matrix_local; hand_rest = rig.data.bones['ar_hand.L'].matrix_local
        arrow_rest = rig.data.bones['arrow'].matrix_local; spear_rest = rig.data.bones['spear'].matrix_local
        for f in range(1, length + 1):
            SC.frame_set(f); carM = PB['car'].matrix.copy()
            for drv in DRIVERS:   # the reins' hand ends ride in the fists, or drop on the floor
                for hand in 'LR':
                    n = f'reins.{drv}.{hand}'; M = carM @ rel[n]; tgt = HP.fist_point(parts[drv], hand)
                    if drop:
                        s_ = C.smooth(drop[0], drop[1], f)
                        if s_ > 0: tgt = tgt.lerp(carM @ car_rest.inverted() @ V((CREW[drv]['at'][0] * .5, Y_A + C.Y_FRONT + .12, FLOOR + .02)), s_)
                    M.translation = tgt; PB[n].matrix = M
            key([n for n in rel], f)
            # the string: on the right fist while he holds it, else straight at its brace
            hold = release is None or ((release[0] is None or f >= release[0]) and f <= release[1])
            hm = PB['ar_hand.L'].matrix @ hand_rest.inverted()
            brace = hm @ nock_rest.translation
            nock = HP.fist_point(ar, 'R') if hold else brace
            M = hm @ nock_rest; M.translation = nock; PB['nock'].matrix = M
            pL, kL, fL = fist(ar, 'L'); rest_pt = pL + kL * -.02
            d = (rest_pt - nock).normalized(); d0 = arrow_rest.to_3x3().col[1].normalized()
            M = (d0.rotation_difference(d).to_matrix() @ arrow_rest.to_3x3()).to_4x4(); M.translation = nock; PB['arrow'].matrix = M
            p, k, fw = fist(sp, 'R'); d = slerp_dir(spear or [(1, (0, -.06, 1))], f); d0 = spear_rest.to_3x3().col[1].normalized()
            M = (d0.rotation_difference(d).to_matrix() @ spear_rest.to_3x3()).to_4x4(); M.translation = p; PB['spear'].matrix = M
            H._upd(); key(['nock', 'arrow', 'spear'], f)
        return act
    A = []
    def every(keys_fn, frames):
        return {pre: [(f, keys_fn(pre, f)) for f in frames] for pre in parts}
    def lean(pre, k=0.0, **over):   # riding at speed: knees bent, leaning into the horses
        P_ = dict(hips={'loc': (0, 0, -.06 - .025 * k)}, chest={'rot': (.15 + .04 * k, 0, 0)}, head={'rot': (-.12 - .03 * k, 0, 0)}); P_.update(over)
        return poses[pre][0](**P_)
    # Idle: the team stands, tails swishing, a head tossed; the crew breathe
    def idle_h(f):
        w = 2 * math.pi * (f - 1) / 48
        return {'hl': {'body': {'loc': (0, 0, .005 * math.sin(w))}, 'h_neck1': {'rot': (.03 * math.sin(w + 1), 0, 0)}, 'h_tail2': {'rot': (0, 0, .14 * math.sin(2 * w))}},
                'hr': {'body': {'loc': (0, 0, .005 * math.sin(w + 2))}, 'h_neck1': {'rot': (.03 * math.sin(w + 2.5) - .08 * math.sin(w / 2) ** 8, 0, .05 * math.sin(w / 2) ** 8)},
                       'h_head': {'rot': (-.06 * math.sin(w / 2) ** 8, 0, 0)}, 'h_tail2': {'rot': (0, 0, .12 * math.sin(2 * w + 1.3))}}}
    def breathe(pre, f):
        st = poses[pre][0]; b = math.sin(2 * math.pi * (f - 1) / 48 + {'ar': 0, 'dr': 1.5, 'ds': 1.5, 'sp': 0}[pre])
        return st(hips={'loc': (0, 0, -.035 - .004 * b)}, chest={'rot': (.08 + .012 * b, 0, 0)})
    A.append(clip('Idle', 49, idle_h, every(breathe, (1, 13, 25, 37, 49))))
    # Walk: the walk of horse.py, the wheels turning; the crew sway with the car
    def sway(pre, f):
        st = poses[pre][0]; c = math.cos(2 * math.pi * (f - 1) / 14)
        return st(hips={'loc': (0, 0, -.035 - .008 * (1 - c) / 2), 'rot': (0, 0, .025 * math.cos(2 * math.pi * (f - 1) / 28))}, chest={'rot': (.08, 0, -.02 * math.cos(2 * math.pi * (f - 1) / 28))})
    A.append(clip('Walk', 29, lambda f: {'hl': HR.gait(horses['hl'], 'walk', f - 1), 'hr': HR.gait(horses['hr'], 'walk', f - 1 + 7)},
                  every(sway, (1, 8, 15, 22, 29)), ground_speed('walk')))
    # Gallop: both horses nearly in step, the car pitching on its axle as the withers rise and fall
    gallop = lambda f: {'hl': HR.gait(horses['hl'], 'gallop', f - 1), 'hr': HR.gait(horses['hr'], 'gallop', f - 1 + .6)}
    def bob(pre, f): return lean(pre, (1 - math.cos(2 * math.pi * (f - 1 + (2 if pre in DRIVERS else 0)) / 8)) / 2)
    A.append(clip('Gallop', 17, gallop, every(bob, (1, 3, 5, 7, 9, 11, 13, 15, 17)), ground_speed('gallop')))
    # Shoot, at the gallop: the archer raises the bow, draws to the jaw, looses, lowers and
    # nocks again; side-on to a target ahead and to the left
    st, armR, armL, _ = poses['ar']
    def side_on(k, **over):
        P_ = lean('ar', 0, hips={'loc': (0, 0, -.06), 'rot': (0, -.36 * k, 0)}, chest={'rot': (.06 + .09 * (1 - k), -.52 * k, 0)},
                  neck={'rot': (0, .38 * k, 0)}, head={'rot': (.06 * k - .1 * (1 - k), .46 * k, 0)})
        P_.update(over); return P_
    raise_ = side_on(.75, armL=armL((.34, -.26, .02), hint=(.4, .3, -1)), armR=armR((.26, -.2, -.02), hint=(-1, .5, -.2)))
    drawn = side_on(1, armL=armL((.4, -.12, .145), hint=(.2, .4, -1)), armR=armR((.103, -.076, .139), hint=(-1, .7, .55)))
    loosed = side_on(1, armL=armL((.4, -.12, .15), hint=(.2, .4, -1)), armR=armR((.04, -.02, .16), hint=(-1, .8, .6), fist=.35))
    follow = side_on(.85, armL=armL((.39, -.14, .12), hint=(.2, .4, -1)), armR=armR((-.02, .02, .08), hint=(-1, .8, .4), fist=.5))
    ar_keys = [(1, lean('ar')), (6, raise_), (11, drawn), (14, drawn), (SHOOT_RELEASE, loosed), (19, follow),
               (26, side_on(.3, armL=armL((.12, -.3, -.12), hint=(.8, .3, -.8)), armR=armR((.3, -.17, -.15), hint=(-.4, .7, -.6)))), (33, lean('ar'))]
    crew = every(bob, range(1, 34, 2)); crew['ar'] = ar_keys
    A.append(clip('Shoot', 33, gallop, crew, ground_speed('gallop'), release=(None, SHOOT_RELEASE - 1)))
    # Thrust, at the gallop: the spearman lifts the spear and drives it forward and down to
    # the right, past the team, and recovers it
    st, armR, armL, _ = poses['sp']
    up = (0, -.06, 1); level = (-.25, -1, -.04); low = (-.42, -.88, -.26)
    sp_keys = [(1, lean('sp')),
               (7, lean('sp', 0, chest={'rot': (.1, .22, 0)}, armR=armR((-.1, .08, .06), hint=(-1, .5, .3)), armL=armL((-.06, -.36, -.18)))),
               (11, lean('sp', 0, hips={'loc': (0, -.05, -.08)}, chest={'rot': (.32, -.34, 0)}, head={'rot': (.05, -.2, 0)},
                         armR=armR((-.16, -.5, -.12), hint=(-1, .3, -.2)), armL=armL((.0, -.34, -.24)))),
               (16, lean('sp', 0, hips={'loc': (0, -.05, -.08)}, chest={'rot': (.3, -.32, 0)}, head={'rot': (.05, -.2, 0)},
                         armR=armR((-.15, -.46, -.12), hint=(-1, .3, -.2)), armL=armL((.0, -.34, -.24)))),
               (24, lean('sp', 0, chest={'rot': (.12, .1, 0)}, armR=armR((-.08, -.1, -.1), hint=(-1, .5, -.2)))), (33, lean('sp'))]
    crew = every(bob, range(1, 34, 2)); crew['sp'] = sp_keys
    A.append(clip('Thrust', 33, gallop, crew, ground_speed('gallop'), spear=[(1, up), (6, level), (11, low), (16, low), (24, (-.1, -.4, 1)), (33, up)]))
    # Hit: the team shies, the crew flinch
    flinch = {'body': {'loc': (.04, .04, .02), 'rot': (-.06, 0, .06)}, 'h_neck1': {'rot': (-.25, 0, -.1)}, 'h_head': {'rot': (-.2, 0, 0)},
              'legs': {'LF': {'off': (.02, -.05, .12), 'cannon': .8, 'pastern': -.4}}}
    def hit_keys(pre):
        st = poses[pre][0]
        return [(1, st()), (4, st(chest={'rot': (-.2, 0, 0)}, head={'rot': (-.28, 0, 0)}, hips={'loc': (0, .06, -.05)})), (10, st(chest={'rot': (0, 0, 0)}, head={'rot': (-.1, 0, 0)})), (18, st())]
    A.append(clip('Hit', 18, lambda f: {pre: {} for pre in horses} if f in (1, 18) else
                  {pre: (flinch if 3 <= f <= 6 else {'body': {'loc': (.02, .01, 0)}, 'h_neck1': {'rot': (-.08, 0, 0)}}) for pre in horses},
                  {pre: hit_keys(pre) for pre in parts}))
    # Death: the team stumbles, falls to its knees and rolls apart onto its sides; the pole
    # drops, the car tips forward on its axle and over onto its right wheel; the crew are
    # thrown out over the sides
    kneel = {'off': (0, .1, .26), 'cannon': 1.55, 'pastern': -1.3, 'body': True}
    tuck = {'off': (0, -.32, .3), 'cannon': -1.2, 'pastern': -.2, 'body': True}
    def death_h(pre):
        s_ = 1 if pre == 'hl' else -1; d = 2 if pre == 'hr' else 0
        return [(1, {}),
                (8 + d, {'body': {'loc': (0, -.04, -.03), 'rot': (.1, 0, 0)}, 'h_neck1': {'rot': (.25, 0, 0)}, 'legs': {'LF': {'off': (0, -.05, 0), 'cannon': .3}}}),
                (16 + d, {'body': {'loc': (0, -.05, -.34), 'rot': (.36, 0, 0)}, 'h_neck1': {'rot': (.35, 0, 0)}, 'h_head': {'rot': (.2, 0, 0)}, 'legs': {'LF': kneel, 'RF': kneel}}),
                (26 + d, {'body': {'loc': (0, -.02, -.6), 'rot': (.04, 0, 0)}, 'h_neck1': {'rot': (.2, 0, 0)}, 'legs': {'LF': kneel, 'RF': kneel, 'LH': tuck, 'RH': tuck}}),
                (38 + d, {'body': {'loc': (s_ * .28, 0, -.66), 'rot': (0, -s_ * 1.35, 0)}, 'h_neck1': {'rot': (.15, 0, s_ * .3)}, 'h_head': {'rot': (.1, 0, s_ * .25)},
                          'legs': {k: {'off': (0, 0, 0), 'body': True} for k in ('LF', 'RF', 'LH', 'RH')}}),
                (60, {'body': {'loc': (s_ * .3, 0, -.67), 'rot': (0, -s_ * 1.4, 0)}, 'h_neck1': {'rot': (.1, 0, s_ * .35)}, 'h_head': {'rot': (.05, 0, s_ * .35)},
                      'legs': {k: {'off': (0, .03, 0), 'body': True} for k in ('LF', 'RF', 'LH', 'RH')}})]
    DH = {pre: death_h(pre) for pre in horses}
    foot = V((-C.TRACK, Y_A, 0))
    def tip(f):   # over onto the right wheel, about its foot
        r = -.2 * C.smooth(22, 36, f) + .03 * math.sin(math.pi * C.smooth(36, 44, f))
        return Matrix.Translation(foot) @ Matrix.Rotation(r, 4, 'Y') @ Matrix.Translation(-foot)
    def fall(pre):
        st, armR, armL, off = poses[pre]; sx = 1 if CREW[pre]['at'][0] > 0 else -1
        flung = dict(armR=armR((-.2 - .2 * sx, -.1, .1), hint=(0, .5, -1), fist=.6), armL=armL((.2 - .2 * sx, -.1, .1), hint=(0, .5, -1), fist=.6))
        land = (sx * 1.62, Y_A - .7, .14)
        limp = dict(armR=armR((.02, -.12, -.44), hint=(-.3, .6, -1), fist=.5), armL=armL((-.02, -.16, -.43), hint=(.3, .6, -1), fist=.5))
        lie = lambda at, rot, arms=flung: (lambda: st(root={'matrix': HP.root_lying(J, V(at), rot)}, chest={'rot': (0, 0, 0)}, hips={'loc': (0, 0, 0)}, knee=(.15, -1, 0),
                                                      **{'ik_foot.L': {'loc': (0, 0, 0)}, 'ik_foot.R': {'loc': (0, .05, .03)}}, **arms))
        return [(1, st()), (7, st(chest={'rot': (.45, 0, 0)}, hips={'loc': (0, -.06, -.1)}, head={'rot': (-.2, 0, 0)},
                                  armR=armR((.02, -.42, -.08)), armL=armL((-.02, -.42, -.08)))),
                (14, lie((off.x + sx * .32, off.y - .22, FLOOR + .78), (.2, sx * .75, 0))),
                (20, lie((sx * 1.2, Y_A - .5, .55), (-.15, sx * 1.25, 0))),
                (26, lie(land, (-.4, sx * 1.52, 0), limp)), (60, lie((land[0], land[1], land[2] - .01), (-.42, sx * 1.55, 0), limp))]   # the arms fall slack by his sides
    A.append(clip('Death', 60, DH, {pre: fall(pre) for pre in parts},
                  lambda f: .5 * ground_speed('walk') * min(f, 12) / C.R_W, spear=[(1, up), (8, (-.2, -.5, 1)), (20, (-.7, .3, -.1)), (60, (-.7, .35, -.1))],
                  drop=(6, 13), car_extra=tip))
    for o in SC.objects:
        for m in o.modifiers:
            if m.type == 'ARMATURE': m.show_viewport = True
    rig.animation_data.action = A[0]
    return A

if __name__ == '__main__':
    static = '--static' in sys.argv
    rig, acts, parts, horses = build(static)
    if not static:
        H.export(rig, os.path.join(OUT, 'chariot.glb'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'chariot.blend'))
    if '--renders' in sys.argv:
        for lv in (1, 2, 3, 4, 5): H.render(rig, os.path.join(OUT, f'chariot_L{lv}.png'), 'Idle', 1, lv, cam=((5.2, -5.6, 2.4), (76, 0, 43)), res=(640, 480))
    print('built', [a.name for a in acts])
