# Копирует рендеры в папку владельца на рабочем столе с понятными именами.
# Запуск: python export_desktop.py
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'renders')
DST = os.path.join(os.path.expanduser('~'), 'Desktop', 'Планировки дома в Зыково', '3D-визуализация Blender')
STYLES = {'nord': '1 Скандинавский', 'japandi': '2 Джапанди', 'graphite': '3 Графит и дерево', 'greige': '4 Современная классика',
          'baroque': '5 Барокко', 'loft': '6 Лофт', 'midcentury': '7 Мид-сенчури'}
LAYOUTS = {'a': 'А', 'b': 'Б', 'v': 'В', 'g': 'Г'}
VIEWS = {'plan': 'план сверху', 'axo': 'дом без крыши', 'kh': 'кухня-зал', 'kitchen': 'кухня', 'bed3': 'спальня', 'terrace': 'терраса'}

n = 0
for name in sorted(os.listdir(SRC)):
    if not name.endswith('.jpg'):
        continue
    parts = name[:-4].split('-')
    if len(parts) != 3 or parts[0] not in LAYOUTS or parts[1] not in STYLES or parts[2] not in VIEWS:
        continue
    lid, sid, view = parts
    folder = os.path.join(DST, STYLES[sid])
    os.makedirs(folder, exist_ok=True)
    target = os.path.join(folder, 'Схема %s, %s.jpg' % (LAYOUTS[lid], VIEWS[view]))
    shutil.copy2(os.path.join(SRC, name), target)
    n += 1
print('скопировано', n, 'в', DST)
