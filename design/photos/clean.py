# Очистка фото интерьера от строительных лесов и мусора: LaMa inpainting (локально, на процессоре).
# Запуск: C:\Users\Oleg\.venvs\lama\Scripts\python.exe clean.py [ключи через запятую]
# Маски заданы многоугольниками в координатах превью 750 x 1000 (как на сетке grid-*.jpg), масштабируются сами.
import os
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageOps

SRC = r'C:\Users\Oleg\Desktop\стройка\Внутри'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clean')
LONG = 2000          # длинная сторона для обработки, с запасом для веб-версии 1600
PREVIEW = (750, 1000)

JOBS = {
    'living': ('IMG_20260702_115801.jpg', [
        [(50, 470), (185, 470), (185, 680), (50, 680)],          # левые козлы
        [(150, 495), (355, 495), (355, 530), (150, 530)],        # перекладина
        [(215, 520), (350, 520), (350, 620), (215, 620)],        # правые опоры и коробка
        [(250, 760), (285, 760), (285, 795), (250, 795)],        # предмет на полу
        [(140, 505), (228, 505), (228, 612), (140, 612)],        # оставшаяся доска
    ]),
    'bedroom': ('IMG_20260702_115648.jpg', [
        [(315, 520), (435, 520), (435, 645), (315, 645)],        # куча в углу
        [(195, 612), (340, 612), (340, 655), (195, 655)],        # доска на полу
        [(510, 500), (550, 500), (550, 535), (510, 535)],        # предмет на подоконнике
    ]),
    'terrace': ('IMG_20260702_115831.jpg', [
        [(315, 755), (395, 755), (405, 1000), (285, 1000)],      # лист ОСБ на полу
    ]),
    'room6': ('IMG_20260702_115704.jpg', [
        [(280, 605), (330, 625), (60, 1000), (0, 1000), (0, 910)],  # доски вдоль стены
        [(362, 568), (422, 568), (422, 614), (362, 614)],        # ведро
    ]),
}


def main():
    from simple_lama_inpainting import SimpleLama
    keys = [k for k in sys.argv[1].split(',') if k] if len(sys.argv) > 1 else list(JOBS)
    os.makedirs(OUT, exist_ok=True)
    lama = SimpleLama()
    for key in keys:
        fname, polys = JOBS[key]
        im = ImageOps.exif_transpose(Image.open(os.path.join(SRC, fname))).convert('RGB')
        im.thumbnail((LONG, LONG))
        w, h = im.size
        sx, sy = w / PREVIEW[0], h / PREVIEW[1]
        mask = Image.new('L', (w, h), 0)
        d = ImageDraw.Draw(mask)
        for poly in polys:
            d.polygon([(x * sx, y * sy) for x, y in poly], fill=255)
        mask = mask.filter(ImageFilter.MaxFilter(15))        # расширить маску на несколько пикселей
        res = lama(im, mask)
        res = res.crop((0, 0, w, h))
        res.save(os.path.join(OUT, key + '.jpg'), quality=92)
        # сравнение до и после для проверки глазами
        side = Image.new('RGB', (w * 2 + 20, h), 'white')
        side.paste(im, (0, 0))
        side.paste(res, (w + 20, 0))
        side.thumbnail((1800, 1800))
        side.save(os.path.join(OUT, key + '-compare.jpg'), quality=85)
        print('done', key, im.size, flush=True)


if __name__ == '__main__':
    main()
