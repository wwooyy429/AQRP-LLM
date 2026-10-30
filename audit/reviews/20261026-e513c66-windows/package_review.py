from pathlib import Path
import argparse, ast, hashlib, io, json, shutil, subprocess, tarfile, zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-e513c66-20261026')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def raw(sha):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',sha])
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        return {m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
def copy(name):
    src=R/name;dst=OUT/name;dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__'))
    else:shutil.copy2(src,dst)
def verify_sources():
    D=read('formal_report.json'); report={}
    for label,sha,path in [('candidate',D['reviewed_source_commit'],OUT/'source'),('baseline7bf',D['baseline_commit'],OUT/'baselines/7bf716f/source'),('baselinefbe','fbe2454e6ea10aa59211c01f236c54bb251527be',OUT/'baselines/fbe2454/source')]:
        expected=raw(sha);actual={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
        assert expected==actual,(label,'Git bytes differ')
        report[label]={'commit':sha,'count':len(expected),'files':{n:hashlib.sha256(b).hexdigest() for n,b in expected.items()}}
    return report
parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');args=parser.parse_args()
if not args.seal:
    assert all(x['exit_code']==0 for x in read('runs/execution_records.json'))
    assert read('evidence_agent/delivery_evidence_report.json')['passed_checks']==381
    assert read('admission_agent/first_results.json')['passed_methods']==24
    assert read('receipt_agent/report.json')['first_run']['failure_records']==2
    assert read('root_parallel_output.json')['confirmed_false_acceptances']==3
    OUT.mkdir(exist_ok=False)
    for n in ['source','admission_agent','receipt_agent','evidence_agent']:copy(n)
    (OUT/'cli_agent').mkdir()
    for p in (R/'cli_agent').iterdir():
        if p.is_file():copy('cli_agent/'+p.name)
        elif p.name.startswith('case-'):
            # Duplicate source trees are reproducible; preserve their actual changed state and inputs.
            for folder in ['audit/runtime','audit/collection_task_inputs']:
                if (p/folder).exists():copy('cli_agent/'+p.name+'/'+folder)
            for name in ['audit/collection_current.json','config/source_catalog.json','config/budget.json','synthetic_delivered_tool.json']:
                if (p/name).exists():copy('cli_agent/'+p.name+'/'+name)
    for p in (R/'runs').iterdir():
        if p.name=='repository_source':copy('runs/repository_source/audit/stage_verification.json')
        else:copy('runs/'+p.name)
    for name in ['formal_report.txt','formal_report.json','environment.json','github_metadata.json','qc_source_readback.json','change.diff','full_pr2.diff','change_stat.txt','minimal_cli_switch.py','minimal_parallel_carrier.py','root_cli_reconciliation.py','run_root_cli_probes.py','root_parallel_output.json','root_probe_execution.json','run_main_checks.py','replay_archived_script.py','replay_public_class.py','run_offline_review.py','verify_artifacts.py','build_formal_report.py','package_review.py']:copy(name)
    for label,sha in [('7bf716f','7bf716f45fd6183951a492f0201012af717070f0'),('fbe2454','fbe2454e6ea10aa59211c01f236c54bb251527be')]:
        base=OUT/'baselines'/label/'source'
        for name,data in raw(sha).items():
            path=base/name;assert path.resolve().is_relative_to(base.resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (OUT/'source_git_manifest.json').write_text(json.dumps(verify_sources(),indent=2),encoding='utf-8')
    versions=read('environment.json')['dependencies'];(OUT/'requirements-audit.txt').write_text(''.join(k+'=='+v+'\n' for k,v in versions.items()),encoding='utf-8')
    (OUT/'README.txt').write_text('AQRP-LLM e513c66 独立审核包\n正式结论：WR-11、WR-12阻断新增采集任务桥；全系统未验收；无金融证据。\nsource为608份固定Git原件，基线7bf/fbe也逐字节保存。\nPython3.10，pip install -r requirements-audit.txt。\npython -B run_offline_review.py --out <一个不存在的新目录>\n预期：既有回归和准入通过；回执、CLI复现exit1，汇总器验证这些预期退出后exit0，不表示软件通过。\n原始首次失败保留。cli_agent/case-*只保存原运行的状态/输入/变更配置，重复源码由source重建；临时绝对路径是历史执行记录。\nportable复验输出另保存在本包portable_replay；不改固定source。只对审核者脚本的解释器/旧fbe路径建立显式diff。\n没有新增平台、市场、模型、部署或真实预算调用。\n',encoding='utf-8')
    print(str(OUT))
else:
    assert OUT.exists();verify_sources()
    for name in ['formal_report.txt','formal_report.json','root_probe_execution.json','verify_artifacts.py','build_formal_report.py','package_review.py']:shutil.copy2(R/name,OUT/name)
    assert json.loads((OUT/'portable_replay/portable_summary.json').read_text())['unexpected_exit_records']==[]
    for p in [OUT/'minimal_cli_switch.py',OUT/'minimal_parallel_carrier.py',OUT/'run_offline_review.py']:ast.parse(p.read_text(encoding='utf-8'))
    check={'source_verified':True,'candidate_files':608,'baseline7bf_files':451,'baselinefbe_files':313,'portable_expected_exit_reproduction_passed':True,'acceptance':'failed_WR11_WR12','financial_evidence':False}
    (OUT/'artifact_verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
    manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'}
    (OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=OUT.with_suffix('.zip');assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in OUT.rglob('*'):
            if p.is_file():z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest
    result={'directory':str(OUT),'zip':str(archive),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,'manifest_entries':len(manifest),'checks':check}
    (R/'package_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
