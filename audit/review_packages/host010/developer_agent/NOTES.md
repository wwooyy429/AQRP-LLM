# host010 implementation evidence (private)

Only tools/followup_host.py and tests/test_followup_host.py are owned product
files. No Git commit, real Registry, real budget, provider, QC, Research, LEAN,
automation or cloud request was made. This is developer software verification,
not independent acceptance, financial evidence or production transport proof.

## First run and reproducible failure

- first-tests.txt: initial 18 host tests passed.
- Auxiliary boundary checker reported UTF-8 character/byte limit mismatch,
  direct API oversize persistence, and host status hiding an unknown discovery
  reservation. Its independent test choices are in host010-boundary (support
  checks only, not formal independent stage review).
- utf8-first-failure.txt: added production host regression; 19 tests ran with
  one failure. Direct oversized response returned invalid_native_response
  instead of response_too_large (and had reached normal response processing).

## Corrections and actual results

- Enforce UTF-8 bytes before serve command processing. Direct accept_response
  checks canonical UTF-8 bytes before hashing, acquiring locks or persistence;
  oversized response is rejected and its existing reservation remains unknown.
- inspect/status and CLI plan expose host unknown reservations and receipt
  handoffs. Identical rejected code/hash observations append only once.
- fixed-tests.txt: 19 tests passed, 12.304 seconds, including four local
  processes sharing a private FilesystemArtifactStore. These tests exercise
  actual TaskFollowupController and private Memory/Filesystem Registry stores.
- controller-regression.txt: existing 22 TaskFollowupController tests passed.
- cli-regression.txt: existing 6 followup CLI tests passed.

## Limits

No production factory or connector is installed by this change. Python
TransportAuthority and task-bound ReadGrant are trusted deployment inputs;
stdin cannot grant permission. The CLI forces real UTC and has no --now.
Discovery is separately permitted, fixed page 1 and durably reserved once.
Host and controller reservations are deliberately at-most-once: crash or lost
response requires attention, never reconstruction or redispatch.

read_backtest requires transport-compatible real task-bound permission;
directory Completed metadata grants none. A native read response remains an
in-memory handoff and returns awaiting_native_receipt. Upstream retains it
securely and still supplies full logs/native zero-order evidence through the
existing tools/stage2.py backtest-result parser -> Bridge -> Registry. The
synthetic late-result test uses that parser and settles the original attempt,
but does not claim a complete automated terminal chain.

Closed old terminal attempts acquire neither a controller watch nor host
stream. No livewatch or automation is created.
