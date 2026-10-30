# Historical source independent review

Candidate: `fbe2454e6ea10aa59211c01f236c54bb251527be`. Scope is the newly added source adapter/catalog and its collector/ingestor/PIT bridge. Production source and configuration were not edited. No actual Research, market, model, LEAN, deployment or PR operations occurred. The SDK was not dynamically loaded or certified.

The new source module has two reproducible P2 findings. These do not overturn previously accepted, unchanged numeric kernels and do not establish any financial evidence.

## WR-09: SDK missing dates become observed financial dates

`cloud/qresearch/historical_source.py:84–90` serializes the date returned by each `.value` accessor. LEAN's date fields can return `default(DateTime)` when no period has a value. This is SDK missingness, yet the adapter stores `0001-01-01`. The public source → `HistoricalSnapshotCollector.collect` → `read_window` path preserves it and counts both dates as nonmissing.

The independent first run supplies `datetime.min` and `has_value=False` for `financial_statements.period_ending_date.value` and `financial_statements.file_date.value`. Both expected values are `None`, with one missing observation each. Both actual values are `0001-01-01`, with zero missing observations each. The entire trace and synthetic projected record are retained in `source_review_results_first.json`.

The official contract is pinned at [LEAN f3d841e](https://github.com/QuantConnect/Lean/tree/f3d841e60dfd010ee5fc293ea893e56952484108). [MultiPeriodField](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Data/Fundamental/MultiPeriodField.cs#L31) defines `NoValue` and its empty-period fallback at lines 31/56; [BaseFundamentalDataProvider](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Data/UniverseSelection/BaseFundamentalDataProvider.cs#L70) defines the default and considers default `DateTime` missing at lines 70–80/107–109. [FileDate](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Data/Fundamental/Generated/FinancialStatementsFileDate.cs#L75) falls back through base `Value` at line 89.

Do not repair this by discarding every field whose default-period `has_value` is false: `.value` can still return a valid alternative period. `test_valid_fallback_dates_and_zero_remain_values` independently verifies preservation of such dates and numeric zero.

## WR-10: native request end convention conflicts with selection-clock windows

`historical_source.py:160–162` forwards the public start/end unchanged. At lines 180–182 it rejects a returned snapshot whose index equals end. The official native path accepts `start < EndTime <= end` and uses `EndTime` as the Pandas index. A normal native endpoint therefore aborts the window; the public collector cannot complete and retains its unfinished intent.

The fixed official chain is:

- [QuantBook](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Research/QuantBook.cs#L765): Python overload 765/774/776 → `RunUniverseSelection` 939/942/959/961. With no date rule, 1132–1136 forwards the history rather than adding another half-open filter.
- [QCAlgorithm.History](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Algorithm/QCAlgorithm.History.cs#L337): 337/342/344 creates the universe request; 1021/1029 calls the history provider.
- [FundamentalUniverse](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Data/Fundamental/FundamentalUniverse.cs#L60): 60/77 returns folding data containing a `Fundamental(date)`; [FineFundamental](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Data/Fundamental/FineFundamental.cs#L33) line 33 gives it the next-day end clock.
- [SubscriptionDataSourceReader](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Engine/DataFeeds/SubscriptionDataSourceReader.cs#L64): 64–65 selects folding aggregation; [Aggregator](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Engine/DataFeeds/BaseDataCollectionAggregatorReader.cs#L68) 68/80 preserves constituent EndTime.
- [HistoryProvider](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Engine/HistoricalData/SubscriptionDataReaderHistoryProvider.cs#L220): 220/222 permits EndTime equal to end and excludes EndTime equal to start.
- [PandasData](https://github.com/QuantConnect/Lean/blob/f3d841e60dfd010ee5fc293ea893e56952484108/Common/Python/PandasData.cs#L175): 175/180/190 uses this EndTime for the Series row.

`minimal_native_endpoint.py` replays a single legal 2017-05-24 end index for a 2017-05-23 → 2017-05-24 request using only invented objects. It exits 1 with `HistoricalSourceError`. Additional independent 1/2/7-day replay cases and the public collector confirm the conflict. These are contract replays, not platform executions or certification of actual response coverage. Merely allowing an end-equal row would conflict with the collector's declared half-open interval; a fix must reconcile the native clock/query convention and the requested window consistently.

## Execution ledger

Runtime: Python 3.10.11, NumPy 1.26.4, pandas 2.3.3. Exact commands are in `review_summary.json`. Only the reviewer output directory is written.

| Program | Methods | Passed | Failed methods | Failure records | Subtests | Errors | Skips |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| independent_source_review.py, first and final | 8 | 7 | 1 | 2 | 73 | 0 | 0 |
| secondary_source_review.py, final observation catch | 3 | 1 | 2 | 4 | 3 | 0 | 0 |
| Combined distinct final methods | 11 | 8 | 3 | 6 | 76 | 0 | 0 |

The first additional execution had three failing endpoint subtests plus one error method. That error was a reviewer exception-observation issue: the collector intentionally wraps the source error in `CollectionError`, while the reviewer caught only its narrower `HistoricalSourceError` subclass. `secondary_source_review_first.py`, first output/results, and `secondary_harness_correction.diff` preserve this history. The only observation fix widens that catch and writes separate final files; inputs and production assertions are unchanged. The final public-collector method records a normal assertion failure rather than an uncaught error. This history must not be described as every execution having zero errors.

Positive cases cover the 15-field projection, lack of fundamental-coverage filtering, permanent SID retention, type validation, zero/NaN/missing handling, projection pinning, DST/UTC endpoints, final/frontier/range rejection, Series/universe/SID shape rejection, source-defined classifications, and unknown evidence through ingestion/PIT refusal. Fake availability/certification values do not fill receipts. The bridge and collector continue to report certification flags false.

The [official universe documentation](https://www.quantconnect.com/docs/v2/research-environment/universes) supports the nonflattened Series, symbol/time MultiIndex and object-list shape. The [official SecurityReference definition](https://www.lean.io/docs/v2/lean-engine/class-reference/classQuantConnect_1_1Data_1_1Fundamental_1_1SecurityReference.html) defines both A and I as still trading, with I lacking fundamental coverage; D/O correspond to former listings. The adapter's A/I mapping is consistent with that definition.

All 19 official source files were downloaded from immutable URLs; hashes and file paths are in `official_sdk_static_manifest.json`. Use raw file one-based line numbers above. Browser text extraction omits blank lines and its displayed indices are not GitHub line anchors. No true SDK Python object conversions, historical all-market coverage, actual vendor receipts, publication/vintage semantics or complete historical US200 were dynamically verified.
