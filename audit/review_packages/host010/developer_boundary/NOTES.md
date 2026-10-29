# host010 developer-support boundary notes

Scope: offline synthetic developer-support check. This is not GPT independent acceptance, market-data coverage evidence, an economic discovery, or a financial test. No QC / Research / LEAN / market / external calls are authorized in this check. Product files and authoritative budget/registry are read only.

Read: workspace AGENTS.md; config/development.json; config/task_followup.json; cloud/qresearch/task_followup.py; tools/task_followup.py; tools/stage2.py; cloud/qresearch/engineering_receipts.py; existing follow-up fixtures.

Proposed boundary checks while host implementation is pending:
- Dispatch disabled must return before opening any production registry/store.
- Only exact next.should_execute True authorizes fixed project-scoped tools. Fixed project discovery needs a separate durable, bounded prerequisite reservation.
- Every request must persist correlation ID, exact tool name, and canonical typed arguments before output; unknown responses and restarts must not redispatch.
- A shared host lock must guarantee one process emits one request without nesting Registry.LOCK.
- Wrong/duplicate correlation IDs, foreign tools, changed arguments, boolean-number coercion, duplicate JSON keys, NaN, malformed lines, and excessive line sizes must be rejected before ledger mutation.
- Historical Completed metadata cannot authorize a tool forbidden by host capabilities and cannot settle the Registry. Input/LLM booleans cannot override the capability set.
- Late native completion may settle via existing fixed engineering_receipts parser and bridge despite host attention state.

Implementation-specific reproducible checks will be appended after tools/followup_host.py appears. Artifacts stay inside this directory.
