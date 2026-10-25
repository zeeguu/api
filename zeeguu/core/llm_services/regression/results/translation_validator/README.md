# Translation validator: regression runs per prompt version

One file per run of `tools/run_validator_regression.py --save`, named
`<PROMPT_VERSION>--<date>.txt`. Every prompt change bumps `PROMPT_VERSION`
(prompts/translation_validator.py) and is judged by a run here before it ships.

| version | runs pass | shipped | note |
|---|---|---|---|
| translation-validator-v1 | 46/58 | api#900, deployed 25 Oct 2026 | fails all adjective-agreement cases (*Zweeds* → *Zweedse*) |
| translation-validator-v2 | 43/58 | no | "add nothing the translation's grammar needs": too lenient (*Nutzer* = *gebruiker* passed) |
| translation-validator-v3 | 48/58 | this PR | v1 + adjective endings and articles exempt |
| translation-validator-v4 | 46/58 | no | v3 + small words around verbs exempt: lenient again; its prompt example reused the *accéder* case |

Still failing in v3: *accéder* = *toegang krijgen*, *poursuivre* = *nastreven* (given
up on: Dutch needs "tot" / "na te streven" around the verb).
