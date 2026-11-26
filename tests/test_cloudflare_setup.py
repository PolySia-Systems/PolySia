"""Controlled contracts for resumable deployment and owner-only ingress."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from deploy.cloudflare_setup import (
    Journal, applies, configure_ingress, disconnected, hostname, owner_email, verify_app, verify_policy,
)


class ConfigAPI:
    def __init__(self):
        self.ingress = []
        self.writes = 0

    def request(self, method, path, body=None, missing=False):
        if method == "PUT":
            self.writes += 1
            self.ingress = body["config"]["ingress"]
        return {"result": {"config": {"ingress": self.ingress}}}


class DeploymentTests(unittest.TestCase):
    def test_fields_and_existing_path_application(self):
        self.assertEqual(hostname("https://APP.Example.com/"), "app.example.com")
        self.assertEqual(owner_email(" Owner@Example.com "), "owner@example.com")
        for value in ("app.example.com/private", "user@app.example.com", "app.example.com:443"):
            with self.assertRaises(ValueError):
                hostname(value)
        app = {"destinations": [{"type": "public", "uri": "*.example.com/admin"}]}
        self.assertTrue(applies(app, "app.example.com"))
        self.assertFalse(applies(app, "unrelated.test"))

    def test_only_one_identity_and_hostname(self):
        row = {"type": "self_hosted", "name": "ours", "domain": "app.example.com", "aud": "a" * 64,
               "allowed_idps": ["otp"], "destinations": [{"type": "public", "uri": "app.example.com"}]}
        verify_app(row, "app.example.com", "otp", "ours")
        with self.assertRaises(ValueError):
            verify_app({**row, "self_hosted_domains": ["more.example.com"]}, "app.example.com", "otp", "ours")
        policy = {"name": "ours", "decision": "allow", "include": [{"email": {"email": "owner@example.com"}}]}
        verify_policy(policy, "owner@example.com", "ours")
        for changed in ({"decision": "bypass"}, {"include": policy["include"] + [{"everyone": {}}]}):
            with self.assertRaises(ValueError):
                verify_policy({**policy, **changed}, "owner@example.com", "ours")

    def test_uncertain_create_recovers_exact_record_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            j = Journal(path, "app.example.com", "owner@example.com")
            row = {"id": "a" * 32, "comment": j.state["marker"]}
            api = Mock()
            owned = lambda r: r.get("comment") == j.state["marker"]
            j.ensure(api, "dns", "/dns", [row], owned, {})
            again = Journal(path, "app.example.com", "owner@example.com")
            self.assertEqual(again.state["dns"], row["id"])
            for conflicting in ([], [row, row], [{**row, "id": "b" * 32}], [{**row, "comment": "other"}]):
                with self.assertRaises(ValueError):
                    again.ensure(api, "dns", "/dns", conflicting, owned, {})
            api.request.assert_not_called()
            with self.assertRaises(ValueError):
                Journal(path, "app.example.com", "other@example.com")

    def test_ingress_is_nonrouting_until_proof_and_audited_before_retry(self):
        api = ConfigAPI()
        inputs = (api, "/config", "app.example.com", "/private/origin.sock")
        configure_ingress(*inputs, None, "audience", False)
        self.assertEqual(api.writes, 0)
        api.ingress = [{"service": "http://localhost:8765"}]
        with self.assertRaises(ValueError):
            configure_ingress(*inputs, None, "audience", False)
        api.ingress = []
        configure_ingress(*inputs, "team", "audience", False)
        api.ingress[-1]["originRequest"] = {}
        configure_ingress(*inputs, "team", "audience", True)
        self.assertEqual(api.writes, 1)
        api.ingress[0]["originRequest"]["access"]["required"] = False
        with self.assertRaises(ValueError):
            configure_ingress(*inputs, "team", "audience", True)
        self.assertEqual(api.writes, 1)

    def test_active_connectors_block_publication(self):
        api = Mock()
        api.request.side_effect = [
            {"result": {"status": "down", "connections": []}}, {"result": [{"id": "another"}]},
        ]
        with self.assertRaises(ValueError):
            disconnected(api, "/tunnel")
