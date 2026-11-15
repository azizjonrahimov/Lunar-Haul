# Code review of Phase 6 (13 Nov 2026)

Range reviewed: `0210c22..b96361e` (already on `main`), code only (lunarsim/, tools/, experiments/, tests/, site/src,
site/lib, site/tests, the paper build scripts). Reviewers: testing, maintainability, security, performance, design,
simplification, state machines, a red team and an adversarial pass (all in-host; no outside model). Tests and fixtures
were read in summary by the security, red-team and adversarial reviewers. Nothing blocks CI or the deploy.
Owner's decisions (13 Nov): fix every defect below; skip the optional cleanups (section S); keep the three test gates
of B-114 (torch skip with a new CI job that installs CPU torch; the git-ignored cache input; design records skipped).

Status words used later in this file: open, fixed (commit), not a defect (reason).

## N. Findings that change or unsupport a published number (do these first)

- N1 `tools/atc/run_e52.py:65-69` route_tiles adds the whole leg length before recording its tiles, so every tile of
  a leg carries the offset of the leg's end (35 distinct offsets for 328 entries). Red team's recomputation: P3 5.10
  "after contact at most 0.08 with hazards first and 1.65 with the oldest change first" becomes 0.40 and 1.72; P3
  Table 13 last column and /protocol/ figure 2 move. Fix: offset at each sample; rerun E52; add a test that the number
  of distinct offsets is close to the number of tile entries. LEAD confirmed by reading.
- N2 `lunarsim/vv6.py:295` row G1 "every Phase 6 option off equals the Phase 5 run" sets options to their defaults
  and compares the default run with itself. Fix: compare with a summary produced by the pre-Phase-6 code (commit
  0210c22, via git archive, stored with its commit), add a row that an option switched on changes the summary, and
  have the site and the papers read `passed`. LEAD confirmed by reading.
- N3 `lunarsim/atc/dtn.py:206-207,178` store-and-forward: each step gives a bundle a full set of attempts whatever
  time is left; the lifetime is checked only at the step start, so a 60 s grant can be delivered up to about 40 s late
  and counted delivered; a delivery on the last attempt of a step is recorded in the next step. E54 grant losses and
  delays understated.
- N4 `lunarsim/atc/dtn.py:239-242,161` bundles still pending at the window end are marked expired (censoring counted
  as loss); a message created at or after the window end is neither delivered nor expired. Two reviewers.
- N5 `lunarsim/atc/dtn.py:275-279` age of information: `last` is updated before the age is taken, giving a floor of
  dt/2 = 30 s whatever the 10 s status period. E54 sf_ll 45.49 s is mostly this. P1 and P3 print these seconds.
  `vv6.py:261-265` (C9) checks the formula with its own inline simulation and never calls the function.
- N6 `lunarsim/atc/dtn.py:112` lost-link return: the code uses the driving time in the hour before the loss (and a
  literal 60 steps); both docstrings say T_hold + 2 x the driving time since the loss. Three reviewers. Decide which
  rule the registration and the papers state, and make code, text and test agree.
- N7 `tools/atc/run_e54.py:219,507` and `phase6_family.py:144`: stuck reservations are the constant 0 under sf_ll and
  come from the contact plan alone otherwise (same 2,566 at every loss level, grants that expired included), yet
  `h14.supported` uses it. The results file must say this half holds by rule, not by measurement, or compute it.
- N8 `tools/atc/phase6_family.py:158` H15a's p is the constant 1/(B+1) with a note that no resample reached 0;
  nothing checks that. Save the count of resamples at or above 0 in E56 and compute p from it.
- N9 `lunarsim/atc/integrity.py:99-102` the E55 replay trial draws the replayed message from the whole 10-minute log
  and then adds 0 to 60 s, so about 1 % of replays fall inside the 10 s freshness window; "0 accepted" is close to
  guaranteed. P3 5.11 and /protocol/ describe it as "replayed after 0 to 60 s". LEAD confirmed by reading.
- N10 `lunarsim/nn/baselines.py:225` an event counts as found if an alarm was already on before onset. Harmless on
  test; out of distribution it inflates the baselines (CUSUM alarm on in the minute before onset in 50.7 % of fault
  streams; its OOD recall 0.842 is 0.693 on events with a quiet minute before). /network/ and the E56 tables print
  these recalls.
- N11 `lunarsim/nn/evaluate.py:228` the false-alarm interval uses the first 200 of the 1,000 stated resamples.
- N12 `tools/atc/run_b105.py:95-106` one round in 20 is timed with tracemalloc running, and those durations enter
  the array whose 99th percentile is published (0.29, 1.09, 1.19 s). The 4x and 8x verdicts sit 9 % and 19 % above
  the 1 s line. Bias not measured.
