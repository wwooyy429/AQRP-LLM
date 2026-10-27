import hashlib,json,shutil
from pathlib import Path
OUT=Path(__file__).resolve().parent
for extension in ('json','md'):
    backup=OUT/('report_before_crash.'+extension)
    if not backup.exists():shutil.copy2(OUT/('report.'+extension),backup)
report=json.loads((OUT/'report_before_crash.json').read_text(encoding='utf-8'))
crash=json.loads((OUT/'crash_addendum/results.json').read_text(encoding='utf-8'))
assert crash['passed']==4 and crash['failed']==0 and crash['source_and_authority_unchanged']
report['initial_6_62_crash_scope']='Manually constructed accepted-pointer-only state rejects later refusal; existing admission without protocol is not backfilled. These original cases did not inject publication failures or verify replay repair.'
report['crash_addendum']={
    'unit_methods':0,'programs':1,'manual_probes':4,'passed':4,'failed':0,'first_failure':None,
    'stats':crash['stats'],'probes':crash['probes'],
    'fixture_origin':'Copies of this reviewer independently constructed v2 native-base fixture; not developer test fixtures.',
    'fault_injection':'Actual production FilesystemArtifactStore.write_once and Registry._append calls raise a synchronous injected exception at the selected boundary. Recovery/refusal uses actual CLI in a separate process.',
    'shared_lock_static_review':{
        'accepted':'engineering_tasks.py:583-602 holds self.store.locked(self.registry.LOCK) while checking fresh state, publishing accepted identity, writing full evidence and transitioning.',
        'rejection':'engineering_tasks.py:662-679 holds that same Registry.LOCK while checking fresh accepted pointer/external ID/state, writing rejection and transitioning.',
        'accepted_wins':'Its published summary blocks rejection even when full original/journal has not been written.',
        'rejection_wins':'Accepted transaction reads fresh failed state under lock and rejects, as original6/62 actual CLI already verified.',
        'new_simultaneous_two_process_race_test':False},
    'limits':crash['limits'],'results':'crash_addendum/results.json','command_log':'crash_addendum/command_log.json',
    'execution':'crash_addendum/execution.json','raw_stdout':'crash_addendum/first.stdout','raw_stderr':'crash_addendum/first.stderr'}
report['counting_before_crash_addendum']=dict(report['counting'])
report['counting']['manual_probe_programs']=2;report['counting']['manual_probe_subcases']=8
report['counting']['actual_CLI_processes']+=crash['stats']['actual_CLI_processes']
report['CLI_command_breakdown']['crash_addendum']={
    'backtest-rejection':3,'backtest-submission':2,'prepare':2}
report['remaining_unverified'].append('No OS kill/power-loss/storage-durability certification or new two-process acceptance-versus-rejection race test; shared-lock source logic and controlled exception boundaries are the tested scope.')
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
text=(OUT/'report_before_crash.md').read_text(encoding='utf-8')
text=text.replace('另1程序／4个参数化失败探针','另2程序／8个参数化探针（原失败4、新crash4）').replace('实际CLI子进程102','实际CLI子进程109')
text+='''
补充真实写入故障：原6/62只构造了崩溃后状态，未注入故障。本次另1个独立程序的4个手工探针首跑全部通过，0 unit方法、7个CLI、0 finish/worker。分别在生产接受指针后原件前、原件后pending追加前注入异常：真实拒绝CLI均阻断，接受CLI同回执重放补齐原件/单个pending事件而不扣费。prepare输入后准入前失败可重试完成；准入后protocol前失败则恢复不补标记，拒绝继续阻断且账本/用量不变。详见`crash_addendum/results.json`及其raw/命令。

共享锁静态核对：接受与拒绝都在同一`self.store.locked(self.registry.LOCK)`内重读当前状态后发布/结算；接受先行则指针阻断拒绝，拒绝先行则failed状态阻断接受。没有另做同时双进程竞争、OS kill或断电测试；不能把同步异常注入扩大为物理存储持久性认证。原62例/原兼容首跑输出未改，补测前报告另存`report_before_crash.json/.md`。
'''
(OUT/'report.md').write_text(text,encoding='utf-8')
manifest=[]
for path in OUT.rglob('*'):
    if path.is_file() and 'cases' not in path.relative_to(OUT).parts and path.name!='manifest.json':
        manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'commit':report['commit'],'excluded':'copied synthetic cases/ trees; scripts/raw/commands/results/pre-addendum reports included','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counting':report['counting'],'new_crash_passed':4,'manifest_files':len(manifest)},ensure_ascii=False))
