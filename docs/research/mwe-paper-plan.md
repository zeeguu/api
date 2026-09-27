# A research plan for MWE detection evidence from Zeeguu

**Status**: plan, not a paper. Written 2026-09-27.
**Inputs**: `research/mwe-learner-census.md` in Mircea's Megavault (the measured
census — all numbers below that are attributed to "the census" come from there and
were measured, not estimated); `docs/adr/0004-multi-word-expression-detection.md`
(the detector this correlates against); `docs/abr/008-mwe-evaluation-report.md` and
`docs/abr/008-mwe-appendix.md` in zeeguu/docs (the existing 56–70-example hand
gold set).

**Note on a document that does not exist**: the census refers to a fuller
literature assessment at `docs/research/mwe-research-angle.md` on branch
`mwe-research-angle`. That branch exists **locally only** (it is not on
`origin`, and `git log master..mwe-research-angle` is empty) and contains no
such file. Nothing was built on it because there is nothing there. If a copy
exists in another working tree, reconcile this document against it.

---

## 0. The short version

There is a paper here, but **not the paper the census first suggests**, and not
at the framing level. Specifically:

1. **The argument is already taken.** "MWE identification should be evaluated
   inside real learning tools" is the explicit argument of Überrück-Fries,
   Savary & Dryjańska ([NLP4CALL 2024](https://aclanthology.org/2024.nlp4call-1.19/)),
   restated at length in their [2026 book chapter](https://zenodo.org/records/21277679).
   A paper whose contribution is that argument is not publishable now. Anything
   Zeeguu writes must contribute a **measurement, a resource, or an experiment**
   that they could not produce.
2. **The reframing is not novel as psychology. It is novel as an NLP-facing
   measurement.** §2: applied linguistics has held for ~20 years that L2
   learners' processing units are frequency- and need-defined rather than
   idiomaticity-defined — Ellis, Simpson-Vlach & Maynard (2008) is the specific
   pre-emption, and Wray's needs-only analysis is the theory. NLP has not
   absorbed any of it. **So the framing must change** from "we discovered that
   learners chunk for comprehension" (a reviewer who knows the applied
   linguistics rejects on that sentence) to "theory predicted this; we are the
   first to observe it unprompted at scale, and we quantify what a PARSEME-style
   scheme cannot express." That framing survives, and it is a stronger position
   than novelty would have been: predicted-then-measured is easier to defend
   than surprising-and-unreplicated.
3. **The strongest asset needs the annotation study to exist at all.** The
   reframing is a claim about a labelled distribution. Right now it is eleven
   Danish strings eyeballed by one person. Until ~600 spans are labelled it is an
   anecdote and a reviewer will say so.
4. **The natural experiment as specified cannot work.** §4: the aggregate Danish
   before/after test is underpowered by roughly an order of magnitude against the
   largest effect the 2026-09-27 fix could plausibly produce; the "after" window
   contains zero data as of today; and the web client shipped the same day,
   rewriting the menu that hosts "Ungroup expression". Two replacements are
   specified, both feasible, and one of them (a randomised lexicon expansion
   pooled across languages) completes in ~2 months and is strictly better.
5. **The exposure diagnosis in the briefing is wrong, in a useful direction.**
   §6: Savary's group is **not** one iteration away — no deployment at scale, the
   builder was an intern who has since published nothing, their funding (COST
   UniDive) expired five days ago, their stated roadmap is bigger classroom
   quizzes rather than log mining, and their 2025–26 output has rotated entirely
   to PARSEME 2.0 and diversity metrics. Their study was **7 completed
   participants, not 12**. The real risk is not priority loss but **being
   reviewed by the people whose open questions this answers** — their 2026
   chapter's §9 asks, in print, exactly the false-positive/false-negative
   question that Zeeguu's 130 overrides operationalise. Cite them as the source
   of the question. Separately, the census misses a closer competitor:
   **Kalinina, François, Vassiliadou & Todirascu (2026)**, currently building
   learner-oriented French MWE resources.
6. **Lead with unpromptedness, not with scale or multilinguality.** Every
   extrinsic MWE evaluation in print is a *solicited* judgement. 13,725
   unprompted fusion decisions are revealed preference, and that is the one claim
   nobody has made. Multilinguality is the weakest card — Linguse already covers
   six languages and their own chapter says the method "should be adaptable".
7. **Venue: not the MWE workshop.** There is no announced 23rd edition and none
   at EMNLP 2026. **BEA 2027 @ ACL 2027 (Kyoto)** is the better target — that
   pool just accepted interaction-log evaluation of a deployed NLP component. And
   there is a near, hard, unrelated deadline worth acting on: **NoDaLiDa 2027 is
   in Copenhagen and its workshop proposals are due 16 November 2026.**

Go/no-go conditions are in §7.

---

## 1. The claim, stated so it survives a reviewer

### 1.1 What the data is

Two labelled signals, both a byproduct of use, nobody asked to annotate:

- **Explicit positives** — `bookmark.total_tokens > 1 AND is_mwe = 0`. The
  learner fused adjacent tokens by hand and paid an interaction cost to do it.
  **13,725 since 2026-01-05, of 22,253 multi-word bookmarks (61.7%), 11
  languages.** No NULLs; clean 0/1 split.
- **Explicit negatives** — `user_mwe_override` rows. The learner rejected a
  grouping the detector proposed, via "Ungroup expression". **130 rows, 46
  users, 130 distinct spans**, 2026-01-07 to 2026-09-24.

The per-language hand-fused rate tracks detector architecture (census, with
strategy names from ADR 0004):

| lang | hand-fused | inner strategy | lexicon |
|---|---|---|---|
| pt | 77.1% | `AuxOnlyStrategy` | none |
| it | 71.2% | `AuxOnlyStrategy` | none |
| es | 68.9% | `AuxOnlyStrategy` | none |
| fr | 66.1% | `AuxOnlyStrategy` | none |
| sv | 65.6% | `GermanicStrategy` | yes |
| ro | 64.9% | `RomanianStrategy` | none |
| de | 60.1% | `GermanicStrategy` | yes |
| da | 54.2% | `GermanicStrategy` | yes |
| el | 53.2% | `GreekStrategy` | none |
| nl | 52.6% | `GermanicStrategy` | yes |
| **en** | **36.8%** | `GermanicStrategy` | yes |

Sample sizes: fr 11,557 bookmarks / 301 users; de 3,129 / 196; da 3,103 / 116;
en 728 / 84. The remaining seven languages share ~3,736 multi-word bookmarks
between them, which is the binding constraint on any per-language claim about
them (§3.2).

**The headline percentage is biased upward, and by how much is unknown.**
Verified in the source: `zeeguu/api/endpoints/translation.py` skips
`Bookmark.find_or_create` entirely when `is_separated_mwe` is true, with the
comment that "the (token_i, total_tokens) span model can't represent a
non-contiguous MWE". So a **detector success** on a discontinuous MWE creates no
bookmark at all, while a learner **cannot** hand-fuse a discontinuous span in the
first place — the affordance is contiguous. The missing rows are therefore all
`is_mwe = 1`, all from the denominator, and none from the numerator. The 61.7%
is an upper bound on the true hand-fused share, and the bias is largest exactly
where separation is most common: Germanic V2 languages with particle verbs
(`rufe … an`, `finde … ud af`), i.e. de, nl, da, sv. **This must be stated in the
paper's limitations, in the abstract's phrasing, and it should be quantified** —
`user_activity_data` logs every `TRANSLATE TEXT` event including ones that
produced no bookmark, so the count of separated-MWE translations is recoverable
from the activity log even though the bookmarks are not.

### 1.2 The reframing, which is the actual finding

The most frequently hand-fused Danish spans are:

```
at få · har fået · skal være · er ikke · et sted · som folk
skal have · at holde · forskere siger · nogle områder · dårlige oplevelser
```

Almost none of these are MWEs under any standard definition. `som folk` is "as
people", `forskere siger` is "researchers say", `dårlige oplevelser` is "bad
experiences" — free and compositional. The rest are analytic grammar: perfect
auxiliary, modal, copula-plus-negation, infinitive marker. `slå op` is a
genuine verb-particle construction and is the exception, not the pattern.

So:

> **`hand-fused` ≠ `missed MWE`.** A paper reporting "61.7% of multi-word
> bookmarks reveal MWE recall failure" would be wrong, and wrong in a way a
> reviewer catches in one glance at the examples.

What the number actually measures is the gap between **the unit a reader needs**
and **the unit MWE annotation defines**. Three quite different things are
collapsed inside the 61.7%:

- *idiomatic* units (what PARSEME annotates — and note that PARSEME 2.0's
  extension to nominal, adjectival, adverbial and functional categories widens
  this slice somewhat; §2.3),
- *constructional* units — analytic tense, mood, negation, infinitive marking:
  compositional in the source, but word-by-word translation is misleading or
  ungrammatical,
- *processing* units — fully compositional and compositionally translatable,
  fused to read a longer stretch with fewer taps.

Only the first is an MWE. All three are cases where a click-to-translate reader
that translates one token is giving the learner something less useful than the
span they asked for. **That is a larger target than MWE identification, it is
measurable from this data, and no intrinsic gold-corpus evaluation can see it.**

### 1.3 What this buys, beyond a negative result

It supplies a *mechanism* for the one puzzling finding in the closest prior
work. Linguse's learners tolerated a fair amount of annotation noise — verbatim
from the interviews: "When reading it was most important to understand the bigger
picture, small annotation errors didn't matter." If the linguist's unit was never
the unit the learner wanted, tolerance of deviation from it is expected rather
than surprising. *(That finding rests on three interviews out of seven completed
participants, so it is a hypothesis to be confirmed at scale rather than a
finding to be explained — which is exactly what §6.2's override-rate analysis
would do.)*

It also makes a concrete, falsifiable prediction that the annotation study
tests: the hand-fused distribution should be dominated by constructional and
processing units, and the MWE fraction should be **low** (prior: 10–25%
across languages) and **not** correlated with the per-language hand-fused rate
in the way a recall story would predict. **Pre-register this before annotating**
(§6.4), because the study has to be able to come out the other way.

---

## 2. Literature check: does the reframing survive?

**Verdict: the reframing survives, but not as a discovery about learners. It
survives as a measurement, and as an argument aimed at NLP.** The psychological
claim "learners chunk by frequency and processing need rather than by
idiomaticity" is roughly twenty years old in applied linguistics and is
well-supported. It is essentially absent from the NLP MWE literature, including
from the learner-facing NLP systems built on that literature. That asymmetry is
the opportunity, and it dictates both the framing and the venue.

Sources below were checked by a literature sweep over the OpenAlex, Crossref and
arXiv APIs plus direct ACL Anthology fetches; open-web search was unavailable
(session budget exhausted), so grey literature and non-indexed proceedings may
have been missed. Items marked **UNVERIFIED** are metadata-confirmed but their
content was not read.

### 2.1 What is already established — do not claim any of this

- **Ellis, Simpson-Vlach & Maynard (2008)**, *TESOL Quarterly* 42(3),
  <https://doi.org/10.1002/j.1545-7249.2008.tb00137.x>. **This is the paper that
  most nearly pre-empts §1.2 and must be cited in the first paragraph of related
  work.** Verbatim: "For native speakers, it is predominantly the MI of the
  formula which determines processability; for nonnative learners of the
  language, it is predominantly the **frequency** of the formula." MI is the
  standard proxy for idiomatic bondedness. Zeeguu's `skal være`, `at få`,
  `som folk` are precisely high-frequency, low-MI sequences. A reviewer will
  send the paper here, so the paper must arrive having already been.
- **Siyanova-Chanturia, Conklin & van Heuven (2011)**, *JEP:LMC* 37(3),
  <https://doi.org/10.1037/a0022531>. Eye-tracking on binomials vs reversed
  binomials, identical in syntax and meaning, differing only in phrasal
  frequency. Natives and non-natives are both frequency-sensitive: the
  processing unit is frequency-defined, not meaning-defined.
- **Siyanova-Chanturia & Martinez (2014)**, *Applied Linguistics* 35(5),
  <https://doi.org/10.1093/applin/amt054>. Argues the MWE processing advantage
  "does not necessarily support the holistic view of formulaic language."
- **Fioravanti, Senaldi, Lenci & Siyanova-Chanturia (2021)**, *Second Language
  Research* 37(4), <https://doi.org/10.1177/0267658320941560>. The most direct
  evidence that learner unithood intuitions diverge from the phraseological
  hierarchy: "L1 speakers judged the use of a synonym as less acceptable in
  collocations than free combinations. On the contrary, **L2 learners judged the
  use of a synonym as more acceptable in collocations than free combinations.**"
- **Wray (2002)**, *Formulaic Language and the Lexicon*, CUP,
  <https://doi.org/10.1017/cbo9780511519772>, and **Wray (2007)** "'Needs Only'
  Analysis", <https://doi.org/10.1007/978-1-84628-779-4_3> (**UNVERIFIED** —
  metadata confirmed, text not read). *Needs-only analysis* is the explicit
  theoretical prediction that a learner segments only as far as their
  comprehension need requires — units are need-defined, not
  compositionality-defined. **This is the theory Zeeguu's data confirms.** Worth
  reading personally before framing the paper; it could either strengthen the
  positioning or reveal that the prediction is more specific than assumed.
  See also **Wray (2000)**, <https://doi.org/10.1093/applin/21.4.463>, and
  **Wray (2012)**, <https://doi.org/10.1017/s026719051200013x>, which questions
  "the coherence of formulaicity as a phenomenon".
- **Christiansen & Chater (2016)**, *BBS* 39,
  <https://doi.org/10.1017/s0140525x1500031x> — the Now-or-Never bottleneck and
  Chunk-and-Pass: the processing-pressure account of chunking with no
  idiomaticity component at all. And **Christiansen & Arnon (2017)**, *Topics in
  Cognitive Science* 9(3), <https://doi.org/10.1111/tops.12274>, which frames the
  field's move away from "multiword sequences being treated as units only in
  peripheral cases such as idioms."
- **Lexical bundles already are a recognised frequency-defined, explicitly
  non-idiomatic unit.** Biber, Conrad & Cortes (2004), *Applied Linguistics*
  25(3), <https://doi.org/10.1093/applin/25.3.371>: "Lexical bundles are usually
  not complete grammatical structures nor are they idiomatic, but they function
  as basic building blocks of discourse." *(Caveat: Crossref and OpenAlex return
  only "D. Biber" for this DOI — an incomplete OUP deposit. Verify the co-author
  list against the PDF.)* So "compositional multi-word units matter" is not news
  and must not be presented as such.
