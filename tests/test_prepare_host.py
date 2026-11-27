"""Bounded Linux host preparation, tested without changing host users or packages."""
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

if sys.platform == "linux":
    from deploy import prepare_host as host


@unittest.skipUnless(sys.platform == "linux", "Linux host bootstrap")
class HostPreparationTests(unittest.TestCase):
    def test_tampered_connector_preserves_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "connector"
            with self.assertRaisesRegex(ValueError, "Integrity"):
                host.install_bytes(path, "a" * 64, lambda: io.BytesIO(b"bad"), 0o755)
            self.assertFalse(path.exists())
            path.write_bytes(b"unrelated tool")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                host.install_bytes(path, "a" * 64, lambda: io.BytesIO(b"bad"), 0o755)
            self.assertEqual(path.read_bytes(), b"unrelated tool")

    def test_existing_unrelated_account_is_never_adopted(self):
        user = SimpleNamespace(pw_gecos="Other application")
        with patch.object(host.pwd, "getpwnam", return_value=user), patch.object(host, "run") as run:
            with self.assertRaisesRegex(ValueError, "Conflicting service account"):
                host.dedicated_user("PolySia deployment id")
            run.assert_not_called()

    def test_unrelated_group_or_home_blocks_account_creation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host.pwd, "getpwnam", side_effect=KeyError), \
                patch.object(host, "run") as run, patch.object(host.grp, "getgrnam", return_value=object()):
            with patch.object(host, "HOME_DIR", Path(tmp)):
                with self.assertRaisesRegex(ValueError, "Existing service home"):
                    host.dedicated_user("tag")
            with patch.object(host, "HOME_DIR", Path(tmp) / "absent"):
                with self.assertRaisesRegex(ValueError, "existing .* group"):
                    host.dedicated_user("tag")
            run.assert_not_called()

    def test_unsupported_host_fails_before_host_changes(self):
        with patch.object(host.os, "geteuid", return_value=0), patch.object(
                host.platform, "freedesktop_os_release", return_value={"ID": "debian", "VERSION_ID": "12"}):
            with patch.object(host, "workspace") as begin, self.assertRaisesRegex(ValueError, "Ubuntu 26.04"):
                host.prepare(Path("/unused"))
            begin.assert_not_called()

    def test_no_package_install_when_ubuntu_would_upgrade_or_remove(self):
        for plan in ["Inst existing [1.0] (2.0 repository)", "Remv unrelated [1.0]"]:
            with patch.object(host.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)), \
                    patch.object(host, "run", side_effect=["", plan]) as run:
                with self.assertRaisesRegex(ValueError, "upgrades or removals"):
                    host.install_runtime()
                self.assertEqual(run.call_count, 2)

    @unittest.skipUnless(getattr(os, "geteuid", lambda: -1)() == 0, "root-owned directory checks")
    def test_root_manifest_stable_reinstall_and_collision(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host, "ROOT", Path(tmp) / "managed"):
            with host.host_lock():
                initial = host.workspace()
            self.assertEqual(initial, host.workspace())
            item = host.ROOT / "connector"
            payload = b"fixture bytes"
            expected = hashlib.sha256(payload).hexdigest()
            host.install_bytes(item, expected, lambda: io.BytesIO(payload), 0o755)
            host.install_bytes(item, expected, lambda: self.fail("duplicate download"), 0o755)
            self.assertEqual(item.read_bytes(), payload)
            (host.ROOT / "installation.json").unlink()
            with self.assertRaisesRegex(ValueError, "Refusing to adopt"):
                host.workspace()
