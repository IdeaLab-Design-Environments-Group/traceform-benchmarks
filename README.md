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

| router | tensile crossings | copper |
|---|---|---|
| `length_only` | 128 | 9,960 mm |
| `traceform` | 0 | 10,064 mm |

Full numbers are in `results/`. Mesh sources are in
`data/meshes/PROVENANCE.md`.
