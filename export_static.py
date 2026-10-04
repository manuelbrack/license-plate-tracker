"""Export the local collection as a standalone, read-only GitHub Pages site.

Run: python3 export_static.py (output defaults to docs/).
Only Python's standard library is required. No server, CDN, or API is used by
this export; even the map data is embedded so index.html also works offline.
"""
import argparse
import ast
import json
from pathlib import Path
import re
import shutil


STATIC_JS = r'''
const $ = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
function svgElement(tag, attrs = {}) {
  const el = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}
function openState(code) {
  const entry = PLATES[code];
  if (!entry) return;
  const name = STATES.find(state => state[0] === code)[1];
  $('dialog-title').textContent = name;
  $('dialog-code').textContent = `${code} · COLLECTED`;
  const img = document.createElement('img');
  img.src = entry.url; img.alt = `${name} license plate photo`;
  $('photo-stage').replaceChildren(img);
  $('dialog-status').textContent = 'A little piece of Joleen’s journey.';
  $('photo-dialog').showModal();
}
$('close-dialog').onclick = () => $('photo-dialog').close();
$('photo-dialog').addEventListener('click', event => {
  if (event.target !== $('photo-dialog')) return;
  const r = event.target.getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close();
});
for (const [index, [code, name]] of STATES.entries()) {
  const entry = PLATES[code];
  const card = document.createElement(entry ? 'button' : 'div');
  card.className = 'state-card' + (entry ? ' collected' : '');
  card.setAttribute('aria-label', `${name}, ${entry ? 'collected. View photo' : 'not collected'}`);
  if (entry) card.onclick = () => openState(code);
  const plate = document.createElement('div'); plate.className = 'plate';
  if (entry) {
    const img = document.createElement('img'); img.src = entry.url;
    img.alt = `${name} license plate`; img.loading = 'lazy'; plate.append(img);
    const badge = document.createElement('span'); badge.className = 'check-badge';
    badge.textContent = '✓'; plate.append(badge);
  } else {
    const abbr = document.createElement('span'); abbr.className = 'plate-abbr';
    abbr.textContent = code; plate.append(abbr);
  }
  const label = document.createElement('div'); label.className = 'card-label';
  const stateName = document.createElement('span'); stateName.className = 'state-name'; stateName.textContent = name;
  const number = document.createElement('span'); number.className = 'state-number'; number.textContent = String(index + 1).padStart(2, '0');
  label.append(stateName, number); card.append(plate, label); $('grid').append(card);
}
const count = Object.keys(PLATES).length;
$('count').textContent = count;
$('percent').textContent = `${count * 2}%`;
$('progress-fill').style.width = `${count * 2}%`;
document.querySelector('[role=progressbar]').setAttribute('aria-valuenow', count);
$('progress-caption').textContent = count === 50 ? 'All fifty. What a collection.' : `${50 - count} states still out there. The adventure continues.`;
let mapLoaded = false;
function setView(view) {
  const map = view === 'map';
  $('grid').hidden = map; $('map-view').hidden = !map;
  $('grid-toggle').setAttribute('aria-pressed', !map); $('map-toggle').setAttribute('aria-pressed', map);
  $('view-caption').textContent = map ? 'JOLEEN’S FINDS, COAST TO COAST' : 'ALL 50 STATES · A–Z';
  if (map && !mapLoaded) { loadMap(); mapLoaded = true; }
}
$('grid-toggle').onclick = () => setView('grid');
$('map-toggle').onclick = () => setView('map');
function loadMap() {
  const decoded = TOPOLOGY.arcs.map(arc => {
    let x = 0, y = 0;
    return arc.map(([dx, dy]) => {
      x += dx; y += dy;
      return [x * TOPOLOGY.transform.scale[0] + TOPOLOGY.transform.translate[0], y * TOPOLOGY.transform.scale[1] + TOPOLOGY.transform.translate[1]];
    });
  });
  const ringPath = ring => {
    const points = ring.flatMap(index => index < 0 ? [...decoded[~index]].reverse() : decoded[index]);
    return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join('') + 'Z';
  };
  const svg = svgElement('svg', {viewBox: '0 0 975 610', role: 'group', 'aria-label': 'Interactive map of the fifty US states'});
  for (const geometry of TOPOLOGY.objects.states.geometries) {
    const state = STATES.find(state => Number(state[2]) === Number(geometry.id));
    if (!state) continue;
    const [code, name] = state, collected = !!PLATES[code];
    const polygons = geometry.type === 'Polygon' ? [geometry.arcs] : geometry.arcs;
    const path = svgElement('path', {
      d: polygons.flatMap(poly => poly.map(ringPath)).join(''),
      class: 'map-state' + (collected ? ' collected' : ''),
      role: collected ? 'button' : 'img', 'data-state': code,
      'aria-label': `${name}, ${collected ? 'collected, view photo' : 'not collected'}`
    });
    const title = svgElement('title'); title.textContent = name; path.append(title);
    const hint = () => $('map-hint').textContent = `${name} · ${collected ? 'Collected — view photo' : 'Still looking'}`;
    path.addEventListener('mouseenter', hint);
    if (collected) {
      path.setAttribute('tabindex', '0');
      path.addEventListener('click', () => openState(code)); path.addEventListener('focus', hint);
      path.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openState(code); }
      });
    }
    svg.append(path);
  }
  $('map-container').replaceChildren(svg);
  const small = ['CT', 'DE', 'MD', 'MA', 'NH', 'NJ', 'RI', 'VT'];
  for (const path of svg.querySelectorAll('path')) {
    const code = path.dataset.state;
    if (small.includes(code)) continue;
    const box = path.getBBox();
    const label = svgElement('text', {x: box.x + box.width / 2, y: box.y + box.height / 2 + 4, class: 'map-label' + (PLATES[code] ? ' collected' : ''), 'aria-hidden': 'true'});
    label.textContent = code; svg.append(label);
  }
  for (const [code, name] of STATES.filter(state => small.includes(state[0]))) {
    const button = document.createElement('button'); button.textContent = name;
    button.classList.toggle('collected', !!PLATES[code]); button.disabled = !PLATES[code];
    button.setAttribute('aria-label', `${name}, ${PLATES[code] ? 'collected, view photo' : 'not collected'}`);
    if (PLATES[code]) button.onclick = () => openState(code);
    $('small-states').append(button);
  }
}
'''