- **The chunked-reading pedagogy literature does exactly what §1.2 describes —
  from the top down.** Yamashita & Ichikawa (2010), *Reading in a Foreign
  Language* 22(2), <https://doi.org/10.64152/10125/66841>: "Grouping words into
  meaningful chunks is a fundamental process for fluent reading"; chunking
  difficulty hurt intermediate learners' comprehension, though *assisting*
  chunking did not clearly help. Kosaka (2024), *System* 126,
  <https://doi.org/10.1016/j.system.2024.103495>: text "segmented into smaller
  units — each grammatically and semantically meaningful", no idiomaticity
  criterion anywhere; training improved chunking skill. Kosaka & Zhao (2025),
  *ARAL*, <https://doi.org/10.1075/aral.24019.kos>. Rasinski (1994),
  <https://doi.org/10.1177/105345129402900307>, the origin of phrase-cued text
  (**UNVERIFIED** content).
  **The gap in all of it: the chunks are imposed by the system or teacher. None
  of it derives chunk boundaries from learners' own behaviour.**
- **L1–L2 congruency, not idiomaticity, predicts difficulty for compositional
  combinations.** Yamashita & Jiang (2010), *TESOL Quarterly* 44(4),
  <https://doi.org/10.5054/tq.2010.235998>: incongruent collocations stay hard
  "even with a considerable amount of exposure." Wolter & Gyllstad (2013),
  *SSLA* 35(3), <https://doi.org/10.1017/s0272263113000107>. **This is the
  existing name for Axis 3's `XLING` category and the paper should use it** —
  congruency is established terminology and inventing a new label for it would
  be a mistake.
- **The counterweight that must be engaged, not ignored**: Martinez & Murphy
  (2011), *TESOL Quarterly* 45(2), <https://doi.org/10.5054/tq.2011.247708>. 101
  Brazilian learners; MWEs built from top-2000 words depressed comprehension and
  learners "tended to overestimate how much they understood as a function of
  expressions that either went unnoticed or were misunderstood." This runs the
  *other* way: learners fail to *notice* MWEs. Zeeguu's data says that when
  learners do act, they act on compositional spans. Both can be true — the
  spans learners miss and the spans they fuse are different populations — and
  saying so explicitly is a strength, not a concession. Related: Hoang & Boers
  (2016), <https://doi.org/10.14746/ssllt.2016.6.3.7>, learners recycle MWEs
  from input only "very marginal[ly]".
- Also relevant to the normative argument: Simpson-Vlach & Ellis (2010),
  <https://doi.org/10.1093/applin/amp058>, build a pedagogic formula list on "an
  empirically derived measure of utility that is educationally and
  psychologically valid" rather than linguistic criteria. Kremmel, Brunfaut &
  Alderson (2017), <https://doi.org/10.1093/applin/amv070>: phraseological
  knowledge outperformed syntactic and vocabulary measures in predicting L2
  reading comprehension, n=418.

### 2.2 The instructive contrast: the field's own learner-facing MWE list filters out exactly what Zeeguu's learners fuse

**Martinez & Schmitt (2012)**, "A Phrasal Expressions List", *Applied
Linguistics* 33(3), <https://doi.org/10.1093/applin/ams010>: the PHRASE List is
"the 505 most frequent **non-transparent** multiword expressions in English,
intended especially for **receptive use**."

Receptive use is Zeeguu's use case, and the list's selection criterion is
non-transparency. If the annotation study comes out as predicted, this is the
single cleanest rhetorical setup available: the flagship receptive-use MWE
resource applies precisely the filter the behavioural data says is wrong.
(Counterpoint to keep honest: Macis & Schmitt (2017),
<https://doi.org/10.1177/1362168816645957>, find no relationship between
transparency and knowledge of figurative meanings.)

### 2.3 NLP: the reframing is absent, and the nearest neighbour assumes its negation

- **Überrück-Fries, Savary & Dryjańska (2024)**, NLP4CALL,
  <https://aclanthology.org/2024.nlp4call-1.19/>, <https://doi.org/10.3384/ecp211019>.
  The only MWE-in-a-reading-app paper, and its premise is the opposite of §1.2.
  Verbatim: "Multiword expressions (MWEs), **due to their idiomatic nature**,
  pose particular challenges in comprehension tasks and vocabulary acquisition
  for language learners"; "It is precisely this **idiomaticity** that makes MWEs
  a notable stumbling block"; the aim is "to bridge the gap between the
  pedagogical requirements of second language learners and the capabilities of
  state-of-the-art NLP systems." The gap they name is a **coverage** gap, closed
  with Wiktionary lexicons — not a gap in the **definition** of the unit. Their
  12 B1 students answered a VKS pre/post quiz and interviews about
  system-pushed annotations; **students never selected spans themselves.** Their
  learner-facing conclusion is tolerance for noise: "When reading it was most
  important to understand the bigger picture, small annotation errors didn't
  matter."
  **This is the sharpest available statement of the contribution: they assume
  idiomaticity is what learners need and push it at them; Zeeguu's logs record
  what learners pull.** Their speculation about "adapting MWE identification to
  the learners' proficiency level" is an open door.
- **Lee & Uvaliyev (2023)**, MWE 2023, <https://aclanthology.org/2023.mwe-1.12/>.
  Verbatim: "While MWE research has been evaluated on various downstream tasks
  such as syntactic parsing and machine translation, **its applications in
  computer-assisted language learning has been less explored**… MWEs extracted
  based on **semantic compositionality**. We evaluate these lists on their
  ability to facilitate text comprehension for learners." The closest existing
  learner-facing extrinsic evaluation — and it pairs a compositionality-based
  selection criterion with a comprehension-based evaluation without ever
  questioning the pairing. Cite as the direct precedent being challenged.
- **Rambelli, Chersoni, Senaldi, Blache & Lenci (2023)**, MWE 2023,
  <https://aclanthology.org/2023.mwe-1.13/>. **The in-venue anchor.** Verbatim:
  "Our results provide evidence that **idiomatic and high-frequency
  compositional expressions are processed similarly** by both humans and NLMs."
  L1 self-paced reading, not learners, not learner-initiated — so it makes the
  point inside the MWE workshop's own literature without doing what Zeeguu can
  do. Citing it is what makes the framing legible to that audience.
- **Schneider et al. (2014)**, LREC, <https://aclanthology.org/L14-1433/>
  (STREUSLE), and Schneider, Danchik, Dyer & Smith (2014), *TACL* 2,
  <https://doi.org/10.1162/tacl_a_00176>. The existing NLP precedent for
  admitting non-idiomatic units: a **strong/weak** distinction on "a continuum of
  lexicality, ranging from fully transparent collocations to completely opaque
  idioms" (*close call* strong, *narrow escape* weak). 3,024 strong vs 459 weak
  instances — a 6.6:1 ratio. **Zeeguu's data should invert that ratio, and
  saying so quantitatively is a concrete, checkable claim aimed at an existing
  annotation scheme.** Adopting STREUSLE's strong/weak axis alongside PARSEME's
  categories in §3.4 would be worth considering.
