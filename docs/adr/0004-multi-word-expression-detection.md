# 0004. Multi-word expression detection

**Status**: Accepted
**Date**: 2026-09-27
**Deciders**: Mircea, Claude

## Context

When a learner taps a word in the reader, we translate it in context. For a
word that belongs to a larger expression, translating the word alone is worse
than useless: it is confidently wrong in a way the learner cannot detect,
because checking it is precisely the skill they do not yet have.

Danish *"Forskerne **fandt ud af**, at sneglen levede i omkring 4,5 år"* is the
case that prompted this record. A tap on `ud af` grouped those two words and
translated them "out of". The expression is `finde ud af` — *find out*.

So the reader needs to know, before translating, which tokens form one unit.
That is multi-word expression (MWE) detection, and it runs at tokenization
time, not at translation time: the groups are baked into the tokens the
frontend receives, and the frontend fuses a tap on any member into the whole
group.

### Constraints

- **Precision beats recall.** A missing group costs a learner one extra tap.
  A wrong group shows them a fluent translation of something that is not an
  expression. These are not symmetric.
- **It must be fast.** This runs over a whole article, and articles are read
  on demand.
- **It must degrade safely.** Every layer's failure mode should be *no group*,
  never *wrong group*.

## Decision

Three layers, composed by `LexiconOverlayStrategy`:

```
get_strategy_for_language(code, mode)
  └─ LexiconOverlayStrategy            # wraps EVERY inner strategy
       ├─ inner strategy               # dependency-parse rules, per language family
       └─ LexiconMatcher               # hand-curated phrase lists
     merge: lexicon wins on overlap
```

### Layer 1 — dependency-parse strategies (`mwe/stanza_mwe_detector.py`)

Stanza parses with `tokenize,pos,lemma,depparse`; the strategies read `dep`,
`pos`, `head` and `lemma` off the token dicts and turn specific relations into
groups. `LANGUAGE_STRATEGIES` maps each language to one:

| Strategy | Languages | Groups on |
|---|---|---|
| `GermanicStrategy` | de nl sv da no en | `compound:prt`, aux, negation, infinitive markers, article+noun |
| `GreekStrategy` | el | aux (θα future, έχει perfect), δεν negation |
| `RomanianStrategy` | ro | aux, subjunctive `să`, reflexives |
| `AuxOnlyStrategy` | fr es it pt | aux+verb only — compound detection had too many false positives |
| `NoOpStrategy` | everything else | nothing |

Slavic and Turkic are deliberately absent: unreliable, and in an agglutinative
language the MWE tends to be one word anyway.

### Layer 2 — hand-curated lexicons (`mwe/lexicons/`, `mwe/lexicon_matcher.py`)

For fixed expressions the parser cannot see — prepositional idioms
(`på jagt efter`) and light-verb constructions (`tage hensyn til`). Longest
match wins; punctuation is skipped when assembling a span.

