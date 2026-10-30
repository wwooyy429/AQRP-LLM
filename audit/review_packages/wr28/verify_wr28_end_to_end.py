"""Independent WR-28 clean-export/LF-checkout/tamper acceptance harness.

Only creates disposable exports/clones and private review output. No provider,
cloud, registration, debit or production source/config/metadata writes.
"""
from hashlib import sha256
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / 'cloud/qresearch').is_dir() and (path / 'config').is_dir())
HERE = Path(__file__).resolve().parent
EVIDENCE = None
CHECKER = 'audit/review_packages/deployment-eof-v2/verify_candidate.py'
OLD_LIST = 'audit/review_packages/deployment-eof-v2/protected_before.json'
FIXTURE = 'audit/review_packages/deployment-eof-v2/fixtures/engineering_smoke_662ccd.py'
AFFECTED = ('audit/data_exposure.json', 'config/research.json', 'config/workflow.json')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def safe_export(commit, destination):
    raw = git('archive', '--format=tar', commit)
    with tarfile.open(fileobj=BytesIO(raw)) as archive:
        for member in archive.getmembers():
            target = destination / member.name
            if not target.resolve().is_relative_to(destination.resolve()) or not (member.isdir() or member.isfile()):
                raise AssertionError('Unsafe archive entry')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())


def clean_env(root):
    env = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'PYTHONOPTIMIZE'):
        env.pop(key, None)
    env['GIT_CEILING_DIRECTORIES'] = str(root.parent)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
        env[key] = '1'
    return env


def digest_paths(root, names):
    return {name: sha256((root / name).read_bytes()).hexdigest() for name in names}


def source_paths():
    return sorted(path.relative_to(ROOT).as_posix()
                  for directory in ('cloud', 'tools', 'config', 'tests')
                  for path in (ROOT / directory).rglob('*')
                  if path.is_file() and path.suffix in ('.py', '.json') and '__pycache__' not in path.parts)


