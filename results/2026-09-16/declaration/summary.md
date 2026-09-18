# Summary

Each method against `length_only` on the same model and layout.
Derived from `benchmark_results.csv`; the CSV itself stays raw.

| model | layout | method | tensile | sum tensile strain | max tensile strain | compression | length | stranded |
|---|---|---|---|---|---|---|---|---|
| bat_body | A | length_only | 23 -> 23 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | A | mountain_penalty | 23 -> 14 (-39%) | -32% | +0% | 0 -> 0 | -12% | 0 |
| bat_body | A | traceform | 23 -> 11 (-52%) | -58% | +0% | 0 -> 0 | -11% | 0 |
| bat_body | B | length_only | 48 -> 48 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | B | mountain_penalty | 48 -> 34 (-29%) | -10% | +1% | 0 -> 0 | +4% | 0 |
| bat_body | B | traceform | 48 -> 35 (-27%) | -18% | +1% | 0 -> 0 | +5% | 0 |
| bat_body | C | length_only | 131 -> 131 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | C | mountain_penalty | 131 -> 92 (-30%) | -16% | +0% | 0 -> 0 | -15% | 0 |
| bat_body | C | traceform | 131 -> 76 (-42%) | -43% | +0% | 0 -> 0 | -25% | 0 |
| church | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | -5% | 0 |
| church | B | length_only | 11 -> 11 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | B | mountain_penalty | 11 -> 10 (-9%) | +0% | +0% | 0 -> 0 | +4% | 0 |
| church | B | traceform | 11 -> 10 (-9%) | -7% | +0% | 0 -> 0 | +2% | 0 |
| church | C | length_only | 71 -> 71 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | C | mountain_penalty | 71 -> 55 (-23%) | -24% | +0% | 0 -> 0 | -19% | 0 |
| church | C | traceform | 71 -> 38 (-46%) | -48% | +0% | 0 -> 0 | -34% | 0 |
| guitar_lower_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | length_only | 19 -> 19 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | mountain_penalty | 19 -> 19 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | traceform | 19 -> 19 (+0%) | +0% | +0% | 0 -> 0 | -0% | 0 |
| guitar_lower_bout | C | length_only | 94 -> 94 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | C | mountain_penalty | 94 -> 79 (-16%) | -11% | +0% | 0 -> 0 | +2% | 0 |
| guitar_lower_bout | C | traceform | 94 -> 83 (-12%) | -15% | +0% | 0 -> 0 | +2% | 0 |
| guitar_upper_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | B | length_only | 23 -> 23 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | B | mountain_penalty | 23 -> 20 (-13%) | -6% | +0% | 0 -> 0 | +4% | 0 |
| guitar_upper_bout | B | traceform | 23 -> 20 (-13%) | -6% | +0% | 0 -> 0 | +3% | 0 |
| guitar_upper_bout | C | length_only | 79 -> 79 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | C | mountain_penalty | 79 -> 70 (-11%) | -8% | +0% | 0 -> 0 | +1% | 0 |
| guitar_upper_bout | C | traceform | 79 -> 73 (-8%) | -11% | -1% | 0 -> 0 | +2% | 0 |
| house | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | length_only | 14 -> 14 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | mountain_penalty | 14 -> 14 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | traceform | 14 -> 13 (-7%) | -7% | +0% | 0 -> 0 | -2% | 0 |
| house | C | length_only | 40 -> 40 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | C | mountain_penalty | 40 -> 35 (-12%) | -12% | +0% | 0 -> 0 | +2% | 0 |
| house | C | traceform | 40 -> 30 (-25%) | -28% | +0% | 0 -> 0 | +9% | 0 |
