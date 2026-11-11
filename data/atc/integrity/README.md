# The integrity dataset (B-96, experiment E56)

Simulated data for one question: can rover A tell that the position reports of rover B are wrong?
Everything here is simulated. Nothing is rover telemetry.

## What is in this folder

| Path | What | In git |
|---|---|---|
| `traces/seedNN/{with,without}.json.gz`, `index.json` | one simulated month per seed (2 to 17), written by `tools/atc/export_trace.py --seed NN --out data/atc/integrity/traces/seedNN` (about 26 s each). Seed 1 is `data/atc/trace_pair/`. | yes (1 MB) |
| `manifest.json` | per split: seeds, pair group, counts, array shapes, sha256 of every array and of every trace file, the parameter file's sha256 and status | yes |
| `landscape.json` | loss surface and training path for the web page (written by `lunarsim.nn.landscape`) | yes |
| `cache/{train,val,test,ood}.npz` | the built arrays, about 850 MB | no (`.gitignore`) |

## How to build it

```
.venv\Scripts\python -m lunarsim.nn.dataset --split train
.venv\Scripts\python -m lunarsim.nn.dataset --split val
.venv\Scripts\python -m lunarsim.nn.dataset --split test
.venv\Scripts\python -m lunarsim.nn.dataset --split ood
```

Each call takes 1.5 to 3.5 minutes, uses under 1 GB, saves every trace as it goes (a stopped call resumes) and
updates `manifest.json`. The builder is deterministic: one master seed (56), and a separate numpy generator per
(split, trace, vehicle) for navigation errors and per (split, trace, stream) for noise, so the arrays do not depend
on the order of the calls. On the same machine and numpy version (2.5.3) a rebuild gives the same sha256;
`tests/test_nn_integrity.py` checks this on a small build. Across machines the last bit of a float can differ.

## From a trace to a stream (code: `lunarsim/nn/tracks.py`, `faults.py`, `dataset.py`)

1. **True motion at 1 Hz.** Each vehicle follows its legs: along the road polyline of a drive or reposition leg
   at constant speed (piece length / piece duration), standing still otherwise. Two additions the trace does not
   hold: every vehicle has its own parking stand 15 m from a site point (the trace puts all parked vehicles on one
   point), and a moving vehicle keeps 2 m to the right of the centre line.
2. **Navigation error of each vehicle** (A's own, and B's, which is inside B's reports). An absolute fix leaves
   an error of 1.7 m (1-sigma per axis); between fixes the error grows with the dead-reckoned displacement (a
   scale-factor error and a heading error, each 2 %, drawn once per fix interval). Fixes: at every stop, and at
   Poisson points every 100 m of driving on average. The uncertainty a vehicle claims is
   sqrt(1.7^2 + (0.02 x distance since the fix)^2).
3. **What A measures.** A two-way range to B each second: UWB up to 100 m (0.3 m noise), the long-range base
   radio beyond that (3 m noise) out to the radio line of sight (smooth-Moon horizon of the two antenna heights,
   at most 5 km); nothing beyond. Blocked-path bursts add +1 m for 5 to 60 s, about two per hour, with a
   link-quality flag that is right 80 % of the time (5 % false flags).
4. **What B reports.** Its navigation solution plus 0.5 m white noise per axis, and its claimed uncertainty.
5. **The ten per-step inputs** (`faults.FEATURES`): normalised range innovation z, measured range, reported speed
   (displacement of the reports over 5 s), reported heading change (between two 10 s displacements, only above
   3 m), B's claimed uncertainty, A's own claimed uncertainty, link-quality flag, seconds since A's last fix,
   range-valid flag, ranging class (0 = UWB, 1 = long).
6. **Faults** (`faults.FAULTS`, on B's reported position only; B's claimed uncertainty does not change):

| Name | In distribution | Out of distribution |
|---|---|---|
| jump | step of 5 to 50 m | 2 to 5 m |
| drift | ramp of 0.01 to 0.5 m/s (log-uniform) | 0.005 to 0.01 m/s |
| frozen | the navigation solution stops updating while B moves (at least 10 m during the fault); report noise goes on | same |
| frame | constant offset of 300 to 1,000 m | same |
| noise | report noise x 3 to 10 | same |

   A fault lasts 120 to 600 s, starts 60 to 400 s into the scored part of its stream, in a random direction.

Parameters: `lunarsim/nn/pnt_params.json` (value, sweep range, unit, source for each). They come from section D of
`research_notes/Lunar Rover Interaction Protocol/01_positioning_and_time.md`; the seven that the note does not give
(report noise and rate, burst rate and length, the two link-flag probabilities, the 5 km cap) are listed in the
file under `not_in_note_01`.

## Streams and splits

- A stream is one ordered pair (observer A, sender B) over a window of one trace. The first 256 steps are
  warm-up and are never scored or trained on. The 128 steps after a fault ends are not scored either.
- **Fault streams**: 256 + 1,200 s with exactly one fault. 70 % of the windows are "active" (A or B drives for at
  least 60 s, in range at least half the time), 30 % "static" (nobody drives); each half in UWB range, half in
  long range, where the trace has enough of both. Frozen faults only where B drives.
- **Fault-free design streams** (train only): the same kinds of window with no fault.
- **Fault-free natural blocks** (val, test, ood): 256 + 3,600 s, the same number from each of four strata
  (active or static) x (UWB or long). Each block carries a weight that restores the natural share of its stratum
  among all blocks of that split in which the pair is in radio range at some time. False-alarm rates "per
  pair-day" are these weighted rates.

| Split | Seeds | Pairs (by \|i - j\|) | Noise and faults |
|---|---|---|---|
| train | 1 to 6 | 1, 4, 5 (14 pairs) | nominal |
| val | 7 to 9 | 2, 6 (8 pairs) | nominal |
| test | 10 to 13 | 3, 7 (6 pairs) | nominal |
| ood | 14 to 17 | 3, 7 (6 pairs) | ranging noise x 2, dead reckoning 5 % (A's filter still assumes 0.3 m, 3 m and 2 %), smaller jumps, slower drifts |

No seed, no vehicle pair and so no pair-month is in two splits (test and ood share the pair group, not the seeds).
Counts per split are in `manifest.json`.

## Arrays in `cache/<split>.npz`

`Xf` [streams, 1456, 10] float32 raw features; `yf` [streams, 1456] uint8 (1 while the fault is active);
`mf` [streams, 14] float64 with the columns of `manifest.json` "meta_columns" (kind 0 = fault-free, 1 to 5 = jump,
drift, frozen, frame, noise; ctx 1 = active; cls 0 = UWB, 1 = long, by the majority of the fault's steps);
`Xn`, `mn` the natural fault-free blocks ([blocks, 3856, 10]); `pop` the population of the four strata.

## Limits

Simulated faults and simulated sensors; one site and one road network; flat 2D positions; eight vehicles of
which two do most of the driving; no terrain blocking of the radio; the 120 s stop for a terrain fix is not in
the traces; the dark-fix accuracy (3 m) is not used.
