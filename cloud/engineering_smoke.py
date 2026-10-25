"""Small cloud plumbing check, not an economic factor or strategy experiment."""
from datetime import datetime
import hashlib
from AlgorithmImports import *
from QuantConnect.Research import QuantBook
from qresearch.cache import SharedDataCache
from qresearch.contracts import DataRequest, NY, digest
from qresearch.point_in_time import causal_window
from qresearch.quantconnect import (QuantConnectHistoryProvider,
                                   ObjectStoreArtifactStore, ExchangeCalendar)


def run():
    qb = QuantBook()
    qb.set_time_zone("America/New_York")
    # QuantBook start_date is the historical data frontier, not a sample start.
    qb.set_start_date(2019, 1, 1)
    qb.set_end_date(2019, 1, 2)
    qb.settings.daily_precise_end_time = True
    securities = [qb.add_equity(ticker, Resolution.DAILY, fill_forward=False,
                               data_normalization_mode=DataNormalizationMode.RAW)
                  for ticker in ("AAPL", "MSFT")]
    # The Symbol is used only to resolve the permanent identity for this fixture.
    symbols = {str(security.symbol.id): security.symbol for security in securities}
    version = "engineering-2018-raw-snapshot-v2"
    provider = QuantConnectHistoryProvider(qb, symbols, version)
    store = ObjectStoreArtifactStore(qb.object_store, "generic-research/v1",
                                    read_only=False, single_producer=True)
    cache = SharedDataCache(store, provider)
    request = DataRequest("US Equities", ("close", "volume"), tuple(symbols),
                          datetime(2018, 1, 1, tzinfo=NY), datetime(2019, 1, 1, tzinfo=NY),
                          version, "engineering-fixed-two-symbol-fixture")
    keys_first = cache.prefetch(request)
    after_first = provider.fetch_call_count
    keys_second = cache.prefetch(request)
    records = cache.read(request, allow_fetch=False)
    after_second = provider.fetch_call_count
    calendar = ExchangeCalendar(securities[0].exchange.hours)
    schedule = calendar.decisions(datetime(2018, 1, 3, tzinfo=NY),
                                  datetime(2018, 1, 10, tzinfo=NY))
    expected = dict(zip(schedule.formation_at, schedule.session_close))
    window = causal_window(records, schedule.formation_at, tuple(symbols),
                           {"close": "exact_session", "volume": "exact_session"}, expected)
    checks = {"nonempty_history": not records.empty,
              "second_prefetch_no_history": after_first == after_second,
              "same_partition_ids": keys_first == keys_second,
              "single_batch_on_cold_cache": after_first in (0, 1),
              "complete_fixture_window": all(frame.notna().all().all() for frame in window.matrices.values()),
              "development_only": all(records.event_time.dt.year == 2018),
              "calendar_before_decision": all(k > v for k, v in expected.items())}
    if not all(checks.values()):
        raise AssertionError("Engineering cloud check failed: " + str([k for k, v in checks.items() if not v]))
    # Metadata only can leave this function through the connector. No prices,
    # factor exposures, labels, or reconstructed market values are logged.
    return {"status": "passed", "checks": checks, "provider_calls_first_pass": after_first,
            "provider_calls_second_pass": after_second - after_first,
            "market_values_exported": False, "economic_factor_tested": False,
            "full_US200_coverage_certified": False, "final_data_accessed": False,
            "snapshot_identity": digest(request.identity())}
