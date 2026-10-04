#!/usr/bin/env python3
"""Loopback-only credential setup; only encrypted credentials reach Python."""
import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parent
BRANCH = "feat/plate-tracker"
CONFIG = "docs/upload-config.json"
MAX_BODY = 32768


class SetupError(Exception):
    pass


def validate_envelope(value):
    expected = {"version", "kdf", "iterations", "salt", "iv", "ciphertext"}
    if not isinstance(value, dict) or set(value) != expected:
        raise SetupError("Invalid encrypted credential format.")
    if type(value["version"]) is not int or value["version"] != 1 or value["kdf"] != "PBKDF2-SHA256" or type(value["iterations"]) is not int or value["iterations"] != 600000:
        raise SetupError("Unsupported credential encryption settings.")
    for field, minimum, maximum in (("salt", 16, 16), ("iv", 12, 12), ("ciphertext", 17, 16400)):
        encoded = value[field]
        if not isinstance(encoded, str) or len(encoded) > 22000:
            raise SetupError("Invalid encrypted credential encoding.")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise SetupError("Invalid encrypted credential encoding.") from None
        if not minimum <= len(decoded) <= maximum or base64.b64encode(decoded).decode("ascii") != encoded:
            raise SetupError("Invalid encrypted credential length.")
    return value


def git(root, *args):
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError("The Git operation could not finish. Check your GitHub connection and try again.") from None
    if result.returncode:
        raise SetupError("The Git operation failed. Check the repository and GitHub connection, then try again.")
    return result.stdout.strip()


def write_config(root, envelope):
    """Atomic write of ciphertext only. Caller must complete repository checks first."""
    destination = root / CONFIG
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, prefix=".upload-config-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(envelope, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def publish_config(root, envelope):
    validate_envelope(envelope)
    if git(root, "branch", "--show-current") != BRANCH:
        raise SetupError("Switch this project to feat/plate-tracker before enabling uploads.")
    if git(root, "status", "--porcelain"):
        raise SetupError("Commit or resolve existing project changes before enabling uploads.")
    git(root, "fetch", "personal", BRANCH)
    git(root, "merge", "--ff-only", "FETCH_HEAD")
    if git(root, "status", "--porcelain"):
        raise SetupError("The project contains changes. Resolve them before enabling uploads.")
    write_config(root, envelope)
    git(root, "add", "--", CONFIG)
    if git(root, "diff", "--cached", "--name-only", "--", CONFIG):
        git(root, "commit", "-m", "Enable encrypted browser uploads", "--", CONFIG)
    try:
        git(root, "push", "personal", "HEAD:" + BRANCH)
    except SetupError:
        raise SetupError("The encrypted credential is saved locally, but publishing failed. Check the connection, then retry. If the remote collection changed, reconcile the branch before retrying.") from None
    return "Encrypted credential published. GitHub Pages will update shortly. Keep the passphrase somewhere safe."


def make_handler(root=ROOT, publisher=publish_config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            # Request bodies and credentials must never enter logs.
            pass

        def allowed_host(self):
            port = self.server.server_port
            return self.headers.get_all("Host") in ([f"127.0.0.1:{port}"], [f"localhost:{port}"])

        def reply(self, status, body, content_type="application/json; charset=utf-8"):
            payload = body if isinstance(body, bytes) else json.dumps({"message": body}).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' https://api.github.com; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if not self.allowed_host():
                self.reply(403, "Invalid local host.")
                return
            routes = {
                "/": ("tools/token-setup.html", "text/html; charset=utf-8"),
                "/token-setup.js": ("tools/token-setup.js", "text/javascript; charset=utf-8"),
                "/token-setup.css": ("tools/token-setup.css", "text/css; charset=utf-8"),
                "/github-client.js": ("site/github-client.js", "text/javascript; charset=utf-8"),
            }
            if self.path not in routes:
                self.reply(404, "Not found.")
                return
            relative, mime = routes[self.path]
            try:
                body = (root / relative).read_bytes()
            except OSError:
                self.reply(500, "The local setup files are missing.")
                return
            self.reply(200, body, mime)

        def do_POST(self):
            if not self.allowed_host() or self.headers.get_all("Origin") != ["http://" + self.headers.get("Host", "")]:
                self.reply(403, "Requests must come from this local setup page.")
                return
            if self.path != "/config":
                self.reply(404, "Not found.")
                return
            if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                self.reply(400, "Send an encrypted JSON credential.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError()
            except ValueError:
                self.reply(413, "The encrypted credential request is too large or empty.")
                return
            try:
                self.connection.settimeout(10)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError()
                envelope = validate_envelope(json.loads(body))
            except (ValueError, UnicodeError, OSError, SetupError):
                self.reply(400, "Invalid encrypted credential. Nothing was published.")
                return
            try:
                message = publisher(root, envelope)
            except SetupError as error:
                self.reply(409, str(error))
                return
            except Exception:
                self.reply(500, "Setup could not finish. Check the local repository before retrying.")
                return
            self.reply(200, message)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5175)
    args = parser.parse_args()
    with HTTPServer(("127.0.0.1", args.port), make_handler()) as server:
        print(f"Open http://127.0.0.1:{server.server_port} to enable uploads. Ctrl-C stops setup.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
