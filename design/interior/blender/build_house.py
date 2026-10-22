# Дом в Зыково: сборка интерьера в Blender по house.json (те же данные, что на странице интерьера).
# Запуск (Blender 5.2):
#   blender -b --factory-startup --python build_house.py -- --layout 0 --style nord --variant 0 \
#           --views plan,axo,kh,kitchen,bed3,terrace --out renders --samples 96 --res 1600x1067 [--save дом.blend]
# Координаты плана: x вправо, y вниз (как на чертежах). В Blender: X = x, Y = -y, Z вверх.
import bpy, bmesh, json, math, os, sys, random, time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, 'house.json'), encoding='utf-8'))
H = DATA['H']
ROOMS = {r['id']: r for r in DATA['ROOMS']}
WALLS = DATA['WALLS']
STYLES = {s['id']: s for s in DATA['STYLES']}
LAT = {'А': 'a', 'Б': 'b', 'В': 'v', 'Г': 'g'}


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    a = {'layout': '0', 'style': 'nord', 'variant': '0', 'views': 'plan', 'out': os.path.join(HERE, 'renders'),
         'samples': '96', 'res': '1600x1067', 'save': '', 'tag': ''}
    i = 0
    while i < len(argv):
        a[argv[i].lstrip('-')] = argv[i + 1]
        i += 2
    a['layout'] = int(a['layout']); a['variant'] = int(a['variant']); a['samples'] = int(a['samples'])
    if not os.path.isabs(a['out']):
        a['out'] = os.path.join(HERE, a['out'])
    return a


# ---------------------------------------------------------------- стили
EXTRA = {
    'nord':       dict(uph='fabric',  lamp='cone',       curtains='sheer', moldings=False, legs='round',   trim='#F4F2EE', door='#F2F0EC', pot='#F2F0EC', plants=2, art='abstract',  rug='plain',     frame='#1E1F22', upholstered_bed=False),
    'japandi':    dict(uph='linen',   lamp='paper',      curtains='sheer', moldings=False, legs='square',  trim='wood',    door='wood',    pot='#B98D5E', plants=3, art='minimal',   rug='jute',      frame='wood',    upholstered_bed=False),
    'graphite':   dict(uph='wool',    lamp='dome',       curtains=None,    moldings=False, legs='metal',   trim='#ECEAE6', door='#3B3F45', pot='#2F3338', plants=2, art='abstract',  rug='plain',     frame='#1E1F22', upholstered_bed=True),
    'greige':     dict(uph='velvet',  lamp='globe',      curtains='heavy', moldings=True,  legs='round',   trim='#FBF9F4', door='#F4F1EB', pot='#E9E4DB', plants=1, art='abstract',  rug='plain',     frame='#B69A76', upholstered_bed=True),
    'baroque':    dict(uph='velvet',  lamp='chandelier', curtains='heavy', moldings=True,  legs='turned',  trim='#FBF8F1', door='#F6F1E6', pot='#E8E2D6', plants=1, art='classic',   rug='ornate',    frame='gold',    upholstered_bed=True, gold=True),
    'loft':       dict(uph='leather', lamp='edison',     curtains=None,    moldings=False, legs='metal',   trim='#2E3033', door='#2E3033', pot='#B4B1AB', plants=2, art='poster',    rug='worn',      frame='#1F1F1F', upholstered_bed=False),
    'midcentury': dict(uph='wool',    lamp='sputnik',    curtains='sheer', moldings=False, legs='tapered', trim='wood',    door='wood',    pot='#C4704A', plants=2, art='geometric', rug='geometric', frame='wood',    upholstered_bed=False),
}

# ---------------------------------------------------------------- цвет и материалы
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(h, k=1.0):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (min(1.0, lin(r) * k), min(1.0, lin(g) * k), min(1.0, lin(b) * k), 1.0)


