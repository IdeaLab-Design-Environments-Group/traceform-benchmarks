# traceformroutebench

Benchmark for Traceform, a router for copper tape on folded sheets.
Main project: <https://github.com/IdeaLab-Design-Environments-Group/kiri>

## Run

```sh
python run_all.py
python run_all.py --verify-determinism
python -m pytest
```

Python 3.11, `PyYAML`, `Pillow`. Settings are in `config.yaml`.

The traceform router isn't published, so its rows can't be regenerated here.
`length_only` and `mountain_penalty` can.

## Results

5 meshes, 3 layouts, one side of the sheet, mean of 3 net orderings.
`mountain_penalty` is Alg. 1 from Nakaya et al., *4D Leaf Circuits*, SCF '25.

| router | tensile crossings | copper |
|---|---|---|
| `length_only` | 571.7 | 21,661 mm |
| `mountain_penalty` | 445.0 | 20,820 mm |
| `traceform` | 421.7 | 19,994 mm |

Against `mountain_penalty`, traceform has 5.2% fewer tensile crossings and uses
4.0% less copper. Over 15 instances it wins 6, ties 7 and loses 2. It does
worse on `guitar_lower_bout` (+1.7% crossings, +1.1% copper).

Full numbers are in `results/2026-09-16/`. Mesh sources are in
`data/meshes/PROVENANCE.md`.
