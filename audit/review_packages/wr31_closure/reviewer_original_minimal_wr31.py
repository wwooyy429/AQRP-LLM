"""Independent literal pagination contract; exits1 whileWR31 is present."""
from pathlib import Path
import importlib.util,json,sys
source=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('fixed_inventory_analyzer',source);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
rows=[{'name':'synthetic-a.json','type':'JSON','display_size':'1 KB','last_modified':'synthetic','exact_bytes':None}]
cases=[('valid','1 to 1 of 1',True),('negative_start','-1 to 1 of 1',False),('contradictory_ranges','1 to 1 of 1; 2 to 2 of 2',False)]
observed=[]
for label,paging,expected in cases:
 result=a.analyze({'scope_root':'synthetic','observations':[{'path':'synthetic','paging':[paging,'Page 1 of 1'],'rows':rows}]},{},{})
 observed.append({'case':label,'paging':paging,'expected_complete':expected,'actual_complete':result['directories'][0]['all_entries_observed_at_UI_metadata_level'],'actual_UI_tree_complete':result['UI_tree_listing_complete_within_declared_scope'],'deletion_authorized':result['objects'][0]['deletion_authorized']})
print(json.dumps(observed))
assert all(r['expected_complete']==r['actual_complete'] for r in observed),'WR-31: invalid/ambiguous paging accepted as complete'