def node(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        try:
            setattr(n, k, v)
        except Exception:
            pass
    return n


ALIAS = {'Fac': 'Factor'}


def inp(n, name, val=None, typ=None):
    if name in ALIAS and not any(s.name == name for s in n.inputs):
        name = ALIAS[name]
    for s in n.inputs:
        if s.name == name and (typ is None or s.type == typ) and s.enabled:
            if val is not None:
                s.default_value = val
            return s
    for s in n.inputs:
        if s.name == name and (typ is None or s.type == typ):
            if val is not None:
                s.default_value = val
            return s
    raise KeyError(name)


def outp(n, name, typ=None):
    if name in ALIAS and not any(s.name == name for s in n.outputs):
        name = ALIAS[name]
    for s in n.outputs:
        if s.name == name and (typ is None or s.type == typ):
            return s
    raise KeyError(name)


def link(nt, a, b):
    nt.links.new(a, b)


def principled(name, color=(0.8, 0.8, 0.8, 1), rough=0.6, metal=0.0, sheen=0.0, sheen_rough=0.5, coat=0.0, spec=0.5,
               emis=None, emis_str=0.0, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    for k, v in (('Base Color', color), ('Roughness', rough), ('Metallic', metal), ('Sheen Weight', sheen),
                 ('Sheen Roughness', sheen_rough), ('Coat Weight', coat), ('Specular IOR Level', spec)):
        if k in b.inputs:
            b.inputs[k].default_value = v
    if transmission:
        b.inputs['Transmission Weight'].default_value = transmission
        b.inputs['IOR'].default_value = ior
    if emis is not None:
        b.inputs['Emission Color'].default_value = emis
        b.inputs['Emission Strength'].default_value = emis_str
    m.diffuse_color = color
    return m, nt, b


def objcoord(nt):
    tc = node(nt, 'ShaderNodeTexCoord')
    return outp(tc, 'Object')


def mapped(nt, src, rot_z=0.0, scale=(1, 1, 1)):
    mp = node(nt, 'ShaderNodeMapping')
    inp(mp, 'Rotation', (0, 0, rot_z))
    inp(mp, 'Scale', scale)
    link(nt, src, inp(mp, 'Vector'))
    return outp(mp, 'Vector')


def noise_bump(nt, b, scale=200.0, strength=0.08, src=None):
    nz = node(nt, 'ShaderNodeTexNoise')
    inp(nz, 'Scale', scale); inp(nz, 'Detail', 4.0)
    if src is not None:
        link(nt, src, inp(nz, 'Vector'))
    bump = node(nt, 'ShaderNodeBump')
    inp(bump, 'Strength', strength); inp(bump, 'Distance', 0.002)
    link(nt, outp(nz, 'Fac'), inp(bump, 'Height'))
    link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
    return bump


def tint_noise(nt, b, hexc, amount=0.06, scale=6.0):
    nz = node(nt, 'ShaderNodeTexNoise')
    inp(nz, 'Scale', scale); inp(nz, 'Detail', 3.0)
    ramp = node(nt, 'ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = rgb(hexc, 1 - amount)
    ramp.color_ramp.elements[1].color = rgb(hexc, 1 + amount)
    link(nt, outp(nz, 'Fac'), inp(ramp, 'Fac'))
    link(nt, outp(ramp, 'Color'), inp(b, 'Base Color'))


class Mats:
    def __init__(self, v, ex, st):
        self.v, self.ex, self.st = v, ex, st
        self.cache = {}

    def get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    # --- базовые
    def paint(self, hexc, rough=0.88, key=None):
        def f():
            m, nt, b = principled('paint ' + hexc, rgb(hexc), rough=rough, spec=0.25)
            noise_bump(nt, b, scale=120, strength=0.02)
            return m
        return self.get(key or ('paint', hexc), f)

    def wood(self, hexc, planks=None, rot=0.0, rough=0.48, key=None):
        def f():
            m, nt, b = principled('wood ' + hexc, rgb(hexc), rough=rough, spec=0.4)
            src = mapped(nt, objcoord(nt), rot_z=rot)
            # волокна: шум, растянутый вдоль X
            gsrc = mapped(nt, src, scale=(1.2, 26.0, 26.0))
            wave = node(nt, 'ShaderNodeTexNoise')
            inp(wave, 'Scale', 1.0); inp(wave, 'Detail', 6.0); inp(wave, 'Roughness', 0.55); inp(wave, 'Distortion', 0.6)
            link(nt, gsrc, inp(wave, 'Vector'))
            if planks:
                gr = node(nt, 'ShaderNodeValToRGB')
                gr.color_ramp.elements[0].position = 0.3
                gr.color_ramp.elements[1].position = 0.75
                gr.color_ramp.elements[0].color = (0.8, 0.8, 0.8, 1)
                gr.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
                link(nt, outp(wave, 'Fac'), inp(gr, 'Fac'))
                br = node(nt, 'ShaderNodeTexBrick', offset=0.5, offset_frequency=2, squash=1.0, squash_frequency=2)
                inp(br, 'Color1', rgb(hexc, 1.06)); inp(br, 'Color2', rgb(hexc, 0.86)); inp(br, 'Mortar', rgb(hexc, 0.42))
                inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.0025); inp(br, 'Mortar Smooth', 0.2)
                inp(br, 'Bias', 0.0); inp(br, 'Brick Width', planks[0]); inp(br, 'Row Height', planks[1])
                link(nt, src, inp(br, 'Vector'))
                mix = node(nt, 'ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
                inp(mix, 'Factor', 0.8, 'VALUE')
                link(nt, outp(br, 'Color'), inp(mix, 'A', None, 'RGBA'))
                link(nt, outp(gr, 'Color'), inp(mix, 'B', None, 'RGBA'))
                link(nt, outp(mix, 'Result', 'RGBA'), inp(b, 'Base Color'))
                bump = node(nt, 'ShaderNodeBump', invert=True)
                inp(bump, 'Strength', 0.4); inp(bump, 'Distance', 0.002)
                link(nt, outp(br, 'Fac'), inp(bump, 'Height'))
                link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
            else:
                gr = node(nt, 'ShaderNodeValToRGB')
                gr.color_ramp.elements[0].position = 0.3
                gr.color_ramp.elements[1].position = 0.75
                gr.color_ramp.elements[0].color = rgb(hexc, 0.84)
                gr.color_ramp.elements[1].color = rgb(hexc, 1.06)
                link(nt, outp(wave, 'Fac'), inp(gr, 'Fac'))
                link(nt, outp(gr, 'Color'), inp(b, 'Base Color'))
            return m
        return self.get(key or ('wood', hexc, bool(planks), rot), f)

    def tiles(self, hexc, size=0.6, grout=None, rough=0.28, key=None):
        def f():
            m, nt, b = principled('tile ' + hexc, rgb(hexc), rough=rough, spec=0.5)
            br = node(nt, 'ShaderNodeTexBrick', offset=0.0)
            inp(br, 'Color1', rgb(hexc, 1.02)); inp(br, 'Color2', rgb(hexc, 0.95)); inp(br, 'Mortar', rgb(grout or hexc, 0.8 if grout else 0.82))
            inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.003); inp(br, 'Brick Width', size); inp(br, 'Row Height', size)
            link(nt, objcoord(nt), inp(br, 'Vector'))
            link(nt, outp(br, 'Color'), inp(b, 'Base Color'))
            bump = node(nt, 'ShaderNodeBump', invert=True)
            inp(bump, 'Strength', 0.3); inp(bump, 'Distance', 0.001)
            link(nt, outp(br, 'Fac'), inp(bump, 'Height'))
            link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
            return m
        return self.get(key or ('tiles', hexc, size), f)

    def wall_tiles(self, hexc, axis):
        def f():
            m, nt, b = principled('wall tile ' + hexc + axis, rgb(hexc), rough=0.18, spec=0.6)
            sep = node(nt, 'ShaderNodeSeparateXYZ'); link(nt, objcoord(nt), inp(sep, 'Vector'))
            cmb = node(nt, 'ShaderNodeCombineXYZ')
            link(nt, outp(sep, 'X' if axis == 'x' else 'Y'), inp(cmb, 'X')); link(nt, outp(sep, 'Z'), inp(cmb, 'Y'))
            br = node(nt, 'ShaderNodeTexBrick', offset=0.0)
            inp(br, 'Color1', rgb(hexc, 1.02)); inp(br, 'Color2', rgb(hexc, 0.97)); inp(br, 'Mortar', rgb(hexc, 0.78))
            inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.002); inp(br, 'Brick Width', 0.6); inp(br, 'Row Height', 0.3)
            link(nt, outp(cmb, 'Vector'), inp(br, 'Vector'))
            link(nt, outp(br, 'Color'), inp(b, 'Base Color'))
            bump = node(nt, 'ShaderNodeBump', invert=True); inp(bump, 'Strength', 0.25); inp(bump, 'Distance', 0.001)
            link(nt, outp(br, 'Fac'), inp(bump, 'Height')); link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
            return m
        return self.get(('wtiles', hexc, axis), f)

    def brick(self, hexc, axis):
        def f():
            m, nt, b = principled('brick ' + hexc + axis, rgb(hexc), rough=0.85, spec=0.2)
            sep = node(nt, 'ShaderNodeSeparateXYZ'); link(nt, objcoord(nt), inp(sep, 'Vector'))
            cmb = node(nt, 'ShaderNodeCombineXYZ')
            link(nt, outp(sep, 'X' if axis == 'x' else 'Y'), inp(cmb, 'X')); link(nt, outp(sep, 'Z'), inp(cmb, 'Y'))
            br = node(nt, 'ShaderNodeTexBrick', offset=0.5)
            inp(br, 'Color1', rgb(hexc, 1.08)); inp(br, 'Color2', rgb(hexc, 0.78)); inp(br, 'Mortar', rgb('#D9D4CC', 0.9))
            inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.011); inp(br, 'Mortar Smooth', 0.3); inp(br, 'Bias', 0.1)
            inp(br, 'Brick Width', 0.25); inp(br, 'Row Height', 0.075)
            link(nt, outp(cmb, 'Vector'), inp(br, 'Vector'))
            nz = node(nt, 'ShaderNodeTexNoise'); inp(nz, 'Scale', 18.0); inp(nz, 'Detail', 6.0)
            link(nt, outp(cmb, 'Vector'), inp(nz, 'Vector'))
            mix = node(nt, 'ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
            inp(mix, 'Factor', 0.35, 'VALUE')
            link(nt, outp(br, 'Color'), inp(mix, 'A', None, 'RGBA')); link(nt, outp(nz, 'Color'), inp(mix, 'B', None, 'RGBA'))
            link(nt, outp(mix, 'Result', 'RGBA'), inp(b, 'Base Color'))
            add = node(nt, 'ShaderNodeMath', operation='ADD')
            link(nt, outp(br, 'Fac'), add.inputs[0]); inp_val = add.inputs[1]; inp_val.default_value = 0.0
            bump = node(nt, 'ShaderNodeBump', invert=True); inp(bump, 'Strength', 0.7); inp(bump, 'Distance', 0.006)
            link(nt, outp(add, 'Value'), inp(bump, 'Height')); link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
            return m
        return self.get(('brick', hexc, axis), f)

    def concrete(self, hexc):
        def f():
            m, nt, b = principled('concrete ' + hexc, rgb(hexc), rough=0.55, spec=0.35)
            nz = node(nt, 'ShaderNodeTexNoise'); inp(nz, 'Scale', 2.2); inp(nz, 'Detail', 8.0); inp(nz, 'Roughness', 0.65)
            ramp = node(nt, 'ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color = rgb(hexc, 0.82); ramp.color_ramp.elements[1].color = rgb(hexc, 1.1)
            link(nt, outp(nz, 'Fac'), inp(ramp, 'Fac')); link(nt, outp(ramp, 'Color'), inp(b, 'Base Color'))
            noise_bump(nt, b, scale=60, strength=0.05)
            return m
        return self.get(('concrete', hexc), f)

    def fabric(self, hexc, kind=None):
        kind = kind or self.ex['uph']
        def f():
            if kind == 'velvet':
                m, nt, b = principled('velvet ' + hexc, rgb(hexc), rough=0.8, sheen=1.0, sheen_rough=0.35, spec=0.3)
                tint_noise(nt, b, hexc, 0.05, 5.0)
            elif kind == 'leather':
                m, nt, b = principled('leather ' + hexc, rgb(hexc), rough=0.42, coat=0.12, spec=0.5)
                tint_noise(nt, b, hexc, 0.12, 4.0)
                noise_bump(nt, b, scale=90, strength=0.12)
            elif kind == 'linen':
                m, nt, b = principled('linen ' + hexc, rgb(hexc), rough=0.95, sheen=0.25, spec=0.3)
                tint_noise(nt, b, hexc, 0.04, 9.0)
                noise_bump(nt, b, scale=420, strength=0.12)
            elif kind == 'wool':
                m, nt, b = principled('wool ' + hexc, rgb(hexc), rough=0.95, sheen=0.55, sheen_rough=0.6, spec=0.3)
                tint_noise(nt, b, hexc, 0.05, 7.0)
                noise_bump(nt, b, scale=260, strength=0.15)
            else:
                m, nt, b = principled('fabric ' + hexc, rgb(hexc), rough=0.92, sheen=0.35, spec=0.3)
                tint_noise(nt, b, hexc, 0.04, 7.0)
                noise_bump(nt, b, scale=300, strength=0.1)
            return m
        return self.get(('fabric', hexc, kind), f)

    def metal(self, hexc, rough=0.32):
        return self.get(('metal', hexc, rough), lambda: principled('metal ' + hexc, rgb(hexc), rough=rough, metal=1.0)[0])

    def plastic(self, hexc, rough=0.35):
        return self.get(('plastic', hexc, rough), lambda: principled('plastic ' + hexc, rgb(hexc), rough=rough, spec=0.5)[0])

    def mirror(self):
        return self.get('mirror', lambda: principled('mirror', (0.9, 0.9, 0.9, 1), rough=0.02, metal=1.0)[0])

    def screen(self):
        return self.get('screen', lambda: principled('screen', (0.008, 0.008, 0.01, 1), rough=0.12, spec=0.6)[0])

    def emit(self, hexc, strength):
        def f():
            m = bpy.data.materials.new('emit ' + hexc)
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                if n.type != 'OUTPUT_MATERIAL':
                    nt.nodes.remove(n)
            o = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
            e = node(nt, 'ShaderNodeEmission')
            inp(e, 'Color', rgb(hexc)); inp(e, 'Strength', strength)
            link(nt, outp(e, 'Emission'), o.inputs['Surface'])
            return m
        return self.get(('emit', hexc, strength), f)

    def glow_shade(self, hexc, strength):
        return self.get(('glow', hexc, strength), lambda: principled('shade ' + hexc, rgb(hexc), rough=0.9, emis=rgb('#FFE2B8'), emis_str=strength)[0])

    def glass(self, reflect=0.12):
        def f():
            m = bpy.data.materials.new('glass')
            m.use_nodes = True
            nt = m.node_tree
            for n in list(nt.nodes):
                if n.type != 'OUTPUT_MATERIAL':
                    nt.nodes.remove(n)
            o = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
            lp = node(nt, 'ShaderNodeLightPath')
            tr = node(nt, 'ShaderNodeBsdfTransparent')
            gl = node(nt, 'ShaderNodeBsdfGlossy'); inp(gl, 'Roughness', 0.03)
            fr = node(nt, 'ShaderNodeFresnel'); inp(fr, 'IOR', 1.5)
            mr = node(nt, 'ShaderNodeMixShader')
            link(nt, outp(fr, 'Fac'), mr.inputs[0]); link(nt, outp(tr, 'BSDF'), mr.inputs[1]); link(nt, outp(gl, 'BSDF'), mr.inputs[2])
            mx = node(nt, 'ShaderNodeMixShader')
            link(nt, outp(lp, 'Is Camera Ray'), mx.inputs[0]); link(nt, outp(tr, 'BSDF'), mx.inputs[1]); link(nt, outp(mr, 'Shader'), mx.inputs[2])
            link(nt, outp(mx, 'Shader'), o.inputs['Surface'])
            m.diffuse_color = (0.7, 0.8, 0.85, 0.3)
            return m
        return self.get(('glass', reflect), f)

    def siding(self, hexc):
        def f():
            m, nt, b = principled('siding ' + hexc, rgb(hexc), rough=0.6, spec=0.4)
            sep = node(nt, 'ShaderNodeSeparateXYZ'); link(nt, objcoord(nt), inp(sep, 'Vector'))
            add = node(nt, 'ShaderNodeMath', operation='ADD')
            link(nt, outp(sep, 'X'), add.inputs[0]); link(nt, outp(sep, 'Y'), add.inputs[1])
            cmb = node(nt, 'ShaderNodeCombineXYZ'); link(nt, outp(add, 'Value'), inp(cmb, 'X')); link(nt, outp(sep, 'Z'), inp(cmb, 'Y'))
            br = node(nt, 'ShaderNodeTexBrick', offset=0.0)
            inp(br, 'Color1', rgb(hexc, 1.0)); inp(br, 'Color2', rgb(hexc, 0.97)); inp(br, 'Mortar', rgb(hexc, 0.55))
            inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.006); inp(br, 'Brick Width', 40.0); inp(br, 'Row Height', 0.2)
            link(nt, outp(cmb, 'Vector'), inp(br, 'Vector'))
            link(nt, outp(br, 'Color'), inp(b, 'Base Color'))
            bump = node(nt, 'ShaderNodeBump', invert=True); inp(bump, 'Strength', 0.5); inp(bump, 'Distance', 0.006)
            link(nt, outp(br, 'Fac'), inp(bump, 'Height')); link(nt, outp(bump, 'Normal'), inp(b, 'Normal'))
            return m
        return self.get(('siding', hexc), f)

    def grass(self):
        def f():
            m, nt, b = principled('grass', rgb('#6E8A4A'), rough=0.95, spec=0.2)
            nz = node(nt, 'ShaderNodeTexNoise'); inp(nz, 'Scale', 0.6); inp(nz, 'Detail', 6.0)
            ramp = node(nt, 'ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color = rgb('#5A7A3A'); ramp.color_ramp.elements[1].color = rgb('#9AA766')
            link(nt, outp(nz, 'Fac'), inp(ramp, 'Fac')); link(nt, outp(ramp, 'Color'), inp(b, 'Base Color'))
            noise_bump(nt, b, scale=40, strength=0.3)
            return m
        return self.get('grass', f)

    def art(self, colors, kind):
        def f():
            m, nt, b = principled('art ' + kind, rgb(colors[0]), rough=0.75, spec=0.3)
            if kind == 'geometric':
                tex = node(nt, 'ShaderNodeTexChecker'); inp(tex, 'Scale', 3.0)
                inp(tex, 'Color1', rgb(colors[0])); inp(tex, 'Color2', rgb(colors[1]))
                link(nt, outp(tex, 'Color'), inp(b, 'Base Color'))
                return m
            tex = node(nt, 'ShaderNodeTexNoise'); inp(tex, 'Scale', 1.4 if kind != 'minimal' else 0.7); inp(tex, 'Detail', 2.0); inp(tex, 'Distortion', 2.5 if kind != 'minimal' else 0.5)
            ramp = node(nt, 'ShaderNodeValToRGB')
            cr = ramp.color_ramp
            cr.elements[0].position = 0.3; cr.elements[0].color = rgb(colors[0])
            cr.elements[1].position = 0.7; cr.elements[1].color = rgb(colors[1])
            e = cr.elements.new(0.5); e.color = rgb(colors[2])
            if kind in ('poster', 'minimal'):
                cr.interpolation = 'CONSTANT'
            link(nt, outp(tex, 'Fac'), inp(ramp, 'Fac')); link(nt, outp(ramp, 'Color'), inp(b, 'Base Color'))
            return m
        return self.get(('art', kind, tuple(colors)), f)

    def rug(self, hexc, hexc2, kind):
        def f():
            m, nt, b = principled('rug ' + kind, rgb(hexc), rough=0.98, sheen=0.4, spec=0.2)
            if kind == 'geometric':
                tex = node(nt, 'ShaderNodeTexChecker'); inp(tex, 'Scale', 4.0)
                inp(tex, 'Color1', rgb(hexc)); inp(tex, 'Color2', rgb(hexc2))
                link(nt, outp(tex, 'Color'), inp(b, 'Base Color'))
            elif kind == 'ornate':
                vo = node(nt, 'ShaderNodeTexVoronoi'); inp(vo, 'Scale', 7.0)
                ramp = node(nt, 'ShaderNodeValToRGB')
                ramp.color_ramp.elements[0].color = rgb(hexc2, 0.7); ramp.color_ramp.elements[1].color = rgb(hexc, 1.0)
                link(nt, outp(vo, 'Distance'), inp(ramp, 'Fac')); link(nt, outp(ramp, 'Color'), inp(b, 'Base Color'))
            elif kind == 'jute':
                br = node(nt, 'ShaderNodeTexBrick', offset=0.5)
                inp(br, 'Color1', rgb(hexc, 1.05)); inp(br, 'Color2', rgb(hexc, 0.9)); inp(br, 'Mortar', rgb(hexc, 0.7))
                inp(br, 'Scale', 1.0); inp(br, 'Mortar Size', 0.004); inp(br, 'Brick Width', 0.03); inp(br, 'Row Height', 0.015)
                link(nt, objcoord(nt), inp(br, 'Vector'))
                link(nt, outp(br, 'Color'), inp(b, 'Base Color'))
            else:
                tint_noise(nt, b, hexc, 0.12 if kind == 'worn' else 0.05, 3.0 if kind == 'worn' else 8.0)
            noise_bump(nt, b, scale=500, strength=0.2)
            return m
        return self.get(('rug', hexc, hexc2, kind), f)


# ---------------------------------------------------------------- геометрия
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
# индексы граней: 0 низ, 1 верх, 2 -Y (юг плана), 3 +X (восток), 4 +Y (север), 5 -X (запад)


class B:
    coll = None


def new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def finish(ob, mats, bevel, seg, smooth, coll):
    for m in mats:
        ob.data.materials.append(m)
    (coll or B.coll).objects.link(ob)
    if bevel and bevel > 0:
        mod = ob.modifiers.new('bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = seg
        mod.limit_method = 'ANGLE'
        try:
            mod.harden_normals = not smooth
        except Exception:
            pass
    if smooth:
        ob.data.shade_smooth()
    return ob


def cube(name, cx, cy, cz, sx, sy, sz, mats, bevel=0.0, seg=2, smooth=False, face_mats=None, coll=None):
    hx, hy, hz = max(sx, 1e-4) / 2, max(sy, 1e-4) / 2, max(sz, 1e-4) / 2
    verts = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], CUBE_F)
    me.update()
    if face_mats:
        for i, mi in enumerate(face_mats):
            me.polygons[i].material_index = mi
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, cy, cz)
    if bevel:
        bevel = min(bevel, 0.45 * min(sx, sy, sz))
    return finish(ob, mats if isinstance(mats, (list, tuple)) else [mats], bevel, seg, smooth, coll)


def pbox(x, y, w, d, h, z0, mat, bevel=0.0, seg=2, smooth=False, face_mats=None, name='box', coll=None):
    """Коробка в координатах плана: левый верхний угол (x, y), ширина w по x, глубина d по y."""
    return cube(name, x + w / 2, -(y + d / 2), z0 + h / 2, w, d, h, mat, bevel, seg, smooth, face_mats, coll)


