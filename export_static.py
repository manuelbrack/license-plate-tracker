"""Build the GitHub Pages interface while preserving its authoritative collection.

Run: python3 export_static.py (output defaults to docs/).
Only Python's standard library is required to build. The hosted browser app
reads collection.json and can upload through GitHub after passphrase unlock.
"""
import argparse
import ast
import json
from pathlib import Path
import re
import shutil


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
    # Once created, the repository manifest is authoritative. Rebuilding the
    # interface must never overwrite browser uploads with stale local data.
    published = root / 'docs'
    manifest_path = published / 'collection.json'
    copies = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        plates = manifest['plates']
        for code, entry in plates.items():
            url = entry.get('url', '')
            if code not in codes or not re.fullmatch(r'photos/[A-Za-z0-9][A-Za-z0-9_-]{0,127}\.(jpg|jpeg|png|webp)', url):
                raise ValueError('Invalid published photo path')
            photo = published / url
            if not photo.is_file():
                raise ValueError('Missing published photo: ' + url)
            copies.append((photo, Path(url).name))
    else:
        entries = json.loads((root / 'data' / 'plates.json').read_text())
        photos = root / 'data' / 'photos'
        plates = {}
        for code, entry in entries.items():
            url = entry['url']
            filename = url.removeprefix('/photos/')
            if code not in codes or not url.startswith('/photos/') or Path(filename).name != filename:
                raise ValueError('Invalid local photo path')
            photo = photos / filename
            if not photo.is_file() or photo.resolve().parent != photos.resolve():
                raise ValueError('Missing or invalid local photo')
            public_name = code + photo.suffix.lower()
            copies.append((photo, public_name))
            plates[code] = {'url': 'photos/' + public_name}
        manifest = {'version': 1, 'revision': 'initial-collection', 'plates': plates}

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
    html = replace_once(html, '<script src="app.js" defer></script>', '<script src="data.js" defer></script><script src="github-client.js" defer></script><script src="photo-convert.js" defer></script><script src="crop-preview.js" defer></script><script src="app.js" defer></script>')
    html = replace_once(html, '<main>', '<main><div id="publish-banner" class="publish-banner" role="status" hidden></div>')
    html = replace_once(html, '<section class="collection"', '<div class="editor-bar"><button id="unlock-editor" class="secondary-button" hidden>Unlock editing</button><div id="editor-controls" hidden><button id="add-find" class="primary-button">Add a find</button><button id="lock-editor" class="secondary-button">Lock editing</button></div></div><p id="collection-error" class="error-banner" role="alert" hidden></p><section class="collection"')
    html = replace_once(html, '<p id="dialog-status" class="dialog-status"></p>', '<p id="dialog-status" class="dialog-status"></p><button id="replace-photo" class="primary-button" hidden>Replace photo</button>')
    html = replace_once(html, '</body>', (root / 'site' / 'upload-dialogs.html').read_text() + '\n</body>')
    html = replace_once(html, 'Joleen’s collection · Shared from the open road.', 'Joleen’s collection · <a href="vendor/README.txt">Image conversion credits</a>')
    script = '\n'.join('const ' + name + ' = ' + json.dumps(value, separators=(',', ':')) + ';'
                       for name, value in [('STATES', states), ('TOPOLOGY', topology)]) + '\n'
    output.mkdir(parents=True, exist_ok=True)
    photo_output = output / 'photos'
    photo_output.mkdir(exist_ok=True)
    for photo, name in copies:
        target = photo_output / name
        if photo.resolve() != target.resolve():
            shutil.copyfile(photo, target)
    if not (output / 'collection.json').exists():
        (output / 'collection.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'index.html').write_text(html)
    (output / 'data.js').write_text(script)
    (output / 'styles.css').write_text((dist / 'styles.css').read_text() + (root / 'site' / 'upload.css').read_text())
    for name in ['app.js', 'github-client.js', 'photo-convert.js', 'crop-preview.js']:
        shutil.copyfile(root / 'site' / name, output / name)
    shutil.copytree(root / 'site' / 'vendor', output / 'vendor', dirs_exist_ok=True)
    config = published / 'upload-config.json'
    if config.exists() and config.resolve() != (output / config.name).resolve():
        shutil.copyfile(config, output / config.name)
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
