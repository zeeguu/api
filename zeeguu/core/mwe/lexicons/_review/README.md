# MWE lexicon candidates (pending review)

This folder holds **candidate** multi-word expressions sourced from
online dictionaries that still need human review before being added to
the per-language `lexicons/<code>.py` files.

Entries here are **not** loaded at runtime — only `lexicons/*.py` is.
This is a curation backlog, not live lexicon data.

## Files

### `da_wiktionary_candidates.txt` — 783 entries

Source pipeline (2026-05-14):

1. Pulled every page in
   [Wiktionary `Category:Danish_multiword_terms`](https://en.wiktionary.org/wiki/Category:Danish_multiword_terms)
   via the MediaWiki API (`action=query&list=categorymembers`,
   3 pages × 500 = **1,423 raw entries**).
2. Stripped proper nouns (first-word-capitalised), entries with
   hyphens/digits/non-Latin script, and entries with fewer than 2 or
   more than 4 tokens (drops most proverbs and abbreviations).
   → **1,061 entries**.
3. Excluded the 53 entries already promoted into `da.py` via the
   UD_Danish-DDT mining pass (these are corpus-attested).
   → **1,036 entries**.
4. Ran the remaining list through Claude Haiku with a "keep only
   function-word-anchored idioms learners need as one unit; drop
   technical compounds, proverbs, proper nouns, foreign loans"
   prompt. → **783 entries kept**.

### What's still wrong with the 783

Manual spot-checks showed Haiku was somewhat permissive. The file
likely still contains:

- A handful of full-sentence utterances ("jeg er sulten",
  "vi ses", "der vil noget") that aren't really MWEs.
- Some proverbs that slipped through ("den der tier samtykker").
- Vulgar/slang expressions that are real MWEs but probably out of
  register for a school-context vocabulary tool.
- Compositional noun phrases ("amerikansk pandekade", "arme
  riddere") that the LLM kept because they have a cultural-specific
  referent.

### Suggested review approach

The right next step is a hand pass — likely batched by a native
speaker — sorting each line into one of:

- **add** → move into the appropriate section of `da.py`
- **drop** → delete
- **defer** → leave in the candidates file with a `#` prefix and a
  short reason, so future curators don't re-litigate it

Once promoted, lines should be removed from this file to keep it
focused on the unresolved backlog.

## Adding more languages

Same pipeline as Danish:

```bash
# Mine corpus-attested candidates from UD
python tools/extract_mwes_from_ud.py path/to/<lang>-ud-train.conllu

# Pull Wiktionary candidates
curl -sG "https://en.wiktionary.org/w/api.php" \
  --data-urlencode "action=query" \
  --data-urlencode "list=categorymembers" \
  --data-urlencode "cmtitle=Category:<Language>_multiword_terms" \
  --data-urlencode "cmlimit=500" \
  --data-urlencode "format=json"
```
