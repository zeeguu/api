# Translation validator: regression runs per prompt version

One file per run of `tools/run_validator_regression.py --save`, named
`<PROMPT_VERSION>--<date>.txt`. Every prompt change bumps `PROMPT_VERSION`
(prompts/translation_validator.py) and is judged by a run here before it ships.

| version | runs pass | shipped | note |
|---|---|---|---|
| translation-validator-v1 | 46/58 | api#900, deployed 25 Oct 2026 | fails all adjective-agreement cases (*Zweeds* → *Zweedse*) |
| translation-validator-v2 | 43/58 | no | "add nothing the translation's grammar needs": too lenient (*Nutzer* = *gebruiker* passed) |
| translation-validator-v3 | 48/58 | no | v1 + adjective endings and articles exempt: +2 is within run-to-run noise, for a longer prompt |
| translation-validator-v4 | 46/58 | no | v3 + small words around verbs exempt: lenient again; its prompt example reused the *accéder* case |

None of v2-v4 shipped (25 Oct 2026): instead of tuning how strictly the card must
fit its sentence, the plan is to keep the looked-up form on the bookmark and the
learning unit on the user word (docs/future-work/bookmark-and-learning-unit.md).
The adjective cases (*Zweeds*, *diep*, *gemeentelijk*, *talrijk*) and *accéder*,
*poursuivre* stay in the set as known v1 misses.
