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
`length_only` and `mountain_penalty` can.

## Results

5 meshes, 3 layouts, one side of the sheet, mean of 3 net orderings.
`mountain_penalty` is Alg. 1 from Nakaya et al., *4D Leaf Circuits*, SCF '25.

| router | tensile crossings | copper |
|---|---|---|
| `length_only` | 571.7 | 21,661 mm |
| `mountain_penalty` | 445.0 | 20,820 mm |
| `traceform` | 417.7 | 20,011 mm |

Against `mountain_penalty`, traceform has 6.1% fewer tensile crossings and uses
3.9% less copper. Over 15 instances it wins 2, ties 13 and loses 0. It does
worse on `guitar_lower_bout` (+1.0% crossings, +1.1% copper).

Full numbers are in `results/`. Mesh sources are in
`data/meshes/PROVENANCE.md`.