- **Alves, Bagdasarov & Teich (2026)**, "Cognitive Signatures of Multi-Word
  Expressions: Reading-Time and Surprisal", MWE 2026,
  <https://aclanthology.org/2026.mwe-1.5/>. Reading time predicts MWE-hood for
  fixed expressions but shows "no consistent predictive effects" for phrasal
  verbs; GPT-2 surprisal correlates with MWE status but "fails to capture the
  distinction between types". **A standing warning that behavioural signal is
  selective by MWE class** — which is why §3.4 stratifies the analysis by
  category rather than reporting one pooled number.
- **Rohanian, Taslimipoor, Yaneva & Ha (2017)**, RANLP,
  <https://aclanthology.org/R17-1078/>, "Using Gaze Data to Predict Multiword
  Expressions" — the only prior behavioural-signal-for-MWE work, and it is lab
  gaze data on native and non-native English readers, not deployment logs.
- **Lew (2012)**, *Lexikos* 22, <https://doi.org/10.5788/22-1-1006>. **The nearest
  methodological ancestor**: Polish learners of English choosing *which component
  word* of an MWE to look up. Frequency is the strongest predictor, with nouns >
  adjectives > verbs and function words "hardly looked up at all". Different
  question — which single word inside a known MWE, not which span to fuse — but
  the same instinct that lookup behaviour is data. Note the tension worth
  reporting: if function words are hardly ever looked up alone, `at få` and
  `skal være` may be evidence that learners fuse function words instead.
- **Methodological analogue for the log-data audit**: Soliar, Colling, Bodnar &
  Meurers (2026), BEA 2026, <https://aclanthology.org/2026.bea-1.14/>, "Using
  Interaction Log Data to Evaluate and Improve Feedback Accuracy in an
  Intelligent Language Tutoring System" — 5,646 logs, 368 students, used to find
  which rules produced incorrect feedback. The template for "audit a rule-based
  component with production logs".
- **On the fragility of intrinsic evaluation**: Ramisch, Walsh, Blanchard &
  Taslimipoor (2023), MWE 2023, <https://aclanthology.org/2023.mwe-1.15/>, "A
  Survey of MWE Identification Experiments: The Devil is in the Details" — 40
  papers, undocumented design choices that "may considerably impact the results".
- **PARSEME 2.0**: Scholivet, Savary, Ramisch, Bilinski, Nakamura, Mitrofan &
  Pais (2026), MWE 2026, <https://aclanthology.org/2026.mwe-1.33/> — 17
  languages, and for the first time verbal, nominal, adjectival, adverbial and
  functional categories together, with a paraphrasing subtask in 14 languages.
  Note that the extension to non-verbal categories **narrows** §1.2's gap
  somewhat: some of what Zeeguu would have labelled "not an MWE" under 1.3 is
  annotatable under 2.0. It does not close the `GRAM` gap, which is the biggest
  category — PARSEME does not annotate auxiliary constructions at any version.
- **Worth opening before finalising the novelty claim** (both **UNVERIFIED**):
  Brooke, Hammond, Jacob, Tsang, Hirst & Shein (2015), "Building a Lexicon of
  Formulaic Language for Language Learners", MWE 2015,
  <https://aclanthology.org/W15-0915/> — the title alone makes it the most
  likely earlier statement of learner-oriented unit selection; and Burstein
  (2013), "The Far Reach of Multiword Expressions in Educational Technology",
  MWE 2013, <https://aclanthology.org/W13-1020/>.

### 2.4 Confirmed absences

A sweep of the MWE workshop volumes for 2013, 2015, 2016, 2018–2023, 2024
(MWE-UD), 2025 and 2026, NLP4CALL 2022–2024, and all arXiv papers matching
`all:"multiword expressions"` found **no** paper that:

- derives MWE candidates from learner behavioural data (clicks, lookups, span
  selections);
- argues that the MWE construct is misaligned with learner comprehension needs;
- evaluates MWE identification against learner-elicited unit boundaries.

### 2.5 What this means for the framing — and it is a real change

