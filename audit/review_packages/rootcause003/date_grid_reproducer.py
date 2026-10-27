"""Offline known answers for the frozen one-day universe-history endpoint bug.

This is a source-equivalent model, not an execution of the LEAN SDK or a data
provider. Each permitted synthetic source file has exactly one artificial item.
The model never loads security identifiers, financial values or licensed data.
"""
from datetime import datetime, timedelta, time
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = json.loads((HERE / 'date_grid_source_evidence.json').read_text(encoding='utf-8'))
CALENDAR = EVIDENCE['reference_calendar_excerpt']
HOLIDAYS = {datetime.strptime(x, '%m/%d/%Y').date() for x in CALENDAR['holidays']}


def endpoint(stamp):
    """Frozen local _history_endpoint algorithm, using absolute subtraction."""
    stamp = pd.Timestamp(stamp)
    stamp = stamp.tz_localize('America/New_York') if stamp.tzinfo is None else stamp.tz_convert('America/New_York')
    return (stamp.tz_convert('UTC') - pd.Timedelta(microseconds=1)).tz_convert('America/New_York').tz_localize(None).to_pydatetime()


def is_open(start, end, *, include_extended=False):
    if start.date() in HOLIDAYS:
        return False
    hours = CALENDAR[start.strftime('%A').lower()]
    return any((include_extended or x['state'] == 'market')
        and start < datetime.combine(start.date(), time.fromisoformat(x['end']))
        and end > datetime.combine(start.date(), time.fromisoformat(x['start'])) for x in hours)


def file_dates(start, end, *, include_extended=False):
    """Exact NY==NY branch of Common/Time.cs EachTradeableDayInTimeZone."""
    current = start
    thru = datetime.combine(end.date() + timedelta(days=1), time())
    result = []
    while current < thru:
        eod = min(datetime.combine(current.date() + timedelta(days=1), time()), thru)
        if is_open(current, eod, include_extended=include_extended):
            result.append(current.date())
        current = eod
    return result


def synthetic_ends(start, end, *, missing_dates=frozenset(), include_extended=False):
    """One fake item per permitted file; missing files never get a substitute."""
    candidates = [datetime.combine(day + timedelta(days=1), time())
        for day in file_dates(start, end, include_extended=include_extended) if day not in missing_dates]
    # SubscriptionDataReaderHistoryProvider.TimeBasedFilter: start < EndTime <= end.
    return [stamp for stamp in candidates if start < stamp <= end]


def expanded_and_cropped(start, end, *, missing_dates=frozenset()):
    observed = synthetic_ends(start - timedelta(days=1), endpoint(end), missing_dates=missing_dates)
    return [stamp for stamp in observed if start <= stamp < end]


def fixture_windows():
    p = EVIDENCE['frozen_fixture']
    start = datetime.fromisoformat(p['start']).replace(tzinfo=None)
    end = datetime.fromisoformat(p['end_exclusive']).replace(tzinfo=None)
    windows = []
    while start < end:
        nxt = min(start + timedelta(days=p['calendar_days_per_request']), end)
        windows.append((start, nxt))
        start = nxt
    return windows


