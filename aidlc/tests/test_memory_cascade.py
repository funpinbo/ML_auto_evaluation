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
spec = importlib.util.spec_from_file_location("memory_cascade", REPO / "aidlc" / "hooks" / "memory_cascade.py")
mc = importlib.util.module_from_spec(spec)
sys.modules["memory_cascade"] = mc
spec.loader.exec_module(mc)


class CascadeTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "aidlc" / "templates", self.root / "aidlc" / "templates")
        shutil.copytree(REPO / "aidlc" / "templates" / "memory", self.root / "workspace" / "memory")
        self.mem = mc.Memory(self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_hook(self, event, payload=None):
        buf = io.StringIO()
        with redirect_stdout(buf):
            mc.handle(event, payload or {}, self.root)
        out = buf.getvalue().strip()
        return json.loads(out) if out else None

    def set_meta(self, path, **updates):
        meta, body = mc.read_doc(path)
        meta.update(updates)
        mc.write_doc(path, meta, body)

    def edit_payload(self, path):
        return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}

    def test_fresh_workspace_has_no_pending(self):
        self.assertIsNone(self.mem.pending())
        self.assertIsNone(self.run_hook("stop"))

    def test_frontmatter_roundtrip(self):
        self.set_meta(self.mem.plan, completed_phases=["P1", "P2"])
        meta, body = mc.read_doc(self.mem.plan)
        self.assertEqual(meta["completed_phases"], ["P1", "P2"])
        self.assertIn("# Plan", body)

    def test_full_cascade_stm_ltm_tasks_plan(self):
        # STM 열고 닫기 -> 보관 + LTM 요구
        self.set_meta(self.mem.stm, status="active", task="T-001", team="backend", outcome="done")
        self.assertIsNone(self.run_hook("post-tool-use", self.edit_payload(self.mem.stm)))
        self.set_meta(self.mem.stm, status="closed")
        out = self.run_hook("post-tool-use", self.edit_payload(self.mem.stm))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("cascade 1/3", ctx)
        self.assertTrue((self.mem.archive / "STM-0001_T-001.md").is_file())
        self.assertEqual(mc.read_doc(self.mem.stm)[0]["status"], "idle")

        # Stop 은 LTM 갱신 전까지 차단
        self.assertEqual(self.run_hook("stop")["decision"], "block")

        # LTM 갱신 -> Tasks 요구
        self.set_meta(self.mem.ltm, rev=1, last_merged_stm=1)
        self.assertEqual(self.mem.pending().level, "tasks")

        # Tasks 갱신 (P1 의 유일한 Task 체크) -> Plan 요구
        text = self.mem.tasks.read_text(encoding="utf-8").replace("- [ ] T-001", "- [x] T-001")
        self.mem.tasks.write_text(text, encoding="utf-8")
        self.set_meta(self.mem.tasks, rev=1, synced_ltm_rev=1)
        step = self.mem.pending()
        self.assertEqual(step.level, "plan")
        self.assertIn("P1", step.message)

        # Plan 갱신 -> 완료
        self.set_meta(self.mem.plan, completed_phases=["P1"], current_phase="P2")
        self.assertIsNone(self.mem.pending())
        self.assertIsNone(self.run_hook("stop"))

    def test_multiple_unmerged_stm_listed(self):
        for task in ("T-001", "T-002"):
            self.set_meta(self.mem.stm, status="closed", task=task)
            self.mem.archive_stm_if_closed()
        step = self.mem.pending()
        self.assertIn("STM-0001_T-001", step.message)
        self.assertIn("STM-0002_T-002", step.message)
        self.assertIn("last_merged_stm: 2", step.message)

    def test_stop_loop_guard_releases(self):
        self.set_meta(self.mem.stm, status="closed", task="T-001")
        for _ in range(mc.MAX_STOP_BLOCKS):
            self.assertEqual(self.run_hook("stop")["decision"], "block")
        out = self.run_hook("stop")
        self.assertNotIn("decision", out)
        self.assertIn("systemMessage", out)

    def test_post_tool_use_ignores_non_memory_files(self):
        self.set_meta(self.mem.ltm, rev=3)  # tasks pending 상태
        self.assertIsNone(self.run_hook("post-tool-use", self.edit_payload(self.root / "src" / "app.py")))

    def test_pre_compact_snapshots_active_stm(self):
        self.set_meta(self.mem.stm, status="active", task="T-009")
        out = self.run_hook("pre-compact")
        self.assertIn("SNAP-", out["systemMessage"])
        self.assertEqual(self.mem.latest_seq(), 0)  # 스냅샷은 cascade 대상 아님

    def test_session_start_injects_summary(self):
        out = self.run_hook("session-start")
        self.assertIn("AI-DLC 상태", out["hookSpecificOutput"]["additionalContext"])

    def test_no_workspace_is_silent(self):
        shutil.rmtree(self.root / "workspace")
        self.assertIsNone(self.run_hook("stop"))
        self.assertIsNone(self.run_hook("session-start"))


if __name__ == "__main__":
    unittest.main()
