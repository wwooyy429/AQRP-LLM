"""Fixed dispatcher/CLI integration with invented tasks and native-shaped metadata."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import stage2
import task_followup as cli
from qresearch.task_followup import TaskFollowupController, TaskFollowupError
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry
from test_engineering_tasks import raw_plan, submission, completed
from test_engineering_receipts import envelope, completed_tool, log_tools, report
from test_task_followup import fixture, history, POLICY, SUBMITTED, DEADLINE
from test_deployment_preflight import LocalFixture


def project_listing(ids=(17,)):
    return envelope("list_projects", {}, {"success": True, "projects": [
        {"projectId": value, "name": "SYNTHETIC", "language": "Py"} for value in ids],
        "page": 1, "nextPage": None, "totalPages": 1})


class FollowupCLITests(unittest.TestCase):
    def test_fixed_utc_cli_plans_one_native_request_without_new_execution_or_clock_override(self):
        store, reg, bridge, attempt, controller = fixture()
        before = reg.snapshot()["usage"]
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp); (root / "config").mkdir()
            (root / "config/task_followup.json").write_bytes(json.dumps(POLICY).encode())
            listing = root / "projects.json"; listing.write_bytes(json.dumps(project_listing()).encode())
            native = root / "history.json"; native.write_bytes(json.dumps(history()).encode())
            stack.enter_context(patch.object(cli, "ROOT", root))
            stack.enter_context(patch.object(cli, "open_registry", return_value=reg))
            stack.enter_context(patch("sys.stdout", io.StringIO()))
            with patch.object(cli, "utc_now", return_value=SUBMITTED):
                self.assertEqual(cli.main(["next", "--attempt", attempt])["action"], "wait_for_delivery")
            with patch.object(cli, "utc_now", return_value=DEADLINE):
                need = cli.main(["next", "--attempt", attempt])
                self.assertEqual(need["action"], "list_projects")
                first = cli.main(["next", "--attempt", attempt, "--projects-file", str(listing)])
                self.assertTrue(first["should_execute"])
                self.assertEqual(first["tool_request"]["tool_name"], "mcp__quantconnect__list_backtests")
                again = cli.main(["next", "--attempt", attempt, "--projects-file", str(listing)])
                self.assertEqual(again["action"], "attention_required")
                cli.main(["history", "--attempt", attempt, "--tool-file", str(native)])
                read = cli.main(["next", "--attempt", attempt, "--projects-file", str(listing)])
                self.assertEqual(read["action"], "read_completed_backtest")
            with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
                cli.main(["next", "--attempt", attempt, "--now", DEADLINE.isoformat()])
        self.assertEqual(reg.snapshot()["usage"], before)

    def test_project_carriers_unknown_values_and_duplicates_fail_closed(self):
        edits = [lambda value: value["projects"][0].update(projectId=True),
                 lambda value: value["projects"][0].update(name=["SYNTHETIC-ROW"]),
                 lambda value: value["projects"][0].update(language=[]),
                 lambda value: value.update(totalPages=True),
                 lambda value: value.update(projects=value["projects"] * 2),
                 lambda value: value.update(rows=[[1]])]
        for edit in edits:
            tool = project_listing(); value = tool["result"]["structuredContent"]; edit(value)
            tool["result"]["content"][0]["text"] = json.dumps(value)
            with self.assertRaises((TaskFollowupError, ValueError)): cli.project_ids(tool)
        tool = project_listing(); tool["result"]["content"][0]["text"] = "{}"
        with self.assertRaises(ValueError): cli.project_ids(tool)

    def test_wrong_project_discovery_does_not_reserve_a_request(self):
        store, reg, bridge, attempt, controller = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "config").mkdir()
            (root / "config/task_followup.json").write_bytes(json.dumps(POLICY).encode())
            listing = root / "projects.json"; listing.write_bytes(json.dumps(project_listing((18,))).encode())
            before = dict(store._data)
            with patch.object(cli, "ROOT", root), patch.object(cli, "open_registry", return_value=reg), \
                 patch.object(cli, "utc_now", return_value=DEADLINE):
                with self.assertRaises(TaskFollowupError): cli.main(["next", "--attempt", attempt, "--projects-file", str(listing)])
            self.assertEqual(store._data, before)

    def test_bad_policy_blocks_freeze_and_registration_before_any_budget_change(self):
        with LocalFixture(1) as fixture:
            fixture.dump("config/task_followup.json", POLICY | {"notification_grace_seconds": True})
            before = fixture.registry.snapshot(); objects = dict(fixture.store._data)
            with self.assertRaises(ValueError): fixture.command("register")
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, objects)

    def test_submission_entry_enrolls_watch_and_terminal_entry_closes_it(self):
        self.run_native_cli_chain(fail_watch=False)

    def test_post_accept_watch_io_failure_is_explicit_attention_never_legacy_or_retry(self):
        self.run_native_cli_chain(fail_watch=True)

    def run_native_cli_chain(self, fail_watch):
        store = MemoryArtifactStore()
        reg = Registry(store, {kind: {"total": 10, "normal": 8, "reserve": 2}
                               for kind in ("configurations", "research", "lean")})
        plan = EngineeringTaskPlan.from_dict(raw_plan(), discovered_project_ids=(17,))
        bridge = EngineeringTaskBridge(reg, plan); bridge.register()
        research = bridge.claim("research"); payload = bridge.payload(research)
        bridge.record_submission(research, submission(payload))
        bridge.consume_completion(research, completion_source=lambda _: completed(payload))
        lean = bridge.claim("lean"); payload = bridge.payload(lean)
        admission = {"payload": payload, "deployment": submission(payload)["deployment"]}
        native = envelope("create_backtest", {"projectId": 17}, {"success": True, "backtestId": "native-backtest-id"})
        before_usage = reg.snapshot()["usage"]
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp); (root / "config").mkdir()
            (root / "config/task_followup.json").write_bytes(json.dumps(POLICY).encode())
            tool = root / "native.json"; tool.write_bytes(json.dumps(native).encode())
            stack.enter_context(patch.object(stage2, "ROOT", root))
            stack.enter_context(patch.object(stage2, "bridge_for_attempt", return_value=bridge))
            stack.enter_context(patch.object(stage2, "admitted_input", return_value=admission))
            stack.enter_context(patch.object(stage2, "export_usage", return_value=None))
            output = stack.enter_context(patch("sys.stdout", io.StringIO()))
            if fail_watch:
                original = store.append_event
                def append(key, value):
                    if key.startswith("engineering/followup/"): raise IOError("SYNTHETIC private path")
                    return original(key, value)
                stack.enter_context(patch.object(store, "append_event", side_effect=append))
            with patch.object(sys, "argv", ["stage2.py", "backtest-submission", "--attempt", lean.attempt_id, "--tool-file", str(tool)]):
                stage2.main()
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "pending")
            self.assertEqual(bridge._record(lean)["external_id"], "native-backtest-id")
            if fail_watch:
                self.assertEqual(result["task_followup"]["action"], "attention_required")
                self.assertNotIn("SYNTHETIC private path", output.getvalue())
            else:
                self.assertEqual(result["task_followup"]["action"], "wait_for_delivery")
                tool.write_bytes(json.dumps(completed_tool()).encode())
                wrapper = report(payload)
                wrapper["cloud_report"]["statistics"]["dividend_event_count"] = 2
                wrapper["report_ref"]["sha256"] = content_hash(wrapper["cloud_report"])
                logs = root / "logs.json"; logs.write_bytes(json.dumps(log_tools(payload, wrapper)).encode())
                output.seek(0); output.truncate(0)
                with patch.object(sys, "argv", ["stage2.py", "backtest-result", "--attempt", lean.attempt_id, "--tool-file", str(tool), "--logs-file", str(logs)]):
                    stage2.main()
                result = json.loads(output.getvalue())
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["task_followup"]["action"], "finished")
        self.assertEqual(reg.snapshot()["usage"], before_usage)


if __name__ == "__main__": unittest.main()
