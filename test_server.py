"""Real HTTP integration checks; run with python3 -m unittest -v test_server."""
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


JPEG = b'\xff\xd8\xff\xe0test-photo\xff\xd9'


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'dist').mkdir()
        (self.root / 'dist' / 'index.html').write_text('<h1>Plate tracker</h1>')
        (self.root / 'secret.txt').write_text('private')
        self.start()

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name('server.py')),
             '--port', '0', '--root', str(self.root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.url = self.process.stdout.readline().strip()
        self.port = int(self.url.rsplit(':', 1)[1])

    def stop(self):
        self.process.terminate()
        self.process.communicate(timeout=5)

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def upload(self, code='CA', image=JPEG, headers=None):
        return self.request('PUT', '/api/plates/' + code, image,
                            headers or {'Content-Type': 'image/jpeg'})

    def test_upload_replace_restart_and_delete(self):
        self.assertEqual(self.request('GET', '/api/plates'), (200, b'{}'))
        status, body = self.upload()
        self.assertEqual(status, 200)
        first = json.loads(body)
        self.assertIn('updated', first)
        self.assertEqual(self.request('GET', first['url']), (200, JPEG))
        status, body = self.upload(image=JPEG + b'')
        second = json.loads(body)
        self.assertNotEqual(first['url'], second['url'])
        self.assertEqual(self.request('GET', first['url'])[0], 404)
        self.stop()
        self.start()
        self.assertEqual(json.loads(self.request('GET', '/api/plates')[1]), {'CA': second})
        self.assertEqual(self.request('DELETE', '/api/plates/CA')[0], 200)
        self.assertEqual(self.request('GET', second['url'])[0], 404)
        self.assertEqual(self.request('GET', '/api/plates'), (200, b'{}'))

    def test_invalid_uploads_do_not_change_collection(self):
        self.assertEqual(self.upload('XX')[0], 400)
        self.assertEqual(self.upload(image=b'not an image')[0], 415)
        self.assertEqual(self.upload(headers={'Content-Type': 'text/html'})[0], 415)
        self.assertEqual(self.upload(headers={'Content-Type': 'image/jpeg',
                                             'Content-Length': str(15 * 1024 * 1024 + 1)})[0], 413)
        self.assertEqual(self.request('GET', '/api/plates'), (200, b'{}'))

    def test_cross_origin_and_host_guards(self):
        self.assertEqual(self.upload(headers={'Content-Type': 'image/jpeg',
                                             'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('GET', '/api/plates', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.upload(headers={'Content-Type': 'image/jpeg',
                                             'Origin': self.url})[0], 200)
        self.assertEqual(self.request('DELETE', '/api/plates/CA',
                                      headers={'Origin': 'null'})[0], 403)

    def test_static_and_private_paths(self):
        self.assertEqual(self.request('GET', '/')[0], 200)
        for path in ['/../secret.txt', '/%2e%2e/secret.txt', '/photos/../secret.txt',
                     '/data/plates.json', '/server.py', '/api/missing']:
            status, body = self.request('GET', path)
            self.assertIn(status, (400, 404), path)
            self.assertNotIn(b'private', body)


if __name__ == '__main__':
    unittest.main()