def cyl(cx, cy, z0, r, h, mat, seg=28, r2=None, smooth=True, name='cyl', coll=None, bevel=0.0):
    """Цилиндр по координатам плана, центр (cx, cy)."""
    r2 = r if r2 is None else r2
    verts, faces = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts.append((r * math.cos(a), r * math.sin(a), 0))
    for i in range(seg):
        a = 2 * math.pi * i / seg
        verts.append((r2 * math.cos(a), r2 * math.sin(a), h))
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((i, j, seg + j, seg + i))
    faces.append(tuple(reversed(range(seg))))
    faces.append(tuple(range(seg, 2 * seg)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = smooth and len(p.vertices) == 4
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cy, z0)
    return finish(ob, [mat], bevel, 2, False, coll)


def sphere(cx, cy, cz, r, mat, scale=(1, 1, 1), seg=24, name='sph', coll=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(8, seg // 2), radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cy, cz)
    ob.scale = scale
    if rot is not None:
        ob.rotation_euler = rot
    return finish(ob, [mat], 0, 2, False, coll)


def torus(cx, cy, cz, R, r, mat, seg=48, seg2=10, name='torus', coll=None):
    verts, faces = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(seg2):
            b = 2 * math.pi * j / seg2
            verts.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(seg2):
            i2, j2 = (i + 1) % seg, (j + 1) % seg2
            faces.append((i * seg2 + j, i2 * seg2 + j, i2 * seg2 + j2, i * seg2 + j2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    ob.location = (cx, -cy, cz)
    return finish(ob, [mat], 0, 2, False, coll)


def beam(p0, p1, tx, ty, mat, name='beam', coll=None, bevel=0.0):
    """Брусок между точками плана p = (x, y, z)."""
    a = Vector((p0[0], -p0[1], p0[2]))
    b = Vector((p1[0], -p1[1], p1[2]))
    v = b - a
    mid = (a + b) / 2
    ob = cube(name, mid.x, mid.y, mid.z, tx, ty, v.length, [mat], bevel=bevel, coll=coll)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = v.to_track_quat('Z', 'Y')
    return ob


def curtain(p_left, tangent, normal, width, z0, z1, mat, coll=None):
    """Складчатая штора: p_left (x, y) плана, tangent и normal - единичные векторы плана."""
    n = max(8, int(width / 0.025))
    verts, faces = [], []
    for i in range(n + 1):
        u = width * i / n
        off = 0.035 * math.sin(2 * math.pi * u / 0.13)
        x = p_left[0] + tangent[0] * u + normal[0] * off
        y = p_left[1] + tangent[1] * u + normal[1] * off
        verts.append((x, -y, z0))
        verts.append((x, -y, z1))
    for i in range(n):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    me = bpy.data.meshes.new('curtain')
    me.from_pydata(verts, [], faces)
    me.update()
    me.shade_smooth()
    ob = bpy.data.objects.new('curtain', me)
    finish(ob, [mat], 0, 2, False, coll)
    so = ob.modifiers.new('solid', 'SOLIDIFY')
    so.thickness = 0.004
    return ob


# ---------------------------------------------------------------- помощники плана
def room_rect(rid):
    p = ROOMS[rid]['poly']
    xs = [q[0] for q in p]; ys = [q[1] for q in p]
    return min(xs), min(ys), max(xs), max(ys)


def in_room(x, y, rooms=None):
    for rid, r in ROOMS.items():
        if rooms and rid not in rooms:
            continue
        x0, y0, x1, y1 = room_rect(rid)
        if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
            return rid
    return None


def wall_segments(wl):
    start = wl['x'] if wl['dir'] == 'h' else wl['y']
    end = start + wl['len']
    ops = sorted(wl.get('op', []), key=lambda o: o['at'])
    segs, c = [], start
    for o in ops:
        if o['at'] > c:
            segs.append((c, o['at']))
        c = o['at'] + o['w']
    if c < end:
        segs.append((c, end))
    return segs


def floor_openings(axis, coord, lo, hi):
    """Проёмы до пола на линии: axis 'h' - линия y=coord, 'v' - x=coord. Возвращает интервалы."""
    res = []
    for wl in WALLS:
        if wl['dir'] != axis:
            continue
        c = wl['y'] if axis == 'h' else wl['x']
        if abs(c - coord) > wl['t'] / 2 + 0.08:
            continue
        for o in wl.get('op', []):
            if o['sill'] < 0.05:
                a, b = o['at'], o['at'] + o['w']
                if b > lo and a < hi:
                    res.append((max(a, lo), min(b, hi)))
    return res


def subtract(lo, hi, holes):
    segs = [(lo, hi)]
    for a, b in holes:
        nxt = []
        for s0, s1 in segs:
            if b <= s0 or a >= s1:
                nxt.append((s0, s1))
            else:
                if a > s0:
                    nxt.append((s0, a))
                if b < s1:
                    nxt.append((b, s1))
        segs = nxt
    return [(a, b) for a, b in segs if b - a > 0.02]


def perimeter(rid, z0, h, thick, mat, skip_openings=True, coll=None, sides='nswe'):
    x0, y0, x1, y1 = room_rect(rid)
    out = []
    for side in sides:
        if side in 'ns':
            yy = y0 if side == 'n' else y1
            holes = floor_openings('h', yy, x0, x1) if skip_openings else []
            for a, b in subtract(x0, x1, holes):
                out.append(pbox(a, yy if side == 'n' else yy - thick, b - a, thick, h, z0, mat, name='trim', coll=coll))
        else:
            xx = x0 if side == 'w' else x1
            holes = floor_openings('v', xx, y0, y1) if skip_openings else []
            for a, b in subtract(y0, y1, holes):
                out.append(pbox(xx if side == 'w' else xx - thick, a, thick, b - a, h, z0, mat, name='trim', coll=coll))
    return out


def rects_overlap(a, b, pad=0.0):
    return not (a[0] + a[2] + pad <= b[0] or b[0] + b[2] + pad <= a[0] or a[1] + a[3] + pad <= b[1] or b[1] + b[3] + pad <= a[1])


# ---------------------------------------------------------------- сборка
class House:
    def __init__(self, layout_idx, style_id, variant):
        self.L = DATA['LAYOUTS'][layout_idx]
        self.st = STYLES[style_id]
        self.v = self.st['variants'][variant]
        self.ex = EXTRA[style_id]
        self.M = Mats(self.v, self.ex, self.st)
        self.furn = self.L['furn']
        self.rnd = random.Random(7)
        self.door_rects = []
        sc = bpy.context.scene
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        self.c_house = new_coll('house')
        self.c_ceiling = new_coll('ceiling')
        self.c_furn = new_coll('furniture')
        self.c_ext = new_coll('exterior')
        self.c_grass = new_coll('ground_grass')
        self.c_paper = new_coll('ground_paper')
        self.c_fill = new_coll('fill_lights')
        self.c_cams = new_coll('cameras')
        B.coll = self.c_house

    # --- материалы стиля
    def m_wood(self):
        return self.M.wood(self.v['wood'])

    def m_trim(self):
        t = self.ex['trim']
        return self.M.wood(self.v['wood']) if t == 'wood' else self.M.paint(t, rough=0.5, key=('trim', t))

    def m_door(self):
        d = self.ex['door']
        return self.M.wood(self.v['wood']) if d == 'wood' else self.M.paint(d, rough=0.45, key=('door', d))

    def m_legs(self):
        lg = self.ex['legs']
        if lg == 'metal':
            return self.M.metal(self.v['metal'], 0.45)
        if lg == 'turned' and self.ex.get('gold'):
            return self.M.metal(self.v['metal'], 0.3)
        return self.M.wood(self.v['wood'])

    def m_frame_color(self):
        fr = self.ex['frame']
        if fr == 'wood':
            return self.M.wood(self.v['wood'])
        if fr == 'gold':
            return self.M.metal(self.v['metal'], 0.28)
        return self.M.plastic(fr, 0.4)

    def floor_mat(self, rid):
        r = ROOMS[rid]
        if r['floor'] == 'stone':
            return self.M.tiles(self.v['stone'], 0.6 if rid != 'bath' else 0.3)
        if r['floor'] == 'deck':
            return self.M.wood('#B08A5E' if self.st['id'] != 'graphite' else '#8E8A84', planks=(2.4, 0.14), rot=math.pi / 2, key='deck')
        if self.v.get('concrete'):
            return self.M.concrete(self.v['floor'])
        x0, y0, x1, y1 = room_rect(rid)
        rot = math.pi / 2 if (y1 - y0) > (x1 - x0) else 0.0
        return self.M.wood(self.v['floor'], planks=(1.25, 0.19), rot=rot)

    # --- корпус
    def build_shell(self):
        M, v = self.M, self.v
        B.coll = self.c_house
        for rid, r in ROOMS.items():
            x0, y0, x1, y1 = room_rect(rid)
            pbox(x0, y0, x1 - x0, y1 - y0, 0.03, -0.03, self.floor_mat(rid), name='floor ' + rid)
        # подложка под полом на стыках стен
        pbox(0, 0, 10.19, 8.17, 0.02, -0.05, M.paint('#3A3A3A', key='sub'), name='subfloor')
        wall_m = M.paint(v['wall'], key='wall')
        siding = M.siding('#A7ADB3')
        cap = M.paint('#2B2D31', rough=0.9, key='cap')
        out_face = {'n': 4, 's': 2, 'w': 5, 'e': 3}
        for wl in WALLS:
            t = wl['t']
            fm = [0, 2, 0, 0, 0, 0]
            if wl.get('out'):
                fm[out_face[wl['out']]] = 1
            mats = [wall_m, siding, cap]

            def piece(a, b, z0, hh):
                if b - a <= 0.001 or hh <= 0.001:
                    return
                if wl['dir'] == 'h':
                    pbox(a, wl['y'] - t / 2, b - a, t, hh, z0, mats, face_mats=fm, name='wall')
                else:
                    pbox(wl['x'] - t / 2, a, t, b - a, hh, z0, mats, face_mats=fm, name='wall')
            for a, b in wall_segments(wl):
                piece(a, b, 0, H)
            for o in wl.get('op', []):
                a, b = o['at'], o['at'] + o['w']
                if o['sill'] > 0:
                    piece(a, b, 0, o['sill'])
                piece(a, b, o['sill'] + o['h'], H - o['sill'] - o['h'])
                if o.get('glass'):
                    self.window(wl, o)
                elif o.get('door'):
                    self.door(wl, o)
        # цоколь и крыльцо
        plinth = M.paint('#24272C', rough=0.8, key='plinth')
        B.coll = self.c_ext
        pbox(0, 0, 10.19, 8.17, 0.75, -0.8, plinth, name='plinth')
        pbox(10.19, 0.25, 2.47, 7.68, 0.72, -0.8, plinth, name='plinth t')
        deck = self.floor_mat('terrace')
        pbox(4.0, 8.17, 2.2, 1.6, 0.04, -0.04, deck, name='porch')
        pbox(4.0, 8.17, 2.2, 1.6, 0.72, -0.8, plinth, name='porch base')
        for i, (yy, zz) in enumerate(((8.17, -0.29), (8.17, -0.54))):
            pbox(6.2 + i * 0.32, 8.17, 0.32, 1.6, 0.04, zz, deck, name='step')
            pbox(6.2 + i * 0.32, 8.17, 0.32, 1.6, zz + 0.8, -0.8, plinth, name='step base')
        for i, zz in enumerate((-0.29, -0.54)):
            pbox(10.3, 7.93 + i * 0.32, 1.1, 0.32, 0.04, zz, deck, name='tstep')
            pbox(10.3, 7.93 + i * 0.32, 1.1, 0.32, zz + 0.8, -0.8, plinth, name='tstep base')
        B.coll = self.c_house

    def window(self, wl, o):
        M = self.M
        B.coll = self.c_house
        frame = M.plastic('#2B2F36', 0.45)
        glass = M.glass()
        a, w, s, h, t = o['at'], o['w'], o['sill'], o['h'], wl['t']
        ft, fd = 0.06, 0.08
        if wl['dir'] == 'h':
            cy = wl['y'] - fd / 2
            pbox(a, cy, w, fd, ft, s, frame, name='frame')
            pbox(a, cy, w, fd, ft, s + h - ft, frame, name='frame')
            pbox(a, cy, ft, fd, h, s, frame, name='frame')
            pbox(a + w - ft, cy, ft, fd, h, s, frame, name='frame')
            if w > 1.15 and s > 0:
                pbox(a + w / 2 - 0.03, cy, 0.06, fd, h, s, frame, name='mullion')
            pbox(a + ft, wl['y'] - 0.005, w - 2 * ft, 0.01, h - 2 * ft, s + ft, glass, name='glass')
            if s > 0:
                inward = 1 if wl.get('out') == 'n' else -1
                face = wl['y'] + inward * t / 2
                yy = face if inward > 0 else face - 0.06
                pbox(a - 0.05, yy, w + 0.1, 0.06, 0.03, s - 0.03, self.m_trim(), bevel=0.004, name='sill')
        else:
            cx = wl['x'] - fd / 2
            pbox(cx, a, fd, w, ft, s, frame, name='frame')
            pbox(cx, a, fd, w, ft, s + h - ft, frame, name='frame')
            pbox(cx, a, fd, ft, h, s, frame, name='frame')
            pbox(cx, a + w - ft, fd, ft, h, s, frame, name='frame')
            if w > 1.15 and s > 0:
                pbox(cx, a + w / 2 - 0.03, fd, 0.06, h, s, frame, name='mullion')
            if s == 0 and w > 1.15:
                pbox(cx, a + w / 2 - 0.03, fd, 0.06, h, s, frame, name='mullion')
            pbox(wl['x'] - 0.005, a + ft, 0.01, w - 2 * ft, h - 2 * ft, s + ft, glass, name='glass')
            if o.get('door'):
                hx = wl['x'] - t / 2 - 0.03
                pbox(hx, a + w - ft - 0.04, 0.03, 0.02, 0.3, 1.0, M.metal(self.v['metal'], 0.3), name='handle')

    def door(self, wl, o):
        M = self.M
        B.coll = self.c_house
        a, w, t = o['at'], o['w'], wl['t']
        leaf = self.m_door()
        handle = M.metal(self.v['metal'] if self.st['id'] not in ('nord',) else '#1E1F22', 0.3)
        trim = self.m_trim()
        dh = o['h'] - 0.02
        if wl['dir'] == 'v':
            inward = -1 if wl['x'] < 5 else 1
            face = wl['x'] + inward * t / 2
            x0 = face if inward > 0 else face - w
            pbox(x0, a + 0.01, w, 0.04, dh, 0.01, leaf, bevel=0.004, name='door leaf')
            self.door_rects.append((x0, a, w, w))
            hx = face + inward * (w - 0.08)
            pbox(hx - 0.06, a + 0.05, 0.12, 0.02, 0.02, 1.0, handle, name='handle')
            for side in (-1, 1):
                fx = wl['x'] + side * (t / 2 + 0.005) - 0.005
                pbox(fx, a - 0.07, 0.01, 0.07, o['h'] + 0.07, 0, trim, name='casing')
                pbox(fx, a + w, 0.01, 0.07, o['h'] + 0.07, 0, trim, name='casing')
                pbox(fx, a - 0.07, 0.01, w + 0.14, 0.07, o['h'], trim, name='casing')
        else:
            up = -1 if wl['y'] > 7 else (1 if wl['y'] > 6 else -1)
            face = wl['y'] + up * t / 2
            y0 = face if up > 0 else face - w
            pbox(a + 0.01, y0, 0.04, w, dh, 0.01, leaf, bevel=0.004, name='door leaf')
            self.door_rects.append((a, y0, w, w))
            hy = face + up * (w - 0.08)
            pbox(a + 0.05, hy - 0.06, 0.02, 0.12, 0.02, 1.0, handle, name='handle')
            if wl.get('out'):
                return
            for side in (-1, 1):
                fy = wl['y'] + side * (t / 2 + 0.005) - 0.005
                pbox(a - 0.07, fy, 0.07, 0.01, o['h'] + 0.07, 0, trim, name='casing')
                pbox(a + w, fy, 0.07, 0.01, o['h'] + 0.07, 0, trim, name='casing')
                pbox(a - 0.07, fy, w + 0.14, 0.01, 0.07, o['h'], trim, name='casing')

    def build_ceiling(self):
        M = self.M
        B.coll = self.c_ceiling
        pbox(0, 0, 10.19, 8.17, 0.12, H, M.paint('#F7F6F3', rough=0.95, key='ceiling'), name='ceiling')
        under = M.wood('#C9A275', planks=(3.0, 0.12), rot=math.pi / 2, key='soffit')
        top = M.paint('#2B2F36', key='roof')
        pbox(10.05, 0.05, 2.75, 8.1, 0.12, H, [top, under], face_mats=[1, 0, 0, 0, 0, 0], name='terrace roof')
        if self.ex['moldings']:
            for rid in ('kh', 'bed2', 'bed3', 'cor', 'hallway'):
                perimeter(rid, H - 0.1, 0.1, 0.05, self.m_trim(), skip_openings=False, coll=self.c_ceiling)
                perimeter(rid, H - 0.13, 0.03, 0.025, self.m_trim(), skip_openings=False, coll=self.c_ceiling)
                if self.ex.get('gold'):
                    perimeter(rid, H - 0.115, 0.01, 0.052, M.metal(self.v['metal'], 0.3), skip_openings=False, coll=self.c_ceiling)
        B.coll = self.c_house

    def build_trim(self):
        M, v = self.M, self.v
        B.coll = self.c_house
        for rid in ('kh', 'bed2', 'bed3', 'cor', 'hallway'):
            perimeter(rid, 0, 0.08, 0.015, self.m_trim())
        # плитка в санузле
        x0, y0, x1, y1 = room_rect('bath')
        tm_x = M.wall_tiles(v['stone'], 'x'); tm_y = M.wall_tiles(v['stone'], 'y')
        for side in 'nswe':
            mat = tm_x if side in 'ns' else tm_y
            perimeter('bath', 0, 2.1, 0.008, mat, sides=side)
        # акцентные стены
        for a in self.L['accents']:
            x, y, w, d = a
            vert = w < d
            if self.st['id'] == 'loft' and not self.v.get('concrete', False) and self.v['name'].startswith('Белён'):
                mat = M.brick(v['accent'], 'y' if vert else 'x')
            elif self.st['id'] == 'loft':
                mat = M.brick(v['accent'], 'y' if vert else 'x')
            else:
                mat = M.paint(v['accent'], key='accent')
            thick = 0.03 if self.st['id'] == 'loft' else 0.012
            if vert:
                inward = 1 if in_room(x + 0.2, y + d / 2, ['kh', 'bed2', 'bed3', 'cor']) else -1
                xx = x if inward > 0 else x + w - thick
                pbox(xx, y, thick, d, H, 0, mat, name='accent')
                if self.ex['moldings']:
                    self.panels(xx + (thick if inward > 0 else 0), y, d, 'v', inward)
            else:
                inward = 1 if in_room(x + w / 2, y + 0.2, ['kh', 'bed2', 'bed3', 'cor']) else -1
                yy = y if inward > 0 else y + d - thick
                pbox(x, yy, w, thick, H, 0, mat, name='accent')
                if self.ex['moldings']:
                    self.panels(x, yy + (thick if inward > 0 else 0), w, 'h', inward)

    def panels(self, px0, py0, length, axis, inward):
        """Рамки-молдинги на акцентной стене. axis 'v': стена вдоль y на x=px0."""
        mat = self.M.metal(self.v['metal'], 0.3) if self.ex.get('gold') else self.m_trim()
        n = max(1, round(length / 1.1))
        gap, margin = 0.12, 0.15
        pw = (length - 2 * margin - (n - 1) * gap) / n
        tiers = [(0.3, 0.85), (1.05, 2.3)] if self.ex.get('gold') else [(0.35, 2.3)]
        sw, st = 0.03, 0.012
        for i in range(n):
            s0 = margin + i * (pw + gap)
            for z0, z1 in tiers:
                for (u0, u1, zz0, zz1) in ((s0, s0 + pw, z0, z0 + sw), (s0, s0 + pw, z1 - sw, z1), (s0, s0 + sw, z0, z1), (s0 + pw - sw, s0 + pw, z0, z1)):
                    if axis == 'v':
                        xx = px0 if inward > 0 else px0 - st
                        pbox(xx, py0 + u0, st, u1 - u0, zz1 - zz0, zz0, mat, name='panel')
                    else:
                        yy = py0 if inward > 0 else py0 - st
                        pbox(px0 + u0, yy, u1 - u0, st, zz1 - zz0, zz0, mat, name='panel')

    def build_terrace(self):
        M = self.M
        B.coll = self.c_house
        wood = M.wood('#B08A5E' if self.st['id'] != 'graphite' else '#8E8A84', key='rail')
        posts = [(12.54, 0.3), (12.54, 2.85), (12.54, 5.35), (12.54, 7.79), (10.25, 0.3), (10.25, 7.79), (11.44, 7.79)]
        for x, y in posts:
            pbox(x, y, 0.12, 0.12, 1.06, 0, wood, bevel=0.008, name='post')
            pbox(x, y, 0.12, 0.12, H - 1.06, 1.06, wood, bevel=0.008, name='post top', coll=self.c_ceiling)
        rx = 12.6
        bays_e = [(0.36, 2.85), (2.97, 5.35), (5.47, 7.79)]
        for a, b in bays_e:
            pbox(rx - 0.03, a, 0.06, b - a, 0.07, 0.98, wood, bevel=0.005, name='rail')
            pbox(rx - 0.03, a, 0.06, b - a, 0.06, 0.08, wood, bevel=0.005, name='rail')
            beam((rx, a + 0.03, 0.14), (rx, b - 0.03, 0.96), 0.04, 0.06, wood, name='brace')
            beam((rx, b - 0.03, 0.14), (rx, a + 0.03, 0.96), 0.04, 0.06, wood, name='brace')
        for a, b, ry in ((10.37, 12.54, 0.36), (11.56, 12.54, 7.85)):
            pbox(a, ry - 0.03, b - a, 0.06, 0.07, 0.98, wood, bevel=0.005, name='rail')
            pbox(a, ry - 0.03, b - a, 0.06, 0.06, 0.08, wood, bevel=0.005, name='rail')
            beam((a + 0.03, ry, 0.14), (b - 0.03, ry, 0.96), 0.06, 0.04, wood, name='brace')
            beam((b - 0.03, ry, 0.14), (a + 0.03, ry, 0.96), 0.06, 0.04, wood, name='brace')

    def build_exterior(self):
        M = self.M
        B.coll = self.c_grass
        pbox(-60, -60, 132, 128, 0.02, -0.82, M.grass(), name='grass')
        B.coll = self.c_paper
        pbox(-60, -60, 132, 128, 0.02, -0.82, M.paint('#E9E5DE', rough=1.0, key='paper'), name='paper')
        B.coll = self.c_ext
        pine = M.fabric('#2F4A2C', 'fabric')
        trunk = M.wood('#5A4030', key='trunk')
        rnd = random.Random(11)
        spots = [(-6, -4), (-9, 3), (-4, 12), (3, 15), (9, 14), (16, 12), (19, 4), (18, -5), (14, -9), (5, -11), (-3, -10), (24, 9), (-12, 9), (27, -2)]
        for x, y in spots:
            hgt = rnd.uniform(4.5, 8.0)
            cyl(x, y, -0.8, 0.12, hgt * 0.35, trunk, seg=10, name='trunk')
            for k in range(3):
                z = -0.8 + hgt * (0.25 + 0.22 * k)
                r = hgt * (0.26 - 0.06 * k)
                cyl(x, y, z, r, hgt * 0.38, pine, seg=14, r2=0.02, smooth=True, name='pine')
        hill = M.fabric('#5E7457', 'fabric')
        for x, y, sx, sy, sz in ((40, -120, 90, 40, 18), (-60, -110, 80, 40, 14), (120, -40, 50, 80, 16), (-40, 120, 90, 40, 12), (90, 110, 70, 40, 15)):
            sphere(x, y, -2, 1.0, hill, scale=(sx, sy, sz), seg=32, name='hill')
        B.coll = self.c_house

    # --- мебель: локальные рамки
    def lbox(self, f, back, u0, v0, z0, du, dv, h, mat, bevel=0.0, seg=2, smooth=False, L=None, D=None, name='part'):
        x, y, w, d = f['x'], f['y'], f['w'], f['d']
        if back == 'n':
            return pbox(x + u0, y + v0, du, dv, h, z0, mat, bevel, seg, smooth, name=name)
        if back == 's':
            return pbox(x + u0, y + d - v0 - dv, du, dv, h, z0, mat, bevel, seg, smooth, name=name)
        if back == 'w':
            return pbox(x + v0, y + u0, dv, du, h, z0, mat, bevel, seg, smooth, name=name)
        return pbox(x + w - v0 - dv, y + u0, dv, du, h, z0, mat, bevel, seg, smooth, name=name)

    def lpt(self, f, back, u, v):
        x, y, w, d = f['x'], f['y'], f['w'], f['d']
        if back == 'n':
            return x + u, y + v
        if back == 's':
            return x + u, y + d - v
        if back == 'w':
            return x + v, y + u
        return x + w - v, y + u

    def dims(self, f, back):
        return (f['w'], f['d']) if back in ('n', 's') else (f['d'], f['w'])

    def legs4(self, f, back, inset, size, h, style=None, z0=0.0):
        style = style or self.ex['legs']
        m = self.m_legs()
        L, D = self.dims(f, back)
        pts = [(inset, inset), (L - inset - size, inset), (inset, D - inset - size), (L - inset - size, D - inset - size)]
        for u, v in pts:
            if style in ('round', 'turned'):
                cx, cy = self.lpt(f, back, u + size / 2, v + size / 2)
                cyl(cx, cy, z0, size / 2, h, m, seg=16, r2=size * 0.38, name='leg')
                if style == 'turned':
                    sphere(cx, cy, z0 + h * 0.6, size * 0.65, m, seg=16, name='leg ball')
            elif style == 'tapered':
                cx, cy = self.lpt(f, back, u + size / 2, v + size / 2)
                ccx, ccy = self.lpt(f, back, L / 2, D / 2)
                dx, dy = (cx - ccx) * 0.12, (cy - ccy) * 0.12
                beam((cx - dx, cy - dy, z0 + h), (cx + dx * 0.4, cy + dy * 0.4, z0), size * 0.8, size * 0.8, m, name='leg')
            elif style == 'metal':
                self.lbox(f, back, u + size * 0.25, v + size * 0.25, z0, size * 0.5, size * 0.5, h, m, name='leg')
            else:
                self.lbox(f, back, u, v, z0, size, size, h, m, bevel=0.004, name='leg')

    # --- предметы
    def sofa(self, f):
        back = f.get('back', 'n')
        L, D = self.dims(f, back)
        up = self.M.fabric(self.v['textile'])
        pil = self.M.fabric(self.v['textile2'])
        a = 0.17
        self.legs4(f, back, 0.06, 0.05, 0.1, style='metal' if self.ex['legs'] == 'metal' else ('round' if self.ex['legs'] != 'square' else 'square'))
        self.lbox(f, back, 0, 0, 0.1, L, D, 0.2, up, bevel=0.02, seg=3, smooth=True, name='sofa base')
        self.lbox(f, back, 0, 0, 0.1, a, D, 0.5, up, bevel=0.05, seg=4, smooth=True, name='sofa arm')
        self.lbox(f, back, L - a, 0, 0.1, a, D, 0.5, up, bevel=0.05, seg=4, smooth=True, name='sofa arm')
        self.lbox(f, back, a, 0, 0.3, L - 2 * a, 0.2, 0.52, up, bevel=0.05, seg=4, smooth=True, name='sofa back')
        n = 3 if L - 2 * a > 1.75 else 2
        cw = (L - 2 * a) / n
        for i in range(n):
            self.lbox(f, back, a + i * cw + 0.005, 0.2, 0.3, cw - 0.01, D - 0.22, 0.15, up, bevel=0.06, seg=4, smooth=True, name='seat')
            self.lbox(f, back, a + i * cw + 0.008, 0.19, 0.45, cw - 0.016, 0.17, 0.42, up, bevel=0.07, seg=4, smooth=True, name='back cushion')
        self.lbox(f, back, a + 0.06, 0.34, 0.47, 0.44, 0.13, 0.42, pil, bevel=0.06, seg=4, smooth=True, name='pillow')
        self.lbox(f, back, L - a - 0.5, 0.34, 0.47, 0.44, 0.13, 0.42, pil, bevel=0.06, seg=4, smooth=True, name='pillow')
        if self.st['id'] in ('nord', 'japandi', 'greige'):
            self.lbox(f, back, L - a - 0.75, 0.2, 0.455, 0.42, D - 0.25, 0.02, pil, bevel=0.008, seg=2, smooth=True, name='throw')

    def bed(self, f):
        head = f.get('head', 'n')
        Lb, Wb = (f['w'], f['d']) if head in ('w', 'e') else (f['d'], f['w'])
        x, y, w, d = f['x'], f['y'], f['w'], f['d']

        def lb(u0, v0, z0, du, dv, h, mat, bevel=0.0, seg=2, smooth=False, name='bed'):
            # u поперёк кровати, v от изголовья к ногам
            if head == 'w':
                return pbox(x + v0, y + u0, dv, du, h, z0, mat, bevel, seg, smooth, name=name)
            if head == 's':
                return pbox(x + u0, y + d - v0 - dv, du, dv, h, z0, mat, bevel, seg, smooth, name=name)
            if head == 'e':
                return pbox(x + w - v0 - dv, y + u0, dv, du, h, z0, mat, bevel, seg, smooth, name=name)
            return pbox(x + u0, y + v0, du, dv, h, z0, mat, bevel, seg, smooth, name=name)
        uph_bed = self.ex['upholstered_bed']
        frame = self.M.fabric(self.v['textile']) if uph_bed else self.m_wood()
        white = self.M.fabric('#F4F2EE', 'fabric')
        duvet = self.M.fabric(self.v['textile2'] if self.st['id'] != 'baroque' else '#EDE4D3', 'fabric' if self.ex['uph'] != 'linen' else 'linen')
        throw = self.M.fabric(self.v['textile'], 'wool' if self.ex['uph'] != 'leather' else 'fabric')
        lb(0, 0.06, 0.06, Wb, Lb - 0.06, 0.24, frame, bevel=0.025 if uph_bed else 0.008, seg=3, smooth=uph_bed, name='bed frame')
        for u0 in (0.04, Wb - 0.09):
            lb(u0, Lb - 0.09, 0.0, 0.05, 0.05, 0.06, self.m_legs(), name='bed leg')
        lb(0.03, 0.09, 0.3, Wb - 0.06, Lb - 0.12, 0.2, white, bevel=0.05, seg=4, smooth=True, name='mattress')
        lb(-0.02, 0.62, 0.43, Wb + 0.04, Lb - 0.64, 0.09, duvet, bevel=0.04, seg=4, smooth=True, name='duvet')
        lb(-0.03, Lb - 0.55, 0.51, Wb + 0.06, 0.36, 0.03, throw, bevel=0.012, seg=3, smooth=True, name='throw')
        n = 2 if Wb > 1.1 else 1
        pw = (Wb - 0.12) / n
        for i in range(n):
            lb(0.06 + i * pw + 0.02, 0.14, 0.5, pw - 0.04, 0.42, 0.15, white, bevel=0.07, seg=4, smooth=True, name='pillow')
        if n == 2:
            lb(Wb / 2 - 0.28, 0.45, 0.52, 0.56, 0.13, 0.36, self.M.fabric(self.v['textile2']), bevel=0.06, seg=4, smooth=True, name='deco pillow')
        hb_h = 1.25 if uph_bed else 1.0
        lb(-0.03, 0.0, 0.0, Wb + 0.06, 0.08, hb_h, frame, bevel=0.035 if uph_bed else 0.01, seg=4, smooth=uph_bed, name='headboard')

    def chair(self, f, kind):
        back = f.get('back', 'n')
        L, D = self.dims(f, back)
        wood = self.m_wood()
        uph = self.ex['uph'] in ('velvet',) or self.st['id'] in ('greige', 'baroque')
        if kind == 'armchair':
            up = self.M.fabric(self.v['textile2'])
            self.legs4(f, back, 0.06, 0.045, 0.14)
            self.lbox(f, back, 0, 0, 0.14, L, D, 0.24, up, bevel=0.04, seg=4, smooth=True, name='arm base')
            self.lbox(f, back, 0, 0, 0.14, 0.12, D, 0.48, up, bevel=0.05, seg=4, smooth=True, name='arm')
            self.lbox(f, back, L - 0.12, 0, 0.14, 0.12, D, 0.48, up, bevel=0.05, seg=4, smooth=True, name='arm')
            self.lbox(f, back, 0.12, 0, 0.3, L - 0.24, 0.16, 0.5, up, bevel=0.05, seg=4, smooth=True, name='arm back')
            self.lbox(f, back, 0.13, 0.16, 0.38, L - 0.26, D - 0.18, 0.12, up, bevel=0.05, seg=4, smooth=True, name='arm seat')
            return
        if kind == 'barstool':
            m = self.M.metal(self.v['metal'], 0.4)
            seat = self.M.fabric(self.v['textile']) if uph or self.ex['uph'] == 'leather' else wood
            cx, cy = self.lpt(f, back, L / 2, D / 2)
            for dx, dy in ((-0.13, -0.13), (0.13, -0.13), (-0.13, 0.13), (0.13, 0.13)):
                beam((cx + dx, cy + dy, 0), (cx + dx * 0.6, cy + dy * 0.6, 0.64), 0.025, 0.025, m, name='stool leg')
            torus(cx, cy, 0.28, 0.14, 0.01, m, name='footrest')
            cyl(cx, cy, 0.64, 0.19, 0.05, seat, seg=28, name='stool seat', bevel=0.012)
            return
        seat_m = self.M.fabric(self.v['textile']) if uph else wood
        self.legs4(f, back, 0.03, 0.035, 0.43)
        self.lbox(f, back, 0, 0, 0.43, L, D, 0.04 if not uph else 0.07, seat_m, bevel=0.012 if not uph else 0.025, seg=3, smooth=uph, name='seat')
        if uph:
            self.lbox(f, back, 0.02, 0.0, 0.5, L - 0.04, 0.06, 0.42, seat_m, bevel=0.025, seg=3, smooth=True, name='chair back')
        else:
            post = self.m_legs()
            self.lbox(f, back, 0.03, 0.0, 0.47, 0.03, 0.03, 0.38, post, name='back post')
            self.lbox(f, back, L - 0.06, 0.0, 0.47, 0.03, 0.03, 0.38, post, name='back post')
            self.lbox(f, back, 0.03, 0.0, 0.73, L - 0.06, 0.025, 0.12, wood, bevel=0.006, name='back rail')
            self.lbox(f, back, 0.03, 0.0, 0.58, L - 0.06, 0.02, 0.04, wood, bevel=0.004, name='back rail')

    def table(self, f, kind):
        w, d, h = f['w'], f['d'], f['h']
        wood = self.m_wood()
        if kind == 'coffee':
            top = self.M.tiles(self.v['stone'], 5.0) if self.st['id'] in ('greige', 'baroque') else wood
            pbox(f['x'], f['y'], w, d, 0.04, h - 0.04, top, bevel=min(w, d) * 0.3, seg=8, name='coffee top')
            if self.st['id'] == 'japandi':
                pbox(f['x'] + 0.08, f['y'] + 0.08, w - 0.16, d - 0.16, h - 0.04, 0, wood, bevel=0.03, seg=4, name='coffee base')
            else:
                self.legs4(f, 'n', 0.07, 0.035, h - 0.04)
            # книги и ваза
            bx, by = f['x'] + w * 0.25, f['y'] + d * 0.3
            pbox(bx, by, 0.22, 0.16, 0.03, h, self.M.plastic('#8A6E55', 0.6), bevel=0.003, name='book')
            pbox(bx + 0.01, by + 0.01, 0.2, 0.14, 0.025, h + 0.03, self.M.plastic('#D8D2C4', 0.6), bevel=0.003, name='book')
            cyl(f['x'] + w * 0.68, f['y'] + d * 0.6, h, 0.05, 0.16, self.M.plastic(self.ex['pot'] if self.ex['pot'].startswith('#') else '#E9E4DB', 0.25), seg=20, r2=0.035, name='vase')
            return
        thick = 0.035
        pbox(f['x'], f['y'], w, d, thick, h - thick, wood, bevel=0.006, seg=2, name='table top')
        if self.ex['legs'] == 'metal' and kind == 'dining':
            m = self.M.metal(self.v['metal'], 0.45)
            for xx in (f['x'] + 0.12, f['x'] + w - 0.16):
                pbox(xx, f['y'] + 0.08, 0.04, d - 0.16, 0.04, 0.05, m, name='trestle')
                pbox(xx, f['y'] + 0.08, 0.04, 0.04, h - thick - 0.05, 0.05, m, name='trestle')
                pbox(xx, f['y'] + d - 0.12, 0.04, 0.04, h - thick - 0.05, 0.05, m, name='trestle')
                pbox(xx, f['y'] + 0.08, 0.04, d - 0.16, 0.04, h - thick - 0.04, m, name='trestle')
        else:
            self.legs4(f, 'n', 0.06, 0.055 if self.ex['legs'] != 'round' else 0.06, h - thick)
        if kind == 'dining':
            cx, cy = f['x'] + w / 2, f['y'] + d / 2
            cyl(cx, cy, h, 0.06, 0.22, self.M.plastic('#F2F0EC' if self.st['id'] != 'loft' else '#2E3033', 0.25), seg=20, r2=0.04, name='vase')
            for k in range(5):
                sphere(cx + 0.03 * math.cos(k), cy + 0.03 * math.sin(k), h + 0.3 + 0.03 * k, 0.04, self.M.fabric('#EBD9C3' if self.st['id'] != 'baroque' else '#B73A4A', 'fabric'), seg=12, name='flower')
            if f.get('lamp'):
                self.pendant(f)
        if kind == 'desk':
            lx, ly = f['x'] + w - 0.18, f['y'] + 0.15
            cyl(lx, ly, h, 0.07, 0.02, self.M.metal(self.v['metal'], 0.35), seg=16, name='lamp base')
            beam((lx, ly, h + 0.02), (lx - 0.05, ly + 0.05, h + 0.4), 0.012, 0.012, self.M.metal(self.v['metal'], 0.35), name='lamp arm')
            cyl(lx - 0.05, ly + 0.08, h + 0.32, 0.08, 0.1, self.M.glow_shade('#F2F0EC', 1.5), seg=20, r2=0.05, name='lamp shade')
            pbox(f['x'] + 0.3, f['y'] + 0.12, 0.34, 0.24, 0.015, h, self.M.metal('#B8BBBF', 0.3), bevel=0.003, name='laptop')

    def pendant(self, f):
        """Светильники над обеденным столом в стиле."""
        M, v, kind = self.M, self.v, self.ex['lamp']
        w, d = f['w'], f['d']
        cx, cy = f['x'] + w / 2, f['y'] + d / 2
        along_x = w >= d
        Lt = max(w, d)
        B.coll = self.c_ceiling
        metal = M.metal(v['metal'], 0.35)
        bulb = M.emit('#FFE4B8', 12.0)
        warm = M.emit('#FFE9C9', 6.0)
        if kind in ('chandelier', 'sputnik'):
            pts = [(cx, cy)]
        elif Lt >= 1.4:
            off = 0.32 if Lt < 1.8 else 0.45
            pts = [(cx - off, cy), (cx + off, cy)] if along_x else [(cx, cy - off), (cx, cy + off)]
        else:
            pts = [(cx, cy)]
        if kind == 'edison':
            off = Lt * 0.3
            pts = [(cx - off, cy), (cx, cy), (cx + off, cy)] if along_x else [(cx, cy - off), (cx, cy), (cx, cy + off)]
        for i, (px, py) in enumerate(pts):
            low = 1.55
            if kind == 'cone':
                cyl(px, py, low + 0.05, 0.16, 0.2, M.plastic('#1E1F22', 0.45), seg=32, r2=0.05, smooth=True, name='shade')
                sphere(px, py, low + 0.1, 0.045, bulb, seg=12, name='bulb')
            elif kind == 'paper':
                sphere(px, py, low + 0.2, 0.22, M.glow_shade('#F4EFE6', 1.2), seg=28, name='paper lamp')
            elif kind == 'dome':
                sph = sphere(px, py, low + 0.18, 0.17, metal, scale=(1, 1, 0.7), seg=28, name='dome')
                sphere(px, py, low + 0.1, 0.05, bulb, seg=12, name='bulb')
            elif kind == 'globe':
                sphere(px, py, low + 0.15, 0.14, M.glow_shade('#FBF7EF', 3.0), seg=28, name='globe')
                cyl(px, py, low + 0.28, 0.04, 0.04, metal, seg=16, name='cap')
            elif kind == 'edison':
                z = low + (0.12 if i % 2 else 0.0)
                sphere(px, py, z, 0.055, bulb, scale=(1, 1, 1.35), seg=14, name='edison')
                cyl(px, py, z + 0.06, 0.018, 0.04, metal, seg=10, name='socket')
            elif kind == 'sputnik':
                sphere(px, py, low + 0.25, 0.06, metal, seg=16, name='sputnik core')
                for k in range(14):
                    th = 2 * math.pi * k / 14
                    ph = (k % 3 - 1) * 0.6
                    ex = math.cos(th) * math.cos(ph) * 0.42
                    ey = math.sin(th) * math.cos(ph) * 0.42
                    ez = math.sin(ph) * 0.42
                    beam((px, py, low + 0.25), (px + ex, py + ey, low + 0.25 + ez), 0.008, 0.008, metal, name='rod')
                    sphere(px + ex, py + ey, low + 0.25 + ez, 0.03, bulb, seg=10, name='sputnik bulb')
            elif kind == 'chandelier':
                gold = M.metal(v['metal'], 0.28)
                z = low + 0.2
                torus(px, py, z, 0.36, 0.018, gold, name='chandelier ring')
                torus(px, py, z + 0.18, 0.2, 0.012, gold, name='chandelier ring2')
                for k in range(8):
                    th = 2 * math.pi * k / 8
                    ex, ey = math.cos(th) * 0.36, math.sin(th) * 0.36
                    cyl(px + ex, py + ey, z + 0.02, 0.012, 0.09, M.plastic('#FBF8F1', 0.3), seg=10, name='candle')
                    sphere(px + ex, py + ey, z + 0.13, 0.016, bulb, scale=(1, 1, 1.6), seg=10, name='flame')
                    for j in range(3):
                        sphere(px + math.cos(th + 0.4) * 0.3, py + math.sin(th + 0.4) * 0.3, z - 0.05 - 0.04 * j, 0.012, M.mirror(), seg=8, name='crystal')
                cyl(px, py, z, 0.03, H - z, gold, seg=12, name='chandelier stem')
            if kind not in ('chandelier',):
                cyl(px, py, low + 0.2, 0.005, H - low - 0.2, M.plastic('#1E1F22', 0.5), seg=6, name='cord')
                cyl(px, py, H - 0.03, 0.05, 0.03, metal, seg=16, name='canopy')
        B.coll = self.c_furn

    def kitchen(self, f):
        M, v = self.M, self.v
        x, y, w, d, h = f['x'], f['y'], f['w'], f['d'], f['h']
        fronts = M.paint(v['kitchen'], rough=0.4, key='kfront')
        carcass = M.paint(v['kitchen'], rough=0.6, key='kcarc')
        top = M.tiles(v['stone'], 5.0, rough=0.2) if True else None
        plinth = M.paint('#2A2A2A', key='kplinth')
        handle = M.metal(v['metal'] if self.st['id'] != 'nord' else '#1E1F22', 0.3)
        island = 'Остров' in (f.get('n') or '')
        x0r, y0r, x1r, y1r = room_rect('kh')
        along_x = w >= d
        if along_x:
            front = 's' if (y - y0r) < 0.12 else 'n'
        else:
            front = 'e' if (x - x0r) < 0.12 else 'w'
        if island:
            front = 'w'
        # тумбы
        pbox(x + 0.05 * (front == 'w'), y + 0.05 * (front == 'n'), w - 0.05 * (front in 'we'), d - 0.05 * (front in 'ns'), 0.1, 0, plinth, name='kplinth')
        pbox(x, y, w, d, h - 0.14, 0.1, carcass, name='kcarcass')
        Lr = w if along_x else d
        n = max(1, round(Lr / 0.6))
        fw = Lr / n
        for i in range(n):
            if along_x:
                fx = x + i * fw + 0.0015
                fy = y + d if front == 's' else y - 0.018
                pbox(fx, fy, fw - 0.003, 0.018, h - 0.17, 0.11, fronts, bevel=0.0015, name='kfront')
                hy = fy + (0.018 if front == 's' else -0.012)
                pbox(fx + fw * 0.25, hy, fw * 0.5, 0.012, 0.012, h - 0.12, handle, name='khandle')
            else:
                fy = y + i * fw + 0.0015
                fx = x + w if front == 'e' else x - 0.018
                pbox(fx, fy, 0.018, fw - 0.003, h - 0.17, 0.11, fronts, bevel=0.0015, name='kfront')
                hx = fx + (0.018 if front == 'e' else -0.012)
                pbox(hx, fy + fw * 0.25, 0.012, fw * 0.5, 0.012, h - 0.12, handle, name='khandle')
        over = 0.02
        if island:
            pbox(x - over, y - over, w + 0.3, d + 2 * over, 0.04, h - 0.04, top, bevel=0.003, name='ktop')
        else:
            ox0 = over if front == 'w' else 0
            ox1 = over if front == 'e' else 0
            oy0 = over if front == 'n' else 0
            oy1 = over if front == 's' else 0
            pbox(x - ox0, y - oy0, w + ox0 + ox1, d + oy0 + oy1, 0.04, h - 0.04, top, bevel=0.003, name='ktop')
            self.backsplash(f, front)
        if f.get('hob'):
            hx = x + f['hob'] - 0.3 if along_x else x + 0.05
            hy = y + 0.05 if along_x else y + f['hob'] - 0.3
            hw, hd = (0.6, 0.5) if along_x else (0.5, 0.6)
            pbox(hx, hy, hw, hd, 0.006, h, M.screen(), bevel=0.002, name='hob')
            for dx, dy in ((0.15, 0.13), (0.45, 0.13), (0.15, 0.37), (0.45, 0.37)):
                cx = hx + (dx if along_x else dy)
                cy = hy + (dy if along_x else dx)
                torus(cx, cy, h + 0.007, 0.08, 0.003, M.plastic('#5A5A5A', 0.4), seg=32, seg2=6, name='ring')
            self.hood(f, front, hx, hy, hw, hd)
        sink_pos = f.get('sink') if along_x else f.get('sinkV')
        if sink_pos:
            if along_x:
                sx, sy = x + sink_pos - 0.25, y + 0.1
                sw, sd = 0.5, 0.4
            else:
                sx, sy = x + 0.1, y + sink_pos - 0.25
                sw, sd = 0.4, 0.5
            pbox(sx, sy, sw, sd, 0.008, h, M.metal('#C9CCD0', 0.25), bevel=0.01, name='sink')
            pbox(sx + 0.03, sy + 0.03, sw - 0.06, sd - 0.06, 0.004, h + 0.006, M.metal('#8E9196', 0.35), bevel=0.01, name='sink basin')
            tx, ty = (sx + sw / 2, sy - 0.02) if along_x else (sx - 0.02, sy + sd / 2)
            if (along_x and front == 'n') or (not along_x and front == 'w'):
                tx, ty = (sx + sw / 2, sy + sd + 0.02) if along_x else (sx + sw + 0.02, sy + sd / 2)
            cyl(tx, ty, h, 0.018, 0.32, handle, seg=14, name='faucet')
            mx, my = (tx, ty + (0.15 if front == 's' else -0.15)) if along_x else (tx + (0.15 if front == 'e' else -0.15), ty)
            beam((tx, ty, h + 0.32), (mx, my, h + 0.3), 0.022, 0.022, handle, name='spout')

    def backsplash(self, f, front):
        x, y, w, d = f['x'], f['y'], f['w'], f['d']
        mat = self.M.tiles(self.v['stone'], 0.1, grout=self.v['stone'], rough=0.15) if self.st['id'] != 'loft' else self.M.brick(self.v['accent'], 'x')
        x0r, y0r, x1r, y1r = room_rect('kh')
        if front == 's':
            holes = [(o['at'], o['at'] + o['w']) for o in WALLS[0].get('op', []) if o['sill'] > 0]
            for a, b in subtract(x, x + w, holes):
                pbox(a, y0r, b - a, 0.008, 0.56, 0.9, mat, name='splash')
        elif front == 'e' and abs(x - x0r) < 0.12:
            pbox(x0r, y, 0.008, d, 0.56, 0.9, mat, name='splash')
        elif front == 'w' and abs(x + w - x1r) < 0.12:
            pbox(x1r - 0.008, y, 0.008, d, 0.56, 0.9, mat, name='splash')

    def hood(self, f, front, hx, hy, hw, hd):
        if front not in ('s', 'e'):
            return
        # над плитой уже висит шкаф: вытяжка встроена в него
        for u in self.furn:
            if u.get('z0', 0) >= 1.4 and u['m'] == 'kitchen' and rects_overlap((hx, hy, hw, hd), (u['x'], u['y'], u['w'], u['d'])):
                return
        mat = self.M.paint(self.v['kitchen'], rough=0.4, key='kfront') if self.st['id'] not in ('loft', 'graphite') else self.M.metal('#3A3D42', 0.45)
        if front == 's':
            pbox(hx, hy - 0.04, hw, 0.45, 0.35, 1.55, mat, bevel=0.004, name='hood')
        else:
            pbox(hx - 0.04, hy, 0.45, hd, 0.35, 1.55, mat, bevel=0.004, name='hood')

    def cabinet_fronts(self, f, front, z0, h, mat, handle, n=None, vertical=False):
        x, y, w, d = f['x'], f['y'], f['w'], f['d']
        along_x = front in ('n', 's')
        Lr = w if along_x else d
        n = n or max(1, round(Lr / 0.5))
        fw = Lr / n
        for i in range(n):
            if along_x:
                fx = x + i * fw + 0.0015
                fy = y + d if front == 's' else y - 0.018
                pbox(fx, fy, fw - 0.003, 0.018, h - 0.004, z0 + 0.002, mat, bevel=0.0015, name='front')
                if handle is not None:
                    hy = fy + (0.018 if front == 's' else -0.012)
                    hxp = fx + (fw - 0.06 if i % 2 == 0 else 0.04)
                    if vertical:
                        pbox(hxp, hy, 0.012, 0.012, min(0.5, h * 0.3), z0 + h * 0.45, handle, name='handle')
                    else:
                        pbox(fx + fw * 0.4, hy, fw * 0.2, 0.012, 0.012, z0 + h - 0.06, handle, name='handle')
            else:
                fy = y + i * fw + 0.0015
                fx = x + w if front == 'e' else x - 0.018
                pbox(fx, fy, 0.018, fw - 0.003, h - 0.004, z0 + 0.002, mat, bevel=0.0015, name='front')
                if handle is not None:
                    hx = fx + (0.018 if front == 'e' else -0.012)
                    hyp = fy + (fw - 0.06 if i % 2 == 0 else 0.04)
                    if vertical:
                        pbox(hx, hyp, 0.012, 0.012, min(0.5, h * 0.3), z0 + h * 0.45, handle, name='handle')
                    else:
                        pbox(hx, fy + fw * 0.4, 0.012, fw * 0.2, 0.012, z0 + h - 0.06, handle, name='handle')

    def front_side(self, f):
        """Сторона, обращённая в комнату: та, что дальше от ближайшей стены."""
        rid = f.get('r')
        x0, y0, x1, y1 = room_rect(rid) if rid in ROOMS else (0, 0, 10, 8)
        x, y, w, d = f['x'], f['y'], f['w'], f['d']
        gaps = {'n': y - y0, 's': y1 - (y + d), 'w': x - x0, 'e': x1 - (x + w)}
        wall = min(gaps, key=gaps.get)
        return {'n': 's', 's': 'n', 'w': 'e', 'e': 'w'}[wall]

    def box_item(self, f, kind):
        M, v = self.M, self.v
        x, y, w, d, h, z0 = f['x'], f['y'], f['w'], f['d'], f['h'], f.get('z0', 0.0)
        wood = self.m_wood()
        handle = M.metal(v['metal'] if self.st['id'] != 'nord' else '#1E1F22', 0.3)
        if kind == 'fridge':
            body = M.paint(v['kitchen'], rough=0.4, key='kfront')
            pbox(x, y, w, d, h, 0, M.paint(v['kitchen'], rough=0.6, key='kcarc'), name='fridge')
            front = self.front_side(f)
            self.cabinet_fronts(f, front, 0.0, 1.25, body, handle, n=1, vertical=True)
            self.cabinet_fronts(f, front, 1.25, h - 1.25, body, handle, n=1, vertical=True)
            # шкаф над холодильником до потолка
            pbox(x, y, w, d, H - h - 0.05, h, M.paint(v['kitchen'], rough=0.6, key='kcarc'), name='fridge top')
            self.cabinet_fronts(f, front, h, H - h - 0.05, body, None, n=1)
        elif kind == 'uppercab':
            front = self.front_side(f)
            pbox(x, y, w, d, h, z0, M.paint(v['kitchen'], rough=0.6, key='kcarc'), name='upper')
            self.cabinet_fronts(f, front, z0, h, M.paint(v['kitchen'], rough=0.4, key='kfront'), handle)
        elif kind == 'tv':
            pbox(x, y, w, d, h, z0, M.screen(), bevel=0.003, name='tv')
        elif kind == 'tvstand':
            front = self.front_side(f)
            body = wood if self.st['id'] not in ('greige', 'nord') else M.paint(v['kitchen'], rough=0.45, key='kfront')
            pbox(x, y, w, d, h - 0.1, 0.1, body, bevel=0.005, name='tvstand')
            self.cabinet_fronts(f, front, 0.12, h - 0.14, body, None, n=3)
            sub = dict(f); sub['h'] = 0.1
            self.legs4(sub, 'n', 0.05, 0.035, 0.1)
            # декор на тумбе
            cyl(x + w * 0.25 if w > d else x + w / 2, y + d / 2 if w > d else y + d * 0.25, h, 0.06, 0.25, M.plastic(self.ex['pot'] if self.ex['pot'].startswith('#') else '#E9E4DB', 0.3), seg=20, r2=0.04, name='vase')
        elif kind == 'nightstand':
            pbox(x, y, w, d, h - 0.08, 0.08, wood, bevel=0.006, name='nightstand')
            front = self.front_side(f)
            self.cabinet_fronts(f, front, 0.25, 0.22, wood, handle, n=1)
            sub = dict(f); self.legs4(sub, 'n', 0.03, 0.03, 0.08)
            cx, cy = x + w / 2, y + d / 2
            cyl(cx, cy, h, 0.07, 0.18, M.plastic(self.ex['pot'] if self.ex['pot'].startswith('#') else '#E9E4DB', 0.3), seg=20, r2=0.05, name='lamp base')
            cyl(cx, cy, h + 0.18, 0.15, 0.2, M.glow_shade(v['textile2'] if self.st['id'] != 'loft' else '#D9D4CC', 1.0), seg=28, r2=0.11, name='lamp shade')
        elif kind == 'wardrobe':
            body = M.paint(v['kitchen'], rough=0.55, key='wcarc')
            fr = M.paint(v['kitchen'], rough=0.42, key='wfront')
            pbox(x, y, w, d, h, 0, body, name='wardrobe')
            front = self.front_side(f)
            self.cabinet_fronts(f, front, 0.0, h, fr, handle, vertical=True)
            if self.ex['moldings']:
                pbox(x - 0.02, y - 0.02, w + 0.04, d + 0.04, 0.05, h, self.m_trim(), bevel=0.01, name='cornice')
        elif kind == 'bench':
            top = wood
            pbox(x, y, w, d, 0.04, h - 0.04, top, bevel=0.005, name='bench top')
            if self.ex['uph'] in ('velvet', 'linen', 'wool') and w < 1.0 and d < 1.0:
                pbox(x + 0.01, y + 0.01, w - 0.02, d - 0.02, 0.05, h, M.fabric(v['textile2']), bevel=0.02, seg=3, smooth=True, name='bench cushion')
            self.legs4(f, 'n', 0.04, 0.04, h - 0.04)
        elif kind == 'dresser':
            pbox(x, y, w, d, h - 0.08, 0.08, wood, bevel=0.006, name='dresser')
            front = self.front_side(f)
            for k in range(3):
                self.cabinet_fronts(f, front, 0.1 + k * 0.26, 0.25, wood, handle, n=1)
            self.legs4(f, 'n', 0.03, 0.03, 0.08)
        elif kind == 'shelf':
            pbox(x, y, 0.02 if w < d else w, 0.02 if w >= d else d, h, 0, wood, name='shelf side')
            if w < d:
                pbox(x, y + d - 0.02, w, 0.02, h, 0, wood, name='shelf side')
                pbox(x, y, w, 0.02, h, 0, wood, name='shelf side')
            rnd = random.Random(int(x * 100 + y * 10))
            colors = ['#8A6E55', '#D8D2C4', '#4C5A6B', '#A65E4A', '#E4D9C3', '#2F3338', '#6B7A4F']
            for k in range(5):
                zz = 0.05 + k * (h - 0.1) / 4
                pbox(x, y, w, d, 0.025, zz, wood, name='shelf')
                if k < 4:
                    pos = 0.05
                    while pos < (d if w < d else w) - 0.1:
                        bw = rnd.uniform(0.025, 0.05)
                        bh = rnd.uniform(0.18, 0.3)
                        if rnd.random() < 0.85:
                            if w < d:
                                pbox(x + 0.05, y + pos, w - 0.1, bw, bh, zz + 0.025, M.plastic(rnd.choice(colors), 0.6), name='book')
                            else:
                                pbox(x + pos, y + 0.05, bw, d - 0.1, bh, zz + 0.025, M.plastic(rnd.choice(colors), 0.6), name='book')
                        pos += bw + 0.004
        elif kind == 'showertray':
            pbox(x, y, w, d, 0.05, 0, M.plastic('#F5F5F3', 0.2), bevel=0.01, name='tray')
            cyl(x + w / 2, y + d / 2, 0.05, 0.04, 0.003, M.metal('#C9CCD0', 0.3), name='drain')
            cyl(x + 0.12, y + 0.05, 0.9, 0.012, 1.1, M.metal(v['metal'] if self.st['id'] != 'nord' else '#1E1F22', 0.3), seg=12, name='shower rail')
            beam((x + 0.12, y + 0.05, 2.0), (x + 0.12, y + 0.3, 2.05), 0.02, 0.02, M.metal('#C9CCD0', 0.3), name='shower arm')
            cyl(x + 0.12, y + 0.32, 2.0, 0.1, 0.02, M.metal('#C9CCD0', 0.3), seg=24, name='shower head')
        elif kind == 'toilet':
            white = M.plastic('#F7F7F5', 0.15)
            pbox(x + 0.02, y, w - 0.04, 0.14, 1.1, 0, M.paint(v['stone'], key='install'), name='install box')
            pbox(x + w / 2 - 0.1, y + 0.14, 0.2, 0.005, 0.14, 0.95, M.metal('#C9CCD0', 0.3), name='flush')
            pbox(x, y + 0.14, w, d - 0.14, 0.32, 0.12, white, bevel=0.1, seg=5, smooth=True, name='toilet bowl')
            pbox(x + 0.01, y + 0.15, w - 0.02, d - 0.16, 0.03, 0.43, white, bevel=0.012, seg=3, smooth=True, name='toilet seat')
        elif kind == 'vanity':
            front = self.front_side(f)
            body = M.paint(v['kitchen'], rough=0.45, key='kfront')
            pbox(x, y, w, d, 0.5, 0.35, body, bevel=0.004, name='vanity')
            self.cabinet_fronts(f, front, 0.37, 0.46, body, handle, n=1)
            pbox(x - 0.01, y - 0.01, w + 0.02, d + 0.02, 0.13, 0.85, M.plastic('#F7F7F5', 0.12), bevel=0.04, seg=4, smooth=True, name='basin')
            cyl(x + 0.08, y + d / 2, 0.98, 0.016, 0.2, M.metal(v['metal'] if self.st['id'] != 'nord' else '#1E1F22', 0.3), seg=12, name='faucet')
        elif kind == 'mirror':
            fr = self.m_frame_color()
            pbox(x - 0.01, y - 0.03, w + 0.01, d + 0.06, h + 0.06, z0 - 0.03, fr, bevel=0.005, name='mirror frame')
            pbox(x + 0.004, y, w, d, h, z0, M.mirror(), name='mirror')
        elif kind == 'planter':
            self.plant(x + w / 2, y + d / 2, 'bush', pot_r=min(w, d) / 2 * 0.9, pot_h=h)
        elif kind == 'crib':
            m = M.paint('#F4F2EE', rough=0.5, key='crib') if self.st['id'] != 'midcentury' else wood
            pbox(x, y, w, d, 0.04, 0.3, m, bevel=0.005, name='crib base')
            pbox(x + 0.03, y + 0.03, w - 0.06, d - 0.06, 0.1, 0.34, M.fabric('#F4F2EE', 'fabric'), bevel=0.03, seg=3, smooth=True, name='crib mattress')
            for (xx, yy, ww, dd) in ((x, y, w, 0.03), (x, y + d - 0.03, w, 0.03), (x, y, 0.03, d), (x + w - 0.03, y, 0.03, d)):
                pbox(xx, yy, ww, dd, 0.03, h - 0.03, m, bevel=0.005, name='crib rail')
            for k in range(int(w / 0.08) + 1):
                for yy in (y + 0.005, y + d - 0.025):
                    pbox(x + k * (w - 0.02) / max(1, int(w / 0.08)), yy, 0.02, 0.02, h - 0.3, 0.3, m, name='slat')
            for xx, yy in ((x, y), (x + w - 0.04, y), (x, y + d - 0.04), (x + w - 0.04, y + d - 0.04)):
                pbox(xx, yy, 0.04, 0.04, h, 0, m, name='crib post')
        elif kind == 'glasspane':
            pbox(x, y, w, d, h, z0, M.glass(), name='shower glass')
            pbox(x, y, w, d, 0.02, z0 + h, M.metal('#C9CCD0', 0.3), name='glass profile')
        else:
            pbox(x, y, w, d, h, z0, wood, bevel=0.005, name='box')

    def rug(self, f):
        kind = self.ex['rug']
        c1 = self.v['textile2']
        c2 = self.v['accent'] if kind != 'ornate' else self.v['textile']
        if kind == 'ornate':
            # классический ковёр: тёмная кайма, светлое поле, медальон
            x, y, w, d = f['x'], f['y'], f['w'], f['d']
            dark = self.M.rug(self.v['textile'], self.v['textile'], 'plain')
            field = self.M.rug(c1, c1, 'plain')
            pbox(x, y, w, d, 0.012, 0.0, dark, bevel=0.004, name='rug')
            pbox(x + 0.16, y + 0.16, w - 0.32, d - 0.32, 0.002, 0.012, field, name='rug field')
            pbox(x + 0.24, y + 0.24, w - 0.48, d - 0.48, 0.001, 0.0142, self.M.rug(self.v['metal'], self.v['metal'], 'plain'), name='rug line')
            pbox(x + 0.26, y + 0.26, w - 0.52, d - 0.52, 0.001, 0.0144, field, name='rug field2')
            r = min(w, d) * 0.22
            cyl(x + w / 2, y + d / 2, 0.0145, r, 0.001, dark, seg=48, smooth=False, name='medallion')
            cyl(x + w / 2, y + d / 2, 0.0146, r * 0.6, 0.001, field, seg=48, smooth=False, name='medallion2')
            return
        pbox(f['x'], f['y'], f['w'], f['d'], 0.012, 0.0, self.M.rug(c1, c2, kind), bevel=0.004, name='rug')

    def plant(self, cx, cy, kind='tree', pot_r=0.17, pot_h=0.38):
        M = self.M
        pot_hex = self.ex['pot']
        pot = M.plastic(pot_hex, 0.35) if pot_hex.startswith('#') else M.plastic('#E9E4DB', 0.35)
        rnd = random.Random(int(cx * 97 + cy * 31))
        cyl(cx, cy, 0, pot_r * 0.82, pot_h, pot, seg=28, r2=pot_r, name='pot')
        cyl(cx, cy, pot_h - 0.04, pot_r * 0.95, 0.02, M.plastic('#3B2E25', 0.9), seg=24, name='soil')
        leaf1 = M.plastic('#3F5E30', 0.55)
        leaf2 = M.plastic('#5F7F3E', 0.55)
        if kind == 'tree':
            trunk = M.wood('#6B5544', key='planttrunk')
            top = pot_h + 1.0
            beam((cx, cy, pot_h), (cx + 0.03, cy - 0.02, top), 0.03, 0.03, trunk, name='trunk')
            for k in range(46):
                a = rnd.uniform(0, 2 * math.pi)
                r = rnd.uniform(0.04, 0.34)
                z = top + rnd.uniform(-0.35, 0.4) - r * 0.4
                L = rnd.uniform(0.09, 0.15)
                sphere(cx + r * math.cos(a), cy + r * math.sin(a), z, L, leaf1 if k % 3 else leaf2, scale=(1, 0.45, 0.06), seg=10, name='leaf',
                       rot=(rnd.uniform(-0.9, 0.9), rnd.uniform(-0.6, 0.6), a + rnd.uniform(-0.7, 0.7)))
        else:
            for k in range(30):
                a = rnd.uniform(0, 2 * math.pi)
                r = rnd.uniform(0.0, pot_r * 1.1)
                z = pot_h + rnd.uniform(0.06, 0.45) * (1 - r / (pot_r * 1.6))
                L = rnd.uniform(0.1, 0.17)
                sphere(cx + r * math.cos(a), cy + r * math.sin(a), z, L, leaf1 if k % 3 else leaf2, scale=(1, 0.42, 0.06), seg=10, name='leaf',
                       rot=(rnd.uniform(-1.1, 1.1), rnd.uniform(-0.5, 0.5), a + rnd.uniform(-0.6, 0.6)))

    def art(self, wall_axis, coord, lo, hi, inward, z0, z1, rid):
        """Картина: wall_axis 'v' - стена x=coord, вдоль y от lo до hi."""
        M, v = self.M, self.v
        kind = self.ex['art']
        colors = {'abstract': [v['textile2'], v['accent'], v['textile']], 'minimal': [v['wall'], v['accent'], v['wood']],
                  'classic': [v['textile'], '#3A3023', v['textile2']], 'poster': ['#E6E3DE', '#26272A', v['accent']],
                  'geometric': [v['textile'], v['textile2'], v['accent']]}[kind]
        canvas = M.art(colors, kind)
        frame = self.m_frame_color()
        t = 0.03
        if wall_axis == 'v':
            xx = coord if inward > 0 else coord - t
            pbox(xx, lo, t, hi - lo, z1 - z0, z0, frame, bevel=0.004, name='art frame')
            cx = xx + (t if inward > 0 else 0) + (0.001 if inward > 0 else -0.003)
            pbox(cx if inward > 0 else cx, lo + 0.04, 0.002, hi - lo - 0.08, z1 - z0 - 0.08, z0 + 0.04, canvas, name='art')
        else:
            yy = coord if inward > 0 else coord - t
            pbox(lo, yy, hi - lo, t, z1 - z0, z0, frame, bevel=0.004, name='art frame')
            cy = yy + (t if inward > 0 else 0) + (0.001 if inward > 0 else -0.003)
            pbox(lo + 0.04, cy, hi - lo - 0.08, 0.002, z1 - z0 - 0.08, z0 + 0.04, canvas, name='art')

    def classify(self, f, prev):
        n = f.get('n') or ''
        t = f['t']
        if t in ('rug', 'kitchen', 'bed', 'sofa'):
            return t
        if not n and prev and prev[0] == t and prev[1] == f['r'] and prev[2] not in ('fridge', 'tv', 'mirror', 'glasspane') and f['m'] != 'glass':
            if not (t == 'box' and f['m'] == 'kitchen' and f.get('z0', 0) >= 1.4):
                return prev[2]
        if t == 'chair':
            if 'Барн' in n:
                return 'barstool'
            if f['w'] >= 0.7:
                return 'armchair'
            return 'chair'
        if t == 'table':
            if f['h'] < 0.5:
                return 'coffee'
            if f['r'] in ('bed2', 'bed3') or 'Рабоч' in n or 'Туалет' in n:
                return 'desk'
            return 'dining'
        if f['m'] == 'glass':
            return 'mirror' if f.get('z0', 0) > 1.0 else 'glasspane'
        if f['m'] == 'white' and f.get('z0'):
            return 'skip'
        if f['m'] == 'kitchen' and f.get('z0', 0) >= 1.4:
            return 'uppercab'
        if f['h'] < 0.05:
            return 'skip'
        for key, kind in (('Холодильник', 'fridge'), ('Телевизор', 'tv'), ('Тумба под ТВ', 'tvstand'), ('Тумба с раковиной', 'vanity'),
                          ('Тумба', 'nightstand'), ('Шкаф', 'wardrobe'), ('Скамья', 'bench'), ('Комод', 'dresser'), ('Стеллаж', 'shelf'),
                          ('Душ', 'showertray'), ('Унитаз', 'toilet'), ('Кашпо', 'planter'), ('кроватка', 'crib')):
            if key in n:
                return kind
        return 'box'

    def build_furniture(self):
        B.coll = self.c_furn
        prev = None
        for f in self.furn:
            kind = self.classify(f, prev)
            prev = (f['t'], f['r'], kind)
            if kind == 'skip':
                continue
            if kind == 'rug':
                self.rug(f)
            elif kind == 'kitchen':
                self.kitchen(f)
            elif kind == 'sofa':
                self.sofa(f)
            elif kind == 'bed':
                self.bed(f)
            elif kind in ('chair', 'armchair', 'barstool'):
                self.chair(f, kind)
            elif kind in ('dining', 'coffee', 'desk'):
                self.table(f, kind)
            else:
                self.box_item(f, kind)
            B.coll = self.c_furn

    def footprints(self):
        return [(f['x'], f['y'], f['w'], f['d']) for f in self.furn if f['t'] != 'rug' and f.get('plan', True) is not False and not f.get('z0')]

    def build_decor(self):
        B.coll = self.c_furn
        M, v = self.M, self.v
        fps = self.footprints()
        # растения в свободных углах кухни-зала и спален
        x0, y0, x1, y1 = room_rect('kh')
        cands = [(x1 - 0.3, y1 - 0.3), (x1 - 0.3, 2.35), (x0 + 0.3, y1 - 0.3), (x1 - 0.3, y0 + 1.1), (x0 + 0.3, 2.7), (x1 - 0.3, 5.3)]
        placed = 0
        for cx, cy in cands:
            if placed >= self.ex['plants']:
                break
            r = (cx - 0.25, cy - 0.25, 0.5, 0.5)
            if any(rects_overlap(r, fp, 0.02) for fp in fps):
                continue
            if 2.6 < cy < 5.05 and cx > x1 - 1.0:
                continue
            self.plant(cx, cy, 'tree' if placed == 0 else 'bush')
            fps.append(r)
            placed += 1
        if self.st['id'] in ('japandi', 'nord', 'midcentury'):
            for rid in ('bed3', 'bed2'):
                bx0, by0, bx1, by1 = room_rect(rid)
                for cx, cy in ((bx1 - 0.28, by0 + 0.28), (bx1 - 0.28, by1 - 0.28), (bx0 + 0.28, by1 - 0.28), (bx0 + 0.28, by0 + 0.28)):
                    r = (cx - 0.22, cy - 0.22, 0.44, 0.44)
                    if any(rects_overlap(r, fp, 0.02) for fp in fps):
                        continue
                    # не перед дверью
                    if abs(cx - 3.99) < 0.3 and (2.7 < cy < 3.9 or 4.9 < cy < 6.1):
                        continue
                    self.plant(cx, cy, 'bush', pot_r=0.14, pot_h=0.3)
                    fps.append(r)
                    break
        # картины над диваном и кроватью
        for f in self.furn:
            if f['t'] == 'sofa' and f.get('n'):
                back = f.get('back', 'n')
                rid = f['r']
                rx0, ry0, rx1, ry1 = room_rect(rid)
                if back == 'w' and f['x'] - rx0 < 0.15:
                    self.art('v', rx0 + 0.012 if any(abs(a[0] - rx0) < 0.05 for a in self.L['accents']) else rx0, f['y'] + f['d'] * 0.2, f['y'] + f['d'] * 0.8, 1, 1.35, 2.05, rid)
                elif back == 'e' and rx1 - (f['x'] + f['w']) < 0.15:
                    self.art('v', rx1, f['y'] + f['d'] * 0.2, f['y'] + f['d'] * 0.8, -1, 1.35, 2.05, rid)
                elif back == 's' and ry1 - (f['y'] + f['d']) < 0.15:
                    self.art('h', ry1, f['x'] + f['w'] * 0.2, f['x'] + f['w'] * 0.8, -1, 1.35, 2.05, rid)
                elif back == 'n' and f['y'] - ry0 < 0.15:
                    self.art('h', ry0, f['x'] + f['w'] * 0.2, f['x'] + f['w'] * 0.8, 1, 1.35, 2.05, rid)
            if f['t'] == 'bed' and f.get('n') and f['w'] > 1.9 and f['d'] > 1.2:
                head = f.get('head', 'n')
                if head == 'w':
                    off = 0.012 if any(abs(a[0] - 0.25) < 0.05 for a in self.L['accents']) else 0.0
                    self.art('v', 0.25 + off, f['y'] + 0.3, f['y'] + f['d'] - 0.3, 1, 1.45, 2.0, f['r'])
        # шторы
        if self.ex['curtains']:
            mat = M.fabric(v['textile'] if self.ex['curtains'] == 'heavy' and self.st['id'] == 'baroque' else (v['textile2'] if self.ex['curtains'] == 'heavy' else '#F1EEE7'),
                           'velvet' if self.st['id'] == 'baroque' else 'linen')
            rod = M.metal(v['metal'], 0.35)
            for wl in WALLS:
                if not wl.get('out'):
                    continue
                for o in wl.get('op', []):
                    if not o.get('glass') or o['sill'] <= 0:
                        continue
                    a, b = o['at'], o['at'] + o['w']
                    t = wl['t']
                    if wl['dir'] == 'h':
                        inward = 1 if wl['out'] == 'n' else -1
                        face = wl['y'] + inward * t / 2
                        rid = in_room((a + b) / 2, face + inward * 0.3)
                        if rid not in ('kh', 'bed2', 'bed3'):
                            continue
                        yy = face + inward * 0.09
                        pw = 0.42
                        for start in (a - 0.32, b - 0.1):
                            curtain((start, yy), (1, 0), (0, inward), pw, 0.02, H - 0.08, mat, coll=self.c_furn)
                        beam((a - 0.4, yy, H - 0.07), (b + 0.4, yy, H - 0.07), 0.02, 0.02, rod, name='rod')
                    else:
                        inward = 1 if wl['out'] == 'w' else -1
                        face = wl['x'] + inward * t / 2
                        rid = in_room(face + inward * 0.3, (a + b) / 2)
                        if rid not in ('kh', 'bed2', 'bed3'):
                            continue
                        xx = face + inward * 0.09
                        for start in (a - 0.32, b - 0.1):
                            curtain((xx, start), (0, 1), (inward, 0), 0.42, 0.02, H - 0.08, mat, coll=self.c_furn)
                        beam((xx, a - 0.4, H - 0.07), (xx, b + 0.4, H - 0.07), 0.02, 0.02, rod, name='rod')
        # потолочные светильники в спальнях и коридоре
        B.coll = self.c_ceiling
        for rid in ('bed2', 'bed3', 'cor', 'hallway'):
            rx0, ry0, rx1, ry1 = room_rect(rid)
            cyl((rx0 + rx1) / 2, (ry0 + ry1) / 2, H - 0.06, 0.2 if rid.startswith('bed') else 0.12, 0.06, M.glow_shade('#FBF8F2', 2.0), seg=32, name='ceiling lamp')
        B.coll = self.c_furn

    # --- свет и мир
    def build_world(self):
        sc = bpy.context.scene
        w = bpy.data.worlds.new('sky')
        sc.world = w
        w.use_nodes = True
        nt = w.node_tree
        bg = nt.nodes.get('Background')
        sky = node(nt, 'ShaderNodeTexSky')
        for k, val in (('sky_type', 'MULTIPLE_SCATTERING'), ('sun_disc', False), ('sun_elevation', math.radians(28)), ('sun_rotation', math.radians(135)), ('altitude', 300.0)):
            try:
                setattr(sky, k, val)
            except Exception:
                pass
        mix = node(nt, 'ShaderNodeMix', data_type='RGBA', blend_type='MIX')
        link(nt, outp(sky, 'Color'), inp(mix, 'A', None, 'RGBA'))
        inp(mix, 'B', (0.62, 0.62, 0.6, 1.0), 'RGBA')
        inp(mix, 'Factor', 0.0, 'VALUE')
        link(nt, outp(mix, 'Result', 'RGBA'), bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.32
        self.sky = sky
        self.bg = bg
        self.sky_mix = mix

    def studio(self, on):
        """Нейтральный свет для планов: без синевы неба."""
        inp(self.sky_mix, 'Factor', 1.0 if on else 0.0, 'VALUE')

    def set_sun(self, elev_deg, az_deg, strength):
        if not hasattr(self, 'sun'):
            ld = bpy.data.lights.new('sun', 'SUN')
            ld.angle = math.radians(1.2)
            ld.color = (1.0, 0.95, 0.88)
            self.sun = bpy.data.objects.new('sun', ld)
            bpy.context.scene.collection.objects.link(self.sun)
        el, az = math.radians(elev_deg), math.radians(az_deg)
        to_sun = Vector((math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)))
        self.sun.rotation_mode = 'QUATERNION'
        self.sun.rotation_quaternion = (-to_sun).to_track_quat('-Z', 'Y')
        self.sun.data.energy = strength
        try:
            self.sky.sun_elevation = el
            self.sky.sun_rotation = az
        except Exception:
            pass

    def build_lights(self):
        # порталы в окнах, чтобы свет неба быстрее сходился внутри
        self.portals = []
        for wl in WALLS:
            if not wl.get('out'):
                continue
            for o in wl.get('op', []):
                if not o.get('glass'):
                    continue
                a, w, s, h, t = o['at'], o['w'], o['sill'], o['h'], wl['t']
                ld = bpy.data.lights.new('portal', 'AREA')
                ld.shape = 'RECTANGLE'; ld.size = w; ld.size_y = h
                ok = False
                for holder in (getattr(ld, 'cycles', None), ld):
                    if holder is not None and hasattr(holder, 'is_portal'):
                        holder.is_portal = True
                        ok = True
                        break
                if not ok:
                    bpy.data.lights.remove(ld)
                    continue
                ob = bpy.data.objects.new('portal', ld)
                if wl['dir'] == 'h':
                    inward = 1 if wl['out'] == 'n' else -1
                    face = wl['y'] + inward * t / 2
                    ob.location = (a + w / 2, -(face + inward * 0.01), s + h / 2)
                    nv = Vector((0, -inward, 0))
                else:
                    inward = 1 if wl['out'] == 'w' else -1
                    face = wl['x'] + inward * t / 2
                    ob.location = (face + inward * 0.01, -(a + w / 2), s + h / 2)
                    nv = Vector((inward, 0, 0))
                ob.rotation_mode = 'QUATERNION'
                ob.rotation_quaternion = nv.to_track_quat('-Z', 'Z')
                self.c_fill.objects.link(ob)
                self.portals.append(ob)
        # мягкая подсветка комнат, невидимая для камеры
        for rid, power in (('kh', 70), ('bed3', 30), ('bed2', 30), ('cor', 14), ('hallway', 8), ('bath', 10)):
            rx0, ry0, rx1, ry1 = room_rect(rid)
            spots = [((rx0 + rx1) / 2, (ry0 + ry1) / 2)] if rid != 'kh' else [((rx0 + rx1) / 2, ry0 + 2.0), ((rx0 + rx1) / 2, ry1 - 2.0)]
            for cx, cy in spots:
                ld = bpy.data.lights.new('fill', 'AREA')
                ld.shape = 'RECTANGLE'; ld.size = (rx1 - rx0) * 0.6; ld.size_y = min(2.5, (ry1 - ry0) * 0.6)
                ld.energy = power
                ld.color = (1.0, 0.93, 0.84)
                ob = bpy.data.objects.new('fill', ld)
                ob.location = (cx, -cy, H - 0.05)
                try:
                    ob.visible_camera = False
                    ob.visible_glossy = False
                except Exception:
                    pass
                self.c_fill.objects.link(ob)

    def build(self):
        t = time.time()
        self.build_shell()
        self.build_ceiling()
        self.build_trim()
        self.build_terrace()
        self.build_exterior()
        self.build_furniture()
        self.build_decor()
        self.build_world()
        self.set_sun(28, 135, 4.0)
        self.build_lights()
        print('BUILD', self.L['id'], self.st['id'], 'objects', len(bpy.data.objects), 'sec', round(time.time() - t, 1), flush=True)


# ---------------------------------------------------------------- камеры и рендер
def make_camera(name, pos, target, lens=18.0, ortho=None, coll=None, max_pitch=7.0):
    cd = bpy.data.cameras.new(name)
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 500
    ob = bpy.data.objects.new(name, cd)
    (coll or bpy.context.scene.collection).objects.link(ob)
    p = Vector((pos[0], -pos[1], pos[2]))
    tg = Vector((target[0], -target[1], target[2]))
    d = tg - p
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
        hz = math.hypot(d.x, d.y)
        lim = math.tan(math.radians(max_pitch)) * hz
        if max_pitch < 80:
            d.z = max(-lim, min(lim, d.z))
    ob.location = p
    if ortho and abs(d.x) < 1e-3 and abs(d.y) < 1e-2:
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = (0.0, 0.0, 0.0)
        return ob
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    return ob


def bed_camera(house, rid):
    beds = [f for f in house.furn if f['r'] == rid and f['t'] == 'bed' and f.get('n')]
    sofas = [f for f in house.furn if f['r'] == rid and f['t'] == 'sofa' and f.get('n')]
    x0, y0, x1, y1 = room_rect(rid)
    if beds:
        f = beds[0]
        head = f.get('head', 'n')
        if head == 'w':
            hc = (f['x'], f['y'] + f['d'] / 2); u = (1, 0)
        elif head == 's':
            hc = (f['x'] + f['w'] / 2, f['y'] + f['d']); u = (0, -1)
        elif head == 'e':
            hc = (f['x'] + f['w'], f['y'] + f['d'] / 2); u = (-1, 0)
        else:
            hc = (f['x'] + f['w'] / 2, f['y']); u = (0, 1)
    elif sofas:
        f = sofas[0]
        hc = (f['x'], f['y'] + f['d'] / 2); u = (1, 0)
    else:
        hc = ((x0 + x1) / 2, y0); u = (0, 1)
    lat = (-u[1], u[0])
    blockers = house.door_rects + [(f['x'], f['y'], f['w'], f['d']) for f in house.furn
                                   if f['r'] == rid and f['t'] != 'rug' and f['h'] > 1.0]
    best, best_d = None, -1
    for side in (1, -1, 0.5, -0.5):
        px = hc[0] + u[0] * 3.3 + lat[0] * 0.9 * side
        py = hc[1] + u[1] * 3.3 + lat[1] * 0.9 * side
        px = max(x0 + 0.3, min(x1 - 0.3, px)); py = max(y0 + 0.3, min(y1 - 0.3, py))
        dmin = 9.0
        for bx, by, bw, bd in blockers:
            dx = max(bx - px, 0, px - (bx + bw)); dy = max(by - py, 0, py - (by + bd))
            dmin = min(dmin, math.hypot(dx, dy))
        if dmin > best_d:
            best, best_d = (px, py), dmin
    return (best[0], best[1], 1.3), (hc[0] + u[0] * 0.9, hc[1] + u[1] * 0.9, 0.85)


def three_to_plan(p):
    return (p[0], p[2], p[1])


def setup_render(sc, samples, res):
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'CPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.03
    cy.use_denoising = True
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    cy.max_bounces = 8
    cy.diffuse_bounces = 4
    cy.glossy_bounces = 3
    cy.transmission_bounces = 6
    cy.transparent_max_bounces = 16
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 6.0
    cy.blur_glossy = 1.0
    sc.render.use_persistent_data = True
    rw, rh = (int(s) for s in res.split('x'))
    sc.render.resolution_x, sc.render.resolution_y = rw, rh
    sc.render.resolution_percentage = PCT[0]
    sc.view_settings.view_transform = 'AgX'
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast', 'AgX - Base Contrast'):
        try:
            sc.view_settings.look = look
            break
        except Exception:
            pass
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 90


def render_views(house, a):
    sc = bpy.context.scene
    os.makedirs(a['out'], exist_ok=True)
    L = house.L
    lid = LAT[L['id']]
    sid = house.st['id']
    res = a['res']
    for view in [v.strip() for v in a['views'].split(',') if v.strip()]:
        fname = os.path.join(a['out'], '%s-%s%s-%s.jpg' % (lid, sid, ('-' + str(a['variant'])) if a['variant'] else '', view))
        if os.path.exists(fname) and os.path.getsize(fname) > 10000 and not a.get('force'):
            print('SKIP', fname, flush=True)
            continue
        interior = view not in ('plan', 'axo', 'axo2')
        house.c_ceiling.hide_render = not interior
        house.c_fill.hide_render = not interior
        house.c_ext.hide_render = False
        house.c_grass.hide_render = not interior
        house.c_paper.hide_render = interior
        for ob in house.c_ext.objects:
            if ob.name.startswith(('pine', 'trunk', 'hill')):
                ob.hide_render = not interior
        samples = a['samples']
        rw, rh = (int(s) for s in res.split('x'))
        house.studio(not interior)
        if view == 'plan':
            house.set_sun(58, 150, 3.2)
            house.bg.inputs['Strength'].default_value = 1.0
            cam = make_camera('cam plan', (6.33, 4.85, 30), (6.33, 4.8501, 0), ortho=14.4, coll=house.c_cams)
            sc.view_settings.exposure = -0.3
            rw, rh = 1800, 1380
            samples = min(samples, 48)
        elif view in ('axo', 'axo2'):
            house.set_sun(42, 150, 3.4)
            house.bg.inputs['Strength'].default_value = 1.0
            if view == 'axo':
                cam = make_camera('cam axo', (1.2, 17.5, 13.5), (6.6, 4.3, 0.0), lens=38, coll=house.c_cams, max_pitch=89)
            else:
                cam = make_camera('cam axo2', (15.5, 16.5, 13.0), (6.0, 4.3, 0.0), lens=38, coll=house.c_cams, max_pitch=89)
            sc.view_settings.exposure = -0.3
            rw, rh = 1800, 1200
            samples = min(samples, 48)
        else:
            house.set_sun(26, 140, 4.0)
            house.bg.inputs['Strength'].default_value = 0.32
            sc.view_settings.exposure = 0.45
            if view in ('kh', 'kitchen'):
                sp = L['spots'][view]
                pos, look = three_to_plan(sp[0]), three_to_plan(sp[1])
                pos = (pos[0], pos[1], 1.35)
                lens = 18 if view == 'kh' else 20
                if view == 'kitchen':
                    dx, dy = look[0] - pos[0], look[1] - pos[1]
                    dl = math.hypot(dx, dy) or 1.0
                    kx0, ky0, kx1, ky1 = room_rect('kh')
                    pos = (max(kx0 + 0.3, min(kx1 - 0.3, pos[0] - dx / dl * 0.6)), max(ky0 + 0.3, min(ky1 - 0.3, pos[1] - dy / dl * 0.6)), 1.45)
            elif view in ('bed3', 'bed2'):
                pos, look = bed_camera(house, view)
                lens = 18
            elif view == 'terrace':
                pos, look, lens = (12.25, 7.55, 1.4), (10.4, 3.2, 1.1), 18
            elif view == 'bath':
                pos, look, lens = (5.6, 2.2, 1.45), (4.6, 0.6, 1.0), 14
            else:
                continue
            cam = make_camera('cam ' + view, pos, look, lens=lens, coll=house.c_cams)
        sc.camera = cam
        setup_render(sc, samples, '%dx%d' % (rw, rh))
        sc.render.filepath = fname
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print('RENDERED', os.path.basename(fname), round(time.time() - t, 1), 's', flush=True)


PCT = [100]


def main():
    a = parse_args()
    PCT[0] = int(a.get('pct', 100))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    house = House(a['layout'], a['style'], a['variant'])
    house.build()
    if a['save']:
        sc = bpy.context.scene
        setup_render(sc, a['samples'], a['res'])
        sp = DATA['LAYOUTS'][a['layout']]['spots']['kh']
        pos, look = three_to_plan(sp[0]), three_to_plan(sp[1])
        sc.camera = make_camera('cam kh', (pos[0], pos[1], 1.35), look, lens=18, coll=house.c_cams)
        make_camera('cam plan', (6.33, 4.85, 30), (6.33, 4.8501, 0), ortho=14.4, coll=house.c_cams)
        house.c_paper.hide_render = True
        house.c_paper.hide_viewport = True
        house.studio(False)
        sc.view_settings.exposure = 0.45
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a['save']))
        print('SAVED', a['save'], flush=True)
    render_views(house, a)


if __name__ == '__main__':
    main()
