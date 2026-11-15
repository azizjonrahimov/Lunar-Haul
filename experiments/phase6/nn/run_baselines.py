"""E56 step 2: fit and tune the classical baselines (training and validation data only).

    python experiments/phase6/nn/run_baselines.py [--max-seconds 520]

Fits the logistic regression on training streams; chooses the windowed chi-square's W and the CUSUM's k and variant (raw or centred) on validation
(the value with the best mean of the macro event recall at 1 false alarm per pair-day and at 1 per pair-hour,
thresholds set on validation fault-free blocks). Writes .cache/nn/baselines.json (the fitted regression, W, k and
the whole tuning table), which lunarsim.nn.evaluate reads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.nn import baselines as B  # noqa: E402
from lunarsim.nn import dataset as D  # noqa: E402
from lunarsim.nn import train as T  # noqa: E402

OUT = os.path.join(T.STATE, "baselines.json")
WINDOWS = (5, 10, 30, 60, 120)
KS = (0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0)
REFS = (0, 120)             # CUSUM on z itself, or on z centred on its mean 120 to 240 s earlier


def main() -> None:
    t0 = time.time()
    os.makedirs(T.STATE, exist_ok=True)
    va = D.load("val")
    wn = va["mn"][:, D.META.index("weight")]

    def val(score_fn):
        ev = T.val_events(score_fn(va["Xf"]), va["mf"], score_fn(va["Xn"]), wn)
        return {"recall_day": ev["day"]["recall_macro"], "recall_hour": ev["hour"]["recall_macro"],
                "by_type_day": ev["day"]["recall_by_type"], "by_type_hour": ev["hour"]["recall_by_type"],
                "median_delay_day_s": ev["day"]["median_delay_s"]}

    doc = {"tuning": {"chi2_window": {}, "cusum": {}}}
    doc["tuning"]["chi2_step"] = val(B.chi2_step)
    print("chi2_step", doc["tuning"]["chi2_step"], flush=True)
    for w in WINDOWS:
        doc["tuning"]["chi2_window"][str(w)] = val(lambda X, w=w: B.chi2_window(X, w))
        print("chi2_window", w, doc["tuning"]["chi2_window"][str(w)], flush=True)
    for ref in REFS:
        for k in KS:
            key = f"{k}|{ref}"
            doc["tuning"]["cusum"][key] = val(lambda X, k=k, ref=ref: B.cusum(X, k, ref))
            print("cusum k", k, "ref", ref, doc["tuning"]["cusum"][key], flush=True)

    def best(table):
        return max(table, key=lambda key: table[key]["recall_day"] + table[key]["recall_hour"])

    doc["chi2_window_W"] = int(best(doc["tuning"]["chi2_window"]))
    kbest = best(doc["tuning"]["cusum"])
    doc["cusum_k"], doc["cusum_ref"] = float(kbest.split("|")[0]), int(kbest.split("|")[1])
    tr = D.load("train")
    lr = B.LogReg().fit(tr["Xf"], tr["yf"], D.score_mask(tr["yf"], tr["mf"]))
    doc["logreg"] = lr.to_doc()
    doc["logreg"]["rows"] = lr.n_rows
    doc["tuning"]["logreg"] = val(lr.score)
    print("logreg", doc["tuning"]["logreg"], flush=True)
    doc["rule"] = "W, k and CUSUM variant: best mean of the validation macro event recall at 1 per pair-day and at 1 per pair-hour"
    doc["wall_s"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print("chosen W", doc["chi2_window_W"], "k", doc["cusum_k"], "ref", doc["cusum_ref"], "->", OUT, doc["wall_s"], "s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    main()
