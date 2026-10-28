"""Independent synthetic deployment identity boundaries; no cloud or data I/O."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / 'cloud/qresearch').is_dir() and (path / 'config').is_dir())
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'cloud'))
from qresearch import deployment_sources as ds


def legacy_sha(raw):
    return sha256(raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')).hexdigest()


class IndependentIdentityBoundaries(unittest.TestCase):
    def test_known_answer_v1_preserves_eof(self):
        source = b'x = 7'
        hashes = []
        for suffix in (b'', b'\n', b'\n\n'):
            observed = ds.source_sha256(source + suffix)
            self.assertEqual(observed, legacy_sha(source + suffix))
            hashes.append(observed)
        self.assertEqual(len(set(hashes)), 3)

    def test_v1_hash_retains_old_invalid_python_support(self):
        raw = b'not valid Python =\n' + b'\n' * 100
        self.assertEqual(ds.source_sha256(raw), legacy_sha(raw))
        self.assertEqual(ds.parse_manifest({'old.py': legacy_sha(raw)})[0], 1)

    def test_old_bom_crlf_identity_is_unchanged(self):
        self.assertEqual(ds.source_sha256(b'\xef\xbb\xbfx=1\r\n\r'), legacy_sha(b'x=1\n\n'))

    def test_v2_worker_accepts_only_terminal_lf_variations(self):
        original = b'value = 31\n'
        record = ds.source_record(original)
        for count in (0, 1, 2, 64):
            self.assertEqual(ds.validate_record_against_source(original.rstrip(b'\n') + b'\n' * count, record), record)

    def test_v2_strict_local_rejects_worker_eof_variations(self):
        record = ds.source_record(b'value=31\n')
        self.assertEqual(ds.validate_record_against_source(b'value=31\n', record, True), record)
        for raw in (b'value=31', b'value=31\n\n'):
            with self.assertRaises(ValueError):
                ds.validate_record_against_source(raw, record, True)

    def test_body_whitespace_comment_and_import_changes_stay_distinct(self):
        original = b'import math\nvalue = 31  # fixed\n'
        record = ds.source_record(original)
        for raw in (b'import math\n\nvalue = 31  # fixed\n', b'import math\nvalue=31  # fixed\n',
                    b'import math\nvalue = 31  # changed\n', b'import cmath\nvalue = 31  # fixed\n',
                    b'import math\nvalue = 31  # fixed \n'):
            with self.assertRaises(ValueError):
                ds.validate_record_against_source(raw, record)

    def test_source_record_sha_tamper_rejects(self):
        record = ds.source_record(b'x=1\n')
        for key in ('source_sha256', 'canonical_sha256'):
            changed = dict(record, **{key: 'f' * 64})
            with self.assertRaises(ValueError):
                ds.validate_record_against_source(b'x=1\n', changed)

    def test_lf_count_cannot_be_changed_without_source_digest(self):
        record = ds.source_record(b'x=1\n')
        for count in (0, 2, 64):
            with self.assertRaises(ValueError):
                ds.validate_record_against_source(b'x=1\n', dict(record, terminal_lf_count=count))

    def test_closed_lf_record_types_and_bounds(self):
        record = ds.source_record(b'x=1\n')
        for count in (True, False, -1, 65, 1.0, '1', None):
            with self.assertRaises(ValueError):
                ds.validate_record_against_source(b'x=1\n', dict(record, terminal_lf_count=count))
        with self.assertRaises(ValueError):
            ds.validate_record_against_source(b'x=1\n', dict(record, extension=True))

    def test_closed_manifest_version_and_policy(self):
        manifest = ds.build_manifest({'sample.py': b'x=1\n'})
        for key, value in (('schema_version', True), ('schema_version', 1), ('schema_version', 3),
                           ('source_identity_policy', 'auto'), ('files', {})):
            changed = deepcopy(manifest)
            changed[key] = value
            with self.assertRaises(ValueError):
                ds.parse_manifest(changed)
        with self.assertRaises(ValueError):
            ds.parse_manifest(dict(manifest, extension=True))

    def test_all_generated_inputs_excluded_from_v2(self):
        for name in ('_engineering_task_input.py', '_collection_task_input.py'):
            with self.assertRaises(ValueError):
                ds.build_manifest({name: b'x=1\n'})

    def test_casefold_paths_are_ambiguous_for_v2(self):
        with self.assertRaises(ValueError):
            ds.build_manifest({'sample.py': b'x=1\n', 'SAMPLE.py': b'x=1\n'})

    def test_path_traversal_and_controls_reject(self):
        for name in ('../sample.py', '/sample.py', 'folder/../sample.py', 'a\\sample.py', 'a\x7fb.py'):
            with self.assertRaises(ValueError):
                ds.build_manifest({name: b'x=1\n'})

    def test_invalid_syntax_never_becomes_canonical(self):
        for raw in (b'x=\n', b'x=1\x00\n', b'\xff\n'):
            with self.assertRaises(ValueError) as caught:
                ds.canonical_source_bytes(raw)
            self.assertNotIn(repr(raw), str(caught.exception))

    def test_terminal_continuation_is_unsafe(self):
        raw = b'x = 1\\\n\n'
        compile(raw, '<synthetic>', 'exec')
        with self.assertRaises(ValueError):
            ds.canonical_source_bytes(raw)

    def test_ascii_cookie_cannot_bypass_validity(self):
        raw = b'# coding: ascii\nx="\xc3\xa9"\n'
        with self.assertRaises(SyntaxError):
            compile(raw, '<synthetic>', 'exec')
        with self.assertRaises(ValueError):
            ds.source_record(raw)

    def test_bom_cookie_conflict_cannot_be_stripped_away(self):
        raw = b'\xef\xbb\xbf# coding: latin-1\nx=1\n'
        with self.assertRaises(SyntaxError):
            compile(raw, '<synthetic>', 'exec')
        with self.assertRaises(ValueError):
            ds.source_record(raw)

    def test_non_utf8_cookie_must_not_change_ast_interpretation(self):
        raw = b'# coding: latin-1\nx="\xc3\xa9"\n'
        # This source is valid as bytes. Either reject it or compile bytes without
        # pretending the UTF8-decoded string is its actual runtime AST.
        try:
            canonical = ds.canonical_source_bytes(raw)
        except ValueError:
            return
        import ast
        self.assertEqual(ast.dump(ast.parse(raw), include_attributes=False),
                         ast.dump(ast.parse(canonical), include_attributes=False))

    def test_v2_resource_limits(self):
        for raw in (b'x=1\n' + b'\n' * 64, b'#' + b'a' * ds.MAX_SOURCE_BYTES + b'\n'):
            with self.assertRaises(ValueError):
                ds.source_record(raw)

    def test_no_source_execution_during_validation(self):
        raw = b'raise RuntimeError("synthetic must not execute")\n'
        record = ds.source_record(raw)
        self.assertEqual(ds.validate_record_against_source(raw, record), record)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentIdentityBoundaries))
    summary = {'kind': 'independent_synthetic_deployment_identity_boundaries',
               'test_count': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'successful': result.wasSuccessful(), 'cloud_calls': 0, 'provider_calls': 0,
               'financial_evidence': False}
    Path(__file__).with_name('boundary_result.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
