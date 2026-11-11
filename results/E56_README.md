# E56 (task B-96): can a rover tell that another rover's position reports are wrong?

Owner's problem 7 ("How can a rover tell that position data from another rover is wrong?"), hypothesis H15.
Everything here is **simulated**: simulated motion, simulated sensors, simulated faults. Parameters are from
research note 01, section D (status `FROM_NOTE_01`); seven that the note does not give are assumptions and are
listed in section 9. Numbers: `results/E56_integrity.json` (all), `results/table_E56.csv` (per detector, rate,
fault type and ranging class), `results/E56_runs.csv` (every training run).

## 1. What was built

| Piece | Where |
|---|---|
| 1 Hz motion from the ATC traces | `lunarsim/nn/tracks.py` |
| Named faults and honest disturbances, the ten per-step inputs | `lunarsim/nn/faults.py`, `lunarsim/nn/pnt_params.json` |
| Deterministic dataset builder, splits, manifest | `lunarsim/nn/dataset.py`, `data/atc/integrity/` |
| Four classical baselines and the shared false-alarm calibration | `lunarsim/nn/baselines.py` |
| The network (causal 1D convolutions), torch and numpy runtimes, JSON codec | `lunarsim/nn/model.py` |
| Training (resumable, logged) | `lunarsim/nn/train.py` |
| Evaluation at fixed false-alarm rates, bootstrap intervals, policy export | `lunarsim/nn/evaluate.py` |
| Loss landscape and training path | `lunarsim/nn/landscape.py` |
| Runner scripts | `experiments/phase6/nn/` |
| Tests (13, about 20 s) | `tests/test_nn_integrity.py` |

## 2. The setting and the data

Observer A hears B's position report once a second and measures the range to B with a two-way ranging radio:
UWB up to 100 m (0.3 m noise), the long-range base radio beyond that (3 m noise) out to the radio line of sight.
A also has its own position estimate, with an error that grows 2 % of the distance driven and collapses to 1.7 m
at an absolute terrain fix (every stop, and about every 100 m of driving). From the last W seconds A must say
whether B's reports are faulty. Faults are put into B's reported position: jump (5 to 50 m), slow drift (0.01 to
0.5 m/s), frozen report, frame error (300 to 1,000 m), noise inflation (x 3 to 10). Fault-free data contains the
honest disturbances: B stopping and starting, A's and B's errors growing and collapsing at a fix (a fix moves a
report by metres at once), dropouts beyond radio range, a change of ranging class at 100 m, blocked-path range
bias (+1 m bursts). True motion is the project's own simulator: 17 seeds of `tools/atc/export_trace.py` (one
simulated month each, two runs per seed), rebuilt at 1 Hz. Full description: `data/atc/integrity/README.md`.

Ten inputs per step, all things A can know: normalised range innovation z, measured range, reported speed and
heading change (from consecutive reports), B's claimed uncertainty, A's own claimed uncertainty, link-quality
flag, time since A's last fix, range-valid flag, ranging class.

## 3. The split

By simulator seed (month) and by vehicle pair, so no pair-month, no seed and no pair is in two splits.

| Split | Seeds | Pairs | Fault streams (20 scored min, one fault each) | Fault-free |
|---|---|---|---|---|
| train | 1 to 6 | 14 | 3,600 (720 per type) | 1,008 design streams |
| validation | 7 to 9 | 8 | 1,020 (204 per type) | 600 natural blocks of 1 h |
| test | 10 to 13 | 6 | 2,000 (400 per type) | 575 natural blocks of 1 h |
| out of distribution | 14 to 17 | the test pairs | 2,000 (400 per type) | 542 natural blocks of 1 h |

Out of distribution: ranging noise x 2 and dead reckoning 5 % while A's filter still assumes the nominal values;
jumps of 2 to 5 m and drifts of 0.005 to 0.01 m/s (outside the training range).

Fault streams are 70 % windows with driving and 30 % without, about half in UWB range and half in long range.
Fault-free blocks are drawn equally from four strata (driving or not) x (UWB or long) and weighted back to the
natural share of each stratum, so "false alarms per pair-day" is a rate in natural operation (11 to 14 % of
pair-hours contain driving, depending on the split; 15 to 30 % are in UWB range).

## 4. Alarms, false alarms, thresholds

One definition for every detector. A detector gives a score per second; an alarm is a second with score above
the threshold. A **false alarm** is a 60 s bin of fault-free stream with at least one alarm. For each detector
(and each seed of the network) the threshold for **1 false alarm per pair-day** and for **1 per pair-hour** is
the lowest one that keeps the weighted rate at or below the target on the **validation** fault-free blocks.
Nothing is set on test data. A fault is **found** if an alarm falls inside it; the **delay** is the first such
second minus the onset. The 128 s after a fault ends are not scored.

## 5. Baselines (built first)

| Baseline | What | Tuned on validation |
|---|---|---|
| chi-square per step | z^2 | nothing |
| chi-square windowed | mean of z^2 over the last W steps | W = 5 s (of 5, 10, 30, 60, 120) |
| CUSUM, two-sided | on z with reference k; variant on z minus its own mean 120 to 240 s earlier | k = 3, centred variant (of k 0.25 to 6, raw or centred) |
| logistic regression | 28 hand-made statistics of the last 16 s and 128 s | fitted on training data |

The CUSUM on z itself does badly here (validation recall 0.27 to 0.72 at 1 per pair-day, best at k = 3 where it
is close to a per-step test): the honest innovation is not zero-mean, because navigation errors bias it for
minutes, so a small k integrates the bias. Centring z on its recent mean repairs most of that and was chosen by
the validation rule. The logistic regression is the strongest baseline.

## 6. The network and how it was chosen

A causal stack of six dilated 1D convolutions (kernel 3, dilations 1, 2, 4, 8, 16, 32, 24 channels, ReLU, a
residual connection from the second layer on) and a 1 x 1 convolution to one logit: the probability that B's
reports are faulty at the end of the last **127 seconds**. Inputs are squashed by fixed transforms (no fitted
statistics). No normalisation layers. **9,529 parameters**: 38,116 bytes as float32, 19,058 as float16, about
10,137 as int8 (an estimate: the int8 network was not built). Loss: class-balanced binary cross-entropy per scored
step. Adam, learning rate 0.003 with cosine decay, 16 epochs, batches of 32 crops of 728 s, CPU, two threads,
about 5 to 9 minutes per run. The model is the weights after the last epoch (no early stopping).

Search rule, fixed before the first run: score = macro event recall on validation faults at 1 false alarm per
pair-day; a change is a gain if it beats the best score so far by more than 0.005; stop after three changes in a
row without a gain; choose the smallest configuration within 0.005 of the best. Five runs (seed 100):

