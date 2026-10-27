from pathlib import Path
import hashlib,json
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion/certification';p=root/'cloud/qresearch/data_certification.py';value=p.read_text(encoding='utf-8')
value=value.replace('from .universe import INCLUDED, select_liquid_universe','from .universe import select_liquid_universe')
value=value.replace('_CONTEXT = "data-certification/v1/contexts/"\n','')
value=value.replace('    "ambiguous_financial_cells", "known_eligible_candidate_expected_cells", "missing_candidate_session_cells",\n    "incomplete_candidate_histories")','    "ambiguous_financial_cells")')
value=value.replace(', "all_known_eligible_candidate_histories_complete"}', '}')
value=value.replace(', "context_ref"} | _FALSE_FLAGS','} | _FALSE_FLAGS')
value=value.replace('not isinstance(path, str) or len(path) > 256 or _PATH.fullmatch(path) is None','not isinstance(path, str) or _PATH.fullmatch(path) is None')
a=value.index('            active = [row for row in masters',value.index('def audit_data_certification'))
b=value.index('            ranked = select_liquid_universe',a);value=value[:a]+value[b:]
needle='        by_sid = {sid: [row for row in active if row["sid"] == sid] for sid in ranked}'
value=value.replace(needle,'        active = [row for row in masters if row["effective_from"] <= formation and row["available_at"] <= formation\n                  and (row["effective_to"] is None or formation < row["effective_to"])]\n'+needle)
value=value.replace('        "all_known_eligible_candidate_histories_complete": counts["known_eligible_candidate_expected_cells"] > 0\n            and not counts["incomplete_candidate_histories"],\n','')
a=value.index('    context = {"schema_version": 1, "plan": plan.to_dict()');b=value.index('    report = {"schema_version": 1, "kind": "data_certification_observed_scope"',a);value=value[:a]+value[b:]
value=value.replace(', "context_ref": context_ref,', ',')
value=value.replace('def summarize_certification_scope(store, scope_manifest, expected_hash, *, calendar, synthetic=False):','def summarize_certification_scope(store, scope_manifest, expected_hash, *, synthetic=False):')
value=value.replace('    """Recompute frozen partition reports before aggregating their metadata.','    """Aggregate exact frozen partition reports without re-reading raw rows.')
value=value.replace('    if not synthetic and not isinstance(calendar, ExchangeCalendar):\n        _fail("An actual exchange calendar adapter is required for partition revalidation")\n','')
value=value.replace('        if not _clock(report["warmup_start"]) < begin:\n            _fail("Partition warmup does not precede its declared scope")\n','')
a=value.index('        context_ref = _references([report["context_ref"]])[0]');b=value.index('        reports.append(report)',a);value=value[:a]+value[b:]
value=value.replace('"raw_rows_recomputed_here": True','"raw_rows_recomputed_here": False')
raw=value.encode('utf-8');digest=hashlib.sha256(raw).hexdigest();expected=json.loads((root/'.git/repair-work/stage2-completion/peer-certification/initial_findings.json').read_bytes())['source_raw_sha256']
(scratch/'pre_peer_reconstructed_data_certification.py').write_bytes(raw)
result={'reconstructed_raw_sha256':digest,'peer_recorded_raw_sha256':expected,'exact_match':digest==expected,'reconstruction_from_inverse_of_recorded_patch':True,'not_claimed_original_until_hash_match':True};(scratch/'pre_peer_reconstruction.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
