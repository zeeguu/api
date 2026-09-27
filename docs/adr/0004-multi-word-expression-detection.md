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

### Where the two layers overlap: the narrower grouping wins

A parser group sharing a token with a lexicon span is dropped; the lexicon span
is kept as it is. `at finde` + `finde ud af` yields `finde ud af`, with `at`
left outside any group.

This is a deliberate reversal. For a while the lexicon span *absorbed* the
parser group, on the reasoning that an auxiliary, a negation or an infinitive
marker belongs with its verb. It does — but deciding that on the learner's
behalf was the wrong way round, because the two errors do not cost the same:

| error | how the learner fixes it | cost |
|---|---|---|
| group too **narrow** | fuse a neighbour onto it | one tap, in the flow of reading |
| group too **wide** | Ungroup expression | find a menu item |

Measured on production since 2026-01-05, when `bookmark.is_mwe` began recording
the distinction: learners fused by hand **13,725** times and ungrouped **130**.
About 105 to 1. The interface says which direction people move in, and the
detector should err the cheap way.

Two conditions make this safe, and neither held before:

- **A contiguous MWE can be extended in the reader** (zeeguu/web#1254). Until
  that shipped, `InteractiveText.translate()` treated an MWE as a closed unit,
  so erring narrow stranded grammar the learner had no way to reattach. The
  order matters: the affordance must exist before the detector leans on it.
- **Separated MWEs are unaffected.** They stay closed in the reader, and the
  backend saves no bookmark for them at all, because `(token_i, total_tokens)`
  cannot express a gap (#769).

`merge_lexicon_with_stanza` still takes `tokens`, which it no longer needs, to
leave room for a level-sensitive policy: level-adapted rows carry `cefr_level`,
and an A1 reader may well want coarser units than a B2 one. That is a policy
decision, not something to inherit from parser internals.

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

- **Changes here are invisible until two separate token stores turn over**, and
  they do not work the same way. Both need doing, *after* the API picks up the
  change — otherwise the first reader re-caches the old grouping.

  **1. `ArticleTokenizationCache`** — a cache in the ordinary sense. No version
  column; its only invalidation is a 7-day age sweep. Delete the rows and the
  next read rebuilds them:

  ```
  python -m tools.cleanup_tokenization_cache --language da --dry-run
  python -m tools.cleanup_tokenization_cache --language da
  ```

  **2. `LevelAdaptedArticleText.tokenized_summary` / `.tokenized_title`** — not
  a cache, despite holding the same shape of data. These are written once, when
  the article is simplified, and *nothing regenerates them*: both readers treat
  an empty column as "this level has no tappable summary" and fall back to plain
  text (`elastic_recommender` guards on `if summary_tokens:`; `UserArticle`
  returns `None`). Clearing them would silently make preview cards untappable,
  permanently. They must be **rewritten**:

  ```
  python -m tools.retokenize_level_adapted_texts --language da --dry-run
  python -m tools.retokenize_level_adapted_texts --language da
  ```

  Skipping step 2 is not a subtle failure: the article body picks up the new
  grouping while the preview card keeps showing the old one. That is exactly how
  this was found -- the reader said `fandt ud af` and the summary card still
  said `ud af`, hours after the flush.

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