Section comments carry [PARSEME](https://typo.uni-konstanz.de/parseme/)'s
category names where they apply, so these lists are legible to anyone from
that literature and a future export to the PARSEME annotation scheme is
mechanical:

| Label | Category | Example |
|---|---|---|
| `LVC` | light-verb construction | `tage hensyn til`, `have brug for` |
| `VPC` | verb-particle construction | `finde ud af`, `lade som om` |
| `VID` | verbal idiom | `ud af det blå` |

Only the verbal categories are labelled. PARSEME 2.0 extends the scheme to
nominal, adjectival, adverbial and functional MWEs — which is what most of
the prepositional idioms are — but those label names have not been checked
against the 2.0 guidelines, so those sections stay descriptive rather than
carry a possibly wrong tag.

Two sets per language, because two kinds of expression inflect differently:

- **`<LANG>_MWES`** — matched on **surface form**. These are frozen: `i dag`
  means *today*, `i dagene` does not.
- **`<LANG>_VERB_MWES`** — matched with the **first token lemmatised**, and
  only if that token is tagged `VERB` or `AUX`. These are verb-initial and only
  the verb inflects, so `har brug for`, `havde brug for` and `have brug for`
  reach one entry.

The verb set is opt-in per language (`VERB_LEXICONS_BY_LANGUAGE`). Only Danish
has one today.

### Layer 3 — LLM detection (`mwe/llm_mwe_detector.py`) — **currently off**

`HYBRID_LANGUAGES = set()` in `mwe/enricher.py`. It costs 5–15s per article,
which is not affordable on a read path. The code is kept, and the comment
above it records how to switch it back on. **When reasoning about a bad
grouping, remember this layer is not running.**

## Why lemmatise rather than enumerate the inflected forms

Considered listing every form (`finde / finder / fandt / fundet / find`) as
separate surface entries and dropping lemma matching entirely. For Danish this
is tractable — verbs do not inflect for person or number, so 16 entries become
58 forms.

Rejected, for three reasons:

1. **Adding an entry would stop being a one-liner.** It would need someone who
   knows the morphology to enumerate ~5 forms, and an omission is silent.
2. **It does not scale to where the lexicon would grow next.** `AuxOnlyStrategy`
   already covers es/fr/it/pt with empty lexicons. One Spanish verb has dozens
   of finite forms across six persons.
3. **The design is already surface everywhere else.** The tails (`brug for`,
   `hensyn til`) are literal; only the head varies. Enumerating forms means
   doing by hand the one job the lemmatiser already does.

Measured before deciding: of the 58 finite and participial forms of the twelve
verbs heading `DANISH_VERB_MWES`, **57 lemmatise correctly and tag as VERB or
AUX**. The miss is the imperative `læg`, which lemmatises to `læge` (*doctor*).
That is patched with one literal in the surface set — the two sets compose, so
a lemmatiser miss costs a line, not an architecture.

The `VERB`/`AUX` gate exists because Danish `have` is both *to have* and
*garden*: without it, `haven` (*the garden*) followed by `brug for` would
lemmatise onto the entry `have brug for`.

## Why this layering, illustrated by the bug that prompted it

Worth keeping, because the failure was not where anyone looked first:

1. The parser was **right** — Stanza attaches `ud --advmod--> fandt`.
2. `GermanicStrategy` **discarded** that: `ADV + advmod` only becomes a group
   for words in `NEGATION_WORDS`, and `ud` is not one. It emitted nothing.
3. The lexicon entry `ud af` then **filled the gap** with a span that is not an
   expression.
4. The LLM detector was **not involved** — it is disabled.

The matcher already preferred the longest entry, so `finde ud af` would have
won had it been present and matchable. It was sitting unpromoted in
`lexicons/_review/`, and would not have matched anyway, because the verb was
inflected.

## Consequences

### Positive

- Each layer fails by producing no group, never a wrong one.
- Lexicon entries stay one line each, in a file a non-programmer can read.
- The lexicon applies to every language, including those whose parser strategy
  is `NoOpStrategy`.

### Negative

- Three places to look when a grouping is wrong, and the answer has been in a
  different one than expected.
- Lemma matching depends on the tokenizer running `lemma`. It does today
  (`TOKENIZER_MODEL = STANZA_TOKEN_POS_DEP`), and `lemma` survives both the
  in-process path and the remote stanza service. If that ever changes, verb
  entries silently match only their infinitive.
- Lexicons are hand-curated, so coverage is uneven between languages.

### Neutral

- **Changes here are invisible until the tokenization cache turns over.**
  `ArticleTokenizationCache` has no version column; its only invalidation is a
  7-day age sweep. After changing detection, flush the affected language:

  ```
  python -m tools.cleanup_tokenization_cache --language da --dry-run
  python -m tools.cleanup_tokenization_cache --language da
  ```

  Run it *after* the API picks up the change, or the first reader re-caches the
  old grouping. Entries re-tokenize on demand.

### Adding a lexicon entry

1. Is it verb-initial and does only the verb inflect? → `<LANG>_VERB_MWES`
   (and register the language in `VERB_LEXICONS_BY_LANGUAGE`). Otherwise →
   `<LANG>_MWES`.
2. Check no shorter existing entry is a prefix of it — that is what caused this
   bug. `lexicons/_review/` holds mined but unpromoted candidates.
3. Verb entries do not apply to **de/nl**: the verb comes last *and* V2 order
   moves it out of the span entirely (`in Betracht ziehen` → "Ich ziehe das in
   Betracht"). Those need the parser, not the lexicon.

## Related

- PR [#764](https://github.com/zeeguu/api/pull/764) — lemma-headed verb lexicon
- `zeeguu/core/mwe/` — enricher, strategies, lexicons, matcher
- `zeeguu/core/test/test_lexicon_mwe.py` — pins both directions: the inflections
  that must match, and `i dagene` / `nødt` as the two ways a looser
  implementation breaks
- ADR [0001](0001-multi-provider-tts.md) — the other per-language routing table
