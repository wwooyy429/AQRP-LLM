"""Additional synthetic failure settlement; no claim of actual native failure."""
import hashlib,json,unittest
from pathlib import Path
import independent_recovery_support as h

records=[]
for version in (1,2):
    context=h.setup_case(version,'failed-research-v'+str(version));case=context['case'];attempt=context['attempt']
    observation=h.envelopes(context,context['admission'],'research');value=json.loads(observation['result'].read_bytes())
    native=value['result']['structuredContent'];text=native['outputs'][0]['text'].split(' ',1)[1]
    wrapper=json.loads(h.base64.b64decode(text));wrapper['cloud_report']['checks']['raw_data_received']=False
    wrapper['cloud_report']['status']='failed';wrapper['report_ref']['sha256']=h.content_hash(wrapper['cloud_report'])
    native['outputs'][0]['text']='AQRP_ENGINEERING_JSON '+h.base64.b64encode(h.canonical_json(wrapper)).decode()
    value['result']['content'][0]['text']=json.dumps(native);h.dump(observation['result'],value)
    usage=h.registry(case).snapshot()['usage'];h.drift(context,attempt)
    result=h.okay(h.invoke(case,['research-result','--attempt',attempt,'--tool-file',observation['result']],'failed-research-v'+str(version)))
    assert result['status']=='failed' and h.registry(case).snapshot()['usage']==usage
    records.append({'version':version,'kind':'Research synthetic fixed-check failed report','status':result['status'],
        'usage_unchanged':True,'real_native_failure_claimed':False})

    context=h.setup_case(version,'failed-lean-v'+str(version));case=context['case'];attempt=context['attempt']
    observation=h.envelopes(context,context['admission'],'research')
    assert h.okay(h.invoke(case,['research-result','--attempt',attempt,'--tool-file',observation['result']],'pre-lean-research-v'+str(version)))['status']=='completed'
    lean=h.okay(h.invoke(case,['claim','--stage','lean'],'failed-lean-claim-v'+str(version)))['attempt_id']
    admission=h.okay(h.invoke(case,['prepare','--attempt',lean],'failed-lean-prepare-v'+str(version)))
    observation=h.envelopes(context,admission,'lean')
    assert h.okay(h.invoke(case,['backtest-submission','--attempt',lean,'--tool-file',observation['submission']],'failed-lean-sub-v'+str(version)))['status']=='pending'
    value=json.loads(observation['result'].read_bytes());native=value['result']['backtest']
    native.update(status='Runtime Error',progress=0.5,error='INDEPENDENT-SYNTHETIC-ERROR-TEXT',stacktrace='INDEPENDENT-SYNTHETIC-ERROR-TEXT')
    h.dump(observation['result'],value);usage=h.registry(case).snapshot()['usage'];h.drift(context,lean)
    result=h.okay(h.invoke(case,['backtest-result','--attempt',lean,'--tool-file',observation['result'],'--logs-file',observation['logs']],'failed-lean-result-v'+str(version)))
    assert result['status']=='failed' and h.registry(case).snapshot()['usage']==usage
    assert not any(b'INDEPENDENT-SYNTHETIC-ERROR-TEXT' in p.read_bytes() for p in (case/'audit/runtime').rglob('*') if p.is_file())
    records.append({'version':version,'kind':'LEAN synthetic delivered Runtime Error envelope','status':result['status'],
        'usage_unchanged':True,'error_text_not_persisted':True,'real_native_failure_claimed':False})

summary={'commit':'ae2b8985f3799c246e90341370f86d80483f63ed','programs':1,'subcases':4,'passed':4,'failures':0,
    'records':records,'stats':h.STATS,'argv':h.sys.argv,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'actual_worker_executions':0,'limits':'self-built whitelisted metadata only; fixed-check false inside success cell is not an actually failed Research execution; LEAN error envelope also synthetic'}
(h.OUT/'failure_settlement_result.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
(h.OUT/'failure_command_log.json').write_text(json.dumps(h.LOG,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