- N13 `lunarsim/atc/messages.py:50` the channel's LRIP sizes hard-code the signed messages as TASK_AWARD and
  RESERVE_GRANT; CAP_MANIFEST is counted 28 B where the codec's table says 84 B. Check whether any E53 or E40 figure
  sends manifests through this path.
- N14 `tools/atc/run_e50.py:230-231` with `lunarsim/atc/pnt.py:218`: the heading is the zero vector outside a leg,
  so a reservation whose time rounds to the step before departure or to the arrival step gets a timing shift of 0.
  Count how many reservations this touches (not measured).
- N15 `lunarsim/atc/pnt.py:229,391` the last partial step of each leg is treated as a new leg (bias redrawn, firm
  ground rate, no heading error); understates error by at most one step per leg.
- N16 `tools/atc/run_e55.py:193` H16's "robust" split is exact for N <= 8 and the degree condition (necessary only)
  above; the exactly-robust evidence is 3 runs. Report the exact cells apart.
- N17 `tools/atc/run_e44.py:427` the fresh-seed violation's replay record writes `"deterministic": True` as a
  literal. Set it from a comparison.
- N18 `tools/atc/run_e45_uphill.py:107` `nominal` is always false (planner is `[0] + [2] * (nv - 1)`), so
  `nominal_only_violations` is 0 of 0 in every cell.
- N19 `tools/atc/run_e50_near.py:212` prints "on the predicted side in every seed" when a reading has no steps.
- N20 `tools/atc/run_e50_overlaps.py:271` pairs whose nominal windows overlap by 1 s or more fall in neither group
  and are not counted (expected 0; print it).
- N21 Caches keyed by seed or name only (`run_e54.py:303,424,445`, `run_e50.py:414,461`,
  `lunarsim/nn/evaluate.py:422`), and `train_bid.py:530` stamps `rerun_commit` when the table is written. Write a
  code fingerprint into each cache file and refuse to mix; stamp the commit at run time.
- N22 `lunarsim/vv6.py:234,247-251,335,159` rows C6, C8, G4 and M4 use typed literals and never call the code they
  cite, so they cannot fail when the code changes.
- N23 `lunarsim/atc/encounter.py:282,706` the actuation-delay buffer has the batch's longest delay for every lagged
  row. Published uphill runs use one delay per batch (not affected). Index per row or refuse a mixed batch. The R1
  breach counter (:718-721) tests the commanded value, not the delayed one.

## C. Protocol codec and other code defects

- C1 `lunarsim/atc/lrip/codec.py:484,347` Receiver.accept returns unauthenticated packets for every type except
  HELLO and POSITION; the schema's signed flag is not enforced on receive. Two reviewers ran it.
- C2 `codec.py:481-496` no replay or freshness check in the codec receiver; an older HELLO replaces a newer
  declaration (the rule exists in `integrity.py:49-52`).
- C3 `codec.py:343,357` the SPI's key epoch is never compared with the receiver's.
- C4 `codec.py:286`, `lrip/cbor.py:49,57` short or malformed input raises struct.error, KeyError, IndexError,
  RecursionError or TypeError, not the documented ValueError family; lengths unchecked; no depth limit.
- C5 `codec.py:357,337` truncated tag compared with `!=` / `==` (use hmac.compare_digest).
- C6 `codec.py:175,189,349` all-zero default key and fixed seed used silently when keys is None.
- C7 `codec.py:387,370` profile B: no type or range check on CBOR items; the array may run into the security header.
- C8 `codec.py:492-493` an authenticated HELLO with invalid codes leaves the earlier declaration in force (design
  choice to confirm; the class text says such codes are refused).
- C9 `lunarsim/atc/lrip/manifest.py:48,73` the compact encoder maps any registry string to its index, the decoder
  maps back only for keys in _STRING_KEYS: some manifests do not round-trip.
- C10 `lunarsim/atc/smap.py:198-202` a valid report on an already-confirmed tile is logged "accepted: provisional".
- C11 `lunarsim/atc/dtn.py:230-231` a relay's store limit is not checked on forwarding.
- C12 `lunarsim/atc/integrity.py:120-126` detectable_error_check ignores alpha and p_detect (literal 4.57).
- C13 `lunarsim/nn/evaluate.py:172` literal 600 s censoring (use F.EVENT_S[1]); `:274,293` thread count set to the
  literal 2; `lunarsim/nn/train.py:142` torch.load with weights_only=False on the local checkpoint.
- C14 Unused imports and dead locals in about 20 new files (list in the maintainability report: smap.py, dtn.py,
  clocks.py, codec.py, evaluate.py, baselines.py, tracks.py, run_e50*.py, run_e54.py, run_e55.py, run_b97.py,
  export_protocol.py, run_b103.py, experiments/phase6/nn/run_baselines.py; `tests/test_lrip.py:181`
  `KEYS if False else`).

