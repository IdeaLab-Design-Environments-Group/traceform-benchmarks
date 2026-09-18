wrote benchmark.csv: 135 rows; eps_f = 0.03

## totals per router
| router | ordering | tensile crossings | copper mm |
|---|---|---|---|
| **length_only** | mean of 3 | **571.7** | **21,661** |
| length_only | widest_first | 544 | 20,844 |
| length_only | narrowest_first | 610 | 22,727 |
| length_only | declaration | 561 | 21,411 |
| **mountain_penalty** | mean of 3 | **445.0** | **20,820** |
| mountain_penalty | widest_first | 428 | 20,963 |
| mountain_penalty | narrowest_first | 457 | 20,998 |
| mountain_penalty | declaration | 450 | 20,499 |
| **traceform** | mean of 3 | **421.7** | **19,994** |
| traceform | widest_first | 414 | 19,445 |
| traceform | narrowest_first | 435 | 20,717 |
| traceform | declaration | 416 | 19,820 |

## ordering sensitivity (max-min of total crossings, % of median)
- length_only: 544-610, median 561, spread 11.8%
- mountain_penalty: 428-457, median 450, spread 6.4%
- traceform: 414-435, median 416, spread 5.0%

## per instance (mean over orderings)
| model | layout | length_only cross / mm | mountain_penalty cross / mm | traceform cross / mm |
|---|---|---|---|---|
| bat_body | A | 19.0 / 537 | 14.0 / 506 | 11.0 / 481 |
| bat_body | B | 46.7 / 1,036 | 32.3 / 1,061 | 32.3 / 1,079 |
| bat_body | C | 135.0 / 2,735 | 86.3 / 2,231 | 83.3 / 2,183 |
| church | A | 2.0 / 512 | 2.0 / 512 | 2.0 / 495 |
| church | B | 10.3 / 1,015 | 10.0 / 1,030 | 10.0 / 1,009 |
| church | C | 60.7 / 3,246 | 48.3 / 2,958 | 37.3 / 2,435 |
| guitar_lower_bout | A | 2.0 / 354 | 2.0 / 354 | 2.0 / 354 |
| guitar_lower_bout | B | 24.0 / 1,101 | 19.0 / 1,014 | 19.0 / 1,014 |
| guitar_lower_bout | C | 98.3 / 3,073 | 80.0 / 3,009 | 81.7 / 3,058 |
| guitar_upper_bout | A | 2.0 / 441 | 2.0 / 441 | 2.0 / 443 |
| guitar_upper_bout | B | 26.7 / 1,050 | 22.3 / 1,097 | 19.7 / 997 |
| guitar_upper_bout | C | 85.0 / 2,332 | 72.7 / 2,361 | 73.0 / 2,219 |
| house | A | 2.0 / 425 | 2.0 / 425 | 2.0 / 424 |
| house | B | 14.0 / 1,325 | 14.0 / 1,325 | 13.3 / 1,309 |
| house | C | 44.0 / 2,478 | 38.0 / 2,496 | 33.0 / 2,495 |

## traceform per instance, marginalised over orderings
| model | layout | vs length_only | vs mountain_penalty |
|---|---|---|---|
| bat_body | A | win (11.0 vs 19.0) | win (11.0 vs 14.0) |
| bat_body | B | win (32.3 vs 46.7) | tie (32.3 vs 32.3) |
| bat_body | C | win (83.3 vs 135.0) | win (83.3 vs 86.3) |
| church | A | tie (2.0 vs 2.0) | tie (2.0 vs 2.0) |
| church | B | win (10.0 vs 10.3) | tie (10.0 vs 10.0) |
| church | C | win (37.3 vs 60.7) | win (37.3 vs 48.3) |
| guitar_lower_bout | A | tie (2.0 vs 2.0) | tie (2.0 vs 2.0) |
| guitar_lower_bout | B | win (19.0 vs 24.0) | tie (19.0 vs 19.0) |
| guitar_lower_bout | C | win (81.7 vs 98.3) | loss (81.7 vs 80.0) |
| guitar_upper_bout | A | tie (2.0 vs 2.0) | tie (2.0 vs 2.0) |
| guitar_upper_bout | B | win (19.7 vs 26.7) | win (19.7 vs 22.3) |
| guitar_upper_bout | C | win (73.0 vs 85.0) | loss (73.0 vs 72.7) |
| house | A | tie (2.0 vs 2.0) | tie (2.0 vs 2.0) |
| house | B | win (13.3 vs 14.0) | win (13.3 vs 14.0) |
| house | C | win (33.0 vs 44.0) | win (33.0 vs 38.0) |
- traceform vs length_only: **11 wins, 4 ties, 0 losses** of 15
- traceform vs mountain_penalty: **6 wins, 7 ties, 2 losses** of 15
- per-(instance, ordering) rows, from wins_vs_* columns:
  - vs length_only: 29 wins, 16 ties, 0 losses of 45
  - vs mountain_penalty: 14 wins, 24 ties, 7 losses of 45

## band distribution per router (summed over instances and orderings)
| router | band 0 | band 1 | band 2 | total |
|---|---|---|---|---|
| length_only | 214 (12.5%) | 366 (21.3%) | 1135 (66.2%) | 1715 |
| mountain_penalty | 89 (6.7%) | 304 (22.8%) | 942 (70.6%) | 1335 |
| traceform | 150 (11.9%) | 292 (23.1%) | 823 (65.1%) | 1265 |

