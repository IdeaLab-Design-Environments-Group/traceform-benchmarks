"""Build benchmark.csv -- one row per (model, layout, router, ordering) -- from the three ordering
runs under this directory, and print every table 7.md needs, so that nothing in 7.md is typed by hand.

Bands follow kiri's `strainBand` exactly, using the eps_f in the config the runs were made with:
    band 0 : eps <= eps_f        (this includes every compressive crossing, eps < 0)
    band 1 : eps_f < eps < 2*eps_f
    band 2 : eps >= 2*eps_f
counted over every crossing row in runs/*.csv that carries a predicted strain (creases and seams
alike, since the harness attributes a strain to both and counts both in tensile_crossing_count).

wins_vs_<router> is +1 if this row's tensile_crossings is strictly below that router's on the same
(model, layout, ordering), 0 if equal, -1 if above.  Wins/ties/losses in 7.md are read off this column.
"""
import csv, glob, math, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERINGS = ["widest_first", "narrowest_first", "declaration"]
ROUTERS = ["length_only", "mountain_penalty", "traceform"]

def load_cfg_eps():
    import yaml
    with open(os.path.join(HERE, ORDERINGS[0], "config.yaml")) as fh:
        cfg = yaml.safe_load(fh)
    return cfg, float(cfg["sheet_spec"]["fatigue_strain"])

def band_of(eps, eps_f):
    if eps <= eps_f: return 0
    if eps < 2 * eps_f: return 1
    return 2

def main():
    cfg, eps_f = load_cfg_eps()
    rows = []
    for o in ORDERINGS:
        with open(os.path.join(HERE, o, "benchmark_results.csv")) as fh:
            for r in csv.DictReader(fh):
                stem = f"{r['model_id']}_{r['layout_id']}_{r['routing_method']}"
                bands = [0, 0, 0]
                with open(os.path.join(HERE, o, "runs", stem + ".csv")) as rh:
                    for c in csv.DictReader(rh):
                        s = c["crossing_predicted_strain"]
                        if s == "": continue
                        bands[band_of(float(s), eps_f)] += 1
                rows.append({
                    "model": r["model_id"], "layout": r["layout_id"],
                    "router": r["routing_method"], "ordering": o,
                    "tensile_crossings": int(r["tensile_crossing_count"]),
                    "copper_mm": float(r["total_trace_length_mm"]),
                    "band0": bands[0], "band1": bands[1], "band2": bands[2],
                })
    by = {(r["model"], r["layout"], r["router"], r["ordering"]): r for r in rows}
    for r in rows:
        for other in ("length_only", "mountain_penalty"):
            o = by[(r["model"], r["layout"], other, r["ordering"])]
            d = r["tensile_crossings"] - o["tensile_crossings"]
            r[f"wins_vs_{other}"] = 1 if d < 0 else (0 if d == 0 else -1)

    cols = ["model", "layout", "router", "ordering", "tensile_crossings", "copper_mm",
            "band0", "band1", "band2", "wins_vs_length_only", "wins_vs_mountain_penalty"]
    rows.sort(key=lambda r: (r["model"], r["layout"], ROUTERS.index(r["router"]), ORDERINGS.index(r["ordering"])))
    with open(os.path.join(HERE, "benchmark.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({k: r[k] for k in cols})
    print(f"wrote benchmark.csv: {len(rows)} rows; eps_f = {eps_f}\n")

    # ---- totals per router, per ordering and averaged
    print("## totals per router")
    print("| router | ordering | tensile crossings | copper mm |")
    print("|---|---|---|---|")
    tot = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))
    for r in rows:
        t = tot[r["router"]][r["ordering"]]; t[0] += r["tensile_crossings"]; t[1] += r["copper_mm"]
    for rt in ROUTERS:
        xs = [tot[rt][o][0] for o in ORDERINGS]; ls = [tot[rt][o][1] for o in ORDERINGS]
        print(f"| **{rt}** | mean of 3 | **{statistics.mean(xs):.1f}** | **{statistics.mean(ls):,.0f}** |")
        for o in ORDERINGS:
            print(f"| {rt} | {o} | {tot[rt][o][0]} | {tot[rt][o][1]:,.0f} |")
    print()

    # ---- ordering sensitivity
    print("## ordering sensitivity (max-min of total crossings, % of median)")
    for rt in ROUTERS:
        xs = [tot[rt][o][0] for o in ORDERINGS]
        med = statistics.median(xs)
        print(f"- {rt}: {min(xs)}-{max(xs)}, median {med:.0f}, spread {100*(max(xs)-min(xs))/med:.1f}%")
    print()

    # ---- per-instance table (ordering-averaged)
    print("## per instance (mean over orderings)")
    print("| model | layout | " + " | ".join(f"{rt} cross / mm" for rt in ROUTERS) + " |")
    print("|---|---|" + "---|" * len(ROUTERS))
    inst = defaultdict(lambda: defaultdict(list))
    for r in rows:
        inst[(r["model"], r["layout"])][r["router"]].append((r["tensile_crossings"], r["copper_mm"]))
    for (m, l), d in sorted(inst.items()):
        cells = []
        for rt in ROUTERS:
            c = statistics.mean(x for x, _ in d[rt]); mm = statistics.mean(y for _, y in d[rt])
            cells.append(f"{c:.1f} / {mm:,.0f}")
        print(f"| {m} | {l} | " + " | ".join(cells) + " |")
    print()

    # ---- per-instance wins for traceform, marginalised over orderings (mean crossings compared)
    print("## traceform per instance, marginalised over orderings")
    print("| model | layout | vs length_only | vs mountain_penalty |")
    print("|---|---|---|---|")
    tally = {"length_only": [0, 0, 0], "mountain_penalty": [0, 0, 0]}
    for (m, l), d in sorted(inst.items()):
        tf = statistics.mean(x for x, _ in d["traceform"])
        cells = []
        for other in ("length_only", "mountain_penalty"):
            ot = statistics.mean(x for x, _ in d[other])
            if tf < ot: word, i = "win", 0
            elif tf == ot: word, i = "tie", 1
            else: word, i = "loss", 2
            tally[other][i] += 1
            cells.append(f"{word} ({tf:.1f} vs {ot:.1f})")
        print(f"| {m} | {l} | " + " | ".join(cells) + " |")
    for other, (w, t, lo) in tally.items():
        print(f"- traceform vs {other}: **{w} wins, {t} ties, {lo} losses** of {w+t+lo}")
    print("- per-(instance, ordering) rows, from wins_vs_* columns:")
    for other in ("length_only", "mountain_penalty"):
        col = f"wins_vs_{other}"
        tf = [r[col] for r in rows if r["router"] == "traceform"]
        print(f"  - vs {other}: {tf.count(1)} wins, {tf.count(0)} ties, {tf.count(-1)} losses of {len(tf)}")
    print()

    # ---- band distribution per router
    print("## band distribution per router (summed over instances and orderings)")
    print("| router | band 0 | band 1 | band 2 | total |")
    print("|---|---|---|---|---|")
    for rt in ROUTERS:
        b = [sum(r[f"band{i}"] for r in rows if r["router"] == rt) for i in range(3)]
        n = sum(b)
        print(f"| {rt} | " + " | ".join(f"{x} ({100*x/n:.1f}%)" for x in b) + f" | {n} |")
    print()

if __name__ == "__main__":
    sys.exit(main())
