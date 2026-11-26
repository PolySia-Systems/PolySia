"""Verify signed Access tokens with an ephemeral key and offline public key set."""
import json
import time
import unittest
from unittest.mock import patch

from apps.server.http import AccessIdentity

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
        claims = {"iss": identity.issuer, "aud": identity.audience, "exp": now + 60, "email": "Owner@example.test"}

        def sign(payload, signing_key=key):
            return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "fixture"})

        with patch.object(identity.keys, "fetch_data", return_value=jwks):
            self.assertEqual(identity.email(sign(claims)), "owner@example.test")
            for change in ({"iss": "https://other.cloudflareaccess.com"}, {"aud": "b" * 64},
                           {"exp": now - 60}, {"nbf": now + 3600}):
                with self.subTest(change=change):
                    self.assertIsNone(identity.email(sign(claims | change)))
            self.assertIsNone(identity.email(sign({k: v for k, v in claims.items() if k != "exp"})))
            other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.assertIsNone(identity.email(sign(claims, other_key)))
