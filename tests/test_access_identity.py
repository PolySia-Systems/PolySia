"""Verify signed Access tokens with an ephemeral key and offline public key set."""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.server.http import AccessIdentity, AccessOrigin
from apps.server.store import Workspace
from test_access_origin import request

try:
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    jwt = None


@unittest.skipIf(jwt is None, "Remote mode requires PyJWT and cryptography")
class AccessIdentityTests(unittest.TestCase):
    def test_signed_identity_is_bound_to_issuer_audience_expiry_and_key(self):
        identity = AccessIdentity({"team": "fixture-team", "audience": "a" * 64})
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwks = {"keys": [dict(jwk, kid="fixture", use="sig")]}
        now = int(time.time())
        claims = {"iss": identity.issuer, "aud": [identity.audience], "exp": now + 60,
                  "type": "app", "email": "Owner@example.test"}

        def sign(payload, signing_key=key):
            return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "fixture"})

        with patch.object(identity.keys, "fetch_data", return_value=jwks):
            self.assertEqual(identity.email(sign(claims)), "owner@example.test")
            for change in ({"iss": "https://other.cloudflareaccess.com"}, {"aud": "b" * 64},
                           {"exp": now - 60}, {"nbf": now + 3600}, {"type": "org"},
                           {"email": "person@exämple.test"}):
                with self.subTest(change=change):
                    self.assertIsNone(identity.email(sign(claims | change)))
            self.assertIsNone(identity.email(sign({k: v for k, v in claims.items() if k != "exp"})))
            other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.assertIsNone(identity.email(sign(claims, other_key)))

    @unittest.skipUnless(os.name == "posix", "Linux private Unix socket")
    def test_signed_owner_reopens_stopped_history(self):
        config = {"team": "fixture-team", "audience": "a" * 64}
        host, owner = "example.test", "owner@example.test"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))

        def headers(email):
            claims = {"iss": "https://fixture-team.cloudflareaccess.com", "aud": [config["audience"]],
                      "exp": int(time.time()) + 300, "type": "app", "email": email}
            token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fixture"})
            return {"Host": host, "Cf-Access-Jwt-Assertion": token, "Origin": "https://" + host,
                    "Content-Type": "application/json"}

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            endpoint = folder / "origin.sock"
            (folder / "access.json").write_text(json.dumps(config))
            route = "/api/v1/public-runs/" + "ab" * 16
            saved = None
            for _ in range(2):
                with AccessOrigin(endpoint, host, owner, Workspace(folder / "data.db")) as server, patch.object(
                        server.identity.keys, "fetch_data", return_value={"keys": [dict(jwk, kid="fixture", use="sig")]}):
                    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
                    worker.start()
                    try:
                        trusted, other = headers(owner), headers("another@example.test")
                        if saved is None:
                            body = dict(wallet="0x" + "12" * 20, capital="100", cap="10", name="Owner portfolio")
                            self.assertEqual(request(endpoint, "PUT", route, trusted, json.dumps(body))[0], 200)
                            revision = json.dumps({"revision": 1})
                            self.assertEqual(request(endpoint, "POST", route + "/stop", other, revision)[0], 403)
                            self.assertEqual(request(endpoint, "POST", route + "/stop", trusted, revision)[0], 200)
                        self.assertEqual(request(endpoint, "GET", route + "/export", other)[0], 403)
                        status, exported = request(endpoint, "GET", route + "/export", trusted)
                        self.assertEqual((status, exported["status"], exported["revision"], exported["cash"]),
                                         (200, "stopped", 2, "100"))
                        if saved is not None:
                            self.assertEqual(exported, saved)
                        saved = exported
                    finally:
                        server.shutdown()
                        worker.join()
