"""Export integration checks: repository uploads must survive interface builds."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from export_static import export_site

class StaticExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); project=Path(__file__).parent
        for folder in ['dist','site']:
            shutil.copytree(project/folder,self.root/folder)
        shutil.copyfile(project/'MAP-LICENSE.txt',self.root/'MAP-LICENSE.txt')
        self.photos=self.root/'data'/'photos';self.photos.mkdir(parents=True)
        self.output=self.root/'docs'
    def entries(self,data):
        (self.root/'data'/'plates.json').write_text(json.dumps(data))
    def test_bootstrap_and_rebuild_preserve_remote_collection_and_encrypted_config(self):
        (self.photos/'wa.jpg').write_bytes(b'original photo')
        self.entries({'WA':{'url':'/photos/wa.jpg'}})
        self.assertEqual(export_site(self.root),1)
        manifest=json.loads((self.output/'collection.json').read_text())
        self.assertEqual(manifest['plates']['WA']['url'],'photos/WA.jpg')
        (self.output/'photos'/'CA-new.jpg').write_bytes(b'browser upload')
        manifest['plates']['CA']={'url':'photos/CA-new.jpg'}
        manifest['revision']='browser-revision'
        serialized=json.dumps(manifest)
        (self.output/'collection.json').write_text(serialized)
        (self.output/'upload-config.json').write_text('{"ciphertext":"encrypted"}')
        self.entries({})
        self.assertEqual(export_site(self.root),2)
        self.assertEqual((self.output/'collection.json').read_text(),serialized)
        self.assertEqual((self.output/'photos'/'CA-new.jpg').read_bytes(),b'browser upload')
        self.assertEqual((self.output/'upload-config.json').read_text(),'{"ciphertext":"encrypted"}')
        html=(self.output/'index.html').read_text()
        self.assertIn('href="./"',html)
        self.assertIn('id="unlock-passphrase"',html)
        self.assertIn('.heic,.heif',html)
        self.assertIn('id="publish-banner"',html)
        for script in ['app.js','data.js','github-client.js','photo-convert.js']:
            self.assertTrue((self.output/script).is_file())
    def test_invalid_or_missing_photo_fails_before_writing(self):
        for url in ['/photos/../../personal.jpg','/photos/missing.jpg']:
            with self.subTest(url=url):
                self.entries({'WA':{'url':url}})
                with self.assertRaises(ValueError):export_site(self.root)
                self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
