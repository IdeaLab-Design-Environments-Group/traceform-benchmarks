#!/usr/bin/env python3
"""Regenerate every result from scratch.

    python run_all.py                      full run
    python run_all.py --verify-determinism run twice, diff the CSVs
    python run_all.py --models house       restrict the sweep

Nothing here is ever hand-edited: results/ is output, config.yaml is input, and
a copy of the config travels with the results so a stored run carries the
parameters that produced it.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import yaml  # noqa: E402

from fold.load import load_mesh  # noqa: E402
from fold.planarise import planarise  # noqa: E402
from fold.strain import SheetSpec  # noqa: E402
from fold.unfold import unfold  # noqa: E402
from footprints import load_library  # noqa: E402
from layouts import build_layout  # noqa: E402
from metrics import COLUMNS, TRACE_COLUMNS, build_row, build_trace_rows  # noqa: E402
from render import build_scene, write_png, write_svg  # noqa: E402
from routing.graph import build_graph  # noqa: E402
from routing.router import route  # noqa: E402
from validate import validate  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, "results")
RUNS = os.path.join(RESULTS, "runs")


def load_config(path: str) -> Dict:
    text = open(path).read()
    cfg = yaml.safe_load(text)
    cfg["_hash"] = hashlib.sha256(text.encode()).hexdigest()[:16]
    cfg["unfold"].setdefault("candidate_directions", 96)
    return cfg


def run(cfg: Dict, out_dir: str, only_models: List[str] = None,
        render: bool = True, quiet: bool = False) -> List[Dict]:
    library = load_library(os.path.join(ROOT, "data", "footprints"))
    spec = SheetSpec.from_config(cfg)
    rows: List[Dict] = []
    unavailable: Dict[str, str] = {}

    for model in cfg["models"]:
        model_id = model["id"]
        if only_models and model_id not in only_models:
            continue
        mesh = load_mesh(os.path.join(ROOT, model["mesh"]),
                         cfg["mesh"]["weld_decimals"])
        panels = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
        flat = unfold(panels, model_id, cfg)
        graph = build_graph(flat, spec, cfg)
        if not quiet:
            print(f"{model_id}: {len(flat.polygons)} panels, "
                  f"{len(flat.creases)} creases, {len(flat.seams)} seams, "
                  f"{flat.cycle_count} cycles, "
                  f"{graph.node_count} nodes / {graph.edge_count} edges")

        for layout_id in cfg["layouts"]:
            layout = build_layout(flat, layout_id, library, cfg)
            for method in cfg["methods"]:
                if method in unavailable:
                    continue
                runtimes: List[float] = []
                result = None
                try:
                    for _ in range(max(1, cfg["timing"]["repeats"])):
                        result = route(graph, layout, method, cfg)
                        runtimes.append(result.runtime_ms)
                except (ValueError, ImportError) as exc:
                    # A method whose implementation is not in this checkout.
                    # Skip its rows and say so, rather than aborting the run or
                    # silently routing it with something else.
                    unavailable[method] = str(exc)
                    if not quiet:
                        print(f"   -- skipping {method}: {exc}")
                    continue
                report = validate(flat, layout, result, cfg)
                row = build_row(model_id, layout_id, method, flat, layout,
                                graph, result, report, runtimes, cfg,
                                mesh.sha256, cfg["_hash"])
                rows.append(row)

                stem = f"{model_id}_{layout_id}_{method}"
                with open(os.path.join(out_dir, "runs", stem + ".csv"), "w",
                          newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=TRACE_COLUMNS)
                    w.writeheader()
                    for trow in build_trace_rows(result, report):
                        w.writerow(trow)
                if render:
                    scene = build_scene(flat, layout, result, cfg)
                    write_svg(os.path.join(out_dir, "runs", stem + ".svg"),
                              scene, flat, stem, cfg)
                    write_png(os.path.join(out_dir, "runs", stem + ".png"),
                              scene, flat, cfg)
                if not quiet:
                    print(f"   {layout_id} {method:17s} "
                          f"tensile={row['tensile_crossing_count']:3d} "
                          f"sumEps={row['sum_predicted_tensile_strain']:8.4f} "
                          f"len={row['total_trace_length_mm']:8.1f}mm "
                          f"stranded={row['stranded_terminals']} "
                          f"cut={row['cut_violation_count']} "
                          f"clear={row['clearance_violation_count']}")
    if unavailable and not quiet:
        for method, why in unavailable.items():
            print(f"\nnot run: {method} -- {why}")
    return rows


def write_csv(path: str, rows: List[Dict]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_summary(path: str, rows: List[Dict]) -> None:
    """Ratios against length_only, kept out of the raw CSV on purpose."""
    index = {(r["model_id"], r["layout_id"], r["routing_method"]): r for r in rows}
    lines = ["# Summary", "",
             "Each method against `length_only` on the same model and layout.",
             "Derived from `benchmark_results.csv`; the CSV itself stays raw.",
             ""]
    header = ("| model | layout | method | tensile | sum tensile strain | "
              "max tensile strain | compression | length | stranded |")
    lines += [header, "|---|---|---|---|---|---|---|---|---|"]
    for (model, layout, method), row in sorted(index.items()):
        base = index.get((model, layout, "length_only"))
        if base is None:
            continue

        def rel(key, fmt="{:+.0f}%"):
            b, v = base[key], row[key]
            if b in (0, 0.0):
                return "n/a" if v in (0, 0.0) else f"0 -> {v}"
            return fmt.format(100.0 * (v / b - 1.0))

        lines.append(
            f"| {model} | {layout} | {method} | "
            f"{base['tensile_crossing_count']} -> {row['tensile_crossing_count']} "
            f"({rel('tensile_crossing_count')}) | "
            f"{rel('sum_predicted_tensile_strain')} | "
            f"{rel('maximum_predicted_tensile_strain')} | "
            f"{base['compression_crossing_count']} -> "
            f"{row['compression_crossing_count']} | "
            f"{rel('total_trace_length_mm')} | "
            f"{row['stranded_terminals']} |")
    open(path, "w").write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--verify-determinism", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--out", default=RESULTS,
                    help="output directory (default: results/)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = os.path.abspath(args.out)
    runs_dir = os.path.join(out_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    for stale in os.listdir(runs_dir):
        os.remove(os.path.join(runs_dir, stale))

    t0 = time.time()
    rows = run(cfg, out_dir, args.models, render=not args.no_render)
    write_csv(os.path.join(out_dir, "benchmark_results.csv"), rows)
    write_summary(os.path.join(out_dir, "summary.md"), rows)
    shutil.copyfile(args.config, os.path.join(out_dir, "config.yaml"))
    print(f"\n{len(rows)} instances in {time.time() - t0:.1f}s "
          f"-> {os.path.relpath(out_dir)}/benchmark_results.csv")

    if args.verify_determinism:
        again = run(cfg, out_dir, args.models, render=False, quiet=True)
        # Wall-clock columns are excluded: they measure the machine, not the
        # benchmark, and can never repeat.  Every other column -- including
        # nodes_expanded, which is the search's own work -- must match exactly.
        timing = {"runtime_ms", "runtime_ms_stdev"}
        keys = [c for c in COLUMNS if c not in timing]
        differing = sorted({k for a, b in zip(rows, again) for k in keys
                            if a[k] != b[k]})
        if not differing and len(rows) == len(again):
            print(f"determinism: OK, {len(rows)} rows identical across two runs "
                  f"(wall-clock columns excluded)")
        else:
            print(f"determinism: FAILED, columns differ: {differing}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
