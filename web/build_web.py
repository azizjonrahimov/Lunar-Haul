"""Build the deployable site in web/dist/: copies index.html, app.js, sim.js, formats.js, worker.js and writes ref.js with
Python reference results for the cross-implementation check (Phase-2 default fleet, from results/E1_phases.csv)."""
import json, os, shutil
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(HERE, "dist")


def ci95(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(1.96 * x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else 0.0


def reference():
    path = os.path.join(ROOT, "results", "E1_phases.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df = df[df.phase == "P2"]
    ref = {}
    for mech in ("inhouse", "pooled_greedy", "central_assign", "marketplace"):
        sub = df[df.mechanism == mech]
        ref[mech] = {key: {"mean": float(np.nanmean(sub[key])), "ci": ci95(sub[key]), "n": int(len(sub))}
                     for key in ("delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "jobs", "night_strandings", "delivered_share")}
    return ref


def main():
    os.makedirs(DIST, exist_ok=True)
    for f in ("index.html", "app.js", "sim.js", "formats.js", "worker.js"):
        shutil.copy(os.path.join(HERE, f), os.path.join(DIST, f))
    ref = reference()
    open(os.path.join(DIST, "ref.js"), "w", encoding="utf-8").write("window.PY_REF = " + json.dumps(ref) + ";\n")
    # also keep a copy next to the sources so the folder can be served directly during development
    shutil.copy(os.path.join(DIST, "ref.js"), os.path.join(HERE, "ref.js"))
    open(os.path.join(DIST, ".nojekyll"), "w").close()
    print("built", DIST, "with reference" if ref else "without reference")


if __name__ == "__main__":
    main()