**Wrong framing** (and the one the census's excitement naturally suggests): "we
discovered that learners chunk for comprehension rather than idiomaticity."
Ellis et al. (2008) and Wray got there, and a reviewer who knows the applied
linguistics will reject the paper on that sentence alone.

**Right framing:**

> The psycholinguistic literature has predicted for two decades that L2
> learners' processing units are frequency- and need-defined rather than
> idiomaticity-defined. NLP's MWE construct — and the learner-facing systems
> built on it — has not absorbed that. We provide the first observation of
> learner-initiated unit selection at scale, in the wild, across eleven
> languages, and quantify how much of what learners ask for a PARSEME-style
> scheme cannot express.

Four things remain genuinely novel on that framing:

1. **The data type** — learner-initiated span fusion in a live tool as a
   behavioural signal of comprehension-unit boundaries. Everything in §2.1 uses
   eye-tracking, self-paced reading, acceptability judgements or lab tasks; the
   chunking-intervention literature imposes chunks top-down; Lew (2012) asks
   which word, not which span.
2. **The ecological, unprompted, multilingual setting** — eleven languages,
   learners acting on felt need rather than on a researcher's stimulus set.
3. **The NLP-facing argument** — MWE identification's extrinsic validity for a
   learner-facing task. Unoccupied.
4. **The quantity** — what fraction of learner-fused spans a PARSEME-style
   scheme would capture. Nobody has reported it. It is checkable and it is §3.

**Consequences for venue.** The applied-linguistics audience already believes
the psychology and will want effect sizes, proficiency covariates and L1
controls that this data cannot supply (Zeeguu records neither proficiency nor L1
reliably for this purpose). The NLP audience does not yet believe the psychology
and is the one whose practice would change. **Target NLP.** §5.5 accordingly
puts the MWE workshop first, and the applied-linguistics literature in §2.1
becomes the paper's *warrant* rather than its competition — which is a
comfortable place to be, because it means the finding is predicted by theory
rather than surprising, and predicted-and-then-measured is a much easier paper
to defend than surprising-and-unreplicated.

---

## 3. The annotation study

Purpose: convert §1.2 from an observation into a measurement, and produce a
releasable resource. This is the single highest-value piece of work in the plan
and everything else depends on it.

### 3.1 Sampling frame — two frames, both required

The hand-fused population is heavily Zipfian: a handful of spans (`at få`,
`er ikke`) account for a large share of rows. That means two different
questions, with two different samples, and reporting only one is a
misrepresentation:

- **Token-level frame** — sample uniformly over *bookmark rows*, so a span that
  was fused 40 times can be drawn 40 times. Estimates **what fraction of
  learner effort went into each category**. This is the frame that supports any
  claim about the 61.7%, and it is the **primary** frame.
- **Type-level frame** — sample uniformly over *distinct span strings*.
  Estimates **what the inventory of fused expressions looks like**. This is the
  frame that supports any claim about lexicon coverage or about what a lexicon
  should contain. **Secondary**, and reported separately — never pooled.

Expect these to diverge sharply. The token frame will be dominated by
grammatical constructions; the type frame will contain a much higher share of
genuine MWEs, because idioms are individually rare. **The divergence is itself a
finding and should be a table in the paper**, because it is precisely the reason
frequency-ranked "top missed spans" lists (which is how this investigation
started) mislead.

Clustering controls, applied to both frames:

- Cap at **5 spans per user per language**, so one heavy reader cannot define a
  stratum.
- Cap at **3 spans per article**.
- Draw with a fixed seed; store the seed and the drawn `bookmark.id` list in the
  repo so the sample is reproducible.

### 3.2 Size and stratification

Per-language precision at n=100 (Wilson 95% CI half-width): ±6.0 pp at a true
proportion of 0.10, ±7.8 pp at 0.20, ±9.6 pp at 0.50. That is enough to
separate "MWE fraction is under a quarter" from "MWE fraction is around half",
which is the claim being made. It is **not** enough to rank languages against
each other by MWE fraction, and the paper must not try.

| tier | languages | n per language | why |
|---|---|---|---|
| **A** | fr, de, da, en | 100 | the four with volume ≥728 and ≥84 users; fr is the largest and is also Linguse's language (comparability); en is the 36.8% low-water mark and so the contrast case |
| **B** | nl, sv, es, it, pt, ro, el | 30 | ±13.9 pp at p=0.20 — enough to show the pattern holds or does not, and explicitly **not** enough for a per-language estimate. Report as an indicative panel with CIs shown, never as point estimates in prose. |

**Total: 400 (A) + 210 (B) = 610 spans**, token-level frame.
Plus a **type-level** sample of **50 per Tier A language = 200**.
Plus a **double-annotated overlap of 20%** for IAA (§3.5): 122 + 40 = 162 spans
labelled twice.

Total annotation events: 610 + 200 + 162 = **972**. At 60–90 s per span with
sentence context visible, that is 16–24 person-hours — realistically **three
working days spread over annotators**, not the "about a day" the census
estimated. The census estimate was for a single language.

If Tier B annotators cannot be found for some languages, **drop those languages
from the paper rather than annotating them badly**. A four-language study with
clean IAA is publishable; an eleven-language study with three unreliable
strata is not.

### 3.3 What the annotator sees

Mandatory, because `et sted` ("a place" vs "somewhere") cannot be labelled
without it:

- the **full sentence**, from `bookmark_context.cached_tokenized` (the only
  long-lived token stream carrying MWE metadata — ADR 0004 and the census both
  note `article_tokenization_cache` is swept every 7 days),
- the **span**, highlighted in that sentence,
- the **language**.

Withheld, deliberately:

- **how often the span was fused** — frequency biases labelling toward treating
  common strings as lexical items,
- **whether the detector caught it**, and which layer — the whole point is a
  reference independent of the detector,
- **the learner's L1 and proficiency** — these matter for interpretation but
  would let an annotator rationalise,
- **any translation** the learner received.

Presentation order randomised across languages and categories, with a fixed
seed.

### 3.4 Annotation guidelines

These are the guidelines, to be used as written. They are three orthogonal
axes plus three flags. Annotate **all** axes for every span.

> **Framing instruction to annotators.** You are not deciding whether the
> learner was right to group these words. They already decided that, and they
> are not available to ask. You are deciding **what kind of thing they grouped**.
> "The learner should not have fused this" is not a label. If the span is a
> perfectly ordinary compositional phrase, that is the informative answer, and
> `FREE` is the correct label — it is not a failure of the item.

#### Axis 1 — `category`: what kind of unit is this? (single label, ordered decision list)

Work down the list. **The first rule that applies wins.** The order exists to
resolve overlaps; do not skip ahead.

**1. `SEG` — segmentation artefact.** Assign if the span
- crosses a clause or sentence boundary (`, at sneglen`),
- includes sentence-level punctuation inside it,
- contains a fragment of a word, or
- is otherwise not something a reader could have meant as one unit.

*Do not* use `SEG` merely because the span is not a syntactic constituent —
that is the `clause_fragment` flag (below), and `forskere siger` is a real
thing a learner meant to group even though subject+verb is not a phrase.

**2. `NE` — named entity.** Proper names, titles of works, institution names.
`Det Hvide Hus`, `New York`, `Dansk Folkeparti`.

**3. `NUM` — numeric, date or measure expression.** `4,5 år`, `i 2026`,
`tre millioner`. Lexicalised temporal adverbials such as Danish `i dag`,
`i går` are **not** `NUM` — they reach rule 5 and are `ADVPREP`.

**4. `GRAM` — analytic grammatical construction.** Assign if the span consists
*only* of a verb together with some combination of
- auxiliaries (perfect, passive, future),
- modals,
- a copula,
- negation particles,
- an infinitive marker (`at`, `te`, `zu`, `om te`),
- a reflexive that carries no lexical meaning,

**and the combination means exactly what the grammar says it means.**

Examples: `har fået`, `skal være`, `er ikke`, `at få`, `at holde`, `skal have`,
`wird kommen`, `heeft gezien`, `θα πάει`, `să fie`, `a été`.

*Boundary against rule 6 (LVC/VID).* If the combination carries lexical meaning
beyond its tense/mood value, it is **not** `GRAM`. Danish `have brug for` has
`have` as a light verb plus a noun that only occurs in this construction — that
is `LVC`, not `GRAM`. The test: **replace the verb with a semantically empty
placeholder of the same grammatical function.** If the meaning survives, it was
grammar; if it collapses, there was lexical content.

*This category does not exist in PARSEME.* PARSEME does not annotate auxiliary
combinations as MWEs. Zeeguu's `GermanicStrategy`, `GreekStrategy` and
`AuxOnlyStrategy` group them deliberately, because a reader tapping `fået` and
getting "got" instead of "has got" is being misled. **The size of `GRAM` in the
token frame is the crispest single number this study can produce**: it measures
exactly how much of the reader's need falls outside the MWE literature's scope
by construction.

**5. Non-verbal lexicalised MWE.** The span is not verb-headed but is a
lexicalised multiword unit. Apply the lexicalisation tests (§3.4.1). Then:
- **`ADVPREP`** — adverbial or prepositional fixed expression, including complex
  prepositions: `i dag`, `på grund af`, `i forhold til`, `ud af`, `for resten`,
  `à cause de`, `im Laufe`. This is where the bulk of Zeeguu's surface lexicons
  live (ADR 0004, layer 2).
- **`NOM`** — fixed or compound-like nominal: `folkeskole` written apart,
  `train station`, `carte bleue`.
- **`FUNC`** — multiword functional item: `as well as`, `så snart som`,
  `ainsi que`.

PARSEME 2.0 ([Scholivet et al., MWE 2026](https://aclanthology.org/2026.mwe-1.33/))
extends the scheme to nominal, adjectival, adverbial and functional MWEs. ADR
0004 records that those 2.0 label names have not been checked against the 2.0
guidelines. **Before annotation starts, check them and map `ADVPREP` / `NOM` /
`FUNC` onto the official 2.0 tags** — the mapping should be mechanical, and
doing it makes the released dataset directly comparable to PARSEME 2.0, which
is worth a lot. Until that check is done, these three labels are Zeeguu-local
and must be presented as such. *(Status: UNVERIFIED — the 2.0 guidelines were
not consulted for this document.)*

**6. Verbal MWE — PARSEME categories.** Verb-headed and lexicalised. Apply
PARSEME's own tests and labels, in PARSEME's own order. Labels
([PARSEME guidelines v1.3.6](https://parsemefr.lis-lab.fr/parseme-st-guidelines/1.3/),
verified): `LVC`, `VID`, `IRV`, `VPC`, `MVC`, `IAV`, `LS.ICV`.
- **`IRV`** — inherently reflexive verb: the reflexive is obligatory and
  non-argumental. `se souvenir`, `sich befinden`.
- **`LVC`** — light-verb construction: the verb is semantically bleached and the
  noun carries the predicate. `tage hensyn til`, `have brug for`,
  `give udtryk for`, `prendre une décision`.
- **`VPC`** — verb-particle construction: verb plus particle with a meaning not
  predictable from the particle. `finde ud af`, `slå op`, `aufstehen` split,
  `turn out`.
- **`MVC`** — multi-verb construction: two verbs forming one predicate that is
  not an auxiliary combination (contrast rule 4). `lade som om` sits near here;
  see edge cases.
- **`IAV`** — inherently adpositional verb: the adposition is obligatory and
  semantically empty. `stå over for`, `være nødt til`, `depend on`.
- **`VID`** — verbal idiom: anything verbal and lexicalised that the above do
  not cover. `ud af det blå`, `kick the bucket`.
- **`LS.ICV`** — language-specific inherently clitic verb; expected only in
  Romance/Greek strata if at all.

Sub-labels `LVC.full` / `LVC.cause` and `VPC.full` / `VPC.semi` exist in the
PARSEME scheme. *(UNVERIFIED for v1.3 — the §3/§5 subsections were not
retrieved. Confirm before use; if in doubt annotate the coarse label only.
Coarse labels are sufficient for every claim this paper makes.)*

**7. `COLL` — collocation.** Transparent and compositional, but with a
conventionally preferred partner: substituting a near-synonym gives something
odd rather than wrong. `stærk kaffe`, `heavy rain`, `faire attention` in its
literal use. Use sparingly — `COLL` is where an over-generous annotator dumps
everything, and the guidelines' job is to stop that. **If you cannot name the
substitution that goes wrong, it is `FREE`.**

**8. `FREE` — free compositional combination.** No lexical status. Each word
means what it means; the combination means their sum; a near-synonym could
replace either word. `som folk`, `forskere siger`, `dårlige oplevelser`,
`nogle områder`.

**9. `UNK`** — cannot decide even with the sentence in front of you. **If `UNK`
exceeds 5% of a stratum, stop and revise the guidelines**; the label set is
failing, not the annotator.

#### 3.4.1 Lexicalisation tests (for rules 5–8)

Standard, applied in this order. A span is lexicalised if **at least one** test
fires:

1. **Substitution.** Replace one component with a close semantic near-synonym.
   If the meaning changes unexpectedly or the result is unacceptable, the span
   is lexicalised. (`på grund af` → `*på årsag af`.)
2. **Morphosyntactic rigidity.** Vary number, definiteness, tense on a
   component. If variation is blocked, lexicalised. (`i dag` vs `*i dagene` —
   the test `docs/../test_lexicon_mwe.py` already pins for the detector.)
3. **Insertion.** Insert a modifier between components. If blocked, lexicalised.
4. **Component in a restricted sense.** Does a component appear here in a sense
   it has nowhere else? (`brug` in `have brug for`.) If yes, lexicalised.
5. **Omission.** Can a component be dropped with proportional loss of meaning?
   If dropping it destroys the meaning entirely, lexicalised.

If no test fires: `COLL` if you can name a conventional preference, else `FREE`.

#### Axis 2 — `wbw_adequate`: would word-by-word translation have been adequate?

**Binary: `yes` / `no`.** Independent of Axis 1, and this is the axis the paper
turns into a new task.

> Imagine the reader tapped each token of this span separately, received the
> best single-token translation of each in context, and read them in order.
> Would that give them an adequate understanding of this span in this sentence?
> `yes` or `no`.

- `har fået` → **no** (word-by-word gives "has got-ten" in a way that can
  mislead about aspect; in many L1s "has" alone is wrong).
- `dårlige oplevelser` → **yes** ("bad" + "experiences").
- `finde ud af` → **no**.
- `som folk` → **yes**.
- `i dag` → **no** ("in" + "day").

Annotate this **against the learner's target language where known, else against
English**. Record which. This axis is deliberately more concrete than Axis 1
and should show higher agreement; if it does not, the guidelines are broken.

**Why this axis matters more than Axis 1 for the paper.** It is the functional
criterion a deployed reader actually needs to predict. It is language-pair
relative, which MWE-hood is not. And the cross-tabulation of Axis 1 × Axis 2 is
the paper's central table: it shows how much of what a reader needs is *not*
MWE-hood, and how much MWE-hood is *not* what a reader needs.

#### Axis 3 — `motivation`: why would a learner need this as one unit? (single label)

- **`IDIOM`** — the meaning is not recoverable from the parts.
- **`GRAMMAR`** — the parts are recoverable but the construction carries
  meaning the parts do not (tense, aspect, mood, negation, infinitive).
- **`XLING`** — compositional in the source, but does not map word-for-word
  into the target language. Cross-lingual non-compositionality without
  monolingual idiomaticity. **Use the established term in the paper:
  *incongruent*, after Yamashita & Jiang (2010) and Wolter & Gyllstad (2013)
  (§2.1). Do not coin a new label for a phenomenon that already has one** —
  congruency is standard vocabulary in L2 collocation research and reusing it
  buys the paper credibility with exactly the audience that would otherwise
  object.
- **`PROCESSING`** — fully compositional, compositionally translatable; the
  plausible reason to fuse is to get a longer stretch in one tap.
- **`MISTAP`** — the fusion looks accidental: a drag overshoot, a span with no
  coherent reading.

#### Flags (independent booleans, annotate all that apply)

- **`partial`** — the span is a strict substring of a larger MWE present in this
  sentence. The canonical case, and the bug that produced ADR 0004: `ud af`
  inside `fandt ud af`. **The rate of `partial` is one of the most
  detector-actionable numbers in the study** — it says how often learners are
  reaching for a real MWE and grabbing part of it, which is a different failure
  from missing it.
- **`discontinuous`** — the MWE in this sentence is discontinuous and the
  learner fused only a contiguous part. Relevant because the census records a
  blind spot: `translation.py:142-152` skips `Bookmark.find_or_create` when
  `is_separated_mwe`, so fully separated MWEs create no bookmark at all. This
  flag catches the partial-overlap residue that does get through, and its rate
  bounds how badly the blind spot distorts the census.
- **`clause_fragment`** — the span is not a syntactic constituent, but is
  intelligible as a chunk. `forskere siger`.
- **`strong` / `weak`** — optional fourth axis, worth adding: STREUSLE's
  lexicality distinction (Schneider et al. 2014, <https://aclanthology.org/L14-1433/>),
  where *close call* is strong and *narrow escape* is weak. Cheap to annotate on
  top of Axis 1, and it lets the paper report Zeeguu's strong:weak ratio directly
  against STREUSLE's 3,024:459 (6.6:1). If Zeeguu's ratio inverts, that is a
  one-number result aimed at an existing scheme, which is a much better kind of
  claim than a qualitative argument.

### 3.5 Inter-annotator agreement

- **Overlap**: 20% of each stratum, double-annotated (162 spans total).
- **Statistics**: Cohen's κ for two annotators per language; Krippendorff's α
  if any language gets three or more. Report per language and pooled.
- **Report κ at three granularities** for Axis 1, because they will differ and
  reporting only the flattering one is the standard sin here:
  1. full label set (13 labels) — expect κ ≈ 0.55–0.70,
  2. collapsed to `{MWE, GRAM, COLL/FREE, SEG/NE/NUM}` — expect κ ≈ 0.70–0.80,
  3. collapsed to binary `{MWE, not-MWE}` — expect κ ≥ 0.75.
- **Pre-registered threshold**: if binary κ < 0.60 in any Tier A language, the
  guidelines are revised, annotators recalibrated, and the stratum redone.
  **Both rounds are reported**, with the revision described. Silently redoing a
  round is the thing that makes annotation studies unreproducible.
- **Calibration round first**: all annotators label the same 25 spans (drawn
  from a language they all read, or from their own language with a shared
  English-glossed set), discuss disagreements against the guidelines, and the
  guidelines are amended *before* the real round starts. The calibration spans
  are excluded from the sample.
- Also report **prevalence- and bias-adjusted κ (PABAK)** alongside κ, because
  `GRAM` and `FREE` will be high-prevalence and raw κ is pessimistic under
  skew. Reporting both pre-empts the obvious reviewer complaint in either
  direction.

### 3.6 Annotators — the real constraint, stated honestly

The label set needs someone who is (a) native or near-native, (b) capable of
applying lexicalisation tests, (c) available for three days. That is a
linguistics student or a colleague, per language. Realistic assignment:

| lang | tier | plausible source | status |
|---|---|---|---|
| da | A | Mircea (near-native, resident, owns the Danish lexicon work) + one Danish native from ITU | plausible |
| en | A | any two of the team | secure |
| de | A | ITU / Zeeguu network; German is common | plausible |
| fr | A | **unsolved, and it is the biggest stratum (11,557 bookmarks, 301 users)** | see below |
| ro | B | Mircea is a Romanian native | secure |
| nl, sv | B | Zeeguu's Dutch and Swedish user communities; a Groningen/Gothenburg contact | uncertain |
| es, it, pt, el | B | unsolved | uncertain |

Two honest consequences:

- **French is the strategic problem.** It is the largest stratum, it is the
  language Linguse works in (so it is where comparability lives), and the
  obvious source of a trained French MWE annotator is **Savary's own group**.
  Collaborating makes the paper much better and removes the exposure risk
  described in §6 by converting a competitor into a co-author. Not
  collaborating means either finding a French annotator elsewhere or
  down-weighting the language that carries half the data. This is a decision to
  make deliberately and early, not to drift into. My recommendation is in §6.3.
- **Tier B will shrink.** Plan for nl, sv, ro plus two of {es, it, pt, el}.
  Write the paper so it survives Tier B being five languages instead of seven.

### 3.7 Two cheap things to compute on the annotated sample

Both are read-only and turn the annotation from a description into an
evaluation. Neither requires touching the production database beyond a one-time
read-only export into a frozen local file.

1. **`detector_now`** — re-run the current enricher offline over each sampled
   span's cached sentence and record whether today's detector would group it.
   Against the annotated labels this yields genuine precision/recall of the
   detector **against a learner-derived reference**, per Axis-1 category. That
   is the extrinsic evaluation the field does not have. Note the caveat the
   census already flags: no detector version is stored anywhere, so this
   measures *today's* detector against *historical* learner behaviour, and must
   be reported that way.
2. **Lexicon-candidate yield** — of the type-frame spans labelled as any MWE
   category, how many are absent from the relevant lexicon? That is a directly
   usable work list, and `lexicons/_review/` already exists as the destination.

---

## 4. The natural experiment — why it fails as specified, and what replaces it

### 4.1 The intervention, precisely

PR [#764](https://github.com/zeeguu/api/pull/764), deployed **2026-09-27 ~18:00
UTC**. It introduced `DANISH_VERB_MWES` — lemma-headed matching so that
verb-initial expressions match in inflected forms, not only the infinitive — and
registered `da` in `VERB_LEXICONS_BY_LANGUAGE`. The set has **16 entries**:

```
LVC : tage hensyn til · tage stilling til · give udtryk for · have brug for
      have lyst til · have ret til · komme i tanke om · lægge mærke til
      holde øje med · sætte pris på · stå over for · være nødt til
      være glad for · blive nødt til
VPC : finde ud af · lade som om
```

Danish is the only language with a verb lexicon. The intervention is genuinely
dated and single-language. It is **not** clean: §4.5 point 5 shows the web client
also shipped on 2026-09-27, rewriting the very menu that hosts "Ungroup
expression". And it is small.

### 4.2 Why the aggregate test cannot work

Three reasons, in increasing severity.

**(a) There is no "after" data.** Today is 2026-09-27; the deploy was at ~18:00
UTC today. A 1-month window closes late October, a 3-month window late
December. Nothing can be computed now.

**(b) The expected effect on the aggregate rate is tiny.** The top hand-fused
Danish spans are `at få`, `har fået`, `skal være`, `er ikke`, `et sted`,
`som folk`, `skal have`, `at holde`, `forskere siger`, `nogle områder`,
`dårlige oplevelser`. The 16-entry fix touches **none** of them. Its effect on
the *aggregate* Danish hand-fusing rate is bounded by the share of Danish
hand-fusings that involve one of those 16 expressions, which on the evidence of
the frequency list is small — plausibly well under 1 percentage point.

**(c) Power, computed.** Two-proportion test, α = 0.05 two-sided, power 0.80,
before-arm n₁ = 3,103 (all Danish multi-word bookmarks 2026-01-05 → 2026-09-27),
after-arm at the observed Danish rate of ~355 multi-word bookmarks/month.
"DEFF = 2" halves effective n to allow for clustering within 116 users — a
conservative but unmeasured assumption, and one that should be replaced with the
measured intra-user correlation before anything is pre-registered:

| after window | n₂ | min. detectable drop, DEFF=1 | DEFF=2 |
|---|---|---|---|
| 1 month | 356 | 7.8 pp | 11.0 pp |
| 2 months | 712 | 5.8 pp | 8.2 pp |
| 3 months | 1,068 | 5.0 pp | 7.0 pp |
| 6 months | 2,136 | 3.9 pp | 5.6 pp |
| 12 months | 4,272 | 3.3 pp | 4.7 pp |

So a year of waiting buys the ability to detect a 4.7 pp drop, against an
expected effect under 1 pp. **The aggregate test is underpowered by roughly an
order of magnitude and should not be run.** Running it and reporting a null
would be actively misleading — it would read as "better detection does not
reduce learner effort" when it in fact shows "16 lexicon entries do not move a
denominator of 3,103".

### 4.3 Replacement 1 — the targeted pre-registered test (retrospective, cheap)

Change the denominator. Restrict to Danish multi-word bookmarks whose span
**contains an inflected form of one of the 16 lexicon verbs** (`tage`, `give`,
`have`, `komme`, `lægge`, `holde`, `sætte`, `stå`, `være`, `blive`, `finde`,
`lade`) **and** whose span overlaps the corresponding lexicon entry. Outcome:
hand-fused share within that subset.

This is the subset the intervention was designed to change, so the expected
effect is near-ceiling rather than marginal. Power, balanced arms, α = 0.05,
power 0.80, DEFF = 2:

| effect | n per arm (DEFF=2) |
|---|---|
| 70% → 20% | 29 |
| 70% → 30% | 47 |
| 60% → 20% | 45 |
| 60% → 30% | 84 |
| 60% → 40% | 194 |
| 50% → 25% | 115 |
| 50% → 35% | 339 |

So **a few dozen bookmarks per arm suffices** if the effect is large, which it
should be by construction.

**The blocking unknown**: nobody has measured how many pre-intervention Danish
multi-word bookmarks fall in that subset. The census does not contain it.
**Measure it first** (read-only), and apply this stopping rule:

> If the pre-intervention targeted subset has fewer than ~150 bookmarks over
> 2026-01-05 → 2026-09-27, the after-arm will take many months to reach even 50
> and the targeted test should also be dropped. Say so in the paper rather than
> reporting an underpowered null.

Sketch of the query (run against a read replica or a local dump — **not**
production):

```sql
-- pre-intervention targeted subset size; adjust the LIKE list to the 16 entries
SELECT SUM(b.is_mwe = 0) AS hand_fused, COUNT(*) AS total
FROM bookmark b /* ... joins to language and to the span surface form ... */
WHERE b.total_tokens > 1
  AND <language = 'da'>
  AND b.time < '2026-09-27 18:00:00'
  AND <span matches one of the 16 lexicon entries, verb lemma-headed>;
```

### 4.4 Replacement 2 — the design that actually supports the causal claim

A prospective **randomised** intervention. Zeeguu can randomise detector
configuration per user; a 12-student questionnaire study cannot. This is the
single thing in the whole plan that is hardest to scoop.

Design:

- **Unit of randomisation**: user, not article or session. Randomising per
  article means the same learner sees inconsistent grouping behaviour inside one
  reading session, which is both a confound and a bad experience.
- **Arms**: lexicon/strategy configuration A vs B. The cleanest version is to
  stage a **lexicon expansion** (the `lexicons/_review/` backlog, plus the
  type-frame candidates from §3.7) and ship it to half of users per language.
- **Primary outcome**: hand-fused share of multi-word bookmarks.
- **Secondary outcomes**: `user_mwe_override` rate (the precision side — a
  larger lexicon should *raise* it, and if it does not, the added entries are
  not being hit); hand-fusings per 1,000 `TRANSLATE TEXT` events (§4.5 point 6).
- **Pre-register** arms, outcomes, window and analysis before shipping.

Power, α = 0.05, power 0.80, DEFF = 2, at observed volumes:

| scope | effect | months to complete |
|---|---|---|
| Danish only (355 MW bookmarks/mo, split 50/50) | 54.2% → 48.0% | ~11.5 |
| Danish only | 54.2% → 44.0% | ~4.2 |
| **all 11 languages (~2,549 MW bookmarks/mo)** | 61.7% → 56.0% | **~1.8** |
| all 11 languages | 61.7% → 54.0% | **~1.0** |

**Pooled across languages the experiment completes in one to two months.** That
is the recommendation: do not spend a year trying to rescue the Danish
retrospective test; spend two months running the randomised version across the
platform. It is faster, it is a real causal estimate, and it is the part of the
contribution nobody else can copy.

### 4.5 Confounds, and what handles each

Applies to §4.3 and (mostly) not to §4.4, which is why §4.4 is better.

1. **Seasonality and term structure.** Zeeguu's Danish reading volume follows
   school/university terms; a 3-month post window runs into the Christmas break.
   → **Difference-in-differences against control languages.** `de`, `nl`, `sv`
   share `GermanicStrategy` and have surface lexicons but received no change;
   `fr`, `es`, `it`, `pt` received no change at all. A Danish-minus-pooled-controls
   estimate removes any platform-wide shift. **Check the parallel-trends
   assumption on the pre-period month by month and show the plot** — if the
   pre-trends are not parallel, DiD is not licensed and should not be used.
2. **User mix.** 116 Danish users since January; a few may dominate. → Fit a
   mixed-effects logistic model with a **user random intercept**, and report a
   **within-user before/after** estimate restricted to users active in both
   windows as the primary specification. Within-user is the cleanest estimator
   available retrospectively.
3. **Article mix.** MWE density varies by source and register. → Article random
   intercept; report whether the feed-source composition shifted across the cut.
4. **Cached tokenizations turned over gradually.** The nastiest one.
   `ArticleTokenizationCache` has no version column and its only invalidation is
   a 7-day age sweep (ADR 0004). Articles cached shortly before the deploy can
   serve the old grouping for up to a week, and whether
   `tools.cleanup_tokenization_cache --language da` was actually run after the
   API picked up the change is **UNVERIFIED** — check the deploy log before
   analysing anything.
   → Two mitigations, use both: **(i)** discard a 7-day washout and start the
   after-window **2026-10-05**; **(ii)** better, classify each after-window
   bookmark as treated or untreated by inspecting its own
   `bookmark_context.cached_tokenized` for whether that token stream carried the
   new grouping. That converts the design from intent-to-treat-by-date into
   **actual-treatment-received per row**, which is both stronger and immune to
   the flush question.
5. **Frontend changes — checked, and the "nothing else changed" premise is
   false.** `zeeguu/web` history says:
   - **2026-09-27** (the same day as the lexicon deploy), `37cecba9` "Replace Ask
     AI with Explain" rewrote `src/reader/AlterMenu.js` (−57 lines), and touched
     `src/reader/TranslatableWord.js` and `src/reader/InteractiveText.js`;
     `4e27fe96` touched `TranslatableWord.js` again. Release 1.3.7 shipped the
     same day (`db39532c`).
   - **2026-09-23**, `249dc128` "Public shared-article page for recipients
     without an account" added `PublicInteractiveText.js` and
     `publicReaderLogic.js` and touched `TranslatableWord.js` — i.e. a **new
     translation surface, four days before the cut**, with a different
     translation path ("translate by word position, not text", `de6087af`).

   Consequences, and they are not symmetric between the two signals:
   - **"Ungroup expression" lives in `AlterMenu.js`** (`AlterMenu.js:214-215`,
     rendered from `TranslatableWord.js:206 ungroupMwe`), and that menu was
     substantially rewritten on the intervention date. **The
     `user_mwe_override` rate is therefore not comparable across 2026-09-27**,
     which kills it as a secondary outcome for the retrospective design and
     means §4.4's precision-side outcome needs a post-2026-09-27 baseline.
   - **The fusing path itself appears untouched**: inspection of the diffs to
     `InteractiveText.js` and `TranslatableWord.js` on `37cecba9` shows the
     changes are additive (an Explain feature and its modal), with no changes to
     multi-word selection or to `LinkedWordListClass`. So the *positive* signal
     is probably safe. "Probably" is the right word; a reviewer is entitled to
     ask, and the honest answer is that the client changed on the same day.
   - The public-article surface may create bookmarks by a different path. Confirm
     whether those rows enter `bookmark` with `total_tokens > 1` and, if so,
     exclude or flag them.

   Mobile (`zeeguu/mobile`) was **not checked** — no local clone was found.
   **UNVERIFIED.**
6. **Learning, which moves the denominator.** A learner who has learnt
   `finde ud af` stops tapping it at all, so the expression leaves the
   denominator rather than moving from numerator to non-numerator. A share-based
   outcome is blind to this. → Also report the **absolute rate**: hand-fusings
   per 1,000 `TRANSLATE TEXT` events from `user_activity_data`, which the census
   confirms logs every tap including taps that produced no bookmark.
7. **Novelty/engagement effects.** None expected here — the change is invisible
   to users except as better grouping — but note it for §4.4, where an arm
   assignment could in principle interact with anything else shipped in the
   window. → Freeze other MWE-affecting changes for the duration, and record
   what shipped.

### 4.6 Instrumentation that must change before any of this runs

From the census's data inventory, all three currently unrecorded and all three
cheap:

1. `user_mwe_override` records `user_id`, `article_id`, `sentence_hash`,
   `mwe_expression` — but **not which detection layer produced the rejected
   group**, **not the token span**, and **not what the learner accepted
   instead**. All three are needed to make the 130 explicit negatives usable as
   a precision measurement. Add them now; the rows accumulate slowly (130 in
   nine months) so every month of delay is a month of unrecoverable data.
2. **No detector version is stored anywhere.** Add a version or config hash to
   the tokenization cache and to `bookmark`. Without it no future before/after
   analysis is possible at all, and §4.3's per-row treatment classification has
   to be reconstructed by inspecting token streams.
3. **Separated MWEs create no bookmark** (`translation.py:142-152` skips
   `Bookmark.find_or_create` when `is_separated_mwe`). The hardest MWE class is
   therefore invisible in `bookmark`, which is a limitation the paper must
   state and which is worth fixing regardless of the paper.

These three are worth doing **even if the paper is abandoned**, which makes
them the least regrettable item in the plan.

---

## 5. Paper skeleton

### 5.1 Title

Preferred:

> **What Unit Does a Reader Need? Learner Chunking and Multiword Expressions in
> a Deployed Reading Tool**

Alternatives, depending on which finding survives §3:

- *Learners Do Not Chunk Idioms: 13,725 Hand-Fused Spans from Eleven Languages*
  — punchier, commits harder to the negative result, riskier if the MWE fraction
  comes out higher than expected.
- *Hand-Fused Spans: A Learner-Derived Reference for Multiword Expression
  Identification* — resource framing, right title for LREC.

### 5.2 Abstract (draft — every number in it is either measured or marked)

> Multiword expression (MWE) identification is evaluated almost exclusively
> against gold corpora, and where it has been evaluated with learners, the
> judgements were solicited: quizzes, ratings, interviews. We report **unprompted**
> evidence. In a click-to-translate reading tool used by learners of eleven
> languages, the tokenizer proposes MWE groupings and learners may both **fuse**
> adjacent words by hand and **reject** a proposed grouping. Over nine months
> ordinary use produced 13,725 hand-fused spans — 61.7% of 22,253 multi-word
> translation requests, an upper bound since detector successes on discontinuous
> MWEs are not recorded — and 130 explicit rejections. Nobody was asked to
> annotate anything. The per-language hand-fusing rate tracks detector coverage:
> 36.8% for English, which has both a dependency strategy and a curated lexicon,
> against 77.1% for Portuguese, which has neither. But the spans learners fuse
> are mostly **not** MWEs. In a sample of N spans annotated with PARSEME
> categories, only X% are lexicalised MWEs; Y% are analytic grammatical
> constructions that PARSEME does not annotate at any version, and Z% are freely
> compositional phrases fused to read a longer stretch in one interaction —
> confirming, in unprompted behaviour and across eleven languages, a prediction
> the psycholinguistics of formulaic language has made for two decades. We argue
> that the reader's requirement is not MWE-hood but **word-by-word
> translatability**, a language-pair-relative property that MWE annotation does
> not capture and which our annotators agree on more reliably than they agree on
> MWE-hood, and we release the annotated sample as a learner-derived reference.
> [If §4.4 runs: A randomised lexicon expansion across N languages reduced
> hand-fusing by K points, establishing that better identification does reduce
> learner effort.]

### 5.3 Sections, the claim each must support, and the evidence status

| § | Section | Claim it must support | Evidence | Status |
|---|---|---|---|---|
| 1 | Introduction | A click-to-translate reader must commit to a span before translating; getting it wrong is undetectable by the learner | ADR 0004's `fandt ud af` case | **in hand** |
| 2 | Related work | Applied linguistics predicted this; NLP has not absorbed it; the argument for in-tool evaluation is published but unmet at scale; behavioural MWE evidence exists only in the lab. **Must name Savary et al.'s published open questions and say which one each result answers** (§6.1) | §2 | **in hand** |
| 3 | The system | Three-layer detector, per-language strategy table, lexicons; the UI affordances that produce both signals | ADR 0004, source | **in hand** |
| 4 | Two byproduct signals | 13,725 positives / 130 negatives exist, are clean, cheap, and **unprompted** — no task demand, no experimenter, no prompt defining "MWE" | census | **in hand** |
| 4b | The override *rate* | Learners reject only a small fraction of proposed groupings — the quantitative answer, at scale, to Savary et al.'s published false-positive question | 130 overrides **plus a denominator nobody has computed** | **NEEDED (one query)** |
| 5 | The census | Hand-fusing rate tracks detector coverage across 11 languages | census table | **in hand** |
| 6 | **What learners actually fuse** | **Most hand-fused spans are not MWEs; the distribution is dominated by grammatical and processing units** | §3 annotation study | **NEEDED — this is the paper** |
| 7 | Word-by-word translatability | An alternative, operationalisable target with higher IAA than MWE-hood, and a different extension | §3 Axis 2, and the Axis1×Axis2 cross-tab | **NEEDED** |
| 8 | Detector evaluation against a learner reference | Precision/recall of the deployed detector against the annotated sample, per category | §3.7 item 1 | **NEEDED (cheap)** |
| 9 | Causal | Better identification reduces learner effort | §4.4 randomised trial, or §4.3 targeted test | **NEEDED; §4.2 shows the originally planned version cannot deliver it** |
| 10 | Limitations | Separated MWEs invisible so 61.7% is an upper bound; no detector version stored; cache swept at 7 days; self-selected users **and a self-selected affordance**; hand-fusing conflates several motives; UI noise | census blind spots + §1.1 + §6.3 | **partly in hand; discoverability and fuser-proficiency figures NEEDED** |
| 11 | Resource release | The annotated sample, guidelines, and sampling seeds | §3 | **NEEDED** |

**Sections 6 and 7 carry the contribution and neither exists yet.** Sections 4b
and 8 are cheap and also missing. That is the honest state of the work: the
in-hand material is all setup.

### 5.4 What can be written today

A **short position/resource paper** covering §§1–5 + 10, i.e. the census, with
§1.2's reframing stated as a *motivating observation with eleven examples* and
explicitly flagged as not yet measured. That is a 4-page workshop paper. It is
publishable at a workshop and it is weak, because its central claim is the one
it does not measure. **Recommendation: do not write it.** Do sections 6 and 7
first; they are three days of annotation away, and §5.5 shows there is no
imminent MWE-venue deadline to rush for.

### 5.5 Venue and deadline

The calendar was checked; it does **not** support the obvious answer.

| venue | status (checked 2026-09-27) | fit |
|---|---|---|
| **MWE workshop, 23rd edition** | **No CFP, no date, no co-location announced** — checked [multiword.org](https://multiword.org/), [previous events](https://multiword.org/events/previousevents), [siglex.org/events](https://siglex.org/events.html). The 22nd was 28 March 2026 @ EACL 2026, Rabat ([volume](https://aclanthology.org/volumes/2026.mwe-1/), [site](https://multiword.org/mwe2026)); its direct-submission deadline was 27 Dec 2025. **There is no MWE workshop in the [EMNLP 2026 accepted-workshop list](https://2026.emnlp.org/program/workshops/)** (28 workshops). Earliest plausible next edition: mid-2027. | best MWE audience; PARSEME's home, which is also §6's reviewing pool |
| **NLP4CALL** | 14th edition was March 2025 @ NoDaLiDa/Baltic-HLT, Tallinn ([volume](https://aclanthology.org/volumes/2025.nlp4call-1/)); **no 2026 edition exists** in the [venue index](https://aclanthology.org/venues/nlp4call/). A 2027 edition would ride NoDaLiDa 2027 — **verified: 25–28 May 2027, University of Copenhagen, workshop proposals due 16 Nov 2026, notification 7 Dec 2026** ([CFP](https://www.aclweb.org/portal/content/workshop-proposals-26th-nordic-conference-computational-linguistics)). | the Linguse venue; exactly the right readers; **and it would be in Copenhagen, where Zeeguu is** |
| **BEA 2027** | BEA 2026 was the 21st @ ACL 2026. By pattern BEA 2027 attaches to **ACL 2027, Kyoto, 17–22 Aug 2027** (verified: <https://2027.aclweb.org/>; ARR route "January 2027", exact dates TBA). CFP **UNVERIFIED**. | **best actual fit.** [Soliar et al. 2026](https://aclanthology.org/2026.bea-1.14/) just published interaction-log evaluation of a deployed NLP component *at BEA*, so that reviewing pool already accepts the genre. The MWE pool does not yet. |
| **NAACL / COLING 2027 via ARR** | **Verified: ARR submission 12 Oct 2026 → commitment 23 Dec 2026** ([ARR dates](https://aclrollingreview.org/dates)). This is ~2 weeks away. | main-conference venue; the work is not ready and forcing it would waste the idea |
| **EACL 2027 via ARR** | ARR Aug 2026 cycle already closed; commitment 11 Oct 2026 | not available |
| **LREC** | LREC 2026 happened ([event index](https://aclanthology.org/events/lrec-2026/), 945 main papers). Biennial pattern implies 2028; **no announcement — UNVERIFIED**. | right home for the released dataset, but two years out is too slow to be the primary target |
| **READIxTSAR @ LREC** | the workshop where [Kalinina et al. 2026](https://aclanthology.org/2026.readi-1.14/) published | worth watching; §6.1a's group's venue |

**Revised recommendation — this supersedes the "MWE workshop first" instinct:**

1. **Primary target: BEA 2027 @ ACL 2027 (Kyoto, 17–22 Aug 2027).** The reviewing
   pool has just accepted a log-based evaluation of a deployed NLP component
   (Soliar et al.), which is exactly this paper's genre. §2.5 concluded the NLP
   audience is the one to aim at; BEA is the NLP audience least likely to reject
   on "logs are too noisy". Submission is via ARR around January 2027, which
   fits the schedule below comfortably.
2. **Secondary, and strategically interesting: propose or join NLP4CALL 2027 at
   NoDaLiDa 2027 in Copenhagen.** Workshop proposals are due **16 November
   2026** — a hard, verified, near date. NoDaLiDa 2027 is *in Copenhagen*, where
   Zeeguu and ITU are. Hosting or co-organising the CALL workshop at a
   local NoDaLiDa is a cheap, high-leverage move that also puts Zeeguu in the
   room with the Linguse community. Worth a decision in the next six weeks
   independently of the paper.
3. **Do not target the MWE workshop as the primary venue.** Not because of the
   reviewing pool — §6 says engaging it is a correctness requirement, not a
   hazard — but because **there is no announced edition to target**, and waiting
   for one would idle the work for a year with no compensating benefit. Submit
   there later if a 2027 edition materialises, or send the PARSEME-facing
   *resource* paper there.
4. **Do not force the ARR 12 Oct 2026 cycle.** Two weeks is not enough for §3,
   and §5.4 explains why the census-only version of the paper should not be
   written.
5. **Plan an LREC (2028?) resource paper** for the dataset once it exists.

**Schedule**, working back from an ARR submission in January 2027:

| by | milestone |
|---|---|
| **early Oct 2026** | 50-span Danish pilot (§7 condition 3); PARSEME 2.0 label check; measure the override denominator and the §4.3 targeted-subset size |
| **mid-Oct 2026** | guidelines finalised after the pilot; calibration round with all annotators |
| **late Oct 2026** | §4.4 randomised lexicon expansion pre-registered and shipped (so it completes ~2 months later) |
| **16 Nov 2026** | NoDaLiDa 2027 workshop-proposal deadline — decide on NLP4CALL |
| **late Nov 2026** | annotation complete (610 + 200 + 162 events) |
| **Dec 2026** | §3.7 offline detector evaluation; §4.4 readout |
| **Jan 2027** | draft complete, ARR submission |

---

## 6. Exposure and risk

### 6.1 The risk is not being scooped. It is being reviewed by the people whose open questions this answers.

The census's framing — "Savary's group is one iteration from doing this" — is
**wrong on the facts**, and the correct diagnosis is a different and more
tractable problem.

**Why the scoop risk is low.** Checked across the ACL Anthology author page, HAL
(which French CNRS researchers are mandated to deposit to; 131 records), the
arXiv API and Semantic Scholar:

- **No deployment at any comparable scale.** Linguse is a third-party
  commercial six-language reader (<https://linguse.com/>, no published user
  count). The book chapter states MWE identification "is not yet implemented"
  for anything but French.
- **Their own intrinsic numbers argue for Zeeguu's point.** WiktSeen mines
  87,767 French MWEs from Wiktionary and scores **F1 0.776** on French
  Sequoia — but **0.929** on MWEs present in both Wiktionary and the corpus and
  only **0.535** on the Wiktionary-only expansion (624 occurrences of 8,716).
  So the lexicon-driven paradigm performs near chance exactly where it goes
  beyond the existing gold corpus. That is a coverage argument, and it is
  orthogonal to whether the covered units are the ones learners want — which is
  the gap this paper occupies.
- **The extrinsic evaluation was smaller than the census assumed.** The
  NLP4CALL paper reports 12 B1 students at the University of Warsaw; the 2026
  book chapter discloses that **only 7 of 12 completed**, run "one cohort (2
  students) at a time".
- **No personnel.** Überrück-Fries built WiktSeen on a single Paris-Saclay
  internship grant and appears in no subsequent publication. Dryjańska is a
  didactician, not someone running a deployment.
- **No funding line pointing here.** COST Action UniDive (CA21167) — the funder
  behind the chapter — ran to **22 September 2026 and has expired**. Its four
  working groups contain no CALL, learner-data or user-study strand. SELEXINI
  (ANR-21-CE23-0033-01) is a corpus/lexicon project.
- **No stated intent to use logs.** Their own roadmap, verbatim from the
  chapter's §10: "Perspectives for future work include the **extension of the
  experiments to larger numbers of learners**, at various learning levels" —
  i.e. bigger classroom quizzes. The word "log" appears in neither document.
  NLP4CALL 2024's future work is (i) more intrinsic dev data via PARSEME, (ii)
  more filters, (iii) more languages.
- **Their programme has visibly rotated elsewhere.** Savary's 2025–26 output is
  PARSEME 2.0, the PARSEME 2.0 corpus (LREC 2026), diversity quantification, and
  French ModernBERT. Nothing learner-facing.

Getting to 13,725 unprompted fusion events is not one iteration away; it is a
multi-year traffic problem they have not begun.

**Why the review risk is high, and this is the real exposure.** §9 of
[the 2026 book chapter](https://zenodo.org/records/21277679)
(Dryjańska, Überrück-Fries & Savary, in Barbu Mititelu & Giouli (eds.),
*Multiword expressions in Natural Language Processing*, Language Science Press,
pp. 225–254, <https://doi.org/10.5281/zenodo.21277679>) is, functionally, the
reviewer form for this paper. They have staked the questions in print:

> "the necessity to establish a benchmark for key metrics such as F-score,
> precision, and recall, in order to evaluate the level of identification and
> annotation of MWEs appropriate for FLT/L purposes. **To the best of our
> knowledge, no such benchmarks exist currently.**"

> "A new research question that has emerged from this study is: **Do false
> positives have a more detrimental effect than false negatives in the context
> of language teaching applications?**"

> "there is a need to explore what types of 'minor annotation errors' can be
> identified and tolerated by learners compared to 'real errors'"

> "An optimal F-measure might not be the right quality criterion. Weighing
> precision vs. recall, depending on the learners vs. teachers perspectives,
> might be considered instead."

> "we observed that non-verbal MWEs (nominal, adjectival, adverbial, and
> functional) may display opposite tendencies […] This brings the literal vs.
> idiomatic disambiguation problem back to the front."

> "**the evaluation scenario seems insightful and applicable on a larger
> scale.**"

Zeeguu's 130 `user_mwe_override` rows are an operationalisation of their
false-positive question. ADR 0004's "precision beats recall" constraint is an
answer to it. **If the related work does not name these questions and say "they
asked; we answer with n = 13,725", a reviewer from the PARSEME/UniDive orbit —
and on an MWE paper there will be one — will read this as a replication that
failed to read the literature.** That is the failure mode to engineer against.
Engineering against it is cheap and improves the paper: cite them as the source
of the question, not as competition.

### 6.1a A competitor the census does not mention, and which is closer

**Kalinina, François, Vassiliadou & Todirascu (2026)**, "A Learner-Oriented
Annotated Resource of French Multiword Expressions for Text Adaptation in
Foreign Language Reading", READIxTSAR @ LREC 2026,
<https://aclanthology.org/2026.readi-1.14/>. ~2,700 French MWEs with CEFR
proficiency levels, distinguishing idioms, opaque collocations and **transparent
collocations**, aimed at text adaptation and educational NLP.

Two things matter here.

1. **On MWE-for-L2 this group (Strasbourg/Louvain, and the lineage behind the
   4,525-MWE L2 corpus that Savary's own paper used) is currently more active
   than Savary's.** They are building learner-oriented MWE resources now. They
   are the more likely source of a competing paper, and the census missed them.
2. **They report only moderate inter-annotator agreement, attributed to "the
   gradient nature of phraseological opacity in language learning contexts."**
   That is expert annotators failing to agree on precisely the boundary
   Zeeguu's learners are drawing with their fingers. **The contrast is a
   finding**: where experts disagree gradiently, learners act decisively, and
   what they act on can be measured. Set §3's IAA numbers against theirs
   explicitly.

### 6.2 What is and is not exposed

**Exposed — do not build the paper on these:**

- *The argument* that in-tool evaluation is needed. Published by them in 2024.
  Zeeguu cannot contribute it.
- *A descriptive census alone.* Any deployed reader with a fuse affordance could
  produce a hand-fusing rate. The number is not the contribution.
- *A per-language recall story.* Also the thing that §1.2 shows is wrong.

- ***Multilinguality.* This is the weakest card and the census overrates it.**
  The book chapter says other languages "are already covered by Linguse" and
  WiktSeen "should be adaptable to at least those languages for which the
  corresponding Wiktionary modules are rich enough". 11 languages against their 6
  is an engineering delta, not a contribution. **Do not lead with it.** Use it
  only as a robustness claim: the divergence between learner chunking and
  lexicon MWE-hood holds across 11 typologically varied languages.

**Not readily reproducible by them, on any short timescale:**

- **Unpromptedness.** This is the strongest card and it should be first in the
  paper. Every extrinsic MWE evaluation in the literature — theirs, Lee &
  Uvaliyev's, Kalinina et al.'s — is a *solicited* judgement: a quiz, a rating
  task, an expert annotation, an interview. Zeeguu's 13,725 fusions are
  unprompted: no task demand, no Hawthorne effect, no experimenter, no prompt
  telling the learner what an MWE is. **Learners as unwitting annotators, and
  fusion as revealed preference over what counts as a unit worth one
  translation.** Nobody has claimed this.
- **Deployment scale, stated as a ratio rather than a count.** 13,725 unprompted
  decisions against 7 completed participants is three orders of magnitude. But
  scale alone reads as a resource paper and invites "so what" — it earns its
  place only because it makes the *distributional* claims of §1.2 possible.
- **The explicit-negative signal.** `user_mwe_override` requires a UI affordance
  for *rejecting* a grouping; nothing in the Linguse papers describes one (their
  learners only received pushed annotations). **Reframe 130 as a rate, not a
  dataset.** If a low single-digit percentage of proposed groupings is ever
  overridden, that quantitatively confirms at scale the tolerance-for-noise
  claim they could only assert from three interviews — a citable, respectful,
  empirically superior replication, and the direct answer to their
  false-positive question. **This requires a denominator that nobody has
  computed: how many groupings were *proposed* over the same period.** Without
  it, 130 is uninterpretable and a reviewer will say so. Recoverable from
  `bookmark` (`is_mwe = 1` rows) as a lower bound, better from the tokenization
  path. **Add this to the immediate to-do list.**
- **The ability to randomise in production** (§4.4). A causal estimate of
  detector quality on learner effort is not obtainable from a questionnaire
  study, and it is the strongest single claim available here.
- **The reframing as a measured distribution** (§1.2), quantified across 11
  languages from in-the-wild behaviour.

### 6.3 What would make it defensible

In priority order:

1. **Lead with unpromptedness, then the reframing.** "Learners produced 13,725
   unprompted grouping decisions, which constitute revealed preference over what
   counts as a chunk worth one translation" is the sentence the paper is built
   on. It is the only claim in the list nobody else has made, and it costs
   nothing to make.
2. **Do the annotation study and release the dataset.** A resource must be
   redone, not argued with. It is also the only thing that makes §1.2 real, and
   §6.4 notes it could equally falsify it.
3. **Run the randomised intervention** (§4.4), pooled across languages, ~2
   months. Supplies the causal claim; uncopyable.
4. **Lead with `wbw_adequate`, not with MWE recall.** Proposing a *different
   target* is a contribution an intrinsic-evaluation group cannot make from gold
   corpora, and it makes the relationship with PARSEME complementary rather than
   competitive — which turns reviewers from that community into allies rather
   than defenders.
5. **Cite Savary's group as the source of the questions being answered**
   (§6.1). This is the single cheapest risk reduction available and it is a
   correctness issue, not a politeness one.
6. **Consider collaborating rather than racing.** §3.6 needs a trained French
   MWE annotator; both Savary's group and Kalinina/Todirascu's have them, and
   the latter has a French MWE resource with CEFR levels that would slot
   directly into §3.4. A joint paper is strictly better than a race, and Zeeguu
   brings exactly what they lack. **Recommendation: write the guidelines, run
   the Danish and English strata first so there is a finished protocol to bring,
   then approach.** Approaching with a protocol is a collaboration; approaching
   with an idea is a gift. Note the scoop risk is low enough (§6.1) that there is
   time to do this properly.

**Three things that will kill the paper if unaddressed**, and none of them is in
the census:

1. **No gold standard** — without §3's annotated subsample the whole argument is
   unfalsifiable. This is the same point as §5.3 but it is worth saying as a
   risk: it is not a nice-to-have section, it is the load-bearing one.
2. **Selection bias in the affordance itself.** Only learners who *discovered*
   the fuse gesture use it. Report its discoverability (what share of users with
   any bookmarks ever fused), and the proficiency distribution of fusers versus
   non-fusers — proficiency is the obvious confound on what gets fused, and
   Zeeguu has a CEFR-ish signal per user. If fusers are systematically lower
   proficiency, the compositional-chunking finding may be a beginner
   phenomenon, which is still interesting but is a different claim.
3. **UI noise in the 13,725.** Accidental drags, overshoots and double-taps.
   Say explicitly how they were filtered. Axis 3's `MISTAP` label (§3.4) gives an
   estimate of the residual rate from the annotated sample; use it to bound the
   contamination and report it.

### 6.4 Other risks

- **The annotation study could falsify the reframing.** If the MWE fraction
  comes out at 45% rather than 15%, the interesting reframing evaporates and
  what is left is a fairly ordinary recall-gap paper — which is worth much less
  and is closer to what Linguse already did. **This is a real possibility and
  the study must be run as a test, not as a confirmation.** Pre-register the
  prediction (MWE fraction below 30% in the token frame, in every Tier A
  language) so the result is informative either way.
- **IAA could come out too low to publish.** Axis 1 has 13 labels and
  boundaries (`COLL`/`FREE`, `GRAM`/`LVC`) that are genuinely hard. §3.5's
  pre-registered revision round is the mitigation; the fallback is to report
  only the collapsed binary and Axis 2.
- **Self-selection.** Zeeguu users are not a random sample of learners; the
  users who fuse by hand are not a random sample of Zeeguu users. Every rate
  here is conditional on both. State it; do not attempt to correct it.
- **The census's own blind spots** limit what can be claimed: separated MWEs are
  invisible, no detector version is recorded, and the tokenization cache is
  swept weekly so historical detector output cannot be reconstructed (§4.6).
- **Ethics and consent.** This is user interaction data. Before publishing,
  confirm what Zeeguu's terms permit, whether released spans can contain
  identifying context, and whether ethics review is needed at ITU. Release
  spans and sentences, never user identifiers; check that sampled sentences
  contain no personal content. **UNVERIFIED — must be resolved before any
  release, and it gates §3's resource contribution, not just the ethics
  section.**

---

## 7. Decision

**There is a paper here.** It is not the census, and it is not the natural
experiment. It is the annotation study plus a randomised intervention, framed
as *the reader's unit is not the linguist's unit*, with the census as
motivation and scale as the defence.

§2 is settled: the reframing survives, as an NLP-facing measurement of a
prediction applied linguistics already made. §6 is settled: the scoop risk is
low, the review risk is high and cheap to fix. What is not settled is whether the
measurement comes out the way §1.2 expects.

**Go conditions** — all three should hold before committing serious time:

1. The pre-registered MWE-fraction prediction survives a **pilot of 50 Danish
   spans** — one afternoon's work, and it de-risks the whole study. If the pilot
   comes out near 45% MWE, stop and rethink the framing before annotating 610.
2. Annotators are secured for at least **da, en, de and one of {fr, nl, sv}**.
   Without a fourth language it is a case study, not a multilingual finding.
3. Ethics and data-release constraints permit publishing spans with sentence
   context (§6.4). This gates the resource contribution, which §6.3 ranks second.

**Stop conditions:**

- The pilot shows the MWE fraction is high (§6.4) **and** no alternative framing
  survives. In that case the honest outcome is a short system-and-census note,
  or nothing.
- Annotators cannot be found for a fourth language.
- *(Not a live stop condition, contrary to the briefing: being scooped by
  Savary's group. §6.1 shows they have neither the data, the people, the funding
  nor the stated intent. Watch Kalinina/Todirascu instead.)*

**Do immediately, regardless of the paper** (§4.6): record the rejected
grouping's layer, token span and accepted replacement on `user_mwe_override`;
store a detector version; and decide whether separated MWEs should create
bookmarks. Every week without these is data that cannot be recovered later.

**Do next, in order:**

1. **The 50-span Danish pilot** (condition 1) — one afternoon, decides everything.
2. **Compute the override denominator** — how many groupings were *proposed* over
   the same period as the 130 rejections. Without it the 130 is uninterpretable
   (§6.2), and this is the number that answers Savary et al.'s published
   false-positive question. One read-only query.
3. **Measure the §4.3 targeted-subset size** — decides whether the retrospective
   test exists at all.
4. **Measure the affordance's discoverability and the proficiency profile of
   fusers vs non-fusers** (§6.3 killer 2). If fusers are systematically lower
   proficiency, the claim changes shape and it is much better to know now.
5. **Quantify the separated-MWE undercount** from `user_activity_data` (§1.1) so
   the headline number can be stated as a bound rather than a point.
6. Check the PARSEME 2.0 non-verbal label names and map `ADVPREP`/`NOM`/`FUNC`
   onto them (§3.4 rule 5).
7. **Decide on NLP4CALL 2027 at NoDaLiDa 2027 in Copenhagen — proposals due
   16 November 2026** (§5.5). Worth doing on its own merits.
8. Secure annotators (§3.6), French first; consider approaching
   Kalinina/Todirascu or Savary with the finished protocol (§6.3 item 6).