| # | Change | Parameters | Window | Val loss | Val recall at 1/pair-day | at 1/pair-hour |
|---|---|---|---|---|---|---|
| 1 | start: 24 channels, 6 layers, 8 epochs | 9,529 | 127 s | 0.2892 | 0.887 | 0.920 |
| 2 | 16 epochs | 9,529 | 127 s | 0.2791 | **0.901** (gain) | 0.942 |
| 3 | 32 channels (against 2) | 16,545 | 127 s | 0.2750 | 0.906 (+0.0049: no gain by the rule) | 0.945 |
| 4 | window 255 s (against 2) | 11,281 | 255 s | 0.2629 | 0.899 (no gain) | 0.950 |
| 5 | learning rate 0.001 (against 2) | 9,529 | 127 s | 0.2922 | 0.863 (no gain) | 0.924 |

Three changes in a row without a gain: the search stopped and configuration 2 was trained with seeds 0 to 4
(validation recall at 1/pair-day 0.898, 0.897, 0.899, 0.900, 0.906). Notes for a reader who wants to push
further: run 3 missed the gain margin by 0.0001, and run 4 has the lowest validation loss; neither was pursued,
because the rule was fixed in advance. A GRU variant exists in `model.py` and was not run. The search is short
(five runs) because each run costs several minutes on this machine. All ten runs in `results/E56_runs.csv` were
trained on the note-01 data; no network was trained on the earlier provisional parameters (only the baselines
were tried on them, on validation data, before the note arrived; those numbers were discarded).

## 7. Final numbers (test set scored once; configuration frozen on validation)

Recall / median delay of the found faults, at the thresholds that give 1 false alarm per pair-day on validation.
Network: mean of 5 seeds (standard deviation of recall over seeds at most 0.012). 400 faults per type.

**Test set**

| Detector | realised false alarms per pair-day (95 %) | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 0.68 (0.18 to 1.42) | 0.70 / 0 s | 0.57 / 109 s | 0.94 / 37 s | 0.99 / 0 s | 0.35 / 86 s | 0.71 / 18 s |
| chi-square windowed | 1.35 (0.03 to 3.70) | 0.76 / 1 s | 0.63 / 100 s | 0.96 / 31 s | 0.99 / 0 s | 0.17 / 64 s | 0.70 / 12 s |
| CUSUM | 2.03 (1.46 to 2.72) | 0.77 / 0 s | 0.56 / 78 s | 0.97 / 29 s | 0.99 / 0 s | 0.57 / 53 s | 0.77 / 14 s |
| logistic regression | 1.26 (0.87 to 1.69) | 0.95 / 0 s | 0.56 / 81 s | 0.95 / 39 s | 1.00 / 0 s | 0.83 / 6 s | 0.86 / 3 s |
| network | 0.53 (0.29 to 0.82) | 0.92 / 1 s | 0.62 / 85 s | 0.98 / 28 s | 1.00 / 0 s | 1.00 / 12 s | 0.90 / 11 s |

**Out-of-distribution set, the same thresholds** (ranging noise x 2, dead reckoning 5 %, jumps 2 to 5 m, drifts
0.005 to 0.01 m/s). No detector keeps its false-alarm rate, so the recalls in this table are NOT at the same
false-alarm rate:

| Detector | realised false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 479 | 0.54 / 60 s | 0.57 / 62 s | 0.98 / 24 s | 1.00 / 0 s | 0.86 / 46 s | 0.79 / 20 s |
| chi-square windowed | 199 | 0.44 / 89 s | 0.40 / 105 s | 0.98 / 25 s | 1.00 / 0 s | 0.71 / 58 s | 0.70 / 20 s |
| CUSUM | 863 | 0.67 / 19 s | 0.67 / 27 s | 0.98 / 17 s | 1.00 / 0 s | 0.89 / 19 s | 0.84 / 12 s |
| logistic regression | 18.3 | 0.45 / 8 s | 0.17 / 53 s | 0.96 / 30 s | 1.00 / 0 s | 0.98 / 4 s | 0.71 / 3 s |
| network | 13.8 | 0.23 / 48 s | 0.11 / 146 s | 0.96 / 32 s | 1.00 / 0 s | 1.00 / 12 s | 0.66 / 12 s |

**Out of distribution with thresholds reset** on one half of the OOD fault-free blocks and false alarms counted
on the other half (0.7 to 1.9 per pair-day). This shows what can be told apart, not what a deployed detector
does: jump 0.01 to 0.03 and drift 0.01 to 0.03 for every detector; frozen 0.78 to 0.92; frame 0.99 to 1.00; noise
0.02 to 0.07 for the innovation tests, 0.40 for the regression, 0.98 for the network; all faults 0.38 to 0.45 for
the baselines, 0.59 for the network.

At 1 false alarm per pair-hour on the test set the regression and the network are level (all faults 0.95 and
0.94; drift 0.78 and 0.73); the innovation tests reach 0.78 to 0.86. The tables at the end give every number,
the per-class tables, precision, p90 delay and the window-level ROC and PR AUC (network 0.951 and 0.949,
regression 0.948 and 0.941, chi-square per step 0.849 and 0.843). The CUSUM's window-level AUC (0.595) says
nothing about it: its statistic is never reset, so it stays high on the fault-free steps after a fault has ended,
and those steps count as negatives in the window-level score. Its event-level numbers do not have this problem
(false alarms are counted on fault-free blocks and, on fault streams, only before the fault).

**Per ranging class** (test, 1 per pair-day): the network's recall is 0.89 on faults seen mostly through UWB and
0.91 on faults seen mostly through the long-range radio; the regression 0.88 and 0.85; chi-square per step 0.72
and 0.71. Drift is found more slowly at long range (network 92 s against 75 s) because 3 m of range noise hides a
small offset longer. Out of distribution the innovation tests break in the long-range class (chi-square 564 false
alarms per pair-day there, 14 in UWB).

**Precision** depends on how often faults happen. If one fault happens per pair-day of natural operation,
precision = recall / (recall + false alarms per pair-day): network 0.63, chi-square per step 0.51, regression
0.41, CUSUM 0.28 (test set, all faults).

**Cost on the flight computer.** 9,529 parameters; 38 kB as float32, 19 kB as float16, about 10 kB as int8
(estimate). One whole 127 s window on this CPU (Intel Core, one thread): median 1.27 ms, p99 2.39 ms in torch;
0.80 ms and 1.53 ms in the numpy reference runtime. A radiation-tolerant processor is slower by a factor we did
not measure.

## 8. Where the network wins and where it does not; H15

PREREG6 states H15 as four tests at 1 false alarm per pair-day.

