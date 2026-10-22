# Снимает контур с чёрного силуэта на белом фоне и отдаёт SVG-путь.
# C:\Users\Oleg\.venvs\lama\Scripts\python.exe trace_svg.py вход.jpg выход.svg [--flip] [--eps 0.004]
import sys
import cv2
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
flip = '--flip' in sys.argv
eps = float(sys.argv[sys.argv.index('--eps') + 1]) if '--eps' in sys.argv else 0.004
g = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
mask = (g < 128).astype(np.uint8) * 255
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
n, lab, stats, _ = cv2.connectedComponentsWithStats(mask)
big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
mask = (lab == big).astype(np.uint8) * 255
cont, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cont, key=cv2.contourArea)
c = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True).reshape(-1, 2).astype(np.float64)
x0, y0 = c.min(axis=0)
x1, y1 = c.max(axis=0)
w, h = x1 - x0, y1 - y0
scale = 200.0 / w
pts = [((x - x0) * scale, (y - y0) * scale) for x, y in c]
if flip:
    pts = [(200.0 - x, y) for x, y in pts]
vb_h = round(h * scale, 1)
d = 'M' + ' L'.join('%.1f,%.1f' % p for p in pts) + ' Z'
svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 %s"><path d="%s"/></svg>' % (vb_h, d)
open(dst, 'w', encoding='utf-8').write(svg)
print('points', len(pts), 'viewBox 0 0 200', vb_h, 'path chars', len(d))
