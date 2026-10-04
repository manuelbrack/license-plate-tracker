import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from http.server import HTTPServer

import setup_upload as setup


def envelope():
    encode = lambda value: base64.b64encode(value).decode("ascii")
    return {"version": 1, "kdf": "PBKDF2-SHA256", "iterations": 600000,
            "salt": encode(b"s" * 16), "iv": encode(b"i" * 12), "ciphertext": encode(b"c" * 80)}


class SetupServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "docs").mkdir()

        def persist(root, encrypted):
            setup.write_config(root, encrypted)
            return "Published encrypted credential."

        self.publisher = Mock(side_effect=persist)
        self.server = HTTPServer(("127.0.0.1", 0), setup.make_handler(self.root, self.publisher))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, method="POST", path="/config", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        request_headers = {"Host": self.host, "Origin": "http://" + self.host, "Content-Type": "application/json"}
        request_headers.update(headers or {})
        for key in [key for key, value in request_headers.items() if value is None]:
            del request_headers[key]
        connection.request(method, path, body=json.dumps(envelope() if body is None else body), headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        connection.close()
        return result

    def assert_not_written(self):
        self.publisher.assert_not_called()
        self.assertFalse((self.root / setup.CONFIG).exists())

    def test_host_origin_and_content_type_rejected_without_writes(self):
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"}, {"Origin": None}, {"Origin": "null"}, {"Content-Type": "text/plain"}):
            with self.subTest(headers=headers):
                self.assertIn(self.request(headers=headers)[0], (400, 403))
                self.assert_not_written()

    def test_invalid_envelopes_and_plaintext_rejected(self):
        cases = [dict(envelope(), token="github_pat_should_never_be_saved"),
                 dict(envelope(), passphrase="never send plaintext"),
                 dict(envelope(), iterations=1), dict(envelope(), version=True),
                 dict(envelope(), salt="bad"), dict(envelope(), iv=base64.b64encode(b"x" * 16).decode()),
                 dict(envelope(), ciphertext="A" * 23000), [], None]
        for value in cases:
            if value is None:
                value = {"token": "plaintext"}
            with self.subTest(value=value):
                self.assertEqual(self.request(body=value)[0], 400)
                self.assert_not_written()
        self.assertEqual(self.request(body={"ciphertext": "x" * 33000})[0], 413)
        self.assert_not_written()

    def test_valid_envelope_persists_only_encrypted_fields(self):
        value = envelope()
        status, headers, _ = self.request(body=value)
        self.assertEqual(status, 200)
        self.publisher.assert_called_once_with(self.root, value)
        self.assertEqual(json.loads((self.root / setup.CONFIG).read_text()), value)
        self.assertEqual(list((self.root / "docs").iterdir()), [self.root / setup.CONFIG])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_only_setup_files_are_served(self):
        for path in ("/docs/upload-config.json", "/.git/config", "/../README.md", "/config"):
            self.assertEqual(self.request(method="GET", path=path)[0], 404)
        self.assert_not_written()

    def test_publishing_error_reports_no_credentials(self):
        self.publisher.side_effect = setup.SetupError("Commit existing project changes first.")
        status, _, body = self.request()
        self.assertEqual(status, 409)
        self.assertIn(b"Commit existing", body)
        self.assertFalse((self.root / setup.CONFIG).exists())


class PublishingTests(unittest.TestCase):
    def test_wrong_branch_and_dirty_work_fail_before_write(self):
        for outputs in (["another-branch"], [setup.BRANCH, " M README.md"]):
            with self.subTest(outputs=outputs), patch.object(setup, "git", side_effect=outputs), patch.object(setup, "write_config") as write:
                with self.assertRaises(setup.SetupError):
                    setup.publish_config(Path("/unused"), envelope())
                write.assert_not_called()

    def test_fetch_and_fast_forward_precede_atomic_config_only_commit(self):
        calls = []

        def fake_git(root, *args):
            calls.append(args)
            if args == ("branch", "--show-current"):
                return setup.BRANCH
            if args[:3] == ("diff", "--cached", "--name-only"):
                return setup.CONFIG
            return ""

        def fake_write(root, value):
            self.assertIn(("fetch", "personal", setup.BRANCH), calls)
            self.assertIn(("merge", "--ff-only", "FETCH_HEAD"), calls)
            calls.append(("WRITE",))

        with patch.object(setup, "git", side_effect=fake_git), patch.object(setup, "write_config", side_effect=fake_write):
            setup.publish_config(Path("/unused"), envelope())
        self.assertIn(("add", "--", setup.CONFIG), calls)
        self.assertIn(("commit", "-m", "Enable encrypted browser uploads", "--", setup.CONFIG), calls)
        self.assertEqual(calls[-1], ("push", "personal", "HEAD:" + setup.BRANCH))

    def test_noop_does_not_commit_and_push_failure_explains_local_state(self):
        calls = []

        def fake_git(root, *args):
            calls.append(args)
            if args == ("branch", "--show-current"):
                return setup.BRANCH
            if args[0] == "push":
                raise setup.SetupError("generic failure")
            return ""

        with patch.object(setup, "git", side_effect=fake_git), patch.object(setup, "write_config") as write:
            with self.assertRaisesRegex(setup.SetupError, "saved locally"):
                setup.publish_config(Path("/unused"), envelope())
        write.assert_called_once()
        self.assertFalse(any(call[0] == "commit" for call in calls))


if __name__ == "__main__":
    unittest.main()