## P. Paper build scripts

- P1 `paper/p2/phase6.py:2388` falls back to the base cells when the mast variant is missing; `:1777` and `:201`
  silent defaults; `:256` and `:2539` swallow KeyError / AttributeError and drop a sentence with its checks.
- P2 Values computed and never checked beside a typed verdict: `paper/p2/phase6.py:2921` (below), `:451` (nm4);
  `paper/p3/build_p3.py:3448` (core_ok), `:2342`, `:2365`; `paper/p2/build_p2.py:955`.
- P3 Wording to follow N1 to N12 once the reruns land (P3 5.10 and Table 13, 5.11; P1 and P3 age of information;
  the G1 sentence; the E56 out-of-distribution recalls; the sizing verdicts).

## W. Site

- W1 `site/lib/network.mjs:47,67,68` a missing row prints a dash and the build passes; a value from a second file is
  shown under the first file's source label. `site/lib/phase6.mjs:22` prints "0 of 0" on missing keys and does not
  read `passed`; `:40` attaches the referee decision by exact clause text with no guard.
  `site/lib/protocol-data.mjs:92-93` optional chaining drops constants the figure reads.
- W2 `tools/ci/budgets.json:49` the /protocol/ data budget counts `protocol/b99/e53_bitrate.json`, which the page no
  longer fetches, and omits `protocol/e53-v02.json`.
- W3 `site/src/protocol/figures.js:249-256` sequential fetches; `site/src/network/landscape.js:113,43,13` full
  redraw on every pointermove.
- W4 `site/src/network/main.js:20` err.message written to innerHTML unescaped.
- W5 Design: `/protocol/` real-data table has no data-labels at 600 px and below (`protocol.css:134`,
  `lib/realdata.mjs:57`); contour text about 6 px on a phone (`network/landscape.js:70`); cutaway labels under 10 px
  (`lib/anatomy-common.mjs:107`); cutaway tour cycles with no pause (`protocol/anatomy-live.js:44`); the ten input
  names are built then hidden (`network/network.css:34`); `ui.css` not imported eagerly on /network/
  (`network/main.js:3`); `:has()` focus fallback (`hub.css:8-9`); fixed ramp in dark theme (`network/inside.js:8`);
  packet field buttons reflow on press (`protocol.css:86`).
- W6 Four new files define their own number formatter in place of `components/num.js` fmt (lacks the "-0.00" guard).

## T. Tests to add (stubs are in the reviewers' reports; LEAD has them)

Codec: unauthenticated packet refused; replay refused; other key epoch refused; short packets and malformed CBOR
raise ValueError; manifest full round trip (both examples, both versions) and free text; HELLO newer replaces older,
invalid HELLO revokes. dtn: never delivered after the lifetime; window end is not expiry; full store drops the
newest; the six untested custody cells. smap: confirmed tile not provisional; same owner other pass confirms.
pnt: ranging lowers the error and counts updates; LANS with a non-zero share. cli: validate skips design records.
nn: Policy refuses other files; guard clauses. Results tests: replace the five `isinstance(supported, bool)` lines
with the verdict recomputed from the file's rows. site: network.mjs every key gives a number and unknown keys throw;
familyRows throws on an unknown clause. CI: a job that installs CPU torch and runs tests/test_nn_integrity.py.

## S. Optional cleanups, skipped by the owner's decision (no code change)

Duplicate `_peak_mb` in four scripts; `_dump`/`_load`/`_seeds` redefined beside run_e50; `smap.TileMap.root_hash`
and `nn/model.transform_np` have no caller; duplicated constants (Moon radius, speed of light).

## O. Open follow-ups after B-120 (14 Nov 2026; not done, by LEAD's decision or as protocol decisions)

- Simplification suggestions of the review (shared helpers, duplicated constants; see S): not taken now.
- `dtn.age_of_information`: per-vehicle Python loops; vectorising it would speed E54 but moves no number. Not now.
- Receiver replay design gaps (`lunarsim/atc/lrip/codec.py` Receiver.accept): the 32-bit sequence number has no wrap
  rule (a sender at 2^32 - 1 is refused for the rest of the key epoch), and a holder of the shared site key can send a
  packet with a high sequence number for another sender and so deny that sender's later packets until the next epoch.
  Both need a protocol rule (wrap = new epoch; pairwise keys or per-sender MAC keys), not a code fix.
- A MAC-only HELLO can replace or revoke a declaration that came from a signed capability manifest (codec.py, the C8
  branch of Receiver.accept): a HELLO carries only a MAC under the site key, so any key holder can undo a signed
  declaration. Stated in Receiver.accept's docstring as the rule in force; whether a signed declaration should outrank
  a HELLO (for replacement as well as revocation) is a protocol decision. Tested as it stands
  (tests/test_lrip_v02.py test_manifest_and_hello_replace_each_other).
