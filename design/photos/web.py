# Веб-версии фотографий и рендеров для v3: python web.py
# Источники: оригиналы съёмки 02.07.2026, очищенные кадры из clean/, рендеры Blender.
import os
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # my-project
DRONE = r'C:\Users\Oleg\Desktop\стройка\С коптера'
INSIDE = r'C:\Users\Oleg\Desktop\стройка\Внутри'
CLEAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clean')
REND = os.path.join(ROOT, 'design', 'interior', 'blender', 'renders')
EXT = os.path.join(ROOT, 'design', 'interior', 'blender', 'renders-ext')
OUT = os.path.join(ROOT, 'v3', 'img')

JOBS = [
    # (источник, имя, ширины, качество)
    (os.path.join(DRONE, 'DJI_20260702122846_0514_D.JPG'), 'hero', (2400, 1400, 900), 82),
    (os.path.join(DRONE, 'DJI_20260702122328_0504_D.JPG'), 'ext-side', (1600, 800), 82),
    (os.path.join(DRONE, 'DJI_20260702122857_0515_D.JPG'), 'ext-front', (1600, 800), 82),
    (os.path.join(DRONE, 'DJI_20260702122642_0511_D.JPG'), 'ext-close', (1600, 800), 82),
    (os.path.join(DRONE, 'DJI_20260702123354_0520_D.JPG'), 'ext-top', (1600, 800), 82),
    (os.path.join(DRONE, 'DJI_20260702122952_0517_D.JPG'), 'ext-terrace-top', (1600, 800), 82),
    (os.path.join(DRONE, 'DJI_20260702124537_0530_D.JPG'), 'taiga', (2200, 1100), 78),
    (os.path.join(CLEAN, 'living.jpg'), 'living', (1200, 600), 82),
    (os.path.join(CLEAN, 'bedroom.jpg'), 'bedroom', (1200, 600), 82),
    (os.path.join(INSIDE, 'IMG_20260702_115752.jpg'), 'room', (1200, 600), 82),
    (os.path.join(INSIDE, 'IMG_20260702_115633.jpg'), 'hall', (1200, 600), 82),
    (os.path.join(INSIDE, 'IMG_20260702_115818.jpg'), 'doors', (1200, 600), 82),
    (os.path.join(INSIDE, 'IMG_20260702_115839.jpg'), 'terrace', (1200, 600), 82),
    (os.path.join(INSIDE, 'IMG_20260702_115835.jpg'), 'terrace-view', (1200, 600), 82),
    (os.path.join(REND, 'a-nord-plan.jpg'), 'plan', (1200,), 85),
    (os.path.join(REND, 'a-nord-axo.jpg'), 'axo', (1400,), 85),
    (os.path.join(REND, 'a-nord-bed3.jpg'), 'room-bed', (1200,), 82),
    (os.path.join(REND, 'a-nord-kitchen.jpg'), 'room-kitchen', (1200,), 82),
    (os.path.join(REND, 'a-nord-terrace.jpg'), 'room-terrace', (1200,), 82),
]
for st in ('nord', 'japandi', 'graphite', 'greige', 'baroque', 'loft', 'midcentury'):
    JOBS.append((os.path.join(REND, 'a-%s-kh.jpg' % st), 'style-' + st, (1200,), 82))
for key in ('built', 'dark', 'plaster', 'wood', 'brick', 'built-evening'):
    JOBS.append((os.path.join(EXT, key + '.jpg'), 'facade-' + key, (1600, 800), 84))
for k in range(24):
    JOBS.append((os.path.join(EXT, 'turn-%02d.png' % k), 'turn-%02d' % k, (1200, 800), 80))


def main():
    os.makedirs(OUT, exist_ok=True)
    made, missing = 0, []
    for src, name, widths, q in JOBS:
        if not os.path.exists(src):
            missing.append(name)
            continue
        im = ImageOps.exif_transpose(Image.open(src))
        alpha = im.mode in ('RGBA', 'LA')
        im = im.convert('RGBA' if alpha else 'RGB')
        for w in widths:
            t = im.copy()
            if t.width > w:
                t = t.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            if alpha:
                t.save(os.path.join(OUT, '%s-%d.webp' % (name, w)), 'WEBP', quality=q, method=6)
            else:
                t.save(os.path.join(OUT, '%s-%d.jpg' % (name, w)), quality=q, optimize=True, progressive=True)
            made += 1
    print('made', made, 'files; missing sources:', ', '.join(missing) or 'none')


if __name__ == '__main__':
    main()
