# Summary

Each method against `length_only` on the same model and layout.
Derived from `benchmark_results.csv`; the CSV itself stays raw.

| model | layout | method | tensile | sum tensile strain | max tensile strain | compression | length | stranded |
|---|---|---|---|---|---|---|---|---|
| bat_body | A | length_only | 18 -> 18 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | A | mountain_penalty | 18 -> 13 (-28%) | -42% | +0% | 0 -> 0 | -2% | 0 |
| bat_body | A | traceform | 18 -> 11 (-39%) | -51% | +0% | 0 -> 0 | -4% | 0 |
| bat_body | B | length_only | 47 -> 47 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | B | mountain_penalty | 47 -> 31 (-34%) | -20% | +1% | 0 -> 0 | +1% | 0 |
| bat_body | B | traceform | 47 -> 31 (-34%) | -20% | +1% | 0 -> 0 | +1% | 0 |
| bat_body | C | length_only | 142 -> 142 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| bat_body | C | mountain_penalty | 142 -> 87 (-39%) | -34% | +0% | 0 -> 0 | -23% | 0 |
| bat_body | C | traceform | 142 -> 88 (-38%) | -39% | +0% | 0 -> 0 | -21% | 0 |
| church | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | -5% | 0 |
| church | B | length_only | 10 -> 10 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | B | mountain_penalty | 10 -> 10 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | B | traceform | 10 -> 10 (+0%) | +0% | +0% | 0 -> 0 | -0% | 0 |
| church | C | length_only | 56 -> 56 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| church | C | mountain_penalty | 56 -> 43 (-23%) | -30% | +0% | 0 -> 0 | -19% | 0 |
| church | C | traceform | 56 -> 37 (-34%) | -44% | +0% | 0 -> 0 | -18% | 0 |
| guitar_lower_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | length_only | 33 -> 33 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | B | mountain_penalty | 33 -> 19 (-42%) | -42% | +0% | 0 -> 0 | -20% | 0 |
| guitar_lower_bout | B | traceform | 33 -> 19 (-42%) | -42% | +0% | 0 -> 0 | -20% | 0 |
| guitar_lower_bout | C | length_only | 109 -> 109 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_lower_bout | C | mountain_penalty | 109 -> 86 (-21%) | -20% | +0% | 0 -> 0 | -8% | 0 |
| guitar_lower_bout | C | traceform | 109 -> 86 (-21%) | -26% | +9% | 0 -> 0 | -3% | 0 |
| guitar_upper_bout | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | B | length_only | 34 -> 34 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | B | mountain_penalty | 34 -> 28 (-18%) | -20% | +3% | 0 -> 0 | +7% | 0 |
| guitar_upper_bout | B | traceform | 34 -> 20 (-41%) | -41% | +0% | 0 -> 0 | -18% | 0 |
| guitar_upper_bout | C | length_only | 90 -> 90 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| guitar_upper_bout | C | mountain_penalty | 90 -> 69 (-23%) | -12% | +27% | 0 -> 0 | -8% | 0 |
| guitar_upper_bout | C | traceform | 90 -> 73 (-19%) | -15% | +27% | 0 -> 0 | -10% | 0 |
| house | A | length_only | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | mountain_penalty | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | A | traceform | 2 -> 2 (+0%) | +0% | +0% | 0 -> 0 | -1% | 0 |
| house | B | length_only | 15 -> 15 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | mountain_penalty | 15 -> 15 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | B | traceform | 15 -> 14 (-7%) | -7% | +0% | 0 -> 0 | -1% | 0 |
| house | C | length_only | 48 -> 48 (+0%) | +0% | +0% | 0 -> 0 | +0% | 0 |
| house | C | mountain_penalty | 48 -> 48 (+0%) | -1% | +0% | 0 -> 0 | +6% | 0 |
| house | C | traceform | 48 -> 38 (-21%) | -24% | +0% | 0 -> 0 | +2% | 0 |