| Test | Result on the test set | Verdict |
|---|---|---|
| (a) on slow drifts the network's median delay is shorter than the per-step chi-square's, bootstrap interval excludes zero | 85 s against 109 s: difference -24.1 s (95 % interval -35.1 to -14.9); on the faults both found -23.2 s (-26.8 to -19.9); recall 0.618 against 0.575 (+0.043, 0.020 to 0.068). The network's realised false-alarm rate is the lower of the two (0.53 against 0.68 per pair-day) | **held** |
| (b) on jumps the two are within one second (equivalence margin 1 s) | the network is slower by 1.2 s (90 % interval 1.0 to 1.6): outside the margin. It finds more jumps: recall 0.919 against 0.698 (+0.22, 0.18 to 0.26) | **failed**, in both directions: about one second later, and many more found. "No better on jumps" was wrong |
| (c) against CUSUM, no predicted direction | drift delay +6.4 s (-3.1 to +15.9), no difference; drift recall +0.053 (0.026 to 0.080); jump recall +0.15. The CUSUM's realised false-alarm rate was 2.0 per pair-day | exploratory |
| (d) out of distribution the network's recall may fall below CUSUM's | at the deployed thresholds: jump 0.23 against 0.67, drift 0.11 against 0.67. But the CUSUM then gives 863 false alarms per pair-day and the network 14; with thresholds reset to about 1 per pair-day nobody finds these faults (0.01 to 0.03) | **happened**: the network fails out of distribution on small jumps and slow drifts, and so does everything else at an honest false-alarm rate |

Plainly:

- **The network beats the chi-square innovation tests and the CUSUM** on jumps (it uses the reported speed, which
  a jump spikes whatever its direction; the innovation only sees the part of a jump along the line of sight), on
  noise inflation (1.00 against 0.35 and 0.57) and on overall recall (0.90 against 0.71 and 0.77), with fewer
  false alarms on the test set than any of them.
- **On slow drifts it is 24 s earlier than chi-square and finds 4 points more**, but it is **not earlier than the
  CUSUM or the logistic regression** (85 s against 78 s and 81 s medians, differences inside the intervals). Its
  drift advantage over those two is recall (+5 points) at a lower false-alarm rate.
- **It does not beat the logistic regression on jumps** (0.92 against 0.95, difference -0.035, interval -0.054 to
  -0.019; and one second slower) **or at 1 false alarm per pair-hour** (0.94 against 0.95 overall, drift 0.73
  against 0.78). A regression on 28 hand-made statistics is nearly as good as the network on this data; the
  network's clear gains over it are noise inflation at the strict rate (1.00 against 0.83) and frozen reports.
- **About 40 % of slow drifts are found by nobody**: a range sees only the offset along the line of sight, and a
  drift of centimetres per second stays inside the claimed uncertainty for minutes.
- **Out of distribution every detector's calibration breaks.** With doubled ranging noise and 5 % dead reckoning
  the false-alarm rate of the network rises from 0.53 to 13.8 per pair-day (26 times), the regression's to 18,
  the innovation tests' to 200 to 860, because A's filter still claims the nominal uncertainty. The network keeps
  frozen, frame and noise faults (0.96, 1.00, 1.00) and loses the small jumps and slow drifts.

## 9. Loss landscape and the training path

Run: final seed 0. Saved: the weight vector at the start, after steps 1, 2, 4, 8, 16, 32, 64 of the first epoch
and after each of the 16 epochs (24 checkpoints, 9,529 numbers each). The loss is the training loss function on
two fixed subsets (60 validation fault streams, 60 training fault streams, 12 per fault type).

1. Random slice (Li et al. 2018): validation loss at final weights + a d1 + b d2, two Gaussian directions with
   filter-wise normalisation (biases not perturbed), a and b from -1 to 1, 41 x 41.
2. PCA plane of the path (Li et al. 2018, section 7): PCA of the checkpoints minus the final weights; validation
   loss on a 42 x 42 grid that covers the whole path with a 20 % margin and has the final model exactly at a node.
   **The two components explain 96.0 % of the path's variance (86.5 % and 9.5 %).**
3. The same surface for the training loss.
4. Straight-line interpolation from the initial to the final weights (Goodfellow et al. 2015), 61 points from
   -0.25 to 1.25.

Self-check (validation subset): the grid centre equals the final loss exactly (difference 0). Loss at the grid
node nearest each projected checkpoint against the loss recorded at that checkpoint: **median gap 0.011 (3.6 %),
largest 0.069 (14 %)**, the largest in the first epoch (epoch 0.44), where the path moves fastest. Evaluating the
plane exactly at the projected points gives the same picture (median 0.011, largest 0.069; 11 % relative), so the
gap is the part of the path outside the plane, not the grid. Late checkpoints lie mostly outside the plane as a
share of their (small) distance to the end (up to 97 %), but there the loss is flat and the gap is small.

What it shows: a single smooth valley; the path curves into it during the first two epochs and then slides
along the floor; the straight line from start to finish has no barrier. The optimiser is Adam with a decaying
step, so this is its path, not that of plain gradient descent.

Web export: `data/atc/integrity/landscape.json` (44 kB): grid axes, the three loss grids (4 significant digits),
the path with epoch, step and losses, explained variance, the self-check, the layer list with shapes, the input
transforms. Weights for a browser: `data/policies/integrity_net_v1.json` (135 kB, format `lunarsim-policy`, kind
`tcn`, with the two validation thresholds) and `integrity_net_v1.check.json` (ten validation windows of 127 x 10
raw inputs and the expected logits, tolerance 1e-6).

Figures (`figures/phase6/`, PNG and PDF): `fig_E56_landscape_3d`, `fig_E56_landscape_contour` (validation and
training, path with epoch marks), `fig_E56_landscape_random`, `fig_E56_interpolation`, `fig_E56_curves`,
`fig_E56_delay_test`, `fig_E56_delay_ood`, `fig_E56_roc`, `fig_E56_recall`.

## 10. Limitations

- **Simulated faults and sensors.** No real rover telemetry, no real ranging radio. The fault shapes are five
  textbook shapes; a real fault can look like none of them. The network was trained on the same generator it was
  tested on (different seeds, pairs and months, same physics).
