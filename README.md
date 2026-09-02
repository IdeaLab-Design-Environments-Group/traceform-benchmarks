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

Forty-five instances: five meshes, three placements, three routers — a
fold-blind control (`length_only`), the published mountain rule of Nakaya,
Fujino, He & Narumi, *4D Leaf Circuits*, SCF '25, Alg. 1 (`mountain_penalty`),
and `traceform`.

**One conductive face, no vias.** That is the process both systems build for:
copper tape on one side of one sheet, which is also what the published method
assumes — its Algorithm 1 routes a single face-adjacency graph with no second
layer anywhere in it. Two-sided routing was measured during development and is
not reported as a result, because with a second face available any rule that
distinguishes tension from compression drives tensile crossings to zero,
including the published one; that arm measures the second face, not the cost.

A *tensile crossing* is a fold crossing that loads the copper in tension — the
loading that fractures traces under folding cycles. The validator recomputes
every constraint figure from trace geometry alone, never from router state.

Because a sequential router is sensitive to net ordering, every figure below is
the mean of three orderings rather than a single run:

| router | tensile crossings | trace length |
|---|---|---|
| `length_only` | 571.7 | 21,661 mm |
| `mountain_penalty` | 445.0 | 20,820 mm |
| `traceform` | **417.7** | **20,011 mm** |

`traceform` carries **6.1% fewer tensile crossings than the published mountain
rule while using 3.9% less copper**, and 26.9% fewer than the fold-blind
control at 7.6% less copper. It leads on both metrics under each of the three
orderings independently. Per instance, once ordering spread is treated as
noise, it wins 2, ties 13 and **loses 0** of 15.

The gain is unevenly distributed, and the per-model split is the honest picture:

| model | prior art | `traceform` | crossings | copper |
|---|---|---|---|---|
| house | 54.0 / 4,246 | 48.3 / 4,227 | −10.5% | −0.4% |
| church | 60.3 / 4,500 | 49.3 / 3,939 | **−18.2%** | **−12.5%** |
| bat_body | 132.7 / 3,798 | 123.7 / 3,756 | −6.8% | −1.1% |
| guitar_lower_bout | 101.0 / 4,377 | 102.0 / 4,424 | +1.0% | +1.1% |
| guitar_upper_bout | 97.0 / 3,899 | 94.3 / 3,664 | −2.7% | −6.0% |

Four of five models improve on crossings; `guitar_lower_bout` is 1% worse on
both and is the one model where the graded price does not pay.

No trace crosses a cut edge and no terminal strands, in any router. Two runs
with one seed produce identical rows.

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
