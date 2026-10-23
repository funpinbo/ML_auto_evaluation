"""python3 -m unittest discover -s aidlc/tests -v"""
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "aidlc" / "examples" / "chatbot-openapi.json"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


od = load("openapi_docs", "aidlc/scripts/openapi_docs.py")
mc = load("memory_cascade_for_docs", "aidlc/hooks/memory_cascade.py")


class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.md = od.render(SAMPLE, cls.tmp).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_detect_finds_sample(self):
        self.assertIn(SAMPLE, od.detect(REPO))

    def test_endpoint_index_links_to_sections(self):
        self.assertIn("[`/conversations/{conversationId}/messages`](#post-conversationsconversationidmessages)", self.md)
        self.assertIn("### POST /conversations/{conversationId}/messages", self.md)

    def test_auth_and_public_endpoint(self):
        self.assertIn("| `bearerAuth` | http | bearer |", self.md)
        health = self.md.split("### GET /health")[1].split("###")[0]
        self.assertIn("**인증:** 불필요", health)

    def test_nested_fields_and_refs(self):
        self.assertIn("| `sources[].score` | number |  | 유사도 0~1 |", self.md)
        self.assertIn("| `message.role` | string enum: `user`, `bot`, `agent` |", self.md)
        self.assertIn("| `conversationId` | path | string (uuid) | ✅ | 대화 ID |", self.md)

    def test_allof_merged_in_schema_section(self):
        conv = self.md.split("### Conversation\n")[1].split("###")[0]
        for field in ("`channel`", "`id`", "`status`", "`created_at`"):
            self.assertIn(field, conv)

    def test_openapi_31_nullable_type(self):
        self.assertIn("| `next_cursor` | string \\| null |  |", self.md)

    def test_tables_have_consistent_columns(self):
        for block in self.md.split("\n\n"):
            lines = [l for l in block.splitlines() if l.startswith("|")]
            if len(lines) < 2:
                continue
            counts = {len(re.split(r"(?<!\\)\|", l)) for l in lines}
            self.assertEqual(len(counts), 1, block[:200])

    def test_curl_example(self):
        self.assertIn("curl -X POST 'https://api.example.com/v1/conversations/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages'", self.md)
        self.assertIn("-H 'Authorization: Bearer $TOKEN'", self.md)
        self.assertIn("-d '{\"text\": \"환불은 며칠 걸리나요?\"}'", self.md)
        self.assertIn("curl -X GET 'https://api.example.com/v1/faq/search?q=환불'", self.md)

    def test_deprecated_marked(self):
        self.assertIn("단발 질문 (구버전) ⚠️ deprecated", self.md)
        self.assertIn("> ⚠️ **Deprecated**", self.md)

    def test_rejects_non_openapi3(self):
        bad = self.tmp / "swagger.json"
        bad.write_text(json.dumps({"swagger": "2.0", "paths": {}}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            od.render(bad, self.tmp / "out")


class SpecHookTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "aidlc" / "templates" / "memory", self.root / "workspace" / "memory")
        self.spec = self.root / "workspace" / "project" / "contracts" / "openapi.json"
        self.spec.parent.mkdir(parents=True)
        shutil.copy(SAMPLE, self.spec)

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_hook(self, path):
        buf = io.StringIO()
        with redirect_stdout(buf):
            mc.handle("post-tool-use", {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}, self.root)
        out = buf.getvalue().strip()
        return json.loads(out) if out else None

    def test_spec_edit_triggers_regeneration_notice(self):
        out = self.run_hook(self.spec)
        self.assertIn("[AI-DLC docs]", out["hookSpecificOutput"]["additionalContext"])

    def test_plain_json_ignored(self):
        other = self.root / "package.json"
        other.write_text('{"name": "x"}', encoding="utf-8")
        self.assertIsNone(self.run_hook(other))


if __name__ == "__main__":
    unittest.main()
