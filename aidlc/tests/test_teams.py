"""python3 -m unittest discover -s aidlc/tests -v"""
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("aidlc_cli", REPO / "aidlc" / "scripts" / "aidlc.py")
cli = importlib.util.module_from_spec(spec)
sys.modules["aidlc_cli"] = cli
spec.loader.exec_module(cli)

REQUIRED = ["id", "title", "group", "tier", "create_when", "mission", "owns", "not_owns",
            "deliverables", "inputs", "collaborates", "dod", "metrics", "review_gate", "guidance"]
CORE = {"product", "architecture", "qa", "cicd", "ops", "security"}


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((REPO / "aidlc" / "teams" / "catalog.json").read_text(encoding="utf-8"))
        self.teams = self.raw["teams"]

    def test_entries_complete(self):
        ids = [t["id"] for t in self.teams]
        self.assertEqual(len(ids), len(set(ids)), "중복 팀 id")
        for t in self.teams:
            for key in REQUIRED:
                self.assertIn(key, t, f"{t['id']}.{key}")
            self.assertTrue(cli.TEAM_ID_RE.match(t["id"]))
            self.assertIn(t["group"], self.raw["groups"])
            self.assertIn(t["tier"], ("core", "conditional"))
            if t["review_gate"]:
                self.assertTrue(t["review_gate"]["applies_to"] and t["review_gate"]["checks"])

    def test_core_teams(self):
        self.assertEqual({t["id"] for t in self.teams if t["tier"] == "core"}, CORE)

    def test_operating_teams_present(self):
        ids = {t["id"] for t in self.teams}
        for must in ("backend", "frontend", "data", "cicd", "ops", "qa", "security", "ml", "infra", "design"):
            self.assertIn(must, ids)


class PlaceholderTest(unittest.TestCase):
    def test_ignores_notation_and_comments(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            doc = tmp / "doc.md"
            doc.write_text("> `{{ }}` = 필수\n<!-- {{주석}} -->\n| URL | `{{URL}}` |\n이름: {{이름}}\n", encoding="utf-8")
            self.assertEqual(cli.find_placeholders(doc), [(3, "URL"), (4, "이름")])
        finally:
            shutil.rmtree(tmp)

    def test_blank_templates_still_fail(self):
        for tpl in (REPO / "aidlc" / "templates" / "user").glob("*.md"):
            self.assertTrue(cli.find_placeholders(tpl), tpl.name)


class NewTeamTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self._orig = (cli.ROOT, cli.WS)
        cli.ROOT, cli.WS = self.root, self.root / "workspace"
        (self.root / ".claude" / "agents").mkdir(parents=True)

    def tearDown(self):
        cli.ROOT, cli.WS = self._orig
        shutil.rmtree(self.root)

    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()):
            return cli.cmd_new_team(list(args))

    def test_core_renders_without_leftover_tokens(self):
        self.assertEqual(self.run_cli("--core"), 0)
        for team in CORE:
            charter = (self.root / "workspace" / "teams" / team / "charter.md").read_text(encoding="utf-8")
            agent = (self.root / ".claude" / "agents" / f"team-{team}.md").read_text(encoding="utf-8")
            for text in (charter, agent):
                self.assertNotRegex(text, r"__[A-Z_]+__")
            self.assertIn(f"name: team-{team}", agent)

    def test_qa_has_review_gate(self):
        self.run_cli("qa")
        charter = (self.root / "workspace" / "teams" / "qa" / "charter.md").read_text(encoding="utf-8")
        self.assertIn("코드를 변경하는 모든 Task", charter)
        self.assertIn("QA / Test 팀 Charter", charter)

    def test_custom_team_with_title(self):
        self.assertEqual(self.run_cli("growth", "Growth Marketing"), 0)
        charter = (self.root / "workspace" / "teams" / "growth" / "charter.md").read_text(encoding="utf-8")
        self.assertIn("Growth Marketing 팀 Charter", charter)
        self.assertIn("team-architect 가", charter)

    def test_existing_files_not_overwritten(self):
        self.run_cli("backend")
        path = self.root / "workspace" / "teams" / "backend" / "charter.md"
        path.write_text("edited", encoding="utf-8")
        self.run_cli("backend")
        self.assertEqual(path.read_text(encoding="utf-8"), "edited")

    def test_invalid_id_rejected(self):
        self.assertEqual(self.run_cli("Bad_ID"), 1)


if __name__ == "__main__":
    unittest.main()
