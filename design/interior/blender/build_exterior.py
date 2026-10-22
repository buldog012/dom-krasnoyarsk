# Внешний вид дома с крышей и варианты фасадов для сайта (на базе build_house.py).
# blender -b --factory-startup --python build_exterior.py -- --mode variants --out renders-ext --samples 64 --res 2000x1250
# blender -b --factory-startup --python build_exterior.py -- --mode turntable --frames 24 --res 1400x875 --samples 32
import bpy
import bmesh
import math
import os
import sys
import time
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_house as bh  # noqa: E402

OVER = 0.55                               # свес крыши
PITCH = math.radians(26)                  # уклон скатов
WALL_TOP = bh.H + 0.12                    # верх перекрытия
EAVE_Z = WALL_TOP - OVER * math.tan(PITCH)
X0, X1 = -OVER, 12.66 + OVER              # крыша накрывает террасу
Y0, Y1 = -OVER, 8.17 + OVER
RIDGE_Y = 8.17 / 2
RIDGE_Z = EAVE_Z + (RIDGE_Y + OVER) * math.tan(PITCH)
CX, CY = 6.3, 4.1                         # центр дома с террасой

VARIANTS = {
    'built':   dict(name='Как построен: светлый сайдинг', kind='siding', color='#A7ADB3'),
    'dark':    dict(name='Тёмная вертикальная доска', kind='vwood', color='#35393D'),
    'plaster': dict(name='Светлая штукатурка', kind='plaster', color='#E7E2D9'),
    'wood':    dict(name='Лиственница, планкен', kind='hwood', color='#C49B6A'),
    'brick':   dict(name='Облицовочный кирпич', kind='brick', color='#8F5F48'),
}


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    a = {'mode': 'variants', 'out': os.path.join(HERE, 'renders-ext'), 'samples': '64', 'res': '2000x1250',
         'only': '', 'frames': '24', 'pct': '100', 'force': '', 'bg': ''}
    i = 0
    while i < len(argv):
        a[argv[i].lstrip('-')] = argv[i + 1]
        i += 2
    if not os.path.isabs(a['out']):
        a['out'] = os.path.join(HERE, a['out'])
    a['samples'] = int(a['samples'])
    a['frames'] = int(a['frames'])
    bh.PCT[0] = int(a['pct'])
    if not a['bg']:
        a['bg'] = 'studio' if a['mode'] == 'turntable' else 'nature'
    return a


# ---------------------------------------------------------------- материалы фасада
def facade_mat(M, kind, hexc):
    def f():
        m, nt, b = bh.principled('facade %s %s' % (kind, hexc), bh.rgb(hexc), rough=0.9 if kind == 'plaster' else 0.62, spec=0.35)
        if kind == 'plaster':
            bh.noise_bump(nt, b, scale=90.0, strength=0.1)
            return m
        sep = bh.node(nt, 'ShaderNodeSeparateXYZ')
        bh.link(nt, bh.objcoord(nt), bh.inp(sep, 'Vector'))
        add = bh.node(nt, 'ShaderNodeMath', operation='ADD')
        bh.link(nt, bh.outp(sep, 'X'), add.inputs[0])
        bh.link(nt, bh.outp(sep, 'Y'), add.inputs[1])
        cmb = bh.node(nt, 'ShaderNodeCombineXYZ')
        bh.link(nt, bh.outp(add, 'Value'), bh.inp(cmb, 'X'))
        bh.link(nt, bh.outp(sep, 'Z'), bh.inp(cmb, 'Y'))
        br = bh.node(nt, 'ShaderNodeTexBrick', offset=0.5 if kind == 'brick' else 0.0)
        if kind == 'brick':
            bw, rh, ms, mortar, c2, dist = 0.25, 0.065, 0.012, bh.rgb('#C9C2B8'), bh.rgb(hexc, 0.82), 0.012
        elif kind == 'vwood':
            bw, rh, ms, mortar, c2, dist = 0.14, 60.0, 0.008, bh.rgb(hexc, 0.45), bh.rgb(hexc, 0.88), 0.008
        elif kind == 'hwood':
            bw, rh, ms, mortar, c2, dist = 60.0, 0.14, 0.007, bh.rgb(hexc, 0.5), bh.rgb(hexc, 0.9), 0.007
        else:  # siding
            bw, rh, ms, mortar, c2, dist = 60.0, 0.2, 0.006, bh.rgb(hexc, 0.55), bh.rgb(hexc, 0.97), 0.006
        bh.inp(br, 'Color1', bh.rgb(hexc, 1.0))
        bh.inp(br, 'Color2', c2)
        bh.inp(br, 'Mortar', mortar)
        bh.inp(br, 'Scale', 1.0)
        bh.inp(br, 'Mortar Size', ms)
        bh.inp(br, 'Brick Width', bw)
        bh.inp(br, 'Row Height', rh)
        bh.link(nt, bh.outp(cmb, 'Vector'), bh.inp(br, 'Vector'))
        bh.link(nt, bh.outp(br, 'Color'), bh.inp(b, 'Base Color'))
        bump = bh.node(nt, 'ShaderNodeBump', invert=True)
        bh.inp(bump, 'Strength', 0.5)
        bh.inp(bump, 'Distance', dist)
        bh.link(nt, bh.outp(br, 'Fac'), bh.inp(bump, 'Height'))
        bh.link(nt, bh.outp(bump, 'Normal'), bh.inp(b, 'Normal'))
        return m
    return M.get(('facade', kind, hexc), f)


