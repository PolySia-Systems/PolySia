"""Controlled contracts for resumable deployment and owner-only ingress."""
import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from deploy.cloudflare_setup import (
    LEGACY_SOCKET, SERVICE_SOCKET, discover_tunnel, Journal, UnsafeAccess, setup, login_team, healthy_connector, provision, select_recovery, transfer_token, applies, check_local_service, configure_ingress, disconnected, hostname, owner_email, verify_app, verify_policy,
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
    def test_https_service_user_cannot_have_an_active_or_boot_enabled_local_service(self):
        with patch("deploy.cloudflare_setup.unit_state") as state:
            for load, active, enabled in (("not-found", "inactive", ""), ("loaded", "inactive", "disabled")):
                state.return_value = dict(LoadState=load, ActiveState=active, UnitFileState=enabled)
                check_local_service()
            for active, enabled in (("active", "disabled"), ("inactive", "enabled"), ("activating", "enabled")):
                state.return_value = dict(LoadState="loaded", ActiveState=active, UnitFileState=enabled)
                with self.assertRaisesRegex(ValueError, "Disable and stop"):
                    check_local_service()

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

class RecoveryTests(unittest.TestCase):
    host = "app.example.com"
    owner = "owner@example.com"
    tunnel = "aaaa0000-0000-0000-0000-000000000000"
    marker = "polysia-" + "1" * 32
    app = "a" * 32
    policy = "b" * 32
    dns = "c" * 32
    otp = "d" * 32
    audience = "a" * 64

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.journal = Journal(Path(directory.name) / "deployment.json", self.host, self.owner)
        self.journal.deferred = True
        self.original = self.journal.path.read_bytes()
        self.endpoint = {"id": self.tunnel, "name": self.marker, "remote_config": True}
        self.record = {"id": self.dns, "name": self.host, "type": "CNAME", "comment": self.marker,
                       "proxied": True, "content": self.tunnel + ".cfargotunnel.com"}
        self.api = Mock()
        base = "/accounts/a"
        apps = base + "/access/apps"
        tunnels = base + "/cfd_tunnel"
        records = "/zones/z/dns_records"
        policies = apps + "/" + self.app + "/policies"
        self.inventory = {
            apps: [{"id": self.app, "name": self.marker, "domain": self.host}],
            records: [self.record], tunnels: [self.endpoint],
            base + "/access/identity_providers": [{"id": self.otp, "type": "onetimepin"}],
            policies: [{"id": self.policy, "name": self.marker}],
        }
        config = ConfigAPI()
        configure_ingress(config, "/config", self.host, "/private/origin.sock", "team", self.audience, False)
        self.details = {
            apps + "/" + self.app: {**self.inventory[apps][0], "type": "self_hosted",
                                    "aud": self.audience, "allowed_idps": [self.otp]},
            policies + "/" + self.policy: {**self.inventory[policies][0], "decision": "allow",
                                           "include": [{"email": {"email": self.owner}}]},
            records + "/" + self.dns: self.record, tunnels + "/" + self.tunnel: self.endpoint,
            tunnels + "/" + self.tunnel + "/configurations": {"config": {"ingress": config.ingress}},
        }
        self.api.rows.side_effect = lambda path, **kwargs: self.inventory[path]

        def read(method, path, **kwargs):
            self.assertEqual(method, "GET", "Recovery preflight must be read-only")
            return {"result": self.details[path]}
        self.api.request.side_effect = read

    def recover(self):
        self.journal.state["marker"] = select_recovery(self.api, "/accounts/a", self.tunnel, self.journal)
        with patch("deploy.cloudflare_setup.login_team", return_value="team"):
            return provision(self.api, "/accounts/a", "z", self.host, self.owner, self.journal,
                             "/private/origin.sock", self.tunnel)

    def test_existing_deployment_without_local_history(self):
        self.recover()
        for name in ("app", "policy", "tunnel", "dns"):
            self.assertEqual(self.journal.state[name], getattr(self, name))
        self.assertEqual(self.journal.path.read_bytes(), self.original)

    def test_hostname_pointing_to_an_unmanaged_tunnel_stops_discovery(self):
        self.endpoint["name"] = "another-site"
        with self.assertRaisesRegex(ValueError, "original site hostname and its DNS record"):
            self.recover()
        self.assertEqual(self.journal.path.read_bytes(), self.original)

    def test_rejects_other_target_and_missing_policy_without_binding_prefix(self):
        self.record["content"] = "other.cfargotunnel.com"
        with self.assertRaisesRegex(ValueError, "DNS"):
            self.recover()
        self.record["content"] = self.tunnel + ".cfargotunnel.com"
        self.inventory[next(key for key in self.inventory if key.endswith("/policies"))] = []
        with self.assertRaisesRegex(ValueError, "policy"):
            self.recover()
        self.assertEqual(self.journal.path.read_bytes(), self.original)

    def test_configured_unsafe_owner_policy_is_distinct_from_read_failure(self):
        policy = next(value for key, value in self.details.items() if key.endswith("/" + self.policy))
        policy["decision"] = "bypass"
        with self.assertRaises(UnsafeAccess):
            self.recover()
        self.api.rows.side_effect = OSError("unavailable")
        with self.assertRaises(OSError):
            self.recover()

    def test_transfer_fences_reconnect_and_rechecks_active_connections(self):
        api = Mock()
        status = {"result": {"status": "down"}}
        empty = {"result": []}
        rotated = {"result": {"id": self.tunnel, "token": "test-token"}}
        url = "/tunnels/" + self.tunnel
        api.request.side_effect = [status, empty, rotated, status, empty]
        self.assertEqual(transfer_token(api, url, self.marker), "test-token")
        self.assertEqual([call.args[0] for call in api.request.call_args_list], ["GET", "GET", "PATCH", "GET", "GET"])
        api.request.side_effect = [status, empty, rotated, status, {"result": [{"id": self.tunnel}]}]
        with self.assertRaisesRegex(ValueError, "active connector"):
            transfer_token(api, url, self.marker)

    def test_extra_connector_cannot_report_success(self):
        api = Mock()
        api.request.side_effect = [{"result": [self.endpoint, self.endpoint]}, {"result": {"status": "healthy"}}]
        with self.assertRaisesRegex(ValueError, "one healthy connector"):
            healthy_connector(api, "/tunnels/id")

    def test_metadata_only_rotation_response_requires_our_secret(self):
        url = "/tunnels/" + self.tunnel
        rotation = {}
        def request(method, path, body=None):
            if method == "PATCH":
                rotation.update(body)
                result = {"id": self.tunnel}
            elif path.endswith("/token"):
                payload = {"s": rotation["tunnel_secret"], "t": self.tunnel}
                result = base64.b64encode(json.dumps(payload).encode()).decode()
            elif path.endswith("/connections"):
                result = []
            else:
                result = {"status": "down"}
            return {"result": result}
        self.api.request.side_effect = request
        self.assertTrue(transfer_token(self.api, url, self.marker))

    def test_anonymous_success_withdraws_access(self):
        with patch("deploy.cloudflare_setup.http.client.HTTPSConnection") as connect:
            connect.return_value.getresponse.return_value.status = 200
            with self.assertRaises(UnsafeAccess):
                login_team(self.host)

    @unittest.skipUnless(sys.platform == "linux", "Uses Linux private directory and host identity")
    def test_transfer_then_rerun_and_read_failure_leave_service_running(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory(dir="/tmp") as directory, ExitStack() as stack:
            prefix = Path(directory)
            sock = prefix / "remote/origin.sock"
            config = next(row for row in self.details.values() if "config" in row)
            config["config"]["ingress"][0]["service"] = "unix:" + str(sock)
            active = False
            rotations = []
            calls = []
            token = "test-connector-credential"
            read = self.api.request.side_effect
            def request(method, path, body=None, **kwargs):
                if method == "PATCH":
                    rotations.append(path)
                    return {"result": {"id": self.tunnel, "token": token}}
                if path.endswith("/token"):
                    return {"result": token}
                if path.endswith("/connections"):
                    return {"result": [{"id": self.tunnel}] if active else []}
                if path.endswith(self.tunnel):
                    return {"result": {**self.endpoint, "status": "healthy" if active else "down"}}
                return read(method, path, **kwargs)

            def service(*args):
                nonlocal active
                calls.append(args)
                if args[-1] == "polysia-tunnel.service" and args[2] in ("disable", "start", "stop"):
                    active = args[2] == "start"
                if args[2] == "restart":
                    (prefix / "data").mkdir(exist_ok=True)
                    (prefix / "data/workspace.sqlite3").write_bytes(b"test workspace")

            self.api.request.side_effect = request
            def substitute(name, **kwargs):
                return stack.enter_context(patch("deploy.cloudflare_setup." + name, **kwargs))
            substitute("deployment_connector", return_value="/usr/bin/cloudflared")
            substitute("API", return_value=self.api)
            substitute("discover_zone", return_value=("z", "a"))
            substitute("login_team", return_value="team")
            substitute("ensure_unit")
            substitute("check_origin")
            substitute("service_invocations", return_value=["a" * 32, "b" * 32])
            substitute("command", side_effect=service)
            substitute("sys.stdin", new=io.StringIO("test-management\n" * 9))
            stack.enter_context(patch.dict(os.environ, {"POLYSIA_HOSTNAME": self.host, "POLYSIA_OWNER_EMAIL": self.owner,
                                                        "XDG_CONFIG_HOME": str(prefix / "config")}))
            archive = prefix / "test.pyz"
            archive.write_bytes(b"release")
            installed = Mock(return_value={"artifactSha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
            with self.assertRaisesRegex(ValueError, "differs from the hostname's DNS target"):
                setup(prefix=prefix, archive=archive, install=installed, recovery_id=self.app)
            with self.assertRaisesRegex(ValueError, "--empty-workspace"):
                setup(prefix=prefix, archive=archive, install=installed, recovery_id="auto")
            active = True
            with self.assertRaisesRegex(ValueError, "active connector"):
                setup(prefix=prefix, archive=archive, install=installed, recovery_id="auto", empty_workspace=True)
            installed.assert_not_called()
            self.assertFalse((prefix / "remote/deployment.json").exists())
            active = False
            setup(prefix=prefix, archive=archive, install=installed, recovery_id="auto", empty_workspace=True)
            self.assertTrue(active)
            self.assertEqual(len(rotations), 1)
            calls.clear()
            setup(prefix=prefix, archive=archive, install=installed, recovery_id="auto", empty_workspace=True)
            setup(prefix=prefix, archive=archive, install=installed)
            credential = prefix / "remote/connector.token"
            credential.write_text("old-test-connector-credential")
            with self.assertRaisesRegex(ValueError, "credential has changed.*choose Recover website"):
                setup(prefix=prefix, archive=archive, install=installed)
            credential.write_text(token)
            database = prefix / "data/workspace.sqlite3"
            database.unlink()
            with self.assertRaisesRegex(ValueError, "workspace.*missing or empty.*Choose Recover website"):
                setup(prefix=prefix, archive=archive, install=installed)
            database.write_bytes(b"test workspace")
            self.api.rows.side_effect = OSError("read failed")
            with self.assertRaises(OSError):
                setup(prefix=prefix, archive=archive, install=installed)
            self.assertEqual(calls, [])
            self.assertTrue(active)

    def test_discovery_rejects_missing_ambiguous_or_shared_dns(self):
        for records, aliases in (([], []), ([self.record, self.record], []),
                                ([{**self.record, "proxied": False}], []),
                                ([{**self.record, "content": "other.example.com"}], []),
                                ([self.record], [self.record, {**self.record, "id": self.app}])):
            with self.subTest(records=len(records), aliases=len(aliases)):
                self.api.rows.side_effect = [records, aliases]
                with self.assertRaises(ValueError):
                    discover_tunnel(self.api, "z", self.host)
                self.api.request.assert_not_called()

    def test_legacy_socket_migration_is_deferred_verified_and_idempotent(self):
        api = ConfigAPI()
        args = (api, "/config", self.host)
        configure_ingress(*args, LEGACY_SOCKET, "team", self.audience, False)
        self.assertTrue(configure_ingress(*args, SERVICE_SOCKET, "team", self.audience, True, allow_legacy=True))
        with patch("deploy.cloudflare_setup.disconnected", side_effect=ValueError("active")):
            with self.assertRaisesRegex(ValueError, "active"):
                configure_ingress(*args, SERVICE_SOCKET, "team", self.audience, True, transfer_url="/tunnel")
        self.assertEqual(api.writes, 1)
        with patch("deploy.cloudflare_setup.disconnected") as check:
            for _ in range(2):
                configure_ingress(*args, SERVICE_SOCKET, "team", self.audience, True, transfer_url="/tunnel")
            check.assert_called_once_with(api, "/tunnel")
        self.assertEqual(api.writes, 2)
        self.assertEqual(api.ingress[0]["service"], "unix:" + SERVICE_SOCKET)
        protected = api.ingress[0].copy()
        for change in ({"service": "unix:/other/origin.sock"}, {"hostname": "another.example.com"},
                       {"originRequest": {}}, {"path": "/other"}):
            api.ingress[0] = {**protected, "service": "unix:" + LEGACY_SOCKET, **change}
            with self.assertRaises(UnsafeAccess):
                configure_ingress(*args, SERVICE_SOCKET, "team", self.audience, True, allow_legacy=True)
        self.assertEqual(api.writes, 2)
