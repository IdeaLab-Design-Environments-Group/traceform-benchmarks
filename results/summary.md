# Summary

Each method against `length_only` on the same model and layout.
Derived from `benchmark_results.csv`; the CSV itself stays raw.

| model | layout | method | tensile | sum tensile strain | max tensile strain | compression | length | stranded |
|---|---|---|---|---|---|---|---|---|
| bat_body | A | length_only | 1 -> 1 (+0%) | +0% | +0% | 1 -> 1 | +0% | 0 |
| bat_body | A | traceform | 1 -> 0 (-100%) | -100% | -100% | 1 -> 2 | +3% | 0 |
| bat_body | B | length_only | 26 -> 26 (+0%) | +0% | +0% | 12 -> 12 | +0% | 0 |
| bat_body | B | traceform | 26 -> 0 (-100%) | -100% | -100% | 12 -> 30 | +0% | 0 |
| bat_body | C | length_only | 39 -> 39 (+0%) | +0% | +0% | 33 -> 33 | +0% | 0 |
| bat_body | C | traceform | 39 -> 0 (-100%) | -100% | -100% | 33 -> 65 | +3% | 0 |
| church | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | traceform | 2 -> 0 (-100%) | -100% | -100% | 0 -> 2 | +5% | 0 |
| church | B | length_only | 8 -> 8 (+0%) | +0% | +0% | 2 -> 2 | +0% | 0 |
| church | B | traceform | 8 -> 0 (-100%) | -100% | -100% | 2 -> 10 | +1% | 0 |
| church | C | length_only | 20 -> 20 (+0%) | +0% | +0% | 18 -> 18 | +0% | 0 |
| church | C | traceform | 20 -> 0 (-100%) | -100% | -100% | 18 -> 30 | +3% | 0 |
| house | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | traceform | 2 -> 0 (-100%) | -100% | -100% | 0 -> 2 | +1% | 0 |
| house | B | length_only | 8 -> 8 (+0%) | +0% | +0% | 5 -> 5 | +0% | 0 |
| house | B | traceform | 8 -> 0 (-100%) | -100% | -100% | 5 -> 13 | -0% | 0 |
| house | C | length_only | 22 -> 22 (+0%) | +0% | +0% | 13 -> 13 | +0% | 0 |
| house | C | traceform | 22 -> 0 (-100%) | -100% | -100% | 13 -> 27 | +4% | 0 |
