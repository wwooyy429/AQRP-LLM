"""Synthetic dependency-closure probe; no source mutations or cloud access."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
root=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(root/'cloud'))
from qresearch.collection import CollectionError
from qresearch.collection_storage import processing_contract_sha256
folder=root/'cloud/qresearch'
names=('historical_source.py','collection.py','artifacts.py','contracts.py','financial_fields.py')
sources={name:(folder/name).read_bytes() for name in names}
def runtime_hash(selected):
    def read(path):return selected[path.name]
    with patch('qresearch.collection_storage.Path.read_bytes',read):
        return processing_contract_sha256()
first=runtime_hash(sources)
changed=dict(sources)
changed['financial_fields.py']=changed['financial_fields.py'].replace(b'presence("12M")',b'presence("3M")')
assert changed['financial_fields.py']!=sources['financial_fields.py']
second=runtime_hash(changed)
try:
    processing_contract_sha256({key:value for key,value in sources.items() if key!='financial_fields.py'})
except CollectionError:missing_rejected=True
else:missing_rejected=False
value={'synthetic':True,'runtime_financial_body_mutation_changes_hash':first!=second,
       'current_adapter_missing_financial_dependency_rejected':missing_rejected,
       'first_hash':first,'mutated_helper_hash':second,'market_data_calls':0,'budget_mutations':0}
print(json.dumps(value))
raise SystemExit(0 if first!=second and missing_rejected else 1)
