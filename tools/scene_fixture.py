"""Fixture of the browser scene reader's parity test (site/tests/scene-data.test.mjs, F-36): lunarsim.scene.position
at 30 moments per package (20 random vehicle/time pairs, 10 inside route drives; plus 3 inside Earth-link waits
when the package has them) -> site/tests/fixtures/scene_positions.json.

    python tools/scene_fixture.py [--packages P2-comms-dte] [--seed 36]

Only the named packages are (re)written; the others keep their rows. Rerun after a package under data/scenes changes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from lunarsim import scene as S  # noqa: E402

OUT = os.path.join(ROOT, "site", "tests", "fixtures", "scene_positions.json")
PACKAGES = ("P2", "P2-comms-dte", "P3")
N_RANDOM, N_DRIVES, N_WAITS = 20, 10, 3


def rows_for(pkg_dir: str, seed: int):
    pkg = S.read(pkg_dir)
    idx, seg = pkg["index"], pkg["segments"]
    c = {k: i for i, k in enumerate(idx["segment_columns"])}
    rng = np.random.default_rng(seed)
    vids = sorted({int(v) for v in seg[:, c["veh"]]})
    t_end = float(seg[:, c["t1"]].max())

    def row(v, t, route=None):
        x, y, z, state = S.position(pkg, v, t)
        r = {"veh": v, "t": t, "x": x, "y": y, "z": z, "state": state}
        if route is not None:
            r["route"] = route
        return r

    out = []
    while len(out) < N_RANDOM:
        v, t = int(rng.choice(vids)), float(rng.uniform(0.0, t_end))
        if ((seg[:, c["veh"]] == v) & (seg[:, c["t0"]] <= t) & (seg[:, c["t1"]] > t)).any():
            out.append(row(v, t))
    drives = np.flatnonzero((seg[:, c["route"]] >= 0) & (seg[:, c["t1"]] - seg[:, c["t0"]] > 1e-3)
                            & (np.array(idx["states"])[seg[:, c["state"]].astype(int)] == "driving"))
    for k in rng.choice(drives, size=N_DRIVES, replace=False):
        r = seg[k]
        t = float(r[c["t0"]] + rng.uniform(0.1, 0.9) * (r[c["t1"]] - r[c["t0"]]))
        out.append(row(int(r[c["veh"]]), t, int(r[c["route"]])))
    states = np.array(idx["states"])[seg[:, c["state"]].astype(int)]
    waits = np.flatnonzero((states == "waiting_for_earth") & (seg[:, c["t1"]] - seg[:, c["t0"]] > 1e-3))
    for k in (rng.choice(waits, size=min(N_WAITS, len(waits)), replace=False) if len(waits) else []):
        r = seg[k]
        out.append(row(int(r[c["veh"]]), float(r[c["t0"]] + rng.uniform(0.1, 0.9) * (r[c["t1"]] - r[c["t0"]]))))
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--packages", default=",".join(PACKAGES))
    ap.add_argument("--seed", type=int, default=36)
    a = ap.parse_args(argv)
    doc = json.load(open(OUT, encoding="utf-8")) if os.path.isfile(OUT) else {"packages": {}}
    doc["note"] = ("lunarsim.scene.position at 20 random (vehicle, time) pairs, 10 moments inside route drives and up to "
                   "3 inside Earth-link waits per package; F-36 fixture (FRONTEND), rows rewritten by "
                   "tools/scene_fixture.py when a package changes")
    for k, name in enumerate(a.packages.split(",")):
        doc["packages"][name] = rows_for(os.path.join(ROOT, "data", "scenes", name), a.seed + k)
        print(f"{name}: {len(doc['packages'][name])} rows")
    with open(OUT, "wb") as f:
        f.write((json.dumps(doc, indent=1) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
