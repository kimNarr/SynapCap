import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SetupParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = []
        self.anchors = []
        self.panels = {}
        self.platform = None
        self.service = None
        self.code = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchors.append(attrs["href"][1:])
        if tag == "details" and attrs.get("id") in {"cli-windows", "cli-macos"}:
            self.platform = attrs["id"]
            self.panels[self.platform] = {}
        if tag == "article" and self.platform and "data-service" in attrs:
            self.service = attrs["data-service"]
            self.panels[self.platform][self.service] = []
        if tag == "code" and self.service:
            self.code = ""

    def handle_data(self, data):
        if self.code is not None:
            self.code += data

    def handle_endtag(self, tag):
        if tag == "code" and self.code is not None:
            self.panels[self.platform][self.service].append(self.code)
            self.code = None
        if tag == "article":
            self.service = None
        if tag == "details":
            self.platform = None


class HomepageSetupTests(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.setup = SetupParser(self.html)

    def test_both_platforms_include_all_default_providers(self):
        self.assertEqual(set(self.setup.panels), {"cli-windows", "cli-macos"})
        for services in self.setup.panels.values():
            self.assertEqual(set(services), {"codex", "antigravity", "claude"})

    def test_installers_use_the_correct_shell_for_each_platform(self):
        hosts = {
            "codex": "chatgpt.com/codex",
            "antigravity": "antigravity.google/cli",
            "claude": "claude.ai",
        }
        for service, host in hosts.items():
            with self.subTest(service=service):
                self.assertEqual(
                    self.setup.panels["cli-windows"][service][0],
                    f"irm https://{host}/install.ps1 | iex",
                )
                shell = "sh" if service == "codex" else "bash"
                self.assertEqual(
                    self.setup.panels["cli-macos"][service][0],
                    f"curl -fsSL https://{host}/install.sh | {shell}",
                )

    def test_each_guide_includes_version_check_and_login(self):
        for platform, services in self.setup.panels.items():
            for service, binary in (("codex", "codex"), ("antigravity", "agy"), ("claude", "claude")):
                with self.subTest(platform=platform, service=service):
                    self.assertIn(f"{binary} --version", services[service])
                    self.assertIn("codex login" if service == "codex" else binary, services[service])

    def test_internal_links_resolve_and_ids_are_unique(self):
        self.assertEqual(len(self.setup.ids), len(set(self.setup.ids)))
        self.assertTrue(set(self.setup.anchors).issubset(self.setup.ids))
        self.assertIn("cli-setup", self.setup.anchors)

    def test_old_macos_only_setup_is_replaced(self):
        self.assertNotIn('class="mac-setup"', self.html)
        self.assertIn("Get-Command codex", self.html)
        self.assertIn("command -v codex", self.html)
        self.assertIn("완전 종료", self.html)
        self.assertIn("WSL", self.html)


if __name__ == "__main__":
    unittest.main()
