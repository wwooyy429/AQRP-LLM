# G4 cloud evidence API (engineering only)

Only the three new files are owned by this task: cloud/qresearch/data_certification.py, tools/data_certification.py and tests/test_data_certification.py. No config/template/budget changes or native calls.

DataCertificationPlan exact keys: schema_version=1, plan_id, start, end_exclusive, warmup_start, timezone=America/New_York, source_manifest_hash, data_version, ingestion_namespace, financial_catalog, universe_size=200, liquidity_lookback_sessions=20. Endpoints are NY midnights, warmup<start<end<=2024-01-01. Each financial_catalog entry freezes exact source path plus unit and period_accessor. Plan does not enable any FactorSpec fields.

Read existing completed HistoricalBatchIngestor liquidity_refs/financial_refs of the exact store, synthetic flag, source namespace, version and catalog. New audit input tables are content-addressed under data-certification/v1/inputs, pinned to the plan hash. Registered private table rows:
- membership: formation_at,sids (exact200 in ranking order)
- prices: sid,session,available_at,open,high,low,close,volume,normalization=raw,source_revision
- security_master: sid,ticker,effective_from,effective_to,available_at,instrument_type,listed,exchange
- corporate_actions: sid,event_time,available_at,kind,source_revision; kind in dividend/split/mapping/delisting/ipo

Call audit_data_certification(store,plan,calendar=actual ExchangeCalendar,ingestor=...,liquidity_refs=...,financial_refs=...,membership_refs=...,price_refs=...,security_master_refs=...,corporate_action_refs=...). All new raw inputs and context/report bytes remain in QC cloud for real data. Helper store_certification_table has synthetic=False by default. The program performs no History request or dispatch. One bounded scope is capped at250000 rows per component; use frozen partitions rather than truncate full history.

Report contains only counts, canonical hashes and refs, never SID lists, prices or financial values. Raw source batches are verified once and the exact existing ingestion/rank calculations reuse those rows. All old eligible candidate inventories are checked for20 actual expected sessions even if rank201 could fill a dropped name. Missing financials never change membership. Date-only filings wait through the next actual exchange close. Report.status=observations_passed means declared-row conformance only, not vendor-authenticated or Research approval.

summarize_certification_scope requires explicit calendar. scope_manifest exact keys: schema_version,start,end_exclusive,source_manifest_hash,ingestion_namespace,data_version_hash,financial_catalog_hash,partitions. Each partition has plan_hash,start,end_exclusive,report_ref (or null for missing). Pin content_hash(scope_manifest) as expected_hash. Scope aggregator revalidates hash-bound plan/source context and recomputes every original private partition input against that calendar; a claimed passed report with zero counts/empty refs cannot pass. Unknown/changed/duplicate/overlapping scopes reject; uncovered intervals or absent reports remain insufficient. Counts are partition sums, not unique rows because warmup may repeat. A2018 fixture cannot cover2010–2023.

All provenance/full-universe/actual-availability/financial-vintage/research-certification flags stay false. Current adapters lack authenticated historical all-market inventory, vendor revision/delivery/ingestion and security-master/action coverage receipts. Event identity tables do not prove cash adjustments, split factors, delisting value recovery or trading accounting. Existing production audit gate is unchanged.

Metadata-only CLI: python -B tools/data_certification.py capabilities; python -B tools/data_certification.py validate-plan --plan-file <permitted metadata.json>. CLI never accepts a row-data file or dispatches a job. Current config/source_catalog has0 as_reported_financial_value entries, captured in capabilities.stdout.
