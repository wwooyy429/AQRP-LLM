"""Synthetic native __class__ failures; public projection must redact them."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'cloud'))
from qresearch.financial_fields import (FINANCIAL_FIELD_PATH,FinancialFieldError,
 extract_financial_field,financial_field_definition)

class NativeClassFailure:
    @property
    def __class__(self):
        raise RuntimeError('SYNTHETIC_PRIVATE_NATIVE_CLASS_ERROR')

class Period:
    twelve_months=NativeClassFailure()
    def has_period_value(self,period):return True

results=[]
for name,period in (('numeric_type_predicate',Period()),('period_type_predicate',NativeClassFailure())):
    row=NS(financial_statements=NS(income_statement=NS(total_revenue_as_reported=period)))
    try:
        extract_financial_field(row,FINANCIAL_FIELD_PATH,financial_field_definition())
    except Exception as error:
        results.append({'case':name,'exact_owned_error':type(error)is FinancialFieldError,
            'raw_native_runtime_error':type(error)is RuntimeError,
            'private_native_argument_escaped':type(error)is RuntimeError and error.args==('SYNTHETIC_PRIVATE_NATIVE_CLASS_ERROR',)})
    else:results.append({'case':name,'exact_owned_error':False,'unexpected_success':True})
print(json.dumps({'synthetic':True,'cases':results}))
raise SystemExit(0 if all(row['exact_owned_error'] for row in results) else 1)
