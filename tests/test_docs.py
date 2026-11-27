"""Keep the repository's user-facing navigation usable from GitHub."""

from pathlib import Path
import re
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
