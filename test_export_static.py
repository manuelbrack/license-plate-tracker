"""Integration checks for the offline, read-only website export."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from export_static import export_site


class StaticExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        project = Path(__file__).parent
        shutil.copytree(project / 'dist', self.root / 'dist')
        shutil.copyfile(project / 'MAP-LICENSE.txt', self.root / 'MAP-LICENSE.txt')
        self.photos = self.root / 'data' / 'photos'
        self.photos.mkdir(parents=True)
        self.output = self.root / 'docs'

    def write_entries(self, entries):
        (self.root / 'data' / 'plates.json').write_text(json.dumps(entries))

    def test_exports_current_photos_and_fifty_states_without_server_or_edit_controls(self):
        photo = b'photo fixture: content must be preserved'
        (self.photos / 'wa-original.jpg').write_bytes(photo)
        (self.photos / 'unused-private.jpg').write_bytes(b'not for export')
        self.write_entries({'WA': {'url': '/photos/wa-original.jpg', 'updated': 'private timestamp'}})
        self.assertEqual(export_site(self.root), 1)
        self.assertEqual((self.output / 'photos' / 'WA.jpg').read_bytes(), photo)
        self.assertEqual([p.name for p in (self.output / 'photos').iterdir()], ['WA.jpg'])
        html = (self.output / 'index.html').read_text()
        script = (self.output / 'app.js').read_text()
        self.assertIn('href="./"', html)
        self.assertIn('id="grid-toggle"', html)
        self.assertIn('id="map-toggle"', html)
        self.assertIn('id="photo-dialog"', html)
        for forbidden in ['upload-button', 'remove-button', 'photo-input', 'type="file"', 'add photo']:
            self.assertNotIn(forbidden, html.lower())
        for forbidden in ['fetch(', '/api/', 'XMLHttpRequest', 'wa-original', 'private timestamp', "method:"]:
            self.assertNotIn(forbidden, script)
        constants = {}
        for line in script.splitlines()[:3]:
            name, value = line.removeprefix('const ').split(' = ', 1)
            constants[name] = json.loads(value.removesuffix(';'))
        self.assertEqual(len(constants['STATES']), 50)
        self.assertEqual([s[1] for s in constants['STATES']], sorted(s[1] for s in constants['STATES']))
        self.assertEqual(constants['PLATES'], {'WA': {'url': 'photos/WA.jpg'}})
        self.assertTrue(constants['TOPOLOGY']['arcs'])
        self.assertTrue((self.output / '.nojekyll').is_file())
        # A later export must remove the old public photo while preserving originals.
        self.write_entries({})
        self.assertEqual(export_site(self.root), 0)
        self.assertFalse((self.output / 'photos' / 'WA.jpg').exists())
        self.assertTrue((self.photos / 'wa-original.jpg').exists())

    def test_invalid_or_missing_photo_fails_before_writing_site(self):
        for url in ['/photos/../../personal.jpg', '/photos/missing.jpg']:
            with self.subTest(url=url):
                self.write_entries({'WA': {'url': url}})
                with self.assertRaises(ValueError):
                    export_site(self.root)
                self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
