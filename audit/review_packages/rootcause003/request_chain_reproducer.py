"""Synthetic source-date enumeration model transcribed from public LEAN 18207.

No QuantBook, provider, security price, fundamental value or cloud task is used.
This demonstrates a sufficient SDK boundary failure under regular NY hours,
not proof that the cloud has matching binaries, data files or permissions.
"""
from datetime import date, datetime, timedelta, time
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).resolve().parent
DAY = timedelta(days=1)
EPS = timedelta(microseconds=1)

def is_open(start, end):
    # Deliberately synthetic weekdays, no holiday input or market data.
    if start.weekday() >= 5:
        return False
    midnight = datetime.combine(start.date(), time())
    return start < midnight + timedelta(hours=16) and end > midnight + timedelta(hours=9, minutes=30)

def source_dates(start, end):
    # Common/Time.cs EachTradeableDayInTimeZone, same data/exchange NY zone.
    current = start
    thru = datetime.combine(end.date(), time()) + DAY
    dates = []
    while current < thru:
        eod = min(datetime.combine(current.date(), time()) + DAY, thru)
        if is_open(current, eod):
            dates.append(current.date())
        current = eod
    return dates

def native_history_ends(start, end):
    # Synthetic source file guaranteed to contain one collection per source
    # date. FineFundamental + folding aggregator set EndTime=date+1 midnight.
    candidates = [datetime.combine(d, time()) + DAY for d in source_dates(start, end)]
    # SubscriptionDataReaderHistoryProvider.TimeBasedFilter, exact endpoints.
    return [point for point in candidates if point <= end and point > start]

def main():
    first = datetime(2018, 1, 1)
    cases = []
    for offset in range(40):
        start, end = first + offset * DAY, first + (offset + 1) * DAY
        current = native_history_ends(start - EPS, end - EPS)
        # A diagnostic counterfactual only, not an authorized code repair:
        # include the full prior source day; keep logical half-open filtering.
        wider = [point for point in native_history_ends(start - DAY, end - EPS) if start <= point < end]
        cases.append({'logical_start': start.isoformat(), 'logical_end_exclusive': end.isoformat(),
            'current_native_records': len(current), 'full_prior_source_day_control_records': len(wider)})
    assert all(item['current_native_records'] == 0 for item in cases)
    assert any(item['full_prior_source_day_control_records'] > 0 for item in cases)
    example_start = datetime(2018, 1, 9)
    example_end = example_start + DAY
    assert source_dates(example_start - EPS, example_end - EPS) == [date(2018, 1, 9)]
    assert native_history_ends(example_start - EPS, example_end - EPS) == []
    assert example_start in native_history_ends(example_start - DAY, example_end - EPS)
    report = {'schema_version': 1, 'scope': 'synthetic_sdk_boundary_transcription',
        'public_sdk_source_commit': 'f3d841e60dfd010ee5fc293ea893e56952484108',
        'production_source_changed': False, 'Research_executions': 0, 'LEAN_submissions': 0,
        'market_data_or_fundamental_values_loaded': False,
        'synthetic_calendar': 'Monday-Friday regular09:30-16:00; holidays intentionally not asserted',
        'known_answer_assertions_passed': 5,
        'all40_current_microsecond_windows_empty_despite_synthetic_source_data': True,
        'counterfactual_prior_source_day_produces_nonempty_logical_windows': True,
        'example': {'logical_window': ['2018-01-09T00:00:00', '2018-01-10T00:00:00'],
            'current_physical_window': [(example_start-EPS).isoformat(), (example_end-EPS).isoformat()],
            'enumerated_file_dates': ['2018-01-09'], 'file_record_EndTime': '2018-01-10T00:00:00',
            'record_rejected_by_end_cutoff': True,
            'needed_prior_file_skipped_because_23_59_tail_closed': '2018-01-08'},
        'limitations': ['This is a faithful logic model, not an actual .NET SDK execution.',
            'Actual cloud type/config/MHDB/permissions were not recorded and are not authenticated by this result.',
            'A sufficient software defect does not prove actual historical files are available or financially point-in-time.'],
        'cases': cases}
    path = OUT / 'request_chain_reproduction.json'
    path.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'report': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'synthetic_windows': len(cases), 'all_current_empty': True, 'known_answers': 5}))

if __name__ == '__main__':
    main()
