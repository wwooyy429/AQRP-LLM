"""One delivered Research failure with duplicate MCP error representations.

The fixed real packet is replayed read-only. Mutations are synthetic; no test
executes Research, contacts QC, changes its input or touches the real ledger.
"""
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import canonical_json, content_hash
import qresearch.engineering_receipts as receipts
from test_engineering_receipts import context, envelope, research_tool
from test_native_research_failure import bind, cell_error

ATTEMPT = "f5d05f5b964b4a1d924e4b70cd207386"
SECRET = "SYNTHETIC_UNREGISTERED_SIDE_OUTPUT"


def duplicated(node=None, *, structured=False):
    node = cell_error() if node is None else node
    tool = envelope("jupyter_execute_cell", {"projectId": 17, "index": 1}, node)
    if not structured:
        del tool["result"]["structuredContent"]
    tool["result"]["content"] *= 2
    tool["result"]["content"] = deepcopy(tool["result"]["content"])
    tool["result"]["isError"] = False
    return tool


class ResearchErrorRepresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.deployment = context("research")
        cls.binding = bind(cls.payload, cls.deployment, index=1)

    def parse(self, tool):
        return receipts.research_observation(self.payload, self.deployment, tool, dispatch_binding=self.binding)

    def test_real_packet_is_one_logical_failure_and_two_native_representations(self):
        path = ROOT / "audit/tool_observations" / (ATTEMPT + "-research.json")
        self.assertEqual(sha256(path.read_bytes()).hexdigest(), "14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3")
        tool = json.loads(path.read_bytes())
        admission = json.loads((ROOT / "audit/runtime/engineering/admitted-inputs" / (ATTEMPT + ".json")).read_bytes())
        binding = json.loads((ROOT / "audit/runtime/engineering/research-dispatch" / (ATTEMPT + ".json")).read_bytes())
        source = receipts.research_cell_source(admission["payload"], admission["deployment"])
        self.assertEqual(sha256(source.encode()).hexdigest(), "33c34e9fbbf958f6518966cee185e947d96a4c610b7c0a942d206dec252e3340")
        result = receipts.research_observation(admission["payload"], admission["deployment"], tool, dispatch_binding=binding)
        platform = result["completion"]["platform"]
        self.assertEqual(platform["status"], "runtime_error")
        self.assertEqual(platform["identity"]["attempt_id"], ATTEMPT)
        raw = platform["raw_receipt"]
        self.assertEqual(raw["error_output_count"], 1)
        self.assertEqual(raw["native_error_representation_count"], 2)
        self.assertEqual(raw["traceback_line_count"], 9)
        self.assertEqual(raw["response_sha256"], content_hash(tool["result"]))
        node = json.loads(tool["result"]["content"][0]["text"])
        self.assertNotIn(node["evalue"], json.dumps(result))
        self.assertNotIn(node["ename"], json.dumps(result))
        self.assertNotIn("cloud_report", result["completion"])

    def test_two_complete_typed_error_mirrors_use_full_original_response_hash(self):
        tool = duplicated()
        result = self.parse(tool)
        raw = result["completion"]["platform"]["raw_receipt"]
        self.assertEqual(raw["error_output_count"], 1)
        self.assertEqual(raw["native_error_representation_count"], 2)
        self.assertEqual(raw["response_sha256"], content_hash(tool["result"]))
        projection = deepcopy(tool["result"]); projection["content"] = projection["content"][:1]
        self.assertNotEqual(raw["response_sha256"], content_hash(projection))
        self.assertNotIn("ValueError", json.dumps(result))

    def test_consistent_structured_mirror_is_counted_but_conflicts_reject(self):
        tool = duplicated(structured=True)
        self.assertEqual(self.parse(tool)["completion"]["platform"]["raw_receipt"]["native_error_representation_count"], 3)
        tool["result"]["structuredContent"]["evalue"] = SECRET
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(tool)

    def test_different_error_or_non_JSON_side_output_cannot_be_deduplicated(self):
        for text in (json.dumps(cell_error(evalue="different")), SECRET, "", "null", "[]", "1", "false"):
            tool = duplicated(); tool["result"]["content"][1]["text"] = text
            with self.subTest(text=text), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool)

    def test_multiple_actual_error_nodes_in_one_JSON_array_remain_multiple(self):
        for node in ([cell_error(), cell_error()], {"status": "error", "outputs": [cell_error(), cell_error()]}):
            for count in (1, 2):
                tool = duplicated(node)
                tool["result"]["content"] = tool["result"]["content"][:count]
                with self.subTest(node=node, count=count), self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool)

    def test_duplicate_carrier_form_does_not_expand_to_nested_or_success_errors(self):
        variants = ([cell_error()], {"status": "error", "outputs": [cell_error()]},
            {"output_type": "stream", "name": "stdout", "text": json.dumps(cell_error())},
            {"success": False, "errors": ["Timeout", SECRET]})
        for node in variants:
            with self.subTest(node=node), self.assertRaises(receipts.ReceiptParseError):
                self.parse(duplicated(node))

    def test_every_annotation_and_unknown_envelope_field_is_validated(self):
        for position in (0, 1):
            for unknown in ({"rows": [SECRET]}, {"priority": True}, {"lastModified": SECRET}):
                tool = duplicated(); tool["result"]["content"][position]["annotations"] = unknown
                with self.subTest(position=position, unknown=unknown), self.assertRaises(receipts.ReceiptParseError):
                    self.parse(tool)
        for mutate in (lambda r:r.update(_meta={"rows": [SECRET]}), lambda r:r.update(side_output=SECRET),
                lambda r:r["content"][1].update(type="image"), lambda r:r["content"][1].update(hidden=SECRET)):
            tool = duplicated(); mutate(tool["result"])
            with self.subTest(mutate=mutate), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool)

    def test_annotations_must_be_consistent_registered_hints(self):
        hints = {"audience": ["assistant"], "priority": 0.5, "lastModified": "2026-10-27T12:00:00Z"}
        tool = duplicated()
        for block in tool["result"]["content"]:
            block["annotations"] = deepcopy(hints)
        self.assertEqual(self.parse(tool)["completion"]["platform"]["status"], "runtime_error")
        tool["result"]["content"][1]["annotations"]["priority"] = 0.75
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(tool)

    def test_exactly_observed_two_carriers_and_typed_dispatch_arguments(self):
        tool = duplicated(); tool["result"]["content"].append(deepcopy(tool["result"]["content"][0]))
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(tool)
        for changes in ({"index": True}, {"index": 2}, {"projectId": True}, {"projectId": 18}, {"extra": SECRET}):
            tool = duplicated(); tool["arguments"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(receipts.ReceiptParseError):
                self.parse(tool)

    def test_default_native_and_success_semantics_are_unchanged(self):
        tool = duplicated()
        self.assertEqual(receipts._native(tool["result"]), [block["text"] for block in tool["result"]["content"]])
        self.assertEqual(sha256(inspect.getsource(receipts._native).encode()).hexdigest(),
            "94e3b597ca229606942fd43e05dc58db867520603517d0a7528b82436e169812")
        success = research_tool(self.payload)
        success["arguments"]["index"] = 1
        self.assertEqual(self.parse(success)["completion"]["platform"]["status"], "completed")
        success["result"]["content"] *= 2
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(success)

    def test_semantically_equal_JSON_formatting_does_not_change_typed_error(self):
        tool = duplicated()
        tool["result"]["content"][1]["text"] = json.dumps(cell_error(), indent=2)
        self.assertEqual(self.parse(tool)["completion"]["platform"]["raw_receipt"]["error_output_count"], 1)
        tool["result"]["content"][1]["text"] = '{"output_type":"error","output_type":"error"}'
        with self.assertRaises(receipts.ReceiptParseError):
            self.parse(tool)


if __name__ == "__main__":
    unittest.main()
