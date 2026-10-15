"""Command-line interface.

    lunarsim run      --scenario P2-default --mechanism marketplace --seeds 30 --out runs.csv
    lunarsim compare  --scenario P2-default --seeds 30 --out compare.csv
    lunarsim trace    --scenario P2-4-vehicles --mechanism marketplace --seed 3 --out trace.json
    lunarsim verify
    lunarsim scenarios list | export --dir data/scenarios
    lunarsim precise  --scenario P2-default --mechanism marketplace --target 0.01 --confidence 0.99
    lunarsim serve    --port 8765 [--static web/dist]
    lunarsim validate data/scenarios/*.json data/sample_traces/*.json
    lunarsim terrain  build --site Site01 --out data/terrain/connecting_ridge | place | info
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

log = logging.getLogger("lunarsim")


def _scenario_ex(arg: str):
    """(Scenario, marketplace kwargs from a compact-form file, else {})."""
    from .config import library, load_scenario_ex
    if os.path.exists(arg):
        try:
            return load_scenario_ex(arg)
        except ValueError as e:
            raise SystemExit(f"{arg}: {e}")
    lib = library()
    if arg in lib:
        return lib[arg], {}
    raise SystemExit(f"unknown scenario '{arg}'. Known: {', '.join(sorted(lib))} or a path to a JSON file")


def _scenario(arg: str):
    return _scenario_ex(arg)[0]


def _with_file_opts(name: str, kw: dict, file_kw: dict) -> dict:
    """Scenario-file marketplace flags apply to the marketplace family only (as on the web page)."""
    return dict(kw, **file_kw) if name.startswith("marketplace") else kw


def _mechanism(name: str):
    from . import dispatch
    if name not in dispatch.MECHANISMS:
        raise SystemExit(f"unknown mechanism '{name}'. Known: {', '.join(dispatch.MECHANISMS)}")
    fn = dispatch.MECHANISMS[name]
    kw = {"batch_h": 1.0} if name == "central_assign" else {}
    return fn, kw


def cmd_run(a):
    import pandas as pd
    from .engine import run
    sc, file_kw = _scenario_ex(a.scenario)
    fn, kw = _mechanism(a.mechanism)
    kw = _with_file_opts(a.mechanism, kw, file_kw)
    t0 = time.time()
    rows = [run(sc, fn, seed=s, **kw) for s in range(a.seeds)]
    df = pd.DataFrame(rows)
    df.insert(0, "mechanism", a.mechanism)
    df.insert(0, "scenario", sc.name)
    if a.out:
        df.to_csv(a.out, index=False)
        log.info("wrote %s", a.out)
    cols = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "delivered_share", "jobs", "night_strandings", "cost_per_kg_usd"]
    print(f"{a.mechanism} on {sc.name}: {a.seeds} seeds in {time.time()-t0:.1f}s")
    for c in cols:
        print(f"  {c:22s} mean {df[c].mean():10.3f}   95% CI ±{1.96*df[c].std(ddof=1)/max(1,len(df))**0.5:.3f}")


def cmd_compare(a):
    import pandas as pd
    from .engine import run
    from . import dispatch
    sc, file_kw = _scenario_ex(a.scenario)
    rows = []
    for name in ("inhouse", "pooled_greedy", "central_assign", "marketplace"):
        fn, kw = _mechanism(name)
        kw = _with_file_opts(name, kw, file_kw)
        for s in range(a.seeds):
            r = run(sc, fn, seed=s, **kw)
            r["mechanism"] = name
            rows.append(r)
    df = pd.DataFrame(rows)
    if a.out:
        df.to_csv(a.out, index=False)
    g = df.groupby("mechanism")[["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "stranded_kg", "jobs", "night_strandings", "operator_hours"]].mean()
    print(g.round(3).to_string())


def cmd_trace(a):
    from .engine import Simulation
    sc, file_kw = _scenario_ex(a.scenario)
    fn, kw = _mechanism(a.mechanism)
    kw = dict(_with_file_opts(a.mechanism, kw, file_kw), trace=True)
    sim = Simulation(sc, fn, seed=a.seed, mech_kwargs=kw)
    sim.run()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(sim.trace_export(mechanism=a.mechanism), f)
    print(f"wrote {a.out}: {len(sim.trace)} jobs, {len(sim.all_cargo)} items")


def cmd_verify(a):
    from . import vv
    checks = vv.run_all_checks()
    ok = 0
    for c in checks:
        flag = "PASS" if c["passed"] else "FAIL"
        ok += c["passed"]
        print(f"{flag}  {c['name']:62s} ref={c['reference']:.5g} sim={c['simulated']:.5g} err={100*c['rel_error']:.3f}%")
    print(f"{ok} of {len(checks)} checks passed")
    sys.exit(0 if ok == len(checks) else 1)


def cmd_scenarios(a):
    from .config import library, save_scenario
    lib = library()
    if a.action == "list":
        for k, sc in lib.items():
            print(f"{k:18s} fleet={len(sc.fleet):d}  landings/yr={sc.landings_per_year}  bulk={sum(b.tonnes_per_year for b in sc.bulk_flows):.0f} t/yr")
    else:
        os.makedirs(a.dir, exist_ok=True)
        for k, sc in lib.items():
            save_scenario(sc.with_(name=k), os.path.join(a.dir, f"{k}.json"))
        print(f"exported {len(lib)} scenarios to {a.dir}")


def cmd_precise(a):
    from .precision import run_until_precise
    sc, file_kw = _scenario_ex(a.scenario)
    fn, kw = _mechanism(a.mechanism)
    kw = _with_file_opts(a.mechanism, kw, file_kw)
    res, df = run_until_precise(sc, fn, {a.metric: a.target}, confidence=a.confidence, block=a.block,
                                n_min=30, n_max=a.max, mech_kwargs=kw, verbose=True)
    r = res[a.metric]
    print(f"{a.metric}: mean {r.mean:.4f}, {100*a.confidence:.0f}% half-width {r.half_width:.4f} ({100*r.rel_half_width:.2f}%) after {r.n} replications; target {'reached' if r.reached else 'not reached'}")
    if a.out:
        df.to_csv(a.out, index=False)


def cmd_serve(a):
    from .server import serve
    try:
        serve(a.port, a.static)
    except ValueError as e:
        raise SystemExit(str(e))


def cmd_validate(a):
    from .formats import validate_file
    failed = 0
    for path in a.files:
        kind, legacy, errs = validate_file(path)
        if errs:
            failed += 1
            print(f"FAIL {path}" + ("" if kind == "?" else f"  {kind} v1"))
            for e in errs:
                print(f"     {e}")
        else:
            print(f"OK   {path}  {kind} v1" + (" legacy" if legacy else ""))
    if len(a.files) > 1:
        print(f"{len(a.files) - failed} of {len(a.files)} files valid")
    sys.exit(1 if failed else 0)


def cmd_terrain(a):
    from . import terrain as T
    if a.action == "build":
        if not a.out:
            raise SystemExit("terrain build needs --out, e.g. --out data/terrain/connecting_ridge")
        src = a.src or T.download(a.site, a.cache, a.url)
        t0 = time.time()
        meta = T.build_pack(src, a.out, a.site, name=a.name, sun_az_deg=a.sun_az, z_scale=a.z_scale, url=a.url)
        st = meta["stats"]
        print(f"wrote {a.out} in {time.time() - t0:.1f}s: {meta['layers']['height_5m']['shape']} px at "
              f"{meta['layers']['height_5m']['px_m']} m, size {meta['size_m'][0] / 1000:g} x {meta['size_m'][1] / 1000:g} km, "
              f"z {st['z_min']:.1f}..{st['z_max']:.1f} m, slope p50/p90 {st['slope_p50']:.1f}/{st['slope_p90']:.1f} deg")
        for L in meta["layers"].values():
            print(f"  {L['file']:18s} {L['shape'][1]}x{L['shape'][0]}  {os.path.getsize(os.path.join(a.out, L['file'])) / 1e6:.2f} MB")
        return
    t = T.Terrain(a.site, a.root)
    if a.action == "info":
        m = t.meta
        print(f"{m['site_id']}: {m['name']} ({m['source']['product']})")
        print(f"  source   {m['source']['url']}")
        print(f"  cite     {m['source']['citation']}  credit {m['source']['credit']}")
        print(f"  crs      {m['crs']}; origin (map m) {m['origin_xy_m']}; size {m['size_m']} m")
        print(f"  z        offset {m['z_encoding']['offset_m']} m, {m['z_encoding']['scale_m_per_unit']} m/unit")
        for k, v in m["stats"].items():
            print(f"  {k:12s} {v}")
        for k, L in m["layers"].items():
            print(f"  layer    {k:14s} {L['file']:18s} {L['shape'][1]}x{L['shape'][0]} @ {L['px_m']} m")
        s = t.sites()
        print(f"  sites    {'sites.json: ' + ', '.join(x['id'] for x in s.get('sites', [])) if s else 'no sites.json yet'}")
        print(f"  generated {m['generated']}")
        return
    # place
    try:
        bx, by = (float(v) for v in a.base.split(","))
    except ValueError:
        raise SystemExit("--base must be X,Y in local metres, e.g. --base 8000,8000")
    if not t.contains(bx, by):
        raise SystemExit(f"--base {bx},{by} is outside the tile (0..{t.size_m[0]:g}, 0..{t.size_m[1]:g})")
    cands = T.place_pads(t, (bx, by), a.standoff, max_slope_deg=a.max_slope, radius_m=a.radius, n=a.n,
                         slope_stat=a.slope_stat)
    if a.json:
        print(json.dumps({"site": t.site_id, "base_xy_m": [bx, by], "standoff_km": a.standoff,
                          "criteria": {"max_slope_deg": a.max_slope, "radius_m": a.radius, "slope_stat": a.slope_stat,
                                       "illum": "mean hillshade, sun az 0/90/180/270, el 1.5 deg"},
                          "candidates": cands}, indent=2))
        return
    print(f"pad candidates on {t.site_id} at {a.standoff:g} km from BASE ({bx:g}, {by:g}); {a.slope_stat} slope <= "
          f"{a.max_slope:g} deg over {a.radius:g} m; ranked by illumination proxy (mean hillshade, sun az 0/90/180/270, el 1.5 deg)")
    if not cands:
        print("  none found; try another --standoff or --max-slope")
    print(f"  {'#':>2} {'x_m':>8} {'y_m':>8} {'km':>6} {'brg':>6} {'plane':>6} {'max':>6} {'illum':>6} {'z_m':>7}  LOS to BASE")
    for i, c in enumerate(cands, 1):
        print(f"  {i:2d} {c['xy_m'][0]:8.0f} {c['xy_m'][1]:8.0f} {c['dist_km']:6.2f} {c['bearing_deg']:6.1f} "
              f"{c['slope_plane_deg']:6.2f} {c['slope_max_deg']:6.2f} {c['illum']:6.3f} {c['z_m']:7.1f}  {c['los_to_base']} ({c['los_clearance_m']:+.0f} m)")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="lunarsim", description="LunarSim: discrete-event testbed for lunar surface logistics")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one mechanism on one scenario for N seeds")
    r.add_argument("--scenario", default="P2-default")
    r.add_argument("--mechanism", default="marketplace")
    r.add_argument("--seeds", type=int, default=30)
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_run)
    c = sub.add_parser("compare", help="run all four mechanisms on one scenario")
    c.add_argument("--scenario", default="P2-default")
    c.add_argument("--seeds", type=int, default=30)
    c.add_argument("--out", default=None)
    c.set_defaults(func=cmd_compare)
    t = sub.add_parser("trace", help="export one replayable year as JSON")
    t.add_argument("--scenario", default="P2-4-vehicles")
    t.add_argument("--mechanism", default="marketplace")
    t.add_argument("--seed", type=int, default=3)
    t.add_argument("--out", default="trace.json")
    t.set_defaults(func=cmd_trace)
    v = sub.add_parser("verify", help="run the verification checks")
    v.set_defaults(func=cmd_verify)
    s = sub.add_parser("scenarios", help="list or export the named scenarios")
    s.add_argument("action", choices=["list", "export"])
    s.add_argument("--dir", default="data/scenarios")
    s.set_defaults(func=cmd_scenarios)
    q = sub.add_parser("precise", help="replicate until a confidence-interval target is met")
    q.add_argument("--scenario", default="P2-default")
    q.add_argument("--mechanism", default="marketplace")
    q.add_argument("--metric", default="delay_prio1_mean_h")
    q.add_argument("--target", type=float, default=0.01, help="relative half-width target")
    q.add_argument("--confidence", type=float, default=0.99)
    q.add_argument("--block", type=int, default=100)
    q.add_argument("--max", type=int, default=4000)
    q.add_argument("--out", default=None)
    q.set_defaults(func=cmd_precise)
    w = sub.add_parser("serve", help="local JSON API on 127.0.0.1 (see lunarsim/server.py)")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--static", default=None, metavar="DIR", help="also serve this folder at / (e.g. web/dist)")
    w.set_defaults(func=cmd_serve)
    x = sub.add_parser("validate", help="check lunarsim-trace / lunarsim-scenario JSON files")
    x.add_argument("files", nargs="+", metavar="FILE")
    x.set_defaults(func=cmd_validate)
    tr = sub.add_parser("terrain", help="build, inspect and place pads on lunarsim-terrain packs (needs [terrain])")
    tr.add_argument("action", choices=["build", "place", "info"])
    tr.add_argument("--site", required=True, help="build: PGDA site (Site01, Site04, ...); place/info: pack id or folder")
    tr.add_argument("--out", help="build: output folder, e.g. data/terrain/connecting_ridge")
    tr.add_argument("--src", default=None, help="build: local GeoTIFF instead of downloading")
    tr.add_argument("--url", default=None, help="build: override the PGDA URL")
    tr.add_argument("--cache", default=os.path.join("data", "terrain", "_cache"))
    tr.add_argument("--name", default=None)
    tr.add_argument("--sun-az", type=float, default=0.0, help="hillshade sun azimuth (deg, grid: 0 = +y, 90 = +x)")
    tr.add_argument("--z-scale", type=float, default=0.5, help="height PNG metres per unit")
    tr.add_argument("--root", default=os.path.join("data", "terrain"))
    tr.add_argument("--standoff", type=float, default=2.0, help="place: km from BASE")
    tr.add_argument("--base", default=None, help="place: BASE position X,Y in local metres")
    tr.add_argument("--max-slope", type=float, default=5.0)
    tr.add_argument("--radius", type=float, default=100.0)
    tr.add_argument("--slope-stat", choices=["plane", "max"], default="plane",
                    help="place: tilt of the mean surface over the disk (default) or steepest 20 m cell")
    tr.add_argument("--n", type=int, default=10)
    tr.add_argument("--json", action="store_true")
    tr.set_defaults(func=cmd_terrain)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
