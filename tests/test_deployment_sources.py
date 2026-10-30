"""Known-answer and adversarial deployment identity tests; no cloud calls."""
import ast
from copy import deepcopy
from hashlib import sha256
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import content_hash
from qresearch.deployment_sources import (SourceIdentityError, SOURCE_IDENTITY_POLICY,
    MAX_SOURCE_BYTES, MAX_TERMINAL_LFS, MAX_SOURCE_FILES, MAX_SOURCE_PATH_BYTES,
    normalize_source_bytes, source_sha256,
    canonical_source_bytes, source_record, build_manifest, parse_manifest,
    validate_record_against_source)


SOURCE = b'# synthetic deployment\nVALUE = "fixture"\n'
SECRET = 'SYNTHETIC-SOURCE-SECRET-123'


class DeploymentSourcesTests(unittest.TestCase):
    def reason(self, expected, action):
        with self.assertRaises(SourceIdentityError) as caught:
            action()
        self.assertEqual(caught.exception.reason, expected)
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_legacy_identity_preserves_each_EOF_without_syntax_restriction(self):
        for raw in (SOURCE, SOURCE[:-1], SOURCE + b'\n', b'\x00', b'x =', b'\n' * 65):
            self.assertEqual(source_sha256(raw), sha256(raw).hexdigest())
        self.assertNotEqual(source_sha256(SOURCE), source_sha256(SOURCE + b'\n'))
        self.assertEqual(normalize_source_bytes(b'\xef\xbb\xbfA\r\nB\rC\n\n'), b'A\nB\nC\n\n')

    def test_v2_zero_one_two_and_maximum_LFs_have_known_answer(self):
        body = b'VALUE = 1'
        expected = sha256(body + b'\n').hexdigest()
        for count in (0, 1, 2, MAX_TERMINAL_LFS):
            raw = body + b'\n' * count
            with self.subTest(count=count):
                record = source_record(raw)
                self.assertEqual(record, {'source_sha256': sha256(raw).hexdigest(),
                    'canonical_sha256': expected, 'terminal_lf_count': count})
                self.assertEqual(canonical_source_bytes(raw), body + b'\n')

    def test_worker_accepts_only_explicitly_versioned_terminal_LF_equivalence(self):
        frozen = source_record(SOURCE)
        for count in (0, 1, 2, MAX_TERMINAL_LFS):
            raw = SOURCE.rstrip(b'\n') + b'\n' * count
            self.assertEqual(validate_record_against_source(raw, frozen), frozen)
        self.assertNotEqual(source_sha256(SOURCE + b'\n'), frozen['source_sha256'])

    def test_strict_project_preflight_preserves_original_EOF(self):
        frozen = source_record(SOURCE)
        self.assertEqual(validate_record_against_source(SOURCE, frozen, True), frozen)
        for raw in (SOURCE[:-1], SOURCE + b'\n'):
            self.reason('source_mismatch', lambda: validate_record_against_source(raw, frozen, True))

    def test_BOM_CRLF_and_CR_keep_existing_equivalence_in_both_modes(self):
        frozen = source_record(SOURCE)
        for raw in (b'\xef\xbb\xbf' + SOURCE, SOURCE.replace(b'\n', b'\r\n'), SOURCE.replace(b'\n', b'\r')):
            self.assertEqual(source_record(raw), frozen)
            self.assertEqual(validate_record_against_source(raw, frozen, True), frozen)

    def test_empty_and_newline_only_sources_keep_explicit_original_identities(self):
        frozen = source_record(b'')
        self.assertEqual(canonical_source_bytes(b''), b'\n')
        self.assertEqual(frozen['terminal_lf_count'], 0)
        self.assertEqual(validate_record_against_source(b'\n\n', frozen), frozen)
        self.reason('source_mismatch', lambda: validate_record_against_source(b'\n', frozen, True))

    def test_body_spaces_tabs_comments_imports_and_values_are_not_stripped(self):
        frozen = source_record(SOURCE)
        changes = [SOURCE.replace(b'VALUE =', b'VALUE  ='), SOURCE + b'# extra comment\n',
            b'import sys\n' + SOURCE, SOURCE.replace(b'fixture', b'changed'),
            SOURCE.replace(b'VALUE =', b'VALUE\t='), SOURCE + b'if True:\n    VALUE = 2\n',
            SOURCE + b' ', SOURCE + b'\t\n']
        for raw in changes:
            with self.subTest(raw=raw):
                self.reason('canonical_mismatch', lambda: validate_record_against_source(raw, frozen))

    def test_multiline_string_internal_newlines_are_preserved(self):
        first = b'VALUE = """first\nsecond\n\n"""\n'
        changed = b'VALUE = """first\nsecond\n"""\n'
        self.assertNotEqual(canonical_source_bytes(first), canonical_source_bytes(changed))
        self.assertEqual(canonical_source_bytes(first + b'\n'), first)
        self.reason('canonical_mismatch', lambda: validate_record_against_source(changed, source_record(first)))

    def test_unsafe_terminal_explicit_continuation_is_not_collapsed(self):
        # Extra physical LF makes this valid Python. Reducing it to one LF
        # leaves an incomplete explicit continuation and must fail closed.
        raw = b'VALUE = 1\\\n\n'
        compile(raw, '<synthetic>', 'exec')
        self.reason('unsafe_normalization', lambda: canonical_source_bytes(raw))
        self.reason('invalid_python', lambda: canonical_source_bytes(b'VALUE = 1\\\n'))
        valid = b'VALUE = (1 + \\\n+2)\n'
        self.assertEqual(canonical_source_bytes(valid + b'\n'), valid)

    def test_terminal_comment_backslash_and_closed_string_are_safe(self):
        for raw in (b'# comment\\\n\n', b'VALUE = "\\\\"\n\n'):
            canonical = canonical_source_bytes(raw)
            self.assertEqual(ast.dump(ast.parse(raw.decode())), ast.dump(ast.parse(canonical.decode())))

    def test_source_is_compiled_for_validation_never_executed(self):
        raw = b'raise RuntimeError("' + SECRET.encode() + b'")\n'
        self.assertEqual(canonical_source_bytes(raw), raw)

    def test_compile_warnings_and_exceptions_do_not_disclose_source(self):
        raw = b'VALUE = (1 is "' + SECRET.encode() + b'")\n'
        stderr = io.StringIO()
        with patch.object(sys, 'stderr', stderr), warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            canonical_source_bytes(raw)
        self.assertEqual(observed, [])
        self.assertEqual(stderr.getvalue(), '')
        for bad in (b'x = "' + SECRET.encode(), b'\x00' + SECRET.encode(), b'\xff' + SECRET.encode()):
            with self.assertRaises(SourceIdentityError) as caught:
                canonical_source_bytes(bad)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_encoding_cookie_and_raw_byte_semantics_are_checked(self):
        for prefix in (b'# coding: utf-8\n', b'# coding: utf8\n',
                b'\xef\xbb\xbf# coding: utf-8\n'):
            raw = prefix + 'VALUE = "é"\n'.encode('utf-8')
            self.assertEqual(canonical_source_bytes(raw), normalize_source_bytes(raw))
        bad = [b'# coding: ascii\n' + 'VALUE = "é"\n'.encode('utf-8'),
            b'# coding: latin-1\n' + 'VALUE = "é"\n'.encode('utf-8'),
            b'\xef\xbb\xbf# coding: latin-1\nVALUE = 1\n',
            b'# coding: missing-' + SECRET.encode() + b'\nVALUE = 1\n',
            b'# coding: latin-1\nVALUE = 1\n',
            b'VALUE = 1\nfrom __future__ import annotations\n']
        for raw in bad:
            self.reason('invalid_python', lambda: canonical_source_bytes(raw))
            self.assertEqual(source_sha256(raw), sha256(normalize_source_bytes(raw)).hexdigest())

    def test_invalid_UTF8_types_and_byte_subclasses_fail_closed(self):
        class BytesSubclass(bytes):
            pass
        for bad in (None, False, '', bytearray(SOURCE), memoryview(SOURCE), BytesSubclass(SOURCE)):
            self.reason('invalid_source_type', lambda: canonical_source_bytes(bad))
        self.reason('invalid_utf8', lambda: canonical_source_bytes(b'\xff'))

    def test_v2_resource_bounds_do_not_modify_legacy_hash(self):
        self.reason('terminal_lf_bound', lambda: canonical_source_bytes(b'\n' * (MAX_TERMINAL_LFS + 1)))
        raw = b'#' + b'a' * MAX_SOURCE_BYTES
        self.assertEqual(source_sha256(raw), sha256(raw).hexdigest())
        self.reason('source_too_large', lambda: canonical_source_bytes(raw))
        at_limit = b'#' + b'a' * (MAX_SOURCE_BYTES - 1)
        self.assertEqual(len(canonical_source_bytes(at_limit)), MAX_SOURCE_BYTES + 1)

    def test_manifest_envelope_is_closed_canonical_and_defensively_copied(self):
        manifest = build_manifest({'z.py': SOURCE, 'q/a.py': b'VALUE=2'})
        self.assertEqual(set(manifest), {'schema_version', 'source_identity_policy', 'files'})
        self.assertEqual(manifest['source_identity_policy'], SOURCE_IDENTITY_POLICY)
        self.assertEqual(list(manifest['files']), ['q/a.py', 'z.py'])
        version, records = parse_manifest(manifest)
        self.assertEqual(version, 2)
        records['z.py']['source_sha256'] = '0' * 64
        self.assertNotEqual(records, manifest['files'])

    def test_legacy_manifest_is_strict_and_does_not_become_a_v2_wrapper(self):
        manifest = {'one.py': source_sha256(SOURCE)}
        self.assertEqual(parse_manifest(manifest), (1, {'one.py': {'source_sha256': source_sha256(SOURCE)}}))
        self.assertNotEqual(content_hash(manifest), content_hash(build_manifest({'one.py': SOURCE})))
        for invalid in ({'one.py': source_record(SOURCE)}, {'one.py': True}, {'one.py': 'A' * 64}, {}):
            with self.assertRaises(SourceIdentityError):
                parse_manifest(invalid)

    def test_claimed_v2_manifest_cannot_downgrade_on_malformed_fields(self):
        base = build_manifest({'one.py': SOURCE})
        bad = [dict(base, schema_version=True), dict(base, schema_version=1),
            dict(base, source_identity_policy='loose'), dict(base, files={}),
            dict(base, extra=True), {k:v for k,v in base.items() if k!='files'},
            {'files': {'one.py': 'a' * 64}}, {'schema_version': 2, 'one.py': 'a' * 64}]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(SourceIdentityError):
                parse_manifest(raw)

    def test_record_bounds_digest_types_and_unknown_keys_are_rejected(self):
        base = source_record(SOURCE)
        bad = [dict(base, terminal_lf_count=x) for x in (True, False, -1, 1.0, None, 65)]
        bad += [dict(base, source_sha256=x) for x in (True, None, 'F'*64, 'a'*63)]
        bad += [dict(base, canonical_sha256=[]), dict(base, extra='secret'), {'source_sha256':'a'*64}]
        for record in bad:
            with self.subTest(record=record):
                with self.assertRaises(SourceIdentityError):
                    validate_record_against_source(SOURCE, record)
                with self.assertRaises(SourceIdentityError):
                    parse_manifest({'schema_version':2,'source_identity_policy':SOURCE_IDENTITY_POLICY,'files':{'one.py':record}})

    def test_unrelated_original_digest_cannot_hide_behind_matching_canonical_digest(self):
        frozen = source_record(SOURCE)
        changed = dict(frozen, source_sha256='0' * 64)
        self.reason('source_record_mismatch', lambda: validate_record_against_source(SOURCE + b'\n', changed))
        changed = dict(frozen, terminal_lf_count=2)
        self.reason('source_record_mismatch', lambda: validate_record_against_source(SOURCE + b'\n', changed))

    def test_self_consistent_different_LF_source_is_a_different_admitted_manifest(self):
        first = build_manifest({'one.py': SOURCE})
        second = build_manifest({'one.py': SOURCE + b'\n'})
        self.assertNotEqual(content_hash(first), content_hash(second))
        record = second['files']['one.py']
        self.reason('source_mismatch', lambda: validate_record_against_source(SOURCE, record, True))
        self.assertEqual(validate_record_against_source(SOURCE + b'\n', record, True), record)

    def test_declared_reconstructed_source_syntax_must_also_be_safe(self):
        raw = b'VALUE = 1\n'
        frozen = source_record(raw)
        self.reason('source_record_mismatch', lambda: validate_record_against_source(raw,
            dict(frozen, source_sha256=source_sha256(b'VALUE = 1\n\n'), terminal_lf_count=0)))

    def test_manifest_paths_reject_traversal_devices_generated_inputs_and_control(self):
        names = ['../x.py','/x.py','C:x.py','x\\y.py','x//y.py','x/../y.py','CON.py','x/NUL.py',
            'x?.py','x\x7f.py','\ud800.py','_engineering_task_input.py','_collection_task_input.py',
            '_COLLECTION_TASK_INPUT.py','q/_engineering_task_input.py',1]
        for name in names:
            with self.subTest(name=ascii(name)), self.assertRaises(SourceIdentityError):
                build_manifest({name: SOURCE})
        self.assertIn('模块.py', build_manifest({'模块.py': SOURCE})['files'])
        # Legacy compatibility: this was previously excluded separately by its
        # collection worker, not by the generic legacy source-path validator.
        self.assertEqual(parse_manifest({'_collection_task_input.py':'a'*64})[0],1)

    def test_v2_case_alias_file_set_and_path_limits_leave_v1_unchanged(self):
        for names in (['one.py', 'ONE.py'], ['q/one.py', 'Q/ONE.py'],
                ['one.py', 'ONE.py/sub.py'], ['ß.py', 'ss.py']):
            self.reason('invalid_path', lambda: build_manifest(dict.fromkeys(names, SOURCE)))
            records = dict.fromkeys(names, source_record(SOURCE))
            self.reason('invalid_path', lambda: parse_manifest({'schema_version': 2,
                'source_identity_policy': SOURCE_IDENTITY_POLICY, 'files': records}))
            self.assertEqual(parse_manifest(dict.fromkeys(names, source_sha256(SOURCE)))[0], 1)
        at_limit = 'x' * (MAX_SOURCE_PATH_BYTES - 3) + '.py'
        self.assertEqual(len(at_limit.encode()), MAX_SOURCE_PATH_BYTES)
        self.assertIn(at_limit, build_manifest({at_limit: SOURCE})['files'])
        over_limit = 'x' + at_limit
        self.reason('invalid_path', lambda: build_manifest({over_limit: SOURCE}))
        self.assertEqual(parse_manifest({over_limit: source_sha256(SOURCE)})[0], 1)
        exactly = {'f{}.py'.format(index): SOURCE for index in range(MAX_SOURCE_FILES)}
        self.assertEqual(len(build_manifest(exactly)['files']), MAX_SOURCE_FILES)
        over = dict(exactly, extra=SOURCE)
        self.reason('invalid_manifest', lambda: build_manifest(over))
        envelope = build_manifest({'one.py': SOURCE})
        envelope['files'] = {'f{}.py'.format(index): source_record(SOURCE)
                             for index in range(MAX_SOURCE_FILES + 1)}
        self.reason('invalid_manifest', lambda: parse_manifest(envelope))

    def test_boolean_selection_and_unknown_error_reasons_do_not_stringify_inputs(self):
        for selection in (1, 0, None, 'yes'):
            self.reason('invalid_selection', lambda: validate_record_against_source(SOURCE, source_record(SOURCE), selection))
        with self.assertRaises(ValueError) as caught:
            SourceIdentityError(SECRET)
        self.assertNotIn(SECRET, str(caught.exception))


if __name__ == '__main__':
    unittest.main()