- **Parameter provenance.** Ranging noise and range, dead-reckoning drift, fix accuracy and fix spacing are from
  note 01, section D; several of those are the note's own assumptions (UWB range 100 m, long-range noise 3 m,
  fix spacing 100 m, blocked-path bias +1 m). Not in the note, assumed here: report noise 0.5 m and 1 Hz (the
  task's values), burst rate 2 per hour and length 5 to 60 s, link-flag probabilities 0.8 and 0.05, the 5 km cap
  on radio range. The note's "1.7 m horizontal" is read as 1.7 m per axis. Only the nominal values were run; the
  sweep ranges in `pnt_params.json` were not swept, except through the one out-of-distribution set.
- **One site, one road network, eight vehicles**, of which two do most of the driving; the pair split holds out
  pairs, not vehicles, sites or fleet sizes.
- **2D positions, no terrain.** Radio line of sight is the smooth-Moon horizon; terrain blocking, multipath and
  elevation are not modelled. The 120 s stop the note gives for a terrain fix is not in the traces. The dark-fix
  accuracy (3 m) is not used.
- **A single range, no filter.** A real vehicle would fuse ranges to several neighbours and beacons; one range
  cannot see an error across the line of sight. The baselines are tests on one innovation stream, not a full
  integrity monitor.
- **False-alarm rates near 1 per pair-day rest on few events**: 575 test blocks stand for 23 weighted pair-days,
  so the realised test rates (0.5 to 2.0) have wide intervals and differ between detectors. Recalls are compared
  at the validation thresholds, not at exactly equal test rates.
- **A false alarm is a 60 s bin**, and a fault-stream fault follows only 1 to 7 clean minutes; the stated
  precision is a formula for an assumed fault rate, not a measurement of field precision.
- **Short model search** (five runs, one seed each); run 3 missed the gain margin by 0.0001 and a longer window
  had a lower validation loss. A larger or recurrent model was not explored. No fault-type head was trained.
- **int8 size is an estimate**; inference time is on a desktop CPU.
- **Determinism** is per machine and numpy version (2.5.3); the sha256 values in `manifest.json` can differ in
  the last float bit elsewhere.
- **Loss landscape**: two-dimensional slices of a 9,529-dimensional surface, on 60-stream subsets, for one seed.

## 11. Commands (each under 9 minutes; a run that stops at its time limit resumes when called again)

```
set PY=.venv\Scripts\python
rem traces for seeds 2..17 (26 s each); seed 1 is data/atc/trace_pair
%PY% tools/atc/export_trace.py --seed 2 --out data/atc/integrity/traces/seed02
rem dataset (1.5 to 3.5 min per split)
%PY% -m lunarsim.nn.dataset --split train
%PY% -m lunarsim.nn.dataset --split val
%PY% -m lunarsim.nn.dataset --split test
%PY% -m lunarsim.nn.dataset --split ood
rem baselines: fit the regression, tune W and k on validation (1 min)
%PY% experiments/phase6/nn/run_baselines.py
rem model search, iterations 1..5 (3 to 9 min each)
%PY% experiments/phase6/nn/run_search.py --iter 1
rem the chosen configuration, seeds 0..4 (5 to 9 min each; seed 0 saves the weight trajectory)
%PY% experiments/phase6/nn/run_final.py --seed 0
rem loss landscape (about 25 min in 3 to 4 calls; exit code 3 = call again)
%PY% -m lunarsim.nn.landscape --run final_s0
rem evaluation on test and out of distribution, policy export (8 min; refuses to run twice without --force)
%PY% -m lunarsim.nn.evaluate
rem a rehearsal that never opens the test sets
%PY% -m lunarsim.nn.evaluate --on val
rem figures and the tables below
%PY% experiments/phase6/nn/make_figures.py
%PY% experiments/phase6/nn/make_tables.py --write
rem tests
%PY% -m pytest tests/test_nn_integrity.py -q
```

Working files (checkpoints, cached scores) are in `.cache/nn/` (not in git). Seeds: dataset master seed 56;
search seed 100; final seeds 0 to 4; bootstrap 1,000 resamples with fixed seeds; random-slice seed 5601.
Dataset sha256 (over the manifest's array hashes): `5499057ae76d65cc...` (full value in
`results/E56_integrity.json`).

## 12. Generated tables

Recall / median delay of the found faults unless the header says otherwise. "ood" = out-of-distribution set at
the deployed thresholds; "ood_recalibrated" = thresholds reset on half of the OOD fault-free blocks.

<!-- BEGIN GENERATED TABLES -->

### test, threshold for 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 0.68 | 0.70 / 0 s | 0.57 / 109 s | 0.94 / 37 s | 0.99 / 0 s | 0.35 / 86 s | 0.71 / 18 s |
| chi-square windowed | 1.35 | 0.76 / 1 s | 0.63 / 100 s | 0.96 / 31 s | 0.99 / 0 s | 0.17 / 64 s | 0.70 / 12 s |
| CUSUM | 2.03 | 0.77 / 0 s | 0.56 / 78 s | 0.97 / 29 s | 0.99 / 0 s | 0.57 / 53 s | 0.77 / 14 s |
| logistic regression | 1.26 | 0.95 / 0 s | 0.56 / 81 s | 0.95 / 39 s | 1.00 / 0 s | 0.83 / 6 s | 0.86 / 3 s |
| network (5 seeds) | 0.53 | 0.92 / 1 s | 0.62 / 85 s | 0.98 / 28 s | 1.00 / 0 s | 1.00 / 12 s | 0.90 / 11 s |

### test, threshold for 1 false alarm per pair-hour: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 24.69 | 0.80 / 0 s | 0.67 / 89 s | 0.97 / 28 s | 0.99 / 0 s | 0.69 / 42 s | 0.82 / 15 s |
| chi-square windowed | 14.13 | 0.80 / 0 s | 0.69 / 90 s | 0.97 / 26 s | 0.99 / 0 s | 0.43 / 61 s | 0.78 / 13 s |
| CUSUM | 15.99 | 0.84 / 0 s | 0.67 / 70 s | 0.98 / 23 s | 0.99 / 0 s | 0.79 / 36 s | 0.86 / 13 s |
| logistic regression | 23.64 | 1.00 / 0 s | 0.78 / 59 s | 0.99 / 16 s | 1.00 / 0 s | 1.00 / 2 s | 0.95 / 0 s |
| network (5 seeds) | 22.03 | 0.98 / 1 s | 0.73 / 64 s | 0.99 / 19 s | 1.00 / 0 s | 1.00 / 8 s | 0.94 / 5 s |

### ood, threshold for 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 479.05 | 0.54 / 60 s | 0.57 / 62 s | 0.98 / 24 s | 1.00 / 0 s | 0.86 / 46 s | 0.79 / 20 s |
| chi-square windowed | 198.97 | 0.44 / 89 s | 0.40 / 105 s | 0.98 / 25 s | 1.00 / 0 s | 0.71 / 58 s | 0.70 / 20 s |
| CUSUM | 863.42 | 0.67 / 19 s | 0.67 / 27 s | 0.98 / 17 s | 1.00 / 0 s | 0.89 / 19 s | 0.84 / 12 s |
| logistic regression | 18.26 | 0.45 / 8 s | 0.17 / 53 s | 0.96 / 30 s | 1.00 / 0 s | 0.98 / 4 s | 0.71 / 3 s |
| network (5 seeds) | 13.84 | 0.23 / 48 s | 0.11 / 146 s | 0.96 / 32 s | 1.00 / 0 s | 1.00 / 12 s | 0.66 / 12 s |

### ood, threshold for 1 false alarm per pair-hour: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 1040.89 | 0.68 / 15 s | 0.68 / 18 s | 0.99 / 13 s | 1.00 / 0 s | 0.94 / 12 s | 0.86 / 9 s |
| chi-square windowed | 689.59 | 0.68 / 28 s | 0.65 / 42 s | 0.99 / 16 s | 1.00 / 0 s | 0.90 / 22 s | 0.84 / 12 s |
| CUSUM | 1168.34 | 0.69 / 9 s | 0.69 / 12 s | 0.99 / 10 s | 1.00 / 0 s | 0.94 / 9 s | 0.86 / 6 s |
| logistic regression | 1066.18 | 0.90 / 0 s | 0.75 / 7 s | 1.00 / 0 s | 1.00 / 0 s | 1.00 / 0 s | 0.93 / 0 s |
| network (5 seeds) | 241.37 | 0.64 / 20 s | 0.45 / 91 s | 0.99 / 18 s | 1.00 / 0 s | 1.00 / 7 s | 0.82 / 8 s |

### ood_recalibrated, threshold for 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 1.04 | 0.02 / 52 s | 0.02 / 314 s | 0.89 / 56 s | 0.99 / 0 s | 0.07 / 152 s | 0.40 / 6 s |
| chi-square windowed | 0.74 | 0.01 / 94 s | 0.01 / 96 s | 0.90 / 50 s | 0.99 / 0 s | 0.02 / 28 s | 0.39 / 0 s |
| CUSUM | 0.92 | 0.01 / 193 s | 0.01 / 0 s | 0.86 / 72 s | 0.99 / 0 s | 0.02 / 136 s | 0.38 / 4 s |
| logistic regression | 1.89 | 0.03 / 223 s | 0.03 / 212 s | 0.78 / 70 s | 1.00 / 0 s | 0.40 / 32 s | 0.45 / 11 s |
| network (5 seeds) | 1.67 | 0.03 / 145 s | 0.03 / 146 s | 0.92 / 44 s | 1.00 / 0 s | 0.98 / 15 s | 0.59 / 15 s |

### ood_recalibrated, threshold for 1 false alarm per pair-hour: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 23.87 | 0.11 / 125 s | 0.10 / 218 s | 0.93 / 44 s | 1.00 / 0 s | 0.33 / 143 s | 0.49 / 23 s |
| chi-square windowed | 26.84 | 0.16 / 99 s | 0.12 / 172 s | 0.96 / 34 s | 1.00 / 0 s | 0.33 / 115 s | 0.51 / 17 s |
| CUSUM | 31.68 | 0.22 / 137 s | 0.18 / 177 s | 0.96 / 33 s | 1.00 / 0 s | 0.41 / 131 s | 0.55 / 20 s |
| logistic regression | 29.78 | 0.54 / 5 s | 0.23 / 77 s | 0.97 / 25 s | 1.00 / 0 s | 0.98 / 2 s | 0.74 / 2 s |
| network (5 seeds) | 29.40 | 0.31 / 37 s | 0.17 / 175 s | 0.97 / 28 s | 1.00 / 0 s | 1.00 / 11 s | 0.69 / 11 s |

### test, ranging class uwb, 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 0.00 | 0.69 / 0 s | 0.56 / 104 s | 0.85 / 26 s | 1.00 / 0 s | 0.56 / 52 s | 0.72 / 0 s |
| chi-square windowed | 6.23 | 0.80 / 0 s | 0.65 / 92 s | 0.91 / 20 s | 1.00 / 0 s | 0.46 / 63 s | 0.76 / 3 s |
| CUSUM | 0.58 | 0.77 / 0 s | 0.55 / 73 s | 0.91 / 20 s | 1.00 / 0 s | 0.69 / 32 s | 0.76 / 1 s |
| logistic regression | 0.78 | 0.97 / 0 s | 0.61 / 75 s | 0.91 / 26 s | 1.00 / 0 s | 0.92 / 4 s | 0.88 / 0 s |
| network (5 seeds) | 0.49 | 0.93 / 1 s | 0.63 / 75 s | 0.94 / 18 s | 1.00 / 0 s | 1.00 / 11 s | 0.89 / 3 s |

### test, ranging class long, 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 0.81 | 0.71 / 0 s | 0.59 / 114 s | 0.96 / 41 s | 0.99 / 0 s | 0.27 / 159 s | 0.71 / 24 s |
| chi-square windowed | 0.37 | 0.72 / 1 s | 0.61 / 104 s | 0.97 / 36 s | 0.99 / 0 s | 0.06 / 119 s | 0.68 / 18 s |
| CUSUM | 2.32 | 0.78 / 0 s | 0.58 / 82 s | 0.98 / 33 s | 0.99 / 0 s | 0.52 / 70 s | 0.78 / 21 s |
| logistic regression | 1.35 | 0.94 / 0 s | 0.53 / 94 s | 0.96 / 45 s | 1.00 / 0 s | 0.80 / 8 s | 0.85 / 7 s |
| network (5 seeds) | 0.54 | 0.91 / 2 s | 0.61 / 92 s | 0.99 / 32 s | 1.00 / 0 s | 1.00 / 12 s | 0.91 / 12 s |

### ood, ranging class uwb, 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 14.20 | 0.06 / 114 s | 0.06 / 34 s | 0.94 / 20 s | 1.00 / 0 s | 0.62 / 49 s | 0.46 / 7 s |
| chi-square windowed | 17.31 | 0.14 / 98 s | 0.06 / 268 s | 0.94 / 15 s | 1.00 / 0 s | 0.41 / 49 s | 0.43 / 2 s |
| CUSUM | 27.59 | 0.20 / 52 s | 0.13 / 53 s | 0.94 / 16 s | 1.00 / 0 s | 0.70 / 31 s | 0.52 / 4 s |
| logistic regression | 7.24 | 0.30 / 8 s | 0.11 / 33 s | 0.95 / 14 s | 1.00 / 0 s | 0.93 / 4 s | 0.59 / 2 s |
| network (5 seeds) | 3.27 | 0.21 / 26 s | 0.05 / 169 s | 0.97 / 18 s | 1.00 / 0 s | 1.00 / 11 s | 0.57 / 9 s |

### ood, ranging class long, 1 false alarm per pair-day: recall / median delay

| Detector | false alarms per pair-day | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|---|
| chi-square per step | 564.00 | 0.86 / 58 s | 0.84 / 63 s | 0.99 / 26 s | 1.00 / 0 s | 0.97 / 44 s | 0.94 / 23 s |
| chi-square windowed | 232.17 | 0.64 / 89 s | 0.59 / 102 s | 0.99 / 29 s | 1.00 / 0 s | 0.84 / 61 s | 0.83 / 26 s |
| CUSUM | 1016.16 | 0.98 / 18 s | 0.95 / 26 s | 0.99 / 17 s | 1.00 / 0 s | 0.98 / 17 s | 0.98 / 13 s |
| logistic regression | 20.27 | 0.54 / 9 s | 0.21 / 67 s | 0.96 / 35 s | 1.00 / 0 s | 1.00 / 3 s | 0.76 / 4 s |
| network (5 seeds) | 15.77 | 0.24 / 60 s | 0.15 / 141 s | 0.96 / 37 s | 1.00 / 0 s | 1.00 / 12 s | 0.70 / 13 s |

### test, details at 1 false alarm per pair-day

| Detector | fault | n | recall (95 % interval) | sd over seeds | precision at 1 fault per pair-day | delay median (95 %) | delay p90 | window ROC AUC | PR AUC |
|---|---|---|---|---|---|---|---|---|---|
| chi-square per step | jump | 400 | 0.698 (0.652 to 0.743) | 0.000 | 0.51 | 0 s (0 to 0) | 37 s | 0.907 | 0.899 |
| chi-square per step | drift | 400 | 0.575 (0.530 to 0.623) | 0.000 | 0.46 | 109 s (94 to 127) | 297 s | 0.785 | 0.769 |
| chi-square per step | frozen | 400 | 0.943 (0.917 to 0.965) | 0.000 | 0.58 | 37 s (33 to 40) | 108 s | 0.958 | 0.955 |
| chi-square per step | frame | 400 | 0.995 (0.988 to 1.000) | 0.000 | 0.59 | 0 s (0 to 0) | 0 s | 0.997 | 0.997 |
| chi-square per step | noise | 400 | 0.355 (0.305 to 0.400) | 0.000 | 0.34 | 86 s (60 to 125) | 312 s | 0.601 | 0.487 |
| chi-square per step | all | 2000 | 0.713 (0.693 to 0.733) | 0.000 | 0.51 | 18 s (15 to 22) | 163 s | 0.849 | 0.843 |
| chi-square windowed | jump | 400 | 0.755 (0.710 to 0.795) | 0.000 | 0.36 | 1 s (0 to 1) | 6 s | 0.920 | 0.912 |
| chi-square windowed | drift | 400 | 0.630 (0.582 to 0.675) | 0.000 | 0.32 | 100 s (84 to 112) | 302 s | 0.797 | 0.787 |
| chi-square windowed | frozen | 400 | 0.960 (0.940 to 0.978) | 0.000 | 0.42 | 31 s (28 to 34) | 95 s | 0.963 | 0.962 |
| chi-square windowed | frame | 400 | 0.995 (0.988 to 1.000) | 0.000 | 0.42 | 0 s (0 to 0) | 0 s | 0.998 | 0.997 |
| chi-square windowed | noise | 400 | 0.175 (0.138 to 0.212) | 0.000 | 0.12 | 64 s (43 to 110) | 248 s | 0.730 | 0.597 |
| chi-square windowed | all | 2000 | 0.703 (0.683 to 0.722) | 0.000 | 0.34 | 12 s (4 to 15) | 128 s | 0.880 | 0.868 |
| CUSUM | jump | 400 | 0.772 (0.730 to 0.810) | 0.000 | 0.28 | 0 s (0 to 0) | 9 s | 0.645 | 0.432 |
| CUSUM | drift | 400 | 0.565 (0.517 to 0.613) | 0.000 | 0.22 | 78 s (70 to 90) | 210 s | 0.577 | 0.381 |
| CUSUM | frozen | 400 | 0.970 (0.953 to 0.985) | 0.000 | 0.32 | 29 s (26 to 32) | 85 s | 0.583 | 0.354 |
| CUSUM | frame | 400 | 0.995 (0.988 to 1.000) | 0.000 | 0.33 | 0 s (0 to 0) | 0 s | 0.603 | 0.378 |
| CUSUM | noise | 400 | 0.568 (0.520 to 0.618) | 0.000 | 0.22 | 53 s (46 to 66) | 238 s | 0.512 | 0.369 |
| CUSUM | all | 2000 | 0.774 (0.755 to 0.791) | 0.000 | 0.28 | 14 s (11 to 18) | 126 s | 0.595 | 0.389 |
| logistic regression | jump | 400 | 0.955 (0.935 to 0.973) | 0.000 | 0.43 | 0 s (0 to 0) | 0 s | 0.940 | 0.927 |
| logistic regression | drift | 400 | 0.562 (0.512 to 0.610) | 0.000 | 0.31 | 81 s (73 to 100) | 293 s | 0.837 | 0.811 |
| logistic regression | frozen | 400 | 0.950 (0.927 to 0.970) | 0.000 | 0.43 | 39 s (36 to 43) | 102 s | 0.959 | 0.952 |
| logistic regression | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.44 | 0 s (0 to 0) | 0 s | 0.998 | 0.999 |
| logistic regression | noise | 400 | 0.835 (0.797 to 0.868) | 0.000 | 0.40 | 6 s (6 to 8) | 70 s | 0.996 | 0.994 |
| logistic regression | all | 2000 | 0.861 (0.845 to 0.875) | 0.000 | 0.41 | 3 s (1 to 5) | 95 s | 0.948 | 0.941 |
| network (5 seeds) | jump | 400 | 0.919 (0.892 to 0.942) | 0.012 | 0.64 | 1 s (1 to 2) | 3 s | 0.944 | 0.937 |
| network (5 seeds) | drift | 400 | 0.618 (0.570 to 0.664) | 0.012 | 0.54 | 85 s (74 to 96) | 289 s | 0.836 | 0.822 |
| network (5 seeds) | frozen | 400 | 0.977 (0.962 to 0.990) | 0.005 | 0.65 | 28 s (26 to 30) | 72 s | 0.966 | 0.965 |
| network (5 seeds) | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.66 | 0 s (0 to 0) | 0 s | 0.999 | 0.999 |
| network (5 seeds) | noise | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.66 | 12 s (11 to 12) | 20 s | 0.996 | 0.995 |
| network (5 seeds) | all | 2000 | 0.903 (0.890 to 0.915) | 0.004 | 0.63 | 11 s (10 to 11) | 72 s | 0.951 | 0.949 |

### out of distribution, details at 1 false alarm per pair-day (thresholds as deployed)

| Detector | fault | n | recall (95 % interval) | sd over seeds | precision at 1 fault per pair-day | delay median (95 %) | delay p90 | window ROC AUC | PR AUC |
|---|---|---|---|---|---|---|---|---|---|
| chi-square per step | jump | 400 | 0.540 (0.492 to 0.590) | 0.000 | 0.00 | 60 s (42 to 80) | 300 s | 0.553 | 0.387 |
| chi-square per step | drift | 400 | 0.570 (0.522 to 0.618) | 0.000 | 0.00 | 62 s (50 to 79) | 234 s | 0.511 | 0.353 |
| chi-square per step | frozen | 400 | 0.985 (0.973 to 0.995) | 0.000 | 0.00 | 24 s (22 to 27) | 85 s | 0.911 | 0.906 |
| chi-square per step | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.00 | 0 s (0 to 0) | 0 s | 0.997 | 0.997 |
| chi-square per step | noise | 400 | 0.865 (0.830 to 0.897) | 0.000 | 0.00 | 46 s (36 to 56) | 160 s | 0.558 | 0.402 |
| chi-square per step | all | 2000 | 0.792 (0.774 to 0.810) | 0.000 | 0.00 | 20 s (18 to 23) | 146 s | 0.703 | 0.675 |
| chi-square windowed | jump | 400 | 0.438 (0.390 to 0.485) | 0.000 | 0.00 | 89 s (62 to 119) | 362 s | 0.563 | 0.410 |
| chi-square windowed | drift | 400 | 0.403 (0.352 to 0.450) | 0.000 | 0.00 | 105 s (78 to 138) | 346 s | 0.510 | 0.365 |
| chi-square windowed | frozen | 400 | 0.980 (0.965 to 0.993) | 0.000 | 0.00 | 25 s (23 to 29) | 90 s | 0.927 | 0.924 |
| chi-square windowed | frame | 400 | 0.998 (0.993 to 1.000) | 0.000 | 0.00 | 0 s (0 to 0) | 0 s | 0.998 | 0.998 |
| chi-square windowed | noise | 400 | 0.708 (0.662 to 0.755) | 0.000 | 0.00 | 58 s (48 to 65) | 240 s | 0.625 | 0.448 |
| chi-square windowed | all | 2000 | 0.705 (0.684 to 0.725) | 0.000 | 0.00 | 20 s (18 to 23) | 198 s | 0.719 | 0.692 |
| CUSUM | jump | 400 | 0.665 (0.615 to 0.715) | 0.000 | 0.00 | 19 s (16 to 22) | 142 s | 0.506 | 0.352 |
| CUSUM | drift | 400 | 0.665 (0.618 to 0.708) | 0.000 | 0.00 | 27 s (22 to 31) | 112 s | 0.499 | 0.343 |
| CUSUM | frozen | 400 | 0.985 (0.973 to 0.998) | 0.000 | 0.00 | 17 s (15 to 18) | 61 s | 0.609 | 0.372 |
| CUSUM | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.00 | 0 s (0 to 0) | 0 s | 0.581 | 0.364 |
| CUSUM | noise | 400 | 0.892 (0.863 to 0.922) | 0.000 | 0.00 | 19 s (16 to 22) | 93 s | 0.524 | 0.388 |
| CUSUM | all | 2000 | 0.842 (0.824 to 0.858) | 0.000 | 0.00 | 12 s (10 to 13) | 74 s | 0.561 | 0.379 |
| logistic regression | jump | 400 | 0.445 (0.398 to 0.490) | 0.000 | 0.02 | 8 s (6 to 11) | 246 s | 0.609 | 0.440 |
| logistic regression | drift | 400 | 0.172 (0.138 to 0.210) | 0.000 | 0.01 | 53 s (19 to 84) | 350 s | 0.511 | 0.344 |
| logistic regression | frozen | 400 | 0.958 (0.935 to 0.975) | 0.000 | 0.05 | 30 s (28 to 34) | 98 s | 0.913 | 0.894 |
| logistic regression | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.05 | 0 s (0 to 0) | 0 s | 0.999 | 0.999 |
| logistic regression | noise | 400 | 0.978 (0.963 to 0.993) | 0.000 | 0.05 | 4 s (3 to 4) | 20 s | 0.990 | 0.984 |
| logistic regression | all | 2000 | 0.711 (0.692 to 0.731) | 0.000 | 0.04 | 3 s (2 to 4) | 78 s | 0.799 | 0.783 |
| network (5 seeds) | jump | 400 | 0.226 (0.187 to 0.263) | 0.037 | 0.02 | 48 s (36 to 73) | 317 s | 0.614 | 0.455 |
| network (5 seeds) | drift | 400 | 0.113 (0.086 to 0.142) | 0.018 | 0.01 | 146 s (85 to 214) | 368 s | 0.534 | 0.372 |
| network (5 seeds) | frozen | 400 | 0.962 (0.943 to 0.978) | 0.005 | 0.07 | 32 s (28 to 35) | 100 s | 0.943 | 0.936 |
| network (5 seeds) | frame | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.07 | 0 s (0 to 0) | 0 s | 1.000 | 0.999 |
| network (5 seeds) | noise | 400 | 1.000 (1.000 to 1.000) | 0.000 | 0.07 | 12 s (11 to 12) | 21 s | 0.992 | 0.990 |
| network (5 seeds) | all | 2000 | 0.660 (0.641 to 0.680) | 0.011 | 0.05 | 12 s (11 to 13) | 73 s | 0.818 | 0.808 |

### false alarms on fault-free blocks

| Detector | set | target | false alarms per pair-day (95 %) | per hour, blocks with driving | per hour, blocks without | UWB blocks, per pair-day | long-range blocks, per pair-day |
|---|---|---|---|---|---|---|---|
| chi-square per step | test | 1 | 0.68 (0.18 to 1.42) | 0.021 | 0.0175 | 0.00 | 0.81 |
| chi-square per step | test | 24 | 24.69 (16.86 to 34.29) | 0.741 | 0.6807 | 1.60 | 29.33 |
| chi-square per step | ood | 1 | 479.05 (447.61 to 507.69) | 16.335 | 12.6175 | 14.20 | 564.00 |
| chi-square per step | ood | 24 | 1040.89 (1002.24 to 1073.96) | 34.891 | 27.6632 | 40.22 | 1223.75 |
| chi-square windowed | test | 1 | 1.35 (0.03 to 3.70) | 0.017 | 0.1368 | 6.23 | 0.37 |
| chi-square windowed | test | 24 | 14.13 (7.64 to 21.94) | 0.645 | 1.1088 | 47.52 | 7.42 |
| chi-square windowed | ood | 1 | 198.97 (172.93 to 222.39) | 8.027 | 5.2491 | 17.31 | 232.17 |
| chi-square windowed | ood | 24 | 689.59 (653.89 to 728.05) | 23.829 | 18.3404 | 32.94 | 809.59 |
| CUSUM | test | 1 | 2.03 (1.46 to 2.72) | 0.397 | 0.0175 | 0.58 | 2.32 |
| CUSUM | test | 24 | 15.99 (13.35 to 19.01) | 1.872 | 0.2667 | 2.35 | 18.73 |
| CUSUM | ood | 1 | 863.42 (834.66 to 889.92) | 30.027 | 22.7053 | 27.59 | 1016.16 |
| CUSUM | ood | 24 | 1168.34 (1131.03 to 1203.17) | 39.595 | 30.8491 | 35.99 | 1375.27 |
| logistic regression | test | 1 | 1.26 (0.87 to 1.69) | 0.414 | 0.0000 | 0.78 | 1.35 |
| logistic regression | test | 24 | 23.64 (18.07 to 31.18) | 4.779 | 0.6386 | 34.68 | 21.42 |
| logistic regression | ood | 1 | 18.26 (14.03 to 23.52) | 4.689 | 0.0281 | 7.24 | 20.27 |
| logistic regression | ood | 24 | 1066.18 (1024.29 to 1100.44) | 36.856 | 28.4737 | 55.24 | 1250.92 |
| network (5 seeds) | test | 1 | 0.53 (0.29 to 0.82) | 0.216 | 0.0000 | 0.49 | 0.54 |
| network (5 seeds) | test | 24 | 22.03 (15.87 to 30.12) | 1.754 | 0.6112 | 9.52 | 24.54 |
| network (5 seeds) | ood | 1 | 13.84 (10.75 to 17.23) | 2.216 | 0.1691 | 3.27 | 15.77 |
| network (5 seeds) | ood | 24 | 241.37 (213.33 to 270.08) | 10.209 | 6.3319 | 20.67 | 281.70 |

### test: paired delay difference on events both found, 1 false alarm per pair-day

| Network minus | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|
| chi-square per step | +1.0 s (+1.0 to +1.0; n 279) | -23.2 s (-26.9 to -19.5; n 225) | -9.0 s (-10.2 to -7.4; n 377) | +0.0 s (+0.0 to +0.0; n 398) | -72.3 s (-112.8 to -49.8; n 142) | +0.0 s (-1.8 to +0.0; n 1421) |
| CUSUM | +1.0 s (+1.0 to +1.0; n 304) | -0.6 s (-3.2 to +1.6; n 218) | -0.2 s (-1.2 to +0.6; n 386) | +0.0 s (+0.0 to +0.0; n 398) | -41.2 s (-55.0 to -33.8; n 227) | +0.0 s (+0.0 to +0.0; n 1533) |
| logistic regression | +1.0 s (+1.0 to +1.4; n 366) | -10.9 s (-13.8 to -8.8; n 218) | -10.8 s (-12.6 to -9.2; n 380) | +0.0 s (+0.0 to +0.0; n 400) | +3.0 s (+2.6 to +4.2; n 334) | +0.0 s (+0.0 to +0.0; n 1698) |

### ood: paired delay difference on events both found, 1 false alarm per pair-day

| Network minus | jump | drift | frozen | frame | noise | all |
|---|---|---|---|---|---|---|
| chi-square per step | +20.6 s (+12.0 to +30.5; n 58) | +69.0 s (+13.0 to +131.4; n 40) | +3.4 s (+2.6 to +4.6; n 382) | +0.0 s (+0.0 to +0.0; n 400) | -33.3 s (-39.6 to -24.8; n 346) | +0.0 s (+0.0 to +0.0; n 1226) |
| CUSUM | +31.5 s (+16.0 to +45.8; n 70) | +56.3 s (+9.8 to +131.6; n 44) | +12.2 s (+9.8 to +14.8; n 381) | +0.0 s (+0.0 to +0.0; n 400) | -5.8 s (-9.4 to -2.2; n 357) | +0.0 s (+0.0 to +0.0; n 1252) |
| logistic regression | +13.6 s (+6.7 to +21.4; n 78) | +4.1 s (+0.7 to +17.0; n 35) | -0.4 s (-1.2 to +0.6; n 380) | +0.0 s (+0.0 to +0.0; n 400) | +7.4 s (+6.8 to +8.2; n 391) | +0.2 s (+0.0 to +0.2; n 1285) |

### runs

| # | change | parameters | window | epochs | val loss | val recall at 1/pair-day | at 1/pair-hour | drift | jump | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 (seed 100) | start: 6 dilated layers, 24 channels, window 127 s | 9529 | 127 s | 8 | 0.2892 | 0.887 | 0.920 | 0.578 | 0.897 | 161 s |
| 2 (seed 100) | train twice as long (16 epochs) | 9529 | 127 s | 16 | 0.2791 | 0.901 | 0.942 | 0.598 | 0.936 | 370 s |
| 3 (seed 100) | wider: 32 channels (against iteration 2) | 16545 | 127 s | 16 | 0.2750 | 0.906 | 0.945 | 0.618 | 0.931 | 524 s |
| 4 (seed 100) | longer window: 255 s (against iteration 2) | 11281 | 255 s | 16 | 0.2629 | 0.899 | 0.950 | 0.613 | 0.897 | 374 s |
| 5 (seed 100) | lower learning rate 0.001 (against iteration 2) | 9529 | 127 s | 16 | 0.2922 | 0.863 | 0.923 | 0.544 | 0.828 | 394 s |
| final(from 2) (seed 0) | the chosen configuration, final seed | 9529 | 127 s | 16 | 0.2798 | 0.898 | 0.939 | 0.603 | 0.931 | 327 s |
| final(from 2) (seed 1) | the chosen configuration, final seed | 9529 | 127 s | 16 | 0.2805 | 0.897 | 0.936 | 0.598 | 0.917 | 542 s |
| final(from 2) (seed 2) | the chosen configuration, final seed | 9529 | 127 s | 16 | 0.2770 | 0.899 | 0.939 | 0.593 | 0.926 | 533 s |
| final(from 2) (seed 3) | the chosen configuration, final seed | 9529 | 127 s | 16 | 0.2744 | 0.900 | 0.945 | 0.608 | 0.926 | 425 s |
| final(from 2) (seed 4) | the chosen configuration, final seed | 9529 | 127 s | 16 | 0.2781 | 0.906 | 0.937 | 0.613 | 0.931 | 311 s |

<!-- END GENERATED TABLES -->
