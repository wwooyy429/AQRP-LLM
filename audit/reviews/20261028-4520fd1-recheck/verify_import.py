"""Read-only verification of exact imported review evidence, not acceptance."""
from pathlib import Path, PureWindowsPath
import argparse
import hashlib
import json
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(*, original_zip=None):
    root=Path(__file__).resolve().parent
    index=json.loads((root/'import_index.json').read_bytes())
    for name,expected in index['copied_files'].items():
        path=(root/name).resolve()
        assert path.is_relative_to(root.resolve()),name
        assert digest(path.read_bytes())==expected,name
    report=json.loads((root/'evidence/formal_report.json').read_bytes())
    assert report['reviewed_source_commit']==index['reviewed_commit']=='4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8'
    assert report['software_acceptance']['phase2_overall']=='not_accepted'
    assert report['findings']==[] and report['historical_findings']['new_WRs']==[]
    assert report['budget_replay']['events']==46
    assert {key:value['total'] for key,value in report['budget_replay']['usage'].items()}==dict(configurations=12,research=15,lean=2)
    assert len(report['platform_evidence_level']['LEAN']['required_checks'])==7
    assert report['platform_evidence_level']['LEAN']['actual_runtime_check_results'] is None
    zip_checked=False
    if original_zip is not None:
        raw=original_zip.read_bytes()
        assert digest(raw)==index['original_zip_sha256']
        with zipfile.ZipFile(original_zip) as archive:
            assert archive.testzip() is None
            members=[m for m in archive.infolist() if not m.is_dir()]
            names=[m.filename for m in members]
            assert len(names)==len(set(names))==index['original_total_files']
            prefix=PureWindowsPath(index['original_bundle']).name+'/'
            if not all(n.startswith(prefix) for n in names):
                prefix=''
            mapping={m.filename[len(prefix):]:m for m in members}
            manifest_raw=archive.read(mapping['artifact_manifest.json'])
            assert digest(manifest_raw)==index['original_artifact_manifest_sha256']
            manifest=json.loads(manifest_raw)
            assert set(mapping)==set(manifest)|{'artifact_manifest.json'}
            for name,expected in manifest.items():
                assert digest(archive.read(mapping[name]))==expected,name
            source_raw=archive.read(mapping['source_git_manifest.json'])
            assert digest(source_raw)==index['original_source_manifest_sha256']
            zip_checked=True
    return dict(kind='developer_readonly_archive_integrity_check',copied_files_verified=len(index['copied_files']),
        reviewed_commit=index['reviewed_commit'],original_zip_checked=zip_checked,
        independent_report_preserved=True,phase2_accepted=False,new_product_test_runs=0,
        cloud_calls=0,budget_changed=False,financial_evidence=False,final_test_enabled=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-zip',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(original_zip=args.original_zip),ensure_ascii=False))
