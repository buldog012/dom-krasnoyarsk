#!/usr/bin/env bash
# Пакетный рендер: все стили и схемы. Готовые картинки пропускаются, прогон можно прерывать.
# Запуск из Git Bash: bash render_all.sh
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
cd "$(dirname "$0")" || exit 1
OUT=renders
SAMPLES=${SAMPLES:-64}
STYLES="nord japandi graphite greige baroque loft midcentury"
run() {
  "$B" -b --factory-startup --python build_house.py -- --layout "$1" --style "$2" --views "$3" \
       --out "$OUT" --samples "$SAMPLES" --res 1440x960 >> render.log 2>&1
  grep -E "RENDERED|Traceback|Error:" render.log | tail -n 6 > /dev/null
}
echo "START $(date)" >> render.log
# 1. Схема А: план, аксонометрия и четыре интерьера в каждом стиле
for st in $STYLES; do run 0 "$st" plan,axo,kh,kitchen,bed3,terrace; done
# 2. Схемы Б, В, Г: план, аксонометрия и кухня-зал в каждом стиле
for l in 1 2 3; do for st in $STYLES; do run "$l" "$st" plan,axo,kh; done; done
echo "ALLDONE $(date)" >> render.log
