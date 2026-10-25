# Re-checks of past verdicts

Output of `tools/recheck_validator_fixes.py`: past validator fixes that a later
prompt version judges differently. Kept as evaluation data: cases from here go
into the regression set (`../translation_validator.yaml`).

| file | judged by | what |
|---|---|---|
| `translation_validator--2026-10-25--top300.csv` | translation-validator-v1 | the 300 past fixes with the most active words: 64 judged differently (50 FIX, 7 WORD_NOT_FIT, 7 BROKEN_SENTENCE). Read 25 Oct: ~20 old fixes really wrong; ~22 only the translation's inflection (Dutch "echt" → "echte"), which led to v2; 7 broken generated examples; ~12 v1 itself wrong (e.g. "noget" = "anything"). |
