# Summary

Each method against `length_only` on the same model and layout.
Derived from `benchmark_results.csv`; the CSV itself stays raw.

| model | layout | method | tensile | sum tensile strain | max tensile strain | compression | length | stranded |
|---|---|---|---|---|---|---|---|---|
| bat_body | A | length_only | 16 -> 16 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | A | mountain_penalty | 16 -> 15 (-6%) | -14% | +0% | 0 -> 0 | -3% | 0 |
| bat_body | A | traceform | 16 -> 11 (-31%) | -40% | +0% | 0 -> 0 | -17% | 0 |
| bat_body | B | length_only | 45 -> 45 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | B | mountain_penalty | 45 -> 32 (-29%) | -13% | +10% | 0 -> 0 | +1% | 0 |
| bat_body | B | traceform | 45 -> 31 (-31%) | -14% | +10% | 0 -> 0 | +7% | 0 |
| bat_body | C | length_only | 132 -> 132 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | C | mountain_penalty | 132 -> 80 (-39%) | -32% | +0% | 0 -> 0 | -17% | 0 |
| bat_body | C | traceform | 132 -> 82 (-38%) | -35% | +0% | 0 -> 0 | -15% | 0 |
| church | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | -1% | 0 |
| church | B | length_only | 10 -> 10 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | B | mountain_penalty | 10 -> 10 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | B | traceform | 10 -> 10 (+0%) | -8% | +0% | 0 -> 0 | -3% | 0 |
| church | C | length_only | 55 -> 55 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | C | mountain_penalty | 55 -> 47 (-15%) | -11% | +0% | 0 -> 0 | +14% | 0 |
| church | C | traceform | 55 -> 37 (-33%) | -37% | +0% | 0 -> 0 | -22% | 0 |
| guitar_lower_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | length_only | 20 -> 20 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | mountain_penalty | 20 -> 19 (-5%) | -2% | +0% | 0 -> 0 | -0% | 0 |
| guitar_lower_bout | B | traceform | 20 -> 19 (-5%) | -2% | +0% | 0 -> 0 | -0% | 0 |
| guitar_lower_bout | C | length_only | 92 -> 92 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | C | mountain_penalty | 92 -> 75 (-18%) | -16% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | C | traceform | 92 -> 76 (-17%) | -17% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +2% | 0 |
| guitar_upper_bout | B | length_only | 23 -> 23 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | B | mountain_penalty | 23 -> 19 (-17%) | -9% | +3% | 0 -> 0 | +2% | 0 |
| guitar_upper_bout | B | traceform | 23 -> 19 (-17%) | -9% | +3% | 0 -> 0 | +3% | 0 |
| guitar_upper_bout | C | length_only | 86 -> 86 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | C | mountain_penalty | 86 -> 79 (-8%) | -2% | +27% | 0 -> 0 | +12% | 0 |
| guitar_upper_bout | C | traceform | 86 -> 73 (-15%) | -13% | +27% | 0 -> 0 | -6% | 0 |
| house | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | length_only | 13 -> 13 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | mountain_penalty | 13 -> 13 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | traceform | 13 -> 13 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | C | length_only | 44 -> 44 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | C | mountain_penalty | 44 -> 31 (-30%) | -32% | +0% | 0 -> 0 | -6% | 0 |
| house | C | traceform | 44 -> 31 (-30%) | -33% | +0% | 0 -> 0 | -8% | 0 |