def run_checker(root, name, expected_success):
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(root / CHECKER)],
                            cwd=root, env=clean_env(root), capture_output=True)
    (EVIDENCE / (name + '.stdout')).write_bytes(result.stdout)
    (EVIDENCE / (name + '.stderr')).write_bytes(result.stderr)
    row = {'case': name, 'exit_code': result.returncode, 'expected_success': expected_success,
           'result_matches_expected': (result.returncode == 0) is expected_success,
           'stdout_sha256': sha256(result.stdout).hexdigest(), 'stderr_sha256': sha256(result.stderr).hexdigest()}
    if expected_success and result.returncode == 0:
        document = json.loads(result.stdout)
        row['checker_result'] = document
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    parser.add_argument('--evidence-dir', required=True, type=Path,
                        help='A new or empty output directory; nonempty directories are rejected')
    parser.add_argument('--full-verify', action='store_true',
                        help='Run the repository synthetic verifier in the disposable LF checkout')
    args = parser.parse_args()
    if re.fullmatch(r'[0-9a-f]{40}', args.commit) is None:
        parser.error('--commit requires an exact 40-character lowercase hexadecimal commit SHA')
    EVIDENCE = args.evidence_dir.resolve()
    if EVIDENCE.exists() and (not EVIDENCE.is_dir() or any(EVIDENCE.iterdir())):
        parser.error('--evidence-dir must be a new or empty directory; previous evidence is never overwritten')
    if any(EVIDENCE.is_relative_to(ROOT / folder) for folder in ('cloud', 'tools', 'config', 'tests')):
        parser.error('--evidence-dir cannot write into production source/config/test directories')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    commit = git('rev-parse', args.commit + '^{commit}').decode('ascii').strip()
    assert commit == args.commit
    declaration = json.loads(git('show', commit + ':' + OLD_LIST))
    protected_names = sorted(declaration)
    watched = sorted(set(protected_names) | set(source_paths()))
    before = digest_paths(ROOT, watched)
    rows, export_readonly, exported_hashes, full_verification = [], True, [], None
    with tempfile.TemporaryDirectory(prefix='aqrp-wr28-final-review-') as temporary:
        area = Path(temporary)
        first = area / 'raw-export-one'
        second = area / 'raw-export-two'
        for index, exported in enumerate((first, second), 1):
            exported.mkdir()
            safe_export(commit, exported)
            assert not (exported / '.git').exists()
            base = digest_paths(exported, protected_names)
            rows.append(run_checker(exported, 'clean_export_' + str(index), True))
            export_readonly &= base == digest_paths(exported, protected_names)
            exported_hashes.append(base)
        for name in AFFECTED:
            path = first / name
            raw = path.read_bytes()
            assert b'\r' not in raw and b'\n' in raw
            label = name.replace('/', '_').replace('.', '_')
            changed = bytearray(raw)
            changed[raw.index(b' ')] = 9
            assert sum(a != b for a, b in zip(raw, changed)) == 1
            try:
                path.write_bytes(bytes(changed))
                rows.append(run_checker(first, 'single_byte_' + label, False))
                path.write_bytes(raw.replace(b'\n', b'\r\n'))
                rows.append(run_checker(first, 'lf_to_crlf_' + label, False))
            finally:
                path.write_bytes(raw)
        path = first / 'audit/runtime/registry/events.jsonl'
        raw = path.read_bytes()
        changed = bytearray(raw)
        changed[0] ^= 1
        try:
            path.write_bytes(bytes(changed))
            rows.append(run_checker(first, 'budget_journal_single_byte', False))
        finally:
            path.write_bytes(raw)
        fixture = first / FIXTURE
        raw = fixture.read_bytes()
        try:
            fixture.write_bytes(raw + b'\n')
            rows.append(run_checker(first, 'portable_fixture_eof_tamper', False))
            fixture.unlink()
            rows.append(run_checker(first, 'portable_fixture_missing', False))
        finally:
            fixture.write_bytes(raw)
        provenance = first / 'audit/review_packages/deployment-eof-v2/protected_git_baseline.json'
        raw = provenance.read_bytes()
        try:
            changed = json.loads(raw)
            record = changed['files'][AFFECTED[0]]
            record['sha256'] = '0' * 64
            provenance.write_text(json.dumps(changed), encoding='utf-8')
            rows.append(run_checker(first, 'manifest_expected_hash_tamper', False))
        finally:
            provenance.write_bytes(raw)
        export_readonly &= exported_hashes[0] == digest_paths(first, protected_names)
        checkout = area / 'lf-checkout'
        subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', '--no-checkout', '--local', str(ROOT), str(checkout)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['git', '-C', str(checkout), '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                        'checkout', '--quiet', '--detach', commit], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        checkout_before = digest_paths(checkout, protected_names)
        rows.append(run_checker(checkout, 'independent_lf_checkout', True))
        export_readonly &= checkout_before == digest_paths(checkout, protected_names)
        protected_equal_across_modes = exported_hashes[0] == exported_hashes[1] == checkout_before
        if args.full_verify:
            build_paths = sorted(path.relative_to(checkout).as_posix()
                                 for folder in ('cloud', 'config')
                                 for path in (checkout / folder).rglob('*')
                                 if path.is_file() and path.suffix in ('.py', '.json')
                                 and '__pycache__' not in path.parts)
            build_before = digest_paths(checkout, build_paths)
            deployment_before = sha256((checkout / 'audit/deployment.json').read_bytes()).hexdigest()
            builds = []
            for sequence in (1, 2):
                built = subprocess.run([sys.executable, '-X', 'utf8', '-B', 'tools/research.py', 'build'],
                                       cwd=checkout, env=clean_env(checkout), capture_output=True)
                (EVIDENCE / ('build_' + str(sequence) + '.stdout')).write_bytes(built.stdout)
                (EVIDENCE / ('build_' + str(sequence) + '.stderr')).write_bytes(built.stderr)
                builds.append({'sequence': sequence, 'exit_code': built.returncode,
                               'result': json.loads(built.stdout) if built.returncode == 0 else None,
                               'cloud_config_raw_bytes_unchanged': build_before == digest_paths(checkout, build_paths),
                               'deployment_manifest_raw_bytes_unchanged': deployment_before == sha256((checkout / 'audit/deployment.json').read_bytes()).hexdigest(),
                               'stdout_sha256': sha256(built.stdout).hexdigest(),
                               'stderr_sha256': sha256(built.stderr).hexdigest()})
            full = subprocess.run([sys.executable, '-X', 'utf8', '-B', 'tools/stages.py', 'verify'],
                                  cwd=checkout, env=clean_env(checkout), capture_output=True)
            (EVIDENCE / 'full_offline_verifier.stdout').write_bytes(full.stdout)
            (EVIDENCE / 'full_offline_verifier.stderr').write_bytes(full.stderr)
            document = json.loads(full.stdout) if full.returncode == 0 else {}
            match = re.search(r'Ran (\d+) tests?', document.get('test_output', ''))
            full_verification = {'command': 'python -B tools/stages.py verify',
                                 'execution_directory': 'independent disposable LF checkout',
                                 'exit_code': full.returncode,
                                 'local_tests_passed': document.get('local_tests_passed') is True,
                                 'reported_test_count': int(match[1]) if match else None,
                                 'source_hash': document.get('source_hash'),
                                 'builds': builds,
                                 'builds_idempotent_and_raw_bytes_preserved': all(
                                     item['exit_code'] == 0 and item['cloud_config_raw_bytes_unchanged']
                                     and item['deployment_manifest_raw_bytes_unchanged']
                                     and item['result'].get('config_changed') is False for item in builds),
                                 'stdout_sha256': sha256(full.stdout).hexdigest(),
                                 'stderr_sha256': sha256(full.stderr).hexdigest(),
                                 'financial_evidence': False}
            export_readonly &= checkout_before == digest_paths(checkout, protected_names)
    after = digest_paths(ROOT, watched)
    result = {'kind': 'developer_auxiliary_wr28_audit_only_end_to_end', 'reviewed_commit': commit,
              'execution_environment': {'python_version': sys.version, 'platform': sys.platform,
                  'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1',
                  'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                  'NUMEXPR_NUM_THREADS': '1', 'VECLIB_MAXIMUM_THREADS': '1'},
              'cases': rows, 'process_count': len(rows),
              'success_cases': sum(row['expected_success'] for row in rows),
              'negative_cases': sum(not row['expected_success'] for row in rows),
              'all_expected_outcomes_observed': all(row['result_matches_expected'] for row in rows),
              'main_source_config_tests_protected_bytes_unchanged': before == after,
              'checker_protected_bytes_unchanged': export_readonly,
              'protected_raw_bytes_equal_across_two_exports_and_lf_checkout': protected_equal_across_modes,
              'protected_file_count': len(protected_names), 'old_wrong_declarations_retained': True,
              'full_offline_verification': full_verification,
              'cloud_calls': 0, 'provider_calls': 0, 'budget_debits': 0,
              'gpt_work_acceptance': False, 'phase_2_accepted': False, 'financial_evidence': False}
    result['passed'] = (result['all_expected_outcomes_observed'] and before == after and export_readonly
                        and protected_equal_across_modes and len(protected_names) == 122
                        and (full_verification is None or (full_verification['exit_code'] == 0
                             and full_verification['local_tests_passed']
                             and full_verification['builds_idempotent_and_raw_bytes_preserved'])))
    (EVIDENCE / 'new_checker_end_to_end_result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['passed'] else 1)