class DateGridKnownAnswers(unittest.TestCase):
    def test_standard_equity_clock_contract(self):
        self.assertEqual(CALENDAR['dataTimeZone'], 'America/New_York')
        self.assertEqual(CALENDAR['exchangeTimeZone'], 'America/New_York')
        self.assertTrue(all(x['end'] <= '20:00:00' for d in ('monday','tuesday','wednesday','thursday','friday') for x in CALENDAR[d]))
        self.assertEqual(EVIDENCE['universe_security_type'], 'Equity')
        self.assertEqual(EVIDENCE['universe_market'], 'usa')
        self.assertFalse(EVIDENCE['universe_extended_hours'])

    def test_midnight_tail_closed_even_with_extended_hours(self):
        a, b = datetime(2018, 1, 8, 23, 59, 59, 999999), datetime(2018, 1, 9)
        self.assertFalse(is_open(a, b))
        self.assertFalse(is_open(a, b, include_extended=True))
        self.assertTrue(is_open(datetime(2018, 1, 8), b))

    def test_regular_and_extended_hours_are_not_confused(self):
        a, b = datetime(2018, 1, 8, 6), datetime(2018, 1, 8, 7)
        self.assertFalse(is_open(a, b))
        self.assertTrue(is_open(a, b, include_extended=True))

    def test_regular_preopen_half_open_boundary(self):
        self.assertFalse(is_open(datetime(2018,1,8,9,29),datetime(2018,1,8,9,30)))
        self.assertTrue(is_open(datetime(2018,1,8,9,29),datetime(2018,1,8,9,30,0,1)))

    def test_regular_close_half_open_boundary(self):
        self.assertFalse(is_open(datetime(2018,1,8,16),datetime(2018,1,8,16,1)))
        self.assertTrue(is_open(datetime(2018,1,8,15,59,59,999999),datetime(2018,1,8,16)))

    def test_buggy_one_day_request_skips_required_prior_file(self):
        a, b = endpoint('2018-01-09'), endpoint('2018-01-10')
        self.assertEqual(file_dates(a, b), [datetime(2018, 1, 9).date()])
        self.assertEqual(synthetic_ends(a, b), [])

    def test_all_frozen40_windows_zero_even_with_source_records(self):
        windows = fixture_windows()
        self.assertEqual(len(windows), 40)
        self.assertTrue(all(synthetic_ends(endpoint(a), endpoint(b)) == [] for a, b in windows))

    def test_deleting_epsilon_returns_upper_endpoint_outside_half_open_window(self):
        a, b = datetime(2018, 1, 9), datetime(2018, 1, 10)
        records = synthetic_ends(a, b)
        self.assertEqual(records, [b])
        self.assertFalse(all(a <= stamp < b for stamp in records))

    def test_prior_full_day_start_and_crop_return_correct_target_clock(self):
        a, b = datetime(2018, 1, 9), datetime(2018, 1, 10)
        self.assertEqual(expanded_and_cropped(a, b), [a])

    def test_increasing_batch_to7_only_hides_first_snapshot_loss(self):
        a, b = datetime(2018, 1, 9), datetime(2018, 1, 16)
        buggy = synthetic_ends(endpoint(a), endpoint(b))
        cropped = expanded_and_cropped(a, b)
        self.assertTrue(buggy)
        self.assertNotIn(a, buggy)
        self.assertEqual(cropped, [a] + buggy)

    def test_weekend_is_not_backfilled_or_relabelled_as_a_session(self):
        # Raw Fundamental EndTime is source date+1. Do not relabel Friday's
        # raw clock as Monday or fill the missing Sunday/Monday snapshots.
        self.assertEqual(expanded_and_cropped(datetime(2018,1,6), datetime(2018,1,9)), [datetime(2018,1,6)])
        self.assertEqual(expanded_and_cropped(datetime(2018,1,8), datetime(2018,1,9)), [])

    def test_missing_source_file_stays_missing(self):
        a, b = datetime(2018, 1, 9), datetime(2018, 1, 10)
        self.assertEqual(expanded_and_cropped(a, b, missing_dates={datetime(2018,1,8).date()}), [])

    def test_dst_absolute_windows_keep23_or25_hours(self):
        for a, b, hours in [('2018-03-11','2018-03-12',23), ('2018-11-04','2018-11-05',25)]:
            x, y = endpoint(a), endpoint(b)
            observed = (pd.Timestamp(y,tz='America/New_York').tz_convert('UTC') - pd.Timestamp(x,tz='America/New_York').tz_convert('UTC')).total_seconds()/3600
            self.assertEqual(observed, hours)
            self.assertLess(x, y)

    def test_frozen_repository_endpoint_matches_the_model(self):
        sys.path.insert(0, str(ROOT / 'cloud'))
        from qresearch.historical_source import _history_endpoint
        for value in ('2018-01-09', '2018-03-12', '2018-11-05'):
            self.assertEqual(_history_endpoint(pd.Timestamp(value,tz='America/New_York')), endpoint(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', type=Path,
        help='Optional already-downloaded official code directory; hash/snippet verification only, never network.')
    args = parser.parse_args()
    verified_sources = []
    if args.source_directory is not None:
        for record in EVIDENCE['upstream_source_files']:
            path = args.source_directory / record['path'].replace('/', '__')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != record['sha256']:
                raise ValueError('Official source hash mismatch: ' + record['path'])
            lines = raw.decode('utf-8-sig').splitlines()
            for part in record['excerpts']:
                if '\n'.join(lines[part['first_line']-1:part['last_line']]) != part['source']:
                    raise ValueError('Official source excerpt mismatch: ' + record['path'])
            verified_sources.append(record['path'])
    log = io.StringIO()
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DateGridKnownAnswers))
    (HERE / 'date_grid_reproduction.log').write_bytes(log.getvalue().encode('utf-8'))
    windows = fixture_windows()
    report = {
        'schema_version':1, 'scope':'source_equivalent_synthetic_reproduction_only',
        'SDK_executed':False, 'host_net10_runtime_or_SDK_available':False,
        'market_data_requested':False, 'QC_tasks_submitted':0, 'budget_ledger_modified':False,
        'public_image':'quantconnect/research:18207',
        'public_image_sourcelink_commit':EVIDENCE['public_image_source_mapping']['source_commit'],
        'cloud_binary_identity_not_certified':True,
        'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors), 'all_passed':result.wasSuccessful(),
        'frozen_window_count':len(windows),
        'buggy_empty_windows_despite_permitted_synthetic_source_records':sum(not synthetic_ends(endpoint(a),endpoint(b)) for a,b in windows),
        'representative_workday':{'logical_window':['2018-01-09T00:00:00-05:00','2018-01-10T00:00:00-05:00'],
            'request':[endpoint('2018-01-09').isoformat(),endpoint('2018-01-10').isoformat()],
            'enumerated_source_dates':[x.isoformat() for x in file_dates(endpoint('2018-01-09'),endpoint('2018-01-10'))],
            'source_date_EndTime':'2018-01-10T00:00:00','accepted_EndTimes':[]},
        'conclusion':'The one-day endpoint transformation is sufficient to produce empty results under standard US-equity hours and the documented Fundamental date+1 EndTime path, even when synthetic source files exist.',
        'limits':['Equivalent algorithm, not loaded SDK execution.','No cloud request/header, exchange-hour override or binary-byte equality was certified.',
            'No repaired cloud run or historical source delivery was tested.','Raw modeled EndTime is not a historical actual availability receipt.'],
        'verified_upstream_source_paths':verified_sources,
        'evidence_sha256':hashlib.sha256((HERE/'date_grid_source_evidence.json').read_bytes()).hexdigest(),
        'program_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'global_usage_preserved':{'configurations':9,'research':12,'lean':1}, 'final_test_enabled':False,
    }
    (HERE/'date_grid_reproduction.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(log.getvalue())
    print(json.dumps(report))
    return not result.wasSuccessful()

if __name__ == '__main__':
    raise SystemExit(main())
