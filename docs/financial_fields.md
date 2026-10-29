# Specified-period financial observations

The engineering catalog declares one numeric financial observation:

`financial_statements.income_statement.total_revenue_as_reported.twelve_months`

Its role is `as_reported_financial_value`, unit is `reported_currency`, and period accessor is `twelve_months`. The program does not assume USD, infer a reporting currency, perform FX conversion or substitute standardized `total_revenue`. It does not enable factor access.

`qresearch.financial_fields` accepts only this exact field definition. The source adapter validates the definition before requesting history. On a native period object, it first calls the fixed SDK method `has_period_value("12M")`; only an exact boolean `True` permits reading the `twelve_months` property. `False` produces `None`, even when the SDK's missing-value sentinel would have been zero. A genuinely present zero remains zero. Default-period `has_value`, `value` and arbitrary field-selected callables cannot establish 12M presence.

Missing parents, `None` and NaN remain missing observations. Invalid types, infinities, absent presence capability and throwing native properties fail closed. Exceptions are converted to owned static messages without rendering native exceptions or numeric subclasses. Rows and their derived values must remain in QuantConnect Cloud.

This is an extraction contract, not data certification. Reporting currency, filing revision, public availability, historical vendor delivery, ingestion time and full historical coverage remain uncertified. `factor_fields_enabled`, vendor revision certification, actual availability certification and final evaluation remain disabled. The archived official API reference used for this implementation is `audit/review_packages/phase2_repair011/financial_API_references.json`; documentation alone is not a row-level provenance receipt.

The current stable collection processing contract binds five sources, including the complete `financial_fields.py` helper. A helper-only semantic change therefore invalidates the cache identity. Offline comparisons may still reproduce the original four-source v1 hash for an old adapter without a financial-helper dependency; a current adapter with an omitted helper is rejected. The current five-source contract differs from the old `5ef61ef7...` contract, so old frozen cache-only plans remain historical and fail closed under the new runtime. This change does not authorize fetching replacement data or modifying old plans and receipts.
