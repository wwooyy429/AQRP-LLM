from pathlib import Path
R=Path(__file__).resolve().parent
prior=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027\archive_agent\verify_source_archive.py')
code=prior.read_text(encoding='utf-8')
code=code.replace("O=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027')", "O=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ccad61d-20261027')")
code=code.replace("C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6';B='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'", "C='44676db609b3b7c2175fa7fa4f19c8ccf8165458';B='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'")
code=code.replace("pack='audit/review_packages/wr22_wr24/'", "pack='audit/review_packages/wr25_wr27/'")
code=code.replace('developer654_final_report_not_independent_acceptance','developer668_final_report_not_independent_acceptance').replace("dev['test_methods']==654", "dev['test_methods']==668").replace("'Ran 654 tests'", "'Ran 668 tests'").replace('developer_tested_source_count_scope140','developer_tested_source_count_scope141')
start=code.index("    provisional=doc(files[pack+'provisional_before_unknown_current/stage_verification.json'])")
end=code.index("    journal=files[",start)
code=code[:start]+"    check('developer_single_final_source_freeze', 'One final frozen version' in dev['source_freeze_note'] and dev['all_tested_source_bytes_unchanged'] is True)\n"+code[end:]
code=code.replace("files['audit/wr22_wr24_source_reference_comparison.json']", "files['audit/wr25_wr27_source_reference_comparison.json']")
start=code.index('    # Complete old package verification')
end=code.index('    development=doc(',start)
replacement='''    # Verify full ccad sealed originals and the developer's explicitly selective copy.
    original={p.relative_to(O).as_posix():p for p in O.rglob('*') if p.is_file()};om=doc((O/'artifact_manifest.json').read_bytes());bad=[p for p,h in om.items() if p not in original or sha(original[p].read_bytes())!=h]
    check('old_complete15119_manifest_and15120_directory',len(om)==15119 and len(original)==15120 and set(original)==set(om)|{'artifact_manifest.json'} and not bad,{'bad':bad})
    zpath=O.with_suffix('.zip');zh=sha(zpath.read_bytes());selpath='audit/reviews/20261027-ccad61d-windows/developer_archive_selection.json';selection=doc(files[selpath]);prefix='audit/reviews/20261027-ccad61d-windows/'
    check('old_completeZIP39319686_identity',zh=='2ffc9089ad19a5675d18cafb5379262db7c99a431e518ae4f52cb2dd094b313c' and zpath.stat().st_size==selection['original_zip_bytes']==39319686,{'bytes':zpath.stat().st_size,'raw_sha256':zh})
    with zipfile.ZipFile(zpath) as z:
        names=z.namelist();prefixz=O.name+'/';bad=[]
        check('old_completeZIP15120_inventory',len(names)==15120 and len(names)==len(set(names)) and set(names)=={prefixz+p for p in original})
        for name in names:
            p=name[len(prefixz):];h=om.get(p) or sha(original[p].read_bytes())
            if sha(z.read(name))!=h:bad.append(p)
        check('old_completeZIP_all_member_raw_hashes',not bad,{'verified':len(names),'bad':bad})
    old_git={}
    for label,item in doc((O/'source_git_manifest.json').read_bytes()).items():
        fixed=tree(item['commit'],'old_original_'+label+'_archive');computed={p:sha(b) for p,b in fixed.items()};old_git[label]={'commit':item['commit'],'files':len(computed)}
        check('old_original_Git_manifest_'+label,len(computed)==item['count'] and computed==item['files'] and all(om[item['directory']+'/'+p]==h for p,h in computed.items()),old_git[label])
    selected=selection['selected_originals'];bad=[]
    for row in selected:
        b=files.get(prefix+row['path'])
        if b is None or sha(b)!=row['raw_sha256'] or len(b)!=row['bytes'] or b!=original[row['path']].read_bytes():bad.append(row['path'])
    check('selective381_original_raw1581651',len(selected)==381 and sum(x['bytes'] for x in selected)==1581651 and not bad,{'bad':bad})
    def reason(p):
        parts=Path(p).parts;base=parts[-1]
        if parts[0] in ('source','baselines'):return 'omitted_duplicate_fixed_Git_snapshot'
        if base.endswith('.index'):return 'omitted_reconstructible_Git_index'
        if p in ('artifact_manifest.json','source_git_manifest.json','archive_agent/source_raw_git_manifest.json'):return 'omitted_complete_large_manifest_retained_in_ZIP'
        if p in ('change.diff','PR_complete_patch.stdout','archive_agent/baseline_to_candidate_full_patch.stdout'):return 'omitted_large_full_patch_retained_in_ZIP'
        if base in ('current_complete_name_status.stdout','PR_complete_name_status.stdout','change.names'):return 'omitted_redundant_full_name_list'
        if p=='archive_agent/old_cloud_source_rows.json':return 'omitted_existing_archived_cloud_reference_copy'
        if len(parts)==1:return 'selected'
        if parts[0] in ('cert_agent','wr25_confirmation','wr26_confirmation','wr27_confirmation','archive_agent'):return 'selected'
        if parts[0]=='protocol_agent':
            if len(parts)==2 or parts[1] in ('legacy_adapted_scripts','recovery_adapted_scripts','original_mre','wr21'):return 'selected'
            if parts[1] in ('boundaries_first','research_failure') and ((len(parts)==3 and base!='command_log.json') or (parts[1]=='boundaries_first' and parts[2]=='parallel')):return 'selected'
            if base in ('results.json','test_results.json','execution.json','execution_records.json','summary.json'):return 'selected'
        if p=='runs/execution_records.json':return 'selected'
        if parts[0] in ('admission_agent','control_replay','recovery_agent') and len(parts)==2 and (base.endswith('.py') or base in ('report.json','report.txt','execution_records.json','new_first_results.json','new_contract_corrected_results.json','script_bindings.json','worker_identity_first_results.json','pure_corrected_results.json','cli_first_results.json','preflight_cli_first_results.json')):return 'selected'
        return 'omitted_historical_replay_detail_retained_in_ZIP'
    expected=set();groups=collections.Counter();nonutf=[]
    for p,path in original.items():
        why=reason(p)
        if why=='selected':
            try:path.read_bytes().decode('utf-8');expected.add(p)
            except UnicodeDecodeError:groups['omitted_non_UTF8_original_retained_in_ZIP']+=1;nonutf.append(p)
        else:groups[why]+=1
    check('selective_exact_rules_and14739_omitted',expected=={r['path'] for r in selected} and dict(groups)==selection['omitted_groups'] and len(original)-len(selected)==selection['omitted_original_count']==14739,{'groups':dict(groups),'non_UTF8_omitted':nonutf})
    for row in selection['verified_external_inventory_refs']:
        p=row['path'];b=original[p].read_bytes();check('external_manifest:'+p,sha(b)==row['raw_sha256'] and len(b)==row['bytes'])
    for row in selection['verified_external_non_UTF8_refs']:
        p=row['path'];b=original[p].read_bytes();check('external_non_UTF8:'+p,sha(b)==row['raw_sha256'] and len(b)==row['bytes'])
    ext={'.gitattributes','ARCHIVE_SCOPE.md','developer_archive_helper.py','developer_archive_selection.json','developer_archive_validation.json','developer_archive_inventory.json','user_pasted_report_original.txt'}
    check('selective_only381_originals_plus7_declared_metadata',{p[len(prefix):] for p in files if p.startswith(prefix)}==expected|ext)
    inv=doc(files[prefix+'developer_archive_inventory.json']);bad=[]
    for row in inv['files']:
        b=files.get(prefix+row['path'])
        if b is None or sha(b)!=row['raw_sha256'] or len(b)!=row['bytes']:bad.append(row['path'])
    check('local_selective_inventory387_plus_itself388',not bad and len(inv['files'])==387 and inv['selected_review_original_count']==381 and inv['developer_metadata_count_including_this_manifest']==6,{'bad':bad})
    pasted=selection['pasted_report'];check('pasted_report_raw_bytes',sha(files[prefix+pasted['path']])==pasted['raw_sha256'] and len(files[prefix+pasted['path']])==pasted['bytes'])
    ac=doc(files['audit/ccad61d_review_archive_check.json']);origreport=doc(original['formal_report.json'].read_bytes())
    check('archive_check_exact_selected_complete_metadata',ac['original_zip_sha256']==zh and ac['original_package_files']==len(original) and ac['original_manifest_registered_files']==len(om) and ac['archived_original_count']==len(selected) and ac['archived_original_raw_bytes']==sum(x['bytes'] for x in selected) and ac['omitted_original_count']==len(original)-len(selected) and ac['archive_selection_ref']['raw_sha256']==sha(files[selpath]) and ac['review_formal_json_raw_sha256']==sha(original['formal_report.json'].read_bytes()) and ac['review_formal_txt_raw_sha256']==sha(original['formal_report.txt'].read_bytes()))
    check('ccad_previous_failed_overall_original_fixes_preserved',ac['software_acceptance']==origreport['software_acceptance'] and ac['stage2_whole_accepted'] is False and origreport['software_acceptance']['overall_status']=='失败' and origreport['financial_evidence'] is False)
    omitted=doc(files[pack+'verification/omitted_working_artifacts.json']);preflight=doc(files[pack+'verification/publication_preflight_first.json']);omitted_details=[]
    devroot=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM 因子生成器')
    for row in omitted['entries']:
        originalpath=devroot/row['original_retained_at'];exists=originalpath.is_file();b=originalpath.read_bytes() if exists else None
        omitted_details.append({'path':row['path'],'original_retained_at':str(originalpath),'exists':exists,'bytes':len(b) if b is not None else None,'raw_sha256':sha(b) if b is not None else None,'claimed_raw_sha256':row['raw_sha256']})
        check('omitted_developer_binary_original_preserved:'+row['path'],row['path'] not in files and exists and len(b)==row['bytes'] and sha(b)==row['raw_sha256'],omitted_details[-1])
    check('binary_preflight_failure_and_nonsource_correction_explicit',preflight['exit_code']==1 and preflight['error_class']=='UnicodeDecodeError' and preflight['source_or_test_changes'] is False and preflight['original_bytes_preserved'] is True and 'not_a_review_original' in omitted['entries'][0]['kind'])
    write(R/'omitted_developer_artifact_verification.json',omitted_details)
'''
code=code[:start]+replacement+code[end:]
code=code.replace('ccad61d-20261027-source-budget-archive','44676db-20261027-source-budget-archive')
(R/'verify_source_archive.py').write_bytes(code.encode())
wrapper=prior.parent.joinpath('run_audit.py').read_bytes();(R/'run_audit.py').write_bytes(wrapper)
print(str(R/'verify_source_archive.py'))
