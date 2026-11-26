"""The release acquisition step must reject a changed artifact before executing it."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


HELPER = Path(__file__).resolve().parents[1] / "deploy" / "verified_install.py"


class VerifiedInstallTests(unittest.TestCase):
    def test_only_the_expected_bytes_run_and_options_reach_the_bundled_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            artifact = stage / "untrusted.pyz"
            marker = stage / "invocation.json"
            with zipfile.ZipFile(artifact, "w") as zf:
                zf.writestr("__main__.py", "import json,sys,pathlib\n"
                            "pathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\n")
            command = [sys.executable, "-I", str(HELPER), "--file", str(artifact), "--sha256"]
            options = ["--", str(marker), "--prefix", "prefix with spaces", "--json"]
            rejected = subprocess.run([*command, "0"*64, *options], capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("verification failed", rejected.stderr)
            self.assertFalse(marker.exists())
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            approved = subprocess.run([*command, digest, *options], capture_output=True, text=True)
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertIn(digest, approved.stderr)
            self.assertEqual(json.loads(marker.read_text()), ["--prefix", "prefix with spaces", "--json"])
