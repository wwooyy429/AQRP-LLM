"""Two hypothetical delivered terminals; no actual platform calls or ledger writes."""
from frontier_support import *
for platform_status,expected in [('completed','completed'),('runtime_error','failed')]:
 store,registry,task,record=copied_context()
 assert registry.snapshot()['usage']==EXPECTED and len(rows(registry))==46
 assert record['status']=='pending'
 observation=synthetic_terminal(task,record,status=platform_status)
 result=task.consume_completion(ATTEMPT,completion_source=lambda _:observation)
 assert result.status==expected
 assert registry.snapshot()['usage']==EXPECTED and len(rows(registry))==47
 saved=store_bytes(store)
 def forbidden(_):raise AssertionError('Terminal replay tried to read a provider')
 assert task.consume_completion(ATTEMPT,completion_source=forbidden).status==expected
 assert store_bytes(store)==saved
 claimed=task.claim('lean',allocation='normal')
 assert claimed.status==expected and claimed.should_execute is False
 assert store_bytes(store)==saved
 print(json.dumps({'hypothetical_terminal':platform_status,'settled_as':expected,
  'usage_config_Research_LEAN':[12,15,2],'journal_events':47,
  'replay_extra_events':0,'real_platform_calls':0,'financial_evidence':False}))
