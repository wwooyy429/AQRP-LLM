# Historical source observation identity

The fixed normal-round diagnostic at source commit `42b45c830aac691fe0763bfc6363997947625bc1`
completed with a native `CollectionError` selecting `native_sid_duplicate`. Its
attempt is `b9f952c1de3a44f9b06e5c552f7d1af3`. The 5,124 emitted rows in that diagnostic
describe the failing fetch, not a completed window or total historical coverage.

The legacy collection protocol remains version 1: `(SID, snapshot_at)` must be
unique. Its old failed intents and partial batches are immutable and never reused
as completed data. The native source keeps `unique_sid` as its default.

Collection protocol 2 explicitly freezes
`observation_policy = retain_source_occurrences`. Each projected source record
adds `source_record_index`, its zero-based position in that snapshot's returned
native list. Positions must start at zero and remain contiguous across batches.
The collector retains every selected-field observation, in order, including
identical and conflicting projections. All other native identity, request-clock,
field whitelist, missing-value, privacy and bounded-window checks still apply.

`source_record_index` is an observation position in one response. It is not a
permanent security identity, a vendor revision, an availability time, or proof of
stable ordering between downloads. SID remains the permanent security key.

Two counts are recomputed from cloud payloads on cache reads:

- `duplicate_projection_records`: occurrences after the first `(SID, snapshot_at)`.
- `conflicting_projection_records`: those later occurrences whose selected
  `values` differ from the first projection's canonical hash.

Equality of four selected fields does not establish equality of full native
records. Hashes of row values stay in the cloud. Neither count selects a winner;
there is no implicit drop, deduplication, averaging, or latest-version rule.

This protocol is restricted to engineering collection. Its coverage, research,
availability and financial-vintage certification flags remain false. The unique
liquidity conversion rejects occurrence rows rather than stripping their ordinal.
Resolving ambiguous observations for a historical US200 pool or financial panel
requires a separately frozen rule and appropriate source/vintage evidence.

A successful Research/LEAN plumbing run under this protocol proves only the
bounded engineering checks. It does not resolve supplier duplication, certify
2010–2023 data, independently test a factor, or open the reserved final window.