def apply_facade(house, mat, terrace_mat):
    """Слот 1 у наружных стен: сайдинг -> материал варианта. Стена под террасой всегда дерево, как построено."""
    n = 0
    for ob in house.c_house.objects:
        if not ob.name.startswith('wall') or len(ob.data.materials) != 3:
            continue
        c = sum((ob.matrix_world @ Vector(v) for v in ob.bound_box), Vector()) / 8
        ob.data.materials[1] = terrace_mat if c.x > 9.9 else mat
        n += 1
    return n


# ---------------------------------------------------------------- крыша
def P(x, y, z):
    return Vector((x, -y, z))


def mesh_obj(name, verts, faces, mat, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(mat)
    return ob


def slab(name, quad, thick, mat, coll):
    pts = [P(*p) for p in quad]
    n = (pts[1] - pts[0]).cross(pts[3] - pts[0]).normalized()
    if n.z < 0:
        n = -n
    verts = pts + [p + n * thick for p in pts]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_obj(name, verts, faces, mat, coll)


def gable(name, x, dx, mat, coll):
    tri = [(x, 0.0, WALL_TOP - 0.02), (x, 8.17, WALL_TOP - 0.02), (x, RIDGE_Y, RIDGE_Z - 0.01)]
    pts = [P(*p) for p in tri]
    verts = pts + [p + Vector((dx, 0, 0)) for p in pts]
    faces = [(0, 1, 2), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
    return mesh_obj(name, verts, faces, mat, coll)


def build_roof(house, facade):
    M = house.M
    coll = house.c_ceiling
    roof = M.paint('#2F2F30', rough=0.92, key='roof metal')
    trim = M.paint('#24272B', rough=0.7, key='fascia')
    slab('roof n', [(X0, Y0, EAVE_Z), (X1, Y0, EAVE_Z), (X1, RIDGE_Y, RIDGE_Z), (X0, RIDGE_Y, RIDGE_Z)], 0.1, roof, coll)
    slab('roof s', [(X0, Y1, EAVE_Z), (X1, Y1, EAVE_Z), (X1, RIDGE_Y, RIDGE_Z), (X0, RIDGE_Y, RIDGE_Z)], 0.1, roof, coll)
    bh.beam((X0, RIDGE_Y, RIDGE_Z + 0.1), (X1, RIDGE_Y, RIDGE_Z + 0.1), 0.36, 0.08, roof, name='ridge', coll=coll)
    for yy in (Y0, Y1):
        bh.beam((X0, yy, EAVE_Z - 0.09), (X1, yy, EAVE_Z - 0.09), 0.04, 0.2, trim, name='fascia', coll=coll)
    for xx in (X0, X1):
        bh.beam((xx, Y0, EAVE_Z - 0.09), (xx, RIDGE_Y, RIDGE_Z - 0.09), 0.04, 0.2, trim, name='barge', coll=coll)
        bh.beam((xx, Y1, EAVE_Z - 0.09), (xx, RIDGE_Y, RIDGE_Z - 0.09), 0.04, 0.2, trim, name='barge', coll=coll)
    gable('gable w', -0.06, 0.06, facade, coll)
    gable('gable e', 12.60, 0.06, facade, coll)
    # пояс по верху стен и террасы, закрывает торец перекрытия
    z0 = bh.H - 0.005
    bh.pbox(-0.03, -0.03, 12.72, 0.06, 0.14, z0, facade, name='band', coll=coll)
    bh.pbox(-0.03, 8.14, 12.72, 0.06, 0.14, z0, facade, name='band', coll=coll)
    bh.pbox(-0.03, -0.03, 0.06, 8.23, 0.14, z0, facade, name='band', coll=coll)
    bh.pbox(12.63, -0.03, 0.06, 8.23, 0.14, z0, facade, name='band', coll=coll)


# ---------------------------------------------------------------- сцена и рендер
def prepare(house, bg):
    nature = bg == 'nature'
    house.c_ceiling.hide_render = False
    house.c_fill.hide_render = True
    house.c_grass.hide_render = not nature
    house.c_paper.hide_render = nature
    house.c_paper.hide_viewport = nature
    for ob in house.c_ext.objects:
        if ob.name.startswith(('pine', 'trunk', 'hill')):
            # в природе прячем сосны перед камерой (южнее дома), в студии прячем всё
            front = ob.location.y < -10.0
            ob.hide_render = (not nature) or (front and not ob.name.startswith('hill'))
        else:
            ob.hide_render = False
    house.studio(not nature)
    if nature:
        bh.inp(house.sky_mix, 'Factor', 0.42, 'VALUE')   # приглушить синеву неба
    house.bg.inputs['Strength'].default_value = 0.72 if nature else 1.15


def light(house, when):
    if when == 'evening':
        house.set_sun(6, 248, 4.2)
        house.sun.data.color = (1.0, 0.72, 0.48)
        house.bg.inputs['Strength'].default_value = 0.55
    else:
        house.set_sun(27, 150, 4.6)
        house.sun.data.color = (1.0, 0.93, 0.84)
        house.bg.inputs['Strength'].default_value = 0.72


def render(sc, fname, samples, res):
    bh.setup_render(sc, samples, res)
    if sc.render.film_transparent:
        sc.render.image_settings.file_format = 'PNG'
        sc.render.image_settings.color_mode = 'RGBA'
        sc.render.image_settings.compression = 50
    sc.render.filepath = fname
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDERED', os.path.basename(fname), round(time.time() - t, 1), 's', flush=True)


def main():
    a = parse()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    house = bh.House(0, 'nord', 0)
    house.build()
    prepare(house, a['bg'])
    sc = bpy.context.scene
    sc.view_settings.exposure = -0.1
    os.makedirs(a['out'], exist_ok=True)
    terrace_wood = facade_mat(house.M, 'hwood', '#BE9566')
    only = [s for s in a['only'].split(',') if s]
    if a['mode'] == 'variants':
        jobs = [(k, 'day') for k in VARIANTS] + [('built', 'evening')]
        first = True
        for key, when in jobs:
            if only and key not in only:
                continue
            fname = os.path.join(a['out'], key + ('-evening' if when == 'evening' else '') + '.jpg')
            if os.path.exists(fname) and os.path.getsize(fname) > 10000 and not a['force']:
                print('SKIP', fname, flush=True)
                continue
            v = VARIANTS[key]
            fm = facade_mat(house.M, v['kind'], v['color'])
            if first:
                build_roof(house, fm)
                first = False
            else:
                for ob in list(house.c_ceiling.objects):
                    if ob.name.startswith(('gable', 'band')):
                        ob.data.materials[0] = fm
            apply_facade(house, fm, terrace_wood)
            light(house, when)
            if when == 'evening':
                sc.view_settings.exposure = -0.35
            else:
                sc.view_settings.exposure = -0.1
            sc.camera = bh.make_camera('cam ext ' + key, (21.8, 15.6, 4.3), (6.3, 4.2, 1.8), lens=35, coll=house.c_cams, max_pitch=89)
            render(sc, fname, a['samples'], a['res'])
    elif a['mode'] == 'turntable':
        v = VARIANTS['built']
        fm = facade_mat(house.M, v['kind'], v['color'])
        build_roof(house, fm)
        apply_facade(house, fm, terrace_wood)
        light(house, 'day')
        if a['bg'] == 'studio':
            # прозрачный фон, земля ловит только тень: дом можно класть на любой фон страницы
            house.bg.inputs['Strength'].default_value = 1.15
            sc.render.film_transparent = True
            for ob in house.c_paper.objects:
                ob.is_shadow_catcher = True
        n = a['frames']
        for k in range(n):
            fname = os.path.join(a['out'], 'turn-%02d.' % k + ('png' if sc.render.film_transparent else 'jpg'))
            if os.path.exists(fname) and os.path.getsize(fname) > 10000 and not a['force']:
                continue
            ang = math.radians(50) - 2 * math.pi * k / n
            pos = (CX + 19.5 * math.cos(ang), CY + 19.5 * math.sin(ang), 5.2)
            sc.camera = bh.make_camera('cam turn %d' % k, pos, (CX, CY, 1.5), lens=36, coll=house.c_cams, max_pitch=89)
            render(sc, fname, a['samples'], a['res'])
    print('EXTERIOR DONE', flush=True)


if __name__ == '__main__':
    main()
