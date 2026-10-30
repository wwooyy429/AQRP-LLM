# Phase 2 certification diagnostic task

This is a Research-only, source-bound diagnostic path. It runs the existing
`data_certification` kernel on already-ingested QuantConnect Cloud references.
It does not obtain missing provider records, authenticate historical vendor
delivery, produce financial evidence, certify platform billing or enable final
evaluation. A completed computation can report `insufficient_evidence`.

## Trusted operator sequence

1. List QuantConnect projects and retain the actual native response. Use only a
   returned project ID. Read the charter, field catalog, partitions and budget.
2. Build one shared deployment using `python -B tools/research.py build` and
   freeze the implementation. Fill an explicit task containing a
   `DataCertificationPlan`, six content-addressed reference lists, the original
   ingestion binding, the cloud Object Store prefix and capacity requirements.
   A source reference is never a row payload. Financial field definitions must
   be selected from `config/source_catalog.json` with role
   `as_reported_financial_value`; the catalog currently declares only one
   explicit engineering observation and cannot be replaced with an
   LLM-generated field list. Catalog presence is not historical value or
   provenance certification.
3. Use `tools/certification_tasks.py preview --plan-file ... --projects-file ...`
   to produce the complete canonical package. Preview performs no Registry
   mutation or execution admission. The source hash uses the existing stable
   execution manifest, which excludes mutable quota-usage projections.
4. A trusted operator must bind the package to an actual human-authorized
   engineering round through `tools/engineering_round.py`. Its fixed grant
   reserves existing normal/reserve capacity. The new task kind cannot use the
   legacy ungranted engineering allowance, change global limits or open final
   testing. Historical package schemas and grant hashes remain unchanged.
5. `freeze`, then `register`, then `claim` on the new CLI publish immutable
   metadata and predebit configuration/Research quota. No command contacts QC.
   A pending/unknown engineering task on the same project blocks a new task.
6. `prepare --attempt ...` binds the charged attempt, full plan, source manifest,
   deployment manifest and all input references. Upload only the returned inert
   `_collection_task_input.py`; this slot is already excluded by the explicit
   deployment-v2 policy and does not overwrite an in-flight engineering input.
   The local file is under `audit/certification_task_inputs/` and contains
   metadata only. The existing core source character limit is enforced.
7. `cell --attempt ...` generates the fixed no-catch entry. Upload this source,
   read the actual cell back, and supply that native `jupyter_read_cell` envelope
   to `dispatch --attempt ... --tool-file ...`. Only an output of
   `should_execute=true` permits the trusted caller's single precharged
   `jupyter_execute_cell` call. The durable dispatch binding is written before
   that external call. A lost response never authorizes a duplicate execution.
8. The fixed cloud entry constructs a QuantBook, NY time zone, SPY exchange
   calendar and the configured Object Store. It reads existing references only;
   before adding SPY it pins the frontier to the NY calendar day preceding the
   preregistered exclusive end, strictly before2024. It issues no History or
   universe request. Before writing metadata, the live
   SDK must report capacity for at least three metadata objects and the frozen
   byte/file reserve. The source/deployment check and the shared kernel run in
   QC Cloud. Actual rows and derived row values remain there.
9. Pass the unchanged native execute-cell envelope to
   `result --attempt ... --tool-file ...`. The fixed parser accepts a single
   aggregate marker or the registered source/cell-bound notebook-error grammar.
   It distinguishes a runtime failure from transport failure or compilation.
   It settles the same charged attempt, preserving spent quota and all history.
   Ordinary public `record_submission`/`consume_completion` callbacks are
   disabled for this task kind. The fixed parser writes an immutable native
   response/binding/submission/completion hash receipt. Both ordinary base-class
   callbacks and generic Registry pending/completed/failed entry points require
   that exact original proof, including journal replay. A binding alone is
   insufficient; free success/failure flags cannot manufacture a terminal.

## Fixed boundaries

- New tasks use explicit `task_kind=data_certification`, schema1,
  `scope=engineering`, Research only and zero automatic retries. Renaming or
  deleting reserved certification fields cannot downgrade into a generic task.
- Task metadata is at most32 KiB, at most128 immutable inputs, one source-bound
  cell dispatch and one normal execution per registered operation. No new
  configuration, alternate operation, LEAN stage, retry or free status flag may
  bypass the authoritative Registry's admission checks.
- The worker report has a closed schema of core checks, integer counts,
  content-addressed references, bounded gaps and source/capacity observations.
  It exports no rows, SIDs, prices or financial values. The observation's own
  report hash, planned interval, references, financial-catalog hash, source
  namespace and synthetic classification are checked.
- Even all declared observations passing leaves vendor provenance,
  full historical US200, actual availability, financial vintage, formal
  Research and financial-evidence flags false. These are software diagnostics,
  not an independent financial test or acceptance decision.
- The native bootstrap, actual QC SDK/version, complete historical sources,
  provenance receipts, store entitlement and actual platform invoice still need
  real external evidence. Synthetic tests cannot authenticate them. Current
  account capacity may require a separately authorized and verified storage
  remedy before any actual dispatch; this module purchases nothing.
- Proof hashes preserve the trusted fixed-parser observation boundary. They do
  not protect against a trusted filesystem writer inventing every source and
  native receipt, and do not authenticate a remote vendor or invoice issuer.

The local `status`, preview, cell-generation and report parsing commands do not
grant permissions. A human-authorized operator must enforce real connector
permissions and call limits, retain actual tool envelopes and distinguish
submission acknowledgement from completed execution. Stage acceptance still
requires independent review of the exact final source version.
