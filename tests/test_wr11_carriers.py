"""WR-11 all-carrier tests and a synthetic CLI-to-Registry completion chain."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore
from qresearch.engineering_receipts import ReceiptParseError, _native
from qresearch.registry import Registry
from qresearch.collection_execution import run_collection_task, stdout_marker
import collection_task_cli as cli
from test_collection_tasks import CAT, Source, manifest, raw_plan


class NativeCarrierTests(unittest.TestCase):
    def clean(self):
        return {"status": "completed", "success": True, "execution_count": 1, "outputs": []}

    def test_single_and_equivalent_dual_json_carriers_preserve_observation(self):
        clean = self.clean()
        examples = [clean, {"structuredContent": clean},
                    {"content": [{"type": "text", "text": json.dumps(clean)}]},
                    {"isError": False, "structuredContent": clean, "content": [], "_meta": {}},
                    {"structuredContent": None, "content": [{"type": "text", "text": json.dumps(clean)}]},
                    {"structuredContent": deepcopy(clean), "content": [{"type": "text", "text": json.dumps(clean, sort_keys=True, indent=2) + "\n"}]}]
        for example in examples:
            with self.subTest(shape=list(example)):
                self.assertEqual(_native(example), clean)

    def test_parallel_text_display_or_error_cannot_be_discarded(self):
        extras = ["SYNTHETIC-EXTRA-ROW 123.5",
                  json.dumps({"outputs": [{"output_type": "display_data", "data": {"text/plain": "SYNTHETIC-EXTRA-ROW"}}]}),
                  json.dumps({"status": "error", "success": False, "outputs": [{"output_type": "error", "evalue": "SYNTHETIC-ERROR"}]})]
        for extra in extras:
            with self.subTest(extra_kind=extra[:20]):
                with self.assertRaises(ReceiptParseError) as error:
                    _native({"isError": False, "structuredContent": self.clean(), "content": [{"type": "text", "text": extra}]})
                self.assertNotIn("SYNTHETIC", str(error.exception))

    def test_conflict_in_either_direction_and_native_block_types_rejected(self):
        clean, changed = self.clean(), self.clean() | {"success": False, "status": "error"}
        for structured, text in ((clean, changed), (changed, clean)):
            with self.subTest(direction=structured["success"]), self.assertRaises(ReceiptParseError):
                _native({"structuredContent": structured, "content": [{"type": "text", "text": json.dumps(text)}]})
        for blocks in ([{"type": "image", "data": "synthetic"}], [{"type": "resource", "resource": {}}]):
            with self.assertRaises(ReceiptParseError):
                _native({"structuredContent": clean, "content": blocks})
        with self.assertRaises(ReceiptParseError):
            _native({"isError": True, "structuredContent": clean, "content": [{"type": "text", "text": json.dumps(clean)}]})

    def test_type_changes_and_duplicate_json_keys_are_not_equivalent(self):
        clean = self.clean()
        changed = clean | {"success": 1}
        for text in (json.dumps(changed), '{"status":"completed","success":true,"success":false,"outputs":[]}'):
            with self.subTest(text=text), self.assertRaises(ReceiptParseError):
                _native({"structuredContent": clean, "content": [{"type": "text", "text": text}]})

    def test_nonempty_unregistered_envelope_output_is_not_ignored(self):
        clean = self.clean()
        for extra in ({"status": "error"}, {"outputs": ["SYNTHETIC-EXTRA"]}, {"_meta": {"rows": ["SYNTHETIC"]}}):
            with self.subTest(extra=list(extra)), self.assertRaises(ReceiptParseError):
                _native({"structuredContent": clean, **extra})


class CarrierCompletionChainTests(unittest.TestCase):
    def test_cli_complete_chain_accepts_equivalent_and_rejects_extra_carriers(self):
        variants = ("structured", "content", "equivalent_dual", "text", "display", "error")
        for variant in variants:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                temp = Path(directory); (temp / "audit").mkdir()
                (temp / "audit/deployment.json").write_text(json.dumps({"source_files": manifest()}), encoding="utf-8")
                local = MemoryArtifactStore()
                registry = Registry(local, {name: {"normal": 8, "reserve": 2, "total": 10}
                                           for name in ("configurations", "research", "lean")})
                with patch.object(cli, "ROOT", temp), patch.object(cli, "open_registry", return_value=registry), \
                     patch.object(cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}), \
                     patch.object(cli, "export_usage", return_value=None):
                    cli.freeze_task(raw_plan(), {"success": True, "projects": [{"projectId": 17}]}, field_catalog=CAT)
                    cli.execute_metadata_command(NS(command="register-task", allocation="normal"), field_catalog=CAT)
                    attempt = cli.execute_metadata_command(NS(command="claim-task", allocation="normal", retry_of=None, reason=None), field_catalog=CAT)["attempt_id"]
                    admitted = cli.execute_metadata_command(NS(command="prepare-task", attempt=attempt), field_catalog=CAT)
                    source = Source()
                    wrapper = run_collection_task(admitted["payload"], field_catalog=CAT, store=MemoryArtifactStore(), source=source, synthetic=True)
                    marker = stdout_marker(wrapper, payload=admitted["payload"], field_catalog=CAT)
                    clean = {"status": "completed", "outputs": [{"output_type": "stream", "name": "stdout", "text": marker + "\n"}]}
                    result = {"isError": False, "structuredContent": clean}
                    if variant == "content":
                        result = {"content": [{"type": "text", "text": json.dumps(clean)}]}
                    elif variant == "equivalent_dual":
                        result["content"] = [{"type": "text", "text": json.dumps(clean, sort_keys=True, indent=2)}]
                    elif variant in {"text", "display", "error"}:
                        other = "SYNTHETIC-EXTRA-ROW 123.5" if variant == "text" else json.dumps({"outputs": [{
                            "output_type": "display_data" if variant == "display" else "error", "data": {"text/plain": "SYNTHETIC-EXTRA-ROW"}}]})
                        result["content"] = [{"type": "text", "text": other}]
                    envelope = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 0}, "result": result}
                    tool_path = temp / "synthetic_native.json"
                    tool_path.write_text(json.dumps(envelope), encoding="utf-8")
                    args = NS(command="research-result", attempt=attempt, tool_file=tool_path)
                    before = registry.snapshot()["usage"]
                    if variant in {"text", "display", "error"}:
                        with self.assertRaises(ReceiptParseError):
                            cli.execute_metadata_command(args, field_catalog=CAT)
                        self.assertEqual(registry.snapshot()["attempts"][-1]["status"], "started")
                        self.assertNotIn(b"SYNTHETIC-EXTRA-ROW", b"".join(local._data.values()))
                    else:
                        self.assertEqual(cli.execute_metadata_command(args, field_catalog=CAT)["status"], "completed")
                    self.assertEqual(registry.snapshot()["usage"], before)
                    self.assertEqual(source.calls, 2)


if __name__ == "__main__":
    unittest.main()
