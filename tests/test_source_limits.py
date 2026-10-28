"""Known-answer plain-source size admission checks without cloud calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.source_limits import SourceLimitError, validate_source_sizes


class SourceLimitsTests(unittest.TestCase):
    def test_exact_limit_and_cjk_characters_use_character_not_byte_count(self):
        result = validate_source_sizes({"main.py": "# 中文\n", "qresearch/a.py": b"pass\n"}, max_file_characters=5)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["total_characters"], 10)
        self.assertEqual(result["total_utf8_bytes"], 14)
        self.assertEqual(result["files"]["main.py"], {"characters": 5, "utf8_bytes": 9})
        self.assertEqual(result["largest_file_characters"], 5)
        self.assertEqual(result["character_measure"], "utf16_code_units")

    def test_all_oversized_files_are_reported_without_source_contents(self):
        with self.assertRaises(SourceLimitError) as caught:
            validate_source_sizes({"main.py": "SECRET", "a.py": "SECRET2", "b.py": "pass"}, max_file_characters=5)
        error = caught.exception
        self.assertEqual(error.reason, "file_character_limit")
        self.assertEqual(error.metadata["over_limit_files"], ["a.py", "main.py"])
        self.assertEqual(error.metadata["files"]["a.py"]["characters"], 7)
        self.assertEqual(error.metadata["status"], "failed")
        self.assertNotIn("SECRET", str(error)); self.assertNotIn("SECRET", str(error.metadata))

    def test_native60800_boundary(self):
        self.assertEqual(validate_source_sizes({"a.py": "x" * 60800}, max_file_characters=60800)["status"], "passed")
        with self.assertRaises(SourceLimitError) as caught:
            validate_source_sizes({"a.py": "x" * 60801}, max_file_characters=60800)
        self.assertEqual(caught.exception.reason, "file_character_limit")
        self.assertEqual(caught.exception.metadata["largest_file_characters"], 60801)

    def test_limit_requires_explicit_positive_native_integer(self):
        class IntegerSubclass(int): pass
        for limit in (True, False, None, 0, -1, 60800.0, "60800", float("inf"), IntegerSubclass(5), 2**32):
            with self.subTest(limit=type(limit)), self.assertRaises(SourceLimitError) as caught:
                validate_source_sizes({"main.py": "pass"}, max_file_characters=limit)
            self.assertEqual(caught.exception.reason, "invalid_limit")

    def test_missing_empty_or_nonmapping_source_sets_are_not_complete(self):
        for source in (None, {}, [], [("a.py", "pass")], {"a.py", "b.py"},
                       {str(i) + ".py": "" for i in range(513)}):
            with self.subTest(source=type(source)), self.assertRaises(SourceLimitError) as caught:
                validate_source_sizes(source, max_file_characters=60800)
            self.assertEqual(caught.exception.reason, "invalid_sources")

    def test_raw_utf8_must_be_plain_text_and_no_automatic_unwrapping(self):
        for value in (b"\xff\xfe", b"PK\x03\x04synthetic", b"pass\x00", "pass\x01", "\ud800", bytearray(b"pass"), None):
            with self.subTest(value=type(value)), self.assertRaises(SourceLimitError) as caught:
                validate_source_sizes({"main.py": value}, max_file_characters=60800)
            self.assertEqual(caught.exception.reason, "invalid_text")

    def test_non_BMP_is_rejected_consistently_with_native_file_API(self):
        with self.assertRaises(SourceLimitError) as caught:
            validate_source_sizes({"main.py": "# \U0001F600\n"}, max_file_characters=60800)
        self.assertEqual(caught.exception.reason, "unsupported_character")

    def test_bom_and_crlf_are_counted_without_silent_normalization(self):
        raw = b"\xef\xbb\xbfA\r\nB\r"
        result = validate_source_sizes({"main.py": raw}, max_file_characters=6)
        self.assertEqual(result["files"]["main.py"], {"characters": 6, "utf8_bytes": 8})
        with self.assertRaises(SourceLimitError): validate_source_sizes({"main.py": raw}, max_file_characters=5)
        self.assertEqual(validate_source_sizes({"main.py": "A\nB\n"}, max_file_characters=5)["files"]["main.py"]["characters"], 4)

    def test_paths_are_canonical_relative_managed_python_files(self):
        for path in ("../a.py", "/a.py", "C:/a.py", "a\\b.py", "a//b.py", "a/./b.py", "CON.py", "a.txt", "a.py/", 1):
            with self.subTest(path=path), self.assertRaises(SourceLimitError) as caught:
                validate_source_sizes({path: "pass"}, max_file_characters=60800)
            self.assertEqual(caught.exception.reason, "invalid_path")

    def test_metadata_is_deterministic_and_inputs_are_untouched(self):
        source = {"z.py": "pass\n", "a.py": ""}; before = deepcopy(source)
        result = validate_source_sizes(source, max_file_characters=60800)
        self.assertEqual(result, validate_source_sizes(dict(reversed(list(source.items()))), max_file_characters=60800))
        self.assertEqual(source, before)
        result["files"]["a.py"]["characters"] = 123
        self.assertEqual(validate_source_sizes(source, max_file_characters=60800)["files"]["a.py"]["characters"], 0)

    def test_this_check_does_not_execute_or_evaluate_source(self):
        result = validate_source_sizes({"main.py": "raise RuntimeError('NEVER EXECUTE')\n"}, max_file_characters=60800)
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
