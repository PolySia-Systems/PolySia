"""Verify the boundary between a validating connector and its OS-private origin."""
import json
import os
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.client import HTTPConnection
from pathlib import Path

from apps.server.http import AccessOrigin
from apps.server.store import Workspace


def request(endpoint, method, path, headers, body=None):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.connect(str(endpoint))
        conn = HTTPConnection("localhost")
        conn.sock = sock
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        return res.status, json.loads(res.read())


@unittest.skipUnless(os.name == "posix", "Linux private Unix socket")
class AccessOriginTests(unittest.TestCase):
    def test_origin_identity_and_browser_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            endpoint = folder / "origin.sock"
            host, owner = "example.test", "owner@example.test"
            store = Workspace(folder / "workspace.sqlite3")
            (folder / "access.json").write_text("{}")
            verifier = patch("apps.server.http.AccessIdentity")
            verifier.start().return_value.email.side_effect = lambda token: token.removeprefix("verified:")
            self.addCleanup(verifier.stop)
            with AccessOrigin(endpoint, host, owner, store, artifact_sha256="candidate") as server:
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                self.addCleanup(worker.join, 2)
                try:
                    def headers(email):
                        return {"Host": host, "Cf-Access-Jwt-Assertion": "verified:" + email}

                    self.assertEqual(request(endpoint, "GET", "/api/v1/workspace", {"Host": host})[0], 403)
                    self.assertEqual(request(endpoint, "GET", "/api/v1/workspace", headers("other@example.test"))[0], 403)
                    owner_headers = headers(owner)
                    self.assertEqual(request(endpoint, "GET", "/api/v1/health", owner_headers)[1]["artifactSha256"], "candidate")
                    self.assertEqual(request(endpoint, "GET", "/api/v1/workspace", {**owner_headers, "Host": "else.test"})[0], 403)
                    settings = request(endpoint, "GET", "/api/v1/workspace", owner_headers)[1]["settings"]
                    settings["theme"] = "dark"
                    for origin in ({}, {"Origin": "https://other.test"}, {"Origin": "null"}):
                        self.assertEqual(request(endpoint, "PUT", "/api/v1/settings", {**owner_headers, **origin},
                                                 json.dumps(settings))[0], 403)
                    status, result = request(endpoint, "PUT", "/api/v1/settings",
                                             {**owner_headers, "Origin": "https://" + host,
                                              "Content-Type": "application/json"}, json.dumps(settings))
                    self.assertEqual((status, result["theme"]), (200, "dark"))
                finally:
                    server.shutdown()
            folder.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "0700"):
                AccessOrigin(endpoint, host, owner, store)