STATIC_CSS = '''
/* Read-only collection: uncollected states are passive placeholders. */
.state-card:not(.collected):hover .plate{border-color:#344043;transform:none}
.state-card:not(.collected):hover .plate-abbr{color:#748185}
.map-state:not(.collected){cursor:default}
.map-state:not(.collected):hover{fill:#3b494d;stroke:var(--panel);stroke-width:1.5}
.small-states button:disabled{opacity:1;cursor:default}
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Local template changed; expected one {old!r}')
    return text.replace(old, new, 1)


def export_site(root, output=None):
    root = Path(root).resolve()
    output = Path(output).resolve() if output else root / 'docs'
    dist = root / 'dist'
    source = (dist / 'app.js').read_text()
    match = re.search(r'const STATES = (\[.*?\]);', source, re.S)
    if not match:
        raise ValueError('Could not find state list in local app')
    states = ast.literal_eval(match.group(1))
    codes = {state[0] for state in states}
    if len(states) != 50 or len(codes) != 50:
        raise ValueError('Expected exactly fifty unique states')
    topology = json.loads((dist / 'states-topology.json').read_text())
    entries = json.loads((root / 'data' / 'plates.json').read_text())
    photos = root / 'data' / 'photos'
    plates, copies = {}, []
    for code, entry in entries.items():
        if code not in codes:
            raise ValueError(f'Unknown state: {code}')
        url = entry['url']
        filename = url.removeprefix('/photos/')
        if not url.startswith('/photos/') or Path(filename).name != filename:
            raise ValueError(f'Invalid photo path for {code}')
        photo = photos / filename
        if not photo.is_file() or photo.resolve().parent != photos.resolve():
            raise ValueError(f'Missing or invalid photo for {code}: {filename}')
        # Stable public names avoid publishing local IDs or timestamps.
        public_name = code + photo.suffix.lower()
        copies.append((photo, public_name))
        plates[code] = {'url': 'photos/' + public_name}

    html = (dist / 'index.html').read_text()
    html = replace_once(html, 'href="/"', 'href="./"')
    html = replace_once(html, 'Every plate has a place. Keep the ones you find.', 'Every plate has a place. Every find has a story.')
    html = replace_once(html, 'Select a state to add or view its photo.', 'Select a collected state to view its photo.')
    html = replace_once(html, 'Photos saved on this computer.', 'Joleen’s collection · Shared from the open road.')
    html, count = re.subn(r'<div class="dialog-actions">.*?</dialog>', '</dialog>', html, flags=re.S)
    if count != 1:
        raise ValueError('Local photo dialog changed; review static template')
    # Remove server-only status widgets from the static document.
    html = re.sub(r'<p class="error-banner" id="page-error".*?</p>', '', html)
    html = re.sub(r'<div id="toast".*?</div>', '', html)
    script = '\n'.join('const ' + name + ' = ' + json.dumps(value, separators=(',', ':')) + ';'
                       for name, value in [('STATES', states), ('PLATES', plates), ('TOPOLOGY', topology)]) + '\n' + STATIC_JS
    output.mkdir(parents=True, exist_ok=True)
    photo_output = output / 'photos'
    photo_output.mkdir(exist_ok=True)
    for photo, name in copies:
        shutil.copyfile(photo, photo_output / name)
    # Retired exported photos must not remain publicly accessible after refresh.
    current_names = {name for _, name in copies}
    for old in photo_output.iterdir():
        if old.is_file() and old.name not in current_names:
            old.unlink()
    (output / 'index.html').write_text(html)
    (output / 'app.js').write_text(script)
    (output / 'styles.css').write_text((dist / 'styles.css').read_text() + STATIC_CSS)
    shutil.copyfile(dist / 'favicon.svg', output / 'favicon.svg')
    shutil.copyfile(root / 'MAP-LICENSE.txt', output / 'MAP-LICENSE.txt')
    (output / '.nojekyll').touch()
    return len(plates)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Export directory (default: docs/)')
    args = parser.parse_args()
    count = export_site(Path(__file__).parent, args.output)
    print(f'Exported {count}/50 states to {args.output or Path(__file__).parent / "docs"}')
