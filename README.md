# traceformroutebench

A reproducible benchmark for routing electrical circuits on a folded substrate:

> Carrying signed fold geometry from 3D unfolding into circuit routing reduces
> mechanically risky crease crossings while respecting fabrication boundaries.

Three meshes are unfolded to flat patterns whose crease edges carry a sign
(mountain/valley) and dihedral angle. Three component placements per model — a
control (A), a spanning layout (B) and an adversarial one (C) — are routed by
two routers, and every claimed property is checked by a validator that works
from the trace geometry alone, never from the router's own reporting.

## Running it

```sh
python run_all.py                       # route every instance
python run_all.py --verify-determinism  # run twice, diff the results
python -m pytest                        # the test suite
```

Python 3.11 with `PyYAML` and `Pillow`. On macOS use an interpreter whose
architecture matches your installed Pillow (`/opt/homebrew/bin/python3.11` on
Apple silicon). Tunables live in `config.yaml`; a copy travels with the
results, and two runs with one seed produce identical rows.

**What this repository can and cannot regenerate.** The traceform router is
withheld (below), so `run_all.py` reproduces the `length_only` rows from source
and skips the `traceform` rows with an explicit notice, rather than quietly
substituting a different router. The published traceform results in
`results/` were produced by the harness in this repository, and every figure in
them is checked by the validator in this repository — but you cannot re-derive
them here. Take them on the same footing as any result whose implementation has
not been released yet.

## The routers

- **`length_only`** — shortest-path routing on geometric length alone. The
  fold-blind baseline this benchmark measures against.
- **`traceform`** — the project's router. It reads the signed fold geometry of
  the unfolding and decides where, and how, copper crosses each fold. The
  algorithm is the subject of a separate write-up and is not published here:
  neither this README nor the source describes it, and the module implementing
  it is not in the repository. The benchmark treats it as a black box and
  measures outcomes.

What the two routers *do* share is published and auditable: the same flat
patterns, the same routing graph, the same component keep-outs, the same
fabrication charges for a taped seam and for a change of face, and the same
validator. The comparison isolates what reading the fold geometry is worth.

## Results

**Yes — traceform beats the length-only router, on every instance in the suite.**

Across all 18 instances the length-only router carries **128** tensile
crossings; traceform carries **0**, for **+2.3%** trace length. The zero holds
on each of the nine model/layout pairs individually, not only in aggregate.
The +2.3% is the aggregate price: traceform routes longer on eight of the nine
pairs and shorter on one. Neither router crosses a cut edge or strands a
terminal in any run.

A *tensile crossing* is a fold crossing that loads the copper in tension, which
is the loading that fractures traces under folding cycles. The validator
recomputes every constraint figure from trace geometry alone, independently of
the router that produced it.

Per-instance numbers are in `results/benchmark_results.csv`, one row per
instance, with `results/summary.md` derived from it.

## Output

- `results/benchmark_results.csv` — the aggregate, header first.
- `results/summary.md` — each router against `length_only`, derived.
- `results/config.yaml` — the exact configuration that produced the run.
- `results/runs/<model>_<layout>_<router>.csv` — per-trace detail: nets, panel
  and fold sequences, every crossing with its sign, angle and predicted strain.
- `results/runs/<model>_<layout>_<router>.svg` / `.png` — the flat pattern with
  creases coloured by sign, cut lips, part footprints and routed copper, both
  rendered from a single scene description so they cannot drift apart.

The per-trace CSVs carry every routed segment of both routers, including each
crossing with its sign, angle and predicted strain, so traceform's *output* is
open to inspection in full even though its implementation is not.

## Meshes

`house`, `church` and `bat_body`, copied unmodified from the source project;
origins and SHA-256 checksums in `data/meshes/PROVENANCE.md`. Component
footprints are parsed from vendored KiCad FabLib files — no pad coordinate in
this repository was typed by hand.
