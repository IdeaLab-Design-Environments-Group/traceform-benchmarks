# traceformroutebench

Benchmark for routing copper tape on folded sheets.

## Run

```sh
python run_all.py
python run_all.py --verify-determinism
python -m pytest
```

Python 3.11, `PyYAML`, `Pillow`. Settings are in `config.yaml`.

The traceform router isn't published, so its rows can't be regenerated here.
`length_only` can.

## Results

3 meshes, 3 layouts, 18 runs.

Traceform has 0 tensile crossings against 128 for `length_only`, with 1.0% more
copper. The 0 holds on all 9 model/layout pairs. It routes longer on 7 and
shorter on 2.

Full numbers are in `results/`. Mesh sources are in
`data/meshes/PROVENANCE.md`.
