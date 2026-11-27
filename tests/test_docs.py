"""Keep the repository's user-facing navigation usable from GitHub."""

import os
from pathlib import Path
import re
import subprocess
import unicodedata
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class DocumentationLinks(unittest.TestCase):
    def test_user_guide_links_resolve(self):
        for name in ("README.md", "AGENTS.md", "docs/operations.md"):
            page = ROOT / name
            for target in re.findall(r"\]\(([^)\s]+)\)", page.read_text(encoding="utf-8")):
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                with self.subTest(page=name, target=target):
                    dest = page.parent / unquote(url.path) if url.path else page
                    self.assertTrue(dest.is_file(), target)
                    if url.fragment:
                        headings = re.findall(r"^#{1,6} (.+)$", dest.read_text(encoding="utf-8"), re.M)
                        anchors = [re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings]
                        self.assertIn(unquote(url.fragment), anchors)


@unittest.skipUnless((ROOT / ".git").exists(), "Repository inventory requires a Git checkout")
class RepositoryLanguage(unittest.TestCase):
    def test_maintained_text_has_no_unexpected_script_phrases(self):
        # Catch pasted translations. Review still decides whether prose is clear English.
        inventory = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        word = r"[^\W\d_\x00-\x7f]{2,}"
        phrases = re.compile(rf"{word}[ \t]+{word}")
        findings = []
        for name in os.fsdecode(inventory).split("\0"):
            path = ROOT / name
            if not path.is_file() or path.is_symlink():
                continue
            if name.startswith("tests/fixtures/") or name == "apps/web/package-lock.json":
                continue  # Captured provider records and generated package metadata.
            data = path.read_bytes()
            if b"\0" in data:
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(content.splitlines(), 1):
                for phrase in phrases.findall(line):
                    if all("LATIN" not in unicodedata.name(c, "") for c in phrase):
                        findings.append(f"{name}:{number}")
                        break
        self.assertFalse(findings, "Review unexpected non-Latin text at " + ", ".join(findings))
