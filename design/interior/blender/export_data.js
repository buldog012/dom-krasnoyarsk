// Вынимает данные планировки, мебели и стилей из ../index.html в house.json для Blender.
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const a = html.indexOf('const H = 2.7;');
const b = html.indexOf('const ROLES = Object.keys(ROLE_NAMES);');
if (a < 0 || b < 0) { console.error('маркеры не найдены'); process.exit(1); }
const code = html.slice(a, b) + '\nreturn { H, ROOMS, WALLS, LAYOUTS: LAYOUTS.map(l => ({ id: l.id, name: l.name, desc: l.desc, accents: l.accents, zones: l.zones, spots: l.spots, furn: furnFor(l) })), STYLES, ROLE_NAMES };';
const data = new Function(code)();
fs.writeFileSync(path.join(__dirname, 'house.json'), JSON.stringify(data, null, 1));
console.log('rooms', data.ROOMS.length, 'walls', data.WALLS.length, 'layouts', data.LAYOUTS.map(l => l.id + ':' + l.furn.length).join(' '), 'styles', data.STYLES.map(s => s.id).join(','));
