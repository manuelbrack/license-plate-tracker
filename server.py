#!/usr/bin/env python3
"""Local, dependency-free photo storage and static server for Plate Atlas."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import unquote, urlsplit
import uuid


STATES = set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
MAX_IMAGE_BYTES = 15 * 1024 * 1024
PHOTO_NAME = re.compile(r'^[A-Z]{2}-[a-f0-9]{32}\.(jpg|png|webp)$')


def atomic_write(path, payload):
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PlateServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root):
        self.root = root.resolve()
        self.photos = self.root / 'data' / 'photos'
        self.photos.mkdir(parents=True, exist_ok=True)
        self.metadata = self.root / 'data' / 'plates.json'
        self.lock = threading.Lock()
        self.plates = json.loads(self.metadata.read_text()) if self.metadata.exists() else {}
        if not isinstance(self.plates, dict) or any(
            code not in STATES or not isinstance(item, dict)
            or not isinstance(item.get('url'), str)
            or not item['url'].startswith('/photos/')
            or not PHOTO_NAME.fullmatch(item['url'][8:])
            for code, item in self.plates.items()
        ):
            raise ValueError('Invalid data/plates.json; restore a backup before starting.')
        super().__init__(address, Handler)

    def save(self, plates):
        atomic_write(self.metadata, json.dumps(plates, sort_keys=True).encode())
        self.plates = plates


class Handler(BaseHTTPRequestHandler):
    server_version = 'PlateAtlas/1.0'

    def log_message(self, format, *args):
        # Avoid writing request paths or photo names to logs.
        pass

    def respond(self, status, body, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'same-origin')
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def error(self, status, message):
        self.respond(status, json.dumps({'error': message}).encode())

    def send_error(self, code, message=None, explain=None):
        self.error(code, message or self.responses.get(code, ('Request failed',))[0])

    def allowed(self, mutation=False):
        host = self.headers.get('Host', '')
        permitted = {'127.0.0.1:' + str(self.server.server_port),
                     'localhost:' + str(self.server.server_port)}
        if host not in permitted:
            self.error(403, 'Only local requests are allowed.')
            return False
        if mutation:
            origin = self.headers.get('Origin')
            if origin is not None and origin != 'http://' + host:
                self.error(403, 'The request must come from this app.')
                return False
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.error(403, 'The request must come from this app.')
                return False
        return True

    def route(self):
        path = unquote(urlsplit(self.path).path)
        if '\x00' in path or '\\' in path or '..' in path.split('/'):
            self.error(400, 'Invalid path.')
            return None
        return path

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.allowed():
            return
        path = self.route()
        if path is None:
            return
        if path == '/api/plates':
            with self.server.lock:
                body = json.dumps(self.server.plates).encode()
            self.respond(200, body)
            return
        if path.startswith('/api/'):
            self.error(404, 'Unknown API endpoint.')
            return
        if path.startswith('/photos/'):
            name = path[8:]
            if not PHOTO_NAME.fullmatch(name):
                self.error(404, 'Photo not found.')
                return
            base = self.server.photos.resolve()
            target = (base / name).resolve()
        else:
            base = (self.server.root / 'dist').resolve()
            target = (base / (path.lstrip('/') or 'index.html')).resolve()
        if base not in target.parents or not target.is_file():
            self.error(404, 'File not found.')
            return
        try:
            payload = target.read_bytes()
        except OSError:
            self.error(404, 'File not found.')
            return
        self.respond(200, payload, mimetypes.guess_type(str(target))[0] or 'application/octet-stream')

    def state_code(self):
        path = self.route()
        if path is None:
            return None
        if not path.startswith('/api/plates/'):
            self.error(404, 'Unknown API endpoint.')
            return None
        code = path[len('/api/plates/'):]
        if code not in STATES:
            self.error(400, 'Choose a valid two-letter US state code.')
            return None
        return code

    def do_PUT(self):
        if not self.allowed(mutation=True):
            return
        code = self.state_code()
        if code is None:
            return
        if self.headers.get('Transfer-Encoding'):
            self.error(400, 'Transfer encoding is not supported.')
            return
        try:
            size = int(self.headers.get('Content-Length', ''))
        except ValueError:
            self.error(411, 'Content-Length is required.')
            return
        if size <= 0 or size > MAX_IMAGE_BYTES:
            self.error(413, 'Choose an image smaller than 15 MB.')
            return
        content_type = self.headers.get('Content-Type', '').split(';')[0].strip()
        extensions = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}
        if content_type not in extensions:
            self.error(415, 'Choose a JPEG, PNG, or WebP image.')
            return
        self.connection.settimeout(30)
        try:
            payload = self.rfile.read(size)
        except (TimeoutError, OSError):
            self.error(408, 'Upload timed out. Please try again.')
            return
        if len(payload) != size:
            self.error(400, 'The image upload was incomplete.')
            return
        valid = {
            'image/jpeg': payload.startswith(b'\xff\xd8\xff') and payload.endswith(b'\xff\xd9'),
            'image/png': payload.startswith(b'\x89PNG\r\n\x1a\n'),
            'image/webp': payload.startswith(b'RIFF') and payload[8:12] == b'WEBP',
        }[content_type]
        if not valid:
            self.error(415, 'The file does not match its image format.')
            return
        filename = code + '-' + uuid.uuid4().hex + '.' + extensions[content_type]
        entry = {'url': '/photos/' + filename, 'updated': datetime.now(timezone.utc).isoformat()}
        with self.server.lock:
            previous = self.server.plates.get(code)
            try:
                atomic_write(self.server.photos / filename, payload)
                self.server.save({**self.server.plates, code: entry})
            except OSError:
                self.error(500, 'Could not save the photo. Check available disk space.')
                return
            if previous:
                self.remove_photo(previous)
        self.respond(200, json.dumps(entry).encode())

    def remove_photo(self, entry):
        try:
            (self.server.photos / entry['url'][8:]).unlink(missing_ok=True)
        except OSError:
            # Metadata is authoritative; an orphan is harmless and preserves data.
            pass

    def do_DELETE(self):
        if not self.allowed(mutation=True):
            return
        code = self.state_code()
        if code is None:
            return
        with self.server.lock:
            previous = self.server.plates.get(code)
            if previous:
                remaining = dict(self.server.plates)
                del remaining[code]
                try:
                    self.server.save(remaining)
                except OSError:
                    self.error(500, 'Could not remove the photo. Please try again.')
                    return
                self.remove_photo(previous)
        self.respond(200, b'{"ok": true}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5173)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    server = PlateServer(('127.0.0.1', args.port), args.root)
    print('http://127.0.0.1:' + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