- The sequence counter is kept per (sender, key epoch), shared by MAC'd and signed packets (stated in the same
  docstring); a sender counting per key or per SPI kind would have its signed packets refused. The schema's rules
  should say which.
- `smap.Contribution.hazard` (default True) is never read: a report with hazard=False takes the hazard path. No caller
  sets it; remove the field or handle it, with a test.
- E45 uphill: with the 1 s actuation delay and the slope term, Mars one-lane gaps end up to 0.14 m below d0 (15 and
  17.2 deg). The cause is not known. Not an R1 breach (0, B-120 A), and not the one-step detection latency: with the
  delay at 0.9 s the shortfall stays (4.876 / 4.880 m).

Added by the second review pass (B-121, 14 Nov 2026), open:
- Code stamps are computed from the files on disk when a cell is written, so a file edited during a resumable
  multi-call run stamps the later cells with the new code while the earlier cells ran the old code.
- Data files are not in the fingerprints: the Earth-link table, the road graph, the vehicle files, and the versions of
  numpy/scipy/torch; a change there leaves the cells' code stamps unchanged.
- The 140 E45 uphill sweep cells carry no code stamp (only the 16 delay cells do, B-120 Q1), and the E45 uphill guard
  does not require all 16 delay cells to be present.
- dtn.simulate: a bundle whose lifetime ends after the window's end but before its next attempt (within one retry_s
  or custody_timer_s, dtn.py drop_retry "next try past the lifetime" and the sf "lifetime over" branch) is expired,
  not censored. The exact rule is now stated in simulate's docstring (B-121, docstring only); whether such a bundle
  should count as censored is open.
- vv6 G1 compares with exact equality (B-120 H); another numpy build may differ in the last digit (CI will show).
- codec: the all-zero key warning covers mac_key only (not the signing key) and repeats on every decode call.
- nn/train.fit catches only pickle.UnpicklingError for an old checkpoint; other errors from loading it are not
  turned into the named message.
- Site: null fallbacks remain for the E51 to E55 and B-99 values, so a missing results key does not stop the build.
- train_bid collect=True perturbs runs on the dispatch fixed point (B-122): hand seed 1 9.78 h collected against 9.06 h
  (= E40); without the fixed point collecting changed nothing. Cause (code reading, not yet fixed or tested):
  lunarsim/atc/learned.py oracle_assignment silences sim._push but not sim.wake_pending, so the teacher's marketplace call
  records lane deadlines in the wake dedupe (lunarsim/dispatch.py, consolidation hold) and the real dispatch then skips
  its WAKE. Fix (deferred to the later PR, after the remaining B-117 controls, because it moves e50_code): save and restore
  sim.wake_pending (and wake_skipped) around the teacher call, with a test that a collecting run on the fixed point equals
  a non-collecting one, the E50 cells re-stamped after a reproduction check, and the fixed-point agreement figures rerun.
  B-122's outcomes come from runs without collection and are not affected; its held-out agreement figures on the fixed
  point (hand 0.884, mlp 0.864, linear 0.703) come from collecting runs and carry the lost wake-ups. 51 collect-affected
  runs were discarded.
- run_e54 build() alone writes E54_dtn.json without lrip_v02 (v02build adds it back); the pair build + v02build
  reproduces the file byte for byte (checked in B-121).

Done in B-121 (no longer open): the E56 false-alarm interval kept at the published 200 resamples in evaluate_set so
--onset-fa can still check it; the B-118 addenda carried over only while their inputs are unchanged; --resample-counts
refuses an empty cache and --onset-fa gates its score files; phase6_family H14 reads the E54 cells through the code
check (e54_code recorded); E54 link files stamped and seed-checked; E54 results files written whole.

Done in B-120 (no longer open): the end-of-window rule in dtn.simulate (B), an unknown protocol string refused and the
base store bounded for Earth-bound bundles (G), the E54 fingerprint covering the engine (C), the code stamp checks of
the E50-family builders (D), the E56 addenda carried over and checked before writing (E), the codec's decode errors,
zero-key warning and NaN clock (F).

## Checked and found sound

Train / validation / test separation in lunarsim/nn (thresholds and model choice on validation only); the JS ports
`site/src/protocol/radio.js` and `site/src/network/tcn.js` agree with the Python; the ITU-R P.526 implementation;
the opt-in paths in radio.py, safety.py, roads.py and encounter.py leave the defaults unchanged; the E44 fresh-seed
bounds; E50b and E45-uphill seed pairing; no secret, eval, shell=True or yaml.load in the diff; pickle and torch.load
only on local git-ignored caches.
